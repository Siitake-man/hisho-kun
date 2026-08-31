"""
LifeCoachEngine のユニットテスト (test_life_coach_engine.py)

AI生活変化エンジン Phase L1 の検証:
- LLM正常系 (JSON解析・スキーマ検証・上限クリップ)
- LLM失敗時の i18n ルールフォールバック
- 日次冪等 (同日の2回目は既存レポートを再利用)
- 生活統計集約 (タスク・習慣のカウント)
- スケジュール判定 (夜間23時 / 朝補完 / 実行済みスキップ)
- /api/status 供給用レポート取得
LLM はモックを使用し、実LLM・実ネットワークには一切接続しない。
"""

import sys
import tempfile
import os
import unittest
from datetime import datetime
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import database
from life_coach_engine import LifeCoachEngine


class LifeCoachEngineTestBase(unittest.TestCase):
    """テスト毎に独立した一時DBを用意する基底クラス。"""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmpdir.name, "test_coach.db")
        database.init_db(self.db_path)
        self.engine = LifeCoachEngine(db_path=self.db_path)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()


class TestParseLlmJson(LifeCoachEngineTestBase):
    """_parse_llm_json のスキーマ検証テスト。"""

    def test_valid_json(self) -> None:
        """正常なJSONをパースしてスキーマ通りの辞書を返す。"""
        raw = (
            '```json\n{"analysis": "a", "micro_actions": ["x", "y"], '
            '"encouragement": "e", "risk_flags": ["r"]}\n```'
        )
        parsed = self.engine._parse_llm_json(raw)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["analysis"], "a")
        self.assertEqual(parsed["micro_actions"], ["x", "y"])
        self.assertEqual(parsed["risk_flags"], ["r"])

    def test_micro_actions_clipped_to_max(self) -> None:
        """マイクロ提案が最大件数 (3) にクリップされる。"""
        raw = (
            '{"analysis": "a", "micro_actions": ["1", "2", "3", "4", "5"], '
            '"encouragement": "e", "risk_flags": []}'
        )
        parsed = self.engine._parse_llm_json(raw)
        assert parsed is not None
        self.assertEqual(len(parsed["micro_actions"]), 3)

    def test_invalid_json_returns_none(self) -> None:
        """JSON以外の出力は None (フォールバック誘発) を返す。"""
        self.assertIsNone(self.engine._parse_llm_json("申し訳ありませんが…"))
        self.assertIsNone(self.engine._parse_llm_json('{"analysis": "", "micro_actions": []}'))


class TestFallbackAndIdempotency(LifeCoachEngineTestBase):
    """フォールバックと日次冪等のテスト。"""

    def test_fallback_on_llm_failure(self) -> None:
        """LLM呼び出し失敗時は i18n ルールベースのレポートを生成する。"""
        now = datetime(2026, 9, 1, 23, 0)
        with patch.object(self.engine, "_invoke_llm", return_value=None):
            report = self.engine.run_analysis_once(now=now, force=True)
        self.assertIsNotNone(report)
        assert report is not None
        self.assertEqual(report["source"], "fallback")
        self.assertEqual(report["run_date"], "2026-09-01")
        self.assertTrue(len(report["micro_actions"]) >= 1)

    def test_llm_report_success(self) -> None:
        """LLM成功時はその結果が採用され、永続化・取得できる。"""
        now = datetime(2026, 9, 1, 23, 0)
        llm_out = {
            "analysis": "よくできています",
            "micro_actions": ["朝に最優先タスクを片付ける"],
            "encouragement": "その調子です",
            "risk_flags": [],
        }
        with patch.object(self.engine, "_invoke_llm", return_value=llm_out):
            report = self.engine.run_analysis_once(now=now, force=True)
        assert report is not None
        self.assertEqual(report["source"], "llm")
        self.assertEqual(self.engine.get_latest_report()["encouragement"], "その調子です")

