"""AgentBridgeHub の保留中リクエスト取消 API (cancel_pending) の TDD 単体テスト."""

import json
import unittest
from local_sync_server import AgentBridgeHub, AgentBridgeRequest


class TestAgentBridgeHubCancelPending(unittest.TestCase):
    """AgentBridgeHub.cancel_pending および待機解放の検証."""

    def setUp(self) -> None:
        self.hub = AgentBridgeHub()

    def test_cancel_pending_success(self) -> None:
        """保留中のリクエストを正常に取り消し、status が cancelled になること."""
        req = self.hub.create_approval_request(
            agent_name="OpenCode",
            command="git status",
            summary="ステータス確認",
            requester_identity="agent",
        )
        self.assertIn(req.request_id, self.hub.pending_requests)

        res = self.hub.cancel_pending(req.request_id, reason="resolved_on_pc")
        self.assertEqual(res, "cancelled")
        self.assertEqual(req.status, "cancelled")
        self.assertEqual(req.decision_message, "resolved_on_pc")
        self.assertNotIn(req.request_id, self.hub.pending_requests)

    def test_cancel_pending_not_found(self) -> None:
        """存在しない request_id は not_found を返すこと."""
        res = self.hub.cancel_pending("req_nonexistent", reason="test")
        self.assertEqual(res, "not_found")

    def test_cancel_pending_already_resolved(self) -> None:
        """既に承認・解決済みのリクエストは already_resolved を返すこと."""
        req = self.hub.create_approval_request(
            agent_name="OpenCode",
            command="git diff",
            summary="差分確認",
            requester_identity="agent",
        )
        req.resolve("approved", "許可")

        res = self.hub.cancel_pending(req.request_id, reason="test")
        self.assertEqual(res, "already_resolved")

    def test_cancel_pending_unblocks_waiting_thread(self) -> None:
        """wait() で待機中のスレッドが cancel_pending によって即座に cancelled で解放されること."""
        req = self.hub.create_question_request(
            agent_name="Antigravity",
            question="確認してください",
            requester_identity="agent",
        )

        import threading
        result = []

        def wait_worker():
            decision = req.wait(timeout=5)
            result.append(decision)

        t = threading.Thread(target=wait_worker)
        t.start()

        # 別スレッドで取り消し
        self.hub.cancel_pending(req.request_id, reason="pc_clicked")
        t.join(timeout=2)

        self.assertFalse(t.is_alive())
        self.assertEqual(result, ["cancelled"])

    def test_cancel_pending_custom_request_id_and_prefix_match(self) -> None:
        """指定したカスタム request_id で生成され、プレフィックス差分があっても取り消せること."""
        custom_id = "opencode_perm_42"
        req = self.hub.create_question_request(
            agent_name="OpenCode",
            question="ファイル変更を許可しますか？",
            requester_identity="agent",
            request_id=f"perm:{custom_id}",
        )
        self.assertEqual(req.request_id, f"perm:{custom_id}")
        self.assertIn(f"perm:{custom_id}", self.hub.pending_requests)

        # プレフィックスなしの "opencode_perm_42" でも正しく取り消せること
        res = self.hub.cancel_pending(custom_id, reason="resolved_on_pc")
        self.assertEqual(res, "cancelled")
        self.assertNotIn(f"perm:{custom_id}", self.hub.pending_requests)
        self.assertEqual(req.status, "cancelled")


class DummyHandler:
    """ApiContext テスト用のダミー HTTP ハンドラ."""

    def __init__(self) -> None:
        import io
        self.wfile = io.BytesIO()
        self.response_status = None
        self.headers_written = []

    def send_response(self, status: int) -> None:
        self.response_status = status

    def send_header(self, key: str, value: str) -> None:
        self.headers_written.append((key, value))

    def _set_cors_headers(self) -> None:
        pass

    def end_headers(self) -> None:
        pass


class TestApiAgentCancelPending(unittest.TestCase):
    """POST /api/agent/cancel_pending ハンドラの検証."""

    def setUp(self) -> None:
        from local_sync_server import get_bridge_hub
        self.hub = get_bridge_hub()
        self.hub.pending_requests.clear()
        self.hub.history.clear()

    def test_handle_agent_cancel_pending_success(self) -> None:
        """API経由で正常に保留中リクエストを取り消せること."""
        from api_context import ApiContext
        from api_agent_bridge import handle_agent_cancel_pending

        req = self.hub.create_approval_request(
            agent_name="OpenCode",
            command="git status",
            summary="ステータス確認",
            requester_identity="agent",
        )

        handler = DummyHandler()
        body = json.dumps({"request_id": req.request_id, "reason": "resolved_on_pc"}).encode("utf-8")
        ctx = ApiContext(handler, body=body, client_ip="127.0.0.1", auth_identity="agent")

        handle_agent_cancel_pending(ctx)

        resp = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(resp.get("status"), "success")
        self.assertEqual(resp.get("result"), "cancelled")
        self.assertEqual(resp.get("request_id"), req.request_id)
        self.assertNotIn(req.request_id, self.hub.pending_requests)

    def test_handle_agent_cancel_pending_not_found(self) -> None:
        """存在しないIDの場合は not_found が返ること."""
        from api_context import ApiContext
        from api_agent_bridge import handle_agent_cancel_pending

        handler = DummyHandler()
        body = json.dumps({"request_id": "non_existent_id"}).encode("utf-8")
        ctx = ApiContext(handler, body=body, client_ip="127.0.0.1", auth_identity="agent")

        handle_agent_cancel_pending(ctx)

        resp = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(resp.get("status"), "not_found")
        self.assertEqual(resp.get("result"), "not_found")

    def test_handle_agent_cancel_pending_invalid_payload(self) -> None:
        """request_id が空の場合は 400 エラーになること."""
        from api_context import ApiContext
        from api_agent_bridge import handle_agent_cancel_pending

        handler = DummyHandler()
        body = json.dumps({"reason": "test"}).encode("utf-8")
        ctx = ApiContext(handler, body=body, client_ip="127.0.0.1", auth_identity="agent")

        handle_agent_cancel_pending(ctx)

        self.assertEqual(handler.response_status, 400)


if __name__ == "__main__":
    unittest.main()
