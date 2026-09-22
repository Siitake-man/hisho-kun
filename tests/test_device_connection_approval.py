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
        import ui.device_approval_dialog as dad
        with dad._dialog_lock:
            dad._is_dialog_active = False

    def tearDown(self) -> None:
        self.tm.close_pairing()
        self.tm.set_device_approval_callback(None)
        local_sync_server.set_gui_instance(None)
        import ui.device_approval_dialog as dad
        with dad._dialog_lock:
            dad._is_dialog_active = False
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
                # 🛡️ P0-3 N4: 個別トークン発行でペアリング待機が即座に閉じること (Single-Use)
                self.assertFalse(self.tm.pairing_open, "発行後はペアリング待機が自動クローズされること")

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
        """信頼できる loopback（TCPピア + Host が loopback 名）は承認コールバックを呼ばず、loopback 専用トークンを返す (P0-3)。"""
        mock_callback = mock.MagicMock(return_value=False)
        self.tm.set_device_approval_callback(mock_callback)

        handler = _FakeHttpHandler()
        handler.path = "/api/auth/token"
        handler.headers = {"User-Agent": "LocalClient", "Host": "127.0.0.1:8765"}

        DeskPetSyncHandler._handle_auth_token(handler, "127.0.0.1", handler.headers["User-Agent"])
        self.assertEqual(handler.status_codes, [200])
        mock_callback.assert_not_called()
        data = _decode_body(handler)
        self.assertEqual(
            data.get("token"), self.tm.loopback_token,
            "🛡️ P0-3: マスター鍵ではなく loopback 専用トークンを返すこと",
        )
        self.assertNotEqual(data.get("token"), self.tm.token, "🛡️ マスター鍵は HTTP で配布しない")

    def test_loopback_ip_with_foreign_host_is_not_trusted(self):
        """TCPピアが loopback でも Host が loopback 名でなければ外部端末扱い（403）となること (P0-3)。

        Tailscale Serve（Host = *.ts.net）や DNS Rebinding（Host = 攻撃者ドメイン）は
        TCPピアが 127.0.0.1 になるため、Host 条件が唯一の構造的な識別子となる。
        """
        mock_callback = mock.MagicMock(return_value=True)
        self.tm.set_device_approval_callback(mock_callback)
        self.tm.close_pairing()

        handler = _FakeHttpHandler()
        handler.path = "/api/auth/token"
        handler.headers = {"User-Agent": "ServeClient", "Host": "neo-pc.tailnet-xxxx.ts.net"}

        DeskPetSyncHandler._handle_auth_token(handler, "127.0.0.1", handler.headers["User-Agent"])
        self.assertEqual(handler.status_codes, [403], "🛡️ Serve 経由は loopback 扱いしない")
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

    @mock.patch("ui.device_approval_dialog.DeviceApprovalDialog")
    def test_ask_device_approval_gui_thread_sync(self, MockDialog):
        """ask_device_approval_gui がGUIスレッドへ after でディスパッチし結果を同期返却する。"""
        from ui.device_approval_dialog import ask_device_approval_gui

        def _init_mock(*args, **kwargs):
            cb = kwargs.get("on_decision")
            if cb:
                cb(True)
            return mock.MagicMock()
        MockDialog.side_effect = _init_mock

        fake_root = mock.MagicMock()
        fake_root.winfo_exists.return_value = True

        # root.after(0, func) を即座に実行するモック
        fake_root.after.side_effect = lambda delay, func: func()

        result = ask_device_approval_gui(fake_root, "TestiPhone", "192.168.1.50", timeout_sec=2)
        self.assertTrue(result)

    @mock.patch("ui.device_approval_dialog.DeviceApprovalDialog")
    def test_ask_device_approval_gui_with_gui_instance_extracts_root(self, MockDialog):
        """NeoSecretaryGUI インスタンス (post_action 属性を持つオブジェクト) が渡されても post_action で動作する。"""
        from ui.device_approval_dialog import ask_device_approval_gui

        def _init_mock(*args, **kwargs):
            cb = kwargs.get("on_decision")
            if cb:
                cb(True)
            return mock.MagicMock()
        MockDialog.side_effect = _init_mock

        fake_gui = mock.MagicMock(spec=["root", "post_action"])
        fake_root = mock.MagicMock()
        fake_root.winfo_exists.return_value = True
        fake_gui.root = fake_root
        fake_gui.post_action.side_effect = lambda func, *a, **kw: func()

        result = ask_device_approval_gui(fake_gui, "AndroidDevice", "192.168.1.4", timeout_sec=2)
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

    def test_dialog_coalesce_same_device(self):
        """同一端末からの重複呼び出しの場合、ビジー拒絶せず既存ダイアログの結果に合流する。"""
        import threading
        import ui.device_approval_dialog as dad

        fake_gui = mock.MagicMock(spec=["root", "post_action"])
        fake_root = mock.MagicMock()
        fake_root.winfo_exists.return_value = True
        fake_gui.root = fake_root

        # 1回目のダイアログは非同期で300ms後に許可される想定
        def _slow_show(func):
            def _delayed():
                import time
                time.sleep(0.05)
                # active_outcome を True にして event を set
                with dad._dialog_lock:
                    if dad._active_outcome is not None:
                        dad._active_outcome[0] = True
                    if dad._active_result_event is not None:
                        dad._active_result_event.set()
            threading.Thread(target=_delayed, daemon=True).start()

        fake_gui.post_action.side_effect = _slow_show

        results = [None, None]

        def _call_1():
            results[0] = dad.ask_device_approval_gui(fake_gui, "SamePhone", "192.168.1.50", timeout_sec=2)

        def _call_2():
            import time
            time.sleep(0.01)  # 1回目がロックを取得した後に発火
            results[1] = dad.ask_device_approval_gui(fake_gui, "SamePhone", "192.168.1.50", timeout_sec=2)

        t1 = threading.Thread(target=_call_1)
        t2 = threading.Thread(target=_call_2)
        t1.start()
        t2.start()
        t1.join(timeout=3)
        t2.join(timeout=3)

        self.assertTrue(results[0])
        self.assertTrue(results[1])

    def test_dialog_recent_approval_debounce(self):
        """直近10秒以内に承認された同一端末からの再要求は、ダイアログを再表示せず即座に承認(True)を返す。"""
        import ui.device_approval_dialog as dad

        fake_gui = mock.MagicMock(spec=["root", "post_action"])
        fake_root = mock.MagicMock()
        fake_root.winfo_exists.return_value = True
        fake_gui.root = fake_root
        # post_actionで即座に承認をセット
        fake_gui.post_action.side_effect = lambda func: func()

        with mock.patch("ui.device_approval_dialog.DeviceApprovalDialog") as MockDialog:
            def _init_mock(*args, **kwargs):
                cb = kwargs.get("on_decision")
                if cb:
                    cb(True)
                return mock.MagicMock()
            MockDialog.side_effect = _init_mock

            # 1回目の承認（ダイアログが開き、承認されて閉じる）
            res1 = dad.ask_device_approval_gui(fake_gui, "DebouncePhone", "192.168.1.60", timeout_sec=2)
            self.assertTrue(res1)
            self.assertEqual(MockDialog.call_count, 1)

            # 2回目（直後に同一端末から再度呼ばれた場合）
            # ダイアログは新たにインスタンス化されず (call_count は 1 のまま)、即座に True が返る
            res2 = dad.ask_device_approval_gui(fake_gui, "DebouncePhone", "192.168.1.60", timeout_sec=2)
            self.assertTrue(res2)
            self.assertEqual(MockDialog.call_count, 1)

            # 異なる端末からの要求は別枠としてダイアログが生成される
            res3 = dad.ask_device_approval_gui(fake_gui, "OtherPhone", "192.168.1.61", timeout_sec=2)
            self.assertTrue(res3)
            self.assertEqual(MockDialog.call_count, 2)


if __name__ == "__main__":
    unittest.main()


