#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - requirements.txt 依存宣言の完全性テスト (tests/test_requirements_pinning.py)

2026-09-12 の CI 失敗 (3ジョブ全滅) の真因は「ローカル venv には入っているが
requirements.txt に宣言されていない依存 (langgraph) が存在したこと」だった。
ローカルでは緑・CI では赤という再発を防ぐため、実行時に必須の主要依存が
requirements.txt に宣言されていることを凍結する。

TDD: langgraph 未宣言の状態では Red で落ちる。
"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 実行時に import される必須のサードパーティ依存 (パッケージ名 = requirements 表記)
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
    """requirements.txt に宣言されているパッケージ名 (正規化済み) を返す。"""
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
            f"requirements.txt に未宣言の必須依存があります (CI で import 失敗します): {missing}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
