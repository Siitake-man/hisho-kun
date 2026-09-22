#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - Web Push サーバ側実装の整合性テスト (tests/test_web_push_server.py)

スマホ PWA への Web Push (Service Worker + VAPID) 導入に伴い、以下を検証する:

  1. storage/push_subscription_repo.py: 購読台帳 (push_subscriptions) の CRUD
  2. storage/vapid_key_repo.py: VAPID 鍵ペアの生成・永続化 (再起動後も同一鍵)
  3. push_sender.py: pywebpush 送信・無効購読 (404/410) の掃除・Fail-Safe・
     daemon スレッドによるノンブロッキング送信
  4. api_push.py: subscribe / unsubscribe の入力検証 (ゼロトラスト)
  5. local_sync_server / api_agent_bridge / reminder_engine への配線

TDD: 実装前に本ファイルを実行すると ImportError / AssertionError で Red となる。
"""

import hashlib
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import init_db
from storage.models import Task, VapidKeys
from storage.push_subscription_repo import (
    upsert_subscription,
    get_all_subscriptions,
    delete_subscription_by_endpoint,
    delete_subscriptions_by_token_hash,
)
from storage.vapid_key_repo import get_or_create_vapid_keys
from push_sender import send_push_to_all_devices, _deliver_push_sync
from api_push import handle_push_subscribe, handle_push_unsubscribe


def _make_ctx(body: Dict[str, Any], bearer: str = "device-token-abc") -> Any:
    """単体テスト用の ApiContext モック (MockHandler + 実 ApiContext) を生成する。

    Args:
        body: JSON 化してボディへ載せる辞書。
        bearer: MockHandler が返す Bearer トークン (空文字なら認証ヘッダ無し)。

    Returns:
        (MockHandler インスタンス, ApiContext インスタンス) のタプル。
    """
    from api_context import ApiContext

    class MockHandler:
        """send_response / wfile をスタブした HTTP ハンドラ代替。"""

        def __init__(self) -> None:
            self.headers: Dict[str, str] = (
                {"Authorization": f"Bearer {bearer}"} if bearer else {}
            )
            self.wfile_buffer = b""
            self.wfile = self
            self.status_code: int | None = None
            self.written_json: Dict[str, Any] | None = None

        def _get_bearer_token(self) -> str:
            """実ハンドラと同一契約の Bearer 抽出 (api_push._get_bearer_token が呼ぶ)。"""
            return bearer

        def send_response(self, status_code: int) -> None:
            self.status_code = status_code

        def send_header(self, name: str, value: str) -> None:
            return None

        def _set_cors_headers(self) -> None:
            return None

        def end_headers(self) -> None:
            return None

        def write(self, data: bytes) -> int:
            self.wfile_buffer += data
            try:
                self.written_json = json.loads(data.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self.written_json = None
            return len(data)

    handler = MockHandler()
    ctx = ApiContext(handler, json.dumps(body).encode("utf-8"), "127.0.0.1", "pytest")
    return handler, ctx


def _make_webpush_exception(status_code: int) -> Exception:
    """テスト用に指定ステータスコードを持つ WebPushException を構築する。

    pywebpush 実物は Push Service が 404/410 を返すと WebPushException を送出し、
    その ``status_code`` プロパティが応答コードを露出する契約である。

    Args:
        status_code: WebPushException に持たせる HTTP ステータスコード。

    Returns:
        response にモックを結合した WebPushException。
    """
    from pywebpush import WebPushException

    exc = WebPushException(f"push service returned {status_code}")
    exc.response = MagicMock(status_code=status_code)
    return exc


class TestPushSubscriptionRepo(unittest.TestCase):
    """購読リポジトリ (push_subscriptions テーブル) の CRUD 操作を検証する。"""

    def setUp(self) -> None:
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        init_db(self.db_path)

    def tearDown(self) -> None:
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_upsert_and_get_all(self) -> None:
        """upsert → get_all_subscriptions で全項性が復元されることを保証する。"""
        sub_id = upsert_subscription(
            token_hash="hash_a",
            endpoint="https://push.example.com/sub1",
            p256dh="pkey111",
            auth="auth111",
            db_path=self.db_path,
        )
        self.assertIsInstance(sub_id, int)
        self.assertGreater(sub_id, 0)

        subs = get_all_subscriptions(db_path=self.db_path)
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0].token_hash, "hash_a")
        self.assertEqual(subs[0].endpoint, "https://push.example.com/sub1")
        self.assertEqual(subs[0].p256dh, "pkey111")
        self.assertEqual(subs[0].auth, "auth111")

    def test_upsert_same_endpoint_updates_row(self) -> None:
        """同一 endpoint の再 upsert で行が増えず、鍵と token_hash が更新されることを保証する。"""
        upsert_subscription("hash_old", "https://push.example.com/same", "pkey_old", "auth_old", db_path=self.db_path)
        upsert_subscription("hash_new", "https://push.example.com/same", "pkey_new", "auth_new", db_path=self.db_path)

        subs = get_all_subscriptions(db_path=self.db_path)
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0].token_hash, "hash_new")
        self.assertEqual(subs[0].p256dh, "pkey_new")
        self.assertEqual(subs[0].auth, "auth_new")

    def test_delete_subscription_by_endpoint(self) -> None:
        """endpoint 指定削除は True を返し、次回以降は False を返すことを保証する。"""
        upsert_subscription("hash_a", "https://push.example.com/del1", "p", "a", db_path=self.db_path)
        self.assertTrue(delete_subscription_by_endpoint("https://push.example.com/del1", db_path=self.db_path))
        self.assertFalse(delete_subscription_by_endpoint("https://push.example.com/del1", db_path=self.db_path))
        self.assertEqual(get_all_subscriptions(db_path=self.db_path), [])

    def test_delete_subscriptions_by_token_hash(self) -> None:
        """token_hash 指定の一括削除で削除件数が返ることを保証する。"""
        upsert_subscription("hash_x", "https://push.example.com/x1", "p", "a", db_path=self.db_path)
        upsert_subscription("hash_x", "https://push.example.com/x2", "p", "a", db_path=self.db_path)
        upsert_subscription("hash_y", "https://push.example.com/y1", "p", "a", db_path=self.db_path)

        deleted = delete_subscriptions_by_token_hash("hash_x", db_path=self.db_path)
        self.assertEqual(deleted, 2)
        remaining = get_all_subscriptions(db_path=self.db_path)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].token_hash, "hash_y")


class TestVapidKeyRepo(unittest.TestCase):
    """VAPID 鍵ペアの永続化と再利用操作を検証する。"""

    def setUp(self) -> None:
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        init_db(self.db_path)

    def tearDown(self) -> None:
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_get_or_create_returns_same_key(self) -> None:
        """2回呼び出して同一の public_key が返る（再生成が起きない）ことを保証する。"""
        keys1 = get_or_create_vapid_keys(db_path=self.db_path)
        keys2 = get_or_create_vapid_keys(db_path=self.db_path)
        self.assertIsInstance(keys1, VapidKeys)
        self.assertEqual(keys1.public_key, keys2.public_key)
        self.assertEqual(keys1.private_key_pem, keys2.private_key_pem)
        self.assertTrue(keys1.public_key)
        self.assertTrue(keys1.private_key_pem)
        self.assertTrue(keys1.subject.startswith("mailto:"))

    def test_persisted_key_survives_reopen(self) -> None:
        """生成した鍵ペアが DB に永続化され、再接続からも同一ペアが読めることを保証する。"""
        keys1 = get_or_create_vapid_keys(db_path=self.db_path)
        keys2 = get_or_create_vapid_keys(db_path=self.db_path)
        self.assertEqual(keys1.public_key, keys2.public_key)


class TestPushSender(unittest.TestCase):
    """push_sender の送信・掃除・例外継続ロジックを検証する（pywebpush はモック）。"""

    def setUp(self) -> None:
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        init_db(self.db_path)

    def tearDown(self) -> None:
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_zero_subscriptions_returns_immediately(self) -> None:
        """購読 0 件時は何も送信せず即 return することを保証する。"""
        with patch("push_sender.webpush") as mock_wp:
            _deliver_push_sync("テスト", "本文", None, "generic", db_path=self.db_path)
            mock_wp.assert_not_called()

    def test_send_push_to_all_devices(self) -> None:
        """全購読へ送信ペイロードが届くことを検証する（pywebpush モック）。"""
        upsert_subscription("h1", "https://push.example.com/a", "pk_a", "au_a", db_path=self.db_path)
        upsert_subscription("h2", "https://push.example.com/b", "pk_b", "au_b", db_path=self.db_path)

        with patch("push_sender.webpush") as mock_wp:
            _deliver_push_sync("完了", "作業が完了しました", "tag_x", "task_done", db_path=self.db_path)
            self.assertEqual(mock_wp.call_count, 2)
            kwargs = mock_wp.call_args.kwargs
            payload = json.loads(kwargs["data"])
            self.assertEqual(payload["title"], "完了")
            self.assertEqual(payload["body"], "作業が完了しました")
            self.assertEqual(payload["tag"], "tag_x")
            self.assertEqual(payload["event_type"], "task_done")
            self.assertIn("timestamp", payload)
            self.assertIn("subscription_info", kwargs)

    def test_404_subscription_is_cleaned_up(self) -> None:
        """404 応答の購読が DB から削除され、他の購読には影響しないことを検証する。"""
        upsert_subscription("h1", "https://push.example.com/dead", "pk", "au", db_path=self.db_path)
        upsert_subscription("h2", "https://push.example.com/alive", "pk", "au", db_path=self.db_path)

        def fake_webpush(subscription_info: Dict[str, Any], **kwargs: Any) -> MagicMock:
            if subscription_info["endpoint"] == "https://push.example.com/dead":
                raise _make_webpush_exception(404)
            return MagicMock(status_code=201)

        with patch("push_sender.webpush", side_effect=fake_webpush):
            _deliver_push_sync("配信", "本文", None, "generic", db_path=self.db_path)

        endpoints = [s.endpoint for s in get_all_subscriptions(db_path=self.db_path)]
        self.assertNotIn("https://push.example.com/dead", endpoints)
        self.assertIn("https://push.example.com/alive", endpoints)

    def test_410_subscription_is_cleaned_up(self) -> None:
        """410 Gone 応答の購読も削除対象となることを検証する。"""
        upsert_subscription("h1", "https://push.example.com/gone", "pk", "au", db_path=self.db_path)

        def fake_webpush(subscription_info: Dict[str, Any], **kwargs: Any) -> MagicMock:
            raise _make_webpush_exception(410)

        with patch("push_sender.webpush", side_effect=fake_webpush):
            _deliver_push_sync("配信", "本文", None, "generic", db_path=self.db_path)

        self.assertEqual(get_all_subscriptions(db_path=self.db_path), [])

    def test_exception_continues_other_sends(self) -> None:
        """1件で例外が起きても他の宛先への送信が継続されることを検証する。"""
        upsert_subscription("h1", "https://push.example.com/err", "pk", "au", db_path=self.db_path)
        upsert_subscription("h2", "https://push.example.com/ok", "pk", "au", db_path=self.db_path)

        def fake_webpush(subscription_info: Dict[str, Any], **kwargs: Any) -> MagicMock:
            if subscription_info["endpoint"] == "https://push.example.com/err":
                raise ConnectionError("network down")
            return MagicMock(status_code=201)

        with patch("push_sender.webpush", side_effect=fake_webpush):
            # 例外が外へ漏れ出さない（Fail-Safe）こと
            _deliver_push_sync("配信", "本文", None, "generic", db_path=self.db_path)

        # どちらも削除されていない（404/410 以外は掃除しない）
        endpoints = [s.endpoint for s in get_all_subscriptions(db_path=self.db_path)]
        self.assertIn("https://push.example.com/err", endpoints)
        self.assertIn("https://push.example.com/ok", endpoints)

    def test_send_push_to_all_devices_is_non_blocking(self) -> None:
        """公開 API send_push_to_all_devices が daemon スレッドで fire-and-forget であることを検証する。"""
        done = threading.Event()

        def fake_webpush(subscription_info: Dict[str, Any], **kwargs: Any) -> MagicMock:
            done.set()
            return MagicMock(status_code=201)

        upsert_subscription("h1", "https://push.example.com/bg", "pk", "au", db_path=self.db_path)
        with patch("push_sender.webpush", side_effect=fake_webpush):
            send_push_to_all_devices("題名", "テスト", db_path=self.db_path)
            self.assertTrue(done.wait(timeout=5.0), "バックグラウンドスレッドで送信が完了しませんでした")


class TestApiPushHandlers(unittest.TestCase):
    """api_push の subscribe / unsubscribe ハンドラの入力検証操作を検証する。"""

    def setUp(self) -> None:
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        init_db(self.db_path)
        self.bearer = "device-bearer-token-xyz"
        self.token_hash = hashlib.sha256(self.bearer.encode("utf-8")).hexdigest()

    def tearDown(self) -> None:
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_subscribe_success(self) -> None:
        """正常な subscribe は 200 {"status": "ok"} を返し台帳へ登録されることを検証する。"""
        body = {
            "endpoint": "https://push.example.com/sub",
            "keys": {"p256dh": "pkey_abc", "auth": "auth_abc"},
        }
        handler, ctx = _make_ctx(body, bearer=self.bearer)

        with patch("api_push.verify_device_token") as mock_verify, \
             patch("api_push._resolve_db_path", return_value=self.db_path):
            mock_verify.return_value = MagicMock(token_hash=self.token_hash, is_revoked=0)
            handle_push_subscribe(ctx)

        self.assertEqual(handler.status_code, 200)
        assert handler.written_json is not None
        self.assertEqual(handler.written_json["status"], "ok")
        subs = get_all_subscriptions(db_path=self.db_path)
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0].token_hash, self.token_hash)

    def test_subscribe_missing_fields_returns_400(self) -> None:
        """endpoint / keys 欠落時に 400 エラー応答となることを検証する。"""
        handler, ctx = _make_ctx({"keys": {"p256dh": "p", "auth": "a"}}, bearer=self.bearer)
        with patch("api_push._resolve_db_path", return_value=self.db_path):
            handle_push_subscribe(ctx)
        self.assertEqual(handler.status_code, 400)

        handler2, ctx2 = _make_ctx({"endpoint": "https://push.example.com/x", "keys": {"p256dh": "p"}}, bearer=self.bearer)
        with patch("api_push._resolve_db_path", return_value=self.db_path):
            handle_push_subscribe(ctx2)
        self.assertEqual(handler2.status_code, 400)

    def test_subscribe_oversized_input_rejected(self) -> None:
        """過大入力（endpoint > 2048 / 鍵 > 512）を 422 で拒否することを検証する。"""
        handler, ctx = _make_ctx(
            {"endpoint": "https://push.example.com/" + "a" * 3000, "keys": {"p256dh": "p", "auth": "a"}},
            bearer=self.bearer,
        )
        with patch("api_push._resolve_db_path", return_value=self.db_path):
            handle_push_subscribe(ctx)
        self.assertEqual(handler.status_code, 422)

        handler2, ctx2 = _make_ctx(
            {"endpoint": "https://push.example.com/sub", "keys": {"p256dh": "p" * 600, "auth": "a"}},
            bearer=self.bearer,
        )
        with patch("api_push._resolve_db_path", return_value=self.db_path):
            handle_push_subscribe(ctx2)
        self.assertEqual(handler2.status_code, 422)

    def test_subscribe_unknown_device_rejected(self) -> None:
        """未登録 Bearer（デバイス解決失敗）時に 403 応答となることを検証する。"""
        body = {"endpoint": "https://push.example.com/sub", "keys": {"p256dh": "p", "auth": "a"}}
        handler, ctx = _make_ctx(body, bearer="unknown-token")
        with patch("api_push.verify_device_token", return_value=None), \
             patch("api_push._resolve_db_path", return_value=self.db_path):
            handle_push_subscribe(ctx)
        self.assertEqual(handler.status_code, 403)

    def test_unsubscribe_success(self) -> None:
        """unsubscribe は該当 endpoint の購読を削除し {"status": "ok"} を返すことを検証する。"""
        upsert_subscription(self.token_hash, "https://push.example.com/unsub", "p", "a", db_path=self.db_path)

        handler, ctx = _make_ctx({"endpoint": "https://push.example.com/unsub"}, bearer=self.bearer)
        with patch("api_push._resolve_db_path", return_value=self.db_path):
            handle_push_unsubscribe(ctx)

        self.assertEqual(handler.status_code, 200)
        assert handler.written_json is not None
        self.assertEqual(handler.written_json["status"], "ok")
        self.assertEqual(get_all_subscriptions(db_path=self.db_path), [])

    def test_invalid_json_returns_400(self) -> None:
        """不正 JSON ボディで 400 応答となることを検証する。"""
        from api_context import ApiContext

        class BareHandler:
            """Authorization ヘッダのみを持つ最小ハンドラ。"""

            def __init__(self) -> None:
                self.headers = {"Authorization": f"Bearer {self_bearer()}"}
                self.wfile = self

            def _get_bearer_token(self) -> str:
                return "device-bearer-token-xyz"

            def send_response(self, status_code: int) -> None:
                self.status_code = status_code

            def send_header(self, name: str, value: str) -> None:
                return None

            def _set_cors_headers(self) -> None:
                return None

            def end_headers(self) -> None:
                return None

            def write(self, data: bytes) -> int:
                return len(data)

        def self_bearer() -> str:
            return "device-bearer-token-xyz"

        handler = BareHandler()
        handler.status_code = None
        ctx = ApiContext(handler, b"not-json{{", "127.0.0.1", "pytest")
        with patch("api_push._resolve_db_path", return_value=self.db_path):
            handle_push_subscribe(ctx)
        self.assertEqual(handler.status_code, 400)


class TestWiring(unittest.TestCase):
    """local_sync_server / api_agent_bridge の配線（ルート登録・push 転送）を検証する。"""

    def test_post_path_handlers_registered(self) -> None:
        """POST_PATH_HANDLERS に /api/push/subscribe, /api/push/unsubscribe が登録されていることを検証する。"""
        from local_sync_server import POST_PATH_HANDLERS

        self.assertIn("/api/push/subscribe", POST_PATH_HANDLERS)
        self.assertIn("/api/push/unsubscribe", POST_PATH_HANDLERS)
        self.assertEqual(POST_PATH_HANDLERS["/api/push/subscribe"].__module__, "api_push")
        self.assertEqual(POST_PATH_HANDLERS["/api/push/unsubscribe"].__module__, "api_push")

    def test_get_vapid_key_handler_registered_and_returns_public_key(self) -> None:
        """GET /api/push/vapid_key が配線され、公開鍵 (Base64URL) を返すことを検証する。"""
        from local_sync_server import GET_PATH_HANDLERS

        self.assertIn("/api/push/vapid_key", GET_PATH_HANDLERS)

        temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = temp_db.name
        temp_db.close()
        try:
            init_db(db_path)
            handler, ctx = _make_ctx({}, bearer="tok")
            with patch("storage.vapid_key_repo.get_or_create_vapid_keys") as mock_keys:
                # handle_get_push_vapid_key は既定 DB パスを参照するため鍵生成を実 DB へ
                # 落とさないよう、DB を一時パスで生成済みの戻り値へ差し替える
                mock_keys.side_effect = lambda **kwargs: get_or_create_vapid_keys(db_path=db_path)
                written = GET_PATH_HANDLERS["/api/push/vapid_key"](ctx)
            self.assertTrue(written)
            assert handler.written_json is not None
            self.assertEqual(handler.written_json["status"], "ok")
            public_key = handler.written_json["public_key"]
            self.assertTrue(public_key)
            # Base64URL (padding 無し) 形式であること
            self.assertNotIn("=", public_key)
            self.assertNotIn("+", public_key)
            self.assertNotIn("/", public_key)
        finally:
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                except OSError:
                    pass

    def test_agent_bridge_calls_push_sender_on_ask(self) -> None:
        """handle_agent_ask の PROMPT/STRICT 分岐で push_sender へ転送されることを検証する。"""
        import api_agent_bridge

        with patch("push_sender.send_push_to_all_devices") as mock_send:
            ctx_payload = {
                "agent_name": "Codex",
                "command": "git push origin main",
                "summary": "本番へのpush",
                "wait_decision": False,
            }
            handler, ctx = _make_ctx(ctx_payload, bearer="tok")
            with patch("local_sync_server.get_link_monitor") as mock_lm, \
                 patch("agent_adapter.get_default_adapter_registry") as mock_registry, \
                 patch("approval_policy.get_default_policy_engine") as mock_policy, \
                 patch("local_sync_server.get_bridge_hub") as mock_hub:
                # normalize 戻り値は文字列属性を持つダミー DTO (Jev 正規表現検査が
                # summary を re.search するため MagicMock のままだと TypeError になる)
                mock_registry.return_value.normalize.return_value = MagicMock(
                    agent_name="Codex",
                    command="git push origin main",
                    summary="",
                    details="",
                    timeout_sec=180,
                    agent_type="generic",
                )
                mock_policy.return_value.evaluate.return_value = MagicMock(
                    risk_level=MagicMock(value="prompt"), is_auto_allowed=False, reason="manual"
                )
                mock_lm.return_value = MagicMock()
                mock_hub.return_value.create_approval_request.return_value = MagicMock(
                    request_id="req1", created_at=0.0, wait=lambda timeout=None: "approve",
                    decision_message="ok", to_dict=lambda: {}, responder_ip="127.0.0.1"
                )
                api_agent_bridge.handle_agent_ask(ctx)

            mock_send.assert_called_once()
            kwargs = mock_send.call_args.kwargs
            self.assertEqual(kwargs["title"], "⚠️ 承認待ち")
            self.assertIn("git push origin main", kwargs["body"])
            self.assertEqual(kwargs["tag"], "approval_request")

    def test_agent_bridge_calls_push_sender_on_ask_input(self) -> None:
        """handle_agent_ask_input で push_sender へ転送されることを検証する。"""
        import api_agent_bridge

        with patch("push_sender.send_push_to_all_devices") as mock_send:
            ctx_payload = {"agent_name": "Claude", "question": "どちらにしますか？", "wait_decision": False}
            handler, ctx = _make_ctx(ctx_payload, bearer="tok")
            with patch("local_sync_server.get_link_monitor") as mock_lm, \
                 patch("local_sync_server.get_gui_instance", return_value=None), \
                 patch("local_sync_server.get_bridge_hub") as mock_hub:
                mock_lm.return_value = MagicMock()
                mock_hub.return_value.create_question_request.return_value = MagicMock(
                    request_id="req2", wait=lambda timeout=None: "approve", decision_message="ok"
                )
                api_agent_bridge.handle_agent_ask_input(ctx)

            mock_send.assert_called_once()
            kwargs = mock_send.call_args.kwargs
            self.assertEqual(kwargs["title"], "💬 質問")
            self.assertEqual(kwargs["body"], "どちらにしますか？")

    def test_agent_bridge_calls_push_sender_on_notify(self) -> None:
        """handle_agent_notify で push_sender へ転送されることを検証する。"""
        import api_agent_bridge

        with patch("push_sender.send_push_to_all_devices") as mock_send:
            ctx_payload = {"agent_name": "Jules", "title": "リファクタ完了", "message": "全テスト通過"}
            handler, ctx = _make_ctx(ctx_payload, bearer="tok")
            with patch("local_sync_server.get_link_monitor") as mock_lm, \
                 patch("local_sync_server.get_gui_instance", return_value=None), \
                 patch("local_sync_server.get_bridge_hub") as mock_hub:
                mock_lm.return_value = MagicMock()
                mock_hub.return_value.set_completed_event.return_value = None
                api_agent_bridge.handle_agent_notify(ctx)

            mock_send.assert_called_once()
            kwargs = mock_send.call_args.kwargs
            self.assertEqual(kwargs["title"], "✨ Jules 完了")
            self.assertIn("リファクタ完了", kwargs["body"])


class TestReminderPush(unittest.TestCase):
    """reminder_engine の push 転送配線を検証する。"""

    def test_check_once_sends_push(self) -> None:
        """check_once 発火時にリマインダー push が送信されることを検証する。"""
        from reminder_engine import ReminderEngine

        temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = temp_db.name
        temp_db.close()
        try:
            init_db(db_path)
            from database import create_task

            due_ms = int(time.time() * 1000) + 5 * 60_000  # 5分後
            create_task(Task(title="push対象タスク", due_date=due_ms), db_path=db_path)
            engine = ReminderEngine(db_path=db_path, lead_minutes=10)

            with patch("push_sender.send_push_to_all_devices") as mock_send:
                fired = engine.check_once()
                self.assertEqual(len(fired), 1)
                mock_send.assert_called_once()
                kwargs = mock_send.call_args.kwargs
                self.assertEqual(kwargs["title"], "⏰ リマインダー")
                self.assertIn("push対象タスク", kwargs["body"])
        finally:
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                except OSError:
                    pass


if __name__ == "__main__":
    unittest.main()
