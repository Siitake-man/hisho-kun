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
import customtkinter as ctk
from dotenv import load_dotenv

from ui.window_icon import apply_window_icon
from sync_config import SERVER_PORT

logger = logging.getLogger(__name__)

class AddMCPServerDialog(ctk.CTkToplevel):
    """
    ユーザーが任意のMCPサーバー（Google Calendar, Notion, Slack等）を追加するためのダイアログ。
    """
    def __init__(self, parent_settings, *args, **kwargs):
        super().__init__(parent_settings, *args, **kwargs)
        self.parent_settings = parent_settings
        self.title("➕ 新規MCPサーバーの追加")
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
        ctk.CTkLabel(self, text="➕ 新しいMCPサーバーを追加", font=self.font_title, text_color=self.primary_color).pack(pady=(12, 6))
        
        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=pad, pady=4)
        
        # 1. サーバーID
        ctk.CTkLabel(form, text="サーバー識別子 (例: google-calendar):", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_id = ctk.CTkEntry(form, placeholder_text="google-calendar")
        self.entry_id.pack(fill="x", pady=(0, 6))
        
        # 2. 表示名
        ctk.CTkLabel(form, text="表示名 (例: Google カレンダー連携):", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_name = ctk.CTkEntry(form, placeholder_text="Google カレンダー連携")
        self.entry_name.pack(fill="x", pady=(0, 6))
        
        # 3. 実行コマンド (command)
        ctk.CTkLabel(form, text="実行コマンド (例: npx, uvx, python):", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_cmd = ctk.CTkEntry(form, placeholder_text="npx")
        self.entry_cmd.insert(0, "npx")
        self.entry_cmd.pack(fill="x", pady=(0, 6))
        
        # 4. 引数 (args)
        ctk.CTkLabel(form, text="引数 (スペース区切り, 例: -y @modelcontextprotocol/server-xxx):", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_args = ctk.CTkEntry(form, placeholder_text="-y @modelcontextprotocol/server-google-calendar")
        self.entry_args.pack(fill="x", pady=(0, 6))
        
        # 5. 説明
        ctk.CTkLabel(form, text="概要・説明 (省略可):", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_desc = ctk.CTkEntry(form, placeholder_text="Googleカレンダーの予定を参照・登録します")
        self.entry_desc.pack(fill="x", pady=(0, 10))
        
        # 登録ボタン
        btn_add = ctk.CTkButton(
            self,
            text="✨ MCPサーバーを登録",
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
        self.title("💡 サジェストソース設定")
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
        ctk.CTkLabel(self, text="💡 インテリジェント・サジェスト設定", font=self.font_title, text_color=self.primary_color).pack(pady=(12, 4))
        ctk.CTkLabel(self, text="画面中央に表示する情報のソースを個別に選べます", font=self.font_small, text_color="#7A6B62").pack(pady=(0, 8))
        
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
                    text="関心キーワード (カンマ区切り):", 
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
            text="設定を保存して閉じる",
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
        self.title("ネオ秘書くん - AIモデル・API設定")
        self.geometry("480x620")
        
        self.bg_color = "#F5F5DC"
        self.primary_color = "#A67B5B"
        self.text_color = "#4A3B32"
        self.configure(fg_color=self.bg_color)
        
        self.font_title = ("DotGothic16", 15, "bold") if "DotGothic16" in tk.font.families() else ("Meiryo UI", 13, "bold")
        self.font_body = ("DotGothic16", 12) if "DotGothic16" in tk.font.families() else ("Meiryo UI", 10)
        self.font_small = ("Meiryo UI", 9)

        # 🖼️ ウィンドウアイコン (Alt+Tab/タスクバー) を統一 (例外安全 Seam)
        apply_window_icon(self)

        self._build_ui()

    def _build_ui(self):
        load_dotenv(override=True)
        from llm_factory import get_llm_factory, LLMProvider
        factory = get_llm_factory()
        
        # ヘッダー
        header = ctk.CTkFrame(self, fg_color=self.primary_color, corner_radius=0, height=45)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)
        
        title_label = ctk.CTkLabel(header, text="⚙ ネオ秘書くん 統合設定", font=self.font_title, text_color="#FFFFFF")
        title_label.pack(pady=8)
        
        # タブビュー領域
        self.tabview = ctk.CTkTabview(self, fg_color=self.bg_color, segmented_button_selected_color=self.primary_color, segmented_button_selected_hover_color="#8B634A")
        self.tabview.pack(side="top", fill="both", expand=True, padx=12, pady=(6, 5))
        
        tab_llm = self.tabview.add("🧠 AIモデル設定")
        tab_mcp = self.tabview.add("🤖 外部AI・MCP連携")
        tab_tools = self.tabview.add("📅 外部ツール・プラグイン")
        tab_devices = self.tabview.add("📱 接続端末管理")
        tab_guide = self.tabview.add("📖 使い方ガイド")

        # =====================================================================
        # Tab 1: AIモデル設定 (LLM Brain)
        # =====================================================================
        content_llm = ctk.CTkScrollableFrame(tab_llm, fg_color="transparent")
        content_llm.pack(fill="both", expand=True)

        # 🌐 一括モデル同期バナー
        sync_banner = ctk.CTkFrame(content_llm, fg_color="#EFEBE9", border_color=self.primary_color, border_width=1.5, corner_radius=8)
        sync_banner.pack(fill="x", pady=(4, 12), padx=2)
        
        sync_inner = ctk.CTkFrame(sync_banner, fg_color="transparent")
        sync_inner.pack(fill="x", padx=10, pady=8)
        
        ctk.CTkLabel(
            sync_inner, 
            text="🌐 接続先APIから最新モデル一覧を一括取得して更新", 
            font=self.font_body, 
            text_color=self.text_color
        ).pack(side="left")
        
        self.btn_sync_all = ctk.CTkButton(
            sync_inner,
            text="⚡ 今すぐ一括同期",
            font=self.font_small,
            fg_color=self.primary_color,
            hover_color="#8B634A",
            width=130,
            height=28,
            command=self._sync_all_models
        )
        self.btn_sync_all.pack(side="right")
        self.lbl_sync_status = ctk.CTkLabel(sync_banner, text="※ ドロップダウンは直接キーボード入力で任意の未来モデル・独自モデル名も手打ち指定可能です", font=("Meiryo UI", 8.5), text_color="#7A6B62")
        self.lbl_sync_status.pack(pady=(0, 6))

        # 1. Google Gemini
        sec_gemini = ctk.CTkLabel(content_llm, text="☁ Google Gemini (2026最新・高効率爆速)", font=self.font_title, text_color=self.primary_color, anchor="w")
        sec_gemini.pack(fill="x", pady=(5, 2))
        
        ctk.CTkLabel(content_llm, text="API Key:", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_gemini_key = ctk.CTkEntry(content_llm, placeholder_text="AIzaSy...", show="*")
        self.entry_gemini_key.insert(0, os.getenv("GOOGLE_API_KEY", ""))
        self.entry_gemini_key.pack(fill="x", pady=(0, 3))
        
        gemini_models = [m["id"] for m in factory.get_models_for_provider(LLMProvider.GEMINI)]
        current_gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
        
        btn_box_gemini = ctk.CTkFrame(content_llm, fg_color="transparent")
        btn_box_gemini.pack(fill="x", pady=(2, 2))
        ctk.CTkLabel(btn_box_gemini, text="使用モデル:", font=self.font_body, text_color=self.text_color).pack(side="left")
        self.btn_fetch_gemini = ctk.CTkButton(btn_box_gemini, text="🔄 一覧取得", width=90, height=24, font=self.font_small, fg_color="#8B634A", command=lambda: self._fetch_models("gemini"))
        self.btn_fetch_gemini.pack(side="right")
        
        self.combo_gemini_model = ctk.CTkComboBox(content_llm, values=gemini_models)
        self.combo_gemini_model.set(current_gemini_model)
        self.combo_gemini_model.pack(fill="x", pady=(0, 2))
        self.lbl_gemini_status = ctk.CTkLabel(content_llm, text="", font=self.font_small, text_color="#2E7D32", anchor="w")
        self.lbl_gemini_status.pack(fill="x", pady=(0, 8))

        # 2. Anthropic Claude
        sec_claude = ctk.CTkLabel(content_llm, text="🟣 Anthropic Claude (最新最高峰知能・エージェント最前線)", font=self.font_title, text_color=self.primary_color, anchor="w")
        sec_claude.pack(fill="x", pady=(5, 2))
        
        ctk.CTkLabel(content_llm, text="API Key:", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_claude_key = ctk.CTkEntry(content_llm, placeholder_text="sk-ant-...", show="*")
        self.entry_claude_key.insert(0, os.getenv("ANTHROPIC_API_KEY", ""))
        self.entry_claude_key.pack(fill="x", pady=(0, 3))
        
        claude_models = [m["id"] for m in factory.get_models_for_provider(LLMProvider.CLAUDE)]
        self.combo_claude_model = ctk.CTkComboBox(content_llm, values=claude_models)
        self.combo_claude_model.set(os.getenv("CLAUDE_MODEL", "claude-fable-5"))
        self.combo_claude_model.pack(fill="x", pady=(0, 8))

        # 3. OpenAI
        sec_openai = ctk.CTkLabel(content_llm, text="🟢 OpenAI (GPT-5.6 Sol / Terra / Luna)", font=self.font_title, text_color=self.primary_color, anchor="w")
        sec_openai.pack(fill="x", pady=(5, 2))
        
        ctk.CTkLabel(content_llm, text="API Key:", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_openai_key = ctk.CTkEntry(content_llm, placeholder_text="sk-...", show="*")
        self.entry_openai_key.insert(0, os.getenv("OPENAI_API_KEY", ""))
        self.entry_openai_key.pack(fill="x", pady=(0, 3))
        
        openai_models = [m["id"] for m in factory.get_models_for_provider(LLMProvider.OPENAI)]
        self.combo_openai_model = ctk.CTkComboBox(content_llm, values=openai_models)
        self.combo_openai_model.set(os.getenv("OPENAI_MODEL", "gpt-5.6-sol"))
        self.combo_openai_model.pack(fill="x", pady=(0, 8))

        # 4. OpenCode GO (DeepSeek)
        sec_opencode = ctk.CTkLabel(content_llm, text="⚡ OpenCode GO (DeepSeek V4 / R1)", font=self.font_title, text_color=self.primary_color, anchor="w")
        sec_opencode.pack(fill="x", pady=(5, 2))
        
        ctk.CTkLabel(content_llm, text="API Key:", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_opencode_key = ctk.CTkEntry(content_llm, placeholder_text="sk-...", show="*")
        self.entry_opencode_key.insert(0, os.getenv("OPENCODE_API_KEY", ""))
        self.entry_opencode_key.pack(fill="x", pady=(0, 3))
        
        ctk.CTkLabel(content_llm, text="Base URL:", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_opencode_url = ctk.CTkEntry(content_llm, placeholder_text="https://api.opencode.go.jp/v1")
        self.entry_opencode_url.insert(0, os.getenv("OPENCODE_BASE_URL", "https://api.opencode.go.jp/v1"))
        self.entry_opencode_url.pack(fill="x", pady=(0, 3))
        
        opencode_models = [m["id"] for m in factory.get_models_for_provider(LLMProvider.OPENCODE)]
        btn_box1 = ctk.CTkFrame(content_llm, fg_color="transparent")
        btn_box1.pack(fill="x", pady=(2, 2))
        ctk.CTkLabel(btn_box1, text="使用モデル:", font=self.font_body, text_color=self.text_color).pack(side="left")
        self.btn_fetch_opencode = ctk.CTkButton(btn_box1, text="🔄 一覧取得", width=90, height=24, font=self.font_small, fg_color="#8B634A", command=lambda: self._fetch_models("opencode"))
        self.btn_fetch_opencode.pack(side="right")
        
        self.combo_opencode_model = ctk.CTkComboBox(content_llm, values=opencode_models)
        self.combo_opencode_model.set(os.getenv("OPENCODE_MODEL", "deepseek-v4-pro"))
        self.combo_opencode_model.pack(fill="x", pady=(0, 2))
        self.lbl_opencode_status = ctk.CTkLabel(content_llm, text="", font=self.font_small, text_color="#2E7D32", anchor="w")
        self.lbl_opencode_status.pack(fill="x", pady=(0, 8))

        # 5. Groq / OpenRouter
        sec_groq = ctk.CTkLabel(content_llm, text="🚀 Groq / OpenRouter (超爆速・万能ハブ)", font=self.font_title, text_color=self.primary_color, anchor="w")
        sec_groq.pack(fill="x", pady=(5, 2))
        
        ctk.CTkLabel(content_llm, text="Groq API Key (gsk_...):", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_groq_key = ctk.CTkEntry(content_llm, placeholder_text="gsk_...", show="*")
        self.entry_groq_key.insert(0, os.getenv("GROQ_API_KEY", ""))
        self.entry_groq_key.pack(fill="x", pady=(0, 3))

        ctk.CTkLabel(content_llm, text="OpenRouter API Key (sk-or-...):", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_openrouter_key = ctk.CTkEntry(content_llm, placeholder_text="sk-or-...", show="*")
        self.entry_openrouter_key.insert(0, os.getenv("OPENROUTER_API_KEY", ""))
        self.entry_openrouter_key.pack(fill="x", pady=(0, 8))

        # 6. 内包ローカルLLM (GGUF / Sidecar) ＆ Ollama
        sec_local = ctk.CTkLabel(content_llm, text="📦 内包ローカルLLM (LFM 2.5 / 完全オフライン)", font=self.font_title, text_color=self.primary_color, anchor="w")
        sec_local.pack(fill="x", pady=(5, 2))
        
        local_card = ctk.CTkFrame(content_llm, fg_color="#F5EFEB", border_color="#D7CCC8", border_width=1, corner_radius=6)
        local_card.pack(fill="x", pady=(2, 6))

        # モデルダウンロードカード内UI
        card_inner = ctk.CTkFrame(local_card, fg_color="transparent")
        card_inner.pack(fill="x", padx=8, pady=6)

        ctk.CTkLabel(
            card_inner, 
            text="APIキー不要！完全オフラインで動く超軽量モデル (Liquid AI LFM2.5・230MB)", 
            font=("Meiryo UI", 9, "bold"), 
            text_color="#5D4037", 
            anchor="w"
        ).pack(fill="x", pady=(0, 4))

        # DLボタン行
        dl_btn_row = ctk.CTkFrame(card_inner, fg_color="transparent")
        dl_btn_row.pack(fill="x", pady=(0, 4))

        self.btn_dl_local_350m = ctk.CTkButton(
            dl_btn_row,
            text="⚡ 超軽量モデル (350M / 約230MB) を今すぐダウンロード",
            font=("Meiryo UI", 9.5, "bold"),
            fg_color="#2E7D32",
            hover_color="#1B5E20",
            height=28,
            command=lambda: self._download_local_model_gui("350m")
        )
        self.btn_dl_local_350m.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_fetch_local = ctk.CTkButton(
            dl_btn_row,
            text="🔄 models/再スキャン",
            width=110,
            height=28,
            font=self.font_small,
            fg_color="#8B634A",
            hover_color="#6D4C41",
            command=lambda: self._fetch_models("local_gguf")
        )
        self.btn_fetch_local.pack(side="right")

        # 進捗バー（初期非表示）
        self.progress_bar_local = ctk.CTkProgressBar(card_inner, fg_color="#D7CCC8", progress_color="#2E7D32")
        self.progress_bar_local.set(0)
        
        # ステータスラベル
        import app_paths
        has_350m = (app_paths.get_app_root() / "models" / "LFM2.5-350M-QAD-Q4_0.gguf").exists()
        status_init_text = "✅ 超軽量モデル (350M) は導入済みです" if has_350m else "※ ワンクリックで Hugging Face から自動ダウンロード・設定されます"
        status_init_color = "#2E7D32" if has_350m else "#757575"
        self.lbl_dl_status = ctk.CTkLabel(card_inner, text=status_init_text, font=self.font_small, text_color=status_init_color, anchor="w")
        self.lbl_dl_status.pack(fill="x", pady=(2, 4))

        local_models = [m["id"] for m in factory.get_models_for_provider(LLMProvider.LOCAL_GGUF)]
        ctk.CTkLabel(card_inner, text="選択中GGUFモデル (models/):", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x", pady=(2, 0))
        self.combo_local_model = ctk.CTkComboBox(card_inner, values=local_models)
        self.combo_local_model.set(os.getenv("LOCAL_GGUF_MODEL", "LFM2.5-350M-QAD-Q4_0.gguf" if has_350m else "lfm2.5-2.6b"))
        self.combo_local_model.pack(fill="x", pady=(2, 2))
        
        # 7. 任意カスタムOpenAI互換 (Custom API / vLLM / 自前サーバー / 独自エンドポイント)
        sec_custom = ctk.CTkLabel(content_llm, text="⚡ 任意カスタムOpenAI互換 (Custom API / vLLM / 独自モデル)", font=self.font_title, text_color=self.primary_color, anchor="w")
        sec_custom.pack(fill="x", pady=(8, 2))
        
        ctk.CTkLabel(content_llm, text="Base URL (例: https://api.together.xyz/v1 や http://192.168.1.50:8000/v1):", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_custom_url = ctk.CTkEntry(content_llm, placeholder_text="http://localhost:8000/v1")
        self.entry_custom_url.insert(0, os.getenv("CUSTOM_OPENAI_BASE_URL", "http://localhost:8000/v1"))
        self.entry_custom_url.pack(fill="x", pady=(0, 3))

        ctk.CTkLabel(content_llm, text="API Key (省略時は local):", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_custom_key = ctk.CTkEntry(content_llm, placeholder_text="sk-...", show="*")
        self.entry_custom_key.insert(0, os.getenv("CUSTOM_OPENAI_API_KEY", ""))
        self.entry_custom_key.pack(fill="x", pady=(0, 3))

        custom_models = [m["id"] for m in factory.get_models_for_provider(LLMProvider.CUSTOM_OPENAI)]
        btn_box_custom = ctk.CTkFrame(content_llm, fg_color="transparent")
        btn_box_custom.pack(fill="x", pady=(2, 2))
        ctk.CTkLabel(btn_box_custom, text="指定モデル名 (直接手入力可):", font=self.font_body, text_color=self.text_color).pack(side="left")
        self.btn_fetch_custom = ctk.CTkButton(btn_box_custom, text="🔄 一覧取得", width=90, height=24, font=self.font_small, fg_color="#8B634A", command=lambda: self._fetch_models("custom_openai"))
        self.btn_fetch_custom.pack(side="right")

        self.combo_custom_model = ctk.CTkComboBox(content_llm, values=custom_models)
        self.combo_custom_model.set(os.getenv("CUSTOM_OPENAI_MODEL", "custom-model"))
        self.combo_custom_model.pack(fill="x", pady=(0, 2))
        self.lbl_custom_status = ctk.CTkLabel(content_llm, text="", font=self.font_small, text_color="#2E7D32", anchor="w")
        self.lbl_custom_status.pack(fill="x", pady=(0, 8))

        # =====================================================================
        # Tab 2: 外部AI・MCP連携 (Agent Bridge & Configs)
        # =====================================================================
        content_mcp = ctk.CTkScrollableFrame(tab_mcp, fg_color="transparent")
        content_mcp.pack(fill="both", expand=True)

        guide_desc = (
            "Codex, Claude Code, Cursor, Antigravity 等のコーディングAIにネオ秘書くんの\n"
            "MCPサーバー（スマホ承認・質問回答・作業完了通知・知識の宝庫）を登録します。\n"
            "下のボタンから各ツールの設定ファイル用コードを1クリックでコピーできます。"
        )
        ctk.CTkLabel(content_mcp, text=guide_desc, font=self.font_small, text_color="#5D4037", justify="left", anchor="w").pack(fill="x", pady=(0, 8))

        # 1. Claude Desktop / Cursor / Antigravity (JSON)
        card_claude = ctk.CTkFrame(content_mcp, fg_color="#FFF8E7", border_width=1, border_color="#A67B5B", corner_radius=6)
        card_claude.pack(fill="x", pady=4, padx=2)
        ctk.CTkLabel(card_claude, text="📦 Antigravity / Claude Desktop / Cursor (ワンクリック自動登録)", font=("Meiryo UI", 10.5, "bold"), text_color="#4A3B32", anchor="w").pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(card_claude, text="お使いのAIツールの設定JSONに、現在のパスで自動注入・登録します。", font=self.font_small, text_color="#8D6E63", anchor="w").pack(fill="x", padx=8, pady=(0, 4))
        
        btn_box = ctk.CTkFrame(card_claude, fg_color="transparent")
        btn_box.pack(fill="x", padx=8, pady=(0, 6))
        
        ctk.CTkButton(
            btn_box,
            text="🚀 Antigravityに自動登録",
            font=("Meiryo UI", 9.5, "bold"),
            fg_color="#2E7D32",
            hover_color="#1B5E20",
            height=26,
            command=lambda: self._auto_install_mcp("antigravity")
        ).pack(side="left", fill="x", expand=True, padx=(0, 2))
        
        ctk.CTkButton(
            btn_box,
            text="🚀 Claude Desktopに自動登録",
            font=("Meiryo UI", 9.5, "bold"),
            fg_color="#D84315",
            hover_color="#BF360C",
            height=26,
            command=lambda: self._auto_install_mcp("claude_desktop")
        ).pack(side="left", fill="x", expand=True, padx=(2, 0))
        
        ctk.CTkButton(
            card_claude,
            text="📋 手動用 MCP設定JSONをコピー",
            font=("Meiryo UI", 9.0),
            fg_color=self.primary_color,
            hover_color="#8B634A",
            height=24,
            command=self._copy_claude_mcp_config
        ).pack(fill="x", padx=8, pady=(0, 6))

        # 2. Codex (TOML / Config)
        card_codex = ctk.CTkFrame(content_mcp, fg_color="#E3F2FD", border_width=1, border_color="#1565C0", corner_radius=6)
        card_codex.pack(fill="x", pady=4, padx=2)
        ctk.CTkLabel(card_codex, text="🤖 Codex 設定 (TOML / Config)", font=("Meiryo UI", 10.5, "bold"), text_color="#0D47A1", anchor="w").pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(card_codex, text="Codex の MCP設定ファイル（config.toml）に貼り付けます。", font=self.font_small, text_color="#1565C0", anchor="w").pack(fill="x", padx=8, pady=(0, 4))
        ctk.CTkButton(
            card_codex,
            text="📋 Codex用 MCP設定TOMLをコピー",
            font=("Meiryo UI", 9.5, "bold"),
            fg_color="#1565C0",
            hover_color="#0D47A1",
            height=26,
            command=self._copy_codex_mcp_config
        ).pack(fill="x", padx=8, pady=(0, 6))

        # 3. Claude Code (CLI Command)
        card_claudecode = ctk.CTkFrame(content_mcp, fg_color="#F3E5F5", border_width=1, border_color="#7B1FA2", corner_radius=6)
        card_claudecode.pack(fill="x", pady=4, padx=2)
        ctk.CTkLabel(card_claudecode, text="⚡ Claude Code (CLI登録コマンド)", font=("Meiryo UI", 10.5, "bold"), text_color="#4A148C", anchor="w").pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(card_claudecode, text="ターミナルで `claude mcp add` コマンドを一発実行します。", font=self.font_small, text_color="#7B1FA2", anchor="w").pack(fill="x", padx=8, pady=(0, 4))
        ctk.CTkButton(
            card_claudecode,
            text="📋 Claude Code登録コマンドをコピー",
            font=("Meiryo UI", 9.5, "bold"),
            fg_color="#7B1FA2",
            hover_color="#4A148C",
            height=26,
            command=self._copy_claude_code_cmd
        ).pack(fill="x", padx=8, pady=(0, 6))

        self.lbl_copy_toast = ctk.CTkLabel(content_mcp, text="", font=self.font_small, text_color="#2E7D32", anchor="w")
        self.lbl_copy_toast.pack(fill="x", padx=4, pady=4)

        # 4. 音声ナレーション設定 (Voice Narration on Task Completion)
        card_voice = ctk.CTkFrame(content_mcp, fg_color="#F1F8E9", border_width=1, border_color="#7CB342", corner_radius=6)
        card_voice.pack(fill="x", pady=4, padx=2)
        ctk.CTkLabel(card_voice, text="🔊 PC音声読み上げ通知 (タスク完了ナレーション)", font=("Meiryo UI", 10.5, "bold"), text_color="#33691E", anchor="w").pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(
            card_voice,
            text="外部AI（Antigravity, Claude Code等）のタスク完了時に、PCスピーカーから音声で報告を読み上げます。\n（※オフィスや夜間、静かな環境ではOFFを推奨します）",
            font=self.font_small,
            text_color="#558B2F",
            anchor="w",
            justify="left"
        ).pack(fill="x", padx=8, pady=(0, 4))

        voice_init = os.getenv("VOICE_NARRATION_ENABLED", "false").lower() in ("true", "1", "yes")
        self.var_voice_narration = tk.BooleanVar(value=voice_init)
        self.chk_voice_narration = ctk.CTkSwitch(
            card_voice,
            text="PC音声読み上げを有効化する",
            variable=self.var_voice_narration,
            font=("Meiryo UI", 9.5),
            progress_color="#558B2F"
        )
        self.chk_voice_narration.pack(anchor="w", padx=8, pady=(2, 6))

        # =====================================================================
        # Tab 3: カレンダー・Google・GitHub・プラグイン
        # =====================================================================
        content_tools = ctk.CTkScrollableFrame(tab_tools, fg_color="transparent")
        content_tools.pack(fill="both", expand=True)

        # 1. Google サービス統合 (Workspace / Gmail / Calendar OAuth 2.0)
        card_google = ctk.CTkFrame(content_tools, fg_color="#FFFFFF", border_width=1, border_color="#E0D8C8", corner_radius=6)
        card_google.pack(fill="x", pady=4, padx=2)
        
        # ヘッダーと認証状態バッジ
        g_head_row = ctk.CTkFrame(card_google, fg_color="transparent")
        g_head_row.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(g_head_row, text="📅 Google サービス連携 (Calendar / Gmail)", font=("Meiryo UI", 11, "bold"), text_color="#D32F2F").pack(side="left")
        
        import google_workspace_tools
        g_status = google_workspace_tools.get_google_auth_status()
        
        self.lbl_google_badge = ctk.CTkLabel(
            g_head_row, 
            text="🟢 連携済み" if g_status["authenticated"] else "⚪ 未認証", 
            font=("Meiryo UI", 9.5, "bold"), 
            text_color="#2E7D32" if g_status["authenticated"] else "#757575"
        )
        self.lbl_google_badge.pack(side="right")
        
        self.lbl_google_info = ctk.CTkLabel(
            card_google, 
            text=g_status["message"], 
            font=self.font_small, 
            text_color="#2E7D32" if g_status["authenticated"] else "#616161", 
            anchor="w"
        )
        self.lbl_google_info.pack(fill="x", padx=8, pady=(0, 4))
        
        ctk.CTkLabel(card_google, text="Google Calendar ID (初期値: primary):", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x", padx=8)
        self.entry_google_cal = ctk.CTkEntry(card_google, placeholder_text="primary または your_email@gmail.com")
        self.entry_google_cal.insert(0, os.getenv("GOOGLE_CALENDAR_ID", "primary"))
        self.entry_google_cal.pack(fill="x", padx=8, pady=(2, 6))

        # Google 操作ボタングループ
        g_btn_row = ctk.CTkFrame(card_google, fg_color="transparent")
        g_btn_row.pack(fill="x", padx=8, pady=(0, 6))
        
        self.btn_google_auth = ctk.CTkButton(
            g_btn_row,
            text="🔗 Googleアカウントで認証ログイン",
            font=self.font_small,
            fg_color="#D32F2F",
            hover_color="#B71C1C",
            height=24,
            command=self._run_google_oauth
        )
        self.btn_google_auth.pack(side="left", padx=(0, 4))
        
        self.btn_google_test = ctk.CTkButton(
            g_btn_row,
            text="🔍 同期テスト",
            font=self.font_small,
            fg_color="#5D4037",
            hover_color="#4E342E",
            height=24,
            command=self._test_google_connection
        )
        self.btn_google_test.pack(side="left", padx=(0, 4))

        self.btn_google_logout = ctk.CTkButton(
            g_btn_row,
            text="🚪 ログアウト",
            font=self.font_small,
            fg_color="#757575",
            hover_color="#616161",
            height=24,
            command=self._logout_google
        )
        self.btn_google_logout.pack(side="left")

        # 1.5. Google カレンダー 秘密iCal URL 連携（読み取り専用・OAuth不要） [2026-08-25]
        card_ical = ctk.CTkFrame(content_tools, fg_color="#FFFFFF", border_width=1, border_color="#E0D8C8", corner_radius=6)
        card_ical.pack(fill="x", pady=4, padx=2)
        ctk.CTkLabel(card_ical, text="📅 Google カレンダー連携 (読み取り専用・OAuth不要・複数登録可)", font=("Meiryo UI", 11, "bold"), text_color="#1565C0", anchor="w").pack(fill="x", padx=8, pady=(6, 2))

        # 取得手順の説明
        ctk.CTkLabel(
            card_ical,
            text=(
                "【取得手順（1回だけ・約1分）】\n"
                "1. Googleカレンダー（PC版）を開く\n"
                "2. 左側のカレンダー名の「⋮」→「設定と共有」\n"
                "3. ページ下部「予定の取得用の秘密のアドレス (iCal)」のURLをコピー\n"
                "4. 「＋ 購読を追加」で行を作りURLを貼り付け「🔄 すべて同期」を押す\n"
                "※ 仕事用・プライベートなど複数のカレンダーを色分け登録できます（☐で一時OFF）"
            ),
            font=self.font_small,
            text_color="#1565C0",
            anchor="w",
            justify="left"
        ).pack(fill="x", padx=8, pady=(0, 4))

        # 読み取り専用の注意書き
        ctk.CTkLabel(
            card_ical,
            text=(
                "⚠️ 注意: この連携は「Googleカレンダーの表示のみ」です。\n"
                "秘書くん側で追加した予定を Google カレンダーへ反映することはできません。\n"
                "（OAuth・パスワード不要の安全でシンプルな方式です。URLは他人に教えないでください）"
            ),
            font=self.font_small,
            text_color="#E65100",
            anchor="w",
            wraplength=420,
            justify="left"
        ).pack(fill="x", padx=8, pady=(0, 4))

        # 購読ソース一覧（仕事用/プライベート等の複数iCalを管理）
        ctk.CTkLabel(card_ical, text="購読カレンダー（☐で一時OFF・色ボタンで色変更）:", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x", padx=8, pady=(2, 0))

        self.sources_scroll = ctk.CTkScrollableFrame(card_ical, fg_color="#FAF6EC", height=150)
        self.sources_scroll.pack(fill="x", padx=8, pady=(2, 4))

        ical_btn_row = ctk.CTkFrame(card_ical, fg_color="transparent")
        ical_btn_row.pack(fill="x", padx=8, pady=(0, 6))

        self.btn_ical_sync = ctk.CTkButton(
            ical_btn_row,
            text="🔄 すべて同期",
            font=self.font_small,
            fg_color="#1565C0",
            hover_color="#0D47A1",
            height=24,
            command=self._sync_ical_now
        )
        self.btn_ical_sync.pack(side="left")

        ctk.CTkButton(
            ical_btn_row,
            text="＋ 購読を追加",
            font=self.font_small,
            fg_color="#A67B5B",
            hover_color="#8B634A",
            height=24,
            command=self._on_add_calendar_source
        ).pack(side="left", padx=(6, 0))

        self.lbl_ical_last_sync = ctk.CTkLabel(
            ical_btn_row,
            text="（以後30分ごとに自動同期）",
            font=self.font_small,
            text_color="#757575"
        )
        self.lbl_ical_last_sync.pack(side="left", padx=(8, 0))

        self._render_calendar_sources()

        # 1.7. 外出先接続 (Tailscale VPN) [2026-08-25]
        card_tailscale = ctk.CTkFrame(content_tools, fg_color="#FFFFFF", border_width=1, border_color="#E0D8C8", corner_radius=6)
        card_tailscale.pack(fill="x", pady=4, padx=2)
        ctk.CTkLabel(card_tailscale, text="🌐 外出先接続 (Tailscale VPN)", font=("Meiryo UI", 11, "bold"), text_color="#6A1B9A", anchor="w").pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(
            card_tailscale,
            text=(
                "カフェ等の外出先Wi-Fi（端末間通信が禁止されたネットワーク）からでも\n"
                "スマホDesk Petへ接続できるようにします。\n"
                "【手順】1. PCとスマホ両方に Tailscale を入れ、同じアカウントでログイン\n"
                f"　 　 2. PC側でコマンド実行: tailscale serve {SERVER_PORT}\n"
                "　 　 3. 下の欄にPCのTailscaleホスト名（例: hisyo-pc.tailXXXX.ts.net）を保存\n"
                "詳細は docs/guides/TAILSCALE_SETUP.md を参照"
            ),
            font=self.font_small,
            text_color="#6A1B9A",
            anchor="w",
            wraplength=420,
            justify="left"
        ).pack(fill="x", padx=8, pady=(0, 4))

        ctk.CTkLabel(card_tailscale, text="PCの Tailscale ホスト名:", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x", padx=8)
        self.entry_tailscale_host = ctk.CTkEntry(card_tailscale, placeholder_text="hisyo-pc.tailXXXX.ts.net")
        self.entry_tailscale_host.insert(0, os.getenv("TAILSCALE_HOSTNAME", ""))
        self.entry_tailscale_host.pack(fill="x", padx=8, pady=(2, 4))

        ctk.CTkButton(
            card_tailscale,
            text="💾 ホスト名を保存",
            font=self.font_small,
            fg_color="#6A1B9A",
            hover_color="#4A148C",
            height=24,
            command=self._save_tailscale_host
        ).pack(anchor="w", padx=8, pady=(0, 6))

        # 1.8. スマホ連携 全解除 (トークン再生成) [2026-09-01 3周レビュー P1対応]
        card_token = ctk.CTkFrame(content_tools, fg_color="#FFFFFF", border_width=1, border_color="#E0D8C8", corner_radius=6)
        card_token.pack(fill="x", pady=4, padx=2)
        ctk.CTkLabel(card_token, text="📱 スマホ連携の全解除 (トークン再生成)", font=("Meiryo UI", 11, "bold"), text_color="#C62828", anchor="w").pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(
            card_token,
            text=(
                "スマホ側に保存された接続トークンをワンクリックで無効化します。\n"
                "端末の紛失・売却・譲渡前に実行してください。解除後はスマホと\n"
                "再ペアリング（QR接続）するまでスマホ側から接続できなくなります。"
            ),
            font=self.font_small,
            text_color="#757575",
            anchor="w",
            wraplength=420,
            justify="left"
        ).pack(fill="x", padx=8, pady=(0, 4))

        self.btn_revoke_sync_token = ctk.CTkButton(
            card_token,
            text="🚫 スマホ連携をすべて解除（トークン再生成）",
            font=self.font_small,
            fg_color="#C62828",
            hover_color="#8E0000",
            height=26,
            command=self._revoke_sync_token
        )
        self.btn_revoke_sync_token.pack(fill="x", padx=8, pady=(0, 6))

        # 2. GitHub サービス統合
        card_github = ctk.CTkFrame(content_tools, fg_color="#FFFFFF", border_width=1, border_color="#E0D8C8", corner_radius=6)
        card_github.pack(fill="x", pady=4, padx=2)
        ctk.CTkLabel(card_github, text="🐙 GitHub 連携設定 (Issue / PR / 監視)", font=("Meiryo UI", 11, "bold"), text_color="#24292E", anchor="w").pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(card_github, text="リポジトリのIssue・PR・コミット状態を秘書くんが通知・連携します。", font=self.font_small, text_color="#757575", anchor="w").pack(fill="x", padx=8, pady=(0, 4))

        ctk.CTkLabel(card_github, text="Personal Access Token (PAT):", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x", padx=8)
        self.entry_github_token = ctk.CTkEntry(card_github, placeholder_text="ghp_...", show="*")
        self.entry_github_token.insert(0, os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", os.getenv("GITHUB_TOKEN", "")))
        self.entry_github_token.pack(fill="x", padx=8, pady=(2, 4))

        ctk.CTkLabel(card_github, text="対象リポジトリ (例: owner/repo):", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x", padx=8)
        self.entry_github_repo = ctk.CTkEntry(card_github, placeholder_text="Siitake-man/hisho-kun")
        self.entry_github_repo.insert(0, os.getenv("GITHUB_REPO", "Siitake-man/hisho-kun"))
        self.entry_github_repo.pack(fill="x", padx=8, pady=(2, 6))

        gh_btn_row = ctk.CTkFrame(card_github, fg_color="transparent")
        gh_btn_row.pack(fill="x", padx=8, pady=(0, 6))
        self.btn_gh_test = ctk.CTkButton(
            gh_btn_row,
            text="🔍 GitHub接続テスト",
            font=self.font_small,
            fg_color="#24292E",
            hover_color="#1B1F23",
            height=24,
            command=self._test_github_connection
        )
        self.btn_gh_test.pack(side="left")
        self.lbl_gh_status = ctk.CTkLabel(gh_btn_row, text="", font=self.font_small, text_color="#2E7D32")
        self.lbl_gh_status.pack(side="left", padx=8)

        # 3. Slack Webhook 連携
        card_slack = ctk.CTkFrame(content_tools, fg_color="#FFFFFF", border_width=1, border_color="#E0D8C8", corner_radius=6)
        card_slack.pack(fill="x", pady=4, padx=2)
        ctk.CTkLabel(card_slack, text="💬 Slack Webhook 連携", font=("Meiryo UI", 11, "bold"), text_color="#4A154B", anchor="w").pack(fill="x", padx=8, pady=(6, 2))
        
        ctk.CTkLabel(card_slack, text="Webhook URL:", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x", padx=8)
        self.entry_slack_webhook = ctk.CTkEntry(card_slack, placeholder_text="https://hooks.slack.com/services/...")
        self.entry_slack_webhook.insert(0, os.getenv("SLACK_WEBHOOK_URL", ""))
        self.entry_slack_webhook.pack(fill="x", padx=8, pady=(2, 6))

        # 3.5. 外部SaaS・マルチ中継 Webhook (Zapier / Make / GAS / IFTTT)
        import webhook_tools
        wh_cfg = webhook_tools.get_webhook_config()
        
        card_webhook = ctk.CTkFrame(content_tools, fg_color="#FFFFFF", border_width=1, border_color="#E0D8C8", corner_radius=6)
        card_webhook.pack(fill="x", pady=4, padx=2)
        ctk.CTkLabel(card_webhook, text="🌐 外部SaaS・マルチ中継 Webhook (Zapier / Make / GAS)", font=("Meiryo UI", 11, "bold"), text_color="#0D47A1", anchor="w").pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(card_webhook, text="Google認証の人数制限を回避し、予定やTODOをZapier/Make/GAS経由で双方向同期します。", font=self.font_small, text_color="#757575", anchor="w").pack(fill="x", padx=8, pady=(0, 4))

        ctk.CTkLabel(card_webhook, text="送信先 Webhook URL (Zapier / Make / GAS):", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x", padx=8)
        self.entry_webhook_outgoing = ctk.CTkEntry(card_webhook, placeholder_text="https://hooks.zapier.com/hooks/catch/...")
        self.entry_webhook_outgoing.insert(0, wh_cfg.get("outgoing_webhook_url", ""))
        self.entry_webhook_outgoing.pack(fill="x", padx=8, pady=(2, 4))

        ctk.CTkLabel(card_webhook, text="Webhook 共有シークレット (任意・認証用):", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x", padx=8)
        self.entry_webhook_secret = ctk.CTkEntry(card_webhook, placeholder_text="任意のパスワードまたは未設定", show="*")
        self.entry_webhook_secret.insert(0, wh_cfg.get("webhook_secret", ""))
        self.entry_webhook_secret.pack(fill="x", padx=8, pady=(2, 4))

        wh_info_frame = ctk.CTkFrame(card_webhook, fg_color="#F5F5F5", corner_radius=4)
        wh_info_frame.pack(fill="x", padx=8, pady=(2, 6))
        ctk.CTkLabel(wh_info_frame, text="📥 秘書くん受信用 URL (外部からPOST送信):", font=("Meiryo UI", 8, "bold"), text_color="#5D4037", anchor="w").pack(anchor="w", padx=6, pady=(4, 1))
        ctk.CTkLabel(wh_info_frame, text=f"予定: http://<PCのIP>:{SERVER_PORT}/api/webhook/calendar\nタスク: http://<PCのIP>:{SERVER_PORT}/api/webhook/task", font=("Consolas", 8), text_color="#424242", justify="left", anchor="w").pack(anchor="w", padx=6, pady=(0, 4))

        # 4. 外部MCPプラグイン一覧
        card_mcp_list = ctk.CTkFrame(content_tools, fg_color="#FFFFFF", border_width=1, border_color="#E0D8C8", corner_radius=6)
        card_mcp_list.pack(fill="x", pady=4, padx=2)
        
        from mcp_manager import get_mcp_manager
        mcp_mgr = get_mcp_manager()
        server_configs = mcp_mgr.get_server_configs()
        
        mcp_header_box = ctk.CTkFrame(card_mcp_list, fg_color="transparent")
        mcp_header_box.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(mcp_header_box, text="🔌 外部MCPプラグイン一覧", font=("Meiryo UI", 11, "bold"), text_color=self.primary_color).pack(side="left")
        btn_add_mcp = ctk.CTkButton(mcp_header_box, text="➕ 追加", width=50, height=22, font=self.font_small, fg_color="#8B634A", command=self._open_add_mcp_dialog)
        btn_add_mcp.pack(side="right")

        self.mcp_checkboxes = {}
        for s_id, s_conf in server_configs.items():
            row = ctk.CTkFrame(card_mcp_list, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=2)
            is_enabled = s_conf.get("enabled", False) if isinstance(s_conf, dict) else getattr(s_conf, "enabled", False)
            s_name = s_conf.get("name", s_id) if isinstance(s_conf, dict) else getattr(s_conf, "name", s_id)
            var = tk.BooleanVar(value=is_enabled)
            self.mcp_checkboxes[s_id] = var
            cb = ctk.CTkCheckBox(row, text=s_name, variable=var, font=self.font_body, text_color=self.text_color)
            cb.pack(side="left")
            btn_del = ctk.CTkButton(row, text="🗑️", width=26, height=20, font=self.font_small, fg_color="#D9534F", hover_color="#C9302C", command=lambda sid=s_id: self._delete_mcp_server(sid))
            btn_del.pack(side="right")

        # =====================================================================
        # Tab 4: 使い方ガイド
        # =====================================================================
        content_guide = ctk.CTkScrollableFrame(tab_guide, fg_color="transparent")
        content_guide.pack(fill="both", expand=True, padx=8, pady=6)

        # クイックスタート
        ctk.CTkLabel(content_guide, text="🚀 クイックスタート", font=self.font_title,
                      text_color=self.primary_color, anchor="w").pack(anchor="w", pady=(6, 2))
        guide_texts = [
            ("📋 メニューの開き方", "ペットを右クリック、またはヘッダーの⚙️メニューボタンで機能一覧が開きます。"),
            ("📱 スマホ連携", "右クリック → 📱スマホ接続 → QRコードをスマホで読み取るだけ。同一Wi-Fiが必須。"),
            ("📔 手帳の使い方", "📔統合手帳で予定・TODO・習慣を確認。GoogleカレンダーiCal URLを設定すると自動同期。"),
            ("🍅 ポモドーロ", "🍅ポモドーロ開始で25分集中。ペットが集中モードに変わります。"),
            ("🧠 AIモデル切替", "右クリック → LLMモデル切り替え から利用するAIモデルを選択できます。"),
            ("🎭 キャラ切替", "右クリック → キャラクタースキン変更 で秘書くん/カイル風精霊を切替。"),
            ("🤖 AIエージェント連携", "MCP連携タブでmcp_installer.pyを実行すると、Cline/Claude等から秘書くんのツールを呼び出せます。"),
        ]
        for title, desc in guide_texts:
            row = ctk.CTkFrame(content_guide, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=title, font=self.font_title,
                          text_color=self.text_color, anchor="w").pack(anchor="w")
            ctk.CTkLabel(row, text=desc, font=self.font_small,
                          text_color="#7A6B62", anchor="w", wraplength=400).pack(anchor="w", padx=(12, 0))

        # ツアー再開ボタン
        ctk.CTkLabel(content_guide, text="", height=10).pack()
        btn_restart_tour = ctk.CTkButton(
            content_guide, text="🎓 秘書くんツアーをもう一度見る",
            font=self.font_body, fg_color=self.primary_color,
            hover_color="#8B634A", height=34,
            command=self._restart_tour
        )
        btn_restart_tour.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(content_guide, text="※ 初回起動時のオンボーディングツアーを再開できます。",
                      font=self.font_small, text_color="#A67B5B", anchor="w").pack(anchor="w", padx=20)

        # 注意事項
        ctk.CTkLabel(content_guide, text="", height=8).pack()
        ctk.CTkLabel(content_guide, text="⚠️ 注意事項", font=self.font_title,
                      text_color=self.primary_color, anchor="w").pack(anchor="w", pady=(6, 2))
        notices = [
            "• スマホ連携にはPCと同じWi-Fiネットワークが必要です。",
            "• 外出先からはTailscale VPN経由で接続できます。",
            "• Googleカレンダー連携は読み取り専用（iCal URL）です。",
            "• LLMのAPIキーは各自ご用意ください（.envファイルに設定）。",
            "• 詳細な使い方は docs/ 配下のドキュメントをご参照ください。",
        ]
        for n in notices:
            ctk.CTkLabel(content_guide, text=n, font=self.font_small,
                          text_color="#7A6B62", anchor="w", wraplength=400).pack(anchor="w", padx=(8, 0))

        # =====================================================================
        # Tab 5: 接続端末管理（ゼロトラスト端末台帳）
        #   Sprint C 先取り (2026-09-16): 台帳の表示・Revoke は
        #   ui/device_manager_panel.py の Deep Module へ委譲し、
        #   本画面はセクションを差し込むだけに留める (肥大化防止)。
        # =====================================================================
        from ui.device_manager_panel import DeviceManagerSection

        # dispatch=parent_gui.post_action により、台帳読み出しはワーカースレッドで実行され
        # 結果だけがメインスレッドで反映される（設定画面が固まらない / P1-3）
        self.device_manager_section = DeviceManagerSection(
            tab_devices, dispatch=getattr(self.parent_gui, "post_action", None)
        )
        self.device_manager_section.pack(fill="both", expand=True, padx=8, pady=6)


        # =====================================================================
        # 保存ボタン
        # =====================================================================
        btn_save = ctk.CTkButton(
            self,
            text="💾 設定を保存して適用",
            font=self.font_title,
            fg_color=self.primary_color,
            hover_color="#8B634A",
            height=38,
            command=self._on_save
        )
        btn_save.pack(side="bottom", fill="x", padx=15, pady=8)

    def _open_add_mcp_dialog(self):
        """MCPサーバー新規追加ダイアログを開く"""
        dialog = AddMCPServerDialog(self)
        dialog.focus()

    def _delete_mcp_server(self, server_id: str):
        """MCPサーバー設定を削除"""
        from mcp_manager import get_mcp_manager
        mcp_mgr = get_mcp_manager()
        if mcp_mgr.delete_server(server_id):
            self.destroy()
            SettingsWindow(self.parent_gui)

    def _sync_all_models(self):
        """全プロバイダの最新モデル一覧を一括巡回取得して画面を更新"""
        from llm_factory import get_llm_factory, LLMProvider
        factory = get_llm_factory()
        
        self.btn_sync_all.configure(text="⏳ 一括同期中...", state="disabled")
        self.lbl_sync_status.configure(text="⏳ 接続先エンドポイントから最新モデル一覧を取得しています...", text_color="#A67B5B")
        self.update_idletasks()
        
        try:
            # 同期実行
            res = factory.sync_all_discovered_models(background=False)
            
            # 各コンボボックスの選択肢を再読み込み
            self.combo_gemini_model.configure(values=[m["id"] for m in factory.get_models_for_provider(LLMProvider.GEMINI)])
            self.combo_claude_model.configure(values=[m["id"] for m in factory.get_models_for_provider(LLMProvider.CLAUDE)])
            self.combo_openai_model.configure(values=[m["id"] for m in factory.get_models_for_provider(LLMProvider.OPENAI)])
            self.combo_opencode_model.configure(values=[m["id"] for m in factory.get_models_for_provider(LLMProvider.OPENCODE)])
            self.combo_local_model.configure(values=[m["id"] for m in factory.get_models_for_provider(LLMProvider.LOCAL_GGUF)])
            self.combo_custom_model.configure(values=[m["id"] for m in factory.get_models_for_provider(LLMProvider.CUSTOM_OPENAI)])
            
            self.btn_sync_all.configure(text="✓ 同期完了", state="normal")
            self.lbl_sync_status.configure(text="✓ 全プロバイダの最新モデル一覧を同期・更新しました！", text_color="#2E7D32")
        except Exception as e:
            logger.error(f"一括同期エラー: {e}")
            self.btn_sync_all.configure(text="⚡ 一括同期", state="normal")
            self.lbl_sync_status.configure(text=f"❌ 一部プロバイダで同期失敗: {e}", text_color="#C62828")

    def _fetch_models(self, provider: str):
        """APIから利用可能なモデル一覧を動的に探索・取得"""
        from llm_factory import get_llm_factory, LLMProvider
        factory = get_llm_factory()
        
        if provider == "opencode":
            lbl, combo = self.lbl_opencode_status, self.combo_opencode_model
        elif provider == "gemini":
            lbl, combo = self.lbl_gemini_status, self.combo_gemini_model
        elif provider == "custom_openai":
            lbl, combo = self.lbl_custom_status, self.combo_custom_model
        else:
            lbl, combo = getattr(self, "lbl_dl_status", None), self.combo_local_model
        
        if lbl:
            lbl.configure(text="⏳ モデル一覧を取得中...", text_color="#A67B5B")
        self.update_idletasks()
        
        try:
            if provider == "opencode":
                key = self.entry_opencode_key.get().strip()
                url = self.entry_opencode_url.get().strip()
                models = factory.fetch_available_models(provider, api_key=key, base_url=url)
            elif provider == "gemini":
                key = self.entry_gemini_key.get().strip()
                models = factory.fetch_available_models(provider, api_key=key)
            elif provider == "custom_openai":
                key = self.entry_custom_key.get().strip()
                url = self.entry_custom_url.get().strip()
                models = factory.fetch_available_models(provider, api_key=key, base_url=url)
            else:
                models = factory.fetch_available_models("local_gguf")
                
            model_ids = [m["id"] for m in models]
            combo.configure(values=model_ids)
            if model_ids:
                combo.set(model_ids[0])
            if lbl:
                lbl.configure(text=f"✓ {len(model_ids)} 件のモデルを取得しました！", text_color="#2E7D32")
        except Exception as e:
            logger.error(f"モデル取得失敗: {e}")
            if lbl:
                lbl.configure(text=f"❌ 取得エラー: {e}", text_color="#C62828")

    def _auto_install_mcp(self, tool_name: str):
        """指定したAIツールへネオ秘書くんMCPをワンクリック自動登録"""
        import mcp_installer
        success, msg = mcp_installer.install_to_tool(tool_name)
        if success:
            self.lbl_copy_toast.configure(text=msg, text_color="#2E7D32")
        else:
            self.lbl_copy_toast.configure(text=msg, text_color="#C62828")

    def _run_google_oauth(self):
        """Google OAuth 2.0 ブラウザ同意画面を起動してログイン"""
        from tkinter import filedialog, messagebox
        import shutil
        import google_workspace_tools
        
        # credentials.json の存在確認
        if not google_workspace_tools.CREDENTIALS_PATH.exists():
            msg = (
                "Google Cloud Console からダウンロードした\n"
                "『OAuth クライアントシークレット (credentials.json)』を選択してください。"
            )
            messagebox.showinfo("Google 認証設定", msg)
            file_path = filedialog.askopenfilename(
                title="Google credentials.json を選択",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            if not file_path:
                return
            try:
                shutil.copy(file_path, str(google_workspace_tools.CREDENTIALS_PATH))
            except Exception as e:
                messagebox.showerror("エラー", f"credentials.json の配置に失敗しました: {e}")
                return

        self.lbl_google_info.configure(text="⏳ ブラウザでGoogle同意画面を開いています...", text_color="#D32F2F")
        self.update_idletasks()
        
        # 認証フロー実行
        success, res = google_workspace_tools.run_google_oauth_flow()
        if success:
            self.lbl_google_badge.configure(text="🟢 連携済み", text_color="#2E7D32")
            self.lbl_google_info.configure(text=f"✓ 認証成功！ アカウント: {res}", text_color="#2E7D32")
            messagebox.showinfo("連携完了", f"Googleアカウント ({res}) とのOAuth2連携が完了しました！✨\nカレンダーとGmailが同期されます。")
        else:
            self.lbl_google_badge.configure(text="🔴 失敗", text_color="#C62828")
            self.lbl_google_info.configure(text=f"❌ 認証エラー: {res}", text_color="#C62828")

    SOURCE_PALETTE = ["#A67B5B", "#1565C0", "#2E7D32", "#C62828", "#6A1B9A", "#00838F", "#F57C00"]

    def _render_calendar_sources(self):
        """購読ソース一覧（有効チェック・色・名前・URL・同期・削除）を再描画する"""
        import database
        for widget in self.sources_scroll.winfo_children():
            widget.destroy()

        sources = database.get_all_calendar_sources()
        if not sources:
            ctk.CTkLabel(
                self.sources_scroll,
                text="購読カレンダーがありません。「＋ 購読を追加」から登録してください。",
                font=self.font_small, text_color="#757575"
            ).pack(pady=8)
            return

        for s in sources:
            row = ctk.CTkFrame(self.sources_scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)

            enabled_var = tk.BooleanVar(value=s.enabled)
            ctk.CTkCheckBox(
                row, text="", width=24, checkbox_width=18, checkbox_height=18,
                fg_color="#1565C0",
                command=lambda sid=s.id, v=enabled_var: self._on_source_toggle(sid, v)
            ).pack(side="left", padx=(2, 4))

            ctk.CTkButton(
                row, text="", width=22, height=22, corner_radius=4,
                fg_color=s.color, hover_color=s.color,
                border_width=1, border_color="#B0A496",
                command=lambda sid=s.id, col=s.color: self._on_source_cycle_color(sid, col)
            ).pack(side="left", padx=(0, 4))

            name_entry = ctk.CTkEntry(row, width=100, font=self.font_small, fg_color="#FFFFFF")
            name_entry.insert(0, s.name)
            name_entry.pack(side="left", padx=(0, 4))

            url_entry = ctk.CTkEntry(
                row, font=("Meiryo UI", 8),
                placeholder_text="https://calendar.google.com/calendar/ical/.../basic.ics"
            )
            url_entry.insert(0, s.url)
            url_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))

            save_cb = lambda e, sid=s.id, n=name_entry, u=url_entry: self._on_source_field_save(sid, n.get(), u.get())
            name_entry.bind("<FocusOut>", save_cb)
            url_entry.bind("<FocusOut>", save_cb)

            ctk.CTkButton(
                row, text="🔄", width=26, height=22, font=self.font_small,
                fg_color="#1565C0", hover_color="#0D47A1",
                command=lambda sid=s.id: self._on_source_sync(sid)
            ).pack(side="left", padx=(0, 2))

            ctk.CTkButton(
                row, text="🗑", width=26, height=22, font=self.font_small,
                fg_color="transparent", hover_color="#FFEBEE", text_color="#C62828",
                border_width=1, border_color="#E0D8C8",
                command=lambda sid=s.id, name=s.name: self._on_source_delete(sid, name)
            ).pack(side="left")

    def _on_add_calendar_source(self):
        """新しい購読ソースを追加する（色はパレットから自動割当）"""
        import database
        used = len(database.get_all_calendar_sources())
        database.create_calendar_source(database.CalendarSource(
            name=f"カレンダー{used + 1}",
            color=self.SOURCE_PALETTE[used % len(self.SOURCE_PALETTE)],
            url="",
            enabled=True
        ))
        self._render_calendar_sources()

    def _on_source_toggle(self, source_id: int, var):
        """購読ソースの有効/無効を切り替える（同期・表示ともに停止）"""
        import database
        database.set_calendar_source_enabled(source_id, bool(var.get()))
        self._render_calendar_sources()

    def _sync_ical_now(self):
        """全購読ソースの iCal を今すぐ同期する（バックグラウンド実行）"""
        import ics_tools
        self.btn_ical_sync.configure(state="disabled", text="⏳ 同期中...")
        self.update_idletasks()

        def _do_sync():
            try:
                count, msg = ics_tools.sync_all_calendar_sources()
                # Tkinter はスレッド非安全のため、必ずメインスレッドの post_action 経由でUI更新する
                self.parent_gui.post_action(self._on_ical_sync_done, count, msg)
                if count > 0:
                    # 手帳ウィンドウが開かれていれば同期結果を即時反映
                    self.parent_gui.post_action(self.parent_gui.refresh_calendar_if_open)
            except Exception as e:
                self.parent_gui.post_action(self._on_ical_sync_done, 0, str(e))

        import threading
        threading.Thread(target=_do_sync, daemon=True).start()

    def _on_ical_sync_done(self, count: int, msg: str):
        """iCal 同期完了時のUI更新"""
        self.btn_ical_sync.configure(state="normal", text="🔄 すべて同期")
        self._render_calendar_sources()
        if count > 0:
            messagebox.showinfo("同期完了", f"📅 {msg} 件の予定を取り込みました！\n手帳とスマホに反映されています。")
        else:
            messagebox.showwarning("同期結果", msg)

    def _on_source_cycle_color(self, source_id: int, current_color: str):
        """色ボタンクリックで識別色をパレット順に切り替える"""
        import database
        try:
            next_idx = (self.SOURCE_PALETTE.index(current_color) + 1) % len(self.SOURCE_PALETTE)
        except ValueError:
            next_idx = 0
        source = database.get_calendar_source(source_id)
        if source is None:
            return
        source.color = self.SOURCE_PALETTE[next_idx]
        database.update_calendar_source(source)
        self._render_calendar_sources()

    def _on_source_field_save(self, source_id: int, name: str, url: str):
        """名前・URLの編集を確定する（FocusOut時）"""
        import database
        source = database.get_calendar_source(source_id)
        if source is None:
            return
        new_name = name.strip()[:50] or source.name
        new_url = url.strip()[:2000]
        if new_name == source.name and new_url == source.url:
            return
        source.name = new_name
        source.url = new_url
        database.update_calendar_source(source)
        self._render_calendar_sources()

    def _on_source_sync(self, source_id: int):
        """購読ソース1件だけを今すぐ同期する（バックグラウンド実行）"""
        import database
        import ics_tools
        source = database.get_calendar_source(source_id)
        if source is None or not source.url.strip():
            messagebox.showwarning("iCal URL 未設定", "先に秘密の iCal アドレスを貼り付けてください。")
            return

        self.btn_ical_sync.configure(state="disabled", text="⏳ 同期中...")
        self.update_idletasks()

        def _do():
            try:
                count, msg = ics_tools.sync_calendar_source(source)
                # Tkinter はスレッド非安全のため、必ずメインスレッドの post_action 経由でUI更新する
                self.parent_gui.post_action(self._on_ical_sync_done, count, msg)
                if count > 0:
                    # 手帳ウィンドウが開かれていれば同期結果を即時反映
                    self.parent_gui.post_action(self.parent_gui.refresh_calendar_if_open)
            except Exception as e:
                self.parent_gui.post_action(self._on_ical_sync_done, 0, str(e))

        import threading
        threading.Thread(target=_do, daemon=True).start()

    def _on_source_delete(self, source_id: int, name: str):
        """購読ソースを削除する（同期済み予定も併せて削除）"""
        import database
        if not messagebox.askyesno("購読削除", f"「{name}」を削除しますか？\nこのカレンダーから同期済みの予定も削除されます。"):
            return
        database.delete_calendar_source(source_id)
        self._render_calendar_sources()

    def _save_tailscale_host(self):
        """Tailscale ホスト名を .env に保存し、QRダイアログの外出先接続に反映する"""
        from dotenv import set_key
        host = self.entry_tailscale_host.get().strip()
        import app_paths
        env_path = app_paths.get_app_root() / ".env"
        set_key(str(env_path), "TAILSCALE_HOSTNAME", host)
        os.environ["TAILSCALE_HOSTNAME"] = host
        messagebox.showinfo(
            "保存完了",
            "Tailscale ホスト名を保存しました。\n"
            "QR接続ダイアログに「🌐 外出先接続」URLが表示されます。\n"
            f"（PC側で `tailscale serve {SERVER_PORT}` の実行が必要です）"
        )

    def _revoke_sync_token(self):
        """スマホ連携トークンを再生成し、既存の全接続セッションを無効化する。

        「スマホ連携 全解除（トークン再生成）」ボタンのハンドラ。
        誤操作防止のため確認ダイアログを挟み、成功・失敗をユーザーへ通知する。
        """
        if not messagebox.askyesno(
            "スマホ連携 全解除",
            "スマホ側に保存された接続トークンを無効化しますか？\n"
            "解除後はスマホで再ペアリング（QR接続）するまで接続できません。"
        ):
            return
        try:
            # 循環インポート防止のためローカルインポート (gui.py と同一パターン)
            from local_sync_server import get_sync_token_manager
            get_sync_token_manager().regenerate()
            messagebox.showinfo(
                "解除完了",
                "スマホ連携をすべて解除しました。\n"
                "再接続するには「📱 スマホDesk Pet接続」からQRペアリングを行ってください。"
            )
        except Exception as e:
            logger.error(f"スマホ連携トークンの再生成に失敗しました: {e}", exc_info=True)
            messagebox.showerror("解除失敗", f"トークン再生成に失敗しました:\n{e}")

    def _test_google_connection(self):
        """GoogleカレンダーとGmailの同期テスト"""
        import google_workspace_tools
        self.lbl_google_info.configure(text="⏳ GoogleカレンダーとGmailから最新情報を取得中...", text_color="#5D4037")
        self.update_idletasks()
        
        events_summary = google_workspace_tools.get_google_calendar_events_tool.invoke({"days": 3})
        gmail_summary = google_workspace_tools.search_gmail_messages_tool.invoke({"query": "is:unread", "max_results": 3})
        
        from tkinter import messagebox
        report = f"【Google カレンダー (直近3日間)】\n{events_summary}\n\n【Gmail 未読メール】\n{gmail_summary}"
        messagebox.showinfo("🔍 Google サービス同期テスト結果", report)
        self.lbl_google_info.configure(text="✓ 同期テスト完了！正常にデータ取得できました。", text_color="#2E7D32")

    def _logout_google(self):
        """Google 認証を解除"""
        from tkinter import messagebox
        import google_workspace_tools
        if messagebox.askyesno("Google ログアウト", "Googleアカウントとの連携を解除（トークン削除）しますか？"):
            google_workspace_tools.revoke_google_auth()
            self.lbl_google_badge.configure(text="⚪ 未認証", text_color="#757575")
            self.lbl_google_info.configure(text="未認証 (ログインしてください)", text_color="#616161")
            messagebox.showinfo("解除完了", "Google連携を解除しました。")

    def _test_github_connection(self):
        """GitHub PATの接続・権限テスト"""
        token = self.entry_github_token.get().strip()
        repo = self.entry_github_repo.get().strip()
        if not token:
            self.lbl_gh_status.configure(text="⚠️ トークンを入力してください", text_color="#F57C00")
            return
            
        self.lbl_gh_status.configure(text="⏳ 接続確認中...", text_color="#A67B5B")
        self.update_idletasks()
        
        import urllib.request
        try:
            req = urllib.request.Request(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": "NeoHisho-App",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
            with urllib.request.urlopen(req, timeout=8) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    user_login = data.get("login", "Unknown")
                    self.lbl_gh_status.configure(text=f"✓ 接続成功: @{user_login}", text_color="#2E7D32")
                else:
                    self.lbl_gh_status.configure(text=f"❌ HTTP {response.status}", text_color="#C62828")
        except Exception as e:
            self.lbl_gh_status.configure(text=f"❌ 認証失敗: {e}", text_color="#C62828")

    def _copy_claude_mcp_config(self):
        """Claude Desktop / Cursor / Antigravity用のMCP設定JSONをコピー"""
        import mcp_installer
        mcp_def = mcp_installer.get_current_mcp_config()
        config = {
            "mcpServers": {
                "neo_hisho_bridge": {
                    "command": mcp_def["command"],
                    "args": mcp_def["args"]
                }
            }
        }
        json_str = json.dumps(config, indent=2, ensure_ascii=False)
        try:
            self.clipboard_clear()
            self.clipboard_append(json_str)
            self.lbl_copy_toast.configure(text="✓ Claude/Cursor/Antigravity用 MCP設定JSONをコピーしました！", text_color="#2E7D32")
        except Exception as e:
            self.lbl_copy_toast.configure(text=f"❌ コピー失敗: {e}", text_color="#C62828")

    def _copy_codex_mcp_config(self):
        """Codex用のMCP設定TOMLをコピー"""
        import mcp_installer
        mcp_def = mcp_installer.get_current_mcp_config()
        command = mcp_def["command"]
        args_str = ", ".join(f'"{arg}"' for arg in mcp_def["args"])
        toml_str = f'[mcp_servers.neo_hisho_bridge]\ncommand = "{command}"\nargs = [{args_str}]'
        try:
            self.clipboard_clear()
            self.clipboard_append(toml_str)
            self.lbl_copy_toast.configure(text="✓ Codex用 MCP設定TOMLをコピーしました！", text_color="#1565C0")
        except Exception as e:
            self.lbl_copy_toast.configure(text=f"❌ コピー失敗: {e}", text_color="#C62828")

    def _copy_claude_code_cmd(self):
        """Claude Code用のmcp addコマンドをコピー"""
        import mcp_installer
        mcp_def = mcp_installer.get_current_mcp_config()
        command = mcp_def["command"]
        args_str = " ".join(mcp_def["args"])
        cmd = f'claude mcp add neo_hisho_bridge "{command}" "{args_str}"'
        try:
            self.clipboard_clear()
            self.clipboard_append(cmd)
            self.lbl_copy_toast.configure(text="✓ Claude Code登録コマンドをコピーしました！", text_color="#7B1FA2")
        except Exception as e:
            self.lbl_copy_toast.configure(text=f"❌ コピー失敗: {e}", text_color="#C62828")

    def _on_save(self):
        """設定を保存"""
        from llm_factory import get_llm_factory
        from mcp_manager import get_mcp_manager
        factory = get_llm_factory()
        mcp_mgr = get_mcp_manager()
        
        # 1. LLM設定 ＆ 外部連携の保存
        new_settings = {
            "GOOGLE_API_KEY": self.entry_gemini_key.get().strip(),
            "GEMINI_MODEL": self.combo_gemini_model.get().strip(),
            "ANTHROPIC_API_KEY": self.entry_claude_key.get().strip(),
            "CLAUDE_MODEL": self.combo_claude_model.get().strip(),
            "OPENAI_API_KEY": self.entry_openai_key.get().strip(),
            "OPENAI_MODEL": self.combo_openai_model.get().strip(),
            "OPENCODE_API_KEY": self.entry_opencode_key.get().strip(),
            "OPENCODE_BASE_URL": self.entry_opencode_url.get().strip(),
            "OPENCODE_MODEL": self.combo_opencode_model.get().strip(),
            "GROQ_API_KEY": self.entry_groq_key.get().strip(),
            "OPENROUTER_API_KEY": self.entry_openrouter_key.get().strip(),
            "CUSTOM_OPENAI_BASE_URL": self.entry_custom_url.get().strip(),
            "CUSTOM_OPENAI_API_KEY": self.entry_custom_key.get().strip(),
            "CUSTOM_OPENAI_MODEL": self.combo_custom_model.get().strip(),
            "LOCAL_GGUF_MODEL": self.combo_local_model.get().strip(),
            "GOOGLE_CALENDAR_ID": self.entry_google_cal.get().strip(),
            "GITHUB_PERSONAL_ACCESS_TOKEN": self.entry_github_token.get().strip(),
            "GITHUB_REPO": self.entry_github_repo.get().strip(),
            "SLACK_WEBHOOK_URL": self.entry_slack_webhook.get().strip(),
            "VOICE_NARRATION_ENABLED": "true" if self.var_voice_narration.get() else "false",
        }
        
        saved_llm = factory.save_settings(new_settings)
        if saved_llm:
            factory.DEFAULT_CONFIGS[factory.current_provider]["default_model"] = new_settings.get(f"{factory.current_provider.value.upper()}_MODEL")

        # 2. MCP設定の保存
        for s_id, var in self.mcp_checkboxes.items():
            mcp_mgr.update_server_status(s_id, var.get())

        # 3. 外部SaaS・マルチ中継 Webhook 設定の保存
        if hasattr(self, 'entry_webhook_outgoing') and hasattr(self, 'entry_webhook_secret'):
            import webhook_tools
            cur_wh = webhook_tools.get_webhook_config()
            cur_wh["outgoing_webhook_url"] = self.entry_webhook_outgoing.get().strip()
            cur_wh["webhook_secret"] = self.entry_webhook_secret.get().strip()
            webhook_tools.save_webhook_config(cur_wh)

        self.parent_gui.update_message("⚙ AI設定 ＆ 外部連携（Google/GitHub/Slack/Webhook/MCP）を保存・適用しました！")
        self.destroy()

    def _download_local_model_gui(self, model_key: str = "350m"):
        """Hugging Faceから超軽量ローカルLLMをバックグラウンドでダウンロードして設定"""
        import threading
        from tkinter import messagebox
        import tools.setup_local_model as setup_tool
        
        self.btn_dl_local_350m.configure(state="disabled", text="⏳ ダウンロード中...")
        self.progress_bar_local.pack(fill="x", pady=(2, 4))
        self.progress_bar_local.set(0)
        self.lbl_dl_status.configure(text="⏳ Hugging Face に接続中...", text_color="#A67B5B")
        self.update_idletasks()

        def _progress_cb(downloaded: int, total: Optional[int], pct: int):
            def _update_ui():
                if total:
                    self.progress_bar_local.set(pct / 100.0)
                    dl_mb = downloaded / (1024 * 1024)
                    tot_mb = total / (1024 * 1024)
                    self.lbl_dl_status.configure(
                        text=f"⏳ ダウンロード中: {pct}% ({dl_mb:.1f}MB / {tot_mb:.1f}MB)",
                        text_color="#A67B5B"
                    )
                else:
                    self.lbl_dl_status.configure(
                        text=f"⏳ ダウンロード中: {downloaded / (1024 * 1024):.1f}MB",
                        text_color="#A67B5B"
                    )
            self.after(0, _update_ui)

        def _do_download():
            try:
                dest = setup_tool.download_model(model_key, progress_callback=_progress_cb)
                setup_tool.apply_env_config(dest.name)
                
                def _on_success():
                    self.btn_dl_local_350m.configure(state="normal", text="⚡ モデル再ダウンロード")
                    self.lbl_dl_status.configure(
                        text=f"✅ ダウンロード完了！ models/{dest.name} を設定しました",
                        text_color="#2E7D32"
                    )
                    self.progress_bar_local.set(1.0)
                    # モデル選択ドロップダウンを更新
                    self._fetch_models("local_gguf")
                    self.combo_local_model.set(dest.name)
                    messagebox.showinfo(
                        "ダウンロード完了",
                        f"🎉 超軽量ローカルLLM ({dest.name}) の導入が完了しました！\n"
                        "APIキー不要・完全オフラインでネオ秘書くんを利用できます。"
                    )
                self.after(0, _on_success)
            except Exception as e:
                def _on_error(err_msg=str(e)):
                    self.btn_dl_local_350m.configure(state="normal", text="⚡ 超軽量モデル (350M) をダウンロード")
                    self.lbl_dl_status.configure(
                        text=f"❌ エラー: {err_msg[:60]}",
                        text_color="#C62828"
                    )
                    messagebox.showerror(
                        "ダウンロード失敗",
                        f"モデルのダウンロードに失敗しました:\n{err_msg}\n\nネットワーク環境（VPN等）を確認してください。"
                    )
                self.after(0, _on_error)

        threading.Thread(target=_do_download, daemon=True).start()

    def _restart_tour(self) -> None:
        """設定画面の「使い方ガイド」タブからツアーを再開する。"""
        import os
        # フラグファイルを削除して初回扱いにする
        flag_file = os.path.join(os.path.dirname(__file__), "..", "backups", ".tour_completed")
        try:
            if os.path.exists(flag_file):
                os.remove(flag_file)
        except Exception:
            pass
        self.parent_gui.post_action(self.parent_gui._start_tour)
        self.destroy()
