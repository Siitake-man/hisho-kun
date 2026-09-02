#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - CORS オリジン制限テスト (tests/test_cors_hardening.py)

2026-09-03 Block 3 ゼロトラスト監査の対策テスト。
かつての ``Access-Control-Allow-Origin: *`` は、スマホのブラウザで開いた任意の
Web サイトから GET /api/status (LAN内トークン不要) 等をクロスオリジン読み取り
できる情報漏洩経路になるため、同一オリジン (PWA 配信元) のみに制限する:

  1. 異オリジンからのリクエストには CORS 許可ヘッダーを付与しない
  2. 同一オリジン (Origin authority == Host ヘッダー) には Origin をエコー
  3. Origin なし (ネイティブクライアント / 同一オリジンGET) には付与しない
  4. OPTIONS プリフライトも異オリジンには許可しない

設計上の注意:
- ポート0 (エフェメラル) で ThreadingHTTPServer を起動し、静的配信 GET / と
  OPTIONS / で検証する (DB 依存なし・本番ポート不接触)。
"""

import logging
import sys
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Optional

# ※ 本ファイルは tests/ 配下にあるため、プロジェクトルートを import パスに追加
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import local_sync_server

# テスト実行中にサーバーロガーがコンソールを荒らすのを防止
logging.getLogger("local_sync_server").setLevel(logging.CRITICAL)


class TestCorsHardening(unittest.TestCase):
    """CORS レスポンスヘッダーのオリジン制限を検証する"""

    @classmethod
    def setUpClass(cls) -> None:
        """エフェメラルポートでHTTPサーバーを起動する (DB依存なし)。"""
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), local_sync_server.DeskPetSyncHandler)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        """HTTPサーバーを後片付けする。"""
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.server_thread.join(timeout=5)

    @classmethod
    def _request(cls, method: str, path: str, origin: Optional[str] = None):
        """Origin ヘッダー付きでリクエストを送り、レスポンスオブジェクトを返す。

        Args:
            method: HTTP メソッド (GET / OPTIONS)。
            path: リクエストパス (静的配信パスを使用)。
            origin: 送信する Origin ヘッダー値 (None なら送信しない)。

        Returns:
            urllib.response: レスポンス (ヘッダー参照用)。
        """
        headers = {}
        if origin is not None:
            headers["Origin"] = origin
        req = urllib.request.Request(
            f"http://127.0.0.1:{cls.port}{path}", headers=headers, method=method
        )
        return urllib.request.urlopen(req, timeout=15)

    def test_foreign_origin_gets_no_cors_grant(self):
        """異オリジン (悪意あるサイト) には CORS 許可を与えない"""
        res = self._request("GET", "/api/auth/token", origin="https://evil.example")
        self.assertIsNone(
            res.headers.get("Access-Control-Allow-Origin"),
            "異オリジンに Access-Control-Allow-Origin を付与してはならない",
        )

    def test_same_origin_gets_no_cors_headers(self):
        """同一オリジン (PWA 配信元) にも CORS ヘッダーを付与しない

        ※ 同一オリジンは CORS 許可なしで動作するため、DNS リバインディング等の
          Host ヘッダー偽装による迂回を含め、許可ヘッダー自体を発行しないのが
          最も安全 (2026-09-02 deep-audit 悪魔の代弁者指摘の是正)。
        """
        res = self._request("GET", "/api/auth/token", origin=f"http://127.0.0.1:{self.port}")
        self.assertIsNone(
            res.headers.get("Access-Control-Allow-Origin"),
            "同一オリジンにも Access-Control-Allow-Origin を付与してはならない",
        )

    def test_no_origin_gets_no_cors_headers(self):
        """Origin なし (ネイティブクライアント) には CORS ヘッダーを付与しない"""
        res = self._request("GET", "/api/auth/token")
        self.assertIsNone(res.headers.get("Access-Control-Allow-Origin"))

    def test_options_preflight_foreign_origin_no_grant(self):
        """異オリジンのプリフライト (OPTIONS) にも CORS 許可を与えない"""
        res = self._request("OPTIONS", "/", origin="https://evil.example")
        self.assertIsNone(
            res.headers.get("Access-Control-Allow-Origin"),
            "異オリジンのプリフライトに Access-Control-Allow-Origin を付与してはならない",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
