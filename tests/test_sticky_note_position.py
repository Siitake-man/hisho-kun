#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - デスクトップ付箋 座標永続化の単体テスト (tests/test_sticky_note_position.py)

Phase 4.2 / B17 仕上げ (Cline実装): ui/sticky_note.py が character_config.json の
"sticky_note_pos" キーへ座標を保存・復元する機能を検証する。

TDD: 本テストは ui/sticky_note.py への実装適用と同時に作成した (Red → Green)。
実ファイル (ボスの character_config.json) は unittest.mock で一時パスへ差し替え、
絶対に汚染しない。
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import tkinter as tk

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import ui.sticky_note as sticky_note_module
from ui.sticky_note import DesktopStickyNote


class StickyNotePositionTestBase(unittest.TestCase):
    """一時設定ファイルと Tk ルートを用意する共通基底クラス"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.config_path = Path(self._tmp.name) / "character_config.json"

        # モジュール定数を実ファイルから一時パスへ差し替え (実設定ファイルの保護)
        patcher = mock.patch.object(sticky_note_module, "STICKY_CONFIG_PATH", self.config_path)
        patcher.start()
        self.addCleanup(patcher.stop)

        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("Tk を初期化できない環境のためスキップします")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

        # シングルトン状態をテスト毎に必ずリセットする
        DesktopStickyNote._instance = None
        self.addCleanup(setattr, DesktopStickyNote, "_instance", None)

    def _make_note(self) -> DesktopStickyNote:
        """テスト用の DesktopStickyNote インスタンスを生成する。"""
        return DesktopStickyNote(self.root)


class TestStickyPositionPersistence(StickyNotePositionTestBase):
    """座標の保存・復元 (Read-Modify-Write) の検証"""

    def test_save_position_writes_key_and_preserves_existing_keys(self) -> None:
        """保存時に既存キー (bond_xp 等) を破壊せず sticky_note_pos を追記すること"""
        self.config_path.write_text(
            json.dumps({"current_character": "kyle", "bond_xp": 502}, ensure_ascii=False),
            encoding="utf-8",
        )
        note = self._make_note()
        note._pos_x = 180
        note._pos_y = 240

        note._save_position()

        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(data["sticky_note_pos"], {"x": 180, "y": 240})
        self.assertEqual(data["current_character"], "kyle")
        self.assertEqual(data["bond_xp"], 502)

    def test_save_position_creates_file_when_missing(self) -> None:
        """設定ファイルが存在しない場合でも新規作成できること"""
        note = self._make_note()
        note._pos_x = 100
        note._pos_y = 120

        note._save_position()

        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(data["sticky_note_pos"], {"x": 100, "y": 120})

    def test_init_restores_saved_position(self) -> None:
        """保存済み座標が初期化時に復元されること (次回起動時の復元)"""
        self.config_path.write_text(
            json.dumps({"sticky_note_pos": {"x": 150, "y": 250}}, ensure_ascii=False),
            encoding="utf-8",
        )
        note = self._make_note()
        self.assertEqual(note._pos_x, 150)
        self.assertEqual(note._pos_y, 250)

    def test_on_drag_end_persists_position(self) -> None:
        """ドラッグ終了時に現在位置が保存されること"""
        note = self._make_note()
        note._pos_x = 200
        note._pos_y = 300

        note._on_drag_end(None)

        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(data["sticky_note_pos"], {"x": 200, "y": 300})


class TestStickyPositionRobustness(StickyNotePositionTestBase):
    """破損ファイル・画面外座標に対する Fail-Safe の検証"""

    def test_load_returns_none_when_file_missing(self) -> None:
        """設定ファイルが存在しない場合は None を返すこと"""
        note = self._make_note()
        self.assertIsNone(note._load_saved_position())

    def test_load_returns_none_when_json_corrupted(self) -> None:
        """JSON が破損している場合は例外を出さず None へフォールバックすること"""
        self.config_path.write_text("{ 破損したJSON !!!", encoding="utf-8")
        note = self._make_note()
        self.assertIsNone(note._load_saved_position())

    def test_load_ignores_invalid_position_values(self) -> None:
        """負の座標は無視して None を返すこと (不正値ガード)"""
        self.config_path.write_text(
            json.dumps({"sticky_note_pos": {"x": -100, "y": 50}}, ensure_ascii=False),
            encoding="utf-8",
        )
        note = self._make_note()
        self.assertIsNone(note._load_saved_position())

    def test_clamp_pulls_offscreen_position_into_view(self) -> None:
        """画面外の保存座標が可視範囲へ補正されること (モニタ構成変更対策)"""
        note = self._make_note()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        clamped_x, clamped_y = note._clamp_to_screen(-5000, -5000)
        self.assertGreaterEqual(clamped_x, -(note._width - 60))
        self.assertGreaterEqual(clamped_y, 0)

        clamped_x2, clamped_y2 = note._clamp_to_screen(screen_w + 5000, screen_h + 5000)
        self.assertLessEqual(clamped_x2, screen_w - 60)
        self.assertLessEqual(clamped_y2, screen_h - 60)


if __name__ == "__main__":
    unittest.main()