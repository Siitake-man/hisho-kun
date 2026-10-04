#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - 外部連携・プラグイン設定タブ (ToolsTab / T5a Seam).

(ui/settings_tabs/tools_tab.py)

目的:
    Fat モジュール `ui/settings_window.py` から、Nav 4「外部連携・プラグイン (MCP & Tools)」の
    UI描画、MCP自動登録・コピー、音声ナレーション、Tailscale、トークン再生成、
    GitHub/Slack/Webhook、および外部MCP一覧管理を独立した Deep Module として切り出す。
    GoogleSection (T5c) および ICalSection (T5b) を内包・結合する。

契約:
    - build() -> ctk.CTkScrollableFrame: Tools設定UIを構築して返却
    - collect() -> dict[str, str]: 保存用データ (Google Cal ID, GitHub, Slack, Voice 等)
    - refresh_texts() -> None: 多言語更新
    - _render_mcp_servers() -> None: 外部MCPプラグイン一覧再描画（設計書 §9①是正）
    - _auto_install_mcp(tool_name: str) -> None: MCPワンクリック登録
    - _copy_claude_mcp_config() -> None: Claude JSON コピー
    - _copy_codex_mcp_config() -> None: Codex TOML コピー
    - _copy_claude_code_cmd() -> None: Claude Code コマンドコピー
    - _save_tailscale_host() -> None: Tailscale ホスト保存
    - _revoke_sync_token() -> None: スマホ連携解除
    - _test_github_connection() -> None: GitHub 接続テスト
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from typing import Any, Callable, Dict, Optional

import customtkinter as ctk

from i18n import t
from sync_config import SERVER_PORT, build_tailscale_serve_command
from ui.settings_tabs.google_section import GoogleSection
from ui.settings_tabs.ical_section import ICalSection

logger = logging.getLogger("tools_tab")


