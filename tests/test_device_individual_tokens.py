#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - 端末台帳の個別トークン化 ＆ 端末単位 un-revoke API 単体テスト
(tests/test_device_individual_tokens.py)

TDD: Red 先行テスト
1. 複数端末への個別トークン発行と独立登録（2台ペアリングで2行登録）
2. 個別失効（端末Aを失効させても端末Bは通信継続、端末Aのみ拒否）
3. 端末単位の復帰（restore_device / POST /api/devices/restore）
4. 監査ログへの who / when / which device 記録
"""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import storage
from api_context import ApiContext
from storage.connection import init_db
from storage.device_repo import (
    get_all_devices,
    get_device_by_token_hash,
    issue_device_token,
    restore_device,
    revoke_device,
    verify_device_token,
)
import api_devices


class _FakeHttpHandler:
    """ApiContext用の最小HTTPハンドラスタブ。"""

    def __init__(self) -> None:
        self.wfile = io.BytesIO()
        self.status_codes: list = []

    def send_response(self, code: int) -> None:
        self.status_codes.append(code)

    def send_header(self, name: str, value: str) -> None:
        pass

    def end_headers(self) -> None:
        pass

    def _set_cors_headers(self) -> None:
        pass


def _decode_body(handler: _FakeHttpHandler) -> dict:
    return json.loads(handler.wfile.getvalue().decode("utf-8"))


class TestDeviceIndividualTokens(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        init_db(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_issue_multiple_device_tokens_creates_distinct_rows(self):
        """2台の異なる端末でトークンを発行すると、2つの異なるトークンが返り、台帳に2行登録される。"""
        token_a = issue_device_token(
            device_name="Boss iPhone 15 Pro",
            ip_address="192.168.1.50",
            user_agent="Mozilla/5.0 (iPhone)",
            db_path=self.db_path,
        )
        token_b = issue_device_token(
            device_name="Boss Pixel 8",
            ip_address="192.168.1.60",
            user_agent="Mozilla/5.0 (Linux; Android)",
            db_path=self.db_path,
        )

        self.assertIsInstance(token_a, str)
        self.assertIsInstance(token_b, str)
        self.assertNotEqual(token_a, token_b)
        self.assertGreaterEqual(len(token_a), 32)
        self.assertGreaterEqual(len(token_b), 32)

        devices = get_all_devices(db_path=self.db_path)
        self.assertEqual(len(devices), 2)
        names = {d.device_name for d in devices}
        self.assertIn("Boss iPhone 15 Pro", names)
        self.assertIn("Boss Pixel 8", names)

    def test_revoke_device_a_does_not_affect_device_b(self):
        """端末Aを失効させても端末Bは有効なままである（個別失効）。"""
        token_a = issue_device_token(
            device_name="Device A",
            ip_address="192.168.1.10",
            db_path=self.db_path,
        )
        token_b = issue_device_token(
            device_name="Device B",
            ip_address="192.168.1.20",
            db_path=self.db_path,
        )

        dev_a = verify_device_token(token_a, db_path=self.db_path)
        dev_b = verify_device_token(token_b, db_path=self.db_path)
        self.assertIsNotNone(dev_a)
        self.assertIsNotNone(dev_b)
        self.assertEqual(dev_a.is_revoked, 0)
        self.assertEqual(dev_b.is_revoked, 0)

        # 端末Aを失効
        ok = revoke_device(dev_a.id, db_path=self.db_path)
        self.assertTrue(ok)

        # 端末Aは失効済み (is_revoked == 1)
        checked_a = verify_device_token(token_a, db_path=self.db_path)
        self.assertIsNotNone(checked_a)
        self.assertEqual(checked_a.is_revoked, 1)

        # 端末Bは影響を受けず有効 (is_revoked == 0)
        checked_b = verify_device_token(token_b, db_path=self.db_path)
        self.assertIsNotNone(checked_b)
        self.assertEqual(checked_b.is_revoked, 0)

    def test_restore_device_re_enables_access(self):
        """失効した端末を restore_device で再有効化できる。"""
        token_a = issue_device_token(
            device_name="Device To Restore",
            ip_address="192.168.1.30",
            db_path=self.db_path,
        )
        dev = verify_device_token(token_a, db_path=self.db_path)
        self.assertIsNotNone(dev)

        # 失効
        revoke_device(dev.id, db_path=self.db_path)
        self.assertEqual(verify_device_token(token_a, db_path=self.db_path).is_revoked, 1)

        # 復帰 (un-revoke)
        restored = restore_device(dev.id, db_path=self.db_path)
        self.assertTrue(restored)

        # 再び有効
        dev_after = verify_device_token(token_a, db_path=self.db_path)
        self.assertIsNotNone(dev_after)
        self.assertEqual(dev_after.is_revoked, 0)

    def test_handle_post_devices_restore_seam(self):
        """POST /api/devices/restore のハンドラが正しく 200/400/404 を返し、監査ログを記録する。"""
        handler = _FakeHttpHandler()
        ctx = ApiContext(handler, b'{"device_id": 42}', "127.0.0.1", "TestAgent")

        with mock.patch("database.restore_device", return_value=True) as mock_restore:
            with mock.patch.object(api_devices, "record_device_restore") as mock_record:
                res = api_devices.handle_post_devices_restore(ctx)
                self.assertTrue(res)
                self.assertEqual(handler.status_codes, [200])
                data = _decode_body(handler)
                self.assertEqual(data.get("status"), "ok")
                self.assertTrue(data.get("restored"))
                mock_restore.assert_called_once_with(42)
                mock_record.assert_called_once_with(42, actor="127.0.0.1", source="api")

        # 存在しないID (404)
        handler404 = _FakeHttpHandler()
        ctx404 = ApiContext(handler404, b'{"device_id": 999}', "127.0.0.1", "TestAgent")
        with mock.patch("database.restore_device", return_value=False):
            with mock.patch.object(api_devices, "record_device_restore") as mock_record:
                res = api_devices.handle_post_devices_restore(ctx404)
                self.assertTrue(res)
                self.assertEqual(handler404.status_codes, [404])
                mock_record.assert_not_called()

        # 不正JSON (400)
        handler400 = _FakeHttpHandler()
        ctx400 = ApiContext(handler400, b"bad-json", "127.0.0.1", "TestAgent")
        res = api_devices.handle_post_devices_restore(ctx400)
        self.assertTrue(res)
        self.assertEqual(handler400.status_codes, [400])

        # device_id 欠落 (400)
        handler_no_id = _FakeHttpHandler()
        ctx_no_id = ApiContext(handler_no_id, b'{"foo": "bar"}', "127.0.0.1", "TestAgent")
        res = api_devices.handle_post_devices_restore(ctx_no_id)
        self.assertTrue(res)
        self.assertEqual(handler_no_id.status_codes, [400])

    def test_server_check_auth_with_individual_and_global_tokens(self):
        """local_sync_server の _check_auth がグローバルおよび個別の両トークンを正しく識別すること。"""
        import local_sync_server
        from local_sync_server import DeskPetSyncHandler

        token_a = issue_device_token(
            device_name="Terminal A",
            ip_address="192.168.1.101",
            user_agent="TestApp/1.0",
            db_path=self.db_path,
        )
        token_b = issue_device_token(
            device_name="Terminal B",
            ip_address="192.168.1.102",
            user_agent="TestApp/1.0",
            db_path=self.db_path,
        )

        global_token = "global_master_token_64chars_long_alpha_bravo_charlie_12345678"

        class DummyHandler:
            def __init__(self, bearer_val: str, client_ip: str = "192.168.1.101"):
                self.headers = {"Authorization": f"Bearer {bearer_val}", "User-Agent": "TestApp/1.0"}
                self.command = "POST"
                self.path = "/api/action"
                self.client_address = (client_ip, 54321)
                self.status_codes = []
                self.wfile = io.BytesIO()

            def _get_bearer_token(self):
                auth = self.headers.get("Authorization", "")
                return auth.split(" ")[1] if " " in auth else ""

            def _is_loopback(self, ip):
                return ip in ("127.0.0.1", "::1", "localhost")

            def _is_private_ip(self, ip):
                return True

            def _infer_device_name(self, ua):
                return "DummyDevice"

            def send_response(self, code):
                self.status_codes.append(code)

            def send_header(self, k, v):
                pass

            def end_headers(self):
                pass

            def _set_cors_headers(self):
                pass

        with mock.patch("storage.device_repo.get_db_connection", side_effect=lambda *args, **kwargs: storage.connection.get_db_connection(self.db_path)):
            with mock.patch("database.verify_device_token", side_effect=lambda b: verify_device_token(b, db_path=self.db_path)):
                with mock.patch("database.touch_device_last_seen", side_effect=lambda h, **kw: storage.device_repo.touch_device_last_seen(h, db_path=self.db_path, **kw)) as mock_touch:
                    with mock.patch.object(local_sync_server.get_sync_token_manager(), "verify", side_effect=lambda t: t == global_token):
                        # 1. グローバルトークンは通る
                        h_global = DummyHandler(global_token)
                        self.assertTrue(DeskPetSyncHandler._check_auth(h_global))

                        # 2. 端末Aの個別トークンは通る
                        h_a = DummyHandler(token_a)
                        self.assertTrue(DeskPetSyncHandler._check_auth(h_a))
                        self.assertTrue(mock_touch.called, "個別端末アクセス時に touch_device_last_seen が呼ばれること")
                        mock_touch.reset_mock()

                        # 3. 端末Bの個別トークンも通る
                        h_b = DummyHandler(token_b)
                        self.assertTrue(DeskPetSyncHandler._check_auth(h_b))
                        self.assertTrue(mock_touch.called, "端末Bアクセス時も touch_device_last_seen が呼ばれること")

                        # 4. 端末Aを失効させる
                        dev_a = verify_device_token(token_a, db_path=self.db_path)
                        revoke_device(dev_a.id, db_path=self.db_path)

                        # 5. 端末Aは 403 で拒絶される
                        h_a_revoked = DummyHandler(token_a)
                        self.assertFalse(DeskPetSyncHandler._check_auth(h_a_revoked))
                        self.assertEqual(h_a_revoked.status_codes, [403])

                        # 6. 端末Bは影響を受けずに通る（個別失効）
                        h_b_ok = DummyHandler(token_b)
                        self.assertTrue(DeskPetSyncHandler._check_auth(h_b_ok))

                        # 7. 未登録の不正トークンは 401
                        h_unknown = DummyHandler("completely_unknown_token")
                        self.assertFalse(DeskPetSyncHandler._check_auth(h_unknown))
                        self.assertEqual(h_unknown.status_codes, [401])


if __name__ == "__main__":
    unittest.main()

