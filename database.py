"""
Neo-Secretary データベースモジュール

SQLiteデータベースの初期化、Pydanticモデル定義、CRUD操作を提供します。
Manus仕様準拠の recurrence_rule (JSON形式) を含む、型安全なデータベース層です。
contextlib.contextmanager による接続管理を一元化し、例外時の自動ロールバックとリソースリーク防止を徹底しています。
"""

import logging
import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, List, Dict, Any, Generator
from pathlib import Path

from pydantic import BaseModel, Field, validator

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# データベース接続コンテキストマネージャ (Connection Lifecycle Management)
# =============================================================================

@contextmanager
def get_db_connection(db_path: str = "neo_secretary.db") -> Generator[sqlite3.Connection, None, None]:
    """
    SQLiteデータベース接続を一元管理するコンテキストマネージャ。
    
    WAL (Write-Ahead Logging) モードを有効化し、GUIとHTTPサーバー間の
    同時読み書きによるロック競合（database is locked）を防止します。
    ブロックを正常に抜けた場合は自動的に commit() を行い、
    例外が発生した場合は自動的に rollback() を実行して安全に close() します。
    
    Args:
        db_path: データベースファイルのパス
        
    Yields:
        sqlite3.Connection: データベース接続オブジェクト
    """
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        # WALモード & 同期レベル設定で並行性と整合性を両立
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"データベース操作エラー (ロールバック実行): {e}")
        raise
    finally:
        conn.close()


# =============================================================================
# Pydanticモデル定義
# =============================================================================

class Category(BaseModel):
    """
    カテゴリ情報を表すモデル。
    
    予定や付箋を分類するために使用します。アイコンと色で視覚的に区別できます。
    
    Attributes:
        id: カテゴリID（自動採番）
        name: カテゴリ名（例: "仕事", "プライベート"）
        color: カラーコード（例: "#A67B5B"）
        icon: アイコン名（例: "work", "home"）
    """
    id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=100)
    color: str = Field(..., pattern=r'^#[0-9A-Fa-f]{6}$')
    icon: str = Field(..., min_length=1, max_length=50)


class Event(BaseModel):
    """
    予定情報を表すモデル。
    
    カレンダーの予定を管理します。Manus仕様準拠のrecurrence_rule（JSON形式）で
    繰り返し予定に対応しています。
    
    Attributes:
        id: 予定ID（自動採番）
        title: 予定のタイトル
        description: 予定の詳細説明
        start_time: 開始時刻（Unix Timestamp ミリ秒）
        end_time: 終了時刻（Unix Timestamp ミリ秒）
        recurrence_type: 繰り返しタイプ（'none', 'daily', 'weekly', 'monthly_date'等）
        recurrence_rule: 繰り返しルールの詳細（JSON形式の辞書）
        category_id: カテゴリID（外部キー）
        google_event_id: Google Calendar同期用のイベントID
    """
    id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = ""
    start_time: int = Field(..., gt=0)
    end_time: int = Field(..., gt=0)
    recurrence_type: str = Field(default='none')
    recurrence_rule: Optional[Dict[str, Any]] = None
    category_id: Optional[int] = None
    google_event_id: Optional[str] = None
    
    @validator('end_time')
    def end_after_start(cls, v, values):
        """終了時刻が開始時刻より後であることを検証します。"""
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('end_timeはstart_timeより後である必要があります')
        return v


class StickyNote(BaseModel):
    """
    付箋情報を表すモデル。
    
    デスクトップ上に配置される付箋メモを管理します。
    位置、サイズ、最小化状態を保持します。
    
    Attributes:
        id: 付箋ID（自動採番）
        content: 付箋の内容
        color: 付箋の色（Hexカラーコード）
        position_x: X座標（ピクセル）
        position_y: Y座標（ピクセル）
        width: 幅（ピクセル）
        height: 高さ（ピクセル）
        is_minimized: 最小化されているか
    """
    id: Optional[int] = None
    content: str = Field(default="", max_length=5000)
    color: str = Field(default="#FFEB3B", pattern=r'^#[0-9A-Fa-f]{6}$')
    position_x: int = Field(default=100, ge=0)
    position_y: int = Field(default=100, ge=0)
    width: int = Field(default=200, ge=100)
    height: int = Field(default=200, ge=100)
    is_minimized: bool = Field(default=False)


