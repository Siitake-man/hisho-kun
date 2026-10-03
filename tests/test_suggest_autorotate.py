"""サジェストカードの自動ローテーション（パラパラ送り・20秒周期）契約テスト."""

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestSuggestAutoRotateContract(unittest.TestCase):
    """web_pet/pet_ui.js のサジェスト自動ローテーション実装を検証する静的契約テスト."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.pet_ui_js = (PROJECT_ROOT / "web_pet" / "pet_ui.js").read_text(encoding="utf-8")

    def test_autorotate_timer_exists(self) -> None:
        """20秒ごとのサジェスト自動ローテーションタイマーが定義されていること."""
        self.assertIn(
            "SUGGEST_AUTOROTATE_INTERVAL_MS",
            self.pet_ui_js,
            "pet_ui.js に SUGGEST_AUTOROTATE_INTERVAL_MS が定義されていません",
        )
        self.assertIn(
            "tickSuggestAutoRotate",
            self.pet_ui_js,
            "pet_ui.js に tickSuggestAutoRotate 関数が定義されていません",
        )

    def test_autorotate_has_energy_and_ux_guards(self) -> None:
        """画面非表示(document.hidden)およびモーダル展開中の誤回転防止ガードが存在すること."""
        self.assertIn(
            "document.hidden",
            self.pet_ui_js,
            "tickSuggestAutoRotate に document.hidden による省電力ガードがありません",
        )
        self.assertIn(
            "bottom-sheet",
            self.pet_ui_js,
            "tickSuggestAutoRotate に bottom-sheet オープン時のスキップガードがありません",
        )

    def test_user_interaction_resets_timer(self) -> None:
        """手動操作（nextSuggest / prevSuggest / スワイプ）時にタイマークールダウンがリセットされること."""
        self.assertIn(
            "resetSuggestRotateTimer",
            self.pet_ui_js,
            "pet_ui.js に resetSuggestRotateTimer 関数が定義されていません",
        )


if __name__ == "__main__":
    unittest.main()
