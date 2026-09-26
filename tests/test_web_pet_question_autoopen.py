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


if __name__ == "__main__":
    unittest.main()
