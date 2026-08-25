"""
統合手帳（CalendarWindow）予定描画エンジンのスモークテスト (tests/test_calendar_ui_smoke.py)

月間グリッド / 週間タイムテーブル / 日間タイムテーブルの3モード描画と、
期間移動・今日ジャンプが例外なく動作することを検証する。
実行: venv\\Scripts\\python.exe -m pytest tests/test_calendar_ui_smoke.py -v
"""

import datetime
import unittest
import tkinter as tk

import database
from ui.calendar_window import CalendarWindow


class _FakeParentGui:
    """CalendarWindow が要求する最小限の親GUIインターフェース"""

    def __init__(self, root: tk.Tk):
        self.root = root


class TestCalendarWindowRendering(unittest.TestCase):
    """3表示モードの描画とナビゲーションを検証する"""

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        # 新しいテーブル（calendar_sources）を含むDBスキーマを初期化
        database.init_db()
        self.win = CalendarWindow(_FakeParentGui(self.root))
        self.win.update()

    def tearDown(self):
        self.win.destroy()
        self.root.destroy()

    def test_month_view_renders(self):
        """月間グリッドが描画される"""
        self.win._on_event_view_change("月間")
        self.win.update()
        self.assertEqual(self.win.view_mode, "month")
        self.assertGreater(len(self.win.events_canvas.find_all()), 0)

    def test_week_view_renders(self):
        """週間タイムテーブルが描画される"""
        self.win._on_event_view_change("週間")
        self.win.update()
        self.assertEqual(self.win.view_mode, "week")
        self.assertGreater(len(self.win.events_canvas.find_all()), 0)

    def test_day_view_renders(self):
        """日間タイムテーブルが描画される"""
        self.win._on_event_view_change("日間")
        self.win.update()
        self.assertEqual(self.win.view_mode, "day")
        self.assertGreater(len(self.win.events_canvas.find_all()), 0)

    def test_period_navigation(self):
        """月/週/日の前後移動と今日ジャンプが例外なく動く"""
        for seg in ("月間", "週間", "日間"):
            self.win._on_event_view_change(seg)
            self.win._on_prev_period()
            self.win._on_next_period()
            self.win._on_jump_today()
        self.assertEqual(self.win.current_date, datetime.date.today())

    def test_load_events_uses_db_range(self):
        """DBから取得した過去含みの予定がキャッシュに載る（iCal同期データの可視化）"""
        now = datetime.datetime.now()
        events = database.get_events_between(
            int((now - datetime.timedelta(days=120)).timestamp() * 1000),
            int((now + datetime.timedelta(days=200)).timestamp() * 1000),
        )
        self.win.load_events(events)
        self.assertEqual(len(self.win.all_cached_events), len(events))


if __name__ == "__main__":
    unittest.main(verbosity=2)
