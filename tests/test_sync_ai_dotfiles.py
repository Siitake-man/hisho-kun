"""ネオ秘書くん — sync_ai_dotfiles および Knowledge Vault エクスポートのテスト (tests/test_sync_ai_dotfiles.py)"""

import json
import os
import tempfile
import unittest
from pathlib import Path

import database
from storage.insight_repo import add_user_insight
from tools.sync_ai_dotfiles import export_knowledge_vault, sync_dotfiles


class TestSyncAiDotfiles(unittest.TestCase):
    """sync_ai_dotfiles ツールおよび Knowledge Vault エクスポートの正常動作を検証するテスト"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_db_path = os.path.join(self.temp_dir.name, "test_vault.db")
        database.init_db(self.tmp_db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_export_knowledge_vault_schema_correctness(self):
        """Knowledge Vault のエクスポートがエラー（no such column: insight_key等）なく、正しいスキーマで最新知見を含んで取得できることを検証"""
        # 知見を追加
        id1 = add_user_insight("Constraint", "平日夜は作業を控える", importance=5, context_tags="time,family", db_path=self.tmp_db_path)
        id2 = add_user_insight("Preference", "ダークモードを優先する", importance=4, context_tags="theme,ui", db_path=self.tmp_db_path)

        self.assertGreater(id1, 0)
        self.assertGreater(id2, 0)

        # エクスポート実行 (例外が発生しないこと、insight_key 等の存在しないカラムエラーが出ないこと)
        insights = export_knowledge_vault(db_path=self.tmp_db_path)

        self.assertEqual(len(insights), 2)

        # 必要なフィールドの存在確認
        expected_keys = {"id", "category", "content", "context_tags", "importance", "created_at", "updated_at"}
        for item in insights:
            self.assertTrue(expected_keys.issubset(item.keys()), f"欠落フィールドがあります: {set(expected_keys) - set(item.keys())}")

        # 追加した最新知見の内容が含まれているか検証
        contents = [item["content"] for item in insights]
        self.assertIn("平日夜は作業を控える", contents)
        self.assertIn("ダークモードを優先する", contents)

    def test_sync_dotfiles_creates_knowledge_vault_json(self):
        """sync_dotfiles 関数が指定ディレクトリへ knowledge_vault.json を正常に同期作成することを検証"""
        add_user_insight("Project", "リファクタリング時はTDDを厳守", importance=5, db_path=self.tmp_db_path)

        dotfiles_path = Path(self.temp_dir.name) / "ai_dotfiles"
        summary = sync_dotfiles(dotfiles_dir=dotfiles_path, db_path=self.tmp_db_path, check_only=False)

        self.assertEqual(summary["status"], "success")
        self.assertEqual(summary["vault_count"], 1)

        vault_file = dotfiles_path / "knowledge_vault.json"
        self.assertTrue(vault_file.exists())

        with open(vault_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["content"], "リファクタリング時はTDDを厳守")


if __name__ == "__main__":
    unittest.main()
