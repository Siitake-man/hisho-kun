#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - 手帳・タスク・習慣・付箋ストレージ統合テスト (tests/test_storage_tasks_consolidated.py)

テストスイート引き算スプリントにより、以下の孤児テストファイルを集約・統合:
  1. TestUpdateTask (旧 tests/test_update_task.py): タスク部分更新・4象限フラグトグル
  2. TestSubtasksAndSticky (旧 tests/test_subtasks_and_sticky.py): サブタスク親子関係・付箋座標永続化
  3. TestHabitCache (旧 tests/test_habit_cache.py): 習慣＆70日ヒートマップ 30秒TTLキャッシュ
"""

import json
import logging
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import database
from database import Task, StickyNote
import life_dreamer
import local_sync_server
import suggest_engine

logging.getLogger("local_sync_server").setLevel(logging.CRITICAL)


# ==============================================================================
# 1. タスク部分更新 (update_task) 契約テスト
# ==============================================================================
class TestUpdateTask(unittest.TestCase):
    """database.update_task の振る舞いテスト (テンポラリDBを使用)。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmp.name, "test_update.db")
        database.init_db(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

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


# ==============================================================================
# 2. サブタスク ＆ 付箋座標永続化 契約テスト
# ==============================================================================
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
        parent = Task(title="大規模リファクタリング計画", priority=2)
        parent_id = database.create_task(parent, db_path=self.db_path)
        self.assertIsNotNone(parent_id)

        sub1_id = database.add_subtask(parent_id, "既存コードの依存関係スキャン", db_path=self.db_path)
        sub2_id = database.add_subtask(parent_id, "単体テストの追加", db_path=self.db_path)

        subtasks = database.get_subtasks(parent_id, db_path=self.db_path)
        self.assertEqual(len(subtasks), 2)
        self.assertEqual(subtasks[0].title, "既存コードの依存関係スキャン")
        self.assertEqual(subtasks[0].parent_id, parent_id)
        self.assertEqual(subtasks[1].title, "単体テストの追加")

        all_tasks = database.get_tasks(status="todo", db_path=self.db_path)
        parent_tasks = [t for t in all_tasks if t.parent_id is None]
        self.assertEqual(len(parent_tasks), 1)
        self.assertEqual(parent_tasks[0].id, parent_id)

        database.complete_task(sub1_id, db_path=self.db_path)
        subtasks_after = database.get_subtasks(parent_id, db_path=self.db_path)
        self.assertEqual(len(subtasks_after), 2)
        self.assertEqual(subtasks_after[0].id, sub2_id)
        self.assertEqual(subtasks_after[0].status, "todo")
        self.assertEqual(subtasks_after[1].id, sub1_id)
        self.assertEqual(subtasks_after[1].status, "completed")

    def test_sticky_note_position_persistence(self):
        """付箋の移動座標（position_x, position_y）がDBへ正しく更新・永続化されるか検証"""
        note = StickyNote(
            content="大事なメモ",
            position_x=100,
            position_y=100,
            width=200,
            height=200,
        )
        note_id = database.create_sticky_note(note, db_path=self.db_path)
        self.assertIsNotNone(note_id)

        note.id = note_id
        note.position_x = 550
        note.position_y = 380
        success = database.update_sticky_note(note, db_path=self.db_path)
        self.assertTrue(success)

        notes = database.get_all_sticky_notes(db_path=self.db_path)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].position_x, 550)
        self.assertEqual(notes[0].position_y, 380)


# ==============================================================================
# 3. 習慣データ ＆ 70日ヒートマップ 30秒TTLキャッシュ 統合テスト
# ==============================================================================
class TestHabitCache(unittest.TestCase):
    """習慣データおよび70日ヒートマップの30秒TTLキャッシュの動作検証"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.mock_get_tasks = MagicMock(return_value=[])
        cls.mock_get_upcoming_events = MagicMock(return_value=[])
        cls.mock_get_all_calendar_sources = MagicMock(return_value=[])
        mock_habit = MagicMock()
        mock_habit.model_dump.return_value = {"id": 1, "title": "読書"}
        cls.mock_get_habits = MagicMock(return_value=[mock_habit])
        cls.mock_get_heatmap = MagicMock(return_value=[])

        cls._patchers = [
            patch.object(database, "get_tasks", cls.mock_get_tasks),
            patch.object(database, "get_upcoming_events", cls.mock_get_upcoming_events),
            patch.object(database, "get_all_calendar_sources", cls.mock_get_all_calendar_sources),
            patch.object(database, "get_habits_with_status", cls.mock_get_habits),
            patch.object(database, "get_habit_heatmap_data", cls.mock_get_heatmap),
        ]

        suggest_engine_mock = MagicMock()
        suggest_engine_mock.get_cached_suggestions.return_value = []
        suggest_engine_mock.config = {"sources": {}, "news_keywords": []}
        cls._patchers.append(patch.object(
            suggest_engine, "get_suggestion_engine", MagicMock(return_value=suggest_engine_mock)
        ))

        life_dreamer_mock = MagicMock()
        life_dreamer_mock.get_life_state.return_value = {
            "current_activity": "resting", "weather": "sunny", "message": "", "history": []
        }
        cls._patchers.append(patch.object(life_dreamer, "get_life_dreamer", MagicMock(return_value=life_dreamer_mock)))

        for p in cls._patchers:
            p.start()

        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), local_sync_server.DeskPetSyncHandler)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.server_thread.join(timeout=5)
        for p in cls._patchers:
            p.stop()

    def setUp(self) -> None:
        local_sync_server.invalidate_habit_cache()
        self.mock_get_habits.reset_mock()
        self.mock_get_heatmap.reset_mock()

    def _request_status(self) -> dict:
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/status")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))

    def test_habit_cache_ttl_and_invalidation(self):
        """30秒TTLキャッシュが効き、無効化関数でリセットされることを検証"""
        # 初回リクエスト: DB参照が1回発生する
        res1 = self._request_status()
        self.assertEqual(self.mock_get_habits.call_count, 1)
        self.assertEqual(self.mock_get_heatmap.call_count, 1)

        # 2回目リクエスト (30秒以内): キャッシュが使われ、DB参照カウントは増えない
        res2 = self._request_status()
        self.assertEqual(self.mock_get_habits.call_count, 1)
        self.assertEqual(self.mock_get_heatmap.call_count, 1)

        # キャッシュ無効化実行
        local_sync_server.invalidate_habit_cache()

        # 3回目リクエスト: キャッシュが無効化されたため、DB参照カウントが増加する (2回目)
        res3 = self._request_status()
        self.assertEqual(self.mock_get_habits.call_count, 2)
        self.assertEqual(self.mock_get_heatmap.call_count, 2)


if __name__ == "__main__":
    unittest.main()
