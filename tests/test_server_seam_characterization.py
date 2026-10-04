#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - Fat モジュール分割リファクタ (Phase F0) キャラクトライゼーションテスト.

(tests/test_server_seam_characterization.py)

目的:
    Fat モジュール分割リファクタ (F0〜F10) において、Seam 切り出し (S1a〜S6 / T1〜T6) 前の
    現行の振る舞い・契約・不変条件を厳格に固定する (Characterization Tests)。
    本テストがリファクタの全工程で一貫して GREEN を維持することで、振る舞い不変
    (Behavioral Invariance) を機械的に保証する。

検証観点:
    1. S1a: SyncTokenManager のトークン生成・検証・失効契約
    2. S1b: プライベート IP 判定 (_is_private_ip) ＆ デバイス名推測 (_infer_device_name)
    3. S1c: Loopback 3条件検証 (_is_loopback, _host_is_loopback, _is_trusted_loopback)
    4. S3: DeviceLinkMonitor の死活監視・リンク状態判定
    5. T5: SettingsWindow の未定義 _render_mcp_servers 現行フォールバック契約
"""

from __future__ import annotations

import sys
import unittest
from unittest import mock
from pathlib import Path
from unittest.mock import MagicMock, patch

# ※ 本ファイルは tests/ 配下にあるため、プロジェクトルートを import パスに追加
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import local_sync_server
import server
from local_sync_server import DeskPetSyncHandler, DeviceLinkMonitor, SyncTokenManager


class TestSyncTokenManagerCharacterization(unittest.TestCase):
    """S1a Seam: SyncTokenManager の現行振る舞い固定テスト."""

    def test_singleton_accessor(self) -> None:
        """get_sync_token_manager が同一インスタンスを返却することを固定."""
        mgr1 = local_sync_server.get_sync_token_manager()
        mgr2 = local_sync_server.get_sync_token_manager()
        self.assertIs(mgr1, mgr2)
        self.assertIsInstance(mgr1, SyncTokenManager)

    def test_verify_loopback_behavior(self) -> None:
        """verify_loopback が発行済みトークンおよびマスターを妥当と判定することを固定."""
        mgr = local_sync_server.get_sync_token_manager()
        # 発行された loopback トークン (プロパティ)
        token = mgr.loopback_token
        self.assertTrue(mgr.verify_loopback(token))
        self.assertFalse(mgr.verify_loopback("invalid_token_12345"))
        self.assertFalse(mgr.verify_loopback(""))

    def test_facade_reexport_integrity(self) -> None:
        """local_sync_server からの Facade 再エクスポートが server.sync_token_manager と同一実体であることを固定."""
        import server.sync_token_manager as stm_mod

        self.assertIs(local_sync_server.SyncTokenManager, stm_mod.SyncTokenManager)
        self.assertIs(local_sync_server.get_sync_token_manager, stm_mod.get_sync_token_manager)
        self.assertEqual(local_sync_server.TOKEN_FILE, stm_mod.TOKEN_FILE)



class TestAuthChecksCharacterization(unittest.TestCase):
    """S1b Seam: auth_checks 系純粋関数の現行振る舞い固定テスト."""

    def test_is_private_ip(self) -> None:
        """プライベート IP 判定契約の固定."""
        # 正常系: プライベート/ループバック
        self.assertTrue(DeskPetSyncHandler._is_private_ip("127.0.0.1"))
        self.assertTrue(DeskPetSyncHandler._is_private_ip("::1"))
        self.assertTrue(DeskPetSyncHandler._is_private_ip("192.168.1.100"))
        self.assertTrue(DeskPetSyncHandler._is_private_ip("10.0.0.1"))
        self.assertTrue(DeskPetSyncHandler._is_private_ip("172.16.0.1"))

        # 異常系: パブリック IP / 不正IP
        self.assertFalse(DeskPetSyncHandler._is_private_ip("8.8.8.8"))
        self.assertFalse(DeskPetSyncHandler._is_private_ip("1.1.1.1"))
        self.assertFalse(DeskPetSyncHandler._is_private_ip("invalid_ip"))
        self.assertFalse(DeskPetSyncHandler._is_private_ip(""))

    def test_infer_device_name(self) -> None:
        """User-Agent からのデバイス名推測契約の固定 (ID 50/53 正直ラベル)."""
        # iPhone
        ua_iphone = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15"
        self.assertEqual(DeskPetSyncHandler._infer_device_name(ua_iphone), "iPhone")

        # Android
        ua_android = "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36"
        self.assertEqual(DeskPetSyncHandler._infer_device_name(ua_android), "Android端末")

        # 空 / 非ブラウザ UA (正直ラベル)
        self.assertEqual(DeskPetSyncHandler._infer_device_name(""), "⚠️ 非ブラウザ端末")

    def test_facade_reexport_integrity(self) -> None:
        """server パッケージからの auth_checks 再エクスポートと DeskPetSyncHandler 委譲の整合性を固定."""
        import server.auth_checks as ac_mod

        self.assertIs(server.check_auth, ac_mod.check_auth)
        self.assertIs(server.check_webhook_auth, ac_mod.check_webhook_auth)
        self.assertIs(server.get_bearer_token, ac_mod.get_bearer_token)
        self.assertIs(server.infer_device_name, ac_mod.infer_device_name)
        self.assertIs(server.is_private_ip, ac_mod.is_private_ip)
        # staticmethod 委譲の同値性
        self.assertEqual(
            DeskPetSyncHandler._infer_device_name("test"),
            ac_mod.infer_device_name("test"),
        )
        self.assertEqual(
            DeskPetSyncHandler._is_private_ip("127.0.0.1"),
            ac_mod.is_private_ip("127.0.0.1"),
        )



class TestLoopbackTrustCharacterization(unittest.TestCase):
    """S1c Seam: loopback 信頼 3条件 (知識の宝庫 ID 13) の現行振る舞い固定テスト."""

    def test_is_loopback_ip(self) -> None:
        """ピア IP のループバック判定契約の固定."""
        self.assertTrue(DeskPetSyncHandler._is_loopback("127.0.0.1"))
        self.assertTrue(DeskPetSyncHandler._is_loopback("::1"))
        self.assertTrue(DeskPetSyncHandler._is_loopback("localhost"))
        self.assertFalse(DeskPetSyncHandler._is_loopback("192.168.1.1"))
        self.assertFalse(DeskPetSyncHandler._is_loopback("10.0.0.1"))

    def test_host_is_loopback(self) -> None:
        """Host ヘッダーの完全形ループバック判定契約の固定."""
        self.assertTrue(DeskPetSyncHandler._host_is_loopback("localhost:8765"))
        self.assertTrue(DeskPetSyncHandler._host_is_loopback("127.0.0.1:8765"))
        self.assertTrue(DeskPetSyncHandler._host_is_loopback("[::1]:8765"))
        self.assertTrue(DeskPetSyncHandler._host_is_loopback("localhost"))

        # 偽装・外部ホスト
        self.assertFalse(DeskPetSyncHandler._host_is_loopback("attacker.com"))
        self.assertFalse(DeskPetSyncHandler._host_is_loopback("192.168.1.10:8765"))
        self.assertFalse(DeskPetSyncHandler._host_is_loopback("evil-localhost.com"))

    def test_facade_reexport_integrity(self) -> None:
        """server パッケージからの loopback_trust 再エクスポートと DeskPetSyncHandler 委譲の整合性を固定."""
        import server.loopback_trust as lt_mod

        self.assertIs(server.is_loopback, lt_mod.is_loopback)
        self.assertIs(server.host_is_loopback, lt_mod.host_is_loopback)
        self.assertIs(server.is_trusted_loopback, lt_mod.is_trusted_loopback)
        self.assertIs(server.resolve_ledger_client_ip, lt_mod.resolve_ledger_client_ip)
        self.assertIs(server.request_is_trusted_loopback, lt_mod.request_is_trusted_loopback)
        # staticmethod 委譲の同値性
        self.assertEqual(
            DeskPetSyncHandler._is_loopback("127.0.0.1"),
            lt_mod.is_loopback("127.0.0.1"),
        )
        self.assertEqual(
            DeskPetSyncHandler._host_is_loopback("localhost"),
            lt_mod.host_is_loopback("localhost"),
        )



class TestDeviceLinkMonitorCharacterization(unittest.TestCase):
    """S3 Seam: DeviceLinkMonitor の現行振る舞い固定テスト."""

    def test_singleton_accessor(self) -> None:
        """get_link_monitor が同一インスタンスを返却することを固定."""
        mon1 = local_sync_server.get_link_monitor()
        mon2 = local_sync_server.get_link_monitor()
        self.assertIs(mon1, mon2)
        self.assertIsInstance(mon1, DeviceLinkMonitor)

    def test_status_structure(self) -> None:
        """get_status の返却辞書スキーマが安定していることを固定."""
        mon = local_sync_server.get_link_monitor()
        status = mon.get_status()
        self.assertIsInstance(status, dict)
        self.assertIn("connected", status)
        self.assertIn("device_name", status)
        self.assertIn("client_ip", status)
        self.assertIn("seconds_ago", status)
        self.assertIn("last_seen", status)


class TestAgentBridgeHubCharacterization(unittest.TestCase):
    """S2 Seam: AgentBridgeHub の現行振る舞い ＆ Facade 完全性テスト (Phase F5)."""

    def test_singleton_accessor(self) -> None:
        """get_bridge_hub が同一インスタンスを返却することを固定."""
        hub1 = local_sync_server.get_bridge_hub()
        hub2 = local_sync_server.get_bridge_hub()
        self.assertIs(hub1, hub2)
        self.assertIsInstance(hub1, local_sync_server.AgentBridgeHub)

    def test_facade_reexport_integrity(self) -> None:
        """local_sync_server からの Facade 再エクスポートが server.agent_bridge_hub と同一実体であることを固定."""
        import server.agent_bridge_hub as hub_mod

        self.assertIs(local_sync_server.AgentBridgeRequest, hub_mod.AgentBridgeRequest)
        self.assertIs(local_sync_server.AgentBridgeHub, hub_mod.AgentBridgeHub)
        self.assertIs(local_sync_server.get_bridge_hub, hub_mod.get_bridge_hub)
        self.assertIs(local_sync_server._PC_LOCAL_IDENTITIES, hub_mod._PC_LOCAL_IDENTITIES)

    def test_patch_local_sync_server_get_bridge_hub(self) -> None:
        """知見ID 45 防衛: patch('local_sync_server.get_bridge_hub') が意図通りモックに置換されることを固定."""
        mock_hub = MagicMock()
        with patch("local_sync_server.get_bridge_hub", return_value=mock_hub):
            resolved = local_sync_server.get_bridge_hub()
            self.assertIs(resolved, mock_hub)

    def test_pc_local_identities_contract(self) -> None:
        """PC ローカル信頼ドメイン規則 (_PC_LOCAL_IDENTITIES) の不変条件を固定."""
        identities = local_sync_server._PC_LOCAL_IDENTITIES
        self.assertIsInstance(identities, frozenset)
        self.assertEqual(identities, frozenset({"agent", "pc-loopback"}))


class TestHttpdCoreCharacterization(unittest.TestCase):
    """S5 Seam: server.httpd_core の現行契約・不変条件テスト."""

    def test_singleton_accessor(self) -> None:
        """get_sync_server() のシングルトン挙動を固定."""
        srv1 = local_sync_server.get_sync_server()
        srv2 = local_sync_server.get_sync_server()
        self.assertIs(srv1, srv2)
        self.assertIsInstance(srv1, local_sync_server.LocalSyncServer)

    def test_facade_reexport_integrity(self) -> None:
        """local_sync_server からの Facade 再エクスポートが server.httpd_core と同一実体であることを固定."""
        import server.httpd_core as httpd_mod

        self.assertIs(local_sync_server.QuietThreadingHTTPServer, httpd_mod.QuietThreadingHTTPServer)
        self.assertIs(local_sync_server.LocalSyncServer, httpd_mod.LocalSyncServer)
        self.assertIs(local_sync_server.get_sync_server, httpd_mod.get_sync_server)

    def test_quiet_server_attributes(self) -> None:
        """QuietThreadingHTTPServer のソケット再利用・デーモンスレッド属性を固定."""
        cls = local_sync_server.QuietThreadingHTTPServer
        self.assertTrue(cls.daemon_threads)
        self.assertTrue(cls.allow_reuse_address)


class TestToolsTabCharacterization(unittest.TestCase):
    """T5 Seam: ui.settings_tabs.tools_tab / google_section / ical_section の契約テスト."""

    def test_render_mcp_servers_fixed(self) -> None:
        """設計書 §2.2.3 / §9①: _render_mcp_servers が F8b にて正式実装・是正されたことを検証."""
        from ui.settings_window import SettingsWindow

        self.assertTrue(hasattr(SettingsWindow, "_render_mcp_servers"))

    def test_tools_tab_exports_and_methods(self) -> None:
        """ToolsTab, GoogleSection, ICalSection が正しく公開されていることを検証."""
        from ui.settings_tabs import ToolsTab, GoogleSection, ICalSection
        from ui.settings_tabs.tools_tab import ToolsTab as DirectToolsTab
        from ui.settings_tabs.google_section import GoogleSection as DirectGoogleSection
        from ui.settings_tabs.ical_section import ICalSection as DirectICalSection

        self.assertIs(ToolsTab, DirectToolsTab)
        self.assertIs(GoogleSection, DirectGoogleSection)
        self.assertIs(ICalSection, DirectICalSection)

        for method in ["build", "collect", "refresh_texts", "_render_mcp_servers"]:
            self.assertTrue(hasattr(ToolsTab, method), f"ToolsTab に {method} がありません")

    def test_tools_tab_collect_contract(self) -> None:
        """ToolsTab.collect() が必要な 5 キーを返すことを検証."""
        from ui.settings_tabs.tools_tab import ToolsTab

        mock_parent = mock.MagicMock()
        mock_gui = mock.MagicMock()
        tab = ToolsTab(mock_parent, mock_gui)
        collected = tab.collect()

        expected_keys = {
            "GOOGLE_CALENDAR_ID",
            "GITHUB_PERSONAL_ACCESS_TOKEN",
            "GITHUB_REPO",
            "SLACK_WEBHOOK_URL",
            "VOICE_NARRATION_ENABLED",
        }
        self.assertEqual(set(collected.keys()), expected_keys)


class TestLLMBrainTabCharacterization(unittest.TestCase):
    """T4 Seam: ui.settings_tabs.llm_brain_tab の現行契約・不変条件テスト."""

    def test_llm_brain_tab_export_and_methods(self) -> None:
        """LLMBrainTab が正しく公開され、主要契約メソッドが実装されていることを検証."""
        from ui.settings_tabs import LLMBrainTab
        from ui.settings_tabs.llm_brain_tab import LLMBrainTab as DirectClass

        self.assertIs(LLMBrainTab, DirectClass)
        expected_methods = [
            "build",
            "collect",
            "refresh_texts",
            "_sync_all_models",
            "_fetch_models",
            "_download_local_model_gui",
        ]
        for method_name in expected_methods:
            self.assertTrue(
                hasattr(LLMBrainTab, method_name),
                f"LLMBrainTab にメソッド {method_name} が定義されていません",
            )

    def test_llm_brain_tab_collect_contract(self) -> None:
        """LLMBrainTab.collect() が設計書 §3.3 の 15 キーを満たすことを検証."""
        from ui.settings_tabs.llm_brain_tab import LLMBrainTab

        mock_parent = mock.MagicMock()
        mock_gui = mock.MagicMock()
        tab = LLMBrainTab(mock_parent, mock_gui)
        collected = tab.collect()

        expected_keys = {
            "GOOGLE_API_KEY",
            "GEMINI_MODEL",
            "ANTHROPIC_API_KEY",
            "CLAUDE_MODEL",
            "OPENAI_API_KEY",
            "OPENAI_MODEL",
            "OPENCODE_API_KEY",
            "OPENCODE_BASE_URL",
            "OPENCODE_MODEL",
            "GROQ_API_KEY",
            "OPENROUTER_API_KEY",
            "CUSTOM_OPENAI_BASE_URL",
            "CUSTOM_OPENAI_API_KEY",
            "CUSTOM_OPENAI_MODEL",
            "LOCAL_GGUF_MODEL",
        }
        self.assertEqual(set(collected.keys()), expected_keys)

    def test_settings_window_delegation_compatibility(self) -> None:
        """SettingsWindow に下位互換委譲メソッドが存在することを検証."""
        from ui.settings_window import SettingsWindow

        for method_name in ["_sync_all_models", "_fetch_models", "_download_local_model_gui"]:
            self.assertTrue(
                hasattr(SettingsWindow, method_name),
                f"SettingsWindow に下位互換メソッド {method_name} がありません",
            )


class TestStatusCacheCharacterization(unittest.TestCase):
    """S4 Seam: server.status_cache のキャッシュ契約・TTL・Facade 再エクスポートテスト (Phase F9)."""

    def test_facade_reexport_invalidate_habit_cache(self) -> None:
        """local_sync_server からの invalidate_habit_cache 再エクスポートが動作することを固定."""
        import server.status_cache as sc_mod

        self.assertIs(local_sync_server.invalidate_habit_cache, sc_mod.invalidate_habit_cache)
        # 呼び出し可能で例外が発生しないこと
        local_sync_server.invalidate_habit_cache()

    def test_status_cache_manager_ttl_and_invalidation(self) -> None:
        """StatusCacheManager の TTL キャッシュ管理および無効化が期待通り動作することを検証."""
        from server.status_cache import StatusCacheManager

        mgr = StatusCacheManager()

        # 初期状態: キャッシュ無効
        is_valid, tasks, events = mgr.get_db_cache(now=100.0, ttl=2.0)
        self.assertFalse(is_valid)

        # キャッシュ設定
        mgr.set_db_cache([{"id": 1, "title": "test"}], [], timestamp=100.0)
        is_valid, tasks, events = mgr.get_db_cache(now=101.0, ttl=2.0)
        self.assertTrue(is_valid)
        self.assertEqual(len(tasks), 1)

        # 2秒TTL切れ
        is_valid, _, _ = mgr.get_db_cache(now=103.0, ttl=2.0)
        self.assertFalse(is_valid)

        # 手動無効化
        mgr.set_db_cache([{"id": 2}], [], timestamp=100.0)
        mgr.invalidate_db_cache()
        is_valid, _, _ = mgr.get_db_cache(now=100.5, ttl=2.0)
        self.assertFalse(is_valid)

    def test_habit_cache_ttl_and_invalidation(self) -> None:
        """習慣キャッシュの 30秒TTL および無効化を検証."""
        from server.status_cache import StatusCacheManager

        mgr = StatusCacheManager()
        mgr.set_habit_cache([{"id": 10}], [{"day": "2026-10-04"}], timestamp=1000.0)

        # 20秒後: まだ有効
        is_valid, habits, heatmap = mgr.get_habit_cache(now=1020.0, ttl=30.0)
        self.assertTrue(is_valid)
        self.assertEqual(len(habits), 1)

        # 31秒後: TTL切れ
        is_valid, _, _ = mgr.get_habit_cache(now=1031.0, ttl=30.0)
        self.assertFalse(is_valid)

        # 手動無効化
        mgr.set_habit_cache([{"id": 10}], [], timestamp=2000.0)
        mgr.invalidate_habit_cache()
        is_valid, _, _ = mgr.get_habit_cache(now=2005.0, ttl=30.0)
        self.assertFalse(is_valid)


class TestApiStatusCharacterization(unittest.TestCase):
    """S4 Seam: server.api_status のペイロード構築 ＆ ヘルパー契約テスト (Phase F9)."""

    @classmethod
    def setUpClass(cls) -> None:
        import database

        try:
            database.init_db()
        except Exception:
            pass

    def test_fmt_event_dt_contract(self) -> None:

        """_fmt_event_dt のミリ秒タイムスタンプ変換契約を検証."""
        from server.api_status import _fmt_event_dt

        # 空値・0・無効値
        self.assertEqual(_fmt_event_dt(None), "")
        self.assertEqual(_fmt_event_dt(0), "")
        self.assertEqual(_fmt_event_dt("invalid"), "")

        # 有効なUnixタイムスタンプ (2026-10-04 12:00:00 JST 付近 = 1791082800000)
        formatted = _fmt_event_dt(1791082800000)
        self.assertTrue(len(formatted) > 10)
        self.assertIn(":", formatted)

    def test_build_status_payload_schema(self) -> None:
        """build_status_payload が必須キーを含む有効なペイロードを返却することを検証."""
        from server.api_status import build_status_payload

        payload = build_status_payload(client_ip="127.0.0.1", user_agent="PyTest-Agent", now=1791082800.0)
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload.get("status"), "ok")

        expected_keys = [
            "pet_state", "message", "character", "bond",
            "habits", "habit_heatmap", "tasks", "events",
            "pomodoro", "language", "server_time", "update",
        ]
        for key in expected_keys:
            self.assertIn(key, payload, f"ステータスペイロードに必須キー {key} が存在しません")


class TestGuiBridgeCharacterization(unittest.TestCase):
    """S6 Seam: server.gui_bridge の現行振る舞い ＆ Facade 完全性テスト (Phase F10)."""

    def test_facade_reexport_gui_instance(self) -> None:
        """local_sync_server からの get_gui_instance / set_gui_instance 再エクスポートが同一実体であることを固定."""
        import server.gui_bridge as gb_mod

        self.assertIs(local_sync_server.get_gui_instance, gb_mod.get_gui_instance)
        self.assertIs(local_sync_server.set_gui_instance, gb_mod.set_gui_instance)

    def test_gui_instance_set_and_get(self) -> None:
        """set_gui_instance で設定した値が get_gui_instance で取得できることを検証."""
        from server.gui_bridge import get_gui_instance, set_gui_instance

        mock_gui = mock.MagicMock()
        set_gui_instance(mock_gui)
        self.assertIs(get_gui_instance(), mock_gui)
        # 後片付け (None リセット)
        set_gui_instance(None)
        self.assertIsNone(get_gui_instance())


class TestRouteRecordCharacterization(unittest.TestCase):
    """S6/F10 Seam: server.routes のルートテーブル ＆ ゼロトラスト防御テスト (Phase F10)."""

    def test_facade_reexport_routes_tables(self) -> None:
        """local_sync_server からの POST/GET ハンドラおよびアクションテーブル再エクスポートを検証."""
        import server.routes as r_mod

        self.assertIs(local_sync_server.POST_PATH_HANDLERS, r_mod.POST_PATH_HANDLERS)
        self.assertIs(local_sync_server.GET_PATH_HANDLERS, r_mod.GET_PATH_HANDLERS)
        self.assertIs(local_sync_server.ACTION_HANDLERS, r_mod.ACTION_HANDLERS)
        self.assertIn("/api/agent/ask", local_sync_server.POST_PATH_HANDLERS)
        self.assertIn("/api/devices", local_sync_server.GET_PATH_HANDLERS)
        self.assertIn("complete_task", local_sync_server.ACTION_HANDLERS)

    def test_post_routes_loopback_definitions(self) -> None:
        """POST_ROUTES の loopback 制限対象が漏れなく定義されていることを検証."""
        from server.routes import POST_ROUTES

        loopback_paths = [
            "/api/agent/ask",
            "/api/agent/ask_input",
            "/api/agent/notify",
            "/api/agent/cancel_pending",
            "/api/devices/revoke",
            "/api/devices/restore",
            "/api/agent/activity",
        ]
        for path in loopback_paths:
            self.assertIn(path, POST_ROUTES)
            self.assertEqual(POST_ROUTES[path].auth_level, "loopback")

    def test_non_loopback_agent_ask_forbidden_contract(self) -> None:
        """設計書 §5.1 / §8 回帰防衛: 非ループバックからの /api/agent/ask が 403 遮断されることを固定."""
        import json
        from io import BytesIO
        from unittest.mock import MagicMock, patch

        handler = mock.MagicMock(spec=DeskPetSyncHandler)
        handler.path = "/api/agent/ask"
        handler.client_address = ("192.168.1.50", 54321)
        handler.headers = {"Host": "192.168.1.10:8765", "User-Agent": "RemoteAgent"}
        handler.rfile = BytesIO(b"{}")
        handler._check_auth = MagicMock(return_value=True)
        # 非ループバックなので False
        handler._request_is_trusted_loopback = MagicMock(return_value=False)

        # レスポンス書き込み先モック
        out_wfile = BytesIO()
        handler.wfile = out_wfile

        # DeskPetSyncHandler.do_POST をモック handler インスタンスで実行
        with patch.object(handler, "headers", {"Content-Length": "2", "Host": "192.168.1.10:8765"}):
            DeskPetSyncHandler.do_POST(handler)

        handler.send_response.assert_called_with(403)
        written_body = out_wfile.getvalue().decode("utf-8")
        parsed = json.loads(written_body)
        self.assertEqual(parsed.get("status"), "error")
        self.assertEqual(parsed.get("message"), "Agent APIs are restricted to localhost connections.")


if __name__ == "__main__":
    unittest.main()




