"""
Neo-Secretary ストレージ層 - Web Push 購読リポジトリ (storage/push_subscription_repo.py)

スマホ PWA (Service Worker) から登録される Push Subscription の台帳
(push_subscriptions テーブル) に対する登録・取得・削除を提供します。
endpoint は UNIQUE 制約により、同一端末・同一 Service Worker の再登録は
冪等な UPDATE として扱われます（重複行の増殖防止）。
"""

import logging
from datetime import datetime
from typing import List

from storage.connection import get_db_connection
from storage.models import PushSubscription

logger = logging.getLogger(__name__)


def _now_ms() -> int:
    """現在時刻を Unix Timestamp ミリ秒で返す内部ヘルパー。

    Returns:
        現在時刻（Unix Timestamp ミリ秒）。
    """
    return int(datetime.now().timestamp() * 1000)


def upsert_subscription(
    token_hash: str,
    endpoint: str,
    p256dh: str,
    auth: str,
    db_path: str = "neo_secretary.db",
) -> int:
    """Push Subscription を登録、または同一 endpoint の既存行を更新します。

    Args:
        token_hash: 登録元デバイスの認証トークン SHA-256 ハッシュ。
        endpoint: Push Service のエンドポイント URL（UNIQUE キー）。
        p256dh: ECDH 鍵合意用クライアント公開鍵 (Base64URL)。
        auth: 認証シークレット (Base64URL)。
        db_path: データベースファイルのパス。

    Returns:
        登録または更新された購読レコードの ID。

    Raises:
        sqlite3.Error: DB 書き込みに失敗した場合（呼び出し元で Fail-Safe）。
    """
    now = _now_ms()
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO push_subscriptions (token_hash, endpoint, p256dh, auth, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(endpoint) DO UPDATE SET
                token_hash = excluded.token_hash,
                p256dh = excluded.p256dh,
                auth = excluded.auth,
                updated_at = excluded.updated_at
            """,
            (token_hash, endpoint, p256dh, auth, now, now),
        )
        cursor.execute("SELECT id FROM push_subscriptions WHERE endpoint = ?", (endpoint,))
        row = cursor.fetchone()
        sub_id = int(row[0]) if row else 0
        logger.info(f"🔔 [Push] 購読を保存しました: id={sub_id}, endpoint={endpoint[:60]}...")
        return sub_id


def get_all_subscriptions(db_path: str = "neo_secretary.db") -> List[PushSubscription]:
    """登録済みの全 Push Subscription を取得します。

    Args:
        db_path: データベースファイルのパス。

    Returns:
        PushSubscription モデルのリスト（登録 0 件時は空リスト）。
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, token_hash, endpoint, p256dh, auth, created_at, updated_at
            FROM push_subscriptions
            ORDER BY id ASC
            """
        )
        rows = cursor.fetchall()
        return [
            PushSubscription(
                id=row[0],
                token_hash=row[1],
                endpoint=row[2],
                p256dh=row[3],
                auth=row[4],
                created_at=row[5],
                updated_at=row[6],
            )
            for row in rows
        ]


def delete_subscription_by_endpoint(endpoint: str, db_path: str = "neo_secretary.db") -> bool:
    """指定 endpoint の Push Subscription を削除します。

    Push Service が 404/410 を返した購読の掃除 (Fail-Safe) に使用します。

    Args:
        endpoint: 削除対象のエンドポイント URL。
        db_path: データベースファイルのパス。

    Returns:
        削除対象が存在し削除できた場合 True、存在しなかった場合 False。
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"🔔 [Push] 無効購読を掃除しました: endpoint={endpoint[:60]}...")
        return deleted


def delete_subscriptions_by_token_hash(token_hash: str, db_path: str = "neo_secretary.db") -> int:
    """指定 token_hash（デバイス）の全 Push Subscription を一括削除します。

    端末失効 (Revoke) 時に、その端末の購読を台帳から一掃するために使用します。

    Args:
        token_hash: デバイスの認証トークン SHA-256 ハッシュ。
        db_path: データベースファイルのパス。

    Returns:
        削除されたレコード件数。
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM push_subscriptions WHERE token_hash = ?", (token_hash,))
        deleted = cursor.rowcount
        if deleted > 0:
            logger.info(f"🔔 [Push] デバイス失効に伴い購読を {deleted} 件削除しました")
        return deleted
