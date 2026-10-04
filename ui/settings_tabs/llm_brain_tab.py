#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - AIモデル設定タブ (LLMBrainTab / T4 Seam).

(ui/settings_tabs/llm_brain_tab.py)

目的:
    Fat モジュール `ui/settings_window.py` (1,930行) から、Nav 3「AIモデル設定 (LLM Brain)」の
    UI描画、モデル一括同期、プロバイダ別動的モデル一覧取得、および
    超軽量ローカルLLM (Liquid AI LFM 2.5) ダウンロード処理を独立した
    Deep Module として切り出す。

契約:
    - build() -> ctk.CTkScrollableFrame: AIモデル設定UIを構築して返却
    - collect() -> dict[str, str]: 保存用データ (15キー: 各プロバイダのAPIキー・URL・モデル名)
    - refresh_texts() -> None: 多言語切り替え時の動的ラベル再描画
    - _sync_all_models() -> None: 全プロバイダモデルの一括同期
    - _fetch_models(provider: str) -> None: 指定プロバイダのモデル一覧動的取得
    - _download_local_model_gui(model_key: str) -> None: ローカルLLMダウンロード
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from tkinter import messagebox
from typing import Any, Callable, Dict, Optional

import customtkinter as ctk

from i18n import t

logger = logging.getLogger("llm_brain_tab")


