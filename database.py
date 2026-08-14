"""
Neo-Secretary データベースモジュール

SQLiteデータベースの初期化、Pydanticモデル定義、CRUD操作を提供します。
Manus仕様準拠の recurrence_rule (JSON形式) を含む、型安全なデータベース層です。
"""

import logging
import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from pydantic import BaseModel, Field, validator

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
    try:
        conn = sqlite3.connect(db_path)
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
        logger.info("categoriesテーブルを作成しました")
        
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
        logger.info("eventsテーブルを作成しました")
        
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
        logger.info("sticky_notesテーブルを作成しました")

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
        logger.info("user_insightsテーブルを作成しました")

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
        logger.info("tasksテーブルを作成しました")
        
        conn.commit()
        logger.info(f"データベース初期化完了: {db_path}")
        
    except sqlite3.Error as e:
        logger.error(f"データベース初期化エラー: {e}")
        raise
    finally:
        conn.close()


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
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO categories (name, color, icon)
            VALUES (?, ?, ?)
        """, (category.name, category.color, category.icon))
        
        conn.commit()
        category_id = cursor.lastrowid
        logger.info(f"カテゴリを作成しました: ID={category_id}, name={category.name}")
        
        return category_id
        
    except sqlite3.Error as e:
        logger.error(f"カテゴリ作成エラー: {e}")
        raise
    finally:
        conn.close()


def get_category(category_id: int, db_path: str = "neo_secretary.db") -> Optional[Category]:
    """
    IDを指定してカテゴリを取得します。
    
    Args:
        category_id: カテゴリID
        db_path: データベースファイルのパス
    
    Returns:
        カテゴリ情報（存在しない場合はNone）
    """
    try:
        conn = sqlite3.connect(db_path)
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
        
    except sqlite3.Error as e:
        logger.error(f"カテゴリ取得エラー: {e}")
        raise
    finally:
        conn.close()


def get_all_categories(db_path: str = "neo_secretary.db") -> List[Category]:
    """
    全てのカテゴリを取得します。
    
    Args:
        db_path: データベースファイルのパス
    
    Returns:
        カテゴリのリスト
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM categories")
        rows = cursor.fetchall()
        
        categories = [
            Category(id=row[0], name=row[1], color=row[2], icon=row[3])
            for row in rows
        ]
        
        logger.info(f"{len(categories)}件のカテゴリを取得しました")
        return categories
        
    except sqlite3.Error as e:
        logger.error(f"カテゴリ一覧取得エラー: {e}")
        raise
    finally:
        conn.close()


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
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # recurrence_ruleをJSON文字列に変換
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
        
        conn.commit()
        event_id = cursor.lastrowid
        logger.info(f"予定を作成しました: ID={event_id}, title={event.title}")
        
        return event_id
        
    except sqlite3.Error as e:
        logger.error(f"予定作成エラー: {e}")
        raise
    finally:
        conn.close()


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
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        row = cursor.fetchone()
        
        if row:
            # recurrence_ruleをJSONから辞書に変換
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
        
    except sqlite3.Error as e:
        logger.error(f"予定取得エラー: {e}")
        raise
    finally:
        conn.close()


def get_upcoming_events(days: int = 7, db_path: str = "neo_secretary.db") -> List[Event]:
    """
    今後N日間の予定を取得します。
    
    Args:
        days: 取得する日数（デフォルト: 7日間）
        db_path: データベースファイルのパス
    
    Returns:
        予定のリスト（開始時刻の昇順）
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 現在時刻から指定日数後までのUnix Timestamp（ミリ秒）を計算
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
        
        logger.info(f"今後{days}日間の予定を{len(events)}件取得しました")
        return events
        
    except sqlite3.Error as e:
        logger.error(f"予定一覧取得エラー: {e}")
        raise
    finally:
        conn.close()


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
    
    Raises:
        sqlite3.Error: データベース操作でエラーが発生した場合
    """
    try:
        conn = sqlite3.connect(db_path)
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
        
        conn.commit()
        note_id = cursor.lastrowid
        logger.info(f"付箋を作成しました: ID={note_id}")
        
        return note_id
        
    except sqlite3.Error as e:
        logger.error(f"付箋作成エラー: {e}")
        raise
    finally:
        conn.close()


def get_all_sticky_notes(db_path: str = "neo_secretary.db") -> List[StickyNote]:
    """
    全ての付箋を取得します。
    
    Args:
        db_path: データベースファイルのパス
    
    Returns:
        付箋のリスト
    """
    try:
        conn = sqlite3.connect(db_path)
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
        
    except sqlite3.Error as e:
        logger.error(f"付箋一覧取得エラー: {e}")
        raise
    finally:
        conn.close()


def update_sticky_note(note: StickyNote, db_path: str = "neo_secretary.db") -> bool:
    """
    付箋の内容や位置を更新します。
    """
    if note.id is None:
        raise ValueError("更新には付箋のIDが必要です")
        
    try:
        conn = sqlite3.connect(db_path)
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
        
        conn.commit()
        success = cursor.rowcount > 0
        if success:
            logger.info(f"付箋を更新しました: ID={note.id}")
        else:
            logger.warning(f"更新対象の付箋が見つかりません: ID={note.id}")
            
        return success
        
    except sqlite3.Error as e:
        logger.error(f"付箋更新エラー: {e}")
        raise
    finally:
        conn.close()


