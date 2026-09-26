#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_agent_approval_flow_e2e.py

Block 2 結合テスト:
AgentAdapter + ApprovalPolicy + AuditLogger が handle_agent_ask 経由で
正しく機能することをエンドツーエンドで検証する。
"""

import io
import json
import os
import tempfile
import time
import unittest
from typing import Any, Dict
from unittest.mock import MagicMock

from api_context import ApiContext


class MockSyncHandler:
    """テスト用の軽量 HTTP ハンドラモック"""

    def __init__(self) -> None:
        self.wfile = io.BytesIO()
        self.headers: Dict[str, str] = {}
        self.status_code = 200

    def send_response(self, code: int) -> None:
        self.status_code = code

    def send_header(self, key: str, value: str) -> None:
        self.headers[key] = value

    def end_headers(self) -> None:
        pass

    def _set_cors_headers(self) -> None:
        pass

    def get_json_response(self) -> Dict[str, Any]:
        """wfile に書き込まれた JSON レスポンスをパースして返す"""
        data = self.wfile.getvalue().decode("utf-8")
        return json.loads(data) if data else {}


class TestAgentApprovalFlowE2E(unittest.TestCase):
    """承認フロー結合テスト"""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_e2e.db")

        import database
        database.init_db(self.db_path)

        # 監査ロガーをテスト用DBに向ける
        import audit_logger
        self.audit_logger = audit_logger.AsyncAuditLogger(db_path=self.db_path)
        self.audit_logger.start()
        self._orig_logger = audit_logger._GLOBAL_AUDIT_LOGGER
        audit_logger._GLOBAL_AUDIT_LOGGER = self.audit_logger

    def tearDown(self) -> None:
        self.audit_logger.stop()
        import audit_logger
        audit_logger._GLOBAL_AUDIT_LOGGER = self._orig_logger
        self.temp_dir.cleanup()

    def _create_mock_context(self, body_dict: dict, client_ip: str = "127.0.0.1") -> ApiContext:
        handler = MockSyncHandler()
        body_bytes = json.dumps(body_dict).encode("utf-8")
        ctx = ApiContext(handler, body_bytes, client_ip, "TestAgent/1.0")
        return ctx

    def test_auto_allow_flow(self) -> None:
        """安全コマンドは即時自動承認され、人間をブロックせず監査ログに記録されること"""
        from api_agent_bridge import handle_agent_ask
        from audit_logger import get_audit_logs

        ctx = self._create_mock_context({
            "agent_name": "Claude Code",
            "command": "git status",
            "summary": "ステータス確認",
        })

        handle_agent_ask(ctx)

        # レスポンス検証
        payload = ctx.handler.get_json_response()
        self.assertEqual(payload.get("status"), "success")
        self.assertEqual(payload.get("decision"), "approve")
        self.assertEqual(payload.get("risk_level"), "auto_allow")
        self.assertIn("Auto-allowed", payload.get("message", ""))

        # 監査ログ検証 (フラッシュ待機 - 非同期キューの処理完了を確実化)
        self.audit_logger._queue.join()
        logs = get_audit_logs(db_path=self.db_path)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].command, "git status")
        self.assertEqual(logs[0].risk_level, "auto_allow")
        self.assertEqual(logs[0].decision, "approve")
        self.assertEqual(logs[0].decision_by, "policy_engine")

    def test_strict_flow_queued(self) -> None:
        """危険コマンドは STRICT と判定され、保留キューに risk_level='strict' で登録されること"""
        from api_agent_bridge import handle_agent_ask
        from local_sync_server import get_bridge_hub

        hub = get_bridge_hub()
        ctx = self._create_mock_context({
            "agent_name": "Cline",
            "command": "rm -rf dist/",
            "wait_decision": False,  # キューイング確認用
        })

        handle_agent_ask(ctx)

        payload = ctx.handler.get_json_response()
        self.assertEqual(payload.get("status"), "queued")
        self.assertEqual(payload.get("risk_level"), "strict")

        # Hub に保留されているか確認
        req_id = payload["request_id"]
        self.assertIn(req_id, hub.pending_requests)
        hub_req = hub.pending_requests[req_id]
        self.assertEqual(hub_req.risk_level, "strict")
        self.assertEqual(hub_req.agent_type, "cline")

        # クリーンアップ
        hub.pending_requests.pop(req_id, None)


if __name__ == "__main__":
    unittest.main()
