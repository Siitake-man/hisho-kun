#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - OpenCode エージェント同期ジェネレータの単体テスト (tests/test_sync_opencode_agents.py)

背景 (P1 / 2026-09-21 独立査読 quality-reviewer):
    `tools/sync_opencode_agents.py` は「正本(.agents/agents) → 生成物(.opencode/agents)」の
    一方向同期と権限翻訳を担う中核ツールであるにもかかわらず、テストが存在しなかった。
    査読で以下が実測されたため、契約として凍結する（AGENTS.md §2.9 TDD の履行）:

      - P1-1: エージェント権限に shell の allow を再宣言すると、ルールは後勝ちで
              グローバル deny を上書きし得る（＝複合コマンドで破壊的 deny が無効化される）
      - P1-2: 正本の `mainAgent` / `subagent` 宣言が捨てられ、mode が subagent 固定だった
      - P1-3: `--check` が孤立した生成物（正本の無い .md）を検知できない
      - P1-4: 検証警告が終了コードに反映されない（CI が緑のまま見逃す）
      - P1-5: 権限ポリシー未定義の新規エージェントで KeyError 即死する
      - P0  : `opencode.json` の `git branch *` allow が `git branch -D/-f` を無承認で通す
"""

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import tools.sync_opencode_agents as sync_mod  # noqa: E402


# =============================================================================
# テスト用ヘルパー
# =============================================================================

SOURCE_TEMPLATE = """---
name: {name}
description: {description}
mainAgent: {main_agent}
subagent: true
tools:
  - view_file
  - grep_search
---

# {name} のテスト用本文

正本の本文がそのまま生成物へ引き継がれることを検証するためのダミー本文。
"""


def strip_jsonc(text: str) -> str:
    """JSONC (コメント付きJSON) からコメントと末尾カンマを除去する。

    Args:
        text: JSONC 文字列。

    Returns:
        str: 純粋なJSON文字列。
    """
    out = []
    i = 0
    n = len(text)
    in_str = False
    esc = False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        out.append(ch)
        i += 1
    import re

    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def load_jsonc(path: Path) -> Dict[str, Any]:
    """JSONC ファイルを辞書として読み込む。

    Args:
        path: 対象ファイルパス。

    Returns:
        Dict[str, Any]: パース結果。
    """
    import json

    return json.loads(strip_jsonc(path.read_text(encoding="utf-8")))


def parse_frontmatter(markdown: str) -> Dict[str, Any]:
    """生成物 Markdown の frontmatter を辞書として返す。

    Args:
        markdown: Markdown 全文。

    Returns:
        Dict[str, Any]: frontmatter 辞書。
    """
    parts = markdown.split("---", 2)
    return yaml.safe_load(parts[1]) or {}


class SyncTestBase(unittest.TestCase):
    """一時ディレクトリ上で同期処理を検証する基底クラス（Seam 注入）。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.source_dir = self.root / "src"
        self.target_dir = self.root / "dst"
        self.source_dir.mkdir()
        self.target_dir.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write_source(
        self,
        name: str,
        *,
        description: str = "テスト用エージェントの説明文。",
        main_agent: bool = False,
    ) -> Path:
        """正本ファイルを1件作成する。

        Args:
            name: エージェント名（ファイル名と frontmatter の name を一致させる）。
            description: description の値（空文字で警告ケースを再現できる）。
            main_agent: mainAgent フラグ。

        Returns:
            Path: 作成した正本のパス。
        """
        path = self.source_dir / ("%s.md" % name)
        path.write_text(
            SOURCE_TEMPLATE.format(
                name=name,
                description=description,
                main_agent="true" if main_agent else "false",
            ),
            encoding="utf-8",
        )
        return path

    def sync(self, check_only: bool = False, prune: bool = False) -> int:
        """テスト用ディレクトリを対象に同期を実行する。

        Args:
            check_only: 差分検知のみ行うか。
            prune: 孤立した生成物を削除するか。

        Returns:
            int: 終了コード。
        """
        return sync_mod.sync(
            check_only=check_only,
            source_dir=self.source_dir,
            target_dir=self.target_dir,
            prune=prune,
        )

    def read_generated(self, name: str) -> str:
        """生成物を読み出す。

        Args:
            name: エージェント名。

        Returns:
            str: 生成物の全文。
        """
        return (self.target_dir / ("%s.md" % name)).read_text(encoding="utf-8")


