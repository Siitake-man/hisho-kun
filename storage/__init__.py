"""
Neo-Secretary ストレージ層 (storage パッケージ)

データモデル、接続ライフサイクル、および各ドメインのRepositoryを提供します。
"""

from storage.models import (
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
)
from storage.connection import (
    get_db_connection,
    init_db,
    backup_database,
    auto_backup,
)
from storage.audit_repo import (
    record_audit_log,
    get_audit_logs,
)
from storage.device_repo import (
    register_device,
    get_device_by_token_hash,
    sync_device_session,
    register_device_from_bearer,
    get_all_devices,
    revoke_device,
    touch_device_last_seen,
)
from storage.calendar_repo import (
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
)
from storage.sticky_repo import (
    create_sticky_note,
    get_all_sticky_notes,
    update_sticky_note,
    delete_sticky_note,
)
from storage.insight_repo import (
    create_user_insight,
    add_user_insight,
    get_user_insights,
    delete_user_insight,
)
from storage.habit_repo import (
    create_habit,
    delete_habit,
    toggle_habit_log,
    get_habits_with_status,
    get_habit_heatmap_data,
)
from storage.minigame_repo import (
    record_minigame_score,
    get_high_score,
    get_recent_minigame_scores,
)
from storage.task_repo import (
    create_task,
    get_tasks,
    get_subtasks,
    add_subtask,
    complete_task,
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
    # Models
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
    # Connection & Backup
    "get_db_connection",
    "init_db",
    "backup_database",
    "auto_backup",
    # Audit Repo
    "record_audit_log",
    "get_audit_logs",
    # Device Repo
    "register_device",
    "get_device_by_token_hash",
    "sync_device_session",
    "register_device_from_bearer",
    "get_all_devices",
    "revoke_device",
    "touch_device_last_seen",
    # Calendar Repo
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
    # Sticky Note Repo
    "create_sticky_note",
    "get_all_sticky_notes",
    "update_sticky_note",
    "delete_sticky_note",
    # Insight Repo
    "create_user_insight",
    "add_user_insight",
    "get_user_insights",
    "delete_user_insight",
    # Habit Repo
    "create_habit",
    "delete_habit",
    "toggle_habit_log",
    "get_habits_with_status",
    "get_habit_heatmap_data",
    # Minigame Repo
    "record_minigame_score",
    "get_high_score",
    "get_recent_minigame_scores",
    # Task Repo
    "create_task",
    "get_tasks",
    "get_subtasks",
    "add_subtask",
    "complete_task",
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
