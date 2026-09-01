#!/usr/bin/env python3
"""
ネオ秘書くん - オンボーディングツアーの単体テスト (test_tour_engine.py)

2026-09-01 3周レビュー P3対応（7ステップ → 3ステップ凝縮）に伴い、
ツアーの構造契約を検証します。

実行:
    venv\\Scripts\\python.exe -m unittest tests.test_tour_engine
"""

import sys
import unittest
from pathlib import Path

# tests/ 配下からプロジェクトルートを import パスへ追加
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import tour_engine  # noqa: E402
from tour_engine import TourEngine, DEFAULT_TOUR_STEPS  # noqa: E402


class TestDefaultTourSteps(unittest.TestCase):
    """デフォルトツアーの構造契約検証。"""

    def test_tour_is_exactly_3_steps(self) -> None:
        """ツアーは認知摩擦低減のためちょうど3ステップである。"""
        self.assertEqual(len(DEFAULT_TOUR_STEPS), 3)

    def test_step_ids_follow_spec(self) -> None:
        """ステップIDは引き継ぎ書仕様 (設定/スマホQR/会話・手帳) に一致する。"""
        ids = [s.id for s in DEFAULT_TOUR_STEPS]
        self.assertEqual(ids, ["settings_menu", "mobile_qr", "chat_notebook"])

    def test_every_step_has_nonempty_title_and_text(self) -> None:
        """全ステップにタイトルと本文が設定されている。"""
        for step in DEFAULT_TOUR_STEPS:
            self.assertTrue(step.title.strip(), f"title が空: {step.id}")
            self.assertTrue(step.text.strip(), f"text が空: {step.id}")


class TestTourEngineContract(unittest.TestCase):
    """TourEngine 状態機械の振る舞い検証 (3ステップ版)。"""

    def setUp(self) -> None:
        self.engine = TourEngine()

    def test_total_steps_is_3(self) -> None:
        """total_steps が 3 を返す。"""
        self.assertEqual(self.engine.total_steps, 3)

    def test_walk_through_fires_complete(self) -> None:
        """3回 next() で完了コールバックが発火する。"""
        completed = []
        self.engine.set_on_complete(lambda: completed.append(True))
        self.engine.start()
        self.assertTrue(self.engine.next())
        self.assertTrue(self.engine.next())
        # 最終ステップで next() → 完了
        self.assertFalse(self.engine.next())
        self.assertEqual(completed, [True])

    def test_step_ids_mapped_in_gui_target_rect(self) -> None:
        """全ステップIDが gui._get_tour_target_rect のハイライト分岐に対応する。

        tour_engine と gui のID契約を検証し、未知IDが
        ペット中央フォールバックに沈む退化を防ぐ (推測コード禁止)。
        """
        gui_src = (PROJECT_ROOT / "gui.py").read_text(encoding="utf-8")
        for step in DEFAULT_TOUR_STEPS:
            self.assertIn(
                f'step_id == "{step.id}"',
                gui_src,
                f"gui.py _get_tour_target_rect に {step.id} の分岐が未定義です",
            )

    def test_no_dead_highlight_callbacks(self) -> None:
        """gui.py が消費しない highlight_callback をステップに残さない (デッド契約防止)。

        gui._on_tour_step は title/text のみを使用し、ハイライトは
        _get_tour_target_rect (step.id 基準) で行うため、
        highlight_callback に文字列を設定しても呼ばれない。
        """
        for step in DEFAULT_TOUR_STEPS:
            self.assertIsNone(
                step.highlight_callback,
                f"{step.id} に未接続の highlight_callback が残っています",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
