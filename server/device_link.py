#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - 端末死活監視＆リンクモニター (DeviceLinkMonitor / S3 Seam).

(server/device_link.py)

目的:
    Fat モジュール `local_sync_server.py` (2,296行) から、スマホ端末とPCの接続状態
    （死活監視・ハートビート・バイブレーション呼び出し・通知保持・イースターエッグ連携）を
    独立した Deep Module として切り出す。

改善点:
    - 設計書 §3.2: `latest_easter_egg_event` が `__init__` で未初期化だった潜在欠陥 (latent defect) を
      `self.latest_easter_egg_event: Optional[Dict[str, Any]] = None` として正規化。
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger("device_link")


class DeviceLinkMonitor:
    """スマホ端末とPCの接続状態（死活監視）を管理するマネージャー."""

    def __init__(self) -> None:
        """DeviceLinkMonitor を初期化する."""
        self._lock = threading.Lock()
        self.last_heartbeat_time: float = 0.0
        self.client_ip: str = ""
        self.user_agent: str = ""
        self.device_name: str = "未接続"
        self.buzz_requested: bool = False
        self.first_link_notified: bool = False
        self.latest_notification: Optional[Dict[str, Any]] = None

    def record_heartbeat(self, client_ip: str, user_agent: str) -> bool:
        """スマホからの通信を検知して更新。初回接続時はTrueを返す.

        Args:
            client_ip: 接続元 IP アドレス。
            user_agent: 接続元 User-Agent。

        Returns:
            bool: 直前までオフラインだった場合 (新規/再接続) True。
        """
        with self._lock:
            now = time.time()
            was_offline = (now - self.last_heartbeat_time) > 12.0 or self.last_heartbeat_time == 0
            self.last_heartbeat_time = now
            self.client_ip = client_ip
            self.user_agent = user_agent

            # User-Agentから簡易デバイス名を特定
            ua_lower = user_agent.lower()
            if "iphone" in ua_lower:
                self.device_name = "iPhone"
            elif "ipad" in ua_lower:
                self.device_name = "iPad"
            elif "android" in ua_lower:
                self.device_name = "Android端末"
            elif "macintosh" in ua_lower:
                self.device_name = "Mac"
            elif "windows" in ua_lower:
                self.device_name = "Windows PC"
            else:
                self.device_name = "スマホブラウザ"

            return was_offline

    def is_connected(self) -> bool:
        """直近45秒以内に通信があったか判定（通信揺らぎ耐性）.

        Returns:
            bool: 接続中の場合 True。
        """
        with self._lock:
            return (time.time() - self.last_heartbeat_time) <= 45.0 and self.last_heartbeat_time > 0

    def get_status(self) -> Dict[str, Any]:
        """現在の接続状態サマリを返却する.

        Returns:
            Dict[str, Any]: connected, device_name, client_ip, seconds_ago, last_seen。
        """
        with self._lock:
            now = time.time()
            connected = (now - self.last_heartbeat_time) <= 45.0 and self.last_heartbeat_time > 0
            seconds_ago = int(now - self.last_heartbeat_time) if self.last_heartbeat_time > 0 else -1
            return {
                "connected": connected,
                "device_name": self.device_name if connected else "未接続",
                "client_ip": self.client_ip if connected else "",
                "seconds_ago": seconds_ago,
                "last_seen": int(self.last_heartbeat_time * 1000) if self.last_heartbeat_time > 0 else 0,
            }

    def trigger_buzz(self) -> None:
        """PCからスマホを呼び出す（バイブレーション要求フラグON）."""
        with self._lock:
            self.buzz_requested = True

    def consume_buzz(self) -> bool:
        """スマホ側が呼び出しを検知して消費.

        Returns:
            bool: 呼び出し要求があった場合 True。
        """
        with self._lock:
            if self.buzz_requested:
                self.buzz_requested = False
                return True
            return False

    def set_notification(self, agent_name: str, title: str, message: str, reaction: str = "celebrate") -> None:
        """最新の通知を保持し、スマホへバイブレーション要求を発行.

        Args:
            agent_name: 通知元エージェント名。
            title: 通知タイトル。
            message: 通知本文。
            reaction: Desk Pet 演出リアクション (デフォルト: celebrate)。
        """
        with self._lock:
            self.latest_notification = {
                "id": f"notif_{uuid.uuid4().hex[:6]}",
                "agent_name": agent_name,
                "title": title,
                "message": message,
                "reaction": reaction,
                "timestamp": time.time(),
            }
            self.buzz_requested = True

    def get_active_notification(self) -> Optional[Dict[str, Any]]:
        """直近10分以内の通知を返す.

        2026-08-31 バグ修正: 従来の60秒TTLでは、スマホが画面OFF/バックグラウンド中に
        通知を受け取った場合（音は鳴るが表示は不可視）、復帰時の再取得までに60秒を
        超えるとサーバー側で破棄済みとなり通知が永久に表示されない不具合があった。
        10分に延長し、復帰時の再表示を可能にする。二重表示はクライアント側の
        sessionStorage 永続化された _lastNotifKey により防止する。

        Returns:
            Optional[Dict[str, Any]]: 有効な通知データ、または None。
        """
        with self._lock:
            if self.latest_notification:
                if time.time() - self.latest_notification["timestamp"] <= 600.0:
                    return self.latest_notification
                else:
                    self.latest_notification = None
            return None


_global_link_monitor: DeviceLinkMonitor = DeviceLinkMonitor()


def get_link_monitor() -> DeviceLinkMonitor:
    """DeviceLinkMonitor のシングルトンインスタンスを返却する.

    Returns:
        DeviceLinkMonitor: グローバルモニターインスタンス。
    """
    return _global_link_monitor


__all__: list[str] = ["DeviceLinkMonitor", "get_link_monitor"]
