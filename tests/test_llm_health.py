#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - LLM プロバイダ健康診断の単体テスト (tests/test_llm_health.py)

tools/check_llm_health.py のプローブ構築 (ネットワーク非接触の純粋関数) を検証する。
2026-09 の OpenCode 仕様変更 (x-opencode-session 必須化) のように、API提供側の
仕様変更を「アプリが沈黙してから」ではなく「健康診断で」早期検知できることを目的とする。

TDD: build_chat_probe() が無い状態では Red で落ちる。
"""

import sys
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from check_llm_health import build_chat_probe  # noqa: E402


class TestBuildChatProbe(unittest.TestCase):
    """プロバイダ別プローブ (URL・ヘッダー・ペイロード) 構築の契約検証"""

    def test_opencode_probe_has_session_header_and_bearer(self) -> None:
        """OpenCode: Bearer 認証 ＋ x-opencode-session ヘッダー必須 (2026-09 仕様)"""
        probe = build_chat_probe(
            "opencode", "https://opencode.ai/zen/go/v1", "sk-test-key", "deepseek-v4.1-flash"
        )

        self.assertTrue(probe.url.endswith("/chat/completions"))
        self.assertEqual(probe.headers["Authorization"], "Bearer sk-test-key")
        self.assertIn("x-opencode-session", probe.headers)
        self.assertTrue(probe.headers["x-opencode-session"])
        self.assertEqual(probe.payload["max_tokens"], 1)

    def test_openai_probe_is_standard_bearer_without_session(self) -> None:
        """標準 OpenAI 互換 (openai) は Bearer のみで独自ヘッダーを付けないこと"""
        probe = build_chat_probe("openai", "https://api.openai.com/v1", "sk-oai", "gpt-x")

        self.assertEqual(probe.headers["Authorization"], "Bearer sk-oai")
        self.assertNotIn("x-opencode-session", probe.headers)

    def test_anthropic_probe_uses_messages_endpoint(self) -> None:
        """Anthropic: x-api-key ＋ anthropic-version ヘッダーで /v1/messages を叩くこと"""
        probe = build_chat_probe("anthropic", "https://api.anthropic.com", "ak-ant", "claude-x")

        self.assertTrue(probe.url.endswith("/v1/messages"))
        self.assertEqual(probe.headers.get("x-api-key"), "ak-ant")
        self.assertEqual(probe.headers.get("anthropic-version"), "2023-06-23")

    def test_unknown_provider_raises_value_error(self) -> None:
        """未知のプロバイダは ValueError (Fail-Fast) であること"""
        with self.assertRaises(ValueError):
            build_chat_probe("unknown_provider", "https://example.com", "key", "model")


if __name__ == "__main__":
    unittest.main(verbosity=2)
