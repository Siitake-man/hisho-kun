"""update_task (タスク部分更新) のユニットテスト。

スマホ編集シートの中枢となる DB 層の挙動を検証する:
- タイトル・期日・優先度の更新
- 重要度/緊急度の True/False/None (未指定) トグル
- ホワイトリスト外キーのみでは更新失敗 (False)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database  # noqa: E402


class TestUpdateTask(unittest.TestCase):
    """database.update_task の振る舞いテスト (テンポラリDBを使用)。"""

    def setUp(self):
        """テストごとに独立したテンポラリDBを用意する。"""
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test_update.db")
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        database.init_db(self.db_path)

    def tearDown(self):
        """テンポラリDBを後片付けする。"""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_update_title_due_priority(self):
        """タイトル・期日・優先度が更新される"""
        task_id = database.create_task(database.Task(title="元タイトル"), db_path=self.db_path)
        ok = database.update_task(task_id, {
            "title": "新しいタイトル",
            "due_date": 1756600000000,
            "priority": 3,
        }, db_path=self.db_path)
        self.assertTrue(ok)
        tasks = database.get_tasks(status="todo", db_path=self.db_path)
        self.assertEqual(len(tasks), 1)
        t = tasks[0]
        self.assertEqual(t.title, "新しいタイトル")
        self.assertEqual(t.due_date, 1756600000000)
        self.assertEqual(t.priority, 3)

    def test_update_flags_true_false_none(self):
        """重要度/緊急度は True/False/None をそのまま保存できる"""
        task_id = database.create_task(database.Task(title="属性テスト"), db_path=self.db_path)
        self.assertTrue(database.update_task(task_id, {
            "importance_flag": True, "urgency_flag": False,
        }, db_path=self.db_path))
        t = database.get_tasks(status="todo", db_path=self.db_path)[0]
        self.assertIs(t.importance_flag, True)
        self.assertIs(t.urgency_flag, False)
        # None = 未指定へ戻す (4象限は推定ルールへフォールバック)
        self.assertTrue(database.update_task(task_id, {
            "importance_flag": None, "urgency_flag": None,
        }, db_path=self.db_path))
        t2 = database.get_tasks(status="todo", db_path=self.db_path)[0]
        self.assertIsNone(t2.importance_flag)
        self.assertIsNone(t2.urgency_flag)

    def test_update_whitelist_and_missing_id(self):
        """ホワイトリスト外キーのみ・存在しないIDは False"""
        task_id = database.create_task(database.Task(title="不正テスト"), db_path=self.db_path)
        self.assertFalse(database.update_task(task_id, {"evil_column": 1}, db_path=self.db_path))
        self.assertFalse(database.update_task(99999, {"title": "狙い打ち"}, db_path=self.db_path))


if __name__ == "__main__":
    unittest.main()