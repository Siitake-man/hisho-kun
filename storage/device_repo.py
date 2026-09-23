"""
Neo-Secretary ストレージ層 - 端末台帳リポジトリ (storage/device_repo.py)

ゼロトラスト端末台帳 (devices テーブル) の個別トークン失効管理、端末登録、
セッション同期、アクセス履歴の更新を提供します。
"""

import hashlib
import logging
import secrets
import sqlite3
import uuid
from datetime import datetime
from typing import List, Optional

from storage.connection import get_db_connection
from storage.models import Device

logger = logging.getLogger(__name__)


def _is_loopback_ip(ip_address: Optional[str]) -> bool:
    """IPアドレス文字列がループバック相当かを判定する (Fail-Safe)。"""
    if not ip_address:
        return False
    return ip_address.startswith("127.") or ip_address in ("::1", "localhost")


def normalize_device_uuid(raw: Optional[str]) -> Optional[str]:
    """端末自己生成UUID（X-Device-UUID ヘッダ）を正規化・検証する (ID 50 / 2026-09-23)。

    PWA が ``crypto.randomUUID()`` で生成し localStorage に永続化する UUID を、
    台帳の行再利用キーとして受け入れる。**推測不能性**が同一性の前提のため、
    厳格な UUID 形式のみを受け付け、それ以外（空・不正・過大長）は None を返す
    （呼び出し側は従来キーへフォールバックする＝後方互換）。

    Notes:
        UUID は「行の同一性」にのみ使用し、**認証の根拠にはしない**
        （資格情報の束縛は人間承認済みペアリング経路のみ＝AD-3 不変）。

    Args:
        raw: ヘッダ等から受け取った生文字列。

    Returns:
        Optional[str]: 正規形（小文字・ハイフン付き）の UUID。不正時は None。
    """
    if not raw:
        return None
    candidate = str(raw).strip()
    if not candidate or len(candidate) > 64:
        return None
    try:
        return str(uuid.UUID(candidate))
    except (ValueError, AttributeError, TypeError):
        return None


