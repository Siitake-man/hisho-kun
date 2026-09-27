#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_gui_window_transparency.py

gui.apply_window_transparency の OS 別分岐を検証する。

背景: `-transparentcolor` は Windows 専用の Tk 属性で、Linux/macOS では
TclError によりアプリが起動不能になっていた。OS ごとに安全に分岐し、
どの経路でも例外で起動を止めないことを保証する。
"""

import sys
import tkinter as tk
import unittest
from unittest import mock

import gui


class TestApplyWindowTransparencyBranches(unittest.TestCase):
    """モックの root で OS 別の呼び出し内容を検証する（ディスプレイ不要）。"""

    def test_windows_keeps_transparentcolor_key(self) -> None:
        """Windows では従来どおり #FF00FF を透過色キーに設定すること。"""
        root = mock.MagicMock()
        color = gui.apply_window_transparency(root, platform="win32")
        self.assertEqual(color, gui.WINDOWS_TRANSPARENT_COLOR)
        root.attributes.assert_called_once_with("-transparentcolor", gui.WINDOWS_TRANSPARENT_COLOR)
        root.config.assert_called_once_with(bg=gui.WINDOWS_TRANSPARENT_COLOR)

    def test_linux_skips_transparentcolor(self) -> None:
        """Linux では -transparentcolor を呼ばず、フォールバック背景色を返すこと。"""
        root = mock.MagicMock()
        color = gui.apply_window_transparency(root, platform="linux")
        self.assertEqual(color, gui.FALLBACK_BACKGROUND_COLOR)
        for call in root.attributes.call_args_list:
            self.assertNotIn("-transparentcolor", call.args)
        root.config.assert_called_once_with(bg=gui.FALLBACK_BACKGROUND_COLOR)

    def test_macos_uses_system_transparent(self) -> None:
        """macOS では -transparent + systemTransparent を使うこと。"""
        root = mock.MagicMock()
        color = gui.apply_window_transparency(root, platform="darwin")
        self.assertEqual(color, "systemTransparent")
        root.attributes.assert_called_once_with("-transparent", True)
        root.config.assert_called_once_with(bg="systemTransparent")

    def test_macos_falls_back_when_unsupported(self) -> None:
        """macOS で透過設定が TclError になっても例外を出さず透過なしで続行すること。"""
        root = mock.MagicMock()
        root.attributes.side_effect = tk.TclError('bad attribute "-transparent"')
        color = gui.apply_window_transparency(root, platform="darwin")
        self.assertEqual(color, gui.FALLBACK_BACKGROUND_COLOR)

    def test_windows_falls_back_when_unsupported(self) -> None:
        """Windows で透過設定が失敗しても起動を止めないこと。"""
        root = mock.MagicMock()
        root.attributes.side_effect = tk.TclError("unsupported")
        color = gui.apply_window_transparency(root, platform="win32")
        self.assertEqual(color, gui.FALLBACK_BACKGROUND_COLOR)


class TestApplyWindowTransparencyRealTk(unittest.TestCase):
    """実際の Tk ルートで、現在の OS の経路が TclError を出さないことを検証する。

    Linux CI では xvfb-run 上で実行される（ディスプレイが無い環境ではスキップ）。
    """

    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as e:
            self.skipTest(f"ディスプレイが無い環境のためスキップ: {e}")
        self.root.withdraw()

    def tearDown(self) -> None:
        self.root.destroy()

    def test_current_platform_does_not_raise(self) -> None:
        """実行中 OS の既定経路で例外が出ず、子ウィジェットに使える色が返ること。"""
        color = gui.apply_window_transparency(self.root)
        frame = tk.Frame(self.root, bg=color)  # 返り値が Tk で有効な色であること
        self.assertEqual(frame.cget("bg"), color)

    @unittest.skipUnless(sys.platform.startswith("linux"), "X11 Tk 上で darwin 経路のフォールバックを検証する")
    def test_darwin_branch_falls_back_on_x11_tk(self) -> None:
        """X11 Tk（-transparent 非対応）で darwin 経路を通しても例外を出さずフォールバックすること。"""
        color = gui.apply_window_transparency(self.root, platform="darwin")
        self.assertEqual(color, gui.FALLBACK_BACKGROUND_COLOR)
        tk.Frame(self.root, bg=color)


if __name__ == "__main__":
    unittest.main()
