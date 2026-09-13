# -*- coding: utf-8 -*-
"""エージェント承認プラットフォームの失敗モード・セキュリティ境界テスト。

Block 3 仕様:
1. 期限切れ（Expired / Timeout）後の遅延応答の拒否
2. 自己承認（同一IPからの承認要請・実行）の拒否（RCE防止ガード）
3. 重複タップ・リトライ時の冪等性（Idempotency）保証
4. 存在しないリクエストIDの安全な処理
5. HTTP API (/api/agent/respond) レベルのレスポンス契約テスト
"""

import io
import json
import time
import unittest
from typing import Any, Dict, Optional
from unittest.mock import patch

from local_sync_server import AgentBridgeHub, AgentBridgeRequest
import api_agent_bridge
from api_context import ApiContext


class MockSyncHandler:
    """テスト用の軽量 HTTP ハンドラモック"""

    def __init__(self, client_ip: str = "192.168.1.100") -> None:
        self.wfile = io.BytesIO()
        self.headers: Dict[str, str] = {}
        self.status_code = 200
        self.client_address = (client_ip, 54321)

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


class TestAgentFailureModes(unittest.TestCase):
    """承認プラットフォームの失敗モードおよびセキュリティ検証 (Hub レベル)。"""

    def setUp(self) -> None:
        """テストごとにクリーンな Hub を用意。"""
        self.hub = AgentBridgeHub()

    def test_expired_request_rejection(self) -> None:
        """期限切れ（timeout_at 超過）リクエストの応答が 'expired' で拒否されること。"""
        req = self.hub.create_approval_request(
            command="git pull",
            summary="コードの更新",
            agent_name="TestAgent",
            requester_ip="127.0.0.1",
            risk_level="prompt",
        )
        req.timeout_at = time.time() - 5.0

        ok, reason = self.hub.respond_checked(
            request_id=req.request_id,
            decision="approve",
            message="",
            responder_ip="192.168.1.100",
        )

        self.assertFalse(ok, "期限切れリクエストの応答は失敗しなければならない")
        self.assertEqual(reason, "expired", "理由コードは 'expired' でなければならない")
        self.assertEqual(req.status, "expired", "リクエスト状態が expired に遷移すること")

    def test_self_approval_denied_same_ip(self) -> None:
        """要求元と応答元の IP が同一の場合、自己承認として拒否されること。"""
        attacker_ip = "192.168.1.50"
        req = self.hub.create_approval_request(
            command="rm -rf /",
            summary="危険なコマンド",
            agent_name="MaliciousAgent",
            requester_ip=attacker_ip,
            risk_level="strict",
        )

        ok, reason = self.hub.respond_checked(
            request_id=req.request_id,
            decision="approve",
            message="自分で承認します",
            responder_ip=attacker_ip,
        )

        self.assertFalse(ok, "同一IPからの自己承認は拒否されなければならない")
        self.assertEqual(reason, "self_approve_denied")
        self.assertEqual(req.status, "pending", "リクエストは pending のままで承認されてはならない")

        # 別のスマホIPからの承認であれば通過すること
        mobile_ip = "192.168.1.100"
        ok_mobile, reason_mobile = self.hub.respond_checked(
            request_id=req.request_id,
            decision="approve",
            message="人間がスマホから承認",
            responder_ip=mobile_ip,
        )
        self.assertTrue(ok_mobile, "正当なスマホ端末からの承認は成功すること")
        self.assertEqual(reason_mobile, "ok")
        self.assertEqual(req.status, "approve")

    def test_unknown_request_returns_not_found(self) -> None:
        """存在しないリクエストIDに対する応答は 'not_found' で返ること。"""
        ok, reason = self.hub.respond_checked(
            request_id="non-existent-uuid-9999",
            decision="approve",
            message="",
            responder_ip="192.168.1.100",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "not_found")

    def test_idempotent_duplicate_response(self) -> None:
        """既済リクエストに対する重複タップ・リトライが安全に冪等処理されること。"""
        req = self.hub.create_approval_request(
            command="pytest",
            summary="テスト実行",
            agent_name="ClaudeCode",
            requester_ip="127.0.0.1",
            risk_level="prompt",
        )

        # 1回目の承認
        ok1, reason1 = self.hub.respond_checked(
            request_id=req.request_id,
            decision="approve",
            message="OK",
            responder_ip="192.168.1.100",
        )
        self.assertTrue(ok1)
        self.assertEqual(reason1, "ok")

        # 2回目の同一承認（Wi-Fi瞬断や連打による再送）
        ok2, reason2 = self.hub.respond_checked(
            request_id=req.request_id,
            decision="approve",
            message="OK",
            responder_ip="192.168.1.100",
        )
        self.assertIn(
            reason2,
            ("ok", "already_resolved", "duplicate"),
            "既済リクエストへの同一判定の再送は冪等に受け入れられるべき",
        )
        self.assertTrue(ok2, "同一判定の重複再送は成功扱い（エラーとしない）とすべき")


