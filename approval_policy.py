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

import re
from dataclasses import dataclass, field
from typing import List, Optional, Pattern

from agent_adapter import RiskLevel


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

        # 2. 🟢 AUTO_ALLOW チェック (安全なコマンドに適合するか)
        # ※ セミコロンやパイプで複合されている場合は慎重にPROMPTに倒す
        if ";" in clean_cmd or "&&" in clean_cmd or "||" in clean_cmd:
            # 複合コマンドは安全のためPROMPTへ
            return PolicyDecision(
                risk_level=RiskLevel.PROMPT,
                reason="複合コマンド（チェイン実行）のため通常承認が必要です",
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
