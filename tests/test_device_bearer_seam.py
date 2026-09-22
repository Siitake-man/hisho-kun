#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - デバイス台帳 Bearer シームの単体テスト (tests/test_device_bearer_seam.py)

レビュー P2「トークンハッシュ化ロジックの漏洩」対応の契約検証。
SHA-256 ハッシュ化をデータベース層内部に隠蔽する sync_device_session /
register_device_from_bearer を実 DB 同等の tempfile SQLite で検証する。

🛡️ P0-1 (2026-09-22) 契約変更:
  1. sync_device_session は **読み取り専用**。未登録の資格情報を自動登録しない
     (マスタートークン保持端末による身元乗っ取りの構造的排除)。
  2. 資格情報の登録 (束縛) は人間承認を伴うペアリング経路 (issue_device_token) のみ。
     同一IP+同一端末名の既存行を再利用し、台帳の重複増殖を防ぐ。
  3. 失効 (is_revoked=1) は自動経路で解除されない (解除は restore_device のみ)。
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
    get_all_devices,
    get_device_by_token_hash,
    register_device_from_bearer,
    sync_device_session,
)
from storage.device_repo import issue_device_token


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

    def test_sync_device_session_does_not_register_unknown_credential(self) -> None:
        """未登録 Bearer は自動登録されず None が返ること (P0-1: 認証経路は読み取り専用)。

        旧契約は未登録ベアラを device_name で自動登録していたが、これが
        マスタートークン保持端末の身元乗っ取り (他端末行の token_hash 上書き) を
        許していたため、書き込みを完全に廃止した。
        """
        dev = sync_device_session(
            "tok-new", ip_address="192.168.1.6", user_agent="android", db_path=self.db_path
        )
        self.assertIsNone(dev, "未登録資格情報は解決不能 (None) であること")
        found = get_device_by_token_hash(
            hashlib.sha256("tok-new".encode("utf-8")).hexdigest(), db_path=self.db_path
        )
        self.assertIsNone(found, "認証経路が台帳へ書き込んではならない (乗っ取り防止)")
        self.assertEqual(get_all_devices(db_path=self.db_path), [], "台帳は空のままであること")

    def test_sync_device_session_touches_last_seen(self) -> None:
        """登録済み端末は sync_device_session 呼出で IP / UA が更新されること"""
        register_device_from_bearer(
            "iPhone", "tok-2", ip_address="192.168.1.5", user_agent="iphone", db_path=self.db_path
        )
        dev = sync_device_session(
            "tok-2", ip_address="10.0.0.9", user_agent="new-ua", db_path=self.db_path
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
            "tok-revoked", ip_address="10.0.0.9", user_agent="ua-x", db_path=self.db_path
        )

        after = get_device_by_token_hash(token_hash, db_path=self.db_path)
        self.assertIsNone(after.ip_address)  # touch をスキップした証拠 (IP 未更新のまま)
        self.assertEqual(after.is_revoked, 1)

    def test_sync_device_session_propagates_contract_violations(self) -> None:
        """契約違反 (bearer=None 等) は握りつぶさず上位へ伝播すること"""
        with self.assertRaises(Exception):
            sync_device_session(None, db_path=self.db_path)

    def test_issue_device_token_reuses_identity_without_duplicate_rows(self) -> None:
        """ペアリング経路 (issue_device_token) は同一IP+名前の行を再利用し重複行を作らないこと。

        P0-1: 再利用 (資格情報の再束縛) は人間承認を伴うペアリング経路のみに許可される。
        再ペアリングで旧トークンは無効化され、失効フラグは維持される (解除は restore_device のみ)。
        """
        old_token = issue_device_token(
            "iPhone", ip_address="192.168.1.50", user_agent="iphone-ua", db_path=self.db_path
        )
        old_dev = get_device_by_token_hash(
            hashlib.sha256(old_token.encode("utf-8")).hexdigest(), db_path=self.db_path
        )
        self.assertIsNotNone(old_dev)

        # 失効させてから再ペアリング (承認済み) — 行は再利用され、失効は維持される
        self.assertTrue(database.revoke_device(old_dev.id, db_path=self.db_path))
        new_token = issue_device_token(
            "iPhone", ip_address="192.168.1.50", user_agent="iphone-ua", db_path=self.db_path
        )
        new_dev = get_device_by_token_hash(
            hashlib.sha256(new_token.encode("utf-8")).hexdigest(), db_path=self.db_path
        )
        self.assertIsNotNone(new_dev, "新トークンが既存行へ束縛されること")
        self.assertEqual(new_dev.id, old_dev.id, "重複行を作らず既存行を再利用すること")
        self.assertEqual(new_dev.is_revoked, 1, "ペアリング経路でも失効は自動解除されないこと")
        self.assertIsNone(
            get_device_by_token_hash(hashlib.sha256(old_token.encode("utf-8")).hexdigest(), db_path=self.db_path),
            "旧トークンは再ペアリングで無効化されること (資格情報ローテーション)",
        )
        self.assertEqual(len(get_all_devices(db_path=self.db_path)), 1, "台帳は1行のままであること")


if __name__ == "__main__":
    unittest.main()
