"""
ネオ秘書くん - 手帳カレンダー リアルタイム反映 の単体テスト (tests/test_ui_notify.py)

ui_notify.notify_calendar_changed() の通知ディスパッチと、
CalendarWindow に軽量リフレッシュ経路 (refresh_events_only) が実装されていることを検証する。
"""

import sys
import types
import unittest
from typing import Any, Dict, List, Optional, Tuple


class _FakeGui:
    """post_action / refresh_calendar_if_open を記録するテスト用GUIスタブ。"""

    def __init__(self) -> None:
        self.posted: List[Tuple[Any, tuple, dict]] = []

    def post_action(self, func: Any, *args: Any, **kwargs: Any) -> None:
        self.posted.append((func, args, kwargs))

    def refresh_calendar_if_open(self) -> None:
        return None


class NotifyCalendarChangedTest(unittest.TestCase):
    """ui_notify.notify_calendar_changed の振る舞いテスト。"""

    def setUp(self) -> None:
        """local_sync_server をスタブへ差し替え、GUI状態を制御できるようにする。"""
        self._original_module = sys.modules.get("local_sync_server")
        self._holder: Dict[str, Optional[_FakeGui]] = {"gui": None}

        fake_module = types.ModuleType("local_sync_server")

        def get_gui_instance() -> Optional[_FakeGui]:
            return self._holder["gui"]

        fake_module.get_gui_instance = get_gui_instance  # type: ignore[attr-defined]
        sys.modules["local_sync_server"] = fake_module

    def tearDown(self) -> None:
        """スタブを元に戻す。"""
        if self._original_module is not None:
            sys.modules["local_sync_server"] = self._original_module
        else:
            sys.modules.pop("local_sync_server", None)

    def test_gui_none_is_silent_noop(self) -> None:
        """GUI未起動(None)でも例外を出さず静かに終わること。"""
        import ui_notify

        self._holder["gui"] = None
        self.assertIsNone(ui_notify.notify_calendar_changed())

    def test_gui_receives_refresh_dispatch(self) -> None:
        """GUIが稼働中なら post_action(refresh_calendar_if_open) が1回ディスパッチされること。"""
        import ui_notify

        gui = _FakeGui()
        self._holder["gui"] = gui
        ui_notify.notify_calendar_changed()
        self.assertEqual(len(gui.posted), 1)
        func, args, kwargs = gui.posted[0]
        self.assertEqual(func.__name__, "refresh_calendar_if_open")
        self.assertEqual(args, ())
        self.assertEqual(kwargs, {})

    def test_gui_without_interface_is_skipped(self) -> None:
        """通知インターフェースを持たないGUIオブジェクトでも例外が出ずスキップされること。"""
        import ui_notify

        class _BareGui:
            pass

        self._holder["gui"] = _BareGui()  # type: ignore[assignment]
        self.assertIsNone(ui_notify.notify_calendar_changed())

    def test_local_sync_server_import_failure_is_swallowed(self) -> None:
        """local_sync_server が get_gui_instance を提供しない環境でも例外が漏れないこと。"""
        import ui_notify

        # get_gui_instance 属性を持たないモジュールスタブ → from import が ImportError になる
        sys.modules["local_sync_server"] = types.ModuleType("local_sync_server")
        self.assertIsNone(ui_notify.notify_calendar_changed())


class CalendarWindowRefreshApiTest(unittest.TestCase):
    """CalendarWindow の軽量リフレッシュAPI存在検証（インスタンス化なしの静的検証）。"""

    def test_refresh_events_only_is_defined(self) -> None:
        """refresh_events_only が CalendarWindow の公開メソッドとして定義されていること。"""
        from ui.calendar_window import CalendarWindow

        self.assertTrue(callable(getattr(CalendarWindow, "refresh_events_only", None)))

    def test_auto_refresh_interval_constant(self) -> None:
        """自動リフレッシュ周期が60秒に設定されていること。"""
        from ui import calendar_window

        self.assertEqual(calendar_window.EVENT_AUTO_REFRESH_INTERVAL_MS, 60_000)

    def test_refresh_all_data_delegates_to_light_path(self) -> None:
        """refresh_all_data の実体が refresh_events_only へ委譲していること（DRY確認）。"""
        import inspect
        from ui.calendar_window import CalendarWindow

        source = inspect.getsource(CalendarWindow.refresh_all_data)
        self.assertIn("self.refresh_events_only()", source)


if __name__ == "__main__":
    unittest.main()
