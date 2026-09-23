"""
ネオ秘書くん - アプリケーションパス解決 (app_paths.py)

PyInstaller でビルドした実行ファイル (frozen) 環境と、リポジトリ直下で
直接実行する開発環境 (python main.py) の両方で、リソース（読み取り専用）と
ユーザーデータ（書き込み可能）の正しい配置場所を「唯一の情報源」として解決する。

配置ポリシー (onedir 配布):
- 読み取り専用リソース (web_pet/, assets/, docs/, .env.example):
  PyInstaller の _internal/ に同梱され、get_resource_root() から参照する。
- 書き込み可能データ (DB, .env, models/, backups/, 各種設定JSON):
  exe と同じフォルダ（ポータブル運用）に置かれ、get_app_root() から参照する。
  アップデート時にアプリ一式を差し替えてもユーザーデータが消失しない。

データ境界ポリシー (ADR-2 / P0-4 2026-09-23):
- **暗号鍵・DB・マスタートークン** (DB は VAPID 秘密鍵と承認監査ログを内包する) は
  ``get_data_root()`` (既定 ``%LOCALAPPDATA%\\NeoHisho``) 配下にのみ配置する。
  OneDrive / Dropbox 等のクラウド同期フォルダは gitignore では守れないため**配置禁止**。
- 旧配置 (リポジトリ/exe 直下) からの移行は ``migrate_legacy_data()`` が
  SQLite Online Backup API で一貫スナップショットを作成し、旧ファイルは
  ``migration_archive/`` へ**退避（移動）**する（削除はしない）。
"""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

logger = logging.getLogger(__name__)

# 環境設定ファイルのファイル名
ENV_NAME: str = ".env"
ENV_EXAMPLE_NAME: str = ".env.example"

# AppData フォールバック時のアプリ専用ディレクトリ名
FALLBACK_DIR_NAME: str = "NeoHisho"

# get_app_root() の決定結果キャッシュ (プロセス内で書き込み判定は一度だけ実施する)
_APP_ROOT_CACHE: Optional[Path] = None

# =============================================================================
# データ境界 (ADR-2: 暗号鍵・DB をクラウド同期フォルダへ置かない)
# =============================================================================

# データルートを明示上書きする環境変数 (テスト隔離・運用切替用)
DATA_DIR_ENV_VAR: str = "NEO_HISHO_DATA_DIR"

# データルートのディレクトリ名 (%LOCALAPPDATA%\<これ> / ~/.local/share/<これ>)
DATA_DIR_NAME: str = "NeoHisho"

# データルート配下のファイル名・ディレクトリ名 (単一情報源)
DB_FILENAME: str = "neo_secretary.db"
SYNC_TOKEN_FILENAME: str = ".sync_token"
BACKUPS_DIR_NAME: str = "backups"
MIGRATION_ARCHIVE_DIR_NAME: str = "migration_archive"

# クラウド同期フォルダのパス構成要素マーカー (小文字比較・完全一致/prefix)
_CLOUD_SYNC_PART_MARKERS = (
    "dropbox",
    "google drive",
    "googleドライブ",
    "icloud drive",
    "box",
    "sharepoint",
    "nextcloud",
)
_CLOUD_SYNC_PART_PREFIXES = ("onedrive", "icloud")
# 独自フォルダ名 (SkyDrive 等) を検知するための環境変数
_CLOUD_SYNC_ENV_VARS = (
    "OneDrive",
    "OneDriveCommercial",
    "OneDriveConsumer",
    "Dropbox",
    "GoogleDrive",
)

# get_data_root() の決定結果キャッシュ
_DATA_ROOT_CACHE: Optional[Path] = None


def reset_path_caches() -> None:
    """パス解決のプロセス内キャッシュを破棄する (テスト・環境変数変更用)。

    本関数は ``get_app_root()`` / ``get_data_root()`` が保持するキャッシュを
    初期化し、次の呼び出しで環境変数を再評価させる。テストの
    setUp / tearDown から呼び出すことを想定している。
    """
    global _APP_ROOT_CACHE, _DATA_ROOT_CACHE
    _APP_ROOT_CACHE = None
    _DATA_ROOT_CACHE = None


