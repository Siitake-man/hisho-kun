#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - 用語境界（MentisDB ≠ 知識の宝庫）の回帰テスト (tests/test_terminology_boundary.py)

2026-09-16 ボス指定の恒久ルール:
- 「知識の宝庫 (Knowledge Vault)」＝ 秘書くんアプリ内のボス知見ストア
  （storage/insight_repo.py・user_insights テーブル / neo_secretary.db）。
  `remember_boss_insight` / `get_boss_insights` (neo_hisho_bridge) が読み書きする。
- 「MentisDB」＝ Cline環境側の汎用エージェント記憶MCP。**別物・混同禁止**。
- 「codebase-memory-mcp」＝ コード知識グラフ ＋ ADR (`manage_adr`)。

背景（2026-09-14 呼称刷新）:
    アプリ内知見蓄積機能は初期に「MentisDB型」と呼称され、2026-09-14 に
    「知識の宝庫 (Knowledge Vault)」へ全面改名済み。しかし active_context.md や
    .agents/skills 配下に「MentisDB ＝ remember_boss_insight」と読める記述が残存し、
    2026-09-16 の Cline セッションで実際に混同（別物を同一視）が発生した。
    本テストは、その混同が **エージェントが最初に読むファイル群へ再流入した瞬間に
    Red で検知** するための番人 (Canary) である。

TDD: 混同記述が残っている状態では Red で落ちる。
"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 混同ではなく「境界の明示」を意図した行にのみ許される注記キーワード
BOUNDARY_MARKERS = ("別物", "旧呼称", "汎用エージェント記憶MCP", "混同禁止", "現在の", "呼称刷新")


def _read(rel: str) -> str:
    return (PROJECT_ROOT / rel).read_text(encoding="utf-8")


class TestTerminologyBoundary(unittest.TestCase):
    """MentisDB と 知識の宝庫 を同一視する記述の再流入防止契約"""

    def test_agents_md_declares_memory_boundary(self) -> None:
        """AGENTS.md が「知識の宝庫」「MentisDB」「別物」を明示して定義していること"""
        source = _read("AGENTS.md")
        for keyword in ("知識の宝庫", "MentisDB", "別物", "remember_boss_insight"):
            with self.subTest(keyword=keyword):
                self.assertIn(keyword, source, "AGENTS.md に境界規約がありません")

    def test_agent_facing_docs_do_not_pair_mentisdb_with_vault_tools(self) -> None:
        """MentisDB と remember_boss_insight（知識の宝庫のツール）を同一視する行を禁止する

        active_context.md は session-start で必ず読まれるため、
        「MentisDB ＝ remember_boss_insight」と読める行は原則禁止。
        境界を明示する注記行（別物/旧呼称/汎用エージェント記憶MCP などを含む行）のみ許可する。
        """
        source = _read("active_context.md")
        for lineno, line in enumerate(source.splitlines(), start=1):
            if "MentisDB" not in line:
                continue
            with self.subTest(lineno=lineno, line=line.strip()):
                self.assertTrue(
                    any(marker in line for marker in BOUNDARY_MARKERS),
                    f"active_context.md:{lineno} に MentisDB の混同/無注記利用があります",
                )

    def test_agent_facing_docs_pair_mentisdb_with_vault_tools_are_annotated(self) -> None:
        """remember_boss_insight 行の MentisDB 表記が境界注記つきであること"""
        source = _read("active_context.md")
        for lineno, line in enumerate(source.splitlines(), start=1):
            if "remember_boss_insight" not in line:
                continue
            with self.subTest(lineno=lineno):
                if "MentisDB" in line:
                    self.assertTrue(
                        any(marker in line for marker in BOUNDARY_MARKERS),
                        f"active_context.md:{lineno} で remember_boss_insight を MentisDB と同一視しています",
                    )

    def test_custom_skills_do_not_mention_mentisdb(self) -> None:
        """.agents/skills 配下の SKILL.md に MentisDB 表記が残っていないこと（ADR/知識の宝庫へ誘導）"""
        skill_files = sorted((PROJECT_ROOT / ".agents" / "skills").glob("*" + "/" + "SKILL.md"))
        self.assertTrue(skill_files, "SKILL.md が1つも見つかりません")
        for path in skill_files:
            with self.subTest(skill=path.name):
                self.assertNotIn(
                    "MentisDB", path.read_text(encoding="utf-8"),
                    f"{path.name} に MentisDB 表記が残っています (知識の宝庫 / codebase-memory ADR に書き換えること)",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
