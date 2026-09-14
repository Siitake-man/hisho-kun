"""
Neo-Secretary ストレージ層 - 付箋リポジトリ (storage/sticky_repo.py)

デスクトップ付箋 (sticky_notes テーブル) の永続化・取得・更新・削除を提供します。
"""

import logging
from typing import List, Optional

from storage.connection import get_db_connection
from storage.models import StickyNote

logger = logging.getLogger(__name__)


def create_sticky_note(note: StickyNote, db_path: str = "neo_secretary.db") -> int:
    """付箋を追加します。

    Args:
        note: 追加する付箋情報
        db_path: データベースファイルのパス

    Returns:
        作成された付箋のID
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sticky_notes (
                content, color, position_x, position_y,
                width, height, is_minimized
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            note.content, note.color, note.position_x, note.position_y,
            note.width, note.height, int(note.is_minimized)
        ))
        note_id = cursor.lastrowid or 0
        logger.info(f"付箋を作成しました: ID={note_id}")
        return note_id


def get_all_sticky_notes(db_path: str = "neo_secretary.db") -> List[StickyNote]:
    """全ての付箋を取得します。

    Args:
        db_path: データベースファイルのパス

    Returns:
        付箋のリスト
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sticky_notes")
        rows = cursor.fetchall()
        notes = [
            StickyNote(
                id=row[0],
                content=row[1],
                color=row[2],
                position_x=row[3],
                position_y=row[4],
                width=row[5],
                height=row[6],
                is_minimized=bool(row[7])
            )
            for row in rows
        ]
        logger.info(f"{len(notes)}件の付箋を取得しました")
        return notes


def update_sticky_note(note: StickyNote, db_path: str = "neo_secretary.db") -> bool:
    """付箋の内容や位置を更新します。"""
    if note.id is None:
        raise ValueError("更新には付箋のIDが必要です")

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE sticky_notes
            SET content = ?, color = ?, position_x = ?, position_y = ?,
                width = ?, height = ?, is_minimized = ?
            WHERE id = ?
        """, (
            note.content, note.color, note.position_x, note.position_y,
            note.width, note.height, int(note.is_minimized), note.id
        ))
        success = cursor.rowcount > 0
        if success:
            logger.info(f"付箋を更新しました: ID={note.id}")
        else:
            logger.warning(f"更新対象の付箋が見つかりません: ID={note.id}")
        return success


def delete_sticky_note(note_id: int, db_path: str = "neo_secretary.db") -> bool:
    """指定したIDの付箋をデータベースから完全に削除します。"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sticky_notes WHERE id = ?", (note_id,))
        success = cursor.rowcount > 0
        if success:
            logger.info(f"付箋を削除しました: ID={note_id}")
        else:
            logger.warning(f"削除対象の付箋が見つかりません: ID={note_id}")
        return success
