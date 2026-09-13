"""
Neo-Secretary データベースモジュール

SQLiteデータベースの初期化、Pydanticモデル定義、CRUD操作を提供します。
Manus仕様準拠の recurrence_rule (JSON形式) を含む、型安全なデータベース層です。
contextlib.contextmanager による接続管理を一元化し、例外時の自動ロールバックとリソースリーク防止を徹底しています。
"""

import logging
import sqlite3
import json
import calendar
import hashlib
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Generator
from pathlib import Path

from pydantic import BaseModel, Field, ValidationInfo, field_validator

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
        # WALファイル肥大化の防止は SQLite エンジンの自動チェックポイントに委譲する。
        # 接続ごとの手動 TRUNCATE チェックポイントは高頻度ポーリング（スマホPWA等）時に
        # I/O競合・ロック遅延を招くため廃止し、wal_autocheckpoint（既定1000ページ）による
        # バックグラウンド自動チェックポイントへ一本化した（2026-09-01 3周レビュー P0対応）。
        conn.execute("PRAGMA wal_autocheckpoint=1000;")
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
    source_id: Optional[int] = None
    
    @field_validator('end_time')
    @classmethod
    def end_after_start(cls, v: int, info: ValidationInfo) -> int:
        """終了時刻が開始時刻より後であることを検証します (Pydantic V2 形式へ移行済み)。"""
        start_time = info.data.get('start_time')
        if start_time is not None and v <= start_time:
            raise ValueError('end_timeはstart_timeより後である必要があります')
        return v


