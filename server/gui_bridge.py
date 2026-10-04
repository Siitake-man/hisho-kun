#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - GUI 連携ブリッジ (server/gui_bridge.py / S6 Seam).

Fat モジュール `local_sync_server.py` から、GUI インスタンスの保持および
Human-in-the-Loop 端末承認ダイアログコールバック登録機構を独立した Deep Module として切り出します。

収容責務:
    - set_gui_instance(gui) -> None
    - get_gui_instance() -> Optional[Any]
    - 端末承認ダイアログコールバック (_approval_cb) の動的バインド/アンバインド
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from server.sync_token_manager import get_sync_token_manager

logger = logging.getLogger(__name__)

_global_gui_instance: Optional[Any] = None


def set_gui_instance(gui: Optional[Any]) -> None:
    """GUIインスタンスを保持し、Human-in-the-Loop 端末承認ダイアログコールバックを設定する。

    Args:
        gui: Tkinter / CustomTkinter の メイン GUI インスタンス（解除時は None）。
    """
    global _global_gui_instance
    _global_gui_instance = gui
    if gui is not None:
        def _approval_cb(device_name: str, client_ip: str) -> bool:
            try:
                from ui.device_approval_dialog import ask_device_approval_gui
                return ask_device_approval_gui(gui, device_name, client_ip, timeout_sec=30)
            except Exception as err:
                logger.error("端末承認ダイアログ呼び出しエラー: %s", err)
                return False

        get_sync_token_manager().set_device_approval_callback(_approval_cb)
        logger.info("🔐 [SyncAuth] Human-in-the-Loop 端末接続承認コールバックを登録しました")
    else:
        get_sync_token_manager().set_device_approval_callback(None)


def get_gui_instance() -> Optional[Any]:
    """登録されているGUIインスタンスを取得する。

    Returns:
        Optional[Any]: 保持されている GUI インスタンス（未登録時は None）。
    """
    return _global_gui_instance
