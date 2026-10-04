#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - Google カレンダー秘密iCal URL 連携セクション (ICalSection / T5b Seam).

(ui/settings_tabs/ical_section.py)

目的:
    Fat モジュール `ui/settings_window.py` から、Google カレンダー秘密 iCal 連携
    (購読ソース一覧・追加・トグル・色切替・編集保存・個別同期・一括同期・削除) の
    UI描画およびハンドラ処理を独立した Deep Module として切り出す。

契約:
    - build() -> ctk.CTkFrame: iCal 購読管理カードUIを構築して返却
    - collect() -> dict: 保存用データ (iCalソースはDB即時保存のため空辞書)
    - refresh_texts() -> None: 多言語更新
    - _render_calendar_sources() -> None: 購読ソース一覧再描画
    - _sync_ical_now() -> None: 全ソース同期実行
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import messagebox
from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk

logger = logging.getLogger("ical_section")


class ICalSection:
    """設定画面「Google カレンダー秘密iCal URL 連携」セクションコンポーネント."""

    SOURCE_PALETTE: List[str] = [
        "#A67B5B", "#1565C0", "#2E7D32", "#C62828", "#6A1B9A", "#00838F", "#F57C00"
    ]

    def __init__(
        self,
        parent_container: ctk.CTkBaseClass,
        parent_gui: Any,
        dispatch: Optional[Callable[[Callable[..., Any]], None]] = None,
        fonts: Optional[Dict[str, Any]] = None,
        colors: Optional[Dict[str, Any]] = None,
    ) -> None:
        """ICalSection を初期化する."""
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
        self.sources_scroll: Optional[ctk.CTkScrollableFrame] = None
        self.btn_ical_sync: Optional[ctk.CTkButton] = None
        self.lbl_ical_last_sync: Optional[ctk.CTkLabel] = None

    def post_ui(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """スレッドセーフにメインスレッドでUI操作を実行する."""
        if self.dispatch:
            self.dispatch(lambda: fn(*args, **kwargs))
        elif hasattr(self.parent_container, "after"):
            self.parent_container.after(0, lambda: fn(*args, **kwargs))
        else:
            fn(*args, **kwargs)

    def build(self) -> ctk.CTkFrame:
        """iCal 購読管理カード UI を構築して返却する."""
        card_ical = ctk.CTkFrame(self.parent_container, fg_color="#FFFFFF", border_width=1, border_color="#E0D8C8", corner_radius=6)
        self.card = card_ical

        ctk.CTkLabel(
            card_ical,
            text="📅 Google カレンダー連携 (読み取り専用・OAuth不要・複数登録可)",
            font=("Meiryo UI", 11, "bold"),
            text_color="#1565C0",
            anchor="w"
        ).pack(fill="x", padx=8, pady=(6, 2))

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

        # 購読ソース一覧
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

        return card_ical

    def collect(self) -> Dict[str, Any]:
        """設定保存用データ（iCalソースはDB即時更新のため空辞書）."""
        return {}

    def refresh_texts(self) -> None:
        """多言語ラベル再描画."""
        pass

    def _render_calendar_sources(self) -> None:
        """購読ソース一覧（有効チェック・色・名前・URL・同期・削除）を再描画する."""
        import database

        if not self.sources_scroll:
            return

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

    def _on_add_calendar_source(self) -> None:
        """新しい購読ソースを追加する（色はパレットから自動割当）."""
        import database

        used = len(database.get_all_calendar_sources())
        database.create_calendar_source(database.CalendarSource(
            name=f"カレンダー{used + 1}",
            color=self.SOURCE_PALETTE[used % len(self.SOURCE_PALETTE)],
            url="",
            enabled=True
        ))
        self._render_calendar_sources()

    def _on_source_toggle(self, source_id: int, var: tk.BooleanVar) -> None:
        """購読ソースの有効/無効を切り替える（同期・表示ともに停止）."""
        import database

        database.set_calendar_source_enabled(source_id, bool(var.get()))
        self._render_calendar_sources()

    def _sync_ical_now(self) -> None:
        """全購読ソースの iCal を今すぐ同期する（バックグラウンド実行）."""
        import ics_tools

        if self.btn_ical_sync:
            self.btn_ical_sync.configure(state="disabled", text="⏳ 同期中...")
        if hasattr(self.parent_container, "update_idletasks"):
            self.parent_container.update_idletasks()

        def _do_sync():
            try:
                count, msg = ics_tools.sync_all_calendar_sources()
                self.post_ui(self._on_ical_sync_done, count, msg)
                if count > 0 and hasattr(self.parent_gui, "refresh_calendar_if_open"):
                    self.post_ui(self.parent_gui.refresh_calendar_if_open)
            except Exception as e:
                self.post_ui(self._on_ical_sync_done, 0, str(e))

        threading.Thread(target=_do_sync, daemon=True).start()

    def _on_ical_sync_done(self, count: int, msg: str) -> None:
        """iCal 同期完了時のUI更新."""
        if self.btn_ical_sync:
            self.btn_ical_sync.configure(state="normal", text="🔄 すべて同期")
        self._render_calendar_sources()
        if count > 0:
            messagebox.showinfo("同期完了", f"📅 {msg} 件の予定を取り込みました！\n手帳とスマホに反映されています。")
        else:
            messagebox.showwarning("同期結果", msg)

    def _on_source_cycle_color(self, source_id: int, current_color: str) -> None:
        """色ボタンクリックで識別色をパレット順に切り替える."""
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

    def _on_source_field_save(self, source_id: int, name: str, url: str) -> None:
        """名前・URLの編集を確定する（FocusOut時）."""
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

    def _on_source_sync(self, source_id: int) -> None:
        """購読ソース1件だけを今すぐ同期する（バックグラウンド実行）."""
        import database
        import ics_tools

        source = database.get_calendar_source(source_id)
        if source is None or not source.url.strip():
            messagebox.showwarning("iCal URL 未設定", "先に秘密の iCal アドレスを貼り付けてください。")
            return

        if self.btn_ical_sync:
            self.btn_ical_sync.configure(state="disabled", text="⏳ 同期中...")
        if hasattr(self.parent_container, "update_idletasks"):
            self.parent_container.update_idletasks()

        def _do():
            try:
                count, msg = ics_tools.sync_calendar_source(source)
                self.post_ui(self._on_ical_sync_done, count, msg)
                if count > 0 and hasattr(self.parent_gui, "refresh_calendar_if_open"):
                    self.post_ui(self.parent_gui.refresh_calendar_if_open)
            except Exception as e:
                self.post_ui(self._on_ical_sync_done, 0, str(e))

        threading.Thread(target=_do, daemon=True).start()

    def _on_source_delete(self, source_id: int, name: str) -> None:
        """購読ソースを削除する（同期済み予定も併せて削除）."""
        import database

        if not messagebox.askyesno("購読削除", f"「{name}」を削除しますか？\nこのカレンダーから同期済みの予定も削除されます。"):
            return
        database.delete_calendar_source(source_id)
        self._render_calendar_sources()
