#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - PC Whisper 音声文字起こしモジュール (whisper_transcriber.py)

スマホDesk Petから送信された音声データ（WebM / WAV / MP3等）を受信し、
PCローカルの faster-whisper（CTranslate2高速バックエンド）を用いて
オフライン・高精度・ゼロ外部通信で日本語テキストへ文字起こしします。

設計方針:
- 遅延ロード (Lazy Load): 初回 transcribe 実行時にモデルをロードし、起動時メモリを浪費しない。
- スレッドセーフ: HTTPリクエストスレッドからの同時呼び出しを threading.Lock で保護。
- グレースフル・フォールバック: faster-whisper 未導入環境でもクラッシュせず is_available()=False を返却。
"""

import os
import io
import tempfile
import logging
import threading
from typing import Optional, List, Any

logger = logging.getLogger(__name__)

# faster-whisper のインポート（未導入時は安全にフラグをFalseにする）
_FASTER_WHISPER_AVAILABLE: bool = False
try:
    from faster_whisper import WhisperModel  # type: ignore
    _FASTER_WHISPER_AVAILABLE = True
except ImportError:
    logger.info("faster-whisper がインストールされていません。音声文字起こし機能は待機状態になります。")
except Exception as e:
    logger.warning("faster-whisper の読み込み中に予期しないエラーが発生しました: %s", e)


class WhisperTranscriber:
    """faster-whisper を用いたローカル音声文字起こしエンジン。

    Attributes:
        model_size (str): Whisperモデルサイズ (base, small, medium, large-v3等)。既定は 'small'。
        language (str): 文字起こし対象言語コード。既定は 'ja'。
        device (str): 実行デバイス ('cpu' または 'cuda')。既定は 'cpu'。
        compute_type (str): 量子化計算タイプ ('int8', 'float16', 'float32'等)。既定は 'int8'。
    """

    _cached_model: Optional[Any] = None
    _model_lock: threading.Lock = threading.Lock()

    def __init__(
        self,
        model_size: str = "small",
        language: str = "ja",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        """WhisperTranscriber を初期化します。

        Args:
            model_size (str): モデルサイズ ('base', 'small', 'medium')。
            language (str): 言語コード ('ja')。
            device (str): 実行デバイス ('cpu' または 'cuda')。
            compute_type (str): 計算精度 ('int8' 等)。
        """
        self.model_size = model_size
        self.language = language
        self.device = device
        self.compute_type = compute_type

    def is_available(self) -> bool:
        """faster-whisper ライブラリが利用可能かどうかを判定します。

        Returns:
            bool: ライブラリがロードされていれば True、未導入なら False。
        """
        return _FASTER_WHISPER_AVAILABLE

    def _get_model(self) -> Any:
        """モデルインスタンスを遅延ロード（スレッドセーフ）して取得します。

        Returns:
            WhisperModel: ロード済みのWhisperModelインスタンス。

        Raises:
            RuntimeError: faster-whisper がインストールされていない場合。
        """
        if not self.is_available():
            raise RuntimeError(
                "faster-whisper がインストールされていないため、音声文字起こしを実行できません。"
                "venv\\Scripts\\pip install -r requirements_whisper.txt を実行してください。"
            )

        with self._model_lock:
            if WhisperTranscriber._cached_model is None:
                logger.info(
                    "Whisper モデルをロード中... (model_size=%s, device=%s, compute_type=%s)",
                    self.model_size,
                    self.device,
                    self.compute_type,
                )
                WhisperTranscriber._cached_model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                )
                logger.info("Whisper モデルのロードが完了しました。")
            return WhisperTranscriber._cached_model

    def transcribe(self, audio_bytes: bytes, filename: str = "voice.webm") -> str:
        """音声バイナリデータを受け取り、日本語テキストへ文字起こしします。

        一時ファイルに音声を書き出し、faster-whisper でセグメントを抽出して結合します。

        Args:
            audio_bytes (bytes): 音声ファイルの生バイナリデータ。
            filename (str): 元のファイル名（拡張子判定用）。既定は 'voice.webm'。

        Returns:
            str: 文字起こしされたテキスト（前後の空白を除去）。空音声時は空文字列。

        Raises:
            RuntimeError: faster-whisper 未導入時、または文字起こし処理中の致命的エラー。
        """
        if not audio_bytes:
            logger.warning("空の音声データを受信しました。")
            return ""

        model = self._get_model()

        # 拡張子の抽出
        _, ext = os.path.splitext(filename)
        if not ext:
            ext = ".webm"

        tmp_file_path: Optional[str] = None
        try:
            # 一時ファイルを作成して音声データを書き込み
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_file_path = tmp.name

            logger.info("音声文字起こしを開始します: size=%d bytes, tmp=%s", len(audio_bytes), tmp_file_path)

            # faster-whisper による文字起こし
            segments, info = model.transcribe(
                tmp_file_path,
                language=self.language,
                beam_size=5,
                vad_filter=True,  # 無音区間の自動除去
            )

            transcript_parts: List[str] = []
            for segment in segments:
                transcript_parts.append(segment.text)

            full_text = "".join(transcript_parts).strip()
            logger.info("音声文字起こし完了: '%s' (detected language: %s, prob: %.2f)", full_text, info.language, info.language_probability)
            return full_text

        except Exception as e:
            logger.error("音声文字起こし処理中にエラーが発生しました: %s", e, exc_info=True)
            raise RuntimeError(f"文字起こし処理エラー: {e}") from e

        finally:
            # 一時ファイルの確実なクリーンアップ
            if tmp_file_path and os.path.exists(tmp_file_path):
                try:
                    os.remove(tmp_file_path)
                except Exception as e:
                    logger.debug("一時ファイルの削除に失敗しました (無視可能): %s", e)
