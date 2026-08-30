# -*- coding: utf-8 -*-
"""ネオ秘書くん - task_parser クイック追加構文のユニットテスト。

TickTick拡張 (Step 4) のクイック追加バー用パーサーの検証:
自然言語1行から 期限/タグ/優先度/タイトル を解析する。
"""

import os
import tempfile
import unittest
from datetime import datetime

import database
from task_parser import parse_input, tags_to_db_string, db_string_to_tags


# テスト用の固定起点日時 (2026-08-30(日) 15:00、決定的テストのため)
FIXED_NOW = datetime(2026, 8, 30, 15, 0, 0)


class TestTaskParser(unittest.TestCase):
    """parse_input の解析ロジックテスト"""

    def test_full_syntax(self):
        """日時+タグ+優先度のフル構文から各要素を抽出できる"""
        result = parse_input("明日18時に会議資料を作る #仕事 !3", now=FIXED_NOW)
        self.assertEqual(result.title, "会議資料を作る")
        self.assertEqual(result.tags, ["仕事"])
        self.assertEqual(result.priority, 3)
        self.assertIsNotNone(result.due_date)

    def test_due_date_is_tomorrow_at_specified_hour(self):
        """「明日18時」が起点日の翌日18時に解析される"""
        result = parse_input("明日18時に報告書提出", now=FIXED_NOW)
        due = datetime.fromtimestamp(result.due_date / 1000)
        self.assertEqual(due.year, 2026)
        self.assertEqual(due.month, 8)
        self.assertEqual(due.day, 31)
        self.assertEqual(due.hour, 18)

    def test_date_only_means_end_of_day(self):
        """日付のみ指定時はその日の23:59 (終日扱い) になる"""
        result = parse_input("明後日 資料レビュー", now=FIXED_NOW)
        due = datetime.fromtimestamp(result.due_date / 1000)
        self.assertEqual(due.day, 1)  # 8/30 + 2日 = 9/1
        self.assertEqual(due.month, 9)
        self.assertEqual(due.hour, 23)

    def test_multiple_tags(self):
        """複数タグが順序保持で抽出される"""
        result = parse_input("経費精算 #仕事 #急ぎ", now=FIXED_NOW)
        self.assertEqual(result.tags, ["仕事", "急ぎ"])
        self.assertEqual(result.title, "経費精算")

    def test_priority_word_forms(self):
        """優先度の語彙形式 (!高/!中/!低) も数値化される"""
        self.assertEqual(parse_input("掃除 !高", now=FIXED_NOW).priority, 3)
        self.assertEqual(parse_input("掃除 !中", now=FIXED_NOW).priority, 2)
        self.assertEqual(parse_input("掃除 !低", now=FIXED_NOW).priority, 1)

    def test_no_date_expression(self):
        """日時表現なしの場合は期限なし・タイトルのみ"""
        result = parse_input("ゴミ出しをする", now=FIXED_NOW)
        self.assertEqual(result.title, "ゴミ出しをする")
        self.assertIsNone(result.due_date)
        self.assertEqual(result.priority, 0)
        self.assertEqual(result.tags, [])

    def test_empty_input(self):
        """空入力は空の ParsedTask を返す"""
        result = parse_input("", now=FIXED_NOW)
        self.assertEqual(result.title, "")
        self.assertIsNone(result.due_date)


class TestTagStringConversion(unittest.TestCase):
    """tags_to_db_string / db_string_to_tags の往復変換テスト"""

    def test_round_trip(self):
        """リスト→DB文字列→リストの往復で元に戻る"""
        tags = ["仕事", "急ぎ", "レビュー"]
        db_value = tags_to_db_string(tags)
        self.assertEqual(db_value, "仕事,急ぎ,レビュー")
        self.assertEqual(db_string_to_tags(db_value), tags)

    def test_deduplication(self):
        """重複タグ・空タグは排除される"""
        self.assertEqual(tags_to_db_string(["仕事", "仕事", "", "急ぎ"]), "仕事,急ぎ")

    def test_empty_db_value(self):
        """空文字列のDB値は空リストに復元される"""
        self.assertEqual(db_string_to_tags(""), [])


class TestQuickAddDbIntegration(unittest.TestCase):
    """task_parser → database.Task → DB保存 の統合テスト"""

    def setUp(self):
        """テストごとに独立した一時DBを用意する"""
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        database.init_db(self.db_path)

    def tearDown(self):
        """一時DBファイルを後片付けする"""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_parsed_task_persists_with_tags(self):
        """解析結果 (タグ・優先度・期限) がDBへ永続化される"""
        from task_parser import ParsedTask

        parsed = parse_input("明日10時に朝会 #仕事 #定期 !2", now=FIXED_NOW)
        task_id = database.create_task(database.Task(
            title=parsed.title,
            description="",
            due_date=parsed.due_date,
            priority=parsed.priority,
            status="todo",
            tags=tags_to_db_string(parsed.tags),
        ), db_path=self.db_path)

        tasks = database.get_tasks(status="todo", db_path=self.db_path)
        saved = next(t for t in tasks if t.id == task_id)
        self.assertEqual(saved.title, "朝会")
        self.assertEqual(saved.priority, 2)
        self.assertEqual(db_string_to_tags(saved.tags), ["仕事", "定期"])
        due = datetime.fromtimestamp(saved.due_date / 1000)
        self.assertEqual((due.month, due.day, due.hour), (8, 31, 10))


if __name__ == "__main__":
    unittest.main()
