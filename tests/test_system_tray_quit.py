#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - タスクトレイ終了経路の単体テスト (tests/test_system_tray_quit.py)

トレイメニュー「❌ 終了」は root.quit() を呼んではならない:
本アプリは mainloop() を使わない自前ループ (main.async_mainloop) で動くため
root.quit() は事実上 no-op となり、トレイだけ消えてプロセスが残存する
(多重起動検知の誤発火・2026-09-09 発見)。正式終了経路は gui.quit_app (トレイ停止
＋quiet_destroy) であり、トレイ側はそれへ委譲する契約を凍結する。

TDD: request_quit() が無い状態では Red で落ちる。
"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.system_tray import SystemTrayManager


class _FakeGui:
    """post_action / quit_app のみを模倣する GUI スタブ。"""

    def __init__(self) -> None:
        self.posted: list = []
        self.quit_app_called = False

    def post_action(self, callback, *args, **kwargs) -> None:
        self.posted.append((callback, args, kwargs))

    def quit_app(self) -> None:
        self.quit_app_called = True


class TestTrayQuitRequest(unittest.TestCase):
    """トレイ終了要求の正式経路委譲契約"""

    def test_request_quit_posts_quit_app_not_root_quit(self) -> None:
        """終了要求は gui.quit_app を post_action で委譲すること (root.quit 禁止)"""
        gui = _FakeGui()
        manager = SystemTrayManager(gui)

        manager.request_quit()

        self.assertEqual(len(gui.posted), 1)
        callback = gui.posted[0][0]
        # post_action されたコールバックを実行すると quit_app が呼ばれる
        callback()
        self.assertTrue(gui.quit_app_called)

    def test_request_quit_stops_tray_icon(self) -> None:
        """終了要求でトレイアイコンが停止 (破棄) されること"""
        gui = _FakeGui()
        manager = SystemTrayManager(gui)
        manager._icon = object()  # 稼働中アイコンを模倣

        manager.request_quit()

        self.assertIsNone(manager._icon)

    def test_request_quit_is_idempotent_without_icon(self) -> None:
        """アイコン未起動でも終了要求が例外を漏らさないこと (Fail-Safe)"""
        gui = _FakeGui()
        manager = SystemTrayManager(gui)

        manager.request_quit()  # 例外を raise しないこと

        self.assertEqual(len(gui.posted), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
