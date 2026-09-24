#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - 手帳系アクションAPIモジュール (api_tasks.py)

POST /api/action のうち、タスク・習慣・タスクリストなど「手帳」ドメインの
アクションを担当するモジュール。local_sync_server.py から P2③ 分割リファクタ
で抽出した。振る舞いは characterization テスト
(tests/test_action_dispatch_characterization.py) で固定済みのため、
ロジックは抽出前と1行も変えずに移動している。

契約:
- 各ハンドラは ``handler(ctx: ApiContext) -> bool`` 署名を持つ。
- レスポンスを書き込んだら True を返す。ガード条件 (task_id 欠落等) を満たさず
  旧仕様どおり無応答となる場合は False を返す (呼び出し元のディスパッチ処理で
  unknown action エラー応答に変換されるのは「未知のアクション名」のみ)。
- GUI 操作は必ず gui.post_action 経由 (メインスレッドへディスパッチ)。

2026-09-03 (P2① 第三段): 受信ボディのパースを sync_dtos.parse_request による
リクエストDTO型付けへ移行 (Primitive Obsession 解消)。壊れたJSON・契約違反は
"invalid request body" / パラメータ欠落は "missing parameter: <param>" の
明示エラーJSONで応答する。
"""

import base64
import json
import logging
from typing import Any, Dict

import database
from api_context import ApiContext
from sync_dtos import (
    AddHabitRequestDTO,
    HabitActionRequestDTO,
    QuickAddRequestDTO,
    TaskActionRequestDTO,
    UpdateTaskRequestDTO,
    parse_request,
    validate_tasks_view_response,
)

logger = logging.getLogger(__name__)


def _respond_invalid_body(ctx: ApiContext, action: str) -> bool:
    """リクエストボディが JSON / DTO として解釈できない場合の明示エラー応答ヘルパー。

    Fowler Duplicated Code 解消 (Sprint A 第3弾)。
    """
    logger.warning(f"📱 {action}: JSONとして解釈できないリクエストを受信しました")
    ctx.write_json({"status": "error", "message": "invalid request body"})
    return True


def _respond_missing_param(ctx: ApiContext, action: str, param_name: str) -> bool:
    """必須パラメータが欠落または空欄の場合の明示エラー応答ヘルパー。

    Fowler Duplicated Code 解消 (Sprint A 第3弾)。
    """
    logger.warning(f"📱 {action}: {param_name} が欠落したリクエストを受信しました")
    ctx.write_json({"status": "error", "message": f"missing parameter: {param_name}"})
    return True


def action_complete_task(ctx: ApiContext) -> bool:
    """スマホ側からのタスク完了を受け付ける。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True (task_id 欠落時は明示エラー)。
    """
    req = parse_request(ctx.body, TaskActionRequestDTO)
    if req is None:
        return _respond_invalid_body(ctx, "complete_task")
    if not req.task_id:
        return _respond_missing_param(ctx, "complete_task", "task_id")
    database.complete_task(req.task_id)
    logger.info(f"📱 スマホ側からタスク完了を受信: TaskID={req.task_id}")
    ctx.write_json({"status": "success", "task_id": req.task_id})
    return True


def action_reopen_task(ctx: ApiContext) -> bool:
    """誤タップ復活: 完了済みタスクを未完了へ戻す (繰り返し次回分も巻き戻し)。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True (task_id 欠落時は明示エラー)。
    """
    req = parse_request(ctx.body, TaskActionRequestDTO)
    if req is None:
        return _respond_invalid_body(ctx, "reopen_task")
    if not req.task_id:
        return _respond_missing_param(ctx, "reopen_task", "task_id")
    success = database.reopen_task(req.task_id)
    logger.info(f"📱 スマホ側からタスク完了取り消しを受信: TaskID={req.task_id}, success={success}")
    ctx.write_json({"status": "success" if success else "error", "task_id": req.task_id})
    return True


def action_toggle_habit(ctx: ApiContext) -> bool:
    """スマホ側からの習慣達成トグルを受け付ける (達成時は親愛度XP +10)。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True (habit_id 欠落時は明示エラー)。
    """
    req = parse_request(ctx.body, HabitActionRequestDTO)
    if req is None:
        return _respond_invalid_body(ctx, "toggle_habit")
    if not req.habit_id:
        return _respond_missing_param(ctx, "toggle_habit", "habit_id")
    is_done = database.toggle_habit_log(req.habit_id)
    from local_sync_server import invalidate_habit_cache
    invalidate_habit_cache()
    # 親愛度XP加算 (+10 XP)
    if is_done:
        from character_manager import get_character_manager
        get_character_manager().add_bond_xp(10)
        from local_sync_server import get_gui_instance
        gui = get_gui_instance()
        if gui and hasattr(gui, 'animator'):
            gui.post_action(gui.animator.trigger_reaction, "task_complete")
    logger.info(f"📱 スマホ側から習慣トグルを受信: HabitID={req.habit_id}, IsDone={is_done}")
    ctx.write_json({"status": "success", "habit_id": req.habit_id, "is_done": is_done})
    return True


def action_add_habit(ctx: ApiContext) -> bool:
    """スマホ側からの習慣新規作成を受け付ける。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True (title 空欄時は明示エラー)。
    """
    req = parse_request(ctx.body, AddHabitRequestDTO)
    if req is None:
        return _respond_invalid_body(ctx, "add_habit")
    title = (req.title or "").strip()
    emoji = req.emoji or "🌱"
    if not title:
        return _respond_missing_param(ctx, "add_habit", "title")
    from database import Habit
    h_id = database.create_habit(Habit(title=title, emoji=emoji))
    from local_sync_server import invalidate_habit_cache
    invalidate_habit_cache()
    logger.info(f"📱 スマホ側から習慣作成を受信: ID={h_id}, Title={title}")
    ctx.write_json({"status": "success", "habit_id": h_id})
    return True


def action_quick_add_task(ctx: ApiContext) -> bool:
    """クイック追加バー用 (TickTick拡張): 自然言語1行から期限/タグ/優先度を解析する。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True (text 欠落時は明示エラー)。
    """
    req = parse_request(ctx.body, QuickAddRequestDTO)
    if req is None:
        return _respond_invalid_body(ctx, "quick_add_task")
    quick_text = (req.text or "").strip()
    if not quick_text:
        return _respond_missing_param(ctx, "quick_add_task", "text")
    from task_parser import parse_input, tags_to_db_string
    parsed = parse_input(quick_text)
    if parsed.title:
        task_id = database.create_task(database.Task(
            title=parsed.title,
            description="",
            due_date=parsed.due_date,
            priority=parsed.priority,
            status="todo",
            tags=tags_to_db_string(parsed.tags),
            importance_flag=parsed.importance,
            urgency_flag=parsed.urgency,
            recurrence=parsed.recurrence,
        ))
        logger.info(f"📱 スマホ側からクイック追加を受信: ID={task_id}, Title={parsed.title}")
        ctx.write_json({
            "status": "success",
            "task_id": task_id,
            "title": parsed.title,
        })
        return True
    ctx.write_json({
        "status": "error", "message": "タスク名を抽出できませんでした"
    })
    return True



def action_update_task(ctx: ApiContext) -> bool:
    """タスク詳細編集 (スマホ編集シート用): ホワイトリスト項目のみDB反映する。

    due_date は epochミリ秒 (null=期日なし)、importance_flag/urgency_flag は
    true/false/null (null=未指定→4象限は推定ルールにフォールバック)。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True (task_id 欠落時は明示エラー)。
    """
    req = parse_request(ctx.body, UpdateTaskRequestDTO)
    if req is None:
        return _respond_invalid_body(ctx, "update_task")
    if not req.task_id:
        return _respond_missing_param(ctx, "update_task", "task_id")
    # model_fields_set で「クライアントが明示送信したキー」のみを反映 (null=未指定維持)
    sent_keys = req.model_fields_set
    fields: Dict[str, Any] = {}
    if "title" in sent_keys:
        new_title = (req.title or "").strip()
        if new_title:
            fields["title"] = new_title
    if "due_date" in sent_keys:
        fields["due_date"] = req.due_date if req.due_date else None
    if "priority" in sent_keys and req.priority is not None:
        fields["priority"] = max(0, min(3, req.priority))
    if "tags" in sent_keys:
        fields["tags"] = (req.tags or "").strip()
    if "list_id" in sent_keys:
        fields["list_id"] = req.list_id if req.list_id else None
    if "importance_flag" in sent_keys:
        fields["importance_flag"] = req.importance_flag
    if "urgency_flag" in sent_keys:
        fields["urgency_flag"] = req.urgency_flag
    success = database.update_task(req.task_id, fields) if fields else False
    logger.info(f"📱 スマホ側からタスク編集を受信: TaskID={req.task_id}, fields={list(fields.keys())}, success={success}")
    ctx.write_json({
        "status": "success" if success else "error", "task_id": req.task_id
    })
    return True


def action_delete_task(ctx: ApiContext) -> bool:
    """タスク削除 (スマホ編集シートの削除ボタン用・確認ダイアログはクライアント側)。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True (task_id 欠落時は明示エラー)。
    """
    req = parse_request(ctx.body, TaskActionRequestDTO)
    if req is None:
        return _respond_invalid_body(ctx, "delete_task")
    if not req.task_id:
        return _respond_missing_param(ctx, "delete_task", "task_id")
    success = database.delete_task(req.task_id)
    logger.info(f"📱 スマホ側からタスク削除を受信: TaskID={req.task_id}, success={success}")
    ctx.write_json({
        "status": "success" if success else "error", "task_id": req.task_id
    })
    return True


def action_list_task_lists(ctx: ApiContext) -> bool:
    """タスクリスト一覧取得 (TickTick拡張・スマホTODOモーダルのリスト切替用)。

    DB層の database.get_task_lists() をラップする薄い読み取り専用アクション。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True。
    """
    try:
        lists = database.get_task_lists()
        payload = [
            {
                "id": l.id,
                "name": l.name,
                "emoji": l.emoji,
                "parent_id": l.parent_id,
                "sort_order": l.sort_order,
            }
            for l in lists
        ]
        logger.info(f"📱 スマホ側からタスクリスト一覧を取得: {len(payload)}件")
        ctx.write_json({
            "status": "success",
            "lists": payload,
        })
        return True
    except Exception as e:
        logger.error(f"タスクリスト一覧の取得に失敗: {e}")
        ctx.write_json({
            "status": "error", "message": str(e)
        })
        return True


def action_get_tasks_view(ctx: ApiContext) -> bool:
    """TODOモーダル用の拡充タスク取得 (TickTick拡張・Plan C)。

    tags / due_date / list_id を含めて返し、リスト・タグ・期間の絞り込みは
    クライアント側 (pet.js) で行う。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True。
    """
    try:
        tasks = database.get_tasks(status="todo", limit=100)
        payload = [
            {
                "id": t.id,
                "title": t.title,
                "priority": t.priority,
                "due_date": t.due_date,
                "tags": t.tags or "",
                "list_id": t.list_id,
                "importance_flag": t.importance_flag,
                "urgency_flag": t.urgency_flag,
                "recurrence": t.recurrence,
            }
            for t in tasks
        ]
        logger.info(f"📱 スマホ側からTODOビューを取得: {len(payload)}件")
        response_payload = validate_tasks_view_response({
            "status": "success",
            "tasks": payload,
        })
        ctx.write_json(response_payload)
        return True
    except Exception as e:
        logger.error(f"TODOビューの取得に失敗: {e}")
        ctx.write_json({
            "status": "error", "message": str(e)
        })
        return True
