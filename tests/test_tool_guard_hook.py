"""Unit tests for Antigravity Tool Guard Hook (tool_guard_hook.py)"""

import unittest
import sys
from pathlib import Path

# Hookモジュールおよびリポジトリルートをインポートパスに追加
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

hook_dir = Path("C:/Users/bonob/.gemini/tools/jev_router")
if str(hook_dir) not in sys.path:
    sys.path.insert(0, str(hook_dir))
import tool_guard_hook as tgh


class TestToolGuardHook(unittest.TestCase):
    def test_japanese_search_allowed(self):
        """日本語を含む文字列検索は許可されること (UI文言・ドキュメント検索等)"""
        dec, _ = tgh.evaluate_grep_query("新しい端末からの接続要求")
        self.assertEqual(dec, "allow")

    def test_config_and_path_allowed(self):
        """設定ファイルパスやURLを含む検索は許可されること"""
        dec1, _ = tgh.evaluate_grep_query(".sync_token")
        self.assertEqual(dec1, "allow")

        dec2, _ = tgh.evaluate_grep_query("/api/auth/token")
        self.assertEqual(dec2, "allow")

    def test_long_error_message_allowed(self):
        """自然言語のエラーメッセージ検索は許可されること"""
        dec, _ = tgh.evaluate_grep_query("Too many failed authentication attempts")
        self.assertEqual(dec, "allow")

    def test_identifier_search_denied(self):
        """単一の識別子（関数名・クラス名）はコード構造探索と判定されて遮断されること"""
        dec1, reason1 = tgh.evaluate_grep_query("ask_device_approval_gui")
        self.assertEqual(dec1, "deny")
        self.assertIn("codebase-memory-mcp", reason1)

        dec2, _ = tgh.evaluate_grep_query("DeskPetSyncHandler")
        self.assertEqual(dec2, "deny")

    def test_def_class_syntax_denied(self):
        """def や class 構文の検索は遮断されること"""
        dec, reason = tgh.evaluate_grep_query("def issue_device_token")
        self.assertEqual(dec, "deny")
        self.assertIn("codebase-memory-mcp", reason)

    def test_prohibited_command_denied(self):
        """禁止されているコマンド実行が遮断されること"""
        dec1, _ = tgh.evaluate_run_command("python main.py")
        self.assertEqual(dec1, "deny")

        dec2, _ = tgh.evaluate_run_command("git reset --hard HEAD~1")
        self.assertEqual(dec2, "deny")

    def test_safe_command_allowed(self):
        """通常の安全なコマンド実行が許可されること"""
        dec, _ = tgh.evaluate_run_command("pytest tests/test_device_registry.py")
        self.assertEqual(dec, "allow")

    def test_notify_waiting_payload_and_debounce(self):
        """notify_waiting が正しいペイロードで /api/agent/ask_input を呼び、同一コマンドをクールダウン抑止すること"""
        from unittest import mock
        import time

        with mock.patch("tool_guard_hook._load_state", return_value={}), \
             mock.patch("tool_guard_hook._save_state") as mock_save, \
             mock.patch("agent_bridge_client._post_to_hub") as mock_post:
            
            mock_post.return_value = {"status": "queued", "request_id": "req_123"}

            # 1回目の呼び出し: 正常に送信されること
            tgh.notify_waiting("git status", reason="承認待ち")

            self.assertTrue(mock_post.called)
            args, kwargs = mock_post.call_args
            self.assertEqual(args[0], "/api/agent/ask_input")
            payload = args[1]
            self.assertEqual(payload["agent_name"], "Antigravity")
            self.assertEqual(payload["wait_decision"], False)
            self.assertEqual(payload["choices"], [])
            self.assertEqual(payload["timeout"], 5)
            self.assertIn("git status", payload["details"])
            self.assertTrue(mock_save.called)

        # 2回目の呼び出し（直後）: クールダウンにより抑止されること
        digest = tgh._calc_command_digest("git status")
        with mock.patch("tool_guard_hook._load_state", return_value={digest: time.time()}), \
             mock.patch("agent_bridge_client._post_to_hub") as mock_post2:
            
            tgh.notify_waiting("git status", reason="承認待ち")
            self.assertFalse(mock_post2.called, "クールダウン期間中は通知が抑止されるべきです")

    def test_notify_waiting_fail_safe(self):
        """通信例外が発生しても通知処理がクラッシュせず、エージェントの動作を止めないこと"""
        from unittest import mock

        with mock.patch("tool_guard_hook._load_state", return_value={}), \
             mock.patch("tool_guard_hook._save_state"), \
             mock.patch("agent_bridge_client._post_to_hub", side_effect=Exception("Server Offline")):
            try:
                tgh.notify_waiting("pytest tests/", reason="安全テスト")
            except Exception as e:
                self.fail(f"notify_waiting raised an exception: {e}")

    def test_is_external_workspace_path(self):
        """ワークスペース外のパス判定が正しく行われること"""
        # 相対パスは内部判定
        self.assertFalse(tgh.is_external_workspace_path("tests/test_tool_guard_hook.py"))
        self.assertFalse(tgh.is_external_workspace_path(""))
        
        # ワークスペース配下の絶対パスは内部判定
        workspace_file = str(tgh.HISHO_ROOT / "main.py")
        self.assertFalse(tgh.is_external_workspace_path(workspace_file))

        # ワークスペース外（~/.gemini や C:\Windows 等）は外部判定
        self.assertTrue(tgh.is_external_workspace_path("C:/Users/bonob/.gemini/config/hooks.json"))
        self.assertTrue(tgh.is_external_workspace_path("C:/Windows/System32"))

    def test_external_path_tool_triggers_notify(self):
        """外部パスへのアクセスツール呼び出し時に notify_waiting がトリガーされること"""
        from unittest import mock

        with mock.patch("tool_guard_hook.notify_waiting") as mock_notify, \
             mock.patch("sys.stdin") as mock_stdin:
            import io
            import json
            
            payload = {
                "toolCall": {
                    "name": "list_dir",
                    "args": {
                        "DirectoryPath": "C:/Users/bonob/.config"
                    }
                }
            }
            mock_stdin.read.return_value = json.dumps(payload)

            with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                tgh.main()
                output = json.loads(mock_stdout.getvalue())
                self.assertEqual(output["decision"], "allow")
                self.assertTrue(mock_notify.called)
                args, _ = mock_notify.call_args
                self.assertIn("list_dir", args[0])
                self.assertIn("C:/Users/bonob/.config", args[0])


if __name__ == "__main__":
    unittest.main()

