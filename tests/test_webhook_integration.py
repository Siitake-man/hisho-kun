"""
ネオ秘書くん - 外部SaaS・マルチ中継Webhook連携 単体テスト (tests/test_webhook_integration.py)
"""
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import database
import webhook_tools


class TestWebhookIntegration(unittest.TestCase):
    """外部 SaaS Webhook の設定永続化・受信登録・送信 POST の契約を検証する。

    受信ペイロードが DB に正しく登録され、送信設定が保存・復元されて
    外部 URL へ POST されること（マルチ中継連携の出入力契約）を守る。
    """

    def setUp(self):
        """テスト用テンポラリSQLiteデータベースの初期化"""
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp_dir.name) / "test_secretary.db")
        database.init_db(self.db_path)

    def tearDown(self):
        """テンポラリディレクトリの破棄"""
        self.tmp_dir.cleanup()

    def test_webhook_config_save_load(self):
        """設定ファイルのロード・保存が正しく動作するか検証"""
        config_path = Path(self.tmp_dir.name) / "webhook_config.json"
        test_cfg = {
            "outgoing_webhook_url": "https://hooks.zapier.com/test",
            "webhook_secret": "secret12345",
            "sync_events": True,
            "sync_tasks": False
        }
        with patch("webhook_tools.CONFIG_PATH", config_path):
            webhook_tools.save_webhook_config(test_cfg)
            loaded = webhook_tools.get_webhook_config()
            self.assertEqual(loaded["outgoing_webhook_url"], "https://hooks.zapier.com/test")
            self.assertEqual(loaded["webhook_secret"], "secret12345")
            self.assertFalse(loaded["sync_tasks"])

    def test_process_incoming_calendar_webhook(self):
        """外部Webhookから届いた予定データが正しくDBへ登録されるか検証"""
        payload = {
            "title": "Zapier連携定例会議",
            "description": "GoogleカレンダーからZapier経由で自動同期された予定",
            "start_time": 1756550000000,
            "end_time": 1756553600000,
            "id": "ext_evt_999"
        }
        result = webhook_tools.process_incoming_calendar_webhook(payload, db_path=self.db_path)
        self.assertEqual(result["status"], "success")
        self.assertIn("event_id", result)

        # DBから取得して検証
        ev = database.get_event(result["event_id"], db_path=self.db_path)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.title, "Zapier連携定例会議")
        self.assertEqual(ev.google_event_id, "ext_evt_999")

    def test_process_incoming_task_webhook(self):
        """外部Webhookから届いたTODOタスクが正しくDBへ登録されるか検証"""
        payload = {
            "title": "Slackで依頼された資料作成",
            "description": "Slackメンションから転送されたタスク",
            "priority": "high",
            "due_date": "2026-08-31"
        }
        result = webhook_tools.process_incoming_task_webhook(payload, db_path=self.db_path)
        self.assertEqual(result["status"], "success")
        self.assertIn("task_id", result)

        # DBから取得して検証
        tasks = database.get_tasks(db_path=self.db_path)
        created = [t for t in tasks if t.id == result["task_id"]]
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].title, "Slackで依頼された資料作成")
        self.assertEqual(created[0].priority, 3)

    def test_send_event_to_outgoing_webhook(self):
        """作成予定が外部Webhook URLへPOST送信されるか検証"""
        config_path = Path(self.tmp_dir.name) / "webhook_config.json"
        test_cfg = {
            "outgoing_webhook_url": "https://hooks.zapier.com/hooks/catch/12345",
            "webhook_secret": "my_secret",
            "sync_events": True,
            "sync_tasks": True
        }
        with patch("webhook_tools.CONFIG_PATH", config_path):
            webhook_tools.save_webhook_config(test_cfg)

            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_res = MagicMock()
                mock_res.status = 200
                mock_res.__enter__.return_value = mock_res
                mock_urlopen.return_value = mock_res

                event_dict = {
                    "title": "新規プロジェクトキックオフ",
                    "start_time": 1756560000000,
                    "end_time": 1756563600000
                }
                success = webhook_tools.send_event_to_outgoing_webhook(event_dict)
                self.assertTrue(success)
                self.assertTrue(mock_urlopen.called)


if __name__ == "__main__":
    unittest.main()
