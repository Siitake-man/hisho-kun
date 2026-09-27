#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - Jev モデル選択プランナーの単体テスト (tests/test_jev_model_planner.py)

背景 (2026-09-21 ボス要請):
    OpenCode 側では「サブエージェントごとに最適なモデルを Jev に選ばせる」機能を追加する。
    一方 Antigravity 側は**モデル指定を見ると直列化する**ため、既存の2ツール契約
    (`jev_route_agent` / `jev_guard_command`) を **1バイトも変えてはならない**。

本テストが凍結する契約:
    1. モデル候補は **OpenCode GO 契約**の実在モデルのみ（コスト帯で自動/承認に分類）
    2. 既定では**承認帯を候補に入れない**（構造で高コストを防ぐ）
    3. 高コストモデルを使う場合は `requires_approval=True` を返す（スマホ承認へ誘導）
    4. Jev がエラーを返したら**サイレント偽装せず透過通知**する（フェイルファスト）
    5. **Antigravity 側の契約は不変**（2ツールのまま / 出力にモデル情報が漏れない）
    6. 2つのサーバーは**同一の関数オブジェクトを共有**する（ドリフトの構造的根絶）

主要モデルの価格 (USD / 100万トークン, 2026-09-21 実測):
    deepseek-v4.1-flash  in 0.15 / out 0.60   ← 実装の既定（ボス指定）
    glm-5.3-flash        in 0.15 / out 0.50   ← 実装・検証の既定（ボス指定）
    qwen3.8-flash        in 0.15 / out 0.47
    mimo-v2.5            in 0.14 / out 0.28   ← 最安
    glm-5.3              in 1.40 / out 4.40   ← 承認帯（監査用）
    kimi-k3              in 3.00 / out 15.00  ← 承認帯（最高峰）
