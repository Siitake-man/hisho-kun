#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - 音声同期 ＆ タスク作成統合テスト (tests/test_voice_sync.py)

local_sync_server の transcribe_voice アクションとタスク自動作成のパイプラインを検証します。
"""

import os
import sys
import json
import base64
import unittest
from unittest.mock import MagicMock, patch

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import database
from whisper_transcriber import WhisperTranscriber


class TestVoiceSyncPipeline(unittest.TestCase):
    """音声文字起こしからタスク作成までの統合テストクラス。"""

    def setUp(self):
        # テスト用の一時ファイルDBを作成（:memory: は接続毎に独立するため不使用・実DBも汚染しない）
        self._tmp_db = os.path.join(os.environ.get("TEMP", os.path.dirname(__file__)), "test_voice_sync_db.sqlite3")
        if os.path.exists(self._tmp_db):
            os.remove(self._tmp_db)
        database.init_db(self._tmp_db)

    def tearDown(self):
        if os.path.exists(self._tmp_db):
            os.remove(self._tmp_db)

    @patch("whisper_transcriber.WhisperTranscriber.is_available", return_value=True)
    @patch("whisper_transcriber.WhisperTranscriber.transcribe", return_value="明日10時に打ち合わせ #仕事 ※重要")
    def test_voice_transcribe_and_task_creation(self, mock_transcribe, mock_is_available):
        """文字起こし結果から task_parser がタグ・重要度を抽出し、DBにタスクが作成されることを確認。"""
        from task_parser import parse_input, tags_to_db_string

        # 重要度フラグは task_parser.py の正式構文「※重要」を使用（!N は優先度指定）
        transcript = "明日10時に打ち合わせ #仕事 ※重要"
        parsed = parse_input(transcript)

        self.assertIn("打ち合わせ", parsed.title)
        self.assertIn("仕事", parsed.tags)
        self.assertTrue(parsed.importance)

        task_id = database.create_task(database.Task(
            title=parsed.title,
            description="🎤 スマホ音声入力より自動登録",
            due_date=parsed.due_date,
            priority=parsed.priority,
            status="todo",
            tags=tags_to_db_string(parsed.tags),
            importance_flag=parsed.importance,
            urgency_flag=parsed.urgency,
            recurrence=parsed.recurrence,
        ), db_path=self._tmp_db)

        self.assertIsNotNone(task_id)
        # database.py の実在API get_tasks() 経由で作成タスクを検証
        tasks = database.get_tasks(status="todo", limit=100, db_path=self._tmp_db)
        self.assertTrue(len(tasks) >= 1)
        task = next(t for t in tasks if t.title == parsed.title)
        self.assertIsNotNone(task)
        self.assertIn("打ち合わせ", task.title)
        self.assertIn("仕事", task.tags)
        self.assertTrue(task.importance_flag)


if __name__ == "__main__":
    unittest.main()
