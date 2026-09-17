#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - PCメインループのアイドル待機レートの単体テスト (tests/test_main_loop_power.py)

タスク2 (P1-3, 2026-09-16 Cline): 省電力スプリント完遂。
自前 Tk/asyncio ループの待機を 100Hz (0.01s) から約30Hz (0.03s) へ**固定レートで緩和**し、
UI応答性を維持しつつメインスレッドのCPU常時占有率を削減する。
マジックナンバーを避けるため定数 MAIN_LOOP_IDLE_SLEEP_SEC を唯一の情報源とする契約を凍結する。

Note:
    実装は無操作を検出して動的に伸長する方式ではない（＝「適応型」ではない）。
    常時 0.03 秒待機の固定レートであり、ユーザー操作時の遅延上限は
    「1ティックの処理時間 + 30ms」となる (P3 2026-09-16 独立査読の指摘を受け明確化)。

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


class TestIdleSleepRate(unittest.TestCase):
    """P1-3: メインループ アイドル待機レート（固定30Hz）の契約"""

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
