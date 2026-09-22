#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - Web Push 送信エンジン (push_sender.py)

スマホ PWA (Service Worker) 登録済みの全購読先へ pywebpush で Web Push を
送信する fire-and-forget モジュール。

設計意図:
    - HTTP ハンドラや GUI スレッドを 1ms たりともブロックしないため、
      公開 API send_push_to_all_devices() は処理を daemon スレッドへ丸投げして
      即 return する (sync_all_discovered_models のバックグラウンドパターン踏襲)。
    - Push Service が 404/410 (購読無効) を返した購読は台帳から掃除する
      (Fail-Safe)。それ以外の失敗はログ記録のみで継続する。
    - 購読 0 件時は DEBUG ログを出して即終了し、pywebpush を import コスト以上に
      動かさない。
"""

import json
import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict, Optional

from pywebpush import webpush, WebPushException
from py_vapid import Vapid

from storage.push_subscription_repo import (
    get_all_subscriptions,
    delete_subscription_by_endpoint,
)
from storage.vapid_key_repo import get_or_create_vapid_keys

logger = logging.getLogger(__name__)

# pywebpush 内部の requests.post へ渡すタイムアウト (秒)。
# 既定値は 10000 秒 (実測: WebPusher.send の kwargs.pop("timeout", 10000)) で
# 実用上無限待ちと等しいため、明示的に 10 秒へ制限する。
PUSH_TIMEOUT_SEC: float = 10.0

# 購読が無効とみなし掃除対象とする Push Service の HTTP ステータスコード
STALE_SUBSCRIPTION_STATUS = (404, 410)


def _build_payload(
    title: str,
    body: str,
    tag: Optional[str],
    event_type: str,
) -> str:
    """Service Worker へ渡す JSON ペイロードを構築する。

    Args:
        title: 通知タイトル。
        body: 通知本文。
        tag: 通知の上書きグループタグ (任意)。
        event_type: イベント種別識別子 (例: "approval_request")。

    Returns:
        JSON 文字列化したペイロード。
    """
    payload: Dict[str, Any] = {
        "title": title,
        "body": body,
        "event_type": event_type,
        "timestamp": int(datetime.now().timestamp() * 1000),
    }
    if tag:
        payload["tag"] = tag
    return json.dumps(payload, ensure_ascii=False)


def _build_push_request(
    title: str,
    body: str,
    tag: Optional[str],
    event_type: str,
    db_path: str,
) -> Optional[Dict[str, Any]]:
    """送信に必要な全データを呼び出し元スレッドで事前構築する。

    DB 読み取り（ミリ秒オーダー）を呼び出し元で完結させることで、
    バックグラウンドスレッドが DB ファイルを保持し続けることを防ぐ
    （テスト環境の一時ファイル削除との競合・WinError 32 の構造的回避）。

    Args:
        title: 通知タイトル。
        body: 通知本文。
        tag: 通知の上書きグループタグ (任意)。
        event_type: イベント種別識別子。
        db_path: データベースファイルのパス。

    Returns:
        送信リクエスト辞書 (subscriptions / vapid / claims / payload)。
        DB 未作成・購読 0 件・準備失敗時は None。
    """
    # DB が未作成の環境 (テスト・初回起動前) で空ファイルを作らないよう事前ガード
    if not os.path.exists(db_path):
        logger.debug(f"[Push] DB 未作成のため送信をスキップしました: {db_path}")
        return None

    try:
        subscriptions = get_all_subscriptions(db_path=db_path)
    except Exception as e:
        logger.error(f"[Push] 購読一覧の取得に失敗したため送信を中止しました: {e}")
        return None

    if not subscriptions:
        logger.debug("[Push] 購読済みデバイスが 0 件のため送信をスキップしました")
        return None

    try:
        vapid_keys = get_or_create_vapid_keys(db_path=db_path)
        vapid = Vapid.from_pem(vapid_keys.private_key_pem.encode("ascii"))
        claims: Dict[str, str] = {"sub": vapid_keys.subject}
    except Exception as e:
        logger.error(f"[Push] VAPID 鍵の準備に失敗したため送信を中止しました: {e}")
        return None

    payload = _build_payload(title, body, tag, event_type)
    return {
        "subscriptions": subscriptions,
        "vapid": vapid,
        "claims": claims,
        "payload": payload,
        "event_type": event_type,
    }


def _deliver_push_request(request: Dict[str, Any], db_path: str) -> None:
    """構築済みリクエストに基づき Web Push 送信を実行する (ワーカー本体)。

    ネットワーク I/O (秒オーダー) のみを担い、DB からの読み取りは行わない。
    無効購読 (404/410) の掃除書き込みのみ発生しうる。

    Args:
        request: _build_push_request の戻り値。
        db_path: 無効購読掃除時に使用するデータベースファイルのパス。
    """
    subscriptions: Any = request["subscriptions"]
    vapid: Any = request["vapid"]
    claims: Dict[str, str] = request["claims"]
    payload: str = request["payload"]

    sent_count = 0
    for sub in subscriptions:
        subscription_info: Dict[str, Any] = {
            "endpoint": sub.endpoint,
            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
        }
        try:
            resp = webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=vapid,
                vapid_claims=claims,
                timeout=PUSH_TIMEOUT_SEC,
            )
            sent_count += 1
            logger.debug(
                f"[Push] 送信成功: status={getattr(resp, 'status_code', '?')}, "
                f"endpoint={sub.endpoint[:60]}..."
            )
        except WebPushException as e:
            status_code = e.status_code
            if status_code in STALE_SUBSCRIPTION_STATUS:
                logger.info(
                    f"[Push] 無効購読 ({status_code}) を検出・掃除します: "
                    f"endpoint={sub.endpoint[:60]}..."
                )
                try:
                    delete_subscription_by_endpoint(sub.endpoint, db_path=db_path)
                except Exception as cleanup_error:
                    logger.error(f"[Push] 無効購読の掃除に失敗しました: {cleanup_error}")
            else:
                logger.error(
                    f"[Push] 送信失敗 (status={status_code}): {e} "
                    f"endpoint={sub.endpoint[:60]}..."
                )
        except Exception as e:
            logger.error(f"[Push] 送信中に予期しない例外 (送信は継続): {e}")

    logger.info(
        f"📲 [Push] {sent_count}/{len(subscriptions)} 台へ Push 送信しました "
        f"(event_type={request['event_type']})"
    )


def _deliver_push_sync(
    title: str,
    body: str,
    tag: Optional[str],
    event_type: str,
    db_path: str = "neo_secretary.db",
) -> None:
    """全購読先への Web Push 送信を同期的に実行する (テスト・同期経路用)。

    Args:
        title: 通知タイトル。
        body: 通知本文。
        tag: 通知の上書きグループタグ (任意)。
        event_type: イベント種別識別子。
        db_path: データベースファイルのパス。
    """
    request = _build_push_request(title, body, tag, event_type, db_path)
    if request is None:
        return
    _deliver_push_request(request, db_path)


def send_push_to_all_devices(
    title: str,
    body: str,
    tag: Optional[str] = None,
    event_type: str = "generic",
    db_path: str = "neo_secretary.db",
) -> None:
    """全購読デバイスへ Web Push をバックグラウンド送信する (fire-and-forget)。

    daemon スレッドへ処理を委譲して即 return するため、HTTP ハンドラ・GUI・
    リマインダー周期処理を一切ブロックしない。送信失敗時も呼び出し元へは
    例外を伝播させない (ワーカー内で Fail-Safe 完結)。

    設計注記: DB 読み取りと VAPID 鍵の準備 (ミリ秒オーダー) は呼び出し元で
    同期実行し、ワーカーはネットワーク送信のみを担う。これによりバックグラウンド
    スレッドが DB ファイルを長時間保持することを構造的に防ぐ。

    Args:
        title: 通知タイトル。
        body: 通知本文。
        tag: 通知の上書きグループタグ (任意)。
        event_type: イベント種別識別子 (既定: "generic")。
        db_path: データベースファイルのパス。
    """
    try:
        request = _build_push_request(title, body, tag, event_type, db_path)
    except Exception as e:
        logger.error(f"[Push] 送信リクエストの構築に失敗したため送信を中止しました: {e}")
        return

    if request is None:
        return

    worker = threading.Thread(
        target=_deliver_push_request,
        args=(request, db_path),
        daemon=True,
        name="WebPushSender",
    )
    worker.start()
