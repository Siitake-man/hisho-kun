"""
Neo-Secretary ストレージ層 - タスク・TODO・リストリポジトリ (storage/task_repo.py)

タスク (tasks テーブル)、サブタスク、繰り返しタスク自動次回生成、
タスクリスト階層管理 (task_lists テーブル)、およびリマインダー重複防止履歴 (reminders_sent テーブル) の
CRUD操作を提供します。
"""

import calendar
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional

from storage.connection import get_db_connection
from storage.models import Task, TaskList

logger = logging.getLogger(__name__)


# =============================================================================
# CRUD操作: Tasks (TODOタスク管理)
# =============================================================================

def create_task(task: Task, db_path: str = "neo_secretary.db") -> int:
    """新しいTODOタスクを作成します。

    Args:
        task: 作成するタスク情報
        db_path: データベースファイルのパス

    Returns:
        作成されたタスクのID
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tasks (title, description, due_date, priority, status, parent_id, list_id, tags, importance_flag, urgency_flag, recurrence, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task.title,
            task.description or "",
            task.due_date,
            task.priority,
            task.status,
            task.parent_id,
            task.list_id,
            task.tags or "",
            None if task.importance_flag is None else int(task.importance_flag),
            None if task.urgency_flag is None else int(task.urgency_flag),
            task.recurrence,
            task.created_at,
            task.updated_at
        ))

        task_id = cursor.lastrowid or 0
        logger.info(f"タスクを作成しました: ID={task_id}, title={task.title}")
        return task_id


def get_tasks(
    status: Optional[str] = None,
    min_priority: int = 0,
    limit: int = 50,
    list_id: Optional[int] = None,
    db_path: str = "neo_secretary.db"
) -> List[Task]:
    """条件を指定してタスク一覧を取得します。

    Args:
        status: 取得する状態 ('todo', 'in_progress', 'completed')。Noneで未完了タスク(todo, in_progress)。
        min_priority: 最小優先度
        limit: 最大取得件数
        list_id: タスクリストIDで絞り込む (Noneで全リスト対象)
        db_path: データベースファイルのパス

    Returns:
        Taskオブジェクトのリスト
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        where_parts = []
        params: List[object] = []
        if status:
            where_parts.append("status = ?")
            params.append(status)
        else:
            where_parts.append("status != 'completed'")
        where_parts.append("priority >= ?")
        params.append(min_priority)
        if list_id is not None:
            where_parts.append("list_id = ?")
            params.append(list_id)
        params.append(limit)
        cursor.execute(f"""
            SELECT id, title, description, due_date, priority, status, parent_id, list_id, tags, importance_flag, urgency_flag, recurrence, created_at, updated_at
            FROM tasks
            WHERE {' AND '.join(where_parts)}
            ORDER BY priority DESC, (due_date IS NULL) ASC, due_date ASC, id ASC
            LIMIT ?
        """, tuple(params))

        rows = cursor.fetchall()
        tasks = []
        for r in rows:
            tasks.append(Task(
                id=r[0],
                title=r[1],
                description=r[2],
                due_date=r[3],
                priority=r[4],
                status=r[5],
                parent_id=r[6],
                list_id=r[7],
                tags=r[8],
                importance_flag=None if r[9] is None else bool(r[9]),
                urgency_flag=None if r[10] is None else bool(r[10]),
                recurrence=r[11],
                created_at=r[12],
                updated_at=r[13]
            ))
        return tasks


def get_subtasks(parent_id: int, db_path: str = "neo_secretary.db") -> List[Task]:
    """指定された親タスクに紐づく子タスク（サブタスク・チェックリスト）一覧を取得します。

    Args:
        parent_id: 親タスクのID
        db_path: データベースファイルのパス

    Returns:
        Taskオブジェクトのリスト（ID昇順）
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, description, due_date, priority, status, parent_id, list_id, tags, importance_flag, urgency_flag, recurrence, created_at, updated_at
            FROM tasks
            WHERE parent_id = ?
            ORDER BY status = 'completed' ASC, id ASC
        """, (parent_id,))
        rows = cursor.fetchall()
        subtasks = []
        for r in rows:
            subtasks.append(Task(
                id=r[0],
                title=r[1],
                description=r[2],
                due_date=r[3],
                priority=r[4],
                status=r[5],
                parent_id=r[6],
                list_id=r[7],
                tags=r[8],
                importance_flag=None if r[9] is None else bool(r[9]),
                urgency_flag=None if r[10] is None else bool(r[10]),
                recurrence=r[11],
                created_at=r[12],
                updated_at=r[13]
            ))
        return subtasks


