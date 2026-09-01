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
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 環境設定ファイルのファイル名
ENV_NAME: str = ".env"
ENV_EXAMPLE_NAME: str = ".env.example"

# AppData フォールバック時のアプリ専用ディレクトリ名
FALLBACK_DIR_NAME: str = "NeoHisho"

# get_app_root() の決定結果キャッシュ (プロセス内で書き込み判定は一度だけ実施する)
_APP_ROOT_CACHE: Optional[Path] = None


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
