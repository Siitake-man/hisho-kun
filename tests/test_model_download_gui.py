import tempfile
import os
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

import tools.setup_local_model as setup_tool


class TestModelDownloadGUI(unittest.TestCase):
    def test_download_model_signature_with_callback(self):
        """download_model が progress_callback を受け取り正常に処理できるか検証"""
        callback_called = []

        def mock_callback(downloaded, total, pct):
            callback_called.append((downloaded, total, pct))

        with tempfile.TemporaryDirectory() as temp_dir:
            test_models_dir = Path(temp_dir)
            
            # 既に存在するファイルとしてモックを作成
            target_file = test_models_dir / "LFM2.5-350M-QAD-Q4_0.gguf"
            target_file.write_bytes(b"dummy_gguf_content" * 100)
            file_size = target_file.stat().st_size

            # fetch_remote_size が同じサイズを返すようにモック（既存ファイル検出パス）
            with patch("tools.setup_local_model.fetch_remote_size", return_value=file_size):
                dest = setup_tool.download_model("350m", models_dir=test_models_dir, progress_callback=mock_callback)
                self.assertEqual(dest.name, "LFM2.5-350M-QAD-Q4_0.gguf")
                self.assertEqual(dest, target_file)
                self.assertGreater(len(callback_called), 0)

    def test_model_catalog_keys(self):
        """350m と 1.2b のモデルカタログ定義が完全か検証"""
        self.assertIn("350m", setup_tool.MODEL_CATALOG)
        self.assertIn("1.2b", setup_tool.MODEL_CATALOG)
        self.assertEqual(setup_tool.MODEL_CATALOG["350m"]["filename"], "LFM2.5-350M-QAD-Q4_0.gguf")
        self.assertEqual(setup_tool.MODEL_CATALOG["1.2b"]["filename"], "LFM2.5-1.2B-Instruct-QAD-Q4_0.gguf")


if __name__ == "__main__":
    unittest.main()
