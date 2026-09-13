#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_approval_policy.py

Block 2 Node B: Approval Policy 3段階コマンド判定エンジンの単体テスト (TDD)
"""

import unittest
from agent_adapter import RiskLevel


class TestApprovalPolicyEngine(unittest.TestCase):
    """3段階判定エンジン (Auto-Allow / Prompt / Strict) の判定テスト"""

    def setUp(self) -> None:
        from approval_policy import ApprovalPolicyEngine
        self.engine = ApprovalPolicyEngine()

    def test_auto_allow_safe_commands(self) -> None:
        """読み取り・テスト・状態確認コマンドが AUTO_ALLOW になること"""
        safe_commands = [
            "git status",
            "git diff HEAD~1",
            "git log -n 5 --oneline",
            "git branch",
            "ls -la",
            "dir",
            "pwd",
            "pytest tests/ -v",
            "python -m unittest discover",
            "npm test",
            "cargo test",
            "cat README.md",
            "grep -r 'pattern' .",
        ]
        for cmd in safe_commands:
            decision = self.engine.evaluate(cmd)
            self.assertEqual(
                decision.risk_level,
                RiskLevel.AUTO_ALLOW,
                f"コマンド '{cmd}' は AUTO_ALLOW と判定されるべきですが、{decision.risk_level} でした (理由: {decision.reason})"
            )
            self.assertTrue(decision.is_auto_allowed)

    def test_strict_dangerous_commands(self) -> None:
        """ファイル全削除・強制プッシュ・DB破壊コマンドが STRICT になること"""
        dangerous_commands = [
            "rm -rf /",
            "rm -rf .git",
            "rm -rf ./dist",
            "rmdir /s /q build",
            "del /s /q C:\\temp",
            "Remove-Item -Recurse -Force ./target",
            "git push origin main --force",
            "git push -f origin main",
            "git reset --hard HEAD~1",
            "git clean -fdx",
            "DROP TABLE users;",
            "chmod 777 -R /var/www",
        ]
        for cmd in dangerous_commands:
            decision = self.engine.evaluate(cmd)
            self.assertEqual(
                decision.risk_level,
                RiskLevel.STRICT,
                f"コマンド '{cmd}' は STRICT と判定されるべきですが、{decision.risk_level} でした (理由: {decision.reason})"
            )
            self.assertTrue(decision.is_strict)

    def test_prompt_normal_commands(self) -> None:
        """通常のインストール・ビルド・コミットが PROMPT になること"""
        normal_commands = [
            "npm install express",
            "pip install -r requirements.txt",
            "python build_exe.py",
            "git add .",
            "git commit -m 'feat: add feature'",
            "git push origin main",
            "docker build -t app .",
        ]
        for cmd in normal_commands:
            decision = self.engine.evaluate(cmd)
            self.assertEqual(
                decision.risk_level,
                RiskLevel.PROMPT,
                f"コマンド '{cmd}' は PROMPT と判定されるべきですが、{decision.risk_level} でした (理由: {decision.reason})"
            )
            self.assertTrue(decision.requires_human_approval)

    def test_custom_rule_addition(self) -> None:
        """ユーザー定義のカスタムホワイトリスト/ブラックリストが機能すること"""
        # カスタムAuto-Allow追加
        self.engine.add_auto_allow_pattern(r"^cargo\s+build$")
        decision = self.engine.evaluate("cargo build")
        self.assertEqual(decision.risk_level, RiskLevel.AUTO_ALLOW)

        # カスタムStrict追加
        self.engine.add_strict_pattern(r"^custom_deploy.*--prod$")
        decision = self.engine.evaluate("custom_deploy --prod")
        self.assertEqual(decision.risk_level, RiskLevel.STRICT)


if __name__ == "__main__":
    unittest.main()
