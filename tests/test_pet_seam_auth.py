#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - Desk Pet Seam分割 第1弾 (pet_auth.js) の整合性テスト (tests/test_pet_seam_auth.py)

Jules 設計レポート (docs/temp/seam_mapping_pet_js.md) に基づく Seam 分割テスト。
web_pet/pet.js から認証トークン管理および authFetch ラッパーが独立モジュール (pet_auth.js)
として安全に切り出され、HTML / Service Worker / HTTP 配信の全レイヤーで整合していることを検証する。

検証項目:
  1. web_pet/pet_auth.js が存在し、構文・主要関数が定義されていること
  2. web_pet/index.html で version.js の直後、pet.js より前に読み込まれていること
  3. web_pet/sw.js の ASSETS_TO_CACHE に ./pet_auth.js が登録されていること
  4. DeskPetSyncHandler 経由で /pet_auth.js および /web_pet/pet_auth.js が 200 OK で配信されること
  5. web_pet/pet.js 側で pet_auth.js のエクスポートを参照・委譲していること
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

# テスト実行中のログ抑制
logging.getLogger("local_sync_server").setLevel(logging.CRITICAL)


class TestPetSeamAuth(unittest.TestCase):
    """pet_auth.js Seamモジュール分割の完全性を検証する"""

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

    def test_pet_auth_file_exists_and_declares_symbols(self) -> None:
        """web_pet/pet_auth.js が存在し、必要なシンボルが公開されていること。"""
        auth_js_path = PROJECT_ROOT / "web_pet" / "pet_auth.js"
        self.assertTrue(auth_js_path.is_file(), "web_pet/pet_auth.js が存在しません")
        content = auth_js_path.read_text(encoding="utf-8")
        
        # 必須関数の定義
        self.assertIn("function loadSyncToken()", content)
        self.assertIn("function setSyncToken(", content)
        self.assertIn("function getSyncToken()", content)
        self.assertIn("async function authFetch(", content)
        self.assertIn("const SYNC_TOKEN_KEY", content)
        self.assertIn("var syncToken", content)
        
        # window への公開
        self.assertIn("window.authFetch = authFetch", content)
        self.assertIn("window.syncToken = syncToken", content)
        self.assertIn("window.getSyncToken = getSyncToken", content)
        self.assertIn("window.loadSyncToken = loadSyncToken", content)
        self.assertIn("window.setSyncToken = setSyncToken", content)

    def test_index_html_loads_pet_auth_in_correct_order(self) -> None:
        """index.html で version.js の後、pet.js の前に pet_auth.js が読み込まれていること。"""
        html_path = PROJECT_ROOT / "web_pet" / "index.html"
        content = html_path.read_text(encoding="utf-8")
        
        self.assertRegex(content, r'<script\s+src="pet_auth\.js(?:\?[^"]*)?"></script>')
        
        pos_version = content.find('src="version.js')
        pos_auth = content.find('src="pet_auth.js')
        pos_pet = content.find('src="pet.js')
        
        self.assertGreater(pos_auth, pos_version, "pet_auth.js は version.js の後に読み込む必要があります")
        self.assertLess(pos_auth, pos_pet, "pet_auth.js は pet.js の前に読み込む必要があります")

    def test_service_worker_caches_pet_auth(self) -> None:
        """sw.js の ASSETS_TO_CACHE に ./pet_auth.js が含まれていること。"""
        sw_path = PROJECT_ROOT / "web_pet" / "sw.js"
        content = sw_path.read_text(encoding="utf-8")
        self.assertIn("'./pet_auth.js'", content)

    def test_pet_js_delegates_to_pet_auth(self) -> None:
        """pet.js が pet_auth.js の定義を安全に委譲・参照していること。"""
        pet_js_path = PROJECT_ROOT / "web_pet" / "pet.js"
        content = pet_js_path.read_text(encoding="utf-8")
        
        # インラインでの重複宣言(const SYNC_TOKEN_KEY)が除去され、委譲コメントが存在すること
        self.assertIn("pet_auth.js にSeam分離済み", content)
        self.assertIn("window.authFetch", content)
        # 🛡️ P0-1 (2026-09-22): ステータス応答を根拠としたトークン上書きは撤去済み。
        # トークン更新は pet_auth.js の requestSyncToken() (/api/auth/token) の一本道であること。
        self.assertNotIn(
            "setSyncToken(data.sync_token)",
            content,
            "ステータス応答によるトークン上書き (権限昇格の温床) を再導入してはならない",
        )

    def test_http_serves_pet_auth_js(self) -> None:
        """HTTPサーバー経由で /pet_auth.js が 200 OK で配信されること。"""
        url = f"http://127.0.0.1:{self.port}/pet_auth.js"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3.0) as res:
            self.assertEqual(res.status, 200)
            body = res.read().decode("utf-8")
            self.assertIn("async function authFetch", body)


if __name__ == "__main__":
    unittest.main()
