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
"""

import logging
import queue
import threading
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

import database

logger = logging.getLogger(__name__)


class AuditLogEntry(BaseModel):
    """承認監査ログの1レコードを表すモデル。"""
    model_config = ConfigDict(extra="allow")

    id: Optional[int] = None
    request_id: str
    agent_type: str = "generic"
    agent_name: str = "AI Agent"
    command: str = ""
    summary: str = ""
    risk_level: str = "prompt"
    decision: str = "pending"  # approved / rejected / auto_allowed / expired / timeout
    decision_by: str = "human"  # human / policy_engine / timeout
    decision_message: Optional[str] = None
    requester_ip: Optional[str] = None
    client_ip: Optional[str] = None
    duration_sec: float = 0.0
    created_at: int = Field(default_factory=lambda: int(time.time()))


def record_audit_log(entry: AuditLogEntry, db_path: str = "neo_secretary.db") -> int:
    """承認監査ログを同期的にデータベースへ記録する。

    Args:
        entry: 記録する監査ログエントリ。
        db_path: データベースファイルパス。

    Returns:
        int: 発行された監査ログレコードのプライマリID。
    """
    sql = """
        INSERT INTO approval_audit_logs (
            request_id, agent_type, agent_name, command, summary,
            risk_level, decision, decision_by, decision_message,
            requester_ip, client_ip, duration_sec, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    with database.get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            sql,
            (
                entry.request_id,
                entry.agent_type,
                entry.agent_name,
                entry.command,
                entry.summary,
                entry.risk_level,
                entry.decision,
                entry.decision_by,
                entry.decision_message,
                entry.requester_ip,
                entry.client_ip,
                entry.duration_sec,
                entry.created_at,
            ),
        )
        log_id = cursor.lastrowid or 0
        logger.info(
            f"🛡️ [Audit Log] 記録完了 (ID: {log_id}): {entry.agent_name} -> "
            f"'{entry.command}' ({entry.decision} by {entry.decision_by})"
        )
        return log_id


def get_audit_logs(
    limit: int = 50,
    offset: int = 0,
    agent_type: Optional[str] = None,
    db_path: str = "neo_secretary.db",
) -> List[AuditLogEntry]:
    """監査ログ履歴を降順（最新順）で取得する。

    Args:
        limit: 取得上限件数。
        offset: 取得開始位置。
        agent_type: 特定のエージェント種別で絞り込む場合指定。
        db_path: データベースファイルパス。

    Returns:
        List[AuditLogEntry]: 監査ログエントリのリスト。
    """
    params: List[Any] = []
    where_clause = ""
    if agent_type:
        where_clause = "WHERE agent_type = ?"
        params.append(agent_type)

    sql = f"""
        SELECT
            id, request_id, agent_type, agent_name, command, summary,
            risk_level, decision, decision_by, decision_message,
            requester_ip, client_ip, duration_sec, created_at
        FROM approval_audit_logs
        {where_clause}
        ORDER BY created_at DESC, id DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    with database.get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()

        results: List[AuditLogEntry] = []
        for row in rows:
            results.append(
                AuditLogEntry(
                    id=row[0],
                    request_id=row[1],
                    agent_type=row[2],
                    agent_name=row[3],
                    command=row[4],
                    summary=row[5] or "",
                    risk_level=row[6],
                    decision=row[7],
                    decision_by=row[8],
                    decision_message=row[9],
                    requester_ip=row[10],
                    client_ip=row[11],
                    duration_sec=float(row[12] or 0.0),
                    created_at=int(row[13]),
                )
            )
        return results


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
