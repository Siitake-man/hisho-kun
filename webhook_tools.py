"""
ネオ秘書くん - 外部SaaS・マルチ中継Webhook連携モジュール (webhook_tools.py)

Zapier, Make (Integromat), IFTTT, Google Apps Script (GAS) などのノーコード・中継ハブと
JSON Webhook経由で双方向に予定やTODOを同期する基盤。
Google公式OAuthの100名制限やアプリ審査を回避し、ユーザー所有のSaaSアカウントと安全に連携します。
"""
import json
import logging
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool

import database
from database import Event, Task

logger = logging.getLogger(__name__)

import app_paths

CONFIG_PATH = app_paths.get_app_root() / "webhook_config.json"

DEFAULT_WEBHOOK_CONFIG = {
    "outgoing_webhook_url": "",
    "webhook_secret": "",
    "sync_events": True,
    "sync_tasks": True
}


def get_webhook_config() -> Dict[str, Any]:
    """Webhook設定を読み込みます"""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return {**DEFAULT_WEBHOOK_CONFIG, **cfg}
        except Exception as e:
            logger.error(f"Webhook設定読み込み失敗: {e}")
    return DEFAULT_WEBHOOK_CONFIG.copy()


def save_webhook_config(config: Dict[str, Any]) -> None:
    """Webhook設定を保存・永続化します"""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        logger.info("Webhook設定を保存しました")
    except Exception as e:
        logger.error(f"Webhook設定保存失敗: {e}")


def send_event_to_outgoing_webhook(event_data: Dict[str, Any]) -> bool:
    """
    秘書くんで作成・更新されたカレンダー予定を外部SaaS（Zapier/Make/GAS等）へPOST送信します。

    Args:
        event_data: 予定情報辞書（title, start_time, end_time, description等）

    Returns:
        bool: 送信成功時 True
    """
    cfg = get_webhook_config()
    target_url = cfg.get("outgoing_webhook_url", "").strip()
    if not target_url or not cfg.get("sync_events", True):
        logger.debug("送信先Webhook URL未設定またはイベント同期OFFのため送信スキップ")
        return False

    payload = {
        "type": "calendar_event",
        "timestamp": int(time.time() * 1000),
        "source": "neo_secretary",
        "data": event_data
    }

    return _post_json(target_url, payload, cfg.get("webhook_secret", ""))


def send_task_to_outgoing_webhook(task_data: Dict[str, Any]) -> bool:
    """
    秘書くんで作成・更新されたTODOタスクを外部SaaS（Notion/Slack/Todoist等）へPOST送信します。

    Args:
        task_data: タスク情報辞書（title, description, priority, due_date等）

    Returns:
        bool: 送信成功時 True
    """
    cfg = get_webhook_config()
    target_url = cfg.get("outgoing_webhook_url", "").strip()
    if not target_url or not cfg.get("sync_tasks", True):
        logger.debug("送信先Webhook URL未設定またはタスク同期OFFのため送信スキップ")
        return False

    payload = {
        "type": "task",
        "timestamp": int(time.time() * 1000),
        "source": "neo_secretary",
        "data": task_data
    }

    return _post_json(target_url, payload, cfg.get("webhook_secret", ""))


def process_incoming_calendar_webhook(payload: Dict[str, Any], db_path: str = "neo_secretary.db") -> Dict[str, Any]:
    """
    外部SaaS（Zapier/Make/GAS）から届いた予定登録リクエストを処理し、ローカルDBへ格納します。

    Args:
        payload: 受信JSON（title, start_time, end_time, description等）
        db_path: DBパス

    Returns:
        Dict[str, Any]: 処理結果辞書
    """
    try:
        title = payload.get("title", "").strip()
        if not title:
            return {"status": "error", "message": "title は必須です"}

        # 時刻のパース（ミリ秒数値またはISO 8601文字列）
        start_time = _parse_timestamp_ms(payload.get("start_time"))
        end_time = _parse_timestamp_ms(payload.get("end_time"))

        if not start_time:
            start_time = int(time.time() * 1000)
        if not end_time or end_time <= start_time:
            end_time = start_time + (60 * 60 * 1000)  # デフォルト1時間

        desc = payload.get("description", "")
        external_id = payload.get("id") or payload.get("google_event_id") or ""

        new_event = Event(
            title=title,
            description=desc,
            start_time=start_time,
            end_time=end_time,
            google_event_id=str(external_id) if external_id else None
        )

        event_id = database.create_event(new_event, db_path=db_path)
        logger.info(f"🔗 外部Webhookから予定を受信・登録完了: ID={event_id}, title={title}")
        return {"status": "success", "event_id": event_id, "title": title}
    except Exception as e:
        logger.error(f"外部予定Webhook処理エラー: {e}")
        return {"status": "error", "message": str(e)}