class UserInsight(BaseModel):
    """
    ユーザーに関する長期知見（MentisDB型エピソード・ルール記憶）を表すモデル。
    
    AIが会話の中でボスの制約、好み、生活習慣、プロジェクトルールを学習し蓄積します。
    
    Attributes:
        id: 知見ID（自動採番）
        category: カテゴリ ('Constraint': 制約, 'Preference': 好み, 'Habit': 習慣, 'Project': PJルール)
        content: 知見の本文（例: '平日夜は家族のケアサポートのため予定を入れない'）
        context_tags: 検索用カンマ区切りタグ（例: 'schedule, family, time'）
        importance: 重要度 (1〜5, 5が最重要)
        created_at: 作成時刻（Unix Timestamp ミリ秒）
        updated_at: 更新時刻（Unix Timestamp ミリ秒）
    """
    id: Optional[int] = None
    category: str = Field(..., pattern=r'^(Constraint|Preference|Habit|Project)$')
    content: str = Field(..., min_length=1, max_length=2000)
    context_tags: Optional[str] = Field(default="")
    importance: int = Field(default=3, ge=1, le=5)
    created_at: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    updated_at: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))


class Task(BaseModel):
    """
    TODOタスク情報を表すモデル（TickTick仕様準拠）。
    
    期日、優先度、状態（todo/in_progress/completed）を管理します。
    
    Attributes:
        id: タスクID（自動採番）
        title: タスクのタイトル
        description: 詳細メモ
        due_date: 期限（Unix Timestamp ミリ秒, 任意）
        priority: 優先度 (0: なし, 1: 低, 2: 中, 3: 高)
        status: 状態 ('todo', 'in_progress', 'completed')
        parent_id: 親タスクID（サブタスク用, 任意）
        created_at: 作成日時（Unix Timestamp ミリ秒）
        updated_at: 更新日時（Unix Timestamp ミリ秒）
    """
    id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = ""
    due_date: Optional[int] = None
    priority: int = Field(default=0, ge=0, le=3)
    status: str = Field(default="todo", pattern=r'^(todo|in_progress|completed)$')
    parent_id: Optional[int] = None
    created_at: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    updated_at: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))


# =============================================================================
# データベース初期化
# =============================================================================

def init_db(db_path: str = "neo_secretary.db") -> None:
    """
    SQLiteデータベースを初期化します。
    
    テーブル（categories, events, sticky_notes, user_insights, tasks）を作成します。
    既にテーブルが存在する場合はスキップされます。
    
    Args:
        db_path: データベースファイルのパス（デフォルト: "neo_secretary.db"）
    
    Raises:
        sqlite3.Error: データベース操作でエラーが発生した場合
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # categoriesテーブル
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                color TEXT NOT NULL,
                icon TEXT NOT NULL
            )
        """)
        logger.info("categoriesテーブルを確認/作成しました")
        
        # eventsテーブル
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                start_time INTEGER NOT NULL,
                end_time INTEGER NOT NULL,
                recurrence_type TEXT NOT NULL DEFAULT 'none',
                recurrence_rule TEXT,
                category_id INTEGER,
                google_event_id TEXT,
                FOREIGN KEY (category_id) REFERENCES categories (id)
            )
        """)
        logger.info("eventsテーブルを確認/作成しました")
        
        # sticky_notesテーブル
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sticky_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                color TEXT NOT NULL,
                position_x INTEGER NOT NULL,
                position_y INTEGER NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                is_minimized INTEGER NOT NULL DEFAULT 0
            )
        """)
        logger.info("sticky_notesテーブルを確認/作成しました")

        # user_insightsテーブル (MentisDB型 長期知見記憶)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                context_tags TEXT,
                importance INTEGER NOT NULL DEFAULT 3,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """)
        logger.info("user_insightsテーブルを確認/作成しました")

        # tasksテーブル (TODOタスク)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                due_date INTEGER,
                priority INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'todo',
                parent_id INTEGER,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (parent_id) REFERENCES tasks (id)
            )
        """)
        logger.info("tasksテーブルを確認/作成しました")
        
    logger.info(f"データベース初期化完了: {db_path}")