class CalendarSource(BaseModel):
    """
    カレンダー購読ソース（iCal URL）を表すモデル。
    
    仕事用・プライベート等の複数のGoogleカレンダーを識別して同期するために使用します。
    
    Attributes:
        id: ソースID（自動採番）
        name: 表示名（例: '仕事用', 'プライベート'）
        color: 手帳表示用の識別色（Hex）
        url: 秘密 iCal アドレス（空なら未設定）
        enabled: 同期・表示のON/OFF
        last_sync: 最終同期時刻（表示用文字列）
    """
    id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=50)
    color: str = Field(default="#A67B5B", pattern=r'^#[0-9A-Fa-f]{6}$')
    url: str = Field(default="", max_length=2000)
    enabled: bool = True
    last_sync: str = "未同期"


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
    """
    id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = ""
    due_date: Optional[int] = None
    priority: int = Field(default=0, ge=0, le=3)
    status: str = Field(default="todo", pattern=r'^(todo|in_progress|completed)$')
    parent_id: Optional[int] = None
    list_id: Optional[int] = None
    tags: str = Field(default="", max_length=500)  # カンマ区切りタグ (例: "仕事,急ぎ")
    importance_flag: Optional[bool] = None  # 明示的重要度 (True=重要 / None=未指定→推定ルールへフォールバック)
    urgency_flag: Optional[bool] = None  # 明示的緊急度 (True=緊急 / None=未指定→推定ルールへフォールバック)
    recurrence: Optional[str] = Field(default=None, pattern=r'^(daily|weekly|monthly)$')  # 繰り返し種別 (None=単発)
    created_at: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    updated_at: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))


class TaskList(BaseModel):
    """
    タスクリスト (TickTick風のリスト分類) を表すモデル。

    parent_id により階層ツリー構造を表現する (フォルダ/サブリスト・Block 1.6-R)。
    parent_id=None は最上位 (ルート) リストを意味する。
    """
    id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=50)
    emoji: str = Field(default="📋")
    parent_id: Optional[int] = None
    sort_order: int = Field(default=0)
    created_at: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))


class Habit(BaseModel):
    """
    習慣トラッカー情報を表すモデル。
    """
    id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=100)
    emoji: str = Field(default="🌱")
    target_days_per_week: int = Field(default=7, ge=1, le=7)
    created_at: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))


class HabitLog(BaseModel):
    """
    習慣達成ログを表すモデル。
    """
    id: Optional[int] = None
    habit_id: int
    completed_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$') # YYYY-MM-DD
    created_at: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
class HabitWithStatus(BaseModel):
    """
    習慣1件と当日の達成状態を表すモデル (get_habits_with_status 戻り値)。

    2026-09-01 P2①第二段: dict 生辞書からの移行。キー名ミスによる
    実行時エラー / サイレントバグ (briefing_engine の is_done 誤参照) を
    型で構造的に防止する。
    """
    id: Optional[int] = None
    title: str = ""
    emoji: Optional[str] = None
    target_days_per_week: int = 7
    completed_today: bool = False
    streak: int = 0
    total_completed: int = 0
    created_at: Optional[int] = None


class HabitHeatmapPoint(BaseModel):
    """
    習慣ヒートマップ1日分の集計を表すモデル (get_habit_heatmap_data 戻り値)。

    level: 0=なし, 1=薄緑, 2=緑, 3=濃緑, 4=金 (達成数に応じる)。
    day_of_week: 0=月 ... 6=日。
    """
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    count: int = 0
    level: int = 0
    day_of_week: int = 0


class MinigameScore(BaseModel):
    """
    ミニゲームのスコア記録を表すモデル。

    シークレットミニゲーム（Phase L5 Pixel Defense 等）のプレイ結果を
    SQLite へ永続化し、ハイスコアや履歴表示に利用します。

    Attributes:
        id: スコア記録ID（自動採番）
        game_id: ゲーム識別子（例: 'pixel_defense'）
        score: 達成スコア（0以上）
        created_at: 記録時刻（Unix Timestamp ミリ秒）
    """
    id: Optional[int] = None
    game_id: str = Field(..., min_length=1, max_length=50)
    score: int = Field(..., ge=0)
    created_at: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))


class Device(BaseModel):
    """
    登録済みクライアント端末（デバイス台帳）を表すモデル。
    
    ゼロトラスト原則に基づき、スマホPWAや外部連携端末の接続トークンハッシュ、
    端末名、IP、User-Agent、失効状態を追跡します。
    
    Attributes:
        id: デバイスID（自動採番）
        device_name: 端末表示名（例: "Boss iPhone 15 Pro"）
        token_hash: 認証トークンのSHA-256ハッシュ
        ip_address: 最終接続元IPアドレス
        user_agent: 最終接続元ブラウザ/クライアント識別子
        created_at: 登録時刻（Unix Timestamp ミリ秒）
        last_seen: 最終アクセス時刻（Unix Timestamp ミリ秒）
        is_revoked: 失効フラグ（0: 有効, 1: 失効）
    """
    id: Optional[int] = None
    device_name: str = Field(..., min_length=1, max_length=100)
    token_hash: str = Field(..., min_length=1)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    last_seen: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    is_revoked: int = 0




# =============================================================================
# データベース初期化
# =============================================================================

def init_db(db_path: str = "neo_secretary.db") -> None:
    """
    SQLiteデータベースを初期化します。
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
        
        # calendar_sourcesテーブル (カレンダー購読ソース: 仕事用/プライベート等の複数iCal)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calendar_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                color TEXT NOT NULL DEFAULT '#A67B5B',
                url TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                last_sync TEXT NOT NULL DEFAULT '未同期'
            )
        """)

        # events.source_id マイグレーション（既存DBへのカラム追加）
        cursor.execute("PRAGMA table_info(events)")
        event_columns = {row[1] for row in cursor.fetchall()}
        if "source_id" not in event_columns:
            cursor.execute("ALTER TABLE events ADD COLUMN source_id INTEGER")
            # 既存のGoogle由来予定は先頭ソース（id=1）へ帰属させる
            cursor.execute("""
                UPDATE events
                SET source_id = 1
                WHERE google_event_id IS NOT NULL AND google_event_id != '' AND source_id IS NULL
            """)
            logger.info("events.source_id カラムを追加し、既存Google予定をソース1へ移行しました")
        
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
                list_id INTEGER,
                tags TEXT NOT NULL DEFAULT '',
                importance_flag INTEGER,
                urgency_flag INTEGER,
                recurrence TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (parent_id) REFERENCES tasks (id)
            )
        """)

        # task_listsテーブル (TickTick風タスクリスト分類・parent_idで階層ツリーを表現)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                emoji TEXT NOT NULL DEFAULT '📋',
                parent_id INTEGER,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (parent_id) REFERENCES task_lists (id)
            )
        """)

        # task_lists.parent_id マイグレーション（既存DBへのカラム追加・Block 1.6-R）
        cursor.execute("PRAGMA table_info(task_lists)")
        task_list_columns = {row[1] for row in cursor.fetchall()}
        if "parent_id" not in task_list_columns:
            cursor.execute("ALTER TABLE task_lists ADD COLUMN parent_id INTEGER")
            logger.info("task_lists.parent_id カラムを追加しました (リスト階層化・Block 1.6-R)")

        # reminders_sentテーブル (リマインダー重複防止・冪等記録: roadmap 3.1)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders_sent (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_type TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                sent_at INTEGER NOT NULL,
                UNIQUE(item_type, item_id)
            )
        """)

        # tasks.list_id / tasks.tags マイグレーション（既存DBへのカラム追加）
        cursor.execute("PRAGMA table_info(tasks)")
        task_columns = {row[1] for row in cursor.fetchall()}
        if "list_id" not in task_columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN list_id INTEGER")
            logger.info("tasks.list_id カラムを追加しました (TickTick拡張)")
        if "tags" not in task_columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN tags TEXT NOT NULL DEFAULT ''")
            logger.info("tasks.tags カラムを追加しました (TickTick拡張)")
        # tasks.importance_flag / tasks.urgency_flag マイグレーション（4象限属性・roadmap 1.14）
        if "importance_flag" not in task_columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN importance_flag INTEGER")
            logger.info("tasks.importance_flag カラムを追加しました (4象限属性)")
        if "urgency_flag" not in task_columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN urgency_flag INTEGER")
            logger.info("tasks.urgency_flag カラムを追加しました (4象限属性)")
        # tasks.recurrence マイグレーション（繰り返しタスク・roadmap 1.12）
        if "recurrence" not in task_columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN recurrence TEXT")
            logger.info("tasks.recurrence カラムを追加しました (繰り返しタスク)")

        # habitsテーブル (習慣トラッカー)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                emoji TEXT NOT NULL DEFAULT '🌱',
                target_days_per_week INTEGER NOT NULL DEFAULT 7,
                created_at INTEGER NOT NULL
            )
        """)

        # habit_logsテーブル (習慣達成ログ)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS habit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id INTEGER NOT NULL,
                completed_date TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (habit_id) REFERENCES habits (id),
                UNIQUE(habit_id, completed_date)
            )
        """)
        logger.info("habits/habit_logsテーブルを確認/作成しました")

        # minigame_scoresテーブル (シークレットミニゲームのスコア記録: Phase L5)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS minigame_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                score INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_minigame_scores_game_score "
            "ON minigame_scores (game_id, score DESC)"
        )
        logger.info("minigame_scoresテーブルを確認/作成しました")

        # devicesテーブル (ゼロトラスト端末台帳・個別トークン失効管理: roadmap 2.6)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_name TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                ip_address TEXT,
                user_agent TEXT,
                created_at INTEGER NOT NULL,
                last_seen INTEGER NOT NULL,
                is_revoked INTEGER NOT NULL DEFAULT 0
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_devices_token_hash "
            "ON devices (token_hash)"
        )
        logger.info("devicesテーブルを確認/作成しました")

        # approval_audit_logsテーブル (エージェント承認監査ログ基盤: Block 2)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS approval_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                agent_type TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                command TEXT NOT NULL,
                summary TEXT,
                risk_level TEXT NOT NULL,
                decision TEXT NOT NULL,
                decision_by TEXT NOT NULL DEFAULT 'human',
                decision_message TEXT,
                requester_ip TEXT,
                client_ip TEXT,
                duration_sec REAL DEFAULT 0.0,
                created_at INTEGER NOT NULL
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_request_id "
            "ON approval_audit_logs (request_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_created_at "
            "ON approval_audit_logs (created_at)"
        )
        logger.info("approval_audit_logsテーブルを確認/作成しました")
        
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
                recurrence_type, recurrence_rule, category_id, google_event_id, source_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.title, event.description, event.start_time, event.end_time,
            event.recurrence_type, recurrence_rule_json, event.category_id, event.google_event_id, event.source_id
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
                google_event_id=row[8],
                source_id=(row[9] if len(row) > 9 else None)
            )
        return None


