"""Unit tests for AI Dotfiles backup and restore tool (tools/sync_ai_dotfiles.py)"""

import unittest
import tempfile
import sqlite3
import shutil
from pathlib import Path
import sys

# リポジトリルートをパスに追加
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from tools import sync_ai_dotfiles as sad


class TestSyncAIDotfiles(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_should_exclude(self):
        """除外パターンが正しく機能すること"""
        self.assertTrue(sad._should_exclude(Path("auth.json")))
        self.assertTrue(sad._should_exclude(Path("cap_sid")))
        self.assertTrue(sad._should_exclude(Path("node_modules")))
        self.assertTrue(sad._should_exclude(Path("logs_2.sqlite")))
        self.assertTrue(sad._should_exclude(Path("test.sqlite-wal")))
        self.assertTrue(sad._should_exclude(Path("test.bak")))

        # 許可されるべきファイル
        self.assertFalse(sad._should_exclude(Path("GEMINI.md")))
        self.assertFalse(sad._should_exclude(Path("instructions.md")))
        self.assertFalse(sad._should_exclude(Path("opencode.jsonc")))
        self.assertFalse(sad._should_exclude(Path("SKILL.md")))

    def test_ensure_gitignore(self):
        """.gitignore が正しく生成され、必要な除外ルールが含まれていること"""
        dotfiles_dir = self.temp_dir / ".ai_dotfiles"
        sad.ensure_gitignore(dotfiles_dir)

        gitignore = dotfiles_dir / ".gitignore"
        self.assertTrue(gitignore.exists())
        content = gitignore.read_text(encoding="utf-8")
        self.assertIn("auth.json", content)
        self.assertIn("cap_sid", content)
        self.assertIn("*.sqlite", content)
        self.assertIn("node_modules/", content)

    def test_export_knowledge_vault_sql(self):
        """SQLite から知識の宝庫 (user_insights) がテキストSQLとしてクリーンにエクスポートされること"""
        # ダミーの SQLite DB を作成
        dummy_hisho = self.temp_dir / "hisho_repo"
        dummy_hisho.mkdir(parents=True)
        db_path = dummy_hisho / "neo_secretary.db"

        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE user_insights (
                category TEXT NOT NULL,
                insight_key TEXT NOT NULL,
                content TEXT NOT NULL,
                context TEXT,
                confidence REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (category, insight_key)
            )
        """)
        conn.execute(
            "INSERT INTO user_insights (category, insight_key, content) VALUES (?, ?, ?)",
            ("architecture", "rule_1", "ボスのこだわり'テスト'ルール")
        )
        conn.commit()
        conn.close()

        # 一時的に HISHO_ROOT をモック
        orig_hisho = sad.HISHO_ROOT
        try:
            sad.HISHO_ROOT = dummy_hisho
            dotfiles_dir = self.temp_dir / ".ai_dotfiles"
            sad.export_knowledge_vault(dotfiles_dir)

            sql_file = dotfiles_dir / "neo_secretary" / "user_insights.sql"
            self.assertTrue(sql_file.exists())
            content = sql_file.read_text(encoding="utf-8")
            self.assertIn("CREATE TABLE IF NOT EXISTS user_insights", content)
            self.assertIn("INSERT OR REPLACE INTO user_insights", content)
            self.assertIn("ボスのこだわり''テスト''ルール", content)
        finally:
            sad.HISHO_ROOT = orig_hisho

    def test_restore_knowledge_vault_sql(self):
        """エクスポートされたSQLが新規DBへ完全に復元されること (ラウンドトリップ検証)"""
        # ダミーの SQL ファイルを配置
        dotfiles_dir = self.temp_dir / ".ai_dotfiles"
        vault_dir = dotfiles_dir / "neo_secretary"
        vault_dir.mkdir(parents=True)
        sql_file = vault_dir / "user_insights.sql"
        sql_file.write_text("""
CREATE TABLE IF NOT EXISTS user_insights (
    category TEXT NOT NULL,
    insight_key TEXT NOT NULL,
    content TEXT NOT NULL,
    context TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (category, insight_key)
);
INSERT OR REPLACE INTO user_insights (category, insight_key, content, context, confidence, created_at, updated_at) VALUES ('safety', 'test_key', 'テスト内容''エスケープ済み', NULL, 1.0, '2026-09-22 09:00:00', '2026-09-22 09:00:00');
""", encoding="utf-8")

        # まだ DB ファイルが存在しない新環境をシミュレート
        dummy_restore_hisho = self.temp_dir / "new_machine_hisho"
        orig_hisho = sad.HISHO_ROOT
        try:
            sad.HISHO_ROOT = dummy_restore_hisho
            sad.restore_dotfiles(dotfiles_dir)

            restored_db = dummy_restore_hisho / "neo_secretary.db"
            self.assertTrue(restored_db.exists(), "新規マシン環境でもDBが自動作成されてインポートされるべきです")

            conn = sqlite3.connect(str(restored_db))
            cursor = conn.cursor()
            cursor.execute("SELECT category, insight_key, content FROM user_insights WHERE insight_key='test_key'")
            row = cursor.fetchone()
            conn.close()

            self.assertIsNotNone(row)
            self.assertEqual(row[0], "safety")
            self.assertEqual(row[1], "test_key")
            self.assertEqual(row[2], "テスト内容'エスケープ済み")
        finally:
            sad.HISHO_ROOT = orig_hisho


if __name__ == "__main__":
    unittest.main()
