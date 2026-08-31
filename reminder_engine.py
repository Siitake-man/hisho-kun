"""
ネオ秘書くん - 時刻ベースリマインダーエンジン (reminder_engine.py)

roadmap 3.1「時刻ベースのリマインダー」の実装モジュール。
タスクの期限 (due_date) と予定の開始時刻 (start_time) を定周期で監視し、
期限の接近を PC ペットの吹き出し (コールバック経由) と
スマホ PWA (/api/status の due_reminders フィールド) へ通知します。

設計意図:
    - DB クエリは 30 秒周期の専用デーモンスレッドでのみ実行し、
      GUI / HTTP ハンドラからは完全に分離する (短期改善 Step 2 確立の
      GIL 分離原則を踏襲。ポーリング側はキャッシュ参照のみ)。
    - 通知済みは database.reminders_sent テーブルへ冪等記録するため、
      アプリ再起動後も同じ対象を二重通知しない。
    - GUI 未起動 (MCP単体起動・テスト環境) でもコールバック無しで動作する。
"""

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

import database

logger = logging.getLogger(__name__)

# 期限の何分前で通知するか (TickTick 既定体験に準拠した暫定定数。設定UIは後続)
REMINDER_LEAD_MINUTES: int = 10

# 監視周期 (秒)。DB負荷と通知精度のトレードオフで30秒を採用
CHECK_INTERVAL_SEC: float = 30.0

# スマホ向けペイロードに保持する通知の有効期間 (秒)
PHONE_TTL_SEC: float = 300.0

# 期限を過ぎてからこの時間以内なら「取りこぼし通知」する (経過後は黙秘)
OVERDUE_GRACE_MINUTES: int = 30

# リマインダー対象1件を表す辞書
ReminderItem = Dict[str, Any]

# 通知時のコールバック型 (引数は通知メッセージ)
ReminderCallback = Callable[[str], None]


