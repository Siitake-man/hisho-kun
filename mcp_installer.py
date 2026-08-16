"""
ネオ秘書くん - MCP環境自動セットアップ・インジェクター (mcp_installer.py)

他者のPCや新規環境で実行された際、現在のPython環境（sys.executable）と
プロジェクトパスを自己検出し、Antigravity / Claude Desktop / Cursor の
MCP設定JSONへワンクリックで自動登録・同期します。
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

def get_current_mcp_config() -> Dict[str, Any]:
    """現在の環境に合致した neo_hisho_bridge のMCP設定辞書を生成"""
    python_exe = sys.executable
    project_dir = Path(__file__).parent.resolve()
    server_script = project_dir / "hisho_mcp_server.py"
    
    return {
        "command": str(python_exe),
        "args": [str(server_script)]
    }

def get_target_config_paths() -> Dict[str, Path]:
    """各AIツールの標準設定ファイルパスを取得"""
    home = Path.home()
    appdata = Path(os.environ.get("APPDATA", str(home / "AppData" / "Roaming")))
    
    paths = {
        "antigravity": home / ".gemini" / "config" / "mcp_config.json",
        "claude_desktop": appdata / "Claude" / "claude_desktop_config.json",
        "cursor": home / ".cursor" / "mcp.json"
    }
    return paths

def install_to_tool(tool_name: str = "antigravity") -> Tuple[bool, str]:
    """
    指定されたAIツールの設定JSONに neo_hisho_bridge を自動追記・登録します。
    
    Args:
        tool_name: 'antigravity', 'claude_desktop', 'cursor'
        
    Returns:
        Tuple[bool, str]: (成功フラグ, メッセージ)
    """
    paths = get_target_config_paths()
    target_path = paths.get(tool_name)
    if not target_path:
        return False, f"未対応のツールです: {tool_name}"
        
    mcp_def = get_current_mcp_config()
    
    try:
        # ディレクトリ作成
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        data: Dict[str, Any] = {"mcpServers": {}}
        if target_path.exists():
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                logger.warning(f"既存設定のパースに失敗。新規作成します: {e}")
                data = {"mcpServers": {}}
                
        if "mcpServers" not in data:
            data["mcpServers"] = {}
            
        data["mcpServers"]["neo_hisho_bridge"] = mcp_def
        
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        msg = f"✓ {tool_name} の設定 ({target_path}) にネオ秘書くんMCPを正常登録しました！"
        logger.info(msg)
        return True, msg
    except Exception as e:
        err = f"MCP設定の書き込みに失敗しました ({target_path}): {e}"
        logger.error(err)
        return False, err

if __name__ == "__main__":
    print("=== ネオ秘書くん MCP自動セットアップ ===")
    success, message = install_to_tool("antigravity")
    print(message)
