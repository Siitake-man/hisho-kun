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


class TestImportanceUrgencyFlags(unittest.TestCase):
    """4象限属性 (※重要/※非重要/※緊急/※非緊急) の解析とDB保存の検証 (roadmap 1.14)"""

    def setUp(self):
        """テストごとに独立した一時DBを用意する"""
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        database.init_db(self.db_path)

    def tearDown(self):
        """一時DBファイルを後片付けする"""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_parse_important_urgent(self):
        """※重要※緊急 が両方Trueに解析される"""
        result = parse_input("顧客対応 #仕事 ※重要※緊急", now=FIXED_NOW)
        self.assertEqual(result.title, "顧客対応")
        self.assertIs(result.importance, True)
        self.assertIs(result.urgency, True)

    def test_parse_negative_flags(self):
        """※非重要/※非緊急 が両方Falseに解析される"""
        result = parse_input("資料整理 ※非重要※非緊急", now=FIXED_NOW)
        self.assertIs(result.importance, False)
        self.assertIs(result.urgency, False)

    def test_parse_no_flags_returns_none(self):
        """フラグ未入力は None (推定ルールへフォールバック)"""
        result = parse_input("普通のタスク", now=FIXED_NOW)
        self.assertIsNone(result.importance)
        self.assertIsNone(result.urgency)

    def test_flags_are_stripped_from_title(self):
        """フラグ表現はタイトルから除去される"""
        result = parse_input("経費精算 ※重要 ※緊急", now=FIXED_NOW)
        self.assertEqual(result.title, "経費精算")

    def test_db_roundtrip_with_flags(self):
        """明示属性がDBに保存され bool として読み戻せる"""
        task_id = database.create_task(database.Task(
            title="四半期決算", importance_flag=True, urgency_flag=False,
        ), db_path=self.db_path)
        saved = next(t for t in database.get_tasks(status="todo", db_path=self.db_path) if t.id == task_id)
        self.assertIs(saved.importance_flag, True)
        self.assertIs(saved.urgency_flag, False)

    def test_db_roundtrip_without_flags(self):
        """未指定属性は None として保存・読み戻される"""
        task_id = database.create_task(database.Task(title="通常タスク"), db_path=self.db_path)
        saved = next(t for t in database.get_tasks(status="todo", db_path=self.db_path) if t.id == task_id)
        self.assertIsNone(saved.importance_flag)
        self.assertIsNone(saved.urgency_flag)


class TestRecurrenceParse(unittest.TestCase):
    """繰り返し構文解析のテスト (roadmap 1.12)"""

    def test_parse_daily(self):
        """「毎日」がdailyに解析され、タイトルから除去される"""
        result = parse_input("毎日9時に日報を書く")
        self.assertEqual(result.recurrence, "daily")
        self.assertNotIn("毎日", result.title)
        self.assertIsNotNone(result.due_date)

    def test_parse_weekday(self):
        """「毎週月曜」がweeklyに解析される"""
        result = parse_input("毎週月曜 ゴミ出し")
        self.assertEqual(result.recurrence, "weekly")
        self.assertNotIn("毎週", result.title)

    def test_parse_weekly_no_weekday(self):
        """「毎週」のみ (曜日指定なし) は期限未定になる"""
        result = parse_input("毎週 掃除")
        self.assertEqual(result.recurrence, "weekly")
        self.assertIsNone(result.due_date)

    def test_parse_monthly(self):
        """「毎月1日」がmonthlyに解析される"""
        result = parse_input("毎月1日 経費精算")
        self.assertEqual(result.recurrence, "monthly")
        self.assertNotIn("毎月", result.title)

    def test_no_recurrence(self):
        """繰り返し語が無い場合はNone"""
        result = parse_input("資料を作る")
        self.assertIsNone(result.recurrence)

    def test_daily_with_time(self):
        """「毎日9時」は今日の9時 (過ぎていれば明日の9時) が期限になる"""
        base = datetime(2026, 8, 31, 10, 0)  # 月曜 10:00
        result = parse_input("毎日9時に日報", now=base)
        self.assertEqual(result.recurrence, "daily")
        # 9時は既に過ぎているため翌日9時
        due = datetime.fromtimestamp(result.due_date / 1000)
        self.assertEqual(due, datetime(2026, 9, 1, 9, 59))

    def test_weekly_next_monday(self):
        """「毎週月曜」は次の月曜が期限になる"""
        base = datetime(2026, 8, 31, 12, 0)  # 月曜 12:00
        result = parse_input("毎週月曜 提出物", now=base)
        due = datetime.fromtimestamp(result.due_date / 1000)
        # 当日は含まないため翌週月曜
        self.assertEqual(due, datetime(2026, 9, 7, 23, 59))


class TestRecurrenceCompletion(unittest.TestCase):
    """繰り返しタスク完了時の次回自動生成テスト (roadmap 1.12)"""

    def setUp(self):
        """テスト用一時DBを初期化する"""
        import tempfile
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_recurrence.db")
        database.init_db(self.db_path)

    def tearDown(self):
        """一時DBを破棄する"""
        self.temp_dir.cleanup()

    def test_complete_daily_generates_next(self):
        """dailyタスクを完了すると翌日期限の次回分が生成される"""
        from datetime import datetime, timedelta
        due = int((datetime.now() + timedelta(hours=1)).timestamp() * 1000)
        tid = database.create_task(database.Task(
            title="日報", due_date=due, status="todo", recurrence="daily"
        ), db_path=self.db_path)
        self.assertTrue(database.complete_task(tid, db_path=self.db_path))
        remaining = database.get_tasks(status="todo", db_path=self.db_path)
        self.assertEqual(len(remaining), 1)
        nxt = remaining[0]
        self.assertEqual(nxt.title, "日報")
        self.assertEqual(nxt.recurrence, "daily")
        # 次回期限は翌日 (前回期限+1日)
        next_due = datetime.fromtimestamp(nxt.due_date / 1000)
        self.assertEqual(next_due.date(), (datetime.fromtimestamp(due / 1000) + timedelta(days=1)).date())

    def test_complete_non_recurring_no_generation(self):
        """単発タスクの完了では次回分を生成しない"""
        tid = database.create_task(database.Task(title="単発", status="todo"), db_path=self.db_path)
        self.assertTrue(database.complete_task(tid, db_path=self.db_path))
        self.assertEqual(len(database.get_tasks(status="todo", db_path=self.db_path)), 0)


if __name__ == "__main__":
    unittest.main()
