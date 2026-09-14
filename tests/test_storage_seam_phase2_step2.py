"""
Neo-Secretary ストレージ Seam 分割 Phase 2 Step 2 回帰テスト (tests/test_storage_seam_phase2_step2.py)

storage パッケージに切り出された全ドメインRepository:
- calendar_repo (予定・カテゴリ・カレンダー購読ソース)
- sticky_repo (付箋メモ)
- insight_repo (ボスの知見・示唆)
- habit_repo (習慣トラッカー・ヒートマップ)
- minigame_repo (ミニゲームスコア)
- task_repo (タスク・リマインダー)
- connection.py (バックアップ機能)
および database.py Facade の 100% 後方互換性を自動検証します。
"""

import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta

import storage
import database
from storage.models import (
    Category,
    Event,
    CalendarSource,
    StickyNote,
    UserInsight,
    Task,
    Habit,
    MinigameScore,
)


class TestStorageSeamPhase2Step2(unittest.TestCase):
    """Phase 2 Step 2: ドメインRepository独立性および database.py Facade 整合性テスト"""

    def test_01_storage_package_step2_exports(self):
        """storage パッケージから Step 2 で切り出された全シンボルがインポート可能であることを検証。"""
        expected_symbols = [
            # Models
            "Category", "Event", "CalendarSource", "StickyNote",
            "UserInsight", "Task", "TaskList", "Habit", "HabitLog",
            "HabitWithStatus", "HabitHeatmapPoint", "MinigameScore",
            # Connection & Backup
            "get_db_connection", "init_db", "backup_database", "auto_backup",
            # Calendar Repo
            "create_category", "get_category", "get_all_categories",
            "create_event", "get_event", "get_upcoming_events", "get_events_between",
            "create_calendar_source", "get_all_calendar_sources", "get_calendar_source",
            "update_calendar_source", "set_calendar_source_enabled", "set_calendar_source_last_sync",
            "delete_calendar_source",
            # Sticky Note Repo
            "create_sticky_note", "get_all_sticky_notes", "update_sticky_note", "delete_sticky_note",
            # Insight Repo
            "create_user_insight", "add_user_insight", "get_user_insights", "delete_user_insight",
            # Habit Repo
            "create_habit", "delete_habit", "toggle_habit_log", "get_habits_with_status", "get_habit_heatmap_data",
            # Minigame Repo
            "record_minigame_score", "get_high_score", "get_recent_minigame_scores",
            # Task Repo
            "create_task", "get_tasks", "get_subtasks", "add_subtask", "complete_task",
            "reopen_task", "update_task", "delete_task", "is_reminder_sent", "mark_reminder_sent",
            "get_task_lists", "create_task_list", "move_task_list", "delete_task_list",
            "rename_task_list", "update_task_tags",
        ]
        for symbol in expected_symbols:
            self.assertTrue(hasattr(storage, symbol), f"storage に {symbol} が存在しません")
            self.assertTrue(hasattr(database, symbol), f"database に {symbol} が存在しません")

    def test_02_database_facade_step2_identity(self):
        """database.py の各関数・モデルが storage 側の実体と同一ポインタであることを検証 (100% 後方互換)。"""
        symbols_to_check = [
            "Category", "Event", "StickyNote", "UserInsight", "Task", "Habit", "MinigameScore",
            "init_db", "backup_database", "auto_backup",
            "create_category", "get_category", "create_event", "get_upcoming_events",
            "create_sticky_note", "get_all_sticky_notes",
            "add_user_insight", "get_user_insights",
            "create_habit", "toggle_habit_log", "get_habits_with_status",
            "record_minigame_score", "get_high_score",
            "create_task", "get_tasks",
        ]
        for symbol in symbols_to_check:
            storage_obj = getattr(storage, symbol)
            database_obj = getattr(database, symbol)
            self.assertIs(storage_obj, database_obj, f"{symbol} の参照先が一致しません (Facade 不整合)")

    def test_03_calendar_repo_crud(self):
        """storage.calendar_repo のカテゴリ＆イベントCRUDを検証。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            temp_db = tf.name

        try:
            storage.init_db(temp_db)

            # カテゴリ作成
            cat = Category(name="会議", color="#FF0000", icon="business")
            cat_id = storage.create_category(cat, db_path=temp_db)
            self.assertGreater(cat_id, 0)

            retrieved_cat = storage.get_category(cat_id, db_path=temp_db)
            self.assertIsNotNone(retrieved_cat)
            self.assertEqual(retrieved_cat.name, "会議")

            # 予定作成
            now_ms = int(time.time() * 1000)
            event = Event(
                title="アーキテクチャレビュー",
                start_time=now_ms + 3600000,
                end_time=now_ms + 7200000,
                category_id=cat_id,
            )
            ev_id = storage.create_event(event, db_path=temp_db)
            self.assertGreater(ev_id, 0)

            upcoming = storage.get_upcoming_events(days=1, db_path=temp_db)
            self.assertEqual(len(upcoming), 1)
            self.assertEqual(upcoming[0].title, "アーキテクチャレビュー")
        finally:
            if os.path.exists(temp_db):
                os.remove(temp_db)

    def test_04_sticky_repo_crud(self):
        """storage.sticky_repo の付箋メモCRUDを検証。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            temp_db = tf.name

        try:
            storage.init_db(temp_db)

            note = StickyNote(content="Seam分割完了！", color="#FEF08A")
            note_id = storage.create_sticky_note(note, db_path=temp_db)
            self.assertGreater(note_id, 0)

            notes = storage.get_all_sticky_notes(db_path=temp_db)
            self.assertEqual(len(notes), 1)
            self.assertEqual(notes[0].content, "Seam分割完了！")

            # 更新
            note.id = note_id
            note.content = "Seam分割完了＆回帰テスト通過！"
            storage.update_sticky_note(note, db_path=temp_db)
            notes_after = storage.get_all_sticky_notes(db_path=temp_db)
            self.assertEqual(notes_after[0].content, "Seam分割完了＆回帰テスト通過！")
        finally:
            if os.path.exists(temp_db):
                os.remove(temp_db)

    def test_05_insight_repo_crud(self):
        """storage.insight_repo のボス知見CRUDを検証。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            temp_db = tf.name

        try:
            storage.init_db(temp_db)

            insight_id = storage.add_user_insight(
                category="Project",
                content="Facade パターンにより既存コードを1行も壊さず Seam を切り出す",
                importance=4,
                db_path=temp_db
            )
            self.assertGreater(insight_id, 0)

            insights = storage.get_user_insights(category="Project", db_path=temp_db)
            self.assertEqual(len(insights), 1)
            self.assertIn("Facade パターン", insights[0].content)
        finally:
            if os.path.exists(temp_db):
                os.remove(temp_db)

    def test_06_habit_repo_crud(self):
        """storage.habit_repo の習慣トラッカーCRUDを検証。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            temp_db = tf.name

        try:
            storage.init_db(temp_db)

            habit = Habit(title="5分コードリーディング", emoji="📖", target_days_per_week=5)
            h_id = storage.create_habit(habit, db_path=temp_db)
            self.assertGreater(h_id, 0)

            today_str = datetime.now().strftime("%Y-%m-%d")
            toggled = storage.toggle_habit_log(h_id, target_date=today_str, db_path=temp_db)
            self.assertTrue(toggled)

            habits_status = storage.get_habits_with_status(db_path=temp_db)
            self.assertEqual(len(habits_status), 1)
            self.assertTrue(habits_status[0].completed_today)
        finally:
            if os.path.exists(temp_db):
                os.remove(temp_db)

    def test_07_minigame_repo_crud(self):
        """storage.minigame_repo のミニゲームスコアCRUDを検証。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            temp_db = tf.name

        try:
            storage.init_db(temp_db)

            s1_id = storage.record_minigame_score("pixel_defense", 1500, db_path=temp_db)
            s2_id = storage.record_minigame_score("pixel_defense", 3000, db_path=temp_db)
            self.assertGreater(s1_id, 0)
            self.assertGreater(s2_id, 0)

            high_score = storage.get_high_score("pixel_defense", db_path=temp_db)
            self.assertEqual(high_score, 3000)

            recent = storage.get_recent_minigame_scores("pixel_defense", limit=5, db_path=temp_db)
            self.assertEqual(len(recent), 2)
            self.assertEqual(recent[0].score, 3000)
        finally:
            if os.path.exists(temp_db):
                os.remove(temp_db)

    def test_08_task_repo_crud(self):
        """storage.task_repo のタスクCRUDを検証。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            temp_db = tf.name

        try:
            storage.init_db(temp_db)

            task = Task(title="Seam分割Phase2完遂", priority=2)
            task_id = storage.create_task(task, db_path=temp_db)
            self.assertGreater(task_id, 0)

            tasks = storage.get_tasks(db_path=temp_db)
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0].title, "Seam分割Phase2完遂")

            # 完了更新
            ok = storage.complete_task(task_id, db_path=temp_db)
            self.assertTrue(ok)

            # completed タスク取得
            completed_tasks = storage.get_tasks(status="completed", db_path=temp_db)
            self.assertEqual(len(completed_tasks), 1)
            self.assertEqual(completed_tasks[0].status, "completed")
        finally:
            if os.path.exists(temp_db):
                os.remove(temp_db)

    def test_09_backup_database(self):
        """storage.connection の backup_database および auto_backup を検証。"""
        with tempfile.TemporaryDirectory() as td:
            db_file = os.path.join(td, "test_backup.db")
            backup_dir = os.path.join(td, "backups")

            storage.init_db(db_file)

            # backup_database
            res_path = storage.backup_database(db_path=db_file, backup_dir=backup_dir, max_generations=2)
            self.assertIsNotNone(res_path)
            self.assertTrue(os.path.exists(res_path))

            # auto_backup (引数なし・フェイルセーフ呼び出し)
            storage.auto_backup()


if __name__ == "__main__":
    unittest.main()
