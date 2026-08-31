#!/usr/bin/env python3
"""
ネオ秘書くん - リマインダーエンジンの単体テスト (tests/test_reminder_engine.py)

roadmap 3.1「時刻ベースのリマインダー」の通知判定ロジックを検証する。
境界: 通知窓内の発火 / 既通知の二重発火防止 / 完了タスクのスキップ /
期限まで遠い対象のスキップ / 予定の発火。
"""

import os
import tempfile
import unittest
from datetime import datetime

import database
from database import Event, Task
from reminder_engine import ReminderEngine


class TestReminderEngine(unittest.TestCase):
    """リマインダー通知判定のテスト"""

    def setUp(self):
        """テスト用の一時DBとエンジンを用意する"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_secretary.db")
        database.init_db(self.db_path)
        self.messages: list = []
        self.engine = ReminderEngine(
            on_reminder=self.messages.append,
            db_path=self.db_path,
            lead_minutes=10,
            interval_sec=30.0,
        )
        self.now_ms = int(datetime.now().timestamp() * 1000)

    def tearDown(self):
        self.engine.stop()
        self.temp_dir.cleanup()

    def _create_task(self, title: str, due_ms: int) -> int:
        """期限付きタスクを作成するヘルパー"""
        return database.create_task(
            Task(title=title, due_date=due_ms, priority=0, status="todo"),
            db_path=self.db_path,
        )

    def test_task_due_soon_fires_once(self):
        """通知窓内 (10分前) のタスクが1回だけ発火し、二重通知しない"""
        task_id = self._create_task("経費精算", self.now_ms + 5 * 60_000)

        fired = self.engine.check_once(now_ms=self.now_ms)
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0]["type"], "task")
        self.assertEqual(fired[0]["id"], task_id)
        self.assertIn("経費精算", fired[0]["message"])
        self.assertEqual(len(self.messages), 1)

        # 2回目の検査では二重発火しない (reminders_sent 冪等記録)
        fired_again = self.engine.check_once(now_ms=self.now_ms + 30_000)
        self.assertEqual(len(fired_again), 0)
        self.assertEqual(len(self.messages), 1)
        self.assertTrue(database.is_reminder_sent("task", task_id, db_path=self.db_path))

    def test_completed_task_skipped(self):
        """完了済みタスクは通知窓内でも発火しない"""
        task_id = self._create_task("終わったタスク", self.now_ms + 5 * 60_000)
        database.complete_task(task_id, db_path=self.db_path)

        fired = self.engine.check_once(now_ms=self.now_ms)
        self.assertEqual(len(fired), 0)
        self.assertEqual(len(self.messages), 0)

    def test_far_future_task_skipped(self):
        """期限が通知窓より遠いタスクは発火しない"""
        self._create_task("来月のタスク", self.now_ms + 60 * 60_000)

        fired = self.engine.check_once(now_ms=self.now_ms)
        self.assertEqual(len(fired), 0)

    def test_overdue_too_old_skipped(self):
        """期限を大きく過ぎたタスク (取りこぼし猶予30分超) は黙秘する"""
        self._create_task("昔のタスク", self.now_ms - 2 * 60 * 60_000)

        fired = self.engine.check_once(now_ms=self.now_ms)
        self.assertEqual(len(fired), 0)

    def test_event_soon_fires(self):
        """開始5分前の予定が発火し、メッセージに予定名が含まれる"""
        start = self.now_ms + 5 * 60_000
        event_id = database.create_event(
            Event(title="歯医者", start_time=start, end_time=start + 60 * 60_000),
            db_path=self.db_path,
        )

        fired = self.engine.check_once(now_ms=self.now_ms)
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0]["type"], "event")
        self.assertEqual(fired[0]["id"], event_id)
        self.assertIn("歯医者", fired[0]["message"])
        self.assertEqual(len(self.messages), 1)

    def test_phone_payload_ttl(self):
        """スマホ向けペイロードは TTL (5分) 経過後に消える"""
        self._create_task("スマホへ通知", self.now_ms + 5 * 60_000)
        self.engine.check_once(now_ms=self.now_ms)

        pending = self.engine.get_pending_for_phone(now_ms=self.now_ms + 60_000)
        self.assertEqual(len(pending), 1)

        pending_expired = self.engine.get_pending_for_phone(now_ms=self.now_ms + 6 * 60_000)
        self.assertEqual(len(pending_expired), 0)


if __name__ == "__main__":
    unittest.main()
