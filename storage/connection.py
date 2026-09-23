"""
Neo-Secretary ストレージ層 - コネクションライフサイクル ＆ 初期化 (storage/connection.py)

SQLiteデータベース接続の一元管理（WALモード、busy_timeout、自動コミット・ロールバック）
および各テーブル・インデックスの初期化・スキーママイグレーションを提供します。
"""

import logging
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

import app_paths

logger = logging.getLogger(__name__)

# init_db の実行時間がこの閾値を超えたら警告する (P2: 起動時ブロックの可視化・2026-09-16)
DB_INIT_SLOW_THRESHOLD_MS = 2000.0

# データ境界 (ADR-2 / P0-4): 既定の相対名はデータルート (%LOCALAPPDATA% 等) へ解決する
DEFAULT_DB_FILENAME: str = app_paths.DB_FILENAME
DEFAULT_BACKUPS_DIR_NAME: str = app_paths.BACKUPS_DIR_NAME

# 旧配置フォールバック（移行未完了）の ERROR ログを初回のみに抑えるフラグ
_LEGACY_FALLBACK_WARNED: bool = False


# =============================================================================
# データ境界の単一チョークポイント (ADR-2 / P0-4 2026-09-23)
# =============================================================================

def _is_default_relative_reference(path: Path, default_filename: str) -> bool:
    """パスが「既定名のカレントディレクトリ直下参照」かどうかを判定する。

    大文字小文字違い（``NEO_SECRETARY.DB``）・冗長な相対表記
    （``sub/../neo_secretary.db``）・``./neo_secretary.db`` を同一視する。
    明示的なサブディレクトリ・絶対パス・別名は False（呼び出し元の指定を尊重）。

    Args:
        path: 判定対象パス。
        default_filename: 既定ファイル名（例: ``neo_secretary.db``）。

    Returns:
        bool: 既定名の CWD 直下参照と判定した場合 True。
    """
    if path.name.casefold() != default_filename.casefold():
        return False
    try:
        resolved = path.resolve()
    except OSError:
        return False
    return resolved.parent == Path.cwd().resolve()


def resolve_db_path(db_path: str = DEFAULT_DB_FILENAME) -> str:
    """DB パスの既定相対名のみを非同期データルートへ解決する (単一チョークポイント)。

    解決規則:
        - ディレクトリ部を持つパス (``tmp/x.db`` / 絶対パス) は**一切変更しない**
          (テスト・運用の明示指定を尊重する)。
        - 既定名 ``neo_secretary.db`` (ベア相対名・大文字小文字違い・冗長表記) は
          ``app_paths.get_db_path()`` へ解決する。
        - ただし移行先 DB が未作成で旧配置 DB が存在する間は旧パスを返す
          (**プロセス間の DB 分裂防止**。アプリ起動時の ``migrate_legacy_data()``
          完了後は自動的に新パスへ切り替わる)。この間は ADR-2 未達である旨を
          初回のみ ERROR ログで可視化する。

    Args:
        db_path: 呼び出し元が指定した DB パス (既定は ``neo_secretary.db``)。

    Returns:
        str: 解決後の DB パス文字列。
    """
    path = Path(db_path)
    if not _is_default_relative_reference(path, DEFAULT_DB_FILENAME):
        return str(path)

    target = app_paths.get_db_path()
    if target.exists():
        return str(target)

    # 旧配置フォールバック（未移行時の暫定運用）は、データルートが明示上書きされて
    # いない場合のみ有効。上書き時は常にデータルートを権威とする（テスト隔離・
    # 運用切替の決定論を守る / 2026-09-23: 本番DBへのテスト書込み障害の再発防止）。
    if not app_paths.is_data_root_overridden():
        legacy = app_paths.get_app_root() / DEFAULT_DB_FILENAME
        if legacy.exists():
            global _LEGACY_FALLBACK_WARNED
            if not _LEGACY_FALLBACK_WARNED:
                _LEGACY_FALLBACK_WARNED = True
                logger.error(
                    "⚠️ データ境界の移行が未完了のため旧配置 DB で運用中です "
                    f"(ADR-2: クラウド同期領域に機密が残存): {legacy}"
                )
            return str(legacy)
    return str(target)


def resolve_backups_dir(backup_dir: str = DEFAULT_BACKUPS_DIR_NAME) -> str:
    """自動バックアップ先の既定相対名 ``backups`` をデータルート配下へ解決する。

    明示指定 (ディレクトリ部を持つパス) は変更しない。

    Args:
        backup_dir: 呼び出し元が指定したバックアップ先 (既定は ``backups``)。

    Returns:
        str: 解決後のバックアップ先パス文字列。
    """
    path = Path(backup_dir)
    if not _is_default_relative_reference(path, DEFAULT_BACKUPS_DIR_NAME):
        return str(path)
    return str(app_paths.get_backups_dir())


# =============================================================================
# データベース接続コンテキストマネージャ (Connection Lifecycle Management)
# =============================================================================

