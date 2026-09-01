"""
ネオ秘書くん - AI生活コーチエンジン (life_coach_engine.py)

AI生活変化エンジン要件定義書 (docs/specs/ai_life_engine_multilang_spec.md F1/F3) の
Phase L1 実装モジュール。

ボスの生活データ（タスク完了率・期限切れ・習慣達成）を日次で統計集約し、
LLMに分析を依頼して「生活変化アクション（マイクロ提案）」を生成する。

設計意図:
    - LLM分析は既定2時間に1回の定周期バッチ (ボス確定 2026-08-31。旧: 1日1回)。
      分析の直後にサジェスト (ニュース取得＋3行サマリ) も同タイミングで更新する。
    - LLMへ送るのは集約統計のみ (タスク本文は送らない / プライバシー §4)。
    - LLM失敗時は i18n ルールベース分析へフォールバックし、機能が止まらない
      (life_dreamer / reminder_engine と同一の二段構え規律)。
    - 分析プロバイダは llm_factory の現行設定に従う (キーデシジョン §6-1 選択式)。
    - 生成レポートは SQLite (coach_reports) に永続化し、再起動後もスマホPWA
      (/api/status の life_coach フィールド) から参照可能。再起動時は前回実行
      から間隔が空いていれば即座に1回実行する。
"""

import json
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import database
from i18n import get_language, t
from proactive_scheduler import PeriodicThrottle, get_proactive_scheduler

logger = logging.getLogger(__name__)

# 分析の実行間隔 (秒)。既定は2時間 (ボス確定 2026-08-31: 「1〜2時間に1度」)
ANALYSIS_INTERVAL_SEC: float = 2 * 60 * 60

# スケジュール監視周期 (秒)。間隔判定をこの周期で行う
CHECK_INTERVAL_SEC: float = 60.0

# LLM出力のマイクロ提案の最大採用数
MAX_MICRO_ACTIONS: int = 3

# レポート保持テーブルのDDL (database.init_db とは独立に遅延生成する)。
# 主キーは実行時刻 (Unixミリ秒) — 1日複数回の分析履歴を保持する
_DDL = """
CREATE TABLE IF NOT EXISTS coach_reports (
    created_at INTEGER PRIMARY KEY,
    run_date TEXT NOT NULL,
    source TEXT NOT NULL,
    payload TEXT NOT NULL
)
"""

# 分析レポート1件を表す辞書
CoachReport = Dict[str, Any]

# 分析完了時のコールバック型 (引数はPC吹き出し表示用メッセージ)
CoachCallback = Callable[[str], None]


