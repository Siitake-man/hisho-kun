#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - サーバー状態キャッシュマネージャー (server/status_cache.py).

Fat モジュール `local_sync_server.py` から、/api/status で使用される
6大インメモリキャッシュ変数（DB負荷軽減用 2秒TTLキャッシュ 3変数 ＋
習慣・ヒートマップ 30秒TTLキャッシュ 3変数）およびキャッシュ無効化ロジックを
スレッドセーフな Deep Module として切り出します。

収容責務:
    - DBデータキャッシュ (2秒TTL):
        - _last_db_cache_time: float
        - _cached_tasks_data: list[dict]
        - _cached_events_data: list[dict]
    - 習慣＆ヒートマップキャッシュ (30秒TTL):
        - _last_habit_cache_time: float
        - _cached_habits_data: list[dict]
        - _cached_heatmap_data: list[dict]
    - スレッドセーフな無効化・取得・更新 API
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class StatusCacheManager:
    """/api/status 用のインメモリキャッシュを安全に管理するスレッドセーフマネージャー."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # DB キャッシュ (2秒TTL)
        self._last_db_cache_time: float = 0.0
        self._cached_tasks_data: List[Dict[str, Any]] = []
        self._cached_events_data: List[Dict[str, Any]] = []
        # 習慣＆草ヒートマップキャッシュ (30秒TTL)
        self._last_habit_cache_time: float = 0.0
        self._cached_habits_data: List[Dict[str, Any]] = []
        self._cached_heatmap_data: List[Dict[str, Any]] = []

    def invalidate_habit_cache(self) -> None:
        """習慣データおよび70日ヒートマップのインメモリTTLキャッシュを無効化する。"""
        with self._lock:
            self._last_habit_cache_time = 0.0
        logger.debug("🔄 [StatusCache] 習慣キャッシュを無効化しました")

    def invalidate_db_cache(self) -> None:
        """タスクおよび予定データのインメモリTTLキャッシュを無効化する。"""
        with self._lock:
            self._last_db_cache_time = 0.0
        logger.debug("🔄 [StatusCache] DBキャッシュを無効化しました")

    def get_db_cache(self, now: Optional[float] = None, ttl: float = 2.0) -> Tuple[bool, List[Dict[str, Any]], List[Dict[str, Any]]]:
        """DBキャッシュの有効性と現在のデータを取得する。

        Args:
            now: 現在時刻 (time.time())。省略時は現在時刻を取得。
            ttl: キャッシュの有効期間 (秒)。デフォルトは 2.0 秒。

        Returns:
            Tuple[bool, List[dict], List[dict]]:
                (is_valid, cached_tasks, cached_events)
                is_valid が True の場合はキャッシュ利用可能、False の場合は再フェッチが必要。
        """
        if now is None:
            now = time.time()
        with self._lock:
            is_valid = (now - self._last_db_cache_time) <= ttl and bool(self._cached_tasks_data or self._cached_events_data)
            return is_valid, list(self._cached_tasks_data), list(self._cached_events_data)

    def set_db_cache(
        self,
        tasks: List[Dict[str, Any]],
        events: List[Dict[str, Any]],
        timestamp: Optional[float] = None,
    ) -> None:
        """DBキャッシュを更新する。

        Args:
            tasks: 整形済みタスク一覧。
            events: 整形済み予定一覧。
            timestamp: 更新時刻。省略時は現在時刻。
        """
        if timestamp is None:
            timestamp = time.time()
        with self._lock:
            self._cached_tasks_data = list(tasks)
            self._cached_events_data = list(events)
            self._last_db_cache_time = timestamp

    def get_habit_cache(self, now: Optional[float] = None, ttl: float = 30.0) -> Tuple[bool, List[Dict[str, Any]], List[Dict[str, Any]]]:
        """習慣キャッシュの有効性と現在のデータを取得する。

        Args:
            now: 現在時刻 (time.time())。省略時は現在時刻を取得。
            ttl: キャッシュの有効期間 (秒)。デフォルトは 30.0 秒。

        Returns:
            Tuple[bool, List[dict], List[dict]]:
                (is_valid, cached_habits, cached_heatmap)
                is_valid が True の場合はキャッシュ利用可能、False の場合は再フェッチが必要。
        """
        if now is None:
            now = time.time()
        with self._lock:
            is_valid = (now - self._last_habit_cache_time) <= ttl and bool(self._cached_habits_data or self._cached_heatmap_data)
            return is_valid, list(self._cached_habits_data), list(self._cached_heatmap_data)

    def set_habit_cache(
        self,
        habits: List[Dict[str, Any]],
        heatmap: List[Dict[str, Any]],
        timestamp: Optional[float] = None,
    ) -> None:
        """習慣＆ヒートマップキャッシュを更新する。

        Args:
            habits: 整形済み習慣一覧。
            heatmap: 整形済みヒートマップデータ。
            timestamp: 更新時刻。省略時は現在時刻。
        """
        if timestamp is None:
            timestamp = time.time()
        with self._lock:
            self._cached_habits_data = list(habits)
            self._cached_heatmap_data = list(heatmap)
            self._last_habit_cache_time = timestamp


# シングルトンインスタンス
_GLOBAL_STATUS_CACHE: Optional[StatusCacheManager] = None
_CACHE_LOCK = threading.Lock()


def get_status_cache() -> StatusCacheManager:
    """StatusCacheManager のグローバルシングルトンインスタンスを取得する。"""
    global _GLOBAL_STATUS_CACHE
    if _GLOBAL_STATUS_CACHE is None:
        with _CACHE_LOCK:
            if _GLOBAL_STATUS_CACHE is None:
                _GLOBAL_STATUS_CACHE = StatusCacheManager()
    return _GLOBAL_STATUS_CACHE


def invalidate_habit_cache() -> None:
    """習慣データおよび70日ヒートマップのインメモリTTLキャッシュを無効化する。

    Facade 再エクスポート互換用公開関数 (local_sync_server.py / api_tasks / calendar_window)。
    """
    get_status_cache().invalidate_habit_cache()


def invalidate_db_cache() -> None:
    """タスクおよび予定データのインメモリTTLキャッシュを無効化する。"""
    get_status_cache().invalidate_db_cache()
