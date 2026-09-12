#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - 思考制御 (reasoning_effort) 注入の単体テスト (tests/test_reasoning_effort.py)

応答速度スプリント (2026-09-12): DeepSeek 系推論モデルが毎パスで思考トークンを
燃やし、応答が 20-30 秒化していた。OpenCode 向けに OpenAI 標準の
``reasoning_effort`` (実機 200 応答確認済み) を extra_body で注入し、
.env の ``OPENCODE_REASONING_EFFORT`` で上書き・空で無効化できる契約を凍結する。
併せて、推論モデル前提にタイムアウトが引き上げられていることを凍結する。

TDD: 実装が無い状態では Red で落ちる。
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from llm_factory import LLM_REQUEST_TIMEOUT_SEC, LLMFactory, LLMProvider  # noqa: E402


class TestReasoningEffortControl(unittest.TestCase):
    """OPENCODE 思考制御パラメータ注入の契約検証"""

    def setUp(self) -> None:
        env_patcher = mock.patch.dict(
            os.environ, {"OPENCODE_API_KEY": "sk-test-dummy"}, clear=False
        )
        env_patcher.start()
        self.addCleanup(env_patcher.stop)

    def _create(self) -> mock.Mock:
        """ChatOpenAI をモックして create_model() の生成引数を返す。"""
        factory = LLMFactory(default_provider=LLMProvider.OPENCODE.value)
        with mock.patch("langchain_openai.ChatOpenAI") as fake_cls:
            factory.create_model(temperature=0.3)
        return fake_cls

    def test_default_injects_reasoning_effort_low(self) -> None:
        """既定 (env 未設定) は reasoning_effort=low が注入されること"""
        kwargs = self._create().call_args.kwargs
        self.assertEqual(kwargs.get("extra_body"), {"reasoning_effort": "low"})

    def test_env_override_reasoning_effort(self) -> None:
        """.env の OPENCODE_REASONING_EFFORT で値を上書きできること"""
        with mock.patch.dict(
            os.environ, {"OPENCODE_REASONING_EFFORT": "minimal"}, clear=False
        ):
            kwargs = self._create().call_args.kwargs
        self.assertEqual(kwargs.get("extra_body"), {"reasoning_effort": "minimal"})

    def test_env_empty_disables_extra_body(self) -> None:
        """OPENCODE_REASONING_EFFORT="" で extra_body 無し (無効化) になること"""
        with mock.patch.dict(
            os.environ, {"OPENCODE_REASONING_EFFORT": ""}, clear=False
        ):
            kwargs = self._create().call_args.kwargs
        self.assertIsNone(kwargs.get("extra_body"))

    def test_other_provider_has_no_extra_body(self) -> None:
        """OPENCODE 以外 (例: OPENAI) は extra_body を注入しないこと"""
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-oai"}, clear=False):
            factory = LLMFactory(default_provider=LLMProvider.OPENAI.value)
            with mock.patch("langchain_openai.ChatOpenAI") as fake_cls:
                factory.create_model(temperature=0.3)
        self.assertIsNone(fake_cls.call_args.kwargs.get("extra_body"))

    def test_timeout_raised_for_reasoning_models(self) -> None:
        """推論モデル前提にタイムアウトが 60 秒へ引き上げられていること (15秒×リトライの増幅防止)"""
        self.assertEqual(LLM_REQUEST_TIMEOUT_SEC, 60.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
