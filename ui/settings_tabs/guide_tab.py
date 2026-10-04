#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - 使い方ガイドタブ (GuideTab / T1 Seam).

(ui/settings_tabs/guide_tab.py)

目的:
    Fat モジュール `ui/settings_window.py` (1,930行) から、最も低リスクな葉ノードである
    Nav 6「使い方ガイド」の描画とツアー再開ロジックを独立した Deep Module として切り出す。

契約:
    - build() -> ctk.CTkScrollableFrame: ガイドUIを構築して返却
    - collect() -> dict: 保存用データ (GuideTab はデータなしのため空辞書)
    - refresh_texts() -> None: 多言語切り替え時の再描画
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, Optional

import customtkinter as ctk

logger = logging.getLogger("guide_tab")


class GuideTab:
    """設定画面「使い方ガイド」タブコンポーネント."""

    def __init__(
        self,
        parent_container: ctk.CTkBaseClass,
        parent_gui: Any,
        dispatch: Optional[Callable[[Callable[..., Any]], None]] = None,
        fonts: Optional[Dict[str, Any]] = None,
        colors: Optional[Dict[str, Any]] = None,
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        """GuideTab を初期化する.

        Args:
            parent_container: 配置先のコンテナウィジェット。
            parent_gui: メインGUIインスタンス (ツアー呼び出し等)。
            dispatch: ワーカースレッドからメインスレッドへのディスパッチャ (post_action)。
            fonts: フォント定義辞書。
            colors: カラー定義辞書。
            on_close: ウィンドウ終了コールバック。
        """
        self.parent_container = parent_container
        self.parent_gui = parent_gui
        self.dispatch = dispatch or getattr(parent_gui, "post_action", None)
        self.fonts = fonts or {}
        self.colors = colors or {}
        self.on_close = on_close

        # フォント・カラーのフォールバック
        self.font_title = self.fonts.get("title", ctk.CTkFont(family="Yu Gothic UI", size=13, weight="bold"))
        self.font_body = self.fonts.get("body", ctk.CTkFont(family="Yu Gothic UI", size=11))
        self.font_small = self.fonts.get("small", ctk.CTkFont(family="Yu Gothic UI", size=10))

        self.primary_color = self.colors.get("primary", "#A67B5B")
        self.text_color = self.colors.get("text", "#3D312A")

        self.frame: Optional[ctk.CTkScrollableFrame] = None

    def build(self) -> ctk.CTkScrollableFrame:
        """使い方ガイドタブのUIを構築する.

        Returns:
            ctk.CTkScrollableFrame: 構築されたスクロール可能フレーム。
        """
        self.frame = ctk.CTkScrollableFrame(self.parent_container, fg_color="transparent")

        # クイックスタート
        ctk.CTkLabel(
            self.frame, text="🚀 クイックスタート", font=self.font_title,
            text_color=self.primary_color, anchor="w"
        ).pack(anchor="w", pady=(6, 2))

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
            row = ctk.CTkFrame(self.frame, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=title, font=self.font_title,
                          text_color=self.text_color, anchor="w").pack(anchor="w")
            ctk.CTkLabel(row, text=desc, font=self.font_small,
                          text_color="#7A6B62", anchor="w", wraplength=400).pack(anchor="w", padx=(12, 0))

        # ツアー再開ボタン
        ctk.CTkLabel(self.frame, text="", height=10).pack()
        btn_restart_tour = ctk.CTkButton(
            self.frame, text="🎓 秘書くんツアーをもう一度見る",
            font=self.font_body, fg_color=self.primary_color,
            hover_color="#8B634A", height=34,
            command=self._restart_tour
        )
        btn_restart_tour.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(
            self.frame, text="※ 初回起動時のオンボーディングツアーを再開できます。",
            font=self.font_small, text_color="#A67B5B", anchor="w"
        ).pack(anchor="w", padx=20)

        # 注意事項
        ctk.CTkLabel(self.frame, text="", height=8).pack()
        ctk.CTkLabel(
            self.frame, text="⚠️ 注意事項", font=self.font_title,
            text_color=self.primary_color, anchor="w"
        ).pack(anchor="w", pady=(6, 2))

        notices = [
            "• スマホ連携にはPCと同じWi-Fiネットワークが必要です。",
            "• 外出先からはTailscale VPN経由で接続できます。",
            "• Googleカレンダー連携は読み取り専用（iCal URL）です。",
            "• LLMのAPIキーは各自ご用意ください（.envファイルに設定）。",
            "• 詳細な使い方は docs/ 配下のドキュメントをご参照ください。",
        ]
        for n in notices:
            ctk.CTkLabel(
                self.frame, text=n, font=self.font_small,
                text_color="#7A6B62", anchor="w", wraplength=400
            ).pack(anchor="w", padx=(8, 0))

        return self.frame

    def collect(self) -> Dict[str, Any]:
        """設定保存用のデータを集約する (GuideTab は保存項目なし)."""
        return {}

    def refresh_texts(self) -> None:
        """多言語変更時の再描画 (静的ガイドテキスト)."""
        pass

    def _restart_tour(self) -> None:
        """ツアー再開を実行する."""
        # フラグファイルを削除して初回扱いにする
        flag_file = os.path.join(os.path.dirname(__file__), "..", "..", "backups", ".tour_completed")
        try:
            if os.path.exists(flag_file):
                os.remove(flag_file)
        except OSError as e:
            logger.warning(f"ツアー完了フラグファイル削除失敗 ({flag_file}): {e}")

        if hasattr(self.parent_gui, "_start_tour"):
            if callable(self.dispatch):
                self.dispatch(self.parent_gui._start_tour)
            else:
                self.parent_gui._start_tour()

        if callable(self.on_close):
            self.on_close()
