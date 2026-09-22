#!/usr/bin/env python3
"""
ネオ秘書くん - 同期APIレスポンスDTOの単体テスト (tests/test_sync_dtos.py)

2026-09-01 コードレビュー P2①「Pydantic DTO完全移行」第一段として、
スマホ同期 API のレスポンス契約を検証する。

検証観点:
- 正常ペイロードは DTO 検証を通過し、値を一切変えずにラウンドトリップする
- 契約違反 (型不一致) のペイロードは例外を外へ漏らさず、元の辞書を
  そのまま返す (スマホ同期を壊さない縮退動作)
- 未知フィールドは失効させずそのまま保持する (段階移行のため extra=allow)

実行:
    venv/Scripts/python.exe -m unittest tests.test_sync_dtos
"""

import unittest
from typing import Any, Dict

from sync_dtos import validate_status_payload, validate_tasks_view_response


def _sample_status_payload() -> Dict[str, Any]:
    """GET /api/status が実装から返すのと同一構造のサンプルペイロード。"""
    return {
        "status": "ok",
        "pet_state": "idle",
        "message": "ボス、いつもお疲れ様です！",
        "character": {
            "id": "hisho",
            "name": "秘書くん",
            "title": "凄腕秘書",
            "emoji": "🤖",
            "all": [{"id": "hisho"}, {"id": "seal"}],
        },
        "bond": {"level": 1},
        "habits": [],
        "habit_heatmap": {},
        "pending_approval": None,
        "active_event": None,
        "latest_notification": None,
        "easter_egg": {
            "attempt_count": 0,
            "daily_count": 0,
            "secret_game_unlocked": False,
            "active_event": None,
        },
        "tasks": [
            {"id": 1, "title": "経費精算", "priority": 0, "due_date": 1790000000000},
            {"id": 2, "title": "資料レビュー", "priority": 2, "due_date": None},
        ],
        "events": [
            {
                "id": 3,
                "title": "歯医者",
                "start_time": "2026-09-01 10:00",
                "description": "",
                "source_color": "#ff0000",
                "source_name": "iCal",
            }
        ],
        "suggestions": [{"id": "s1", "title": "ダミー提案"}],
        "due_reminders": [],
        "suggest_config": {"sources": {}},
        "pomodoro": {
            "active": False,
            "is_break": False,
            "remaining_seconds": 0,
            "total_seconds": 1500,
            "mode_label": "🍅 集中中",
        },
        "buzz": False,
        "life_state": {},
        "life_coach": None,
        "weather_location": "東京",
        "update": {"update_available": False, "current_version": None},
        # 🛡️ P0-1 (2026-09-22): /api/status は同期トークン (マスターキー) を配布しない
        "language": "ja",
        "server_time": 1790000000000,
    }


class StatusResponseDTOTest(unittest.TestCase):
    """GET /api/status レスポンス契約のテスト。"""

    def test_valid_payload_roundtrips_without_change(self) -> None:
        """正常ペイロードは検証を通過し、値が一切変わらないこと。"""
        payload = _sample_status_payload()
        validated = validate_status_payload(payload)
        self.assertEqual(validated, payload)

    def test_language_field_is_validated(self) -> None:
        """language フィールドが正常に検証・保持されること。"""
        payload = _sample_status_payload()
        payload["language"] = "en"
        validated = validate_status_payload(payload)
        self.assertEqual(validated["language"], "en")

    def test_corrupt_task_falls_back_to_raw_payload(self) -> None:
        """契約違反タスクが混在しても例外を漏らさず生辞書で応答すること。"""
        payload = _sample_status_payload()
        payload["tasks"] = [{"id": 1, "title": 999}]
        result = validate_status_payload(payload)
        self.assertEqual(result, payload)

    def test_unknown_fields_are_preserved(self) -> None:
        """将来追加の未知フィールドが失効せず保持されること。"""
        payload = _sample_status_payload()
        payload["future_field"] = {"alpha": 1}
        validated = validate_status_payload(payload)
        self.assertEqual(validated["future_field"], {"alpha": 1})

    def test_minimal_payload_does_not_raise(self) -> None:
        """最小構成でも例外が発生しないこと (縮退時の安全網)。"""
        result = validate_status_payload({"status": "ok"})
        self.assertEqual(result["status"], "ok")


class TasksViewResponseDTOTest(unittest.TestCase):
    """POST get_tasks_view アクションレスポンス契約のテスト。"""

    def _sample(self) -> Dict[str, Any]:
        """get_tasks_view の実応答と同一構造のサンプル。"""
        return {
            "status": "success",
            "tasks": [
                {
                    "id": 1,
                    "title": "資料作成",
                    "priority": 2,
                    "due_date": 1790000000000,
                    "tags": "仕事,急ぎ",
                    "list_id": 3,
                    "importance_flag": True,
                    "urgency_flag": None,
                    "recurrence": None,
                }
            ],
        }

    def test_valid_payload_roundtrips_without_change(self) -> None:
        """正常レスポンスは検証を通過し、値が一切変わらないこと。"""
        payload = self._sample()
        validated = validate_tasks_view_response(payload)
        self.assertEqual(validated, payload)

    def test_corrupt_task_falls_back_to_raw_payload(self) -> None:
        """契約違反タスクが混在しても例外を漏らさず生辞書で応答すること。"""
        payload = self._sample()
        payload["tasks"] = [{"id": 1, "title": None}]
        result = validate_tasks_view_response(payload)
        self.assertEqual(result, payload)


if __name__ == "__main__":
    unittest.main(verbosity=2)
