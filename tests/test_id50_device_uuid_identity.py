#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ID 50: 端末自己生成UUIDによる識別恒久化（ペアリング行マッチの属性依存解消）を検証する。

背景（2026-09-23）:
    行再利用キーが ``(IP, 端末名)`` 依存のため、IP変更や Serve/LAN 併用で台帳行が
    分裂・増殖していた（ゾンビ行・失効漏れ・1クリック横取りの温床）。ブラウザから
    MAC は取得不可のため、**PWA が自分で生成する UUID**（crypto.randomUUID）を
    永続化し、``X-Device-UUID`` ヘッダで申告する方式へ移行する。

本テストが凍結する契約:
    1. ``register_device(..., device_uuid=...)`` は **UUID 一致を最優先**で行を再利用し、
       IP・UA・経路が変わっても行を増やさない。
    2. UUID が無い/不正なクライアントは従来どおり（IP+端末名 → 端末名+UA）で動作する（後方互換）。
    3. UUID は**認証の根拠にならない**（資格情報の束縛は人間承認済みペアリング経路のみ＝AD-3 不変）。
    4. 端末一覧とログで端末を識別できる（短縮表示）。
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
    get_all_devices,
    issue_device_token,
    normalize_device_uuid,
    register_device,
)
from ui import device_manager_panel

VALID_UUID = "123e4567-e89b-42d3-a456-426614174000"
ANOTHER_UUID = "9c858901-8a57-4791-81fe-4c455b099bc9"
ANDROID_UA = "Mozilla/5.0 (Linux; Android 14; Pixel 8)"


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


class TestNormalizeDeviceUuid(unittest.TestCase):
    """UUID 正規化の入力検証（推測不能・長さ上限・不正値の排除）を検証する。"""

    def test_valid_uuid_is_canonicalized(self) -> None:
        """正しい UUID は小文字の正規形で返る。"""
        self.assertEqual(normalize_device_uuid(VALID_UUID.upper()), VALID_UUID)

    def test_invalid_values_return_none(self) -> None:
        """不正値・空・過大長は None（呼び出し側は従来キーへフォールバック）。"""
        for raw in (None, "", "   ", "not-a-uuid", "1234567890", "a" * 100):
            with self.subTest(raw=raw):
                self.assertIsNone(normalize_device_uuid(raw))