def is_data_root_overridden() -> bool:
    """データルートが環境変数 ``NEO_HISHO_DATA_DIR`` で明示上書きされているかを返す。

    明示されたデータルートは**常に権威**であり、旧配置へのフォールバック
    （未移行時の暫定運用）を無効化する。テスト隔離と運用切替の決定論を守るための
    Seam (2026-09-23: 上書きを無視して本番DBへ解決する障害の再発防止)。

    Returns:
        bool: 上書きが設定されている場合 True。
    """
    return bool(os.environ.get(DATA_DIR_ENV_VAR, "").strip())


def is_cloud_synced_path(path: Union[str, Path]) -> bool:
    """パスがクラウド同期フォルダ配下かどうかを判定する (ADR-2 の禁止領域検知)。

    パス構成要素を正規化して比較するため、``Sandbox`` のような部分文字列
    (box を含む語) を誤検知しない。環境変数 (OneDrive 等) が指すルート配下も
    ``SkyDrive`` のような独自フォルダ名であっても検知する。

    Args:
        path: 判定対象のファイル/ディレクトリパス。

    Returns:
        bool: クラウド同期フォルダ配下と判定した場合 True。
    """
    text_path = Path(str(path))
    parts = [part.lower() for part in text_path.parts]
    for part in parts:
        if part in _CLOUD_SYNC_PART_MARKERS:
            return True
        if part.startswith(_CLOUD_SYNC_PART_PREFIXES):
            return True

    normalized = str(text_path).replace("\\", "/").rstrip("/").lower()
    for env_name in _CLOUD_SYNC_ENV_VARS:
        root = os.environ.get(env_name, "").strip()
        if not root:
            continue
        root_norm = root.replace("\\", "/").rstrip("/").lower()
        if normalized == root_norm or normalized.startswith(root_norm + "/"):
            return True
    return False


def get_data_root() -> Path:
    """暗号鍵・DB・マスタートークンを配置する非同期データルートを返す (ADR-2)。

    解決順序:
        1. 環境変数 ``NEO_HISHO_DATA_DIR`` (テスト隔離・運用切替の明示上書き)
        2. ``%LOCALAPPDATA%\\NeoHisho`` (Windows 既定)
        3. ``$XDG_DATA_HOME/NeoHisho`` → ``~/.local/share/NeoHisho`` (非 Windows / CI)

    解決結果はプロセス内でキャッシュする。ディレクトリが存在しない場合は
    自動作成を試みる (失敗時はログ出力のみ。後続の書き込み処理が個別に
    エラーハンドリングする)。

    Returns:
        Path: 書き込み可能なデータルートディレクトリ。
    """
    global _DATA_ROOT_CACHE
    if _DATA_ROOT_CACHE is not None:
        return _DATA_ROOT_CACHE

    override = os.environ.get(DATA_DIR_ENV_VAR, "").strip()
    if override:
        root = Path(override).expanduser()
    else:
        base = os.environ.get("LOCALAPPDATA", "").strip() or os.environ.get(
            "XDG_DATA_HOME", ""
        ).strip()
        if base:
            root = Path(base).expanduser() / DATA_DIR_NAME
        else:
            root = Path.home() / ".local" / "share" / DATA_DIR_NAME

    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"データルートの作成に失敗しました: {root} ({e})")

    _DATA_ROOT_CACHE = root
    return root


def get_db_path() -> Path:
    """本番 DB (VAPID 秘密鍵・監査ログを内包) の絶対パスを返す。

    Returns:
        Path: ``<データルート>/neo_secretary.db``。
    """
    return get_data_root() / DB_FILENAME


