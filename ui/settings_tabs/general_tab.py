#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - 一般・言語設定タブ (GeneralTab / T2 Seam).

(ui/settings_tabs/general_tab.py)

目的:
    Fat モジュール `ui/settings_window.py` (1,930行) から、Nav 1「一般・言語設定」の
    描画・言語選択イベント処理を独立した Deep Module として切り出す。

契約:
    - build() -> ctk.CTkScrollableFrame: 一般設定UIを構築して返却
    - collect() -> dict: 保存用データ ({"APP_LANGUAGE": lang_code})
    - refresh_texts() -> None: 多言語切り替え時の動的ラベル再描画
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

import customtkinter as ctk

import i18n
from i18n import t

logger = logging.getLogger("general_tab")


class GeneralTab:
    """設定画面「一般・言語設定」タブコンポーネント."""

    def __init__(
        self,
        parent_container: ctk.CTkBaseClass,
        parent_gui: Any,
        dispatch: Optional[Callable[[Callable[..., Any]], None]] = None,
        fonts: Optional[Dict[str, Any]] = None,
        colors: Optional[Dict[str, Any]] = None,
        on_language_change: Optional[Callable[[str], None]] = None,
    ) -> None:
        """GeneralTab を初期化する.

        Args:
            parent_container: 配置先のコンテナウィジェット。
            parent_gui: メインGUIインスタンス。
            dispatch: ワーカースレッドからメインスレッドへのディスパッチャ。
            fonts: フォント定義辞書。
            colors: カラー定義辞書。
            on_language_change: 言語変更時のコールバック関数 (SettingsWindow._on_language_changed)。
        """
        self.parent_container = parent_container
        self.parent_gui = parent_gui
        self.dispatch = dispatch or getattr(parent_gui, "post_action", None)
        self.fonts = fonts or {}
        self.colors = colors or {}
        self.on_language_change = on_language_change

        # フォント・カラーのフォールバック
        self.font_title = self.fonts.get("title", ("Meiryo UI", 11, "bold"))
        self.font_body = self.fonts.get("body", ctk.CTkFont(family="Yu Gothic UI", size=11))
        self.font_small = self.fonts.get("small", ctk.CTkFont(family="Yu Gothic UI", size=10))

        self.primary_color = self.colors.get("primary", "#A67B5B")
        self.text_color = self.colors.get("text", "#3D312A")

        # 言語コード・表示名マッピング
        self._LANG_NAME_TO_CODE = {"日本語": "ja", "English": "en"}
        self._LANG_CODE_TO_NAME = {"ja": "日本語", "en": "English"}

        self.frame: Optional[ctk.CTkScrollableFrame] = None
        self.card_lang: Optional[ctk.CTkFrame] = None
        self.lbl_card_title: Optional[ctk.CTkLabel] = None
        self.lbl_lang_desc: Optional[ctk.CTkLabel] = None
        self.lbl_select_lang: Optional[ctk.CTkLabel] = None
        self.combo_language: Optional[ctk.CTkOptionMenu] = None

    def build(self) -> ctk.CTkScrollableFrame:
        """一般・言語設定タブのUIを構築する.

        Returns:
            ctk.CTkScrollableFrame: 構築されたスクロール可能フレーム。
        """
        self.frame = ctk.CTkScrollableFrame(self.parent_container, fg_color="transparent")

        self.card_lang = ctk.CTkFrame(
            self.frame, fg_color="#FFFFFF", border_width=1, border_color="#E0D8C8", corner_radius=8
        )
        self.card_lang.pack(fill="x", pady=6, padx=2)

        # 英語長文でも見切れない Auto-fit レイアウト: column 0 は自動幅、column 1 は weight=1 で横伸長
        self.card_lang.grid_columnconfigure(0, weight=0)
        self.card_lang.grid_columnconfigure(1, weight=1)

        self.lbl_card_title = ctk.CTkLabel(
            self.card_lang,
            text=f"🌐 {t('ui.settings.language_card_title')}",
            font=self.font_title,
            text_color=self.primary_color,
            anchor="w"
        )
        self.lbl_card_title.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(10, 4))

        self.lbl_lang_desc = ctk.CTkLabel(
            self.card_lang,
            text=t("ui.settings.language_desc"),
            font=self.font_small,
            text_color="#7A6B62",
            anchor="w",
            justify="left"
        )
        self.lbl_lang_desc.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 10))

        # 言語選択行
        self.lbl_select_lang = ctk.CTkLabel(
            self.card_lang,
            text=f"{t('ui.settings.language')}:",
            font=self.font_body,
            text_color=self.text_color,
            anchor="w"
        )
        self.lbl_select_lang.grid(row=2, column=0, sticky="w", padx=(12, 8), pady=(0, 12))

        curr_lang = i18n.get_language()
        init_lang_name = self._LANG_CODE_TO_NAME.get(curr_lang, "日本語")

        def _on_language_selected(selected_name: str) -> None:
            code = self._LANG_NAME_TO_CODE.get(selected_name, "ja")
            i18n.set_language(code)
            logger.info("設定画面から言語を変更しました: %s (%s)", code, selected_name)
            if callable(self.on_language_change):
                self.on_language_change(code)
            self.refresh_texts()

        self.combo_language = ctk.CTkOptionMenu(
            self.card_lang,
            values=["日本語", "English"],
            command=_on_language_selected,
            fg_color=self.primary_color,
            button_color="#8B634A",
            button_hover_color="#6F4E37",
            font=self.font_body,
            dropdown_font=self.font_body,
            dynamic_resizing=True
        )
        self.combo_language.set(init_lang_name)
        self.combo_language.grid(row=2, column=1, sticky="ew", padx=(0, 12), pady=(0, 12))

        return self.frame

    def collect(self) -> Dict[str, Any]:
        """設定保存用のデータを集約する.

        Returns:
            Dict[str, Any]: APP_LANGUAGE を含む辞書。
        """
        selected_code = "ja"
        if self.combo_language:
            selected_name = self.combo_language.get()
            selected_code = self._LANG_NAME_TO_CODE.get(selected_name, "ja")
        return {"APP_LANGUAGE": selected_code}

    def refresh_texts(self, lang: Optional[str] = None) -> None:
        """多言語変更時の再描画."""
        if self.lbl_card_title and getattr(self.lbl_card_title, "winfo_exists", lambda: False)():
            self.lbl_card_title.configure(text=f"🌐 {t('ui.settings.language_card_title', lang=lang)}")
        if self.lbl_lang_desc and getattr(self.lbl_lang_desc, "winfo_exists", lambda: False)():
            self.lbl_lang_desc.configure(text=t("ui.settings.language_desc", lang=lang))
        if self.lbl_select_lang and getattr(self.lbl_select_lang, "winfo_exists", lambda: False)():
            self.lbl_select_lang.configure(text=f"{t('ui.settings.language', lang=lang)}:")