# =============================================================================
# CRUD操作: Categories
# =============================================================================

def create_category(category: Category, db_path: str = "neo_secretary.db") -> int:
    """
    カテゴリを追加します。
    
    Args:
        category: 追加するカテゴリ情報
        db_path: データベースファイルのパス
    
    Returns:
        作成されたカテゴリのID
    
    Raises:
        sqlite3.Error: データベース操作でエラーが発生した場合
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO categories (name, color, icon)
            VALUES (?, ?, ?)
        """, (category.name, category.color, category.icon))
        
        category_id = cursor.lastrowid
        logger.info(f"カテゴリを作成しました: ID={category_id}, name={category.name}")
        return category_id


def get_category(category_id: int, db_path: str = "neo_secretary.db") -> Optional[Category]:
    """
    IDを指定してカテゴリを取得します。
    
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
    """
    全てのカテゴリを取得します。
    
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
    """
    予定を追加します。
    
    recurrence_ruleは自動的にJSON文字列に変換されます。
    
    Args:
        event: 追加する予定情報
        db_path: データベースファイルのパス
    
    Returns:
        作成された予定のID
    
    Raises:
        sqlite3.Error: データベース操作でエラーが発生した場合
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        recurrence_rule_json = json.dumps(event.recurrence_rule) if event.recurrence_rule else None
        
        cursor.execute("""
            INSERT INTO events (
                title, description, start_time, end_time,
                recurrence_type, recurrence_rule, category_id, google_event_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.title, event.description, event.start_time, event.end_time,
            event.recurrence_type, recurrence_rule_json, event.category_id, event.google_event_id
        ))
        
        event_id = cursor.lastrowid
        logger.info(f"予定を作成しました: ID={event_id}, title={event.title}")
        return event_id


def get_event(event_id: int, db_path: str = "neo_secretary.db") -> Optional[Event]:
    """
    IDを指定して予定を取得します。
    
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
                google_event_id=row[8]
            )
        return None


def get_upcoming_events(days: int = 7, db_path: str = "neo_secretary.db") -> List[Event]:
    """
    今後N日間の予定を取得します。
    
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
        
        rows = cursor.fetchall()
        events = []
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
                google_event_id=row[8]
            ))
        
        logger.debug(f"今後{days}日間の予定を{len(events)}件取得しました")
        return events


# =============================================================================
# CRUD操作: StickyNotes
# =============================================================================

def create_sticky_note(note: StickyNote, db_path: str = "neo_secretary.db") -> int:
    """
    付箋を追加します。
    
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
        
        note_id = cursor.lastrowid
        logger.info(f"付箋を作成しました: ID={note_id}")
        return note_id


def get_all_sticky_notes(db_path: str = "neo_secretary.db") -> List[StickyNote]:
    """
    全ての付箋を取得します。
    
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
    """
    付箋の内容や位置を更新します。
    """
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
    """
    指定したIDの付箋をデータベースから完全に削除します。
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sticky_notes WHERE id = ?", (note_id,))
        success = cursor.rowcount > 0
        if success:
            logger.info(f"付箋を削除しました: ID={note_id}")
        else:
            logger.warning(f"削除対象の付箋が見つかりません: ID={note_id}")
        return success


# =============================================================================
# CRUD操作: UserInsights (MentisDB型 長期知見記憶)
# =============================================================================

def create_user_insight(insight: UserInsight, db_path: str = "neo_secretary.db") -> int:
    """
    ユーザーに関する知見（制約・好み・習慣・PJルール）を追加します。
    
    Args:
        insight: 追加する知見オブジェクト
        db_path: データベースファイルのパス
        
    Returns:
        作成された知見のID
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_insights (category, content, context_tags, importance, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            insight.category,
            insight.content,
            insight.context_tags or "",
            insight.importance,
            insight.created_at,
            insight.updated_at
        ))
        
        insight_id = cursor.lastrowid
        logger.info(f"ユーザー知見を保存しました: ID={insight_id}, [{insight.category}] {insight.content[:30]}...")
        return insight_id


