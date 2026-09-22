"""
Neo-Secretary ストレージ層 - VAPID 鍵ペアリポジトリ (storage/vapid_key_repo.py)

Web Push 送信時の VAPID 署名に使用する ECDSA P-256 鍵ペアの生成・永続化を
提供します。vapid_keys テーブルは単一行運用とし、鍵が存在する限り再生成は
行いません（鍵が変わると全端末の購読が無効化されるため）。
"""

import base64
import logging
from datetime import datetime
from typing import Optional

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid

from storage.connection import get_db_connection
from storage.models import VapidKeys

logger = logging.getLogger(__name__)

# VAPID claims の既定 sub (subject)。push service への連絡先用メールアドレス形式。
DEFAULT_VAPID_SUBJECT: str = "mailto:neo-hisho@localhost"


def _public_key_b64url(vapid: Vapid) -> str:
    """VAPID インスタンスから Base64URL エンコードした非圧縮公開鍵を取り出す。

    Args:
        vapid: 鍵ペアを保持する py_vapid.Vapid インスタンス。

    Returns:
        Base64URL エンコードした P-256 非圧縮公開鍵 (65バイト・padding なし)。
    """
    raw = vapid.public_key.public_bytes(
        encoding=Encoding.X962,
        format=PublicFormat.UncompressedPoint,
    )
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def get_or_create_vapid_keys(db_path: str = "neo_secretary.db") -> VapidKeys:
    """VAPID 鍵ペアを取得し、存在しなければ生成して永続化します。

    単一行運用: 最初の行を正とし、2行目以降が万一存在しても id 昇順の先頭行を
    使用します。鍵生成は ECDSA P-256 (SECP256R1) で行い、秘密鍵は PKCS#8 PEM
    として平文で DB に永続化します（ローカル単体アプリの脅威モデルでは
    DB ファイル自体が信頼境界の内側にあるため）。

    Args:
        db_path: データベースファイルのパス。

    Returns:
        永続化済みの VapidKeys モデル。

    Raises:
        sqlite3.Error: DB 操作に失敗した場合。
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, private_key_pem, public_key, subject, created_at "
            "FROM vapid_keys ORDER BY id ASC LIMIT 1"
        )
        row = cursor.fetchone()
        if row:
            return VapidKeys(
                id=row[0],
                private_key_pem=row[1],
                public_key=row[2],
                subject=row[3],
                created_at=row[4],
            )

        # 鍵ペアが無い場合のみ生成する（既存購読の無効化を避けるため再生成はしない）
        vapid = Vapid()
        vapid.generate_keys()
        private_pem = vapid.private_pem().decode("ascii")
        public_key_b64 = _public_key_b64url(vapid)

        now = int(datetime.now().timestamp() * 1000)
        cursor.execute(
            "INSERT INTO vapid_keys (private_key_pem, public_key, subject, created_at) "
            "VALUES (?, ?, ?, ?)",
            (private_pem, public_key_b64, DEFAULT_VAPID_SUBJECT, now),
        )
        new_id = int(cursor.lastrowid) if cursor.lastrowid is not None else 1
        logger.info("🔑 [Push] VAPID 鍵ペアを新規生成・永続化しました")
        return VapidKeys(
            id=new_id,
            private_key_pem=private_pem,
            public_key=public_key_b64,
            subject=DEFAULT_VAPID_SUBJECT,
            created_at=now,
        )


def load_vapid_instance(db_path: str = "neo_secretary.db") -> Optional[Vapid]:
    """永続化済み VAPID 鍵から py_vapid.Vapid インスタンスを復元します。

    push_sender が webpush() に渡す vapid_private_key (Vapid インスタンス) を
    生成するためのヘルパーです。

    Args:
        db_path: データベースファイルのパス。

    Returns:
        復元した Vapid インスタンス。鍵が存在しない・復元に失敗した場合は None。
    """
    try:
        keys = get_or_create_vapid_keys(db_path=db_path)
        return Vapid.from_pem(keys.private_key_pem.encode("ascii"))
    except Exception as e:
        logger.error(f"VAPID 鍵インスタンスの復元に失敗しました: {e}")
        return None
