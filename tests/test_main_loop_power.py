#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - PCメインループ適応型スリープの単体テスト (tests/test_main_loop_power.py)

タスク2 (P1-3, 2026-09-16 Cline): 省電力スプリント完遂。
ユーザー無操作 (アイドル) 時に 100Hz (0.01s) で回していた自前 Tk/asyncio ループを
約30Hz (0.03s) へ緩和し、UI応答性を維持しつつメインスレッドのCPU常時占有率を
削減する。マジックナンバーを避けるため定数 MAIN_LOOP_IDLE_SLEEP_SEC を
唯一の情報源とする契約を凍結する。

TDD: MAIN_LOOP_IDLE_SLEEP_SEC が未定義の状態では Red で落ちる。
"""

import inspect
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import main  # noqa: E402


class TestAdaptiveIdleSleep(unittest.TestCase):
    """P1-3: メインループ アイドル待機の契約"""

    def test_idle_sleep_constant_is_30hz(self) -> None:
        """アイドル待機が約30Hz (0.03秒) に緩和されていること"""
        self.assertEqual(main.MAIN_LOOP_IDLE_SLEEP_SEC, 0.03)

    def test_idle_sleep_constant_is_used_by_mainloop(self) -> None:
        """async_mainloop が定数を参照していること (マジックナンバー禁止)"""
        source = inspect.getsource(main.async_mainloop)
        self.assertIn("MAIN_LOOP_IDLE_SLEEP_SEC", source)

    def test_legacy_100hz_sleep_is_removed(self) -> None:
        """旧 0.01 秒 (100Hz) のベタ書き待機が残っていないこと"""
        source = inspect.getsource(main.async_mainloop)
        self.assertNotIn("asyncio.sleep(0.01)", source)

    def test_ui_update_still_runs_every_tick(self) -> None:
        """アイドル待機を緩めても UI イベント処理・再描画は毎ティック実行されること"""
        source = inspect.getsource(main.async_mainloop)
        self.assertIn("process_action_queue", source)
        self.assertIn("root.update", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
