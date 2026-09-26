"""web_pet 質問シート自動オープン (案α) の規約テスト (A1・2026-09-26).

OS 通知タップ等で PWA が前面復帰した瞬間・および status 初回同期時に、
未回答の質問シートが自動で開くこと (タップ数削減・ID 63 の一部)。
"""

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestQuestionSheetAutoOpen(unittest.TestCase):
    """pet.js の質問シート自動オープン機構の存在と安全ガードを検証する."""

    def setUp(self) -> None:
        self.pet_js = (PROJECT_ROOT / "web_pet" / "pet.js").read_text(encoding="utf-8")

    def test_visibilitychange_auto_open_registered(self) -> None:
        """PWA 前面復帰 (visibilitychange) 時に自動オープンが走ること."""
        self.assertIn(
            "visibilitychange",
            self.pet_js,
            "pet.js に visibilitychange リスナーがありません。"
            "通知タップでの復帰時に質問シートを自動オープンしてください",
        )
        self.assertIn(
            "maybeAutoOpenQuestionSheet",
            self.pet_js,
            "pet.js に自動オープン関数 maybeAutoOpenQuestionSheet がありません",
        )

    def test_auto_open_is_once_per_request(self) -> None:
        """同一 request_id で複数回自動オープンしないガードがあること."""
        self.assertIn(
            "_autoOpenedQuestionId",
            self.pet_js,
            "自動オープンの重複防止ガード (_autoOpenedQuestionId) がありません",
        )

    def test_auto_open_only_for_question_type(self) -> None:
        """自動オープン対象が質問 (type: 'question') に限定されていること.

        承認要請 (approve/deny) はバナーのボタンで回答するため、
        シートの自動割り込み対象外とする。
        """
        self.assertIn(
            "req.type !== 'question'",
            self.pet_js,
            "自動オープンが質問型 (type: 'question') に限定されていません",
        )

    def test_auto_open_skips_choiceless_notification(self) -> None:
        """選択肢を持たない通知型質問は自動オープンしないこと.

        Antigravity tool_guard_hook や OpenCode plugin の「承認待ち heads-up」は
        choices=[] で送られ、スマホから回答できない（自由回答はPC側）。
        このようなカードが自動展開すると回答不能なシートが開いて割り込みになる
        （2026-09-26 ボス実感・スクショ報告）。自動オープンは「スマホで回答できる
        選択肢付き質問」に限定し、選択肢なしは従来どおりバナーのみにする。

        検証は pet.js 全文ではなく maybeAutoOpenQuestionSheet 関数本体に
        限定する（バナー表示側の同名比較で誤検知させない・Red 保証）。
        """
        start = self.pet_js.find("function maybeAutoOpenQuestionSheet")
        self.assertGreaterEqual(
            start,
            0,
            "pet.js に自動オープン関数 maybeAutoOpenQuestionSheet がありません",
        )
        fn_body = self.pet_js[start : start + 1500]
        self.assertIn(
            "choices.length > 0",
            fn_body,
            "maybeAutoOpenQuestionSheet に選択肢ガード (choices.length > 0) がありません。"
            "choices=[] の通知型質問 (Antigravity 承認待ち通知等) の自動展開は"
            "回答不能な割り込みになるため禁止します",
        )


if __name__ == "__main__":
    unittest.main()