def add_subtask(parent_id: int, title: str, db_path: str = "neo_secretary.db") -> int:
    """親タスクに子タスク（サブタスク）を追加します。

    Args:
        parent_id: 親タスクID
        title: 子タスクのタイトル
        db_path: DBパス

    Returns:
        作成された子タスクID
    """
    new_sub = Task(
        title=title,
        parent_id=parent_id,
        status="todo"
    )
    return create_task(new_sub, db_path=db_path)


def _next_recurrence_due(
    recurrence: str,
    due_date_ms: Optional[int],
    now_ms: int,
) -> Optional[int]:
    """繰り返しタスクの次回期限を計算する (完了時の自動次回生成用)。

    Args:
        recurrence: 繰り返し種別 ('daily' / 'weekly' / 'monthly')
        due_date_ms: 直前の期限 (epochミリ秒)。Noneの場合は現在時刻を基準にする
        now_ms: 現在時刻 (epochミリ秒)

    Returns:
        次回期限のepochミリ秒 (計算不能な場合はNone)
    """
    base_ms = due_date_ms if due_date_ms is not None else now_ms
    base = datetime.fromtimestamp(base_ms / 1000)
    now = datetime.fromtimestamp(now_ms / 1000)
    if recurrence == "daily":
        next_due = base + timedelta(days=1)
        while next_due <= now:
            next_due += timedelta(days=1)
        return int(next_due.timestamp() * 1000)
    if recurrence == "weekly":
        next_due = base + timedelta(weeks=1)
        while next_due <= now:
            next_due += timedelta(weeks=1)
        return int(next_due.timestamp() * 1000)
    if recurrence == "monthly":
        year, month = base.year, base.month
        next_due = base
        for _ in range(48):  # 無限ループ防止 (48ヶ月先まで)
            month += 1
            if month > 12:
                month = 1
                year += 1
            last_day = calendar.monthrange(year, month)[1]
            day = min(base.day, last_day)
            next_due = base.replace(year=year, month=month, day=day)
            if next_due > now:
                break
        return int(next_due.timestamp() * 1000)
    return None


def complete_task(task_id: int, db_path: str = "neo_secretary.db") -> bool:
    """タスクを完了状態 ('completed') に更新します。

    繰り返しタスク (recurrence 設定あり) を完了した場合は、
    次回期限を持つ同一内容の新タスクを自動生成します (roadmap 1.12)。

    Args:
        task_id: 完了にするタスクID
        db_path: データベースファイルのパス

    Returns:
        更新成功時はTrue
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        now = int(datetime.now().timestamp() * 1000)
        cursor.execute(
            "SELECT recurrence, due_date, title, description, priority, tags, list_id, importance_flag, urgency_flag FROM tasks WHERE id = ?",
            (task_id,)
        )
        row = cursor.fetchone()
        cursor.execute("UPDATE tasks SET status = 'completed', updated_at = ? WHERE id = ?", (now, task_id))
        success = cursor.rowcount > 0
        if success:
            logger.info(f"タスクを完了にしました: ID={task_id}")
            if row and row[0]:
                recurrence = row[0]
                next_due = _next_recurrence_due(recurrence, row[1], now)
                if next_due is not None:
                    try:
                        cursor.execute("""
                            INSERT INTO tasks (title, description, due_date, priority, status, parent_id, list_id, tags, importance_flag, urgency_flag, recurrence, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row[2],
                            row[3] or "",
                            next_due,
                            row[4],
                            "todo",
                            None,
                            row[5] if row[5] else None,
                            row[6] or "",
                            None if row[7] is None else int(row[7]),
                            None if row[8] is None else int(row[8]),
                            recurrence,
                            now,
                            now,
                        ))
                        next_id = cursor.lastrowid
                        logger.info(
                            f"🔁 繰り返しタスクの次回分を生成しました: ID={next_id} "
                            f"(recurrence={recurrence}, 次回期限={datetime.fromtimestamp(next_due / 1000):%Y-%m-%d %H:%M})"
                        )
                    except sqlite3.Error as e:
                        logger.error(f"繰り返しタスクの次回生成に失敗: {e}")
        return success


