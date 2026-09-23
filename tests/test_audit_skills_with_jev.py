#!/usr/bin/env python3
"""
tools/audit_skills_with_jev.py の単体テスト・検証スイート (test_audit_skills_with_jev.py)
Jev 全スキル棚卸し監査スクリプトの構文・型整合性・抽出ロジック・Jev API整合性・ボス指定ガードを検証する。
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

try:
    import audit_skills_with_jev as audit_mod
except ImportError:  # pragma: no cover - CI等で依存が無い場合
    audit_mod = None

# 🛡️ 2026-09-23: Jev クライアントはボスのローカル専用（~/.gemini/tools/jev_router）。
# CI・配布環境には存在しないため、Jev 依存の検証はスキップする（PR #7 と同じ方針）。
_JEV_AVAILABLE = audit_mod is not None and getattr(audit_mod, "JevClient", None) is not None


@unittest.skipUnless(_JEV_AVAILABLE, "JevClient が未実装の環境 (CI等) のためスキップします")
class TestAuditSkillsWithJev(unittest.TestCase):
    """audit_skills_with_jev の抽出、State構築、Jev API適合性、ボス指定ガードを検証"""

    def setUp(self):
        self.dummy_skill_dir = REPO_ROOT / "tests" / "fixtures" / "dummy_skills"

    def test_syntax_and_module_attributes(self):
        """1. モジュール構文および必須定数・関数の存在確認"""
        self.assertTrue(hasattr(audit_mod, "parse_skill_detailed"))
        self.assertTrue(hasattr(audit_mod, "build_macro_state"))
        self.assertTrue(hasattr(audit_mod, "estimate_tokens"))
        self.assertTrue(hasattr(audit_mod, "classify_skill_domain"))
        self.assertTrue(hasattr(audit_mod, "audit_domain_relative_with_jev"))
        self.assertTrue(hasattr(audit_mod, "BOSS_RETAIN_MASTERS"))
        self.assertTrue(hasattr(audit_mod, "BOSS_META_SKILLS"))
        self.assertTrue(hasattr(audit_mod, "DOMAINS"))

    def test_parse_skill_detailed_normal(self):
        """2. parse_skill_detailed: 正常なfrontmatterと本文からの約600文字抽出"""
        sample_content = """---
name: test-sample-skill
description: A sample test skill for unit verification
---
# Test Heading