class ReminderEngine:
    """タスク・予定の期限接近を定周期で監視し通知するエンジン。

    Attributes:
        _on_reminder: PC側への通知コールバック (吹き出し表示など)
        _db_path: 監視対象のデータベースパス (テスト注入用)
        _lead_minutes: 期限の何分前で通知するか
        _interval_sec: 監視周期 (秒)
    """

    def __init__(
        self,
        on_reminder: Optional[ReminderCallback] = None,
        db_path: str = "neo_secretary.db",
        lead_minutes: int = REMINDER_LEAD_MINUTES,
        interval_sec: float = CHECK_INTERVAL_SEC,
    ) -> None:
        """エンジンを初期化する (スレッドは start() 呼び出しまで起動しない)。

        Args:
            on_reminder: PC側への通知コールバック (任意)
            db_path: 監視対象のデータベースパス
            lead_minutes: 期限の何分前で通知するか
            interval_sec: 監視周期 (秒)
        """
        self._on_reminder = on_reminder
        self._db_path = db_path
        self._lead_minutes = lead_minutes
        self._interval_sec = interval_sec
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._pending_for_phone: List[ReminderItem] = []

    def start(self) -> None:
        """監視デーモンスレッドを起動する (二重起動は無視)。"""
        if self._thread is not None and self._thread.is_alive():
            logger.debug("ReminderEngine は既に起動済みのため起動をスキップしました")
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="ReminderEngine")
        self._thread.start()
        logger.info(f"⏰ リマインダーエンジンを起動しました (周期: {self._interval_sec}秒 / 通知: {self._lead_minutes}分前)")

    def stop(self) -> None:
        """監視ループを停止する (スレッドは次の周期で終了)。"""
        self._stop.set()

    def is_running(self) -> bool:
        """監視スレッドが稼働中かを返す。"""
        return self._thread is not None and self._thread.is_alive()

    def _loop(self) -> None:
        """定周期で check_once() を呼ぶデーモンループ。"""
        while not self._stop.wait(self._interval_sec):
            try:
                self.check_once()
            except Exception as e:
                logger.warning(f"リマインダー監視中にエラー (次周期で継続): {e}")

    def check_once(self, now_ms: Optional[int] = None) -> List[ReminderItem]:
        """現在時刻を基準に期限接近の対象を1回分検査し、新規分を通知する。

        テスト容易性のため周期ループから本体を分離している。

        Args:
            now_ms: 現在時刻 (Unix ミリ秒)。None ならシステム時刻を使用

        Returns:
            今回新たに通知した対象のリスト
        """
        now = now_ms if now_ms is not None else int(time.time() * 1000)
        window_end = now + self._lead_minutes * 60_000
        # 期限切れからの取りこぼし通知の下限 (これより古いものは黙秘)
        stale_floor = now - OVERDUE_GRACE_MINUTES * 60_000
        fired: List[ReminderItem] = []

        # 1. タスクの期限 (未完了のみ。get_tasks(status=None) は completed を除外)
        for t in database.get_tasks(status=None, db_path=self._db_path):
            if not t.due_date or t.id is None:
                continue
            if not (stale_floor <= t.due_date <= window_end):
                continue
            if database.is_reminder_sent("task", t.id, db_path=self._db_path):
                continue
            database.mark_reminder_sent("task", t.id, db_path=self._db_path)
            message = f"⏰ タスク「{t.title}」の期限が近づいています！"
            item: ReminderItem = {
                "type": "task",
                "id": t.id,
                "title": t.title,
                "message": message,
                "due_at": t.due_date,
                "sent_at": now,
            }
            fired.append(item)
            self._dispatch(message)

        # 2. 予定の開始時刻
        for e in database.get_upcoming_events(days=1, db_path=self._db_path):
            if e.id is None:
                continue
            if not (stale_floor <= e.start_time <= window_end):
                continue
            if database.is_reminder_sent("event", e.id, db_path=self._db_path):
                continue
            database.mark_reminder_sent("event", e.id, db_path=self._db_path)
            message = f"⏰ まもなく「{e.title}」が始まります！"
            fired.append({
                "type": "event",
                "id": e.id,
                "title": e.title,
                "message": message,
                "due_at": e.start_time,
                "sent_at": now,
            })
            self._dispatch(message)

        if fired:
            with self._lock:
                self._pending_for_phone.extend(fired)
                self._prune_phone_cache(now)
            logger.info(f"⏰ リマインダーを {len(fired)} 件通知しました: {[i['title'] for i in fired]}")

        return fired

    def get_pending_for_phone(self, now_ms: Optional[int] = None) -> List[ReminderItem]:
        """スマホ PWA (/api/status) へ渡す未過期の通知一覧を返す。

        Args:
            now_ms: 現在時刻 (Unix ミリ秒)。None ならシステム時刻を使用

        Returns:
            PHONE_TTL_SEC 以内に通知した対象のコピー (辞書リスト)
        """
        now = now_ms if now_ms is not None else int(time.time() * 1000)
        with self._lock:
            self._prune_phone_cache(now)
            return [dict(item) for item in self._pending_for_phone]

    def _prune_phone_cache(self, now_ms: int) -> None:
        """スマホ向けキャッシュから有効期限切れの通知を除去する。

        呼び出し元で self._lock の取得が必須 (内部ヘルパー)。

        Args:
            now_ms: 現在時刻 (Unix ミリ秒)
        """
        self._pending_for_phone = [
            item for item in self._pending_for_phone
            if (now_ms - item.get("sent_at", 0)) / 1000.0 <= PHONE_TTL_SEC
        ]

    def _dispatch(self, message: str) -> None:
        """PC側コールバックへ通知をディスパッチする (ベストエフォート)。

        Args:
            message: 通知メッセージ
        """
        if not callable(self._on_reminder):
            return
        try:
            self._on_reminder(message)
        except Exception as e:
            logger.warning(f"リマインダーのコールバック実行に失敗しました: {e}")


# モジュール単位のシングルトン
_engine: Optional[ReminderEngine] = None


def get_reminder_engine(on_reminder: Optional[ReminderCallback] = None) -> ReminderEngine:
    """リマインダーエンジンのシングルトンを取得する。

    Args:
        on_reminder: 初回生成時に設定するPC側通知コールバック (任意)。
                    既存インスタンスが存在し callback 未設定の場合は後付けする。

    Returns:
        ReminderEngine のシングルトンインスタンス
    """
    global _engine
    if _engine is None:
        _engine = ReminderEngine(on_reminder=on_reminder)
    elif on_reminder is not None and _engine._on_reminder is None:
        _engine._on_reminder = on_reminder
    return _engine

