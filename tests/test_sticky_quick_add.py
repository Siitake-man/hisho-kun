#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - 付箋クイック追加 ＆ タスク描画の単体テスト (tests/test_sticky_quick_add.py)

付箋機能の3連バグを契約として凍結する:
  1. _on_quick_add が database.create_task を Task モデルで呼ぶ (旧: キーワード引数で TypeError)
  2. refresh_tasks が実在する database.get_tasks を使う (旧: 存在しない get_active_tasks)
  3. importance_flag / urgency_flag (実フィールド) からバッジを描画する (旧: is_important 等の幻フィールド)

TDD: 現行コードは 1 で TypeError、2 で AttributeError となる (Red)。
CTkEntry / Toplevel はスタブ化し、UIフレームワーク非依存でロジックのみを検証する。
"""

import sys
import unittest
from pathlib import Path
from unittest import mock
from typing import Optional
import tkinter as tk

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import ui.sticky_note as sticky_note_module
from database import Task
from ui.sticky_note import DesktopStickyNote
from ui.tk_teardown import quiet_destroy


class _FakeEntry:
    """CTkEntry のテスト用スタブ (get / delete のみを模倣)。"""

    def __init__(self, text: str = "") -> None:
        self._text = text

    def get(self) -> str:
        return self._text

    def delete(self, first: object, last: object = None) -> None:
        self._text = ""


class _FakeWindow:
    """Toplevel のテスト用スタブ (winfo_exists のみを模倣)。"""

    def winfo_exists(self) -> bool:
        return True


class StickyQuickAddTestBase(unittest.TestCase):
    """Tk ルートとスタブを用意する共通基底クラス"""

    root: Optional[tk.Tk] = None

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except tk.TclError:
            cls.root = None

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.root is not None:
            quiet_destroy(cls.root)
            cls.root = None

    def setUp(self) -> None:
        if self.root is None:
            self.skipTest("Tk を初期化できない環境のためスキップします")

        # シングルトン状態をテスト毎に必ずリセットする
        DesktopStickyNote._instance = None
        self.addCleanup(setattr, DesktopStickyNote, "_instance", None)

        self.note = DesktopStickyNote(self.root)
        self.note.window = _FakeWindow()
        self.note.tasks_container = tk.Frame(self.root)
        self.addCleanup(self.note.tasks_container.destroy)

    def _all_label_texts(self) -> list:
        """tasks_container 配下の全 Label テキストを収集する。"""
        texts = []
        for row in self.note.tasks_container.winfo_children():
            for widget in row.winfo_children():
                try:
                    texts.append(widget.cget("text"))
                except Exception:
                    continue
        return texts


class TestStickyQuickAdd(StickyQuickAddTestBase):
    """クイック追加の DB 契約検証"""

    def test_quick_add_creates_task_via_task_object(self) -> None:
        """create_task には Task モデル (importance_flag/urgency_flag) を渡すこと"""
        self.note.add_entry = _FakeEntry("DNS設定の確認")
        with mock.patch.object(sticky_note_module.database, "create_task") as fake_create:
            self.note._on_quick_add()

        fake_create.assert_called_once()
        created = fake_create.call_args[0][0]
        self.assertIsInstance(created, Task)
        self.assertEqual(created.title, "DNS設定の確認")
        self.assertEqual(created.priority, 2)
        self.assertTrue(created.importance_flag)
        self.assertTrue(created.urgency_flag)

    def test_quick_add_ignores_whitespace_only_input(self) -> None:
        """空白のみの入力では create_task を呼ばないこと"""
        self.note.add_entry = _FakeEntry("   ")
        with mock.patch.object(sticky_note_module.database, "create_task") as fake_create:
            self.note._on_quick_add()
        fake_create.assert_not_called()

    def test_quick_add_clears_entry_and_refreshes(self) -> None:
        """追加成功後に入力欄がクリアされ、再描画されること"""
        self.note.add_entry = _FakeEntry("緊急連絡")
        with mock.patch.object(sticky_note_module.database, "create_task"), \
                mock.patch.object(self.note, "refresh_tasks") as fake_refresh:
            self.note._on_quick_add()
        self.assertEqual(self.note.add_entry.get(), "")
        fake_refresh.assert_called_once()

    def test_quick_add_survives_db_error(self) -> None:
        """DB エラー時も例外を握りつぶさずログに残してアプリが継続すること"""
        self.note.add_entry = _FakeEntry("壊れる入力")
        with mock.patch.object(
            sticky_note_module.database, "create_task", side_effect=RuntimeError("db down")
        ):
            self.note._on_quick_add()  # 例外が外部へ漏れないこと


class TestStickyTaskRendering(StickyQuickAddTestBase):
    """タスクリスト描画 (get_tasks 接続 ＆ バッジ) の検証"""

    def test_refresh_tasks_fetches_via_get_tasks(self) -> None:
        """refresh_tasks は実在する database.get_tasks を使用すること (旧 get_active_tasks の回帰防止)"""
        task = Task(id=1, title="通常タスク", priority=0)
        with mock.patch.object(sticky_note_module.database, "get_tasks", return_value=[task]) as fake_get:
            self.note.refresh_tasks()
        fake_get.assert_called_once()
        self.assertEqual(len(self.note.tasks_container.winfo_children()), 1)

    def test_priority_badge_rendered_from_flags(self) -> None:
        """importance_flag/urgency_flag から [最優先] バッジが描画されること"""
        task = Task(id=2, title="重要かつ緊急", priority=2, importance_flag=True, urgency_flag=True)
        with mock.patch.object(sticky_note_module.database, "get_tasks", return_value=[task]):
            self.note.refresh_tasks()
        joined = "".join(self._all_label_texts())
        self.assertIn("[最優先] ", joined)
        self.assertIn("重要かつ緊急", joined)

    def test_complete_task_delegates_to_database(self) -> None:
        """◯ ボタン (完了) は database.complete_task(task_id) に委譲すること"""
        with mock.patch.object(sticky_note_module.database, "complete_task") as fake_complete, \
                mock.patch.object(self.note, "refresh_tasks"):
            self.note._on_complete_task(42)
        fake_complete.assert_called_once_with(42)

    def test_complete_task_ignores_none_id(self) -> None:
        """task_id が None の場合は complete_task を呼ばないこと"""
        with mock.patch.object(sticky_note_module.database, "complete_task") as fake_complete:
            self.note._on_complete_task(None)
        fake_complete.assert_not_called()


if __name__ == "__main__":
    unittest.main()