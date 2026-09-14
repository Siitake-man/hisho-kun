#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - 承認監査ログ基盤モジュール (audit_logger.py)

外部 AI Agent (Claude Code, Cline, Cursor, Codex 等) が要請した
すべてのコマンド実行・承認・却下・自動許可の履歴を SQLite へ永続化し、
企業セキュリティ監査 (SOC2 / ISO27001) にも耐えうるトレーサビリティを提供する。

特徴:
- Pydantic v2 による型安全な監査ログモデル。
- WALモードを活用した高速な同期/非同期書き込み。
- メモリスレッドキュー (AsyncAuditLogger) によるノンブロッキング記録。
- データアクセスの実体は storage.audit_repo へ委搬 (Facade) される。
"""

import logging
import queue
import threading
import time
from typing import Any, Dict, List, Optional

from storage.models import AuditLogEntry
from storage.audit_repo import record_audit_log, get_audit_logs

logger = logging.getLogger(__name__)


class AsyncAuditLogger:
    """HTTPサーバーやUIスレッドをブロックしない、非同期バックグラウンド監査ロガー。"""

    def __init__(self, db_path: str = "neo_secretary.db") -> None:
        self.db_path = db_path
        self._queue: queue.Queue[Optional[AuditLogEntry]] = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        """ワーカースレッドを開始する。"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._worker_loop,
            name="AuditLoggerWorker",
            daemon=True,
        )
        self._thread.start()
        logger.info("🛡️ [Audit Log] 非同期監査ロガーワーカースレッドが開始しました")

    def stop(self, timeout: float = 2.0) -> None:
        """キュー内の未処理ログをフラッシュしてスレッドを停止する。"""
        if not self._running:
            return
        self._running = False
        self._queue.put(None)  # 終了シグナル
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def log(self, entry: AuditLogEntry) -> None:
        """監査ログエントリを非同期キューへ投入する。"""
        if not self._running:
            # 停止中・未起動時は同期フォールバックでデータ喪失を防ぐ
            record_audit_log(entry, db_path=self.db_path)
            return
        self._queue.put(entry)

    def _worker_loop(self) -> None:
        """キューからエントリを取り出してDBへ書き込むワーカーループ。"""
        while self._running:
            try:
                entry = self._queue.get(timeout=1.0)
                if entry is None:
                    break
                try:
                    record_audit_log(entry, db_path=self.db_path)
                except Exception as e:
                    logger.error(f"非同期監査ログ書き込みエラー: {e}")
                finally:
                    self._queue.task_done()
            except queue.Empty:
                continue


# シングルトン非同期ロガーインスタンス
_GLOBAL_AUDIT_LOGGER: Optional[AsyncAuditLogger] = None


def get_global_audit_logger(db_path: str = "neo_secretary.db") -> AsyncAuditLogger:
    """グローバルな非同期監査ロガーを取得（または初期化起動）する。"""
    global _GLOBAL_AUDIT_LOGGER
    if _GLOBAL_AUDIT_LOGGER is None:
        _GLOBAL_AUDIT_LOGGER = AsyncAuditLogger(db_path=db_path)
        _GLOBAL_AUDIT_LOGGER.start()
    return _GLOBAL_AUDIT_LOGGER