def _rows_to_events(rows: list) -> List[Event]:
    """
    events テーブルの SELECT * 結果行を Event モデルのリストへ変換する（共通ヘルパー）。

    Args:
        rows: cursor.fetchall() の結果（カラム順は events テーブル定義に従う）。

    Returns:
        予定のリスト（入力順）。
    """
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
        
        events = _rows_to_events(cursor.fetchall())
        
        logger.debug(f"今後{days}日間の予定を{len(events)}件取得しました")
        return events


def get_events_between(start_ms: int, end_ms: int, db_path: str = "neo_secretary.db") -> List[Event]:
    """
    指定した期間内に開始する予定を取得します。
    
    月間・週間カレンダー描画のように「過去を含む任意期間」を表示するために使用します。
    get_upcoming_events は「現在時刻以降」に限定されるため、過去日を含むカレンダー描画には使えません。
    
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
    """
    カレンダー購読ソースを追加します。
    
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
        source_id = cursor.lastrowid
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
    """
    全てのカレンダー購読ソースを取得します（作成順）。
    
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
    """
    IDを指定してカレンダー購読ソースを取得します。
    
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
    """
    カレンダー購読ソースの内容（名前・色・URL・有効フラグ・最終同期）を更新します。
    
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
    """
    カレンダー購読ソースの有効/無効を切り替えます。
    
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
    """
    カレンダー購読ソースの最終同期時刻を記録します。
    
    Args:
        source_id: ソースID
        time_str: 表示用の同期時刻文字列
        db_path: データベースファイルのパス
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE calendar_sources SET last_sync = ? WHERE id = ?", (time_str, source_id))


def delete_calendar_source(source_id: int, db_path: str = "neo_secretary.db") -> None:
    """
    カレンダー購読ソースを削除し、その同期済み予定も併せて削除します。
    
    Args:
        source_id: ソースID
        db_path: データベースファイルのパス
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM events WHERE source_id = ?", (source_id,))
        cursor.execute("DELETE FROM calendar_sources WHERE id = ?", (source_id,))
        logger.info(f"カレンダーソースとその予定を削除しました: ID={source_id}")


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


