"""
Neo-Secretary ストレージ層 - 承認監査ログリポジトリ (storage/audit_repo.py)

承認監査ログ (approval_audit_logs テーブル) の永続化および検索を行います。
"""

import logging
from typing import Any, List, Optional

from storage.connection import get_db_connection
from storage.models import AuditLogEntry

logger = logging.getLogger(__name__)


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
    with get_db_connection(db_path) as conn:
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

    with get_db_connection(db_path) as conn:
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
