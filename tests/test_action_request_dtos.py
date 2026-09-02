#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - アクションリクエストDTO 単体テスト (tests/test_action_request_dtos.py)

P2① 残部「内部処理の dict 扱い → Pydantic DTO 完全移行」の第三段。
api_tasks.py のアクション受信パース (json.loads → 生dict操作) を
sync_dtos.py のリクエストDTO (parse_request) で型付けし、
パラメータ欠落・型揺れ・壊れたJSONを構造的に検出できるようにする。

検証観点:
  1. 正常系: task_id / habit_id / title / text のパースと型正規化 (文字列→int等)
  2. 欠落系: パラメータ欠落時は該当フィールドが None (ハンドラが明示エラー応答)
  3. 縮退系: 壊れたJSON・空ボディは None (ハンドラが明示エラー応答)
  4. 透過系: 未知フィールドは extra=allow で保持 (PWA契約保護)

設計上の注意:
- 純関数 (parse_request) の単体テストのため HTTP サーバー / DB Mock は不要。
"""

import json
import sys
import unittest
from pathlib import Path

# ※ 本ファイルは tests/ 配下にあるため、プロジェクトルートを import パスに追加
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sync_dtos import (
    AddHabitRequestDTO,
    HabitActionRequestDTO,
    QuickAddRequestDTO,
    TaskActionRequestDTO,
    UpdateTaskRequestDTO,
    parse_request,
)


class TestActionRequestDTOs(unittest.TestCase):
    """api_tasks.py のリクエストDTOパース (parse_request) を検証する"""

    # ==========================================================================
    # 1. 正常系: パースと型正規化
    # ==========================================================================
    def test_complete_task_request_parses_task_id(self):
        """complete_task リクエストから task_id (int) を取得できる"""
        body = json.dumps({"action": "complete_task", "task_id": 5}).encode("utf-8")
        req = parse_request(body, TaskActionRequestDTO)
        self.assertIsInstance(req, TaskActionRequestDTO)
        self.assertEqual(req.task_id, 5)

    def test_task_id_string_is_coerced_to_int(self):
        """task_id が文字列 ("7") でも int (7) に正規化される"""
        req = parse_request(b'{"action": "complete_task", "task_id": "7"}', TaskActionRequestDTO)
        self.assertEqual(req.task_id, 7)
        self.assertIsInstance(req.task_id, int)

    def test_toggle_habit_request_parses_habit_id(self):
        """toggle_habit リクエストから habit_id を取得できる"""
        req = parse_request(b'{"action": "toggle_habit", "habit_id": 3}', HabitActionRequestDTO)
        self.assertEqual(req.habit_id, 3)

    def test_add_habit_request_parses_title_and_emoji(self):
        """add_habit リクエストから title と emoji を取得できる (emoji 既定値は 🌱)"""
        body = json.dumps({"action": "add_habit", "title": "朝のストレッチ"}).encode("utf-8")
        req = parse_request(body, AddHabitRequestDTO)
        self.assertEqual(req.title, "朝のストレッチ")
        self.assertEqual(req.emoji, "🌱")

    def test_quick_add_request_keeps_raw_text(self):
        """quick_add_task の text は生値を保持する (strip はハンドラ側の責務)"""
        body = json.dumps({"action": "quick_add_task", "text": "  牛乳を買う  "}).encode("utf-8")
        req = parse_request(body, QuickAddRequestDTO)
        self.assertEqual(req.text, "  牛乳を買う  ")

    def test_update_task_request_parses_optional_fields(self):
        """update_task リクエストのオプション項目をパースできる"""
        body = json.dumps({
            "action": "update_task", "task_id": 9, "title": "編集後",
            "due_date": 1756500000000, "priority": 3, "tags": "a,b",
            "importance_flag": True, "urgency_flag": None,
        }).encode("utf-8")
        req = parse_request(body, UpdateTaskRequestDTO)
        self.assertEqual(req.task_id, 9)
        self.assertEqual(req.title, "編集後")
        self.assertEqual(req.due_date, 1756500000000)
        self.assertEqual(req.priority, 3)
        self.assertEqual(req.tags, "a,b")
        self.assertIs(req.importance_flag, True)
        self.assertIsNone(req.urgency_flag)

    # ==========================================================================
    # 2. 欠落系: フィールドは None (ハンドラが明示エラー応答する)
    # ==========================================================================
    def test_missing_task_id_is_none(self):
        """task_id 欠落時は req.task_id が None"""
        req = parse_request(b'{"action": "complete_task"}', TaskActionRequestDTO)
        self.assertIsNone(req.task_id)

    def test_missing_text_is_none(self):
        """text 欠落時は req.text が None"""
        req = parse_request(b'{"action": "quick_add_task"}', QuickAddRequestDTO)
        self.assertIsNone(req.text)

    # ==========================================================================
    # 3. 縮退系: 壊れたJSON・空ボディは None
    # ==========================================================================
    def test_corrupt_json_returns_none(self):
        """JSONとして不正なボディは None (ハンドラが明示エラー応答する)"""
        self.assertIsNone(parse_request(b"not-json{{{", TaskActionRequestDTO))

    def test_empty_body_returns_none(self):
        """空ボディは None"""
        self.assertIsNone(parse_request(b"", TaskActionRequestDTO))

    def test_non_object_json_returns_none(self):
        """JSON配列・文字列などオブジェクト以外のボディは None"""
        self.assertIsNone(parse_request(b'["task_id", 5]', TaskActionRequestDTO))
        self.assertIsNone(parse_request(b'"complete_task"', TaskActionRequestDTO))

    # ==========================================================================
    # 4. 透過系: 未知フィールドは extra=allow で保持
    # ==========================================================================
    def test_extra_fields_are_preserved(self):
        """未知フィールドは失われず保持される (PWA契約保護)"""
        body = json.dumps({
            "action": "complete_task", "task_id": 5, "client_hint": "pixel7",
        }).encode("utf-8")
        req = parse_request(body, TaskActionRequestDTO)
        self.assertEqual(req.model_dump().get("client_hint"), "pixel7")


if __name__ == "__main__":
    unittest.main(verbosity=2)
