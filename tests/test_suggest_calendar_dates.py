"""
予定サジェスト日付・時間判定 TDD 単体テスト (tests/test_suggest_calendar_dates.py)

ユーザー報告事象:
「今日の予定はないはずですが、スマホ側ではなぜか明日の15時からの予定が今日の予定として表示されます」
この不具合を恒久根治するため、本日・明日・明後日以降・進行中・直前リマインドの
表示ラベル（urgency）が正しく付与されることを自動検証します。
"""

import datetime
import time
import unittest
from unittest.mock import patch

import storage
from suggest_engine import SuggestionEngine


_orig_datetime = datetime.datetime


def _make_mock_datetime(fixed_now: datetime.datetime):
    """datetime.datetime を安全にモックするサブクラスを生成するヘルパー（無限再帰防止）"""
    class MockDateTime(_orig_datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now

        @classmethod
        def fromtimestamp(cls, ts, tz=None):
            return _orig_datetime.fromtimestamp(ts, tz=tz)

    return MockDateTime


class TestSuggestCalendarDates(unittest.TestCase):
    """カレンダー予定サジェストの日付・時間判定テスト"""

    def setUp(self):
        """テスト用モックおよびエンジンの初期化"""
        self.engine = SuggestionEngine()
        # カレンダーソースのみ有効化
        self.engine.config = {
            "sources": {
                "calendar": {"enabled": True},
                "high_priority_tasks": {"enabled": False},
                "proactive_care": {"enabled": False},
                "boss_insights": {"enabled": False},
                "news_topics": {"enabled": False},
                "google_calendar": {"enabled": False},
                "gmail": {"enabled": False},
            }
        }

    @patch("suggest_engine.database.get_upcoming_events")
    def test_01_today_future_event_label(self, mock_events):
        """本日の予定（60分超先）が【本日 HH:MM〜】となることを検証"""
        now = datetime.datetime(2026, 9, 14, 10, 0, 0)
        now_ts = int(now.timestamp() * 1000)

        # 本日 14:30 の予定（4時間半後）
        event_dt = datetime.datetime(2026, 9, 14, 14, 30, 0)
        event_ts = int(event_dt.timestamp() * 1000)

        mock_ev = storage.Event(
            id=1,
            title="チーム定例ミーティング",
            start_time=event_ts,
            end_time=event_ts + 3600000,
            description="進捗確認"
        )
        mock_events.return_value = [mock_ev]

        mock_dt_class = _make_mock_datetime(now)
        with patch("suggest_engine.datetime.datetime", mock_dt_class), \
             patch("suggest_engine.time.time", return_value=now.timestamp()):
            suggestions = self.engine.generate_suggestions()

        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["id"], "event_1")
        self.assertIn("【本日 14:30〜】", suggestions[0]["title"])
        self.assertIn("チーム定例ミーティング", suggestions[0]["title"])

    @patch("suggest_engine.database.get_upcoming_events")
    def test_02_tomorrow_event_label(self, mock_events):
        """【真因根治】明日の予定（明日の15:00）が【明日 15:00〜】となることを検証（本日と誤認しない）"""
        now = datetime.datetime(2026, 9, 14, 20, 0, 0)  # 今夜20時
        now_ts = int(now.timestamp() * 1000)

        # 明日 15:00 の予定（翌日）
        event_dt = datetime.datetime(2026, 9, 15, 15, 0, 0)
        event_ts = int(event_dt.timestamp() * 1000)

        mock_ev = storage.Event(
            id=2,
            title="顧客打ち合わせ",
            start_time=event_ts,
            end_time=event_ts + 3600000,
            description="新機能デモ"
        )
        mock_events.return_value = [mock_ev]

        mock_dt_class = _make_mock_datetime(now)
        with patch("suggest_engine.datetime.datetime", mock_dt_class), \
             patch("suggest_engine.time.time", return_value=now.timestamp()):
            suggestions = self.engine.generate_suggestions()

        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["id"], "event_2")
        # 従来のバグでは「【本日 15:00〜】」になっていた
        self.assertIn("【明日 15:00〜】", suggestions[0]["title"])
        self.assertNotIn("【本日", suggestions[0]["title"])

    @patch("suggest_engine.database.get_upcoming_events")
    def test_03_imminent_event_label(self, mock_events):
        """直前（60分以内）の予定が【あと XX分】となることを検証"""
        now = datetime.datetime(2026, 9, 14, 10, 0, 0)

        # 本日 10:25 の予定（25分後）
        event_dt = datetime.datetime(2026, 9, 14, 10, 25, 0)
        event_ts = int(event_dt.timestamp() * 1000)

        mock_ev = storage.Event(
            id=3,
            title="スタンドアップ",
            start_time=event_ts,
            end_time=event_ts + 1800000,
        )
        mock_events.return_value = [mock_ev]

        mock_dt_class = _make_mock_datetime(now)
        with patch("suggest_engine.datetime.datetime", mock_dt_class), \
             patch("suggest_engine.time.time", return_value=now.timestamp()):
            suggestions = self.engine.generate_suggestions()

        self.assertEqual(len(suggestions), 1)
        self.assertIn("【あと 25分】", suggestions[0]["title"])

    @patch("suggest_engine.database.get_upcoming_events")
    def test_04_ongoing_event_label(self, mock_events):
        """開始時刻を過ぎている（diff_mins < 0）が終了前の予定が【進行中】となることを検証"""
        now = datetime.datetime(2026, 9, 14, 10, 30, 0)

        # 10:00〜11:00 の予定（現在 10:30）
        start_dt = datetime.datetime(2026, 9, 14, 10, 0, 0)
        end_dt = datetime.datetime(2026, 9, 14, 11, 0, 0)

        mock_ev = storage.Event(
            id=4,
            title="進行中ワークショップ",
            start_time=int(start_dt.timestamp() * 1000),
            end_time=int(end_dt.timestamp() * 1000),
        )
        mock_events.return_value = [mock_ev]

        mock_dt_class = _make_mock_datetime(now)
        with patch("suggest_engine.datetime.datetime", mock_dt_class), \
             patch("suggest_engine.time.time", return_value=now.timestamp()):
            suggestions = self.engine.generate_suggestions()

        self.assertEqual(len(suggestions), 1)
        self.assertIn("【進行中】", suggestions[0]["title"])

    @patch("suggest_engine.database.get_upcoming_events")
    def test_05_day_after_tomorrow_event_label(self, mock_events):
        """明後日以降の予定が【M/D HH:MM〜】となることを検証"""
        now = datetime.datetime(2026, 9, 14, 10, 0, 0)

        # 9/16 11:00 の予定（2日後）
        event_dt = datetime.datetime(2026, 9, 16, 11, 0, 0)
        event_ts = int(event_dt.timestamp() * 1000)

        mock_ev = storage.Event(
            id=5,
            title="明後日のカンファレンス",
            start_time=event_ts,
            end_time=event_ts + 7200000,
        )
        mock_events.return_value = [mock_ev]

        mock_dt_class = _make_mock_datetime(now)
        with patch("suggest_engine.datetime.datetime", mock_dt_class), \
             patch("suggest_engine.time.time", return_value=now.timestamp()):
            suggestions = self.engine.generate_suggestions()

        self.assertEqual(len(suggestions), 1)
        self.assertIn("【9/16 11:00〜】", suggestions[0]["title"])


if __name__ == "__main__":
    unittest.main()
