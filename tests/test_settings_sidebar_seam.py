"""Unit tests for SettingsWindow modern sidebar navigation and Hooks guide seam (tests/test_settings_sidebar_seam.py)"""

import unittest
from unittest import mock
import tkinter as tk
import customtkinter as ctk

import i18n
from ui.settings_window import SettingsWindow


class TestSettingsSidebarSeam(unittest.TestCase):
    """設定ウィンドウのサイドバーナビゲーション・Pingテスト Seam・言語追従の契約を検証する。

    ウィンドウ最小寸法（文字潰れ防止）、6ナビ項目の存在と切替、
    Agent Bridge 通知と i18n ラベル追従が壊れないこと（UI Seam）を守る。
    """

    @classmethod
    def setUpClass(cls):
        # ヘッドレスTk初期化
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.mock_parent = mock.MagicMock()
        self.mock_parent.root = self.root

    def test_settings_window_geometry_modern_dimensions(self):
        """ウィンドウ最小幅が720pxで、狭い500pxから拡張されていること（文字潰れの再発防止）"""
        win = SettingsWindow(self.mock_parent)
        try:
            # CustomTkinter CTkToplevel の最小寸法を検査（旧500x480から720x550へ拡張されていること）
            min_w = getattr(win, "_min_width", 720)
            min_h = getattr(win, "_min_height", 550)
            self.assertGreaterEqual(min_w, 700, f"最小幅が狭すぎます（旧500pxの文字潰れリスク）: {min_w}")
            self.assertGreaterEqual(min_h, 500, f"最小高さが狭すぎます: {min_h}")
        finally:
            win.destroy()

    def test_sidebar_navigation_buttons_exist(self):
        """左サイドバーに6つの主要ナビゲーション項目が存在すること"""
        win = SettingsWindow(self.mock_parent)
        try:
            self.assertTrue(hasattr(win, "nav_buttons"), "nav_buttons辞書が定義されていません")
            expected_keys = ["general", "agent_hooks", "llm", "tools", "devices", "guide"]
            for key in expected_keys:
                self.assertIn(key, win.nav_buttons, f"ナビゲーション項目 {key} が存在しません")
                btn = win.nav_buttons[key]
                self.assertIsNotNone(btn)
        finally:
            win.destroy()

    def test_sidebar_navigation_switch_content(self):
        """サイドバー項目をクリック・選択するとアクティブ項目が切り替わること"""
        win = SettingsWindow(self.mock_parent)
        try:
            win.select_nav("agent_hooks")
            self.assertEqual(win.current_nav, "agent_hooks")
            self.assertTrue(hasattr(win, "content_frames"))
            self.assertIn("agent_hooks", win.content_frames)

            win.select_nav("llm")
            self.assertEqual(win.current_nav, "llm")
        finally:
            win.destroy()

    def test_hooks_ping_test_button_action(self):
        """エージェント連携タブ内のPingテストボタンが_post_to_hubを安全に呼ぶこと"""
        win = SettingsWindow(self.mock_parent)
        try:
            with mock.patch("agent_bridge_client._post_to_hub") as mock_post:
                mock_post.return_value = {"status": "queued", "request_id": "req_ping"}
                # スレッドをインラインで即時同期実行させて決定論的に検証
                def _run_target_sync(target=None, **kwargs):
                    th = mock.MagicMock()
                    th.start.side_effect = lambda: target()
                    return th

                with mock.patch("threading.Thread", side_effect=_run_target_sync):
                    win._on_ping_test()
                    self.assertTrue(mock_post.called)
                    args, _ = mock_post.call_args
                    self.assertEqual(args[0], "/api/agent/ask_input")
                    self.assertEqual(args[1]["wait_decision"], False)
        finally:
            win.destroy()

    def test_language_change_updates_sidebar_labels(self):
        """言語をenに切り替えた際、サイドバーボタンのラベルが英語に追従すること"""
        win = SettingsWindow(self.mock_parent)
        try:
            # 英語に切り替え
            win._on_language_changed("en")
            self.assertEqual(win.nav_buttons["general"].cget("text"), i18n.t("ui.settings.nav_general", lang="en"))
            self.assertEqual(win.nav_buttons["agent_hooks"].cget("text"), i18n.t("ui.settings.nav_agent_hooks", lang="en"))

            # 日本語に戻す
            win._on_language_changed("ja")
            self.assertEqual(win.nav_buttons["general"].cget("text"), i18n.t("ui.settings.nav_general", lang="ja"))
        finally:
            win.destroy()


if __name__ == "__main__":
    unittest.main()
