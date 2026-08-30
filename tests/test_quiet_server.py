# -*- coding: utf-8 -*-
"""QuietThreadingHTTPServer.handle_error のログレベル分岐を検証するテスト。"""
import io
import logging
import tempfile
import unittest
from unittest import mock

import local_sync_server


class TestQuietServerErrorHandling(unittest.TestCase):
    """切断系例外はDEBUG・その他はWARNINGで記録されることのテスト"""

    def setUp(self):
        """一時DBとロガーキャプチャを用意する"""
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        io.open(fd).close()
        import database
        database.init_db(self.db_path)
        self.server = local_sync_server.QuietThreadingHTTPServer(
            ("127.0.0.1", 0), local_sync_server.DeskPetSyncHandler
        )
        self.logger = local_sync_server.logger
        patcher = mock.patch.object(self.logger, "debug")
        patcher2 = mock.patch.object(self.logger, "warning")
        self.mock_debug = patcher.start()
        self.mock_warning = patcher2.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(patcher2.stop)

    def tearDown(self):
        """サーバーと一時DBを後片付けする"""
        self.server.server_close()
        import os
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_connection_aborted_logged_as_debug(self):
        """WinError 10053 (ConnectionAbortedError) がDEBUGで記録されること"""
        try:
            raise ConnectionAbortedError(10053, "接続が中止されました")
        except ConnectionAbortedError:
            self.server.handle_error(None, ("192.168.1.10", 54321))
        self.mock_debug.assert_called_once()
        self.mock_warning.assert_not_called()

    def test_connection_reset_logged_as_debug(self):
        """ConnectionResetError がDEBUGで記録されること"""
        try:
            raise ConnectionResetError(10054, "リセット")
        except ConnectionResetError:
            self.server.handle_error(None, ("192.168.1.10", 54322))
        self.mock_debug.assert_called_once()
        self.mock_warning.assert_not_called()

    def test_unexpected_error_logged_as_warning(self):
        """予期しない例外はWARNING (トレースバック付き) で記録されること"""
        try:
            raise RuntimeError("重大な障害")
        except RuntimeError:
            self.server.handle_error(None, ("192.168.1.10", 54323))
        self.mock_debug.assert_not_called()
        self.mock_warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
