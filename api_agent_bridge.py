#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - Agent Bridge ＆ デバイス連携APIモジュール (api_agent_bridge.py)

コーディングエージェント (Claude Code / Codex / Antigravity / Cursor 等) と
スマホ Desk Pet・PC ペット間の仲介 API を担当するモジュール。
local_sync_server.py から P2③ 分割リファクタで抽出した。

契約:
- パス系ハンドラ (handle_*) は ``handler(ctx: ApiContext) -> None`` 署名を持ち、
  常にレスポンスを書き込む。
- アクション系ハンドラ (action_*) は ``handler(ctx: ApiContext) -> bool`` 署名を持ち、
  レスポンスを書き込んだら True を返す。パラメータ欠落・GUI 未起動等のガード
  未成立時も明示エラー ({"status": "error"}) を書き込んで True を返す
  (2026-09-03 改修: 旧仕様の無応答200空ボディは廃止。False は将来の例外経路用)。
- AGENT_ONLY_PATHS のループバック制限 (RCE チェーン遮断) は呼び出し元
  (local_sync_server.do_POST) で適用されるため、本モジュールでは再検査しない。
- GUI 操作は必ず gui.post_action 経由 (メインスレッドへディスパッチ)。
"""

import json
import logging
import time
from typing import Any, Dict

from api_context import ApiContext

logger = logging.getLogger(__name__)


# =============================================================================
# パス系ハンドラ (POST /api/agent/* ・ /api/test_buzz)
# =============================================================================


def handle_agent_ask(ctx: ApiContext) -> None:
    """外部エージェントからの承認要請 (POST /api/agent/ask) を処理する。

    Block 2 統合機能:
    1. AgentAdapter: Claude Code / Cline / 汎用エージェントのペイロードを共通DTOへ正規化。
    2. ApprovalPolicy: 3段階 (Auto-Allow / Prompt / Strict) 判定。安全なテスト等は即時自動許可。
    3. AuditLogger: 全ての承認・却下・自動許可履歴を SQLite に非同期安全に永続化。

    Args:
        ctx: リクエストコンテキスト。
    """
    from local_sync_server import get_bridge_hub, get_link_monitor
    from agent_adapter import get_default_adapter_registry, RiskLevel
    from approval_policy import get_default_policy_engine
    from audit_logger import get_global_audit_logger, AuditLogEntry

    ctx.begin_json_response()
    try:
        # bytes / str 両対応の安全なデコード
        if isinstance(ctx.body, bytes):
            body_str = ctx.body.decode("utf-8")
        elif isinstance(ctx.body, str):
            body_str = ctx.body
        else:
            body_str = "{}"
        raw_data = json.loads(body_str) if body_str else {}

        # 1. 共通DTOへ正規化 (Node A: Agent Adapter)
        registry = get_default_adapter_registry()
        req_dto = registry.normalize(raw_data, client_ip=ctx.client_ip)

        # 2. 3段階コマンド危険度判定 (Node B: Approval Policy)
        policy_engine = get_default_policy_engine()
        decision_policy = policy_engine.evaluate(req_dto.command)
        req_dto.risk_level = decision_policy.risk_level

        # Jev 安全審査レベルの自動抽出 (明示指定または summary から)
        safety_level = raw_data.get("safety_level")
        if not safety_level and req_dto.summary:
            import re
            m = re.search(r"【Jev安全審査:\s*(allow|confirm|deny)", req_dto.summary, re.IGNORECASE)
            if m:
                safety_level = m.group(1).lower()

        hub = get_bridge_hub()
        req = hub.create_approval_request(
            agent_name=req_dto.agent_name,
            command=req_dto.command,
            summary=req_dto.summary,
            details=req_dto.details,
            timeout_sec=req_dto.timeout_sec,
            requester_ip=ctx.client_ip,
            risk_level=req_dto.risk_level.value,
            agent_type=req_dto.agent_type,
            safety_level=safety_level
        )

        audit_logger = get_global_audit_logger()
        start_time = time.time()

        # 🟢 AUTO_ALLOW の場合: スマホ通知をスキップし即座に自動承認で解決
        if decision_policy.is_auto_allowed:
            req.resolve("approve", f"Auto-allowed by policy: {decision_policy.reason}")
            with hub._lock:
                hub.pending_requests.pop(req.request_id, None)
                hub.history.append(req.to_dict())
            audit_logger.log(AuditLogEntry(
                request_id=req.request_id,
                agent_type=req_dto.agent_type,
                agent_name=req_dto.agent_name,
                command=req_dto.command,
                summary=req_dto.summary,
                risk_level=req_dto.risk_level.value,
                decision="approve",
                decision_by="policy_engine",
                decision_message=req.decision_message,
                requester_ip=ctx.client_ip,
                client_ip="127.0.0.1",
                duration_sec=0.0,
                created_at=int(req.created_at),
            ))
        else:
            # 🟡 PROMPT または 🔴 STRICT: スマホ Desk Pet を振動・点滅させて人間承認を促す
            get_link_monitor().trigger_buzz()

        if raw_data.get("wait_decision", True):
            decision = req.wait(timeout=req_dto.timeout_sec)
            duration = time.time() - start_time

            # 3. 監査ログの記録 (Node C: Audit Log, PROMPT/STRICT用)
            if not decision_policy.is_auto_allowed:
                decision_by = "human" if decision in ("approve", "approved", "rejected") else "timeout"
                audit_logger.log(AuditLogEntry(
                    request_id=req.request_id,
                    agent_type=req_dto.agent_type,
                    agent_name=req_dto.agent_name,
                    command=req_dto.command,
                    summary=req_dto.summary,
                    risk_level=req_dto.risk_level.value,
                    decision=decision,
                    decision_by=decision_by,
                    decision_message=req.decision_message,
                    requester_ip=ctx.client_ip,
                    client_ip=getattr(req, "responder_ip", ""),
                    duration_sec=round(duration, 2),
                    created_at=int(req.created_at),
                ))

            ctx.write_json({
                "status": "success",
                "request_id": req.request_id,
                "decision": decision,
                "risk_level": req_dto.risk_level.value,
                "message": req.decision_message
            }, ensure_ascii=False)
        else:
            ctx.write_json({
                "status": "queued",
                "request_id": req.request_id,
                "risk_level": req_dto.risk_level.value
            }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Agent Ask API エラー: {e}")
        ctx.send_error_json(str(e))


def handle_agent_ask_input(ctx: ApiContext) -> None:
    """外部エージェントからの質問・選択肢回答要請 (POST /api/agent/ask_input) を処理する。

    Args:
        ctx: リクエストコンテキスト。
    """
    from local_sync_server import get_bridge_hub, get_gui_instance, get_link_monitor
    ctx.begin_json_response()
    try:
        data = json.loads(ctx.body.decode("utf-8"))
        agent_name = data.get("agent_name", "AI Agent")
        question = data.get("question", "確認事項があります")
        choices = data.get("choices", [])
        details = data.get("details", "")
        timeout = int(data.get("timeout", 180))

        hub = get_bridge_hub()
        req = hub.create_question_request(agent_name, question, choices, details, timeout_sec=timeout, requester_ip=ctx.client_ip)
        get_link_monitor().trigger_buzz()

        # PCペットのメッセージとリアクション（非表示状態は維持）
        gui = get_gui_instance()
        if gui:
            gui.post_action(gui.update_message, f"【{agent_name}】{question}")
            gui.post_action(gui.set_pet_state, "alarm_ask", 6000)

        if data.get("wait_decision", True):
            decision = req.wait(timeout=timeout)
            ctx.write_json({
                "status": "success",
                "request_id": req.request_id,
                "decision": decision,
                "answer": req.decision_message
            }, ensure_ascii=False)
        else:
            ctx.write_json({
                "status": "queued",
                "request_id": req.request_id
            }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Agent Ask Input API エラー: {e}")
        ctx.send_error_json(str(e))


def handle_agent_respond(ctx: ApiContext) -> None:
    """スマホからの意思決定・回答送信 (POST /api/agent/respond) を処理する。

    Args:
        ctx: リクエストコンテキスト。
    """
    from local_sync_server import get_bridge_hub, get_link_monitor
    get_link_monitor().record_heartbeat(ctx.client_ip, ctx.user_agent)
    ctx.begin_json_response()
    try:
        if isinstance(ctx.body, bytes):
            data = json.loads(ctx.body.decode("utf-8"))
        elif isinstance(ctx.body, str):
            data = json.loads(ctx.body)
        else:
            data = {}
        request_id = data.get("request_id")
        decision = data.get("decision", "approve")
        message = data.get("message", "")

        hub = get_bridge_hub()
        success, reason = hub.respond_checked(request_id, decision, message, responder_ip=ctx.client_ip)
        status_payload: Dict[str, Any] = {"status": "success", "reason": reason}
        if not success:
            if reason == "self_approve_denied":
                status_payload = {
                    "status": "error",
                    "reason": "self_approve_denied",
                    "message": "自己承認は禁止されています（要求元と同じ端末からの承認は無効）"
                }
            elif reason == "expired":
                status_payload = {
                    "status": "expired",
                    "reason": "expired",
                    "message": "この承認要請・質問は期限切れです（タイムアウトしました）。エージェントに再問い合わせしてください。"
                }
            else:
                status_payload = {
                    "status": "not_found",
                    "reason": "not_found",
                    "message": "対象のリクエストが見つかりません"
                }
        elif reason == "already_resolved":
            status_payload = {
                "status": "success",
                "reason": "already_resolved",
                "duplicate": True,
                "message": "既に処理済みのリクエストです"
            }
        ctx.write_json(status_payload, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Agent Respond API エラー: {e}")
        ctx.send_error_json(str(e))


def handle_agent_dismiss_completed(ctx: ApiContext) -> None:
    """スマホからの作業完了カード閉じる (POST /api/agent/dismiss_completed) を処理する。

    Args:
        ctx: リクエストコンテキスト。
    """
    from local_sync_server import get_bridge_hub
    ctx.begin_json_response()
    get_bridge_hub().dismiss_completed()
    ctx.write_json({"status": "success"})


def handle_agent_notify(ctx: ApiContext) -> None:
    """外部エージェント (Codex/Claude Code) からの作業完了・イベント通知 (POST /api/agent/notify) を処理する。

    Args:
        ctx: リクエストコンテキスト。
    """
    from local_sync_server import get_bridge_hub, get_gui_instance, get_link_monitor
    ctx.begin_json_response()
    try:
        data = json.loads(ctx.body.decode("utf-8"))
        agent_name = data.get("agent_name", "外部AI")
        title = data.get("title", "作業完了通知")
        message = data.get("message", "")
        details = data.get("details", "")
        pet_reaction = data.get("reaction", "celebrate")

        logger.info(f"🤖 [Agent Bridge Notify] {agent_name}から通知受信: {title} - {message}")

        # BridgeHubへ完了イベントを登録（リッチカード表示用）
        hub = get_bridge_hub()
        hub.set_completed_event(agent_name, title, message, details)

        # PCペットのリアクションとメッセージ更新（非表示状態は維持）
        gui = get_gui_instance()
        if gui:
            full_text = f"【{agent_name}】{title}\n{message}" if message else f"【{agent_name}】{title}"
            gui.post_action(gui.update_message, full_text)
            gui.post_action(gui.set_pet_state, pet_reaction, 6000)

        # スマホDesk Petへ最新通知をセット（自動でbuzz要求も発行）
        get_link_monitor().set_notification(agent_name, title, message, pet_reaction)

        ctx.write_json({
            "status": "success",
            "agent_name": agent_name,
            "reaction": pet_reaction
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Agent Notify API エラー: {e}")
        ctx.send_error_json(str(e))


def handle_test_buzz(ctx: ApiContext) -> None:
    """PCからのスマホ呼び出しテスト (POST /api/test_buzz) を処理する。

    Args:
        ctx: リクエストコンテキスト。
    """
    from local_sync_server import get_link_monitor
    ctx.begin_json_response()
    get_link_monitor().trigger_buzz()
    logger.info("📲 [Link Monitor] PCからスマホへ呼び出し信号(Buzz)を送信しました")
    ctx.write_json({"status": "buzz_triggered"}, ensure_ascii=False)


# =============================================================================
# アクション系ハンドラ (POST /api/action のアクション名に対応)
# =============================================================================


def action_start_pomodoro(ctx: ApiContext) -> bool:
    """スマホ側からのポモドーロ開始要求を処理する。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True (GUI 未起動時は明示エラー)。
    """
    data = json.loads(ctx.body.decode("utf-8"))
    from local_sync_server import get_gui_instance
    gui = get_gui_instance()
    if gui:
        mins = int(data.get("minutes", 25))
        gui.post_action(gui.start_pomodoro, mins)
        logger.info(f"📱 スマホ側からポモドーロ開始を受信: {mins}分")
        ctx.write_json({"status": "success", "action": "start_pomodoro"})
        return True
    logger.warning("📱 start_pomodoro: PC GUI 未起動のため要求を拒否しました")
    ctx.write_json({
        "status": "error",
        "message": "PC GUI is not running for action: start_pomodoro",
    })
    return True


def action_stop_pomodoro(ctx: ApiContext) -> bool:
    """スマホ側からのポモドーロ停止要求を処理する。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True (GUI 未起動時は明示エラー)。
    """
    from local_sync_server import get_gui_instance
    gui = get_gui_instance()
    if gui:
        gui.post_action(gui.stop_pomodoro)
        logger.info("📱 スマホ側からポモドーロ停止を受信")
        ctx.write_json({"status": "success", "action": "stop_pomodoro"})
        return True
    logger.warning("📱 stop_pomodoro: PC GUI 未起動のため要求を拒否しました")
    ctx.write_json({
        "status": "error",
        "message": "PC GUI is not running for action: stop_pomodoro",
    })
    return True


def action_show_pc_pet(ctx: ApiContext) -> bool:
    """スマホ側からのPCペット再表示要求を処理する。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True (GUI 未起動時は明示エラー)。
    """
    from local_sync_server import get_gui_instance
    gui = get_gui_instance()
    if gui:
        gui.post_action(gui.show_pc_pet)
        logger.info("📱 スマホ側からPCペット再表示要求を受信")
        ctx.write_json({"status": "success", "action": "show_pc_pet"})
        return True
    logger.warning("📱 show_pc_pet: PC GUI 未起動のため要求を拒否しました")
    ctx.write_json({
        "status": "error",
        "message": "PC GUI is not running for action: show_pc_pet",
    })
    return True


def action_switch_character(ctx: ApiContext) -> bool:
    """スマホ側からのキャラクタースキン変更要求を処理する。

    未知のキャラIDはサーバー側で拒否する (スマホ側だけ切り替わる状態分裂を防止)。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True。
    """
    from character_manager import get_character_manager
    data = json.loads(ctx.body.decode("utf-8"))
    char_id = data.get("character_id", "hisho")
    valid_ids = {c.get("id") for c in get_character_manager().get_all_characters()}
    if char_id not in valid_ids:
        logger.warning(f"📱 未知のキャラクターIDの変更要求を拒否: {char_id}")
        ctx.write_json(
            {"status": "error", "message": f"unknown character_id: {char_id}"},
            ensure_ascii=False
        )
        return True
    from local_sync_server import get_gui_instance
    gui = get_gui_instance()
    if gui:
        gui.post_action(gui.switch_character_skin, char_id)
    else:
        get_character_manager().set_character(char_id)
    logger.info(f"📱 スマホ側からキャラクタースキン変更を受信: {char_id}")
    ctx.write_json({"status": "success", "character_id": char_id})
    return True


def action_set_language(ctx: ApiContext) -> bool:
    """スマホ側からの言語切替要求を処理し、デスクトップおよびサーバーの言語を双方向同期する。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True。
    """
    import i18n
    try:
        data = json.loads(ctx.body.decode("utf-8")) if ctx.body else {}
    except Exception:
        data = {}
    lang = data.get("language", "ja")
    if lang not in ("ja", "en"):
        lang = "ja"
    i18n.set_language(lang)
    logger.info(f"📱 スマホ側から言語切替を受信・双方向同期: {lang}")
    ctx.write_json({"status": "success", "language": lang})
    return True



def action_toggle_suggest_source(ctx: ApiContext) -> bool:
    """スマホ側からのサジェストソース有効/無効変更要求を処理する。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True。
    """
    from suggest_engine import get_suggestion_engine
    data = json.loads(ctx.body.decode("utf-8"))
    source_key = data.get("source_key")
    enabled = data.get("enabled", True)
    get_suggestion_engine().toggle_source(source_key, enabled)
    logger.info(f"📱 スマホ側からサジェスト設定変更を受信: {source_key}={enabled}")
    ctx.write_json({"status": "success", "source_key": source_key, "enabled": enabled})
    return True


def action_set_news_keywords(ctx: ApiContext) -> bool:
    """スマホ側からのニュースキーワード更新要求を処理する。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True。
    """
    from suggest_engine import get_suggestion_engine
    data = json.loads(ctx.body.decode("utf-8"))
    keywords = data.get("keywords", "")
    eng = get_suggestion_engine()
    eng.set_news_keywords(keywords)
    updated_kw = eng.get_news_keywords()
    logger.info(f"📱 スマホ側からニュースキーワード更新を受信: {updated_kw}")
    ctx.write_json({"status": "success", "keywords": updated_kw})
    return True


def action_pet_reaction(ctx: ApiContext) -> bool:
    """スマホ側からのペット演出リクエストを処理する。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True。
    """
    from local_sync_server import get_gui_instance
    data = json.loads(ctx.body.decode("utf-8"))
    state = data.get("state", "celebrate")
    duration_ms = int(data.get("duration_ms", 5000))
    gui = get_gui_instance()
    if gui:
        gui.post_action(gui.set_pet_state, state, duration_ms)
        logger.info(f"🎉 スマホ側からペット演出リクエスト: {state} ({duration_ms}ms)")
    ctx.write_json({"status": "success", "state": state})
    return True


def action_ping_test(ctx: ApiContext) -> bool:
    """スマホからの死活確認 Ping テストを処理する。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True。
    """
    logger.debug(f"📶 スマホからPingテスト受信 ({ctx.client_ip})")
    ctx.write_json({"status": "pong", "server_time": int(time.time() * 1000)})
    return True


def action_voice_command(ctx: ApiContext) -> bool:
    """スマホからの音声コマンドをPC側エージェントへ投入する。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True。
    """
    from local_sync_server import get_gui_instance
    data = json.loads(ctx.body.decode("utf-8"))
    voice_text = data.get("text", "")
    logger.info(f"🎤 スマホから音声入力受信: {voice_text}")
    # PCペットの吹き出しへ表示
    gui = get_gui_instance()
    if gui:
        gui.post_action(gui.update_message, f"🎤 {voice_text}")
    # エージェントへ投げる（既存チャットパイプライン）
    from main import NeoSecretaryApp
    app = NeoSecretaryApp.get_instance()
    if app and voice_text:
        app.post_human_message(voice_text)
    ctx.write_json({"status": "success", "text": voice_text})
    return True


def action_easter_egg_trigger(ctx: ApiContext) -> bool:
    """スマホ側からのイースターエッグ発火フレーズを処理する。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True。
    """
    from local_sync_server import get_gui_instance, get_link_monitor
    import easter_egg_engine
    data = json.loads(ctx.body.decode("utf-8"))
    phrase = data.get("phrase", "お前を消す方法")
    ee_event = easter_egg_engine.observe_message(phrase)
    if ee_event:
        get_link_monitor().set_easter_egg_event(
            stage=ee_event["stage"],
            daily_count=ee_event["daily_count"],
            attempt_count=ee_event["attempt_count"],
            message=ee_event["fallback_reply"]
        )
        gui = get_gui_instance()
        if gui:
            gui.post_action(gui.update_message, ee_event["fallback_reply"])
            if ee_event["stage"] >= 3:
                gui.post_action(gui.set_pet_state, "thinking", 3000)
        logger.info(f"📱 スマホ側からイースターエッグ発火: stage={ee_event['stage']}")
        ctx.write_json({
            "status": "success",
            "stage": ee_event["stage"],
            "reply": ee_event["fallback_reply"],
            "daily_count": ee_event["daily_count"],
            "attempt_count": ee_event["attempt_count"]
        }, ensure_ascii=False)
    else:
        ctx.write_json({"status": "no_trigger"})
    return True


def action_trigger_briefing(ctx: ApiContext) -> bool:
    """スマホ側からの朝会/終礼ブリーフィング要求を処理する。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True。
    """
    from local_sync_server import get_gui_instance
    import briefing_engine
    data = json.loads(ctx.body.decode("utf-8"))
    force_mode = data.get("mode")
    report = briefing_engine.generate_briefing(force_mode=force_mode)
    gui = get_gui_instance()
    if gui:
        # PCペットの吹き出しにも短縮要約を表示
        short_text = f"【{report.mode_label}】\n{report.greeting}\n\n🌡️ 天気: {report.weather_summary['desc']} ({report.weather_summary['temperature']:.1f}°C)\n📅 予定: {len(report.events_today)}件 | 📝 残TODO: {len(report.active_tasks)}件\n\n{report.encouragement}"
        gui.post_action(gui.update_message, short_text)
        gui.post_action(gui.set_pet_state, "happy", 4000)
    logger.info(f"📱 スマホからブリーフィング要求受信: mode={report.mode}")
    ctx.write_json({"status": "success", "briefing": report.to_dict()}, ensure_ascii=False)
    return True


def action_set_weather_location(ctx: ApiContext) -> bool:
    """スマホ側からの天気地域手動設定要求を処理する。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True。
    """
    from local_sync_server import get_gui_instance
    import weather_tools
    data = json.loads(ctx.body.decode("utf-8"))
    loc = data.get("location", "").strip()
    weather_tools.save_location(loc)
    # 即座に天気キャッシュを更新
    w_new = weather_tools.get_weather()
    gui = get_gui_instance()
    if gui:
        gui.post_action(gui.update_message, f"📍 お住まいの地域を【{loc or 'IP自動検出'}】に設定しました！\n現在の天気: {w_new.get('city')} {w_new.get('weather')}")
    logger.info(f"📍 天気地域を手動設定: {loc}")
    ctx.write_json({"status": "success", "location": loc, "weather": w_new}, ensure_ascii=False)
    return True


def action_record_minigame_score(ctx: ApiContext) -> bool:
    """Phase L5: シークレットミニゲーム「Pixel Defense」のスコア永続化。

    改竄・誤送信対策: 数値変換不能な入力は 0 として扱い、負値は 0 にクランプする。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        bool: 常にレスポンスを書き込むため True。
    """
    import database
    data = json.loads(ctx.body.decode("utf-8"))
    game_id = str(data.get("game_id", "pixel_defense")).strip() or "pixel_defense"
    try:
        score = int(data.get("score", 0))
    except (TypeError, ValueError):
        logger.warning(f"👾 不正なミニゲームスコアを受信 (game_id={game_id}): {data.get('score')!r} → 0 にクランプ")
        score = 0
    score = max(0, score)
    previous_high = database.get_high_score(game_id)
    record_id = database.record_minigame_score(game_id, score)
    new_high = max(previous_high, score)
    logger.info(f"👾 スマホ側からミニゲームスコアを受信: game_id={game_id}, score={score}, high_score={new_high}")
    ctx.write_json({"status": "success", "record_id": record_id, "high_score": new_high, "score": score})
    return True