class LLMBrainTab:
    """設定画面「AIモデル設定 (LLM Brain)」タブコンポーネント."""

    def __init__(
        self,
        parent_container: ctk.CTkBaseClass,
        parent_gui: Any,
        dispatch: Optional[Callable[[Callable[..., Any]], None]] = None,
        fonts: Optional[Dict[str, Any]] = None,
        colors: Optional[Dict[str, Any]] = None,
    ) -> None:
        """LLMBrainTab を初期化する.

        Args:
            parent_container: 配置先のコンテナウィジェット。
            parent_gui: メインGUIインスタンス。
            dispatch: ワーカースレッドからメインスレッドへのディスパッチャ。
            fonts: フォント定義辞書。
            colors: カラー定義辞書。
        """
        self.parent_container = parent_container
        self.parent_gui = parent_gui
        self.dispatch = dispatch or getattr(parent_gui, "post_action", None)
        self.fonts = fonts or {}
        self.colors = colors or {}

        # スタイル参照
        self.font_title = self.fonts.get("title", ("Meiryo UI", 12, "bold"))
        self.font_body = self.fonts.get("body", ("Meiryo UI", 10))
        self.font_small = self.fonts.get("small", ("Meiryo UI", 9))
        self.primary_color = self.colors.get("primary", "#5D4037")
        self.text_color = self.colors.get("text", "#3E2723")

        # 保持ウィジェット
        self.frame: Optional[ctk.CTkScrollableFrame] = None
        self.lbl_sync_banner: Optional[ctk.CTkLabel] = None
        self.btn_sync_all: Optional[ctk.CTkButton] = None
        self.lbl_sync_status: Optional[ctk.CTkLabel] = None

        # 1. Gemini
        self.entry_gemini_key: Optional[ctk.CTkEntry] = None
        self.combo_gemini_model: Optional[ctk.CTkComboBox] = None
        self.btn_fetch_gemini: Optional[ctk.CTkButton] = None
        self.lbl_gemini_status: Optional[ctk.CTkLabel] = None

        # 2. Claude
        self.entry_claude_key: Optional[ctk.CTkEntry] = None
        self.combo_claude_model: Optional[ctk.CTkComboBox] = None

        # 3. OpenAI
        self.entry_openai_key: Optional[ctk.CTkEntry] = None
        self.combo_openai_model: Optional[ctk.CTkComboBox] = None

        # 4. OpenCode
        self.entry_opencode_key: Optional[ctk.CTkEntry] = None
        self.entry_opencode_url: Optional[ctk.CTkEntry] = None
        self.combo_opencode_model: Optional[ctk.CTkComboBox] = None
        self.btn_fetch_opencode: Optional[ctk.CTkButton] = None
        self.lbl_opencode_status: Optional[ctk.CTkLabel] = None

        # 5. Groq / OpenRouter
        self.entry_groq_key: Optional[ctk.CTkEntry] = None
        self.entry_openrouter_key: Optional[ctk.CTkEntry] = None

        # 6. Local GGUF
        self.btn_dl_local_350m: Optional[ctk.CTkButton] = None
        self.btn_fetch_local: Optional[ctk.CTkButton] = None
        self.progress_bar_local: Optional[ctk.CTkProgressBar] = None
        self.lbl_dl_status: Optional[ctk.CTkLabel] = None
        self.combo_local_model: Optional[ctk.CTkComboBox] = None

        # 7. Custom OpenAI
        self.entry_custom_url: Optional[ctk.CTkEntry] = None
        self.entry_custom_key: Optional[ctk.CTkEntry] = None
        self.combo_custom_model: Optional[ctk.CTkComboBox] = None
        self.btn_fetch_custom: Optional[ctk.CTkButton] = None
        self.lbl_custom_status: Optional[ctk.CTkLabel] = None

    def post_ui(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """スレッドセーフにメインスレッドでUI操作を実行する."""
        if self.dispatch:
            self.dispatch(lambda: fn(*args, **kwargs))
        elif hasattr(self.parent_container, "after"):
            self.parent_container.after(0, lambda: fn(*args, **kwargs))
        else:
            fn(*args, **kwargs)

    def build(self) -> ctk.CTkScrollableFrame:
        """AIモデル設定タブのUIツリーを構築して返却する."""
        from llm_factory import get_llm_factory, LLMProvider
        factory = get_llm_factory()

        content_llm = ctk.CTkScrollableFrame(self.parent_container, fg_color="transparent")
        self.frame = content_llm

        # 🌐 一括モデル同期バナー
        sync_banner = ctk.CTkFrame(content_llm, fg_color="#EFEBE9", border_color=self.primary_color, border_width=1.5, corner_radius=8)
        sync_banner.pack(fill="x", pady=(4, 12), padx=2)

        sync_inner = ctk.CTkFrame(sync_banner, fg_color="transparent")
        sync_inner.pack(fill="x", padx=10, pady=8)

        self.lbl_sync_banner = ctk.CTkLabel(
            sync_inner,
            text=t("ui.settings.llm_sync_banner"),
            font=self.font_body,
            text_color=self.text_color
        )
        self.lbl_sync_banner.pack(side="left")

        self.btn_sync_all = ctk.CTkButton(
            sync_inner,
            text=t("ui.settings.llm_sync_btn"),
            font=self.font_small,
            fg_color=self.primary_color,
            hover_color="#8B634A",
            width=130,
            height=28,
            command=self._sync_all_models
        )
        self.btn_sync_all.pack(side="right")
        self.lbl_sync_status = ctk.CTkLabel(sync_banner, text=t("ui.settings.llm_sync_note"), font=("Meiryo UI", 8.5), text_color="#7A6B62")
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

        return content_llm

    def collect(self) -> Dict[str, str]:
        """AIモデル設定タブの全入力値 (15キー) を収集して辞書で返却する."""
        return {
            "GOOGLE_API_KEY": self.entry_gemini_key.get().strip() if self.entry_gemini_key else "",
            "GEMINI_MODEL": self.combo_gemini_model.get().strip() if self.combo_gemini_model else "",
            "ANTHROPIC_API_KEY": self.entry_claude_key.get().strip() if self.entry_claude_key else "",
            "CLAUDE_MODEL": self.combo_claude_model.get().strip() if self.combo_claude_model else "",
            "OPENAI_API_KEY": self.entry_openai_key.get().strip() if self.entry_openai_key else "",
            "OPENAI_MODEL": self.combo_openai_model.get().strip() if self.combo_openai_model else "",
            "OPENCODE_API_KEY": self.entry_opencode_key.get().strip() if self.entry_opencode_key else "",
            "OPENCODE_BASE_URL": self.entry_opencode_url.get().strip() if self.entry_opencode_url else "",
            "OPENCODE_MODEL": self.combo_opencode_model.get().strip() if self.combo_opencode_model else "",
            "GROQ_API_KEY": self.entry_groq_key.get().strip() if self.entry_groq_key else "",
            "OPENROUTER_API_KEY": self.entry_openrouter_key.get().strip() if self.entry_openrouter_key else "",
            "CUSTOM_OPENAI_BASE_URL": self.entry_custom_url.get().strip() if self.entry_custom_url else "",
            "CUSTOM_OPENAI_API_KEY": self.entry_custom_key.get().strip() if self.entry_custom_key else "",
            "CUSTOM_OPENAI_MODEL": self.combo_custom_model.get().strip() if self.combo_custom_model else "",
            "LOCAL_GGUF_MODEL": self.combo_local_model.get().strip() if self.combo_local_model else "",
        }

    def refresh_texts(self) -> None:
        """多言語変更時に動的テキストラベルを再描画する."""
        if self.lbl_sync_banner and self.lbl_sync_banner.winfo_exists():
            self.lbl_sync_banner.configure(text=t("ui.settings.llm_sync_banner"))
        if self.btn_sync_all and self.btn_sync_all.winfo_exists():
            self.btn_sync_all.configure(text=t("ui.settings.llm_sync_btn"))
        if self.lbl_sync_status and self.lbl_sync_status.winfo_exists():
            self.lbl_sync_status.configure(text=t("ui.settings.llm_sync_note"))

    def _sync_all_models(self) -> None:
        """全プロバイダの最新モデル一覧を一括巡回取得して画面を更新."""
        from llm_factory import get_llm_factory, LLMProvider
        factory = get_llm_factory()

        if self.btn_sync_all:
            self.btn_sync_all.configure(text="⏳ 一括同期中...", state="disabled")
        if self.lbl_sync_status:
            self.lbl_sync_status.configure(text="⏳ 接続先エンドポイントから最新モデル一覧を取得しています...", text_color="#A67B5B")
        if hasattr(self.parent_container, "update_idletasks"):
            self.parent_container.update_idletasks()

        try:
            # 同期実行
            factory.sync_all_discovered_models(background=False)

            # 各コンボボックスの選択肢を再読み込み
            if self.combo_gemini_model:
                self.combo_gemini_model.configure(values=[m["id"] for m in factory.get_models_for_provider(LLMProvider.GEMINI)])
            if self.combo_claude_model:
                self.combo_claude_model.configure(values=[m["id"] for m in factory.get_models_for_provider(LLMProvider.CLAUDE)])
            if self.combo_openai_model:
                self.combo_openai_model.configure(values=[m["id"] for m in factory.get_models_for_provider(LLMProvider.OPENAI)])
            if self.combo_opencode_model:
                self.combo_opencode_model.configure(values=[m["id"] for m in factory.get_models_for_provider(LLMProvider.OPENCODE)])
            if self.combo_local_model:
                self.combo_local_model.configure(values=[m["id"] for m in factory.get_models_for_provider(LLMProvider.LOCAL_GGUF)])
            if self.combo_custom_model:
                self.combo_custom_model.configure(values=[m["id"] for m in factory.get_models_for_provider(LLMProvider.CUSTOM_OPENAI)])

            if self.btn_sync_all:
                self.btn_sync_all.configure(text="✓ 同期完了", state="normal")
            if self.lbl_sync_status:
                self.lbl_sync_status.configure(text="✓ 全プロバイダの最新モデル一覧を同期・更新しました！", text_color="#2E7D32")
        except Exception as e:
            logger.error("一括同期エラー: %s", e)
            if self.btn_sync_all:
                self.btn_sync_all.configure(text="⚡ 一括同期", state="normal")
            if self.lbl_sync_status:
                self.lbl_sync_status.configure(text=f"❌ 一部プロバイダで同期失敗: {e}", text_color="#C62828")

    def _fetch_models(self, provider: str) -> None:
        """APIから利用可能なモデル一覧を動的に探索・取得."""
        from llm_factory import get_llm_factory
        factory = get_llm_factory()

        if provider == "opencode":
            lbl, combo = self.lbl_opencode_status, self.combo_opencode_model
        elif provider == "gemini":
            lbl, combo = self.lbl_gemini_status, self.combo_gemini_model
        elif provider == "custom_openai":
            lbl, combo = self.lbl_custom_status, self.combo_custom_model
        else:
            lbl, combo = self.lbl_dl_status, self.combo_local_model

        if lbl:
            lbl.configure(text="⏳ モデル一覧を取得中...", text_color="#A67B5B")
        if hasattr(self.parent_container, "update_idletasks"):
            self.parent_container.update_idletasks()

        try:
            if provider == "opencode":
                key = self.entry_opencode_key.get().strip() if self.entry_opencode_key else ""
                url = self.entry_opencode_url.get().strip() if self.entry_opencode_url else ""
                models = factory.fetch_available_models(provider, api_key=key, base_url=url)
            elif provider == "gemini":
                key = self.entry_gemini_key.get().strip() if self.entry_gemini_key else ""
                models = factory.fetch_available_models(provider, api_key=key)
            elif provider == "custom_openai":
                key = self.entry_custom_key.get().strip() if self.entry_custom_key else ""
                url = self.entry_custom_url.get().strip() if self.entry_custom_url else ""
                models = factory.fetch_available_models(provider, api_key=key, base_url=url)
            else:
                models = factory.fetch_available_models("local_gguf")

            model_ids = [m["id"] for m in models]
            if combo:
                combo.configure(values=model_ids)
                if model_ids:
                    combo.set(model_ids[0])
            if lbl:
                lbl.configure(text=f"✓ {len(model_ids)} 件のモデルを取得しました！", text_color="#2E7D32")
        except Exception as e:
            logger.error("モデル取得失敗: %s", e)
            if lbl:
                lbl.configure(text=f"❌ 取得エラー: {e}", text_color="#C62828")

    def _download_local_model_gui(self, model_key: str = "350m") -> None:
        """Hugging Faceから超軽量ローカルLLMをバックグラウンドでダウンロードして設定."""
        import tools.setup_local_model as setup_tool

        if self.btn_dl_local_350m:
            self.btn_dl_local_350m.configure(state="disabled", text="⏳ ダウンロード中...")
        if self.progress_bar_local:
            self.progress_bar_local.pack(fill="x", pady=(2, 4))
            self.progress_bar_local.set(0)
        if self.lbl_dl_status:
            self.lbl_dl_status.configure(text="⏳ Hugging Face に接続中...", text_color="#A67B5B")
        if hasattr(self.parent_container, "update_idletasks"):
            self.parent_container.update_idletasks()

        def _progress_cb(downloaded: int, total: Optional[int], pct: int):
            def _update_ui():
                if self.progress_bar_local and total:
                    self.progress_bar_local.set(pct / 100.0)
                if self.lbl_dl_status:
                    if total:
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
            self.post_ui(_update_ui)

        def _do_download():
            try:
                dest = setup_tool.download_model(model_key, progress_callback=_progress_cb)
                setup_tool.apply_env_config(dest.name)

                def _on_success():
                    if self.btn_dl_local_350m:
                        self.btn_dl_local_350m.configure(state="normal", text="⚡ モデル再ダウンロード")
                    if self.lbl_dl_status:
                        self.lbl_dl_status.configure(
                            text=f"✅ ダウンロード完了！ models/{dest.name} を設定しました",
                            text_color="#2E7D32"
                        )
                    if self.progress_bar_local:
                        self.progress_bar_local.set(1.0)
                    # モデル選択ドロップダウンを更新
                    self._fetch_models("local_gguf")
                    if self.combo_local_model:
                        self.combo_local_model.set(dest.name)
                    messagebox.showinfo(
                        "ダウンロード完了",
                        f"🎉 超軽量ローカルLLM ({dest.name}) の導入が完了しました！\n"
                        "APIキー不要・完全オフラインでネオ秘書くんを利用できます。"
                    )
                self.post_ui(_on_success)
            except Exception as e:
                def _on_error(err_msg=str(e)):
                    if self.btn_dl_local_350m:
                        self.btn_dl_local_350m.configure(state="normal", text="⚡ 超軽量モデル (350M) をダウンロード")
                    if self.lbl_dl_status:
                        self.lbl_dl_status.configure(
                            text=f"❌ エラー: {err_msg[:60]}",
                            text_color="#C62828"
                        )
                    messagebox.showerror(
                        "ダウンロード失敗",
                        f"モデルのダウンロードに失敗しました:\n{err_msg}\n\nネットワーク環境（VPN等）を確認してください。"
                    )
                self.post_ui(_on_error)

        threading.Thread(target=_do_download, daemon=True).start()
