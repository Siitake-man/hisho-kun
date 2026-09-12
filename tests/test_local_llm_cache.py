#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - 内包ローカルLLM メモリ常駐キャッシュの単体テスト (tests/test_local_llm_cache.py)

P1-C (LM Studio 同等の爆速常駐化): 会話ごとに create_model() が呼ばれても、
同一 GGUF パスに対する Llama テンソル初期化 (ディスク再ロード) は 1 度しか
走らないこと / 別モデル切替時に旧常駐分が解放されること /
clear_local_model_cache() でキャッシュが全解放されることを検証する。

TDD: 現行実装 (会話ごとに再ロード) は本テストを Red で落とす。
Llama は llama_cpp モジュール属性をパッチしてディスクモデル不要で検証する。
llama_cpp_python は Windows ビルドが重大なため CI では除外インストールとし、
未導入環境では本テストクラス全体を自動スキップする (ローカル実行は従来どおり実施)。
"""

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from llm_factory import LLMFactory

# キャッシュロジックの検証にはテンソル不要のため、実パッケージ (jinja2 チェーン込みで
# import が重く、環境によってはテストランナーが固まる) を読まず、最小スタブ
# (Llama 属性のみ) を sys.modules に注入する。mock.patch("llama_cpp.Llama") は
# import 可能なモジュールのみを要求するため、スタブで十分かつ決定論的。
# ※ 実テンソルのロード/解放は実機動作確認で検証する (テストの関心事ではない)。
_llama_stub = types.ModuleType("llama_cpp")
_llama_stub.Llama = object  # type: ignore[attr-defined]
sys.modules.setdefault("llama_cpp", _llama_stub)  # type: ignore[assignment]
llama_cpp = _llama_stub  # type: ignore[assignment]


class TestLocalLlmCache(unittest.TestCase):
    """LLMFactory の内包ローカル GGUF 常駐キャッシュ契約検証"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.models_dir = Path(self._tmp.name)
        # create_model() のモデル存在検査を通すためのダミー GGUF
        (self.models_dir / "dummy_a.gguf").write_bytes(b"dummy gguf a")
        (self.models_dir / "dummy_b.gguf").write_bytes(b"dummy gguf b")

        # 環境変数を固定して GPU/スレッド設定の検証を決定論化
        env_patcher = mock.patch.dict(
            os.environ, {"HISHO_GPU_LAYERS": "-1", "HISHO_CPU_THREADS": "1"}, clear=False
        )
        env_patcher.start()
        self.addCleanup(env_patcher.stop)

        # MODELS_DIR をテスト用一時ディレクトリへ差し替え (実 models/ を絶対に触らない)
        models_patcher = mock.patch.object(LLMFactory, "MODELS_DIR", self.models_dir)
        models_patcher.start()
        self.addCleanup(models_patcher.stop)

        self.factory = LLMFactory(default_provider="local_gguf")
        self.factory._current_model = "dummy_a.gguf"

    def test_same_model_reuses_cached_llama_instance(self) -> None:
        """同一モデルパスで 2 回 create_model() しても Llama 初期化は 1 回のみであること"""
        fake_llama_cls = mock.MagicMock(name="FakeLlama")
        with mock.patch("llama_cpp.Llama", fake_llama_cls):
            model1 = self.factory.create_model(temperature=0.3)
            model2 = self.factory.create_model(temperature=0.8)

        self.assertEqual(fake_llama_cls.call_count, 1)
        self.assertIs(model1._llm, model2._llm)  # メモリ常駐インスタンスの共有
        self.assertEqual(model1._temperature, 0.3)
        self.assertEqual(model2._temperature, 0.8)

        kwargs = fake_llama_cls.call_args.kwargs
        self.assertEqual(kwargs.get("n_gpu_layers"), -1)  # GPU 自動オフロード
        self.assertEqual(kwargs.get("n_threads"), 1)      # HISHO_CPU_THREADS=1 が反映

    def test_switch_model_releases_old_instance(self) -> None:
        """別モデルへ切替時、旧常駐分を解放して新モデルを 1 度だけロードすること"""
        fake_llama_cls = mock.MagicMock(name="FakeLlama")
        with mock.patch("llama_cpp.Llama", fake_llama_cls):
            self.factory.create_model()
            first_path = str(self.models_dir / "dummy_a.gguf")
            self.assertEqual(list(self.factory._local_llm_cache.keys()), [first_path])

            self.factory._current_model = "dummy_b.gguf"
            self.factory.create_model()

            second_path = str(self.models_dir / "dummy_b.gguf")
            self.assertEqual(list(self.factory._local_llm_cache.keys()), [second_path])
            self.assertEqual(fake_llama_cls.call_count, 2)

    def test_clear_cache_forces_reload(self) -> None:
        """clear_local_model_cache() 後は次回 create_model() で再ロードされること"""
        fake_llama_cls = mock.MagicMock(name="FakeLlama")
        with mock.patch("llama_cpp.Llama", fake_llama_cls):
            self.factory.create_model()
            self.assertEqual(fake_llama_cls.call_count, 1)

            self.factory.clear_local_model_cache()
            self.assertEqual(self.factory._local_llm_cache, {})

            self.factory.create_model()
            self.assertEqual(fake_llama_cls.call_count, 2)


if __name__ == "__main__":
    unittest.main()