def get_sync_token_path() -> Path:
    """同期サーバーのマスタートークン (.sync_token) の絶対パスを返す。

    Returns:
        Path: ``<データルート>/.sync_token``。
    """
    return get_data_root() / SYNC_TOKEN_FILENAME


def get_backups_dir() -> Path:
    """自動バックアップ (DB コピー) の保存先ディレクトリを返す。

    Returns:
        Path: ``<データルート>/backups``。
    """
    return get_data_root() / BACKUPS_DIR_NAME


@dataclass
class MigrationReport:
    """``migrate_legacy_data()`` の実行結果レポート。

    Attributes:
        data_root: 移行先データルート。
        migrated_db: DB 本体を移行した場合 True。
        migrated_token: マスタートークンを移行した場合 True。
        migrated_backups: 退避した旧バックアップの件数。
        skipped: スキップ理由の一覧 (既存温存・対象なし等)。
        warnings: 注意事項 (移動不可のためコピー残置等)。
        errors: 失敗事項 (データを壊さないため温存した)。
    """

    data_root: Path
    migrated_db: bool = False
    migrated_token: bool = False
    migrated_backups: int = 0
    skipped: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _legacy_roots(legacy_root: Optional[Path]) -> List[Path]:
    """旧データの探索ルート一覧を返す (明示指定 > アプリルート > CWD)。"""
    if legacy_root is not None:
        return [Path(legacy_root)]

    roots: List[Path] = [get_app_root()]
    try:
        cwd = Path.cwd()
    except OSError as e:
        logger.warning(f"CWD の取得に失敗しました (旧データ探索から除外): {e}")
        cwd = None
    if cwd is not None and cwd not in roots:
        roots.append(cwd)
    return roots


def _archive_dir(data_root: Path) -> Path:
    """移行アーカイブの作成先 (タイムスタンプ付き) を返す。"""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(data_root) / MIGRATION_ARCHIVE_DIR_NAME / stamp


def _archive_legacy_file(src: Path, archive_dir: Path) -> Optional[str]:
    """旧ファイルをアーカイブへ退避する (移動優先・ロック時はコピー残置)。

    Args:
        src: 退避する旧ファイル。
        archive_dir: アーカイブディレクトリ。

    Returns:
        Optional[str]: 完全な移動ができなかった場合の警告文。成功時は None。
    """
    try:
        archive_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return f"アーカイブディレクトリを作成できませんでした: {archive_dir} ({e})"

    destination = archive_dir / src.name
    try:
        shutil.move(str(src), str(destination))
        logger.info(f"旧データを退避しました: {src} → {destination}")
        return None
    except (OSError, shutil.Error) as move_error:
        try:
            shutil.copy2(src, destination)
            return (
                f"旧ファイルが使用中のため移動できずコピー退避しました "
                f"(アプリ停止後に削除を検討): {src} ({move_error})"
            )
        except (OSError, shutil.Error) as copy_error:
            return f"旧ファイルの退避に失敗しました: {src} ({copy_error})"


def _copy_sqlite_safely(source: Path, destination: Path) -> None:
    """SQLite Online Backup API で一貫スナップショットを作成する (WAL 込み)。

    Args:
        source: 旧 DB ファイル。
        destination: 移行先の一時ファイル (``*.migrating``)。

    Raises:
        sqlite3.Error: 旧ファイルが DB でない・読み取り不能等の場合。
    """
    source_conn = sqlite3.connect(str(source), timeout=30.0)
    try:
        destination_conn = sqlite3.connect(str(destination))
        try:
            with destination_conn:
                source_conn.backup(destination_conn, pages=100, sleep=0.01)
        finally:
            destination_conn.close()
    finally:
        source_conn.close()


def _verify_sqlite(path: Path) -> bool:
    """``PRAGMA quick_check`` で移行先 DB の健全性を検証する。"""
    conn = sqlite3.connect(str(path))
    try:
        row = conn.execute("PRAGMA quick_check").fetchone()
        return bool(row) and row[0] == "ok"
    finally:
        conn.close()


