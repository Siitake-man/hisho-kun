#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - Tkinter/CustomTkinter 静かな終了処理の単体テスト (tests/test_tk_teardown.py)

Jules 夜間タスクB (2026-09-06) の根治を凍結する:
CustomTkinter の ScalingTracker / AppearanceModeTracker が root 破棄後に
自己再スケジュールした after コールバックを残し、
``invalid command name "...check_dpi_scaling" / "...update"`` が stderr に漏出する
問題の対策 (トラッカー停止・未消化 after のキャンセル・静かな破棄) を検証する。

TDD: 実装 (ui/tk_teardown.py) が存在しない状態では本テストは Red で落ちる。
"""

import sys
import types
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.tk_teardown import (
    cancel_pending_after_callbacks,
    dedupe_tcl_commands,
    quiet_destroy,
    stop_ctk_background_trackers,
)


def _noop() -> None:
    """after タイマー用の何もしないコールバック。"""


def _is_alive(root: tk.Misc) -> bool:
    """root が生存しているかを安全に判定する (破棄済みは False 扱い)。

    tk.Tk.destroy() 後の winfo_exists() は、Tcl アプリケーション状態の
    破棄タイミング (GC・interp 状態) により
    「TclError (application has been destroyed) を raise」する場合と
    「0 (False) を返す」場合の両方が起こり得る非決定動作のため、
    両者をまとめて「生存していない」と判定する。

    Args:
        root: 判定対象の Tk/Toplevel。

    Returns:
        bool: 生存中の場合 True。破棄済み (例外 or False) の場合 False。
    """
    try:
        return bool(root.winfo_exists())
    except tk.TclError:
        return False


class TestStopCtkBackgroundTrackers(unittest.TestCase):
    """CustomTkinter クラスレベル監視ループの停止契約検証"""

    def test_clears_scaling_tracker_state(self) -> None:
        """ScalingTracker の window 辞書とループ実行フラグが初期化されること"""
        from customtkinter.windows.widgets.scaling.scaling_tracker import ScalingTracker

        ScalingTracker.window_widgets_dict["__dummy__"] = []
        ScalingTracker.window_dpi_scaling_dict["__dummy__"] = 1.5
        ScalingTracker.update_loop_running = True

        stop_ctk_background_trackers()

        self.assertEqual(ScalingTracker.window_widgets_dict, {})
        self.assertEqual(ScalingTracker.window_dpi_scaling_dict, {})
        self.assertFalse(ScalingTracker.update_loop_running)

    def test_clears_appearance_mode_tracker_state(self) -> None:
        """AppearanceModeTracker の app/callback リストとループ実行フラグが初期化されること"""
        from customtkinter.windows.widgets.appearance_mode.appearance_mode_tracker import (
            AppearanceModeTracker,
        )

        AppearanceModeTracker.app_list.append("__dummy__")
        AppearanceModeTracker.callback_list.append(lambda mode: None)
        AppearanceModeTracker.update_loop_running = True

        stop_ctk_background_trackers()

        self.assertEqual(AppearanceModeTracker.app_list, [])
        self.assertEqual(AppearanceModeTracker.callback_list, [])
        self.assertFalse(AppearanceModeTracker.update_loop_running)

    def test_tolerates_missing_customtkinter(self) -> None:
        """customtkinter が import 不可能でも例外を漏らさないこと (Fail-Safe)"""
        with mock.patch.dict(
            sys.modules,
            {
                "customtkinter": None,
                "customtkinter.windows": None,
                "customtkinter.windows.widgets": None,
                "customtkinter.windows.widgets.scaling": None,
                "customtkinter.windows.widgets.scaling.scaling_tracker": None,
                "customtkinter.windows.widgets.appearance_mode": None,
                "customtkinter.windows.widgets.appearance_mode.appearance_mode_tracker": None,
            },
        ):
            stop_ctk_background_trackers()  # 例外を raise しないこと


class TestAfterCancellationAndQuietDestroy(unittest.TestCase):
    """未消化 after のキャンセルと静かな破棄の契約検証 (実 Tk を使用)"""

    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self._safe_destroy)

    def _safe_destroy(self) -> None:
        """tearDown 用の二重破棄安全な root 破棄。"""
        try:
            if self.root.winfo_exists():
                self.root.destroy()
        except tk.TclError:
            pass

    def test_cancel_pending_after_callbacks_clears_timers(self) -> None:
        """未消化の after タイマーが全件キャンセルされ、after info が空になること"""
        self.root.after(50, _noop)
        self.root.after(80, _noop)

        cancelled = cancel_pending_after_callbacks(self.root)

        self.assertGreaterEqual(cancelled, 2)
        self.assertEqual(list(self.root.tk.call("after", "info")), [])

    def test_cancel_returns_zero_for_destroyed_root(self) -> None:
        """破棄済み root に対しても例外を漏らさず 0 を返すこと (Fail-Safe)"""
        self.root.destroy()

        self.assertEqual(cancel_pending_after_callbacks(self.root), 0)

    def test_dedupe_removes_duplicate_tcl_command_names(self) -> None:
        """_tclCommands の同名重複が排除されること (destroy 中断の回避)"""
        fake_root = types.SimpleNamespace(
            _tclCommands=[
                "2715320140288check_dpi_scaling",
                "2715320023616update",
                "2715320140288check_dpi_scaling",
                "2715320140288check_dpi_scaling",
            ]
        )

        removed = dedupe_tcl_commands(fake_root)

        self.assertEqual(removed, 2)
        self.assertEqual(
            fake_root._tclCommands,
            ["2715320140288check_dpi_scaling", "2715320023616update"],
        )

    def test_dedupe_returns_zero_without_duplicates(self) -> None:
        """重複なし・属性不在の場合は 0 を返しリストを変更しないこと"""
        clean = types.SimpleNamespace(_tclCommands=["a", "b"])
        self.assertEqual(dedupe_tcl_commands(clean), 0)
        self.assertEqual(clean._tclCommands, ["a", "b"])
        self.assertEqual(dedupe_tcl_commands(types.SimpleNamespace()), 0)

    def test_quiet_destroy_destroys_root(self) -> None:
        """quiet_destroy 後に root が生存していないこと"""
        self.root.after(50, _noop)

        quiet_destroy(self.root)

        # 破棄後の winfo_exists() は「TclError raise」と「False 返却」の
        # 両方が起こり得る非決定動作のため、_is_alive で決定論的に判定する。
        self.assertFalse(_is_alive(self.root))


if __name__ == "__main__":
    unittest.main(verbosity=2)