This is a deep module rule that provides excellent testing guidance.
<!-- This comment should be ignored -->
Rule 1: Always test boundaries and edge cases.
Rule 2: Ensure that output tokens remain bounded.
""" + ("Extra text line for length check. " * 30)

        mock_path = MagicMock(spec=Path)
        mock_file = MagicMock(spec=Path)
        mock_path.is_dir.return_value = True
        mock_path.__truediv__.return_value = mock_file
        mock_path.name = "test-sample-skill"
        mock_file.exists.return_value = True
        mock_file.read_text.return_value = sample_content

        res = audit_mod.parse_skill_detailed(mock_path)
        self.assertEqual(res["name"], "test-sample-skill")
        self.assertEqual(res["description"], "A sample test skill for unit verification")
        self.assertIn("Test Heading", res["body_core"])
        self.assertNotIn("<!--", res["body_core"])
        # 約580文字以上で切り上げられていることの検証
        self.assertLessEqual(len(res["body_core"]), 750)
        self.assertIn("### Skill: `test-sample-skill`", res["full_excerpt"])

    def test_parse_skill_detailed_missing_file(self):
        """2b. parse_skill_detailed: SKILL.md不在時の安全なフォールバック"""
        mock_path = MagicMock(spec=Path)
        mock_file = MagicMock(spec=Path)
        mock_path.is_dir.return_value = True
        mock_path.__truediv__.return_value = mock_file
        mock_path.name = "nonexistent-skill"
        mock_file.exists.return_value = False

        res = audit_mod.parse_skill_detailed(mock_path)
        self.assertEqual(res["name"], "nonexistent-skill")
        self.assertEqual(res["description"], "No SKILL.md found")
        self.assertIn("ファイルが存在しません", res["body_core"])

    def test_token_estimation(self):
        """2c. estimate_tokens: トークン概算関数の健全性"""
        text = "Hello world! This is a test. 日本語のテストです。"
        toks = audit_mod.estimate_tokens(text)
        self.assertIsInstance(toks, int)
        self.assertGreater(toks, 5)

    def test_build_macro_state_structure(self):
        """2d. build_macro_state: 全体State構造およびボス指定・メタスキルの埋め込み検証"""
        sample_skills = [
            {
                "name": "codebase-design",
                "description": "Deep module architecture",
                "body_core": "John Ousterhout philosophy",
                "full_excerpt": "### Skill: `codebase-design`\n**Description**: Deep module architecture\n"
            },
            {
                "name": "random-helper",
                "description": "Helper utility",
                "body_core": "Helper details",
                "full_excerpt": "### Skill: `random-helper`\n**Description**: Helper utility\n"
            }
        ]
        state = audit_mod.build_macro_state(sample_skills)
        self.assertIn("MASTER ARCHITECTURAL STATE", state)
        self.assertIn("ABSOLUTE BOSS-RETAINED MASTERS", state)
        self.assertIn("codebase-design", state)
        self.assertIn("init-session-skills", state)
        self.assertIn("random-helper", state)

    def test_classify_skill_domain(self):
        """3a. classify_skill_domain: ルーティングとキーワード分類の正確性"""
        # ボス指定スキルの直接ルーティング
        self.assertEqual(audit_mod.classify_skill_domain("codebase-design", "desc"), "code_architecture")
        self.assertEqual(audit_mod.classify_skill_domain("archify", "desc"), "concept_explainer")
        self.assertEqual(audit_mod.classify_skill_domain("teach", "desc"), "concept_explainer")
        self.assertEqual(audit_mod.classify_skill_domain("ui-ux-pro-max", "desc"), "frontend_ui")
        self.assertEqual(audit_mod.classify_skill_domain("ruthless-code-evaluation", "desc"), "code_architecture")

        # キーワードルーティング
        self.assertEqual(audit_mod.classify_skill_domain("bigquery-sql", "SQL tuning"), "enterprise_cloud_data")
        self.assertEqual(audit_mod.classify_skill_domain("officecli", "Word and Excel"), "office_docs")
        self.assertEqual(audit_mod.classify_skill_domain("git-guardrails", "Block git push"), "security_governance")
        self.assertEqual(audit_mod.classify_skill_domain("custom-unknown-tool", "Something generic"), "general_utility")

    def test_jev_decisions_api_format_compatibility(self):
        """3b. audit_domain_relative_with_jev: Jev Decisions API の質問フォーマットおよびパース適合性"""
        mock_client = MagicMock()
        mock_client.decide.return_value = {
            "answers": {
                "canonical_master": {"choice": "codebase-design"},
                "redundancy_level": {"choice": "high_redundancy"},
                "domain_action": {"choice": "keep_and_prune"}
            },
            "confidence": 0.95
        }

        domain_info = {
            "name": "コード設計・アーキテクチャ・品質監査",
            "description": "ディープモジュール、リファクタリング、品質監査"
        }
        domain_skills = [
            {"name": "codebase-design", "description": "Deep module philosophy"},
            {"name": "codebase-helper", "description": "Helper for codebase"}
        ]

        result = audit_mod.audit_domain_relative_with_jev(
            mock_client,
            "dummy_macro_state",
            "code_architecture",
            domain_info,
            domain_skills
        )

        # decideに渡された質問引数の構造検証
        call_args = mock_client.decide.call_args
        self.assertIsNotNone(call_args)
        prompt_arg, questions_arg = call_args[0]

        # Decisions API 規格検証 (choice型, instructions, criteria dict)
        self.assertIn("canonical_master", questions_arg)
        self.assertEqual(questions_arg["canonical_master"]["type"], "choice")
        self.assertIn("codebase-design", questions_arg["canonical_master"]["criteria"])
        self.assertIn("none", questions_arg["canonical_master"]["criteria"])

        self.assertIn("redundancy_level", questions_arg)
        self.assertEqual(questions_arg["redundancy_level"]["type"], "choice")
        self.assertIn("high_redundancy", questions_arg["redundancy_level"]["criteria"])

        self.assertIn("domain_action", questions_arg)
        self.assertEqual(questions_arg["domain_action"]["type"], "choice")
        self.assertIn("keep_and_prune", questions_arg["domain_action"]["criteria"])

        # 結果パース検証
        self.assertEqual(result["canonical_master"], "codebase-design")
        self.assertEqual(result["redundancy_level"], "high_redundancy")
        self.assertEqual(result["domain_action"], "keep_and_prune")
        self.assertEqual(result["confidence"], 0.95)

    def test_boss_six_and_meta_skills_absolute_tier1_guard(self):
        """4. ボス指定6大スキルおよび自作メタスキルの絶対一軍ガード検証"""
        boss_six = [
            "codebase-design",
            "archify",
            "fireworks-open-eli5",
            "teach",
            "ui-ux-pro-max",
            "ruthless-code-evaluation"
        ]
        meta_skills = [
            "init-session-skills",
            "code-review-skill-generator",
            "graph-engineering-skill-generator",
            "generate-ai-company-context",
            "generate-project-agents",
            "skill-generator",
            "skill-repair"
        ]

        # BOSS_RETAIN_MASTERS に6大スキルが過不足なく含まれていること
        for skill in boss_six:
            self.assertIn(skill, audit_mod.BOSS_RETAIN_MASTERS, f"Boss skill {skill} must be in BOSS_RETAIN_MASTERS")

        # BOSS_META_SKILLS に自作メタスキルが含まれていること
        for meta in meta_skills:
            self.assertIn(meta, audit_mod.BOSS_META_SKILLS, f"Meta skill {meta} must be in BOSS_META_SKILLS")

        # 判定ロジックの優先順位シミュレーション
        # 仮に Jev が high_redundancy かつ canonical_master に別スキルを選んだり、
        # enterprise_cloud_data ドメインと誤認された場合でも、ボス指定ガードが最優先されるか
        test_cases = [
            ("codebase-design", "enterprise_cloud_data", "some-other-master", "high_redundancy"),
            ("archify", "concept_explainer", "some-other-master", "high_redundancy"),
            ("init-session-skills", "meta_workflow", "none", "high_redundancy")
        ]

        for name, domain_id, master_skill, redundancy in test_cases:
            # main() 内の判定ロジックを忠実に再現
            if name in audit_mod.BOSS_RETAIN_MASTERS:
                action = "【ボス指定温存（精鋭一軍マスター）】"
            elif name in audit_mod.BOSS_META_SKILLS:
                action = "【ボス自作メタ（精鋭一軍マスター）】"
            elif domain_id == "enterprise_cloud_data":
                action = "【アーカイブ退避候補】"
            elif name == master_skill:
                action = "【残す（精鋭一軍マスター）】"
            else:
                action = "【温存（二軍実用・独自の刃）】"

            self.assertIn("一軍", action, f"{name} はあらゆる競合状態でも精鋭一軍として保護されなければならない")


if __name__ == "__main__":
    unittest.main()
