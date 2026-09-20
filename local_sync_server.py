"""
ネオ秘書くん - スマホ専用ペット端末 (Desk Pet) ＆ Agent Bridge Hub サーバー (local_sync_server.py)

PCと手元のスマートフォン（PWA / Web Bluetooth / Wi-Fi）を直接接続し、
タスクや予定、ペットの状態をリアルタイム同期するとともに、
Claude Code, Codex, Antigravity, Cursor, Aider 等のコーディングエージェントからの
「コマンド実行承認要請」をスマホへ中継・ワンタップ承認するハブ機能を提供します。
さらに、PCとスマホの双方向リンク検知（死活監視 / ヘルスチェック / 呼び出しテスト）をサポートします。
"""

import os
import sys
import json
import time
import uuid
import hmac
import socket
import secrets
import logging
import threading
from typing import Any, Dict, Optional
from datetime import datetime
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler


class QuietThreadingHTTPServer(ThreadingHTTPServer):
    """クライアント切断時のトレースバック出力を抑制するHTTPサーバー。

    PWA のポーリング中にスマホ側が画面を閉じる等で発生する
    ``ConnectionAbortedError`` (WinError 10053) や ``ConnectionResetError``
    は日常的な切断であり、DEBUG レベルに格下げして起動ログのノイズを
    排除する。それ以外の予期しない例外は従来どおり WARNING で出力する。
    """

    def handle_error(self, request, client_address):
        """リクエスト処理中の例外をログレベルを分けて記録する。

        Args:
            request: リクエストオブジェクト (ソケット等)。
            client_address: クライアントのアドレス (host, port)。
        """
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
            logger.debug(
                "クライアント切断 (%s:%s): %s",
                client_address[0],
                client_address[1],
                type(exc).__name__,
            )
        else:
            logger.warning(
                "リクエスト処理中に例外 (%s:%s): %s",
                client_address[0],
                client_address[1],
                exc,
                exc_info=True,
            )
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from urllib.parse import urlsplit, parse_qs
from auth_rate_limiter import get_auth_rate_limiter


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

import database
import sync_config
from web_assets import guess_asset_content_type, resolve_asset_path
from update_checker import get_update_status
from sync_dtos import validate_status_payload, validate_tasks_view_response
from api_context import ApiContext
import api_tasks
import api_agent_bridge
import api_calendar
import api_devices
from server_watchdog import ServerWatchdog
from agent_fsm import agent_fsm

logger = logging.getLogger(__name__)

WEB_PET_DIR = Path(__file__).parent / "web_pet"
ASSETS_DIR = Path(__file__).parent / "assets"
# 待受ポートは sync_config を唯一の情報源とする (QRダイアログ/Tailscale起動と一元化)
SERVER_PORT = sync_config.SERVER_PORT
TOKEN_FILE = Path(__file__).parent / ".sync_token"

_global_gui_instance = None


def set_gui_instance(gui) -> None:
    """GUIインスタンスを保持し、Human-in-the-Loop 端末承認ダイアログコールバックを設定する。"""
    global _global_gui_instance
    _global_gui_instance = gui
    if gui is not None:
        def _approval_cb(device_name: str, client_ip: str) -> bool:
            try:
                from ui.device_approval_dialog import ask_device_approval_gui
                return ask_device_approval_gui(gui, device_name, client_ip, timeout_sec=30)
            except Exception as err:
                logger.error(f"端末承認ダイアログ呼び出しエラー: {err}")
                return False

        get_sync_token_manager().set_device_approval_callback(_approval_cb)
        logger.info("🔐 [SyncAuth] Human-in-the-Loop 端末接続承認コールバックを登録しました")


def get_gui_instance():
    """登録されているGUIインスタンスを取得する。"""
    return _global_gui_instance



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
        # 🛡️ P0-2: 未承認外部端末接続時の Human-in-the-Loop 承認コールバック
        self._device_approval_callback = None
        self._load_or_create()

    def set_device_approval_callback(self, callback) -> None:
        """未承認端末接続時の Human-in-the-Loop 承認コールバックを登録する。

        Args:
            callback: Callable[[str, str], bool] - (device_name, client_ip) を受け取り、
                      ユーザー承認時は True、拒否時は False を返す関数。
        """
        with self._lock:
            self._device_approval_callback = callback

    @property
    def device_approval_callback(self):
        """登録されている端末接続承認コールバックを返す。"""
        with self._lock:
            return self._device_approval_callback

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

    def close_pairing(self) -> None:
        """QRペアリング待機を即座に終了する (ワンタイム化・P0-2対策)。"""
        with self._lock:
            self._pairing_unlocked_until = 0.0
        logger.info("🔐 [SyncAuth] ペアリングモードを終了（クローズ）しました")

    def _save_token(self) -> None:
        """トークンを .sync_token へアトミックに書き込む。

        読み取りとの競合を防ぐため、一時ファイルに書き込んでからリネームする。
        """
        try:
            tmp = TOKEN_FILE.with_suffix(".sync_token.tmp")
            tmp.write_text(self._token, encoding="utf-8")
            tmp.replace(TOKEN_FILE)
        except Exception as e:
            logger.warning(f".sync_token のアトミック書き込みに失敗（直接書き込みにフォールバック）: {e}")
            TOKEN_FILE.write_text(self._token, encoding="utf-8")

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
            self._save_token()
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

    def regenerate(self) -> str:
        """既存トークンを無効化し、新しいトークンを生成・保存する。

        設定画面の「スマホ連携 全解除（トークン再生成）」ボタンから呼び出される
        ワンクリック操作。トークンを差し替えることで、スマホ側に保存された旧
        トークンによる全セッションを即座に無効化する（セッション全破棄 /
        紛失・売却・リセット時のセキュリティ対処）。
        さらに、ゼロトラスト端末台帳（devices テーブル）の全個別端末も一括失効させる (P0-1 対策)。

        Returns:
            str: 新しく生成された同期トークン (64文字hex)。
        """
        with self._lock:
            self._token = secrets.token_hex(32)
            self._save_token()
        try:
            database.revoke_all_devices()
        except Exception as e:
            logger.error(f"全端末一括失効エラー (グローバルトークン再生成は完了): {e}")
        logger.warning(
            "🔐 [SyncAuth] 同期トークンを再生成し、全接続端末を一括失効しました。"
            "既存のスマホ接続セッションはすべて無効になります"
        )
        return self._token


_global_token_manager: Optional[SyncTokenManager] = None


