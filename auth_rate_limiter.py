#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - 認証レートリミッタ (auth_rate_limiter.py)

Sprint A 第2弾: レートリミット (方式b: 401認証失敗のIP別カウント→締め出し)
- 1分間 (60秒) 以内に同一送信元IPから 10回以上 401 認証失敗が発生した場合、
  そのIPを 5分間 (300秒) 締め出す (ATMロック方式)。
- 締め出し期間中のアクセスには 429 Too Many Requests と Retry-After を返す。
- メモリ上スライディングウィンドウ方式で動作し、DB負荷ゼロ・超軽量。
"""

import logging
import threading
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AuthRateLimiter:
    """送信元IPごとの認証失敗レートリミッタ (メモリ管理・スレッドセーフ)"""

    def __init__(
        self,
        max_failures: int = 10,
        window_seconds: float = 60.0,
        lockout_seconds: float = 300.0,
    ) -> None:
        """
        Args:
            max_failures: ロックアウトを発火させる失敗回数のしきい値 (デフォルト: 10)
            window_seconds: 失敗履歴を保持・監視する時間枠 (秒) (デフォルト: 60.0)
            lockout_seconds: 締め出し継続時間 (秒) (デフォルト: 300.0)
        """
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds

        self._lock = threading.Lock()
        # IPごとの失敗タイムスタンプリスト: {ip: [t1, t2, ...]}
        self._failure_timestamps: Dict[str, List[float]] = {}
        # IPごとのブロック解除予定時刻: {ip: expire_timestamp}
        self._blocked_until: Dict[str, float] = {}

    def is_blocked(self, ip: str, now: Optional[float] = None) -> Tuple[bool, int]:
        """指定されたIPが現在ロックアウト中かどうかを判定する。

        Args:
            ip: クライアントIPアドレス。
            now: テスト用の現在時刻 (未指定時は time.time())。

        Returns:
            (ブロック中か否か, 残り秒数)
        """
        current_time = now if now is not None else time.time()
        with self._lock:
            blocked_time = self._blocked_until.get(ip)
            if blocked_time is not None:
                if current_time < blocked_time:
                    remaining = int(blocked_time - current_time) + 1
                    return True, remaining
                else:
                    # 締め出し期限切れ -> ブロック解除
                    del self._blocked_until[ip]
                    if ip in self._failure_timestamps:
                        del self._failure_timestamps[ip]
            return False, 0

    def record_failure(self, ip: str, now: Optional[float] = None) -> Tuple[bool, int]:
        """認証失敗を記録し、しきい値到達時にロックアウトを発火させる。

        Args:
            ip: クライアントIPアドレス。
            now: テスト用の現在時刻 (未指定時は time.time())。

        Returns:
            (ロックアウトされたか否か, 締め出し秒数)
        """
        current_time = now if now is not None else time.time()
        with self._lock:
            # 既にブロック中なら残り時間を返す
            blocked_time = self._blocked_until.get(ip)
            if blocked_time is not None:
                if current_time < blocked_time:
                    remaining = int(blocked_time - current_time) + 1
                    return True, remaining
                else:
                    del self._blocked_until[ip]
                    if ip in self._failure_timestamps:
                        del self._failure_timestamps[ip]

            # 履歴リスト取得または新設
            timestamps = self._failure_timestamps.setdefault(ip, [])
            timestamps.append(current_time)

            # window_seconds より古い履歴をスライディング消去
            cutoff = current_time - self.window_seconds
            valid_timestamps = [t for t in timestamps if t >= cutoff]
            self._failure_timestamps[ip] = valid_timestamps

            # しきい値判定
            if len(valid_timestamps) >= self.max_failures:
                expire_time = current_time + self.lockout_seconds
                self._blocked_until[ip] = expire_time
                logger.warning(
                    f"🚨 [RateLimit] IP {ip} が認証失敗過多 ({len(valid_timestamps)}回) により "
                    f"{int(self.lockout_seconds)}秒間 ロックアウトされました。"
                )
                return True, int(self.lockout_seconds)

            return False, 0

    def reset(self) -> None:
        """テスト用: 全てのレートリミット状態をクリアする。"""
        with self._lock:
            self._failure_timestamps.clear()
            self._blocked_until.clear()


# グローバルシングルトン
_global_rate_limiter: Optional[AuthRateLimiter] = None
_rate_limiter_lock = threading.Lock()


def get_auth_rate_limiter() -> AuthRateLimiter:
    """AuthRateLimiter のグローバルシングルトンインスタンスを取得する。"""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        with _rate_limiter_lock:
            if _global_rate_limiter is None:
                _global_rate_limiter = AuthRateLimiter()
    return _global_rate_limiter
