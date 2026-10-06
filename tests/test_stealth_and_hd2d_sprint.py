"""
手帳ID 93: UI/UX体験改善 ＆ 引き算の美学 ＆ スマホDesk Pet HD-2D進化スプリントの単体テスト
(tests/test_stealth_and_hd2d_sprint.py)
"""

import unittest
from pathlib import Path
from unittest import mock
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import version
import i18n
from character_manager import get_character_manager, CHARACTERS_DATA


class TestHD2DAndCharacterEvolution(unittest.TestCase):
    """HD-2Dキャラクターと時間帯台詞の検証"""

    def setUp(self):
        self.char_mgr = get_character_manager()

    def test_three_characters_coexist(self):
        """hisho, kyle, hisho_hd2d の3種類が共存していること（カイルは現行維持）"""
        chars = self.char_mgr.get_all_characters()
        char_ids = [c["id"] for c in chars]
        self.assertIn("hisho", char_ids)
        self.assertIn("kyle", char_ids)
        self.assertIn("hisho_hd2d", char_ids)
        self.assertEqual(len(chars), 3)

    def test_hd2d_base_char_and_sprite_prefix(self):
        """HD-2D版のbase_charが正しく解決され、スプライト接頭辞が基底キャラに一致すること"""
        self.char_mgr.set_character("hisho_hd2d")
        self.assertEqual(self.char_mgr.get_sprite_prefix(), "hisho_")

        # 復元
        self.char_mgr.set_character("hisho")
        self.assertEqual(self.char_mgr.get_sprite_prefix(), "hisho_")

    def test_character_time_greetings(self):
        """全3キャラで各時間帯 (朝/昼/午後/夕方/夜) の個性台詞が取得できること"""
        for char_id in ("hisho", "kyle", "hisho_hd2d"):
            morning = self.char_mgr.get_time_greeting(char_id=char_id, hour=8)
            noon = self.char_mgr.get_time_greeting(char_id=char_id, hour=12)
            afternoon = self.char_mgr.get_time_greeting(char_id=char_id, hour=15)
            evening = self.char_mgr.get_time_greeting(char_id=char_id, hour=19)
            night = self.char_mgr.get_time_greeting(char_id=char_id, hour=23)

            self.assertTrue(len(morning) > 0)
            self.assertTrue(len(noon) > 0)
            self.assertTrue(len(afternoon) > 0)
            self.assertTrue(len(evening) > 0)
            self.assertTrue(len(night) > 0)

            # hisho系はお茶、kyle系は貝型PCに言及
            if "hisho" in char_id:
                self.assertIn("茶", morning)
            elif "kyle" in char_id:
                self.assertIn("貝型PC", morning)

    def test_voice_transcription_notation_invariant(self):
        """全キャラのシステムプロンプトで『内蔵の音声文字起こし機能』表記が守られていること"""
        for char_id, data in CHARACTERS_DATA.items():
            prompt = data.get("system_prompt", "")
            self.assertIn("内蔵の音声文字起こし機能", prompt, f"{char_id} で表記違反")
            self.assertNotIn("内蔵音声認識は", prompt, f"{char_id} で旧表記検出")


