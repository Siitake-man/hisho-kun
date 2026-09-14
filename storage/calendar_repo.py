"""
Neo-Secretary ストレージ層 - カレンダー・カテゴリリポジトリ (storage/calendar_repo.py)

カレンダー予定 (events テーブル)、購読ソース (calendar_sources テーブル)、
およびカテゴリ (categories テーブル) の永続化・検索・更新・削除を提供します。
"""

import json
import logging
from datetime import datetime
from typing import List, Optional

from storage.connection import get_db_connection
from storage.models import Category, Event, CalendarSource

logger = logging.getLogger(__name__)


# =============================================================================
# CRUD操作: Categories
# =============================================================================

def create_category(category: Category, db_path: str = "neo_secretary.db") -> int:
    """カテゴリを追加します。

    Args:
        category: 追加するカテゴリ情報
        db_path: データベースファイルのパス

    Returns:
        作成されたカテゴリのID
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO categories (name, color, icon)
            VALUES (?, ?, ?)
        """, (category.name, category.color, category.icon))
        category_id = cursor.lastrowid or 0
        logger.info(f"カテゴリを作成しました: ID={category_id}, name={category.name}")
        return category_id


def get_category(category_id: int, db_path: str = "neo_secretary.db") -> Optional[Category]:
    """IDを指定してカテゴリを取得します。

    Args:
        category_id: カテゴリID
        db_path: データベースファイルのパス

    Returns:
        カテゴリ情報（存在しない場合はNone）
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
        row = cursor.fetchone()
        if row:
            return Category(
                id=row[0],
                name=row[1],
                color=row[2],
                icon=row[3]
            )
        return None


def get_all_categories(db_path: str = "neo_secretary.db") -> List[Category]:
    """全てのカテゴリを取得します。

    Args:
        db_path: データベースファイルのパス

    Returns:
        カテゴリのリスト
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM categories")
        rows = cursor.fetchall()
        categories = [
            Category(id=row[0], name=row[1], color=row[2], icon=row[3])
            for row in rows
        ]
        logger.info(f"{len(categories)}件のカテゴリを取得しました")
        return categories


# =============================================================================
# CRUD操作: Events
# =============================================================================

def create_event(event: Event, db_path: str = "neo_secretary.db") -> int:
    """予定を追加します。

    recurrence_ruleは自動的にJSON文字列に変換されます。

    Args:
        event: 追加する予定情報
        db_path: データベースファイルのパス

    Returns:
        作成された予定のID
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        recurrence_rule_json = json.dumps(event.recurrence_rule) if event.recurrence_rule else None

        cursor.execute("""
            INSERT INTO events (
                title, description, start_time, end_time,
                recurrence_type, recurrence_rule, category_id, google_event_id, source_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.title, event.description, event.start_time, event.end_time,
            event.recurrence_type, recurrence_rule_json, event.category_id, event.google_event_id, event.source_id
        ))

        event_id = cursor.lastrowid or 0
        logger.info(f"予定を作成しました: ID={event_id}, title={event.title}")
        return event_id


def get_event(event_id: int, db_path: str = "neo_secretary.db") -> Optional[Event]:
    """IDを指定して予定を取得します。

    recurrence_ruleは自動的にPythonの辞書に変換されます。

    Args:
        event_id: 予定ID
        db_path: データベースファイルのパス

    Returns:
        予定情報（存在しない場合はNone）
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        row = cursor.fetchone()

        if row:
            recurrence_rule = json.loads(row[6]) if row[6] else None
            return Event(
                id=row[0],
                title=row[1],
                description=row[2],
                start_time=row[3],
                end_time=row[4],
                recurrence_type=row[5],
                recurrence_rule=recurrence_rule,
                category_id=row[7],
                google_event_id=row[8],
                source_id=(row[9] if len(row) > 9 else None)
            )
        return None


def _rows_to_events(rows: list) -> List[Event]:
    """events テーブルの SELECT * 結果行を Event モデルのリストへ変換する（共通ヘルパー）。"""
    events: List[Event] = []
    for row in rows:
        recurrence_rule = json.loads(row[6]) if row[6] else None
        events.append(Event(
            id=row[0],
            title=row[1],
            description=row[2],
            start_time=row[3],
            end_time=row[4],
            recurrence_type=row[5],
            recurrence_rule=recurrence_rule,
            category_id=row[7],
            google_event_id=row[8],
            source_id=(row[9] if len(row) > 9 else None)
        ))
    return events


def get_upcoming_events(days: int = 7, db_path: str = "neo_secretary.db") -> List[Event]:
    """今後N日間の予定を取得します。

    Args:
        days: 取得する日数（デフォルト: 7日間）
        db_path: データベースファイルのパス

    Returns:
        予定のリスト（開始時刻の昇順）
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        now_ms = int(datetime.now().timestamp() * 1000)
        future_ms = now_ms + (days * 24 * 60 * 60 * 1000)

        cursor.execute("""
            SELECT * FROM events
            WHERE start_time >= ? AND start_time <= ?
            ORDER BY start_time ASC
        """, (now_ms, future_ms))

        events = _rows_to_events(cursor.fetchall())
        logger.debug(f"今後{days}日間の予定を{len(events)}件取得しました")
        return events


