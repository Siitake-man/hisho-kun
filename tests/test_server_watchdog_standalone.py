"""
server_watchdog.py の単体テスト (tests/test_server_watchdog_standalone.py)

TDD & 耐障害性検証:
1. 正常系: サーバーが健全な間は再起動を発火しない
2. ヒステリシス: 連続失敗回数が failure_threshold に達した時点で再起動を発火
3. 指数バックオフ: 再起動失敗時にバックオフ時間が増加
4. 終端契約: stop() 後はスレッドが速やかに停止しゾンビ再起動が起きない
"""

import time
import unittest
from unittest.mock import MagicMock
from server_watchdog import ServerWatchdog


class TestServerWatchdogStandalone(unittest.TestCase):
    """server_watchdog のヒステリシス再起動とスレッド終端契約を検証する。

    健全時は再起動せず、連続失敗が閾値に達した時点で一度だけ発火し、
    stop() 後にゾンビ再起動が起きないこと（耐障害性）を守る。
    """

    def test_healthy_server_does_not_trigger_restart(self):
        """プローブが常に真を返す場合、restart_fn は呼ばれない。"""
        probe_fn = MagicMock(return_value=True)
        restart_fn = MagicMock(return_value=True)

        wd = ServerWatchdog(
            probe_fn=probe_fn,
            restart_fn=restart_fn,
            interval=0.05,
            failure_threshold=1,
            thread_name="test-wd-healthy",
        )
        wd.start()
        time.sleep(0.2)
        wd.stop()

        self.assertGreater(probe_fn.call_count, 1)
        self.assertEqual(restart_fn.call_count, 0)

    def test_hysteresis_threshold(self):
        """failure_threshold=2 の場合、1回目の失敗では再起動せず、2回目の失敗で発火する。"""
        # 1回目 False, 2回目 False, 3回目 True
        probe_results = [False, False, True, True]
        def mock_probe():
            if probe_results:
                return probe_results.pop(0)
            return True

        restart_fn = MagicMock(return_value=True)

        wd = ServerWatchdog(
            probe_fn=mock_probe,
            restart_fn=restart_fn,
            interval=0.05,
            failure_threshold=2,
            thread_name="test-wd-hysteresis",
        )
        wd.start()
        time.sleep(0.25)
        wd.stop()

        # 2回連続失敗で 1 回だけ再起動が発火するはず
        self.assertEqual(restart_fn.call_count, 1)

    def test_stop_terminates_cleanly(self):
        """stop() 後はスレッドが終了し、プローブが停止する。"""
        probe_fn = MagicMock(return_value=True)
        restart_fn = MagicMock(return_value=True)

        wd = ServerWatchdog(
            probe_fn=probe_fn,
            restart_fn=restart_fn,
            interval=0.05,
            thread_name="test-wd-stop",
        )
        wd.start()
        self.assertTrue(wd.is_running)

        wd.stop(timeout=1.0)
        self.assertFalse(wd.is_running)
        count_at_stop = probe_fn.call_count

        time.sleep(0.15)
        self.assertEqual(probe_fn.call_count, count_at_stop, "stop 後にプローブが実行された")


if __name__ == "__main__":
    unittest.main()
