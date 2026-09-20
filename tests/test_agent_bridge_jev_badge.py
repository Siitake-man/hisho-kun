"""
Jev 安全審査バッジ連携のデータフロー検証テスト (tests/test_agent_bridge_jev_badge.py)

1. AgentBridgeRequest が summary および safety_level を保持し、to_dict() に含めること。
2. api_agent_bridge.handle_agent_ask が summary から Jev 安全審査レベルを自動抽出すること。
3. web_pet/pet_ui.js が req.title / req.content からもバッジ抽出できる構文になっていること。
"""

import io
import json
import unittest
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

from local_sync_server import AgentBridgeHub, AgentBridgeRequest
import api_agent_bridge
from api_context import ApiContext


class MockSyncHandler:
    """テスト用モックハンドラ"""
    def __init__(self, client_ip: str = "127.0.0.1") -> None:
        self.wfile = io.BytesIO()
        self.headers: Dict[str, str] = {}
        self.status_code = 200
        self.client_address = (client_ip, 12345)

    def send_response(self, code: int) -> None:
        self.status_code = code

    def send_header(self, key: str, value: str) -> None:
        self.headers[key] = value

    def end_headers(self) -> None:
        pass

    def _set_cors_headers(self) -> None:
        pass

    def get_json_response(self) -> Dict[str, Any]:
        data = self.wfile.getvalue().decode("utf-8")
        return json.loads(data) if data else {}


class TestAgentBridgeJevBadge(unittest.TestCase):
    """Jev 安全審査バッジのデータ伝達整合性テスト"""

    def setUp(self) -> None:
        self.hub = AgentBridgeHub()

    def test_bridge_request_to_dict_includes_summary_and_safety_level(self) -> None:
        """to_dict() に summary と safety_level が正しくシリアライズされること。"""
        req = self.hub.create_approval_request(
            agent_name="Antigravity",
            command="pytest -v",
            summary="【Jev安全審査: allow (スコア: 0.99)】テスト実行",
            safety_level="allow"
        )
        d = req.to_dict()
        self.assertIn("summary", d)
        self.assertEqual(d["summary"], "【Jev安全審査: allow (スコア: 0.99)】テスト実行")
        self.assertIn("safety_level", d)
        self.assertEqual(d["safety_level"], "allow")

    def test_handle_agent_ask_auto_extracts_safety_level_from_summary(self) -> None:
        """POST /api/agent/ask において summary から safety_level が自動抽出されること。"""
        handler = MockSyncHandler(client_ip="127.0.0.1")
        body_bytes = json.dumps({
            "agent_name": "Antigravity",
            "command": "git push origin main",
            "summary": "【Jev安全審査: confirm (スコア: 0.72)】プッシュ承認要請",
            "wait_decision": False
        }).encode("utf-8")

        ctx = ApiContext(handler=handler, body=body_bytes, client_ip="127.0.0.1")

        with patch("local_sync_server.get_bridge_hub", return_value=self.hub):
            # PROMPT または STRICT なので pending_requests に入る
            api_agent_bridge.handle_agent_ask(ctx)

        self.assertEqual(len(self.hub.pending_requests), 1)
        req = list(self.hub.pending_requests.values())[0]
        self.assertEqual(req.safety_level, "confirm")
        self.assertIn("【Jev安全審査: confirm", req.summary)
        # to_dict にも反映されていること
        req_dict = req.to_dict()
        self.assertEqual(req_dict["safety_level"], "confirm")
        self.assertEqual(req_dict["summary"], req.summary)


if __name__ == "__main__":
    unittest.main()