class TestRegisterDeviceUuidReuse(unittest.TestCase):
    """UUID 優先の行再利用（IP/UA 変更でも増殖しない）を検証する。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmp.name) / "neo_secretary.db")
        init_db(self.db_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_reuses_row_by_uuid_across_ip_and_ua_change(self) -> None:
        """同一UUIDなら IP・UA が変わっても同じ行を再利用する（ID 50 の核心）。"""
        first_id = register_device(
            "Android端末", "hash-1", ip_address="192.168.1.4", user_agent="UA-A",
            db_path=self.db_path, reuse_identity=True, device_uuid=VALID_UUID,
        )
        second_id = register_device(
            "Android端末", "hash-2", ip_address="100.64.0.5", user_agent="UA-B",
            db_path=self.db_path, reuse_identity=True, device_uuid=VALID_UUID,
        )

        self.assertEqual(first_id, second_id, "行が増殖しないこと")
        devices = get_all_devices(db_path=self.db_path)
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].ip_address, "100.64.0.5")
        self.assertEqual(devices[0].device_uuid, VALID_UUID)

    def test_different_uuid_creates_new_row(self) -> None:
        """別UUIDの端末は別行として登録される（UUIDが端末識別の主キー）。"""
        register_device(
            "Android端末", "hash-1", ip_address="192.168.1.4",
            db_path=self.db_path, reuse_identity=True, device_uuid=VALID_UUID,
        )
        register_device(
            "Android端末", "hash-2", ip_address="192.168.1.4",
            db_path=self.db_path, reuse_identity=True, device_uuid=ANOTHER_UUID,
        )
        self.assertEqual(len(get_all_devices(db_path=self.db_path)), 2)

    def test_falls_back_without_uuid(self) -> None:
        """UUID 無しは従来どおり (IP, 端末名) で再利用する（後方互換）。"""
        first_id = register_device(
            "Legacy端末", "hash-1", ip_address="192.168.1.9",
            db_path=self.db_path, reuse_identity=True,
        )
        second_id = register_device(
            "Legacy端末", "hash-2", ip_address="192.168.1.9", user_agent="UA-X",
            db_path=self.db_path, reuse_identity=True,
        )
        self.assertEqual(first_id, second_id)
        self.assertIsNone(get_all_devices(db_path=self.db_path)[0].device_uuid)

    def test_uuid_registered_row_is_never_adopted_by_legacy_keys(self) -> None:
        """UUID 記名済み行は、ヘッダを外したクライアントの (名前, UA) 一致でも乗っ取れない (P1-1)。"""
        register_device(
            "Android端末", "hash-1", user_agent="UA-A",
            db_path=self.db_path, reuse_identity=True, device_uuid=VALID_UUID,
        )
        register_device(
            "Android端末", "hash-2", user_agent="UA-A",
            db_path=self.db_path, reuse_identity=True,
        )
        devices = get_all_devices(db_path=self.db_path)
        self.assertEqual(len(devices), 2, "UUID記名行は UUID 一致でのみ再利用されること")
        uuid_rows = [d for d in devices if d.device_uuid == VALID_UUID]
        self.assertEqual(len(uuid_rows), 1)
        self.assertNotEqual(uuid_rows[0].token_hash, "hash-2", "victim の資格情報が置換されないこと")

    def test_legacy_null_row_is_adopted_and_uuid_bound(self) -> None:
        """UUID 導入前の旧行（NULL）は UUID 提示クライアントに採用され、UUID が束縛される (P2-1)。"""
        legacy_id = register_device(
            "Android端末", "hash-legacy", ip_address="192.168.1.4",
            db_path=self.db_path, reuse_identity=True,
        )
        adopted_id = register_device(
            "Android端末", "hash-new", ip_address="192.168.1.4", user_agent="UA-B",
            db_path=self.db_path, reuse_identity=True, device_uuid=VALID_UUID,
        )
        self.assertEqual(legacy_id, adopted_id, "移行ゾンビ行を作らないこと")
        devices = get_all_devices(db_path=self.db_path)
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].device_uuid, VALID_UUID)

    def test_existing_uuid_is_preserved_when_reregistered_without_uuid(self) -> None:
        """同一 token_hash の再登録で UUID を送らなくても既存 UUID が消えない (COALESCE 凍結)。"""
        register_device(
            "Android端末", "hash-1", db_path=self.db_path,
            reuse_identity=True, device_uuid=VALID_UUID,
        )
        register_device("Android端末", "hash-1", db_path=self.db_path, reuse_identity=True)
        self.assertEqual(get_all_devices(db_path=self.db_path)[0].device_uuid, VALID_UUID)


class TestPairingStoresDeviceUuid(unittest.TestCase):
    """Serve 経由ペアリングが X-Device-UUID を台帳へ保存し、行を集約することを検証する。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmp.name) / "neo_secretary.db")
        init_db(self.db_path)
        self._resolver_patch = mock.patch(
            "storage.connection.resolve_db_path",
            side_effect=lambda db_path="neo_secretary.db": self.db_path,
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

    def _pair_via_serve(self, headers: dict) -> dict:
        tm = local_sync_server.get_sync_token_manager()
        tm.unlock_pairing(duration_sec=60)
        tm.set_device_approval_callback(lambda dev_name, client_ip: True)
        handler = _FakeHttpHandler()
        handler.headers = {"Host": "node.tail08a991.ts.net", "User-Agent": ANDROID_UA}
        handler.headers.update(headers)
        DeskPetSyncHandler._handle_auth_token(handler, "127.0.0.1", ANDROID_UA)
        return json.loads(handler.wfile.getvalue().decode("utf-8"))

    def test_pairing_stores_uuid_and_aggregates_rows(self) -> None:
        """同じUUIDで Serve/LAN の実IPが変わっても1行に集約される。"""
        first = self._pair_via_serve(
            {"X-Device-UUID": VALID_UUID, "X-Forwarded-For": "100.64.0.5"}
        )
        self.assertIn("token", first)

        devices = get_all_devices(db_path=self.db_path)
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].device_uuid, VALID_UUID)
        first_id = devices[0].id

        second = self._pair_via_serve(
            {"X-Device-UUID": VALID_UUID, "X-Forwarded-For": "192.168.1.4"}
        )
        self.assertIn("token", second)

        devices_after = get_all_devices(db_path=self.db_path)
        self.assertEqual(len(devices_after), 1, "経路が変わっても行が増殖しないこと")
        self.assertEqual(devices_after[0].id, first_id)
        self.assertEqual(devices_after[0].ip_address, "192.168.1.4")

    def test_invalid_uuid_header_is_ignored(self) -> None:
        """不正な UUID ヘッダは無視され、従来動作（UUIDなし）で登録される。"""
        response = self._pair_via_serve(
            {"X-Device-UUID": "not-a-uuid", "X-Forwarded-For": "100.64.0.5"}
        )
        self.assertIn("token", response)
        devices = get_all_devices(db_path=self.db_path)
        self.assertEqual(len(devices), 1)
        self.assertIsNone(devices[0].device_uuid)


