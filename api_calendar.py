#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - 外部SaaS Webhook APIモジュール (api_calendar.py)

外部SaaS・マルチ中継サービス (Zapier / IFTTT / Make 等) からの予定・TODO
登録 Webhook を担当するモジュール。local_sync_server.py から P2③ 分割
リファクタで抽出した。

契約:
- 認証は X-Webhook-Secret ヘッダー または Bearer トークン
  (_check_webhook_auth: Secret優先 → SyncToken → ループバック許可)。
- GUI 操作は必ず gui.post_action 経由 (メインスレッドへディスパッチ)。
"""

import json
import logging

from api_context import ApiContext

logger = logging.getLogger(__name__)


def handle_webhook_calendar(ctx: ApiContext) -> None:
    """外部SaaSからの予定登録 Webhook (POST /api/webhook/calendar) を処理する。

    Args:
        ctx: リクエストコンテキスト。
    """
    if not ctx.handler._check_webhook_auth():
        return
    ctx.begin_json_response()
    try:
        data = json.loads(ctx.body.decode("utf-8")) if ctx.body else {}
        import webhook_tools
        result = webhook_tools.process_incoming_calendar_webhook(data)

        # 手帳が開いていれば再描画
        from local_sync_server import get_gui_instance
        gui = get_gui_instance()
        if gui:
            if hasattr(gui, 'refresh_calendar_if_open'):
                gui.post_action(gui.refresh_calendar_if_open)
            title = result.get("title", "新しい予定")
            gui.post_action(gui.update_message, f"📅 外部SaaSから予定を受信しました:\n{title}")

        ctx.write_json(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Webhook カレンダー登録エラー: {e}")
        ctx.send_error_json(str(e))


def handle_webhook_task(ctx: ApiContext) -> None:
    """外部SaaSからのTODO登録 Webhook (POST /api/webhook/task) を処理する。

    Args:
        ctx: リクエストコンテキスト。
    """
    if not ctx.handler._check_webhook_auth():
        return
    ctx.begin_json_response()
    try:
        data = json.loads(ctx.body.decode("utf-8")) if ctx.body else {}
        import webhook_tools
        result = webhook_tools.process_incoming_task_webhook(data)

        from local_sync_server import get_gui_instance
        gui = get_gui_instance()
        if gui:
            title = result.get("title", "新しいタスク")
            gui.post_action(gui.update_message, f"📝 外部SaaSからTODOを受信しました:\n{title}")

        ctx.write_json(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Webhook タスク登録エラー: {e}")
        ctx.send_error_json(str(e))
