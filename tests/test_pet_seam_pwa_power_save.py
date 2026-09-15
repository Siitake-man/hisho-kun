#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - PWA画面非表示時省電力化 (P0-2) の整合性テスト (tests/test_pet_seam_pwa_power_save.py)

Page Visibility API (document.hidden) に連動した省電力ポーリング間引き（2秒➔30秒）
および画面復帰時のタイマー多重発火防止・即時同期ロジックを検証する。

検証項目:
  1. web_pet/pet.js に FETCH_HIDDEN_INTERVAL (30000ms) 定数が定義されていること
  2. getNextFetchInterval() で document.hidden を判定し、非表示時に 30000ms を返すこと
  3. タイマー二重発火防止用ハンドル (pollingTimerId 等) が導入され、clearTimeout が適切に呼ばれていること
  4. visibilitychange リスナーで画面復帰時 (!document.hidden) に即時フェッチおよびタイマー初期化が行われること
"""

import re
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestPetSeamPwaPowerSave(unittest.TestCase):
    """PWA画面非表示時の省電力ポーリングおよび画面復帰処理の整合性を検証する"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.pet_js_path = PROJECT_ROOT / "web_pet" / "pet.js"
        cls.assertTrue(cls.pet_js_path.is_file(), "web_pet/pet.js が存在しません")
        cls.content = cls.pet_js_path.read_text(encoding="utf-8")

    def test_01_fetch_hidden_interval_constant_exists(self) -> None:
        """FETCH_HIDDEN_INTERVAL 定数が 30000 (30秒) で定義されていること"""
        pattern = r"const\s+FETCH_HIDDEN_INTERVAL\s*=\s*30000;"
        self.assertRegex(
            self.content,
            pattern,
            "pet.js 内に 'const FETCH_HIDDEN_INTERVAL = 30000;' が見つかりません"
        )

    def test_02_get_next_fetch_interval_handles_document_hidden(self) -> None:
        """getNextFetchInterval 関数内で document.hidden を判定し、非表示時は FETCH_HIDDEN_INTERVAL を返すこと"""
        # getNextFetchInterval 関数の抽出
        fn_match = re.search(r"function\s+getNextFetchInterval\s*\(\)\s*\{([\s\S]*?)\}", self.content)
        self.assertIsNotNone(fn_match, "getNextFetchInterval 関数が定義されていません")
        fn_body = fn_match.group(1)

        self.assertIn(
            "document.hidden",
            fn_body,
            "getNextFetchInterval 内で document.hidden の判定が行われていません"
        )
        self.assertIn(
            "FETCH_HIDDEN_INTERVAL",
            fn_body,
            "getNextFetchInterval 内で FETCH_HIDDEN_INTERVAL が返却されていません"
        )

    def test_03_timer_handle_and_clear_timeout_exists(self) -> None:
        """ポーリングタイマー多重発火防止用のハンドルと clearTimeout が配備されていること"""
        # pollingTimerId 変数の宣言
        self.assertRegex(
            self.content,
            r"let\s+pollingTimerId\s*=",
            "タイマー管理変数 'let pollingTimerId' が宣言されていません"
        )
        # clearTimeout(pollingTimerId) の呼び出し
        self.assertIn(
            "clearTimeout(pollingTimerId)",
            self.content,
            "タイマーリセット 'clearTimeout(pollingTimerId)' が呼ばれていません"
        )

    def test_04_visibilitychange_resets_timer_and_fetches(self) -> None:
        """visibilitychange イベントで画面復帰時に即時同期とタイマーリセットが行われること"""
        # visibilitychange リスナーの存在確認
        self.assertIn(
            "'visibilitychange'",
            self.content,
            "visibilitychange イベントリスナーが存在しません"
        )
        self.assertIn(
            "!document.hidden",
            self.content,
            "visibilitychange 内で !document.hidden (復帰) の判定がありません"
        )
        self.assertIn(
            "triggerPollingStep",
            self.content,
            "復帰時またはタイマー初期化で triggerPollingStep が使用されていません"
        )


if __name__ == "__main__":
    unittest.main()