def _archive_db_with_sidecars(
    legacy_db: Path,
    archive_dir: Path,
    report: "MigrationReport",
    residual_header: str,
) -> None:
    """旧DB本体と ``-wal`` / ``-shm`` を運命共同体として退避する (P1-N3)。

    本体の退避に失敗した場合（使用中）は sidecar も退避しない（データ整合優先）。
    本体が退避できた場合は sidecar も続けて退避し、失敗は警告に留める。

    Args:
        legacy_db: 旧DB本体のパス。
        archive_dir: アーカイブディレクトリ。
        report: 結果を記録する MigrationReport。
        residual_header: 本体が残存した場合の警告文プレフィックス。
    """
    note = _archive_legacy_file(legacy_db, archive_dir)
    if note:
        residual = f"{residual_header}: {legacy_db} ({note})"
        report.warnings.append(residual)
        logger.error(residual)
        return
    for suffix in ("-wal", "-shm"):
        side = Path(str(legacy_db) + suffix)
        if side.exists():
            side_note = _archive_legacy_file(side, archive_dir)
            if side_note:
                report.warnings.append(f"旧DB付随ファイルの退避に失敗: {side} ({side_note})")


def warn_if_legacy_data_pending(
    legacy_root: Optional[Path] = None,
    data_root: Optional[Path] = None,
) -> bool:
    """未移行の旧データが残っている場合に警告する（**移行は実行しない**）。

    Notes:
        🛡️ 2026-09-23 設計判断: データ所有者はデスクトップアプリ (main.py) ただ1つ。
        MCP サーバー等のクライアントプロセスが移行を実行すると、アプリが稼働中の
        ケースで「アプリは旧DB・クライアントは新DB」の**DB分裂**を生む
        (アプリが移行後に書いた旧DBはアーカイブされ、更新が失われる)。
        そのためクライアントは移行せず、旧配置フォールバックで一貫して旧DBを使い、
        警告でボスに「アプリを起動して移行してください」と案内する。

    Args:
        legacy_root: 旧データの探索ルート（省略時は get_app_root() と CWD）。
        data_root: データルート（省略時は get_data_root()）。

    Returns:
        bool: 未移行の旧DBが存在する（＝アプリ起動による移行待ち）場合 True。
    """
    data_dir = Path(data_root) if data_root is not None else get_data_root()
    target_db = data_dir / DB_FILENAME
    if target_db.exists():
        return False

    for root in _legacy_roots(legacy_root):
        legacy_db = Path(root) / DB_FILENAME
        if legacy_db.exists():
            logger.warning(
                "⚠️ [ADR-2] 旧配置の DB が未移行です（アプリを起動すると %LOCALAPPDATA% へ"
                f"安全に移行されます。クライアントは旧DBを継続使用）: {legacy_db}"
            )
            if is_cloud_synced_path(legacy_db):
                logger.error(
                    f"🚨 [ADR-2] 未移行の旧DBがクラウド同期フォルダ配下にあります（機密残存）: {legacy_db}"
                )
            return True
    return False