def register_device(
    device_name: str,
    token_hash: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    db_path: str = "neo_secretary.db",
    *,
    reuse_identity: bool = False,
    device_uuid: Optional[str] = None
) -> int:
    """
    新規端末を登録、または同一token_hashの端末情報を更新します。

    Notes:
        🛡️ P0-1 (2026-09-22): 既存行の失効フラグ (is_revoked) は決して書き換えません。
        失効の解除は restore_device() を呼ぶ明示的な人間操作のみです
        (AD-1: 失効のチャネル横断不変条件)。

        🔐 reuse_identity=True は「同一IP+同一端末名の既存行を再利用して新しい資格情報
        (token_hash) を束縛する」動作を許可します。これは **人間承認を伴うペアリング経路
        (issue_device_token) 専用** です。認証経路 (sync_device_session) で有効化すると、
        マスタートークン保持端末が他端末の身元を乗っ取り、失効を回避できてしまうため
        既定値は False (Fail-Closed) とします。

    Args:
        device_name: 端末表示名
        token_hash: 認証トークンのSHA-256ハッシュ文字列
        ip_address: 接続元IP
        user_agent: 接続元User-Agent
        db_path: データベースファイルのパス
        reuse_identity: 同一IP+端末名の既存行の再利用 (資格情報の束縛) を許可するか。
            ペアリング経路のみ True。既定 False。
        device_uuid: 端末自己生成UUID（X-Device-UUID ヘッダ。ID 50 / 2026-09-23）。
            提示時は UUID 一致を最優先の行再利用キーとする。フォールバックは
            ``device_uuid IS NULL`` の行に限定され、UUID 記名済み行は乗っ取れない。

    Returns:
        登録または更新されたデバイスID
    """
    now = int(datetime.now().timestamp() * 1000)
    normalized_uuid = normalize_device_uuid(device_uuid)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM devices WHERE token_hash = ?
        """, (token_hash,))
        row = cursor.fetchone()
        if row is None and reuse_identity and normalized_uuid:
            # 🛡️ ID 50 (2026-09-23): 端末自己生成UUID（MACの代替）を**最優先**の行再利用キーとする。
            # UUID 一致＝同一端末として扱い、IP・UA・経路（Serve/LAN）が変わっても1行に集約する。
            cursor.execute("""
                SELECT id FROM devices WHERE device_uuid = ?
                ORDER BY last_seen DESC LIMIT 1
            """, (normalized_uuid,))
            row = cursor.fetchone()
        if row is None and reuse_identity:
            # 🛡️ P1-1 (2026-09-23 査読): フォールバックは **device_uuid IS NULL の行のみ**を対象とする。
            # 攻撃者はヘッダを自由に外せるため、「UUID を送らないクライアント」から
            # UUID 記名済み行（＝真の構造排除の対象）へ到達できると排除が形骸化する。
            # また UUID 記名済みクライアントにも開放することで、UUID 導入前の旧行
            # （NULL 行）を採用して UUID を束縛でき、移行ゾンビ行の発生も防ぐ (P2-1)。
            if ip_address and not _is_loopback_ip(ip_address):
                cursor.execute("""
                    SELECT id FROM devices
                    WHERE ip_address = ? AND device_name = ? AND device_uuid IS NULL
                    ORDER BY last_seen DESC LIMIT 1
                """, (ip_address, device_name))
            else:
                cursor.execute("""
                    SELECT id FROM devices
                    WHERE device_name = ?
                      AND COALESCE(user_agent, '') = COALESCE(?, '')
                      AND device_uuid IS NULL
                    ORDER BY last_seen DESC LIMIT 1
                """, (device_name, user_agent))
            row = cursor.fetchone()

        if row:
            dev_id = int(row[0])
            # 🛡️ P0-1: 既存行の失効フラグ (is_revoked) には一切触れない。
            # 失効の解除は restore_device() を呼ぶ明示的な人間操作
            # (♻️ 接続復帰 / 承認済み再ペアリング) のみに限定する (AD-1: 失効のチャネル横断不変条件)。
            # ここで失効フラグを 0 に戻すと、失効端末がリクエストを1回送るだけで
            # 無言で復活する「失効巻き戻し」脆弱性になる (2026-09-22 レビュー P0-1)。
            # なお資格情報 (token_hash) は更新する: 失効中は新トークンでも 403 のままとなり、
            # 人間が復帰させた時点で最新トークンが有効になる (資格情報ローテーション)。
            cursor.execute("""
                UPDATE devices
                SET device_name = ?,
                    token_hash = ?,
                    ip_address = COALESCE(?, ip_address),
                    user_agent = COALESCE(?, user_agent),
                    device_uuid = COALESCE(?, device_uuid),
                    last_seen = ?
                WHERE id = ?
            """, (device_name, token_hash, ip_address, user_agent, normalized_uuid, now, dev_id))
            logger.info(f"デバイス台帳更新: ID={dev_id}, name={device_name}")
            return dev_id
        else:
            try:
                cursor.execute("""
                    INSERT INTO devices (
                        device_name, token_hash, ip_address, user_agent,
                        created_at, last_seen, is_revoked, device_uuid
                    ) VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                """, (device_name, token_hash, ip_address, user_agent, now, now, normalized_uuid))
            except sqlite3.IntegrityError:
                # 🛡️ P3-1 (2026-09-23 査読): 並列ペアリングで同一UUIDが競合した場合は
                # **先着行を採用**して資格情報を更新する (ThreadingHTTPServer の並列受理対策)。
                # 注意: 行は先着・資格情報 (token_hash) は後着が勝つため、先着側のトークンは
                # 無効化される (Fail-Closed 側。手動再承認で復帰可能)。発生条件は
                # 「同一UUIDの2並列ペアリング＋人間承認2回」と狭い。
                if not normalized_uuid:
                    raise
                cursor.execute("""
                    SELECT id FROM devices WHERE device_uuid = ?
                    ORDER BY last_seen DESC LIMIT 1
                """, (normalized_uuid,))
                existing = cursor.fetchone()
                if existing is None:
                    raise
                dev_id = int(existing[0])
                cursor.execute("""
                    UPDATE devices
                    SET device_name = ?, token_hash = ?, ip_address = COALESCE(?, ip_address),
                        user_agent = COALESCE(?, user_agent), last_seen = ?
                    WHERE id = ?
                """, (device_name, token_hash, ip_address, user_agent, now, dev_id))
                logger.info(f"デバイス台帳更新 (UUID競合の先着採用): ID={dev_id}, name={device_name}")
                return dev_id
            dev_id = int(cursor.lastrowid)
            logger.info(f"新規デバイス登録: ID={dev_id}, name={device_name}")
            return dev_id


def get_device_by_token_hash(token_hash: str, db_path: str = "neo_secretary.db") -> Optional[Device]:
    """
    token_hash に合致するデバイス情報を取得します。

    Args:
        token_hash: トークンのSHA-256ハッシュ
        db_path: データベースファイルのパス

    Returns:
        Device モデル、見つからない場合は None
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, device_name, token_hash, ip_address, user_agent,
                   created_at, last_seen, is_revoked, device_uuid
            FROM devices
            WHERE token_hash = ?
        """, (token_hash,))
        row = cursor.fetchone()
        if not row:
            return None
        return Device(
            id=row[0],
            device_name=row[1],
            token_hash=row[2],
            ip_address=row[3],
            user_agent=row[4],
            created_at=row[5],
            last_seen=row[6],
            is_revoked=row[7],
            device_uuid=row[8],
        )


def sync_device_session(
    bearer: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    db_path: str = "neo_secretary.db"
) -> Optional[Device]:
    """認証済み Bearer トークンに対応する端末を台帳から照会し、last_seen を更新する。

    SHA-256 ハッシュ化をデータベース層の内部手順として隠蔽し、呼び出し側
    (HTTPサーバー) からハッシュアルゴリズムの詳細を取り除く (Deep Module 原則)。

    🛡️ P0-1 (2026-09-22): 本関数は **台帳へ一切書き込まない (読み取り専用)**。
    未登録の資格情報は自動登録せず None を返す。資格情報の登録 (束縛) は
    人間承認を伴うペアリング経路 (issue_device_token) のみが行う。これは
    マスタートークン保持端末が「同一IP+端末名」の既存行を乗っ取り、失効を
    回避する攻撃 (devils-advocate 指摘 P0) を構造的に排除するためである。
    登録済みかつ失効していない端末は last_seen を更新し、失効済み端末は更新しない
    (失効セッションの生存期間を演出しないため)。台帳照会の失敗は握りつぶさず
    上位へ伝播させる (呼び出し側が Fail-Closed で拒否する)。

    Args:
        bearer: 平文の Bearer トークン文字列。
        ip_address: 接続元 IP。
        user_agent: 接続元 User-Agent。
        db_path: データベースファイルのパス。

    Returns:
        該当 Device モデル (照会・更新後の実体。未登録または解決不能な場合は None)。
    """
    token_hash = hashlib.sha256(bearer.encode("utf-8")).hexdigest()
    device = get_device_by_token_hash(token_hash, db_path=db_path)
    if device is None:
        return None
    # 失効済み端末の last_seen は更新しない (失効セッションの生存期間を演出しないため)
    if device.is_revoked != 1:
        touch_device_last_seen(token_hash, ip_address=ip_address, user_agent=user_agent, db_path=db_path)
        # 返却する Device は touch 後の最新状態 (ip_address / user_agent / last_seen) を反映させる
        device = get_device_by_token_hash(token_hash, db_path=db_path)
    return device


def register_device_from_bearer(
    device_name: str,
    bearer: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    db_path: str = "neo_secretary.db"
) -> int:
    """トークン配布 (QRペアリング等) 時に、平文 Bearer を内部でハッシュ化して台帳へ登録する。

    SHA-256 ハッシュ化をデータベース層の内部手順として隠蔽する (Deep Module 原則)。
    同一トークンの再配布時は既存レコードの情報が更新される (register_device 準拠)。

    Args:
        device_name: 端末表示名。
        bearer: 平文の Bearer トークン文字列。
        ip_address: 接続元 IP。
        user_agent: 接続元 User-Agent。
        db_path: データベースファイルのパス。

    Returns:
        登録または更新されたデバイス ID。
    """
    token_hash = hashlib.sha256(bearer.encode("utf-8")).hexdigest()
    return register_device(device_name, token_hash, ip_address=ip_address, user_agent=user_agent, db_path=db_path)


def get_all_devices(db_path: str = "neo_secretary.db") -> List[Device]:
    """
    登録されているすべてのデバイス一覧を最終接続日時の新しい順に取得します。

    Args:
        db_path: データベースファイルのパス

    Returns:
        Device モデルのリスト
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, device_name, token_hash, ip_address, user_agent,
                   created_at, last_seen, is_revoked, device_uuid
            FROM devices
            ORDER BY last_seen DESC, id DESC
        """)
        rows = cursor.fetchall()
        return [
            Device(
                id=row[0],
                device_name=row[1],
                token_hash=row[2],
                ip_address=row[3],
                user_agent=row[4],
                created_at=row[5],
                last_seen=row[6],
                is_revoked=row[7],
                device_uuid=row[8],
            )
            for row in rows
        ]


def revoke_device(device_id: int, db_path: str = "neo_secretary.db") -> bool:
    """
    指定したデバイスを失効状態にします。

    Args:
        device_id: デバイスID
        db_path: データベースファイルのパス

    Returns:
        更新成功時は True
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE devices
            SET is_revoked = 1
            WHERE id = ?
        """, (device_id,))
        success = cursor.rowcount > 0
        if success:
            logger.warning(f"デバイスID={device_id} を失効 (Revoked) に設定しました")
        return success


def revoke_all_devices(db_path: str = "neo_secretary.db") -> int:
    """すべての登録デバイスを一括で失効（Revoke）状態にします。

    「スマホ連携 全解除（トークン再生成）」時に呼び出され、グローバルトークンだけでなく
    台帳に記録された全端末の個別トークンを一括失効させます (P0-1 対策)。

    Args:
        db_path: データベースファイルのパス

    Returns:
        int: 失効状態に更新された端末数
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE devices
            SET is_revoked = 1
            WHERE is_revoked = 0
        """)
        count = cursor.rowcount
        if count > 0:
            logger.warning(f"🔐 [DeviceAuth] 全 {count} 台のデバイスを一括失効 (Revoked) に設定しました")
        return count


def touch_device_last_seen(
    token_hash: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    db_path: str = "neo_secretary.db"
) -> bool:
    """
    通信発生時にデバイスの最終アクセス日時（およびIP/UA）を更新します。

    Args:
        token_hash: 認証トークンのSHA-256ハッシュ
        ip_address: 接続元IP（任意）
        user_agent: 接続元User-Agent（任意）
        db_path: データベースファイルのパス

    Returns:
        更新対象が存在した場合は True
    """
    now = int(datetime.now().timestamp() * 1000)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE devices
            SET last_seen = ?,
                ip_address = COALESCE(?, ip_address),
                user_agent = COALESCE(?, user_agent)
            WHERE token_hash = ?
        """, (now, ip_address, user_agent, token_hash))
        return cursor.rowcount > 0


