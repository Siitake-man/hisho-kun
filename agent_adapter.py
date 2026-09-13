#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - Agent Approval Protocol ＆ アダプターモジュール (agent_adapter.py)

世界水準の AI Agent 承認プラットフォームとして、各社エージェント
(Claude Code, Cline, Cursor, Codex, Antigravity 等) からの
コマンド承認要請を統一プロトコル (共通DTO) へ正規化するモジュール。

アーキテクチャ規約:
- Pydantic v2 を用いた厳格な型付けとシリアライズ保証。
- アダプターパターンによるエージェント差分の隠蔽 (Open-Closed Principle)。
- 未知のフィールドも透過し、エージェント仕様変更への追随性を確保。
"""

import time
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RiskLevel(str, Enum):
    """コマンド実行の危険度判定レベル。

    Attributes:
        AUTO_ALLOW: 閲覧・テストなど副作用のない安全コマンド (自動即時承認)。
        PROMPT: 通常のファイル編集・インストールなど (スマホ通常承認)。
        STRICT: 削除・強制プッシュなど破壊的変更 (スマホ赤バナー警告承認)。
    """
    AUTO_ALLOW = "auto_allow"
    PROMPT = "prompt"
    STRICT = "strict"


class AgentApprovalRequest(BaseModel):
    """エージェント承認要請の共通統一DTO (Data Transfer Object)。

    すべての外部エージェントからの承認リクエストはこの型に正規化されて
    AgentBridgeHub およびスマホ Desk Pet (PWA) へ渡される。
    """
    model_config = ConfigDict(extra="allow")

    request_id: str = Field(default_factory=lambda: f"req_{uuid.uuid4().hex[:8]}")
    agent_type: str = "generic"
    agent_name: str = "AI Agent"
    command: str = ""
    summary: str = ""
    details: str = ""
    cwd: Optional[str] = None
    risk_level: RiskLevel = RiskLevel.PROMPT
    timeout_sec: int = 180
    requester_ip: str = ""
    created_at: float = Field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """ハブやPWA、データベースへ渡すためのシリアライズ辞書を返す。

        Returns:
            Dict[str, Any]: JSONシリアライズ可能な辞書表現。
        """
        d = self.model_dump()
        d["risk_level"] = self.risk_level.value
        return d


class BaseAgentAdapter(ABC):
    """各エージェント特有のペイロードを共通DTOへ変換するアダプター基底クラス。"""

    @abstractmethod
    def can_handle(self, raw_data: Dict[str, Any]) -> bool:
        """指定されたペイロードが自アダプターで処理可能かを判定する。

        Args:
            raw_data: 受信した生の辞書データ。

        Returns:
            bool: 処理可能な場合 True。
        """
        pass

    @abstractmethod
    def normalize(self, raw_data: Dict[str, Any], client_ip: str = "") -> AgentApprovalRequest:
        """生のペイロードを共通統一DTOへ正規化する。

        Args:
            raw_data: 受信した生の辞書データ。
            client_ip: リクエスト元のクライアントIPアドレス。

        Returns:
            AgentApprovalRequest: 正規化された共通DTO。
        """
        pass


class GenericAgentAdapter(BaseAgentAdapter):
    """ネオ秘書くん標準・汎用エージェント向けアダプター。"""

    def can_handle(self, raw_data: Dict[str, Any]) -> bool:
        """汎用アダプターは常にフォールバックとして処理可能。"""
        return True

    def normalize(self, raw_data: Dict[str, Any], client_ip: str = "") -> AgentApprovalRequest:
        agent_name = raw_data.get("agent_name") or raw_data.get("agent") or "AI Agent"
        command = raw_data.get("command") or ""
        summary = raw_data.get("summary") or (f"『{command}』の実行許可" if command else "コマンドの実行許可を求めています")
        details = raw_data.get("details") or ""
        cwd = raw_data.get("cwd")
        timeout_sec = int(raw_data.get("timeout") or raw_data.get("timeout_sec") or 180)
        request_id = raw_data.get("request_id") or f"req_{uuid.uuid4().hex[:8]}"

        raw_risk = raw_data.get("risk_level")
        risk_level = RiskLevel.PROMPT
        if isinstance(raw_risk, str):
            try:
                risk_level = RiskLevel(raw_risk.lower())
            except ValueError:
                risk_level = RiskLevel.PROMPT

        return AgentApprovalRequest(
            request_id=request_id,
            agent_type="generic",
            agent_name=agent_name,
            command=command,
            summary=summary,
            details=details,
            cwd=cwd,
            risk_level=risk_level,
            timeout_sec=timeout_sec,
            requester_ip=client_ip,
        )


class ClaudeCodeAdapter(BaseAgentAdapter):
    """Anthropic Claude Code 特有のツール呼び出し形式を正規化するアダプター。"""

    def can_handle(self, raw_data: Dict[str, Any]) -> bool:
        # tool_name が "Bash" または agent に "claude" が含まれる場合
        if raw_data.get("tool_name") == "Bash":
            return True
        agent = str(raw_data.get("agent", "")).lower()
        if "claude" in agent:
            return True
        return False

    def normalize(self, raw_data: Dict[str, Any], client_ip: str = "") -> AgentApprovalRequest:
        tool_input = raw_data.get("tool_input", {})
        command = ""
        summary = ""

        if isinstance(tool_input, dict):
            command = tool_input.get("command") or ""
            summary = tool_input.get("description") or tool_input.get("explanation") or ""
        elif isinstance(tool_input, str):
            command = tool_input

        if not command:
            command = raw_data.get("command") or ""

        if not summary:
            summary = raw_data.get("summary") or f"Claude Code: 『{command}』の実行許可"

        details = raw_data.get("details") or ""
        timeout_sec = int(raw_data.get("timeout") or raw_data.get("timeout_sec") or 180)

        return AgentApprovalRequest(
            agent_type="claude-code",
            agent_name="Claude Code",
            command=command,
            summary=summary,
            details=details,
            cwd=raw_data.get("cwd") or (tool_input.get("cwd") if isinstance(tool_input, dict) else None),
            timeout_sec=timeout_sec,
            requester_ip=client_ip,
        )


class ClineAdapter(BaseAgentAdapter):
    """Cline / Roo Code 特有のシグネチャを正規化するアダプター。"""

    def can_handle(self, raw_data: Dict[str, Any]) -> bool:
        source = str(raw_data.get("source", "")).lower()
        agent = str(raw_data.get("agent_name") or raw_data.get("agent", "")).lower()
        return "cline" in source or "cline" in agent or "roo" in source or "roo" in agent

    def normalize(self, raw_data: Dict[str, Any], client_ip: str = "") -> AgentApprovalRequest:
        command = raw_data.get("command") or ""
        summary = raw_data.get("explanation") or raw_data.get("summary") or f"Cline: 『{command}』の実行許可"
        details = raw_data.get("details") or ""
        cwd = raw_data.get("cwd")
        timeout_sec = int(raw_data.get("timeout") or raw_data.get("timeout_sec") or 180)

        return AgentApprovalRequest(
            agent_type="cline",
            agent_name="Cline",
            command=command,
            summary=summary,
            details=details,
            cwd=cwd,
            timeout_sec=timeout_sec,
            requester_ip=client_ip,
        )


class AgentAdapterRegistry:
    """登録された各社アダプターを管理し、ペイロードを自動判別して正規化するレジストリ。"""

    def __init__(self) -> None:
        # 判定の優先順位: 特化アダプター ➔ 最後に汎用フォールバック
        self._adapters: List[BaseAgentAdapter] = [
            ClaudeCodeAdapter(),
            ClineAdapter(),
            GenericAgentAdapter(),
        ]

    def register(self, adapter: BaseAgentAdapter, priority: int = 0) -> None:
        """新しいエージェントアダプターを登録する。

        Args:
            adapter: 登録するアダプターインスタンス。
            priority: 挿入位置 (0 は最優先)。
        """
        self._adapters.insert(priority, adapter)

    def normalize(self, raw_data: Dict[str, Any], client_ip: str = "") -> AgentApprovalRequest:
        """最適なアダプターを自動検索して共通DTOを生成する。

        Args:
            raw_data: 受信した生の辞書データ。
            client_ip: 要求元のIPアドレス。

        Returns:
            AgentApprovalRequest: 正規化された共通DTO。
        """
        for adapter in self._adapters:
            if adapter.can_handle(raw_data):
                return adapter.normalize(raw_data, client_ip=client_ip)
        # どの特化アダプターにもマッチしない場合は GenericAgentAdapter を強制使用
        return GenericAgentAdapter().normalize(raw_data, client_ip=client_ip)


# プロジェクト共通のシングルトンレジストリ
_DEFAULT_REGISTRY: Optional[AgentAdapterRegistry] = None


def get_default_adapter_registry() -> AgentAdapterRegistry:
    """デフォルトのアダプターレジストリインスタンスを返す。

    Returns:
        AgentAdapterRegistry: グローバルレジストリ。
    """
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = AgentAdapterRegistry()
    return _DEFAULT_REGISTRY
