#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - Approval Policy 3段階コマンド判定エンジン (approval_policy.py)

AIコーディングエージェントからのコマンド実行要請を解析し、
認知負荷を削減しながら安全性を担保する3段階判定エンジン。

3段階の判定基準:
- 🟢 AUTO_ALLOW: 閲覧・テスト・状態確認など、副作用のない安全な操作。
               人間を煩わせず即座に自動承認し、AIの思考・開発ループを加速。
- 🟡 PROMPT: 通常の編集・パッケージ追加・ビルドなど、標準的な開発操作。
            スマホ Desk Pet に通知し、ワンタップ承認を促す。
- 🔴 STRICT: ファイル全削除・強制プッシュ・テーブル削除などの破壊的変更。
            スマホ画面が赤く警告点滅し、慎重な二重確認を求める。
"""

import logging
import re
import shlex
from dataclasses import dataclass, field
from typing import List, Optional, Pattern

from agent_adapter import RiskLevel

logger = logging.getLogger(__name__)


@dataclass
class PolicyDecision:
    """コマンド評価の結果を表すデータクラス。

    Attributes:
        risk_level: 判定された危険度レベル (AUTO_ALLOW / PROMPT / STRICT)。
        reason: 判定理由の説明テキスト。
        matched_rule: マッチしたルール名またはパターン。
    """
    risk_level: RiskLevel
    reason: str
    matched_rule: str = ""

    @property
    def is_auto_allowed(self) -> bool:
        """即時自動許可可能かどうかを返す。"""
        return self.risk_level == RiskLevel.AUTO_ALLOW

    @property
    def is_strict(self) -> bool:
        """破壊的・高危険度コマンドかどうかを返す。"""
        return self.risk_level == RiskLevel.STRICT

    @property
    def requires_human_approval(self) -> bool:
        """人間による確認・タップ承認が必要かどうかを返す。"""
        return self.risk_level in (RiskLevel.PROMPT, RiskLevel.STRICT)


class ApprovalPolicyEngine:
    """エージェントが要求したコマンドの危険度を正規表現ベースで多重評価するエンジン。"""

    # 🛡️ P0-2 (2026-09-22): shlex 構造パースで「複合コマンド」と判定するシェル演算子。
    #    部分文字列（`;` 等）ではなくトークン単位で判定するため、引用符内の演算子を
    #    含む語（例: `echo "a;b"`）は単一コマンドとして扱われる。
    #    ※ 引用符が語全体を覆う純粋演算子（例: `echo ">"`）は保守的に複合扱い（安全側）。
    _PUNCT_CHARS = frozenset("();<>|&")

    # 展開構文（コマンド置換・変数展開）: shlex は展開を解釈しないため明示検知する。
    #  %VAR% (cmd.exe) / $env:X (PowerShell) / ${X} (bash) / $( ) / バッククォート
    _EXPANSION_RE: Pattern[str] = re.compile(
        r"\$\(|`|%[A-Za-z_][A-Za-z0-9_]*%|\$(env:|\{)", re.IGNORECASE
    )

    # パイプ・xargs 経由の実行で危険とみなすインタプリタ
    _INTERPRETER_TOKENS = frozenset({
        "sh", "bash", "zsh", "dash", "ksh", "pwsh", "powershell", "cmd",
        "python", "python3", "perl", "ruby", "node", "php",
    })

    # 🔴 STRICT (破壊的・危険コマンド) の正規表現パターン
    DEFAULT_STRICT_PATTERNS: List[str] = [
        # 再帰的・強制削除 (rm -rf, rmdir /s, del /s, Remove-Item -Recurse -Force 等)
        r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\b",
        r"\brm\s+-[a-zA-Z]*f[a-zA-Z]*r\b",
        r"\brmdir\s+/[sS]\b",
        r"\bdel\s+/[sS]\b",
        r"\bRemove-Item\b.*-[rR]ecurse.*-[fF]orce\b",
        r"\bRemove-Item\b.*-[fF]orce.*-[rR]ecurse\b",

        # Git 危険操作 (force push, reset --hard, clean -fdx 等)
        r"\bgit\s+push\b.*(--force|-f\b)",
        r"\bgit\s+reset\s+--hard\b",
        r"\bgit\s+clean\s+-[a-zA-Z]*f",

        # データベース破壊 (DROP TABLE, DROP DATABASE, TRUNCATE 等)
        r"\bDROP\s+(TABLE|DATABASE)\b",
        r"\bTRUNCATE\s+TABLE\b",

        # 権限昇格・全開放 (chmod 777, sudo 等)
        r"\bchmod\s+777\b",
        r"\bsudo\s+",
        r"\bchown\s+-R\b",

        # ディスク・OS破壊
        r"\bmkfs\b",
        r"\bformat\s+[a-zA-Z]:",
        r"\bdd\s+if=",

        # 🛡️ P0-2 (2026-09-22): 構造パースで検知する任意コード実行の複合形
        #    パイプ先がインタプリタ（シェル・スクリプト言語）＝無承認で任意コード実行
        r"\|\s*(sh|bash|zsh|dash|ksh|pwsh|powershell|cmd|python[0-9.]*|perl|ruby|node|php)\b",

        # 🛡️ P0-2: ファイル書込・破壊を伴う「読み取り系」の変種（無承認化の防止）
        r"\bgit\s+(status|diff|log|show)\b[^|;&]*--output",
        r"\bgit\s+branch\s+(-[dDmMfcu]|--delete|--set-upstream-to)",
        r"\bgit\s+tag\s+(?!(-l|-n|--list|--contains|--points-at|--merged|--sort|--format)\b)\S",
        r"\bgit\s+remote\s+(add|remove|set-url|rename|prune|set-head|set-branches|update)\b",
        r"\brm\b[^|;&]*(--recursive\b|-r\b)[^|;&]*(--force\b|-f\b)",
        r"\brm\b[^|;&]*(--force\b|-f\b)[^|;&]*(--recursive\b|-r\b)",
        r"\bRemove-Item\b[^|;&]*-[rR]ecurse\b",
    ]

    # 🟢 AUTO_ALLOW (安全・読み取り専用・テストコマンド) の正規表現パターン
    DEFAULT_AUTO_ALLOW_PATTERNS: List[str] = [
        # Git 読み取り系
        r"^git\s+(status|diff|log|branch|show|remote(\s+-v)?|tag(\s+-l)?)\b",

        # ディレクトリ・ファイル読み取り系
        r"^(ls|dir|pwd|echo|cat|type|head|tail|more|less)\b",
        r"^(which|where|find|grep|ripgrep|rg)\b",

        # テスト実行系 (自動テストランナー)
        r"^pytest\b",
        r"^python(\.exe)?\s+-m\s+unittest\b",
        r"^npm\s+test\b",
        r"^cargo\s+test\b",
        r"^cargo\s+check\b",
        r"^go\s+test\b",
    ]

    def __init__(self) -> None:
        self._strict_regexes: List[Pattern[str]] = [
            re.compile(p, re.IGNORECASE) for p in self.DEFAULT_STRICT_PATTERNS
        ]
        self._auto_allow_regexes: List[Pattern[str]] = [
            re.compile(p, re.IGNORECASE) for p in self.DEFAULT_AUTO_ALLOW_PATTERNS
        ]

    def add_strict_pattern(self, pattern: str) -> None:
        """危険コマンド判定パターンを動的に追加する。"""
        self._strict_regexes.insert(0, re.compile(pattern, re.IGNORECASE))

    def add_auto_allow_pattern(self, pattern: str) -> None:
        """自動許可コマンド判定パターンを動的に追加する。"""
        self._auto_allow_regexes.insert(0, re.compile(pattern, re.IGNORECASE))

    def _tokenize(self, command: str) -> Optional[List[str]]:
        """シェル字句解析（shlex）でトークン列を得る (P0-2)。

        Notes:
            🛡️ P0-2: `commenters` を無効化する。shlex の既定値は `'#'` をコメント開始と
            みなし **語中でも以降を読み捨てる**ため、`echo pwn#>~/.bashrc` が
            「複合なし」と誤判定され無承認書込に到達してしまう（bash は語中 `#` を
            リテラル扱いする）。解析不能（閉じない引用符等）は None を返し、
            呼び出し側が Fail-Closed（PROMPT）に倒す。

        Args:
            command (str): 実行予定のコマンドライン文字列。

        Returns:
            Optional[List[str]]: トークン列（解析不能時は None）。
        """
        try:
            lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
            lexer.whitespace_split = True
            lexer.commenters = ""
            return list(lexer)
        except ValueError as e:
            logger.warning("コマンド構文の解析に失敗しました (Fail-Closed で PROMPT に倒します): %s", e)
            return None

    def _detect_structural_strict(self, tokens: List[str]) -> str:
        """トークン列から構造的に危険な操作を検出する (P0-2)。

        引用符内の文字列（例: `grep -r 'eval(' .` の `eval(`）を誤検知しないよう、
        生文字列ではなくトークン（＝シェルが実際にコマンド語として解釈する単位）で判定する。

        Args:
            tokens (List[str]): `_tokenize` の結果。

        Returns:
            str: 検出理由（該当なしの場合は空文字）。
        """
        lowered = [t.lower() for t in tokens]
        for name in ("eval", "invoke-expression", "iex"):
            if name in lowered:
                return f"動的評価 ({name}) を検出しました"
        if "find" in lowered:
            # 🛡️ 完全一致ではなく**先頭一致**で判定する（-fprint0 / -okdir 等の派生形を取りこぼさない）
            for flag in ("-exec", "-execdir", "-delete", "-fprint", "-fprintf", "-fls", "-ok", "-okdir"):
                if any(token == flag or token.startswith(flag) for token in lowered):
                    return f"find の {flag} 系による任意操作を検出しました"
        if "xargs" in lowered:
            for name in self._INTERPRETER_TOKENS:
                if name in lowered:
                    return f"xargs 経由のインタプリタ実行 ({name}) を検出しました"
        # パイプ経由のインタプリタ実行はパス修飾形（/bin/bash・env bash 等）も検出する
        has_pipe = any(t and all(ch in self._PUNCT_CHARS for ch in t) and "|" in t for t in tokens)
        if has_pipe:
            for token in tokens:
                base = token.replace("\\", "/").rsplit("/", 1)[-1].lower()
                if base in self._INTERPRETER_TOKENS:
                    return f"パイプ経由のインタプリタ実行 ({base}) を検出しました"
        return ""

    def _detect_composite(self, command: str) -> str:
        """シェル構造を字句解析し、複合コマンド・リダイレクト・展開を検出する (P0-2)。

        Notes:
            🛡️ P0-2 (2026-09-22): 旧実装は `;` `&&` `||` の**部分文字列**しか見ていなかったため、
            `cat evil.sh | bash`（パイプ）・`echo x > ~/.bashrc`（リダイレクト）・
            `ls & pytest`（バックグラウンド）・`cat $(whoami)`（置換）が AUTO_ALLOW を素通りしていた。
            shlex の punctuation_chars でシェル演算子をトークン化し、
            **句読点のみで構成されるトークン＝演算子ラン**（`>|` `&>` `&>>` 等の連結形を含む）を
            構造で判定する。

        Args:
            command (str): 実行予定のコマンドライン文字列。

        Returns:
            str: 複合と判定した理由（単一コマンドの場合は空文字）。
        """
        if self._EXPANSION_RE.search(command):
            return "コマンド置換・変数展開を含むため通常承認が必要です"
        if "\n" in command or "\r" in command:
            # 改行はシェルではコマンド区切り（shlex は空白として扱うため明示検知する）
            return "複数行コマンド（改行による複合）のため通常承認が必要です"
        tokens = self._tokenize(command)
        if tokens is None:
            return "シェル構文の解析に失敗したため通常承認が必要です"
        for token in tokens:
            if token and all(ch in self._PUNCT_CHARS for ch in token):
                return "複合コマンド（パイプ・チェイン・リダイレクト）のため通常承認が必要です"
        return ""

    def evaluate(self, command: str) -> PolicyDecision:
        """コマンドを評価し、3段階の危険度判定を下す。

        評価順序 (Fail-Safe 原則):
        1. まず 🔴 STRICT パターンに該当しないかを最優先検証 (複合コマンド内の危険操作を検知)。
        2. 次に 🟢 AUTO_ALLOW パターンに完全準拠しているかを検証。
        3. いずれにも当てはまらない通常の開発コマンドは 🟡 PROMPT (人間確認) にフォールバック。

        Args:
            command: 実行予定のコマンドライン文字列。

        Returns:
            PolicyDecision: 判定結果オブジェクト。
        """
        clean_cmd = command.strip()
        if not clean_cmd:
            return PolicyDecision(
                risk_level=RiskLevel.PROMPT,
                reason="空のコマンドです",
                matched_rule="empty_command",
            )

        # 1. 🔴 STRICT チェック (どこかに危険パターンが含まれていれば即座に赤判定)
        for pattern in self._strict_regexes:
            match = pattern.search(clean_cmd)
            if match:
                return PolicyDecision(
                    risk_level=RiskLevel.STRICT,
                    reason=f"破壊的または危険な操作を検出しました: {match.group(0)}",
                    matched_rule=pattern.pattern,
                )

        # 1.5 🔴 STRICT チェック（構造判定 / P0-2）: 引用符内の文字列を誤検知しないよう
        #     シェルが実際にコマンド語として解釈するトークン列で危険操作を判定する。
        tokens = self._tokenize(clean_cmd)
        if tokens is not None:
            structural_strict_reason = self._detect_structural_strict(tokens)
            if structural_strict_reason:
                return PolicyDecision(
                    risk_level=RiskLevel.STRICT,
                    reason=structural_strict_reason,
                    matched_rule="structural_strict",
                )

        # 2. 🟢 AUTO_ALLOW チェック (安全なコマンドに適合するか)
        # 🛡️ P0-2 (2026-09-22): シェル構造をパースし、複合コマンド・リダイレクト・コマンド置換は
        # 安全のため PROMPT へ倒す（部分文字列判定を廃止し、構造判定へ移行）。
        composite_reason = self._detect_composite(clean_cmd)
        if composite_reason:
            return PolicyDecision(
                risk_level=RiskLevel.PROMPT,
                reason=composite_reason,
                matched_rule="composite_command",
            )

        for pattern in self._auto_allow_regexes:
            if pattern.search(clean_cmd):
                return PolicyDecision(
                    risk_level=RiskLevel.AUTO_ALLOW,
                    reason="安全な閲覧またはテストコマンドとして自動許可されました",
                    matched_rule=pattern.pattern,
                )

        # 3. 🟡 PROMPT (デフォルト・通常承認)
        return PolicyDecision(
            risk_level=RiskLevel.PROMPT,
            reason="通常の開発・変更操作のため、確認・ワンタップ承認が必要です",
            matched_rule="default_prompt",
        )


# グローバル共有の判定エンジンインスタンス
_DEFAULT_POLICY_ENGINE: Optional[ApprovalPolicyEngine] = None


def get_default_policy_engine() -> ApprovalPolicyEngine:
    """デフォルトのポリシーエンジンインスタンスを返す。"""
    global _DEFAULT_POLICY_ENGINE
    if _DEFAULT_POLICY_ENGINE is None:
        _DEFAULT_POLICY_ENGINE = ApprovalPolicyEngine()
    return _DEFAULT_POLICY_ENGINE
