#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - HTTPサーバー基盤 ＆ ライフサイクル管理 (httpd_core / S5 Seam).

(server/httpd_core.py)

目的:
    Fat モジュール `local_sync_server.py` から、HTTPサーバーのコア通信基盤
    (QuietThreadingHTTPServer) およびバックグラウンド稼働・自己治癒watchdog
    (LocalSyncServer, get_sync_server) を独立した Deep Module として切り出す。

責務:
    1. クライアント日常切断（WinError 10053等）のトレースバック抑制 (QuietThreadingHTTPServer)
    2. 自己治癒 watchdog 連携とポート再バインド保証 (LocalSyncServer)
    3. 自律生活ドリーマー (LifeDreamer) 連携およびPCペット状態ミラー
    4. サーバー起動・停止のグローバルライフサイクル統括 (get_sync_server)
"""

from __future__ import annotations

import logging
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Optional, Type

import sync_config
from server_watchdog import ServerWatchdog

# 親ロガー local_sync_server への伝播 (propagation) を担保する階層ロガー
logger = logging.getLogger("local_sync_server.httpd_core")

# デフォルトポート (sync_config を唯一の情報源とする)
SERVER_PORT: int = sync_config.SERVER_PORT


class QuietThreadingHTTPServer(ThreadingHTTPServer):
    """クライアント切断時のトレースバック出力を抑制するHTTPサーバー。

    PWA のポーリング中にスマホ側が画面を閉じる等で発生する
    ``ConnectionAbortedError`` (WinError 10053) や ``ConnectionResetError``
    は日常的な切断であり、DEBUG レベルに格下げして起動ログのノイズを
    排除する。それ以外の予期しない例外は従来どおり WARNING で出力する。
    """

    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request: Any, client_address: tuple[str, int]) -> None:
        """リクエスト処理中の例外をログレベルを分けて記録する。

        Args:
            request: リクエストオブジェクト (ソケット等)。
            client_address: クライアントのアドレス (host, port)。
        """
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
            logger.debug(
                "クライアント切断 (%s:%s): %s",
                client_address[0],
                client_address[1],
                type(exc).__name__,
            )
        else:
            logger.warning(
                "リクエスト処理中に例外 (%s:%s): %s",
                client_address[0],
                client_address[1],
                exc,
                exc_info=True,
            )


class LocalSyncServer:
    """バックグラウンドで稼働するローカル同期サーバー。

    2026-09-03 (Block 2 / 2026-09-06 分離): スリープ復帰等で serve_forever スレッドが死亡した場合に
    周期ヘルスプローブで検出し、解決済みポートへ再バインドする自己治癒watchdog (server_watchdog.py) を備える。
    """

    def __init__(
        self,
        port: int = SERVER_PORT,
        handler_class: Optional[Type[BaseHTTPRequestHandler]] = None,
    ) -> None:
        """ローカル同期サーバーを初期化する。

        Args:
            port: 待受ポート番号 (0 の場合はエフェメラルポート)。
            handler_class: リクエストハンドラクラス (未指定時は DeskPetSyncHandler を遅延解決)。
        """
        self.port: int = port
        self.handler_class: Optional[Type[BaseHTTPRequestHandler]] = handler_class
        self.httpd: Optional[QuietThreadingHTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        # watchdog 用状態
        self._bound_port: Optional[int] = None  # port=0 (エフェメラル) 時の解決済みポート
        self._watchdog_interval: float = 5.0
        self._watchdog: ServerWatchdog = ServerWatchdog(
            probe_fn=self.is_healthy,
            restart_fn=self._restart_httpd,
            interval=self._watchdog_interval,
            failure_threshold=3,
            thread_name="sync-server-watchdog",
        )

    def _get_handler_class(self) -> Type[BaseHTTPRequestHandler]:
        """リクエストハンドラクラスを解決する (DI または Facade 遅延インポート)."""
        if self.handler_class is not None:
            return self.handler_class
        import local_sync_server
        return local_sync_server.DeskPetSyncHandler

    @property
    def watchdog_interval(self) -> float:
        """watchdog の監視インターバル (秒)."""
        return self._watchdog.interval

    @watchdog_interval.setter
    def watchdog_interval(self, val: float) -> None:
        self._watchdog_interval = float(val)
        self._watchdog.interval = float(val)

    @property
    def _watchdog_thread(self) -> Optional[threading.Thread]:
        """既存テスト後方互換用: watchdogスレッド参照."""
        return self._watchdog._thread

    def _start_httpd(self) -> bool:
        """HTTPサーバーを生成してバックグラウンドスレッドで起動する。

        再起動時は _bound_port (解決済みポート) へ再バインドし、
        エフェメラルポートの再抽選によるポート変更を防止する。

        Returns:
            bool: 起動に成功した場合は True (ポート競合等は False)。
        """
        bind_port = self._bound_port if self._bound_port is not None else self.port
        handler_cls = self._get_handler_class()
        try:
            self.httpd = QuietThreadingHTTPServer(("0.0.0.0", bind_port), handler_cls)
        except OSError as e:
            logger.error(f"📱 [Watchdog] 同期サーバーのバインドに失敗しました (ポート={bind_port}): {e}")
            return False
        self._bound_port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        logger.info(
            f"📱 [Agent Bridge Hub] Desk Pet 同期サーバーが起動しました: "
            f"http://localhost:{self._bound_port} (LAN/Bluetooth対応)"
        )
        return True

    def is_healthy(self) -> bool:
        """サーバースレッドの生存とループバック疎通を確認する。

        Returns:
            bool: スレッドが生存し、ループバック接続に成功する場合は True。
        """
        if self.thread is None or not self.thread.is_alive():
            return False
        if self._bound_port is None:
            return False
        try:
            with socket.create_connection(("127.0.0.1", self._bound_port), timeout=2.0):
                return True
        except OSError:
            return False

    def _restart_httpd(self) -> bool:
        """旧サーバーを片付けて自己治癒再起動を行う。

        Returns:
            bool: 再起動に成功した場合は True。
        """
        old_httpd = self.httpd
        if self.thread is not None and self.thread.is_alive() and old_httpd is not None:
            # スレッドは生存だが疎通しない (ハング等) → shutdown を要求して出口を待つ
            old_httpd.shutdown()
        if old_httpd is not None:
            try:
                old_httpd.server_close()
            except OSError as e:
                logger.debug(f"📱 [Watchdog] 旧サーバーソケットの解放に失敗: {e}")
        success = self._start_httpd()
        if success:
            logger.warning("📱 [Watchdog] 同期サーバーを自己治癒再起動しました")
        else:
            logger.warning("📱 [Watchdog] 同期サーバーの自己治癒再起動に失敗 (次周期で再試行)")
        return success

    def start(self, gui: Optional[Any] = None) -> None:
        """バックグラウンドスレッドでサーバーを起動する."""
        if gui:
            try:
                import local_sync_server
                local_sync_server.set_gui_instance(gui)
            except Exception as e:
                logger.warning(f"GUIインスタンスの登録エラー: {e}")

        # 🌈 自律生活ドリーマーエンジンの起動（PCペットミラー用コールバック登録）
        try:
            from life_dreamer import get_life_dreamer
            dreamer = get_life_dreamer()
            if gui is not None:
                dreamer.set_on_state_change(lambda state: self._mirror_to_pc_pet(gui, state))
            dreamer.start()
        except Exception as e:
            logger.warning(f"🌈 [LifeDreamer] 起動をスキップしました: {e}")

        if not self._start_httpd():
            logger.warning("Desk Pet 同期サーバーの起動をスキップしました（ポート競合など）")
            return
        self._watchdog.start()

    @staticmethod
    def _mirror_to_pc_pet(gui: Any, state: Dict[str, Any]) -> None:
        """ライフステートの変化をPCデスクトップペットへミラーする。

        ※ LifeDreamer のスレッドから呼ばれるため、GUI操作は必ず
        post_action 経由でメインスレッドへディスパッチすること。
        """
        try:
            activity = state.get("current_activity", "resting")
            message = state.get("message", "")
            from life_dreamer import ACTIVITY_PET_STATE_MAP
            pet_state = ACTIVITY_PET_STATE_MAP.get(activity, "idle")
            if message:
                gui.post_action(gui.update_message, f"🌈 {message}")
            gui.post_action(gui.set_pet_state, pet_state, duration_ms=8000)
        except Exception as e:
            logger.debug(f"LifeDreamer PCペットミラーエラー: {e}")

    def stop(self) -> None:
        """サーバーとwatchdogを停止する (ゾンビ再起動を防止する終端契約)。"""
        self._watchdog.stop(timeout=5.0)
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Desk Pet 同期サーバーを停止しました")


# グローバルシングルトン
_global_sync_server: Optional[LocalSyncServer] = None


def get_sync_server(gui: Optional[Any] = None) -> LocalSyncServer:
    """LocalSyncServer のシングルトンインスタンスを返却する。

    Args:
        gui: GUI インスタンス (渡された場合は登録を行う)。

    Returns:
        LocalSyncServer: グローバル同期サーバーインスタンス。
    """
    global _global_sync_server
    if _global_sync_server is None:
        _global_sync_server = LocalSyncServer()
    if gui:
        try:
            import local_sync_server
            local_sync_server.set_gui_instance(gui)
        except Exception:
            pass
    return _global_sync_server


__all__: list[str] = [
    "QuietThreadingHTTPServer",
    "LocalSyncServer",
    "get_sync_server",
]
