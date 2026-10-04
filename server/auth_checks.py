#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - 認証判定 ＆ デバイス識別基盤 (auth_checks / S1b Seam).

(server/auth_checks.py)

目的:
    Fat モジュール `local_sync_server.py` から、Bearer トークン抽出、
    プライベート IP 判定、User-Agent からのデバイス名推定、外部 Webhook 認証、
    およびゼロトラスト端末台帳 (devices) 照合を伴う HTTP 認証判定ロジックを
    独立した Deep Module として切り出す。

防衛策:
    - 🛡️ P0-1 (2026-09-22): マスタートークンはループバック (PC自身) 専用。非ループバックからは台帳照合必須。
    - 🛡️ P0-3 (2026-09-22): loopback 専用トークンは信頼できる loopback でのみ有効。
    - 🛡️ ID 50/53 (2026-09-23): 非ブラウザUAは正直ラベル「⚠️ 非ブラウザ端末」を返す。
    - 🛡️ ID 52 (2026-09-23): 認証主体の毎リクエスト決定論的初期化 (handler.auth_identity = "")。
    - 🛡️ ID 53 (2026-09-23): Tailscale Serve 等のリバースプロキシ経由時は実IP (ledger_ip) で台帳照合。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import database
from auth_rate_limiter import get_auth_rate_limiter
from server.sync_token_manager import get_sync_token_manager

# 親ロガー local_sync_server へのログ伝播 (propagation) を担保する階層ロガー
logger = logging.getLogger("local_sync_server.auth_checks")


def get_bearer_token(headers: Any) -> str:
    """Authorization ヘッダーから Bearer トークンを抽出する。

    Args:
        headers: リクエストヘッダー (dict または email.message.Message)。

    Returns:
        str: 抽出されたトークン文字列 (未指定時は空文字)。
    """
    if hasattr(headers, "get"):
        auth_header = headers.get("Authorization", "")
    else:
        auth_header = ""
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer ") :].strip()
    return ""


def is_private_ip(client_ip: str) -> bool:
    """接続元IPがローカルまたは同一LAN・Tailscale内のプライベートIPか判定する。

    Args:
        client_ip: クライアントの IP アドレス文字列。

    Returns:
        bool: プライベート/ループバック IP の場合 True。
    """
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


def infer_device_name(user_agent: str) -> str:
    """User-Agent 文字列からデバイス表示名を推定する。

    Notes:
        🛡️ ID 50/53 (2026-09-23): 非ブラウザUA（PC側の Python クライアント等）を
        「スマホブラウザ」と偽装すると、ボスが承認ダイアログで正体を判別できない
        （1クリック横取りの温床）。ブラウザUA（Mozilla 系）以外は正直なラベルを返す。

    Args:
        user_agent: User-Agent ヘッダ値。

    Returns:
        str: 端末表示名。
    """
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
    if "mozilla" in ua:
        return "スマホブラウザ"
    return "⚠️ 非ブラウザ端末"