def restore_device(device_id: int, db_path: str = "neo_secretary.db") -> bool:
    """失効（Revoked）状態のデバイスを再有効化（復帰）します。

    Args:
        device_id: デバイスID
        db_path: データベースファイルのパス

    Returns:
        更新成功時は True
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE devices
            SET is_revoked = 0
            WHERE id = ?
        """, (device_id,))
        success = cursor.rowcount > 0
        if success:
            logger.info(f"デバイスID={device_id} の失効を解除 (Restored) しました")
        return success


def issue_device_token(
    device_name: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    db_path: str = "neo_secretary.db",
    device_uuid: Optional[str] = None
) -> str:
    """新規の暗号論的乱数トークン（64文字hex）を発行し、デバイス台帳に登録します。

    QRペアリング単位で端末固有のトークンを発行することで、端末ごとの個別台帳管理と
    個別失効（Revoke）を実現します。平文トークンは返却のみ行い、DBにはSHA-256ハッシュのみ永続化します。

    Notes:
        🛡️ P0-1 (2026-09-22): 本関数は人間承認（承認ダイアログ）を経たペアリング経路からのみ
        呼び出されるため、reuse_identity=True で「同一IP+同一端末名の既存行の再利用
        (資格情報の再束縛)」を許可します。これにより端末再ペアリング時に台帳が重複増殖せず、
        失効中の端末は復帰判定 (is_revoked=1 のまま返る → 呼び出し側で明示 restore) に回せます。
        認証経路 (sync_device_session) は書き込みを行わないため、身元の乗っ取りは成立しません。

        🛡️ ID 50 (2026-09-23): ``device_uuid``（PWA 自己生成UUID）が提示された場合は
        それを**最優先の行再利用キー**として使用し、IP・UA・経路の変化で行が増殖しない。

    Args:
        device_name: デバイス表示名
        ip_address: 接続元IP
        user_agent: 接続元User-Agent
        db_path: データベースファイルのパス
        device_uuid: 端末自己生成UUID（X-Device-UUID ヘッダ。省略可）

    Returns:
        発行された平文トークン文字列 (64文字hex)
    """
    raw_token = secrets.token_hex(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    register_device(
        device_name=device_name,
        token_hash=token_hash,
        ip_address=ip_address,
        user_agent=user_agent,
        db_path=db_path,
        reuse_identity=True,
        device_uuid=device_uuid,
    )
    logger.info(f"🔐 [DeviceAuth] 端末固有トークンを発行・登録しました: {device_name}")
    return raw_token


def verify_device_token(bearer: str, db_path: str = "neo_secretary.db") -> Optional[Device]:
    """提示されたBearerトークンに対応するデバイス情報を台帳から照会します。

    Args:
        bearer: 平文のBearerトークン文字列
        db_path: データベースファイルのパス

    Returns:
        合致する Device モデル（未登録の場合は None）
    """
    if not bearer:
        return None
    token_hash = hashlib.sha256(bearer.encode("utf-8")).hexdigest()
    return get_device_by_token_hash(token_hash, db_path=db_path)


def cleanup_loopback_devices(db_path: str = "neo_secretary.db") -> int:
    """**失効済み**のループバック端末レコードのみを台帳から一括削除する。

    Notes:
        🛡️ P2-N6 (2026-09-23): 旧実装は有効トークン保有行も無条件に物理削除しており、
        Tailscale Serve 中継のスマホ行（当時は 127.0.0.1 記録）の個別トークンを即死させる
        ID 53 障害の原因だった。失効済み (``is_revoked = 1``) に限定することで、
        将来の誤呼び出しでも有効資格情報は消えない (Fail-Safe)。
        現在この関数を自動で呼ぶ箇所は存在しない (明示的な保守操作専用)。

    Args:
        db_path: データベースファイルのパス

    Returns:
        削除されたレコード件数
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM devices
            WHERE is_revoked = 1
              AND (
                    ip_address IN ('127.0.0.1', '::1', 'localhost')
                 OR ip_address LIKE '127.%'
              )
        """)
        conn.commit()
        return cursor.rowcount


def delete_device(device_id: int, db_path: str = "neo_secretary.db") -> bool:
    """指定されたIDの端末レコードを台帳から物理削除する。

    Args:
        device_id: 削除対象の端末ID
        db_path: データベースファイルのパス

    Returns:
        bool: 削除成功時 True、見つからなかった場合 False
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM devices WHERE id = ?", (device_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"🗑️ [DeviceAuth] 端末レコードを削除しました: ID={device_id}")
        return deleted

