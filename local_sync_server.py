"""
ネオ秘書くん - スマホ専用ペット端末 (Desk Pet) ＆ Agent Bridge Hub サーバー (local_sync_server.py)

PCと手元のスマートフォン（PWA / Web Bluetooth / Wi-Fi）を直接接続し、
タスクや予定、ペットの状態をリアルタイム同期するとともに、
Claude Code, Codex, Antigravity, Cursor, Aider 等のコーディングエージェントからの
「コマンド実行承認要請」をスマホへ中継・ワンタップ承認するハブ機能を提供します。
さらに、PCとスマホの双方向リンク検知（死活監視 / ヘルスチェック / 呼び出しテスト）をサポートします。
"""

import os
import json
import time
import uuid
import hmac
import secrets
import logging
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, Optional, List, Set

import database

logger = logging.getLogger(__name__)

WEB_PET_DIR = Path(__file__).parent / "web_pet"
ASSETS_DIR = Path(__file__).parent / "assets"
SERVER_PORT = 8765
TOKEN_FILE = Path(__file__).parent / ".sync_token"

# =============================================================================
# 🔐 同期サーバー認証トークン管理 (Zero-Trust Bearer Auth)
# =============================================================================

class SyncTokenManager:
    """同期サーバーのBearerトークンを生成・検証するマネージャー。

    起動時に暗号論的乱数でトークンを生成し .sync_token に保存する。
    スマホ/PWAは初回アクセス時にこのトークンを取得して以降のAPI呼び出しに
    Authorization: Bearer ヘッダーで添付する。トークン無し・不一致の
    APIリクエストは401で拒否される。
    """

    def __init__(self) -> None:
        self._token: str = ""
        self._lock = threading.Lock()
        # ペアリングモードの解除期限(epoch秒)。QR接続ダイアログ表示中のみトークン配布APIを開放する(Fail-Closed)
        self._pairing_unlocked_until: float = 0.0
        self._load_or_create()

    @property
    def pairing_open(self) -> bool:
        """トークン配布（ペアリング受付）が現在有効かどうかを返す。

        Returns:
            bool: QRペアリング期間中(解除期限以内)の場合 True。
        """
        with self._lock:
            return time.time() < self._pairing_unlocked_until

    def unlock_pairing(self, duration_sec: int = 600) -> None:
        """QR接続ダイアログ表示中等に限り、トークン配布API (/api/auth/token) を開放する。

        常時開放すると同一LAN上の第三者が GET /api/auth/token でトークンを取得できてしまうため、
        PCユーザーが明示的にペアリング操作を行っている期間のみ応答する Fail-Closed 設計とした。

        Args:
            duration_sec (int): 開放する秒数。デフォルト600秒(10分)。連続呼び出し時は期限が延長される。
        """
        with self._lock:
            self._pairing_unlocked_until = max(
                self._pairing_unlocked_until, time.time() + float(duration_sec)
            )
        logger.info(f"🔐 [SyncAuth] ペアリングモードを {duration_sec} 秒間開放しました")

    def _load_or_create(self) -> None:
        """既存トークンを読み込み、無ければ新規生成して保存する。"""
        try:
            if TOKEN_FILE.exists():
                stored = TOKEN_FILE.read_text(encoding="utf-8").strip()
                if len(stored) >= 32:
                    self._token = stored
                    logger.info("🔐 [SyncAuth] 既存の同期トークンをロードしました")
                    return
            # 32バイト=256bit の暗号論的乱数をhex化（64文字）
            self._token = secrets.token_hex(32)
            TOKEN_FILE.write_text(self._token, encoding="utf-8")
            logger.info(f"🔐 [SyncAuth] 新しい同期トークンを生成しました: {TOKEN_FILE.name}")
        except Exception as e:
            # トークンファイルI/O失敗時もセッション限定トークンで運用継続（Fail-Closedではないが可用性優先）
            self._token = secrets.token_hex(32)
            logger.warning(f"🔐 [SyncAuth] トークンファイル操作エラー、セッション限定トークンで起動: {e}")

    @property
    def token(self) -> str:
        """現在の有効トークンを返す。"""
        return self._token

    def verify(self, presented: str) -> bool:
        """提示されたトークンを定数時間比較で検証する。"""
        if not presented:
            return False
        return hmac.compare_digest(presented.strip(), self._token)


_global_token_manager: Optional[SyncTokenManager] = None


def get_sync_token_manager() -> SyncTokenManager:
    """SyncTokenManager のシングルトンを取得する。"""
    global _global_token_manager
    if _global_token_manager is None:
        _global_token_manager = SyncTokenManager()
    return _global_token_manager


# =============================================================================
# 📶 デバイスリンク検知 ＆ 死活監視マネージャー (Link Monitor)
# =============================================================================

