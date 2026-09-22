#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - 起動時LLMモデル同期の設定済みプロバイダ限定テスト (tests/test_llm_factory_sync_gating.py)

背景 (手帳 TODO ID 31 / ロードマップ §13.19 第5項):
  起動時の sync_all_discovered_models() は LLMProvider 全10プロバイダを無条件巡回し、
  APIキー未設定 (openai/groq/openrouter) やローカルサーバー未起動 (ollama/lm_studio/
  custom_openai) の6プロバイダで確定失敗のネットワーク試行＋ERRORログ＋フォールバック
  ロードが毎回発生していた (実測約4.6秒)。

検証項目:
  1. クラウド系 (api_key_env あり) は is_provider_configured()==False なら巡回スキップ
  2. ローカルサーバー系 (ollama/lm_studio) は TCP プローブ成功時のみ巡回
  3. 現行選択中プロバイダと LOCAL_GGUF (ローカルスキャン) は常に巡回
  4. sync_all_discovered_models 全体で、対象外プロバイダの fetch が呼ばれないこと

Gotcha: _compute_provider_configured は最新 .env の反映のため load_dotenv(override=True)
を呼ぶため、検証時は llm_factory.load_dotenv も遮断して実 .env の影響を断つ。
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from llm_factory import LLMFactory, LLMProvider

# 実 .env の影響を遮断するパッチ (生成・判定の両方で使う)
LOAD_DOTENV_NOP = patch("llm_factory.load_dotenv", lambda **kwargs: None)


def _make_factory() -> LLMFactory:
    """実 .env の影響を遮断した検証用 LLMFactory を生成する。

    Returns:
        現行プロバイダが OPENCODE の検証用インスタンス。
    """
    with LOAD_DOTENV_NOP, patch.dict("os.environ", {}, clear=True):
        return LLMFactory(default_provider="opencode")


class TestShouldProbeProvider(unittest.TestCase):
    """should_probe_provider のゲート判定 (設定済みプロバイダ限定) を検証する。"""

    def test_unconfigured_cloud_providers_are_skipped(self) -> None:
        """APIキー未設定のクラウドプロバイダが巡回対象外となることを保証する。"""
        factory = _make_factory()
        with LOAD_DOTENV_NOP, patch.dict("os.environ", {}, clear=True):
            self.assertFalse(factory.should_probe_provider(LLMProvider.OPENAI))
            self.assertFalse(factory.should_probe_provider(LLMProvider.GROQ))
            self.assertFalse(factory.should_probe_provider(LLMProvider.OPENROUTER))
            self.assertFalse(factory.should_probe_provider(LLMProvider.GEMINI))

    def test_configured_cloud_provider_is_probed(self) -> None:
        """APIキー設定済みのクラウドプロバイダが巡回対象となることを保証する。"""
        factory = _make_factory()
        with LOAD_DOTENV_NOP, patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}, clear=True):
            self.assertTrue(factory.should_probe_provider(LLMProvider.OPENAI))

    def test_current_provider_is_always_probed(self) -> None:
        """現行選択中プロバイダは未設定でも常に巡回対象となることを保証する。"""
        factory = _make_factory()
        with LOAD_DOTENV_NOP, patch.dict("os.environ", {}, clear=True):
            self.assertTrue(factory.should_probe_provider(LLMProvider.OPENCODE))

    def test_local_gguf_is_always_probed(self) -> None:
        """LOCAL_GGUF (ローカルディレクトリスキャン・通信無し) は常に巡回対象となることを保証する。"""
        factory = _make_factory()
        with LOAD_DOTENV_NOP, patch.dict("os.environ", {}, clear=True):
            self.assertTrue(factory.should_probe_provider(LLMProvider.LOCAL_GGUF))

    def test_local_server_refused_is_skipped(self) -> None:
        """TCPプローブが接続拒否のローカルサーバーが巡回対象外となることを保証する。"""
        factory = _make_factory()
        with LOAD_DOTENV_NOP, patch.dict("os.environ", {}, clear=True), \
             patch("socket.create_connection", side_effect=OSError("connection refused")):
            self.assertFalse(factory.should_probe_provider(LLMProvider.OLLAMA))
            self.assertFalse(factory.should_probe_provider(LLMProvider.LM_STUDIO))

    def test_local_server_running_is_probed(self) -> None:
        """TCPプローブに成功するローカルサーバーが巡回対象となることを保証する。"""
        factory = _make_factory()
        with LOAD_DOTENV_NOP, patch.dict("os.environ", {}, clear=True), \
             patch("socket.create_connection", return_value=MagicMock()):
            self.assertTrue(factory.should_probe_provider(LLMProvider.OLLAMA))
            self.assertTrue(factory.should_probe_provider(LLMProvider.LM_STUDIO))


class TestSyncAllDiscoveredModelsGating(unittest.TestCase):
    """sync_all_discovered_models 全体での巡回対象限定を検証する。"""

    def test_sync_calls_fetch_only_for_eligible_providers(self) -> None:
        """未設定・未起動プロバイダの fetch_available_models が呼ばれないことを保証する。"""
        factory = _make_factory()
        with LOAD_DOTENV_NOP, patch.dict("os.environ", {}, clear=True), \
             patch("socket.create_connection", side_effect=OSError("connection refused")), \
             patch.object(factory, "fetch_available_models", return_value=[]) as mock_fetch:
            results = factory.sync_all_discovered_models(background=False)

        fetched = {call.args[0] for call in mock_fetch.call_args_list}
        self.assertEqual(fetched, {"opencode", "local_gguf"})
        self.assertEqual(results["openai"], "skipped: 未設定・未起動")
        self.assertEqual(results["ollama"], "skipped: 未設定・未起動")

    def test_sync_probes_running_local_server(self) -> None:
        """TCPプローブ成功時のローカルサーバーが巡回されることを保証する。"""
        factory = _make_factory()
        with LOAD_DOTENV_NOP, patch.dict("os.environ", {}, clear=True), \
             patch("socket.create_connection", return_value=MagicMock()), \
             patch.object(factory, "fetch_available_models", return_value=[]) as mock_fetch:
            factory.sync_all_discovered_models(background=False)

        fetched = {call.args[0] for call in mock_fetch.call_args_list}
        self.assertIn("ollama", fetched)
        self.assertIn("lm_studio", fetched)
        self.assertNotIn("openai", fetched)


if __name__ == "__main__":
    unittest.main()
