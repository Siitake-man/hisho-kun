"""
ネオ秘書くん - 同期サーバー設定の単一情報源 (sync_config.py)

ローカル同期サーバー (local_sync_server) の待受ポート等、
複数モジュール (本体 / QR接続ダイアログ / main の Tailscale 自動起動) が
共通参照する設定値を集約します。

設計意図 (Why):
    ポート番号のベタ書きが各所に散ると、変更時に修正漏れが起きる
    (Divergent Change)。また local_sync_server を import して定数を取りに行く
    設計は agent_fsm / database 等の重量級依存を連鎖 import させ、GUI 起動や
    テストのコストを押し上げる。そこで「値だけを持つ極小モジュール」を
    情報源とし、全モジュールがここを参照する。
"""

import os
from pathlib import Path
from typing import Any, Final, Optional

# 既定の待受ポート (この値は「既定値」であり、利用側は SERVER_PORT を参照すること)
DEFAULT_SERVER_PORT: Final[int] = 8765

# 環境変数による上書きキー (ポート競合時の回避用 / P1-4)
PORT_ENV_KEY: Final[str] = "NEO_HISHO_PORT"


def resolve_server_port(raw_port: Any = None) -> int:
    """待受ポートを決定する (環境変数オーバーライド対応・入力検証つき)。

    Args:
        raw_port: 生のポート値 (環境変数由来の文字列など)。
            省略/None/空文字、数値でない値、範囲外 (1〜65535 外) は既定値へ退避する。

    Returns:
        int: 使用する待受ポート番号。

    Notes:
        ``NEO_HISHO_PORT`` を設定すると、別プロセスとのポート競合を回避できる。
        不正値はクラッシュさせず既定ポートへ黙って退避する (起動優先)。
    """
    if raw_port is None or str(raw_port).strip() == "":
        return DEFAULT_SERVER_PORT
    try:
        port = int(str(raw_port).strip())
    except (TypeError, ValueError):
        return DEFAULT_SERVER_PORT
    if not 1 <= port <= 65535:
        return DEFAULT_SERVER_PORT
    return port


def _default_env_path() -> Optional[Path]:
    """アプリデータルートの `.env` を解決する（解決できなければ None）。

    Notes:
        `app_paths` は frozen/開発の両モードでアプリルートを解決する軽量モジュール。
        import 失敗時は None を返し、起動を妨げない（Fail-Safe）。
    """
    try:
        import app_paths

        return app_paths.get_app_root() / ".env"
    except Exception:
        return None


def read_port_from_env_file(env_path: Optional[Path] = None) -> Optional[str]:
    """`.env` から `NEO_HISHO_PORT` の生の値を読み取る（OS環境変数が無い場合のフォールバック）。

    Args:
        env_path: `.env` のパス（省略時はアプリデータルートの `.env`）。

    Returns:
        Optional[str]: 見つかった生の値（前後の引用符を除去済み）。
            未記載・コメント行のみ・ファイル不在・読取失敗時は None。

    Notes:
        2026-09-16 (P1-1): `main.py` は `agent.py`（load_dotenv 実行元）より先に
        sync_config を import するため、`.env` の値は os.environ に載っていない。
        案内（`.env.example`）と実装を一致させるため、stdlib のみで軽量に読む
        （os.environ は汚染しない）。
    """
    path = Path(env_path) if env_path is not None else _default_env_path()
    if path is None or not path.is_file():
        return None

    try:
        with path.open(encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                if key.strip() != PORT_ENV_KEY:
                    continue
                return value.strip().strip('"').strip("'")
    except OSError:
        return None
    return None


def _read_env_port() -> Optional[str]:
    """待受ポートの生値を決定する（OS環境変数 → `.env` の順に解決）。"""
    value = os.getenv(PORT_ENV_KEY)
    if value is not None and str(value).strip():
        return value
    return read_port_from_env_file()


# Tailscale Serve のリバースプロキシ起動フラグ。
# `--bg` を付けるとフォアグラウンドを占有せずバックグラウンドで常駐する
# （付けないとコマンドが終了せず、アプリからの自動起動や手順書のコピペで混乱する）。
# P2 (2026-09-16 ruthless-code-evaluation): 旧実装は main.py（--bg なし）と
# QRダイアログ/手順書（--bg あり）で2種類のコマンドが混在していた。
TAILSCALE_SERVE_FLAGS: Final[tuple] = ("--bg",)


def tailscale_serve_command_args() -> list:
    """Tailscale Serve 起動コマンドの引数リストを生成する（単一情報源）。

    Returns:
        list: 例 ``["tailscale", "serve", "--bg", "8765"]``。
            ポートは `SERVER_PORT`（OS環境変数/.env/既定）を参照する。
    """
    return ["tailscale", "serve", *TAILSCALE_SERVE_FLAGS, str(SERVER_PORT)]


def build_tailscale_serve_command() -> str:
    """Tailscale Serve 起動コマンドの表示用文字列を生成する（手順書・UI用）。

    Returns:
        str: 例 ``"tailscale serve --bg 8765"``。
    """
    return " ".join(tailscale_serve_command_args())


# 待受ポート (唯一の情報源)。QRコード・Tailscale Serve コマンド・サーバーバインドは
# すべて本値を参照するため、変更はここ1箇所 (+ 必要なら NEO_HISHO_PORT の設定) で済む。
SERVER_PORT: Final[int] = resolve_server_port(_read_env_port())
