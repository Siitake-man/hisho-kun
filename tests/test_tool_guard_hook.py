"""Unit tests for Antigravity Tool Guard Hook (tool_guard_hook.py)"""

import os
import unittest
import sys
from pathlib import Path

# Hookモジュールおよびリポジトリルートをインポートパスに追加
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# tool_guard_hook.py は本リポジトリ外（利用者の ~/.gemini/tools/jev_router）に置かれるグローバル資産。
# 配置先は環境変数 JEV_ROUTER_DIR で上書きできる（個人環境の絶対パスは埋め込まない）。
hook_dir = Path(os.environ.get("JEV_ROUTER_DIR") or (Path.home() / ".gemini" / "tools" / "jev_router"))
if str(hook_dir) not in sys.path:
    sys.path.insert(0, str(hook_dir))
try:
    import tool_guard_hook as tgh
except ImportError:
    tgh = None


#: ワークスペース外パスの例（実行ユーザーのホーム配下。個人環境の絶対パスは埋め込まない）
HOME_POSIX = Path.home().as_posix()


class TestToolGuardHook(unittest.TestCase):
    def setUp(self):
        if tgh is None:
            self.skipTest(
                f"tool_guard_hook はリポジトリ外のグローバル資産のため、未配置の環境ではスキップ ({hook_dir})"
            )
    """Tool Guard Hook の allow/deny 判定と承認通知・フェイルセーフ契約を検証する。

    日本語文言検索は許可し、識別子・禁止コマンドは遮断、通信例外時は
    エージェント動作を止めないこと（二層防御のソフト層）を守る。
    """

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
             mock.patch("urllib.request.urlopen", side_effect=OSError("test isolation: 実ハブへ送らない")), \
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
             mock.patch("urllib.request.urlopen", side_effect=OSError("test isolation: 実ハブへ送らない")), \
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
        self.assertTrue(tgh.is_external_workspace_path(f"{HOME_POSIX}/.gemini/config/hooks.json"))
        self.assertTrue(tgh.is_external_workspace_path("C:/Windows/System32"))

    def test_external_path_write_tool_triggers_notify(self):
        """ワークスペース外の書き込み系ツールで notify_waiting がトリガーされること

        2026-09-26 ボス承認方針: 「書き込み系と危険操作のみ通知」。
        読み取り系 (view_file / list_dir) は自動実行されるため通知しない。
        """
        from unittest import mock

        with mock.patch("tool_guard_hook.notify_waiting") as mock_notify, \
             mock.patch("sys.stdin") as mock_stdin:
            import io
            import json

            payload = {
                "toolCall": {
                    "name": "write_to_file",
                    "args": {
                        "TargetFile": f"{HOME_POSIX}/.config/settings.json"
                    }
                }
            }
            mock_stdin.read.return_value = json.dumps(payload)

            with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                tgh.main()
                output = json.loads(mock_stdout.getvalue())
                self.assertEqual(output["decision"], "allow")
                self.assertTrue(mock_notify.called, "ワークスペース外書き込みは通知され아야 합니다")
                args, _ = mock_notify.call_args
                self.assertIn("write_to_file", args[0])
                self.assertIn(f"{HOME_POSIX}/.config", args[0])

    def test_external_path_read_tool_does_not_notify(self):
        """ワークスペース外の読み取り系ツールでは通知しないこと（通知スパム防止）

        2026-09-26 実測: 別ファイルを 1 個読むごとに 1 件の通知が飛び、
        承認ダイアログも出ないままスマホが連呼されていた（待ちぼうけではなくノイズ）。
        """
        from unittest import mock

        for tool_name, arg_key in (
            ("view_file", "AbsolutePath"),
            ("list_dir", "DirectoryPath"),
        ):
            with self.subTest(tool=tool_name):
                with mock.patch("tool_guard_hook.notify_waiting") as mock_notify, \
                     mock.patch("sys.stdin") as mock_stdin:
                    import io
                    import json

                    payload = {
                        "toolCall": {
                            "name": tool_name,
                            "args": {arg_key: f"{HOME_POSIX}/.config"}
                        }
                    }
                    mock_stdin.read.return_value = json.dumps(payload)

                    with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                        tgh.main()
                        output = json.loads(mock_stdout.getvalue())
                        self.assertEqual(output["decision"], "allow")
                        self.assertFalse(
                            mock_notify.called,
                            f"読み取り系 {tool_name} は通知対象外（ボス承認 2026-09-26）",
                        )


if __name__ == "__main__":
    unittest.main()