def add_user_insight(
    category: str,
    content: str,
    importance: int = 3,
    context_tags: str = "",
    db_path: str = "neo_secretary.db"
) -> int:
    """
    新しいユーザー知見を user_insights テーブルに登録します。

    Args:
        category: 知見カテゴリ ('Constraint', 'Preference', 'Habit', 'Project')
        content: 知見の本文
        importance: 重要度 (1〜5, 5が最重要)
        context_tags: 検索用カンマ区切りタグ
        db_path: データベースファイルのパス

    Returns:
        作成された知見のID

    Raises:
        ValueError: category が許可パターン外の場合 (Pydantic 検証)
    """
    insight = UserInsight(
        category=category,
        content=content,
        context_tags=context_tags,
        importance=importance
    )
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
        logger.info(f"ユーザー知見を登録しました: ID={insight_id}, category={insight.category}")
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
        
        task_id = cursor.lastrowid
        logger.info(f"タスクを作成しました: ID={task_id}, title={task.title}")
        return task_id


def get_tasks(
    status: Optional[str] = None, 
    min_priority: int = 0, 
    limit: int = 50, 
    list_id: Optional[int] = None,
    db_path: str = "neo_secretary.db"
) -> List[Task]:
    """
    条件を指定してタスク一覧を取得します。
    
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
    """
    指定された親タスクに紐づく子タスク（サブタスク・チェックリスト）一覧を取得します。
    
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
    """
    親タスクに子タスク（サブタスク）を追加します。
    
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
    """
    繰り返しタスクの次回期限を計算する (完了時の自動次回生成用)。

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
        # 前回期限の翌日。既に現在時刻を過ぎていれば過ぎるまで進める
        # (しばらく完了せず放置していたケースで未来日までスキップする)
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
        # 月加算は月末クランプ付き (1月31日 → 2月28日 → 3月28日)
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
    """
    タスクを完了状態 ('completed') に更新します。

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
        # 繰り返し属性を完了更新前に取得 (同一コネクション内で完結させる)
        cursor.execute(
            "SELECT recurrence, due_date, title, description, priority, tags, list_id, importance_flag, urgency_flag FROM tasks WHERE id = ?",
            (task_id,)
        )
        row = cursor.fetchone()
        cursor.execute("UPDATE tasks SET status = 'completed', updated_at = ? WHERE id = ?", (now, task_id))
        success = cursor.rowcount > 0
        if success:
            logger.info(f"タスクを完了にしました: ID={task_id}")
            # 繰り返しタスクなら次回分を自動生成する
            # 注意: このトランザクション内 (同一接続) で完結させる。
            # 別接続の create_task を呼ぶと SQLite の書き込みロック競合で
            # "database is locked" になるため、ここでは直接 INSERT する。
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
                        # 次回生成に失敗しても完了更新自体は成功扱いとする (ログで追跡)
                        logger.error(f"繰り返しタスクの次回生成に失敗: {e}")
        return success


def reopen_task(task_id: int, db_path: str = "neo_secretary.db") -> bool:
    """
    完了済みタスクを未完了 ('todo') に戻します (誤タップ復活用)。

    繰り返しタスクを取り消した場合は、完了時に自動生成された「次回分」タスクを
    削除して完了前の状態に巻き戻します。次回分の特定は「同一タイトル×同一
    recurrence×未完了×完了時刻 (updated_at) 以降に作成されたもの」とする。

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
            # 繰り返しタスクなら完了時に生成された次回分を巻き戻し削除する
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


