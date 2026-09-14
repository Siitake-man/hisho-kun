"""
Neo-Secretary ストレージ Seam 分割 Phase 1 回帰テスト (tests/test_storage_seam_phase1.py)

storage パッケージの models.py および connection.py の独立性、
および database.py の Facade（完全後方互換性）を自動検証します。
"""

import os
import tempfile
import unittest

import storage
import database


class TestStorageSeamPhase1(unittest.TestCase):
    """Phase 1: models.py / connection.py の独立性および Facade 後方互換性テスト"""

    def test_01_storage_package_exports(self):
        """storage パッケージから必須シンボルがすべてインポート可能であることを検証。"""
        expected_symbols = [
            "Category",
            "Event",
            "CalendarSource",
            "StickyNote",
            "UserInsight",
            "Task",
            "TaskList",
            "Habit",
            "HabitLog",
            "HabitWithStatus",
            "HabitHeatmapPoint",
            "MinigameScore",
            "Device",
            "get_db_connection",
            "init_db",
        ]
        for symbol in expected_symbols:
            self.assertTrue(hasattr(storage, symbol), f"storage に {symbol} が存在しません")

    def test_02_database_facade_backward_compatibility(self):
        """database.py が storage の全シンボルを同一オブジェクトとして再エクスポートしていることを検証。"""
        check_pairs = [
            ("Category", storage.Category, database.Category),
            ("Event", storage.Event, database.Event),
            ("CalendarSource", storage.CalendarSource, database.CalendarSource),
            ("StickyNote", storage.StickyNote, database.StickyNote),
            ("UserInsight", storage.UserInsight, database.UserInsight),
            ("Task", storage.Task, database.Task),
            ("TaskList", storage.TaskList, database.TaskList),
            ("Habit", storage.Habit, database.Habit),
            ("HabitLog", storage.HabitLog, database.HabitLog),
            ("HabitWithStatus", storage.HabitWithStatus, database.HabitWithStatus),
            ("HabitHeatmapPoint", storage.HabitHeatmapPoint, database.HabitHeatmapPoint),
            ("MinigameScore", storage.MinigameScore, database.MinigameScore),
            ("Device", storage.Device, database.Device),
            ("get_db_connection", storage.get_db_connection, database.get_db_connection),
            ("init_db", storage.init_db, database.init_db),
        ]
        for name, storage_obj, database_obj in check_pairs:
            self.assertIs(storage_obj, database_obj, f"{name} の参照先が一致しません (Facade不整合)")

    def test_03_init_db_in_temp_database(self):
        """新設された connection.py の init_db が一時DBに対して全テーブルを正常初期化することを検証。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            temp_db = tf.name

        try:
            # 初期化実行
            storage.init_db(temp_db)

            # テーブル一覧を取得して検証
            with storage.get_db_connection(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = {row[0] for row in cursor.fetchall()}

            required_tables = {
                "categories",
                "events",
                "calendar_sources",
                "sticky_notes",
                "user_insights",
                "tasks",
                "task_lists",
                "reminders_sent",
                "habits",
                "habit_logs",
                "minigame_scores",
                "devices",
                "approval_audit_logs",
            }
            missing = required_tables - tables
            self.assertFalse(missing, f"必須テーブルが作成されていません: {missing}")
        finally:
            if os.path.exists(temp_db):
                os.remove(temp_db)

    def test_04_model_validation_integrity(self):
        """モデルのバリデーションが models.py でも意図通り動作することを検証。"""
        # Event の終了時刻 > 開始時刻 バリデーション
        with self.assertRaises(ValueError):
            storage.Event(
                title="エラーテスト",
                start_time=1000,
                end_time=500,  # start_time より前なのでエラーになるべき
            )

        # 正常な Event
        ev = storage.Event(
            title="正常テスト",
            start_time=1000,
            end_time=2000,
        )
        self.assertEqual(ev.title, "正常テスト")

        # Task のバリデーション
        task = storage.Task(title="タスクテスト", status="todo")
        self.assertEqual(task.title, "タスクテスト")
        self.assertEqual(task.status, "todo")


if __name__ == "__main__":
    unittest.main()
