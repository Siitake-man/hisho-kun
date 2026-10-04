"""
ネオ秘書くん - 統合設定ウィンドウ (ui/settings_window.py)
AIモデル(LLM)設定、外部AI・MCP連携設定、Googleカレンダー/Slack等の設定ダイアログ。
"""

import os
import sys
import json
import logging
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from typing import Optional
import customtkinter as ctk
from dotenv import load_dotenv

from ui.window_icon import apply_window_icon
from sync_config import SERVER_PORT, build_tailscale_serve_command
import i18n
from i18n import t

logger = logging.getLogger(__name__)

class AddMCPServerDialog(ctk.CTkToplevel):
    """
    ユーザーが任意のMCPサーバー（Google Calendar, Notion, Slack等）を追加するためのダイアログ。
    """
    def __init__(self, parent_settings, *args, **kwargs):
        super().__init__(parent_settings, *args, **kwargs)
        self.parent_settings = parent_settings
        self.title(t("ui.settings.mcp_dialog_title"))
        self.geometry("420x460")
        self.resizable(False, False)
        
        self.bg_color = "#F5F5DC"
        self.primary_color = "#A67B5B"
        self.text_color = "#4A3B32"
        self.configure(fg_color=self.bg_color)
        
        self.font_title = ("DotGothic16", 13, "bold") if "DotGothic16" in tk.font.families() else ("Meiryo UI", 11, "bold")
        self.font_body = ("DotGothic16", 11) if "DotGothic16" in tk.font.families() else ("Meiryo UI", 10)
        self.font_small = ("Meiryo UI", 9)
        
        self._build_ui()

    def _build_ui(self):
        pad = 12
        ctk.CTkLabel(self, text=t("ui.settings.mcp_dialog_header"), font=self.font_title, text_color=self.primary_color).pack(pady=(12, 6))
        
        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=pad, pady=4)
        
        # 1. サーバーID
        ctk.CTkLabel(form, text=t("ui.settings.mcp_id"), font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_id = ctk.CTkEntry(form, placeholder_text="google-calendar")
        self.entry_id.pack(fill="x", pady=(0, 6))
        
        # 2. 表示名
        ctk.CTkLabel(form, text=t("ui.settings.mcp_name"), font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_name = ctk.CTkEntry(form, placeholder_text=t("ui.settings.mcp_name_placeholder"))
        self.entry_name.pack(fill="x", pady=(0, 6))
        
        # 3. 実行コマンド (command)
        ctk.CTkLabel(form, text=t("ui.settings.mcp_cmd"), font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_cmd = ctk.CTkEntry(form, placeholder_text="npx")
        self.entry_cmd.insert(0, "npx")
        self.entry_cmd.pack(fill="x", pady=(0, 6))
        
        # 4. 引数 (args)
        ctk.CTkLabel(form, text=t("ui.settings.mcp_args"), font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_args = ctk.CTkEntry(form, placeholder_text="-y @modelcontextprotocol/server-google-calendar")
        self.entry_args.pack(fill="x", pady=(0, 6))
        
        # 5. 説明
        ctk.CTkLabel(form, text=t("ui.settings.mcp_desc"), font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_desc = ctk.CTkEntry(form, placeholder_text=t("ui.settings.mcp_desc_placeholder"))
        self.entry_desc.pack(fill="x", pady=(0, 10))
        
        # 登録ボタン
        btn_add = ctk.CTkButton(
            self,
            text=t("ui.settings.mcp_submit"),
            font=self.font_title,
            fg_color=self.primary_color,
            hover_color="#8B634A",
            height=36,
            command=self._on_submit
        )
        btn_add.pack(fill="x", padx=pad, pady=(0, 14))

    def _on_submit(self):
        s_id = self.entry_id.get().strip()
        name = self.entry_name.get().strip() or s_id
        cmd = self.entry_cmd.get().strip()
        args_str = self.entry_args.get().strip()
        desc = self.entry_desc.get().strip()
        
        if not s_id or not cmd:
            return
            
        args_list = args_str.split() if args_str else []
        
        from mcp_manager import get_mcp_manager, MCPServerConfig
        mcp_mgr = get_mcp_manager()
        
        conf = MCPServerConfig(
            name=name,
            command=cmd,
            args=args_list,
            env={},
            enabled=True,
            description=desc
        )
        
        mcp_mgr.add_or_update_server(s_id, conf)
        
        # 設定画面を再描画して閉じる
        if hasattr(self.parent_settings, "_render_mcp_servers"):
            self.parent_settings._render_mcp_servers()
        self.destroy()


class SuggestSettingsDialog(ctk.CTkToplevel):
    """サジェストソースの個別ON/OFF設定ダイアログ"""
    def __init__(self, parent_gui, *args, **kwargs):
        super().__init__(parent_gui.root, *args, **kwargs)
        self.parent_gui = parent_gui
        self.title(t("ui.settings.suggest_dialog_title"))
        self.geometry("380x430")
        self.resizable(False, False)
        
        self.bg_color = "#F5F5DC"
        self.primary_color = "#A67B5B"
        self.text_color = "#4A3B32"
        self.configure(fg_color=self.bg_color)
        
        from suggest_engine import get_suggestion_engine
        self.engine = get_suggestion_engine()
        self.config = self.engine.config
        
        self.font_title = ("DotGothic16", 13, "bold") if "DotGothic16" in tk.font.families() else ("Meiryo UI", 11, "bold")
        self.font_body = ("Meiryo UI", 10)
        self.font_small = ("Meiryo UI", 8.5)
        
        self._build_ui()

    def _build_ui(self):
        pad = 14
        ctk.CTkLabel(self, text=t("ui.settings.suggest_dialog_header"), font=self.font_title, text_color=self.primary_color).pack(pady=(12, 4))
        ctk.CTkLabel(self, text=t("ui.settings.suggest_dialog_sub"), font=self.font_small, text_color="#7A6B62").pack(pady=(0, 8))
        
        scroll = ctk.CTkScrollableFrame(self, fg_color="#FFFFFF", border_color="#A67B5B", border_width=1.5, corner_radius=8)
        scroll.pack(fill="both", expand=True, padx=pad, pady=4)
        
        sources = self.config.get("sources", {})
        self.check_vars = {}
        self.news_keywords_entry = None
        
        for key, info in sources.items():
            card = ctk.CTkFrame(scroll, fg_color="#FDFBF7", corner_radius=6, border_color="#E0D8C8", border_width=1)
            card.pack(fill="x", pady=4, padx=4)
            
            var = tk.BooleanVar(value=info.get("enabled", True))
            self.check_vars[key] = var
            
            chk = ctk.CTkCheckBox(
                card,
                text=info.get("name", key),
                variable=var,
                font=("Meiryo UI", 10, "bold"),
                text_color=self.text_color,
                fg_color=self.primary_color,
                hover_color="#8B634A",
                command=lambda k=key, v=var: self._on_toggle(k, v)
            )
            chk.pack(anchor="w", padx=8, pady=(6, 2))
            
            desc = info.get("description", "")
            if desc:
                ctk.CTkLabel(card, text=desc, font=self.font_small, text_color="#6D4C41", anchor="w").pack(fill="x", padx=28, pady=(0, 4))

            # news_topics の場合に関心キーワード入力欄を追加
            if key == "news_topics":
                kw_frame = ctk.CTkFrame(card, fg_color="transparent")
                kw_frame.pack(fill="x", padx=28, pady=(0, 6))
                
                ctk.CTkLabel(
                    kw_frame, 
                    text=t("ui.settings.suggest_keywords"),
                    font=("Meiryo UI", 8, "bold"), 
                    text_color="#8B634A"
                ).pack(anchor="w")
                
                kw_list = self.engine.get_news_keywords()
                kw_str = ", ".join(kw_list)
                
                self.news_keywords_entry = ctk.CTkEntry(
                    kw_frame,
                    font=("Meiryo UI", 9),
                    height=26,
                    fg_color="#FFFFFF",
                    border_color="#D5C7B8",
                    border_width=1,
                    text_color=self.text_color
                )
                self.news_keywords_entry.insert(0, kw_str)
                self.news_keywords_entry.pack(fill="x", pady=(2, 0))

        btn_close = ctk.CTkButton(
            self,
            text=t("ui.settings.suggest_save"),
            font=("Meiryo UI", 10, "bold"),
            fg_color=self.primary_color,
            hover_color="#8B634A",
            height=32,
            command=self._on_save_and_close
        )
        btn_close.pack(fill="x", padx=pad, pady=10)

    def _on_toggle(self, key, var):
        self.engine.toggle_source(key, var.get())
        if hasattr(self.parent_gui, '_update_suggestion_card'):
            self.parent_gui._update_suggestion_card()

    def _on_save_and_close(self):
        """キーワード設定を永続保存して閉じる"""
        if self.news_keywords_entry:
            kw_val = self.news_keywords_entry.get().strip()
            self.engine.set_news_keywords(kw_val)
        if hasattr(self.parent_gui, '_update_suggestion_card'):
            self.parent_gui._update_suggestion_card()
        self.destroy()


class SettingsWindow(ctk.CTkToplevel):
    """
    APIキーやLLM接続先を設定し、利用可能なモデル一覧を動的取得・選択するための設定ウィンドウ。
    """
    def __init__(self, parent_gui, *args, **kwargs):
        super().__init__(parent_gui.root, *args, **kwargs)
        self.parent_gui = parent_gui
        self.title(t("ui.settings.title"))
        self.minsize(720, 550)
        self.geometry("760x600")
        
        self.bg_color = "#F5F5DC"
        self.primary_color = "#A67B5B"
        self.text_color = "#4A3B32"
        self.configure(fg_color=self.bg_color)
        
        self.font_title = ("DotGothic16", 15, "bold") if "DotGothic16" in tk.font.families() else ("Meiryo UI", 13, "bold")
        self.font_body = ("DotGothic16", 12) if "DotGothic16" in tk.font.families() else ("Meiryo UI", 10)
        self.font_small = ("Meiryo UI", 9)

        # 🖼️ ウィンドウアイコン (Alt+Tab/タスクバー) を統一 (例外安全 Seam)
        apply_window_icon(self)

        from i18n import subscribe_language_change
        subscribe_language_change(self._on_language_changed)

        self.nav_buttons = {}
        self.content_frames = {}
        self.current_nav = "general"

        self._build_ui()

    def select_nav(self, nav_key: str):
        """サイドバーで選択されたカテゴリを表示する"""
        if self.current_nav == nav_key and self.content_frames.get(nav_key) and self.content_frames[nav_key].winfo_ismapped():
            return
        self.current_nav = nav_key
        for k, btn in self.nav_buttons.items():
            if k == nav_key:
                btn.configure(fg_color=self.primary_color, text_color="#FFFFFF")
            else:
                btn.configure(fg_color="transparent", text_color=self.text_color)
        
        for k, frame in self.content_frames.items():
            if k == nav_key:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_forget()

    def _build_ui(self):
        load_dotenv(override=True)
        from llm_factory import get_llm_factory, LLMProvider
        factory = get_llm_factory()
        
        # ヘッダー (上部タイトルバー)
        header = ctk.CTkFrame(self, fg_color=self.primary_color, corner_radius=0, height=45)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)
        
        self.header_title = ctk.CTkLabel(header, text=t("ui.settings.title"), font=self.font_title, text_color="#FFFFFF")
        self.header_title.pack(pady=8)

        # 保存ボタンバー (最下部固定)
        footer = ctk.CTkFrame(self, fg_color=self.bg_color, height=48)
        footer.pack(side="bottom", fill="x", padx=12, pady=(4, 8))
        self.btn_save = ctk.CTkButton(
            footer,
            text=f"💾 {t('ui.settings.save')}",
            font=self.font_title,
            fg_color=self.primary_color,
            hover_color="#8B634A",
            height=38,
            command=self._on_save
        )
        self.btn_save.pack(fill="x")
        
        # メインボディ領域 (左右分割: 左サイドバー + 右コンテンツ)
        main_body = ctk.CTkFrame(self, fg_color=self.bg_color, corner_radius=0)
        main_body.pack(side="top", fill="both", expand=True)

        # 左サイドバー (Navigation Rail: 幅190px)
        self.sidebar_frame = ctk.CTkFrame(main_body, fg_color="#EDE6D6", width=190, corner_radius=0)
        self.sidebar_frame.pack(side="left", fill="y", padx=0, pady=0)
        self.sidebar_frame.pack_propagate(False)

        self.nav_items_def = [
            ("general", "ui.settings.nav_general"),
            ("agent_hooks", "ui.settings.nav_agent_hooks"),
            ("llm", "ui.settings.nav_llm"),
            ("tools", "ui.settings.nav_tools"),
            ("devices", "ui.settings.nav_devices"),
            ("guide", "ui.settings.nav_guide"),
        ]
        for key, text_key in self.nav_items_def:
            btn = ctk.CTkButton(
                self.sidebar_frame,
                text=t(text_key),
                font=self.font_body,
                fg_color="transparent",
                text_color=self.text_color,
                hover_color="#D8CFBD",
                anchor="w",
                height=42,
                corner_radius=6,
                command=lambda k=key: self.select_nav(k)
            )
            btn.pack(fill="x", padx=8, pady=4)
            self.nav_buttons[key] = btn

        # 右コンテンツコンテナ
        self.content_container = ctk.CTkFrame(main_body, fg_color="transparent")
        self.content_container.pack(side="right", fill="both", expand=True, padx=8, pady=6)
        self.content_container.grid_rowconfigure(0, weight=1)
        self.content_container.grid_columnconfigure(0, weight=1)

        # =====================================================================
        # Nav 1: 一般・言語設定 (General Settings)
        #   Fat Module 分割 Phase F2 (2026-10-04): 描画と言語選択処理を
        #   ui/settings_tabs/general_tab.py の GeneralTab へ委譲 (肥大化防止)。
        # =====================================================================
        from ui.settings_tabs.general_tab import GeneralTab

        self.general_tab = GeneralTab(
            self.content_container,
            self.parent_gui,
            dispatch=getattr(self.parent_gui, "post_action", None),
            fonts={"title": self.font_title, "body": self.font_body, "small": self.font_small},
            colors={"primary": self.primary_color, "text": self.text_color},
            on_language_change=self._on_language_changed,
        )
        content_general = self.general_tab.build()
        self.content_frames["general"] = content_general

        # 既存 _on_save / 外部参照との後方互換プロパティエイリアス
        self.combo_language = self.general_tab.combo_language
        self._LANG_NAME_TO_CODE = self.general_tab._LANG_NAME_TO_CODE
        self._LANG_CODE_TO_NAME = self.general_tab._LANG_CODE_TO_NAME

        # =====================================================================
        # Nav 2: エージェント連携 ＆ Hooks設定 (Agent Hooks & Approval)
        #   Fat Module 分割 Phase F3 (2026-10-04): 描画とスニペット切り替えを
        #   ui/settings_tabs/agent_hooks_tab.py の AgentHooksTab へ委譲 (肥大化防止)。
        # =====================================================================
        from ui.settings_tabs.agent_hooks_tab import AgentHooksTab

        self.agent_hooks_tab = AgentHooksTab(
            self.content_container,
            self.parent_gui,
            dispatch=getattr(self.parent_gui, "post_action", None),
            fonts={"title": ("Meiryo UI", 12, "bold"), "body": self.font_body, "small": self.font_small},
            colors={"primary": self.primary_color, "text": self.text_color},
            on_ping_test=self._on_ping_test,
        )
        content_hooks = self.agent_hooks_tab.build()
        self.content_frames["agent_hooks"] = content_hooks

        # 既存テスト (test_settings_sidebar_seam) 契約のためのプロパティエイリアス
        self.btn_ping = self.agent_hooks_tab.btn_ping
        self.lbl_hooks_title = self.agent_hooks_tab.lbl_hooks_title
        self.lbl_hooks_desc = self.agent_hooks_tab.lbl_hooks_desc
        self.txt_snippet = self.agent_hooks_tab.txt_snippet

        # =====================================================================
        # Nav 3: AIモデル設定 (LLM Brain)
        #   Fat Module 分割 Phase F8a (2026-10-04): 描画、一括同期、モデル一覧取得、
        #   およびローカルLLM DL処理を ui/settings_tabs/llm_brain_tab.py の
        #   LLMBrainTab へ委譲 (肥大化防止)。
        # =====================================================================
        from ui.settings_tabs.llm_brain_tab import LLMBrainTab

        self.llm_brain_tab = LLMBrainTab(
            self.content_container,
            self.parent_gui,
            dispatch=getattr(self.parent_gui, "post_action", None),
            fonts={"title": self.font_title, "body": self.font_body, "small": self.font_small},
            colors={"primary": self.primary_color, "text": self.text_color},
        )
        content_llm = self.llm_brain_tab.build()
        self.content_frames["llm"] = content_llm

        # 既存テスト・外部参照契約のためのプロパティエイリアス
        self.btn_sync_all = self.llm_brain_tab.btn_sync_all
        self.lbl_sync_status = self.llm_brain_tab.lbl_sync_status
        self.entry_gemini_key = self.llm_brain_tab.entry_gemini_key
        self.combo_gemini_model = self.llm_brain_tab.combo_gemini_model
        self.btn_fetch_gemini = self.llm_brain_tab.btn_fetch_gemini
        self.lbl_gemini_status = self.llm_brain_tab.lbl_gemini_status
        self.entry_claude_key = self.llm_brain_tab.entry_claude_key
        self.combo_claude_model = self.llm_brain_tab.combo_claude_model
        self.entry_openai_key = self.llm_brain_tab.entry_openai_key
        self.combo_openai_model = self.llm_brain_tab.combo_openai_model
        self.entry_opencode_key = self.llm_brain_tab.entry_opencode_key
        self.entry_opencode_url = self.llm_brain_tab.entry_opencode_url
        self.combo_opencode_model = self.llm_brain_tab.combo_opencode_model
        self.btn_fetch_opencode = self.llm_brain_tab.btn_fetch_opencode
        self.lbl_opencode_status = self.llm_brain_tab.lbl_opencode_status
        self.entry_groq_key = self.llm_brain_tab.entry_groq_key
        self.entry_openrouter_key = self.llm_brain_tab.entry_openrouter_key
        self.btn_dl_local_350m = self.llm_brain_tab.btn_dl_local_350m
        self.btn_fetch_local = self.llm_brain_tab.btn_fetch_local
        self.progress_bar_local = self.llm_brain_tab.progress_bar_local
        self.lbl_dl_status = self.llm_brain_tab.lbl_dl_status
        self.combo_local_model = self.llm_brain_tab.combo_local_model
        self.entry_custom_url = self.llm_brain_tab.entry_custom_url
        self.entry_custom_key = self.llm_brain_tab.entry_custom_key
        self.btn_fetch_custom = self.llm_brain_tab.btn_fetch_custom
        self.combo_custom_model = self.llm_brain_tab.combo_custom_model
        self.lbl_custom_status = self.llm_brain_tab.lbl_custom_status

        # =====================================================================
        # Nav 4: 外部連携・プラグイン (MCP & Tools)
        #   Fat Module 分割 Phase F8b (2026-10-04): 描画・MCP登録・SaaS連携・
        #   Google/iCal セクションを ui/settings_tabs/tools_tab.py の
        #   ToolsTab へ委譲 (肥大化防止)。
        # =====================================================================
        from ui.settings_tabs.tools_tab import ToolsTab

        self.tools_tab = ToolsTab(
            self.content_container,
            self.parent_gui,
            parent_window=self,
            dispatch=getattr(self.parent_gui, "post_action", None),
            fonts={"title": self.font_title, "body": self.font_body, "small": self.font_small},
            colors={"primary": self.primary_color, "text": self.text_color},
        )
        content_tools = self.tools_tab.build()
        self.content_frames["tools"] = content_tools

        # 既存テスト・外部参照契約のためのプロパティエイリアス
        self.google_section = self.tools_tab.google_section
        self.ical_section = self.tools_tab.ical_section
        self.lbl_copy_toast = self.tools_tab.lbl_copy_toast
        self.var_voice_narration = self.tools_tab.var_voice_narration
        self.chk_voice_narration = self.tools_tab.chk_voice_narration
        self.lbl_google_badge = self.tools_tab.google_section.lbl_google_badge
        self.lbl_google_info = self.tools_tab.google_section.lbl_google_info
        self.entry_google_cal = self.tools_tab.google_section.entry_google_cal
        self.btn_google_auth = self.tools_tab.google_section.btn_google_auth
        self.btn_google_test = self.tools_tab.google_section.btn_google_test
        self.btn_google_logout = self.tools_tab.google_section.btn_google_logout
        self.sources_scroll = self.tools_tab.ical_section.sources_scroll
        self.btn_ical_sync = self.tools_tab.ical_section.btn_ical_sync
        self.lbl_ical_last_sync = self.tools_tab.ical_section.lbl_ical_last_sync
        self.entry_tailscale_host = self.tools_tab.entry_tailscale_host
        self.btn_revoke_sync_token = self.tools_tab.btn_revoke_sync_token
        self.entry_github_token = self.tools_tab.entry_github_token
        self.entry_github_repo = self.tools_tab.entry_github_repo
        self.btn_gh_test = self.tools_tab.btn_gh_test
        self.lbl_gh_status = self.tools_tab.lbl_gh_status
        self.entry_slack_webhook = self.tools_tab.entry_slack_webhook
        self.entry_webhook_outgoing = self.tools_tab.entry_webhook_outgoing
        self.entry_webhook_secret = self.tools_tab.entry_webhook_secret
        self.mcp_checkboxes = self.tools_tab.mcp_checkboxes

        # =====================================================================
        # Nav 6: 使い方ガイド
        #   Fat Module 分割 Phase F1 (2026-10-04): 描画とツアー再開ロジックを
        #   ui/settings_tabs/guide_tab.py の GuideTab へ委譲 (肥大化防止)。
        # =====================================================================
        from ui.settings_tabs.guide_tab import GuideTab

        self.guide_tab = GuideTab(
            self.content_container,
            self.parent_gui,
            dispatch=getattr(self.parent_gui, "post_action", None),
            fonts={"title": self.font_title, "body": self.font_body, "small": self.font_small},
            colors={"primary": self.primary_color, "text": self.text_color},
            on_close=self.destroy,
        )
        content_guide = self.guide_tab.build()
        self.content_frames["guide"] = content_guide

        # =====================================================================
        # Nav 5: 接続端末管理（ゼロトラスト端末台帳）
        #   Sprint C 先取り (2026-09-16): 台帳の表示・Revoke は
        #   ui/device_manager_panel.py の Deep Module へ委譲し、
        #   本画面はセクションを差し込むだけに留める (肥大化防止)。
        # =====================================================================
        content_devices = ctk.CTkFrame(self.content_container, fg_color="transparent")
        self.content_frames["devices"] = content_devices

        from ui.device_manager_panel import DeviceManagerSection

        # dispatch=parent_gui.post_action により、台帳読み出しはワーカースレッドで実行され
        # 結果だけがメインスレッドで反映される（設定画面が固まらない / P1-3）
        self.device_manager_section = DeviceManagerSection(
            content_devices, dispatch=getattr(self.parent_gui, "post_action", None)
        )
        self.device_manager_section.pack(fill="both", expand=True, padx=8, pady=6)

        # 初期表示: 一般タブを選択
        self.select_nav("general")

    def _on_ping_test(self):
        """エージェント連携の接続テスト (Ping) を送信し、PCペットとスマホDesk Petをテスト通知させる"""
        import threading

        if hasattr(self, "btn_ping") and self.btn_ping.winfo_exists():
            self.btn_ping.configure(state="disabled", text="⏳ 送信中...")

        def _worker():
            try:
                import agent_bridge_client
                payload = {
                    "agent_name": "SettingsUI",
                    "question": "🔔 設定画面からの接続テスト（Ping）です！通知は正常に届いています。",
                    "choices": ["了解"],
                    "wait_decision": False
                }
                res = agent_bridge_client._post_to_hub("/api/agent/ask_input", payload, timeout=5)
                success = res.get("status") not in ("error", "unreachable")

                def _ui_callback():
                    if not self.winfo_exists():
                        return
                    if hasattr(self, "btn_ping") and self.btn_ping.winfo_exists():
                        self.btn_ping.configure(state="normal", text=t("ui.settings.hooks_ping_btn"))
                    if success:
                        messagebox.showinfo("Neo-Secretary", t("ui.settings.hooks_ping_success"), parent=self)
                    else:
                        messagebox.showwarning("Neo-Secretary", t("ui.settings.hooks_ping_fail"), parent=self)

                self.after(0, _ui_callback)
            except Exception as ex:
                logger.warning("Ping test failed: %s", ex)
                err_msg = str(ex)
                def _ui_error():
                    if not self.winfo_exists():
                        return
                    if hasattr(self, "btn_ping") and self.btn_ping.winfo_exists():
                        self.btn_ping.configure(state="normal", text=t("ui.settings.hooks_ping_btn"))
                    messagebox.showwarning("Neo-Secretary", f"{t('ui.settings.hooks_ping_fail')}\n({err_msg})", parent=self)
                self.after(0, _ui_error)

        threading.Thread(target=_worker, daemon=True).start()

    def _open_add_mcp_dialog(self):
        """MCPサーバー新規追加ダイアログを開く（ToolsTab へ委譲）"""
        if hasattr(self, "tools_tab"):
            self.tools_tab._open_add_mcp_dialog()
        else:
            dialog = AddMCPServerDialog(self)
            dialog.focus()

    def _delete_mcp_server(self, server_id: str):
        """MCPサーバー設定を削除（ToolsTab へ委譲）"""
        if hasattr(self, "tools_tab"):
            self.tools_tab._delete_mcp_server(server_id)
        else:
            from mcp_manager import get_mcp_manager
            mcp_mgr = get_mcp_manager()
            if mcp_mgr.delete_server(server_id):
                self.destroy()
                SettingsWindow(self.parent_gui)

    def _render_mcp_servers(self):
        """外部MCPサーバー一覧を再描画（ToolsTab へ委譲・設計書 §9①未定義参照の完全是正）"""
        if hasattr(self, "tools_tab"):
            self.tools_tab._render_mcp_servers()

    def _sync_all_models(self):
        """全プロバイダの最新モデル一覧を一括巡回取得して画面を更新（LLMBrainTab へ委譲）"""
        if hasattr(self, "llm_brain_tab"):
            self.llm_brain_tab._sync_all_models()

    def _fetch_models(self, provider: str):
        """APIから利用可能なモデル一覧を動的に探索・取得（LLMBrainTab へ委譲）"""
        if hasattr(self, "llm_brain_tab"):
            self.llm_brain_tab._fetch_models(provider)

    SOURCE_PALETTE = ["#A67B5B", "#1565C0", "#2E7D32", "#C62828", "#6A1B9A", "#00838F", "#F57C00"]

    def _auto_install_mcp(self, tool_name: str):
        """指定したAIツールへネオ秘書くんMCPをワンクリック自動登録（ToolsTab へ委譲）"""
        if hasattr(self, "tools_tab"):
            self.tools_tab._auto_install_mcp(tool_name)

    def _run_google_oauth(self):
        """Google OAuth 2.0 ブラウザ同意画面を起動してログイン（GoogleSection へ委譲）"""
        if hasattr(self, "google_section"):
            self.google_section._run_google_oauth()

    def _render_calendar_sources(self):
        """購読ソース一覧を再描画する（ICalSection へ委譲）"""
        if hasattr(self, "ical_section"):
            self.ical_section._render_calendar_sources()

    def _on_add_calendar_source(self):
        """新しい購読ソースを追加する（ICalSection へ委譲）"""
        if hasattr(self, "ical_section"):
            self.ical_section._on_add_calendar_source()

    def _on_source_toggle(self, source_id: int, var):
        """購読ソースの有効/無効を切り替える（ICalSection へ委譲）"""
        if hasattr(self, "ical_section"):
            self.ical_section._on_source_toggle(source_id, var)

    def _sync_ical_now(self):
        """全購読ソースの iCal を今すぐ同期する（ICalSection へ委譲）"""
        if hasattr(self, "ical_section"):
            self.ical_section._sync_ical_now()

    def _on_ical_sync_done(self, count: int, msg: str):
        """iCal 同期完了時のUI更新（ICalSection へ委譲）"""
        if hasattr(self, "ical_section"):
            self.ical_section._on_ical_sync_done(count, msg)

    def _on_source_cycle_color(self, source_id: int, current_color: str):
        """色ボタンクリックで識別色をパレット順に切り替える（ICalSection へ委譲）"""
        if hasattr(self, "ical_section"):
            self.ical_section._on_source_cycle_color(source_id, current_color)

    def _on_source_field_save(self, source_id: int, name: str, url: str):
        """名前・URLの編集を確定する（ICalSection へ委譲）"""
        if hasattr(self, "ical_section"):
            self.ical_section._on_source_field_save(source_id, name, url)

    def _on_source_sync(self, source_id: int):
        """購読ソース1件だけを今すぐ同期する（ICalSection へ委譲）"""
        if hasattr(self, "ical_section"):
            self.ical_section._on_source_sync(source_id)

    def _on_source_delete(self, source_id: int, name: str):
        """購読ソースを削除する（ICalSection へ委譲）"""
        if hasattr(self, "ical_section"):
            self.ical_section._on_source_delete(source_id, name)

    def _save_tailscale_host(self):
        """Tailscale ホスト名を保存（ToolsTab へ委譲）"""
        if hasattr(self, "tools_tab"):
            self.tools_tab._save_tailscale_host()

    def _revoke_sync_token(self):
        """スマホ連携トークンを再生成（ToolsTab へ委譲）"""
        if hasattr(self, "tools_tab"):
            self.tools_tab._revoke_sync_token()

    def _test_google_connection(self):
        """GoogleカレンダーとGmailの同期テスト（GoogleSection へ委譲）"""
        if hasattr(self, "google_section"):
            self.google_section._test_google_connection()

    def _logout_google(self):
        """Google 認証を解除（GoogleSection へ委譲）"""
        if hasattr(self, "google_section"):
            self.google_section._logout_google()

    def _test_github_connection(self):
        """GitHub PATの接続・権限テスト（ToolsTab へ委譲）"""
        if hasattr(self, "tools_tab"):
            self.tools_tab._test_github_connection()

    def _copy_claude_mcp_config(self):
        """Claude Desktop / Cursor / Antigravity用のMCP設定JSONをコピー（ToolsTab へ委譲）"""
        if hasattr(self, "tools_tab"):
            self.tools_tab._copy_claude_mcp_config()

    def _copy_codex_mcp_config(self):
        """Codex用のMCP設定TOMLをコピー（ToolsTab へ委譲）"""
        if hasattr(self, "tools_tab"):
            self.tools_tab._copy_codex_mcp_config()

    def _copy_claude_code_cmd(self):
        """Claude Code用のmcp addコマンドをコピー（ToolsTab へ委譲）"""
        if hasattr(self, "tools_tab"):
            self.tools_tab._copy_claude_code_cmd()

    def _on_save(self):
        """設定を保存"""
        from llm_factory import get_llm_factory
        from mcp_manager import get_mcp_manager
        factory = get_llm_factory()
        mcp_mgr = get_mcp_manager()

        # 0. 表示言語設定の保存・反映
        selected_lang_code = "ja"
        if hasattr(self, "combo_language"):
            selected_display = self.combo_language.get()
            selected_lang_code = getattr(self, "_LANG_NAME_TO_CODE", {}).get(selected_display, "ja")
            i18n.set_language(selected_lang_code)
        
        # 1. LLM設定 ＆ 外部連携の保存
        llm_settings = self.llm_brain_tab.collect() if hasattr(self, "llm_brain_tab") else {}
        tools_settings = self.tools_tab.collect() if hasattr(self, "tools_tab") else {}
        new_settings = {
            "APP_LANGUAGE": selected_lang_code,
            **llm_settings,
            **tools_settings,
        }
        
        saved_llm = factory.save_settings(new_settings)
        if saved_llm:
            factory.DEFAULT_CONFIGS[factory.current_provider]["default_model"] = new_settings.get(f"{factory.current_provider.value.upper()}_MODEL")

        # 2. MCP ＆ 外部Webhook 設定の保存（ToolsTab へ委譲）
        if hasattr(self, "tools_tab"):
            self.tools_tab.save_additional_configs()

        saved_msg = (
            "⚙ AI設定 ＆ 外部連携（Google/GitHub/Slack/Webhook/MCP）を保存・適用しました！"
            if selected_lang_code == "ja"
            else "⚙ Settings & integrations (Google/GitHub/Slack/Webhook/MCP) saved and applied!"
        )
        self.parent_gui.update_message(saved_msg)
        self.destroy()

    def _download_local_model_gui(self, model_key: str = "350m"):
        """Hugging Faceから超軽量ローカルLLMをバックグラウンドでダウンロードして設定（LLMBrainTab へ委譲）"""
        if hasattr(self, "llm_brain_tab"):
            self.llm_brain_tab._download_local_model_gui(model_key)


    def destroy(self):
        try:
            from i18n import unsubscribe_language_change
            unsubscribe_language_change(self._on_language_changed)
        except Exception as e:
            logger.debug(f"設定画面破棄時の i18n 解除エラー: {e}")
        super().destroy()

    def _on_language_changed(self, lang: str) -> None:
        """言語変更イベントを受信し、設定画面のUI要素をリアルタイム更新する"""
        try:
            if not self.winfo_exists():
                return
            self.title(t("ui.settings.title"))
            if hasattr(self, "header_title") and self.header_title.winfo_exists():
                self.header_title.configure(text=t("ui.settings.title"))
            # サイドバーナビゲーションボタンの多言語更新
            for key, text_key in getattr(self, "nav_items_def", []):
                if key in self.nav_buttons and self.nav_buttons[key].winfo_exists():
                    self.nav_buttons[key].configure(text=t(text_key))
            if hasattr(self, "general_tab"):
                self.general_tab.refresh_texts()
            if hasattr(self, "agent_hooks_tab"):
                self.agent_hooks_tab.refresh_texts()
            if hasattr(self, "llm_brain_tab"):
                self.llm_brain_tab.refresh_texts()
            if hasattr(self, "tools_tab"):
                self.tools_tab.refresh_texts()
            if hasattr(self, "btn_save") and self.btn_save.winfo_exists():
                self.btn_save.configure(text=f"💾 {t('ui.settings.save')}")
            if hasattr(self, "btn_sync_all") and self.btn_sync_all.winfo_exists():
                self.btn_sync_all.configure(text=t("ui.settings.llm_sync_btn"))
            if hasattr(self, "lbl_sync_status") and self.lbl_sync_status.winfo_exists():
                self.lbl_sync_status.configure(text=t("ui.settings.llm_sync_note"))
        except Exception as e:
            logger.warning("設定画面言語更新エラー: %s", e)

    def _restart_tour(self) -> None:
        """設定画面の「使い方ガイド」タブからツアーを再開する（GuideTab へ委譲）。"""
        if hasattr(self, "guide_tab"):
            self.guide_tab._restart_tour()
        else:
            from ui.settings_tabs.guide_tab import GuideTab
            GuideTab(self.content_container, self.parent_gui, on_close=self.destroy)._restart_tour()

