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

import logging
from typing import Any, Dict, List

from api_context import ApiContext
import database

logger = logging.getLogger(__name__)


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
