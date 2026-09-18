#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - ゼロトラスト端末台帳APIモジュール (api_devices.py)

P1-B 第一歩 (Jules 夜間タスクC・2026-09-07): local_sync_server.do_GET 内の
インライン実装 (GET /api/devices) を本モジュールへ抽出し、Divergent Change を解消する。

契約 (api_context.py / api_agent_bridge.py と同一方式):
- handle_* は ``handler(ctx: ApiContext) -> bool`` 署名を持つモジュール関数。
  レスポンスを書き込んだら True を返す。例外時も明示エラー JSON を書き込んで True
  (無応答 200 空ボディは 2026-09-03 改修により廃止済み)。
- Bearer 認証 (_check_auth) は呼び出し元 (local_sync_server.do_GET) で適用されるため、
  本モジュールでは再検査しない (POST パス系ハンドラと同一の責務分離)。
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List

from api_context import ApiContext
import database

logger = logging.getLogger(__name__)


def record_device_revoke(
    device_id: int, *, actor: str, source: str, device_name: str = ""
) -> None:
    """端末失効（Revoke）を監査ログへ記録する（ゼロトラスト監査: who / when / what）。

    Args:
        device_id: 失効させたデバイスID。
        actor: 操作主体（例: "pc_settings_ui" / 接続元IP / "localhost"）。
        source: 操作経路（"ui" = PC設定画面 / "api" = ローカルAPI）。
        device_name: 端末名（表示用・不明なら空）。

    Notes:
        P1-4 (2026-09-16 ruthless-code-evaluation): 旧実装は失効操作が一切記録されず、
        「誰がいつどの端末を切ったか」が追跡不能だった。既存の承認監査基盤
        (`approval_audit_logs`) を再利用する。
        P1-2 (2026-09-16 独立査読): 非同期ロガーは終了時にキューがフラッシュされず
        「失効成功・監査0件」を実測で再現した。失効は低頻度かつ高重要の操作であり、
        失効本体（同期DB書き込み）と同じブロッキング特性で問題にならないため、
        本経路のみ**同期書き込み**で証跡を確定させる。
    """
    try:
        from storage.audit_repo import record_audit_log
        from storage.models import AuditLogEntry

        entry = AuditLogEntry(
            request_id=f"device-revoke-{device_id}-{int(datetime.now().timestamp() * 1000)}",
            agent_type="device_management",
            agent_name=actor,
            command=f"revoke device_id={device_id} ({device_name or 'unknown'})",
            summary=f"端末の接続解除（{source}）",
            risk_level="high",
            decision="approved",
            decision_by=actor,
            decision_message=f"source={source}",
            requester_ip=None,
            client_ip=actor if source == "api" else None,
        )
        record_audit_log(entry)
        logger.warning(
            f"🛡️ [Audit Log] 端末失効を記録: device_id={device_id} source={source} actor={actor}"
        )
    except Exception as e:  # 監査記録の失敗で失効作業を止めない（可用性優先）
        logger.error(f"端末失効の監査ログ記録に失敗しました (device_id={device_id}): {e}")


def handle_post_devices_revoke(ctx: ApiContext) -> bool:
    """端末個別失効 (POST /api/devices/revoke) を処理し、監査ログへ記録する。

    Notes:
        呼び出し元 (local_sync_server.do_POST) でループバック限定チェックを済ませている前提。
        レスポンスは常に書き込む (無応答200空ボディは廃止済みの規約に従う)。

    Args:
        ctx: リクエストコンテキスト (body / client_ip を使用)。

    Returns:
        bool: レスポンス書き込み済みのため常に True。
    """
    try:
        data = json.loads(ctx.body.decode("utf-8")) if ctx.body else {}
    except Exception as e:
        logger.error(f"デバイス失効リクエストのJSON解析に失敗: {e}")
        ctx.write_json(
            {"status": "error", "message": "invalid JSON body"},
            ensure_ascii=False,
            status_code=400,
        )
        return True

    device_id = data.get("device_id") if isinstance(data, dict) else None
    if not device_id:
        ctx.write_json(
            {"status": "error", "message": "device_id is required"},
            ensure_ascii=False,
            status_code=400,
        )
        return True

    try:
        device_id_int = int(device_id)
        ok = bool(database.revoke_device(device_id_int))
        if ok:
            record_device_revoke(
                device_id_int, actor=ctx.client_ip or "localhost", source="api"
            )
        ctx.write_json(
            {"status": "ok" if ok else "not_found", "revoked": ok},
            ensure_ascii=False,
            status_code=200 if ok else 404,
        )
    except Exception as e:
        logger.error(f"デバイス失効エラー: {e}")
        ctx.write_json(
            {"status": "error", "message": str(e)},
            ensure_ascii=False,
            status_code=500,
        )
    return True


