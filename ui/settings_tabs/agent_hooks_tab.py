#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - エージェント連携＆Hooks設定タブ (AgentHooksTab / T3 Seam).

(ui/settings_tabs/agent_hooks_tab.py)

目的:
    Fat モジュール `ui/settings_window.py` (1,930行) から、Nav 2「エージェント連携 ＆ Hooks設定」の
    UI描画、エージェント設定スニペット切り替え・コピー、および Ping テスト処理を独立した
    Deep Module として切り出す。

契約:
    - build() -> ctk.CTkScrollableFrame: Hooks設定UIを構築して返却
    - collect() -> dict: 保存用データ (Hooks設定は保存項目なしのため空辞書)
    - refresh_texts() -> None: 多言語切り替え時の動的ラベル再描画
    - _on_ping_test() -> None: エージェント連携の接続テスト実行
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from tkinter import messagebox
from typing import Any, Callable, Dict, Optional

import customtkinter as ctk

from i18n import t
from sync_config import SERVER_PORT

logger = logging.getLogger("agent_hooks_tab")


class AgentHooksTab:
    """設定画面「エージェント連携＆Hooks設定」タブコンポーネント."""

    def __init__(
        self,
        parent_container: ctk.CTkBaseClass,
        parent_gui: Any,
        dispatch: Optional[Callable[[Callable[..., Any]], None]] = None,
        fonts: Optional[Dict[str, Any]] = None,
        colors: Optional[Dict[str, Any]] = None,
        on_ping_test: Optional[Callable[[], None]] = None,
    ) -> None:
        """AgentHooksTab を初期化する.

        Args:
            parent_container: 配置先のコンテナウィジェット。
            parent_gui: メインGUIインスタンス。
            dispatch: ワーカースレッドからメインスレッドへのディスパッチャ。
            fonts: フォント定義辞書。
            colors: カラー定義辞書。
            on_ping_test: Pingテスト実行委譲ハンドラ。
        """
        self.parent_container = parent_container
        self.parent_gui = parent_gui
        self.dispatch = dispatch or getattr(parent_gui, "post_action", None)
        self.fonts = fonts or {}
        self.colors = colors or {}
        self.on_ping_test_override = on_ping_test

        # フォント・カラーのフォールバック
        self.font_title = self.fonts.get("title", ("Meiryo UI", 12, "bold"))
        self.font_body = self.fonts.get("body", ctk.CTkFont(family="Yu Gothic UI", size=11))
        self.font_small = self.fonts.get("small", ctk.CTkFont(family="Yu Gothic UI", size=10))

        self.primary_color = self.colors.get("primary", "#A67B5B")
        self.text_color = self.colors.get("text", "#3D312A")

        self.frame: Optional[ctk.CTkScrollableFrame] = None
        self.lbl_hooks_title: Optional[ctk.CTkLabel] = None
        self.lbl_hooks_desc: Optional[ctk.CTkLabel] = None
        self.btn_ping: Optional[ctk.CTkButton] = None
        self.txt_snippet: Optional[ctk.CTkTextbox] = None

    def build(self) -> ctk.CTkScrollableFrame:
        """エージェント連携＆Hooks設定タブのUIを構築する.

        Returns:
            ctk.CTkScrollableFrame: 構築されたスクロール可能フレーム。
        """
        self.frame = ctk.CTkScrollableFrame(self.parent_container, fg_color="transparent")

        # カード1: 概要 ＆ 🔔 接続テスト (Ping)
        card_hooks_intro = ctk.CTkFrame(
            self.frame, fg_color="#FFFFFF", border_width=1, border_color="#E0D8C8", corner_radius=8
        )
        card_hooks_intro.pack(fill="x", pady=6, padx=2)

        self.lbl_hooks_title = ctk.CTkLabel(
            card_hooks_intro,
            text=f"🤖 {t('ui.settings.hooks_card_title')}",
            font=self.font_title,
            text_color=self.primary_color,
            anchor="w"
        )
        self.lbl_hooks_title.pack(fill="x", padx=12, pady=(10, 4))

        self.lbl_hooks_desc = ctk.CTkLabel(
            card_hooks_intro,
            text=t("ui.settings.hooks_desc"),
            font=self.font_small,
            text_color="#7A6B62",
            anchor="w",
            justify="left"
        )
        self.lbl_hooks_desc.pack(fill="x", padx=12, pady=(0, 10))

        # Pingテストボタン
        self.btn_ping = ctk.CTkButton(
            card_hooks_intro,
            text=t("ui.settings.hooks_ping_btn"),
            font=self.font_body,
            fg_color="#4CAF50",
            hover_color="#388E3C",
            height=34,
            command=self._on_ping_test
        )
        self.btn_ping.pack(fill="x", padx=12, pady=(0, 12))

        # カード2: エージェント別設定スニペット
        card_snippets = ctk.CTkFrame(
            self.frame, fg_color="#FFFFFF", border_width=1, border_color="#E0D8C8", corner_radius=8
        )
        card_snippets.pack(fill="x", pady=6, padx=2)

        ctk.CTkLabel(
            card_snippets,
            text="📋 主要エージェント向け設定スニペット",
            font=("Meiryo UI", 11, "bold"),
            text_color=self.primary_color,
            anchor="w"
        ).pack(fill="x", padx=12, pady=(10, 4))

        tool_guard_hook_path = (Path.home() / ".gemini" / "tools" / "jev_router" / "tool_guard_hook.py").as_posix()
        snippets = {
            "Antigravity": (
                "// ~/.gemini/config/hooks.json または .agents/hooks.json\n"
                "{\n"
                '  "code-discovery-and-safety-guard": {\n'
                '    "enabled": true,\n'
                '    "PreToolUse": [\n'
                "      {\n"
                '        "matcher": "grep_search|run_command",\n'
                '        "hooks": [\n'
                "          {\n"
                '            "type": "command",\n'
                f'            "command": "python {tool_guard_hook_path}",\n'
                '            "timeout": 5\n'
                "          }\n"
                "        ]\n"
                "      }\n"
                "    ]\n"
                "  }\n"
                "}"
            ),
            "OpenCode": (
                "// ~/.config/opencode/plugins/hisho-approval-notify/index.ts\n"
                "// ctx.permission.hook('evaluate', event => {\n"
                "//   if (event.effect === 'ask') {\n"
                f"//     fetch('http://localhost:{SERVER_PORT}/api/agent/ask_input', {{\n"
                "//       method: 'POST',\n"
                "//       body: JSON.stringify({ agent_name: 'OpenCode', wait_decision: false, ... })\n"
                "//     })\n"
                "//   }\n"
                "// })"
            ),
            "Claude Code": (
                "// ~/.claude/config.json または PreToolUse フック\n"
                "// neo_hisho_bridge MCP サーバーを有効化し、\n"
                "// 危険コマンド実行前に ask_human_approval を自動呼び出し"
            )
        }

        self.txt_snippet = ctk.CTkTextbox(card_snippets, height=130, font=("Consolas", 10))
        self.txt_snippet.pack(fill="x", padx=12, pady=6)
        self.txt_snippet.insert("1.0", snippets["Antigravity"])
        self.txt_snippet.configure(state="disabled")

        def _on_snippet_agent_select(agent: str) -> None:
            if self.txt_snippet:
                self.txt_snippet.configure(state="normal")
                self.txt_snippet.delete("1.0", "end")
                self.txt_snippet.insert("1.0", snippets.get(agent, ""))
                self.txt_snippet.configure(state="disabled")

        combo_agent = ctk.CTkSegmentedButton(
            card_snippets,
            values=["Antigravity", "OpenCode", "Claude Code"],
            command=_on_snippet_agent_select,
            selected_color=self.primary_color
        )
        combo_agent.set("Antigravity")
        combo_agent.pack(fill="x", padx=12, pady=(0, 6))

        def _copy_snippet() -> None:
            if self.txt_snippet:
                text = self.txt_snippet.get("1.0", "end-1c")
                self.frame.clipboard_clear()
                self.frame.clipboard_append(text)
                messagebox.showinfo("Neo-Secretary", t("ui.settings.hooks_copied_msg"))

        btn_copy = ctk.CTkButton(
            card_snippets,
            text=t("ui.settings.hooks_copy_btn"),
            font=self.font_small,
            fg_color=self.primary_color,
            hover_color="#8B634A",
            height=30,
            command=_copy_snippet
        )
        btn_copy.pack(fill="x", padx=12, pady=(0, 12))

        return self.frame

    def collect(self) -> Dict[str, Any]:
        """設定保存用のデータを集約する (HooksTab は保存項目なし)."""
        return {}

    def refresh_texts(self) -> None:
        """多言語変更時の再描画."""
        if self.lbl_hooks_title and getattr(self.lbl_hooks_title, "winfo_exists", lambda: False)():
            self.lbl_hooks_title.configure(text=f"🤖 {t('ui.settings.hooks_card_title')}")
        if self.lbl_hooks_desc and getattr(self.lbl_hooks_desc, "winfo_exists", lambda: False)():
            self.lbl_hooks_desc.configure(text=t("ui.settings.hooks_desc"))
        if self.btn_ping and getattr(self.btn_ping, "winfo_exists", lambda: False)():
            self.btn_ping.configure(text=t("ui.settings.hooks_ping_btn"))

    def _on_ping_test(self) -> None:
        """エージェント連携の接続テスト (Ping) を送信する."""
        if callable(self.on_ping_test_override):
            self.on_ping_test_override()
            return

        if self.btn_ping and getattr(self.btn_ping, "winfo_exists", lambda: False)():
            self.btn_ping.configure(state="disabled", text="⏳ 送信中...")

        def _worker() -> None:
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

                def _ui_callback() -> None:
                    if self.btn_ping and getattr(self.btn_ping, "winfo_exists", lambda: False)():
                        self.btn_ping.configure(state="normal", text=t("ui.settings.hooks_ping_btn"))
                    if success:
                        messagebox.showinfo("Neo-Secretary", t("ui.settings.hooks_ping_success"))
                    else:
                        messagebox.showwarning("Neo-Secretary", t("ui.settings.hooks_ping_fail"))

                if self.frame:
                    self.frame.after(0, _ui_callback)
            except Exception as ex:
                logger.warning("Ping test failed: %s", ex)
                err_msg = str(ex)

                def _ui_error() -> None:
                    if self.btn_ping and getattr(self.btn_ping, "winfo_exists", lambda: False)():
                        self.btn_ping.configure(state="normal", text=t("ui.settings.hooks_ping_btn"))
                    messagebox.showwarning("Neo-Secretary", f"{t('ui.settings.hooks_ping_fail')}\n({err_msg})")

                if self.frame:
                    self.frame.after(0, _ui_error)

        threading.Thread(target=_worker, daemon=True).start()