class TestAgentRespondApiContract(unittest.TestCase):
    """POST /api/agent/respond の API 契約テスト。"""

    def setUp(self) -> None:
        self.hub = AgentBridgeHub()
        # local_sync_server.get_bridge_hub をパッチ
        self.hub_patcher = patch("local_sync_server.get_bridge_hub", return_value=self.hub)
        self.hub_patcher.start()

    def tearDown(self) -> None:
        self.hub_patcher.stop()

    def _call_respond_api(
        self, body: Dict[str, Any], client_ip: str = "192.168.1.100"
    ) -> Dict[str, Any]:
        handler = MockSyncHandler(client_ip=client_ip)
        ctx = ApiContext(
            handler=handler,  # type: ignore
            body=json.dumps(body).encode("utf-8"),
            client_ip=client_ip,
            user_agent="NeoHishoDeskPet/1.0",
        )
        api_agent_bridge.handle_agent_respond(ctx)
        return handler.get_json_response()

    def test_api_self_approval_denied_contract(self) -> None:
        """自己承認時に status: 'error', reason: 'self_approve_denied' が返ること。"""
        requester_ip = "192.168.1.50"
        req = self.hub.create_approval_request(
            command="format C:",
            summary="危険",
            agent_name="AgentX",
            requester_ip=requester_ip,
            risk_level="strict",
        )

        res = self._call_respond_api(
            {"request_id": req.request_id, "decision": "approve"},
            client_ip=requester_ip,  # 要求元と同一IP
        )
        self.assertEqual(res.get("status"), "error")
        self.assertEqual(res.get("reason"), "self_approve_denied")
        self.assertIn("自己承認は禁止", res.get("message", ""))

    def test_api_expired_contract(self) -> None:
        """期限切れ時に status: 'expired', reason: 'expired' が返ること。"""
        req = self.hub.create_approval_request(
            command="ls",
            summary="確認",
            agent_name="AgentY",
            requester_ip="127.0.0.1",
        )
        req.timeout_at = time.time() - 10.0

        res = self._call_respond_api(
            {"request_id": req.request_id, "decision": "approve"},
            client_ip="192.168.1.100",
        )
        self.assertEqual(res.get("status"), "expired")
        self.assertEqual(res.get("reason"), "expired")
        self.assertIn("期限切れ", res.get("message", ""))

    def test_api_duplicate_tap_contract(self) -> None:
        """重複タップ時に status: 'success', duplicate: True が返ること。"""
        req = self.hub.create_approval_request(
            command="echo hello",
            summary="テスト",
            agent_name="AgentZ",
            requester_ip="127.0.0.1",
        )

        # 1回目
        res1 = self._call_respond_api(
            {"request_id": req.request_id, "decision": "approve"},
            client_ip="192.168.1.100",
        )
        self.assertEqual(res1.get("status"), "success")

        # 2回目 (重複タップ)
        res2 = self._call_respond_api(
            {"request_id": req.request_id, "decision": "approve"},
            client_ip="192.168.1.100",
        )
        self.assertEqual(res2.get("status"), "success")
        self.assertTrue(res2.get("duplicate"))
        self.assertEqual(res2.get("reason"), "already_resolved")


if __name__ == "__main__":
    unittest.main()
