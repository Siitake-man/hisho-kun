#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - 単一インスタンスロックの単体テスト (tests/test_single_instance_lock.py)

二重起動防止ロック (ポート54321) は bind() だけでなく listen() していること。
listen しないバウンドのみのソケットは netstat / Get-NetTCPConnection に現れず、
残留プロセス (タスクトレイ終了漏れ等) の発見・終了が不可能になる
(2026-09-12 問題: トレイ終了後もプロセスが残り、掃除コマンドでも見つからない)。

TDD: acquire_single_instance_lock() が無い状態では Red で落ちる。
"""

import socket
import sys
import unittest
import warnings
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import acquire_single_instance_lock  # noqa: E402


class TestSingleInstanceLock(unittest.TestCase):
    """単一インスタンスロックソケットの監視可能化契約"""

    def test_lock_socket_is_listening_and_discoverable(self) -> None:
        """ロックソケットが listen 状態 (netstat/Get-NetTCPConnection に現れる) であること"""
        try:
            lock = acquire_single_instance_lock()
        except OSError:
            self.skipTest("既に別インスタンスがポート54321を使用中 (アプリ起動中)")
        self.addCleanup(lock.close)

        # SO_ACCEPTCONN == 1 はソケットが listen() 済みであることを示す
        self.assertEqual(
            lock.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN), 1
        )

        # 同一ポートへの2重取得は OSError (多重起動検知の本体)
        with self.assertRaises(OSError):
            second = acquire_single_instance_lock()
            second.close()

    def test_failed_acquire_closes_socket_no_resource_warning(self) -> None:
        """bind 失敗時もソケットが閉じられ ResourceWarning を漏らさないこと"""
        try:
            first = acquire_single_instance_lock()
        except OSError:
            self.skipTest("既に別インスタンスがポート54321を使用中 (アプリ起動中)")
        self.addCleanup(first.close)

        # 失敗側ソケットは即GCされるため、ResourceWarning を error 化して検知する
        with warnings.catch_warnings():
            warnings.simplefilter("error", ResourceWarning)
            with self.assertRaises(OSError):
                acquire_single_instance_lock()


if __name__ == "__main__":
    unittest.main(verbosity=2)
