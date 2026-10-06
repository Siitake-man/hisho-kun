#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - 公開前ハードニングの単体テスト (tests/test_review_hardening.py)

外部レビュー (2026-09-12) で検出された以下のコード課題を凍結する:
1. Claude (Anthropic) 選択時、langchain-anthropic 未導入で OpenAI 互換クライアントを
   Anthropic の URL へ向ける「100% 失敗するフォールバック」 → 明確なヒント付き
   ImportError へ置換。

TDD: 実装前は Red で落ちる。
"""

import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app_paths
from llm_factory import LLMFactory, LLMProvider


class TestClaudeFallback(unittest.TestCase):
    """langchain-anthropic 未導入時の Claude 選択は明確なエラーで縮退すること"""

    def setUp(self) -> None:
        env_patcher = mock.patch.dict(
            os.environ, {"ANTHROPIC_API_KEY": "sk-ant-dummy"}, clear=False
        )
        env_patcher.start()
        self.addCleanup(env_patcher.stop)

    def test_missing_langchain_anthropic_raises_actionable_error(self) -> None:
        """未導入時は pip install ヒントを含む ImportError を送出すること"""
        factory = LLMFactory(default_provider=LLMProvider.CLAUDE.value)
        with mock.patch.dict(sys.modules, {"langchain_anthropic": None}):
            with self.assertRaises(ImportError) as ctx:
                factory.create_model(temperature=0.3)
        self.assertIn("langchain-anthropic", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