def process_incoming_task_webhook(payload: Dict[str, Any], db_path: str = "neo_secretary.db") -> Dict[str, Any]:
    """
    外部SaaS（Slack/Notion/Zapier）から届いたTODO登録リクエストを処理し、ローカルDBへ格納します。

    Args:
        payload: 受信JSON（title, description, priority, due_date等）
        db_path: DBパス

    Returns:
        Dict[str, Any]: 処理結果辞書
    """
    try:
        title = payload.get("title", "").strip()
        if not title:
            return {"status": "error", "message": "title は必須です"}

        desc = payload.get("description", "")
        priority_val = payload.get("priority", 1)
        if isinstance(priority_val, str):
            priority_val = 3 if priority_val.lower() == "high" else (2 if priority_val.lower() == "medium" else 1)
        
        due_date_raw = payload.get("due_date")
        due_date_ms = _parse_timestamp_ms(due_date_raw)

        new_task = Task(
            title=title,
            description=desc,
            priority=int(priority_val),
            due_date=due_date_ms,
            status="todo"
        )

        task_id = database.create_task(new_task, db_path=db_path)
        logger.info(f"🔗 外部WebhookからTODOタスクを受信・登録完了: ID={task_id}, title={title}")
        return {"status": "success", "task_id": task_id, "title": title}
    except Exception as e:
        logger.error(f"外部タスクWebhook処理エラー: {e}")
        return {"status": "error", "message": str(e)}


def _post_json(url: str, payload: Dict[str, Any], secret: str = "") -> bool:
    """JSONペイロードをHTTP POST送信"""
    try:
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "NeoSecretary-Webhook/1.0"
        }
        if secret:
            headers["X-Webhook-Secret"] = secret
            headers["Authorization"] = f"Bearer {secret}"

        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as res:
            logger.info(f"Webhook送信成功: {url} (HTTP {res.status})")
            return True
    except Exception as e:
        logger.warning(f"Webhook送信失敗: {url}, エラー: {e}")
        return False


def _parse_timestamp_ms(val: Any) -> Optional[int]:
    """ミリ秒タイムスタンプまたはISO 8601日時文字列をミリ秒整数へ変換"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        # 秒単位の場合はミリ秒へ補正
        if val < 10000000000:
            return int(val * 1000)
        return int(val)
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return None
        # 数値文字列
        if val.isdigit():
            v = int(val)
            return v * 1000 if v < 10000000000 else v
        # ISO 8601 パース
        try:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except Exception:
            pass
    return None


# =============================================================================
# LangChain Tool 定義（LangGraph / agent.py 連携用）
# =============================================================================

@tool
def send_calendar_event_to_webhook_tool(title: str, start_time_str: str, duration_hours: float = 1.0, description: str = "") -> str:
    """
    作成した予定をZapier/Make/GASなどの外部連携Webhookへ送信します。
    
    Args:
        title: 予定のタイトル
        start_time_str: 開始時刻（例: "2026-08-30 15:00" または "2026-08-30T15:00:00"）
        duration_hours: 所要時間（時間単位、デフォルト: 1.0）
        description: 予定の詳細メモ
    """
    try:
        dt = datetime.fromisoformat(start_time_str.replace(" ", "T"))
        st_ms = int(dt.timestamp() * 1000)
        et_ms = st_ms + int(duration_hours * 3600 * 1000)
        
        event_dict = {
            "title": title,
            "description": description,
            "start_time": st_ms,
            "end_time": et_ms
        }
        success = send_event_to_outgoing_webhook(event_dict)
        if success:
            return f"予定「{title}」を外部SaaS（Zapier/Make/GAS）Webhookへ送信しました。"
        return "Webhook送信先URLが未設定、または送信に失敗しました。"
    except Exception as e:
        return f"予定送信エラー: {e}"
