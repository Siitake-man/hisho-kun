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
import ipaddress
import socket
import secrets
import logging
import threading
from typing import Any, Dict, Optional
from datetime import datetime
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler


# =============================================================================
# HTTP サーバー基盤 (QuietThreadingHTTPServer / S5 Seam)
#   Fat Module 分割 Phase F6 (2026-10-04): server/httpd_core.py へ委譲し、
#   本モジュールからは完全互換 Facade 再エクスポートを行う (DESIGN_SPEC 準拠)。
# =============================================================================
from server.httpd_core import QuietThreadingHTTPServer
from server.auth_checks import (
    check_auth,
    check_webhook_auth,
    get_bearer_token,
    infer_device_name,
    is_private_ip,
)
from server.loopback_trust import (
    host_is_loopback,
    is_loopback,
    is_trusted_loopback,
    request_is_trusted_loopback,
    resolve_ledger_client_ip,
)
from server.api_status import (
    build_status_payload,
    handle_get_status,
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
import i18n
import app_paths
from web_assets import guess_asset_content_type, resolve_asset_path
from update_checker import get_update_status
from sync_dtos import validate_status_payload, validate_tasks_view_response
from api_context import ApiContext
import api_tasks
import api_agent_bridge
import api_calendar
import api_devices
import api_push
from server_watchdog import ServerWatchdog
from agent_fsm import agent_fsm

logger = logging.getLogger(__name__)

WEB_PET_DIR = Path(__file__).parent / "web_pet"
ASSETS_DIR = Path(__file__).parent / "assets"
# 待受ポートは sync_config を唯一の情報源とする (QRダイアログ/Tailscale起動と一元化)
SERVER_PORT = sync_config.SERVER_PORT
# 🛡️ P0-4 (2026-09-23 / ADR-2): マスタートークンはデータ境界 (非同期領域) に配置する。
# 旧配置 (リポジトリ/exe 直下) はクラウド同期で漏洩し得るため禁止。
TOKEN_FILE = app_paths.get_sync_token_path()

# =============================================================================
# 🖥️ GUI インスタンス保持 ＆ 承認ダイアログ連携 (gui_bridge / S6 Seam)
#   Fat Module 分割 Phase F10 (2026-10-04): server/gui_bridge.py へ委譲し、
#   本モジュールからは完全互換 Facade 再エクスポートを行う (DESIGN_SPEC 準拠)。
# =============================================================================
from server.gui_bridge import get_gui_instance, set_gui_instance




# =============================================================================
# 🔐 同期サーバー認証トークン管理 (SyncTokenManager / S1a Seam)
#   Fat Module 分割 Phase F7a (2026-10-04): server/sync_token_manager.py へ委譲し、
#   本モジュールからは完全互換 Facade 再エクスポートを行う (DESIGN_SPEC 準拠)。
# =============================================================================
from server.sync_token_manager import SyncTokenManager, get_sync_token_manager



# =============================================================================
# 📊 状態同期キャッシュ ＆ 無効化 (status_cache / S4 Seam)
#   Fat Module 分割 Phase F9 (2026-10-04): server/status_cache.py へ委譲し、
#   本モジュールからは完全互換 Facade 再エクスポートを行う (DESIGN_SPEC 準拠)。
# =============================================================================
from server.status_cache import (
    StatusCacheManager,
    get_status_cache,
    invalidate_db_cache,
    invalidate_habit_cache,
)


# =============================================================================
# 📶 デバイスリンク検知 ＆ 死活監視マネージャー (Link Monitor)
# =============================================================================

# =============================================================================
# 端末接続状態モニター (DeviceLinkMonitor / S3 Seam)
#   Fat Module 分割 Phase F4 (2026-10-04): server/device_link.py へ委譲し、
#   本モジュールからは完全互換 Facade 再エクスポートを行う (DESIGN_SPEC 準拠)。
# =============================================================================
from server.device_link import DeviceLinkMonitor, get_link_monitor


# =============================================================================
# Agent Bridge 承認リクエスト管理キュー (AgentBridgeHub / S2 Seam)
#   Fat Module 分割 Phase F5 (2026-10-04): server/agent_bridge_hub.py へ委譲し、
#   本モジュールからは完全互換 Facade 再エクスポートを行う (知見ID 45 / DESIGN_SPEC 準拠)。
# =============================================================================
from server.agent_bridge_hub import (
    AgentBridgeRequest,
    AgentBridgeHub,
    get_bridge_hub,
    _PC_LOCAL_IDENTITIES,
)





# =============================================================================
# HTTP & API ハンドラ
# =============================================================================

# =============================================================================
# 🚦 ルートレコード ＆ ディスパッチテーブル (routes / Phase F10)
#   Fat Module 分割 Phase F10 (2026-10-04): server/routes.py へ委譲し、
#   本モジュールからは完全互換 Facade 再エクスポートを行う (DESIGN_SPEC 準拠)。
# =============================================================================
from server.routes import (
    ACTION_HANDLERS,
    ACTION_HANDLERS_DEVICE,
    ACTION_HANDLERS_TASKS,
    GET_PATH_HANDLERS,
    GET_ROUTES,
    POST_PATH_HANDLERS,
    POST_ROUTES,
    RouteRecord,
)



class DeskPetSyncHandler(SimpleHTTPRequestHandler):
    """Desk Pet PWA用の静的ファイル配信 ＆ JSON APIハンドラ"""
    
    # 🛡️ P0-3 (Slowloris対策): ソケット受信タイムアウトを10秒に明示設定し、スレッド枯渇を防止
    timeout = 10.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_PET_DIR), **kwargs)
        # 認証主体 (identity) のプレースホルダ。_check_auth() がトークン検証に
        # 成功した際に確定値へ更新する (手帳 ID 52: IP ではなく identity で
        # 自己承認を判定するための属性。未認証・検証前は unknown = 空文字)。
        self.auth_identity: str = ""

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

        - ペアリング開放中 or 信頼できる loopback（TCPピア + Host + プロキシヘッダ無しの3条件）のみ許可。
        - 個別トークンを1度正常発行したら即座にペアリング待機を終了する (P0-2 ワンタイム化・Single-Use Fail-Closed)。
        - 個別トークン発行失敗時はグローバルトークンを返さず HTTP 500 で遮断する (P1-2 Fail-Closed)。
        - 外部端末は必ず人間承認（承認ダイアログ）を経てから個別トークンを発行する (P0-2 Human-in-the-Loop)。
        - 🛡️ P0-1 (2026-09-22): 承認済み再ペアリングは明示的な復帰操作とみなし、失効中の端末
          (is_revoked=1) を restore_device() で復帰させ、監査ログ (source="pairing") へ記録する。
        - 🛡️ P0-3 (2026-09-22): **マスター鍵は HTTP で一切配布しない**。loopback には
          loopback 専用トークン（プロセス内生成・台帳非登録）を返す。Tailscale Serve 等の
          リバースプロキシ経由は Host ヘッダが loopback 名でないため loopback 信頼が成立せず、
          外部端末として人間承認 + 個別トークンの対象になる。

        Args:
            client_ip (str): 接続元IPアドレス。
            user_agent (str): 接続元User-Agent（端末表示名の推定に使用）。
        """
        tm = get_sync_token_manager()
        headers = getattr(self, "headers", None) or {}
        trusted_loopback = DeskPetSyncHandler._is_trusted_loopback(
            client_ip, str(headers.get("Host", "")), headers
        )
        # 🛡️ ID 53 (2026-09-23): Serve 中継の TCPピア (127.0.0.1) をそのまま台帳へ書くと
        # 「PC内のゴミ」と誤認され cleanup に物理削除される。中継経由では XFF の実IPを採用する。
        ledger_ip = DeskPetSyncHandler._resolve_ledger_client_ip(
            client_ip, str(headers.get("Host", "")), headers
        )
        # 🛡️ P2-N4: XFF 由来の推定値であることを承認ダイアログで明示する
        # (単一値XFFを上書きする中継の背後での誤誘導を防ぐ)
        if ledger_ip is None:
            approval_ip_label = "中継経由（IP不明）"
        elif ledger_ip != client_ip:
            approval_ip_label = f"{ledger_ip}（中継経由・推定）"
        else:
            approval_ip_label = ledger_ip
        # 🛡️ ID 50 (2026-09-23): 端末自己生成UUID（X-Device-UUID ヘッダ）を台帳の行再利用キーに使用。
        # 不正値は無視して従来キーへフォールバックする（後方互換）。認証の根拠にはしない。
        from storage.device_repo import normalize_device_uuid as _normalize_device_uuid

        device_uuid = _normalize_device_uuid(headers.get("X-Device-UUID"))
        if not (tm.pairing_open or trusted_loopback):
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
        if trusted_loopback:
            # 🛡️ P0-3: PC内ブラウザへは loopback 専用トークン（マスター鍵ではない）を返す。
            # 台帳 (devices) にも登録しないため PC ブラウザ利用で台帳を汚さない。
            token = tm.loopback_token
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
                approved = cb(dev_name, approval_ip_label)
            except Exception as e:
                logger.error(f"端末接続承認コールバック例外 (Fail-Closed): {e}")
                approved = False

            if not approved:
                logger.warning(f"🚫 [SyncAuth] 端末接続がユーザーにより拒否されました: {dev_name} (IP: {ledger_ip or 'unknown'})")
                self.send_response(403)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(
                    {"status": "forbidden", "message": "PC側で端末の接続が拒否されました。"},
                    ensure_ascii=False
                ).encode("utf-8"))
                return

            logger.warning(
                f"🔐 [SyncAuth] 端末接続承認を通過: {dev_name} (実IP: {ledger_ip or '不明（中継経由）'} / "
                f"TCPピア: {client_ip} / 端末ID: {(device_uuid or '-')[:8]} / UA: {user_agent[:80]})"
            )
            try:
                token = database.issue_device_token(
                    dev_name,
                    ip_address=ledger_ip,
                    user_agent=user_agent,
                    device_uuid=device_uuid,
                )
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

            # 🛡️ P0-3 N4: 個別トークンを1度発行したら即座にペアリング待機を終了する
            # (DESIGN_SPEC §10.2 の Single-Use Fail-Closed を実装で担保。600秒窓の悪用を封鎖)
            tm.close_pairing()

            # ♻️ P0-1 / AD-1: 失効の解除は「人間の明示操作」のみ。
            # ここへ到達するには ①PC側でQRペアリングダイアログを開く ②PC側の承認ダイアログで
            # 許可する、という2段の人間操作が必須のため、承認済み再ペアリングは明示的な
            # 復帰操作とみなして監査ログ付きで解除する (無言の巻き戻しとは明確に区別する)。
            try:
                paired_dev = database.verify_device_token(token)
                if paired_dev is not None and paired_dev.is_revoked == 1:
                    restored = bool(database.restore_device(paired_dev.id))
                    if restored:
                        api_devices.record_device_restore(
                            paired_dev.id,
                            actor=ledger_ip or "relayed-unknown",
                            source="pairing",
                            device_name=paired_dev.device_name,
                        )
                        logger.warning(
                            f"♻️ [SyncAuth] 承認済み再ペアリングにより失効端末を復帰: ID={paired_dev.id} ({paired_dev.device_name})"
                        )
                    else:
                        # 復帰できなかった場合は失効のまま (Fail-Closed)。UI の嘘を作らないため可視化する
                        logger.warning(
                            f"⚠️ [SyncAuth] 承認済み再ペアリングの復帰に失敗 (対象行消失など): ID={paired_dev.id} — 失効状態を維持します"
                        )
            except Exception as e:
                # 復帰処理の失敗はトークン配布自体を失敗させない (端末は失効のまま = Fail-Closed 側に倒れる)
                logger.error(f"再ペアリング時の端末復帰処理エラー (失効状態を維持): {e}")

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "token": token}, ensure_ascii=False).encode("utf-8"))

    def _dispatch_get_devices(self, client_ip: str) -> bool:
        """GET /api/devices をディスパッチする Seam。信頼できる loopback のみ許可する (P1-3 / P0-3)。

        Args:
            client_ip (str): 接続元IPアドレス。

        Returns:
            bool: レスポンス書き込み済みのため常に True (呼び出し側の分岐を単純化する)。
        """
        headers = getattr(self, "headers", None) or {}
        if not DeskPetSyncHandler._is_trusted_loopback(client_ip, str(headers.get("Host", "")), headers):
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
        return api_devices.handle_get_devices(
            ApiContext(
                self, b"", client_ip, user_agent,
                auth_identity=getattr(self, "auth_identity", ""),
            )
        )

    # =========================================================================
    # 🔐 認証判定 ＆ デバイス識別 (auth_checks / S1b Seam 委譲)
    #   Fat Module 分割 Phase F7b (2026-10-04): server/auth_checks.py へ委譲し、
    #   既存テスト・呼び出し元互換の staticmethod / メソッド契約を完全維持する。
    # =========================================================================
    def _get_bearer_token(self) -> str:
        """AuthorizationヘッダーからBearerトークンを抽出する。"""
        return get_bearer_token(self.headers)

    @staticmethod
    def _is_private_ip(client_ip: str) -> bool:
        """接続元IPがローカルまたは同一LAN・Tailscale内のプライベートIPか判定する。"""
        return is_private_ip(client_ip)

    @staticmethod
    def _infer_device_name(user_agent: str) -> str:
        """User-Agent 文字列からデバイス表示名を推定する。"""
        return infer_device_name(user_agent)

    def _check_auth(self) -> bool:
        """Bearerトークンを検証する。LAN内接続時は柔軟に自己治癒を許可する。"""
        return check_auth(self)

    def _check_webhook_auth(self) -> bool:
        """外部Webhookリクエストの認証を検証（Secret または Bearerトークン）。"""
        return check_webhook_auth(self)


    # =========================================================================
    # 🛡️ ループバック信頼 ＆ 実IP解決 (loopback_trust / S1c Seam 委譲)
    #   Fat Module 分割 Phase F7c (2026-10-04): server/loopback_trust.py へ委譲し、
    #   既存テスト・呼び出し元互換の staticmethod / メソッド契約を完全維持する。
    # =========================================================================
    @staticmethod
    def _is_loopback(client_ip: str) -> bool:
        """接続元IPが同一PC内（ループバック）かどうかを判定する。"""
        return is_loopback(client_ip)

    @staticmethod
    def _host_is_loopback(host_header: str) -> bool:
        """Host ヘッダが loopback 名（localhost / 127.0.0.1 / ::1）かどうかを判定する。"""
        return host_is_loopback(host_header)

    @staticmethod
    def _is_trusted_loopback(
        client_ip: str, host_header: str = "", headers: Optional[Dict[str, Any]] = None
    ) -> bool:
        """loopback 信頼の3条件（TCPピア + Host + プロキシヘッダ無し）を判定する (P0-3)。"""
        return is_trusted_loopback(client_ip, host_header, headers)

    @staticmethod
    def _resolve_ledger_client_ip(
        client_ip: str, host_header: str = "", headers: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """台帳・監査へ記録するクライアントIPを解決する (ID 53 / 2026-09-23)。"""
        return resolve_ledger_client_ip(client_ip, host_header, headers)

    def _request_is_trusted_loopback(self) -> bool:
        """このリクエストが信頼できる loopback かを3条件で判定する (P0-3)。"""
        return request_is_trusted_loopback(self)

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
            get_path_handler(
                ApiContext(
                    self, b"", client_ip, user_agent,
                    auth_identity=getattr(self, "auth_identity", ""),
                )
            )
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
        #   Fat Module 分割 Phase F9 (2026-10-04): server/api_status.py へ委譲 (S4 Seam)
        if self.path == "/api/status":
            if not self._check_auth():
                return
            handle_get_status(self, client_ip, user_agent)
            return


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

        # 1. 統合 POST ルートテーブル (POST_ROUTES / Phase F10) によるディスパッチ
        route = POST_ROUTES.get(self.path)
        if route is not None:
            if route.auth_level == "loopback" and not self._request_is_trusted_loopback():
                logger.warning(f"🚫 [Security] 非ループバック({client_ip})からの制限API呼び出しを拒否: {self.path}")
                self.send_response(403)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(
                    {"status": "error", "message": route.loopback_error_msg},
                    ensure_ascii=False
                ).encode("utf-8"))
                return

            ctx = ApiContext(
                self, body, client_ip, user_agent,
                auth_identity=getattr(self, "auth_identity", ""),
            )
            route.handler(ctx)
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
            ctx = ApiContext(
                self, body, client_ip, user_agent,
                auth_identity=getattr(self, "auth_identity", ""),
            )

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



# =============================================================================
# 同期サーバー ＆ ライフサイクル管理 (LocalSyncServer / S5 Seam)
#   Fat Module 分割 Phase F6 (2026-10-04): server/httpd_core.py へ委譲し、
#   本モジュールからは完全互換 Facade 再エクスポートを行う (DESIGN_SPEC 準拠)。
# =============================================================================
from server.httpd_core import LocalSyncServer, get_sync_server