def get_events_between(start_ms: int, end_ms: int, db_path: str = "neo_secretary.db") -> List[Event]:
    """指定した期間内に開始する予定を取得します。

    Args:
        start_ms: 期間の開始（Unix Timestamp ミリ秒・この時刻以降に開始する予定が対象）
        end_ms: 期間の終了（Unix Timestamp ミリ秒・この時刻以前に開始する予定が対象）
        db_path: データベースファイルのパス

    Returns:
        予定のリスト（開始時刻の昇順）
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM events
            WHERE start_time >= ? AND start_time <= ?
            ORDER BY start_time ASC
        """, (start_ms, end_ms))

        events = _rows_to_events(cursor.fetchall())
        logger.debug(f"指定期間の予定を{len(events)}件取得しました")
        return events


# =============================================================================
# CRUD操作: CalendarSources (カレンダー購読ソース)
# =============================================================================

def create_calendar_source(source: CalendarSource, db_path: str = "neo_secretary.db") -> int:
    """カレンダー購読ソースを追加します。

    Args:
        source: 追加するソース情報
        db_path: データベースファイルのパス

    Returns:
        作成されたソースのID
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO calendar_sources (name, color, url, enabled, last_sync)
            VALUES (?, ?, ?, ?, ?)
        """, (source.name, source.color, source.url, 1 if source.enabled else 0, source.last_sync))
        source_id = cursor.lastrowid or 0
        logger.info(f"カレンダーソースを作成しました: ID={source_id}, name={source.name}")
        return source_id


def _row_to_calendar_source(row) -> CalendarSource:
    """calendar_sources テーブルの SELECT * 行を CalendarSource モデルへ変換する"""
    return CalendarSource(
        id=row[0],
        name=row[1],
        color=row[2],
        url=row[3],
        enabled=bool(row[4]),
        last_sync=row[5]
    )


def get_all_calendar_sources(db_path: str = "neo_secretary.db") -> List[CalendarSource]:
    """全てのカレンダー購読ソースを取得します（作成順）。

    Args:
        db_path: データベースファイルのパス

    Returns:
        ソースのリスト
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM calendar_sources ORDER BY id ASC")
        return [_row_to_calendar_source(row) for row in cursor.fetchall()]


def get_calendar_source(source_id: int, db_path: str = "neo_secretary.db") -> Optional[CalendarSource]:
    """IDを指定してカレンダー購読ソースを取得します。

    Args:
        source_id: ソースID
        db_path: データベースファイルのパス

    Returns:
        ソース情報（存在しない場合はNone）
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM calendar_sources WHERE id = ?", (source_id,))
        row = cursor.fetchone()
        return _row_to_calendar_source(row) if row else None


def update_calendar_source(source: CalendarSource, db_path: str = "neo_secretary.db") -> None:
    """カレンダー購読ソースの内容（名前・色・URL・有効フラグ・最終同期）を更新します。

    Args:
        source: 更新するソース情報（id は必須）
        db_path: データベースファイルのパス
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE calendar_sources
            SET name = ?, color = ?, url = ?, enabled = ?, last_sync = ?
            WHERE id = ?
        """, (source.name, source.color, source.url, 1 if source.enabled else 0, source.last_sync, source.id))
        logger.info(f"カレンダーソースを更新しました: ID={source.id}, name={source.name}")


def set_calendar_source_enabled(source_id: int, enabled: bool, db_path: str = "neo_secretary.db") -> None:
    """カレンダー購読ソースの有効/無効を切り替えます。

    Args:
        source_id: ソースID
        enabled: True で有効化、False で無効化（同期・表示ともに停止）
        db_path: データベースファイルのパス
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE calendar_sources SET enabled = ? WHERE id = ?", (1 if enabled else 0, source_id))
        logger.info(f"カレンダーソースの有効状態を変更しました: ID={source_id}, enabled={enabled}")


def set_calendar_source_last_sync(source_id: int, time_str: str, db_path: str = "neo_secretary.db") -> None:
    """カレンダー購読ソースの最終同期時刻を記録します。

    Args:
        source_id: ソースID
        time_str: 表示用の同期時刻文字列
        db_path: データベースファイルのパス
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE calendar_sources SET last_sync = ? WHERE id = ?", (time_str, source_id))


def delete_calendar_source(source_id: int, db_path: str = "neo_secretary.db") -> None:
    """カレンダー購読ソースを削除し、その同期済み予定も併せて削除します。

    Args:
        source_id: ソースID
        db_path: データベースファイルのパス
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM events WHERE source_id = ?", (source_id,))
        cursor.execute("DELETE FROM calendar_sources WHERE id = ?", (source_id,))
        logger.info(f"カレンダーソースとその予定を削除しました: ID={source_id}")
