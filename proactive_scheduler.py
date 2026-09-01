"""
ネオ秘書くん - 自律通知スケジューラー (proactive_scheduler.py)

proactive_engine / reminder_engine / suggest_engine / life_coach_engine 等に
分散していた周期タイマーを 1本のデーモンスレッドへ集約する Deep Module
(2026-09-01 3周レビュー P2「スケジューラー共通化」対応)。

設計 (Deep Module):
- 小さな契約: register(on_tick) するだけで、共有スレッドが定周期で呼び出す。
  各エンジンは内部に持つ間隔スロットル (last_care_time 等) をそのまま使い続ける
  ため、呼び出し周期は「最小tick」であり、エンジン個別のスレッド数は 0 にできる。
- プラグインの例外は握りつぶさずログ出力し、スケジューラ全体を停止させない。
- stop() で確実にスレッドを停止する (アプリ終了時のスレッドリーク防止)。

移行方針 (段階移行):
- 第一段 (本対応): main.py の asyncio ループ内 tick (care / event_reminders) を移管。
- 第二段以降: suggest_engine SuggestBgWorker / life_coach_engine / reminder_engine
  の個別スレッドを順次 register() へ置換する。
"""

import logging
import threading
import time
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

# 既定の呼び出し周期 (秒)。各プラグインは内部スロットルで実間隔を制御する。
DEFAULT_TICK_INTERVAL_SEC: float = 1.0


class ProactiveScheduler:
    """登録されたプラグイン (on_tick 関数) を定周期で呼び出す単一スレッド。

    Tkinter/asyncio ループから周期処理を分離し、UIスレッドの負荷と
    エンジンごとのタイマー重複 (Shotgun Surgery) を解消する。

    Attributes:
        tick_interval_sec: on_tick を呼び出す周期 (秒)。0.1 未満は 0.1 にクランプ。
    """

    def __init__(self, tick_interval_sec: float = DEFAULT_TICK_INTERVAL_SEC) -> None:
        self.tick_interval_sec = max(0.1, float(tick_interval_sec))
        self._plugins: List[Callable[[float], None]] = []
        self._plugin_names: List[str] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def register(self, on_tick: Callable[[float], None], name: str = "") -> None:
        """周期実行するプラグインを登録する。

        Args:
            on_tick: (now: float epoch秒) を引数に取るコールバック。
                     例外を投げてもスケジューラは停止しない。
            name: ログ用のプラグイン名 (省略時は関数名)。
        """
        plugin_name = name or getattr(on_tick, "__name__", "unnamed")
        with self._lock:
            self._plugins.append(on_tick)
            self._plugin_names.append(plugin_name)
        logger.info(
            f"⏱️ [Scheduler] プラグイン登録: {plugin_name} (登録数: {len(self._plugins)})"
        )

    def unregister(self, on_tick: Callable[[float], None]) -> bool:
        """登録済みプラグインを解除する。

        Args:
            on_tick: register() に渡したものと同一の callable。

        Returns:
            bool: 解除に成功した場合 True、未登録の場合 False。
        """
        with self._lock:
            try:
                idx = self._plugins.index(on_tick)
            except ValueError:
                return False
            self._plugins.pop(idx)
            self._plugin_names.pop(idx)
        logger.info(f"⏱️ [Scheduler] プラグイン解除 (登録数: {len(self._plugins)})")
        return True

    @property
    def plugin_count(self) -> int:
        """登録中のプラグイン数。"""
        with self._lock:
            return len(self._plugins)

    @property
    def is_running(self) -> bool:
        """スケジューラスレッドが稼働中かどうか。"""
        return bool(self._thread is not None and self._thread.is_alive())

    def start(self) -> None:
        """スケジューラスレッドを起動する (二重起動時は無視)。"""
        if self.is_running:
            logger.debug("⏱️ [Scheduler] 既に起動済みのため start() をスキップ")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="ProactiveScheduler"
        )
        self._thread.start()
        logger.info(
            f"⏱️ [Scheduler] 起動しました "
            f"(周期: {self.tick_interval_sec}秒 / プラグイン: {self.plugin_count})"
        )

    def stop(self, timeout_sec: float = 3.0) -> None:
        """スケジューラスレッドを停止する (アプリ終了時)。

        Args:
            timeout_sec: スレッド終了を待つ最大秒数。
        """
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout_sec)
        self._thread = None
        logger.info("⏱️ [Scheduler] 停止しました")

    def _loop(self) -> None:
        """スケジューラのメインループ。プラグイン例外を隔离して継続する。"""
        while not self._stop_event.wait(self.tick_interval_sec):
            now = time.time()
            # ロック内はコピーのみ。プラグイン実行中に register/unregister されても安全。
            with self._lock:
                plugins = list(self._plugins)
                names = list(self._plugin_names)
            for plugin, name in zip(plugins, names):
                try:
                    plugin(now)
                except Exception as e:
                    logger.error(
                        f"⏱️ [Scheduler] プラグイン '{name}' で例外 (次周期へ継続): {e}",
                        exc_info=True,
                    )


_global_scheduler: Optional[ProactiveScheduler] = None
_scheduler_init_lock = threading.Lock()


def get_proactive_scheduler() -> ProactiveScheduler:
    """ProactiveScheduler のシングルトンを取得する。

    Returns:
        ProactiveScheduler: プロセス共通のスケジューラインスタンス。
    """
    global _global_scheduler
    with _scheduler_init_lock:
        if _global_scheduler is None:
            _global_scheduler = ProactiveScheduler()
        return _global_scheduler