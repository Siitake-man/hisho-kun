#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - ルートレコード ＆ ディスパッチテーブル (server/routes.py / Phase F10).

Fat モジュール `local_sync_server.py` から、API ディスパッチテーブルおよび
エンドポイントの認証レベル定義を独立した Deep Module として切り出します。

契約:
    - RouteRecord: パス・メソッド・ハンドラ・認証レベル (loopback / bearer / public) のレコード定義
    - POST_PATH_HANDLERS: 既存テスト互換 (test_web_push_server 等) の POST ハンドラマップ
    - GET_PATH_HANDLERS: 既存テスト互換の GET ハンドラマップ
    - ACTION_HANDLERS: スマホ手帳・ウィジェット用 Desk Pet アクションマップ
    - POST_ROUTES: RouteRecord による統合 POST ルートテーブル
    - GET_ROUTES: RouteRecord による統合 GET ルートテーブル
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

import api_agent_bridge
import api_calendar
import api_devices
import api_push
import api_tasks
from agent_fsm import agent_fsm
from api_context import ApiContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RouteRecord:
    """単一の API エンドポイントルート定義レコード."""

    path: str
    method: str  # "GET" | "POST"
    handler: Callable[..., Any]
    auth_level: str = "bearer"  # "loopback" | "bearer" | "public"
    requires_auth: bool = True
    loopback_error_msg: str = "Access is restricted to localhost."



# =============================================================================
# 📋 Desk Pet アクションディスパッチテーブル (/api/action 用)
# =============================================================================
ACTION_HANDLERS_TASKS: Dict[str, Callable] = {
    "complete_task": api_tasks.action_complete_task,
    "reopen_task": api_tasks.action_reopen_task,
    "toggle_habit": api_tasks.action_toggle_habit,
    "add_habit": api_tasks.action_add_habit,
    "quick_add_task": api_tasks.action_quick_add_task,
    "update_task": api_tasks.action_update_task,
    "delete_task": api_tasks.action_delete_task,
    "list_task_lists": api_tasks.action_list_task_lists,
    "get_tasks_view": api_tasks.action_get_tasks_view,
}

ACTION_HANDLERS_DEVICE: Dict[str, Callable] = {
    "start_pomodoro": api_agent_bridge.action_start_pomodoro,
    "stop_pomodoro": api_agent_bridge.action_stop_pomodoro,
    "show_pc_pet": api_agent_bridge.action_show_pc_pet,
    "switch_character": api_agent_bridge.action_switch_character,
    "toggle_suggest_source": api_agent_bridge.action_toggle_suggest_source,
    "set_news_keywords": api_agent_bridge.action_set_news_keywords,
    "pet_reaction": api_agent_bridge.action_pet_reaction,
    "ping_test": api_agent_bridge.action_ping_test,
    "voice_command": api_agent_bridge.action_voice_command,
    "easter_egg_trigger": api_agent_bridge.action_easter_egg_trigger,
    "trigger_briefing": api_agent_bridge.action_trigger_briefing,
    "set_weather_location": api_agent_bridge.action_set_weather_location,
    "record_minigame_score": api_agent_bridge.action_record_minigame_score,
    "set_language": api_agent_bridge.action_set_language,
}

# 全アクションの統合ディスパッチテーブル
ACTION_HANDLERS: Dict[str, Callable] = {**ACTION_HANDLERS_TASKS, **ACTION_HANDLERS_DEVICE}


# =============================================================================
# 📬 既存互換ハンドラマップ (test_web_push_server 等の __module__ 契約保全)
# =============================================================================
POST_PATH_HANDLERS: Dict[str, Callable] = {
    "/api/agent/ask": api_agent_bridge.handle_agent_ask,
    "/api/agent/ask_input": api_agent_bridge.handle_agent_ask_input,
    "/api/agent/respond": api_agent_bridge.handle_agent_respond,
    "/api/agent/dismiss_completed": api_agent_bridge.handle_agent_dismiss_completed,
    "/api/agent/cancel_pending": api_agent_bridge.handle_agent_cancel_pending,
    "/api/agent/notify": api_agent_bridge.handle_agent_notify,
    "/api/test_buzz": api_agent_bridge.handle_test_buzz,
    "/api/webhook/calendar": api_calendar.handle_webhook_calendar,
    "/api/webhook/task": api_calendar.handle_webhook_task,
    "/api/push/subscribe": api_push.handle_push_subscribe,
    "/api/push/unsubscribe": api_push.handle_push_unsubscribe,
}

GET_PATH_HANDLERS: Dict[str, Callable] = {
    "/api/devices": api_devices.handle_get_devices,
    "/api/push/vapid_key": api_push.handle_get_push_vapid_key,
}