def migrate_legacy_data(
    legacy_root: Optional[Path] = None,
    data_root: Optional[Path] = None,
) -> MigrationReport:
    """旧データ (クラウド同期領域) を非同期データルートへ安全に移行する (P0-4 / ADR-2)。

    対象: ``neo_secretary.db`` (``-wal`` / ``-shm`` 含む) / ``.sync_token`` /
    ``backups/neo_secretary_backup_*.db*``。

    安全設計 (Fail-Safe):
        - クラウド同期フォルダ配下のデータルートは **ADR-2 違反として拒否**する
          (``errors`` に記録し、移行しない)。
        - 移行先に既存データがある場合は**一切上書きしない**。ただし旧DBが
          同期領域に残っていれば退避を再試行し、失敗時は「機密残存」を警告する。
        - DB は Online Backup API → ``quick_check`` 合格後にのみ本採用する
          (一意名の ``*.migrating`` 一時ファイル経由。失敗時は一時ファイルを削除)。
        - 旧ファイルは ``migration_archive/<timestamp>/`` へ**退避（移動）**し、
          削除しない。ロック等で移動できない場合はコピーを残置し警告を記録する。
          ``-wal`` / ``-shm`` は本体の退避が成功した場合のみ退避する
          (オール・オア・ナッシングでデータ整合を守る)。
        - 例外は送出せず ``MigrationReport`` に集約する (起動を止めない)。

    Args:
        legacy_root: 旧データの探索ルート (テスト・運用の明示指定用)。
            省略時は ``get_app_root()`` と CWD を探索する。
        data_root: 移行先データルート (テスト用)。省略時は ``get_data_root()``。

    Returns:
        MigrationReport: 実行結果 (移行/スキップ/警告/エラー)。
    """
    data_dir = Path(data_root) if data_root is not None else get_data_root()
    report = MigrationReport(data_root=data_dir)
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        report.errors.append(f"データルートを作成できませんでした: {data_dir} ({e})")
        return report

    # ADR-2 の禁止領域チェック: クラウド同期フォルダへの移行は Fail-Closed で拒否する
    # (鍵素材を同期領域へ置く事故を「警告して続行」で見逃さない)
    if is_cloud_synced_path(data_dir):
        note = (
            "ADR-2 違反: データルートがクラウド同期フォルダ配下です。"
            f"移行を中止しました (NEO_HISHO_DATA_DIR を見直してください): {data_dir}"
        )
        report.errors.append(note)
        logger.error(note)
        return report

    target_db = data_dir / DB_FILENAME
    target_token = data_dir / SYNC_TOKEN_FILENAME
    target_backups = data_dir / BACKUPS_DIR_NAME
    archive_dir = _archive_dir(data_dir)

    try:
        for root in _legacy_roots(legacy_root):
            root = Path(root)

            # --- 1) DB 本体 (-wal / -shm 含む) ---
            legacy_db = root / DB_FILENAME
            if not legacy_db.exists():
                report.skipped.append(f"旧DBなし: {legacy_db}")
            elif target_db.exists():
                # 移行済みでも、旧DB（VAPID 秘密鍵を内包）が同期領域に残っていれば
                # 退避を再試行する。失敗した場合は「機密残存」を警告で明示する。
                report.skipped.append(f"移行先DBが存在するため上書きしない: {legacy_db}")
                _archive_db_with_sidecars(
                    legacy_db,
                    archive_dir,
                    report,
                    "⚠️ 旧DB (VAPID 秘密鍵を内包) が同期領域に残存しています。"
                    "アプリ/ MCP を停止して再実行してください",
                )
            else:
                migrating: Optional[Path] = None
                try:
                    handle, migrating_name = tempfile.mkstemp(
                        dir=str(data_dir), prefix=f"{target_db.name}.", suffix=".migrating"
                    )
                    os.close(handle)
                    migrating = Path(migrating_name)
                    _copy_sqlite_safely(legacy_db, migrating)
                    if not _verify_sqlite(migrating):
                        raise sqlite3.DatabaseError("quick_check に失敗しました")
                    migrating.replace(target_db)
                    report.migrated_db = True
                    logger.info(f"🔐 DB を非同期領域へ移行しました: {legacy_db} → {target_db}")
                    # 旧DB本体の退避。失敗（使用中）時はコピー退避＋警告とし、
                    # -wal/-shm は本体と運命を共にする（単独で退避しない = データ整合）
                    _archive_db_with_sidecars(
                        legacy_db,
                        archive_dir,
                        report,
                        "⚠️ 旧DBが同期領域に残存しています (コピーは移行済み)。"
                        "アプリ/ MCP を停止して再実行してください",
                    )
                except (sqlite3.Error, OSError, shutil.Error) as e:
                    report.errors.append(f"DBの移行に失敗しました (旧DBは温存): {legacy_db} ({e})")
                    logger.error(f"DBの移行に失敗しました: {legacy_db} ({e})")
                    if migrating is not None:
                        try:
                            migrating.unlink(missing_ok=True)
                        except OSError as cleanup_error:
                            logger.warning(
                                f"移行用一時ファイルを削除できませんでした: {migrating} ({cleanup_error})"
                            )

            # --- 2) マスタートークン (.sync_token) ---
            legacy_token = root / SYNC_TOKEN_FILENAME
            if not legacy_token.exists():
                report.skipped.append(f"旧トークンなし: {legacy_token}")
            elif target_token.exists():
                report.skipped.append(f"移行先トークンが存在するため温存: {legacy_token}")
            else:
                try:
                    shutil.move(str(legacy_token), str(target_token))
                    report.migrated_token = True
                    logger.info(f"🔐 マスタートークンを非同期領域へ移行しました: {target_token}")
                except (OSError, shutil.Error) as e:
                    report.errors.append(
                        f"トークンの移行に失敗しました (旧トークンは温存): {legacy_token} ({e})"
                    )

            # --- 3) 旧バックアップ (VAPID PEM を内包する DB コピー) ---
            legacy_backups = root / BACKUPS_DIR_NAME
            if not legacy_backups.is_dir():
                report.skipped.append(f"旧バックアップなし: {legacy_backups}")
                continue
            candidates = sorted(legacy_backups.glob("neo_secretary_backup_*.db*"))
            if not candidates:
                report.skipped.append(f"旧バックアップなし: {legacy_backups}")
                continue
            try:
                target_backups.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                report.errors.append(f"バックアップ移行先を作成できませんでした: {target_backups} ({e})")
                continue
            for source in candidates:
                destination = target_backups / source.name
                if destination.exists():
                    # 同名が移行済みでも旧コピー（機密同梱）はアーカイブへ退避する
                    report.skipped.append(f"同名バックアップが移行済みのため複製せず退避: {source}")
                    note = _archive_legacy_file(source, archive_dir)
                    if note:
                        report.warnings.append(
                            f"⚠️ 旧バックアップ (機密同梱) が同期領域に残存: {source} ({note})"
                        )
                    continue
                try:
                    shutil.move(str(source), str(destination))
                    report.migrated_backups += 1
                except (OSError, shutil.Error) as e:
                    report.errors.append(f"バックアップの退避に失敗しました: {source} ({e})")
    except Exception as e:
        # 最終防衛線: 移行の失敗でアプリ起動を妨げない (契約: 例外を送出しない)
        report.errors.append(f"移行処理で予期しないエラーが発生しました: {e}")
        logger.error(f"移行処理で予期しないエラーが発生しました: {e}")

    if report.migrated_db or report.migrated_token or report.migrated_backups:
        logger.info(
            f"🔐 [ADR-2] 旧データの非同期領域への移行が完了しました "
            f"(db={report.migrated_db} / token={report.migrated_token} / "
            f"backups={report.migrated_backups})"
        )
    return report