class TestIntervalSchedule(LifeCoachEngineTestBase):
    """間隔ベース・スケジューリングのテスト (既定2時間周期)。"""

    def _seed_data(self) -> None:
        """テスト用にタスク2件 (うち1件期限切れ) と習慣1件を登録する。"""
        overdue_ms = int(datetime(2026, 8, 30, 9, 0).timestamp() * 1000)
        database.create_task(
            database.Task(title="期限切れタスク", due_date=overdue_ms, priority=2),
            db_path=self.db_path,
        )
        database.create_task(
            database.Task(title="通常タスク"),
            db_path=self.db_path,
        )
        habit_id = database.create_habit(
            database.Habit(title="水を飲む"), db_path=self.db_path
        )
        # completed_today 判定は「システム上の今日」基準のため当日日付で達成記録する
        database.toggle_habit_log(habit_id, db_path=self.db_path)

    def test_collect_stats_counts(self) -> None:
        """タスク・習慣の統計が正しく集約される。"""
        self._seed_data()
        stats = self.engine._collect_stats(datetime(2026, 9, 1, 23, 0))
        self.assertEqual(stats["unfinished_count"], 2)
        self.assertEqual(stats["overdue_count"], 1)
        self.assertEqual(stats["habits_total"], 1)
        self.assertEqual(stats["habits_done"], 1)

    def test_first_run_and_interval_throttle(self) -> None:
        """起動直後 (前回実行なし) は実行 True。直後の再実行は間隔未満で False。"""
        first_ms = datetime(2026, 9, 1, 8, 0).timestamp() * 1000
        self.assertTrue(self.engine._should_run_now(first_ms))
        with patch.object(self.engine, "_invoke_llm", return_value=None):
            self.engine.run_analysis_once(now=datetime(2026, 9, 1, 8, 0))
        # 30分後 → まだ2時間に達しないのでスキップ
        plus30min_ms = datetime(2026, 9, 1, 8, 30).timestamp() * 1000
        self.assertFalse(self.engine._should_run_now(plus30min_ms))
        # 2時間経過後 → 実行
        plus2h_ms = datetime(2026, 9, 1, 10, 0).timestamp() * 1000
        self.assertTrue(self.engine._should_run_now(plus2h_ms))

    def test_idempotent_within_interval(self) -> None:
        """間隔内の2回目実行は既存レポートを再利用する (LLMを再呼び出ししない)。"""
        now = datetime(2026, 9, 1, 8, 0)
        with patch.object(self.engine, "_invoke_llm", return_value=None):
            first = self.engine.run_analysis_once(now=now)
        with patch.object(self.engine, "_invoke_llm") as mock_llm:
            second = self.engine.run_analysis_once(now=now)
        mock_llm.assert_not_called()
        self.assertEqual(first, second)

    def test_rerun_after_interval(self) -> None:
        """間隔経過後の実行はLLMを再呼び出しして新しいレポートを作る。"""
        t1 = datetime(2026, 9, 1, 8, 0)
        t2 = datetime(2026, 9, 1, 10, 1)
        with patch.object(self.engine, "_invoke_llm", return_value=None):
            self.engine.run_analysis_once(now=t1)
        with patch.object(self.engine, "_invoke_llm", return_value=None) as mock_llm:
            self.engine.run_analysis_once(now=t2)
        mock_llm.assert_called_once()

    def test_restore_last_run_ts_on_restart(self) -> None:
        """再起動時 (新インスタンス) は永続化から前回実行時刻を復元する。"""
        t1 = datetime(2026, 9, 1, 8, 0)
        with patch.object(self.engine, "_invoke_llm", return_value=None):
            self.engine.run_analysis_once(now=t1)
        restarted = LifeCoachEngine(db_path=self.db_path)
        # 30分後は間隔未満 → 実行しない (前回実行時刻が復元されている証拠)
        plus30min_ms = datetime(2026, 9, 1, 8, 30).timestamp() * 1000
        self.assertFalse(restarted._should_run_now(plus30min_ms))
        self.assertIsNotNone(restarted.get_latest_report())

    def test_analysis_triggers_suggest_refresh(self) -> None:
        """分析完了時にサジェスト (ニュース) 更新が依頼される。"""
        with patch.object(self.engine, "_invoke_llm", return_value=None), \
                patch.object(self.engine, "_refresh_suggestions") as mock_refresh:
            self.engine.run_analysis_once(now=datetime(2026, 9, 1, 8, 0))
        mock_refresh.assert_called_once()


if __name__ == "__main__":
    unittest.main()