def record_device_restore(
    device_id: int, *, actor: str, source: str, device_name: str = ""
) -> None:
    """端末復帰（Restore）を監査ログへ記録する（ゼロトラスト監査: who / when / what）。

    Args:
        device_id: 復帰させたデバイスID。
        actor: 操作主体（例: "pc_settings_ui" / 接続元IP / "localhost"）。
        source: 操作経路（"ui" = PC設定画面 / "api" = ローカルAPI）。
        device_name: 端末名（表示用・不明なら空）。
    """
    try:
        from storage.audit_repo import record_audit_log
        from storage.models import AuditLogEntry

        entry = AuditLogEntry(
            request_id=f"device-restore-{device_id}-{int(datetime.now().timestamp() * 1000)}",
            agent_type="device_management",
            agent_name=actor,
            command=f"restore device_id={device_id} ({device_name or 'unknown'})",
            summary=f"端末の接続復帰（{source}）",
            risk_level="medium",
            decision="approved",
            decision_by=actor,
            decision_message=f"source={source}",
            requester_ip=None,
            client_ip=actor if source == "api" else None,
        )
        record_audit_log(entry)
        logger.info(
            f"🛡️ [Audit Log] 端末復帰を記録: device_id={device_id} source={source} actor={actor}"
        )
    except Exception as e:
        logger.error(f"端末復帰の監査ログ記録に失敗しました (device_id={device_id}): {e}")


def handle_post_devices_restore(ctx: ApiContext) -> bool:
    """端末個別復帰 (POST /api/devices/restore) を処理し、監査ログへ記録する。

    Notes:
        呼び出し元 (local_sync_server.do_POST) でループバック限定チェックを済ませている前提。
        レスポンスは常に書き込む。

    Args:
        ctx: リクエストコンテキスト (body / client_ip を使用)。

    Returns:
        bool: レスポンス書き込み済みのため常に True。
    """
    try:
        data = json.loads(ctx.body.decode("utf-8")) if ctx.body else {}
    except Exception as e:
        logger.error(f"デバイス復帰リクエストのJSON解析に失敗: {e}")
        ctx.write_json(
            {"status": "error", "message": "invalid JSON body"},
            ensure_ascii=False,
            status_code=400,
        )
        return True

    device_id = data.get("device_id") if isinstance(data, dict) else None
    if not device_id:
        ctx.write_json(
            {"status": "error", "message": "device_id is required"},
            ensure_ascii=False,
            status_code=400,
        )
        return True

    try:
        device_id_int = int(device_id)
        ok = bool(database.restore_device(device_id_int))
        if ok:
            record_device_restore(
                device_id_int, actor=ctx.client_ip or "localhost", source="api"
            )
        ctx.write_json(
            {"status": "ok" if ok else "not_found", "restored": ok},
            ensure_ascii=False,
            status_code=200 if ok else 404,
        )
    except Exception as e:
        logger.error(f"デバイス復帰エラー: {e}")
        ctx.write_json(
            {"status": "error", "message": str(e)},
            ensure_ascii=False,
            status_code=500,
        )
    return True



def handle_get_devices(ctx: ApiContext) -> bool:
    """登録デバイス一覧 (GET /api/devices) を JSON で返却する。

    ゼロトラスト台帳 (devices テーブル) の全行を PWA 表示用の辞書へ変換する。
    トークンハッシュ等の機微カラムはレスポンスに含めない。

    Args:
        ctx: リクエストコンテキスト (Bearer 認証は呼び出し元で完了済み)。

    Returns:
        bool: レスポンス書き込み済みの場合 True (例外時もエラー JSON を書き込む)。
    """
    try:
        devices = database.get_all_devices()
        dev_list: List[Dict[str, Any]] = [
            {
                "id": d.id,
                "device_name": d.device_name,
                "ip_address": d.ip_address,
                "user_agent": d.user_agent,
                "created_at": d.created_at,
                "last_seen": d.last_seen,
                "is_revoked": d.is_revoked,
            }
            for d in devices
        ]
        ctx.write_json(
            {"status": "ok", "devices": dev_list}, ensure_ascii=False, status_code=200
        )
        return True
    except Exception as e:
        logger.error(f"デバイス一覧取得エラー: {e}")
        ctx.write_json(
            {"status": "error", "message": str(e)},
            ensure_ascii=False,
            status_code=500,
        )
        return True