def is_frozen() -> bool:
    """PyInstaller 実行ファイル環境かどうかを判定する。

    Returns:
        bool: exe 実行時は True、開発環境 (python main.py) は False。
    """
    return bool(getattr(sys, "frozen", False))


def _is_writable(directory: Path) -> bool:
    """指定ディレクトリへの書き込み可否を一時ファイルの作成試行で検証する。

    管理者権限を要するフォルダ (例: ``C:\\Program Files``) にアプリが配置された
    場合でも起動クラッシュしないよう、実際にプローブファイルを書き込んで判定する。
    判定処理はファイルシステム I/O を伴うため、get_app_root() 側で結果をキャッシュし、
    プロセス内で本関数が繰り返し呼ばれないようになっている。

    Args:
        directory: 書き込み可否を検証するディレクトリ。

    Returns:
        bool: 一時ファイルの作成・削除に成功した場合 True、
              PermissionError 等の OSError が発生した場合 False。
    """
    probe = directory / ".neo_hisho_write_probe.tmp"
    try:
        with probe.open("w", encoding="utf-8") as f:
            f.write("probe")
        return True
    except OSError as e:
        logger.info(f"書き込み不可と判定しました: {directory} ({e})")
        return False
    finally:
        try:
            probe.unlink(missing_ok=True)
        except OSError as e:
            logger.warning(f"書き込み確認用プローブファイルの削除に失敗しました: {probe} ({e})")


