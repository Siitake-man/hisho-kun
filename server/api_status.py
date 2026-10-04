#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - 状態同期 API ハンドラー (server/api_status.py / S4 Seam).

Fat モジュール `local_sync_server.py` から、GET /api/status の
ペイロード生成処理（248行）および HTTP ハンドリングを独立した Deep Module として切り出します。

契約:
    - build_status_payload(client_ip: str, user_agent: str, now: Optional[float] = None) -> dict
    - handle_get_status(handler, client_ip: str, user_agent: str) -> None
    - _fmt_event_dt(ms_val: Any) -> str
    - get_update_notice_payload() -> dict
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import database
import i18n
from agent_fsm import agent_fsm
from server.agent_bridge_hub import get_bridge_hub
from server.device_link import get_link_monitor
from server.status_cache import get_status_cache
from sync_dtos import validate_status_payload

logger = logging.getLogger(__name__)


def _fmt_event_dt(ms_val: Any) -> str:
    """ミリ秒タイムスタンプをスマホ手帳表示用の 'YYYY-MM-DD HH:MM' 文字列へ変換する。

    Args:
        ms_val: Unixタイムスタンプ（ミリ秒）。

    Returns:
        str: 整形済み日時文字列（変換失敗時は空文字）。
    """
    try:
        if not ms_val:
            return ""
        return datetime.fromtimestamp(int(ms_val) / 1000).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def get_update_notice_payload() -> Dict[str, Any]:
    """スマホPWA向けの更新通知ペイロードを生成する (/api/status 専用)。"""
    try:
        from update_checker import get_update_status
        return get_update_status()
    except Exception as e:
        logger.warning("更新状態ペイロードの生成に失敗 (無視): %s", e)
        return {"update_available": False, "current_version": None}


