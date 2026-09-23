#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ID 53: Tailscale Serve 経由スマホの台帳アイデンティティ修正を検証する。

背景（2026-09-23 実機障害）:
    Serve 中継のリクエストは TCPピアが 127.0.0.1 になるため、スマホの台帳行が
    127.0.0.1 として記録され、次の2重の実害が発生していた:
      ① ``cleanup_loopback_devices`` が「PCのゴミ」と誤認して行を物理削除
         → スマホの個別トークンが即死し、承認のたびに再ペアリング要求が再発
      ② ``reuse_identity`` の 127.* 除外により、承認のたびに新しい行とトークンが増殖

本テストが凍結する契約（修正仕様）:
    1. 「TCPピアが loopback かつ loopback 信頼の3条件を満たさない」＝中継経由と
       確定できる場合に限り、``X-Forwarded-For`` の先頭IPを実クライアントIPとして
       台帳・監査に採用する（XFF 無し/複数/不正は TCPピアへ Fail-Safe）。
       ※ 非loopbackの直接接続は XFF を信用しない（詐称防止）。
    2. 実IPで記録されるため cleanup の削除対象外になり、同一端末の再ペアリングは
       行を再利用する（増殖しない）。
    3. 端末管理パネルは一覧表示で台帳を物理削除しない（暗黙削除の撤去）。
    4. 非ブラウザUA（PC側クライアント等）は「スマホブラウザ」と偽装せず、
       承認ダイアログで見分けられるラベルを返す。
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import local_sync_server
from local_sync_server import DeskPetSyncHandler
from storage.connection import init_db
from storage.device_repo import (
    cleanup_loopback_devices,
    get_all_devices,
    issue_device_token,
)
from ui import device_manager_panel


class _FakeHttpHandler:
    """``_handle_auth_token`` を駆動するための最小HTTPハンドラスタブ。"""

    def __init__(self) -> None:
        self.wfile = io.BytesIO()
        self.status_codes: list = []
        self.headers: dict = {}

    def send_response(self, code: int) -> None:
        self.status_codes.append(code)

    def send_header(self, name: str, value: str) -> None:
        pass

    def end_headers(self) -> None:
        pass

    def _set_cors_headers(self) -> None:
        pass


class TestResolveLedgerClientIp(unittest.TestCase):
    """台帳へ記録するクライアントIPの解決規則（中継経由の実IP採用）を検証する。"""

    def test_trusted_loopback_keeps_tcp_peer(self) -> None:
        """信頼できる loopback（PC内ブラウザ・Agent Bridge）は TCPピアを維持する。"""
        self.assertEqual(
            DeskPetSyncHandler._resolve_ledger_client_ip("127.0.0.1", "localhost:8765", {}),
            "127.0.0.1",
        )

    def test_serve_relay_uses_first_forwarded_for(self) -> None:
        """Serve 中継（TCPピア loopback + 非loopback名の Host）は XFF の先頭IPを採用する。"""
        self.assertEqual(
            DeskPetSyncHandler._resolve_ledger_client_ip(
                "127.0.0.1",
                "node.tail08a991.ts.net",
                {"X-Forwarded-For": "100.64.0.5"},
            ),
            "100.64.0.5",
        )

    def test_direct_remote_with_spoofed_xff_keeps_tcp_peer(self) -> None:
        """非loopbackの直接接続では XFF を信用しない（詐称対策）。"""
        self.assertEqual(
            DeskPetSyncHandler._resolve_ledger_client_ip(
                "192.168.1.9",
                "192.168.1.9:8765",
                {"X-Forwarded-For": "1.2.3.4"},
            ),
            "192.168.1.9",
        )

    def test_multiple_forwarded_values_return_none(self) -> None:
        """XFF が複数出現（チェーン）の場合は実IP不明 (None) とする（毒値127.0.0.1を返さない）。"""
        self.assertIsNone(
            DeskPetSyncHandler._resolve_ledger_client_ip(
                "127.0.0.1",
                "node.tail08a991.ts.net",
                {"X-Forwarded-For": "100.64.0.5, 100.64.0.6"},
            )
        )

    def test_invalid_forwarded_value_returns_none(self) -> None:
        """XFF がIPとして不正な場合は実IP不明 (None) とする。"""
        self.assertIsNone(
            DeskPetSyncHandler._resolve_ledger_client_ip(
                "127.0.0.1",
                "node.tail08a991.ts.net",
                {"X-Forwarded-For": "not-an-ip"},
            )
        )

    def test_loopback_forwarded_value_is_rejected(self) -> None:
        """中継経由の XFF が loopback 値の場合は異常として破棄する (P1-N1)。"""
        self.assertIsNone(
            DeskPetSyncHandler._resolve_ledger_client_ip(
                "127.0.0.1",
                "node.tail08a991.ts.net",
                {"X-Forwarded-For": "127.0.0.1"},
            )
        )

    def test_missing_forwarded_header_returns_none(self) -> None:
        """XFF が無い中継経由は実IP不明 (None) とする。"""
        self.assertIsNone(
            DeskPetSyncHandler._resolve_ledger_client_ip(
                "127.0.0.1", "node.tail08a991.ts.net", {}
            )
        )


