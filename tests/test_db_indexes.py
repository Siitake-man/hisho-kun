#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - SQLite 明示的インデックスの単体テスト (tests/test_db_indexes.py)

タスク2 (P1-2, 2026-09-16 Cline): 省電力スプリント完遂。
/api/status の定期ポーリング (2秒間隔) や手帳画面表示で走る
「status 絞り込み + due_date 範囲比較」(tasks) および
「期間重複判定」(events) を、フルスキャン O(N) からインデックススキャン
O(log N) へ高速化した契約を凍結する。

TDD: init_db に idx_tasks_status_due / idx_events_start_end が無い状態では Red。
"""

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import storage  # noqa: E402


TASKS_INDEX = "idx_tasks_status_due"
EVENTS_INDEX = "idx_events_start_end"


class _IndexTestBase(unittest.TestCase):
    """一時DBを用意する共通基底クラス"""

    def setUp(self) -> None:
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = handle.name
        handle.close()
        storage.init_db(self.db_path)

    def tearDown(self) -> None:
        Path(self.db_path).unlink(missing_ok=True)

    def _query(self, sql: str, params: tuple = ()) -> list:
        """一時DBへ直接クエリを投げて結果行を返す。"""
        conn = sqlite3.connect(self.db_path)
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def _index_definition(self, index_name: str) -> str:
        """sqlite_master から索引定義SQLを取得する (未作成なら空文字)。"""
        rows = self._query(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?",
            (index_name,),
        )
        return rows[0][0] if rows and rows[0][0] else ""

    def _index_columns(self, index_name: str) -> list:
        """PRAGMA index_info から索引の対象カラム名を順序どおり取得する。"""
        rows = self._query(f"PRAGMA index_info({index_name})")
        return [row[2] for row in rows]

    def _query_plan(self, sql: str, params: tuple = ()) -> str:
        """EXPLAIN QUERY PLAN の詳細文字列を連結して返す。"""
        rows = self._query(f"EXPLAIN QUERY PLAN {sql}", params)
        return " | ".join(str(row[-1]) for row in rows)


class TestPowerSprintIndexes(_IndexTestBase):
    """P1-2: 頻出カラムの明示的インデックス契約"""

    def test_tasks_status_due_index_is_created(self) -> None:
        """tasks(status, due_date) の複合インデックスが存在すること"""
        self.assertEqual(self._index_columns(TASKS_INDEX), ["status", "due_date"])
        self.assertIn("tasks", self._index_definition(TASKS_INDEX))

    def test_events_start_end_index_is_created(self) -> None:
        """events(start_time, end_time) の複合インデックスが存在すること"""
        self.assertEqual(
            self._index_columns(EVENTS_INDEX), ["start_time", "end_time"]
        )
        self.assertIn("events", self._index_definition(EVENTS_INDEX))

    def test_tasks_query_plan_uses_index_not_full_scan(self) -> None:
        """TODOの status 絞り込み + 期日比較がインデックススキャンになること"""
        plan = self._query_plan(
            "SELECT id FROM tasks WHERE status = 'todo' AND due_date <= ?", (0,)
        )
        self.assertIn(TASKS_INDEX, plan)
        self.assertNotIn("SCAN", plan.upper())

    def test_events_query_plan_uses_index_not_full_scan(self) -> None:
        """予定の期間比較がインデックススキャンになること"""
        plan = self._query_plan(
            "SELECT id FROM events WHERE start_time >= ? AND end_time <= ?", (0, 1)
        )
        self.assertIn(EVENTS_INDEX, plan)

    def test_init_db_is_idempotent_for_indexes(self) -> None:
        """init_db を再実行しても例外なくインデックスが維持されること (冪等)"""
        storage.init_db(self.db_path)
        storage.init_db(self.db_path)
        self.assertEqual(self._index_columns(TASKS_INDEX), ["status", "due_date"])
        self.assertEqual(
            self._index_columns(EVENTS_INDEX), ["start_time", "end_time"]
        )

    def test_indexes_are_added_to_legacy_database(self) -> None:
        """旧DB (P1-2 以前＝インデックス未作成) へ init_db が索引を付与すること"""
        # 旧バージョン相当のDBを作る: 一度 init_db した後、索引だけを削除する
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute(f"DROP INDEX IF EXISTS {TASKS_INDEX}")
            conn.execute(f"DROP INDEX IF EXISTS {EVENTS_INDEX}")
        conn.close()
        self.assertEqual(self._index_columns(TASKS_INDEX), [])

        # 起動時の init_db (マイグレーション) が索引を再作成する
        storage.init_db(self.db_path)

        self.assertEqual(self._index_columns(TASKS_INDEX), ["status", "due_date"])
        self.assertEqual(
            self._index_columns(EVENTS_INDEX), ["start_time", "end_time"]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
