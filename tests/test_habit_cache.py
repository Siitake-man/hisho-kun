#!/usr/bin/env python3
"""
ネオ秘書くん - 習慣データ＆70日ヒートマップ 30秒TTLキャッシュのテスト (tests/test_habit_cache.py)
"""

import json
import logging
import sys
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
import life_dreamer
import local_sync_server
import suggest_engine

logging.getLogger("local_sync_server").setLevel(logging.CRITICAL)


class TestHabitCache(unittest.TestCase):
    """習慣データおよび70日ヒートマップの30秒TTLキャッシュの動作検証"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.mock_get_tasks = MagicMock(return_value=[])
        cls.mock_get_upcoming_events = MagicMock(return_value=[])
        cls.mock_get_all_calendar_sources = MagicMock(return_value=[])
        cls.mock_get_habits = MagicMock(return_value=[])
        cls.mock_get_heatmap = MagicMock(return_value=[])

        cls._patchers = [
            patch.object(local_sync_server.database, "get_tasks", cls.mock_get_tasks),
            patch.object(local_sync_server.database, "get_upcoming_events", cls.mock_get_upcoming_events),
            patch.object(local_sync_server.database, "get_all_calendar_sources", cls.mock_get_all_calendar_sources),
            patch.object(local_sync_server.database, "get_habits_with_status", cls.mock_get_habits),
            patch.object(local_sync_server.database, "get_habit_heatmap_data", cls.mock_get_heatmap),
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
        cls._patchers.append(patch.object(
            life_dreamer, "get_life_dreamer", MagicMock(return_value=life_dreamer_mock)
        ))

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