def build_status_payload(
    client_ip: str,
    user_agent: str,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """/api/status で返却する完全な JSON ペイロード辞書を構築する。

    2秒TTL DBキャッシュおよび30秒TTL習慣キャッシュを適用し、
    エージェント状態、リマインダー、サジェスト、生活ドリーマー等を統合します。

    Args:
        client_ip: クライアント接続元 IP アドレス。
        user_agent: クライアント User-Agent 文字列。
        now: 基準時刻 (time.time())。テスト等のため注入可能。

    Returns:
        Dict[str, Any]: Pydantic DTO 検証済みのステータスペイロード。
    """
    if now is None:
        now = time.time()

    cache = get_status_cache()

    # 1. 2秒キャッシュによりDBの過負荷を防止
    is_db_valid, cached_tasks, cached_events = cache.get_db_cache(now=now, ttl=2.0)
    if not is_db_valid:
        cached_tasks = []
        cached_events = []
        try:
            tasks = database.get_tasks(status="todo", limit=20)
            events = database.get_upcoming_events(days=3)
            sources_by_id: Dict[int, Dict[str, str]] = {}
            try:
                for s in database.get_all_calendar_sources():
                    sources_by_id[s.id] = {"name": s.name, "color": s.color}
            except Exception as e:
                logger.warning("カレンダーソース取得失敗: %s", e)

            cached_tasks = [
                {"id": t.id, "title": t.title, "priority": t.priority, "due_date": t.due_date}
                for t in tasks
            ]
            cached_events = [
                {
                    "id": e.id,
                    "title": e.title,
                    "start_time": _fmt_event_dt(e.start_time),
                    "description": e.description,
                    "source_color": sources_by_id.get(e.source_id, {}).get("color", ""),
                    "source_name": sources_by_id.get(e.source_id, {}).get("name", ""),
                }
                for e in events
            ]
        except Exception as db_err:
            logger.warning("DBタスク/予定取得失敗 (空配列フォールバック): %s", db_err)

        cache.set_db_cache(cached_tasks, cached_events, timestamp=now)


    monitor = get_link_monitor()
    hub = get_bridge_hub()
    pending_req = hub.get_latest_pending()
    should_buzz = monitor.consume_buzz()

    current_lang = i18n.get_language()
    is_en = (current_lang == "en")

    # ポモドーロ状態の取得 (GUI インスタンスから取得)
    import local_sync_server
    gui = local_sync_server.get_gui_instance()
    pomodoro_active = getattr(gui, "pomodoro_active", False) if gui else False
    pomodoro_is_break = getattr(gui, "pomodoro_is_break", False) if gui else False
    pomodoro_sec = getattr(gui, "pomodoro_remaining_seconds", 0) if gui else 0
    if is_en:
        pomodoro_label = "☕ Break" if pomodoro_is_break else "🍅 Focus"
    else:
        pomodoro_label = "☕ 休憩中" if pomodoro_is_break else "🍅 集中中"

    # ⏰ 期限リマインダー (roadmap 3.1)
    due_reminders: List[Dict[str, Any]] = []
    try:
        from reminder_engine import get_reminder_engine
        due_reminders = get_reminder_engine().get_pending_for_phone()
    except Exception as rem_err:
        logger.debug("リマインダー状態取得スキップ: %s", rem_err)

    pet_state = "alarm_ask" if pending_req else ("focus" if (pomodoro_active and not pomodoro_is_break) else "idle")
    # 台詞の優先順位: 承認要請 > リマインダー > 集中タイム > PCペット最新セリフ（ミラー） > キャラ別ローテーション挨拶
    pc_message = str(getattr(gui, "current_message", "") or "").strip() if gui else ""
    use_greeting_rotation = not (pending_req or due_reminders or (pomodoro_active and not pomodoro_is_break) or pc_message)
    if pending_req:
        default_msg = "Boss! An AI agent is requesting approval to execute a command!" if is_en else "ボス！エージェントからコマンド実行の許可を求められています！"
    elif due_reminders:
        rem_first = due_reminders[0]
        default_msg = f"⏰ Reminder: {rem_first.get('title', 'Upcoming schedule!')}" if is_en else f"⏰ 予定リマインダー: {rem_first.get('title', 'まもなく予定の時間です！')}"
    elif pomodoro_active and not pomodoro_is_break:
        default_msg = "Focus time! Let's do our best together, Boss! 🔥" if is_en else "集中タイムです！ボス、一緒に頑張りましょう！🔥"
    elif pc_message:
        default_msg = pc_message
    else:
        default_msg = "Boss, thank you for your hard work! Watching over you from mobile! ✨" if is_en else "ボス、いつもお疲れ様です！スマホからも見守っていますよ！"

    # サジェスト
    from suggest_engine import get_suggestion_engine
    suggest_eng = get_suggestion_engine()
    suggestions_data = suggest_eng.get_cached_suggestions()

    # キャラクター
    from character_manager import get_character_manager
    char_mgr = get_character_manager()
    char_info = char_mgr.get_current_character()

    # 🌈 自律生活ドリーマーの状態を取得
    try:
        from life_dreamer import get_life_dreamer
        life_state = get_life_dreamer().get_life_state()
    except Exception as life_err:
        logger.debug("LifeDreamer 状態取得スキップ: %s", life_err)
        life_state = {
            "current_activity": "resting",
            "weather": "sunny",
            "message": "",
            "history": [],
        }

    active_event = hub.get_active_event()
    active_notification = monitor.get_active_notification()

    # ペット状態の決定
    agent_activity = agent_fsm.get_current_activity()
    if active_event:
        ev_type = active_event.get("type")
        if ev_type in ("approval", "question"):
            pet_state = "alarm_ask"
        elif ev_type == "completed":
            pet_state = "celebrate"
        else:
            pet_state = "idle"
    elif agent_activity.get("is_active"):
        act_st = agent_activity.get("state")
        if act_st == "coding":
            pet_state = "focus"
        elif act_st == "thinking":
            pet_state = "think"
        elif act_st == "waiting_approval":
            pet_state = "alarm_ask"
        elif act_st == "success":
            pet_state = "celebrate"
        else:
            pet_state = "idle"
    elif due_reminders:
        pet_state = "alarm_ask"
    else:
        pet_state = "focus" if (pomodoro_active and not pomodoro_is_break) else "idle"

    # 習慣 ＆ 草ヒートマップデータ (30秒TTLキャッシュ)
    is_habit_valid, cached_habits, cached_heatmap = cache.get_habit_cache(now=now, ttl=30.0)
    if not is_habit_valid:
        cached_habits = []
        cached_heatmap = []
        try:
            cached_habits = [h.model_dump() for h in database.get_habits_with_status()]
            cached_heatmap = [d.model_dump() for d in database.get_habit_heatmap_data(days=70)]
        except Exception as habit_err:
            logger.warning("DB習慣/ヒートマップ取得失敗 (空配列フォールバック): %s", habit_err)
        cache.set_habit_cache(cached_habits, cached_heatmap, timestamp=now)


    bond_info = char_mgr.get_bond_info()

    # キャラ別挨拶 × 時間帯 × 90秒ローテーション
    if use_greeting_rotation:
        try:
            greetings = list(char_mgr.get_current_character().get("greetings", []))
        except Exception:
            greetings = []
        hour = time.localtime(now).tm_hour
        if is_en:
            if 5 <= hour < 11:
                greetings = ["Good morning, Boss! Let's make today count! ✨"]
            elif 11 <= hour < 18:
                greetings = ["Boss, watching over your afternoon work from here! ✨"]
            elif 18 <= hour < 23:
                greetings = ["Great work today, Boss! Thank you for your dedication ✨"]
            else:
                greetings = ["Yawn... Still awake? Don't overdo it, Boss. 🌙"]
        else:
            if 5 <= hour < 11:
                greetings.append("おはようございます、ボス！今日も一日よろしくです！")
            elif 11 <= hour < 18:
                greetings.append("ボス、午後の業務もここから見守っていますよ！")
            elif 18 <= hour < 23:
                greetings.append("ボス、今日も一日お疲れ様です！もう少しだけ付き合ってください✨")
            else:
                greetings.append("ふぁ…まだ起きています？無理は禁物ですよ、ボス。")
        if greetings:
            default_msg = greetings[int(now // 90) % len(greetings)]

    # イースターエッグ状態
    try:
        import easter_egg_engine
        ee_state = easter_egg_engine.load_state()
        ee_payload = {
            "attempt_count": ee_state.attempt_count,
            "daily_count": ee_state.daily_count,
            "secret_game_unlocked": ee_state.secret_game_unlocked,
            "active_event": monitor.get_active_easter_egg_event(),
        }
    except Exception as ee_err:
        logger.debug("イースターエッグ状態取得スキップ: %s", ee_err)
        ee_payload = {
            "attempt_count": 0,
            "daily_count": 0,
            "secret_game_unlocked": False,
            "active_event": None,
        }

    payload: Dict[str, Any] = {
        "status": "ok",
        "pet_state": pet_state,
        "message": default_msg,
        "character": {
            "id": char_info["id"],
            "name": char_info["name"],
            "title": char_info["title"],
            "emoji": char_info["emoji"],
            "all": char_mgr.get_all_characters(),
        },
        "bond": bond_info,
        "habits": cached_habits,
        "habit_heatmap": cached_heatmap,
        "pending_approval": pending_req,
        "active_event": active_event,
        "latest_notification": active_notification,
        "agent_activity": agent_activity,
        "easter_egg": ee_payload,
        "tasks": cached_tasks,
        "events": cached_events,
        "suggestions": suggestions_data,
        "due_reminders": due_reminders,
        "suggest_config": suggest_eng.config,
        "pomodoro": {
            "active": pomodoro_active,
            "is_break": pomodoro_is_break,
            "remaining_seconds": pomodoro_sec,
            "total_seconds": getattr(gui, "pomodoro_total_seconds", 25 * 60) if gui else 25 * 60,
            "mode_label": pomodoro_label,
        },
        "buzz": should_buzz,
        "life_state": life_state,
        "life_coach": None,  # AI生活コーチ機能は ID 36 にて撤去済み (互換性維持)
        "weather_location": (lambda: (__import__("weather_tools").get_current_location_setting()))(),
        "update": get_update_notice_payload(),
        "language": current_lang,
        "server_time": int(now * 1000),
    }

    # P2①: Pydantic DTO 境界検証 (契約違反時は生辞書フォールバックで可用性維持)
    return validate_status_payload(payload)


def handle_get_status(handler: Any, client_ip: str, user_agent: str) -> None:
    """GET /api/status リクエストを処理し、クライアントへ JSON レスポンスを送信する。

    Args:
        handler: HTTPRequestHandler インスタンス。
        client_ip: 接続元 IP アドレス。
        user_agent: 接続元 User-Agent。
    """
    monitor = get_link_monitor()
    was_offline = monitor.record_heartbeat(client_ip, user_agent)
    if was_offline:
        logger.info("📱 [Link Monitor] スマホ端末が接続されました: %s (%s)", monitor.device_name, client_ip)

    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    if hasattr(handler, "_set_cors_headers"):
        handler._set_cors_headers()
    handler.end_headers()

    try:
        payload = build_status_payload(client_ip, user_agent)
        handler.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    except Exception as e:
        logger.error("Status API エラー: %s", e)
        handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))