def get_user_insights(
    category: Optional[str] = None, 
    min_importance: int = 1,
    limit: int = 20, 
    db_path: str = "neo_secretary.db"
) -> List[UserInsight]:
    """
    重要度順（降順）でユーザー知見を取得します。
    
    Args:
        category: 取得対象のカテゴリ（'Constraint', 'Preference', 'Habit', 'Project'）。Noneで全件。
        min_importance: 最小重要度（1〜5）
        limit: 最大取得件数
        db_path: データベースファイルのパス
        
    Returns:
        UserInsightオブジェクトのリスト
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        if category:
            cursor.execute("""
                SELECT id, category, content, context_tags, importance, created_at, updated_at
                FROM user_insights
                WHERE category = ? AND importance >= ?
                ORDER BY importance DESC, updated_at DESC
                LIMIT ?
            """, (category, min_importance, limit))
        else:
            cursor.execute("""
                SELECT id, category, content, context_tags, importance, created_at, updated_at
                FROM user_insights
                WHERE importance >= ?
                ORDER BY importance DESC, updated_at DESC
                LIMIT ?
            """, (min_importance, limit))
            
        rows = cursor.fetchall()
        insights = []
        for r in rows:
            insights.append(UserInsight(
                id=r[0],
                category=r[1],
                content=r[2],
                context_tags=r[3],
                importance=r[4],
                created_at=r[5],
                updated_at=r[6]
            ))
        return insights


def delete_user_insight(insight_id: int, db_path: str = "neo_secretary.db") -> bool:
    """
    知見をID指定で削除します。
    
    Args:
        insight_id: 削除する知見ID
        db_path: データベースファイルのパス
        
    Returns:
        削除成功時はTrue
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_insights WHERE id = ?", (insight_id,))
        success = cursor.rowcount > 0
        if success:
            logger.info(f"ユーザー知見を削除しました: ID={insight_id}")
        return success


# =============================================================================
# CRUD操作: Tasks (TODOタスク管理)
# =============================================================================

def create_task(task: Task, db_path: str = "neo_secretary.db") -> int:
    """
    新しいTODOタスクを作成します。
    
    Args:
        task: 作成するタスク情報
        db_path: データベースファイルのパス
        
    Returns:
        作成されたタスクのID
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tasks (title, description, due_date, priority, status, parent_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task.title,
            task.description or "",
            task.due_date,
            task.priority,
            task.status,
            task.parent_id,
            task.created_at,
            task.updated_at
        ))
        
        task_id = cursor.lastrowid
        logger.info(f"タスクを作成しました: ID={task_id}, title={task.title}")
        return task_id


def get_tasks(
    status: Optional[str] = None, 
    min_priority: int = 0, 
    limit: int = 50, 
    db_path: str = "neo_secretary.db"
) -> List[Task]:
    """
    条件を指定してタスク一覧を取得します。
    
    Args:
        status: 取得する状態 ('todo', 'in_progress', 'completed')。Noneで未完了タスク(todo, in_progress)。
        min_priority: 最小優先度
        limit: 最大取得件数
        db_path: データベースファイルのパス
        
    Returns:
        Taskオブジェクトのリスト
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        if status:
            cursor.execute("""
                SELECT id, title, description, due_date, priority, status, parent_id, created_at, updated_at
                FROM tasks
                WHERE status = ? AND priority >= ?
                ORDER BY priority DESC, (due_date IS NULL) ASC, due_date ASC, id ASC
                LIMIT ?
            """, (status, min_priority, limit))
        else:
            cursor.execute("""
                SELECT id, title, description, due_date, priority, status, parent_id, created_at, updated_at
                FROM tasks
                WHERE status != 'completed' AND priority >= ?
                ORDER BY priority DESC, (due_date IS NULL) ASC, due_date ASC, id ASC
                LIMIT ?
            """, (min_priority, limit))
            
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
                created_at=r[7],
                updated_at=r[8]
            ))
        return tasks


