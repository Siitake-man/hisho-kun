#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - Web Push 購読管理APIモジュール (api_push.py)

スマホ PWA (Service Worker) からの Push 購読登録・解除 API を担当する。

契約 (api_context.py / api_agent_bridge.py と同一方式):
- handle_* は ``handler(ctx: ApiContext) -> None`` 署名を持ち、常にレスポンスを
  書き込む。
- Bearer 認証 (_check_auth) は呼び出し元 (local_sync_server.do_POST) で適用
  済みのため、本モジュールでは再検査しない。ただし購読の台帳紐付けのため
  Bearer からデバイスを解決する（解決失敗時は 403 で拒否する: ゼロトラスト）。

ゼロトラスト入力検証:
- endpoint ≤ 2048 文字 / p256dh, auth ≤ 512 文字の長さ上限を検証し、
  超過は HTTP 422 で拒否する。
"""

import json
import logging
from typing import Any, Dict

from api_context import ApiContext
from database import verify_device_token
from storage.push_subscription_repo import (
    upsert_subscription,
    delete_subscription_by_endpoint,
)

logger = logging.getLogger(__name__)

# 入力長上限 (ゼロトラスト: 過大入力による DB 肥大化・DoS の防止)
MAX_ENDPOINT_LENGTH: int = 2048
MAX_KEY_LENGTH: int = 512


def _resolve_db_path() -> str:
    """アプリ既定の DB パスを解決する (テストで patch 可能な Seam)。

    Returns:
        neo_secretary.db の既定パス文字列。
    """
    return "neo_secretary.db"


def _get_bearer_token(ctx: ApiContext) -> str:
    """ApiContext の HTTP ハンドラから Bearer トークンを抽出する。

    DeskPetSyncHandler._get_bearer_token (実在メソッド) への委譲であり、
    テストでは同等のメソッドを持つ MockHandler を注入できる。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        Bearer トークン文字列 (未設定時は空文字)。
    """
    getter = getattr(ctx.handler, "_get_bearer_token", None)
    if callable(getter):
        token = getter()
        return token if isinstance(token, str) else ""
    return ""


def _parse_json_body(ctx: ApiContext) -> Dict[str, Any] | None:
    """リクエストボディを JSON として安全にパースする。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        パース成功時は辞書、失敗時は None。
    """
    if not ctx.body:
        return {}
    try:
        if isinstance(ctx.body, bytes):
            data = json.loads(ctx.body.decode("utf-8"))
        else:
            data = json.loads(ctx.body)
    except (ValueError, UnicodeDecodeError) as e:
        logger.warning(f"[Push API] JSON ボディの解析に失敗しました: {e}")
        return None
    return data if isinstance(data, dict) else None


def handle_push_subscribe(ctx: ApiContext) -> None:
    """Push 購読の登録・更新 (POST /api/push/subscribe) を処理する。

    期待ボディ: {"endpoint": "...", "keys": {"p256dh": "...", "auth": "..."}}
    Bearer から解決したデバイスの token_hash に紐付けて台帳へ upsert する。

    Args:
        ctx: リクエストコンテキスト。
    """
    # Lazy Headers 契約: ここで begin_json_response() を先送りしない。
    # 検証失敗時に send_error_json(4xx) が正しいステータスコードでヘッダーを
    # 送出できるよう、ヘッダー送出は write_json / send_error_json に委ねる。
    data = _parse_json_body(ctx)
    if data is None:
        ctx.send_error_json("invalid JSON body", status_code=400)
        return

    endpoint = data.get("endpoint")
    keys = data.get("keys")
    if not isinstance(endpoint, str) or not endpoint:
        ctx.send_error_json("endpoint is required", status_code=400)
        return
    if not isinstance(keys, dict) or not isinstance(keys.get("p256dh"), str) or not isinstance(keys.get("auth"), str):
        ctx.send_error_json("keys.p256dh and keys.auth are required", status_code=400)
        return
    p256dh = keys["p256dh"]
    auth = keys["auth"]

    # ゼロトラスト: 長さ上限検証（超過は 422 Unprocessable Entity で拒否）
    if len(endpoint) > MAX_ENDPOINT_LENGTH:
        ctx.send_error_json("endpoint too long", status_code=422)
        return
    if len(p256dh) > MAX_KEY_LENGTH or len(auth) > MAX_KEY_LENGTH:
        ctx.send_error_json("key too long", status_code=422)
        return

    bearer = _get_bearer_token(ctx)
    device = verify_device_token(bearer, db_path=_resolve_db_path())
    if device is None or device.is_revoked == 1:
        logger.warning(
            f"🚫 [Push API] 未登録・失効済みデバイスからの購読要求を拒否しました (ip={ctx.client_ip})"
        )
        ctx.send_error_json("unknown or revoked device", status_code=403)
        return

    try:
        upsert_subscription(
            token_hash=device.token_hash,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            db_path=_resolve_db_path(),
        )
    except Exception as e:
        logger.error(f"[Push API] 購読の保存に失敗しました: {e}")
        ctx.send_error_json("failed to save subscription", status_code=500)
        return

    logger.info(f"🔔 [Push API] 購読を受け付けました: endpoint={endpoint[:60]}...")
    ctx.write_json({"status": "ok"}, ensure_ascii=False)


def handle_push_unsubscribe(ctx: ApiContext) -> None:
    """Push 購読の解除 (POST /api/push/unsubscribe) を処理する。

    期待ボディ: {"endpoint": "..."}。該当購読が存在しない場合も冪等成功
    ({\"status\": \"ok\"}) を返す（クライアント側の Service Worker 解除完了を優先）。

    Args:
        ctx: リクエストコンテキスト。
    """
    # Lazy Headers 契約: ヘッダー送出は write_json / send_error_json に委ねる
    # (検証失敗時に 400/422 を正しく返すための先行送出は行わない)。
    data = _parse_json_body(ctx)
    if data is None:
        ctx.send_error_json("invalid JSON body", status_code=400)
        return

    endpoint = data.get("endpoint")
    if not isinstance(endpoint, str) or not endpoint:
        ctx.send_error_json("endpoint is required", status_code=400)
        return
    if len(endpoint) > MAX_ENDPOINT_LENGTH:
        ctx.send_error_json("endpoint too long", status_code=422)
        return

    try:
        delete_subscription_by_endpoint(endpoint, db_path=_resolve_db_path())
    except Exception as e:
        logger.error(f"[Push API] 購読の解除に失敗しました: {e}")
        ctx.send_error_json("failed to delete subscription", status_code=500)
        return

    logger.info(f"🔔 [Push API] 購読を解除しました: endpoint={endpoint[:60]}...")
    ctx.write_json({"status": "ok"}, ensure_ascii=False)


def handle_get_push_vapid_key(ctx: ApiContext) -> bool:
    """Push 購読用の VAPID 公開鍵を返却する (GET /api/push/vapid_key)。

    PWA (pet_push.js) が pushManager.subscribe の applicationServerKey として
    使用する Base64URL エンコード済み P-256 公開鍵を JSON で返す。
    公開鍵は公開情報であり秘密鍵は返さない (ゼロトラスト)。
    Bearer 認証は呼び出し元 (do_GET の GET_PATH_HANDLERS ディスパッチ) で適用済み。

    Args:
        ctx: リクエストコンテキスト。

    Returns:
        レスポンス書き込み済みの場合 True。
    """
    from storage.vapid_key_repo import get_or_create_vapid_keys

    try:
        keys = get_or_create_vapid_keys()
        ctx.write_json({"status": "ok", "public_key": keys.public_key}, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"[Push API] VAPID 公開鍵の取得に失敗しました: {e}")
        ctx.send_error_json("failed to load VAPID public key", status_code=500)
        return True