# =============================================================================
# 1. 冪等性・決定性
# =============================================================================


class TestDeterminism(SyncTestBase):
    """生成物が決定的であり、何度実行しても同じ結果になること。"""

    def test_sync_is_idempotent(self) -> None:
        """2回同期しても生成物が1バイトも変わらないこと（冪等性）"""
        self.write_source("python-architect")

        self.assertEqual(self.sync(), 0)
        first = self.read_generated("python-architect")
        self.assertEqual(self.sync(), 0)

        self.assertEqual(self.read_generated("python-architect"), first)

    def test_check_returns_zero_after_sync(self) -> None:
        """同期直後の --check はドリフト0で終了コード0になること"""
        self.write_source("python-architect")
        self.sync()

        self.assertEqual(self.sync(check_only=True), 0)

    def test_check_detects_hand_edited_generated_file(self) -> None:
        """生成物を手編集したら --check がドリフトとして検知すること"""
        self.write_source("python-architect")
        self.sync()
        target = self.target_dir / "python-architect.md"
        target.write_text(target.read_text(encoding="utf-8") + "\n手編集\n", encoding="utf-8")

        self.assertEqual(self.sync(check_only=True), 1)


# =============================================================================
# 2. 孤立生成物の検知（P1-3）
# =============================================================================


class TestOrphanDetection(SyncTestBase):
    """正本に対応しない生成物（改名の残骸・ゴーストエージェント）の検知。"""

    def test_check_detects_orphan_generated_file(self) -> None:
        """正本に存在しない .md が残っていたら --check が終了コード1で検知すること（P1-3）"""
        self.write_source("python-architect")
        (self.target_dir / "ghost-agent.md").write_text(
            "---\nmode: subagent\n---\n\n残骸\n", encoding="utf-8"
        )

        self.assertEqual(self.sync(check_only=True), 1)

    def test_sync_without_prune_keeps_orphan_file(self) -> None:
        """--prune 未指定では孤立ファイルを勝手に削除しないこと（AGENTS.md 3. 同意なき削除の禁止）"""
        self.write_source("python-architect")
        orphan = self.target_dir / "ghost-agent.md"
        orphan.write_text("残骸\n", encoding="utf-8")

        self.sync()

        self.assertTrue(orphan.exists())

    def test_sync_with_prune_removes_orphan_file(self) -> None:
        """--prune を明示指定した場合のみ孤立ファイルを削除すること"""
        self.write_source("python-architect")
        orphan = self.target_dir / "ghost-agent.md"
        orphan.write_text("残骸\n", encoding="utf-8")

        self.sync(prune=True)

        self.assertFalse(orphan.exists())


# =============================================================================
# 3. 終了コード契約（P1-4）
# =============================================================================


class TestExitCodeContract(SyncTestBase):
    """検証警告が CI を落とせること（終了コード契約）。"""

    def test_check_fails_when_description_is_empty(self) -> None:
        """description が空の正本は --check で終了コード1（OpenCodeが起動候補に出せないため）（P1-4）"""
        self.write_source("python-architect", description="")

        self.assertEqual(self.sync(check_only=True), 1)

    def test_check_fails_when_name_differs_from_filename(self) -> None:
        """frontmatter の name とファイル名が不一致なら --check は終了コード1"""
        path = self.source_dir / "wrong-name.md"
        path.write_text(
            SOURCE_TEMPLATE.format(
                name="python-architect", description="説明", main_agent="false"
            ),
            encoding="utf-8",
        )

        self.assertEqual(self.sync(check_only=True), 1)


