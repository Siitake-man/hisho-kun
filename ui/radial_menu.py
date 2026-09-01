#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - サークルメニュー (放射状クイックメニュー) UIモジュール (ui/radial_menu.py)

P2③ 分割リファクタ (Divergent Change 解消) により gui.py から抽出した。
6ボタンの放射状配置メニューの構築・展開/収納アニメーション・各ボタンの
コマンドハンドラ・ホバー時の吹き出し説明を担当する。

設計 (Mixin Seam):
- RadialMenuMixin は NeoSecretaryGUI へ Mixin される前提で、self 経由で
  ホスト (char_canvas / root / circle_menu_active 等) を利用する。
- ボタン座標は Canvas ローカル座標 (中心 170,135) を基準に配置する。
"""

import logging
from typing import Callable, Optional

import customtkinter as ctk

from ui.settings_window import SuggestSettingsDialog

logger = logging.getLogger(__name__)


class RadialMenuMixin:
    """NeoSecretaryGUI にサークルメニュー機能を提供する Mixin。

    Required host attributes:
        root, char_canvas, circle_menu_active, circle_menu_buttons
    Required host methods:
        update_message, switch_character_skin, _open_calendar, _open_qr_connection,
        _open_settings, start_pomodoro, stop_pomodoro
    """

    def _build_radial_menu(self):
        """サークルメニューのボタン群を構築（6ボタン放射状配置）"""
        # サークルメニュー配置: 左右展開（180°付近と0°付近）
        # 上部の吹き出し・入力欄と被らないよう、水平方向に広げる
        import math as _m
        _R = 130
        btn_configs = [
            {"icon": "📔", "cmd": self._on_circle_calendar, "color": "#A67B5B", "dx": int(_R * _m.cos(_m.radians(180))), "dy": -int(_R * _m.sin(_m.radians(180))), "title": "📔 統合手帳（予定・TODO・知見）", "desc": "カレンダー・TODOタスク・知見ノートを開きます。"},
            {"icon": "🍅", "cmd": self._on_circle_pomodoro, "color": "#E53935", "dx": int(_R * _m.cos(_m.radians(150))), "dy": -int(_R * _m.sin(_m.radians(150))), "title": "🍅 ポモドーロ集中タイマー", "desc": "25分間の集中タイマーを開始/停止します。"},
            {"icon": "🎨", "cmd": self._on_circle_skin, "color": "#AB47BC", "dx": int(_R * _m.cos(_m.radians(210))), "dy": -int(_R * _m.sin(_m.radians(210))), "title": "🎨 キャラクタースキン着せ替え", "desc": "秘書くん・キノコ君・アザラシ・ウォンバットを切り替えます。"},
            {"icon": "📱", "cmd": self._on_circle_mobile, "color": "#5B8A72", "dx": int(_R * _m.cos(_m.radians(0))), "dy": -int(_R * _m.sin(_m.radians(0))), "title": "📱 スマホDesk Pet接続", "desc": "スマホ画面と連携するQRコードを表示します。"},
            {"icon": "💡", "cmd": self._on_circle_suggest, "color": "#F57F17", "dx": int(_R * _m.cos(_m.radians(30))), "dy": -int(_R * _m.sin(_m.radians(30))), "title": "💡 サジェストソース設定", "desc": "予定やTODOの自動サジェスト項目を設定します。"},
            {"icon": "⚙", "cmd": self._on_circle_settings, "color": "#7A6B62", "dx": int(_R * _m.cos(_m.radians(330))), "dy": -int(_R * _m.sin(_m.radians(330))), "title": "⚙ アプリ・LLM設定", "desc": "AIモデルやAPIキー、連携設定を開きます。"}
        ]
        
        self.circle_menu_buttons = []
        for cfg in btn_configs:
            btn = ctk.CTkButton(
                self.char_canvas,
                text=cfg["icon"],
                width=38,
                height=38,
                corner_radius=19,
                font=("Meiryo UI", 15, "bold"),
                fg_color=cfg["color"],
                hover_color="#2E1C14",
                command=cfg["cmd"]
            )
            # マウスホバーで吹き出しに機能名と説明を表示
            btn.bind("<Enter>", lambda e, title=cfg["title"], desc=cfg["desc"]: self._on_circle_btn_hover(title, desc))
            btn.bind("<Leave>", lambda e: self._on_circle_btn_leave())
            self.circle_menu_buttons.append({"btn": btn, "dx": cfg["dx"], "dy": cfg["dy"]})

    def _on_circle_skin(self):
        """サークルメニューから次のキャラクタースキンへクイック着せ替え"""
        self.toggle_circle_menu()
        from character_manager import get_character_manager
        char_mgr = get_character_manager()
        order = ["hisho", "kyle"]
        cur = char_mgr.current_character_id
        next_idx = (order.index(cur) + 1) % len(order) if cur in order else 0
        self.switch_character_skin(order[next_idx])

    def _on_circle_btn_hover(self, title: str, desc: str):
        """サークルボタンホバー時に吹き出しへ詳細説明を表示"""
        if self.circle_menu_active:
            self.update_message(f"【{title}】\n{desc}")

    def _on_circle_btn_leave(self):
        """マウスが離れた時に吹き出しを戻す"""
        if self.circle_menu_active:
            self.update_message("えへへ、くすぐったいです！🥰\nボス、呼び出したい機能を選んでくださいね！")

    def toggle_circle_menu(self, on_complete: Optional[Callable[[], None]] = None):
        """サークルメニューの展開/収納アニメーションをトグル"""
        if self.circle_menu_active:
            self._animate_circle_menu(step=4, forward=False, on_complete=on_complete)
        else:
            self._animate_circle_menu(step=1, forward=True, on_complete=on_complete)

    def _animate_circle_menu(self, step: int, forward: bool, on_complete: Optional[Callable[[], None]] = None):
        """放射状アニメーションのステップ進行"""
        cx, cy = 170, 135
        max_steps = 4
        progress = step / float(max_steps)

        if forward:
            self.circle_menu_active = True
            for item in self.circle_menu_buttons:
                btn = item["btn"]
                x = int(cx + item["dx"] * progress - 19)
                y = int(cy + item["dy"] * progress - 19)
                btn.place(x=x, y=y)
                btn.lift()
            
            if step < max_steps:
                self.root.after(20, lambda: self._animate_circle_menu(step + 1, forward=True, on_complete=on_complete))
            else:
                if on_complete:
                    on_complete()
        else:
            for item in self.circle_menu_buttons:
                btn = item["btn"]
                x = int(cx + item["dx"] * progress - 19)
                y = int(cy + item["dy"] * progress - 19)
                btn.place(x=x, y=y)
            
            if step > 0:
                self.root.after(20, lambda: self._animate_circle_menu(step - 1, forward=False, on_complete=on_complete))
            else:
                self.circle_menu_active = False
                for item in self.circle_menu_buttons:
                    item["btn"].place_forget()
                if on_complete:
                    on_complete()

    def _on_circle_calendar(self):
        self.toggle_circle_menu()
        self._open_calendar()

    def _on_circle_pomodoro(self):
        self.toggle_circle_menu()
        if self.pomodoro_active:
            self.stop_pomodoro()
        else:
            self.start_pomodoro(25)

    def _on_circle_mobile(self):
        self.toggle_circle_menu()
        self._open_qr_connection()

    def _on_circle_suggest(self):
        self.toggle_circle_menu()
        SuggestSettingsDialog(self)

    def _on_circle_settings(self):
        self.toggle_circle_menu()
        self._open_settings()
