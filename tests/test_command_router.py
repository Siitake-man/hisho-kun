"""command_router の決定論的解析部の単体テスト（DB書き込みを伴わない範囲のみ検証）"""
import unittest
from datetime import datetime

from command_router import (
    _extract_title,
    _resolve_event_datetimes,
    try_route_command,
)


class TestCommandRouterParsing(unittest.TestCase):
    """日時解析・タイトル抽出・インテント判定のユニットテスト"""

    def setUp(self) -> None:
        """解析基準時刻を固定化（再現性の確保）"""
        self.now = datetime(2026, 8, 30, 12, 0, 0)

    def test_relative_day_and_time(self) -> None:
        """「明日15時に〜」が翌日15:00-16:00として解析される"""
        result = _resolve_event_datetimes("明日15時に開発会議を入れて", now=self.now)
        self.assertIsNotNone(result)
        start, end = result
        self.assertEqual(start, datetime(2026, 8, 31, 15, 0, 0))
        self.assertEqual(end, datetime(2026, 8, 31, 16, 0, 0))

    def test_afternoon_and_duration(self) -> None:
        """「午後3時から2時間」が15:00-17:00として解析される"""
        result = _resolve_event_datetimes("明日の午後3時から2時間、打ち合わせを登録して", now=self.now)
        self.assertIsNotNone(result)
        start, end = result
        self.assertEqual(start, datetime(2026, 8, 31, 15, 0, 0))
        self.assertEqual(end, datetime(2026, 8, 31, 17, 0, 0))

    def test_explicit_date(self) -> None:
        """「9月5日の10時」が絶対日付として解析される"""
        result = _resolve_event_datetimes("9月5日の10時に歯医者を追加して", now=self.now)
        self.assertIsNotNone(result)
        start, _end = result
        self.assertEqual(start, datetime(2026, 9, 5, 10, 0, 0))

    def test_no_datetime_returns_none(self) -> None:
        """日時を含まない指示は None（LLM委譲）になる"""
        self.assertIsNone(_resolve_event_datetimes("予定を入れて", now=self.now))

    def test_extract_title_plain(self) -> None:
        """トリガー直前の語句から日時表現を除いたタイトルが抽出される"""
        self.assertEqual(_extract_title("明日15時に開発会議を入れて"), "開発会議")
        self.assertEqual(_extract_title("明日の午後3時から2時間、打ち合わせを登録して"), "打ち合わせ")

    def test_extract_title_quoted(self) -> None:
        """引用囲みのタイトルが最優先で抽出される"""
        self.assertEqual(_extract_title("明日15時に「顧客MTG」を登録して"), "顧客MTG")

    def test_no_intent_returns_none(self) -> None:
        """予定登録インテントの無い入力は None になる"""
        self.assertIsNone(try_route_command("こんにちは、元気？"))
        self.assertIsNone(try_route_command("今週の予定を教えて"))

    def test_task_only_intent_returns_none(self) -> None:
        """タスク登録（対象外）は None で LLM 委譲になる"""
        self.assertIsNone(try_route_command("「資料作成」のタスクを追加して"))


if __name__ == "__main__":
    unittest.main()