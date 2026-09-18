"""reopen_task (タスク完了取り消し) のユニットテスト。

誤タップ復活の中枢となる DB 層の挙動を検証する:
- 単発タスク: 完了 → 取り消しで 'todo' に戻る
- 繰り返しタスク: 完了時に生成された次回分が取り消し時に削除される
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database  # noqa: E402


class TestReopenTask(unittest.TestCase):
    """database.reopen_task の振る舞いテスト (テンポラリDBを使用)。"""

    def setUp(self):
        """テストごとに独立したテンポラリDBを用意する。"""
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test_reopen.db")
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        database.init_db(self.db_path)

    def tearDown(self):
        """テンポラリDBを後片付けする。"""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_reopen_simple_task(self):
        """単発タスク: 完了 → 取り消しで status が 'todo' に戻る"""
        task = database.create_task(database.Task(title="取り消しテスト"), db_path=self.db_path)
        self.assertTrue(database.complete_task(task, db_path=self.db_path))
        done = database.get_tasks(status="completed", db_path=self.db_path)
        self.assertEqual(len(done), 1)
        self.assertTrue(database.reopen_task(task, db_path=self.db_path))
        todo = database.get_tasks(status="todo", db_path=self.db_path)
        self.assertEqual(len(todo), 1)
        self.assertEqual(todo[0].title, "取り消しテスト")

    def test_reopen_recurring_task_removes_next_occurrence(self):
        """繰り返しタスク: 完了で次回分が生成され、取り消しで次回分も削除される"""
        task = database.create_task(database.Task(
            title="毎週の掃除", recurrence="weekly",
        ), db_path=self.db_path)
        self.assertTrue(database.complete_task(task, db_path=self.db_path))
        # 完了によって次回分 (未完了・同一タイトル) が自動生成されている
        todo_after_complete = database.get_tasks(status="todo", db_path=self.db_path)
        self.assertEqual(len(todo_after_complete), 1)
        self.assertEqual(todo_after_complete[0].title, "毎週の掃除")
        # 取り消すと元タスクが復活し、次回分は消える
        self.assertTrue(database.reopen_task(task, db_path=self.db_path))
        todo_after_reopen = database.get_tasks(status="todo", db_path=self.db_path)
        self.assertEqual(len(todo_after_reopen), 1)
        self.assertEqual(todo_after_reopen[0].id, task)

    def test_reopen_nonexistent_or_todo_task_fails(self):
        """未完了タスクや存在しないIDは取り消し対象外 (False)"""
        task = database.create_task(database.Task(title="未完了のまま"), db_path=self.db_path)
        self.assertFalse(database.reopen_task(task, db_path=self.db_path))
        self.assertFalse(database.reopen_task(99999, db_path=self.db_path))

    def test_get_tasks_completed_today_filters_old_completed_tasks(self):
        """get_tasks_completed_today は過去日時の完了タスクを除外し、本日分のみ返す (P1-1)。"""
        from datetime import datetime, timedelta
        import storage.connection

        # 1. 本日完了タスクを作成
        t_today = database.create_task(database.Task(title="今日完了タスク"), db_path=self.db_path)
        database.complete_task(t_today, db_path=self.db_path)

        # 2. 3日前に完了した古いタスクを作成し、updated_at を3日前に偽装
        t_old = database.create_task(database.Task(title="3日前完了タスク"), db_path=self.db_path)
        database.complete_task(t_old, db_path=self.db_path)
        old_ms = int((datetime.now() - timedelta(days=3)).timestamp() * 1000)
        with storage.connection.get_db_connection(self.db_path) as conn:
            conn.execute("UPDATE tasks SET updated_at = ? WHERE id = ?", (old_ms, t_old))

        # 3. get_tasks(status="completed") だと両方取れてしまう（従来のバグ）
        all_completed = database.get_tasks(status="completed", db_path=self.db_path)
        self.assertEqual(len(all_completed), 2)

        # 4. get_tasks_completed_today() だと本日分のみ取れる（新設 Seam の成果）
        today_completed = database.get_tasks_completed_today(db_path=self.db_path)
        self.assertEqual(len(today_completed), 1)
        self.assertEqual(today_completed[0].title, "今日完了タスク")


if __name__ == "__main__":
    unittest.main()
