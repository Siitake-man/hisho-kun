"""
Desk Pet PWA Seam分割 第2弾 (pet_audio_se.js) 回帰防止テスト

【検証内容】
1. web_pet/pet_audio_se.js が実在すること
2. 音響・SE主要シンボル (getAudioContext, unlockAudio, playAlertChime, playDecisionSound, playCharacterSE 等) が定義されていること
3. web_pet/index.html で pet_audio_se.js が正しい順序 (pet_auth.js 直後、pet.js 直前) でロードされていること
4. web_pet/sw.js の ASSETS_TO_CACHE に './pet_audio_se.js' が登録されていること
5. local_sync_server.py の静的ファイル配信で pet_audio_se.js が 200 OK で取得できること
"""

import os
import re
import socket
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path

from local_sync_server import DeskPetSyncHandler


class TestPetSeamAudio(unittest.TestCase):
    """Desk Pet PWA のオーディオSeam分割 (pet_audio_se.js) 整合性テスト"""

    def setUp(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.web_pet_dir = self.project_root / "web_pet"
        self.audio_js = self.web_pet_dir / "pet_audio_se.js"
        self.index_html = self.web_pet_dir / "index.html"
        self.sw_js = self.web_pet_dir / "sw.js"
        self.pet_js = self.web_pet_dir / "pet.js"

    def test_01_pet_audio_se_file_exists(self):
        """web_pet/pet_audio_se.js が物理的に存在すること"""
        self.assertTrue(
            self.audio_js.exists(),
            f"pet_audio_se.js が存在しません: {self.audio_js}",
        )

    def test_02_pet_audio_symbols_exported(self):
        """主要シンボルが正しく定義・公開されていること"""
        content = self.audio_js.read_text(encoding="utf-8")

        required_symbols = [
            "getAudioContext",
            "unlockAudio",
            "playTwoTone",
            "playAlertChime",
            "stopAlertChime",
            "playDecisionSound",
            "playCharacterSE",
        ]
        for sym in required_symbols:
            self.assertIn(
                sym,
                content,
                f"pet_audio_se.js に必須シンボル '{sym}' が見つかりません",
            )

        # モバイル解錠イベントリスナーが登録されていること
        self.assertIn("pointerdown", content)
        self.assertIn("touchstart", content)
        self.assertIn("visibilitychange", content)

    def test_03_index_html_script_order(self):
        """index.html で pet_audio_se.js が pet_auth.js の直後かつ pet.js の直前に読み込まれていること"""
        content = self.index_html.read_text(encoding="utf-8")

        self.assertIn(
            '<script src="pet_audio_se.js"></script>',
            content,
            "index.html に pet_audio_se.js の script タグがありません",
        )

        # 読み込み順序の厳密検証: version.js -> pet_auth.js -> pet_audio_se.js -> pet.js
        idx_version = content.find('src="version.js"')
        idx_auth = content.find('src="pet_auth.js"')
        idx_audio = content.find('src="pet_audio_se.js"')
        idx_pet = content.find('src="pet.js')

        self.assertTrue(
            idx_version < idx_auth < idx_audio < idx_pet,
            f"スクリプトのロード順序が不正です: "
            f"version.js({idx_version}) < pet_auth.js({idx_auth}) < pet_audio_se.js({idx_audio}) < pet.js({idx_pet})",
        )

    def test_04_sw_assets_cache_includes_pet_audio_se(self):
        """web_pet/sw.js の ASSETS_TO_CACHE に pet_audio_se.js が含まれていること"""
        content = self.sw_js.read_text(encoding="utf-8")
        self.assertIn(
            "'./pet_audio_se.js'",
            content,
            "sw.js の ASSETS_TO_CACHE に './pet_audio_se.js' が含まれていません",
        )

    def test_05_static_serve_pet_audio_se(self):
        """local_sync_server 経由で /pet_audio_se.js が正常に配信されること"""
        server = HTTPServer(("127.0.0.1", 0), DeskPetSyncHandler)
        port = server.server_port
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            import urllib.request

            url = f"http://127.0.0.1:{port}/pet_audio_se.js"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                self.assertEqual(resp.status, 200)
                body = resp.read().decode("utf-8")
                self.assertIn("playAlertChime", body)
                self.assertIn("playCharacterSE", body)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
