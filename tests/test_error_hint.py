#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - LLMエラーヒント生成の単体テスト (tests/test_error_hint.py)

2026-09 の OpenCode 仕様変更 (x-opencode-session 必須化) 時、UI が汎用文言
「AIとの通信に失敗しました」しか出さず真因特定にオフライン診断が必要だった。
provider 由来の具体的エラー型を 1 行ヒントとして UI に見せる契約を凍結する。
機微情報 (APIキー等) は防御的にマスクされること。

TDD: format_llm_error_hint() が無い状態では Red で落ちる。
"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from llm_factory import format_llm_error_hint


class TestFormatLlmErrorHint(unittest.TestCase):
    """エラーヒント生成 (1行・マスク済み) の契約検証"""

    def test_includes_exception_type_and_message(self) -> None:
        """例外型名とメッセージが含まれること (真因がその場で分かる)"""
        hint = format_llm_error_hint(RuntimeError("MissingSessionID"))

        self.assertIn("RuntimeError", hint)
        self.assertIn("MissingSessionID", hint)

    def test_masks_api_key_like_strings(self) -> None:
        """APIキーらしき文字列 (sk-...) はマスクされること (二次漏洩防止)"""
        exc = RuntimeError("auth failed for key sk-abcdefghij1234567890abcd")

        hint = format_llm_error_hint(exc)

        self.assertNotIn("sk-abcdefghij", hint)
        self.assertIn("***", hint)

    def test_masks_bearer_tokens(self) -> None:
        """Bearer トークンもマスクされること"""
        exc = RuntimeError("denied for Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9zzz")

        hint = format_llm_error_hint(exc)

        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9zzz", hint)

    def test_truncates_to_limit(self) -> None:
        """limit (既定100文字) 以内に切り詰められること (吹き出しの幅制約)"""
        hint = format_llm_error_hint(ValueError("x" * 500), limit=50)

        self.assertLessEqual(len(hint), 50)

    def test_collapses_whitespace_to_single_line(self) -> None:
        """改行・連続空白は 1 行に潰されること (吹き出し表示崩れ防止)"""
        hint = format_llm_error_hint(RuntimeError("line1\nline2\r\n  line3"))

        self.assertNotIn("\n", hint)
        self.assertNotIn("\r", hint)


if __name__ == "__main__":
    unittest.main(verbosity=2)
