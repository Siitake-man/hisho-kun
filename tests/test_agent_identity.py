#!/usr/bin/env python3
"""
ネオ秘書くん - agent_identity (エージェント自動識別) 単体テスト
"""
import os
import unittest
from unittest.mock import patch

import agent_identity


class TestAgentIdentity(unittest.TestCase):
    """エージェント自動識別の優先順位・環境シグネチャ・フォールバック契約を検証する。

    明示指定 > 環境変数上書き > 親プロセス/環境シグネチャ > デフォルト名、
    の優先順位が崩れないこと（コード探索と重複しないこと）を守る。
    """

    def test_explicit_name_wins(self):
        """明示指定されたエージェント名は環境検出より優先される"""
        with patch.dict(os.environ, {"HISHO_AGENT_NAME": "Claude Code", "CLAUDECODE": "1"}, clear=True):
            self.assertEqual(agent_identity.resolve_agent_name("Cline"), "Cline")

    def test_env_override_key(self):
        """HISHO_AGENT_NAME 環境変数による明示上書きが機能する"""
        with patch.dict(os.environ, {"HISHO_AGENT_NAME": "Antigravity"}, clear=True):
            with patch.object(agent_identity, "_detect_from_parent_process", return_value=""):
                self.assertEqual(agent_identity.detect_agent_name(), "Antigravity")
                self.assertEqual(agent_identity.resolve_agent_name(), "Antigravity")

    def test_claude_code_signature(self):
        """CLAUDECODE 環境変数から Claude Code を検出する"""
        with patch.dict(os.environ, {"CLAUDECODE": "1"}, clear=True):
            with patch.object(agent_identity, "_detect_from_parent_process", return_value=""):
                self.assertEqual(agent_identity.detect_agent_name(), "Claude Code")

    def test_cursor_signature(self):
        """CURSOR_TRACE_ID 環境変数から Cursor を検出する"""
        with patch.dict(os.environ, {"CURSOR_TRACE_ID": "abc123"}, clear=True):
            with patch.object(agent_identity, "_detect_from_parent_process", return_value=""):
                self.assertEqual(agent_identity.detect_agent_name(), "Cursor")

    def test_codex_signature(self):
        """CODEX_SANDBOX 環境変数から Codex を検出する"""
        with patch.dict(os.environ, {"CODEX_SANDBOX": "1"}, clear=True):
            with patch.object(agent_identity, "_detect_from_parent_process", return_value=""):
                self.assertEqual(agent_identity.detect_agent_name(), "Codex")

    def test_fallback_default(self):
        """何も検出できない場合はデフォルト名へフォールバックする"""
        with patch.dict(os.environ, {"PATH": "C:\\"}, clear=True):
            with patch.object(agent_identity, "_detect_from_parent_process", return_value=""):
                self.assertEqual(agent_identity.detect_agent_name(), agent_identity.DEFAULT_AGENT_NAME)

    def test_explicit_empty_string_triggers_detection(self):
        """空文字指定は未指定扱いとなり自動検出に委譲される"""
        with patch.dict(os.environ, {"HISHO_AGENT_NAME": "Gemini CLI"}, clear=True):
            self.assertEqual(agent_identity.resolve_agent_name(""), "Gemini CLI")
            self.assertEqual(agent_identity.resolve_agent_name("   "), "Gemini CLI")


if __name__ == "__main__":
    unittest.main()