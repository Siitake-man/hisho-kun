#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - 公開前ハードニングの単体テスト (tests/test_review_hardening.py)

外部レビュー (2026-09-12) で検出された以下のコード課題を凍結する:
1. easter_egg_engine の STATE_PATH が exe (PyInstaller) 環境で書込不能な
   ``Path(__file__).parent`` を参照している → ``app_paths.get_app_root()`` に統一。
2. Claude (Anthropic) 選択時、langchain-anthropic 未導入で OpenAI 互換クライアントを
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
import easter_egg_engine
from llm_factory import LLMFactory, LLMProvider


class TestEasterEggStatePath(unittest.TestCase):
    """easter_egg_engine の状態ファイルパスがアプリ書き込みルート基準であること"""

    def test_state_path_follows_app_root(self) -> None:
        """app_paths.get_app_root() の変更に STATE_PATH が追従すること (exe 書込対応)"""
        frozen_root = Path("X:/frozen_app_root")
        try:
            with mock.patch.object(app_paths, "get_app_root", return_value=frozen_root):
                importlib.reload(easter_egg_engine)
                self.assertEqual(
                    easter_egg_engine.STATE_PATH,
                    frozen_root / "easter_egg_state.json",
                    "STATE_PATH は app_paths.get_app_root() 基準で解決されること",
                )
        finally:
            # 元のパス解決へ戻す (他テストへの副作用防止)
            importlib.reload(easter_egg_engine)

    def test_state_path_basename_is_state_file(self) -> None:
        """STATE_PATH のファイル名が easter_egg_state.json であること"""
        self.assertEqual(easter_egg_engine.STATE_PATH.name, "easter_egg_state.json")


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