# =============================================================================
# 4. 権限ポリシー未定義への耐性（P1-5）
# =============================================================================


class TestMissingPolicy(SyncTestBase):
    """新規エージェント追加時にクラッシュせず、修正方法を提示すること。"""

    def test_write_mode_raises_actionable_error(self) -> None:
        """権限ポリシー未定義なら、修正箇所を明示した ValueError を送出すること（P1-5）"""
        self.write_source("brand-new-agent")

        with self.assertRaises(ValueError) as ctx:
            self.sync()

        self.assertIn("AGENT_POLICIES", str(ctx.exception))

    def test_check_mode_returns_error_instead_of_crashing(self) -> None:
        """--check ではクラッシュせず終了コード1で報告すること（P1-5）"""
        self.write_source("brand-new-agent")

        self.assertEqual(self.sync(check_only=True), 1)


# =============================================================================
# 5. mode 導出（P1-2）
# =============================================================================


class TestModeMapping(SyncTestBase):
    """正本の mainAgent / subagent 宣言が mode に忠実に反映されること。"""

    def test_mode_all_when_main_agent_and_subagent(self) -> None:
        """mainAgent:true + subagent:true → mode:all（Antigravity と同一の選択可能性）(P1-2)"""
        self.write_source("hisho-orchestrator", main_agent=True)
        self.sync()

        self.assertEqual(parse_frontmatter(self.read_generated("hisho-orchestrator"))["mode"], "all")

    def test_mode_subagent_when_not_main_agent(self) -> None:
        """mainAgent:false → mode:subagent（subagent 専任）(P1-2)"""
        self.write_source("devils-advocate", main_agent=False)
        self.sync()

        self.assertEqual(parse_frontmatter(self.read_generated("devils-advocate"))["mode"], "subagent")

    def test_every_generated_agent_declares_subagent_capability(self) -> None:
        """正本が subagent:true である以上、全生成物が subagent 起動可能であること"""
        self.write_source("python-architect", main_agent=True)
        self.sync()

        self.assertIn(
            parse_frontmatter(self.read_generated("python-architect"))["mode"],
            ("subagent", "all"),
        )


# =============================================================================
# 6. 「締める方向にのみ働く」不変条件（P1-1）
# =============================================================================


class TestTighteningOnlyInvariant(unittest.TestCase):
    """エージェント権限はグローバル ACL を締める方向にのみ働くこと。"""

    def test_agent_policies_never_grant_shell_allow(self) -> None:
        """エージェント権限で shell の allow を再宣言しないこと（後勝ちでグローバルdenyを無効化し得る）(P1-1)"""
        for name, (permissions, _color) in sync_mod.AGENT_POLICIES.items():
            for rule in permissions:
                with self.subTest(agent=name, rule=rule):
                    self.assertFalse(
                        rule["action"] == "shell" and rule["effect"] == "allow",
                        "%s が shell allow を再宣言している（グローバル deny を上書きし得る）" % name,
                    )

    def test_read_only_agents_deny_edit_shell_subagent(self) -> None:
        """Read-Only エージェントは edit / shell / subagent を deny すること"""
        for name in (
            "task-planner",
            "error-analyst",
            "quality-reviewer",
            "devils-advocate",
            "product-strategist",
            "legal-compliance",
            "visionary-dreamer",
        ):
            actions = {(r["action"], r["effect"]) for r in sync_mod.AGENT_POLICIES[name][0]}
            with self.subTest(agent=name):
                for action in ("edit", "shell", "subagent"):
                    self.assertIn((action, "deny"), actions)

    def test_read_only_agents_cannot_write_via_mcp(self) -> None:
        """Read-Only エージェントは MCP 経由の書き込みツールも deny すること（P2-2）"""
        write_tools = (
            "neo_hisho_bridge_create_task",
            "neo_hisho_bridge_complete_task",
            "neo_hisho_bridge_create_calendar_event",
            "neo_hisho_bridge_remember_boss_insight",
        )
        for name in ("quality-reviewer", "devils-advocate", "legal-compliance"):
            actions = {r["action"] for r in sync_mod.AGENT_POLICIES[name][0]}
            with self.subTest(agent=name):
                for tool in write_tools:
                    self.assertIn(tool, actions)

    def test_orchestrator_cannot_edit_files(self) -> None:
        """オーケストレーターは自らコードを書かない（edit deny）"""
        actions = {(r["action"], r["effect"]) for r in sync_mod.AGENT_POLICIES["hisho-orchestrator"][0]}

        self.assertIn(("edit", "deny"), actions)


