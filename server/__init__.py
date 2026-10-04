"""ネオ秘書くん - ローカル同期サーバー Seam パッケージ (server).

本パッケージは、Fat モジュール `local_sync_server.py` から Deep Module / Seam 原則に
基づいて切り出された各責務モジュール群を収容します。

収容予定の Seam モジュール:
    - sync_token_manager (S1a): トークン発行・検証・失効管理
    - auth_checks (S1b): Bearer 認証・プライベート IP 判定・Webhook 認証
    - loopback_trust (S1c): Loopback 3条件検証・クライアント IP 解決
    - agent_bridge_hub (S2): エージェント承認キュー・冪等応答
    - device_link (S3): 端末死活監視・リンク状態通知
    - api_status (S4): /api/status ペイロード生成
    - status_cache (S4): ステータス・習慣キャッシュ集約
    - httpd_core (S5): QuietThreadingHTTPServer / LocalSyncServer
    - gui_bridge (S6): GUI 参照登録・逆参照解消ハブ
"""

from __future__ import annotations

from server.agent_bridge_hub import (
    AgentBridgeHub,
    AgentBridgeRequest,
    get_bridge_hub,
)
from server.auth_checks import (
    check_auth,
    check_webhook_auth,
    get_bearer_token,
    infer_device_name,
    is_private_ip,
)
from server.device_link import DeviceLinkMonitor, get_link_monitor
from server.httpd_core import (
    LocalSyncServer,
    QuietThreadingHTTPServer,
    get_sync_server,
)
from server.api_status import (
    build_status_payload,
    handle_get_status,
)
from server.gui_bridge import (
    get_gui_instance,
    set_gui_instance,
)
from server.loopback_trust import (
    host_is_loopback,
    is_loopback,
    is_trusted_loopback,
    request_is_trusted_loopback,
    resolve_ledger_client_ip,
)
from server.routes import (
    ACTION_HANDLERS,
    GET_PATH_HANDLERS,
    GET_ROUTES,
    POST_PATH_HANDLERS,
    POST_ROUTES,
    RouteRecord,
)
from server.status_cache import (
    StatusCacheManager,
    get_status_cache,
    invalidate_db_cache,
    invalidate_habit_cache,
)
from server.sync_token_manager import (
    TOKEN_FILE,
    SyncTokenManager,
    get_sync_token_manager,
)

__all__: list[str] = [
    "ACTION_HANDLERS",
    "AgentBridgeHub",
    "AgentBridgeRequest",
    "DeviceLinkMonitor",
    "GET_PATH_HANDLERS",
    "GET_ROUTES",
    "LocalSyncServer",
    "POST_PATH_HANDLERS",
    "POST_ROUTES",
    "QuietThreadingHTTPServer",
    "RouteRecord",
    "StatusCacheManager",
    "SyncTokenManager",
    "TOKEN_FILE",
    "build_status_payload",
    "check_auth",
    "check_webhook_auth",
    "get_bearer_token",
    "get_bridge_hub",
    "get_gui_instance",
    "get_link_monitor",
    "get_status_cache",
    "get_sync_server",
    "get_sync_token_manager",
    "handle_get_status",
    "host_is_loopback",
    "infer_device_name",
    "invalidate_db_cache",
    "invalidate_habit_cache",
    "is_loopback",
    "is_private_ip",
    "is_trusted_loopback",
    "request_is_trusted_loopback",
    "resolve_ledger_client_ip",
    "set_gui_instance",
]



