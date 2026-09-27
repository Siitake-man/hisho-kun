#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_approval_policy_sensitive.py

AUTO_ALLOW の締め付け（機密読み取り・pytest プラグイン読込・電源操作）の回帰テスト。

背景: `^cat` / `^grep` / `^pytest` の前方一致だけで自動許可していたため、
`cat .env`・`cat ~/.ssh/id_rsa`・`grep -r API_KEY ~`・`pytest -p <plugin>` が
スマホ確認なしで実行でき、`shutdown` も STRICT ではなく PROMPT 止まりだった。
"""

import unittest

from agent_adapter import RiskLevel
from approval_policy import ApprovalPolicyEngine


class _PolicyCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = ApprovalPolicyEngine()

    def assertLevel(self, commands, expected: RiskLevel) -> None:
        for cmd in commands:
            with self.subTest(cmd=cmd):
                decision = self.engine.evaluate(cmd)
                self.assertEqual(
                    decision.risk_level, expected,
                    f"'{cmd}' は {expected.name} であるべき (actual={decision.risk_level.name}, reason={decision.reason})",
                )


class TestSecretFileReadsAreNotAutoAllowed(_PolicyCase):

    def test_env_files_require_prompt(self) -> None:
        """.env 系（API キー格納）の閲覧は PROMPT（人間確認）になること。"""
        self.assertLevel([
            "cat .env",
            "cat ./.env.local",
            "head -n 5 config/.env",
            "tail .env.production",
            "type .env",
            r"type C:\Users\x\project\.env",
            "git show HEAD:.env",
        ], RiskLevel.PROMPT)

    def test_env_templates_stay_auto_allowed(self) -> None:
        """.env.example 等のテンプレートは機密ではないため AUTO_ALLOW のままであること。"""
        self.assertLevel([
            "cat .env.example",
            "cat .env.sample",
            "type .env.template",
        ], RiskLevel.AUTO_ALLOW)

    def test_credential_files_require_prompt(self) -> None:
        """~/.ssh・クラウド認証情報・証明書鍵等の閲覧は PROMPT になること。"""
        self.assertLevel([
            "ls ~/.ssh",
            "cat ~/.ssh/config",
            "cat ~/.ssh/id_ed25519.pub",
            "cat ~/.aws/credentials",
            "cat ~/.kube/config",
            "cat ~/.docker/config.json",
            "cat ~/.netrc",
            "cat ~/.git-credentials",
            "cat ~/.npmrc",
            "cat ~/.pypirc",
            "cat credentials.json",
            "cat client_secret_1234.json",
            "cat secrets.yaml",
            "cat server.pem",
            "cat tls.key",
            "cat .sync_token",
        ], RiskLevel.PROMPT)

    def test_private_keys_are_strict(self) -> None:
        """秘密鍵そのもの・パスワードハッシュの参照は STRICT（赤警告・二重確認）になること。"""
        self.assertLevel([
            "cat ~/.ssh/id_rsa",
            "cat ~/.ssh/id_ed25519",
            "head -1 /home/user/.ssh/id_ecdsa",
            r"type C:\Users\x\.ssh\id_rsa",
            "cat putty.ppk",
            "ls ~/.gnupg",
            "cat /etc/shadow",
        ], RiskLevel.STRICT)


class TestSecretSearchesAreNotAutoAllowed(_PolicyCase):

    def test_secret_keyword_search_requires_prompt(self) -> None:
        """API キー・トークン・パスワード等の検索は（.env 等の中身を表示し得るため）PROMPT になること。"""
        self.assertLevel([
            "grep -r API_KEY ~",
            "grep -r API_KEY .",
            "grep -rn OPENAI_API_KEY src",
            "rg -i password",
            "grep -ri secret .",
            "grep -rn token .",
            "grep -r 'Bearer' .",
            "findstr /s /i apikey *.*",
        ], RiskLevel.PROMPT)

    def test_home_or_root_wide_search_requires_prompt(self) -> None:
        """ホーム・ルートそのものを対象にした横断検索は PROMPT になること。"""
        self.assertLevel([
            "grep -r foo ~",
            "grep -r foo /",
            "rg foo ~/",
            "find ~ -name '*.txt'",
            "find / -name id_rsa.pub",
            "find /home -name '*.db'",
        ], RiskLevel.PROMPT)

    def test_ordinary_code_search_stays_auto_allowed(self) -> None:
        """通常のコード検索（機密キーワードを含まない）は AUTO_ALLOW のままであること。"""
        self.assertLevel([
            "grep -r 'pattern' .",
            "grep -rn TODO src",
            "rg tokenize src",
            "grep -r shutdown .",
            "find . -name '*.py'",
            "cat README.md",
            "cat tools/scan_git_secrets.py",
        ], RiskLevel.AUTO_ALLOW)


class TestPytestPluginLoadingIsNotAutoAllowed(_PolicyCase):

    def test_plugin_and_config_override_options_require_prompt(self) -> None:
        """任意モジュール読込・設定差し替えとなる pytest オプションは PROMPT になること。"""
        self.assertLevel([
            "pytest -p evil_plugin",
            "pytest -pevil_plugin",
            "pytest tests/ -p evil_plugin",
            "pytest --pyargs some.package",
            "pytest -o addopts=-pevil",
            "pytest --override-ini=addopts=-pevil",
            "pytest -c /tmp/other.ini",
            "pytest --config-file=/tmp/other.toml",
            "pytest --rootdir=/tmp",
            "pytest --confcutdir /tmp",
        ], RiskLevel.PROMPT)

    def test_regular_pytest_stays_auto_allowed(self) -> None:
        """通常の pytest 実行・プラグイン無効化 (-p no:xxx) は AUTO_ALLOW のままであること。"""
        self.assertLevel([
            "pytest",
            "pytest tests/ -v",
            "pytest -k 'test_a' -q",
            "pytest -x --tb=short",
            "pytest -p no:cacheprovider tests/",
            "pytest -pno:randomly",
        ], RiskLevel.AUTO_ALLOW)


class TestPowerCommandsAreStrict(_PolicyCase):

    def test_shutdown_family_is_strict(self) -> None:
        """シャットダウン・再起動・停止は STRICT になること（ラッパー経由・パス修飾を含む）。"""
        self.assertLevel([
            "shutdown -h now",
            "shutdown /s /t 0",
            "shutdown -r now",
            "reboot",
            "halt",
            "poweroff",
            "/sbin/shutdown -r now",
            "shutdown.exe /r",
            "systemctl poweroff",
            "systemctl reboot",
            "init 0",
            "cmd /c shutdown /s",
            "timeout 5 shutdown",
            'bash -c "shutdown -h now"',
            "Stop-Computer",
            "Restart-Computer -Force",
            "git status && reboot",
        ], RiskLevel.STRICT)

    def test_power_words_as_arguments_are_not_strict(self) -> None:
        """検索語・メッセージ内の shutdown 等は電源操作として誤検知しないこと。"""
        self.assertLevel(["grep -r shutdown .", "echo reboot", "cat shutdown.log"], RiskLevel.AUTO_ALLOW)
        self.assertLevel(["git commit -m 'fix shutdown'", "systemctl status nginx"], RiskLevel.PROMPT)


if __name__ == "__main__":
    unittest.main()
