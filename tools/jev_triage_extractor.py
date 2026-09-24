"""Jev System One テスト失敗トリアージ用シグナル抽出モジュール.

生pytestログおよび直前のGit変更コンテキストから、
Jev（System One）が判定に必要な「4大シグナル」を高精度に蒸留・抽出する。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class JevTriageExtractor:
    """pytestの実行出力からJev判定用シグナルを抽出するクラス."""

    # 一般的なPython例外パターンの正規表現（末尾コロンなし行にもマッチ）
    EXCEPTION_PATTERN = re.compile(
        r"(?:E\s+)?([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Warning|Interrupt))(?::\s*(.*)|$)"
    )
    # pytestの失敗箇所パターン (FAILED tests/xxx.py::test_yyy または tests/xxx.py::test_yyy FAILED)
    FAILED_TEST_PATTERN = re.compile(
        r"(?:FAILED\s+([^\s:]+\.py)::([^\s]+)|([^\s:]+\.py)::([^\s]+)\s+FAILED)"
    )
    # pytestのトレースバック行 (file.py:line: in func または file.py:line: Exception)
    LOCATION_PATTERN = re.compile(
        r"([^\s:]+\.py):(\d+)(?::\s+in\s+([^\s]+)|:\s+([A-Za-z_]+))?"
    )

    @classmethod
    def extract_signals(
        cls,
        raw_log: str,
        changed_files: Optional[List[str]] = None,
        git_diff_summary: str = "",
    ) -> Dict[str, Any]:
        """pytestの生ログから4大シグナルを抽出する.

        Args:
            raw_log: pytest実行時の標準出力・標準エラー出力文字列
            changed_files: 直近で変更されたファイルパス一覧（任意）
            git_diff_summary: 直近のgit diff統計サマリ文字列（任意）

        Returns:
            Dict[str, Any]: Jevへ渡す構造化シグナル辞書
                - exception_type (str): 検出された例外クラス名
                - error_message (str): 最終エラーメッセージ
                - failed_location (str): 失敗したテスト名またはファイル位置
                - changed_files (List[str]): 関連変更ファイル一覧
                - is_assertion_failure (bool): AssertionErrorか否か
                - raw_snippet (str): 失敗周辺の主要3行
        """
        exception_type = "UnknownError"
        error_message = ""
        failed_location = ""
        raw_snippet_lines: List[str] = []

        lines = raw_log.splitlines()

        # 1. 失敗したテストの場所を特定
        for line in reversed(lines):
            match_failed = cls.FAILED_TEST_PATTERN.search(line)
            if match_failed:
                file_path = match_failed.group(1) or match_failed.group(3)
                test_name = match_failed.group(2) or match_failed.group(4)
                failed_location = f"{file_path}::{test_name}"
                break

        if not failed_location:
            # 代替: location pattern から探す
            for line in reversed(lines):
                match_loc = cls.LOCATION_PATTERN.search(line)
                if match_loc:
                    func_name = match_loc.group(3) or match_loc.group(4) or "unknown"
                    failed_location = f"{match_loc.group(1)}:{match_loc.group(2)} ({func_name})"
                    break

        # 2. 例外クラス名とエラーメッセージの抽出
        for line in lines:
            stripped = line.strip()
            # pytestの "E   AttributeError: ..." 行を優先探索
            if stripped.startswith("E ") or stripped.startswith("E:"):
                raw_snippet_lines.append(stripped)
                match_exc = cls.EXCEPTION_PATTERN.search(stripped)
                if match_exc:
                    exception_type = match_exc.group(1)
                    error_message = (match_exc.group(2) or "").strip()

        # もしE行で見つからなければ、全体から最後の例外を探す
        if exception_type == "UnknownError":
            for line in reversed(lines):
                match_exc = cls.EXCEPTION_PATTERN.search(line)
                if match_exc:
                    exception_type = match_exc.group(1)
                    error_message = (match_exc.group(2) or "").strip()
                    break

        # pytest特有: E 行に assert がある場合、AssertionError とみなす
        if exception_type == "UnknownError":
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("E   assert ") or stripped.startswith("E assert "):
                    exception_type = "AssertionError"
                    error_message = stripped.replace("E   ", "").replace("E ", "")
                    break

        # 3. AssertionError の特殊ハンドリング
        is_assertion = (exception_type == "AssertionError")
        if is_assertion and not error_message:
            # assert 条件の行を探す
            for line in reversed(lines):
                stripped = line.strip()
                if (
                    stripped.startswith("E   assert ")
                    or stripped.startswith("E assert ")
                    or stripped.startswith("assert ")
                ):
                    error_message = stripped.replace("E   ", "").replace("E ", "")
                    break

        # 4. 主要スニペットのトリミング（最大3行）
        raw_snippet = "\n".join(raw_snippet_lines[-3:]) if raw_snippet_lines else error_message

        return {
            "exception_type": exception_type,
            "error_message": error_message,
            "failed_location": failed_location or "unknown_test",
            "changed_files": changed_files or [],
            "git_diff_summary": git_diff_summary,
            "is_assertion_failure": is_assertion,
            "raw_snippet": raw_snippet,
        }