class ToolsTab:
    """設定画面「外部連携・プラグイン (MCP & Tools)」タブコンポーネント."""

    def __init__(
        self,
        parent_container: ctk.CTkBaseClass,
        parent_gui: Any,
        parent_window: Optional[Any] = None,
        dispatch: Optional[Callable[[Callable[..., Any]], None]] = None,
        fonts: Optional[Dict[str, Any]] = None,
        colors: Optional[Dict[str, Any]] = None,
    ) -> None:
        """ToolsTab を初期化する."""
        self.parent_container = parent_container
        self.parent_gui = parent_gui
        self.parent_window = parent_window
        self.dispatch = dispatch or getattr(parent_gui, "post_action", None)
        self.fonts = fonts or {}
        self.colors = colors or {}

        self.font_title = self.fonts.get("title", ("Meiryo UI", 12, "bold"))
        self.font_body = self.fonts.get("body", ("Meiryo UI", 10))
        self.font_small = self.fonts.get("small", ("Meiryo UI", 9))
        self.primary_color = self.colors.get("primary", "#5D4037")
        self.text_color = self.colors.get("text", "#3E2723")

        self.frame: Optional[ctk.CTkScrollableFrame] = None
        self.lbl_copy_toast: Optional[ctk.CTkLabel] = None

        # 音声ナレーション
        self.var_voice_narration: Optional[tk.BooleanVar] = None
        self.chk_voice_narration: Optional[ctk.CTkSwitch] = None

        # 内包セクション
        self.google_section = GoogleSection(
            parent_container, parent_gui, dispatch=self.dispatch, fonts=self.fonts, colors=self.colors
        )
        self.ical_section = ICalSection(
            parent_container, parent_gui, dispatch=self.dispatch, fonts=self.fonts, colors=self.colors
        )

        # Tailscale
        self.entry_tailscale_host: Optional[ctk.CTkEntry] = None

        # トークン再生成
        self.btn_revoke_sync_token: Optional[ctk.CTkButton] = None

        # GitHub
        self.entry_github_token: Optional[ctk.CTkEntry] = None
        self.entry_github_repo: Optional[ctk.CTkEntry] = None
        self.btn_gh_test: Optional[ctk.CTkButton] = None
        self.lbl_gh_status: Optional[ctk.CTkLabel] = None

        # Slack
        self.entry_slack_webhook: Optional[ctk.CTkEntry] = None

        # 外部SaaS Webhook
        self.entry_webhook_outgoing: Optional[ctk.CTkEntry] = None
        self.entry_webhook_secret: Optional[ctk.CTkEntry] = None

        # 外部MCPプラグイン一覧
        self.card_mcp_list: Optional[ctk.CTkFrame] = None
        self.mcp_list_rows_container: Optional[ctk.CTkFrame] = None
        self.mcp_checkboxes: Dict[str, tk.BooleanVar] = {}

    def post_ui(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """スレッドセーフにメインスレッドでUI操作を実行する."""
        if self.dispatch:
            self.dispatch(lambda: fn(*args, **kwargs))
        elif hasattr(self.parent_container, "after"):
            self.parent_container.after(0, lambda: fn(*args, **kwargs))
        else:
            fn(*args, **kwargs)

    def build(self) -> ctk.CTkScrollableFrame:
        """Tools設定タブのUIツリーを構築して返却する."""
        content_tools = ctk.CTkScrollableFrame(self.parent_container, fg_color="transparent")
        self.frame = content_tools
        content_mcp = content_tools

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

        # 4. 音声ナレーション設定
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

        # 5. Google サービス統合 (GoogleSection)
        self.google_section.parent_container = content_tools
        self.google_section.build()

        # 1.5. Google カレンダー 秘密iCal URL 連携 (ICalSection)
        self.ical_section.parent_container = content_tools
        self.ical_section.build()

        # 1.7. 外出先接続 (Tailscale VPN)
        card_tailscale = ctk.CTkFrame(content_tools, fg_color="#FFFFFF", border_width=1, border_color="#E0D8C8", corner_radius=6)
        card_tailscale.pack(fill="x", pady=4, padx=2)
        ctk.CTkLabel(card_tailscale, text="🌐 外出先接続 (Tailscale VPN)", font=("Meiryo UI", 11, "bold"), text_color="#6A1B9A", anchor="w").pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(
            card_tailscale,
            text=(
                "カフェ等の外出先Wi-Fi（端末間通信が禁止されたネットワーク）からでも\n"
                "スマホDesk Petへ接続できるようにします。\n"
                "【手順】1. PCとスマホ両方に Tailscale を入れ、同じアカウントでログイン\n"
                f"　 　 2. PC側でコマンド実行: {build_tailscale_serve_command()}\n"
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

        # 1.8. スマホ連携 全解除 (トークン再生成)
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

        # 3.5. 外部SaaS・マルチ中継 Webhook
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
        self.card_mcp_list = card_mcp_list

        mcp_header_box = ctk.CTkFrame(card_mcp_list, fg_color="transparent")
        mcp_header_box.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(mcp_header_box, text="🔌 外部MCPプラグイン一覧", font=("Meiryo UI", 11, "bold"), text_color=self.primary_color).pack(side="left")
        btn_add_mcp = ctk.CTkButton(mcp_header_box, text="➕ 追加", width=50, height=22, font=self.font_small, fg_color="#8B634A", command=self._open_add_mcp_dialog)
        btn_add_mcp.pack(side="right")

        self.mcp_list_rows_container = ctk.CTkFrame(card_mcp_list, fg_color="transparent")
        self.mcp_list_rows_container.pack(fill="x", padx=8, pady=(0, 6))

        # MCP一覧描画（初回）
        self._render_mcp_servers()

        return content_tools

    def _render_mcp_servers(self) -> None:
        """外部MCPサーバー一覧を動的に再描画する（設計書 §9①未定義参照の是正）."""
        from mcp_manager import get_mcp_manager

        if not self.mcp_list_rows_container:
            return

        for widget in self.mcp_list_rows_container.winfo_children():
            widget.destroy()

        mcp_mgr = get_mcp_manager()
        server_configs = mcp_mgr.get_server_configs()
        self.mcp_checkboxes.clear()

        for s_id, s_conf in server_configs.items():
            row = ctk.CTkFrame(self.mcp_list_rows_container, fg_color="transparent")
            row.pack(fill="x", pady=2)
            is_enabled = s_conf.get("enabled", False) if isinstance(s_conf, dict) else getattr(s_conf, "enabled", False)
            s_name = s_conf.get("name", s_id) if isinstance(s_conf, dict) else getattr(s_conf, "name", s_id)
            var = tk.BooleanVar(value=is_enabled)
            self.mcp_checkboxes[s_id] = var
            cb = ctk.CTkCheckBox(row, text=s_name, variable=var, font=self.font_body, text_color=self.text_color)
            cb.pack(side="left")
            btn_del = ctk.CTkButton(
                row, text="🗑️", width=26, height=20, font=self.font_small,
                fg_color="#D9534F", hover_color="#C9302C",
                command=lambda sid=s_id: self._delete_mcp_server(sid)
            )
            btn_del.pack(side="right")

    def collect(self) -> Dict[str, Any]:
        """ToolsTab の全設定値を収集して返却する."""
        data = {
            "GOOGLE_CALENDAR_ID": self.google_section.collect().get("GOOGLE_CALENDAR_ID", "primary"),
            "GITHUB_PERSONAL_ACCESS_TOKEN": self.entry_github_token.get().strip() if self.entry_github_token else "",
            "GITHUB_REPO": self.entry_github_repo.get().strip() if self.entry_github_repo else "",
            "SLACK_WEBHOOK_URL": self.entry_slack_webhook.get().strip() if self.entry_slack_webhook else "",
            "VOICE_NARRATION_ENABLED": "true" if (self.var_voice_narration and self.var_voice_narration.get()) else "false",
        }
        return data

    def save_additional_configs(self) -> None:
        """MCP設定および外部Webhook設定を永続化する."""
        from mcp_manager import get_mcp_manager
        import webhook_tools

        # 1. MCP設定の保存
        mcp_mgr = get_mcp_manager()
        for s_id, var in self.mcp_checkboxes.items():
            mcp_mgr.update_server_status(s_id, var.get())

        # 2. 外部SaaS Webhook 設定の保存
        if self.entry_webhook_outgoing and self.entry_webhook_secret:
            cur_wh = webhook_tools.get_webhook_config()
            cur_wh["outgoing_webhook_url"] = self.entry_webhook_outgoing.get().strip()
            cur_wh["webhook_secret"] = self.entry_webhook_secret.get().strip()
            webhook_tools.save_webhook_config(cur_wh)

    def refresh_texts(self) -> None:
        """多言語ラベル再描画."""
        self.google_section.refresh_texts()
        self.ical_section.refresh_texts()

    def _auto_install_mcp(self, tool_name: str) -> None:
        """指定したAIツールへネオ秘書くんMCPをワンクリック自動登録."""
        import mcp_installer

        success, msg = mcp_installer.install_to_tool(tool_name)
        if self.lbl_copy_toast:
            if success:
                self.lbl_copy_toast.configure(text=msg, text_color="#2E7D32")
            else:
                self.lbl_copy_toast.configure(text=msg, text_color="#C62828")

    def _copy_claude_mcp_config(self) -> None:
        """Claude Desktop / Cursor / Antigravity用のMCP設定JSONをコピー."""
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
            if hasattr(self.parent_container, "clipboard_clear"):
                self.parent_container.clipboard_clear()
                self.parent_container.clipboard_append(json_str)
            if self.lbl_copy_toast:
                self.lbl_copy_toast.configure(text="✓ Claude/Cursor/Antigravity用 MCP設定JSONをコピーしました！", text_color="#2E7D32")
        except Exception as e:
            if self.lbl_copy_toast:
                self.lbl_copy_toast.configure(text=f"❌ コピー失敗: {e}", text_color="#C62828")

    def _copy_codex_mcp_config(self) -> None:
        """Codex用のMCP設定TOMLをコピー."""
        import mcp_installer

        mcp_def = mcp_installer.get_current_mcp_config()
        command = mcp_def["command"]
        args_str = ", ".join(f'"{arg}"' for arg in mcp_def["args"])
        toml_str = f'[mcp_servers.neo_hisho_bridge]\ncommand = "{command}"\nargs = [{args_str}]'
        try:
            if hasattr(self.parent_container, "clipboard_clear"):
                self.parent_container.clipboard_clear()
                self.parent_container.clipboard_append(toml_str)
            if self.lbl_copy_toast:
                self.lbl_copy_toast.configure(text="✓ Codex用 MCP設定TOMLをコピーしました！", text_color="#1565C0")
        except Exception as e:
            if self.lbl_copy_toast:
                self.lbl_copy_toast.configure(text=f"❌ コピー失敗: {e}", text_color="#C62828")

    def _copy_claude_code_cmd(self) -> None:
        """Claude Code用のmcp addコマンドをコピー."""
        import mcp_installer

        mcp_def = mcp_installer.get_current_mcp_config()
        command = mcp_def["command"]
        args_str = " ".join(mcp_def["args"])
        cmd = f'claude mcp add neo_hisho_bridge "{command}" "{args_str}"'
        try:
            if hasattr(self.parent_container, "clipboard_clear"):
                self.parent_container.clipboard_clear()
                self.parent_container.clipboard_append(cmd)
            if self.lbl_copy_toast:
                self.lbl_copy_toast.configure(text="✓ Claude Code登録コマンドをコピーしました！", text_color="#7B1FA2")
        except Exception as e:
            if self.lbl_copy_toast:
                self.lbl_copy_toast.configure(text=f"❌ コピー失敗: {e}", text_color="#C62828")

    def _save_tailscale_host(self) -> None:
        """Tailscale ホスト名を .env に保存し、QRダイアログの外出先接続に反映する."""
        from dotenv import set_key
        import app_paths

        if not self.entry_tailscale_host:
            return
        host = self.entry_tailscale_host.get().strip()
        env_path = app_paths.get_app_root() / ".env"
        set_key(str(env_path), "TAILSCALE_HOSTNAME", host)
        os.environ["TAILSCALE_HOSTNAME"] = host
        messagebox.showinfo(
            "保存完了",
            "Tailscale ホスト名を保存しました。\n"
            "QR接続ダイアログに「🌐 外出先接続」URLが表示されます。\n"
            f"（PC側で `{build_tailscale_serve_command()}` の実行が必要です）"
        )

    def _revoke_sync_token(self) -> None:
        """スマホ連携トークンを再生成し、既存の全接続セッションを無効化する."""
        if not messagebox.askyesno(
            "スマホ連携 全解除",
            "スマホ側に保存された接続トークンを無効化しますか？\n"
            "解除後はスマホで再ペアリング（QR接続）するまで接続できません。"
        ):
            return
        try:
            from local_sync_server import get_sync_token_manager
            get_sync_token_manager().regenerate()
            messagebox.showinfo(
                "解除完了",
                "スマホ連携をすべて解除しました。\n"
                "再接続するには「📱 スマホDesk Pet接続」からQRペアリングを行ってください。"
            )
        except Exception as e:
            logger.error("スマホ連携トークンの再生成に失敗しました: %s", e, exc_info=True)
            messagebox.showerror("解除失敗", f"トークン再生成に失敗しました:\n{e}")

    def _test_github_connection(self) -> None:
        """GitHub PATの接続・権限テスト."""
        if not self.entry_github_token:
            return
        token = self.entry_github_token.get().strip()
        if not token:
            if self.lbl_gh_status:
                self.lbl_gh_status.configure(text="⚠️ トークンを入力してください", text_color="#F57C00")
            return

        if self.lbl_gh_status:
            self.lbl_gh_status.configure(text="⏳ 接続確認中...", text_color="#A67B5B")
        if hasattr(self.parent_container, "update_idletasks"):
            self.parent_container.update_idletasks()

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
                    if self.lbl_gh_status:
                        self.lbl_gh_status.configure(text=f"✓ 接続成功: @{user_login}", text_color="#2E7D32")
                else:
                    if self.lbl_gh_status:
                        self.lbl_gh_status.configure(text=f"❌ HTTP {response.status}", text_color="#C62828")
        except Exception as e:
            if self.lbl_gh_status:
                self.lbl_gh_status.configure(text=f"❌ 認証失敗: {e}", text_color="#C62828")

    def _open_add_mcp_dialog(self) -> None:
        """MCPサーバー新規追加ダイアログを開く."""
        if self.parent_window:
            from ui.settings_window import AddMCPServerDialog
            dialog = AddMCPServerDialog(self.parent_window)
            dialog.focus()

    def _delete_mcp_server(self, server_id: str) -> None:
        """MCPサーバー設定を削除."""
        from mcp_manager import get_mcp_manager

        mcp_mgr = get_mcp_manager()
        if mcp_mgr.delete_server(server_id):
            self._render_mcp_servers()
