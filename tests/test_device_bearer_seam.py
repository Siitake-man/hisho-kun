#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - デバイス台帳 Bearer シームの単体テスト (tests/test_device_bearer_seam.py)

レビュー P2「トークンハッシュ化ロジックの漏洩」対応の契約検証。
SHA-256 ハッシュ化をデータベース層内部に隠蔽する sync_device_session /
register_device_from_bearer を実 DB 同等の tempfile SQLite で検証する。
"""

import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import database
from database import (
    get_device_by_token_hash,
    register_device_from_bearer,
    sync_device_session,
)


class TestDeviceBearerSeam(unittest.TestCase):
    """Bearer → デバイス台帳シーム (ハッシュ隠蔽 API) の契約検証"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db_path = os.path.join(self._tmp.name, "test_devices.db")
        database.init_db(self.db_path)

    def test_register_device_from_bearer_hashes_and_registers(self) -> None:
        """平文 Bearer が SHA-256 ハッシュ化されて台帳へ登録されること"""
        register_device_from_bearer(
            "iPhone", "tok-secret-1", ip_address="192.168.1.5", user_agent="iphone", db_path=self.db_path
        )
        expected_hash = hashlib.sha256("tok-secret-1".encode("utf-8")).hexdigest()
        device = get_device_by_token_hash(expected_hash, db_path=self.db_path)
        self.assertIsNotNone(device)
        self.assertEqual(device.device_name, "iPhone")

    def test_sync_device_session_registers_new_device_and_returns_none(self) -> None:
        """未登録 Bearer は自動登録され、旧契約と同一の None を返すこと"""
        dev = sync_device_session(
            "Android端末", "tok-new", ip_address="192.168.1.6", user_agent="android", db_path=self.db_path
        )
        self.assertIsNone(dev)
        found = get_device_by_token_hash(
            hashlib.sha256("tok-new".encode("utf-8")).hexdigest(), db_path=self.db_path
        )
        self.assertIsNotNone(found)
        self.assertEqual(found.device_name, "Android端末")

    def test_sync_device_session_touches_last_seen(self) -> None:
        """登録済み端末は sync_device_session 呼出で IP / UA が更新されること"""
        register_device_from_bearer(
            "iPhone", "tok-2", ip_address="192.168.1.5", user_agent="iphone", db_path=self.db_path
        )
        dev = sync_device_session(
            "iPhone", "tok-2", ip_address="10.0.0.9", user_agent="new-ua", db_path=self.db_path
        )
        self.assertIsNotNone(dev)
        self.assertEqual(dev.ip_address, "10.0.0.9")
        self.assertEqual(dev.user_agent, "new-ua")

    def test_sync_device_session_skips_touch_for_revoked(self) -> None:
        """失効済み端末の last_seen は更新せず. 失効状態の Device を返すこと"""
        token_hash = hashlib.sha256("tok-revoked".encode("utf-8")).hexdigest()
        dev_id = database.register_device("旧端末", token_hash, db_path=self.db_path)
        self.assertTrue(database.revoke_device(dev_id, db_path=self.db_path))

        before = get_device_by_token_hash(token_hash, db_path=self.db_path)
        self.assertIsNotNone(before)

        sync_device_session(
            "旧端末", "tok-revoked", ip_address="10.0.0.9", user_agent="ua-x", db_path=self.db_path
        )

        after = get_device_by_token_hash(token_hash, db_path=self.db_path)
        self.assertIsNone(after.ip_address)  # touch をスキップした証拠 (IP 未更新のまま)
        self.assertEqual(after.is_revoked, 1)

    def test_sync_device_session_propagates_contract_violations(self) -> None:
        """契約違反 (bearer=None 等) は握りつぶさず上位へ伝播すること"""
        with self.assertRaises(Exception):
            sync_device_session("x", None, db_path=self.db_path)


if __name__ == "__main__":
    unittest.main()