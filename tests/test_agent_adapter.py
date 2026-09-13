#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_agent_adapter.py

Block 2 Node A: Agent Approval Protocol ＆ 共通DTO の単体テスト (TDD)
"""

import unittest
from typing import Any, Dict


class TestAgentApprovalRequestDTO(unittest.TestCase):
    """共通DTO AgentApprovalRequest の契約テスト"""

    def test_create_minimal_approval_request(self) -> None:
        """最小限のパラメータでDTOが正常生成されること"""
        from agent_adapter import AgentApprovalRequest, RiskLevel

        req = AgentApprovalRequest(
            agent_name="TestAgent",
            command="git status",
        )
        self.assertTrue(req.request_id.startswith("req_"))
        self.assertEqual(req.agent_name, "TestAgent")
        self.assertEqual(req.command, "git status")
        self.assertEqual(req.agent_type, "generic")
        self.assertEqual(req.risk_level, RiskLevel.PROMPT)
        self.assertEqual(req.timeout_sec, 180)
        self.assertGreater(req.created_at, 0)

    def test_create_full_approval_request(self) -> None:
        """全パラメータを指定してDTOが生成されること"""
        from agent_adapter import AgentApprovalRequest, RiskLevel

        req = AgentApprovalRequest(
            request_id="custom_req_001",
            agent_type="claude-code",
            agent_name="Claude Code",
            command="rm -rf dist/",
            summary="ビルド成果物の削除",
            details="dist/ 以下の全ファイルをクリーンアップします",
            cwd="/workspace/project",
            risk_level=RiskLevel.STRICT,
            timeout_sec=60,
            requester_ip="127.0.0.1",
        )
        self.assertEqual(req.request_id, "custom_req_001")
        self.assertEqual(req.agent_type, "claude-code")
        self.assertEqual(req.risk_level, RiskLevel.STRICT)
        self.assertEqual(req.cwd, "/workspace/project")
        self.assertEqual(req.requester_ip, "127.0.0.1")

    def test_dto_serialization_to_dict(self) -> None:
        """PWAやHubへ渡すための辞書シリアライズが互換性を維持していること"""
        from agent_adapter import AgentApprovalRequest, RiskLevel

        req = AgentApprovalRequest(
            agent_name="Cline",
            command="npm install",
            summary="依存関係のインストール",
        )
        d = req.to_dict()
        self.assertEqual(d["agent_name"], "Cline")
        self.assertEqual(d["command"], "npm install")
        self.assertEqual(d["risk_level"], "prompt")
        self.assertIn("request_id", d)
        self.assertIn("created_at", d)


class TestAgentAdapters(unittest.TestCase):
    """各エージェント専用アダプターの正規化テスト"""

    def test_generic_adapter(self) -> None:
        """従来のネオ秘書くん汎用ペイロードが正規化されること"""
        from agent_adapter import GenericAgentAdapter, RiskLevel

        adapter = GenericAgentAdapter()
        raw = {
            "agent_name": "Antigravity",
            "command": "git push origin main",
            "summary": "最新コードのプッシュ",
            "details": "コミット f5146b8 をプッシュ",
            "timeout": 120,
        }
        self.assertTrue(adapter.can_handle(raw))
        req = adapter.normalize(raw, client_ip="192.168.1.50")
        self.assertEqual(req.agent_name, "Antigravity")
        self.assertEqual(req.agent_type, "generic")
        self.assertEqual(req.command, "git push origin main")
        self.assertEqual(req.timeout_sec, 120)
        self.assertEqual(req.requester_ip, "192.168.1.50")

    def test_claude_code_adapter(self) -> None:
        """Claude Code 形式のペイロードが正しく認識・正規化されること"""
        from agent_adapter import ClaudeCodeAdapter

        adapter = ClaudeCodeAdapter()
        # Claude Code 特有のシグネチャ (tool_name="Bash" 等)
        raw = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "pytest tests/ -v",
                "description": "テストスイートの全件実行"
            },
            "agent": "claude-code",
        }
        self.assertTrue(adapter.can_handle(raw))
        req = adapter.normalize(raw, client_ip="127.0.0.1")
        self.assertEqual(req.agent_type, "claude-code")
        self.assertEqual(req.agent_name, "Claude Code")
        self.assertEqual(req.command, "pytest tests/ -v")
        self.assertEqual(req.summary, "テストスイートの全件実行")

    def test_cline_adapter(self) -> None:
        """Cline 形式のペイロードが正しく認識・正規化されること"""
        from agent_adapter import ClineAdapter

        adapter = ClineAdapter()
        raw = {
            "source": "cline",
            "command": "cargo build --release",
            "cwd": "C:/Project/RustApp",
            "explanation": "リリースビルドの実行",
        }
        self.assertTrue(adapter.can_handle(raw))
        req = adapter.normalize(raw, client_ip="127.0.0.1")
        self.assertEqual(req.agent_type, "cline")
        self.assertEqual(req.agent_name, "Cline")
        self.assertEqual(req.command, "cargo build --release")
        self.assertEqual(req.cwd, "C:/Project/RustApp")
        self.assertEqual(req.summary, "リリースビルドの実行")


class TestAgentAdapterRegistry(unittest.TestCase):
    """アダプターレジストリ（ディスパッチャー）のテスト"""

    def test_registry_auto_dispatch(self) -> None:
        """レジストリが自動で適切なアダプターを選択して共通DTOを返すこと"""
        from agent_adapter import AgentAdapterRegistry

        registry = AgentAdapterRegistry()

        # Claude Code ペイロード
        req_claude = registry.normalize({
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"}
        })
        self.assertEqual(req_claude.agent_type, "claude-code")

        # Cline ペイロード
        req_cline = registry.normalize({
            "source": "cline",
            "command": "dir",
        })
        self.assertEqual(req_cline.agent_type, "cline")

        # 汎用ペイロード
        req_generic = registry.normalize({
            "agent_name": "CustomBot",
            "command": "python test.py",
        })
        self.assertEqual(req_generic.agent_type, "generic")
        self.assertEqual(req_generic.agent_name, "CustomBot")


if __name__ == "__main__":
    unittest.main()
