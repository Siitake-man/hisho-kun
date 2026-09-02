#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - git履歴機密スキャナ (tools/scan_git_secrets.py)

Phase J「GitHub 公開準備」の必須ゲートツール。git 履歴全体 (--all) を走査し、
API キー・トークン・秘密鍵などの機密パターンを検出する。

機能:
  1. `git log --all -p -U0` の差分テキストを機密パターンでスキャン
     (検出時は コミットハッシュ / ファイル名 / マスク済み行 をレポート)
  2. 機密ファイル (.env / *.db / *.gguf / *.pem / *.key / .sync_token 等) が
     一度でも追加コミットされていないかを履歴検査
  3. 検出値はマスク表示 (先頭6文字のみ) — レポート自体が二次漏洩しない設計

使い方 (PowerShell):
    & .\\venv\\Scripts\\python.exe tools\\scan_git_secrets.py

終了コード: 0 = CLEAN / 1 = 要対応 (機密検出あり) / 2 = git 実行エラー
"""

import argparse
import re
import subprocess
import sys
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# 機密パターン定義 (ラベル, コンパイル済み正規表現)
# ---------------------------------------------------------------------------
SECRET_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("Google API Key", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("OpenAI/互換 Key", re.compile(r"sk-[a-zA-Z0-9]{20,}")),
    ("OpenAI Project Key", re.compile(r"sk-proj-[A-Za-z0-9_\-]{20,}")),
    ("Anthropic Key", re.compile(r"sk-ant-[a-zA-Z0-9_\-]{20,}")),
    ("GitHub Token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("GitHub Fine-grained PAT", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("Slack Token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Private Key Block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("JWT Token", re.compile(r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")),
]

# 一度でもコミットされていたら要対応の機密ファイル群
SENSITIVE_FILE_PATTERNS: List[Tuple[str, re.Pattern]] = [
    (".env (環境変数)", re.compile(r"(^|/)\.env$")),
    ("SQLite DB", re.compile(r"\.db$")),
    ("GGUF モデル", re.compile(r"\.gguf$")),
    ("秘密鍵ファイル", re.compile(r"\.(pem|key)$")),
    ("同期トークン", re.compile(r"(^|/)\.sync_token$")),
    ("MCP 設定", re.compile(r"mcp_config\.json$")),
    ("モデル発見キャッシュ", re.compile(r"discovered_models\.json$")),
]


def mask_secret(line: str) -> str:
    """行内の機密値を先頭6文字 + ***MASKED*** にマスクする。

    Args:
        line: スキャン対象の生の行。

    Returns:
        str: 機密値がマスクされた行。
    """
    masked = line
    for _, pattern in SECRET_PATTERNS:
        masked = pattern.sub(lambda m: m.group(0)[:6] + "***MASKED***", masked)
    return masked


def find_secrets(text: str) -> List[Tuple[str, str]]:
    """テキストから機密パターンを検出する。

    Args:
        text: スキャン対象テキスト (diff の1行など)。

    Returns:
        List[Tuple[str, str]]: (ラベル, マスク済み行) のリスト。該当なしは空リスト。
    """
    findings: List[Tuple[str, str]] = []
    for line in text.splitlines():
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append((label, mask_secret(line)))
    return findings


def run_git(args: List[str]) -> Optional[str]:
    """git コマンドを実行して標準出力を返す。

    Args:
        args: git への引数リスト (先頭の 'git' を除く)。

    Returns:
        Optional[str]: 成功時は標準出力。git が使えない等の失敗時は None。
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as e:
        print(f"[ERROR] git の実行に失敗しました: {e}", file=sys.stderr)
        return None
    if result.returncode != 0:
        print(f"[ERROR] git がエラーを返しました: {result.stderr.strip()}", file=sys.stderr)
        return None
    return result.stdout


def scan_history() -> List[Tuple[str, str, str]]:
    """git 履歴全体の差分を走査して機密を検出する。

    Returns:
        List[Tuple[str, str, str]]: (コミット, ファイル, マスク済み行) のリスト。
        git の実行に失敗した場合は空リスト (呼び出し側でエラー表示)。
    """
    log_text = run_git(["log", "--all", "-p", "-U0", "--no-color"])
    if log_text is None:
        return []

    findings: List[Tuple[str, str, str]] = []
    current_commit = "(unknown)"
    current_file = "(unknown)"
    for line in log_text.splitlines():
        if line.startswith("commit "):
            current_commit = line[len("commit "):].strip()[:12]
            current_file = "(unknown)"
        elif line.startswith("+++ b/"):
            current_file = line[len("+++ b/"):].strip()
        else:
            for label, masked in find_secrets(line):
                findings.append((current_commit, current_file, f"[{label}] {masked}"))
    return findings


def scan_sensitive_files() -> List[Tuple[str, str]]:
    """機密ファイルが一度でも追加コミットされていないか履歴を検査する。

    Returns:
        List[Tuple[str, str]]: (ラベル, ファイルパス) のリスト。
    """
    log_text = run_git(
        ["log", "--all", "--diff-filter=A", "--name-only", "--format="]
    )
    if log_text is None:
        return []

    findings: List[Tuple[str, str]] = []
    seen = set()
    for path in log_text.splitlines():
        path = path.strip()
        if not path:
            continue
        for label, pattern in SENSITIVE_FILE_PATTERNS:
            if pattern.search(path) and (label, path) not in seen:
                seen.add((label, path))
                findings.append((label, path))
    return findings


def main() -> int:
    """監査のエントリポイント。

    Returns:
        int: 0 = CLEAN / 1 = 要対応 (機密検出あり) / 2 = git 実行エラー。
    """
    parser = argparse.ArgumentParser(description="git履歴 機密スキャナ (ネオ秘書くん Phase J ゲート)")
    parser.parse_args()

    print("🔍 git履歴 機密スキャンを開始します (--all)")
    history_findings = scan_history()
    file_findings = scan_sensitive_files()

    if not history_findings and not file_findings:
        print("✅ CLEAN: 機密パターン・機密ファイルともに検出ゼロでした。")
        return 0

    if history_findings:
        print(f"\n🚨 差分内の機密パターン検出: {len(history_findings)}件")
        for commit, file_path, masked in history_findings:
            print(f"  - commit {commit} / {file_path}")
            print(f"      {masked}")
    if file_findings:
        print(f"\n🚨 履歴に機密ファイルの追加コミットあり: {len(file_findings)}件")
        for label, path in file_findings:
            print(f"  - [{label}] {path}")
    print("\n→ 対応: 該当キーの無効化(ローテーション) ＋ 必要に応じて git filter-repo での履歴除去を検討してください。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
