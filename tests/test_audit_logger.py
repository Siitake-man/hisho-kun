#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_audit_logger.py

Block 2 Node C: Audit Log 承認監査ログ基盤の単体テスト (TDD)
"""

import os
import tempfile
import time
import unittest
from typing import List


class TestAuditLogger(unittest.TestCase):
    """承認監査ログの永続化・クエリのテスト"""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_audit.db")

        # データベース初期化
        import database
        database.init_db(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_record_and_get_audit_log(self) -> None:
        """監査ログが正常に記録され、取得できること"""
        from audit_logger import AuditLogEntry, record_audit_log, get_audit_logs

        entry = AuditLogEntry(
            request_id="req_test_123",
            agent_type="claude-code",
            agent_name="Claude Code",
            command="git push origin main",
            summary="本番コードのプッシュ",
            risk_level="prompt",
            decision="approved",
            decision_by="human",
            decision_message="ボスによるワンタップ承認",
            requester_ip="127.0.0.1",
            client_ip="192.168.1.15",
            duration_sec=4.5,
            created_at=int(time.time()),
        )
        log_id = record_audit_log(entry, db_path=self.db_path)
        self.assertGreater(log_id, 0)

        # 取得検証
        logs = get_audit_logs(db_path=self.db_path)
        self.assertEqual(len(logs), 1)
        retrieved = logs[0]
        self.assertEqual(retrieved.request_id, "req_test_123")
        self.assertEqual(retrieved.agent_type, "claude-code")
        self.assertEqual(retrieved.command, "git push origin main")
        self.assertEqual(retrieved.decision, "approved")
        self.assertEqual(retrieved.decision_by, "human")
        self.assertAlmostEqual(retrieved.duration_sec, 4.5, places=1)

    def test_filter_audit_logs_by_agent_type(self) -> None:
        """エージェントタイプ別にフィルタリング取得できること"""
        from audit_logger import AuditLogEntry, record_audit_log, get_audit_logs

        # 2種類のエージェントのログを記録
        record_audit_log(AuditLogEntry(
            request_id="req_1", agent_type="claude-code", agent_name="Claude Code",
            command="ls", risk_level="auto_allow", decision="auto_allowed",
            decision_by="policy_engine", created_at=int(time.time()),
        ), db_path=self.db_path)

        record_audit_log(AuditLogEntry(
            request_id="req_2", agent_type="cline", agent_name="Cline",
            command="npm test", risk_level="auto_allow", decision="auto_allowed",
            decision_by="policy_engine", created_at=int(time.time()),
        ), db_path=self.db_path)

        # フィルタリング
        claude_logs = get_audit_logs(agent_type="claude-code", db_path=self.db_path)
        self.assertEqual(len(claude_logs), 1)
        self.assertEqual(claude_logs[0].request_id, "req_1")

        cline_logs = get_audit_logs(agent_type="cline", db_path=self.db_path)
        self.assertEqual(len(cline_logs), 1)
        self.assertEqual(cline_logs[0].request_id, "req_2")


if __name__ == "__main__":
    unittest.main()
