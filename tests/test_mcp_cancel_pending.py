"""hisho_mcp_server の execute_cancel_pending および wait_decision オプションの単体テスト."""

import unittest
from unittest.mock import patch, MagicMock
import hisho_mcp_server


class TestMcpCancelPending(unittest.TestCase):
    """MCPサーバー側のキャンセル・非同期送信機能のテスト."""

    @patch("hisho_mcp_server._post_to_hub")
    def test_execute_cancel_pending_success(self, mock_post):
        mock_post.return_value = {"status": "success", "result": "cancelled"}
        res = hisho_mcp_server.execute_cancel_pending(request_id="req_123", reason="resolved_on_pc")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["result"], "cancelled")
        mock_post.assert_called_once_with(
            "/api/agent/cancel_pending",
            {"request_id": "req_123", "reason": "resolved_on_pc"},
            timeout=5
        )

    @patch("hisho_mcp_server._post_to_hub")
    def test_execute_notify_user_input_needed_async(self, mock_post):
        mock_post.return_value = {"status": "success", "request_id": "req_999"}
        res = hisho_mcp_server.execute_notify_user_input_needed(
            question="テスト質問",
            choices="A,B",
            wait_decision=False
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["request_id"], "req_999")
        # wait_decision が False で送信されているか
        call_args = mock_post.call_args[0]
        self.assertEqual(call_args[0], "/api/agent/ask_input")
        self.assertFalse(call_args[1]["wait_decision"])


if __name__ == "__main__":
    unittest.main()