def get_sync_token_manager() -> SyncTokenManager:
    """SyncTokenManager のシングルトンを取得する。"""
    global _global_token_manager
    if _global_token_manager is None:
        _global_token_manager = SyncTokenManager()
    return _global_token_manager



# 30秒TTL 習慣＆70日ヒートマップキャッシュ変数
_last_habit_cache_time = 0.0
_cached_habits_data = []
_cached_heatmap_data = []

def invalidate_habit_cache() -> None:
    """習慣データおよび70日ヒートマップのインメモリTTLキャッシュを無効化する。"""
    global _last_habit_cache_time
    _last_habit_cache_time = 0.0


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
        """直近10分以内の通知を返す。

        2026-08-31 バグ修正: 従来の60秒TTLでは、スマホが画面OFF/バックグラウンド中に
        通知を受け取った場合（音は鳴るが表示は不可視）、復帰時の再取得までに60秒を
        超えるとサーバー側で破棄済みとなり通知が永久に表示されない不具合があった。
        10分に延長し、復帰時の再表示を可能にする。二重表示はクライアント側の
        sessionStorage 永続化された _lastNotifKey により防止する。
        """
        with self._lock:
            if self.latest_notification:
                if time.time() - self.latest_notification["timestamp"] <= 600.0:
                    return self.latest_notification
                else:
                    self.latest_notification = None
            return None

    def set_easter_egg_event(self, stage: int, daily_count: int, attempt_count: int, message: str = "") -> None:
        """最新のイースターエッグ発火イベントを保持し、スマホへ演出要求を発行"""
        with self._lock:
            self.latest_easter_egg_event = {
                "id": f"ee_{uuid.uuid4().hex[:6]}",
                "stage": stage,
                "daily_count": daily_count,
                "attempt_count": attempt_count,
                "message": message,
                "timestamp": time.time()
            }
            self.buzz_requested = True

    def get_active_easter_egg_event(self) -> Optional[Dict[str, Any]]:
        """直近25秒以内のイースターエッグイベントを返す"""
        with self._lock:
            if hasattr(self, 'latest_easter_egg_event') and self.latest_easter_egg_event:
                if time.time() - self.latest_easter_egg_event["timestamp"] <= 25.0:
                    return self.latest_easter_egg_event
                else:
                    self.latest_easter_egg_event = None
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
        requester_ip: str = "",
        risk_level: str = "prompt",
        agent_type: str = "generic",
        summary: str = "",
        safety_level: Optional[str] = None
    ):
        self.request_id = f"req_{uuid.uuid4().hex[:8]}"
        self.req_type = req_type
        self.agent_name = agent_name
        self.agent_type = agent_type
        self.title = title
        self.summary = summary or title
        self.safety_level = safety_level
        self.content = content
        self.command = command
        self.choices = choices or []
        self.risk_level = risk_level
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
            "agent_type": self.agent_type,
            "title": self.title,
            "summary": self.summary,
            "safety_level": self.safety_level,
            "content": self.content,
            "command": self.command,
            "choices": self.choices,
            "risk_level": self.risk_level,
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

    def create_approval_request(
        self,
        agent_name: str,
        command: str,
        summary: str,
        details: str = "",
        timeout_sec: int = 180,
        requester_ip: str = "",
        risk_level: str = "prompt",
        agent_type: str = "generic",
        safety_level: Optional[str] = None
    ) -> AgentBridgeRequest:
        req = AgentBridgeRequest(
            req_type="approval",
            agent_name=agent_name,
            title=summary if summary else f"『{command}』の実行許可",
            summary=summary,
            content=details,
            command=command,
            timeout_sec=timeout_sec,
            requester_ip=requester_ip,
            risk_level=risk_level,
            agent_type=agent_type,
            safety_level=safety_level
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
            # 期限切れおよび解決済み（pendingでない）リクエストのクリーンアップ
            stale_ids = []
            for rid, r in list(self.pending_requests.items()):
                if now > r.timeout_at:
                    stale_ids.append((rid, "expired"))
                elif r.status != "pending":
                    stale_ids.append((rid, "resolved"))

            for rid, reason in stale_ids:
                r = self.pending_requests.pop(rid, None)
                if r:
                    if reason == "expired" and r.status == "pending":
                        r.resolve("expired")
                    self.history.append(r.to_dict())

            # status == 'pending' の真の保留中リクエストのみを抽出
            active_pendings = [r for r in self.pending_requests.values() if r.status == "pending"]
            if not active_pendings:
                return None
            return active_pendings[-1].to_dict()

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

    def respond_checked(self, request_id: str, decision: str, message: str = "", responder_ip: Optional[str] = None) -> tuple:
        """承認応答を処理し、自己承認(RCE)防止チェックと期限切れ検知を行う拡張版。

        要求元IP(requester_ip)と同一IPからの応答は人間による承認とみなさず拒否する。
        これにより「攻撃者が自作した承認要請を自分で承認する」RCEチェーンを遮断する。
        また、タイムアウト（timeout_at）を超過したリクエストは期限切れとして拒否する。

        Args:
            request_id (str): 対象リクエストID。
            decision (str): 承認判定 ('approve' / 'reject' / 'answered' 等)。
            message (str): ユーザーからの添付メッセージ。
            responder_ip (Optional[str]): 応答元クライアントのIPアドレス。Noneの場合チェックをスキップする。

        Returns:
            tuple[bool, str]: (処理成功可否, 理由コード)。理由コードは 'ok' / 'not_found' / 'self_approve_denied' / 'expired'。
        """
        with self._lock:
            req = self.pending_requests.get(request_id)
            if not req:
                # 冪等性チェック: 既に history に存在し、同一の判定であれば成功（already_resolved）を返す
                for hist in reversed(self.history):
                    if hist.get("request_id") == request_id:
                        prev_status = hist.get("status")
                        is_match = (
                            prev_status == decision
                            or (decision in ("approve", "approved") and prev_status in ("approve", "approved"))
                            or (decision in ("reject", "deny") and prev_status in ("reject", "deny"))
                        )
                        if is_match:
                            logger.info(
                                f"🔄 [Agent Bridge] 重複リクエストの冪等処理: ID={request_id} -> {decision}"
                            )
                            return True, "already_resolved"
                return False, "not_found"
            # 期限切れ検知: timeout_at を超過している場合は拒否する
            # wait_decision=False の非同期質問でもタイムアウト後にタップされるとここで検知される
            if req.timeout_at is not None and time.time() > req.timeout_at:
                logger.warning(
                    f"⏰ 期限切れリクエストの応答を拒否: ID={request_id} (status={req.status})"
                )
                req.status = "expired"
                return False, "expired"
            if req.status != "pending":
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

# =============================================================================
# 🗂️ /api/action アクションディスパッチテーブル (P2③ 分割リファクタ)
# =============================================================================
# 各ハンドラは handler(ctx: ApiContext) -> bool 署名を持つモジュール関数。
# True: レスポンス書き込み済み (パラメータ欠落時は明示エラーJSONを書き込む)。
# False: 例外等で応答を書き込めなかった場合のみ (呼び出し元は無応答のまま返る)。

ACTION_HANDLERS_TASKS = {
    "complete_task": api_tasks.action_complete_task,
    "reopen_task": api_tasks.action_reopen_task,
    "toggle_habit": api_tasks.action_toggle_habit,
    "add_habit": api_tasks.action_add_habit,
    "quick_add_task": api_tasks.action_quick_add_task,
    "transcribe_voice": api_tasks.action_transcribe_voice,
    "update_task": api_tasks.action_update_task,
    "delete_task": api_tasks.action_delete_task,
    "list_task_lists": api_tasks.action_list_task_lists,
    "get_tasks_view": api_tasks.action_get_tasks_view,
}

ACTION_HANDLERS_DEVICE = {
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
}

# 全アクションの統合ディスパッチテーブル
ACTION_HANDLERS = {**ACTION_HANDLERS_TASKS, **ACTION_HANDLERS_DEVICE}

# POST パス系APIのディスパッチテーブル (P2③ 分割リファクタ)
POST_PATH_HANDLERS = {
    "/api/agent/ask": api_agent_bridge.handle_agent_ask,
    "/api/agent/ask_input": api_agent_bridge.handle_agent_ask_input,
    "/api/agent/respond": api_agent_bridge.handle_agent_respond,
    "/api/agent/dismiss_completed": api_agent_bridge.handle_agent_dismiss_completed,
    "/api/agent/notify": api_agent_bridge.handle_agent_notify,
    "/api/test_buzz": api_agent_bridge.handle_test_buzz,
    "/api/webhook/calendar": api_calendar.handle_webhook_calendar,
    "/api/webhook/task": api_calendar.handle_webhook_task,
}

# GET パス系APIのディスパッチテーブル (P1-B 第一歩: api_devices モジュールへ委譲)
# 各ハンドラは handler(ctx: ApiContext) -> bool 署名 (True: レスポンス書き込み済み)。
# Bearer 認証 (_check_auth) は do_GET 側のディスパッチ箇所で適用する。
GET_PATH_HANDLERS = {
    "/api/devices": api_devices.handle_get_devices,
}


class DeskPetSyncHandler(SimpleHTTPRequestHandler):
    """Desk Pet PWA用の静的ファイル配信 ＆ JSON APIハンドラ"""
    
    # 🛡️ P0-3 (Slowloris対策): ソケット受信タイムアウトを10秒に明示設定し、スレッド枯渇を防止
    timeout = 10.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_PET_DIR), **kwargs)

    def _set_cors_headers(self):
        """CORS 許可ヘッダーを一切発行しない (ゼロトラスト強化・2026-09-02確定)。

        PWA は本サーバーと同一オリジンで配信されるため CORS 許可は本来不要。
        かつての ``Access-Control-Allow-Origin: *`` は、スマホのブラウザで開いた
        任意の Web サイトから GET /api/status 等をクロスオリジン読み取りできる
        情報漏洩経路になるため廃止した。

        さらに「Origin authority == Host ヘッダー」のエコー方式も廃止した:
        DNS リバインディング (evil.com → PCのIP解決) ではブラウザが
        Origin と Host の両方に evil.com を乗せるためエコー方式は迂回可能。
        同一オリジンは許可ヘッダーなしで動作するため、発行ゼロが最も安全。
        本メソッドは呼び出し互換のため残置する no-op であり、将来クロス
        オリジン連携が必要になった場合は明示的なオリジン許可リスト方式で
        実装すること (ワイルドカード・単純エコーの再導入は禁止)。
        """
        return

    def end_headers(self):
        """ブラウザ・PWAの強力キャッシュを回避し、常に最新ファイルを配信する"""
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_OPTIONS(self):
        """CORS プリフライト対応"""
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def _handle_auth_token(self, client_ip: str, user_agent: str) -> None:
        """トークン配布 (GET /api/auth/token) を処理する Seam。

        - ペアリング開放中 or 同一PC内（ループバック）のみ許可。
        - 個別トークンを1度正常発行したら即座にペアリング待機を終了する (P0-2 ワンタイム化・Single-Use Fail-Closed)。
        - 個別トークン発行失敗時はグローバルトークンを返さず HTTP 500 で遮断する (P1-2 Fail-Closed)。
        """
        tm = get_sync_token_manager()
        if not (tm.pairing_open or DeskPetSyncHandler._is_loopback(client_ip)):
            logger.warning(f"🚫 [SyncAuth] 外部IPからのトークン要求を拒否 (IP: {client_ip})")
            self.send_response(403)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(
                {"status": "forbidden", "message": "同一LAN外からのアクセス、またはペアリング期間外です。"},
                ensure_ascii=False
            ).encode("utf-8"))
            return

        dev_name = DeskPetSyncHandler._infer_device_name(user_agent)
        if DeskPetSyncHandler._is_loopback(client_ip):
            # 🛡️ ループバック（PC自身）は端末台帳に登録しない（マスタトークン返却）
            token = tm.token
        else:
            # 🛡️ P0-2: 未承認外部端末接続時の Human-in-the-Loop 承認
            cb = tm.device_approval_callback
            if cb is None:
                logger.warning(f"🚫 [SyncAuth] 承認UI未登録のため外部接続をFail-Closed拒否: {dev_name} (IP: {client_ip})")
                self.send_response(403)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(
                    {"status": "forbidden", "message": "承認ダイアログが利用できないため接続できません。"},
                    ensure_ascii=False
                ).encode("utf-8"))
                return

            try:
                approved = cb(dev_name, client_ip)
            except Exception as e:
                logger.error(f"端末接続承認コールバック例外 (Fail-Closed): {e}")
                approved = False

            if not approved:
                logger.warning(f"🚫 [SyncAuth] 端末接続がユーザーにより拒否されました: {dev_name} (IP: {client_ip})")
                self.send_response(403)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(
                    {"status": "forbidden", "message": "PC側で端末の接続が拒否されました。"},
                    ensure_ascii=False
                ).encode("utf-8"))
                return

            try:
                token = database.issue_device_token(dev_name, ip_address=client_ip, user_agent=user_agent)
            except Exception as e:
                logger.error(f"個別トークン発行エラー (Fail-Closed: 500返却): {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(
                    {"status": "error", "message": "Failed to issue device token."},
                    ensure_ascii=False
                ).encode("utf-8"))
                return

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "token": token}, ensure_ascii=False).encode("utf-8"))

    def _dispatch_get_devices(self, client_ip: str) -> bool:
        """GET /api/devices をディスパッチする Seam。PC同一マシン（ループバック）のみ許可する (P1-3)。"""
        if not DeskPetSyncHandler._is_loopback(client_ip):
            logger.warning(f"🚫 [Security] 非ループバック({client_ip})からのデバイス一覧閲覧要求を拒否")
            self.send_response(403)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(
                {"status": "forbidden", "message": "Device listing is restricted to localhost."},
                ensure_ascii=False
            ).encode("utf-8"))
            return True
        if not self._check_auth():
            return True
        user_agent = self.headers.get("User-Agent", "") if hasattr(self, "headers") and self.headers else ""
        return api_devices.handle_get_devices(ApiContext(self, b"", client_ip, user_agent))

    def _get_bearer_token(self) -> str:
        """AuthorizationヘッダーからBearerトークンを抽出する。"""
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[len("Bearer "):].strip()
        return ""

    @staticmethod
    def _is_private_ip(client_ip: str) -> bool:
        """接続元IPがローカルまたは同一LAN・Tailscale内のプライベートIPか判定する。"""
        if client_ip in ("127.0.0.1", "::1", "localhost", "unknown"):
            return True
        # 192.168.x.x, 10.x.x.x, 172.16.x.x - 172.31.x.x
        if client_ip.startswith("192.168.") or client_ip.startswith("10."):
            return True
        if client_ip.startswith("172."):
            parts = client_ip.split(".")
            if len(parts) >= 2 and parts[1].isdigit() and 16 <= int(parts[1]) <= 31:
                return True
        # Tailscale CGNAT (100.64.0.0/10: 100.64.x.x - 100.127.x.x)
        if client_ip.startswith("100."):
            parts = client_ip.split(".")
            if len(parts) >= 2 and parts[1].isdigit() and 64 <= int(parts[1]) <= 127:
                return True
        return False

    @staticmethod
    def _infer_device_name(user_agent: str) -> str:
        """User-Agent 文字列からデバイス表示名を推定する。"""
        ua = (user_agent or "").lower()
        if "iphone" in ua:
            return "iPhone"
        elif "ipad" in ua:
            return "iPad"
        elif "android" in ua:
            return "Android端末"
        elif "macintosh" in ua:
            return "Mac"
        elif "windows" in ua:
            return "Windows PC"
        return "スマホブラウザ"

    def _check_auth(self) -> bool:
        """Bearerトークンを検証する。LAN内接続時は柔軟に自己治癒を許可する。

        Sprint A 第2弾: 401 認証失敗のIP別レートリミット (1分10回失敗で5分間締め出し)。
        締め出し期間中は 429 Too Many Requests と Retry-After ヘッダーを返す。
        さらに、デバイス台帳 (devices テーブル) と照合し、個別失効 (Revoke) 済み端末を 403 で拒絶する。
        """
        client_ip = self.client_address[0] if self.client_address else "unknown"
        user_agent = self.headers.get("User-Agent", "")
        rate_limiter = get_auth_rate_limiter()
        is_trusted = self._is_private_ip(client_ip)

        # 1. 締め出し判定 (外部IPのみ。同一LAN・Tailscale端末は再起動時のトークン不整合による誤遮断を防止)
        if not is_trusted:
            blocked, retry_after = rate_limiter.is_blocked(client_ip)
            if blocked:
                logger.warning(
                    f"🚨 [RateLimit] IP {client_ip} はロックアウト中のため拒否 (残り {retry_after}秒)"
                )
                try:
                    self.send_response(429)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Retry-After", str(retry_after))
                    self._set_cors_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps(
                        {
                            "status": "error",
                            "message": "Too many failed authentication attempts. Please try again later.",
                            "retry_after": retry_after,
                        },
                        ensure_ascii=False
                    ).encode("utf-8"))
                except Exception:
                    pass
                return False

        token_mgr = get_sync_token_manager()
        bearer = self._get_bearer_token()

        # 2. 有効なBearerトークンがあれば認証OK（デバイス台帳で失効状態を検査）。
        #    グローバルトークン（PC内・Agent Bridge用）または端末固有トークン（QRペアリング用）のいずれかを検証。
        if bearer:
            dev = None
            is_valid_token = False
            if token_mgr.verify(bearer):
                is_valid_token = True
                # 🛡️ ループバック（PC自身）は端末台帳に登録・同期しない (外部スマホ専用)
                if not DeskPetSyncHandler._is_loopback(client_ip):
                    try:
                        dev = database.sync_device_session(
                            device_name=DeskPetSyncHandler._infer_device_name(user_agent),
                            bearer=bearer,
                            ip_address=client_ip,
                            user_agent=user_agent,
                        )
                    except Exception as e:
                        logger.debug(f"デバイス台帳同期エラー (Fail-Safe で認証継続): {e}")
                        dev = None
            else:
                try:
                    dev = database.verify_device_token(bearer)
                    if dev is not None:
                        is_valid_token = True
                        if dev.is_revoked != 1:
                            database.touch_device_last_seen(dev.token_hash, ip_address=client_ip, user_agent=user_agent)
                except Exception as e:
                    logger.debug(f"個別端末トークン検証エラー: {e}")
                    dev = None

            if is_valid_token:
                if dev is not None and dev.is_revoked == 1:
                    logger.warning(
                        f"🚫 [SyncAuth] 失効済みデバイスからのアクセス拒否: ID={dev.id}, name={dev.device_name} (IP: {client_ip})"
                    )
                    try:
                        self.send_response(403)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self._set_cors_headers()
                        self.end_headers()
                        self.wfile.write(json.dumps(
                            {"status": "forbidden", "message": "この端末の連携は失効しています。"},
                            ensure_ascii=False
                        ).encode("utf-8"))
                    except Exception:
                        pass
                    return False
                return True

        # 3. GETリクエストの閲覧許可は「同一PC内 (ループバック)」のみ (ゼロトラスト強化 2026-09-12)
        #    従来は同一LAN (192.168.x.x 等) なら無条件で閲覧できたが、共有Wi-Fi の第三者に
        #    /api/status (TODO・予定・生活状態) を覗き見されるため塞いだ。スマホPWA は
        #    ペアリング後に Bearer を保持して GET にも付与するため機能影響はない。
        if self.command == "GET" and self._is_loopback(client_ip):
            return True

        # 4. 認証失敗: 外部IPのみ失敗カウントを記録
        if not is_trusted:
            rate_limiter.record_failure(client_ip)

        logger.warning(
            f"🚫 [SyncAuth] 認証失敗: {self.path} (IP: {client_ip})"
        )
        try:
            self.send_response(401)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(
                {"status": "unauthorized", "message": "有効なトークンがありません。"},
                ensure_ascii=False
            ).encode("utf-8"))
        except Exception:
            pass
        return False

    def _check_webhook_auth(self) -> bool:
        """外部Webhookリクエストの認証を検証（Secret または Bearerトークン）。"""
        import webhook_tools
        cfg = webhook_tools.get_webhook_config()
        configured_secret = cfg.get("webhook_secret", "").strip()

        # 1. 共有シークレットが設定されている場合
        if configured_secret:
            incoming_secret = self.headers.get("X-Webhook-Secret", "").strip()
            bearer = self._get_bearer_token()
            if incoming_secret == configured_secret or bearer == configured_secret:
                return True
        
        # 2. 通常のSyncTokenが合致している場合
        token_mgr = get_sync_token_manager()
        if token_mgr.verify(self._get_bearer_token()):
            return True

        # 3. シークレット未設定かつローカルループバック接続の場合
        client_ip = self.client_address[0] if self.client_address else "unknown"
        if not configured_secret and self._is_loopback(client_ip):
            return True

        logger.warning(f"🚫 [WebhookAuth] 認証失敗: {self.path} (IP: {client_ip})")
        try:
            self.send_response(401)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(
                {"status": "unauthorized", "message": "Webhook Secret または有効なトークンがありません。"},
                ensure_ascii=False
            ).encode("utf-8"))
        except Exception:
            pass
        return False

    @staticmethod
    def _is_loopback(client_ip: str) -> bool:
        """接続元IPが同一PC内（ループバック）かどうかを判定する。"""
        return client_ip in ("127.0.0.1", "::1", "localhost")

    def _update_notice_payload(self) -> Dict[str, Any]:
        """スマホPWA向けの更新通知ペイロードを生成する (/api/status 専用)。"""
        try:
            return get_update_status()
        except Exception as e:
            logger.warning(f"更新状態ペイロードの生成に失敗 (無視): {e}")
            return {"update_available": False, "current_version": None}

    def do_GET(self):
        """APIエンドポイントまたは静的ファイルの処理"""
        client_ip = self.client_address[0] if self.client_address else "unknown"
        user_agent = self.headers.get("User-Agent", "")

        # 0.0 バージョン定数一元化 (GET /version.js または GET /web_pet/version.js)
        #     Single Source of Truth: version.py の __version__ から動的生成
        req_path_clean = self.path.split("?")[0]
        if req_path_clean in ("/version.js", "/web_pet/version.js"):
            from version import __version__
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self._set_cors_headers()
            self.end_headers()
            js_body = (
                f"// Auto-generated from version.py (Single Source of Truth)\n"
                f'self.APP_VERSION = "{__version__}";\n'
                f'self.WEB_PET_CACHE_NAME = "neo-pet-v{__version__}";\n'
                f"if (typeof window !== 'undefined') {{\n"
                f"    window.APP_VERSION = self.APP_VERSION;\n"
                f"    window.WEB_PET_CACHE_NAME = self.WEB_PET_CACHE_NAME;\n"
                f"}}\n"
            )
            self.wfile.write(js_body.encode("utf-8"))
            return

        # 0. トークン配布 (GET /api/auth/token) — ペアリング開放中 or 同一PC内 (ループバック) のみ
        if self.path == "/api/auth/token":
            self._handle_auth_token(client_ip, user_agent)
            return

        # 0.4 GET パス系APIのディスパッチ (P1-B 第一歩: api_devices モジュールへ委譲)
        # ゼロトラスト台帳 (GET /api/devices) — ループバック限定 (P1-3) ＆ Bearer 認証
        if self.path == "/api/devices":
            self._dispatch_get_devices(client_ip)
            return
        get_path_handler = GET_PATH_HANDLERS.get(self.path)
        if get_path_handler:
            if not self._check_auth():
                return
            get_path_handler(ApiContext(self, b"", client_ip, user_agent))
            return

        # 0.5 ミニゲームハイスコア取得 (GET /api/minigame/high?game_id=xxx)
        if self.path.startswith("/api/minigame/high"):
            if not self._check_auth():
                return

            def _json_response(status_code: int, payload: Dict[str, Any]) -> None:
                """JSONレスポンスを送信する (既存ハンドラと同一のヘッダ構成)。"""
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

            try:
                query = parse_qs(urlsplit(self.path).query)
                game_id = (query.get("game_id", [""])[0]).strip()
                if not game_id:
                    _json_response(400, {"status": "error", "message": "game_id is required"})
                    return
                high = database.get_high_score(game_id)
                _json_response(200, {"status": "ok", "game_id": game_id, "high_score": high})
            except Exception as e:
                logger.error(f"⚠️ [Minigame] ハイスコア取得エラー: {e}")
                _json_response(500, {"status": "error", "message": "internal error"})
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
                    _sources_by_id = {}
                    try:
                        for s in database.get_all_calendar_sources():
                            _sources_by_id[s.id] = {"name": s.name, "color": s.color}
                    except Exception:
                        pass
                    _cached_tasks_data = [
                        {"id": t.id, "title": t.title, "priority": t.priority, "due_date": t.due_date}
                        for t in tasks
                    ]
                    _cached_events_data = [
                        {
                            "id": e.id, "title": e.title,
                            # スマホ手帳は数値(ms)をそのまま描画できず桁数字になるため ISO 文字列で渡す
                            "start_time": _fmt_event_dt(e.start_time),
                            "description": e.description,
                            "source_color": _sources_by_id.get(e.source_id, {}).get("color", ""),
                            "source_name": _sources_by_id.get(e.source_id, {}).get("name", "")
                        }
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
                
                # ⏰ 期限リマインダー (roadmap 3.1) — エンジン未起動 (テスト/MCP単体) 時は空配列
                try:
                    from reminder_engine import get_reminder_engine
                    due_reminders = get_reminder_engine().get_pending_for_phone()
                except Exception as rem_err:
                    logger.debug(f"リマインダー状態取得スキップ: {rem_err}")
                    due_reminders = []

                pet_state = "alarm_ask" if pending_req else ("focus" if (pomodoro_active and not pomodoro_is_break) else "idle")
                # 台詞の優先順位: 承認要請 > リマインダー > 集中タイム > PCペット最新セリフ（ミラー） > キャラ別ローテーション挨拶
                pc_message = str(getattr(gui, "current_message", "") or "").strip() if gui else ""
                use_greeting_rotation = not (pending_req or due_reminders or (pomodoro_active and not pomodoro_is_break) or pc_message)
                if pending_req:
                    default_msg = "ボス！エージェントからコマンド実行の許可を求められています！"
                elif due_reminders:
                    rem_first = due_reminders[0]
                    default_msg = f"⏰ 予定リマインダー: {rem_first.get('title', 'まもなく予定の時間です！')}"
                elif pomodoro_active and not pomodoro_is_break:
                    default_msg = "集中タイムです！ボス、一緒に頑張りましょう！🔥"
                elif pc_message:
                    default_msg = pc_message
                else:
                    default_msg = "ボス、いつもお疲れ様です！スマホからも見守っていますよ！"
                
                from suggest_engine import get_suggestion_engine
                suggest_eng = get_suggestion_engine()
                # 短期改善 Step 2: 生成済みキャッシュの即時読み出しに変更。
                # 重い生成処理（DB/LLM/RSS）は SuggestBgWorker スレッドに隔離済みで、
                # ポーリングハンドラが GUI スレッドの GIL を奪わない。
                suggestions_data = suggest_eng.get_cached_suggestions()
                
                from character_manager import get_character_manager
                char_mgr = get_character_manager()
                char_info = char_mgr.get_current_character()

                # 🌈 自律生活ドリーマーの状態を取得（無ければ既定値）
                try:
                    from life_dreamer import get_life_dreamer
                    life_state = get_life_dreamer().get_life_state()
                except Exception as life_err:
                    logger.debug(f"LifeDreamer 状態取得スキップ: {life_err}")
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
                    if active_event.get("type") == "approval":
                        pet_state = "alarm_ask"
                    elif active_event.get("type") == "question":
                        pet_state = "alarm_ask"
                    elif active_event.get("type") == "completed":
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
                global _last_habit_cache_time, _cached_habits_data, _cached_heatmap_data
                if (now - _last_habit_cache_time) > 30.0:
                    _cached_habits_data = [h.model_dump() for h in database.get_habits_with_status()]
                    _cached_heatmap_data = [d.model_dump() for d in database.get_habit_heatmap_data(days=70)]
                    _last_habit_cache_time = now
                habits_data = _cached_habits_data
                heatmap_data = _cached_heatmap_data
                bond_info = char_mgr.get_bond_info()

                # キャラ別挨拶 × 時間帯 × 90秒ローテーション（固定文言の解消）
                if use_greeting_rotation:
                    try:
                        greetings = list(char_mgr.get_current_character().get("greetings", []))
                    except Exception:
                        greetings = []
                    hour = time.localtime().tm_hour
                    if 5 <= hour < 11:
                        greetings.append("おはようございます、ボス！今日も一日よろしくです！")
                    elif 11 <= hour < 18:
                        greetings.append("ボス、午後の業務もここから見守っていますよ！")
                    elif 18 <= hour < 23:
                        greetings.append("ボス、今日も一日お疲れ様です！もう少しだけ付き合ってください✨")
                    else:
                        greetings.append("ふぁ…まだ起きています？無理は禁物ですよ、ボス。")
                    if greetings:
                        default_msg = greetings[int(time.time() // 90) % len(greetings)]

                # イースターエッグ状態（最新イベント ＆ 永続化状態）
                try:
                    import easter_egg_engine
                    ee_state = easter_egg_engine.load_state()
                    ee_payload = {
                        "attempt_count": ee_state.attempt_count,
                        "daily_count": ee_state.daily_count,
                        "secret_game_unlocked": ee_state.secret_game_unlocked,
                        "active_event": monitor.get_active_easter_egg_event()
                    }
                except Exception as ee_err:
                    logger.debug(f"イースターエッグ状態取得スキップ: {ee_err}")
                    ee_payload = {
                        "attempt_count": 0,
                        "daily_count": 0,
                        "secret_game_unlocked": False,
                        "active_event": None
                    }

                # 同期トークンはスマホ側のペアリング表示用にペイロードへ同梱する。
                # (バグ修正 2026-08-30: token_mgr 未定義の NameError により
                #  /api/status が常に {"status": "error"} を返し、スマホ同期が
                #  全滅していた障害を解消)
                token_mgr = get_sync_token_manager()
                # AI生活コーチの最新分析レポート (Phase L1: life_coach フィールド)
                try:
                    from life_coach_engine import get_life_coach_engine
                    coach_report = get_life_coach_engine().get_latest_report()
                except Exception as coach_err:
                    logger.debug(f"生活コーチ状態取得スキップ: {coach_err}")
                    coach_report = None
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
                    "agent_activity": agent_activity,
                    "easter_egg": ee_payload,
                    "tasks": _cached_tasks_data,
                    "events": _cached_events_data,
                    "suggestions": suggestions_data,
                    "due_reminders": due_reminders,
                    "suggest_config": suggest_eng.config,
                    "pomodoro": {
                        "active": pomodoro_active,
                        "is_break": pomodoro_is_break,
                        "remaining_seconds": pomodoro_sec,
                        "total_seconds": getattr(gui, "pomodoro_total_seconds", 25 * 60) if gui else 25 * 60,
                        "mode_label": pomodoro_label
                    },
                    "buzz": should_buzz,
                    "life_state": life_state,
                    "life_coach": coach_report,
                    "weather_location": (lambda: (__import__('weather_tools').get_current_location_setting()))(),
                    "update": self._update_notice_payload(),
                    "sync_token": token_mgr.token,
                    "server_time": int(now * 1000)
                }
                # P2①: Pydantic DTO 境界検証 (契約違反時は生辞書フォールバックで可用性維持)
                payload = validate_status_payload(payload)
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

        # 3.8. 朝会/終礼ブリーフィングAPI (GET /api/briefing?mode=...)
        elif self.path.startswith("/api/briefing"):
            if not self._check_auth():
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._set_cors_headers()
            self.end_headers()
            try:
                import urllib.parse
                import briefing_engine
                parsed = urllib.parse.urlparse(self.path)
                params = urllib.parse.parse_qs(parsed.query)
                force_mode = params.get("mode", [None])[0]
                report = briefing_engine.generate_briefing(force_mode=force_mode)
                self.wfile.write(json.dumps({"status": "ok", "briefing": report.to_dict()}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                logger.error(f"Briefing API エラー: {e}")
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False).encode("utf-8"))

        # 4. アセット配信 (GET /assets/...) — 静的画像のみ・認証不要（PWAアイコン/スプライト）
        #    P0-1 (2026-09-16): パス検証を web_assets.resolve_asset_path へ集約。
        #    「\」始まり絶対パス等による assets 外読み出しを根治（多層防御）。
        elif self.path.startswith("/assets/"):
            filename = self.path[len("/assets/"):].split("?")[0]
            asset_file = resolve_asset_path(filename, ASSETS_DIR)

            if asset_file is not None:
                self.send_response(200)
                self.send_header("Content-Type", guess_asset_content_type(asset_file))
                self.send_header("Cache-Control", "no-cache")
                self._set_cors_headers()
                self.end_headers()
                with open(asset_file, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, f"Asset not found: {filename}")

        else:
            super().do_GET()

    def do_POST(self):
        """スマホ側からのアクションおよび外部エージェントからの要請受信

        P2③ 分割リファクタ: 本メソッドは認証・ループバック制限・ディスパッチのみを
        担当し、個別処理は api_tasks / api_agent_bridge モジュールのハンドラ関数へ委譲する。
        """
        # 🛡️ ボディサイズ上限 (OOM DoS 防止・2026-09-12 レビュー対応)。
        #    Content-Length を無制限に読むと巨大サイズ指定でメモリを食い潰されるため、
        #    上限超過は本文を読まずに即 413 を返す。数値以外は 0 として扱う。
        MAX_BODY_SIZE = 5 * 1024 * 1024  # 5MB
        try:
            content_length = int(self.headers.get('Content-Length', 0))
        except (TypeError, ValueError):
            content_length = 0
        if content_length > MAX_BODY_SIZE:
            logger.warning(
                f"🚫 [Security] 過大な Content-Length ({content_length}) を拒否 (上限 {MAX_BODY_SIZE})"
            )
            self.send_error(413, "Payload Too Large")
            return
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

        # パス系APIのディスパッチ (P2③: api_agent_bridge モジュールへ委譲)
        path_handler = POST_PATH_HANDLERS.get(self.path)
        if path_handler:
            path_handler(ApiContext(self, body, client_ip, user_agent))

        # 3.5 デバイス個別失効API (POST /api/devices/revoke) — 管理者/同一PC操作に限定
        #     処理本体（監査ログ記録を含む）は api_devices.handle_post_devices_revoke へ委譲 (P1-4)
        elif self.path == "/api/devices/revoke":
            if not self._is_loopback(client_ip):
                logger.warning(f"🚫 [Security] 非ループバック({client_ip})からのデバイス失効要求を拒否")
                self.send_response(403)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": "Device revoke is restricted to localhost."}, ensure_ascii=False).encode("utf-8"))
                return
            api_devices.handle_post_devices_revoke(ApiContext(self, body, client_ip, user_agent))
            return

        # 3.5b デバイス個別復帰API (POST /api/devices/restore) — 管理者/同一PC操作に限定
        elif self.path == "/api/devices/restore":
            if not self._is_loopback(client_ip):
                logger.warning(f"🚫 [Security] 非ループバック({client_ip})からのデバイス復帰要求を拒否")
                self.send_response(403)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": "Device restore is restricted to localhost."}, ensure_ascii=False).encode("utf-8"))
                return
            api_devices.handle_post_devices_restore(ApiContext(self, body, client_ip, user_agent))
            return

        # 3.6 AIエージェント稼働状態更新 (POST /api/agent/activity) — Phase H
        elif self.path == "/api/agent/activity":
            if not self._is_loopback(client_ip):
                logger.warning(f"🚫 [Security] 非ループバック({client_ip})からのエージェント状態更新を拒否")
                self.send_response(403)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": "Agent activity API is restricted to localhost."}, ensure_ascii=False).encode("utf-8"))
                return
            try:
                data = json.loads(body.decode("utf-8")) if body else {}
                state = data.get("state", "idle")
                agent_name = data.get("agent_name", "AI Agent")
                detail = data.get("detail", "")
                ttl_seconds = data.get("ttl_seconds")
                if ttl_seconds is not None:
                    ttl_seconds = float(ttl_seconds)

                updated = agent_fsm.set_state(state, agent_name=agent_name, detail=detail, ttl_seconds=ttl_seconds)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "activity": updated}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                logger.error(f"エージェント状態更新エラー: {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False).encode("utf-8"))
            return

        # 4. 通常のDesk Petアクション (POST /api/action)
        #
        # 🔐 セキュリティ設計 (2026-08-26 S-1 対応):
        #   - /api/action は AGENT_ONLY_PATHS に含めず、スマートフォンPWAからも
        #     Bearer 認証経由でアクセス可能にする。
        #   - 理由: スマホPWAは show_pc_pet / complete_task / toggle_habit 等の
        #     ユーザー操作をこのエンドポイント経由で実行する必要がある。
        #   - AGENT_ONLY_PATHS の本来の目的は「承認要請の作成を localhost に制限する
        #     (RCEチェーン遮断)」であり、/api/action は承認要請を作成しないため
        #     追加制限不要。Bearer 認証が既に適用されている。
        #   - 監査: 全アクションの呼び出しを client_ip 付きでログ出力する。
        elif self.path == "/api/action":
            get_link_monitor().record_heartbeat(client_ip, user_agent)
            ctx = ApiContext(self, body, client_ip, user_agent)

            try:
                data = json.loads(body.decode("utf-8"))
                action = data.get("action")
                logger.debug(f"📱 /api/action 呼び出し: action={action}, client_ip={client_ip}")

                action_handler = ACTION_HANDLERS.get(action)
                if action_handler is not None:
                    # アクション処理は機能別モジュール (api_tasks / api_agent_bridge) へ委譲。
                    # パラメータ欠落等のガード未成立時も明示エラーJSONが書き込まれる
                    # (Sprint A 第1弾: ApiContext の遅延ヘッダー送出により、ハンドラ側で status_code 制御が可能)。
                    if action_handler(ctx):
                        return
                else:
                    # 未知のアクションは明示的にエラーを返す（旧仕様は無応答 200 で、
                    # クライアントが成功と誤認する障害を生んでいた）
                    logger.warning(f"📱 未知のアクションを受信: {action}")
                    ctx.write_json(
                        {"status": "error", "message": f"unknown action: {action}"},
                        ensure_ascii=False
                    )
                    return

            except Exception as e:
                logger.error(f"Action API エラー: {e}")
                ctx.write_json({"status": "error", "message": str(e)})

        else:
            self.send_error(404)

    def log_message(self, format, *args):
        """標準出力のノイズを抑えるカスタムロガー"""
        pass



class LocalSyncServer:
    """バックグラウンドで稼働するローカル同期サーバー

    2026-09-03 (Block 2 / 2026-09-06 分離): スリープ復帰等で serve_forever スレッドが死亡した場合に
    周期ヘルスプローブで検出し、解決済みポートへ再バインドする自己治癒watchdog (server_watchdog.py) を備える。
    """

    def __init__(self, port: int = SERVER_PORT):
        self.port = port
        self.httpd = None
        self.thread = None
        # watchdog 用状態
        self._bound_port: Optional[int] = None  # port=0 (エフェメラル) 時の解決済みポート
        self._watchdog_interval: float = 5.0
        self._watchdog = ServerWatchdog(
            probe_fn=self.is_healthy,
            restart_fn=self._restart_httpd,
            interval=self._watchdog_interval,
            failure_threshold=1,
            thread_name="sync-server-watchdog",
        )

    @property
    def watchdog_interval(self) -> float:
        return self._watchdog.interval

    @watchdog_interval.setter
    def watchdog_interval(self, val: float) -> None:
        self._watchdog_interval = float(val)
        self._watchdog.interval = float(val)

    @property
    def _watchdog_thread(self) -> Optional[threading.Thread]:
        """既存テスト後方互換用: watchdogスレッド参照"""
        return self._watchdog._thread

    def _start_httpd(self) -> bool:
        """HTTPサーバーを生成してバックグラウンドスレッドで起動する。

        再起動時は _bound_port (解決済みポート) へ再バインドし、
        エフェメラルポートの再抽選によるポート変更を防止する。

        Returns:
            bool: 起動に成功した場合は True (ポート競合等は False)。
        """
        bind_port = self._bound_port if self._bound_port is not None else self.port
        try:
            self.httpd = QuietThreadingHTTPServer(("0.0.0.0", bind_port), DeskPetSyncHandler)
        except OSError as e:
            logger.error(f"📱 [Watchdog] 同期サーバーのバインドに失敗しました (ポート={bind_port}): {e}")
            return False
        self._bound_port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        logger.info(
            f"📱 [Agent Bridge Hub] Desk Pet 同期サーバーが起動しました: "
            f"http://localhost:{self._bound_port} (LAN/Bluetooth対応)"
        )
        return True

    def is_healthy(self) -> bool:
        """サーバースレッドの生存とループバック疎通を確認する。

        Returns:
            bool: スレッドが生存し、ループバック接続に成功する場合は True。
        """
        if self.thread is None or not self.thread.is_alive():
            return False
        if self._bound_port is None:
            return False
        try:
            with socket.create_connection(("127.0.0.1", self._bound_port), timeout=0.5):
                return True
        except OSError:
            return False

    def _restart_httpd(self) -> bool:
        """旧サーバーを片付けて自己治癒再起動を行う。

        Returns:
            bool: 再起動に成功した場合は True。
        """
        old_httpd = self.httpd
        if self.thread is not None and self.thread.is_alive() and old_httpd is not None:
            # スレッドは生存だが疎通しない (ハング等) → shutdown を要求して出口を待つ
            old_httpd.shutdown()
        if old_httpd is not None:
            try:
                old_httpd.server_close()
            except OSError as e:
                logger.debug(f"📱 [Watchdog] 旧サーバーソケットの解放に失敗: {e}")
        success = self._start_httpd()
        if success:
            logger.warning("📱 [Watchdog] 同期サーバーを自己治癒再起動しました")
        else:
            logger.warning("📱 [Watchdog] 同期サーバーの自己治癒再起動に失敗 (次周期で再試行)")
        return success

    def start(self, gui=None):
        """バックグラウンドスレッドでサーバーを起動"""
        if gui:
            set_gui_instance(gui)
        # 🌈 自律生活ドリーマーエンジンの起動（PCペットミラー用コールバック登録）
        try:
            from life_dreamer import get_life_dreamer
            dreamer = get_life_dreamer()
            if gui is not None:
                dreamer.set_on_state_change(lambda state: self._mirror_to_pc_pet(gui, state))
            dreamer.start()
        except Exception as e:
            logger.warning(f"🌈 [LifeDreamer] 起動をスキップしました: {e}")
        if not self._start_httpd():
            logger.warning("Desk Pet 同期サーバーの起動をスキップしました（ポート競合など）")
            return
        self._watchdog.start()

    @staticmethod
    def _mirror_to_pc_pet(gui, state: Dict[str, Any]) -> None:
        """ライフステートの変化をPCデスクトップペットへミラーする。

        ※ LifeDreamer のスレッドから呼ばれるため、GUI操作は必ず
        post_action 経由でメインスレッドへディスパッチすること。
        """
        try:
            activity = state.get("current_activity", "resting")
            message = state.get("message", "")
            from life_dreamer import ACTIVITY_PET_STATE_MAP
            pet_state = ACTIVITY_PET_STATE_MAP.get(activity, "idle")
            if message:
                gui.post_action(gui.update_message, f"🌈 {message}")
            gui.post_action(gui.set_pet_state, pet_state, duration_ms=8000)
        except Exception as e:
            logger.debug(f"LifeDreamer PCペットミラーエラー: {e}")

    def stop(self):
        """サーバーとwatchdogを停止する (ゾンビ再起動を防止する終端契約)。"""
        self._watchdog.stop(timeout=5.0)
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        if self.thread:
            self.thread.join(timeout=5)
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