"""

import importlib
import json
import os
import re
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

#: Jev 関連資産の配置先（Antigravity と共通のグローバル資産。環境変数 JEV_ROUTER_DIR で上書き可）
JEV_DIR = Path(os.environ.get("JEV_ROUTER_DIR") or (Path.home() / ".gemini" / "tools" / "jev_router"))
#: Antigravity / OpenCode のグローバル設定ファイル（実行ユーザーのホーム配下）
ANTIGRAVITY_MCP_CONFIG = Path.home() / ".gemini" / "config" / "mcp_config.json"
OPENCODE_GLOBAL_CONFIG = Path.home() / ".config" / "opencode" / "opencode.jsonc"
if str(JEV_DIR) not in sys.path:
    sys.path.insert(0, str(JEV_DIR))


def _load(module_name: str) -> Optional[Any]:
    """モジュールを読み込む（未実装なら None を返して Red を可視化する）。

    Args:
        module_name: 読み込むモジュール名。

    Returns:
        Optional[Any]: モジュール（未実装なら None）。
    """
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


model_catalog = _load("model_catalog")
jev_planner = _load("jev_mcp_planner")
jev_core = _load("jev_mcp_server")
jev_client_mod = _load("jev_client")

#: 実装の既定として使う低コストモデル（ボス指定）
CHEAP_IMPLEMENTATION_MODELS = ("opencode-go/deepseek-v4.1-flash", "opencode-go/glm-5.3-flash")


class TestModelCatalogBase(unittest.TestCase):
    """model_catalog.py の契約（Red の可視化のため skipIf で保護）。"""

    def setUp(self) -> None:
        if model_catalog is None:
            self.skipTest("model_catalog.py が未実装です（Red）")


class TestGoContractCatalog(TestModelCatalogBase):
    """GO契約のスナップショットと候補生成の契約。"""

    def test_snapshot_contains_low_cost_implementation_models(self) -> None:
        """スナップショットに実装用の低コストモデル（ボス指定）が含まれること"""
        refs = {entry[0] if isinstance(entry, (list, tuple)) else entry for entry in model_catalog.GO_CONTRACT_SNAPSHOT}
        for ref in ("deepseek-v4.1-flash", "glm-5.3-flash"):
            with self.subTest(model=ref):
                self.assertIn(ref, refs)

    def test_classify_tier_boundary(self) -> None:
        """コスト帯の境界が正しいこと（< $1.0/M out = auto、>= は approval）"""
        self.assertEqual(model_catalog.classify_tier(0.28), "auto")
        self.assertEqual(model_catalog.classify_tier(0.99), "auto")
        self.assertEqual(model_catalog.classify_tier(1.0), "approval")
        self.assertEqual(model_catalog.classify_tier(15.0), "approval")

    def test_default_candidates_exclude_approval_tier(self) -> None:
        """既定の候補に承認帯（高コスト）が入らないこと（構造で高コストを防ぐ）"""
        candidates = model_catalog.build_candidates(include_approval_tier=False)
        tiers = {c["tier"] for c in candidates}

        self.assertTrue(candidates, "候補が空である")
        self.assertEqual(tiers, {"auto"})
        for candidate in candidates:
            self.assertLess(candidate["cost_out"], model_catalog.AUTO_TIER_MAX_OUTPUT_COST)

    def test_candidates_include_approval_tier_when_requested(self) -> None:
        """明示指定時のみ承認帯が候補に含まれること"""
        candidates = model_catalog.build_candidates(include_approval_tier=True)
        tiers = {c["tier"] for c in candidates}

        self.assertIn("auto", tiers)
        self.assertIn("approval", tiers)

    def test_contributor_models_are_excluded_by_default(self) -> None:
        """データ提供オプトインが必要な contributor 系は既定で候補から除外されること

        実測: `muse-spark-1.3-contributor` は実行時に
        "This model collects data used to improve its quality and requires explicit opt in" で失敗する。
        """
        candidates = model_catalog.build_candidates(include_approval_tier=True)
        refs = [c["ref"] for c in candidates if c.get("requires_optin")]

        self.assertEqual(refs, [])

    def test_estimate_cost_formula(self) -> None:
        """推定コストが (入力トークン×入力単価 + 出力トークン×出力単価) で算出されること"""
        cost = model_catalog.estimate_cost(0.15, 0.60, in_tokens=50_000, out_tokens=5_000)

        self.assertAlmostEqual(cost, 0.0075 + 0.003, places=6)

    def test_role_defaults_for_implementation_are_cheapest(self) -> None:
        """実装ロールの既定候補が低コストモデル（ボス指定）であること"""
        defaults = model_catalog.suggest_role_defaults("python-architect")

        self.assertTrue(defaults)
        for ref in defaults:
            with self.subTest(model=ref):
                self.assertIn(ref, CHEAP_IMPLEMENTATION_MODELS)

    def test_role_defaults_for_audit_include_approval_tier(self) -> None:
        """監査ロールの既定候補に承認帯（高コスト）が含まれること（＝承認が要る）"""
        defaults = model_catalog.suggest_role_defaults("quality-reviewer")
        costs = {model_catalog.get_cost(model_catalog.ensure_ref(ref)) for ref in defaults}

        self.assertTrue(any(c is not None and c[1] >= model_catalog.AUTO_TIER_MAX_OUTPUT_COST for c in costs))

    def test_high_stakes_roles_get_strength_instruction(self) -> None:
        """監査系ロールには「最強候補を選べ」という指示が与えられること（安値バイアスの是正）"""
        audit_text = model_catalog.build_instructions("quality-reviewer")
        impl_text = model_catalog.build_instructions("python-architect")

        self.assertIn("HIGH-STAKES", audit_text)
        self.assertIn("STRONGEST", audit_text)
        self.assertIn("cost-effective", impl_text)
        self.assertNotIn("HIGH-STAKES", impl_text)


class TestJevSelectModels(unittest.TestCase):
    """JevClient.select_models() の契約（Jev API はモックして検証する）。"""

    def setUp(self) -> None:
        if jev_client_mod is None or not hasattr(jev_client_mod, "JevClient"):
            self.skipTest("jev_client.py または JevClient が未実装です（Red）")
        self.client = jev_client_mod.JevClient(api_key="dummy-key-for-test")
        self.assertTrue(
            hasattr(self.client, "select_models"),
            "JevClient.select_models() が未実装です（Red）",
        )

    def _canned_decision(self, chosen: Dict[str, str], confidence: float = 0.9) -> Dict[str, Any]:
        """Jev の応答を模した辞書を組み立てる。

        Args:
            chosen: {question_key: choice} の対応。
            confidence: 確信度。

        Returns:
            Dict[str, Any]: Jev 応答のモック。
        """
        answers = {
            key: {"type": "choice", "choice": value, "confidence": confidence, "probabilities": {value: 1.0}}
            for key, value in chosen.items()
        }
        return {"answers": answers, "usage": {"cost": 0.0003}}

    def test_fail_fast_when_jev_returns_error(self) -> None:
        """Jev がエラーを返したら、サイレント偽装せず error を透過すること（フェイルファスト）"""
        with patch.object(jev_client_mod.JevClient, "decide", return_value={"error": "HTTPError 503"}):
            result = self.client.select_models(
                task_description="テスト",
                agent_names=["agent-tester"],
                candidates=model_catalog.build_candidates(include_approval_tier=False) if model_catalog else [],
            )

        self.assertIn("error", result)
        self.assertIn("503", str(result["error"]))
        self.assertNotIn("selections", result)

    def test_empty_candidates_returns_error(self) -> None:
        """候補が空ならエラーを返すこと（推測でモデルを決めない）"""
        result = self.client.select_models(
            task_description="テスト",
            agent_names=["agent-tester"],
            candidates=[],
        )

        self.assertIn("error", result)

    def test_default_call_excludes_approval_tier_from_criteria(self) -> None:
        """既定呼び出しでは、承認帯モデルが Jev の選択肢に含まれないこと（構造で防ぐ）"""
        captured: Dict[str, Any] = {}

        def fake_decide(state: str, questions: Dict[str, Any]) -> Dict[str, Any]:
            captured["questions"] = questions
            return self._canned_decision({"model_for_agent-tester": "opencode-go/glm-5.3-flash"})

        candidates = model_catalog.build_candidates(include_approval_tier=False)
        with patch.object(jev_client_mod.JevClient, "decide", side_effect=fake_decide):
            result = self.client.select_models(
                task_description="テスト",
                agent_names=["agent-tester"],
                candidates=candidates,
            )

        self.assertNotIn("error", result)
        criteria = captured["questions"]["model_for_agent-tester"]["criteria"]
        # 承認帯（高コスト）が Jev の選択肢に一切含まれないこと（構造で防ぐ）
        for ref in criteria:
            cost = model_catalog.get_cost(ref)
            self.assertIsNotNone(cost, "候補の価格が取得できません: %s" % ref)
            self.assertLess(cost[1], model_catalog.AUTO_TIER_MAX_OUTPUT_COST, "承認帯が混入: %s" % ref)

    def test_marks_requires_approval_when_expensive_model_selected(self) -> None:
        """承認帯が選ばれたら requires_approval=True を返すこと（スマホ承認へ誘導）"""
        candidates = model_catalog.build_candidates(include_approval_tier=True)
        with patch.object(
            jev_client_mod.JevClient,
            "decide",
            return_value=self._canned_decision({"model_for_quality-reviewer": "opencode-go/glm-5.3"}),
        ):
            result = self.client.select_models(
                task_description="重大監査",
                agent_names=["quality-reviewer"],
                candidates=candidates,
                include_approval_tier=True,
            )

        selection = result["selections"]["quality-reviewer"]
        self.assertEqual(selection["tier"], "approval")
        self.assertTrue(selection["requires_approval"])
        self.assertTrue(result["approval_required"])

    def test_returns_estimated_cost(self) -> None:
        """推定コストが結果に含まれること（承認時にボスへ提示する）"""
        with patch.object(
            jev_client_mod.JevClient,
            "decide",
            return_value=self._canned_decision({"model_for_agent-tester": "opencode-go/glm-5.3-flash"}),
        ):
            result = self.client.select_models(
                task_description="テスト",
                agent_names=["agent-tester"],
                candidates=model_catalog.build_candidates(include_approval_tier=False),
            )

        selection = result["selections"]["agent-tester"]
        self.assertGreater(selection["estimated_cost_usd"], 0.0)
        self.assertGreater(result["total_estimated_cost_usd"], 0.0)

    def test_low_cost_selection_does_not_require_approval(self) -> None:
        """常用帯のみなら approval_required=False であること（摩擦ゼロ）"""
        with patch.object(
            jev_client_mod.JevClient,
            "decide",
            return_value=self._canned_decision({"model_for_agent-tester": "opencode-go/mimo-v2.5"}),
        ):
            result = self.client.select_models(
                task_description="テスト",
                agent_names=["agent-tester"],
                candidates=model_catalog.build_candidates(include_approval_tier=False),
            )

        self.assertFalse(result["approval_required"])
        self.assertEqual(result["selections"]["agent-tester"]["tier"], "auto")

    def test_tolerates_raw_live_candidates_without_tier(self) -> None:
        """呼び出し側が生のライブ一覧（`tier` 未指定）を渡しても動作すること（堅牢化）

        一次情報は OpenCode のライブ取得であり、そこには `tier` が無い。
        よって価格から帯を判定できる必要がある（2026-09-21 実装時に発見した穴）。
        """
        raw = [
            {"ref": "opencode-go/mimo-v2.5", "name": "MiMo V2.5", "cost_in": 0.14, "cost_out": 0.28},
            {"ref": "opencode-go/kimi-k3", "name": "Kimi K3", "cost_in": 3.0, "cost_out": 15.0},
        ]
        captured: Dict[str, Any] = {}

        def fake_decide(state: str, questions: Dict[str, Any]) -> Dict[str, Any]:
            captured["questions"] = questions
            return self._canned_decision({"model_for_agent-tester": "opencode-go/mimo-v2.5"})

        with patch.object(jev_client_mod.JevClient, "decide", side_effect=fake_decide):
            result = self.client.select_models(
                task_description="テスト",
                agent_names=["agent-tester"],
                candidates=raw,
            )

        self.assertNotIn("error", result)
        criteria = captured["questions"]["model_for_agent-tester"]["criteria"]
        self.assertIn("opencode-go/mimo-v2.5", criteria)
        self.assertNotIn("opencode-go/kimi-k3", criteria)  # 承認帯は既定で除外される

    def test_role_scope_restricts_to_boss_specified_models(self) -> None:
        """実装ロールの候補がボス指定モデル（+ より安いモデル）に限定されること"""
        captured: Dict[str, Any] = {}

        def fake_decide(state: str, questions: Dict[str, Any]) -> Dict[str, Any]:
            captured["questions"] = questions
            return self._canned_decision({"model_for_python-architect": "opencode-go/deepseek-v4.1-flash"})

        with patch.object(jev_client_mod.JevClient, "decide", side_effect=fake_decide):
            result = self.client.select_models(
                task_description="実装",
                agent_names=["python-architect"],
                candidates=model_catalog.build_candidates(include_approval_tier=False),
            )

        self.assertNotIn("error", result)
        criteria = captured["questions"]["model_for_python-architect"]["criteria"]
        # ボス指定の2モデルは必ず含まれる
        self.assertIn("opencode-go/deepseek-v4.1-flash", criteria)
        self.assertIn("opencode-go/glm-5.3-flash", criteria)
        # より高価な非指定モデル（qwen3.7-plus $1.6 等）は範囲外
        self.assertNotIn("opencode-go/qwen3.7-plus", criteria)
        self.assertNotIn("opencode-go/deepseek-v4-pro", criteria)

    def test_audit_role_scope_contains_only_strong_models(self) -> None:
        """監査ロールの候補が「強いモデル」のみに限定されること（安価な混入を防ぐ）"""
        captured: Dict[str, Any] = {}

        def fake_decide(state: str, questions: Dict[str, Any]) -> Dict[str, Any]:
            captured["questions"] = questions
            return self._canned_decision({"model_for_quality-reviewer": "opencode-go/glm-5.3"})

        with patch.object(jev_client_mod.JevClient, "decide", side_effect=fake_decide):
            result = self.client.select_models(
                task_description="重大監査",
                agent_names=["quality-reviewer"],
                candidates=model_catalog.build_candidates(include_approval_tier=True),
                include_approval_tier=True,
            )

        self.assertNotIn("error", result)
        criteria = captured["questions"]["model_for_quality-reviewer"]["criteria"]
        self.assertIn("opencode-go/glm-5.3", criteria)
        self.assertNotIn("opencode-go/mimo-v2.5", criteria)  # 最安モデルは監査に混ぜない
        self.assertNotIn("opencode-go/deepseek-v4.1-flash", criteria)


class TestAntigravityContractFrozen(unittest.TestCase):
    """Antigravity 側の契約が不変であることを機械的に凍結する（最重要）。"""

    def setUp(self) -> None:
        if jev_core is None:
            self.skipTest("jev_mcp_server.py が読み込めません")

    def test_core_server_exposes_only_two_tools(self) -> None:
        """Antigravity 側サーバーは 2 ツールのままで、モデル選択ツールを持たないこと"""
        if not hasattr(jev_core, "jev_guard_command") or not hasattr(jev_core, "jev_route_agent"):
            self.skipTest("jev_core tools not present in this environment")
        self.assertTrue(callable(getattr(jev_core, "jev_guard_command", None)))
        self.assertTrue(callable(getattr(jev_core, "jev_route_agent", None)))
        self.assertFalse(hasattr(jev_core, "jev_select_models"))
        self.assertFalse(hasattr(jev_core, "select_models"))

    def test_route_subagents_output_contains_no_model_keys(self) -> None:
        """`route_subagents` の出力にモデル関連キーが漏れていないこと（直列化事故の防止）"""
        allowed_keys = {
            "should_spawn",
            "selected_agents",
            "concurrency",
            "primary_agent",
            "secondary_agent",
            "category_skills",
            "recommended_skills",
            "recommended_mcp",
            "skills_ranked",
            "skills_ranked_by_category",
            "mcps_ranked",
            "agents_ranked",
            "confidence",
            "raw_decision",
            "error",
        }
        canned = {
            "answers": {
                "should_spawn": {"choice": "yes"},
                "primary_agent": {"choice": "agent-tester", "confidence": 0.9, "probabilities": {"agent-tester": 0.9}},
                "secondary_agent": {"choice": "none"},
                "concurrency": {"choice": "solo"},
                "primary_mcp": {"choice": "none", "probabilities": {}},
            },
            "usage": {"cost": 0.0003},
        }
        if jev_client_mod is None or not hasattr(jev_client_mod, "JevClient"):
            self.skipTest("JevClient が未実装です")
        client = jev_client_mod.JevClient(api_key="dummy-key-for-test")
        with patch.object(jev_client_mod.JevClient, "decide", return_value=canned):
            result = client.route_subagents("テスト", workspace_dir=str(PROJECT_ROOT))

        self.assertTrue(set(result.keys()).issubset(allowed_keys), "許可されていないキー: %s" % (set(result.keys()) - allowed_keys))
        for key in result:
            self.assertNotIn("model", key.lower())

    @unittest.skipUnless(
        ANTIGRAVITY_MCP_CONFIG.exists(),
        "Antigravity のグローバルMCP設定が無い環境ではスキップ",
    )
    def test_antigravity_config_still_points_to_legacy_server(self) -> None:
        """Antigravity の MCP 設定は従来の jev_mcp_server.py を指したままであること"""
        raw = ANTIGRAVITY_MCP_CONFIG.read_text(encoding="utf-8")
        data = json.loads(raw)

        args = data["mcpServers"]["jev-mcp"]["args"]
        joined = " ".join(args)

        self.assertIn("jev_mcp_server.py", joined)
        self.assertNotIn("jev_mcp_planner.py", joined)


class TestOpenCodePlannerServer(unittest.TestCase):
    """OpenCode 側サーバーの構造と、Antigravity との関係を凍結する。"""

    def setUp(self) -> None:
        if jev_planner is None:
            self.skipTest("jev_mcp_planner.py が未実装です（Red）")

    def test_planner_shares_contract_functions_with_core(self) -> None:
        """2つのサーバーが同一の関数オブジェクトを共有すること（ドリフトの構造的根絶）"""
        self.assertIs(jev_planner.jev_guard_command, jev_core.jev_guard_command)
        self.assertIs(jev_planner.jev_route_agent, jev_core.jev_route_agent)

    def test_planner_exposes_select_models_tool(self) -> None:
        """プランナーが jev_select_models ツールを公開すること"""
        self.assertTrue(callable(getattr(jev_planner, "jev_select_models", None)))

    @unittest.skipUnless(
        OPENCODE_GLOBAL_CONFIG.exists(),
        "OpenCode のグローバル設定が無い環境ではスキップ",
    )
    def test_opencode_config_points_to_planner(self) -> None:
        """OpenCode の MCP 設定が jev_mcp_planner.py を指していること"""
        raw = OPENCODE_GLOBAL_CONFIG.read_text(encoding="utf-8")
        stripped = re.sub(r"(?m)^\s*//.*$", "", raw)

        self.assertIn("jev_mcp_planner.py", stripped)
        self.assertNotIn("jev_mcp_server.py", stripped)


class TestModelPolicyFile(unittest.TestCase):
    """ボスが編集できるポリシーファイル（`model_policy.json`）の契約。"""

    def setUp(self) -> None:
        if model_catalog is None:
            self.skipTest("model_catalog.py が未実装です（Red）")

    def test_policy_file_exists_and_is_valid(self) -> None:
        """ポリシーファイルが実在し、JSON として妥当であること"""
        policy_path = JEV_DIR / "model_policy.json"

        self.assertTrue(policy_path.exists(), "model_policy.json がありません（Red）")
        data = json.loads(policy_path.read_text(encoding="utf-8"))
        self.assertIn("auto_tier_max_output_cost", data)
        self.assertIn("role_models", data)
        self.assertIn("high_stakes_roles", data)

    def test_module_constants_reflect_policy_file(self) -> None:
        """モジュール定数がポリシーファイルの内容を反映していること（単一情報源）"""
        data = json.loads((JEV_DIR / "model_policy.json").read_text(encoding="utf-8"))
        expected_threshold = float(data["auto_tier_max_output_cost"])

        self.assertEqual(model_catalog.AUTO_TIER_MAX_OUTPUT_COST, expected_threshold)
        arch = model_catalog.ROLE_PREFERRED_MODELS["python-architect"]
        self.assertEqual(list(arch), list(data["role_models"]["python-architect"]))

    def test_load_policy_falls_back_when_missing(self) -> None:
        """ポリシーファイルが無い場合はコード内既定へフォールバックすること"""
        fallback = model_catalog.load_policy(Path("C:/__not_exist__/model_policy.json"))

        self.assertEqual(fallback["auto_tier_max_output_cost"], 1.0)
        self.assertIn("python-architect", fallback["role_models"])

    def test_boss_can_change_threshold_via_policy(self) -> None:
        """ポリシーのしきい値を変えると帯判定が変わること（ボスが1行で更新できる）"""
        policy = model_catalog.load_policy(Path("C:/__not_exist__/model_policy.json"))
        policy["auto_tier_max_output_cost"] = 0.1

        self.assertEqual(model_catalog.classify_tier(0.28, policy), "approval")
        self.assertEqual(model_catalog.classify_tier(0.05, policy), "auto")


class TestStrictModelScope(unittest.TestCase):
    """B案: ボス指定モデルを厳格に守る（安い代替への逃げ道を塞ぐ）。"""

    def setUp(self) -> None:
        if model_catalog is None:
            self.skipTest("model_catalog.py が未実装です（Red）")
        if jev_client_mod is None:
            self.skipTest("jev_client.py が読み込めません")
        self.client = jev_client_mod.JevClient(api_key="dummy-key-for-test")

    def _capture_criteria(self, agent: str, candidates: list) -> Dict[str, Any]:
        captured: Dict[str, Any] = {}

        def fake_decide(state: str, questions: Dict[str, Any]) -> Dict[str, Any]:
            captured["questions"] = questions
            return {"answers": {}, "usage": {"cost": 0.0003}}

        with patch.object(jev_client_mod.JevClient, "decide", side_effect=fake_decide):
            self.client.select_models(
                task_description="テスト",
                agent_names=[agent],
                candidates=candidates,
                include_approval_tier=True,
            )
        return captured["questions"]["model_for_%s" % agent]["criteria"]

    def test_implementation_scope_excludes_cheaper_unlisted_models(self) -> None:
        """実装ロールでは、ボス指定より安いモデル（mimo-v2.5 等）も候補から除外されること（B案）"""
        criteria = self._capture_criteria(
            "python-architect", model_catalog.build_candidates(include_approval_tier=True)
        )

        self.assertIn("opencode-go/deepseek-v4.1-flash", criteria)
        self.assertIn("opencode-go/glm-5.3-flash", criteria)
        self.assertNotIn("opencode-go/mimo-v2.5", criteria)
        self.assertNotIn("opencode-go/qwen3.8-flash", criteria)

    def test_audit_scope_only_strong_models(self) -> None:
        """監査ロールは強いモデルのみ（安価な混入なし）"""
        criteria = self._capture_criteria(
            "quality-reviewer", model_catalog.build_candidates(include_approval_tier=True)
        )

        self.assertIn("opencode-go/glm-5.3", criteria)
        self.assertNotIn("opencode-go/mimo-v2.5", criteria)


class TestPolicyDriftDetection(unittest.TestCase):
    """モデル提供の変化（廃止・新規・価格改定）を検知できること。"""

    def setUp(self) -> None:
        if model_catalog is None:
            self.skipTest("model_catalog.py が未実装です（Red）")

    def test_detects_missing_preferred_models(self) -> None:
        """ポリシーの推奨モデルがライブから消えたら検知すること"""
        live = [
            {"ref": "opencode-go/glm-5.3-flash", "name": "GLM-5.3-Flash", "cost_in": 0.15, "cost_out": 0.5},
        ]

        drift = model_catalog.detect_policy_drift(live)

        self.assertIn("opencode-go/deepseek-v4.1-flash", drift["missing_preferred"])

    def test_detects_unlisted_new_models(self) -> None:
        """どのロールにも未登録の新モデル（例: 無料のステルスモデル）を検知すること"""
        live = [
            {"ref": "opencode-go/stealth-free-2026", "name": "Stealth Free", "cost_in": 0.0, "cost_out": 0.0},
        ]

        drift = model_catalog.detect_policy_drift(live)

        self.assertIn("opencode-go/stealth-free-2026", drift["unlisted_new"])

    def test_detects_price_changes(self) -> None:
        """価格改定を検知すること"""
        live = [
            {"ref": "opencode-go/glm-5.3-flash", "name": "GLM-5.3-Flash", "cost_in": 0.15, "cost_out": 9.99},
        ]

        drift = model_catalog.detect_policy_drift(live)

        changed = {item["ref"]: item for item in drift["price_changed"]}
        self.assertIn("opencode-go/glm-5.3-flash", changed)
        self.assertAlmostEqual(changed["opencode-go/glm-5.3-flash"]["new"], 9.99, places=2)


class TestOpenCodeDocumentation(unittest.TestCase):
    """規約ドキュメントにモデル帯の運用が明記されていること。"""

    def test_opencode_md_documents_model_tier_policy(self) -> None:
        """OPENCODE.md に「承認帯はスマホ承認必須」が明記されていること"""
        text = (PROJECT_ROOT / "OPENCODE.md").read_text(encoding="utf-8")

        self.assertIn("jev_select_models", text)
        self.assertIn("承認帯", text)
        self.assertIn("requires_approval", text)


if __name__ == "__main__":
    unittest.main()
