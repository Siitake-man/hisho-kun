#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - 認証レートリミッタ テスト (tests/test_auth_rate_limiter.py)

Sprint A 第2弾: レートリミット (401失敗のIP別カウント→5分間締め出し→429+Retry-After)
TDD Red テスト。
"""

import sys
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from auth_rate_limiter import AuthRateLimiter, get_auth_rate_limiter


class TestAuthRateLimiterUnit(unittest.TestCase):
    """AuthRateLimiter の単体ロジックテスト"""

    def setUp(self):
        self.limiter = AuthRateLimiter(
            max_failures=10,
            window_seconds=60.0,
            lockout_seconds=300.0,
        )

    def test_initial_state_not_blocked(self):
        """初期状態ではどのIPもブロックされていないこと"""
        blocked, retry_after = self.limiter.is_blocked("192.168.1.100")
        self.assertFalse(blocked)
        self.assertEqual(retry_after, 0)

    def test_nine_failures_not_blocked(self):
        """9回以内の認証失敗ではブロックされないこと (しきい値10)"""
        for _ in range(9):
            blocked, retry_after = self.limiter.record_failure("192.168.1.100")
            self.assertFalse(blocked)
            self.assertEqual(retry_after, 0)

        blocked, retry_after = self.limiter.is_blocked("192.168.1.100")
        self.assertFalse(blocked)
        self.assertEqual(retry_after, 0)

    def test_tenth_failure_triggers_lockout(self):
        """1分以内に10回目の失敗で5分間 (300秒) ロックアウトされること"""
        for _ in range(9):
            self.limiter.record_failure("192.168.1.100")

        # 10回目
        blocked, retry_after = self.limiter.record_failure("192.168.1.100")
        self.assertTrue(blocked)
        self.assertGreaterEqual(retry_after, 298)
        self.assertLessEqual(retry_after, 300)

        # 直後の is_blocked もブロック中を返すこと
        b, r = self.limiter.is_blocked("192.168.1.100")
        self.assertTrue(b)
        self.assertGreaterEqual(r, 298)

    def test_different_ips_tracked_independently(self):
        """異なるIPアドレスは独立してカウントされること"""
        for _ in range(10):
            self.limiter.record_failure("192.168.1.100")

        # IP 100 はブロック中
        self.assertTrue(self.limiter.is_blocked("192.168.1.100")[0])

        # IP 101 はブロックされていない
        self.assertFalse(self.limiter.is_blocked("192.168.1.101")[0])

    def test_old_failures_expire_from_window(self):
        """window_seconds (60秒) を超過した古い失敗履歴は消去されること"""
        now = time.time()
        # 過去 (70秒前) に9回失敗した履歴を模擬
        old_time = now - 70.0
        self.limiter.record_failure("192.168.1.100", now=old_time)
        for _ in range(8):
            self.limiter.record_failure("192.168.1.100", now=old_time)

        # 現在時刻で1回失敗しても、合計10回にはならずブロックされない
        blocked, _ = self.limiter.record_failure("192.168.1.100", now=now)
        self.assertFalse(blocked)

    def test_lockout_expires_after_duration(self):
        """lockout_seconds が経過した後は自動的にブロックが解除されること"""
        now = time.time()
        for _ in range(10):
            self.limiter.record_failure("192.168.1.100", now=now)

        self.assertTrue(self.limiter.is_blocked("192.168.1.100", now=now)[0])

        # 301秒後
        after_lockout = now + 301.0
        blocked, retry_after = self.limiter.is_blocked("192.168.1.100", now=after_lockout)
        self.assertFalse(blocked)
        self.assertEqual(retry_after, 0)

    def test_reset_clears_all(self):
        """reset() で全記録が消去されること"""
        for _ in range(10):
            self.limiter.record_failure("192.168.1.100")
        self.assertTrue(self.limiter.is_blocked("192.168.1.100")[0])

        self.limiter.reset()
        self.assertFalse(self.limiter.is_blocked("192.168.1.100")[0])


class TestAuthRateLimiterIntegration(unittest.TestCase):
    """HTTP サーバーを介した 429 Too Many Requests 結合テスト"""

    @classmethod
    def setUpClass(cls):
        import local_sync_server
        import threading
        from http.server import ThreadingHTTPServer

        cls.limiter = get_auth_rate_limiter()
        cls.limiter.reset()

        # エフェメラルポート (port=0) でサーバー起動
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), local_sync_server.DeskPetSyncHandler)
        cls.port = cls.httpd.server_port
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=3)
        cls.limiter.reset()

    def setUp(self):
        self.limiter.reset()

    def test_ten_failures_then_eleventh_returns_429(self):
        """不正トークンで10回認証失敗すると、11回目に 429 Too Many Requests が返ること"""
        import json
        import urllib.error
        import urllib.request

        url = f"http://127.0.0.1:{self.port}/api/action"
        data = json.dumps({"action": "ping_test"}).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer invalid_token_xyz",
        }

        # 1〜10回目: 401 Unauthorized
        for i in range(10):
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req) as resp:
                    self.fail(f"{i+1}回目は 401 になるべき")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 401, f"{i+1}回目の失敗ステータス")

        # 11回目: 429 Too Many Requests + Retry-After ヘッダー
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                self.fail("11回目は 429 になるべき")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 429, "11回目は 429 ロックアウト")
            retry_after = e.headers.get("Retry-After")
            self.assertIsNotNone(retry_after)
            self.assertGreater(int(retry_after), 0)
            body = json.loads(e.read().decode("utf-8"))
            self.assertEqual(body.get("status"), "error")
            self.assertIn("Too many failed authentication attempts", body.get("message"))


if __name__ == "__main__":
    unittest.main()

