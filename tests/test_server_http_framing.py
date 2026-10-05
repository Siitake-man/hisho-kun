#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - HTTP Framing ＆ Content-Length 堅牢性テスト (tests/test_server_http_framing.py).

ChatGPT 外部レビュー指摘に基づく P0 脆弱性封鎖テスト:
- 負の Content-Length (例: -1, -999) による read(-1) 無限EOFハングの防止
- 非整数・壊れた Content-Length による 400 Bad Request 返却
- 5MB 上限超過による 413 Payload Too Large 返却
- Content-Length 欠落・ゼロ時の安全な処理 (後方互換性)
"""

import io
import os
import socket
import tempfile
import threading
import unittest
from pathlib import Path

import database
import local_sync_server


class TestServerHttpFraming(unittest.TestCase):
    """HTTP Framing および Content-Length 入力バリデーションのテスト"""

    @classmethod
    def setUpClass(cls):
        """エフェメラルポートでサーバーを起動する"""
        fd, cls.db_path = tempfile.mkstemp(suffix=".db")
        io.open(fd).close()
        database.init_db(cls.db_path)

        cls.server = local_sync_server.QuietThreadingHTTPServer(
            ("127.0.0.1", 0), local_sync_server.DeskPetSyncHandler
        )
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        """サーバーを停止しDBをクリーンアップする"""
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        if os.path.exists(cls.db_path):
            try:
                os.remove(cls.db_path)
            except OSError:
                pass

    def _send_raw_http(self, request_bytes: bytes, timeout: float = 2.0, shutdown_wr: bool = False) -> bytes:
        """生のソケットで HTTP リクエストを送信し、レスポンスを受信する。"""
        with socket.create_connection(("127.0.0.1", self.port), timeout=timeout) as s:
            s.sendall(request_bytes)
            if shutdown_wr:
                # 送信完了 (TCP FIN) を通知し、サーバー側の read EOF を確定させる
                s.shutdown(socket.SHUT_WR)
            # レスポンスを受信
            response = b""
            while True:
                try:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    response += chunk
                    # HTTP ヘッダー終端を受信したら終了 (または EOF)
                    if b"\r\n\r\n" in response:
                        break
                except socket.timeout:
                    break
            return response

    def test_negative_content_length_minus_one_rejected_with_400(self):
        """P0: Content-Length: -1 のリクエストが 400 Bad Request で即座に拒否され、read(-1)ハングしないこと"""
        raw_req = (
            b"POST /api/action HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: -1\r\n"
            b"\r\n"
        )
        resp = self._send_raw_http(raw_req, timeout=2.0)
        # タイムアウトせずに 400 Bad Request が返ること
        self.assertIn(b"400 Bad Request", resp, f"Expected 400 Bad Request, got: {resp[:200]}")

    def test_negative_content_length_large_negative_rejected_with_400(self):
        """P0: 極端な負数 Content-Length: -99999 が 400 Bad Request で拒否されること"""
        raw_req = (
            b"POST /api/action HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Length: -99999\r\n"
            b"\r\n"
        )
        resp = self._send_raw_http(raw_req, timeout=2.0)
        self.assertIn(b"400 Bad Request", resp)

    def test_invalid_non_numeric_content_length_rejected_with_400(self):
        """不正形式の Content-Length (アルファベット等) が 400 Bad Request で拒否されること"""
        raw_req = (
            b"POST /api/action HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Length: abc_invalid\r\n"
            b"\r\n"
        )
        resp = self._send_raw_http(raw_req, timeout=2.0)
        self.assertIn(b"400 Bad Request", resp)

    def test_exorbitant_content_length_rejected_with_413(self):
        """上限 (5MB) を超える Content-Length が 413 Payload Too Large で拒否されること"""
        raw_req = (
            b"POST /api/action HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Length: 10485760\r\n"  # 10MB
            b"\r\n"
        )
        resp = self._send_raw_http(raw_req, timeout=2.0)
        self.assertIn(b"413", resp)

    def test_missing_content_length_treated_as_zero_length(self):
        """Content-Length ヘッダーが欠落している場合、400にならず長さ0として安全に処理されること"""
        raw_req = (
            b"POST /api/action HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"\r\n"
        )
        resp = self._send_raw_http(raw_req, timeout=2.0)
        # 400 や 413 ではなく、認証エラー (401) または正常処理へ進むこと
        self.assertNotIn(b"400 Bad Request", resp)
        self.assertNotIn(b"413", resp)


    def test_duplicate_content_length_rejected_with_400(self):
        """CL.CL Smuggling防止: 重複した Content-Length ヘッダーが 400 Bad Request で遮断されること (RFC 9112 Section 6.3)"""
        raw_req = (
            b"POST /api/action HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Length: 10\r\n"
            b"Content-Length: 20\r\n"
            b"\r\n"
            b"1234567890"
        )
        resp = self._send_raw_http(raw_req, timeout=2.0)
        self.assertIn(b"400 Bad Request", resp)

    def test_transfer_encoding_rejected_with_400(self):
        """CL.TE Smuggling防止: 未対応の Transfer-Encoding ヘッダーが 400 Bad Request で遮断されること"""
        raw_req = (
            b"POST /api/action HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Transfer-Encoding: chunked\r\n"
            b"\r\n"
            b"0\r\n\r\n"
        )
        resp = self._send_raw_http(raw_req, timeout=2.0)
        self.assertIn(b"400 Bad Request", resp)

    def test_fullwidth_unicode_digits_rejected_with_400(self):
        """Python int() 罠防止: 全角数字の Content-Length が 400 Bad Request で遮断されること"""
        raw_req = (
            b"POST /api/action HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Length: \xef\xbc\x91\xef\xbc\x90\xef\xbc\x90\r\n"  # １００ (UTF-8)
            b"\r\n"
        )
        resp = self._send_raw_http(raw_req, timeout=2.0)
        self.assertIn(b"400 Bad Request", resp)

    def test_underscore_numeric_literal_rejected_with_400(self):
        """Python int() 罠防止: アンダースコア入り数値リテラル (1_000) が 400 Bad Request で遮断されること"""
        raw_req = (
            b"POST /api/action HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Length: 1_000\r\n"
            b"\r\n"
        )
        resp = self._send_raw_http(raw_req, timeout=2.0)
        self.assertIn(b"400 Bad Request", resp)

    def test_plus_sign_content_length_rejected_with_400(self):
        """RFC 9110 準拠: プラス符号付き (+100) が 400 Bad Request で遮断されること"""
        raw_req = (
            b"POST /api/action HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Length: +100\r\n"
            b"\r\n"
        )
        resp = self._send_raw_http(raw_req, timeout=2.0)
        self.assertIn(b"400 Bad Request", resp)

    def test_truncated_body_rejected_with_400(self):
        """本文途中切断防止: 宣言した Content-Length より短い本文で切断された場合、
        サーバーが処理を実行せず 400 Bad Request で拒絶するか、または安全に切断（無応答破棄）すること"""
        raw_req = (
            b"POST /api/action HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Length: 100\r\n"
            b"Connection: close\r\n"
            b"\r\n"
            b'{"action":"ping"}'  # 17バイト
        )
        resp = self._send_raw_http(raw_req, timeout=2.0, shutdown_wr=True)
        # 400 Bad Request が返るか、またはクライアント切断による無応答切断 (b"") であること
        # (いかなる場合も 200 OK や正常処理、500 等の内部例外へ進まないこと)
        self.assertTrue(
            b"400 Bad Request" in resp or resp == b"",
            f"Expected 400 Bad Request or connection closure, got: {resp!r}"
        )
        self.assertNotIn(b"200 OK", resp)
        self.assertNotIn(b"500 Internal", resp)


if __name__ == "__main__":
    unittest.main()

