#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - B20 音声パイプライン E2E 検証ツール (tools/e2e_voice_check.py)

edge-tts (Microsoft Edge 音声, ja-JP-NanamiNeural) で日本語音声 MP3 を合成し、
「合成音声 → WhisperTranscriber 文字起こし → task_parser.parse_input 解析」
の B20 パイプラインを通し検証する手動実行ツール。

使い方:
    venv\\Scripts\\python.exe tools\\e2e_voice_check.py

注意:
- 初回実行時、Whisper 'small' モデル (~463MB) を Hugging Face からダウンロードする。
- 音声合成は edge-tts を使用するためネットワーク接続が必要 (Whisper 自体はオフライン)。
"""

import asyncio
import os
import sys
import tempfile
import logging

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

SAMPLE_TEXT = "明日の朝9時に企画書のレビューをしてください"


async def _synthesize_edge_tts(text: str, out_path: str) -> None:
    """edge-tts で日本語音声 MP3 を合成する。

    Args:
        text (str): 読み上げるテキスト。
        out_path (str): 出力 MP3 パス。
    """
    import edge_tts  # type: ignore

    communicate = edge_tts.Communicate(text, "ja-JP-NanamiNeural")
    await communicate.save(out_path)


def synthesize_voice(text: str, out_path: str) -> str:
    """音声合成のエントリ。生成したファイルパスを返す（失敗時は空文字）。"""
    try:
        asyncio.run(_synthesize_edge_tts(text, out_path))
        return out_path
    except Exception as e:  # noqa: BLE001 - 手動ツールのため詳細を画面へ出す
        print(f"⚠ 音声合成に失敗しました: {e}")
        return ""


def main() -> int:
    """E2E 検証の本体。戻り値 0=成功 / 1=失敗。"""
    # --- Step 1: edge-tts 音声合成 ---
    mp3_path = os.path.join(tempfile.gettempdir(), "hisho_e2e_voice.mp3")
    print(f"\n[Step 1] edge-tts 音声合成: '{SAMPLE_TEXT}'")
    if not synthesize_voice(SAMPLE_TEXT, mp3_path):
        print("→ 音声合成に失敗したため検証を中断しました (ネットワーク接続を確認してください)。")
        return 1
    size = os.path.getsize(mp3_path)
    print(f"→ MP3 生成 OK: {mp3_path} ({size:,} bytes)")
    assert size > 10000, "MP3 が異常に小さい"

    # --- Step 2: Whisper 文字起こし ---
    print("\n[Step 2] WhisperTranscriber で文字起こし (初回はモデルDLあり)")
    from whisper_transcriber import WhisperTranscriber

    transcriber = WhisperTranscriber()
    assert transcriber.is_available(), "faster-whisper が利用できません"
    with open(mp3_path, "rb") as f:
        audio_bytes = f.read()
    transcript = transcriber.transcribe(audio_bytes, filename="e2e.mp3")
    print(f"→ 文字起こし結果: '{transcript}'")
    assert transcript, "文字起こしが空"

    # --- Step 3: タスク解析 (スマホ transcribe_voice と同一経路) ---
    print("\n[Step 3] task_parser.parse_input でタスク解析")
    from task_parser import parse_input

    parsed = parse_input(transcript)
    print(f"→ title    : {parsed.title}")
    print(f"→ due_date : {parsed.due_date}")
    print(f"→ priority : {parsed.priority}")
    print(f"→ tags     : {parsed.tags}")
    print(f"→ 重要/緊急: {parsed.importance} / {parsed.urgency}")
    assert parsed.title, "タスク名が解析できなかった"

    print("\n✅ B20 パイプライン E2E 全ステップ成功 (音声→文字起こし→タスク解析)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
