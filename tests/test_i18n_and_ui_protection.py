"""
Sprint Global (Phase 2): i18n 多言語拡張・動的LLMガード・UI防御検証テスト
"""

import unittest
from unittest.mock import MagicMock
import tkinter as tk

import i18n
from i18n import t, set_language, get_language, get_no_chinese_instruction, get_prompt_language_instruction
from ui.pet_window import calculate_bubble_width, draw_speech_bubble, PetBubbleManager


class TestI18nAndUIGlobal(unittest.TestCase):
    def setUp(self):
        # 既定言語を ja に戻す
        set_language("ja")

    def tearDown(self):
        set_language("ja")

    def test_i18n_ui_dictionary_ja(self):
        """日本語UI辞書キーが正しく取得できることを検証"""
        set_language("ja")
        self.assertEqual(t("ui.settings.title"), "⚙️ ネオ秘書くん 設定")
        self.assertEqual(t("ui.settings.general"), "一般")
        self.assertEqual(t("ui.settings.language"), "表示言語 / Language")
        self.assertEqual(t("ui.settings.save"), "保存して閉じる")
        self.assertEqual(t("ui.pet.working"), "お仕事中")
        self.assertEqual(t("ui.pet.sleeping"), "睡眠中")
        self.assertEqual(t("ui.pet.auto_minimize_toggle", status="有効"), "📱 スマホ接続時のPCペット自動最小化を【有効】にしました！")
        self.assertEqual(t("ui.tray.settings"), "⚙️ 設定を開く")
        self.assertEqual(t("ui.tray.exit"), "❌ ネオ秘書くんを終了")

    def test_i18n_ui_dictionary_en(self):
        """英語UI辞書キーが正しく取得できることを検証"""
        set_language("en")
        self.assertEqual(t("ui.settings.title"), "⚙️ Neo-Secretary Settings")
        self.assertEqual(t("ui.settings.general"), "General")
        self.assertEqual(t("ui.settings.language"), "Language")
        self.assertEqual(t("ui.settings.save"), "Save & Close")
        self.assertEqual(t("ui.pet.working"), "Working")
        self.assertEqual(t("ui.pet.sleeping"), "Sleeping")
        self.assertEqual(t("ui.pet.auto_minimize_toggle", status="Enabled"), "📱 Auto-minimize on mobile link set to 【Enabled】!")
        self.assertEqual(t("ui.tray.settings"), "⚙️ Open Settings")
        self.assertEqual(t("ui.tray.exit"), "❌ Exit Neo-Secretary")

    def test_dynamic_llm_language_guard(self):
        """言語切替に応じて LLM ガード指示文が動的に切り替わることを検証"""
        # 日本語時
        set_language("ja")
        guard_ja = get_no_chinese_instruction()
        self.assertIn("Write ALL text fields in 日本語", guard_ja)
        self.assertIn("Do NOT use Chinese (简体中文), English", guard_ja)

        prompt_ja = get_prompt_language_instruction()
        self.assertTrue(prompt_ja.startswith("Response Language: 日本語"))
        self.assertIn(guard_ja, prompt_ja)

        # 英語時
        set_language("en")
        guard_en = get_no_chinese_instruction()
        self.assertIn("Write ALL text fields in English", guard_en)
        self.assertIn("Do NOT use Chinese (简体中文), Japanese", guard_en)

        prompt_en = get_prompt_language_instruction()
        self.assertTrue(prompt_en.startswith("Response Language: English"))
        self.assertIn(guard_en, prompt_en)

    def test_bubble_width_scaling(self):
        """吹き出し横幅がテキスト長に応じて 220px〜320px で伸縮することを検証"""
        # 短文
        short_w = calculate_bubble_width("Hello")
        self.assertEqual(short_w, 220)

        # 超長文
        long_text = "This is a very long English sentence designed to test the maximum bubble width expansion in Neo Secretary desktop mascot UI."
        long_w = calculate_bubble_width(long_text)
        self.assertEqual(long_w, 320)

        # 中間長
        mid_text = "あいうえおかきくけこさしすせそたちつてとなにぬねの"  # 25文字〜90文字の間
        mid_w = calculate_bubble_width(mid_text)
        self.assertTrue(220 <= mid_w <= 320)

    def test_bubble_canvas_draw_mock(self):
        """Canvas 上での draw_speech_bubble が正常に実行され、寸法タプルを返すことを検証"""
        # tk.Canvas のモック
        mock_canvas = MagicMock()
        mock_canvas.bbox.return_value = (10, 10, 200, 50)  # テキストのbbox

        w, h = draw_speech_bubble(
            canvas=mock_canvas,
            text="Testing Word Wrapping in Speech Bubble",
            x=170,
            y=10,
            min_width=220,
            max_width=320,
        )

        self.assertTrue(220 <= w <= 320)
        self.assertGreater(h, 0)
        # create_text に width パラメータが渡されていることを検証 (Word Wrapping)
        calls = mock_canvas.create_text.call_args_list
        self.assertTrue(any("width" in call[1] and call[1]["width"] >= 100 for call in calls))


    def test_i18n_dictionary_symmetry(self):
        """ja と en の翻訳辞書キーが完全に対称（欠落なし）であることを検証"""
        ja_keys = set(i18n._TRANSLATIONS.get("ja", {}).keys())
        en_keys = set(i18n._TRANSLATIONS.get("en", {}).keys())
        self.assertGreater(len(ja_keys), 0)
        self.assertEqual(ja_keys, en_keys, f"辞書キーの不一致: 差分 ja - en = {ja_keys - en_keys}, en - ja = {en_keys - ja_keys}")

    def test_i18n_fallback_behavior(self):
        """辞書に存在しないキーや未対応言語が指定された時のフォールバックを検証"""
        # 1. 存在しないキーのフォールバック (キー名そのものを返す)
        self.assertEqual(t("non.existent.dummy.key"), "non.existent.dummy.key")

        # 2. 未対応言語コードのフォールバック (既定言語 ja に切り替わる)
        set_language("fr")
        self.assertEqual(get_language(), "ja")
        self.assertEqual(t("ui.settings.general"), "一般")

        # 3. 英語環境で en に存在しない架空のキーが ja に存在する場合のフォールバック
        set_language("en")
        orig_en = i18n._TRANSLATIONS["en"].copy()
        try:
            # en から一時的に削除してフォールバック動作を検証
            del i18n._TRANSLATIONS["en"]["ui.settings.general"]
            self.assertEqual(t("ui.settings.general"), "一般")
        finally:
            i18n._TRANSLATIONS["en"] = orig_en

    def test_bubble_width_exact_boundaries(self):
        """文字長 0, 10, 50, 100, 500 における境界値の動的伸縮を厳密に検証"""
        # 文字長 0: 最小幅 220px
        self.assertEqual(calculate_bubble_width(""), 220)

        # 文字長 10: 25文字以下なので最小幅 220px
        self.assertEqual(calculate_bubble_width("A" * 10), 220)

        # 文字長 50: (50 - 25) / (90 - 25) = 25/65 ≈ 0.3846 -> 220 + int(38.46) = 258px
        w_50 = calculate_bubble_width("A" * 50)
        self.assertEqual(w_50, 258)

        # 文字長 100: 90文字以上なので最大幅 320px
        self.assertEqual(calculate_bubble_width("A" * 100), 320)

        # 文字長 500: 90文字以上なので最大幅 320px
        self.assertEqual(calculate_bubble_width("A" * 500), 320)

    def test_pet_bubble_manager_mock(self):
        """ヘッドレス環境で PetBubbleManager が MagicMock Canvas を介して安全に動作することを検証"""
        mock_canvas = MagicMock()
        mock_canvas.bbox.return_value = (10, 10, 210, 45)

        manager = PetBubbleManager(canvas=mock_canvas, center_x=150.0, top_y=20.0)
        w, h = manager.show_message("Hello from headless test!")

        self.assertTrue(220 <= w <= 320)
        self.assertGreater(h, 0)
        self.assertEqual(manager.current_text, "Hello from headless test!")

        # clear の検証
        manager.clear()
        mock_canvas.delete.assert_called_with("pet_speech_bubble")
        self.assertEqual(manager.current_text, "")


    def test_1000_char_bomb_and_unbroken_token_defense(self):
        """1000文字爆弾やスペースなし長大トークンが注入されても破綻・窒息死しないことを検証"""
        mock_canvas = MagicMock()
        mock_canvas.bbox.return_value = (10, 10, 300, 300)

        # 1. 1000文字爆弾 (超長文)
        bomb_text = "ERROR " * 200
        w, h = draw_speech_bubble(
            canvas=mock_canvas,
            text=bomb_text,
            x=170,
            y=10,
            max_height=140,
        )
        # 高さが 140px で安全に clamp されていることを検証
        self.assertLessEqual(h, 140)
        self.assertTrue(220 <= w <= 320)

        # 2. 空白のない200文字トークン (Word Wrapping 破壊攻撃)
        unbroken_token = "A" * 200
        w2, h2 = draw_speech_bubble(
            canvas=mock_canvas,
            text=unbroken_token,
            x=170,
            y=10,
        )
        self.assertTrue(220 <= w2 <= 320)
        # create_text に渡されたテキストが強制分割されていることを検証
        last_call_text = mock_canvas.create_text.call_args[1]["text"]
        self.assertIn(" ", last_call_text)  # 25文字ごとに空白が注入されている

    def test_i18n_value_error_and_type_resilience(self):
        """不揃いな波括弧や非文字列オブジェクトが渡されてもクラッシュしないことを検証"""
        # 不揃いな波括弧
        res = t("test: {unclosed", val=123)
        self.assertEqual(res, "test: {unclosed")

    def test_i18n_language_subscription(self):
        """言語変更イベントリスナーが正しく発火し解除できることを検証"""
        from i18n import subscribe_language_change, unsubscribe_language_change
        events = []

        def _listener(lang):
            events.append(lang)

        subscribe_language_change(_listener)
        try:
            set_language("en")
            self.assertIn("en", events)
            set_language("ja")
            self.assertIn("ja", events)
        finally:
            unsubscribe_language_change(_listener)

        # 解除後は発火しないこと
        count_before = len(events)
        set_language("en")
        self.assertEqual(len(events), count_before)

    def test_new_ui_keys_en_and_ja(self):
        """新規追加された menu.*, tray.*, radial.*, qr.*, dev.* キーが正常に引けることを検証"""
        set_language("en")
        self.assertEqual(t("ui.tray.show"), "🖥️ Summon Pet to Screen")
        self.assertEqual(t("ui.gui.header_cal"), "📔 Notebook")
        self.assertEqual(t("ui.radial.cal_title"), "📔 Integrated Notebook")
        self.assertEqual(t("ui.qr.title"), "📱 Mobile Desk Pet & Approval Cockpit")
        self.assertEqual(t("ui.dev.new_req"), "📱 Connection Request from New Device")
        self.assertEqual(t("ui.gui.fsm_coding", agent_name="Antigravity"), "🤖 [Antigravity] Writing code furiously! 🔥")

        set_language("ja")
        self.assertEqual(t("ui.tray.show"), "🖥️ ペットを画面に呼び出す")
        self.assertEqual(t("ui.gui.header_cal"), "📔 手帳")
        self.assertEqual(t("ui.radial.cal_title"), "📔 統合手帳（予定・TODO・知見）")
        self.assertEqual(t("ui.qr.title"), "📱 スマホDesk Pet ＆ 承認コクピット接続")
        self.assertEqual(t("ui.dev.new_req"), "📱 新しい端末からの接続要求")
        self.assertEqual(t("ui.gui.fsm_coding", agent_name="Antigravity"), "🤖 [Antigravity] 猛烈にコード書き込み中！🔥")



    def test_phase3_settings_and_tour_keys_en_and_ja(self):
        """Phase 3 (Settings, Tour, Briefing) の翻訳キーが ja/en とも正常に取得できることを検証"""
        set_language("en")
        self.assertEqual(t("ui.settings.tab_llm"), "AI Models")
        self.assertEqual(t("ui.settings.mcp_dialog_title"), "➕ Add New MCP Server")
        self.assertEqual(t("ui.settings.suggest_dialog_title"), "💡 Suggestion Source Settings")
        self.assertEqual(t("ui.settings.llm_sync_btn"), "⚡ Sync All Now")
        self.assertEqual(t("tour.settings_menu.title"), "🎉 Welcome! First, Right-Click")
        self.assertEqual(t("ui.tour.skip"), "Skip")
        self.assertEqual(t("briefing.mode.morning"), "☀️ Morning Briefing")

        set_language("ja")
        self.assertEqual(t("ui.settings.tab_llm"), "AIモデル設定")
        self.assertEqual(t("ui.settings.mcp_dialog_title"), "➕ 新規MCPサーバーの追加")
        self.assertEqual(t("ui.settings.suggest_dialog_title"), "💡 サジェストソース設定")
        self.assertEqual(t("ui.settings.llm_sync_btn"), "⚡ 今すぐ一括同期")
        self.assertEqual(t("tour.settings_menu.title"), "🎉 ようこそ！まずは右クリック")
        self.assertEqual(t("ui.tour.skip"), "スキップ")
        self.assertEqual(t("briefing.mode.morning"), "☀️ 朝会ブリーフィング")

    def test_tour_engine_multilang(self):
        """TourEngine が言語切り替えに応じて英語/日本語ステップを動的生成することを検証"""
        from tour_engine import get_default_tour_steps, TourEngine
        set_language("en")
        steps_en = get_default_tour_steps()
        self.assertEqual(len(steps_en), 3)
        self.assertIn("Welcome", steps_en[0].title)

        engine_en = TourEngine()
        engine_en.start()
        self.assertEqual(engine_en.current_step.title, "🎉 Welcome! First, Right-Click")

        set_language("ja")
        steps_ja = get_default_tour_steps()
        self.assertEqual(len(steps_ja), 3)
        self.assertIn("ようこそ", steps_ja[0].title)

        engine_ja = TourEngine()
        engine_ja.start()
        self.assertEqual(engine_ja.current_step.title, "🎉 ようこそ！まずは右クリック")

    def test_briefing_engine_multilang(self):
        """BriefingEngine が ja/en それぞれで正しい言語のレポートを生成することを検証"""
        from briefing_engine import generate_briefing
        set_language("en")
        report_en = generate_briefing(force_mode="morning")
        self.assertEqual(report_en.mode_label, "☀️ Morning Briefing")
        self.assertIn("Current Weather", report_en.formatted_markdown)

        set_language("ja")
        report_ja = generate_briefing(force_mode="morning")
        self.assertEqual(report_ja.mode_label, "☀️ 朝会ブリーフィング")
        self.assertIn("現在の天気", report_ja.formatted_markdown)

    def test_i18n_sticky_note_multilang(self):
        """付箋UI用辞書キーが ja/en で正しく切り替わることを検証"""
        set_language("ja")
        self.assertEqual(t("ui.sticky.title"), "📌 今日の最優先タスク")
        self.assertEqual(t("ui.sticky.placeholder"), "新しいタスクを急ぎ追加...")
        self.assertIn("保留中のタスクはありません", t("ui.sticky.no_tasks"))
        self.assertEqual(t("ui.sticky.badge_top"), "[最優先] ")
        self.assertEqual(t("ui.sticky.badge_urgent"), "[至急] ")
        self.assertEqual(t("ui.sticky.badge_important"), "[重要] ")

        set_language("en")
        self.assertEqual(t("ui.sticky.title"), "📌 Top Priority Tasks")
        self.assertEqual(t("ui.sticky.placeholder"), "Quick add urgent task...")
        self.assertIn("No pending tasks", t("ui.sticky.no_tasks"))
        self.assertEqual(t("ui.sticky.badge_top"), "[Top] ")
        self.assertEqual(t("ui.sticky.badge_urgent"), "[Urgent] ")
        self.assertEqual(t("ui.sticky.badge_important"), "[Important] ")

    def test_reload_language_from_env(self):
        """環境変数から言語が正しく初期化・再ロードされることを検証"""
        import os
        orig = os.environ.get("APP_LANGUAGE")
        try:
            os.environ["APP_LANGUAGE"] = "en"
            lang = i18n.reload_language_from_env()
            self.assertEqual(lang, "en")
            self.assertEqual(get_language(), "en")

            os.environ["APP_LANGUAGE"] = "ja"
            lang = i18n.reload_language_from_env()
            self.assertEqual(lang, "ja")
            self.assertEqual(get_language(), "ja")

            # 不正な言語コードの場合は既定 ja へフォールバック
            os.environ["APP_LANGUAGE"] = "invalid_lang"
            lang = i18n.reload_language_from_env()
            self.assertEqual(lang, "ja")
        finally:
            if orig is not None:
                os.environ["APP_LANGUAGE"] = orig
            elif "APP_LANGUAGE" in os.environ:
                del os.environ["APP_LANGUAGE"]
            set_language("ja")


if __name__ == "__main__":
    unittest.main()

