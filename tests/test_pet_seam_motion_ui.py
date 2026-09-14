"""
Desk Pet PWA Seam分割 第4弾 (pet_motion.js) ＆ 第5弾 (pet_ui.js) 回帰防止テスト

【検証内容】
1. web_pet/pet_motion.js, web_pet/pet_ui.js が物理的に存在すること
2. pet_motion.js の主要シンボルが定義・公開されていること
   (CHARACTERS, preloadSprites, updateLifeSprite, triggerCelebrateReaction,
    updatePetLifeActivity, petWanderTick, onPetTap, _setPetSprite, WANDER)
3. pet_ui.js の主要シンボルが定義・公開されていること
   (showToast, escapeHtml, renderSuggestionCard, nextSuggest, openBottomSheet,
    closeBottomSheet, setupBannerSwipe, openApprovalSheet, respondApproval,
    setupMediaKeyApproval, updateClock, togglePomodoro, updateAgentActivityBadge)
4. web_pet/index.html でスクリプト読み込み順序が正しいこと
   (version -> pet_auth -> pet_audio_se -> pet_particles -> pet_motion -> pet_ui -> pet.js)
5. web_pet/sw.js の ASSETS_TO_CACHE に両ファイルが登録されていること
6. local_sync_server.py の静的ファイル配信で両ファイルが 200 OK で取得できること
"""

import threading
import unittest
from http.server import HTTPServer
from pathlib import Path
import urllib.request

from local_sync_server import DeskPetSyncHandler


class TestPetSeamMotionAndUI(unittest.TestCase):
    """Desk Pet PWA のモーション＆UI Seam分割 (pet_motion.js, pet_ui.js) 整合性テスト"""

    def setUp(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.web_pet_dir = self.project_root / "web_pet"
        self.motion_js = self.web_pet_dir / "pet_motion.js"
        self.ui_js = self.web_pet_dir / "pet_ui.js"
        self.index_html = self.web_pet_dir / "index.html"
        self.sw_js = self.web_pet_dir / "sw.js"
        self.pet_js = self.web_pet_dir / "pet.js"

    def test_01_files_exist(self):
        """pet_motion.js と pet_ui.js が物理的に存在すること"""
        self.assertTrue(self.motion_js.exists(), f"pet_motion.js が存在しません: {self.motion_js}")
        self.assertTrue(self.ui_js.exists(), f"pet_ui.js が存在しません: {self.ui_js}")

    def test_02_motion_symbols_exported(self):
        """pet_motion.js に主要シンボルが定義・公開されていること"""
        content = self.motion_js.read_text(encoding="utf-8")
        required_symbols = [
            "CHARACTERS",
            "preloadSprites",
            "_setPetSprite",
            "setPetSprite",
            "updateLifeSprite",
            "updatePetLifeActivity",
            "triggerCelebrateReaction",
            "WANDER",
            "petWanderTick",
            "onPetTap",
            "cycleCharacter",
        ]
        for sym in required_symbols:
            self.assertIn(sym, content, f"pet_motion.js に必須シンボル '{sym}' が見つかりません")

    def test_03_ui_symbols_exported(self):
        """pet_ui.js に主要シンボルが定義・公開されていること"""
        content = self.ui_js.read_text(encoding="utf-8")
        required_symbols = [
            "showToast",
            "escapeHtml",
            "renderSuggestionCard",
            "nextSuggest",
            "prevSuggest",
            "setupSuggestSwipe",
            "openBottomSheet",
            "closeBottomSheet",
            "setupBannerSwipe",
            "openApprovalSheet",
            "openQuestionSheet",
            "respondApproval",
            "setupMediaKeyApproval",
            "updateClock",
            "togglePomodoro",
            "updateAgentActivityBadge",
        ]
        for sym in required_symbols:
            self.assertIn(sym, content, f"pet_ui.js に必須シンボル '{sym}' が見つかりません")

    def test_04_index_html_script_order(self):
        """index.html でスクリプト読み込み順序が正しいこと"""
        content = self.index_html.read_text(encoding="utf-8")

        self.assertIn('<script src="pet_motion.js"></script>', content)
        self.assertIn('<script src="pet_ui.js"></script>', content)

        idx_version = content.find('src="version.js"')
        idx_auth = content.find('src="pet_auth.js"')
        idx_audio = content.find('src="pet_audio_se.js"')
        idx_particles = content.find('src="pet_particles.js"')
        idx_motion = content.find('src="pet_motion.js"')
        idx_ui = content.find('src="pet_ui.js"')
        idx_pet = content.find('src="pet.js')

        self.assertTrue(
            idx_version < idx_auth < idx_audio < idx_particles < idx_motion < idx_ui < idx_pet,
            f"スクリプトのロード順序が不正です: "
            f"version({idx_version}) < auth({idx_auth}) < audio({idx_audio}) < "
            f"particles({idx_particles}) < motion({idx_motion}) < ui({idx_ui}) < pet({idx_pet})",
        )

    def test_05_sw_assets_cache_includes_motion_and_ui(self):
        """web_pet/sw.js の ASSETS_TO_CACHE に pet_motion.js と pet_ui.js が含まれていること"""
        content = self.sw_js.read_text(encoding="utf-8")
        self.assertIn("'./pet_motion.js'", content, "sw.js に './pet_motion.js' が含まれていません")
        self.assertIn("'./pet_ui.js'", content, "sw.js に './pet_ui.js' が含まれていません")

    def test_06_static_serve_motion_and_ui(self):
        """local_sync_server 経由で /pet_motion.js と /pet_ui.js が正常に配信されること"""
        server = HTTPServer(("127.0.0.1", 0), DeskPetSyncHandler)
        port = server.server_port
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            # 1. pet_motion.js
            url_motion = f"http://127.0.0.1:{port}/pet_motion.js"
            with urllib.request.urlopen(url_motion, timeout=3.0) as resp:
                self.assertEqual(resp.status, 200)
                body = resp.read().decode("utf-8")
                self.assertIn("pet_motion.js", body)

            # 2. pet_ui.js
            url_ui = f"http://127.0.0.1:{port}/pet_ui.js"
            with urllib.request.urlopen(url_ui, timeout=3.0) as resp:
                self.assertEqual(resp.status, 200)
                body = resp.read().decode("utf-8")
                self.assertIn("pet_ui.js", body)
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