def reopen_task(task_id: int, db_path: str = "neo_secretary.db") -> bool:
    """完了済みタスクを未完了 ('todo') に戻します (誤タップ復活用)。

    繰り返しタスクを取り消した場合は、完了時に自動生成された「次回分」タスクを
    削除して完了前の状態に巻き戻します。

    Args:
        task_id: 未完了に戻すタスクID
        db_path: データベースファイルのパス

    Returns:
        更新成功時はTrue
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        now = int(datetime.now().timestamp() * 1000)
        cursor.execute(
            "SELECT title, recurrence, due_date, updated_at FROM tasks WHERE id = ? AND status = 'completed'",
            (task_id,)
        )
        row = cursor.fetchone()
        if row is None:
            logger.warning(f"取り消し対象の完了済みタスクが見つかりません: ID={task_id}")
            return False
        cursor.execute("UPDATE tasks SET status = 'todo', updated_at = ? WHERE id = ?", (now, task_id))
        success = cursor.rowcount > 0
        if success:
            logger.info(f"タスクの完了を取り消しました: ID={task_id}")
            if row[1]:
                try:
                    cursor.execute("""
                        DELETE FROM tasks
                        WHERE id != ?
                          AND title = ?
                          AND recurrence = ?
                          AND status = 'todo'
                          AND created_at >= ?
                    """, (task_id, row[0], row[1], row[3]))
                    if cursor.rowcount > 0:
                        logger.info(
                            f"🔁 繰り返しタスクの完了取り消しに伴い次回分を削除: {cursor.rowcount}件"
                        )
                except sqlite3.Error as e:
                    logger.error(f"繰り返しタスクの次回分巻き戻しに失敗: {e}")
        return success


def get_tasks_completed_today(
    now_ms: Optional[int] = None,
    limit: int = 10,
    db_path: str = "neo_secretary.db"
) -> List[Task]:
    """本日（00:00:00以降）完了したタスク一覧を取得する Seam (P1-1 対策)。

    終礼日報（eveningモード）で、過去数ヶ月前の完了タスクが誤って本日分として
    報告されるバグを根本治療します。

    Args:
        now_ms: 基準時刻（Unixミリ秒）。Noneの場合は現在時刻
        limit: 最大取得件数
        db_path: データベースファイルのパス

    Returns:
        本日完了したTaskオブジェクトのリスト（直近完了順）
    """
    if now_ms is None:
        now_dt = datetime.now()
    else:
        now_dt = datetime.fromtimestamp(now_ms / 1000.0)

    start_of_today = datetime(now_dt.year, now_dt.month, now_dt.day, 0, 0, 0)
    start_of_today_ms = int(start_of_today.timestamp() * 1000)

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, description, due_date, priority, status, parent_id, list_id, tags, importance_flag, urgency_flag, recurrence, created_at, updated_at
            FROM tasks
            WHERE status = 'completed' AND updated_at >= ?
            ORDER BY updated_at DESC, priority DESC
            LIMIT ?
        """, (start_of_today_ms, limit))

        rows = cursor.fetchall()
        tasks = []
        for r in rows:
            tasks.append(Task(
                id=r[0],
                title=r[1],
                description=r[2],
                due_date=r[3],
                priority=r[4],
                status=r[5],
                parent_id=r[6],
                list_id=r[7],
                tags=r[8],
                importance_flag=None if r[9] is None else bool(r[9]),
                urgency_flag=None if r[10] is None else bool(r[10]),
                recurrence=r[11],
                created_at=r[12],
                updated_at=r[13]
            ))
        return tasks


def update_task(task_id: int, updates: dict, db_path: str = "neo_secretary.db") -> bool:
    """タスクの指定フィールドを更新します (スマホ編集シート・PC手帳共通)。

    Args:
        task_id: 更新対象のタスクID
        updates: 更新するフィールドの辞書
        db_path: データベースファイルのパス

    Returns:
        更新が1件以上適用された場合はTrue
    """
    allowed = {
        "title", "description", "due_date", "priority", "status", "tags",
        "importance_flag", "urgency_flag", "recurrence", "list_id",
    }
    cols = []
    params = []
    for key, value in updates.items():
        if key not in allowed:
            logger.warning(f"update_task: 許可されていないキーを無視します: {key}")
            continue
        if key in ("importance_flag", "urgency_flag") and value is not None:
            value = int(bool(value))
        cols.append(f"{key} = ?")
        params.append(value)
    if not cols:
        return False
    now = int(datetime.now().timestamp() * 1000)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE tasks SET {', '.join(cols)}, updated_at = ? WHERE id = ?",
            (*params, now, task_id),
        )
        success = cursor.rowcount > 0
        if success:
            logger.info(f"タスクを更新しました: ID={task_id} keys={[c.split(' =')[0] for c in cols]}")
        else:
            logger.warning(f"update_task: 更新対象が見つかりません: ID={task_id}")
        return success