def _fallback_app_root() -> Path:
    """書き込み不可フォルダ配置時に使用する AppData 配下のフォールバックルートを返す。

    Returns:
        Path: ``%APPDATA%\\NeoHisho`` (環境変数 APPDATA 未定義時は ``~/NeoHisho``)。
              ディレクトリが存在しない場合は自動作成を試みる (失敗時はログ出力のみで
              例外は再送出しない。後続の書き込み処理が個別にエラーハンドリングする)。
    """
    fallback = Path(os.environ.get("APPDATA", "~")).expanduser() / FALLBACK_DIR_NAME
    logger.warning(
        f"アプリ配置フォルダへの書き込みが不可のため、ユーザーデータを "
        f"%APPDATA% 配下へフォールバックします: {fallback}"
    )
    try:
        fallback.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"フォールバックディレクトリの作成に失敗しました: {fallback} ({e})")
    return fallback


def get_app_root() -> Path:
    """書き込み可能データ (DB や .env 等) を配置するルートディレクトリを返す。

    exe と同じフォルダ (frozen 時) / プロジェクトルート (開発時) に書き込みできない
    場合 (例: ``C:\\Program Files`` への解凍、管理者権限フォルダ) は、
    ``%APPDATA%\\NeoHisho`` へ自動フォールバックし、初回起動がクラッシュしないことを
    保証する (「まず繋がる体験」の死守 / 2026-09-01 3周レビュー P0対応)。

    判定結果はプロセス内でキャッシュされ、2回目以降の呼び出しではディスク I/O を
    行わずに即座に返す。

    Returns:
        Path: 書き込み可能なユーザーデータルートディレクトリ。
    """
    global _APP_ROOT_CACHE
    if _APP_ROOT_CACHE is not None:
        return _APP_ROOT_CACHE

    if is_frozen():
        candidate = Path(sys.executable).resolve().parent
    else:
        candidate = Path(__file__).resolve().parent

    if _is_writable(candidate):
        _APP_ROOT_CACHE = candidate
        return candidate

    fallback = _fallback_app_root()
    _APP_ROOT_CACHE = fallback
    return fallback


def get_resource_root() -> Path:
    """読み取り専用リソース (同梱アセット) のルートディレクトリを返す。

    Returns:
        Path: frozen 時は PyInstaller の展開先 (sys._MEIPASS)、
              開発時はプロジェクトルート。
    """
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def ensure_env_file() -> Path:
    """.env が存在しなければ .env.example から自動生成する (初回起動ブートストラップ)。

    生成直後は API キーが未設定だが、アプリ自体は起動し
    「使い方ガイド」でキー設定を案内できる (「まず繋がる体験」優先)。

    Returns:
        Path: 保証された .env ファイルのパス。
    """
    env_path = get_app_root() / ENV_NAME
    if env_path.exists():
        return env_path
    example_path = get_resource_root() / ENV_EXAMPLE_NAME
    try:
        if example_path.exists():
            shutil.copy2(example_path, env_path)
            logger.info(f"初回起動: .env を .env.example から自動生成しました: {env_path}")
        else:
            env_path.touch()
            logger.warning(
                f".env.example が同梱されていないため空の .env を作成しました: {env_path}"
            )
    except Exception as e:
        logger.error(f".env 自動生成に失敗しました: {e}")
    return env_path
