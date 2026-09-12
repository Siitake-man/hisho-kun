#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - OpenCode セッションヘッダーの単体テスト (tests/test_opencode_session_header.py)

2026-09 の OpenCode Zen (Console Go ルーティング) 仕様変更により、チャットリクエストは
``x-opencode-session`` ヘッダー必須となった (欠落時は 400 MissingSessionID)。
LLMFactory.create_model() が OPENCODE プロバイダ向けに本ヘッダーを注入することを凍結する。

TDD: 実装 (llm_factory.create_model の default_headers 注入) が無い状態では Red で落ちる。
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from llm_factory import LLMFactory, LLMProvider


class TestOpencodeSessionHeader(unittest.TestCase):
    """OPENCODE プロバイダの x-opencode-session ヘッダー注入契約"""

    def setUp(self) -> None:
        env_patcher = mock.patch.dict(
            os.environ, {"OPENCODE_API_KEY": "sk-test-dummy"}, clear=False
        )
        env_patcher.start()
        self.addCleanup(env_patcher.stop)

    def _create_with_patched_chat(self, provider: LLMProvider):
        """ChatOpenAI をモックして create_model() の生成引数を検査する。"""
        factory = LLMFactory(default_provider=provider.value)
        with mock.patch("langchain_openai.ChatOpenAI") as fake_cls:
            factory.create_model(temperature=0.3)
        return fake_cls

    def test_opencode_injects_session_header(self) -> None:
        """OPENCODE 向け生成時に x-opencode-session ヘッダーが注入されること"""
        fake_cls = self._create_with_patched_chat(LLMProvider.OPENCODE)
        kwargs = fake_cls.call_args.kwargs
        headers = kwargs.get("default_headers") or {}
        self.assertIn("x-opencode-session", headers)
        self.assertTrue(headers["x-opencode-session"])

    def test_opencode_session_is_stable_within_process(self) -> None:
        """セッションIDは同一プロセス内で安定していること (ルーティング親和性)"""
        fake_cls1 = self._create_with_patched_chat(LLMProvider.OPENCODE)
        fake_cls2 = self._create_with_patched_chat(LLMProvider.OPENCODE)
        headers1 = fake_cls1.call_args.kwargs.get("default_headers") or {}
        headers2 = fake_cls2.call_args.kwargs.get("default_headers") or {}
        self.assertEqual(
            headers1.get("x-opencode-session"), headers2.get("x-opencode-session")
        )

    def test_env_override_for_session_id(self) -> None:
        """.env の OPENCODE_SESSION_ID でセッションIDを上書きできること"""
        with mock.patch.dict(
            os.environ, {"OPENCODE_SESSION_ID": "my-fixed-session"}, clear=False
        ):
            fake_cls = self._create_with_patched_chat(LLMProvider.OPENCODE)
        headers = fake_cls.call_args.kwargs.get("default_headers") or {}
        self.assertEqual(headers.get("x-opencode-session"), "my-fixed-session")

    def test_other_providers_do_not_inject_header(self) -> None:
        """OPENCODE 以外の OpenAI 互換プロバイダ (例: OPENAI) はヘッダー未注入であること"""
        env_patcher = mock.patch.dict(
            os.environ, {"OPENAI_API_KEY": "sk-other-dummy"}, clear=False
        )
        env_patcher.start()
        self.addCleanup(env_patcher.stop)

        fake_cls = self._create_with_patched_chat(LLMProvider.OPENAI)
        kwargs = fake_cls.call_args.kwargs
        headers = kwargs.get("default_headers")
        if headers is not None:
            self.assertNotIn("x-opencode-session", headers)


if __name__ == "__main__":
    unittest.main(verbosity=2)
