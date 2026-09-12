#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - llama_cpp devnull ハンドル後片付けの単体テスト (tests/test_llama_devnull_cleanup.py)

Jules 夜間タスクA (2026-09-06) の根治を凍結する:
llama_cpp._utils がモジュール import 時に ``open(os.devnull, "w")`` (encoding 指定なし
→ locale エンコーディング cp932) を 2 本開きっぱなしにするため、インタプリタ終了時の
GC で ``ResourceWarning: unclosed file <_io.TextIOWrapper name='nul' ...>`` が漏出する。
本テストは atexit 経由の解放ヘルパ (_close_llama_cpp_devnull_leaks) の契約を検証する。

TDD: 実装 (llm_factory._close_llama_cpp_devnull_leaks) が存在しない状態では Red で落ちる。
"""

import sys
import types
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import llm_factory


class _FakeFile:
    """close() のみを模倣する最小ファイルスタブ。"""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class TestCloseLlamaCppDevnullLeaks(unittest.TestCase):
    """llama_cpp._utils の devnull ハンドル解放ヘルパの契約検証"""

    def setUp(self) -> None:
        llm_factory._LLAMA_CPP_CLEANUP_REGISTERED = False

    def tearDown(self) -> None:
        llm_factory._LLAMA_CPP_CLEANUP_REGISTERED = False

    def test_closes_both_leaked_handles(self) -> None:
        """outnull_file / errnull_file の双方が close されること"""
        fake_utils = types.ModuleType("llama_cpp._utils")
        out_f = _FakeFile()
        err_f = _FakeFile()
        fake_utils.outnull_file = out_f
        fake_utils.errnull_file = err_f

        with mock.patch.dict(sys.modules, {"llama_cpp._utils": fake_utils}):
            llm_factory._close_llama_cpp_devnull_leaks()

        self.assertTrue(out_f.closed)
        self.assertTrue(err_f.closed)

    def test_tolerates_already_closed_handles(self) -> None:
        """既に close 済みのハンドルに対して再 close しないこと (冪等)"""
        fake_utils = types.ModuleType("llama_cpp._utils")
        out_f = _FakeFile()
        out_f.closed = True
        fake_utils.outnull_file = out_f
        fake_utils.errnull_file = _FakeFile()

        with mock.patch.dict(sys.modules, {"llama_cpp._utils": fake_utils}):
            llm_factory._close_llama_cpp_devnull_leaks()

        self.assertTrue(fake_utils.errnull_file.closed)

    def test_tolerates_missing_llama_cpp(self) -> None:
        """llama_cpp._utils が import 不可能でも例外を漏らさないこと (Fail-Safe)"""
        with mock.patch.dict(sys.modules, {"llama_cpp._utils": None}):
            llm_factory._close_llama_cpp_devnull_leaks()  # 例外を raise しないこと

    def test_registration_is_idempotent(self) -> None:
        """atexit 登録が複数回の llama import でも 1 度しか行われないこと"""
        with mock.patch("atexit.register") as fake_register:
            llm_factory._register_llama_cpp_devnull_cleanup()
            llm_factory._register_llama_cpp_devnull_cleanup()

        self.assertEqual(fake_register.call_count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