class TestDeviceUuidVisibility(unittest.TestCase):
    """端末一覧で UUID 短縮表示（識別可能性）を検証する。"""

    def test_subtitle_shows_short_uuid(self) -> None:
        device = mock.Mock(
            id=1,
            device_name="Pixel Desk Pet",
            ip_address="192.168.1.9",
            user_agent="Mozilla/5.0 (Linux; Android 14)",
            is_revoked=0,
            created_at=1758000600000,
            last_seen=1758000600000,
            device_uuid=VALID_UUID,
        )
        rows = device_manager_panel.build_device_rows([device])
        self.assertEqual(len(rows), 1)
        self.assertIn("端末ID: 123e4567", rows[0].subtitle)


class TestDeviceUuidMigration(unittest.TestCase):
    """旧スキーマ（device_uuid 無し）からの冪等マイグレーションを検証する (P2-2)。"""

    def test_init_db_adds_column_to_legacy_schema_idempotently(self) -> None:
        import sqlite3

        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "legacy.db")
            conn = sqlite3.connect(db_path)
            try:
                conn.execute("""
                    CREATE TABLE devices (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        device_name TEXT NOT NULL,
                        token_hash TEXT NOT NULL UNIQUE,
                        ip_address TEXT,
                        user_agent TEXT,
                        created_at INTEGER NOT NULL,
                        last_seen INTEGER NOT NULL,
                        is_revoked INTEGER NOT NULL DEFAULT 0
                    )
                """)
                conn.commit()
            finally:
                conn.close()

            init_db(db_path)  # 1回目: device_uuid を追加
            init_db(db_path)  # 2回目: 冪等（エラーなし）

            conn = sqlite3.connect(db_path)
            try:
                columns = {row[1] for row in conn.execute("PRAGMA table_info(devices)")}
            finally:
                conn.close()
            self.assertIn("device_uuid", columns)


class TestPwaSendsDeviceUuid(unittest.TestCase):
    """PWA が端末UUIDを生成・永続化してヘッダ送信することをソース凍結で保証する。"""

    def test_pet_auth_js_generates_and_sends_uuid(self) -> None:
        source = (
            Path(__file__).resolve().parent.parent / "web_pet" / "pet_auth.js"
        ).read_text(encoding="utf-8")
        # コメントではなく**コード行**を拘束する (P2-2: コメントで満たせる断言の排除)
        self.assertIn("localStorage.setItem(DEVICE_UUID_KEY, uuid)", source)
        self.assertIn("'X-Device-UUID': deviceUuid", source)
        self.assertIn("window.crypto.getRandomValues(bytes)", source)
        self.assertIn("window.crypto.randomUUID()", source)


if __name__ == "__main__":
    unittest.main()
