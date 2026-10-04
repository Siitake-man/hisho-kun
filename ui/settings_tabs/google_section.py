#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - Google サービス連携セクション (GoogleSection / T5c Seam).

(ui/settings_tabs/google_section.py)

目的:
    Fat モジュール `ui/settings_window.py` から、Google サービス連携
    (Calendar / Gmail OAuth 2.0 認証・同期テスト・ログアウト) の
    UI描画およびハンドラ処理を独立した Deep Module として切り出す。

契約:
    - build() -> ctk.CTkFrame: Google 連携カードUIを構築して返却
    - collect() -> dict[str, str]: 保存用データ ({"GOOGLE_CALENDAR_ID": ...})
    - refresh_texts() -> None: 多言語更新
    - _run_google_oauth() -> None: OAuth 2.0 認証フロー
    - _test_google_connection() -> None: 同期テスト
    - _logout_google() -> None: 認証解除
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Callable, Dict, Optional

import customtkinter as ctk

logger = logging.getLogger("google_section")


class GoogleSection:
    """設定画面「Google サービス連携 (Calendar / Gmail)」セクションコンポーネント."""

    def __init__(
        self,
        parent_container: ctk.CTkBaseClass,
        parent_gui: Any,
        dispatch: Optional[Callable[[Callable[..., Any]], None]] = None,
        fonts: Optional[Dict[str, Any]] = None,
        colors: Optional[Dict[str, Any]] = None,
    ) -> None:
        """GoogleSection を初期化する."""
        self.parent_container = parent_container
        self.parent_gui = parent_gui
        self.dispatch = dispatch or getattr(parent_gui, "post_action", None)
        self.fonts = fonts or {}
        self.colors = colors or {}

        self.font_title = self.fonts.get("title", ("Meiryo UI", 12, "bold"))
        self.font_body = self.fonts.get("body", ("Meiryo UI", 10))
        self.font_small = self.fonts.get("small", ("Meiryo UI", 9))
        self.primary_color = self.colors.get("primary", "#5D4037")
        self.text_color = self.colors.get("text", "#3E2723")

        self.card: Optional[ctk.CTkFrame] = None
        self.lbl_google_badge: Optional[ctk.CTkLabel] = None
        self.lbl_google_info: Optional[ctk.CTkLabel] = None
        self.entry_google_cal: Optional[ctk.CTkEntry] = None
        self.btn_google_auth: Optional[ctk.CTkButton] = None
        self.btn_google_test: Optional[ctk.CTkButton] = None
        self.btn_google_logout: Optional[ctk.CTkButton] = None

    def post_ui(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """スレッドセーフにメインスレッドでUI操作を実行する."""
        if self.dispatch:
            self.dispatch(lambda: fn(*args, **kwargs))
        elif hasattr(self.parent_container, "after"):
            self.parent_container.after(0, lambda: fn(*args, **kwargs))
        else:
            fn(*args, **kwargs)

    def build(self) -> ctk.CTkFrame:
        """Google 連携カード UI を構築して返却する."""
        import google_workspace_tools

        card_google = ctk.CTkFrame(self.parent_container, fg_color="#FFFFFF", border_width=1, border_color="#E0D8C8", corner_radius=6)
        self.card = card_google

        # ヘッダーと認証状態バッジ
        g_head_row = ctk.CTkFrame(card_google, fg_color="transparent")
        g_head_row.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(g_head_row, text="📅 Google サービス連携 (Calendar / Gmail)", font=("Meiryo UI", 11, "bold"), text_color="#D32F2F").pack(side="left")

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

        return card_google

    def collect(self) -> Dict[str, str]:
        """設定保存用の Google Calendar ID を返却する."""
        return {
            "GOOGLE_CALENDAR_ID": self.entry_google_cal.get().strip() if self.entry_google_cal else "primary"
        }

    def refresh_texts(self) -> None:
        """多言語ラベル再描画."""
        pass

    def _run_google_oauth(self) -> None:
        """Google OAuth 2.0 ブラウザ同意画面を起動してログイン."""
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

        if self.lbl_google_info:
            self.lbl_google_info.configure(text="⏳ ブラウザでGoogle同意画面を開いています...", text_color="#D32F2F")
        if hasattr(self.parent_container, "update_idletasks"):
            self.parent_container.update_idletasks()

        # 認証フロー実行
        success, res = google_workspace_tools.run_google_oauth_flow()
        if success:
            if self.lbl_google_badge:
                self.lbl_google_badge.configure(text="🟢 連携済み", text_color="#2E7D32")
            if self.lbl_google_info:
                self.lbl_google_info.configure(text=f"✓ 認証成功！ アカウント: {res}", text_color="#2E7D32")
            messagebox.showinfo("連携完了", f"Googleアカウント ({res}) とのOAuth2連携が完了しました！✨\nカレンダーとGmailが同期されます。")
        else:
            if self.lbl_google_badge:
                self.lbl_google_badge.configure(text="🔴 失敗", text_color="#C62828")
            if self.lbl_google_info:
                self.lbl_google_info.configure(text=f"❌ 認証エラー: {res}", text_color="#C62828")

    def _test_google_connection(self) -> None:
        """GoogleカレンダーとGmailの同期テスト."""
        import google_workspace_tools

        if self.lbl_google_info:
            self.lbl_google_info.configure(text="⏳ GoogleカレンダーとGmailから最新情報を取得中...", text_color="#5D4037")
        if hasattr(self.parent_container, "update_idletasks"):
            self.parent_container.update_idletasks()

        try:
            events_summary = google_workspace_tools.get_google_calendar_events_tool.invoke({"days": 3})
            gmail_summary = google_workspace_tools.search_gmail_messages_tool.invoke({"query": "is:unread", "max_results": 3})
            report = f"【Google カレンダー (直近3日間)】\n{events_summary}\n\n【Gmail 未読メール】\n{gmail_summary}"
            messagebox.showinfo("🔍 Google サービス同期テスト結果", report)
            if self.lbl_google_info:
                self.lbl_google_info.configure(text="✓ 同期テスト完了！正常にデータ取得できました。", text_color="#2E7D32")
        except Exception as e:
            logger.error("Google 同期テスト失敗: %s", e)
            if self.lbl_google_info:
                self.lbl_google_info.configure(text=f"❌ テスト失敗: {e}", text_color="#C62828")

    def _logout_google(self) -> None:
        """Google 認証を解除."""
        import google_workspace_tools

        if messagebox.askyesno("Google ログアウト", "Googleアカウントとの連携を解除（トークン削除）しますか？"):
            google_workspace_tools.revoke_google_auth()
            if self.lbl_google_badge:
                self.lbl_google_badge.configure(text="⚪ 未認証", text_color="#757575")
            if self.lbl_google_info:
                self.lbl_google_info.configure(text="未認証 (ログインしてください)", text_color="#616161")
            messagebox.showinfo("解除完了", "Google連携を解除しました。")
