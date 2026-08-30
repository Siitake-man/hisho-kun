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
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# 環境設定ファイルのファイル名
ENV_NAME: str = ".env"
ENV_EXAMPLE_NAME: str = ".env.example"


def is_frozen() -> bool:
    """PyInstaller 実行ファイル環境かどうかを判定する。

    Returns:
        bool: exe 実行時は True、開発環境 (python main.py) は False。
    """
    return bool(getattr(sys, "frozen", False))


def get_app_root() -> Path:
    """書き込み可能データ (DB や .env 等) を配置するルートディレクトリを返す。

    Returns:
        Path: frozen 時は exe と同じフォルダ、開発時はプロジェクトルート。
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


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
