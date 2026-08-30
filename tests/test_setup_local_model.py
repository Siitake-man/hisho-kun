"""
ネオ秘書くん - LFM2.5 セットアップツール ユニットテスト (tests/test_setup_local_model.py)

ネットワーク通信を伴うダウンロード処理は検証対象外とし、
カタログ整合・URL組立・.env永続化ロジックを検証する。
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# tools/ 配下のモジュールを import するためプロジェクトルートを追加
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from setup_local_model import (  # noqa: E402
    MIN_VALID_BYTES,
    MODEL_CATALOG,
    apply_env_config,
    build_download_url,
    setup_model,
)


class TestModelCatalog(unittest.TestCase):
    """モデルカタログ定義の整合性テスト"""

    def test_catalog_contains_two_tiers(self):
        """350m(推奨)と1.2bの2段構成であること"""
        self.assertIn("350m", MODEL_CATALOG)
        self.assertIn("1.2b", MODEL_CATALOG)
        self.assertTrue(MODEL_CATALOG["350m"].get("recommended"))
        self.assertFalse(MODEL_CATALOG["1.2b"].get("recommended"))

    def test_catalog_entries_are_well_formed(self):
        """全エントリが必須キーを持ち・QAD-Q4_0の公式GGUFを指すこと"""
        for key, entry in MODEL_CATALOG.items():
            with self.subTest(key=key):
                for required in ("repo_id", "filename", "display_name", "description"):
                    self.assertIn(required, entry)
                self.assertTrue(str(entry["filename"]).endswith(".gguf"))
                self.assertIn("QAD-Q4_0", str(entry["filename"]))
                self.assertTrue(str(entry["repo_id"]).startswith("LiquidAI/"))

    def test_setup_model_rejects_unknown_key(self):
        """不明なモデルキーでKeyErrorになること"""
        with self.assertRaises(KeyError):
            setup_model("nonexistent_model")

    def test_min_valid_bytes_guard(self):
        """最低妥当サイズガードがHTMLエラーページ等を排除する水準であること"""
        self.assertGreater(MIN_VALID_BYTES, 1 * 1024 * 1024)


class TestEnvPersistence(unittest.TestCase):
    """apply_env_config の .env 永続化テスト"""

    def setUp(self):
        """テストごとに独立した一時.envを用意する"""
        fd, self.env_path = tempfile.mkstemp(suffix=".env")
        os.close(fd)
        self.env_file = Path(self.env_path)

    def tearDown(self):
        """一時.envファイルを後片付けする"""
        if self.env_file.exists():
            self.env_file.unlink()

    def test_apply_env_config_writes_keys(self):
        """LOCAL_GGUF_MODEL と DEFAULT_LLM_PROVIDER が書き込まれること

        ※ python-dotenv の set_key は値をシングルクォートで囲むため、
           キーと値の存在を個別に検証する（クォート様式に依存しない）。
        """
        apply_env_config("LFM2.5-350M-QAD-Q4_0.gguf", self.env_file)
        content = self.env_file.read_text(encoding="utf-8")
        self.assertIn("LOCAL_GGUF_MODEL", content)
        self.assertIn("LFM2.5-350M-QAD-Q4_0.gguf", content)
        self.assertIn("DEFAULT_LLM_PROVIDER", content)
        self.assertIn("local_gguf", content)


class TestUrlBuilder(unittest.TestCase):
    """ダウンロードURL組み立てのテスト"""

    def test_build_download_url(self):
        """Hugging Face resolve形式のURLが組み立てられること"""
        url = build_download_url("LiquidAI/LFM2.5-350M-GGUF", "LFM2.5-350M-QAD-Q4_0.gguf")
        self.assertEqual(
            url,
            "https://huggingface.co/LiquidAI/LFM2.5-350M-GGUF/resolve/main/LFM2.5-350M-QAD-Q4_0.gguf",
        )


if __name__ == "__main__":
    unittest.main()