def delete_task(task_id: int, db_path: str = "neo_secretary.db") -> bool:
    """タスクを削除します。"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        success = cursor.rowcount > 0
        if success:
            logger.info(f"タスクを削除しました: ID={task_id}")
        return success


# =============================================================================
# リマインダー送信履歴 (reminder_engine から利用・重複通知防止)
# =============================================================================

def is_reminder_sent(item_type: str, item_id: int, db_path: str = "neo_secretary.db") -> bool:
    """指定した対象のリマインダーが既に送信済みかを判定します。

    Args:
        item_type: 対象種別 ('task' または 'event')
        item_id: タスク/予定のID
        db_path: データベースファイルのパス

    Returns:
        送信済みの場合True
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM reminders_sent WHERE item_type = ? AND item_id = ?",
            (item_type, item_id),
        )
        return cursor.fetchone() is not None


def mark_reminder_sent(item_type: str, item_id: int, db_path: str = "neo_secretary.db") -> None:
    """リマインダーの送信済みを冪等に記録します (再通知防止)。

    Args:
        item_type: 対象種別 ('task' または 'event')
        item_id: タスク/予定のID
        db_path: データベースファイルのパス
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        now = int(datetime.now().timestamp() * 1000)
        cursor.execute(
            "INSERT OR IGNORE INTO reminders_sent (item_type, item_id, sent_at) VALUES (?, ?, ?)",
            (item_type, item_id, now),
        )
        logger.debug(f"リマインダー送信済みを記録: {item_type}#{item_id}")


# =============================================================================
# CRUD操作: TaskLists (タスクリスト階層管理)
# =============================================================================

def get_task_lists(db_path: str = "neo_secretary.db") -> List[TaskList]:
    """タスクリスト一覧を作成順で取得します。

    Args:
        db_path: データベースファイルのパス

    Returns:
        TaskListオブジェクトのリスト
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, emoji, parent_id, sort_order, created_at
            FROM task_lists
            ORDER BY sort_order ASC, id ASC
        """)
        rows = cursor.fetchall()
        lists = []
        for r in rows:
            lists.append(TaskList(
                id=r[0],
                name=r[1],
                emoji=r[2],
                parent_id=r[3],
                sort_order=r[4],
                created_at=r[5]
            ))
        return lists


def _task_list_has_cycle(list_id: int, new_parent_id: Optional[int], conn, db_path: str) -> bool:
    """リスト移動時に循環参照が発生するかを判定します (内部ヘルパー)。"""
    if new_parent_id is None:
        return False
    if new_parent_id == list_id:
        return True
    cursor = conn.cursor()
    seen = {list_id}
    current = new_parent_id
    while current is not None:
        if current in seen:
            return True
        seen.add(current)
        cursor.execute("SELECT parent_id FROM task_lists WHERE id = ?", (current,))
        row = cursor.fetchone()
        if row is None:
            return False
        current = row[0]
    return False


def create_task_list(
    name: str,
    emoji: str = "📋",
    sort_order: int = 0,
    parent_id: Optional[int] = None,
    db_path: str = "neo_secretary.db"
) -> int:
    """新しいタスクリストを作成します (任意の親リストの下に階層作成可能)。

    Args:
        name: リスト名
        emoji: リストに表示する絵文字
        sort_order: ソート順
        parent_id: 親リストID (None=最上位)
        db_path: データベースファイルのパス

    Returns:
        作成されたリストのID
    """
    clean_name = (name or "").strip()
    if not clean_name:
        raise ValueError("タスクリスト名が空です")
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        if parent_id is not None:
            cursor.execute("SELECT id FROM task_lists WHERE id = ?", (parent_id,))
            if cursor.fetchone() is None:
                raise ValueError(f"親リストが存在しません: ID={parent_id}")
        cursor.execute("""
            INSERT INTO task_lists (name, emoji, parent_id, sort_order, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            clean_name,
            emoji or "📋",
            parent_id,
            sort_order,
            int(datetime.now().timestamp() * 1000)
        ))
        list_id = cursor.lastrowid or 0
        logger.info(f"タスクリストを作成しました: ID={list_id}, name={clean_name}, parent_id={parent_id}")
        return list_id


