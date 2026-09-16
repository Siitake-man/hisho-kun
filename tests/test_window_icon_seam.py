#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - ウィンドウアイコン適用 Seam の単体テスト (tests/test_window_icon_seam.py)

タスク0 (2026-09-16 Cline): 秘書くんアイコン化。
メインウィンドウ/各ダイアログ (手帳・設定・QR) へ同一アイコンを例外安全に適用する。
Windows の iconbitmap を第一候補とし、失敗時は iconphoto へフォールバックする
契約を凍結する (片方しか対応しない環境でも起動を止めない)。

TDD: ui/window_icon.py が無い状態では Red で落ちる。
"""

import sys
import tkinter as tk
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.window_icon import (  # noqa: E402
    ICON_ICO_PATH,
    ICON_PNG_PATH,
    apply_window_icon,
)


class _FakeWindow:
    """iconbitmap / iconphoto のみを模倣するウィンドウスタブ。"""

    def __init__(self, bitmap_fails: bool = False, photo_fails: bool = False) -> None:
        self.bitmap_calls: list = []
        self.photo_calls: list = []
        self._bitmap_fails = bitmap_fails
        self._photo_fails = photo_fails

    def iconbitmap(self, *args, **kwargs):
        self.bitmap_calls.append((args, kwargs))
        if self._bitmap_fails:
            raise tk.TclError("iconbitmap unavailable (模擬)")

    def iconphoto(self, *args, **kwargs):
        self.photo_calls.append((args, kwargs))
        if self._photo_fails:
            raise tk.TclError("iconphoto unavailable (模擬)")


class TestIconAssets(unittest.TestCase):
    """アイコンアセットの実在契約"""

    def test_ico_asset_exists(self) -> None:
        """.ico (EXE/ウィンドウ用) が存在すること"""
        self.assertTrue(ICON_ICO_PATH.is_file(), f"見つかりません: {ICON_ICO_PATH}")

    def test_png_asset_exists(self) -> None:
        """フォールバック用 PNG (秘書くんドット絵) が存在すること"""
        self.assertTrue(ICON_PNG_PATH.is_file(), f"見つかりません: {ICON_PNG_PATH}")
        self.assertEqual(ICON_PNG_PATH.name, "idle_1.png")
        self.assertEqual(ICON_PNG_PATH.parent.name, "hisho")


class TestApplyWindowIcon(unittest.TestCase):
    """apply_window_icon のフォールバック契約"""

    @classmethod
    def setUpClass(cls) -> None:
        # iconphoto は PIL の PhotoImage を使うため実 Tk ルートが必要。
        # テスト毎の Tk 生成/破棄は Tcl の後始末レースを招くためクラスで1回だけ作る。
        try:
            cls.root = tk.Tk()
        except tk.TclError:
            cls.root = None
        else:
            cls.root.withdraw()

    @classmethod
    def tearDownClass(cls) -> None:
        if getattr(cls, "root", None) is not None:
            try:
                cls.root.destroy()
            except tk.TclError:
                pass
            cls.root = None

    def setUp(self) -> None:
        if self.__class__.root is None:
            self.skipTest("Tk を初期化できない環境のためスキップします")

    def test_prefers_iconbitmap(self) -> None:
        """第一候補として iconbitmap が呼ばれること"""
        window = _FakeWindow()

        self.assertTrue(apply_window_icon(window))

        self.assertEqual(len(window.bitmap_calls), 1)
        self.assertEqual(len(window.photo_calls), 0)

    def test_falls_back_to_iconphoto(self) -> None:
        """iconbitmap 失敗時は iconphoto(False, image) へフォールバックすること"""
        window = _FakeWindow(bitmap_fails=True)

        self.assertTrue(apply_window_icon(window))

        self.assertEqual(len(window.photo_calls), 1)
        args, _kwargs = window.photo_calls[0]
        self.assertFalse(args[0])

    def test_returns_false_when_all_paths_fail(self) -> None:
        """全候補が失敗しても例外を漏らさず False を返すこと (起動継続)"""
        window = _FakeWindow(bitmap_fails=True, photo_fails=True)

        self.assertFalse(apply_window_icon(window))

    def test_returns_false_for_non_window_object(self) -> None:
        """ウィンドウ風オブジェクトでなくてもクラッシュしないこと (Fail-Safe)"""
        self.assertFalse(apply_window_icon(object()))

    def test_keeps_reference_to_photo_image(self) -> None:
        """iconphoto 用画像は GC されないようウィンドウ側に保持されること"""
        window = _FakeWindow(bitmap_fails=True)

        apply_window_icon(window)

        self.assertTrue(hasattr(window, "_neo_hisho_icon_photo"))

    def test_real_tk_window_receives_icon(self) -> None:
        """実 Tk ウィンドウへ .ico アイコンを例外なく適用できること (Windows 実機確認)

        Note:
            Tk の ``wm iconbitmap`` は Windows で設定後の値を返さない
            (問い合わせると空文字) ため、ここでは「実際の Tk に対して
            iconbitmap が成功した」ことを戻り値 True で確認する。
            呼び出し内容の検証は _FakeWindow 側のテストで担保済み。
        """
        root = self.__class__.root
        self.assertTrue(apply_window_icon(root))


class TestIconAppliedToWindows(unittest.TestCase):
    """主要ウィンドウ/ダイアログへの適用漏れがないことの回帰契約"""

    def test_gui_and_dialogs_call_apply_window_icon(self) -> None:
        """gui.py・手帳・設定・QRダイアログが Seam を呼んでいること"""
        targets = ("gui.py", "ui/calendar_window.py", "ui/settings_window.py", "ui/qr_dialog.py")
        for rel in targets:
            with self.subTest(target=rel):
                source = (PROJECT_ROOT / rel).read_text(encoding="utf-8")
                self.assertIn("apply_window_icon", source, f"{rel} でアイコン未適用")


if __name__ == "__main__":
    unittest.main(verbosity=2)
