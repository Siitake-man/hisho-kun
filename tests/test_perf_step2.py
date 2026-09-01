"""
ネオ秘書くん - 短期改善 Step 2 の単体テスト (tests/test_perf_step2.py)

SuggestionEngine のバックグラウンドキャッシュワーカーと
AgentWatcher の監視対象列挙キャッシュを検証する。
"""

import threading
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch


class SuggestBackgroundWorkerTest(unittest.TestCase):
    """SuggestionEngine バックグラウンドワーカーの振る舞いテスト。"""

    def _make_engine(self) -> Any:
        """テスト用に SuggestionEngine を生成する（設定ファイル非依存）。"""
        import suggest_engine

        with patch.object(suggest_engine.SuggestionEngine, "_start_background_worker", lambda self: None):
            engine = suggest_engine.SuggestionEngine()
        return engine

    def test_interval_constant(self) -> None:
        """再生成周期が30秒に設定されていること。"""
        import suggest_engine

        self.assertEqual(suggest_engine.SUGGEST_REFRESH_INTERVAL_SEC, 30)

    def test_get_cached_returns_initially_empty(self) -> None:
        """初回生成前のキャッシュは空リストであること。"""
        engine = self._make_engine()
        self.assertEqual(engine.get_cached_suggestions(), [])

    def test_worker_updates_cache(self) -> None:
        """ワーカー生成結果がキャッシュへ反映されること。"""
        engine = self._make_engine()
        dummy: List[Dict[str, Any]] = [{"id": "test_1", "title": "ダミー"}]
        with patch.object(engine, "generate_suggestions", return_value=dummy):
            engine._refresh_cache_once()
        self.assertEqual(engine.get_cached_suggestions(), dummy)

    def test_refresh_cache_once_survives_exception(self) -> None:
        """生成中に例外が起きてもワーカーが死なずキャッシュが維持されること。"""
        engine = self._make_engine()
        seed: List[Dict[str, Any]] = [{"id": "seed"}]
        with patch.object(engine, "generate_suggestions", return_value=seed):
            engine._refresh_cache_once()

        def _boom() -> List[Dict[str, Any]]:
            raise RuntimeError("LLM timeout")

        with patch.object(engine, "generate_suggestions", side_effect=_boom):
            engine._refresh_cache_once()  # 例外が外へ漏れない
        self.assertEqual(engine.get_cached_suggestions(), seed)

    def test_start_registers_plugin_without_own_thread(self) -> None:
        """_start_background_worker() は専用スレッドを生成せずスケジューラへ登録する。"""
        import suggest_engine
        from proactive_scheduler import get_proactive_scheduler

        get_proactive_scheduler().stop()
        scheduler = get_proactive_scheduler()
        baseline = scheduler.plugin_count
        with patch.object(suggest_engine.SuggestionEngine, "generate_suggestions", return_value=[]):
            engine = suggest_engine.SuggestionEngine()
            try:
                self.assertIsNotNone(engine._refresh_plugin)
                self.assertEqual(scheduler.plugin_count, baseline + 1)
                thread_names = [t.name for t in threading.enumerate()]
                self.assertNotIn("SuggestBgWorker", thread_names)
            finally:
                engine.shutdown_worker()
        self.assertIsNone(engine._refresh_plugin)
        self.assertEqual(scheduler.plugin_count, baseline)

    def test_force_refresh_triggers_immediate_tick_refresh(self) -> None:
        """request_refresh() 後の tick は interval 未満でも即座に再生成する。"""
        engine = self._make_engine()
        calls: List[int] = []
        with patch.object(engine, "generate_suggestions", side_effect=lambda: calls.append(1) or []):
            engine._last_refresh_at = 1000.0
            engine.request_refresh()
            engine._on_scheduler_tick(1005.0)
        self.assertEqual(len(calls), 1)
        self.assertFalse(engine._force_refresh.is_set())

    def test_tick_refreshes_only_after_interval(self) -> None:
        """強制更新が無い場合、tick は interval (30秒) 経過後にのみ再生成する。"""
        engine = self._make_engine()
        calls: List[int] = []
        with patch.object(engine, "generate_suggestions", side_effect=lambda: calls.append(1) or []):
            engine._last_refresh_at = 1000.0
            engine._on_scheduler_tick(1010.0)
            self.assertEqual(len(calls), 0)
            engine._on_scheduler_tick(1031.0)
        self.assertEqual(len(calls), 1)

    def test_shutdown_worker_unregisters_plugin(self) -> None:
        """shutdown_worker() はスケジューラから登録解除する (冪等)。"""
        import suggest_engine
        from proactive_scheduler import get_proactive_scheduler

        get_proactive_scheduler().stop()
        scheduler = get_proactive_scheduler()
        with patch.object(suggest_engine.SuggestionEngine, "generate_suggestions", return_value=[]):
            engine = suggest_engine.SuggestionEngine()
            self.assertIsNotNone(engine._refresh_plugin)
            engine.shutdown_worker()
            engine.shutdown_worker()  # 二重呼び出しでも例外にしない
        self.assertIsNone(engine._refresh_plugin)

    def test_request_refresh_is_non_blocking(self) -> None:
        """request_refresh() がブロックせずフラグを立てること。"""
        engine = self._make_engine()
        start = time.time()
        engine.request_refresh()
        self.assertLess(time.time() - start, 0.5)
        self.assertTrue(engine._force_refresh.is_set())


class AgentWatcherTargetCacheTest(unittest.TestCase):
    """AgentWatcher 監視対象列挙キャッシュの振る舞いテスト。"""

    def _make_watcher(self) -> Any:
        """コールバック無しの AgentWatcher を生成する。"""
        import agent_watcher

        return agent_watcher.AgentWatcher()

    def test_first_call_scans(self) -> None:
        """初回呼び出しで実際に列挙が実行されること。"""
        watcher = self._make_watcher()
        with patch.object(watcher, "get_watch_targets", return_value=[Path("a.log")]) as m:
            result = watcher._get_watch_targets_cached()
        m.assert_called_once()
        self.assertEqual(result, [Path("a.log")])

    def test_second_call_uses_cache(self) -> None:
        """30秒以内の再呼び出しでは列挙が再実行されないこと。"""
        watcher = self._make_watcher()
        with patch.object(watcher, "get_watch_targets", return_value=[Path("a.log")]) as m:
            watcher._get_watch_targets_cached()
            watcher._get_watch_targets_cached()
            watcher._get_watch_targets_cached()
        self.assertEqual(m.call_count, 1)

    def test_rescan_after_interval(self) -> None:
        """列挙間隔経過後は再列挙が実行されること。"""
        watcher = self._make_watcher()
        watcher._target_scan_interval = 0.0  # 常に再列挙扱い
        count = {"n": 0}

        def _targets() -> List[Path]:
            count["n"] += 1
            return []

        with patch.object(watcher, "get_watch_targets", side_effect=_targets):
            watcher._get_watch_targets_cached()
            watcher._get_watch_targets_cached()
        self.assertEqual(count["n"], 2)

    def test_scan_failure_keeps_previous_cache(self) -> None:
        """再列挙が失敗しても前回キャッシュが維持されること。"""
        watcher = self._make_watcher()
        with patch.object(watcher, "get_watch_targets", return_value=[Path("keep.log")]):
            watcher._get_watch_targets_cached()

        def _boom() -> List[Path]:
            raise OSError("disk error")

        with patch.object(watcher, "get_watch_targets", side_effect=_boom):
            result = watcher._get_watch_targets_cached()
        self.assertEqual(result, [Path("keep.log")])


if __name__ == "__main__":
    unittest.main()
