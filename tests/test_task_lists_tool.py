#!/usr/bin/env python3
"""
ネオ秘書くん - タスクリスト機能の単体テスト (tests/test_task_lists_tool.py)

Plan A (整合性Fix) で追実装した list_task_lists_tool (AIツール) と
database.get_task_lists / create_task_list (DB層) の結合を検証する。
"""

import os
import tempfile
import unittest

import database
import db_tools


class TestTaskListsTool(unittest.TestCase):
    """タスクリスト一覧取得 (AIツール + DB層) のテスト"""

    def setUp(self):
        """テスト用の一時DBを生成し、AIツールのDB参照をテストDBへ差し替える"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_secretary.db")
        database.init_db(self.db_path)
        self._orig_get_task_lists = database.get_task_lists
        # db_tools.list_task_lists_tool は既定DBパスで呼ぶため、テストDBへ向け直す
        database.get_task_lists = lambda db_path="neo_secretary.db": self._orig_get_task_lists(db_path=self.db_path)

    def tearDown(self):
        database.get_task_lists = self._orig_get_task_lists
        self.temp_dir.cleanup()

    def test_get_task_lists_empty(self):
        """リスト未作成の状態では空リストが返る"""
        lists = database.get_task_lists(db_path=self.db_path)
        self.assertEqual(len(lists), 0)

    def test_create_and_get_task_lists(self):
        """リスト作成後、sort_order順で取得できる"""
        id_b = database.create_task_list("仕事", emoji="💼", sort_order=1, db_path=self.db_path)
        id_a = database.create_task_list("プライベート", emoji="🏠", sort_order=0, db_path=self.db_path)

        lists = database.get_task_lists(db_path=self.db_path)
        self.assertEqual(len(lists), 2)
        # sort_order 昇順 → プライベート(0) → 仕事(1)
        self.assertEqual(lists[0].id, id_a)
        self.assertEqual(lists[0].name, "プライベート")
        self.assertEqual(lists[1].id, id_b)
        self.assertEqual(lists[1].name, "仕事")

    def test_tool_returns_formatted_lists(self):
        """AIツール list_task_lists_tool が整形済み一覧文字列を返す"""
        database.create_task_list("仕事", emoji="💼", sort_order=0, db_path=self.db_path)
        result = db_tools.list_task_lists_tool.invoke({})
        self.assertIn("🗂️ タスクリスト一覧:", result)
        self.assertIn("💼 仕事", result)
        self.assertIn("ID:", result)

    def test_tool_returns_empty_message(self):
        """リストが1つも無い場合、AIツールは案内メッセージを返す"""
        result = db_tools.list_task_lists_tool.invoke({})
        self.assertIn("まだ1つも作成されていません", result)


if __name__ == "__main__":
    unittest.main()