class DeviceLinkMonitor:
    """スマホ端末とPCの接続状態（死活監視）を管理するマネージャー"""
    def __init__(self):
        self._lock = threading.Lock()
        self.last_heartbeat_time: float = 0.0
        self.client_ip: str = ""
        self.user_agent: str = ""
        self.device_name: str = "未接続"
        self.buzz_requested: bool = False
        self.first_link_notified: bool = False
        self.latest_notification: Optional[Dict[str, Any]] = None

    def record_heartbeat(self, client_ip: str, user_agent: str) -> bool:
        """スマホからの通信を検知して更新。初回接続時はTrueを返す"""
        with self._lock:
            now = time.time()
            was_offline = (now - self.last_heartbeat_time) > 12.0 or self.last_heartbeat_time == 0
            self.last_heartbeat_time = now
            self.client_ip = client_ip
            self.user_agent = user_agent
            
            # User-Agentから簡易デバイス名を特定
            ua_lower = user_agent.lower()
            if "iphone" in ua_lower:
                self.device_name = "iPhone"
            elif "ipad" in ua_lower:
                self.device_name = "iPad"
            elif "android" in ua_lower:
                self.device_name = "Android端末"
            elif "macintosh" in ua_lower:
                self.device_name = "Mac"
            elif "windows" in ua_lower:
                self.device_name = "Windows PC"
            else:
                self.device_name = "スマホブラウザ"
                
            return was_offline

    def is_connected(self) -> bool:
        """直近45秒以内に通信があったか判定（通信揺らぎ耐性）"""
        with self._lock:
            return (time.time() - self.last_heartbeat_time) <= 45.0 and self.last_heartbeat_time > 0

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            now = time.time()
            connected = (now - self.last_heartbeat_time) <= 45.0 and self.last_heartbeat_time > 0
            seconds_ago = int(now - self.last_heartbeat_time) if self.last_heartbeat_time > 0 else -1
            return {
                "connected": connected,
                "device_name": self.device_name if connected else "未接続",
                "client_ip": self.client_ip if connected else "",
                "seconds_ago": seconds_ago,
                "last_seen": int(self.last_heartbeat_time * 1000) if self.last_heartbeat_time > 0 else 0
            }

    def trigger_buzz(self) -> None:
        """PCからスマホを呼び出す（バイブレーション要求フラグON）"""
        with self._lock:
            self.buzz_requested = True

    def consume_buzz(self) -> bool:
        """スマホ側が呼び出しを検知して消費"""
        with self._lock:
            if self.buzz_requested:
                self.buzz_requested = False
                return True
            return False

    def set_notification(self, agent_name: str, title: str, message: str, reaction: str = "celebrate") -> None:
        """最新の通知を保持し、スマホへバイブレーション要求を発行"""
        with self._lock:
            self.latest_notification = {
                "id": f"notif_{uuid.uuid4().hex[:6]}",
                "agent_name": agent_name,
                "title": title,
                "message": message,
                "reaction": reaction,
                "timestamp": time.time()
            }
            self.buzz_requested = True

    def get_active_notification(self) -> Optional[Dict[str, Any]]:
        """直近60秒以内の通知を返す"""
        with self._lock:
            if self.latest_notification:
                if time.time() - self.latest_notification["timestamp"] <= 60.0:
                    return self.latest_notification
                else:
                    self.latest_notification = None
            return None


_global_link_monitor = DeviceLinkMonitor()

def get_link_monitor() -> DeviceLinkMonitor:
    return _global_link_monitor


# =============================================================================
# Agent Bridge 承認リクエスト管理キュー
# =============================================================================

class AgentBridgeRequest:
    """エージェントからの承認要請または質問・入力待ちリクエスト"""
    def __init__(
        self,
        req_type: str,  # 'approval' または 'question'
        agent_name: str,
        title: str,
        content: str = "",
        command: str = "",
        choices: Optional[List[str]] = None,
        timeout_sec: int = 180,
        requester_ip: str = ""
    ):
        self.request_id = f"req_{uuid.uuid4().hex[:8]}"
        self.req_type = req_type
        self.agent_name = agent_name
        self.title = title
        self.content = content
        self.command = command
        self.choices = choices or []
        self.created_at = time.time()
        self.timeout_at = self.created_at + timeout_sec
        self.status = "pending"  # 'pending', 'approved', 'rejected', 'answered', 'expired'
        self.decision_message = ""
        # 承認要請を作成したクライアントのIP。自己承認(RCE)防止のために記録する。
        self.requester_ip = requester_ip
        self._event = threading.Event()

    def resolve(self, decision: str, message: str = "") -> None:
        """スマホ側から意思決定・回答を受信した際に解決"""
        self.status = decision
        self.decision_message = message
        self._event.set()

    def wait(self, timeout: Optional[float] = None) -> str:
        """エージェント側が判定・回答結果を待機"""
        self._event.wait(timeout=timeout)
        if not self._event.is_set():
            self.status = "expired"
        return self.status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "type": self.req_type,
            "agent_name": self.agent_name,
            "title": self.title,
            "content": self.content,
            "command": self.command,
            "choices": self.choices,
            "created_at": self.created_at,
            "timeout_at": self.timeout_at,
            "status": self.status,
            "decision_message": self.decision_message
        }