def check_auth(handler: Any) -> bool:
    """Bearerトークンを検証する。LAN内接続時は柔軟に自己治癒を許可する。

    Sprint A 第2弾: 401 認証失敗のIP別レートリミット (1分10回失敗で5分間締め出し)。
    締め出し期間中は 429 Too Many Requests と Retry-After ヘッダーを返す。
    さらに、デバイス台帳 (devices テーブル) と照合し、個別失効 (Revoke) 済み端末を 403 で拒絶する。

    Args:
        handler: HTTPリクエストハンドラインスタンス (DeskPetSyncHandler)。

    Returns:
        bool: 認証成功時は True。失敗時はエラー応答を送信して False。
    """
    client_ip = handler.client_address[0] if handler.client_address else "unknown"
    user_agent = handler.headers.get("User-Agent", "") if hasattr(handler, "headers") else ""
    headers = getattr(handler, "headers", None) or {}
    rate_limiter = get_auth_rate_limiter()

    # 認証主体の毎リクエストリセット (手帳 ID 52): 前リクエストの identity 残留を
    # 排除し、未認証経路 (identity 不明 = 空文字) を決定論的に初期化する。
    handler.auth_identity = ""

    # 🛡️ ID 53 / P2-N5 (2026-09-23): 中継経由 (Tailscale Serve 等) は TCPピアが
    # 127.0.0.1 になるため、台帳照会とレートリミットのキーを実IP (ledger_ip) へ統一する。
    host_hdr = str(headers.get("Host", "")) if hasattr(headers, "get") else ""
    if hasattr(handler, "_resolve_ledger_client_ip"):
        ledger_ip = handler._resolve_ledger_client_ip(client_ip, host_hdr, headers)
    else:
        ledger_ip = client_ip
    limiter_key = ledger_ip or client_ip
    is_trusted = is_private_ip(limiter_key)

    # 1. 締め出し判定 (外部IPのみ。同一LAN・Tailscale端末は再起動時のトークン不整合による誤遮断を防止)
    if not is_trusted:
        blocked, retry_after = rate_limiter.is_blocked(limiter_key)
        if blocked:
            logger.warning(
                f"🚨 [RateLimit] IP {limiter_key} はロックアウト中のため拒否 (残り {retry_after}秒)"
            )
            try:
                handler.send_response(429)
                handler.send_header("Content-Type", "application/json; charset=utf-8")
                handler.send_header("Retry-After", str(retry_after))
                handler._set_cors_headers()
                handler.end_headers()
                handler.wfile.write(
                    json.dumps(
                        {
                            "status": "error",
                            "message": "Too many failed authentication attempts. Please try again later.",
                            "retry_after": retry_after,
                        },
                        ensure_ascii=False,
                    ).encode("utf-8")
                )
            except (OSError, RuntimeError) as e:
                logger.debug(f"レートリミット応答送信失敗: {e}")
            return False

    token_mgr = get_sync_token_manager()
    bearer = get_bearer_token(headers)

    # 2. 有効なBearerトークンがあれば認証OK（デバイス台帳で失効状態を検査）。
    # 🛡️ P0-3: loopback 信頼は3条件（TCPピア + Host + プロキシヘッダ無し）でのみ成立
    if hasattr(handler, "_is_trusted_loopback"):
        trusted_loopback = handler._is_trusted_loopback(client_ip, host_hdr, headers)
    else:
        trusted_loopback = client_ip in ("127.0.0.1", "::1", "localhost")

    if bearer:
        dev = None
        is_valid_token = False
        if token_mgr.verify_loopback(bearer):
            # 🛡️ P0-3: loopback 専用トークン（PC内ブラウザ用）は信頼できる loopback でのみ有効。
            if trusted_loopback:
                is_valid_token = True
                handler.auth_identity = "pc-loopback"
            else:
                logger.warning(
                    f"🚫 [SyncAuth] loopback 専用トークンを非ループバック({client_ip})から拒否しました"
                )
        elif token_mgr.verify(bearer):
            # 🛡️ マスタートークン（PCマスターキー）は信頼できる loopback 専用（Agent Bridge・MCPサーバー）
            if trusted_loopback:
                is_valid_token = True
                handler.auth_identity = "agent"
            else:
                try:
                    dev = database.sync_device_session(
                        bearer=bearer,
                        ip_address=ledger_ip,
                        user_agent=user_agent,
                    )
                    is_valid_token = dev is not None
                except Exception as e:
                    # 🛡️ Fail-Closed: 台帳照合に失敗した場合は認証を成立させない
                    logger.warning(f"🚫 [SyncAuth] 台帳照合エラーによりマスタートークンを拒否 (Fail-Closed): {e}")
                    dev = None
                    is_valid_token = False
                if not is_valid_token:
                    logger.warning(
                        f"🚫 [SyncAuth] 台帳未登録のマスタートークンを非ループバック({client_ip})から拒否しました"
                    )
        else:
            try:
                dev = database.verify_device_token(bearer)
                if dev is not None:
                    is_valid_token = True
                    if dev.is_revoked != 1:
                        database.touch_device_last_seen(
                            dev.token_hash, ip_address=ledger_ip, user_agent=user_agent
                        )
            except Exception as e:
                # 🛡️ Fail-Closed: 照会失敗時は認証を成立させない
                logger.warning(f"🚫 [SyncAuth] 個別端末トークン照合エラー (Fail-Closed で拒否): {e}")
                dev = None
                is_valid_token = False

        if is_valid_token:
            if dev is not None and dev.is_revoked == 1:
                logger.warning(
                    f"🚫 [SyncAuth] 失効済みデバイスからのアクセス拒否: ID={dev.id}, name={dev.device_name} (IP: {client_ip})"
                )
                try:
                    handler.send_response(403)
                    handler.send_header("Content-Type", "application/json; charset=utf-8")
                    handler._set_cors_headers()
                    handler.end_headers()
                    handler.wfile.write(
                        json.dumps(
                            {"status": "forbidden", "message": "この端末の連携は失効しています。"},
                            ensure_ascii=False,
                        ).encode("utf-8")
                    )
                except (OSError, RuntimeError) as e:
                    logger.debug(f"失効通知応答送信失敗: {e}")
                return False
            # 認証主体: 台帳照合に成功した端末 (手帳 ID 52: identity ベース自己承認判定用)
            if dev is not None:
                device_uuid = getattr(dev, "device_uuid", None)
                if device_uuid:
                    handler.auth_identity = f"device:{device_uuid}"
                else:
                    handler.auth_identity = f"device:#{dev.id}"
            return True

    # 3. GETリクエストの閲覧許可は「同一PC内 (ループバック)」のみ (ゼロトラスト強化 2026-09-12)
    if getattr(handler, "command", "") == "GET" and trusted_loopback:
        return True

    # 4. 認証失敗: 外部IPのみ失敗カウントを記録
    if not is_trusted:
        rate_limiter.record_failure(client_ip)

    logger.warning(f"🚫 [SyncAuth] 認証失敗: {getattr(handler, 'path', '')} (IP: {client_ip})")
    try:
        handler.send_response(401)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler._set_cors_headers()
        handler.end_headers()
        handler.wfile.write(
            json.dumps(
                {"status": "unauthorized", "message": "有効なトークンがありません。"},
                ensure_ascii=False,
            ).encode("utf-8")
        )
    except (OSError, RuntimeError) as e:
        logger.debug(f"未認証応答送信失敗: {e}")
    return False


