#!/usr/bin/env python3
"""
ネオ秘書くん - 自律通知スケジューラーの単体テスト (test_proactive_scheduler.py)

P2「スケジューラー共通化」で新設した ProactiveScheduler の振る舞いを検証する。
実スレッドを使用するため、短い周期 (0.05秒) + イベント待ちで検証する。

実行:
    venv\\Scripts\\python.exe -m unittest tests.test_proactive_scheduler
"""

import threading
import time
import unittest

from proactive_scheduler import ProactiveScheduler, get_proactive_scheduler


class TestProactiveScheduler(unittest.TestCase):
    """ProactiveScheduler の振る舞いテスト。"""

    def setUp(self) -> None:
        # テスト間のシングルトン状態漏えいを防ぐため毎回停止
        get_proactive_scheduler().stop()
        self.addCleanup(get_proactive_scheduler().stop)

    def test_registered_plugin_called_on_tick(self) -> None:
        """登録したプラグインが tick 周期で呼び出される。"""
        scheduler = ProactiveScheduler(tick_interval_sec=0.05)
        calls = []
        scheduler.register(lambda now: calls.append(now), name="probe")
        scheduler.start()
        deadline = time.time() + 2.0
        while len(calls) == 0 and time.time() < deadline:
            time.sleep(0.01)
        self.assertGreaterEqual(len(calls), 1, "プラグインが1度も呼ばれていません")
        scheduler.stop()

    def test_plugin_exception_does_not_kill_loop(self) -> None:
        """プラグインが例外を投げてもスケジューラは継続する。"""
        scheduler = ProactiveScheduler(tick_interval_sec=0.05)

        def bad_plugin(now: float) -> None:
            raise RuntimeError("boom")

        calls = []
        scheduler.register(bad_plugin, name="bad")
        scheduler.register(lambda now: calls.append(now), name="good")
        scheduler.start()
        deadline = time.time() + 2.0
        while len(calls) == 0 and time.time() < deadline:
            time.sleep(0.01)
        self.assertGreaterEqual(len(calls), 1, "例外後にスケジューラが停止しています")
        scheduler.stop()

    def test_unregister_removes_plugin(self) -> None:
        """unregister() でプラグインが解除され、以後呼ばれない。"""
        scheduler = ProactiveScheduler(tick_interval_sec=0.05)
        calls = []
        plugin = lambda now: calls.append(now)  # noqa: E731
        scheduler.register(plugin, name="probe")
        self.assertTrue(scheduler.unregister(plugin))
        self.assertFalse(scheduler.unregister(plugin))  # 二重解除は False
        self.assertEqual(scheduler.plugin_count, 0)

    def test_stop_terminates_thread(self) -> None:
        """stop() 後にスレッドが終了し is_running が False になる。"""
        scheduler = ProactiveScheduler(tick_interval_sec=0.05)
        scheduler.start()
        self.assertTrue(scheduler.is_running)
        scheduler.stop(timeout_sec=2.0)
        self.assertFalse(scheduler.is_running)

    def test_singleton_returns_same_instance(self) -> None:
        """get_proactive_scheduler() は同一インスタンスを返す。"""
        self.assertIs(get_proactive_scheduler(), get_proactive_scheduler())

    def test_register_is_thread_safe(self) -> None:
        """並行 register しても全プラグインが登録される。"""
        scheduler = ProactiveScheduler(tick_interval_sec=0.05)
        errors = []

        def _register_many(n: int) -> None:
            try:
                for _ in range(n):
                    scheduler.register(lambda now: None, name="x")
            except Exception as e:  # pragma: no cover - 失敗時のみ
                errors.append(e)

        threads = [threading.Thread(target=_register_many, args=(50,)) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(scheduler.plugin_count, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)