class LifeCoachEngine:
    """ボスの生活データを日次分析し、マイクロ提案を生成するエンジン。

    Attributes:
        _on_analysis: 分析完了時にPC側へ通知するコールバック (吹き出し表示など)
        _db_path: 集約対象・永続化先のデータベースパス (テスト注入用)
        _run_hour: 夜間バッチの実行時刻 (時)
        _catchup_hour: 朝の補完実行を許可する最早時刻 (時)
        _interval_sec: スケジュール監視周期 (秒)
    """

    def __init__(
        self,
        on_analysis: Optional[CoachCallback] = None,
        db_path: str = "neo_secretary.db",
        interval_sec: float = ANALYSIS_INTERVAL_SEC,
        check_interval_sec: float = CHECK_INTERVAL_SEC,
    ) -> None:
        """エンジンを初期化する (スレッドは start() 呼び出しまで起動しない)。

        Args:
            on_analysis: 分析完了時のコールバック (任意)
            db_path: データベースパス
            interval_sec: 分析の実行間隔 (秒)。既定2時間
            check_interval_sec: 間隔判定の監視周期 (秒)
        """
        self._on_analysis = on_analysis
        self._db_path = db_path
        self._interval_sec = interval_sec
        self._check_interval_sec = check_interval_sec
        self._stop = threading.Event()
        self._throttle: Optional[PeriodicThrottle] = None
        self._lock = threading.Lock()
        self._latest_report: Optional[CoachReport] = None
        # 前回実行時刻 (Unixミリ秒)。永続化から復元し、再起動後も間隔判定を正しく行う
        self._last_run_ts_ms: float = 0.0
        self._ensure_table()
        self._restore_latest_report()

    # ---------------------------------------------------------------------
    # 公開API
    # ---------------------------------------------------------------------
    def start(self) -> None:
        """共有スケジューラへ定周期スケジュール監視を登録する (二重起動は無視)。

        専用スレッドは廃止し、ProactiveScheduler の単一デーモンスレッド上で
        check_interval_sec 周期 (PeriodicThrottle 間引き) で間隔判定を実行する。
        """
        if self.is_running():
            logger.debug("LifeCoachEngine は既に起動済みのため起動をスキップしました")
            return
        self._stop.clear()
        scheduler = get_proactive_scheduler()
        self._throttle = scheduler.register_periodic(
            self._scheduled_tick,
            interval_sec=self._check_interval_sec,
            name="LifeCoachEngine",
        )
        scheduler.start()
        logger.info(
            "🧭 [LifeCoach] 生活コーチエンジンを起動しました (実行間隔: %.1f時間)",
            self._interval_sec / 3600.0,
        )

    def stop(self) -> None:
        """スケジュール監視を停止し、共有スケジューラから登録を解除する (冪等)。"""
        self._stop.set()
        throttle = self._throttle
        if throttle is not None:
            get_proactive_scheduler().unregister(throttle)
            self._throttle = None
            logger.info("🧭 [LifeCoach] 生活コーチエンジンを停止しました")

    def is_running(self) -> bool:
        """スケジュール監視が共有スケジューラへ登録済みかを返す。"""
        return self._throttle is not None

    def get_latest_report(self) -> Optional[CoachReport]:
        """最新の分析レポートのコピーを返す (/api/status 用・スレッドセーフ)。

        Returns:
            レポート未生成 (または復元失敗) の場合は None
        """
        with self._lock:
            if self._latest_report is None:
                return None
            return dict(self._latest_report)

    def run_analysis_once(
        self, now: Optional[datetime] = None, force: bool = False
    ) -> Optional[CoachReport]:
        """生活データを1回分分析し、レポートを生成・永続化する。

        テスト容易性のためスケジュールループから本体を分離している。
        前回実行から interval_sec 未満しか経過していない場合は既存レポートを
        再利用する (force=True で無視)。

        Args:
            now: 基準時刻。None ならシステム時刻を使用
            force: True の場合は間隔判定を無視して強制再分析する

        Returns:
            生成 (または再利用) したレポート
        """
        now = now or datetime.now()
        now_ms = float(now.timestamp() * 1000)

        if not force:
            latest = self._load_latest_report()
            if latest is not None and (now_ms - self._last_run_ts_ms) < self._interval_sec * 1000:
                with self._lock:
                    self._latest_report = latest
                return latest

        stats = self._collect_stats(now)
        report = self._invoke_llm(stats)
        source = "llm"
        if report is None:
            report = self._build_fallback_report(stats)
            source = "fallback"

        report.update({
            "run_date": now.strftime("%Y-%m-%d"),
            "source": source,
            "generated_at": int(now.timestamp() * 1000),
        })
        self._save_report(report)

        with self._lock:
            self._latest_report = report
        self._last_run_ts_ms = float(report["generated_at"])

        # ニュース (サジェスト) も同じタイミングで更新する (ボス確定 2026-08-31)
        self._refresh_suggestions()

        message = f"🧭 {t('coach.analysis_title')} {report['encouragement']}"
        logger.info(
            "🧭 [LifeCoach] 日次分析完了 (%s): actions=%d risks=%d",
            source, len(report["micro_actions"]), len(report["risk_flags"]),
        )
        self._dispatch(message)
        return report

    # ---------------------------------------------------------------------
    # 内部実装: 統計集約 (LLMへ送るのはここで作った統計のみ)
    # ---------------------------------------------------------------------
    def _collect_stats(self, now: datetime) -> Dict[str, Any]:
        """DBから生活統計を集約する (タスク本文は LLM へ送らない)。

        Args:
            now: 基準時刻

        Returns:
            統計辞書 (未完了数・期限切れ数・今日完了数・習慣達成率など)
        """
        today_str = now.strftime("%Y-%m-%d")
        now_ms = int(now.timestamp() * 1000)

        unfinished = database.get_tasks(limit=200, db_path=self._db_path)
        overdue = [task for task in unfinished if task.due_date and task.due_date < now_ms]
        completed_today = 0
        for task in database.get_tasks(status="completed", limit=200, db_path=self._db_path):
            completed_day = datetime.fromtimestamp(task.updated_at / 1000.0).strftime("%Y-%m-%d")
            if completed_day == today_str:
                completed_today += 1

        habits = database.get_habits_with_status(db_path=self._db_path)
        habits_done = sum(1 for h in habits if h.completed_today)
        streaks = [h.streak for h in habits]
        avg_streak = (sum(streaks) / len(streaks)) if streaks else 0.0

        return {
            "unfinished_count": len(unfinished),
            "overdue_count": len(overdue),
            "completed_today": completed_today,
            "habits_total": len(habits),
            "habits_done": habits_done,
            "avg_streak": round(avg_streak, 1),
            "best_streak": max(streaks) if streaks else 0,
            "overdue_ratio": round(len(overdue) / len(unfinished), 2) if unfinished else 0.0,
        }

    # ---------------------------------------------------------------------
    # 内部実装: LLM分析とフォールバック
    # ---------------------------------------------------------------------
    def _invoke_llm(self, stats: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """LLMに生活分析を依頼し、固定スキーマのJSONへ整形する。

        Args:
            stats: _collect_stats の統計辞書

        Returns:
            スキーマ検証済みレポート辞書。LLM失敗・解析失敗時は None
        """
        prompt = (
            "You are a caring life coach embedded in a desktop pet app. "
            "Analyze the user's daily statistics and output coaching advice.\n"
            f"Statistics (JSON): {json.dumps(stats, ensure_ascii=False)}\n"
            f"Output language: {get_language()}\n\n"
            "Output ONLY this JSON (no explanations, no code fences):\n"
            '{"analysis": "<1-2 sentences>", '
            '"micro_actions": ["<tomorrow-action>", "..."], '
            '"encouragement": "<one warm sentence>", '
            '"risk_flags": ["<short risk label>", "..."]}\n'
            f"Rules: micro_actions must be {MAX_MICRO_ACTIONS} items or fewer, "
            "each a single concrete small action. risk_flags may be empty."
        )
        try:
            from llm_factory import get_llm_factory

            model = get_llm_factory().create_model(temperature=0.7)
            response = model.invoke(prompt)
            raw = response.content if isinstance(response.content, str) else str(response.content)
        except Exception as e:
            logger.info("🧭 [LifeCoach] LLM呼び出し失敗、ルールにフォールバック: %s", e)
            return None

        parsed = self._parse_llm_json(raw)
        if parsed is None:
            logger.info("🧭 [LifeCoach] LLM出力の解析に失敗、ルールにフォールバック")
        return parsed

    def _parse_llm_json(self, raw: str) -> Optional[Dict[str, Any]]:
        """LLM出力からJSON部分を抽出してスキーマ検証する (揺らぎに耐性を持たせる)。

        Args:
            raw: LLM生出力

        Returns:
            検証済みレポート辞書。抽出・検証失敗時は None
        """
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None

        analysis = str(data.get("analysis", "")).strip()
        encouragement = str(data.get("encouragement", "")).strip()
        actions_raw = data.get("micro_actions", [])
        risks_raw = data.get("risk_flags", [])
        if not analysis or not encouragement or not isinstance(actions_raw, list):
            return None
        micro_actions = [str(a).strip() for a in actions_raw if str(a).strip()]
        if not micro_actions:
            return None
        risk_flags = (
            [str(r).strip() for r in risks_raw if str(r).strip()]
            if isinstance(risks_raw, list) else []
        )
        return {
            "analysis": analysis,
            "micro_actions": micro_actions[:MAX_MICRO_ACTIONS],
            "encouragement": encouragement,
            "risk_flags": risk_flags,
        }

    def _build_fallback_report(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """LLM失敗時のルールベース分析レポートを組み立てる (i18n準拠)。

        Args:
            stats: _collect_stats の統計辞書

        Returns:
            レポート辞書 (source="fallback")
        """
        analysis = t(
            "coach.fallback_analysis",
            unfinished=stats["unfinished_count"],
            overdue=stats["overdue_count"],
            habits_done=stats["habits_done"],
            habits_total=stats["habits_total"],
        )
        micro_actions: List[str] = []
        if stats["overdue_count"] > 0:
            micro_actions.append(t("coach.fallback_action_overdue"))
        if not micro_actions:
            micro_actions.append(t("coach.fallback_action_rest"))
        micro_actions = micro_actions[:MAX_MICRO_ACTIONS]

        risk_flags: List[str] = []
        if stats["overdue_count"] > 0:
            risk_flags.append(t("coach.fallback_risk_overdue"))
        if stats["habits_total"] > 0 and stats["habits_done"] < stats["habits_total"] / 2:
            risk_flags.append(t("coach.fallback_risk_habit"))

        return {
            "analysis": analysis,
            "micro_actions": micro_actions,
            "encouragement": t("coach.fallback_encouragement"),
            "risk_flags": risk_flags,
        }

    # ---------------------------------------------------------------------
    # 内部実装: 永続化 (coach_reports テーブル)
    # ---------------------------------------------------------------------
    def _ensure_table(self) -> None:
        """レポート保持テーブルを遅延生成する (冪等)。"""
        try:
            with database.get_db_connection(self._db_path) as conn:
                conn.cursor().execute(_DDL)
        except Exception as e:
            logger.warning("🧭 [LifeCoach] coach_reports テーブル生成に失敗: %s", e)

    def _save_report(self, report: CoachReport) -> None:
        """レポートをSQLiteへ永続化する (ベストエフォート)。"""
        try:
            with database.get_db_connection(self._db_path) as conn:
                conn.cursor().execute(
                    "INSERT OR REPLACE INTO coach_reports "
                    "(created_at, run_date, source, payload) VALUES (?, ?, ?, ?)",
                    (
                        report["generated_at"],
                        report["run_date"],
                        report["source"],
                        json.dumps(report, ensure_ascii=False),
                    ),
                )
        except Exception as e:
            logger.warning("🧭 [LifeCoach] レポート保存に失敗: %s", e)

    def _load_latest_report(self) -> Optional[CoachReport]:
        """最新のレポートをSQLiteから読み出す。

        Returns:
            レポート辞書。存在しない場合は None
        """
        try:
            with database.get_db_connection(self._db_path) as conn:
                cur = conn.cursor().execute(
                    "SELECT payload, created_at FROM coach_reports "
                    "ORDER BY created_at DESC LIMIT 1"
                )
                row = cur.fetchone()
            if row is None:
                return None
            data = json.loads(row[0])
            if isinstance(data, dict):
                self._last_run_ts_ms = float(row[1])
                return data
            return None
        except Exception as e:
            logger.warning("🧭 [LifeCoach] レポート読み出しに失敗: %s", e)
            return None

    def _restore_latest_report(self) -> None:
        """起動時に最新レポートと前回実行時刻を復元する (失敗しても起動は継続)。"""
        data = self._load_latest_report()
        if data is not None:
            with self._lock:
                self._latest_report = data

    # ---------------------------------------------------------------------
    # 内部実装: スケジューラ
    # ---------------------------------------------------------------------
    def _scheduled_tick(self, now: float) -> None:
        """スケジューラの tick から呼ばれる1回分の間隔判定・分析実行。

        Args:
            now: 現在時刻 (Unix 秒・プラグイン契約で必須だが本処理では未使用)。
        """
        try:
            if self._should_run_now():
                self.run_analysis_once()
        except Exception as e:
            logger.warning("🧭 [LifeCoach] スケジュール実行中にエラー (次周期で継続): %s", e)

    def _should_run_now(self, now_ms: Optional[float] = None) -> bool:
        """前回実行からの経過時間が実行間隔に達したか判定する。

        起動直後 (前回実行不明) は最初の周期で1回実行する。

        Args:
            now_ms: 現在時刻 (Unixミリ秒)。None ならシステム時刻を使用

        Returns:
            実行すべき場合 True
        """
        now_ms = now_ms if now_ms is not None else time.time() * 1000.0
        return (now_ms - self._last_run_ts_ms) >= self._interval_sec * 1000

    def _refresh_suggestions(self) -> None:
        """サジェスト (ニュース取得＋AIサマリ) の再生成を依頼する (ベストエフォート)。

        分析と同じタイミングでニュースを更新する (ボス確定 2026-08-31)。
        suggest_engine 未初期化の環境 (単体テスト等) では何もしない。
        """
        try:
            from suggest_engine import get_suggestion_engine

            get_suggestion_engine().request_refresh()
        except Exception as e:
            logger.debug("🧭 [LifeCoach] サジェスト更新依頼をスキップ: %s", e)

    def _dispatch(self, message: str) -> None:
        """PC側コールバックへ分析完了をディスパッチする (ベストエフォート)。

        Args:
            message: 吹き出し表示用メッセージ
        """
        if not callable(self._on_analysis):
            return
        try:
            self._on_analysis(message)
        except Exception as e:
            logger.warning("🧭 [LifeCoach] コールバック実行に失敗しました: %s", e)


# =============================================================================
# シングルトン提供
# =============================================================================
_engine: Optional[LifeCoachEngine] = None
_engine_lock = threading.Lock()


def get_life_coach_engine(
    on_analysis: Optional[CoachCallback] = None,
    db_path: str = "neo_secretary.db",
) -> LifeCoachEngine:
    """LifeCoachEngine のシングルトンを取得する。

    Args:
        on_analysis: 初回生成時に設定するPC側通知コールバック (任意)。
                    既存インスタンスが存在し callback 未設定の場合は後付けする。
        db_path: データベースパス (初回生成時のみ有効)

    Returns:
        LifeCoachEngine のシングルトンインスタンス
    """
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = LifeCoachEngine(on_analysis=on_analysis, db_path=db_path)
    elif on_analysis is not None and _engine._on_analysis is None:
        _engine._on_analysis = on_analysis
    return _engine
