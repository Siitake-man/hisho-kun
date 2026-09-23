"""
デバイス台帳機能 (devices テーブル & CRUD) の単体テスト

TDD: Red先行テスト
- register_device: 新規登録
- get_device_by_token_hash: 取得と属性検証
- touch_device_last_seen: 最終アクセス日時の更新
- revoke_device: 特定端末の失効
- get_all_devices: 一覧取得
"""

import os
import tempfile
import unittest
import hashlib
from datetime import datetime

from database import (
    init_db,
    Device,
    register_device,
    get_device_by_token_hash,
    get_all_devices,
    revoke_device,
    touch_device_last_seen,
)


class TestDeviceRegistry(unittest.TestCase):
    """端末台帳 (devices テーブル) の CRUD と last_seen 更新契約を検証する。

    登録・取得・最終アクセス更新・失効・一覧取得が同一 DB 上で
    一貫して振る舞うこと（トークンハッシュによる台帳照会が壊れないこと）を守る。
    """

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        init_db(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_register_and_get_device(self):
        """登録直後の端末がトークンハッシュ経由で全属性付きで復元されることを保証する。"""
        raw_token = "secret_token_alpha_123"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        device_id = register_device(
            device_name="Boss iPhone 15 Pro",
            token_hash=token_hash,
            ip_address="192.168.1.50",
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
            db_path=self.db_path,
        )
        self.assertIsInstance(device_id, int)
        self.assertGreater(device_id, 0)

        device = get_device_by_token_hash(token_hash, db_path=self.db_path)
        self.assertIsNotNone(device)
        self.assertEqual(device.device_name, "Boss iPhone 15 Pro")
        self.assertEqual(device.token_hash, token_hash)
        self.assertEqual(device.ip_address, "192.168.1.50")
        self.assertEqual(device.is_revoked, 0)

    def test_touch_device_last_seen(self):
        """touch_device_last_seen 呼び出しで最終アクセス日時と IP が進むことを保証する。"""
        raw_token = "secret_token_beta_456"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        register_device(
            device_name="Boss iPad Mini",
            token_hash=token_hash,
            ip_address="192.168.1.60",
            db_path=self.db_path,
        )

        device_before = get_device_by_token_hash(token_hash, db_path=self.db_path)
        self.assertIsNotNone(device_before)

        # last_seen を更新
        success = touch_device_last_seen(
            token_hash=token_hash,
            ip_address="100.64.0.5",  # Tailscale IP
            db_path=self.db_path,
        )
        self.assertTrue(success)

        device_after = get_device_by_token_hash(token_hash, db_path=self.db_path)
        self.assertEqual(device_after.ip_address, "100.64.0.5")
        self.assertGreaterEqual(device_after.last_seen, device_before.last_seen)

    def test_revoke_device(self):
        """失効実行後も端末レコードは残り、is_revoked が 1 に切り替わることを保証する。"""
        raw_token = "secret_token_gamma_789"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        dev_id = register_device(
            device_name="Old Android Phone",
            token_hash=token_hash,
            db_path=self.db_path,
        )

        # 失効実行
        res = revoke_device(dev_id, db_path=self.db_path)
        self.assertTrue(res)

        device = get_device_by_token_hash(token_hash, db_path=self.db_path)
        self.assertIsNotNone(device)
        self.assertEqual(device.is_revoked, 1)

    def test_get_all_devices(self):
        """登録済みの全端末が登録順に漏れなく一覧取得されることを保証する。"""
        token1 = hashlib.sha256(b"tok1").hexdigest()
        token2 = hashlib.sha256(b"tok2").hexdigest()

        register_device("Dev 1", token1, db_path=self.db_path)
        register_device("Dev 2", token2, db_path=self.db_path)

        devices = get_all_devices(db_path=self.db_path)
        self.assertEqual(len(devices), 2)
        names = [d.device_name for d in devices]
        self.assertIn("Dev 1", names)
        self.assertIn("Dev 2", names)

    def test_infer_device_name(self):
        """User-Agent から端末種別名が推定され、非ブラウザUAも正直に表示されることを保証する。"""
        from local_sync_server import DeskPetSyncHandler
        self.assertEqual(
            DeskPetSyncHandler._infer_device_name("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"),
            "iPhone"
        )
        self.assertEqual(
            DeskPetSyncHandler._infer_device_name("Mozilla/5.0 (iPad; CPU OS 16_5 like Mac OS X)"),
            "iPad"
        )
        self.assertEqual(
            DeskPetSyncHandler._infer_device_name("Mozilla/5.0 (Linux; Android 14; Pixel 8)"),
            "Android端末"
        )
        self.assertEqual(
            DeskPetSyncHandler._infer_device_name("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"),
            "Mac"
        )
        self.assertEqual(
            DeskPetSyncHandler._infer_device_name("Mozilla/5.0 (Windows NT 10.0; Win64; x64)"),
            "Windows PC"
        )
        # 🛡️ ID 50/53 (2026-09-23): 非ブラウザUAを「スマホブラウザ」と偽装しない
        # (承認ダイアログでボスが正体を判別できるようにする契約変更)
        self.assertEqual(
            DeskPetSyncHandler._infer_device_name("UnknownCustomClient/1.0"),
            "⚠️ 非ブラウザ端末"
        )


if __name__ == "__main__":
    unittest.main()