def move_task_list(list_id: int, new_parent_id: Optional[int], db_path: str = "neo_secretary.db") -> bool:
    """タスクリストを別の親リストの下へ移動します (階層変更・Block 1.6-R)。

    Args:
        list_id: 移動対象リストID
        new_parent_id: 新しい親リストID
        db_path: データベースファイルのパス

    Returns:
        移動成功時はTrue
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM task_lists WHERE id = ?", (list_id,))
        if cursor.fetchone() is None:
            logger.warning("リスト移動: 対象リストが存在しません ID=%s", list_id)
            return False
        if new_parent_id is not None:
            cursor.execute("SELECT id FROM task_lists WHERE id = ?", (new_parent_id,))
            if cursor.fetchone() is None:
                raise ValueError(f"移動先の親リストが存在しません: ID={new_parent_id}")
        if _task_list_has_cycle(list_id, new_parent_id, conn, db_path):
            raise ValueError("自分自身または子孫のリストを親に指定することはできません (循環参照)")
        cursor.execute(
            "UPDATE task_lists SET parent_id = ? WHERE id = ?",
            (new_parent_id, list_id)
        )
        logger.info(f"タスクリストを移動しました: ID={list_id}, new_parent_id={new_parent_id}")
        return True


def delete_task_list(list_id: int, db_path: str = "neo_secretary.db") -> bool:
    """タスクリストを削除します。所属タスクはリスト未分類 (list_id=NULL) へ移行されます。

    Args:
        list_id: 削除するリストID
        db_path: データベースファイルのパス

    Returns:
        削除成功時はTrue
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        now = int(datetime.now().timestamp() * 1000)
        cursor.execute("UPDATE tasks SET list_id = NULL, updated_at = ? WHERE list_id = ?", (now, list_id))
        cursor.execute("""
            UPDATE task_lists
            SET parent_id = (SELECT parent_id FROM task_lists WHERE id = ?)
            WHERE parent_id = ?
        """, (list_id, list_id))
        cursor.execute("DELETE FROM task_lists WHERE id = ?", (list_id,))
        success = cursor.rowcount > 0
        if success:
            logger.info(f"タスクリストを削除しました: ID={list_id} (所属タスクは未分類へ・子リストは昇格)")
        return success


def rename_task_list(list_id: int, name: str, emoji: Optional[str] = None, db_path: str = "neo_secretary.db") -> bool:
    """タスクリストの名称（および任意で絵文字）を変更します。

    Args:
        list_id: 対象リストID
        name: 新しいリスト名
        emoji: 新しい絵文字
        db_path: データベースファイルのパス

    Returns:
        更新成功時はTrue
    """
    clean_name = (name or "").strip()
    if not clean_name:
        raise ValueError("タスクリスト名が空です")
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        if emoji is None:
            cursor.execute(
                "UPDATE task_lists SET name = ? WHERE id = ?",
                (clean_name, list_id)
            )
        else:
            cursor.execute(
                "UPDATE task_lists SET name = ?, emoji = ? WHERE id = ?",
                (clean_name, emoji or "📋", list_id)
            )
        success = cursor.rowcount > 0
        if success:
            logger.info(f"タスクリスト名を変更しました: ID={list_id}, name={clean_name}")
        return success


def update_task_tags(task_id: int, tags: str, db_path: str = "neo_secretary.db") -> bool:
    """タスクのタグを更新します (カンマ区切り)。

    Args:
        task_id: 対象タスクID
        tags: カンマ区切りタグ文字列
        db_path: データベースファイルのパス

    Returns:
        更新成功時はTrue
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        now = int(datetime.now().timestamp() * 1000)
        cursor.execute("UPDATE tasks SET tags = ?, updated_at = ? WHERE id = ?", (tags or "", now, task_id))
        success = cursor.rowcount > 0
        if success:
            logger.info(f"タスクのタグを更新しました: ID={task_id}, tags={tags}")
        return success