def complete_task(task_id: int, db_path: str = "neo_secretary.db") -> bool:
    """
    タスクを完了状態 ('completed') に更新します。
    
    Args:
        task_id: 完了にするタスクID
        db_path: データベースファイルのパス
        
    Returns:
        更新成功時はTrue
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        now = int(datetime.now().timestamp() * 1000)
        cursor.execute("UPDATE tasks SET status = 'completed', updated_at = ? WHERE id = ?", (now, task_id))
        success = cursor.rowcount > 0
        if success:
            logger.info(f"タスクを完了にしました: ID={task_id}")
        return success


def delete_task(task_id: int, db_path: str = "neo_secretary.db") -> bool:
    """
    タスクを削除します。
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        success = cursor.rowcount > 0
        if success:
            logger.info(f"タスクを削除しました: ID={task_id}")
        return success


# =============================================================================
# データベース自動バックアップ＆整合性保護 (Data Persistence & Safety)
# =============================================================================

def backup_database(
    db_path: str = "neo_secretary.db",
    backup_dir: str = "backups",
    max_generations: int = 7
) -> Optional[str]:
    """
    SQLiteのOnline Backup API (`conn.backup()`) を使用して、
    アプリ稼働中・書き込み中でも破損リスクゼロで安全にバックアップを作成します。
    
    Args:
        db_path: ソースDBファイルパス
        backup_dir: バックアップ保存先ディレクトリ
        max_generations: 保持する世代数（古いものは自動ローテーション削除）
        
    Returns:
        Optional[str]: 作成されたバックアップファイルのパス（失敗時はNone）
    """
    source_file = Path(db_path)
    if not source_file.exists():
        logger.warning(f"バックアップ元DBファイルが存在しません: {db_path}")
        return None
        
    target_dir = Path(backup_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = target_dir / f"neo_secretary_backup_{timestamp}.db"
    
    try:
        source_conn = sqlite3.connect(str(source_file), timeout=10.0)
        backup_conn = sqlite3.connect(str(backup_file))
        
        with backup_conn:
            source_conn.backup(backup_conn, pages=100, sleep=0.01)
            
        backup_conn.close()
        source_conn.close()
        logger.info(f"データベースのオンラインバックアップを作成しました: {backup_file}")
        
        # 世代管理（古いバックアップのローテーション）
        existing_backups = sorted(
            list(target_dir.glob("neo_secretary_backup_*.db")),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        if len(existing_backups) > max_generations:
            for old_bak in existing_backups[max_generations:]:
                try:
                    old_bak.unlink()
                    logger.info(f"古いバックアップを自動ローテーション削除しました: {old_bak.name}")
                except Exception as e:
                    logger.warning(f"バックアップ削除エラー: {e}")
                    
        return str(backup_file)
    except Exception as e:
        logger.error(f"データベースバックアップ失敗: {e}")
        return None


def auto_backup():
    """起動時・終了時に呼び出す自動バックアップ（エラー発生時もメイン処理を止めない安全設計）"""
    try:
        backup_database()
    except Exception as e:
        logger.error(f"auto_backup 実行エラー: {e}")


# =============================================================================
# メイン処理（テスト用）
# =============================================================================

if __name__ == "__main__":
    print("=== データベース初期化 ===")
    init_db()
    
    print("\n=== カテゴリ作成 ===")
    work_category = Category(name="仕事", color="#A67B5B", icon="work")
    work_id = create_category(work_category)
    print(f"作成されたカテゴリID: {work_id}")
    
    print("\n=== 予定作成 ===")
    now = int(datetime.now().timestamp() * 1000)
    event = Event(
        title="プロジェクト会議",
        description="Neo-Secretaryの設計レビュー",
        start_time=now,
        end_time=now + (60 * 60 * 1000),
        recurrence_type="weekly",
        recurrence_rule={"days": ["月", "水", "金"], "time": "10:00"},
        category_id=work_id
    )
    event_id = create_event(event)
    print(f"作成された予定ID: {event_id}")
    
    print("\n=== 予定取得 ===")
    retrieved_event = get_event(event_id)
    if retrieved_event:
        print(f"取得した予定: {retrieved_event.title}")
    
    print("\n=== すべての操作が完了しました ===")
