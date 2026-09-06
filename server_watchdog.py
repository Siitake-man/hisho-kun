"""
ネオ秘書くん - サーバー自己治癒監視モジュール (server_watchdog.py)

HTTP/WebSocket等のバックグラウンドサーバーの死活監視（周期プローブ）と
異常検知時の自己治癒再起動（Self-Healing Restart）を担当する独立モジュール。
スリープ復帰時のソケット死亡やハングアップからの自律復旧を実現します。

設計哲学 (Codebase Design / Deep Module):
- 小さなインターフェース: probe_fn と restart_fn を渡すだけで安全なスレッドループを提供。
- 終端契約 (Terminal Contract): stop() 後はゾンビ再起動が絶対に起きない安全停止を保証。
- 耐障害性 (Chaos Resistance): 連続失敗ヒステリシスと指数バックオフで過剰再起動を防止。
"""

import time
import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class ServerWatchdog:
    """サーバーの死活監視と自己治癒再起動を自律管理するウォッチドッグ。

    Attributes:
        probe_fn: サーバーの健全性を判定するコールバック (() -> bool)。
        restart_fn: サーバー再起動を実行するコールバック (() -> bool)。
        interval: ヘルスプローブの周期（秒）。
        failure_threshold: 再起動を発火させる連続プローブ失敗回数（ヒステリシス）。
        max_backoff: 再起動失敗時の最大バックオフ時間（秒）。
    """

    def __init__(
        self,
        probe_fn: Callable[[], bool],
        restart_fn: Callable[[], bool],
        interval: float = 5.0,
        failure_threshold: int = 1,
        max_backoff: float = 30.0,
        thread_name: str = "server-watchdog",
    ) -> None:
        """ServerWatchdog を初期化する。

        Args:
            probe_fn: 健全性確認コールバック。True で正常、False で異常。
            restart_fn: 再起動処理コールバック。True で再起動成功。
            interval: 監視周期秒数。
            failure_threshold: 再起動を発火させる連続失敗カウント。
            max_backoff: 連続再起動失敗時の最大待機秒数。
            thread_name: バックグラウンド監視スレッドの名称。
        """
        self._probe_fn = probe_fn
        self._restart_fn = restart_fn
        self.interval = float(interval)
        self.failure_threshold = max(1, int(failure_threshold))
        self.max_backoff = float(max_backoff)
        self.thread_name = thread_name

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._consecutive_failures: int = 0
        self._current_backoff: float = 0.0

    @property
    def is_running(self) -> bool:
        """ウォッチドッグスレッドが稼働中かどうかを返す。"""
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """ウォッチドッグ監視スレッドを起動する。"""
        if self.is_running:
            logger.debug(f"🐕 [{self.thread_name}] 既に起動しています")
            return

        self._stop_event.clear()
        self._consecutive_failures = 0
        self._current_backoff = 0.0
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name=self.thread_name
        )
        self._thread.start()
        logger.info(f"🐕 [{self.thread_name}] 自己治癒ウォッチドッグを開始しました (周期={self.interval}s)")

    def stop(self, timeout: float = 5.0) -> None:
        """ウォッチドッグを停止する（ゾンビ再起動防止の終端契約）。

        Args:
            timeout: スレッド終了の待機秒数。
        """
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._thread = None
        logger.info(f"🐕 [{self.thread_name}] 自己治癒ウォッチドッグを停止しました")

    def _run_loop(self) -> None:
        """監視メインループ。_stop_event がセットされるまで周期プローブを実行する。"""
        while not self._stop_event.wait(self.interval):
            # バックオフ待機中であればスキップ
            if self._current_backoff > 0:
                time.sleep(min(self._current_backoff, self.interval))
                self._current_backoff = max(0.0, self._current_backoff - self.interval)
                continue

            # 1. ヘルスプローブ
            try:
                healthy = self._probe_fn()
            except Exception as e:
                logger.warning(f"🐕 [{self.thread_name}] プローブ実行中に例外発生 (異常扱い): {e}")
                healthy = False

            if healthy:
                # 正常復旧
                if self._consecutive_failures > 0:
                    logger.info(f"🐕 [{self.thread_name}] サーバーの正常復帰を確認しました")
                self._consecutive_failures = 0
                self._current_backoff = 0.0
                continue

            # 2. 異常検知・ヒステリシスカウント
            self._consecutive_failures += 1
            logger.warning(
                f"🐕 [{self.thread_name}] サーバー停止/異常を検出 "
                f"({self._consecutive_failures}/{self.failure_threshold})"
            )

            if self._consecutive_failures < self.failure_threshold:
                continue

            # 3. 再起動発火
            if self._stop_event.is_set():
                break

            logger.warning(f"🐕 [{self.thread_name}] 連続失敗がしきい値に達しました → 自己治癒再起動を発火")
            try:
                success = self._restart_fn()
            except Exception as e:
                logger.error(f"🐕 [{self.thread_name}] 再起動処理中に例外発生: {e}")
                success = False

            if success:
                logger.info(f"🐕 [{self.thread_name}] 自己治癒再起動に成功しました")
                self._consecutive_failures = 0
                self._current_backoff = 0.0
            else:
                # 指数バックオフ
                self._current_backoff = min(
                    self.max_backoff,
                    max(self.interval, (2 ** min(self._consecutive_failures, 6)))
                )
                logger.warning(
                    f"🐕 [{self.thread_name}] 再起動に失敗しました。"
                    f"{self._current_backoff:.1f}秒間バックオフ待機します"
                )
