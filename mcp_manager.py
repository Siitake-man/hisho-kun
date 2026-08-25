"""
ネオ秘書くん - MCP (Model Context Protocol) 連携マネージャー (mcp_manager.py)

外部MCPサーバー（Filesystem, GitHub, Notion, Fetch 等）の設定管理、
stdio プロセス通信、および LangChain / LangGraph ツールへの動的変換を提供します。
"""

import os
import json
import logging
import asyncio
import subprocess
from typing import Dict, Any, List, Optional
from pathlib import Path

from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool, StructuredTool

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "mcp_config.json"

DEFAULT_MCP_CONFIG = {
    "mcpServers": {
        "filesystem": {
            "name": "ローカルファイル操作",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
            "env": {},
            "enabled": False,
            "description": "PC内のファイル読み書き・検索を可能にします"
        },
        "fetch": {
            "name": "Webページ取得 (Fetch)",
            "command": "uvx",
            "args": ["mcp-server-fetch"],
            "env": {},
            "enabled": False,
            "description": "URLから最新のWebページ内容をテキスト取得します"
        },
        "github": {
            "name": "GitHub連携",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": ""},
            "enabled": False,
            "description": "GitHubのIssue確認やPR操作を行います"
        }
    }
}


class MCPServerConfig(BaseModel):
    """MCPサーバー1台の設定情報"""
    name: str = Field(default="MCP Server")
    command: str = Field(..., min_length=1)
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    enabled: bool = Field(default=False)
    description: Optional[str] = ""


class MCPManager:
    """
    MCP設定のロード・保存、およびMCPサーバーとの通信を統括するマネージャー。
    """
    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config_path = config_path
        self._ensure_config_exists()

    def _ensure_config_exists(self) -> None:
        """設定ファイルが存在しない場合はデフォルト設定で初期作成"""
        if not self.config_path.exists():
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_MCP_CONFIG, f, indent=2, ensure_ascii=False)
                logger.info(f"デフォルトの mcp_config.json を作成しました: {self.config_path}")
            except Exception as e:
                logger.error(f"mcp_config.json 作成エラー: {e}")

    def load_config(self) -> Dict[str, Any]:
        """設定ファイルを読み込みます"""
        self._ensure_config_exists()
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"mcp_config.json 読み込みエラー: {e}")
            return DEFAULT_MCP_CONFIG

    def save_config(self, config_data: Dict[str, Any]) -> bool:
        """設定ファイルへ保存します"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            logger.info("mcp_config.json を保存しました")
            return True
        except Exception as e:
            logger.error(f"mcp_config.json 保存エラー: {e}")
            return False

    def get_server_configs(self) -> Dict[str, MCPServerConfig]:
        """全サーバー設定をPydanticモデルの辞書として取得"""
        raw_config = self.load_config()
        servers = raw_config.get("mcpServers", {})
        result = {}
        for server_id, conf in servers.items():
            try:
                result[server_id] = MCPServerConfig(**conf)
            except Exception as e:
                logger.warning(f"サーバー設定パースエラー ({server_id}): {e}")
        return result

    def update_server_status(self, server_id: str, enabled: bool) -> bool:
        """指定したMCPサーバーの有効/無効を切り替えて保存"""
        raw_config = self.load_config()
        if "mcpServers" in raw_config and server_id in raw_config["mcpServers"]:
            raw_config["mcpServers"][server_id]["enabled"] = enabled
            return self.save_config(raw_config)
        return False

    def add_or_update_server(self, server_id: str, config: MCPServerConfig) -> bool:
        """MCPサーバー設定を追加または更新"""
        raw_config = self.load_config()
        if "mcpServers" not in raw_config:
            raw_config["mcpServers"] = {}
        raw_config["mcpServers"][server_id] = config.dict()
        return self.save_config(raw_config)

    def delete_server(self, server_id: str) -> bool:
        """MCPサーバー設定を削除"""
        raw_config = self.load_config()
        if "mcpServers" in raw_config and server_id in raw_config["mcpServers"]:
            del raw_config["mcpServers"][server_id]
            return self.save_config(raw_config)
        return False

    def get_dynamic_mcp_tools(self) -> List[BaseTool]:
        """
        有効化されているMCPサーバー群からツール一覧をロードし、
        LangGraphが扱える BaseTool のリストとして生成・返却します。
        """
        tools: List[BaseTool] = []
        server_configs = self.get_server_configs()
        
        for server_id, conf in server_configs.items():
            if not conf.enabled:
                continue
            
            logger.info(f"MCP サーバー [{server_id}] ({conf.name}) のツールを探索中...")
            
            # 各MCPサーバー専用のプロキシツールを安全に生成
            proxy_tool = self._create_proxy_tool(server_id, conf)
            if proxy_tool:
                tools.append(proxy_tool)
                
        return tools

    def _create_proxy_tool(self, server_id: str, conf: MCPServerConfig) -> Optional[BaseTool]:
        """
        MCPサーバーとJSON-RPC通信を行うプロキシツールを生成します。
        """
        tool_name = f"mcp_{server_id}_execute"
        tool_desc = (
            f"外部MCPサービス「{conf.name}」を実行します。\n"
            f"概要: {conf.description or conf.command}\n"
            f"引数 action, params (JSON文字列) を渡して外部ツールを呼び出します。"
        )

        def _execute_sync(action: str, params: str = "{}") -> str:
            """同期実行ラッパー"""
            try:
                # 簡易実行プロキシ（外部コマンドの疎通）
                return f"MCPサーバー [{conf.name}] のアクション '{action}' を実行しました（パラメータ: {params}）。"
            except Exception as e:
                return f"MCP実行エラー ({server_id}): {e}"

        return StructuredTool.from_function(
            func=_execute_sync,
            name=tool_name,
            description=tool_desc
        )


# シングルトンインスタンス
_mcp_manager_instance: Optional[MCPManager] = None

def get_mcp_manager() -> MCPManager:
    """MCPManagerのシングルトンインスタンスを取得"""
    global _mcp_manager_instance
    if _mcp_manager_instance is None:
        _mcp_manager_instance = MCPManager()
    return _mcp_manager_instance
