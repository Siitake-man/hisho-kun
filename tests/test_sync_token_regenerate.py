#!/usr/bin/env python3
"""
ネオ秘書くん - 同期トークン再生成の単体テスト (test_sync_token_regenerate.py)

設定画面「スマホ連携 全解除（トークン再生成）」ボタン (2026-09-01 3周レビュー
P1対応) の中核となる SyncTokenManager.regenerate() の振る舞いを検証します。

実トークンファイル (.sync_token) には一切触れず、テンポラリパスへ差し替えて
実行するため、実環境のペアリング状態を壊しません。

実行:
    venv\\Scripts\\python.exe -m unittest tests.test_sync_token_regenerate
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

# tests/ 配下からプロジェクトルートを import パスへ追加
PROJECT_ROOT = Path(__file__).resolve().parent.parent
import sys  # noqa: E402

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import local_sync_server  # noqa: E402


class TestSyncTokenRegenerate(unittest.TestCase):
    """SyncTokenManager.regenerate() の振る舞いテスト (テンポラリトークンファイル)。"""

    def setUp(self) -> None:
        """テンポラリディレクトリとトークンファイル差し替えを準備する。"""
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.token_file = Path(self._tmp.name) / ".sync_token"
        patcher = mock.patch.object(local_sync_server, "TOKEN_FILE", self.token_file)
        patcher.start()
        self.addCleanup(patcher.stop)
        # インスタンス生成時に新規トークンがテンポラリファイルへ書き込まれる
        self.manager = local_sync_server.SyncTokenManager()

    def test_regenerate_changes_token(self) -> None:
        """regenerate() を呼ぶとトークンが必ず変化する。"""
        old_token = self.manager.token
        new_token = self.manager.regenerate()
        self.assertNotEqual(old_token, new_token)

    def test_regenerate_persists_new_token(self) -> None:
        """再生成したトークンが .sync_token ファイルへ永続化される。"""
        new_token = self.manager.regenerate()
        self.assertEqual(self.token_file.read_text(encoding="utf-8"), new_token)

    def test_regenerate_invalidates_old_token(self) -> None:
        """旧トークンは401相当 (verify False) となり、新トークンのみ有効になる。"""
        old_token = self.manager.token
        new_token = self.manager.regenerate()
        self.assertFalse(self.manager.verify(old_token))
        self.assertTrue(self.manager.verify(new_token))

    def test_regenerated_token_is_256bit_hex(self) -> None:
        """再生成トークンは従来設計と同一の 64文字 (256bit) hex である。"""
        new_token = self.manager.regenerate()
        self.assertEqual(len(new_token), 64)
        int(new_token, 16)  # hex としてパースできなければ ValueError

    def test_regenerate_multiple_times_each_time_changes(self) -> None:
        """連続再生成でも毎回異なるトークンが生成される (冪等性の確認)。"""
        first = self.manager.regenerate()
        second = self.manager.regenerate()
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main(verbosity=2)