# =============================================================================
# 7. プロジェクト Hard ACL の契約（P0 再発防止）
# =============================================================================


@unittest.skipUnless(
    (PROJECT_ROOT / "opencode.json").exists(),
    "opencode.json はローカル専用（.gitignore 対象）のため、無い環境ではスキップする",
)
class TestProjectHardAcl(unittest.TestCase):
    """`opencode.json` の Hard ACL が破壊的操作を無承認で通さないこと（P0 再発防止）。"""

    def setUp(self) -> None:
        self.config = load_jsonc(PROJECT_ROOT / "opencode.json")

    def _resources(self, action: str, effect: str) -> set:
        """指定 action / effect のリソース集合を返す。

        Args:
            action: permission action。
            effect: allow / deny / ask。

        Returns:
            set: resource 文字列の集合。
        """
        return {
            r["resource"]
            for r in self.config.get("permissions", [])
            if r.get("action") == action and r.get("effect") == effect
        }

    def test_git_branch_allow_covers_read_only_forms_only(self) -> None:
        """`git branch` の allow は読み取り専用形のみであること（P0: -D/-f/-m を無承認で通さない）"""
        allows = self._resources("shell", "allow")

        self.assertNotIn("git branch *", allows)
        for resource in allows:
            if resource.startswith("git branch"):
                self.assertTrue(
                    resource == "git branch"
                    or resource.startswith(("git branch --list", "git branch -v", "git branch -a")),
                    "読み取り専用ではない git branch が allow されている: %s" % resource,
                )

    def test_destructive_git_branch_ops_are_denied(self) -> None:
        """`git branch -D/-d/-f/-m/--delete/--force/--move` が deny されていること（P0）"""
        denies = self._resources("shell", "deny")

        for pattern in (
            "*git branch -D*",
            "*git branch -d*",
            "*git branch -f*",
            "*git branch -m*",
            "*git branch --delete*",
            "*git branch --force*",
            "*git branch --move*",
        ):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, denies)

    def test_destructive_core_ops_are_denied(self) -> None:
        """rm -rf / / git reset --hard / git push --force / DROP TABLE / mkfs が deny されていること"""
        denies = self._resources("shell", "deny")

        for pattern in (
            "*rm -rf /*",
            "*git reset --hard*",
            "*git push*--force*",
            "*DROP TABLE*",
            "*mkfs*",
        ):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, denies)

    def test_shell_default_is_ask(self) -> None:
        """シェルの既定が「ボス承認待ち(ask)」であること（人間ゲートを主防御とする）"""
        rules = self.config.get("permissions", [])
        self.assertTrue(rules, "permissions が空である")
        self.assertEqual(rules[0], {"action": "shell", "resource": "*", "effect": "ask"})

    def test_secrets_and_db_edits_require_approval(self) -> None:
        """.env と *.db の編集が ask であること（秘密情報・個人データ保護）"""
        asks = self._resources("edit", "ask")

        for pattern in ("*.env", "*.db"):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, asks)


if __name__ == "__main__":
    unittest.main()
