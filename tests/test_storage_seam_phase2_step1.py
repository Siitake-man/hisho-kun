"""
Neo-Secretary ストレージ Seam 分割 Phase 2 第一歩 回帰テスト (tests/test_storage_seam_phase2_step1.py)

storage/audit_repo.py および storage/device_repo.py の直接利用・独立機能検証、
および database.py / audit_logger.py の Facade (100% 後方互換性) を自動検証します。
"""

import hashlib
import os
import tempfile
import time
import unittest

import storage
import database
import audit_logger
from storage.models import AuditLogEntry, Device
from storage.audit_repo import record_audit_log, get_audit_logs
from storage.device_repo import (
    register_device,
    get_device_by_token_hash,
    sync_device_session,
    register_device_from_bearer,
    get_all_devices,
    revoke_device,
    touch_device_last_seen,
)


class TestStorageSeamPhase2Step1(unittest.TestCase):
    """Phase 2 Step 1: audit_repo.py / device_repo.py の独立性および Facade 後方互換性テスト"""

    def test_01_storage_package_phase2_exports(self):
        """storage パッケージから Phase 2 第一歩で切り出されたシンボルがインポート可能であることを検証。"""
        expected_symbols = [
            "AuditLogEntry",
            "record_audit_log",
            "get_audit_logs",
            "register_device",
            "get_device_by_token_hash",
            "sync_device_session",
            "register_device_from_bearer",
            "get_all_devices",
            "revoke_device",
            "touch_device_last_seen",
        ]
        for symbol in expected_symbols:
            self.assertTrue(hasattr(storage, symbol), f"storage に {symbol} が存在しません")

    def test_02_database_and_audit_logger_facade_identity(self):
        """database.py および audit_logger.py が storage 側のオブジェクトと同一であることを検証 (100% 後方互換性)。"""
        check_pairs = [
            ("AuditLogEntry (database)", storage.AuditLogEntry, database.AuditLogEntry),
            ("AuditLogEntry (audit_logger)", storage.AuditLogEntry, audit_logger.AuditLogEntry),
            ("record_audit_log (database)", storage.record_audit_log, database.record_audit_log),
            ("record_audit_log (audit_logger)", storage.record_audit_log, audit_logger.record_audit_log),
            ("get_audit_logs (database)", storage.get_audit_logs, database.get_audit_logs),
            ("get_audit_logs (audit_logger)", storage.get_audit_logs, audit_logger.get_audit_logs),
            ("register_device", storage.register_device, database.register_device),
            ("get_device_by_token_hash", storage.get_device_by_token_hash, database.get_device_by_token_hash),
            ("sync_device_session", storage.sync_device_session, database.sync_device_session),
            ("register_device_from_bearer", storage.register_device_from_bearer, database.register_device_from_bearer),
            ("get_all_devices", storage.get_all_devices, database.get_all_devices),
            ("revoke_device", storage.revoke_device, database.revoke_device),
            ("touch_device_last_seen", storage.touch_device_last_seen, database.touch_device_last_seen),
        ]
        for name, storage_obj, target_obj in check_pairs:
            self.assertIs(storage_obj, target_obj, f"{name} の参照先が一致しません (Facade不整合)")

    def test_03_audit_repo_direct_usage(self):
        """storage.audit_repo の録画・取得が直接呼び出しで正常動作することを検証。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            temp_db = tf.name

        try:
            storage.init_db(temp_db)

            entry = AuditLogEntry(
                request_id="req_phase2_01",
                agent_type="claude-code",
                agent_name="Claude Code",
                command="pytest tests/",
                summary="独立性テスト実行",
                risk_level="auto_allow",
                decision="auto_allowed",
                decision_by="policy_engine",
                created_at=int(time.time()),
            )
            log_id = record_audit_log(entry, db_path=temp_db)
            self.assertGreater(log_id, 0)

            logs = get_audit_logs(db_path=temp_db)
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0].request_id, "req_phase2_01")
            self.assertEqual(logs[0].command, "pytest tests/")
        finally:
            if os.path.exists(temp_db):
                os.remove(temp_db)

    def test_04_device_repo_direct_usage(self):
        """storage.device_repo の端末登録・同期・取得・失効が直接呼び出しで正常動作することを検証。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            temp_db = tf.name

        try:
            storage.init_db(temp_db)

            # 1. Bearer から登録
            raw_token = "phase2_secret_bearer_token"
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

            dev_id = register_device_from_bearer(
                "Boss iPhone 15", raw_token, ip_address="192.168.1.100", user_agent="PWAClient", db_path=temp_db
            )
            self.assertGreater(dev_id, 0)

            # 2. 検索検証
            device = get_device_by_token_hash(token_hash, db_path=temp_db)
            self.assertIsNotNone(device)
            self.assertEqual(device.device_name, "Boss iPhone 15")
            self.assertEqual(device.is_revoked, 0)

            # 3. セッション同期 (touch_last_seen) — P0-1: 認証経路は読み取り専用 (bearer のみ)
            synced_device = sync_device_session(
                raw_token, ip_address="10.0.0.1", user_agent="PWAClientV2", db_path=temp_db
            )
            self.assertIsNotNone(synced_device)
            self.assertEqual(synced_device.ip_address, "10.0.0.1")

            # 4. 一覧取得
            all_devs = get_all_devices(db_path=temp_db)
            self.assertEqual(len(all_devs), 1)
            self.assertEqual(all_devs[0].device_name, "Boss iPhone 15")

            # 5. 端末失効
            ok = revoke_device(dev_id, db_path=temp_db)
            self.assertTrue(ok)

            revoked_device = get_device_by_token_hash(token_hash, db_path=temp_db)
            self.assertIsNotNone(revoked_device)
            self.assertEqual(revoked_device.is_revoked, 1)
        finally:
            if os.path.exists(temp_db):
                os.remove(temp_db)


if __name__ == "__main__":
    unittest.main()