class TestServeRelayPairingIdentity(unittest.TestCase):
    """Serve 経由ペアリングが実IPで台帳へ記録され、行が増殖しないことを検証する。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmp.name) / "neo_secretary.db")
        init_db(self.db_path)
        # 本番 DB / .sync_token に触れないよう Seam を差し替える
        self._resolver_patch = mock.patch(
            "storage.connection.resolve_db_path", side_effect=lambda db_path="neo_secretary.db": self.db_path
        )
        self._resolver_patch.start()
        self._token_patch = mock.patch(
            "local_sync_server.TOKEN_FILE", Path(self._tmp.name) / ".sync_token"
        )
        self._token_patch.start()

        tm = local_sync_server.get_sync_token_manager()
        self._orig_pairing = tm._pairing_unlocked_until
        self._orig_callback = tm.device_approval_callback

    def tearDown(self) -> None:
        tm = local_sync_server.get_sync_token_manager()
        tm.close_pairing()
        tm.set_device_approval_callback(self._orig_callback)
        tm._pairing_unlocked_until = self._orig_pairing
        self._token_patch.stop()
        self._resolver_patch.stop()
        self._tmp.cleanup()

    def _pair_via_serve(self, user_agent: str) -> dict:
        """Serve 中継を模したトークン発行を1回実行してレスポンスJSONを返す。"""
        tm = local_sync_server.get_sync_token_manager()
        tm.unlock_pairing(duration_sec=60)
        tm.set_device_approval_callback(lambda dev_name, client_ip: True)

        handler = _FakeHttpHandler()
        handler.headers = {
            "Host": "node.tail08a991.ts.net",
            "User-Agent": user_agent,
            "X-Forwarded-For": "100.64.0.5",
        }
        DeskPetSyncHandler._handle_auth_token(handler, "127.0.0.1", user_agent)
        return json.loads(handler.wfile.getvalue().decode("utf-8"))

    def test_pairing_records_real_ip_and_reuses_row(self) -> None:
        """実IPが台帳に記録され、再ペアリングで行が増殖せず cleanup も削除しない。"""
        agent = "Mozilla/5.0 (Linux; Android 14; Pixel 8)"
        first = self._pair_via_serve(agent)
        self.assertIn("token", first)

        devices = get_all_devices(db_path=self.db_path)
        self.assertEqual(len(devices), 1, "承認1回につき1行のみ")
        self.assertEqual(devices[0].ip_address, "100.64.0.5", "Serve の実IPが記録されること")
        first_id = devices[0].id

        second = self._pair_via_serve(agent)
        self.assertIn("token", second)
        self.assertNotEqual(first["token"], second["token"], "トークンは毎回新規発行される")

        devices_after = get_all_devices(db_path=self.db_path)
        self.assertEqual(len(devices_after), 1, "再ペアリングで行が増殖しないこと")
        self.assertEqual(devices_after[0].id, first_id, "同一端末は既存行を再利用すること")

        self.assertEqual(
            cleanup_loopback_devices(db_path=self.db_path),
            0,
            "実IPで登録されたスマホ行は cleanup の削除対象外であること",
        )


    def test_pairing_without_xff_keeps_single_row(self) -> None:
        """XFF が無い中継経由（実IP不明）でも、承認のたびに行が増殖しない (P1-N1)。"""
        agent = "Mozilla/5.0 (Linux; Android 14; Pixel 8)"

        def pair_without_xff() -> dict:
            tm = local_sync_server.get_sync_token_manager()
            tm.unlock_pairing(duration_sec=60)
            tm.set_device_approval_callback(lambda dev_name, client_ip: True)
            handler = _FakeHttpHandler()
            handler.headers = {"Host": "node.tail08a991.ts.net", "User-Agent": agent}
            DeskPetSyncHandler._handle_auth_token(handler, "127.0.0.1", agent)
            return json.loads(handler.wfile.getvalue().decode("utf-8"))

        first = pair_without_xff()
        second = pair_without_xff()
        self.assertIn("token", first)
        self.assertIn("token", second)

        devices = get_all_devices(db_path=self.db_path)
        self.assertEqual(len(devices), 1, "実IP不明でも同一端末は1行に集約されること")
        self.assertIsNone(devices[0].ip_address, "毒値 127.0.0.1 を記録しないこと")
        self.assertEqual(devices[0].device_name, "Android端末")


class TestDeviceManagerNoImplicitCleanup(unittest.TestCase):
    """端末管理パネルの一覧表示が台帳を物理削除しないこと（暗黙削除の撤去）を検証する。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmp.name) / "neo_secretary.db")
        init_db(self.db_path)
        self._resolver_patch = mock.patch(
            "storage.connection.resolve_db_path", side_effect=lambda db_path="neo_secretary.db": self.db_path
        )
        self._resolver_patch.start()

    def tearDown(self) -> None:
        self._resolver_patch.stop()
        self._tmp.cleanup()

    def test_list_device_rows_never_deletes_registry_rows(self) -> None:
        """一覧を開いても台帳は削除されず、ループバック残存行は警告付きで表示される (P1-N2)。"""
        issue_device_token("Local Ghost", ip_address="127.0.0.1", db_path=self.db_path)

        with mock.patch.object(
            device_manager_panel.database,
            "cleanup_loopback_devices",
            side_effect=AssertionError("一覧表示で台帳を削除してはならない"),
        ) as cleanup_spy:
            rows = device_manager_panel.list_device_rows()

        cleanup_spy.assert_not_called()
        ghost_rows = [r for r in rows if "Ghost" in r.title]
        self.assertEqual(len(ghost_rows), 1, "不可視の有効資格情報を残さない (表示して失効可能にする)")
        self.assertIn("中継以前の残存行", ghost_rows[0].subtitle)
        self.assertEqual(len(get_all_devices(db_path=self.db_path)), 1, "台帳の行は保持されること")


class TestInferDeviceNameHonesty(unittest.TestCase):
    """承認ダイアログの端末名が非ブラウザクライアントを偽装しないことを検証する。"""

    def test_non_browser_user_agent_is_labeled_honestly(self) -> None:
        """PC側の Python クライアント等は「スマホブラウザ」と表示しない。"""
        self.assertEqual(
            DeskPetSyncHandler._infer_device_name("Python-urllib/3.13"),
            "⚠️ 非ブラウザ端末",
        )

    def test_browser_user_agents_are_unchanged(self) -> None:
        """ブラウザUAの推定は従来どおり。"""
        self.assertEqual(
            DeskPetSyncHandler._infer_device_name("Mozilla/5.0 (Linux; Android 14; Pixel 8)"),
            "Android端末",
        )


if __name__ == "__main__":
    unittest.main()
