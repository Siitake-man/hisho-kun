"""
Desk Pet PWA Seam分割 第3弾 (pet_particles.js) 回帰防止テスト

【検証内容】
1. web_pet/pet_particles.js が実在すること
2. 背景・天候・パーティクル描画の主要シンボルが定義・公開されていること
   (initEnvCanvas, particleLoop, drawEnvScene, spawnWeatherParticles,
    cycleEnvTheme, spawnTouchParticles, spawnCelebrationConfetti, ENV_THEMES)
3. web_pet/index.html で pet_particles.js が正しい順序 (pet_audio_se.js 直後、pet.js 直前) でロードされていること
4. web_pet/sw.js の ASSETS_TO_CACHE に './pet_particles.js' が登録されていること
5. local_sync_server.py の静的ファイル配信で pet_particles.js が 200 OK で取得できること
"""

import os
import re
import socket
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path

from local_sync_server import DeskPetSyncHandler


class TestPetSeamParticles(unittest.TestCase):
    """Desk Pet PWA の環境・パーティクルSeam分割 (pet_particles.js) 整合性テスト"""

    def setUp(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.web_pet_dir = self.project_root / "web_pet"
        self.particles_js = self.web_pet_dir / "pet_particles.js"
        self.index_html = self.web_pet_dir / "index.html"
        self.sw_js = self.web_pet_dir / "sw.js"
        self.pet_js = self.web_pet_dir / "pet.js"

    def test_01_pet_particles_file_exists(self):
        """web_pet/pet_particles.js が物理的に存在すること"""
        self.assertTrue(
            self.particles_js.exists(),
            f"pet_particles.js が存在しません: {self.particles_js}",
        )

    def test_02_pet_particles_symbols_exported(self):
        """主要シンボルが正しく定義・公開されていること"""
        content = self.particles_js.read_text(encoding="utf-8")

        required_symbols = [
            "initEnvCanvas",
            "particleLoop",
            "drawEnvScene",
            "spawnWeatherParticles",
            "cycleEnvTheme",
            "setEnvTheme",
            "spawnTouchParticles",
            "spawnCelebrationConfetti",
            "ENV_THEMES",
            "envCanvas",
        ]
        for sym in required_symbols:
            self.assertIn(
                sym,
                content,
                f"pet_particles.js に必須シンボル '{sym}' が見つかりません",
            )

    def test_03_index_html_script_order(self):
        """index.html で pet_particles.js が pet_audio_se.js の直後かつ pet.js の直前に読み込まれていること"""
        content = self.index_html.read_text(encoding="utf-8")

        self.assertRegex(
            content,
            r'<script\s+src="pet_particles\.js(?:\?[^"]*)?"></script>',
            "index.html に pet_particles.js の script タグがありません",
        )

        idx_version = content.find('src="version.js')
        idx_auth = content.find('src="pet_auth.js')
        idx_audio = content.find('src="pet_audio_se.js')
        idx_particles = content.find('src="pet_particles.js')
        idx_pet = content.find('src="pet.js')

        self.assertTrue(
            idx_version < idx_auth < idx_audio < idx_particles < idx_pet,
            f"スクリプトのロード順序が不正です: "
            f"version({idx_version}) < auth({idx_auth}) < audio({idx_audio}) < particles({idx_particles}) < pet({idx_pet})",
        )

    def test_04_sw_assets_cache_includes_pet_particles(self):
        """web_pet/sw.js の ASSETS_TO_CACHE に pet_particles.js が含まれていること"""
        content = self.sw_js.read_text(encoding="utf-8")
        self.assertIn(
            "'./pet_particles.js'",
            content,
            "sw.js の ASSETS_TO_CACHE に './pet_particles.js' が含まれていません",
        )

    def test_05_static_serve_pet_particles(self):
        """local_sync_server 経由で /pet_particles.js が正常に配信されること"""
        server = HTTPServer(("127.0.0.1", 0), DeskPetSyncHandler)
        port = server.server_port
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            import urllib.request

            url = f"http://127.0.0.1:{port}/pet_particles.js"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                self.assertEqual(resp.status, 200)
                body = resp.read().decode("utf-8")
                self.assertIn("particleLoop", body)
                self.assertIn("spawnCelebrationConfetti", body)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
