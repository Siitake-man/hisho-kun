"""
ネオ秘書くん - UIパッケージ (ui/)
各UIコンポーネントを独立したDeep Moduleとして提供します。
"""

try:
    from .qr_dialog import QRCodeConnectionDialog
    from .settings_window import SettingsWindow, AddMCPServerDialog
    from .calendar_window import CalendarWindow
    from .sticky_note import DraggableStickyNote
    from .db_viewer import DatabaseViewerWindow

    __all__ = [
        "QRCodeConnectionDialog",
        "SettingsWindow",
        "AddMCPServerDialog",
        "CalendarWindow",
        "DraggableStickyNote",
        "DatabaseViewerWindow"
    ]
except (ImportError, ModuleNotFoundError):
    # ヘッドレス/CLI環境や customtkinter 未インストールの軽量環境向けフォールバック
    __all__ = []
