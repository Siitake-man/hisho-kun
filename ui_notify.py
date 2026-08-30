"""
ネオ秘書くん - UI通知ユーティリティ (ui_notify.py)

バックグラウンドスレッド（AIチャット / MCPサーバー / webhook / iCal同期）から
Tkinter GUI メインスレッドへ「手帳のデータが変わった」ことを安全に通知するための
薄いブリッジモジュール。

設計意図:
    - DB書き込み側は GUI の存在を知るべきではない（疎結合）。
    - GUI への実行ディスパッチは既存の gui.post_action（スレッド安全キュー）に集約。
    - GUI 未起動（MCP単体起動・テスト環境）では何もせず静かに終わる（ベストエフォート）。
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def notify_calendar_changed() -> None:
    """手帳カレンダーのデータ変更を GUI へ通知する（スレッド安全・ベストエフォート）。

    GUI インスタンスが取得できる場合のみ、メインスレッド上で
    ``gui.refresh_calendar_if_open()`` を実行するようディスパッチする。
    手帳が閉じている場合は GUI 側で何もしないため、呼び出しコストは最小。

    GUI が未起動（MCPサーバー単体起動 / テスト環境）の場合は
    ``local_sync_server`` のインポートに失敗するか ``get_gui_instance()`` が
    ``None`` を返すため、警告ログ無し（debug レベル）で静かに終了する。
    """
    gui: Optional[Any] = None
    try:
        # 遅延importで循環参照を回避（local_sync_server → db_tools → ui_notify）
        from local_sync_server import get_gui_instance

        gui = get_gui_instance()
    except Exception as e:
        logger.debug(f"GUIインスタンスの取得をスキップしました（GUI未起動）: {e}")
        return

    if gui is None:
        return

    post_action = getattr(gui, "post_action", None)
    refresh = getattr(gui, "refresh_calendar_if_open", None)
    if not callable(post_action) or not callable(refresh):
        logger.debug("GUIが通知インターフェース(post_action/refresh_calendar_if_open)を持たないためスキップしました")
        return

    try:
        post_action(refresh)
        logger.debug("手帳カレンダーの変更をGUIへ通知しました")
    except Exception as e:
        logger.warning(f"手帳カレンダーの変更通知に失敗しました: {e}")