def delete_sticky_note(note_id: int, db_path: str = "neo_secretary.db") -> bool:
    """
    指定したIDの付箋をデータベースから完全に削除します。
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM sticky_notes WHERE id = ?", (note_id,))
        conn.commit()
        
        success = cursor.rowcount > 0
        if success:
            logger.info(f"付箋を削除しました: ID={note_id}")
        else:
            logger.warning(f"削除対象の付箋が見つかりません: ID={note_id}")
            
        return success
        
    except sqlite3.Error as e:
        logger.error(f"付箋削除エラー: {e}")
        raise
    finally:
        conn.close()


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
    try:
        conn = sqlite3.connect(db_path)
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
        
        conn.commit()
        insight_id = cursor.lastrowid
        logger.info(f"ユーザー知見を保存しました: ID={insight_id}, [{insight.category}] {insight.content[:30]}...")
        return insight_id
    except sqlite3.Error as e:
        logger.error(f"ユーザー知見保存エラー: {e}")
        raise
    finally:
        conn.close()


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
    try:
        conn = sqlite3.connect(db_path)
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
    except sqlite3.Error as e:
        logger.error(f"ユーザー知見取得エラー: {e}")
        return []
    finally:
        conn.close()


def delete_user_insight(insight_id: int, db_path: str = "neo_secretary.db") -> bool:
    """
    知見をID指定で削除します。
    
    Args:
        insight_id: 削除する知見ID
        db_path: データベースファイルのパス
        
    Returns:
        削除成功時はTrue
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_insights WHERE id = ?", (insight_id,))
        conn.commit()
        logger.info(f"ユーザー知見を削除しました: ID={insight_id}")
        return True
    except sqlite3.Error as e:
        logger.error(f"ユーザー知見削除エラー: {e}")
        return False
    finally:
        conn.close()


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
    try:
        conn = sqlite3.connect(db_path)
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
        
        conn.commit()
        task_id = cursor.lastrowid
        logger.info(f"タスクを作成しました: ID={task_id}, title={task.title}")
        return task_id
    except sqlite3.Error as e:
        logger.error(f"タスク作成エラー: {e}")
        raise
    finally:
        conn.close()


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
    try:
        conn = sqlite3.connect(db_path)
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
    except sqlite3.Error as e:
        logger.error(f"タスク取得エラー: {e}")
        return []
    finally:
        conn.close()


def complete_task(task_id: int, db_path: str = "neo_secretary.db") -> bool:
    """
    タスクを完了状態 ('completed') に更新します。
    
    Args:
        task_id: 完了にするタスクID
        db_path: データベースファイルのパス
        
    Returns:
        更新成功時はTrue
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        now = int(datetime.now().timestamp() * 1000)
        cursor.execute("UPDATE tasks SET status = 'completed', updated_at = ? WHERE id = ?", (now, task_id))
        conn.commit()
        logger.info(f"タスクを完了にしました: ID={task_id}")
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"タスク完了更新エラー: {e}")
        return False
    finally:
        conn.close()


def delete_task(task_id: int, db_path: str = "neo_secretary.db") -> bool:
    """
    タスクを削除します。
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        logger.info(f"タスクを削除しました: ID={task_id}")
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"タスク削除エラー: {e}")
        return False
    finally:
        conn.close()


# =============================================================================
# メイン処理（テスト用）
# =============================================================================

if __name__ == "__main__":
    # データベース初期化
    print("=== データベース初期化 ===")
    init_db()
    
    # サンプルカテゴリ作成
    print("\n=== カテゴリ作成 ===")
    work_category = Category(name="仕事", color="#A67B5B", icon="work")
    work_id = create_category(work_category)
    print(f"作成されたカテゴリID: {work_id}")
    
    # サンプル予定作成
    print("\n=== 予定作成 ===")
    now = int(datetime.now().timestamp() * 1000)
    event = Event(
        title="プロジェクト会議",
        description="Neo-Secretaryの設計レビュー",
        start_time=now,
        end_time=now + (60 * 60 * 1000),  # 1時間後
        recurrence_type="weekly",
        recurrence_rule={"days": ["月", "水", "金"], "time": "10:00"},
        category_id=work_id
    )
    event_id = create_event(event)
    print(f"作成された予定ID: {event_id}")
    
    # 予定取得
    print("\n=== 予定取得 ===")
    retrieved_event = get_event(event_id)
    print(f"取得した予定: {retrieved_event.title}")
    print(f"繰り返しルール: {retrieved_event.recurrence_rule}")
    
    # 付箋作成
    print("\n=== 付箋作成 ===")
    note = StickyNote(
        content="データベース実装完了！",
        color="#FFEB3B",
        position_x=200,
        position_y=200
    )
    note_id = create_sticky_note(note)
    print(f"作成された付箋ID: {note_id}")
    
    print("\n=== すべての操作が完了しました ===")
