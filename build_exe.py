"""
ネオ秘書くん - 配布パッケージビルドスクリプト (build_exe.py)

PyInstaller (onedir) で NeoHisho.exe をビルドし、機密ファイル混入スキャンを
通過させた上で、社内配布用の zip を作成するオーケストレーター。

実行方法 (ボス手動 — PowerShell):
    venv\\Scripts\\python.exe build_exe.py

成果物:
    dist/NeoHisho/                     ... アプリ一式 (onedir)
    dist/NeoHisho_v{version}_win64.zip ... 社内配布用アーカイブ
"""

import hashlib
import logging
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
APP_DIR = DIST_DIR / "NeoHisho"
SPEC_FILE = PROJECT_ROOT / "neo_hisho.spec"

# 機密混入スキャンの対象 (配布zipに絶対に含めてはいけないファイル)
SECRET_PATTERNS = (
    ".env",
    ".sync_token",
    "neo_secretary.db",
    "google_token.json",
    "google_credentials.json",
)
SECRET_EXTENSIONS = (".gguf", ".db", ".db-wal", ".db-shm")

logger = logging.getLogger("build_exe")


def _setup_logging() -> None:
    """ロギングの初期設定を行う (コンソール表示用)。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def ensure_pyinstaller() -> None:
    """PyInstaller が無ければ venv へ自動インストールする。

    Raises:
        RuntimeError: インストールに失敗した場合。
    """
    try:
        import PyInstaller  # noqa: F401
        logger.info("PyInstaller は既に導入済みです")
        return
    except ImportError:
        logger.info("PyInstaller が未導入のため venv へインストールします...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "pyinstaller"],
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            raise RuntimeError("PyInstaller のインストールに失敗しました")
        logger.info("PyInstaller のインストールが完了しました")


def clean_previous_build() -> None:
    """前回のビルド成果物 (build/ と dist/NeoHisho) を削除する。"""
    for target in (BUILD_DIR, APP_DIR):
        if target.exists():
            logger.info(f"前回成果物を削除: {target}")
            shutil.rmtree(target)


def run_pyinstaller() -> None:
    """neo_hisho.spec を使って onedir ビルドを実行する。

    Raises:
        RuntimeError: PyInstaller が非ゼロ終了した場合。
    """
    logger.info("PyInstaller ビルドを開始します (数分かかります)...")
    result = subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            str(SPEC_FILE),
            "--noconfirm",
            "--clean",
        ],
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode != 0:
        raise RuntimeError(f"PyInstaller が失敗しました (returncode={result.returncode})")
    if not (APP_DIR / "NeoHisho.exe").exists():
        raise RuntimeError(f"NeoHisho.exe が生成されませんでした: {APP_DIR}")
    logger.info(f"ビルド完了: {APP_DIR}")


def scan_secrets() -> Tuple[List[Path], List[Path]]:
    """配布物に機密ファイルが混入していないかを走査する。

    Returns:
        Tuple[List[Path], List[Path]]: (見つかった機密ファイル, 大容量警告対象)

    Raises:
        RuntimeError: 機密ファイルが混入していた場合 (配布禁止)。
    """
    found_secrets: List[Path] = []
    large_files: List[Path] = []
    for path in APP_DIR.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if name in SECRET_PATTERNS:
            found_secrets.append(path)
        elif path.suffix.lower() in SECRET_EXTENSIONS:
            found_secrets.append(path)
        elif path.suffix.lower() == ".gguf" or path.stat().st_size > 200 * 1024 * 1024:
            large_files.append(path)
    if found_secrets:
        for p in found_secrets:
            logger.error(f"機密ファイル混入！配布禁止: {p}")
        raise RuntimeError("機密ファイルが dist に混入しています。ビルド設定を確認してください。")
    for p in large_files:
        logger.warning(f"大容量ファイルが含まれています (同梱意図を確認): {p}")
    logger.info("機密混入スキャン: 問題なし (OK)")
    return found_secrets, large_files


def make_zip() -> Path:
    """dist/NeoHisho を社内配布用 zip にアーカイブする。

    Returns:
        Path: 生成された zip ファイルのパス。

    Raises:
        RuntimeError: zip 作成に失敗した場合。
    """
    sys.path.insert(0, str(PROJECT_ROOT))
    from version import __version__  # Single Source of Truth から取得

    zip_path = DIST_DIR / f"NeoHisho_v{__version__}_win64.zip"
    if zip_path.exists():
        zip_path.unlink()
    logger.info(f"zip 作成中: {zip_path}")
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for path in sorted(APP_DIR.rglob("*")):
                if path.is_file():
                    arcname = Path("NeoHisho") / path.relative_to(APP_DIR)
                    zf.write(path, arcname=str(arcname))
    except OSError as e:
        raise RuntimeError(f"zip 作成に失敗しました (ファイルロック確認): {e}")
    logger.info(f"zip 作成完了: {zip_path}")
    return zip_path


def print_summary(zip_path: Path) -> None:
    """ビルド結果のサマリ (サイズ・SHA256) を出力する。"""
    zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
    sha256 = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    logger.info("=" * 60)
    logger.info("🎉 ビルド成功！")
    logger.info(f"  アプリ一式 : {APP_DIR}")
    logger.info(f"  配布zip    : {zip_path} ({zip_size_mb:.1f} MB)")
    logger.info(f"  SHA256     : {sha256}")
    logger.info("配布手順: INSTALL_GUIDE.md を添えて zip を配布してください")
    logger.info("=" * 60)


def main() -> int:
    """ビルドの全工程を実行するエントリポイント。

    Returns:
        int: 終了コード (0=成功, 1=失敗)。
    """
    _setup_logging()
    try:
        ensure_pyinstaller()
        clean_previous_build()
        run_pyinstaller()
        scan_secrets()
        zip_path = make_zip()
        print_summary(zip_path)
        return 0
    except RuntimeError as e:
        logger.error(f"ビルド失敗: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
