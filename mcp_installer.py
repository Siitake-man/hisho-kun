"""
ネオ秘書くん - MCP環境自動セットアップ・インジェクター (mcp_installer.py)

他者のPCや新規環境で実行された際、現在のPython環境（sys.executable）と
プロジェクトパスを自己検出し、各種AIエージェントのMCP設定ファイルへ
ワンコマンドで自動登録・同期します。

使い方 (「1コマンド原則」— エージェントには本コマンド1発だけ実行させる):
    python mcp_installer.py --all            # 対応全クライアントへ一括登録
    python mcp_installer.py --tool claude_desktop cursor
    python mcp_installer.py --list           # 対応クライアントと設定パスの表示

注意:
- 書き込み前に必ず既存設定を <ファイル名>.bak へバックアップします。
- Codex (config.toml) はTOML形式のため自動登録非対象です (誤記で壊すリスクを回避)。
"""

import argparse
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

SERVER_ID = "neo_hisho_bridge"


def _build_tool_registry() -> Dict[str, Dict[str, Any]]:
    """対応クライアントごとの設定ファイルパスとJSONルートキーを返す。

    Returns:
        Dict[str, Dict[str, Any]]: クライアントID →
            {"path": Path, "root_key": "mcpServers" | "servers", "label": str}
    """
    home = Path.home()
    appdata = Path(os.environ.get("APPDATA", str(home / "AppData" / "Roaming")))
    return {
        "antigravity": {
            "path": home / ".gemini" / "config" / "mcp_config.json",
            "root_key": "mcpServers",
            "label": "Antigravity",
        },
        "claude_desktop": {
            "path": appdata / "Claude" / "claude_desktop_config.json",
            "root_key": "mcpServers",
            "label": "Claude Desktop",
        },
        "cursor": {
            "path": home / ".cursor" / "mcp.json",
            "root_key": "mcpServers",
            "label": "Cursor",
        },
        "cline": {
            "path": appdata
            / "Code"
            / "User"
            / "globalStorage"
            / "saoudrizwan.claude-settings"
            / "settings"
            / "cline_mcp_settings.json",
            "root_key": "mcpServers",
            "label": "Cline (VS Code)",
        },
        "claude_code": {
            "path": home / ".claude.json",
            "root_key": "mcpServers",
            "label": "Claude Code",
        },
        "vscode": {
            "path": Path.cwd() / ".vscode" / "mcp.json",
            "root_key": "servers",
            "label": "VS Code (ワークスペース)",
        },
    }


def get_current_mcp_config() -> Dict[str, Any]:
    """現在の環境に合致した neo_hisho_bridge のMCP設定辞書を生成する。

    Returns:
        Dict[str, Any]: {"command": Python実行ファイル, "args": [サーバスクリプト]}
    """
    return {
        "command": Path(sys.executable).as_posix(),
        "args": [(Path(__file__).parent.resolve() / "hisho_mcp_server.py").as_posix()],
    }

def _backup_file(target: Path) -> None:
    """既存設定ファイルを <ファイル名>.bak へ退避する (冪等・上書き許容)。

    Args:
        target: バックアップ対象の設定ファイルパス。
    """
    if target.exists():
        backup = target.with_name(target.name + ".bak")
        shutil.copy2(target, backup)
        logger.info(f"設定バックアップ作成: {backup}")


def install_to_tool(tool_name: str = "antigravity") -> Tuple[bool, str]:
    """指定クライアントのMCP設定JSONへ neo_hisho_bridge を自動追記・登録する。

    既存の他サーバー定義は保持したままマージのみ行う (冪等実装)。
    書き込み前に必ず .bak バックアップを作成し、失敗時もユーザー設定を壊さない。

    Args:
        tool_name: 対応クライアントID (--list で一覧表示)。

    Returns:
        Tuple[bool, str]: (成功フラグ, 結果メッセージ)
    """
    registry = _build_tool_registry()
    entry = registry.get(tool_name)
    if not entry:
        return False, f"未対応のツールです: {tool_name} (--list で一覧を確認できます)"

    target_path: Path = entry["path"]
    root_key: str = entry["root_key"]
    label: str = entry["label"]
    mcp_def = get_current_mcp_config()

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        _backup_file(target_path)

        data: Dict[str, Any] = {root_key: {}}
        if target_path.exists():
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                logger.warning(f"既存設定 [{label}] のパースに失敗。新規作成します: {e}")
                data = {root_key: {}}

        if root_key not in data or not isinstance(data[root_key], dict):
            data[root_key] = {}

        # 古い無効なSSE設定の残骸を自動クリーンアップ
        if "agent-bridge-mcp" in data[root_key]:
            del data[root_key]["agent-bridge-mcp"]
            logger.info("古い agent-bridge-mcp 設定を自動クリーンアップ削除しました")

        data[root_key][SERVER_ID] = mcp_def

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        msg = f"✓ [{label}] {target_path} にネオ秘書くんMCPを登録しました"
        logger.info(msg)
        return True, msg
    except Exception as e:
        err = f"MCP設定の書き込みに失敗しました [{label}] ({target_path}): {e}"
        logger.error(err)
        return False, err


def get_target_config_paths() -> Dict[str, Path]:
    """各AIツールの標準設定ファイルパスを取得する (後方互換エイリアス)。

    Note:
        新規コードは `_build_tool_registry()` を直接利用すること。
        本関数は settings_window.py 等の既存呼び出し互換のため維持する。

    Returns:
        Dict[str, Path]: クライアントID → 設定ファイルパス。
    """
    return {tool_id: entry["path"] for tool_id, entry in _build_tool_registry().items()}


def install_to_all() -> Dict[str, Tuple[bool, str]]:
    """対応全クライアントへ neo_hisho_bridge を一括登録する。

    Returns:
        Dict[str, Tuple[bool, str]]: クライアントID → (成功フラグ, メッセージ)
    """
    results: Dict[str, Tuple[bool, str]] = {}
    for tool_id in _build_tool_registry():
        results[tool_id] = install_to_tool(tool_id)
    return results


def main(argv: Any = None) -> int:
    """CLIエントリポイント。

    Args:
        argv: コマンドライン引数リスト (None なら sys.argv を使用)。

    Returns:
        int: プロセス終了コード (0=成功, 1=一部失敗)。
    """
    parser = argparse.ArgumentParser(
        description="ネオ秘書くん MCP自動セットアップ (各AIクライアントの設定JSONへ登録)"
    )
    parser.add_argument("--all", action="store_true", help="対応全クライアントへ一括登録")
    parser.add_argument(
        "--tool", nargs="+", metavar="ID",
        help="指定クライアントへ登録 (例: --tool claude_desktop cursor)"
    )
    parser.add_argument("--list", action="store_true", help="対応クライアントと設定パスを表示")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    registry = _build_tool_registry()

    if args.list:
        print("=== ネオ秘書くん MCP 対応クライアント一覧 ===")
        for tool_id, entry in registry.items():
            print(f"  {tool_id:<15} {entry['label']}: {entry['path']}")
        print("  ※ Codex (config.toml) はTOML形式のため自動登録非対応です")
        return 0

    if args.all or not args.tool:
        # 引数なしは --all 扱い (「1コマンド原則」— エージェントからの実行ミスを防ぐ)
        targets = list(registry.keys())
    else:
        targets = args.tool

    exit_code = 0
    print("=== ネオ秘書くん MCP自動セットアップ ===")
    for tool_id in targets:
        ok, message = install_to_tool(tool_id)
        print(message)
        if not ok:
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

