"""
カレンダー購読ソース（複数アカウント）のCRUD運用テスト (tests/test_calendar_sources.py)

実行: venv\\Scripts\\python.exe -m unittest tests/test_calendar_sources.py -v
"""

import logging
import unittest
import database

logging.disable(logging.CRITICAL)


class TestCalendarSources(unittest.TestCase):
    """カレンダー購読ソースのCRUDと連携動作を検証する"""

    def setUp(self):
        database.init_db()
        # テスト用のソースを作成
        self.src1 = database.create_calendar_source(database.CalendarSource(
            name="仕事用", color="#1565C0", url="https://calendar.google.com/calendar/ical/work/basic.ics", enabled=True
        ))
        self.src2 = database.create_calendar_source(database.CalendarSource(
            name="プライベート", color="#2E7D32", url="https://calendar.google.com/calendar/ical/private/basic.ics", enabled=True
        ))

    def tearDown(self):
        # テスト用ソースとその予定をクリーンアップ
        with database.get_db_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM events WHERE source_id IN (?, ?)", (self.src1, self.src2))
            c.execute("DELETE FROM calendar_sources WHERE id IN (?, ?)", (self.src1, self.src2))

    def test_create_and_list(self):
        """ソースを作成し一覧取得できる"""
        sources = database.get_all_calendar_sources()
        self.assertGreaterEqual(len(sources), 2)
        names = [s.name for s in sources]
        self.assertIn("仕事用", names)
        self.assertIn("プライベート", names)

    def test_get_by_id(self):
        """ID指定でソースを取得できる"""
        s = database.get_calendar_source(self.src1)
        self.assertIsNotNone(s)
        self.assertEqual(s.name, "仕事用")
        self.assertEqual(s.color, "#1565C0")

    def test_update(self):
        """ソースの内容を更新できる"""
        s = database.get_calendar_source(self.src1)
        s.name = "ビジネス"
        s.color = "#C62828"
        s.enabled = False
        database.update_calendar_source(s)
        updated = database.get_calendar_source(self.src1)
        self.assertEqual(updated.name, "ビジネス")
        self.assertEqual(updated.color, "#C62828")
        self.assertFalse(updated.enabled)

    def test_toggle_enabled(self):
        """有効/無効を切り替えられる"""
        database.set_calendar_source_enabled(self.src1, False)
        s = database.get_calendar_source(self.src1)
        self.assertFalse(s.enabled)
        database.set_calendar_source_enabled(self.src1, True)
        s = database.get_calendar_source(self.src1)
        self.assertTrue(s.enabled)

    def test_last_sync(self):
        """最終同期時刻を記録できる"""
        database.set_calendar_source_last_sync(self.src1, "2026-08-25 19:00")
        s = database.get_calendar_source(self.src1)
        self.assertEqual(s.last_sync, "2026-08-25 19:00")

    def test_delete_cascades_events(self):
        """ソース削除でそのソースの予定も削除される"""
        e_id = database.create_event(database.Event(
            title="テスト予定", start_time=1000000, end_time=2000000,
            google_event_id="test_uid", source_id=self.src2
        ))
        self.assertIsNotNone(database.get_event(e_id))
        database.delete_calendar_source(self.src2)
        self.assertIsNone(database.get_event(e_id))


if __name__ == "__main__":
    unittest.main(verbosity=2)