class TestStealthModeAndResurfacing(unittest.TestCase):
    """ステルスモードおよび再表示ガードの検証"""

    def test_stealth_mode_guards_deiconify(self):
        """ステルスモード中はfrom_tray=True以外のshow_pc_pet呼び出しで再表示されないこと"""
        from gui import NeoSecretaryGUI

        with mock.patch("customtkinter.CTk"), \
             mock.patch("ui.system_tray.init_system_tray", return_value=None), \
             mock.patch.object(NeoSecretaryGUI, "_build_ui"), \
             mock.patch.object(NeoSecretaryGUI, "_bind_events"):
            gui = NeoSecretaryGUI.__new__(NeoSecretaryGUI)
            gui.root = mock.MagicMock()
            gui.stealth_mode = False
            gui.auto_minimize_on_link = False
            gui._was_linked_minimized = False
            gui.update_message = mock.MagicMock()
            gui.set_pet_state = mock.MagicMock()

            # 通常時は from_tray=False でも deiconify される
            gui.show_pc_pet(from_tray=False)
            gui.root.deiconify.assert_called_once()
            gui.root.deiconify.reset_mock()

            # ステルスモード突入
            gui.enter_stealth_mode()
            self.assertTrue(gui.stealth_mode)
            gui.root.withdraw.assert_called_once()

            # ステルスモード中は from_tray=False (agent ask/mobile) では deiconify されない
            gui.show_pc_pet(from_tray=False)
            gui.root.deiconify.assert_not_called()
            self.assertTrue(gui.stealth_mode)

            # ステルスモード中は toggle_auto_minimize でも勝手に deiconify されない
            gui.toggle_auto_minimize()
            gui.root.deiconify.assert_not_called()
            self.assertTrue(gui.stealth_mode)

            # トレイからの明示呼出 (from_tray=True) のみ deiconify され、ステルス解除される
            gui.show_pc_pet(from_tray=True)
            gui.root.deiconify.assert_called_once()
            self.assertFalse(gui.stealth_mode)

    def test_stealth_mode_menu_item_exists(self):
        """右クリックメニューにステルスモード項目が多言語対応で定義されていること"""
        self.assertIn("ui.menu.stealth", i18n.TRANSLATIONS["ja"])
        self.assertIn("ui.menu.stealth", i18n.TRANSLATIONS["en"])
        self.assertEqual(i18n.t("ui.menu.stealth", lang="ja"), "🥷 ペットを隠す (ステルスモード)")
        self.assertEqual(i18n.t("ui.menu.stealth", lang="en"), "🥷 Hide Pet (Stealth Mode)")


class TestEliminateNumericAffinity(unittest.TestCase):
    """親愛度Lv/XP数値表示排除の検証"""

    def test_no_numeric_level_in_main_agent_task_completed(self):
        """main.py 内に 'Lv.{bond[\'level\']}' の文字列が存在しないこと"""
        main_src = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("Lv.{bond['level']}", main_src)
        self.assertIn("🎊 【絆が深まりました！】", main_src)

    def test_no_numeric_level_in_calendar_window(self):
        """ui/calendar_window.py 内に 'Lv.{bond[\'level\']}' の文字列が存在しないこと"""
        cal_src = (PROJECT_ROOT / "ui" / "calendar_window.py").read_text(encoding="utf-8")
        self.assertNotIn("Lv.{bond['level']}", cal_src)
        self.assertIn("🎊 【絆が深まりました！】", cal_src)

    def test_no_numeric_level_or_xp_in_gui_click(self):
        """gui.py の _on_pet_click に 'Lv.{bond[\'level\']}' や '(親愛度: {bond[\'xp\']} XP)' が存在しないこと"""
        gui_src = (PROJECT_ROOT / "gui.py").read_text(encoding="utf-8")
        self.assertNotIn("Lv.{bond['level']}", gui_src)
        self.assertNotIn("{bond['xp']} XP", gui_src)


class TestWebPetHD2DAndMotions(unittest.TestCase):
    """web_pet HTML/JS HD-2D およびモーション拡張の検証"""

    def test_index_html_contains_hd2d_and_motion_classes(self):
        """index.html に HD-2D と 5大モーションキーフレームが含まれていること"""
        index_html = (PROJECT_ROOT / "web_pet" / "index.html").read_text(encoding="utf-8")
        self.assertIn(".pet-stage.is-hd2d", index_html)
        self.assertIn(".pixel-ring", index_html)
        self.assertIn("pet-hop", index_html)
        self.assertIn("pet-jiggle", index_html)
        self.assertIn("pet-bow", index_html)
        self.assertIn("pet-tea-serve", index_html)
        self.assertIn("pet-typing-frenzy", index_html)

    def test_pet_motion_js_exports_and_characters(self):
        """pet_motion.js が 3キャラ (hisho, kyle, hisho_hd2d) を定義し、新モーション関数をエクスポートしていること"""
        pet_motion_js = (PROJECT_ROOT / "web_pet" / "pet_motion.js").read_text(encoding="utf-8")
        self.assertIn("'hisho'", pet_motion_js)
        self.assertIn("'kyle'", pet_motion_js)
        self.assertIn("'hisho_hd2d'", pet_motion_js)
        self.assertIn("triggerPetMotion", pet_motion_js)
        self.assertIn("spawnPixelRing", pet_motion_js)
        self.assertIn("getBaseCharacter", pet_motion_js)


if __name__ == "__main__":
    unittest.main(verbosity=2)