def check_webhook_auth(handler: Any) -> bool:
    """外部Webhookリクエストの認証を検証（Secret または Bearerトークン）。

    Args:
        handler: HTTPリクエストハンドラインスタンス。

    Returns:
        bool: 認証成功時は True。
    """
    import webhook_tools

    cfg = webhook_tools.get_webhook_config()
    configured_secret = cfg.get("webhook_secret", "").strip()
    headers = getattr(handler, "headers", None) or {}

    # 1. 共有シークレットが設定されている場合
    if configured_secret:
        incoming_secret = headers.get("X-Webhook-Secret", "").strip() if hasattr(headers, "get") else ""
        bearer = get_bearer_token(headers)
        if incoming_secret == configured_secret or bearer == configured_secret:
            return True

    # 2. 通常のSyncTokenが合致している場合
    token_mgr = get_sync_token_manager()
    if token_mgr.verify(get_bearer_token(headers)):
        return True

    # 3. シークレット未設定かつローカルループバック接続の場合
    client_ip = handler.client_address[0] if handler.client_address else "unknown"
    if not configured_secret and hasattr(handler, "_request_is_trusted_loopback"):
        if handler._request_is_trusted_loopback():
            return True

    logger.warning(f"🚫 [WebhookAuth] 認証失敗: {getattr(handler, 'path', '')} (IP: {client_ip})")
    try:
        handler.send_response(401)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler._set_cors_headers()
        handler.end_headers()
        handler.wfile.write(
            json.dumps(
                {"status": "unauthorized", "message": "Webhook Secret または有効なトークンがありません。"},
                ensure_ascii=False,
            ).encode("utf-8")
        )
    except (OSError, RuntimeError) as e:
        logger.debug(f"Webhook未認証応答送信失敗: {e}")
    return False


__all__: list[str] = [
    "get_bearer_token",
    "is_private_ip",
    "infer_device_name",
    "check_auth",
    "check_webhook_auth",
]
