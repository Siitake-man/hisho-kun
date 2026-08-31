#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - WhisperTranscriber 単体テスト (tests/test_whisper_transcriber.py)

faster-whisper の未導入時フォールバックおよびモックを用いた文字起こしパイプラインを検証します。
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# プロジェクトルートをパスに追加
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from whisper_transcriber import WhisperTranscriber, _FASTER_WHISPER_AVAILABLE


class TestWhisperTranscriber(unittest.TestCase):
    """WhisperTranscriber の単体テストクラス。"""

    def setUp(self):
        self.transcriber = WhisperTranscriber(model_size="small", language="ja")

    def test_initialization(self):
        """初期化パラメーターが正しく設定されていることを確認。"""
        self.assertEqual(self.transcriber.model_size, "small")
        self.assertEqual(self.transcriber.language, "ja")
        self.assertEqual(self.transcriber.device, "cpu")
        self.assertEqual(self.transcriber.compute_type, "int8")

    def test_is_available(self):
        """ライブラリの有無フラグと is_available() の一致を確認。"""
        self.assertEqual(self.transcriber.is_available(), _FASTER_WHISPER_AVAILABLE)

    def test_empty_audio_bytes(self):
        """空の音声データに対しては空文字を即時返却することを確認。"""
        res = self.transcriber.transcribe(b"")
        self.assertEqual(res, "")

    @patch("whisper_transcriber._FASTER_WHISPER_AVAILABLE", False)
    def test_unavailable_fallback_raises(self):
        """ライブラリ未導入時に transcribe を呼ぶと RuntimeError が発生することを確認。"""
        t = WhisperTranscriber()
        with self.assertRaises(RuntimeError) as ctx:
            t.transcribe(b"dummy_audio_bytes")
        self.assertIn("faster-whisper がインストールされていないため", str(ctx.exception))

    @patch("whisper_transcriber._FASTER_WHISPER_AVAILABLE", True)
    def test_mock_transcribe_success(self):
        """モックモデルを用いて正常に文字起こしテキストが結合されることを確認。"""
        mock_segment1 = MagicMock()
        mock_segment1.text = "明日の朝9時に"
        mock_segment2 = MagicMock()
        mock_segment2.text = "企画書のレビューをする"

        mock_info = MagicMock()
        mock_info.language = "ja"
        mock_info.language_probability = 0.99

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment1, mock_segment2], mock_info)

        with patch.object(WhisperTranscriber, "_get_model", return_value=mock_model):
            t = WhisperTranscriber()
            result = t.transcribe(b"fake_audio_content", filename="test.webm")
            self.assertEqual(result, "明日の朝9時に企画書のレビューをする")


if __name__ == "__main__":
    unittest.main()
