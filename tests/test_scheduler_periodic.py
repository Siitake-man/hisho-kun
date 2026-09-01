#!/usr/bin/env python3
"""
ネオ秘書くん - ProactiveScheduler 第二段の単体テスト (tests/test_scheduler_periodic.py)

P2②「ProactiveScheduler共通化 第二段」の基盤となる PeriodicThrottle /
register_periodic()、および reminder_engine / life_coach_engine の
専用スレッド廃止・スケジューラ移管を検証する。

実行:
    venv/Scripts/python.exe -m unittest tests.test_scheduler_periodic
"""

import os
import tempfile
import threading
import unittest
from typing import List

import database
from proactive_scheduler import PeriodicThrottle, get_proactive_scheduler
from reminder_engine import ReminderEngine
from life_coach_engine import LifeCoachEngine


class PeriodicThrottleTest(unittest.TestCase):
    """PeriodicThrottle の間引きロジックテスト (実スレッド不使用)。"""

    def test_first_call_fires_immediately(self) -> None:
        """初回 tick で即実行する (起動直後の即監視を保証)。"""
        fired: List[float] = []
        throttle = PeriodicThrottle(fired.append, interval_sec=1.0)
        throttle(1000.0)
        self.assertEqual(fired, [1000.0])

    def test_fires_immediately_then_throttled_by_interval(self) -> None:
        """初回即実行後は interval 経過時のみ再発火する。"""
        fired: List[float] = []
        throttle = PeriodicThrottle(fired.append, interval_sec=1.0)
        throttle(1000.0)
        throttle(1000.5)
        self.assertEqual(fired, [1000.0])
        throttle(1001.0)
        self.assertEqual(fired, [1000.0, 1001.0])
        throttle(1001.9)
        self.assertEqual(fired, [1000.0, 1001.0])
        throttle(1002.0)
        self.assertEqual(fired, [1000.0, 1001.0, 1002.0])

    def test_negative_interval_treated_as_zero(self) -> None:
        """負の interval は 0 秒として扱い、毎 tick 発火する。"""
        fired: List[float] = []
        throttle = PeriodicThrottle(fired.append, interval_sec=-5.0)
        throttle(1.0)
        throttle(2.0)
        self.assertEqual(fired, [1.0, 2.0])


class SchedulerRegisterPeriodicTest(unittest.TestCase):
    """register_periodic() の登録・解除テスト。"""

    def setUp(self) -> None:
        """テスト間のシングルトン状態漏えいを防ぐため毎回停止。"""
        get_proactive_scheduler().stop()
        self.addCleanup(get_proactive_scheduler().stop)

    def test_register_periodic_returns_throttle_and_counts_plugin(self) -> None:
        """register_periodic() は PeriodicThrottle を返し、1プラグインとして数えられる。"""
        scheduler = get_proactive_scheduler()
        calls: List[float] = []
        throttle = scheduler.register_periodic(calls.append, interval_sec=30.0, name="probe")
        self.assertIsInstance(throttle, PeriodicThrottle)
        self.assertEqual(scheduler.plugin_count, 1)
        self.assertTrue(scheduler.unregister(throttle))
        self.assertEqual(scheduler.plugin_count, 0)

    def test_stop_clears_registered_plugins(self) -> None:
        """stop() はライフサイクル終端として登録済みプラグインもクリアする。

        停止済みスケジューラに幽霊プラグインが残留し、再 start() 時に
        意図せず発火する状態を構造的に防ぐ (テスト孤立性も向上)。
        """
        scheduler = get_proactive_scheduler()
        scheduler.register(lambda now: None, name="probe")
        self.assertEqual(scheduler.plugin_count, 1)
        scheduler.stop()
        self.assertEqual(scheduler.plugin_count, 0)


class ReminderEngineSchedulerMigrationTest(unittest.TestCase):
    """ReminderEngine の専用スレッド廃止・スケジューラ移管テスト。"""

    def setUp(self) -> None:
        """テスト用一時DBとスケジューラの初期化。"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_reminder_sched.db")
        database.init_db(self.db_path)
        get_proactive_scheduler().stop()
        self.addCleanup(get_proactive_scheduler().stop)
        self.addCleanup(self.temp_dir.cleanup)

    def test_start_registers_plugin_without_own_thread(self) -> None:
        """start() はスケジューラへ登録し、ReminderEngine 名の専用スレッドを生成しない。"""
        scheduler = get_proactive_scheduler()
        engine = ReminderEngine(db_path=self.db_path)
        engine.start()
        try:
            self.assertTrue(engine.is_running())
            self.assertGreaterEqual(scheduler.plugin_count, 1)
            thread_names = [t.name for t in threading.enumerate()]
            self.assertNotIn("ReminderEngine", thread_names)
        finally:
            engine.stop()
        self.assertFalse(engine.is_running())

    def test_stop_unregisters_plugin(self) -> None:
        """stop() はスケジューラから登録解除する。"""
        scheduler = get_proactive_scheduler()
        engine = ReminderEngine(db_path=self.db_path)
        engine.start()
        count_with_plugin = scheduler.plugin_count
        engine.stop()
        self.assertEqual(scheduler.plugin_count, count_with_plugin - 1)

    def test_stop_before_start_is_noop(self) -> None:
        """start() 前の stop() は例外を投げない (冪等)。"""
        engine = ReminderEngine(db_path=self.db_path)
        engine.stop()
        self.assertFalse(engine.is_running())


class LifeCoachEngineSchedulerMigrationTest(unittest.TestCase):
    """LifeCoachEngine の専用スレッド廃止・スケジューラ移管テスト。"""

    def setUp(self) -> None:
        """テスト用一時DBとスケジューラの初期化。"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_coach_sched.db")
        database.init_db(self.db_path)
        get_proactive_scheduler().stop()
        self.addCleanup(get_proactive_scheduler().stop)
        self.addCleanup(self.temp_dir.cleanup)

    def test_start_registers_plugin_without_own_thread(self) -> None:
        """start() はスケジューラへ登録し、LifeCoachEngine 名の専用スレッドを生成しない。"""
        engine = LifeCoachEngine(db_path=self.db_path)
        engine.start()
        try:
            self.assertTrue(engine.is_running())
            thread_names = [t.name for t in threading.enumerate()]
            self.assertNotIn("LifeCoachEngine", thread_names)
        finally:
            engine.stop()
        self.assertFalse(engine.is_running())


if __name__ == "__main__":
    unittest.main(verbosity=2)
