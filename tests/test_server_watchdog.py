#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - 同期サーバー 自己治癒watchdog テスト (tests/test_server_watchdog.py)

2026-09-02 ディープ監査の残存リスク「Windows スリープ復帰時のソケット再バインド
自動復帰テストが未整備」への対策 (Block 2)。LocalSyncServer に実装する
自己治癒watchdog (周期ヘルスプローブ → 死亡検出 → 同ポート再バインド) を検証する:

  1. rebind 前提: QuietThreadingHTTPServer.allow_reuse_address が有効 (TIME_WAIT再バインド)
  2. 自己治癒: serve_forever スレッドの死亡を検出し、同ポートで自動再起動する
  3. 誤検知防止: 健全なサーバーを再起動しない (httpd インスタンス不変)
  4. 終端契約: stop() 後はwatchdogも停止し、ゾンビ再起動が起きない

設計上の注意:
- ポート0 (エフェメラル) で起動し、_bound_port に解決されたポートを記録する。
  watchdog 再起動時は解決済みポートへ再バインドする (ポータル変更を防止)。
- life_dreamer (start() 内で起動される重い依存) は sys.modules パッチで隔離する。
"""

import logging
import socket
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ※ 本ファイルは tests/ 配下にあるため、プロジェクトルートを import パスに追加
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import local_sync_server

# テスト実行中にサーバーロガーがコンソールを荒らすのを防止
logging.getLogger("local_sync_server").setLevel(logging.CRITICAL)


def _fake_life_dreamer_module() -> MagicMock:
    """start() 内で import される life_dreamer の隔離用フェイクモジュール。"""
    fake = MagicMock()
    fake.get_life_dreamer.return_value = MagicMock()
    return fake


class TestServerWatchdog(unittest.TestCase):
    """LocalSyncServer 自己治癒watchdogの振る舞いを検証する"""

    WATCHDOG_INTERVAL = 0.2

    def setUp(self) -> None:
        """エフェメラルポートで LocalSyncServer を起動する (life_dreamer 隔離)。"""
        self.server = local_sync_server.LocalSyncServer(port=0)
        self.server.watchdog_interval = self.WATCHDOG_INTERVAL
        with patch.dict(sys.modules, {"life_dreamer": _fake_life_dreamer_module()}):
            self.server.start(gui=None)
        self.assertTrue(
            self._wait_until(self.server.is_healthy, timeout=5.0),
            "テスト用同期サーバーが起動しませんでした",
        )

    def tearDown(self) -> None:
        """サーバーとwatchdogを確実に停止する。"""
        self.server.stop()

    @staticmethod
    def _wait_until(predicate, timeout: float) -> bool:
        """predicate が真になるまで待機する (タイムアウト時は False)。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return True
            time.sleep(0.05)
        return predicate()

    @staticmethod
    def _port_open(port) -> bool:
        """指定ポートへのループバック接続可否を返す。"""
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            return False

    # ==========================================================================
    # 1. rebind 前提
    # ==========================================================================
    def test_allow_reuse_address_is_enabled(self):
        """QuietThreadingHTTPServer は allow_reuse_address 有効 (スリープ復帰の再バインド前提)"""
        self.assertTrue(
            local_sync_server.QuietThreadingHTTPServer.allow_reuse_address,
            "TIME_WAIT からの再バインドのため allow_reuse_address が必要",
        )

    # ==========================================================================
    # 2. 自己治癒
    # ==========================================================================
    def test_watchdog_restarts_dead_server_thread(self):
        """serve_forever スレッドの死亡を検出し、同ポートで自動再起動する"""
        old_httpd = self.server.httpd
        old_port = self.server._bound_port

        # スリープ復帰時のソケット死を模擬: サーバースレッドを強制停止する
        old_httpd.shutdown()
        old_httpd.server_close()

        restarted = self._wait_until(
            lambda: self.server.httpd is not old_httpd and self.server.is_healthy(),
            timeout=5.0,
        )
        self.assertTrue(restarted, "watchdog がサーバーを再起動しませんでした")
        self.assertEqual(
            self.server._bound_port, old_port,
            "再起動時は解決済みポートへ再バインドすること (ポート変更防止)",
        )

    # ==========================================================================
    # 3. 誤検知防止
    # ==========================================================================
    def test_watchdog_does_not_restart_healthy_server(self):
        """健全なサーバーは再起動しない (httpd インスタンス不変)"""
        stable_httpd = self.server.httpd
        time.sleep(self.WATCHDOG_INTERVAL * 4 + 0.2)
        self.assertIs(self.server.httpd, stable_httpd, "健全なサーバーが再起動された")
        self.assertTrue(self.server.is_healthy())

    # ==========================================================================
    # 4. 終端契約
    # ==========================================================================
    def test_stop_disables_watchdog(self):
        """stop() 後はwatchdogも停止し、ゾンビ再起動が起きない"""
        port = self.server._bound_port
        self.server.stop()
        time.sleep(self.WATCHDOG_INTERVAL * 4 + 0.3)
        self.assertFalse(self.server.thread.is_alive(), "stop 後にスレッドが生存している")
        self.assertFalse(self._port_open(port), "stop 後にゾンビ再起動でポートが再オープンされた")


if __name__ == "__main__":
    unittest.main(verbosity=2)
