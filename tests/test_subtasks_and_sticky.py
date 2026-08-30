#!/usr/bin/env python3
"""
ネオ秘書くん - サブタスク ＆ 付箋座標永続化の単体テスト (tests/test_subtasks_and_sticky.py)
"""

import os
import tempfile
import unittest
import database
from database import Task, StickyNote


class TestSubtasksAndSticky(unittest.TestCase):
    """サブタスク機能および付箋座標永続化のテスト"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_secretary.db")
        database.init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_subtasks_creation_and_retrieval(self):
        """親タスクに対する子タスク（サブタスク）の作成・取得・完了を検証"""
        # 1. 親タスク作成
        parent = Task(title="大規模リファクタリング計画", priority=2)
        parent_id = database.create_task(parent, db_path=self.db_path)
        self.assertIsNotNone(parent_id)

        # 2. サブタスク（子タスク）の追加
        sub1_id = database.add_subtask(parent_id, "既存コードの依存関係スキャン", db_path=self.db_path)
        sub2_id = database.add_subtask(parent_id, "単体テストの追加", db_path=self.db_path)

        # 3. サブタスク一覧の取得
        subtasks = database.get_subtasks(parent_id, db_path=self.db_path)
        self.assertEqual(len(subtasks), 2)
        self.assertEqual(subtasks[0].title, "既存コードの依存関係スキャン")
        self.assertEqual(subtasks[0].parent_id, parent_id)
        self.assertEqual(subtasks[1].title, "単体テストの追加")

        # 4. 親タスク一覧の取得 (parent_id is Noneのみ)
        all_tasks = database.get_tasks(status="todo", db_path=self.db_path)
        parent_tasks = [t for t in all_tasks if t.parent_id is None]
        self.assertEqual(len(parent_tasks), 1)
        self.assertEqual(parent_tasks[0].id, parent_id)

        # 5. サブタスクの完了
        database.complete_task(sub1_id, db_path=self.db_path)
        subtasks_after = database.get_subtasks(parent_id, db_path=self.db_path)
        self.assertEqual(len(subtasks_after), 2)
        # 未完了が先、完了済みが後にソートされる
        self.assertEqual(subtasks_after[0].id, sub2_id)
        self.assertEqual(subtasks_after[0].status, "todo")
        self.assertEqual(subtasks_after[1].id, sub1_id)
        self.assertEqual(subtasks_after[1].status, "completed")

    def test_sticky_note_position_persistence(self):
        """付箋の移動座標（position_x, position_y）がDBへ正しく更新・永続化されるか検証"""
        # 1. 付箋の作成
        note = StickyNote(
            content="大事なメモ",
            position_x=100,
            position_y=100,
            width=200,
            height=200
        )
        note_id = database.create_sticky_note(note, db_path=self.db_path)
        self.assertIsNotNone(note_id)

        # 2. 移動後の座標に更新
        note.id = note_id
        note.position_x = 550
        note.position_y = 380
        success = database.update_sticky_note(note, db_path=self.db_path)
        self.assertTrue(success)

        # 3. DBから再取得して座標が一致するか確認
        notes = database.get_all_sticky_notes(db_path=self.db_path)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].position_x, 550)
        self.assertEqual(notes[0].position_y, 380)


if __name__ == "__main__":
    unittest.main()
