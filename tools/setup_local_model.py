"""
ネオ秘書くん - ローカルLLM (LFM2.5) セットアップツール
(tools/setup_local_model.py)

初回起動時に LFM2.5 GGUF モデルを Hugging Face からダウンロードし、
models/ へ配置して .env にローカル推論設定を永続化する。

モデルカタログ:
    - 350m (推奨・超軽量モード): LFM2.5-350M QAD-Q4_0 (約230MB)
    - 1.2b (高品質モード):       LFM2.5-1.2B-Instruct QAD-Q4_0 (約770MB)

ライセンス: LFM Open License v1.0 (年間収入 $10M 未満の商用利用可 / 出典明記必須)
    https://huggingface.co/LiquidAI/LFM2.5-350M-GGUF/blob/main/LICENSE

使い方:
    python tools/setup_local_model.py              # 対話式選択
    python tools/setup_local_model.py --model 350m # 非対話（超軽量モード）
    python tools/setup_local_model.py --model 1.2b # 非対話（高品質モード）
    python tools/setup_local_model.py --list       # カタログ表示のみ
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Optional, Callable

import requests
from dotenv import set_key

# モデルと .env はアプリデータ配置ポリシーに従い書き込みルートへ (frozen時は exe 直下)
import app_paths

PROJECT_ROOT = app_paths.get_app_root()
MODELS_DIR = PROJECT_ROOT / "models"
ENV_PATH = PROJECT_ROOT / ".env"

# ダウンロード時の最低妥当サイズ（これ未満はHTMLエラーページ等の可能性があり破損扱い）
MIN_VALID_BYTES = 100 * 1024 * 1024

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("setup_local_model")

# =============================================================================
# モデルカタログ（Hugging Face 公式GGUF・QAD=量子化認識蒸留版で高精度）
# =============================================================================
MODEL_CATALOG: Dict[str, Dict[str, object]] = {
    "350m": {
        "repo_id": "LiquidAI/LFM2.5-350M-GGUF",
        "filename": "LFM2.5-350M-QAD-Q4_0.gguf",
        "display_name": "超軽量モード (LFM2.5-350M・約230MB)",
        "description": "大体のPCでサクサク動く推奨サイズ。応答は最速。",
        "recommended": True,
    },
    "1.2b": {
        "repo_id": "LiquidAI/LFM2.5-1.2B-Instruct-GGUF",
        "filename": "LFM2.5-1.2B-Instruct-QAD-Q4_0.gguf",
        "display_name": "高品質モード (LFM2.5-1.2B-Instruct・約770MB)",
        "description": "より賢い応答。4GB RAM以上のPC向け。",
        "recommended": False,
    },
}


def build_download_url(repo_id: str, filename: str) -> str:
    """Hugging Face のダウンロードURLを組み立てる。

    Args:
        repo_id: Hugging Face リポジトリID (例: 'LiquidAI/LFM2.5-350M-GGUF')
        filename: リポジトリ内のGGUFファイル名

    Returns:
        ダウンロードURL
    """
    return f"https://huggingface.co/{repo_id}/resolve/main/{filename}"


def fetch_remote_size(url: str, timeout: float = 30.0) -> Optional[int]:
    """HEADリクエストでリモートファイルのサイズを取得する。

    Args:
        url: ダウンロードURL
        timeout: タイムアウト秒数

    Returns:
        ファイルサイズ (バイト数)。取得できない場合は None。
    """
    try:
        resp = requests.head(url, allow_redirects=True, timeout=timeout)
        length = resp.headers.get("Content-Length")
        return int(length) if length else None
    except (requests.RequestException, ValueError) as e:
        logger.warning(f"リモートサイズの取得に失敗（スキップして続行）: {e}")
        return None


def download_model(
    model_key: str, 
    models_dir: Path = MODELS_DIR,
    progress_callback: Optional[Callable[[int, Optional[int], int], None]] = None
) -> Path:
    """カタログ指定のモデルを Hugging Face からダウンロードする。

    進捗はログに出力し、ダウンロード後はサイズ妥当性を検証する。
    既に同一名のファイルが存在しサイズが一致する場合は再ダウンロードをスキップする。

    Args:
        model_key: カタログキー ('350m' または '1.2b')
        models_dir: 保存先ディレクトリ
        progress_callback: 進捗コールバック (downloaded_bytes, total_bytes, percentage)

    Returns:
        保存されたGGUFファイルのパス

    Raises:
        KeyError: model_key がカタログに存在しない場合
        RuntimeError: ダウンロードまたは検証に失敗した場合
    """
    entry = MODEL_CATALOG[model_key]
    repo_id: str = str(entry["repo_id"])  # type: ignore[assignment]
    filename: str = str(entry["filename"])  # type: ignore[assignment]
    url = build_download_url(repo_id, filename)
    dest = models_dir / filename

    models_dir.mkdir(parents=True, exist_ok=True)

    remote_size = fetch_remote_size(url)
    if dest.exists() and remote_size and dest.stat().st_size == remote_size:
        logger.info(f"✅ 既にダウンロード済み（サイズ一致）: {dest.name}")
        if progress_callback:
            progress_callback(remote_size, remote_size, 100)
        return dest

    logger.info(f"⬇ ダウンロード開始: {entry['display_name']}")
    logger.info(f"   URL: {url}")
    tmp_path = dest.with_suffix(dest.suffix + ".part")

    try:
        with requests.get(url, stream=True, timeout=(30.0, 120.0)) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", 0)) or None
            downloaded = 0
            last_logged_pct = -10
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = int(downloaded * 100 / total)
                            if pct >= last_logged_pct + 5:
                                logger.info(f"   {pct}% ({downloaded / (1024 * 1024):.0f}MB / {total / (1024 * 1024):.0f}MB)")
                                last_logged_pct = pct
                            if progress_callback:
                                progress_callback(downloaded, total, pct)
                        else:
                            if progress_callback:
                                progress_callback(downloaded, None, 0)
        logger.info(f"   100% ({downloaded / (1024 * 1024):.0f}MB) ダウンロード完了")
        if progress_callback and total:
            progress_callback(downloaded, total, 100)
    except requests.RequestException as e:
        if tmp_path.exists():
            tmp_path.unlink()
        raise RuntimeError(f"ダウンロードに失敗しました: {e}") from e

    # 妥当性検証: 最低サイズ + リモートサイズとの一致
    actual_size = tmp_path.stat().st_size
    if actual_size < MIN_VALID_BYTES:
        tmp_path.unlink()
        raise RuntimeError(
            f"ダウンロードされたファイルが異常に小さい ({actual_size} bytes)。"
            f"ネットワーク環境またはURLを確認してください: {url}"
        )
    if remote_size and actual_size != remote_size:
        tmp_path.unlink()
        raise RuntimeError(
            f"ファイルサイズが一致しません (期待: {remote_size}, 実際: {actual_size})。"
            "ダウンロードが中断された可能性があります。再実行してください。"
        )

    tmp_path.replace(dest)  # os.replace: Windowsでも既存ファイルをアトミックに上書き
    logger.info(f"✅ 保存完了: {dest}")
    return dest


def apply_env_config(model_filename: str, env_path: Path = ENV_PATH) -> None:
    """.env にローカル推論設定を永続化する（既存キーは上書き）。

    Args:
        model_filename: models/ に配置したGGUFファイル名
        env_path: .env ファイルのパス
    """
    if not env_path.exists():
        env_path.touch()
    set_key(str(env_path), "LOCAL_GGUF_MODEL", model_filename)
    set_key(str(env_path), "DEFAULT_LLM_PROVIDER", "local_gguf")
    logger.info(f"✅ .env を更新しました: LOCAL_GGUF_MODEL={model_filename}, DEFAULT_LLM_PROVIDER=local_gguf")


def setup_model(model_key: str) -> Path:
    """モデルのダウンロードから .env 永続化までの一連のセットアップを実行する。

    Args:
        model_key: カタログキー ('350m' または '1.2b')

    Returns:
        保存されたGGUFファイルのパス

    Raises:
        KeyError: model_key がカタログに存在しない場合
        RuntimeError: ダウンロードに失敗した場合
    """
    if model_key not in MODEL_CATALOG:
        raise KeyError(f"不明なモデルキー: {model_key} (選択肢: {', '.join(MODEL_CATALOG)})")
    dest = download_model(model_key)
    apply_env_config(dest.name)
    return dest


def prompt_model_selection() -> str:
    """対話式でモデルを選択させる（start.bat 経由の初回セットアップ用）。

    Returns:
        選択されたカタログキー
    """
    print()
    print("=== ネオ秘書くん ローカルAIモデル セットアップ ===")
    for key, entry in MODEL_CATALOG.items():
        mark = "⭐推奨" if entry.get("recommended") else "    "
        print(f"  [{key}] {mark} {entry['display_name']}")
        print(f"         {entry['description']}")
    print()

    while True:
        choice = input("どのモデルをセットアップしますか？ [350m/1.2b] (Enter=350m): ").strip().lower()
        if choice == "":
            return "350m"
        if choice in MODEL_CATALOG:
            return choice
        print("⚠ '350m' または '1.2b' を入力してください。")


def main() -> int:
    """CLIエントリポイント。

    Returns:
        int: 成功時 0、失敗時 1。
    """
    parser = argparse.ArgumentParser(description="LFM2.5 ローカルモデルのセットアップ")
    parser.add_argument("--model", choices=list(MODEL_CATALOG), help="非対話でモデルを指定")
    parser.add_argument("--list", action="store_true", help="カタログを表示して終了")
    args = parser.parse_args()

    if args.list:
        for key, entry in MODEL_CATALOG.items():
            mark = " (推奨)" if entry.get("recommended") else ""
            print(f"{key}: {entry['display_name']}{mark} - {entry['description']}")
        return 0

    try:
        model_key = args.model if args.model else prompt_model_selection()
        dest = setup_model(model_key)
        print()
        print(f"🎉 セットアップ完了！ モデル: {dest.name}")
        print("   ネオ秘書くんを起動すると、オフラインのローカルAI (local_gguf) が有効になります。")
        return 0
    except (RuntimeError, KeyError) as e:
        logger.error(f"セットアップに失敗しました: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