def handle_post_agent_activity(ctx: ApiContext) -> None:
    """エージェント稼働状態更新ハンドラ (POST /api/agent/activity)."""
    try:
        body = ctx.body
        data = json.loads(body.decode("utf-8")) if body else {}
        state = data.get("state", "idle")
        agent_name = data.get("agent_name", "AI Agent")
        detail = data.get("detail", "")
        ttl_seconds = data.get("ttl_seconds")
        if ttl_seconds is not None:
            ttl_seconds = float(ttl_seconds)

        updated = agent_fsm.set_state(state, agent_name=agent_name, detail=detail, ttl_seconds=ttl_seconds)
        ctx.handler.send_response(200)
        ctx.handler.send_header("Content-Type", "application/json; charset=utf-8")
        if hasattr(ctx.handler, "_set_cors_headers"):
            ctx.handler._set_cors_headers()
        ctx.handler.end_headers()
        ctx.handler.wfile.write(json.dumps({"status": "ok", "activity": updated}, ensure_ascii=False).encode("utf-8"))
    except Exception as e:
        logger.error("エージェント状態更新エラー: %s", e)
        ctx.handler.send_response(500)
        ctx.handler.send_header("Content-Type", "application/json; charset=utf-8")
        if hasattr(ctx.handler, "_set_cors_headers"):
            ctx.handler._set_cors_headers()
        ctx.handler.end_headers()
        ctx.handler.wfile.write(json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False).encode("utf-8"))


# =============================================================================
# 🛡️ 統合ルートテーブル (Route Record)
# =============================================================================
POST_ROUTES: Dict[str, RouteRecord] = {
    # 1. エージェント発信系 (同一PC・loopback 限定: RCE 遮断チェーン)
    "/api/agent/ask": RouteRecord(
        "/api/agent/ask", "POST", api_agent_bridge.handle_agent_ask,
        auth_level="loopback", loopback_error_msg="Agent APIs are restricted to localhost connections."
    ),
    "/api/agent/ask_input": RouteRecord(
        "/api/agent/ask_input", "POST", api_agent_bridge.handle_agent_ask_input,
        auth_level="loopback", loopback_error_msg="Agent APIs are restricted to localhost connections."
    ),
    "/api/agent/notify": RouteRecord(
        "/api/agent/notify", "POST", api_agent_bridge.handle_agent_notify,
        auth_level="loopback", loopback_error_msg="Agent APIs are restricted to localhost connections."
    ),
    "/api/agent/cancel_pending": RouteRecord(
        "/api/agent/cancel_pending", "POST", api_agent_bridge.handle_agent_cancel_pending,
        auth_level="loopback", loopback_error_msg="Agent APIs are restricted to localhost connections."
    ),
    # 2. デバイス管理系 (同一PC・loopback 限定)
    "/api/devices/revoke": RouteRecord(
        "/api/devices/revoke", "POST", api_devices.handle_post_devices_revoke,
        auth_level="loopback", loopback_error_msg="Device revoke is restricted to localhost."
    ),
    "/api/devices/restore": RouteRecord(
        "/api/devices/restore", "POST", api_devices.handle_post_devices_restore,
        auth_level="loopback", loopback_error_msg="Device restore is restricted to localhost."
    ),
    "/api/agent/activity": RouteRecord(
        "/api/agent/activity", "POST", handle_post_agent_activity,
        auth_level="loopback", loopback_error_msg="Agent activity API is restricted to localhost."
    ),
    # 3. エージェント応答・通知系 (Bearer 認証)
    "/api/agent/respond": RouteRecord("/api/agent/respond", "POST", api_agent_bridge.handle_agent_respond, auth_level="bearer"),
    "/api/agent/dismiss_completed": RouteRecord("/api/agent/dismiss_completed", "POST", api_agent_bridge.handle_agent_dismiss_completed, auth_level="bearer"),
    "/api/test_buzz": RouteRecord("/api/test_buzz", "POST", api_agent_bridge.handle_test_buzz, auth_level="bearer"),
    "/api/webhook/calendar": RouteRecord("/api/webhook/calendar", "POST", api_calendar.handle_webhook_calendar, auth_level="bearer"),
    "/api/webhook/task": RouteRecord("/api/webhook/task", "POST", api_calendar.handle_webhook_task, auth_level="bearer"),
    "/api/push/subscribe": RouteRecord("/api/push/subscribe", "POST", api_push.handle_push_subscribe, auth_level="bearer"),
    "/api/push/unsubscribe": RouteRecord("/api/push/unsubscribe", "POST", api_push.handle_push_unsubscribe, auth_level="bearer"),
}

GET_ROUTES: Dict[str, RouteRecord] = {
    # デバイス台帳一覧 (同一PC・loopback 限定)
    "/api/devices": RouteRecord(
        "/api/devices", "GET", api_devices.handle_get_devices,
        auth_level="loopback", loopback_error_msg="Device listing is restricted to localhost."
    ),
    # VAPID 公開鍵取得 (Bearer 認証)
    "/api/push/vapid_key": RouteRecord("/api/push/vapid_key", "GET", api_push.handle_get_push_vapid_key, auth_level="bearer"),
}

