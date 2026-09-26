"""web_pet 初期スプライト表示バグの規約テスト (S3・2026-09-26).

初回接続時に未採用キャラ (seal/kinoko/marmot) が表示される事故の恒久防止:
  1. index.html の #pet-sprite 初期 src はロースター登録キャラのみを指すこと
  2. pet.js は /api/status 同期時にキャラID一致でも初回1回は sprite を必ず
     再確定すること (HTML 静的初期値の誤りを自己修復する)
"""

import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# character_manager.py の CHARACTERS_DATA に登録されている正規キャラ ID
# (kinoko / seal / marmot は「一時ロースター除外中」・ID 36 関連の運用方針)
ROSTER_CHARACTER_IDS = ("hisho", "kyle")
FORBIDDEN_CHARACTER_IDS = ("seal", "kinoko", "marmot")


class TestInitialPetSprite(unittest.TestCase):
    """index.html 初期 sprite と pet.js 初回同期の規約検証."""

    def test_initial_sprite_src_points_to_roster_character(self) -> None:
        """index.html の #pet-sprite 初期 src がロースター登録キャラを指すこと."""
        index_html = (PROJECT_ROOT / "web_pet" / "index.html").read_text(encoding="utf-8")
        match = re.search(
            r'<img id="pet-sprite"[^>]*src="([^"]+)"',
            index_html,
        )
        self.assertIsNotNone(match, "index.html に #pet-sprite の img タグが見つかりません")
        src = match.group(1)

        for forbidden in FORBIDDEN_CHARACTER_IDS:
            self.assertNotIn(
                f"/assets/dot/{forbidden}/",
                src,
                f"初期スプライトが未採用キャラ ({forbidden}) を指しています。"
                "ロースター登録キャラのみを初期値にしてください",
            )
        self.assertTrue(
            any(f"/assets/dot/{allowed}/" in src for allowed in ROSTER_CHARACTER_IDS),
            f"初期スプライトの src ({src}) がロースター登録キャラ "
            f"{ROSTER_CHARACTER_IDS} のいずれでもありません",
        )

    def test_pet_js_resyncs_sprite_on_first_status_sync(self) -> None:
        """pet.js が初回 status 同期時に sprite を必ず再確定する機構を持つこと.

        キャラ ID が一致する場合でも、HTML 静的初期 src (誤りの可能性) を
        status 応答の正規キャラで上書きする初回同期フラグを必須とする。
        """
        pet_js = (PROJECT_ROOT / "web_pet" / "pet.js").read_text(encoding="utf-8")
        self.assertIn(
            "spriteSynced",
            pet_js,
            "pet.js に初回 sprite 同期フラグ (spriteSynced) が存在しません。"
            "status 受信時にキャラ一致でも1度は sprite を再確定してください",
        )
        self.assertNotIn(
            '"/assets/dot/seal/',
            pet_js,
            "pet.js に未採用キャラ (seal) の直接参照が含まれています",
        )


if __name__ == "__main__":
    unittest.main()