class AgentBridgeHub:
    """エージェント承認要請および質問・入力待ちの管理ハブ（シングルトン）"""
    def __init__(self):
        self._lock = threading.RLock()
        self.pending_requests: Dict[str, AgentBridgeRequest] = {}
        self.latest_completed: Optional[Dict[str, Any]] = None
        self.history: List[Dict[str, Any]] = []

    def create_approval_request(self, agent_name: str, command: str, summary: str, details: str = "", timeout_sec: int = 180, requester_ip: str = "") -> AgentBridgeRequest:
        req = AgentBridgeRequest(
            req_type="approval",
            agent_name=agent_name,
            title=summary if summary else f"『{command}』の実行許可",
            content=details,
            command=command,
            timeout_sec=timeout_sec,
            requester_ip=requester_ip
        )
        with self._lock:
            self.pending_requests[req.request_id] = req
        logger.info(f"🤖 [Agent Bridge] 新規承認要請: {agent_name} -> '{command}' (ID: {req.request_id}, 要求元IP: {requester_ip})")
        return req

    def create_question_request(self, agent_name: str, question: str, choices: Optional[List[str]] = None, details: str = "", timeout_sec: int = 180, requester_ip: str = "") -> AgentBridgeRequest:
        req = AgentBridgeRequest(
            req_type="question",
            agent_name=agent_name,
            title=question,
            content=details,
            choices=choices or [],
            timeout_sec=timeout_sec,
            requester_ip=requester_ip
        )
        with self._lock:
            self.pending_requests[req.request_id] = req
        logger.info(f"🤖 [Agent Bridge] 新規質問・確認要請: {agent_name} -> '{question}' (選択肢: {choices})")
        return req

    def set_completed_event(self, agent_name: str, title: str, summary: str, details: str = "") -> None:
        with self._lock:
            self.latest_completed = {
                "id": f"comp_{uuid.uuid4().hex[:6]}",
                "type": "completed",
                "agent_name": agent_name,
                "title": title,
                "summary": summary,
                "details": details,
                "timestamp": time.time()
            }

    def dismiss_completed(self) -> None:
        with self._lock:
            self.latest_completed = None

    def get_latest_pending(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            now = time.time()
            # 期限切れのクリーンアップ
            expired_ids = [rid for rid, r in self.pending_requests.items() if now > r.timeout_at]
            for rid in expired_ids:
                r = self.pending_requests.pop(rid)
                r.resolve("expired")

            if not self.pending_requests:
                return None
            latest = list(self.pending_requests.values())[-1]
            return latest.to_dict()

    def get_active_event(self) -> Optional[Dict[str, Any]]:
        """スマホ画面で表示すべき最優先イベント（承認 > 質問 > 作業完了）を返す"""
        with self._lock:
            now = time.time()
            # 1. 承認または質問中の pending リクエスト
            pending = self.get_latest_pending()
            if pending:
                return pending
            
            # 2. 直近90秒以内の作業完了イベント
            if self.latest_completed:
                if now - self.latest_completed["timestamp"] <= 90.0:
                    return self.latest_completed
                else:
                    self.latest_completed = None
            return None

    def respond(self, request_id: str, decision: str, message: str = "") -> bool:
        """承認応答を処理する（後方互換ラッパー）。

        Args:
            request_id (str): 対象リクエストID。
            decision (str): 承認判定 ('approve' / 'reject' / 'answered' 等)。
            message (str): ユーザーからの添付メッセージ。

        Returns:
            bool: 処理成功の場合 True。
        """
        ok, _reason = self.respond_checked(request_id, decision, message, responder_ip=None)
        return ok

    def respond_checked(self, request_id: str, decision: str, message: str = "", responder_ip: Optional[str] = None) -> tuple:
        """承認応答を処理し、自己承認(RCE)防止チェックを行う拡張版。

        要求元IP(requester_ip)と同一IPからの応答は人間による承認とみなさず拒否する。
        これにより「攻撃者が自作した承認要請を自分で承認する」RCEチェーンを遮断する。

        Args:
            request_id (str): 対象リクエストID。
            decision (str): 承認判定 ('approve' / 'reject' / 'answered' 等)。
            message (str): ユーザーからの添付メッセージ。
            responder_ip (Optional[str]): 応答元クライアントのIPアドレス。Noneの場合チェックをスキップする。

        Returns:
            tuple[bool, str]: (処理成功可否, 理由コード)。理由コードは 'ok' / 'not_found' / 'self_approve_denied'。
        """
        with self._lock:
            req = self.pending_requests.get(request_id)
            if not req or req.status != "pending":
                return False, "not_found"
            # 自己承認防止: 承認要請を作成したクライアントと同一IPからの応答を拒否する
            if responder_ip and req.requester_ip and responder_ip == req.requester_ip:
                logger.warning(
                    f"🚫 [Security] 自己承認を検知して拒否: ID={request_id} (要求元=応答元IP: {responder_ip})"
                )
                return False, "self_approve_denied"
            req.resolve(decision, message)
            self.history.append(req.to_dict())
            del self.pending_requests[request_id]
            logger.info(f"📱 [Agent Bridge] スマホから判定・回答を受信: ID={request_id} -> {decision} (msg: {message})")
            return True, "ok"


_global_bridge_hub = AgentBridgeHub()

def get_bridge_hub() -> AgentBridgeHub:
    return _global_bridge_hub


# =============================================================================
# HTTP & API ハンドラ
# =============================================================================

class DeskPetSyncHandler(SimpleHTTPRequestHandler):
    """Desk Pet PWA用の静的ファイル配信 ＆ JSON APIハンドラ"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_PET_DIR), **kwargs)

    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        """CORS プリフライト対応"""
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def _get_bearer_token(self) -> str:
        """AuthorizationヘッダーからBearerトークンを抽出する。"""
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[len("Bearer "):].strip()
        return ""

    def _check_auth(self) -> bool:
        """Bearerトークンを検証し、不正なら401レスポンスを送信してFalseを返す。

        トークン配布用の /api/auth/token エンドポイントのみ認証不要。
        """
        token_mgr = get_sync_token_manager()
        if token_mgr.verify(self._get_bearer_token()):
            return True
        logger.warning(
            f"🚫 [SyncAuth] 認証失敗: {self.path} (IP: {self.client_address[0] if self.client_address else 'unknown'})"
        )
        try:
            self.send_response(401)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(
                {"status": "unauthorized", "message": "有効なトークンがありません。PC側の .sync_token を確認してください。"},
                ensure_ascii=False
            ).encode("utf-8"))
        except Exception:
            pass
        return False

    @staticmethod
    def _is_loopback(client_ip: str) -> bool:
        """接続元IPが同一PC内（ループバック）かどうかを判定する。

        Args:
            client_ip (str): 接続元クライアントのIPアドレス。

        Returns:
            bool: ループバックアドレスの場合 True。
        """
        return client_ip in ("127.0.0.1", "::1", "localhost")

    def do_GET(self):
        """APIエンドポイントまたは静的ファイルの処理"""
        client_ip = self.client_address[0] if self.client_address else "unknown"
        user_agent = self.headers.get("User-Agent", "")

        # 0. トークン配布 (GET /api/auth/token) — ペアリングモード中のみ応答 (Fail-Closed)
        # ※ QR接続ダイアログ表示中(最大10分)だけトークンを配布する。
        #   常時開放だと同一LAN上の第三者が GET /api/auth/token でトークンを取得でき、
        #   承認API等への不正アクセスにつながるため、明示的なペアリング操作中のみ応答する。
        if self.path == "/api/auth/token":
            tm = get_sync_token_manager()
            if not tm.pairing_open:
                logger.warning(f"🚫 [SyncAuth] ペアリング非開放中のトークン要求を拒否 (IP: {client_ip})")
                self.send_response(403)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(
                    {"status": "forbidden", "message": "ペアリングモードが閉じています。PC側でQR接続ダイアログを開いてください。"},
                    ensure_ascii=False
                ).encode("utf-8"))
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "token": tm.token}, ensure_ascii=False).encode("utf-8"))
            return

        # 1. 状態同期API (GET /api/status)
        if self.path == "/api/status":
            if not self._check_auth():
                return
            monitor = get_link_monitor()
            was_offline = monitor.record_heartbeat(client_ip, user_agent)
            if was_offline:
                logger.info(f"📱 [Link Monitor] スマホ端末が接続されました: {monitor.device_name} ({client_ip})")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._set_cors_headers()
            self.end_headers()
            
            try:
                # 2秒キャッシュによりDBの過負荷を防止
                now = time.time()
                global _last_db_cache_time, _cached_tasks_data, _cached_events_data
                if '_last_db_cache_time' not in globals() or (now - _last_db_cache_time) > 2.0:
                    tasks = database.get_tasks(status="todo", limit=20)
                    events = database.get_upcoming_events(days=3)
                    _cached_tasks_data = [
                        {"id": t.id, "title": t.title, "priority": t.priority, "due_date": t.due_date}
                        for t in tasks
                    ]
                    _cached_events_data = [
                        {"id": e.id, "title": e.title, "start_time": e.start_time, "description": e.description}
                        for e in events
                    ]
                    _last_db_cache_time = now

                hub = get_bridge_hub()
                pending_req = hub.get_latest_pending()
                should_buzz = monitor.consume_buzz()
                
                # ポモドーロ状態の取得
                gui = get_gui_instance()
                pomodoro_active = getattr(gui, "pomodoro_active", False) if gui else False
                pomodoro_is_break = getattr(gui, "pomodoro_is_break", False) if gui else False
                pomodoro_sec = getattr(gui, "pomodoro_remaining_seconds", 0) if gui else 0
                pomodoro_label = "☕ 休憩中" if pomodoro_is_break else "🍅 集中中"
                
                pet_state = "alarm_ask" if pending_req else ("focus" if (pomodoro_active and not pomodoro_is_break) else "idle")
                default_msg = "ボス！エージェントからコマンド実行の許可要請が届いています！" if pending_req else ("集中タイムです！ボス、一緒に頑張りましょう！🔥" if (pomodoro_active and not pomodoro_is_break) else "ボス、いつもお疲れ様です！スマホからも見守っていますよ！")
                
                from suggest_engine import get_suggestion_engine
                suggest_eng = get_suggestion_engine()
                suggestions_data = suggest_eng.generate_suggestions()
                
                from character_manager import get_character_manager
                char_mgr = get_character_manager()
                char_info = char_mgr.get_current_character()
                
                active_event = hub.get_active_event()
                active_notification = monitor.get_active_notification()
                
                # ペット状態の決定
                if active_event:
                    if active_event.get("type") == "approval":
                        pet_state = "alarm_ask"
                    elif active_event.get("type") == "question":
                        pet_state = "alarm_ask"
                    elif active_event.get("type") == "completed":
                        pet_state = "celebrate"
                    else:
                        pet_state = "idle"
                else:
                    pet_state = "focus" if (pomodoro_active and not pomodoro_is_break) else "idle"
                
                # 習慣 ＆ 草ヒートマップデータ
                # ※ database はモジュール先頭で import 済み。関数内 import を置くと
                #    Python が database をローカル変数扱いし、上記の get_tasks 等の参照が
                #    UnboundLocalError となるため、ここでの再 import は禁止。
                habits_data = database.get_habits_with_status()
                heatmap_data = database.get_habit_heatmap_data(days=70)
                bond_info = char_mgr.get_bond_info()

                payload = {
                    "status": "ok",
                    "pet_state": pet_state,
                    "message": default_msg,
                    "character": {
                        "id": char_info["id"],
                        "name": char_info["name"],
                        "title": char_info["title"],
                        "emoji": char_info["emoji"],
                        "all": char_mgr.get_all_characters()
                    },
                    "bond": bond_info,
                    "habits": habits_data,
                    "habit_heatmap": heatmap_data,
                    "pending_approval": pending_req,
                    "active_event": active_event,
                    "latest_notification": active_notification,
                    "tasks": _cached_tasks_data,
                    "events": _cached_events_data,
                    "suggestions": suggestions_data,
                    "suggest_config": suggest_eng.config,
                    "pomodoro": {
                        "active": pomodoro_active,
                        "is_break": pomodoro_is_break,
                        "remaining_seconds": pomodoro_sec,
                        "total_seconds": getattr(gui, "pomodoro_total_seconds", 25 * 60) if gui else 25 * 60,
                        "mode_label": pomodoro_label
                    },
                    "buzz": should_buzz,
                    "server_time": int(now * 1000)
                }
                self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                logger.error(f"Status API エラー: {e}")
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))

        # 2. PC側ダイアログ用 リンク状態確認API (GET /api/link_status)
        elif self.path == "/api/link_status":
            if not self._check_auth():
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._set_cors_headers()
            self.end_headers()
            
            monitor = get_link_monitor()
            self.wfile.write(json.dumps(monitor.get_status(), ensure_ascii=False).encode("utf-8"))

        # 3. 承認待ち確認 (GET /api/agent/pending)
        elif self.path == "/api/agent/pending":
            if not self._check_auth():
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._set_cors_headers()
            self.end_headers()
            hub = get_bridge_hub()
            req = hub.get_latest_pending()
            self.wfile.write(json.dumps({"status": "ok", "pending": req}, ensure_ascii=False).encode("utf-8"))

        # 3.5. LLMプロバイダ・モデル一覧API (GET /api/llm/presets)
        elif self.path == "/api/llm/presets":
            if not self._check_auth():
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._set_cors_headers()
            self.end_headers()
            from llm_factory import get_llm_factory
            factory = get_llm_factory()
            presets = factory.list_presets(only_configured=True)
            self.wfile.write(json.dumps({"status": "ok", "presets": presets}, ensure_ascii=False).encode("utf-8"))

        # 4. アセット画像配信 (GET /assets/...) — 静的画像は認証不要（PWA表示用）
        elif self.path.startswith("/assets/"):
            filename = self.path[len("/assets/"):].split("?")[0]
            # パストラバーサル対策: 相対参照・ドライブ指定を含むリクエストは拒否
            if ".." in filename or filename.startswith("/") or ":" in filename:
                logger.warning(f"🚫 [Security] 不正なアセットパス要求を拒否: {filename}")
                self.send_error(404, "Invalid asset path")
                return
            asset_file = ASSETS_DIR / filename
            if not asset_file.is_file():
                # mascot_ プレフィックスの有無を相互フォールバック
                if filename.startswith("mascot_"):
                    asset_file = ASSETS_DIR / filename[len("mascot_"):]
                else:
                    asset_file = ASSETS_DIR / f"mascot_{filename}"

            if asset_file.is_file():
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-cache")
                self._set_cors_headers()
                self.end_headers()
                with open(asset_file, "rb") as f:
                    self.wfile.write(f.read())
            else:
                logger.warning(f"アセットが見つかりません: {filename}")
                self.send_error(404, f"Asset not found: {filename}")

        else:
            super().do_GET()

    def do_POST(self):
        """スマホ側からのアクションおよび外部エージェントからの要請受信"""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        client_ip = self.client_address[0] if self.client_address else "unknown"
        user_agent = self.headers.get("User-Agent", "")

        # 全POST APIにBearer認証を強制（Zero-Trust）
        if not self._check_auth():
            return

        # エージェント発信系API（承認要請・通知の作成）は同一PC内(localhost)からの呼び出しのみ許可する。
        # 外部コーディングエージェント(Claude Code等)は localhost 経由で利用するため影響なし。
        # これにより、LAN上の攻撃者がトークンを入手しても ask を作成できず、
        # 「自作リクエスト → 自己承認」の RCE チェーンが成立しなくなる (要求元/承認者の分離)。
        AGENT_ONLY_PATHS = ("/api/agent/ask", "/api/agent/ask_input", "/api/agent/notify")
        if self.path in AGENT_ONLY_PATHS and not self._is_loopback(client_ip):
            logger.warning(f"🚫 [Security] 非ループバック({client_ip})からのエージェントAPI呼び出しを拒否: {self.path}")
            self.send_response(403)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(
                {"status": "error", "message": "Agent APIs are restricted to localhost connections."},
                ensure_ascii=False
            ).encode("utf-8"))
            return

        # 1. 外部エージェントからの承認要請 (POST /api/agent/ask)
        if self.path == "/api/agent/ask":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._set_cors_headers()
            self.end_headers()
            
            try:
                data = json.loads(body.decode("utf-8"))
                agent_name = data.get("agent_name", "AI Agent")
                command = data.get("command", "")
                summary = data.get("summary", "コマンドの実行許可を求めています")
                details = data.get("details", "")
                timeout = int(data.get("timeout", 180))
                
                hub = get_bridge_hub()
                req = hub.create_approval_request(agent_name, command, summary, details, timeout_sec=timeout, requester_ip=client_ip)
                get_link_monitor().trigger_buzz()
                
                if data.get("wait_decision", True):
                    decision = req.wait(timeout=timeout)
                    self.wfile.write(json.dumps({
                        "status": "success",
                        "request_id": req.request_id,
                        "decision": decision,
                        "message": req.decision_message
                    }, ensure_ascii=False).encode("utf-8"))
                else:
                    self.wfile.write(json.dumps({
                        "status": "queued",
                        "request_id": req.request_id
                    }, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                logger.error(f"Agent Ask API エラー: {e}")
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))

        # 1.5. 外部エージェントからの質問・選択肢回答要請 (POST /api/agent/ask_input)
        elif self.path == "/api/agent/ask_input":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._set_cors_headers()
            self.end_headers()
            
            try:
                data = json.loads(body.decode("utf-8"))
                agent_name = data.get("agent_name", "AI Agent")
                question = data.get("question", "確認事項があります")
                choices = data.get("choices", [])
                details = data.get("details", "")
                timeout = int(data.get("timeout", 180))
                
                hub = get_bridge_hub()
                req = hub.create_question_request(agent_name, question, choices, details, timeout_sec=timeout, requester_ip=client_ip)
                get_link_monitor().trigger_buzz()
                
                # PCペットのメッセージとリアクション
                gui = get_gui_instance()
                if gui:
                    gui.post_action(gui.show_pc_pet)
                    gui.post_action(gui.update_message, f"【{agent_name}】{question}")
                    gui.post_action(gui.set_pet_state, "alarm_ask", 6000)
                
                if data.get("wait_decision", True):
                    decision = req.wait(timeout=timeout)
                    self.wfile.write(json.dumps({
                        "status": "success",
                        "request_id": req.request_id,
                        "decision": decision,
                        "answer": req.decision_message
                    }, ensure_ascii=False).encode("utf-8"))
                else:
                    self.wfile.write(json.dumps({
                        "status": "queued",
                        "request_id": req.request_id
                    }, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                logger.error(f"Agent Ask Input API エラー: {e}")
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))

        # 2. スマホからの意思決定・回答送信 (POST /api/agent/respond)
        elif self.path == "/api/agent/respond":
            get_link_monitor().record_heartbeat(client_ip, user_agent)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._set_cors_headers()
            self.end_headers()
            
            try:
                data = json.loads(body.decode("utf-8"))
                request_id = data.get("request_id")
                decision = data.get("decision", "approve")
                message = data.get("message", "")
                
                hub = get_bridge_hub()
                success, reason = hub.respond_checked(request_id, decision, message, responder_ip=client_ip)
                if success:
                    status_payload: Dict[str, Any] = {"status": "success"}
                elif reason == "self_approve_denied":
                    status_payload = {
                        "status": "error",
                        "message": "自己承認は禁止されています（要求元と同じ端末からの承認は無効）"
                    }
                else:
                    status_payload = {"status": "not_found", "message": "対象のリクエストが見つかりません"}
                self.wfile.write(json.dumps(status_payload, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                logger.error(f"Agent Respond API エラー: {e}")
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))

        # 2.3. スマホからの作業完了カード閉じる (POST /api/agent/dismiss_completed)
        elif self.path == "/api/agent/dismiss_completed":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._set_cors_headers()
            self.end_headers()
            get_bridge_hub().dismiss_completed()
            self.wfile.write(json.dumps({"status": "success"}).encode("utf-8"))

        # 2.5. 外部エージェント(Codex/Claude Code)からの作業完了・イベント通知 (POST /api/agent/notify)
        elif self.path == "/api/agent/notify":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._set_cors_headers()
            self.end_headers()
            
            try:
                data = json.loads(body.decode("utf-8"))
                agent_name = data.get("agent_name", "外部AI")
                title = data.get("title", "作業完了通知")
                message = data.get("message", "")
                details = data.get("details", "")
                pet_reaction = data.get("reaction", "celebrate")
                
                logger.info(f"🤖 [Agent Bridge Notify] {agent_name}から通知受信: {title} - {message}")
                
                # BridgeHubへ完了イベントを登録（リッチカード表示用）
                hub = get_bridge_hub()
                hub.set_completed_event(agent_name, title, message, details)
                
                # PCペットのリアクションとメッセージ更新
                gui = get_gui_instance()
                if gui:
                    gui.post_action(gui.show_pc_pet)
                    full_text = f"【{agent_name}】{title}\n{message}" if message else f"【{agent_name}】{title}"
                    gui.post_action(gui.update_message, full_text)
                    gui.post_action(gui.set_pet_state, pet_reaction, 6000)
                
                # スマホDesk Petへ最新通知をセット（自動でbuzz要求も発行）
                get_link_monitor().set_notification(agent_name, title, message, pet_reaction)
                
                self.wfile.write(json.dumps({
                    "status": "success",
                    "agent_name": agent_name,
                    "reaction": pet_reaction
                }, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                logger.error(f"Agent Notify API エラー: {e}")
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))

        # 3. PCからのスマホ呼び出しテスト (POST /api/test_buzz)
        elif self.path == "/api/test_buzz":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._set_cors_headers()
            self.end_headers()
            
            get_link_monitor().trigger_buzz()
            logger.info("📲 [Link Monitor] PCからスマホへ呼び出し信号(Buzz)を送信しました")
            self.wfile.write(json.dumps({"status": "buzz_triggered"}, ensure_ascii=False).encode("utf-8"))

        # 4. 通常のDesk Petアクション (POST /api/action)
        elif self.path == "/api/action":
            get_link_monitor().record_heartbeat(client_ip, user_agent)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._set_cors_headers()
            self.end_headers()
            
            try:
                data = json.loads(body.decode("utf-8"))
                action = data.get("action")
                
                if action == "complete_task":
                    task_id = data.get("task_id")
                    if task_id:
                        database.complete_task(int(task_id))
                        logger.info(f"📱 スマホ側からタスク完了を受信: TaskID={task_id}")
                        self.wfile.write(json.dumps({"status": "success", "task_id": task_id}).encode("utf-8"))
                        return
                elif action == "toggle_habit":
                    habit_id = data.get("habit_id")
                    if habit_id:
                        is_done = database.toggle_habit_log(int(habit_id))
                        # 親愛度XP加算 (+10 XP)
                        if is_done:
                            from character_manager import get_character_manager
                            get_character_manager().add_bond_xp(10)
                            gui = get_gui_instance()
                            if gui and hasattr(gui, 'animator'):
                                gui.post_action(gui.animator.trigger_reaction, "task_complete")
                        logger.info(f"📱 スマホ側から習慣トグルを受信: HabitID={habit_id}, IsDone={is_done}")
                        self.wfile.write(json.dumps({"status": "success", "habit_id": habit_id, "is_done": is_done}).encode("utf-8"))
                        return
                elif action == "add_habit":
                    title = data.get("title", "").strip()
                    emoji = data.get("emoji", "🌱")
                    if title:
                        from database import Habit
                        h_id = database.create_habit(Habit(title=title, emoji=emoji))
                        logger.info(f"📱 スマホ側から習慣作成を受信: ID={h_id}, Title={title}")
                        self.wfile.write(json.dumps({"status": "success", "habit_id": h_id}).encode("utf-8"))
                        return
                elif action == "start_pomodoro":
                    gui = get_gui_instance()
                    if gui:
                        mins = int(data.get("minutes", 25))
                        gui.post_action(gui.start_pomodoro, mins)
                        logger.info(f"📱 スマホ側からポモドーロ開始を受信: {mins}分")
                        self.wfile.write(json.dumps({"status": "success", "action": "start_pomodoro"}).encode("utf-8"))
                        return
                elif action == "stop_pomodoro":
                    gui = get_gui_instance()
                    if gui:
                        gui.post_action(gui.stop_pomodoro)
                        logger.info("📱 スマホ側からポモドーロ停止を受信")
                        self.wfile.write(json.dumps({"status": "success", "action": "stop_pomodoro"}).encode("utf-8"))
                        return
                elif action == "show_pc_pet":
                    gui = get_gui_instance()
                    if gui:
                        gui.post_action(gui.show_pc_pet)
                        logger.info("📱 スマホ側からPCペット再表示要求を受信")
                        self.wfile.write(json.dumps({"status": "success", "action": "show_pc_pet"}).encode("utf-8"))
                        return
                elif action == "switch_character":
                    char_id = data.get("character_id", "hisho")
                    gui = get_gui_instance()
                    if gui:
                        gui.post_action(gui.switch_character_skin, char_id)
                    else:
                        from character_manager import get_character_manager
                        get_character_manager().set_character(char_id)
                    logger.info(f"📱 スマホ側からキャラクタースキン変更を受信: {char_id}")
                    self.wfile.write(json.dumps({"status": "success", "character_id": char_id}).encode("utf-8"))
                    return
                elif action == "toggle_suggest_source":
                    source_key = data.get("source_key")
                    enabled = data.get("enabled", True)
                    from suggest_engine import get_suggestion_engine
                    get_suggestion_engine().toggle_source(source_key, enabled)
                    logger.info(f"📱 スマホ側からサジェスト設定変更を受信: {source_key}={enabled}")
                    self.wfile.write(json.dumps({"status": "success", "source_key": source_key, "enabled": enabled}).encode("utf-8"))
                    return
                elif action == "ping_test":
                    logger.info(f"📶 スマホからPingテスト受信 ({client_ip})")
                    self.wfile.write(json.dumps({"status": "pong", "server_time": int(time.time() * 1000)}).encode("utf-8"))
                    return
                        
                self.wfile.write(json.dumps({"status": "unknown_action"}).encode("utf-8"))
            except Exception as e:
                logger.error(f"Action API エラー: {e}")
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        """標準出力のノイズを抑えるカスタムロガー"""
        pass


# グローバルGUI参照
_global_gui_instance = None

def set_gui_instance(gui) -> None:
    global _global_gui_instance
    _global_gui_instance = gui

def get_gui_instance():
    return _global_gui_instance


class LocalSyncServer:
    """バックグラウンドで稼働するローカル同期サーバー"""
    
    def __init__(self, port: int = SERVER_PORT):
        self.port = port
        self.httpd = None
        self.thread = None

    def start(self, gui=None):
        """バックグラウンドスレッドでサーバーを起動"""
        if gui:
            set_gui_instance(gui)
        try:
            self.httpd = ThreadingHTTPServer(("0.0.0.0", self.port), DeskPetSyncHandler)
            self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.thread.start()
            logger.info(f"📱 [Agent Bridge Hub] Desk Pet 同期サーバーが起動しました: http://localhost:{self.port} (LAN/Bluetooth対応)")
        except Exception as e:
            logger.warning(f"Desk Pet 同期サーバーの起動をスキップしました（ポート競合など）: {e}")

    def stop(self):
        """サーバーを停止"""
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            logger.info("Desk Pet 同期サーバーを停止しました")


# シングルトン
_global_sync_server = None

def get_sync_server(gui=None) -> LocalSyncServer:
    global _global_sync_server
    if _global_sync_server is None:
        _global_sync_server = LocalSyncServer()
    if gui:
        set_gui_instance(gui)
    return _global_sync_server
