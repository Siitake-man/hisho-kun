#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - ゼロトラスト端末台帳 API シーム移管の単体テスト (tests/test_api_devices_seam.py)

Jules 夜間タスクC (2026-09-06) / P1-B 第一歩:
GET /api/devices のハンドラを local_sync_server.do_GET のインライン実装から
api_devices.handle_get_devices へ抽出した際の契約を凍結する。

TDD: api_devices モジュールが存在しない状態では本テストは Red で落ちる。
"""

import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api_context import ApiContext


class _FakeHttpHandler:
    """ApiContext.begin_json_response / write_json が要求する最小ハンドラスタブ。"""

    def __init__(self) -> None:
        self.wfile = io.BytesIO()
        self.status_codes: list = []

    def send_response(self, code: int) -> None:
        self.status_codes.append(code)

    def send_header(self, name: str, value: str) -> None:
        pass

    def end_headers(self) -> None:
        pass

    def _set_cors_headers(self) -> None:
        pass


def _decode_body(handler: _FakeHttpHandler) -> dict:
    """書き込まれたレスポンスボディを JSON デコードする。"""
    return json.loads(handler.wfile.getvalue().decode("utf-8"))


def _make_device_row() -> mock.Mock:
    """database.get_all_devices() の戻り値要素 (Device モデル相当) のスタブ。"""
    return mock.Mock(
        id=1,
        device_name="Pixel Desk Pet",
        ip_address="192.168.1.9",
        user_agent="Mozilla/5.0 (Linux; Android)",
        created_at="2026-09-07 09:00",
        last_seen="2026-09-07 09:05",
        is_revoked=0,
    )


class TestHandleGetDevices(unittest.TestCase):
    """api_devices.handle_get_devices の契約検証"""

    def test_returns_device_list_with_200(self) -> None:
        """台帳全件が {"status": "ok", "devices": [...]} として 200 応答されること"""
        import api_devices

        with mock.patch.object(
            api_devices.database, "get_all_devices", return_value=[_make_device_row()]
        ):
            handler = _FakeHttpHandler()
            responded = api_devices.handle_get_devices(ApiContext(handler))

        self.assertTrue(responded)
        self.assertEqual(handler.status_codes, [200])
        payload = _decode_body(handler)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(len(payload["devices"]), 1)
        self.assertEqual(payload["devices"][0]["device_name"], "Pixel Desk Pet")
        self.assertEqual(payload["devices"][0]["is_revoked"], 0)

    def test_db_error_writes_500_error_json(self) -> None:
        """DB 異常時に {"status": "error"} を 500 で応答し、無応答にしないこと"""
        import api_devices

        with mock.patch.object(
            api_devices.database,
            "get_all_devices",
            side_effect=RuntimeError("database is locked"),
        ):
            handler = _FakeHttpHandler()
            responded = api_devices.handle_get_devices(ApiContext(handler))

        self.assertTrue(responded)
        self.assertEqual(handler.status_codes, [500])
        payload = _decode_body(handler)
        self.assertEqual(payload["status"], "error")
        self.assertIn("database is locked", payload["message"])

    def test_empty_registry_returns_ok_with_empty_list(self) -> None:
        """登録ゼロでも status=ok / devices=[] を応答すること (Fail-Safe)"""
        import api_devices

        with mock.patch.object(api_devices.database, "get_all_devices", return_value=[]):
            handler = _FakeHttpHandler()
            responded = api_devices.handle_get_devices(ApiContext(handler))

        self.assertTrue(responded)
        payload = _decode_body(handler)
        self.assertEqual(payload, {"status": "ok", "devices": []})

    def test_dispatch_table_maps_devices_path(self) -> None:
        """local_sync_server.GET_PATH_HANDLERS に /api/devices が登録されていること"""
        import api_devices
        import local_sync_server

        self.assertIs(
            local_sync_server.GET_PATH_HANDLERS.get("/api/devices"),
            api_devices.handle_get_devices,
        )


class TestHandlePostDevicesRevoke(unittest.TestCase):
    """POST /api/devices/revoke ハンドラの契約（P1-4: 監査ログ付き）

    旧実装は local_sync_server.do_POST にインライン展開されており、失効操作が
    一切記録されなかった。監査ログ記録を含む処理本体を api_devices へ抽出した契約を凍結する。
    """

    def _ctx(self, body: bytes, client_ip: str = "127.0.0.1"):
        handler = _FakeHttpHandler()
        return handler, ApiContext(handler, body=body, client_ip=client_ip)

    def test_success_returns_200_and_records_audit(self) -> None:
        """失効成功時は 200 を返し、監査ログ（source=api）へ記録すること"""
        import api_devices

        with mock.patch.object(
            api_devices.database, "revoke_device", return_value=True
        ) as revoke_mock, mock.patch.object(
            api_devices, "record_device_revoke"
        ) as audit_mock:
            handler, ctx = self._ctx(b'{"device_id": 7}')
            responded = api_devices.handle_post_devices_revoke(ctx)

        self.assertTrue(responded)
        self.assertEqual(handler.status_codes, [200])
        self.assertTrue(_decode_body(handler)["revoked"])
        revoke_mock.assert_called_once_with(7)
        audit_mock.assert_called_once()
        self.assertEqual(audit_mock.call_args[0][0], 7)
        self.assertEqual(audit_mock.call_args[1]["source"], "api")

    def test_missing_device_id_returns_400_without_audit(self) -> None:
        """device_id 欠落は 400 を返し、監査ログも台帳も触らないこと"""
        import api_devices

        with mock.patch.object(api_devices.database, "revoke_device") as revoke_mock, \
                mock.patch.object(api_devices, "record_device_revoke") as audit_mock:
            handler, ctx = self._ctx(b"{}")
            responded = api_devices.handle_post_devices_revoke(ctx)

        self.assertTrue(responded)
        self.assertEqual(handler.status_codes, [400])
        self.assertFalse(revoke_mock.called)
        self.assertFalse(audit_mock.called)

    def test_unknown_device_returns_404_without_audit(self) -> None:
        """存在しない端末は 404 を返し、監査ログには記録しないこと"""
        import api_devices

        with mock.patch.object(
            api_devices.database, "revoke_device", return_value=False
        ), mock.patch.object(api_devices, "record_device_revoke") as audit_mock:
            handler, ctx = self._ctx(b'{"device_id": 999}')
            responded = api_devices.handle_post_devices_revoke(ctx)

        self.assertTrue(responded)
        self.assertEqual(handler.status_codes, [404])
        self.assertFalse(audit_mock.called)

    def test_invalid_json_returns_400(self) -> None:
        """壊れた JSON ボディでも無応答にせず 400 を返すこと"""
        import api_devices

        handler, ctx = self._ctx(b"{not-json")
        responded = api_devices.handle_post_devices_revoke(ctx)

        self.assertTrue(responded)
        self.assertEqual(handler.status_codes, [400])
        self.assertEqual(_decode_body(handler)["status"], "error")

    def test_db_error_returns_500(self) -> None:
        """DB異常時は 500 を返し、内容を欠落させないこと"""
        import api_devices

        with mock.patch.object(
            api_devices.database, "revoke_device", side_effect=RuntimeError("database is locked")
        ):
            handler, ctx = self._ctx(b'{"device_id": 1}')
            responded = api_devices.handle_post_devices_revoke(ctx)

        self.assertTrue(responded)
        self.assertEqual(handler.status_codes, [500])
        self.assertIn("database is locked", _decode_body(handler)["message"])


class TestDeviceRevokeAuditEntry(unittest.TestCase):
    """record_device_revoke が「誰が・いつ・何を」を監査ログへ残す契約（P1-4）"""

    def test_entry_contains_actor_operation_and_source(self) -> None:
        """操作主体・対象端末・経路がエントリへ記録されること"""
        import api_devices

        with mock.patch("storage.audit_repo.record_audit_log") as record_mock:
            api_devices.record_device_revoke(
                3, actor="pc_settings_ui", source="ui", device_name="Pixel Desk Pet"
            )

        entry = record_mock.call_args[0][0]
        self.assertEqual(entry.agent_type, "device_management")
        self.assertIn("device_id=3", entry.command)
        self.assertIn("Pixel Desk Pet", entry.command)
        self.assertEqual(entry.decision_by, "pc_settings_ui")
        self.assertIn("ui", entry.decision_message)
        self.assertEqual(entry.decision, "approved")
        self.assertEqual(entry.client_ip, None, "UI経路は client_ip を持たない")

    def test_api_source_records_client_ip(self) -> None:
        """API経路では接続元IPが client_ip として残ること"""
        import api_devices

        with mock.patch("storage.audit_repo.record_audit_log") as record_mock:
            api_devices.record_device_revoke(4, actor="192.168.1.9", source="api")

        entry = record_mock.call_args[0][0]
        self.assertEqual(entry.client_ip, "192.168.1.9")
        self.assertIn("api", entry.decision_message)

    def test_audit_is_written_synchronously(self) -> None:
        """失効の証跡は同期書き込みで確定すること（非同期キューに依存しない・P1-2）"""
        import api_devices

        with mock.patch("storage.audit_repo.record_audit_log") as record_mock, \
                mock.patch("audit_logger.get_global_audit_logger") as async_logger:
            api_devices.record_device_revoke(1, actor="x", source="ui")

        self.assertTrue(record_mock.called, "同期書き込みが行われていません")
        self.assertFalse(
            async_logger.called, "非同期ロガーへ委譲すると終了時に証跡が消える可能性があります"
        )

    def test_audit_failure_does_not_raise(self) -> None:
        """監査基盤の異常で失効作業を落とさないこと（可用性優先）"""
        import api_devices

        with mock.patch(
            "storage.audit_repo.record_audit_log", side_effect=RuntimeError("boom")
        ):
            api_devices.record_device_revoke(1, actor="x", source="ui")  # 例外を漏らさない


if __name__ == "__main__":
    unittest.main(verbosity=2)
