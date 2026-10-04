"""ネオ秘書くん - 設定画面タブ分離パッケージ (ui.settings_tabs).

Fat モジュール `ui/settings_window.py` から Deep Module 原則に基づいて
切り出されたタブ別 UI コンポーネント群を収容します。

収容コンポーネント:
    - GuideTab (T1): 使い方ガイド・ツアー再開
    - GeneralTab (T2): 一般設定・言語選択
    - AgentHooksTab (T3): エージェント連携＆Hooks
    - LLMBrainTab (T4): AIモデル設定・同期
    - ToolsTab (T5a): 外部連携・MCP・SaaS連携
    - ICalSection (T5b): iCal 購読管理
    - GoogleSection (T5c): Google OAuth 連携
"""

from ui.settings_tabs.agent_hooks_tab import AgentHooksTab
from ui.settings_tabs.general_tab import GeneralTab
from ui.settings_tabs.google_section import GoogleSection
from ui.settings_tabs.guide_tab import GuideTab
from ui.settings_tabs.ical_section import ICalSection
from ui.settings_tabs.llm_brain_tab import LLMBrainTab
from ui.settings_tabs.tools_tab import ToolsTab

__all__: list[str] = [
    "AgentHooksTab",
    "GeneralTab",
    "GoogleSection",
    "GuideTab",
    "ICalSection",
    "LLMBrainTab",
    "ToolsTab",
]