def update_task(task_id: int, updates: dict, db_path: str = "neo_secretary.db") -> bool:
    """
    タスクの指定フィールドを更新します (スマホ編集シート・PC手帳共通)。

    ホワイトリスト外のキーは無視するため、クライアント由来の不正な
    カラム指定を構造的に遮断します。

    Args:
        task_id: 更新対象のタスクID
        updates: 更新するフィールドの辞書 (title / description / due_date /
                 priority / status / tags / importance_flag / urgency_flag /
                 recurrence / list_id が有効)
        db_path: データベースファイルのパス

    Returns:
        更新が1件以上適用された場合はTrue、対象なし・無効キーのみはFalse
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
        # 真偽値属性はSQLiteのINTEGER (0/1/NULL) に正規化する
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
# リマインダー送信履歴 (reminder_engine から利用・重複通知防止)
# =============================================================================

def is_reminder_sent(item_type: str, item_id: int, db_path: str = "neo_secretary.db") -> bool:
    """
    指定した対象のリマインダーが既に送信済みかを判定します。

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
    """
    リマインダーの送信済みを冪等に記録します (再通知防止)。

    UNIQUE(item_type, item_id) 制約により二重記録は無視されます。

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


def get_task_lists(db_path: str = "neo_secretary.db") -> List[TaskList]:
    """
    タスクリスト一覧を作成順で取得します。

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
    """
    リスト移動時に循環参照が発生するかを判定します (内部ヘルパー)。

    Args:
        list_id: 移動対象リストID
        new_parent_id: 新しい親リストID
        conn: 既存のDB接続 (get_db_connection コンテキスト内)
        db_path: データベースファイルのパス (ログ用)

    Returns:
        循環 (自分自身または子孫を親に指定) する場合はTrue
    """
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
    """
    新しいタスクリストを作成します (任意の親リストの下に階層作成可能)。

    Args:
        name: リスト名 (空・空白のみはValueError)
        emoji: リストに表示する絵文字
        sort_order: ソート順 (小さいほど先頭)
        parent_id: 親リストID (None=最上位 / 存在しないIDはValueError)
        db_path: データベースファイルのパス

    Returns:
        作成されたリストのID

    Raises:
        ValueError: リスト名が空の場合、または親リストIDが存在しない場合
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
        list_id = cursor.lastrowid
        logger.info(f"タスクリストを作成しました: ID={list_id}, name={clean_name}, parent_id={parent_id}")
        return list_id


def move_task_list(list_id: int, new_parent_id: Optional[int], db_path: str = "neo_secretary.db") -> bool:
    """
    タスクリストを別の親リストの下へ移動します (階層変更・Block 1.6-R)。

    Args:
        list_id: 移動対象リストID
        new_parent_id: 新しい親リストID (None=最上位へ移動)
        db_path: データベースファイルのパス

    Returns:
        移動成功時はTrue (対象リストが存在しない場合はFalse)

    Raises:
        ValueError: 自分自身または子孫リストを親に指定した場合 (循環参照)
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
    """
    タスクリストを削除します。所属タスクはリスト未分類 (list_id=NULL) へ移行されます。

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
        # 子リストは親の親へ昇格させる (階層ツリー分断の防止・Block 1.6-R)
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
    """
    タスクリストの名称（および任意で絵文字）を変更します (PC手帳リスト管理・roadmap 1.6)。

    Args:
        list_id: 対象リストID
        name: 新しいリスト名 (空・空白のみはValueError)
        emoji: 新しい絵文字 (Noneの場合は変更しない)
        db_path: データベースファイルのパス

    Returns:
        更新成功時はTrue (対象リストが存在しない場合はFalse)

    Raises:
        ValueError: リスト名が空の場合
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
    """
    タスクのタグを更新します (カンマ区切り)。

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
# CRUD操作: Habits (習慣トラッカー ＆ キズナ草ヒートマップ)
# =============================================================================

def create_habit(habit: Habit, db_path: str = "neo_secretary.db") -> int:
    """新規習慣を登録"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO habits (title, emoji, target_days_per_week, created_at)
            VALUES (?, ?, ?, ?)
        """, (habit.title, habit.emoji, habit.target_days_per_week, habit.created_at))
        habit_id = cursor.lastrowid
        logger.info(f"習慣を作成しました: ID={habit_id}, title={habit.title}")
        return habit_id


def delete_habit(habit_id: int, db_path: str = "neo_secretary.db") -> bool:
    """習慣および関連ログを削除"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM habit_logs WHERE habit_id = ?", (habit_id,))
        cursor.execute("DELETE FROM habits WHERE id = ?", (habit_id,))
        return cursor.rowcount > 0