@contextmanager
def get_db_connection(db_path: str = DEFAULT_DB_FILENAME) -> Generator[sqlite3.Connection, None, None]:
    """
    SQLiteデータベース接続を一元管理するコンテキストマネージャ。
    
    WAL (Write-Ahead Logging) モードを有効化し、GUIとHTTPサーバー間の
    同時読み書きによるロック競合（database is locked）を防止します。
    ブロックを正常に抜けた場合は自動的に commit() を行い、
    例外が発生した場合は自動的に rollback() を実行して安全に close() します。

    Notes:
        ``db_path`` は :func:`resolve_db_path` を通すため、既定の相対名を渡した
        呼び出し元 (100超) は無改修で非同期データルート (ADR-2) へ到達する。

    Args:
        db_path: データベースファイルのパス
        
    Yields:
        sqlite3.Connection: データベース接続オブジェクト
    """
    resolved_path = resolve_db_path(db_path)
    conn = sqlite3.connect(resolved_path, timeout=30.0)
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

def init_db(db_path: str = DEFAULT_DB_FILENAME) -> None:
    """
    SQLiteデータベースを初期化し、全テーブル・インデックスを作成・検証します。
    既存データベースに対するカラム追加マイグレーションも冪等に実行します。

    Notes:
        本関数は起動時にメインスレッドで実行される。`CREATE INDEX IF NOT EXISTS` は
        既存インデックスでは即座に no-op だが、**初回のみ**インデックス構築のコスト
        （旧DB＋大量行では数十秒）が発生し得る。P2 (2026-09-16 独立査読) の指摘を受け、
        実行時間を実測して閾値超過時に警告する（バックグラウンド化は起動直後の
        書き込みロック競合リスクが高いため、まず可視化で判断材料を残す方針）。
    """
    db_path = resolve_db_path(db_path)
    started_at = time.perf_counter()
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

        # P1-2 (省電力スプリント 2026-09-16): 予定の期間重複判定 (start_time/end_time) を
        # インデックススキャン O(log N) へ高速化し、手帳画面表示・スマホPWAの
        # 定期ポーリング時のフルスキャン O(N) を排除する。
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_start_end "
            "ON events (start_time, end_time)"
        )
        
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

        # user_insightsテーブル (知識の宝庫 長期知見記憶)
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

        # P1-2 (省電力スプリント 2026-09-16): TODOの「ステータス絞り込み＋期日比較」
        # (例: /api/status の未完了タスク抽出、手帳の期日アラート) を
        # インデックススキャン O(log N) へ高速化し、2秒周期ポーリング時の
        # フルスキャン O(N) を排除する。
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_status_due "
            "ON tasks (status, due_date)"
        )

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
                is_revoked INTEGER NOT NULL DEFAULT 0,
                device_uuid TEXT
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_devices_token_hash "
            "ON devices (token_hash)"
        )
        # devices.device_uuid マイグレーション (ID 50: 端末自己生成UUIDによる識別恒久化)
        cursor.execute("PRAGMA table_info(devices)")
        device_columns = {row[1] for row in cursor.fetchall()}
        if "device_uuid" not in device_columns:
            cursor.execute("ALTER TABLE devices ADD COLUMN device_uuid TEXT")
            logger.info("devices.device_uuid カラムを追加しました (ID 50)")
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_devices_device_uuid "
            "ON devices (device_uuid)"
        )
        logger.info("devicesテーブルを確認/作成しました")

        # Web Push 購読台帳 (Service Worker Push Subscription: endpoint UNIQUE)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_hash TEXT NOT NULL,
                endpoint TEXT NOT NULL UNIQUE,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_push_subscriptions_token_hash "
            "ON push_subscriptions (token_hash)"
        )
        logger.info("push_subscriptionsテーブルを確認/作成しました")

        # VAPID 鍵ペア (単一行運用・Web Push 送信署名用)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vapid_keys (
                id INTEGER PRIMARY KEY,
                private_key_pem TEXT NOT NULL,
                public_key TEXT NOT NULL,
                subject TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)
        logger.info("vapid_keysテーブルを確認/作成しました")

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
        
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    logger.info(f"データベース初期化完了: {db_path} ({elapsed_ms:.0f}ms)")
    if elapsed_ms > DB_INIT_SLOW_THRESHOLD_MS:
        logger.warning(
            "⚠️ データベース初期化に %.1f 秒かかりました（初回起動時のインデックス構築等）。"
            "2回目以降の起動では短縮されるはずです。",
            elapsed_ms / 1000.0,
        )


# =============================================================================
# データベース自動バックアップ＆整合性保護 (Data Persistence & Safety)
# =============================================================================

def backup_database(
    db_path: str = DEFAULT_DB_FILENAME,
    backup_dir: str = DEFAULT_BACKUPS_DIR_NAME,
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
    db_path = resolve_db_path(db_path)
    backup_dir = resolve_backups_dir(backup_dir)
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

