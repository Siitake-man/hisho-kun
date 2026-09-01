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
"""

import base64
import json
import logging
from typing import Any, Dict

import database
from api_context import ApiContext
from sync_dtos import validate_tasks_view_response

logger = logging.getLogger(__name__)


def action_complete_task(ctx: ApiContext) -> bool:
    """スマホ側からのタスク完了を受け付ける。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: レスポンスを書き込んだ場合は True (task_id 欠落時は False)。
    """
    data: Dict[str, Any] = json.loads(ctx.body.decode("utf-8"))
    task_id = data.get("task_id")
    if task_id:
        database.complete_task(int(task_id))
        logger.info(f"📱 スマホ側からタスク完了を受信: TaskID={task_id}")
        ctx.write_json({"status": "success", "task_id": task_id})
        return True
    return False


def action_reopen_task(ctx: ApiContext) -> bool:
    """誤タップ復活: 完了済みタスクを未完了へ戻す (繰り返し次回分も巻き戻し)。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: レスポンスを書き込んだ場合は True (task_id 欠落時は False)。
    """
    data = json.loads(ctx.body.decode("utf-8"))
    task_id = data.get("task_id")
    if task_id:
        success = database.reopen_task(int(task_id))
        logger.info(f"📱 スマホ側からタスク完了取り消しを受信: TaskID={task_id}, success={success}")
        ctx.write_json({"status": "success" if success else "error", "task_id": task_id})
        return True
    return False


def action_toggle_habit(ctx: ApiContext) -> bool:
    """スマホ側からの習慣達成トグルを受け付ける (達成時は親愛度XP +10)。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: レスポンスを書き込んだ場合は True (habit_id 欠落時は False)。
    """
    data = json.loads(ctx.body.decode("utf-8"))
    habit_id = data.get("habit_id")
    if habit_id:
        is_done = database.toggle_habit_log(int(habit_id))
        # 親愛度XP加算 (+10 XP)
        if is_done:
            from character_manager import get_character_manager
            get_character_manager().add_bond_xp(10)
            from local_sync_server import get_gui_instance
            gui = get_gui_instance()
            if gui and hasattr(gui, 'animator'):
                gui.post_action(gui.animator.trigger_reaction, "task_complete")
        logger.info(f"📱 スマホ側から習慣トグルを受信: HabitID={habit_id}, IsDone={is_done}")
        ctx.write_json({"status": "success", "habit_id": habit_id, "is_done": is_done})
        return True
    return False


def action_add_habit(ctx: ApiContext) -> bool:
    """スマホ側からの習慣新規作成を受け付ける。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: レスポンスを書き込んだ場合は True (title 空欄時は False)。
    """
    data = json.loads(ctx.body.decode("utf-8"))
    title = data.get("title", "").strip()
    emoji = data.get("emoji", "🌱")
    if title:
        from database import Habit
        h_id = database.create_habit(Habit(title=title, emoji=emoji))
        logger.info(f"📱 スマホ側から習慣作成を受信: ID={h_id}, Title={title}")
        ctx.write_json({"status": "success", "habit_id": h_id})
        return True
    return False


def action_quick_add_task(ctx: ApiContext) -> bool:
    """クイック追加バー用 (TickTick拡張): 自然言語1行から期限/タグ/優先度を解析する。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: レスポンスを書き込んだ場合は True (text 欠落時は False)。
    """
    data = json.loads(ctx.body.decode("utf-8"))
    quick_text = data.get("text", "").strip()
    if quick_text:
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
    return False


def action_transcribe_voice(ctx: ApiContext) -> bool:
    """スマホ音声 ➔ PC Whisper 文字起こし ➔ quick_add_task パイプライン (B20)。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True。
    """
    data = json.loads(ctx.body.decode("utf-8"))
    audio_b64 = data.get("audio_base64", "")
    filename = data.get("filename", "voice.webm")
    auto_add_task = data.get("auto_add_task", True)

    if not audio_b64:
        logger.warning("音声データが空の transcribe_voice リクエストを受信しました")
        ctx.write_json({
            "status": "error", "message": "音声データ (audio_base64) が指定されていません"
        }, ensure_ascii=False)
        return True

    try:
        audio_bytes = base64.b64decode(audio_b64)
    except Exception as b64_err:
        logger.error("音声Base64のデコードに失敗: %s", b64_err)
        ctx.write_json({
            "status": "error", "message": f"Base64デコードエラー: {b64_err}"
        }, ensure_ascii=False)
        return True

    try:
        from whisper_transcriber import WhisperTranscriber
        transcriber = WhisperTranscriber()
        if not transcriber.is_available():
            logger.warning("WhisperTranscriber が未インストールのため音声認識を実行できません")
            ctx.write_json({
                "status": "error",
                "message": "PC側の音声文字起こしライブラリ (faster-whisper) が未導入です。requirements_whisper.txt をインストールしてください。"
            }, ensure_ascii=False)
            return True

        transcript = transcriber.transcribe(audio_bytes, filename=filename)
        if not transcript:
            logger.info("📱 音声文字起こし結果が空でした (無音または認識不能)")
            ctx.write_json({
                "status": "empty_transcript",
                "transcript": "",
                "task_created": False,
                "message": "音声を認識できませんでした。もう少しはっきりと話してみてください。"
            }, ensure_ascii=False)
            return True

        # 自動タスク作成 (auto_add_task) の内部呼び出し
        task_created = False
        task_id = None
        extracted_title = ""
        if auto_add_task:
            from task_parser import parse_input, tags_to_db_string
            parsed = parse_input(transcript)
            if parsed.title:
                task_id = database.create_task(database.Task(
                    title=parsed.title,
                    description="🎤 スマホ音声入力より自動登録",
                    due_date=parsed.due_date,
                    priority=parsed.priority,
                    status="todo",
                    tags=tags_to_db_string(parsed.tags),
                    importance_flag=parsed.importance,
                    urgency_flag=parsed.urgency,
                    recurrence=parsed.recurrence,
                ))
                task_created = True
                extracted_title = parsed.title
                logger.info("📱 🎤 音声文字起こしからタスク自動作成: ID=%s, Title='%s' (元音声='%s')", task_id, parsed.title, transcript)

                # PC側ペットのセリフ更新
                from local_sync_server import get_gui_instance
                gui = get_gui_instance()
                if gui:
                    gui.post_action(gui.update_message, f"🎤 音声からTODOを作成しました:\n「{parsed.title}」")
                    if hasattr(gui, 'animator'):
                        gui.post_action(gui.animator.trigger_reaction, "task_complete")

        ctx.write_json({
            "status": "ok",
            "transcript": transcript,
            "task_created": task_created,
            "task_id": task_id,
            "title": extracted_title
        }, ensure_ascii=False)
        return True

    except Exception as tr_err:
        logger.error("音声文字起こしパイプライン処理中にエラー: %s", tr_err, exc_info=True)
        ctx.write_json({
            "status": "error",
            "message": f"音声文字起こしエラー: {tr_err}"
        }, ensure_ascii=False)
        return True


def action_update_task(ctx: ApiContext) -> bool:
    """タスク詳細編集 (スマホ編集シート用): ホワイトリスト項目のみDB反映する。

    due_date は epochミリ秒 (null=期日なし)、importance_flag/urgency_flag は
    true/false/null (null=未指定→4象限は推定ルールにフォールバック)。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: レスポンスを書き込んだ場合は True (task_id 欠落時は False)。
    """
    data = json.loads(ctx.body.decode("utf-8"))
    task_id = data.get("task_id")
    if task_id:
        fields = {}
        if "title" in data:
            new_title = str(data["title"]).strip()
            if new_title:
                fields["title"] = new_title
        if "due_date" in data:
            due = data["due_date"]
            fields["due_date"] = int(due) if due else None
        if "priority" in data:
            fields["priority"] = max(0, min(3, int(data["priority"])))
        if "tags" in data:
            fields["tags"] = str(data["tags"]).strip()
        if "list_id" in data:
            lid = data["list_id"]
            fields["list_id"] = int(lid) if lid else None
        if "importance_flag" in data:
            iv = data["importance_flag"]
            fields["importance_flag"] = None if iv is None else bool(iv)
        if "urgency_flag" in data:
            uv = data["urgency_flag"]
            fields["urgency_flag"] = None if uv is None else bool(uv)
        success = database.update_task(int(task_id), fields) if fields else False
        logger.info(f"📱 スマホ側からタスク編集を受信: TaskID={task_id}, fields={list(fields.keys())}, success={success}")
        ctx.write_json({
            "status": "success" if success else "error", "task_id": task_id
        })
        return True
    return False


def action_delete_task(ctx: ApiContext) -> bool:
    """タスク削除 (スマホ編集シートの削除ボタン用・確認ダイアログはクライアント側)。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: レスポンスを書き込んだ場合は True (task_id 欠落時は False)。
    """
    data = json.loads(ctx.body.decode("utf-8"))
    task_id = data.get("task_id")
    if task_id:
        success = database.delete_task(int(task_id))
        logger.info(f"📱 スマホ側からタスク削除を受信: TaskID={task_id}, success={success}")
        ctx.write_json({
            "status": "success" if success else "error", "task_id": task_id
        })
        return True
    return False


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