def toggle_habit_log(habit_id: int, target_date: Optional[str] = None, db_path: str = "neo_secretary.db") -> bool:
    """
    指定日（デフォルト: 今日 YYYY-MM-DD）の習慣達成をトグル（ON/OFF）。
    達成された場合は True、解除された場合は False を返却。
    """
    if not target_date:
        target_date = datetime.now().strftime("%Y-%m-%d")

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM habit_logs WHERE habit_id = ? AND completed_date = ?", (habit_id, target_date))
        row = cursor.fetchone()
        
        if row:
            # 既に達成済み ➔ 解除
            cursor.execute("DELETE FROM habit_logs WHERE id = ?", (row[0],))
            logger.info(f"習慣達成を解除: Habit={habit_id}, Date={target_date}")
            return False
        else:
            # 未達成 ➔ 達成マーク
            now_ms = int(datetime.now().timestamp() * 1000)
            cursor.execute("""
                INSERT INTO habit_logs (habit_id, completed_date, created_at)
                VALUES (?, ?, ?)
            """, (habit_id, target_date, now_ms))
            logger.info(f"習慣達成を記録: Habit={habit_id}, Date={target_date}")
            return True


def get_habits_with_status(db_path: str = "neo_secretary.db") -> List[HabitWithStatus]:
    """
    全習慣リストを取得し、今日の達成状態（completed_today）、現在の連続日数（streak）、
    および過去7日間の達成履歴を付与して返却。
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, emoji, target_days_per_week, created_at FROM habits ORDER BY id ASC")
        rows = cursor.fetchall()
        
        results = []
        for r in rows:
            h_id, title, emoji, target_days, created_at = r
            
            # 今日の達成
            cursor.execute("SELECT 1 FROM habit_logs WHERE habit_id = ? AND completed_date = ?", (h_id, today_str))
            completed_today = cursor.fetchone() is not None
            
            # 全達成日を取得してストリーク計算
            cursor.execute("SELECT completed_date FROM habit_logs WHERE habit_id = ? ORDER BY completed_date DESC", (h_id,))
            dates = [row[0] for row in cursor.fetchall()]
            
            # 連続日数 (Streak) 計算
            streak = 0
            check_date = datetime.now().date()
            if not completed_today:
                # 今日まだやってない場合は昨日から数える
                from datetime import timedelta
                check_date = check_date - timedelta(days=1)
                
            from datetime import timedelta
            date_set = set(dates)
            while check_date.strftime("%Y-%m-%d") in date_set:
                streak += 1
                check_date = check_date - timedelta(days=1)
                
            results.append(HabitWithStatus(
                id=h_id,
                title=title,
                emoji=emoji,
                target_days_per_week=target_days,
                completed_today=completed_today,
                streak=streak,
                total_completed=len(dates),
                created_at=created_at,
            ))
            
        return results


def get_habit_heatmap_data(days: int = 90, db_path: str = "neo_secretary.db") -> List[HabitHeatmapPoint]:
    """
    過去N日間のGitHub草風ヒートマップ集計データを返却。
    
    Returns:
        List[Dict[str, Any]]: 各日の日付(date)、達成数(count)、レベル0〜4(level: 0=なし, 1=薄緑, 2=緑, 3=濃緑, 4=金)
    """
    from datetime import timedelta, date
    today = date.today()
    start_date = today - timedelta(days=days - 1)
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT completed_date, COUNT(*) 
            FROM habit_logs 
            WHERE completed_date >= ?
            GROUP BY completed_date
        """, (start_date.strftime("%Y-%m-%d"),))
        
        counts = {r[0]: r[1] for r in cursor.fetchall()}
        
    heatmap = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        cnt = counts.get(d_str, 0)
        
        # 達成数に応じたレベル判定 (0〜4)
        if cnt == 0:
            lvl = 0
        elif cnt == 1:
            lvl = 1
        elif cnt == 2:
            lvl = 2
        elif cnt >= 3 and cnt < 5:
            lvl = 3
        else:
            lvl = 4
            
        heatmap.append(HabitHeatmapPoint(
            date=d_str,
            count=cnt,
            level=lvl,
            day_of_week=d.weekday(),  # 0=月, 6=日
        ))
        
    return heatmap


# =============================================================================
# CRUD操作: MinigameScores (Phase L5 シークレットミニゲーム)
# =============================================================================

