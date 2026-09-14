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
    # Connection
    "get_db_connection",
    "init_db",
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
]
