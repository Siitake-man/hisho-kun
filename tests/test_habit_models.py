#!/usr/bin/env python3
"""
ネオ秘書くん - 習慣データモデルの単体テスト (tests/test_habit_models.py)

2026-09-01 コードレビュー P2①「Pydantic DTO完全移行」第二段。
get_habits_with_status / get_habit_heatmap_data の戻り値を dict 生辞書から
Pydantic モデルへ移行した契約と、briefing_engine の習慣集計
(旧実装は存在しない is_done キーを参照し達成数が常に0になる潜在バグがあった)
を検証する。

実行:
    venv/Scripts/python.exe -m unittest tests.test_habit_models
"""

import os
import tempfile
import unittest
from datetime import datetime

import database
from database import Habit, HabitHeatmapPoint, HabitWithStatus
from briefing_engine import _build_habit_summary


class HabitWithStatusModelTest(unittest.TestCase):
    """get_habits_with_status のモデル返却契約テスト。"""

    def setUp(self) -> None:
        """テスト用一時DBと習慣1件を準備する。"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_habit_models.db")
        database.init_db(self.db_path)
        self.habit_id = database.create_habit(
            Habit(title="水を飲む", emoji="💧", target_days_per_week=7),
            db_path=self.db_path,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_returns_habit_with_status_models(self) -> None:
        """戻り値が HabitWithStatus モデルのリストであること。"""
        habits = database.get_habits_with_status(db_path=self.db_path)
        self.assertEqual(len(habits), 1)
        self.assertIsInstance(habits[0], HabitWithStatus)

    def test_completed_today_and_streak(self) -> None:
        """達成トグル後、completed_today=True / streak=1 / total_completed=1 になること。"""
        database.toggle_habit_log(self.habit_id, db_path=self.db_path)
        h = database.get_habits_with_status(db_path=self.db_path)[0]
        self.assertTrue(h.completed_today)
        self.assertEqual(h.streak, 1)
        self.assertEqual(h.total_completed, 1)
        self.assertEqual(h.title, "水を飲む")
        self.assertEqual(h.emoji, "💧")
        self.assertEqual(h.target_days_per_week, 7)

    def test_model_dump_matches_legacy_dict_keys(self) -> None:
        """旧 dict 契約と同じキーが model_dump で得られること (JSON送信の後方互換)。"""
        database.toggle_habit_log(self.habit_id, db_path=self.db_path)
        dumped = database.get_habits_with_status(db_path=self.db_path)[0].model_dump()
        for key in (
            "id", "title", "emoji", "target_days_per_week",
            "completed_today", "streak", "total_completed", "created_at",
        ):
            self.assertIn(key, dumped)


class HabitHeatmapPointModelTest(unittest.TestCase):
    """get_habit_heatmap_data のモデル返却契約テスト。"""

    def setUp(self) -> None:
        """テスト用一時DBと習慣1件を準備する。"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_habit_heatmap.db")
        database.init_db(self.db_path)
        self.habit_id = database.create_habit(Habit(title="読書"), db_path=self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_returns_habit_heatmap_point_models(self) -> None:
        """戻り値が HabitHeatmapPoint モデルのリスト (指定日数分) であること。"""
        points = database.get_habit_heatmap_data(days=7, db_path=self.db_path)
        self.assertEqual(len(points), 7)
        for p in points:
            self.assertIsInstance(p, HabitHeatmapPoint)

    def test_today_count_and_level_after_toggle(self) -> None:
        """達成トグル後、当日エントリの count=1 / level=1 になること。"""
        database.toggle_habit_log(self.habit_id, db_path=self.db_path)
        points = database.get_habit_heatmap_data(days=7, db_path=self.db_path)
        today_str = datetime.now().strftime("%Y-%m-%d")
        today = next(p for p in points if p.date == today_str)
        self.assertEqual(today.count, 1)
        self.assertEqual(today.level, 1)
        self.assertTrue(0 <= today.day_of_week <= 6)


class BuildHabitSummaryTest(unittest.TestCase):
    """briefing_engine._build_habit_summary の集計契約テスト。

    旧実装は存在しない is_done キーを参照していたため、朝会/終礼の
    習慣達成数が常に 0 になる潜在バグがあった。completed_today を参照して
    正しく集計することを検証する (回帰防止)。
    """

    def _habit(self, completed_today: bool) -> HabitWithStatus:
        """テスト用の習慣モデルを生成する。"""
        return HabitWithStatus(
            id=1,
            title="テスト習慣",
            emoji="🌱",
            target_days_per_week=7,
            completed_today=completed_today,
            streak=1,
            total_completed=1,
            created_at=0,
        )

    def test_counts_completed_today(self) -> None:
        """completed_today=True の習慣のみ達成数に数えられること (旧 is_done バグの回帰防止)。"""
        summary = _build_habit_summary([self._habit(True), self._habit(False), self._habit(True)])
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["done"], 2)
        self.assertEqual(summary["rate_percent"], 66)

    def test_list_items_are_dicts(self) -> None:
        """list フィールドは JSON に直接載せられるよう dict 化されていること。"""
        summary = _build_habit_summary([self._habit(True)])
        self.assertIsInstance(summary["list"][0], dict)

    def test_empty_habits(self) -> None:
        """習慣ゼロ件でも zero 除算せず rate=0 を返すこと。"""
        summary = _build_habit_summary([])
        self.assertEqual(summary, {"total": 0, "done": 0, "rate_percent": 0, "list": []})


if __name__ == "__main__":
    unittest.main(verbosity=2)
