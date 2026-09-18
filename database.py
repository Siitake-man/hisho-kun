"""
Neo-Secretary データベースモジュール (Facade)

本モジュールは後方互換性のために維持されている薄型ファサード (Facade) です。
実際の実装は `storage` パッケージ配下のドメイン別リポジトリに分割・整理されています。

- `storage.models`: Pydantic データモデル定義
- `storage.connection`: SQLite 接続ライフサイクル管理・自動バックアップ
- `storage.calendar_repo`: 予定・カテゴリ・外部カレンダーCRUD
- `storage.task_repo`: タスク・リスト・リマインダーCRUD
- `storage.habit_repo`: 習慣トラッカー・ログ・ヒートマップCRUD
- `storage.sticky_repo`: 付箋メモCRUD
- `storage.insight_repo`: ボスの知見・示唆CRUD
- `storage.minigame_repo`: ミニゲームスコアCRUD
- `storage.device_repo`: 端末ペアリング・セッション管理CRUD
- `storage.audit_repo`: 監査ログ記録・取得
"""

import logging
from datetime import datetime

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# ストレージ層 (storage パッケージ) からの全シンボル再エクスポート
# =============================================================================
from storage import (
    # データモデル
    Category,
    Event,
    CalendarSource,
    StickyNote,
    UserInsight,
    Task,
    TaskList,
    Habit,
    HabitLog,
    HabitWithStatus,
    HabitHeatmapPoint,
    MinigameScore,
    Device,
    AuditLogEntry,
    # 接続・初期化・バックアップ
    get_db_connection,
    init_db,
    backup_database,
    auto_backup,
    # 監査ログ
    record_audit_log,
    get_audit_logs,
    # 端末認証
    register_device,
    get_device_by_token_hash,
    sync_device_session,
    register_device_from_bearer,
    get_all_devices,
    revoke_device,
    revoke_all_devices,
    touch_device_last_seen,
    restore_device,
    issue_device_token,
    verify_device_token,
    # カレンダー・カテゴリ
    create_category,
    get_category,
    get_all_categories,
    create_event,
    get_event,
    get_upcoming_events,
    get_events_between,
    create_calendar_source,
    get_all_calendar_sources,
    get_calendar_source,
    update_calendar_source,
    set_calendar_source_enabled,
    set_calendar_source_last_sync,
    delete_calendar_source,
    # 付箋
    create_sticky_note,
    get_all_sticky_notes,
    update_sticky_note,
    delete_sticky_note,
    # 知見
    create_user_insight,
    add_user_insight,
    get_user_insights,
    delete_user_insight,
    # 習慣
    create_habit,
    delete_habit,
    toggle_habit_log,
    get_habits_with_status,
    get_habit_heatmap_data,
    # ミニゲーム
    record_minigame_score,
    get_high_score,
    get_recent_minigame_scores,
    # タスク
    create_task,
    get_tasks,
    get_subtasks,
    add_subtask,
    complete_task,
    get_tasks_completed_today,
    reopen_task,
    update_task,
    delete_task,
    is_reminder_sent,
    mark_reminder_sent,
    get_task_lists,
    create_task_list,
    move_task_list,
    delete_task_list,
    rename_task_list,
    update_task_tags,
)

__all__ = [
    # データモデル
    "Category",
    "Event",
    "CalendarSource",
    "StickyNote",
    "UserInsight",
    "Task",
    "TaskList",
    "Habit",
    "HabitLog",
    "HabitWithStatus",
    "HabitHeatmapPoint",
    "MinigameScore",
    "Device",
    "AuditLogEntry",
    # 接続・初期化・バックアップ
    "get_db_connection",
    "init_db",
    "backup_database",
    "auto_backup",
    # 監査ログ
    "record_audit_log",
    "get_audit_logs",
    # 端末認証
    "register_device",
    "get_device_by_token_hash",
    "sync_device_session",
    "register_device_from_bearer",
    "get_all_devices",
    "revoke_device",
    "revoke_all_devices",
    "touch_device_last_seen",
    "restore_device",
    "issue_device_token",
    "verify_device_token",
    # カレンダー・カテゴリ
    "create_category",
    "get_category",
    "get_all_categories",
    "create_event",
    "get_event",
    "get_upcoming_events",
    "get_events_between",
    "create_calendar_source",
    "get_all_calendar_sources",
    "get_calendar_source",
    "update_calendar_source",
    "set_calendar_source_enabled",
    "set_calendar_source_last_sync",
    "delete_calendar_source",
    # 付箋
    "create_sticky_note",
    "get_all_sticky_notes",
    "update_sticky_note",
    "delete_sticky_note",
    # 知見
    "create_user_insight",
    "add_user_insight",
    "get_user_insights",
    "delete_user_insight",
    # 習慣
    "create_habit",
    "delete_habit",
    "toggle_habit_log",
    "get_habits_with_status",
    "get_habit_heatmap_data",
    # ミニゲーム
    "record_minigame_score",
    "get_high_score",
    "get_recent_minigame_scores",
    # タスク
    "create_task",
    "get_tasks",
    "get_subtasks",
    "add_subtask",
    "complete_task",
    "get_tasks_completed_today",
    "reopen_task",
    "update_task",
    "delete_task",
    "is_reminder_sent",
    "mark_reminder_sent",
    "get_task_lists",
    "create_task_list",
    "move_task_list",
    "delete_task_list",
    "rename_task_list",
    "update_task_tags",
]

# =============================================================================
# スクリプト直接実行時の動作確認用
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
