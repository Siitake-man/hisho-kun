"""ネオ秘書くん アプリケーションバージョン定義

アプリケーションのバージョンとリリース情報の「唯一の情報源」(Single Source of Truth)。
更新チェック (update_checker.py) や MCP サーバー応答 (hisho_mcp_server.py) 等、
バージョン番号が必要な箇所はすべて本モジュールの値を参照すること。
"""

from typing import Final

# アプリケーションのセマンティックバージョン (major.minor.patch)
__version__: Final[str] = "1.1.15"

# 表示用アプリケーション名
APP_NAME: Final[str] = "ネオ秘書くん (Neo-Secretary)"

# 公開リポジトリ (owner/repo 形式)。更新チェックの対象。
GITHUB_REPO: Final[str] = "Siitake-man/hisho-kun"

# GitHub Releases 最新リリース取得 API エンドポイント
RELEASES_API_URL: Final[str] = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# ユーザーへ案内するリリースページ URL
RELEASES_PAGE_URL: Final[str] = f"https://github.com/{GITHUB_REPO}/releases/latest"