def record_minigame_score(game_id: str, score: int, db_path: str = "neo_secretary.db") -> int:
    """
    ミニゲームのスコアを1件記録します。

    Args:
        game_id: ゲーム識別子（例: 'pixel_defense'）
        score: 達成スコア（0以上の整数）
        db_path: データベースファイルのパス

    Returns:
        作成されたスコア記録のID

    Raises:
        ValueError: game_id が空または score が負の場合
        sqlite3.Error: データベース操作でエラーが発生した場合
    """
    normalized_game_id = (game_id or "").strip()
    if not normalized_game_id:
        raise ValueError("game_id は空文字であってはいけません")
    if score < 0:
        raise ValueError("score は0以上の整数である必要があります")

    record = MinigameScore(game_id=normalized_game_id, score=score)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO minigame_scores (game_id, score, created_at)
            VALUES (?, ?, ?)
        """, (record.game_id, record.score, record.created_at))
        record_id = cursor.lastrowid
        logger.info(f"👾 ミニゲームスコアを記録: game_id={record.game_id}, score={record.score}, ID={record_id}")
        return record_id


def get_high_score(game_id: str, db_path: str = "neo_secretary.db") -> int:
    """
    指定ゲームのハイスコア（自己ベスト）を取得します。

    Args:
        game_id: ゲーム識別子（例: 'pixel_defense'）
        db_path: データベースファイルのパス

    Returns:
        ハイスコア（記録が1件もない場合は0）
    """
    normalized_game_id = (game_id or "").strip()
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MAX(score) FROM minigame_scores WHERE game_id = ?
        """, (normalized_game_id,))
        row = cursor.fetchone()
        return int(row[0]) if row and row[0] is not None else 0


def get_recent_minigame_scores(game_id: str, limit: int = 10, db_path: str = "neo_secretary.db") -> List[MinigameScore]:
    """
    指定ゲームの直近スコア履歴を新しい順に取得します。

    Args:
        game_id: ゲーム識別子（例: 'pixel_defense'）
        limit: 取得する最大件数（1以上）
        db_path: データベースファイルのパス

    Returns:
        スコア記録のリスト（新しい順）
    """
    normalized_game_id = (game_id or "").strip()
    if limit < 1:
        limit = 1
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, game_id, score, created_at
            FROM minigame_scores
            WHERE game_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        """, (normalized_game_id, limit))
        rows = cursor.fetchall()
        return [
            MinigameScore(id=row[0], game_id=row[1], score=row[2], created_at=row[3])
            for row in rows
        ]


# =============================================================================
# CRUD操作: Devices (端末台帳・ゼロトラスト認証)
# =============================================================================

def register_device(
    device_name: str,
    token_hash: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    db_path: str = "neo_secretary.db"
) -> int:
    """
    新規端末を登録、または同一token_hashの端末情報を更新します。

    Args:
        device_name: 端末表示名
        token_hash: 認証トークンのSHA-256ハッシュ文字列
        ip_address: 接続元IP
        user_agent: 接続元User-Agent
        db_path: データベースファイルのパス

    Returns:
        登録または更新されたデバイスID
    """
    now = int(datetime.now().timestamp() * 1000)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM devices WHERE token_hash = ?
        """, (token_hash,))
        row = cursor.fetchone()
        if row:
            dev_id = int(row[0])
            cursor.execute("""
                UPDATE devices
                SET device_name = ?,
                    ip_address = COALESCE(?, ip_address),
                    user_agent = COALESCE(?, user_agent),
                    last_seen = ?
                WHERE id = ?
            """, (device_name, ip_address, user_agent, now, dev_id))
            logger.info(f"デバイス台帳更新: ID={dev_id}, name={device_name}")
            return dev_id
        else:
            cursor.execute("""
                INSERT INTO devices (
                    device_name, token_hash, ip_address, user_agent,
                    created_at, last_seen, is_revoked
                ) VALUES (?, ?, ?, ?, ?, ?, 0)
            """, (device_name, token_hash, ip_address, user_agent, now, now))
            dev_id = int(cursor.lastrowid)
            logger.info(f"新規デバイス登録: ID={dev_id}, name={device_name}")
            return dev_id


def get_device_by_token_hash(token_hash: str, db_path: str = "neo_secretary.db") -> Optional[Device]:
    """
    token_hash に合致するデバイス情報を取得します。

    Args:
        token_hash: トークンのSHA-256ハッシュ
        db_path: データベースファイルのパス

    Returns:
        Device モデル、見つからない場合は None
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, device_name, token_hash, ip_address, user_agent,
                   created_at, last_seen, is_revoked
            FROM devices
            WHERE token_hash = ?
        """, (token_hash,))
        row = cursor.fetchone()
        if not row:
            return None
        return Device(
            id=row[0],
            device_name=row[1],
            token_hash=row[2],
            ip_address=row[3],
            user_agent=row[4],
            created_at=row[5],
            last_seen=row[6],
            is_revoked=row[7],
        )


