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


if __name__ == "__main__":
    unittest.main(verbosity=2)
