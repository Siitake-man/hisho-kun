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
- 第一段 (完了): main.py の asyncio ループ内 tick (care / event_reminders) を移管。
- 第二段 (2026-09-01 着手): reminder_engine / life_coach_engine の専用スレッドを
  register_periodic() (PeriodicThrottle 間引き) へ置換。
- 第二段残: suggest_engine SuggestBgWorker (初回即生成 + force_refresh 割込みの
  特殊セマンティクスがあるため、次回マイクロタスクで慎重に移行する)。
"""

import logging
import threading
import time
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

# 既定の呼び出し周期 (秒)。各プラグインは内部スロットルで実間隔を制御する。
DEFAULT_TICK_INTERVAL_SEC: float = 1.0


class PeriodicThrottle:
    """on_tick 呼び出しを interval_sec 以上の間隔に間引くプラグインラッパー。

    ProactiveScheduler の tick (既定1秒) をそのままプラグインへ渡すと、
    「本来は30秒周期」のようなエンジンが過剰頻度で実行されてしまう。
    本クラスは register_periodic() 経由でラップし、初回 tick で即実行した後、
    interval_sec 経過ごとにコールバックを発火する (起動直後の即監視を保証。
    冪等なエンジン処理と組み合わせて使用する)。

    注意: 例外の隔離は ProactiveScheduler._loop() が担うため、本クラスは
    透過的に再送出する (単一責任)。
    """

    def __init__(self, callback: Callable[[float], None], interval_sec: float) -> None:
        """間引きラッパーを生成する。

        Args:
            callback: 間引き対象のコールバック (now: float epoch秒)。
            interval_sec: 最小呼び出し間隔 (秒)。負値は 0 として扱う。
        """
        self._callback = callback
        self.interval_sec = max(0.0, float(interval_sec))
        self._last_run: Optional[float] = None
        self._lock = threading.Lock()

    def __call__(self, now: float) -> None:
        """tick を受けて間引き判定し、必要時のみコールバックを実行する。

        Args:
            now: 現在時刻 (Unix 秒)。
        """
        with self._lock:
            if self._last_run is not None and (now - self._last_run) < self.interval_sec:
                return
            self._last_run = now
        self._callback(now)


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

    def register_periodic(
        self, on_tick: Callable[[float], None], interval_sec: float, name: str = ""
    ) -> PeriodicThrottle:
        """定周期プラグインを間引きラッパー付きで登録する。

        第二段 (2026-09-01) で新設。エンジン側の専用スレッドを廃止し、
        共有スレッド上で interval_sec 間隔の呼び出しを実現する。

        Args:
            on_tick: 実行したいコールバック (now: float epoch秒)。
            interval_sec: 最小呼び出し間隔 (秒)。
            name: ログ用のプラグイン名 (省略時は関数名)。

        Returns:
            PeriodicThrottle: 登録したラッパー。unregister() に渡すと解除できる。
        """
        plugin_name = name or getattr(on_tick, "__name__", "periodic")
        throttle = PeriodicThrottle(on_tick, interval_sec)
        self.register(throttle, name=plugin_name)
        return throttle

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
        # stop() はライフサイクルの終端とみなし、登録済みプラグインもクリアする。
        # (各エンジンは自身の stop() で unregister するが、テスト孤立性と
        #  「停止済みスケジューラに幽霊プラグインが残留し再 start() 時に
        #   意図せず発火する」状態を構造的に防ぐ)
        with self._lock:
            self._plugins.clear()
            self._plugin_names.clear()
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