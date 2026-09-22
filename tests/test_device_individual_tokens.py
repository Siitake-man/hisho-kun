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
    register_device_from_bearer,
    restore_device,
    revoke_all_devices,
    revoke_device,
    verify_device_token,
    cleanup_loopback_devices,
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

    @staticmethod
    def _is_loopback(client_ip: str) -> bool:
        return client_ip in ("127.0.0.1", "::1", "localhost")

    @staticmethod
    def _infer_device_name(user_agent: str) -> str:
        from local_sync_server import DeskPetSyncHandler
        return DeskPetSyncHandler._infer_device_name(user_agent)


def _decode_body(handler: _FakeHttpHandler) -> dict:
    return json.loads(handler.wfile.getvalue().decode("utf-8"))


class TestDeviceIndividualTokens(unittest.TestCase):
    """端末個別トークンの発行・個別失効・復帰・監査ログの契約を検証する。

    1台を失効・削除しても他端末の通信が継続し、グローバルトークンが
    個別トークン経路から漏洩しないこと（fail-closed）を守る。
    """

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        init_db(self.db_path)

        # 🛡️ 実環境の .sync_token を保護するためテンポラリファイルへパッチ
        import local_sync_server
        self.temp_token_file = Path(tempfile.NamedTemporaryFile(suffix=".sync_token", delete=False).name)
        self.token_file_patcher = mock.patch.object(local_sync_server, "TOKEN_FILE", self.temp_token_file)
        self.token_file_patcher.start()

        # シングルトンの状態退避
        tm = local_sync_server.get_sync_token_manager()
        self._orig_tm_token = tm._token
        self._orig_tm_pairing = tm._pairing_unlocked_until

    def tearDown(self):
        # シングルトンの状態復元
        import local_sync_server
        tm = local_sync_server.get_sync_token_manager()
        tm._token = self._orig_tm_token
        tm._pairing_unlocked_until = self._orig_tm_pairing

        self.token_file_patcher.stop()
        if self.temp_token_file.exists():
            try:
                self.temp_token_file.unlink()
            except OSError:
                pass

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
                        # 1. 🛡️ P0-1 (A案): 台帳未登録のマスタートークンは非ループバックから拒否 (401)
                        h_global = DummyHandler(global_token)
                        self.assertFalse(DeskPetSyncHandler._check_auth(h_global))
                        self.assertEqual(h_global.status_codes, [401])

                        # 1b. 台帳に登録済みのマスタートークン (レガシー登録) は通る
                        register_device_from_bearer(
                            "Legacy Bridge", global_token,
                            ip_address="192.168.1.101", user_agent="TestApp/1.0",
                            db_path=self.db_path,
                        )
                        h_global_registered = DummyHandler(global_token)
                        self.assertTrue(DeskPetSyncHandler._check_auth(h_global_registered))

                        # 1c. 登録済みでも失効させれば 403 (失効は資格情報の種別に依存しない)
                        legacy_dev = verify_device_token(global_token, db_path=self.db_path)
                        revoke_device(legacy_dev.id, db_path=self.db_path)
                        h_global_revoked = DummyHandler(global_token)
                        self.assertFalse(DeskPetSyncHandler._check_auth(h_global_revoked))
                        self.assertEqual(h_global_revoked.status_codes, [403])

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

    def test_revoke_all_devices_invalidates_all_individual_tokens(self):
        """revoke_all_devices() を呼ぶと台帳内の全端末が一括で失効（is_revoked = 1）になる。"""
        token_a = issue_device_token("Phone A", db_path=self.db_path)
        token_b = issue_device_token("Phone B", db_path=self.db_path)

        dev_a = verify_device_token(token_a, db_path=self.db_path)
        dev_b = verify_device_token(token_b, db_path=self.db_path)
        self.assertEqual(dev_a.is_revoked, 0)
        self.assertEqual(dev_b.is_revoked, 0)

        count = revoke_all_devices(db_path=self.db_path)
        self.assertEqual(count, 2)

        dev_a_after = verify_device_token(token_a, db_path=self.db_path)
        dev_b_after = verify_device_token(token_b, db_path=self.db_path)
        self.assertEqual(dev_a_after.is_revoked, 1)
        self.assertEqual(dev_b_after.is_revoked, 1)

    def test_regenerate_token_revokes_all_devices(self):
        """SyncTokenManager.regenerate() を呼ぶとグローバルトークンだけでなく全個別端末も失効する (P0-1)。"""
        import local_sync_server
        from local_sync_server import get_sync_token_manager

        token_a = issue_device_token("Phone A", db_path=self.db_path)
        tm = get_sync_token_manager()

        with mock.patch("storage.device_repo.get_db_connection", side_effect=lambda *args, **kwargs: storage.connection.get_db_connection(self.db_path)):
            with mock.patch("database.revoke_all_devices", side_effect=lambda **kw: revoke_all_devices(db_path=self.db_path)):
                tm.regenerate()

                dev_a = verify_device_token(token_a, db_path=self.db_path)
                self.assertEqual(dev_a.is_revoked, 1, "全解除実行後に個別端末が失効していること")

    def test_pairing_token_issue_is_one_time_and_fails_closed(self):
        """QRペアリング開放時、1回発行するとペアリング待機が自動終了し、2回目は拒絶される (P0-2)。"""
        import local_sync_server
        from local_sync_server import get_sync_token_manager, DeskPetSyncHandler

        tm = get_sync_token_manager()
        tm.unlock_pairing(duration_sec=600)
        tm.set_device_approval_callback(lambda dev_name, client_ip: True)
        self.assertTrue(tm.pairing_open)

        # 1回目の発行シミュレーション
        handler1 = _FakeHttpHandler()
        handler1.path = "/api/auth/token"
        handler1.headers = {"User-Agent": "TestPhone"}

        with mock.patch("storage.device_repo.get_db_connection", side_effect=lambda *args, **kwargs: storage.connection.get_db_connection(self.db_path)):
            with mock.patch("database.issue_device_token", side_effect=lambda *a, **kw: issue_device_token(*a, db_path=self.db_path, **kw)):
                DeskPetSyncHandler._handle_auth_token(handler1, "192.168.1.100", "TestPhone")
                self.assertEqual(handler1.status_codes, [200])
                data1 = _decode_body(handler1)
                self.assertEqual(data1.get("status"), "ok")
                self.assertIn("token", data1)

                # 🔐 ダイアログクローズ時（または明示的close時）にペアリングモードが閉じること
                tm.close_pairing()
                self.assertFalse(tm.pairing_open, "ペアリングクローズ後はFalseになること")

                # クローズ後の2回目の呼び出しは 403 で拒絶される
                handler2 = _FakeHttpHandler()
                handler2.path = "/api/auth/token"
                handler2.headers = {"User-Agent": "TestPhone2"}
                DeskPetSyncHandler._handle_auth_token(handler2, "192.168.1.101", "TestPhone2")
                self.assertEqual(handler2.status_codes, [403])
                data2 = _decode_body(handler2)
                self.assertEqual(data2.get("status"), "forbidden")

    def test_cleanup_loopback_devices(self):
        """ループバック端末 (127.0.0.1) のみが台帳から削除され、実スマホは残る。"""
        issue_device_token("Local Test 1", ip_address="127.0.0.1", db_path=self.db_path)
        issue_device_token("Local Test 2", ip_address="::1", db_path=self.db_path)
        issue_device_token("Boss Real iPhone", ip_address="192.168.1.50", db_path=self.db_path)

        count = cleanup_loopback_devices(db_path=self.db_path)
        self.assertEqual(count, 2, "127.0.0.1 と ::1 の2件が削除されること")

        remaining = get_all_devices(db_path=self.db_path)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].device_name, "Boss Real iPhone")

    def test_pairing_error_fails_closed_without_leaking_global_token(self):
        """個別トークン発行でDBエラー等の例外が起きた際、グローバルトークンを返さず500を返す (P1-2)。"""
        from local_sync_server import get_sync_token_manager, DeskPetSyncHandler

        tm = get_sync_token_manager()
        tm.unlock_pairing(duration_sec=600)
        tm.set_device_approval_callback(lambda dev_name, client_ip: True)

        handler = _FakeHttpHandler()
        handler.path = "/api/auth/token"
        handler.headers = {"User-Agent": "ErrorPhone"}

        with mock.patch("database.issue_device_token", side_effect=RuntimeError("DB is locked")):
            DeskPetSyncHandler._handle_auth_token(handler, "192.168.1.100", "ErrorPhone")
            self.assertEqual(handler.status_codes, [500])
            data = _decode_body(handler)
            self.assertEqual(data.get("status"), "error")
            self.assertNotIn("token", data)
            # グローバルトークンが漏洩していないこと
            self.assertNotEqual(data.get("token"), tm.token)

    def test_get_devices_restricted_to_loopback(self):
        """GET /api/devices はループバック（同一PC内）以外からのアクセスを 403 で拒絶する (P1-3)。"""
        from local_sync_server import DeskPetSyncHandler

        # 非ループバックIP (同一LAN) からのリクエスト
        handler_lan = _FakeHttpHandler()
        handler_lan.path = "/api/devices"
        handler_lan.headers = {"Authorization": "Bearer some_valid_token"}

        # ループバック判定モック
        with mock.patch.object(DeskPetSyncHandler, "_check_auth", return_value=True):
            DeskPetSyncHandler._dispatch_get_devices(handler_lan, "192.168.1.50")
            self.assertEqual(handler_lan.status_codes, [403])
            data = _decode_body(handler_lan)
            self.assertEqual(data.get("status"), "forbidden")


if __name__ == "__main__":
    unittest.main()

