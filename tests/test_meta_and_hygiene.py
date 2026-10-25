#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - メタ検証・健全性・起動スモーク統合テスト (tests/test_meta_and_hygiene.py)

テストスイート引き算スプリントにより、以下の孤児テストファイルを集約・統合:
  1. TestRequirementsCompleteness (旧 tests/test_requirements_pinning.py): requirements.txt 必須依存宣言
  2. TestClaudeFallback (旧 tests/test_review_hardening.py): langchain-anthropic 未導入時エラーヒント
  3. TestStartupSmoke (旧 tests/test_startup_smoke.py): Linux (Xvfb) 実機起動スモーク
  4. TestSyncAiDotfiles (旧 tests/test_sync_ai_dotfiles.py): Knowledge Vault エクスポート & Dotfiles同期
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import database
from llm_factory import LLMFactory, LLMProvider
from storage.insight_repo import add_user_insight
from tools.sync_ai_dotfiles import export_knowledge_vault, sync_dotfiles


# ==============================================================================
# 1. requirements.txt 必須依存宣言 検査
# ==============================================================================
REQUIRED_RUNTIME_PACKAGES = (
    "langgraph",              # agent.py (LangGraph の状態グラフ)
    "langchain-core",         # LangChain 抽象 (agent.py / llm_factory.py)
    "langchain-openai",       # OpenAI互換プロバイダ (llm_factory.py)
    "langchain-google-genai", # Gemini プロバイダ (llm_factory.py)
    "customtkinter",          # PCペットUI (gui.py / ui/*)
    "pydantic",               # DTO / DBモデル (database.py / sync_dtos.py)
    "httpx",                  # LLM通信 / 健康診断 (llm_factory.py / tools)
    "pillow",                 # 画像・トレイアイコン (gui.py / ui/system_tray.py)
    "python-dotenv",          # .env 読み込み (llm_factory.py ほか)
    "requests",               # 外部API・更新確認 (update_checker.py ほか)
    "pystray",                # タスクトレイ常駐 (ui/system_tray.py)
    "qrcode",                 # QRペアリング (ui/qr_dialog.py)
)


def _declared_package_names() -> set:
    text = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")
    names = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name = line.split("==")[0].split(">=")[0].split("[")[0].strip().lower()
        names.add(name.replace("_", "-"))
    return names


class TestRequirementsCompleteness(unittest.TestCase):
    """実行時必須依存が requirements.txt に宣言されていること"""

    def test_all_runtime_dependencies_are_declared(self) -> None:
        """実行時に import される必須依存がすべて requirements.txt に宣言されていることを保証する。"""
        declared = _declared_package_names()
        missing = [
            pkg for pkg in REQUIRED_RUNTIME_PACKAGES
            if pkg.lower().replace("_", "-") not in declared
        ]
        self.assertEqual(
            missing, [],
            f"requirements.txt に未宣言の必須依存があります: {missing}",
        )


# ==============================================================================
# 2. 未導入プロバイダ選択時の Actionable エラー検証
# ==============================================================================
class TestClaudeFallback(unittest.TestCase):
    """langchain-anthropic 未導入時の Claude 選択は明確なエラーで縮退すること"""

    def setUp(self) -> None:
        env_patcher = mock.patch.dict(
            os.environ, {"ANTHROPIC_API_KEY": "sk-ant-dummy"}, clear=False
        )
        env_patcher.start()
        self.addCleanup(env_patcher.stop)

    def test_missing_langchain_anthropic_raises_actionable_error(self) -> None:
        """未導入時は pip install ヒントを含む ImportError を送出すること"""
        factory = LLMFactory(default_provider=LLMProvider.CLAUDE.value)
        with mock.patch.dict(sys.modules, {"langchain_anthropic": None}):
            with self.assertRaises(ImportError) as ctx:
                factory.create_model(temperature=0.3)
        self.assertIn("langchain-anthropic", str(ctx.exception))


# ==============================================================================
# 3. 実アプリ起動スモーク (Linux / Xvfb CI用)
# ==============================================================================
SINGLE_INSTANCE_LOCK_PORT = 54321


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux (Xvfb) 上の起動スモーク。Windows は既存の GUI テストで担保")
class TestStartupSmoke(unittest.TestCase):
    """Linux 仮想スクリーン上での起動スモーク"""

    def setUp(self) -> None:
        if not os.environ.get("DISPLAY"):
            self.skipTest("DISPLAY が無い環境のためスキップ (xvfb-run -a pytest で実行してください)")
        try:
            import tkinter as tk
            probe = tk.Tk()
            probe.destroy()
        except Exception as e:
            self.skipTest(f"ディスプレイに接続できないためスキップ: {e}")
        if _port_in_use(SINGLE_INSTANCE_LOCK_PORT):
            self.skipTest("別のネオ秘書くんが起動中 (127.0.0.1:54321 使用中) のためスキップ")

    def test_app_reaches_main_loop_and_serves_http(self) -> None:
        """プレースホルダーキーで起動し、メインループ到達と /version.js = 200 を確認して終了すること。"""
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "tools" / "smoke_startup.py")],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, f"起動スモーク失敗:\n{result.stdout}\n{result.stderr}")
        self.assertIn("[smoke] OK", result.stdout)


# ==============================================================================
# 4. Knowledge Vault & AI Dotfiles 同期テスト
# ==============================================================================
class TestSyncAiDotfiles(unittest.TestCase):
    """sync_ai_dotfiles ツールおよび Knowledge Vault エクスポートの正常動作検証"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_db_path = os.path.join(self.temp_dir.name, "test_vault.db")
        database.init_db(self.tmp_db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_export_knowledge_vault_schema_correctness(self):
        """Knowledge Vault のエクスポートが正しいスキーマで最新知見を含んで取得できること"""
        id1 = add_user_insight("Constraint", "平日夜は作業を控える", importance=5, context_tags="time,family", db_path=self.tmp_db_path)
        id2 = add_user_insight("Preference", "ダークモードを優先する", importance=4, context_tags="theme,ui", db_path=self.tmp_db_path)
        self.assertGreater(id1, 0)
        self.assertGreater(id2, 0)

        insights = export_knowledge_vault(db_path=self.tmp_db_path)
        self.assertEqual(len(insights), 2)
        expected_keys = {"id", "category", "content", "context_tags", "importance", "created_at", "updated_at"}
        for item in insights:
            self.assertTrue(expected_keys.issubset(item.keys()), f"欠落フィールドがあります: {set(expected_keys) - set(item.keys())}")

        contents = [item["content"] for item in insights]
        self.assertIn("平日夜は作業を控える", contents)
        self.assertIn("ダークモードを優先する", contents)

    def test_sync_dotfiles_creates_knowledge_vault_json(self):
        """sync_dotfiles 関数が指定ディレクトリへ knowledge_vault.json を正常に同期作成すること"""
        add_user_insight("Project", "リファクタリング時はTDDを厳守", importance=5, db_path=self.tmp_db_path)
        dotfiles_path = Path(self.temp_dir.name) / "ai_dotfiles"
        summary = sync_dotfiles(dotfiles_dir=dotfiles_path, db_path=self.tmp_db_path, check_only=False)

        self.assertEqual(summary["status"], "success")
        self.assertEqual(summary["vault_count"], 1)
        vault_file = dotfiles_path / "knowledge_vault.json"
        self.assertTrue(vault_file.exists())


if __name__ == "__main__":
    unittest.main()
