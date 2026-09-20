#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - 未承認端末接続時の Human-in-the-Loop 承認単体テスト
(tests/test_device_connection_approval.py)

TDD: Red 先行テスト
1. 未承認外部端末接続時、承認ハンドラが呼ばれ、許可された場合はトークンが発行される (200 OK)
2. 承認ハンドラで拒絶された場合、403 Forbidden で拒絶される
3. タイムアウト時、Fail-Closed として 403 Forbidden で遮断される
4. ループバック（PC自身）は承認待ちを行わず即時発行される
"""

import io
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import storage
from storage.connection import init_db
from storage.device_repo import get_all_devices, issue_device_token
import local_sync_server
from local_sync_server import get_sync_token_manager, DeskPetSyncHandler


class _FakeHttpHandler:
    """ApiContext用の最小HTTPハンドラスタブ。"""

    def __init__(self) -> None:
        self.wfile = io.BytesIO()
        self.status_codes: list = []
        self.headers = {}
        self.path = ""

    def send_response(self, code: int) -> None:
        self.status_codes.append(code)

    def send_header(self, name: str, value: str) -> None:
        pass

    def end_headers(self) -> None:
        pass

    def _set_cors_headers(self) -> None:
        pass


def _decode_body(handler: _FakeHttpHandler) -> dict:
    handler.wfile.seek(0)
    raw = handler.wfile.read()
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


class TestDeviceConnectionApproval(unittest.TestCase):
    """端末接続時の Human-in-the-Loop 承認テストケース。"""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_approval.db")
        init_db(self.db_path)
        self.tm = get_sync_token_manager()
        self.tm.unlock_pairing(duration_sec=60)

    def tearDown(self) -> None:
        self.tm.close_pairing()
        self.tm.set_device_approval_callback(None)
        self.temp_dir.cleanup()

    def test_approval_granted_issues_token(self):
        """PC側で承認された場合、200 OK で個別トークンが返却される。"""
        # 承認コールバック: 常に True (承認) を返す
        approval_called = []

        def mock_callback(device_name: str, client_ip: str) -> bool:
            approval_called.append((device_name, client_ip))
            return True

        self.tm.set_device_approval_callback(mock_callback)

        handler = _FakeHttpHandler()
        handler.path = "/api/auth/token"
        handler.headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)"}

        with mock.patch("storage.device_repo.get_db_connection", side_effect=lambda *a, **k: storage.connection.get_db_connection(self.db_path)):
            with mock.patch("database.issue_device_token", side_effect=lambda *a, **kw: issue_device_token(*a, db_path=self.db_path, **kw)):
                DeskPetSyncHandler._handle_auth_token(handler, "192.168.1.50", handler.headers["User-Agent"])
                self.assertEqual(handler.status_codes, [200])
                data = _decode_body(handler)
                self.assertEqual(data.get("status"), "ok")
                self.assertIn("token", data)
                self.assertEqual(len(approval_called), 1)
                self.assertEqual(approval_called[0][1], "192.168.1.50")

    def test_approval_denied_returns_403(self):
        """PC側で拒絶された場合、403 Forbidden が返却されトークンは発行されない。"""
        # 承認コールバック: False (拒絶) を返す
        def mock_callback(device_name: str, client_ip: str) -> bool:
            return False

        self.tm.set_device_approval_callback(mock_callback)

        handler = _FakeHttpHandler()
        handler.path = "/api/auth/token"
        handler.headers = {"User-Agent": "Mozilla/5.0 (Android; Mobile)"}

        DeskPetSyncHandler._handle_auth_token(handler, "192.168.1.80", handler.headers["User-Agent"])
        self.assertEqual(handler.status_codes, [403])
        data = _decode_body(handler)
        self.assertEqual(data.get("status"), "forbidden")
        self.assertNotIn("token", data)
        self.assertIn("拒否", data.get("message", ""))

    def test_loopback_skips_approval(self):
        """ループバック（PC自身）は承認コールバックを呼ばずに即座にマスタトークンを返す。"""
        mock_callback = mock.MagicMock(return_value=False)
        self.tm.set_device_approval_callback(mock_callback)

        handler = _FakeHttpHandler()
        handler.path = "/api/auth/token"
        handler.headers = {"User-Agent": "LocalClient"}

        DeskPetSyncHandler._handle_auth_token(handler, "127.0.0.1", handler.headers["User-Agent"])
        self.assertEqual(handler.status_codes, [200])
        mock_callback.assert_not_called()

    def test_set_gui_instance_registers_callback(self):
        """set_gui_instance(gui) を呼ぶと SyncTokenManager に承認コールバックが自動登録される。"""
        fake_gui = mock.MagicMock()
        local_sync_server.set_gui_instance(fake_gui)
        self.assertIsNotNone(self.tm.device_approval_callback)

    def test_callback_exception_fails_closed_403(self):
        """承認コールバック内で例外が発生した場合、Fail-Closed として 403 で遮断される。"""
        def crashing_callback(dev_name, client_ip):
            raise RuntimeError("Unexpected GUI crash or deadlock")

        self.tm.set_device_approval_callback(crashing_callback)

        handler = _FakeHttpHandler()
        handler.path = "/api/auth/token"
        handler.headers = {"User-Agent": "CrashPhone"}

        DeskPetSyncHandler._handle_auth_token(handler, "192.168.1.99", "CrashPhone")
        self.assertEqual(handler.status_codes, [403])
        data = _decode_body(handler)
        self.assertEqual(data.get("status"), "forbidden")
        self.assertNotIn("token", data)

    def test_ask_device_approval_gui_none_root_fails_closed(self):
        """GUIが存在しない (root=None) 環境では自動的に False (Fail-Closed) を返す。"""
        from ui.device_approval_dialog import ask_device_approval_gui
        result = ask_device_approval_gui(None, "TestDevice", "192.168.1.10")
        self.assertFalse(result)

    def test_ask_device_approval_gui_thread_sync(self):
        """ask_device_approval_gui がGUIスレッドへ after でディスパッチし結果を同期返却する。"""
        from ui.device_approval_dialog import ask_device_approval_gui

        fake_root = mock.MagicMock()
        fake_root.winfo_exists.return_value = True

        # root.after(0, func) を即座に実行するモック
        def fake_after(delay, func):
            # モックダイアログの挙動をシミュレート
            with mock.patch("ui.device_approval_dialog.DeviceApprovalDialog") as MockDialog:
                instance = MockDialog.return_value
                instance.result = True
                instance.wait_window.return_value = None
                func()

        fake_root.after.side_effect = fake_after

        result = ask_device_approval_gui(fake_root, "TestiPhone", "192.168.1.50", timeout_sec=2)
        self.assertTrue(result)

    def test_cb_none_fails_closed_403(self):
        """承認コールバックが未登録 (None) の場合、外部端末は Fail-Closed (403) で自動拒絶される。"""
        self.tm.set_device_approval_callback(None)

        handler = _FakeHttpHandler()
        handler.path = "/api/auth/token"
        handler.headers = {"User-Agent": "ExternalDevice"}

        DeskPetSyncHandler._handle_auth_token(handler, "192.168.1.77", "ExternalDevice")
        self.assertEqual(handler.status_codes, [403])
        data = _decode_body(handler)
        self.assertEqual(data.get("status"), "forbidden")
        self.assertNotIn("token", data)

    def test_unpaired_request_rejected_403(self):
        """ペアリング期間外 (pairing_open == False) の場合、外部端末は 403 で即座に拒絶される。"""
        self.tm.close_pairing()

        handler = _FakeHttpHandler()
        handler.path = "/api/auth/token"
        handler.headers = {"User-Agent": "ExternalDevice"}

        DeskPetSyncHandler._handle_auth_token(handler, "192.168.1.88", "ExternalDevice")
        self.assertEqual(handler.status_codes, [403])
        data = _decode_body(handler)
        self.assertEqual(data.get("status"), "forbidden")
        self.assertNotIn("token", data)

    def test_slowloris_socket_timeout_p0_3(self):
        """Slowloris対策としてソケットタイムアウトが 10.0秒 に設定されていることを担保する。"""
        self.assertEqual(DeskPetSyncHandler.timeout, 10.0)

    def test_dialog_stacking_mutex_guard(self):
        """承認ダイアログが既にアクティブな場合、二重呼び出しは排他制御で即座に False を返す。"""
        import ui.device_approval_dialog as dad

        fake_root = mock.MagicMock()
        fake_root.winfo_exists.return_value = True

        with dad._dialog_lock:
            dad._is_dialog_active = True

        try:
            res = dad.ask_device_approval_gui(fake_root, "SecondDevice", "192.168.1.99")
            self.assertFalse(res)
        finally:
            with dad._dialog_lock:
                dad._is_dialog_active = False


if __name__ == "__main__":
    unittest.main()

