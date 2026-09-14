"""
Neo-Secretary ストレージ層 - コネクションライフサイクル ＆ 初期化 (storage/connection.py)

SQLiteデータベース接続の一元管理（WALモード、busy_timeout、自動コミット・ロールバック）
および各テーブル・インデックスの初期化・スキーママイグレーションを提供します。
"""

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

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
# データベース初期化 ＆ スキーママイグレーション
# =============================================================================

def init_db(db_path: str = "neo_secretary.db") -> None:
    """
    SQLiteデータベースを初期化し、全テーブル・インデックスを作成・検証します。
    既存データベースに対するカラム追加マイグレーションも冪等に実行します。
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

        # task_listsテーブル (タスクリスト・フォルダ分類: TickTick拡張)
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
# データベース自動バックアップ＆整合性保護 (Data Persistence & Safety)
# =============================================================================

def backup_database(
    db_path: str = "neo_secretary.db",
    backup_dir: str = "backups",
    max_generations: int = 7
) -> Optional[str]:
    """SQLiteのOnline Backup API (`conn.backup()`) を使用して、
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