def sync_device_session(
    device_name: str,
    bearer: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    db_path: str = "neo_secretary.db"
) -> Optional[Device]:
    """認証済み Bearer トークンに対応する端末セッションをデバイス台帳へ同期する。

    SHA-256 ハッシュ化をデータベース層の内部手順として隠蔽し、呼び出し側
    (HTTPサーバー) からハッシュアルゴリズムの詳細を取り除く (Deep Module 原則)。
    登録済みかつ失効していない端末は last_seen 更新のみを行い、
    未登録端末は device_name で自動登録する。last_seen 更新と自動登録は
    通信を阻害しないよう失敗時に debug ログのみで継続する Fail-Safe とする。
    なお台帳照会の失敗は握りつぶさず上位へ伝播させる (呼び出し側で Fail-Safe)。

    Args:
        device_name: 未登録時の登録名 (User-Agent 等から呼び出し側が推定して渡す)。
        bearer: 平文の Bearer トークン文字列。
        ip_address: 接続元 IP。
        user_agent: 接続元 User-Agent。
        db_path: データベースファイルのパス。

    Returns:
        該当 Device モデル (未登録時は None。失効済み端末はそのまま返却)。
    """
    token_hash = hashlib.sha256(bearer.encode("utf-8")).hexdigest()
    device = get_device_by_token_hash(token_hash, db_path=db_path)
    if device is None:
        try:
            register_device(device_name, token_hash, ip_address=ip_address, user_agent=user_agent, db_path=db_path)
        except Exception as e:
            logger.debug(f"デバイス台帳自動登録エラー (無視): {e}")
    else:
        # 失効済み端末の last_seen は更新しない (失効セッションの生存期間を演出しないため)
        if device.is_revoked != 1:
            try:
                touch_device_last_seen(token_hash, ip_address=ip_address, user_agent=user_agent, db_path=db_path)
                # 返却する Device は touch 後の最新状態 (ip_address / user_agent / last_seen) を反映させる
                device = get_device_by_token_hash(token_hash, db_path=db_path)
            except Exception as e:
                logger.debug(f"last_seen 更新エラー (無視): {e}")
    return device


def register_device_from_bearer(
    device_name: str,
    bearer: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    db_path: str = "neo_secretary.db"
) -> int:
    """トークン配布 (QRペアリング等) 時に、平文 Bearer を内部でハッシュ化して台帳へ登録する。

    SHA-256 ハッシュ化をデータベース層の内部手順として隠蔽する (Deep Module 原則)。
    同一トークンの再配布時は既存レコードの情報が更新される (register_device 準拠)。

    Args:
        device_name: 端末表示名。
        bearer: 平文の Bearer トークン文字列。
        ip_address: 接続元 IP。
        user_agent: 接続元 User-Agent。
        db_path: データベースファイルのパス。

    Returns:
        登録または更新されたデバイス ID。
    """
    token_hash = hashlib.sha256(bearer.encode("utf-8")).hexdigest()
    return register_device(device_name, token_hash, ip_address=ip_address, user_agent=user_agent, db_path=db_path)


def get_all_devices(db_path: str = "neo_secretary.db") -> List[Device]:
    """
    登録されているすべてのデバイス一覧を最終接続日時の新しい順に取得します。

    Args:
        db_path: データベースファイルのパス

    Returns:
        Device モデルのリスト
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, device_name, token_hash, ip_address, user_agent,
                   created_at, last_seen, is_revoked
            FROM devices
            ORDER BY last_seen DESC, id DESC
        """)
        rows = cursor.fetchall()
        return [
            Device(
                id=row[0],
                device_name=row[1],
                token_hash=row[2],
                ip_address=row[3],
                user_agent=row[4],
                created_at=row[5],
                last_seen=row[6],
                is_revoked=row[7],
            )
            for row in rows
        ]


def revoke_device(device_id: int, db_path: str = "neo_secretary.db") -> bool:
    """
    指定したデバイスを失効状態にします。

    Args:
        device_id: デバイスID
        db_path: データベースファイルのパス

    Returns:
        更新成功時は True
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE devices
            SET is_revoked = 1
            WHERE id = ?
        """, (device_id,))
        success = cursor.rowcount > 0
        if success:
            logger.warning(f"デバイスID={device_id} を失効 (Revoked) に設定しました")
        return success


def touch_device_last_seen(
    token_hash: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    db_path: str = "neo_secretary.db"
) -> bool:
    """
    通信発生時にデバイスの最終アクセス日時（およびIP/UA）を更新します。

    Args:
        token_hash: 認証トークンのSHA-256ハッシュ
        ip_address: 接続元IP（任意）
        user_agent: 接続元User-Agent（任意）
        db_path: データベースファイルのパス

    Returns:
        更新対象が存在した場合は True
    """
    now = int(datetime.now().timestamp() * 1000)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE devices
            SET last_seen = ?,
                ip_address = COALESCE(?, ip_address),
                user_agent = COALESCE(?, user_agent)
            WHERE token_hash = ?
        """, (now, ip_address, user_agent, token_hash))
        return cursor.rowcount > 0



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
