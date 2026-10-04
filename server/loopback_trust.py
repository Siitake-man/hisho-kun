#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - ループバック信頼 ＆ 実IP解決基盤 (loopback_trust / S1c Seam).

(server/loopback_trust.py)

目的:
    Fat モジュール `local_sync_server.py` から、同一PC内ループバック判定、
    RFC 7230 準拠の Host ヘッダー検証、プロキシ中継遮断（loopback 3条件）、
    および中継経由時の実IP解決 (resolve_ledger_client_ip) を独立した
    Deep Module (純粋関数群) として切り出す。

防衛策:
    - 🛡️ P0-3 (2026-09-22): loopback 信頼の3条件 (TCPピア + Host + プロキシヘッダ無し)
    - 🛡️ ID 53 (2026-09-23): 中継経由 (Tailscale Serve 等) は XFF から単一実IPを解決。
      127.0.0.1 の毒値は絶対に返さない (台帳の行増殖・不可視化防止)。
"""

from __future__ import annotations

import ipaddress
import logging
from typing import Any, Dict, List, Optional

# 親ロガー local_sync_server へのログ伝播 (propagation) を担保する階層ロガー
logger = logging.getLogger("local_sync_server.loopback_trust")


def is_loopback(client_ip: str) -> bool:
    """接続元IPが同一PC内（ループバック）かどうかを判定する。

    Args:
        client_ip: クライアント IP アドレス文字列。

    Returns:
        bool: ループバック IP の場合 True。
    """
    return client_ip in ("127.0.0.1", "::1", "localhost")


def host_is_loopback(host_header: str) -> bool:
    """Host ヘッダが loopback 名（localhost / 127.0.0.1 / ::1）かどうかを判定する。

    Notes:
        🛡️ P0-3 (2026-09-22): Tailscale Serve 等のリバースプロキシは接続元を
        127.0.0.1 に中継するため、TCPピアだけで loopback を信頼すると
        テールネット全体が PC 自身として扱われてしまう。Host ヘッダが
        loopback 名であることを loopback 信頼の必須条件に加える。
        Host 無し（空）は HTTP/1.1 では異常なため Fail-Closed で非ループバック扱いとする。

    Args:
        host_header: Host ヘッダの値（ポート付き可）。

    Returns:
        bool: loopback 名の場合 True。
    """
    host = (host_header or "").strip().lower()
    if not host:
        return False
    if host.startswith("["):
        # IPv6 リテラルは `[::1]` または `[::1]:<port>` の完全形のみ許可する (P0-3 N2)
        closing = host.find("]")
        if closing == -1:
            return False
        literal = host[1:closing]
        remainder = host[closing + 1 :]
        if remainder and not remainder.startswith(":"):
            return False
        return literal == "::1"
    if ":" in host:
        host = host.rsplit(":", 1)[0]
    return host in ("localhost", "127.0.0.1", "::1")


def is_trusted_loopback(
    client_ip: str, host_header: str = "", headers: Optional[Dict[str, Any]] = None
) -> bool:
    """loopback 信頼の3条件（TCPピア + Host + プロキシヘッダ無し）を判定する (P0-3)。

    Notes:
        🛡️ P0-3: 「PC自身」= TCPピアが loopback の接続、と同一視してはならない。
        リバースプロキシ（Tailscale Serve / DNS Rebinding 経由のブラウザ）を
        構造的に排除するため、次の3条件すべてを要求する:
          1. TCPピアが loopback (127.0.0.1 / ::1)
          2. プロキシヘッダ (X-Forwarded-For / Forwarded / X-Real-IP 等) が無い
          3. Host ヘッダが loopback 名である
        条件を満たさない接続は「外部端末」として個別トークン + 人間承認の対象になる。

    Args:
        client_ip: TCPピアのIPアドレス。
        host_header: Host ヘッダの値。
        headers: リクエストヘッダ辞書（プロキシ検出用）。

    Returns:
        bool: 3条件すべてを満たす場合 True。
    """
    if not is_loopback(client_ip):
        return False
    header_map = headers or {}

    def _header_values(name: str) -> List[str]:
        """同名ヘッダの全出現値を返す（email.message / 素の dict 双方に対応）。"""
        if hasattr(header_map, "get_all"):
            return [str(v or "") for v in (header_map.get_all(name) or [])]
        value = header_map.get(name)
        return [str(value or "")] if value is not None else []

    # Host は単一出現のみ許可する (RFC 7230 / P0-3 N3: 複数 Host は Fail-Closed)
    if len(_header_values("Host")) > 1:
        return False
    # プロキシ・中継の痕跡ヘッダが1つでも非空なら loopback 信頼を無効化する (P0-3 N1/N3)
    for name in (
        "X-Forwarded-For",
        "X-Forwarded-Host",
        "X-Forwarded-Proto",
        "Forwarded",
        "X-Real-IP",
        "Via",
        "Tailscale-User-Login",
        "Tailscale-Funnel-Request",
        "Tailscale-Headers-Info",
    ):
        if any(value.strip() for value in _header_values(name)):
            return False
    return host_is_loopback(host_header)


def resolve_ledger_client_ip(
    client_ip: str, host_header: str = "", headers: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """台帳・監査へ記録するクライアントIPを解決する (ID 53 / 2026-09-23)。

    Notes:
        Tailscale Serve 等のリバースプロキシは TCPピアを 127.0.0.1 に中継するため、
        TCPピアをそのまま台帳へ書くと「PC内のゴミ」と誤認され、
        ①cleanup に物理削除される（個別トークン即死）②reuse_identity の 127.* 除外で
        承認のたびに行が増殖する、という実害が出る。そこで「TCPピアが loopback かつ
        loopback 信頼の3条件を満たさない」＝中継経由と確定できる場合に限り、
        ``X-Forwarded-For`` が**単一の非loopback有効IP**であるときだけ実IPとして採用する。
        XFF が無い・複数出現（チェーン）・IP不正・loopback値の場合は
        ``None``（IP不明）を返す。**毒値 127.0.0.1 は絶対に返さない**
        (P1-N1: 返すと行増殖・不可視化の障害が再発するため)。
        非loopbackの直接接続は、XFF を詐称し得るため TCPピアをそのまま採用する。

    Args:
        client_ip: TCPピアのIPアドレス。
        host_header: Host ヘッダの値。
        headers: リクエストヘッダ辞書（email.message / 素の dict 双方に対応）。

    Returns:
        Optional[str]: 台帳・監査に記録するIPアドレス。中継経由で特定不能な場合は None。
    """
    if not is_loopback(client_ip):
        return client_ip
    if is_trusted_loopback(client_ip, host_header, headers):
        return client_ip

    header_map = headers or {}
    if hasattr(header_map, "get_all"):
        raw_values = [str(v or "") for v in (header_map.get_all("X-Forwarded-For") or [])]
    else:
        raw_value = header_map.get("X-Forwarded-For")
        raw_values = [str(raw_value or "")] if raw_value is not None else []

    entries = [part.strip() for value in raw_values for part in value.split(",") if part.strip()]
    if len(entries) != 1:
        logger.info(
            f"🛡️ [SyncAuth] 中継経由で実IPを特定できません (XFF欠落/複数: {len(entries)}件) → IP不明として記録"
        )
        return None
    try:
        parsed = ipaddress.ip_address(entries[0])
    except ValueError:
        logger.warning(f"🚫 [SyncAuth] X-Forwarded-For の値がIPとして不正のため IP不明として記録: {entries[0]!r}")
        return None
    if parsed.is_loopback:
        # 中継経由なのに loopback 値は異常（詐称・多重中継）→ 毒値として捨てる
        logger.warning(f"🚫 [SyncAuth] 中継経由の X-Forwarded-For が loopback 値のため破棄: {entries[0]!r}")
        return None
    return entries[0]


def request_is_trusted_loopback(handler: Any) -> bool:
    """このリクエストが信頼できる loopback かを3条件で判定する (P0-3)。

    Args:
        handler: HTTPリクエストハンドラインスタンス。

    Returns:
        bool: 3条件すべてを満たす場合 True。
    """
    client_ip = handler.client_address[0] if getattr(handler, "client_address", None) else "unknown"
    headers = getattr(handler, "headers", None) or {}
    host_hdr = str(headers.get("Host", "")) if hasattr(headers, "get") else ""
    return is_trusted_loopback(client_ip, host_hdr, headers)


__all__: list[str] = [
    "is_loopback",
    "host_is_loopback",
    "is_trusted_loopback",
    "resolve_ledger_client_ip",
    "request_is_trusted_loopback",
]
