#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - バージョン定数一元化 (version.js) エンドポイントのテスト (tests/test_version_endpoint.py)

Jules 夜間設計レポート (docs/temp/seam_mapping_pet_js.md) に基づく TDD テスト。
Python 側の version.py (__version__) を唯一の真実の源 (Single Source of Truth) とし、
local_sync_server.py の DeskPetSyncHandler から動的 JavaScript として配信されることを検証する。

検証項目:
  1. GET /version.js が 200 OK で JavaScript を返すこと
  2. GET /web_pet/version.js (クエリ付き含む) も同一の動的 JavaScript を返すこと
  3. Content-Type が application/javascript で Cache-Control に no-cache が指定されていること
  4. レスポンスボディに version.__version__ 由来の APP_VERSION および WEB_PET_CACHE_NAME が含まれること
  5. 静的ファイル web_pet/version.js が存在し、オフライン・フォールバック時も契約が満たされること
"""

import logging
import sys
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import local_sync_server
import version

# テスト実行中のログ抑制
logging.getLogger("local_sync_server").setLevel(logging.CRITICAL)


class TestVersionEndpoint(unittest.TestCase):
    """version.js 動的配信エンドポイントの契約を検証する"""

    @classmethod
    def setUpClass(cls) -> None:
        """エフェメラルポートでテスト用 HTTP サーバーを起動する。"""
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), local_sync_server.DeskPetSyncHandler)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        """サーバーを安全に停止する。"""
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.server_thread.join(timeout=2.0)

    def test_get_version_js_returns_200_and_javascript(self) -> None:
        """GET /version.js が 200 OK かつ JavaScript として配信されること。"""
        url = f"http://127.0.0.1:{self.port}/version.js"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3.0) as res:
            self.assertEqual(res.status, 200)
            content_type = res.headers.get("Content-Type", "")
            self.assertIn("javascript", content_type.lower())
            body = res.read().decode("utf-8")
            
            # version.py 由来の値が含まれていること
            expected_ver = version.__version__
            self.assertIn(f'APP_VERSION = "{expected_ver}";', body)
            self.assertIn(f'WEB_PET_CACHE_NAME = "neo-pet-v{expected_ver}";', body)
            self.assertIn("window.APP_VERSION", body)
            self.assertIn("window.WEB_PET_CACHE_NAME", body)

    def test_get_web_pet_version_js_with_query(self) -> None:
        """GET /web_pet/version.js?v=xxx も動的生成されること。"""
        url = f"http://127.0.0.1:{self.port}/web_pet/version.js?v=test123"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3.0) as res:
            self.assertEqual(res.status, 200)
            body = res.read().decode("utf-8")
            self.assertIn(f'APP_VERSION = "{version.__version__}";', body)

    def test_cache_control_headers(self) -> None:
        """PWA やブラウザのキャッシュ事故を防ぐため no-cache が指定されていること。"""
        url = f"http://127.0.0.1:{self.port}/version.js"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3.0) as res:
            cache_ctrl = res.headers.get("Cache-Control", "").lower()
            self.assertIn("no-cache", cache_ctrl)

    def test_static_fallback_file_exists(self) -> None:
        """オフライン時・開発環境フォールバック用の静的ファイル web_pet/version.js が存在すること。"""
        fallback_path = PROJECT_ROOT / "web_pet" / "version.js"
        self.assertTrue(fallback_path.is_file(), "web_pet/version.js が存在しません")
        content = fallback_path.read_text(encoding="utf-8")
        self.assertIn(f'APP_VERSION = "{version.__version__}";', content)
        self.assertIn(f'WEB_PET_CACHE_NAME = "neo-pet-v{version.__version__}";', content)


if __name__ == "__main__":
    unittest.main()
