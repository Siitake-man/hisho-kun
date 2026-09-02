#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - git履歴機密スキャナ 単体テスト (tests/test_secret_scanner.py)

tools/scan_git_secrets.py の検出パターンとマスク処理を検証する
(Phase J GitHub公開準備の機密監査ゲート用ツール)。
"""

import re
import sys
import unittest
from pathlib import Path

# tools/ を import パスへ追加
TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from scan_git_secrets import SECRET_PATTERNS, find_secrets, mask_secret


class TestSecretScanner(unittest.TestCase):
    """機密パターン検出とマスク処理を検証する"""

    def test_mask_secret_hides_value_but_keeps_prefix(self):
        """機密値は先頭6文字+***MASKED*** にマスクされる"""
        line = '  "api_key": "sk-abcdef1234567890abcdef123456"'
        masked = mask_secret(line)
        self.assertNotIn("abcdef1234567890", masked, "機密値がそのまま残っている")
        self.assertIn("sk-abc***MASKED***", masked)

    def test_find_secrets_detects_google_api_key(self):
        """Google API Key (AIza...) を検出する"""
        findings = find_secrets("+    \"key\": \"AIzaSyA-1234567890abcdefghijklmnopqrstuvw\"")
        labels = [label for label, _ in findings]
        self.assertTrue(any("Google API Key" in label for label in labels))

    def test_find_secrets_detects_openai_style_key(self):
        """OpenAI 互換 Key (sk-...) を検出する"""
        findings = find_secrets("+API_KEY=sk-proj-abcdefghij1234567890ABCDE")
        self.assertTrue(len(findings) >= 1)

    def test_find_secrets_detects_private_key_block(self):
        """秘密鍵ブロックを検出する"""
        findings = find_secrets("+-----BEGIN RSA PRIVATE KEY-----")
        self.assertTrue(any("Private Key" in label for label, _ in findings))

    def test_find_secrets_clean_text_returns_empty(self):
        """機密を含まないテキストは検出ゼロ (誤検知なし)"""
        self.assertEqual(find_secrets("+token = get_sync_token_manager().token"), [])
        self.assertEqual(find_secrets("+AUTH = f'Bearer {syncToken}'"), [])

    def test_all_patterns_have_labels(self):
        """全パターンに重複のないラベルが付与され、正規表現がコンパイル済みであること"""
        labels = [label for label, _ in SECRET_PATTERNS]
        self.assertTrue(all(labels), "空ラベルが存在する")
        self.assertEqual(len(labels), len(set(labels)), "ラベルが重複している")
        for label, pattern in SECRET_PATTERNS:
            self.assertIsInstance(pattern, re.Pattern, f"{label} のパターンが未コンパイル")


if __name__ == "__main__":
    unittest.main(verbosity=2)
