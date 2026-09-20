#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - オンボーディングツアーUIモジュール (ui/tour_overlay.py)

P2③ 分割リファクタ (Divergent Change 解消) により gui.py から抽出した。
tour_engine.py と連携し、ガイドカード (Toplevel) の表示/更新、Canvas 上への
ピンポイントハイライトリング描画、ツアーの開始/完了処理を担当する。

設計 (Mixin Seam):
- TourOverlayMixin は NeoSecretaryGUI へ Mixin される前提で、self 経由で
  ホスト (root / char_canvas / circle_menu_buttons / menu_btn 等) を利用する。
- 設計: 不透明ガイドカード + ハイライトリング方式。従来のフルスクリーン
  半透明オーバーレイ (alpha依存) を廃止し、Windows Layered Window の
  描画破綻問題を根本解決している。
- ツアーコールバックは tour_engine のスレッドから post_action 経由で
  メインスレッドへディスパッチされる (_start_tour 参照)。
"""

import logging
import os

import tkinter as tk

import app_paths
from tour_engine import TourStep, get_tour_engine

logger = logging.getLogger(__name__)


class TourOverlayMixin:
    """NeoSecretaryGUI にオンボーディングツアー機能を提供する Mixin。

    Required host attributes:
        root, char_canvas, circle_menu_buttons, circle_menu_active, menu_btn
    Required host methods:
        update_message, set_pet_state, post_action, toggle_circle_menu
    """

    def _get_pet_center_rect(self) -> tuple:
        """ペット本体（Canvas中央）のスクリーン座標矩形を返す。"""
        self.root.update_idletasks()
        try:
            canv_x = self.char_canvas.winfo_rootx()
            canv_y = self.char_canvas.winfo_rooty()
        except Exception:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            return (sw - 220, sh - 220, sw - 60, sh - 60)
        cx = canv_x + 170
        cy = canv_y + 135
        # イルカ/マスコットに合わせたジャストサイズ
        return (cx - 75, cy - 65, cx + 75, cy + 65)

    def _get_circle_btn_rect(self, btn_idx: int) -> tuple:
        """指定したサークルメニューボタンのスクリーン座標矩形を返す。"""
        self.root.update_idletasks()
        try:
            canv_x = self.char_canvas.winfo_rootx()
            canv_y = self.char_canvas.winfo_rooty()
        except Exception:
            return self._get_pet_center_rect()

        if 0 <= btn_idx < len(self.circle_menu_buttons):
            cfg = self.circle_menu_buttons[btn_idx]
            bx = canv_x + 170 + cfg["dx"]
            by = canv_y + 135 + cfg["dy"]
            pad = 24  # ボタン半径19px + 余白5px
            return (bx - pad, by - pad, bx + pad, by + pad)
        return self._get_pet_center_rect()

    def _get_widget_rect(self, widget, pad: int = 6) -> tuple:
        """Tkinter/CTk ウィジェットのスクリーン座標矩形を返す。"""
        self.root.update_idletasks()
        try:
            x1 = widget.winfo_rootx()
            y1 = widget.winfo_rooty()
            w = widget.winfo_width()
            h = widget.winfo_height()
            return (x1 - pad, y1 - pad, x1 + w + pad, y1 + h + pad)
        except Exception:
            return self._get_pet_center_rect()

    def _get_tour_target_rect(self, step: 'TourStep') -> tuple:
        """ツアーステップに応じたピンポイントなスクリーン座標矩形を返す。

        step.id は tour_engine.DEFAULT_TOUR_STEPS の3ステップIDと1対1で対応する
        (tests/test_tour_engine.py が整合性を検証)。未知IDはペット本体にフォールバック。
        """
        step_id = getattr(step, 'id', '')

        if step_id == "settings_menu":
            # 1. ようこそ・右クリック案内: ヘッダーの ⚙ メニューボタンを囲む
            return self._get_widget_rect(self.menu_btn, pad=6)
        elif step_id == "mobile_qr":
            # 2. スマホQR連携: サークルメニューの 📱 スマホボタン (index 3)
            return self._get_circle_btn_rect(3)
        elif step_id == "chat_notebook":
            # 3. 会話・手帳: サークルメニューの 📔 手帳ボタン (index 0)
            return self._get_circle_btn_rect(0)
        else:
            return self._get_pet_center_rect()

    def _on_tour_step(self, step: 'TourStep', index: int, total: int) -> None:
        """ツアーステップ変更時のコールバック (post_action 経由で呼ばれる)。"""
        self.update_message(f"【{step.title}】({index+1}/{total})\n\n{step.text}")
        self.set_pet_state("happy", duration_ms=3000)

        # サークルメニューの動的展開/収納連動:
        # 手帳・スマホ・ポモドーロ・設定ではサークルメニューを展開して該当ボタンを光らせる
        step_id = getattr(step, 'id', '')
        if step_id in ("notebook", "mobile", "pomodoro", "settings"):
            if not self.circle_menu_active:
                self.toggle_circle_menu()
        elif step_id in ("greeting", "complete", "menu"):
            if self.circle_menu_active:
                self.toggle_circle_menu()

        # メニューアニメーション完了待ち（少し遅延させて正確な座標でリング描画）
        self.root.after(120, lambda: self._update_tour_overlay(step, index, total))

    def _draw_canvas_tour_highlight(self, cx: int, cy: int, r: int = 24, is_circle: bool = True):
        """Canvas上に直接ハイライトリングを描画する（DPIズレ・透過バグ皆無）。"""
        self.char_canvas.delete("tour_highlight")
        if is_circle:
            # 二重の光る金色オーラ
            self.char_canvas.create_oval(
                cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4,
                outline="#FFD700", width=4, tags="tour_highlight"
            )
            self.char_canvas.create_oval(
                cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1,
                outline="#FFA500", width=2, tags="tour_highlight"
            )
        else:
            self.char_canvas.create_rectangle(
                cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4,
                outline="#FFD700", width=4, tags="tour_highlight"
            )
            self.char_canvas.create_rectangle(
                cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1,
                outline="#FFA500", width=2, tags="tour_highlight"
            )
        # ハイライトリングを最前面に上げつつ、ボタンの下層へ
        self.char_canvas.tag_raise("tour_highlight")
        for item in self.circle_menu_buttons:
            item["btn"].lift()

    def _update_tour_overlay(self, step: 'TourStep', index: int, total: int) -> None:
        """ツアーガイドカードを表示/更新し、Canvas上の対象をピタッとハイライトする。"""
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        CARD_W, CARD_H = 400, 320
        step_id = getattr(step, 'id', '')

        # 1. Canvas上でのピンポイントハイライト描画 (Canvasローカル座標で1ピクセルも狂わない)
        if step_id == "greeting":
            # ペット本体 (中心 170, 135)
            self._draw_canvas_tour_highlight(170, 135, r=55, is_circle=True)
        elif step_id == "menu":
            # メニュー案内: サークルメニュー全体を想起させるペット周辺
            self._draw_canvas_tour_highlight(170, 135, r=60, is_circle=True)
        elif step_id == "notebook":
            # 📔 統合手帳ボタン (dx=-130, dy=0) -> (40, 135)
            self._draw_canvas_tour_highlight(40, 135, r=24, is_circle=True)
        elif step_id == "mobile":
            # 📱 スマホボタン (dx=130, dy=0) -> (300, 135)
            self._draw_canvas_tour_highlight(300, 135, r=24, is_circle=True)
        elif step_id == "pomodoro":
            # 🍅 ポモドーロボタン (dx=-112, dy=-65) -> (58, 70)
            self._draw_canvas_tour_highlight(58, 70, r=24, is_circle=True)
        elif step_id == "settings":
            # ⚙ 設定ボタン (dx=112, dy=65) -> (282, 200)
            self._draw_canvas_tour_highlight(282, 200, r=24, is_circle=True)
        elif step_id == "complete":
            # 🎉 完了: ペット本体
            self._draw_canvas_tour_highlight(170, 135, r=65, is_circle=True)
        else:
            self.char_canvas.delete("tour_highlight")

        # 2. ガイドカードUIの更新
        if not hasattr(self, '_tour_card') or self._tour_card is None:
            self._tour_card = tk.Toplevel(self.root)
            self._tour_card.overrideredirect(True)
            self._tour_card.attributes('-topmost', True)
            self._tour_card.configure(bg='#F5F5DC')

            # ヘッダー (TOP)
            header = tk.Frame(self._tour_card, bg='#F5F5DC', height=36)
            header.pack(fill=tk.X, side=tk.TOP)
            header.pack_propagate(False)

            self._tour_title = tk.Label(
                header, font=("Meiryo UI", 13, "bold"),
                bg='#F5F5DC', fg='#4A3B32', anchor=tk.W)
            self._tour_title.pack(side=tk.LEFT, padx=(14, 4))

            btn_skip = tk.Button(
                header, text="✕ スキップ", font=("Meiryo UI", 10),
                bg='#F5F5DC', fg='#8B7355', bd=0,
                activebackground='#E8DCC8', activeforeground='#8B7355',
                cursor="hand2",
                command=lambda: self._do_tour_action("skip"))
            btn_skip.pack(side=tk.RIGHT, padx=(0, 10))

            self._tour_counter = tk.Label(
                header, font=("Meiryo UI", 10, "bold"),
                bg='#F5F5DC', fg='#A67B5B', anchor=tk.E)
            self._tour_counter.pack(side=tk.RIGHT, padx=(4, 8))

            sep = tk.Frame(self._tour_card, bg='#D4C5A9', height=1)
            sep.pack(fill=tk.X, side=tk.TOP)

            # フッターボタン (BOTTOM)
            btn_frame = tk.Frame(self._tour_card, bg='#F5F5DC', height=50)
            btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
            btn_frame.pack_propagate(False)

            bf = ("Meiryo UI", 11, "bold")
            self._tour_card_prev = tk.Button(
                btn_frame, text="◀ 戻る", font=bf,
                bg='#8B7355', fg='#FFFFFF', bd=1, relief=tk.RAISED,
                activebackground='#A67B5B', activeforeground='#FFFFFF',
                padx=14, pady=4, cursor="hand2",
                command=lambda: self._do_tour_action("prev"))
            self._tour_card_prev.pack(side=tk.LEFT, padx=(14, 6), pady=8)

            self._tour_card_next = tk.Button(
                btn_frame, text="次へ ▶", font=bf,
                bg='#2E7D32', fg='#FFFFFF', bd=1, relief=tk.RAISED,
                activebackground='#388E3C', activeforeground='#FFFFFF',
                padx=16, pady=4, cursor="hand2",
                command=lambda: self._do_tour_action("next"))
            self._tour_card_next.pack(side=tk.RIGHT, padx=(6, 14), pady=8)

            # テキスト領域 (中央expand)
            text_frame = tk.Frame(self._tour_card, bg='#FFF8F0')
            text_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

            self._tour_text = tk.Text(
                text_frame, wrap=tk.WORD, font=("Meiryo UI", 11),
                bg='#FFF8F0', fg='#4A3B32', bd=0,
                padx=8, pady=6, relief=tk.FLAT)
            self._tour_text.pack(fill=tk.BOTH, expand=True)

            self._tour_card.bind("<Escape>", lambda e: self._do_tour_action("skip"))

        self._tour_title.config(text=step.title)
        self._tour_counter.config(text=f"{index+1} / {total}")
        self._tour_text.config(state=tk.NORMAL)
        self._tour_text.delete("1.0", tk.END)
        self._tour_text.insert("1.0", step.text)
        self._tour_text.config(state=tk.DISABLED)

        self._tour_card_prev.config(state=tk.NORMAL if index > 0 else tk.DISABLED)
        next_text = "次へ ▶" if index < total - 1 else "🎉 完了"
        self._tour_card_next.config(text=next_text)

        # カードの配置（ネオ秘書くんウィンドウの左側にスマート配置）
        try:
            root_x = self.root.winfo_rootx()
            root_y = self.root.winfo_rooty()
            root_h = self.root.winfo_height()
        except Exception:
            root_x = sw - 380
            root_y = sh - 480
            root_h = 440

        card_x = max(10, root_x - CARD_W - 20)
        card_y = max(10, min(sh - CARD_H - 20, root_y + (root_h - CARD_H) // 2))

        self._tour_card.geometry(f"{CARD_W}x{CARD_H}+{card_x}+{card_y}")
        self._tour_card.lift()
        self._tour_card.focus_set()

    def _do_tour_action(self, action: str) -> None:
        """ツアーナビゲーションボタンからのアクションを処理する。"""
        e = get_tour_engine()
        if action == "next":
            e.next()
        elif action == "prev":
            e.prev()
        elif action == "skip":
            e.skip()
            self._destroy_tour_overlay()
            self.update_message(
                "🎓 ツアーをスキップしました。\n"
                "いつでも「使い方を教えて」と言ってくださいね！")
        if not e.is_active:
            self._destroy_tour_overlay()

    def _destroy_tour_overlay(self) -> None:
        """ガイドカードとリングを破棄し、サークルメニューを収納・ハイライトを消去する。"""
        try:
            self.char_canvas.delete("tour_highlight")
        except Exception:
            pass
        if getattr(self, 'circle_menu_active', False):
            self.toggle_circle_menu()
        for attr in ('_tour_card', '_tour_ring'):
            w = getattr(self, attr, None)
            if w is not None:
                try:
                    w.destroy()
                except Exception:
                    pass
                setattr(self, attr, None)
        self._tour_ring_canvas = None

    def _check_first_launch_tour(self) -> None:
        """初回起動かどうかを確認し、未完了ならツアーを自動開始する。"""
        flag_file = str(app_paths.get_app_root() / "backups" / ".tour_completed")
        if not os.path.exists(flag_file):
            self.update_message(
                "🎓 はじめまして、ボス！\n"
                "初めてのご利用ありがとうございます！\n"
                "これから使い方をご案内しますね。\n\n"
                "（すぐにスタートします）"
            )
            self.root.after(1500, self._start_tour)

    def _start_tour(self) -> None:
        """秘書くんツアーを開始する。右クリックメニューや初回起動時から呼ばれる。"""
        e = get_tour_engine()
        self._tour_completed = False  # 再開時は冪等ガードをリセット
        e.set_on_step(lambda step, idx, total: self.post_action(
            self._on_tour_step, step, idx, total
        ))
        e.set_on_complete(lambda: self.post_action(self._on_tour_complete))
        # NOTE: skip() は engine 内部で _on_skip_callback と _on_complete_callback
        # の両方を呼ぶため、set_on_skip は設定しない（二重post防止）。
        e.start()

    def _on_tour_complete(self) -> None:
        """ツアー完了後処理。"""
        if getattr(self, '_tour_completed', False):
            return  # 冪等性ガード
        self._tour_completed = True
        self._destroy_tour_overlay()
        flag_dir = str(app_paths.get_app_root() / "backups")
        os.makedirs(flag_dir, exist_ok=True)
        with open(os.path.join(flag_dir, ".tour_completed"), "w") as f:
            f.write("1")
        self.update_message(
            "🎊 ツアー終了！覚えておいてほしいことは…\n\n"
            "📋 **右クリック** でメニュー\n"
            "📔 **統合手帳** で予定・TODO管理\n"
            "📱 **スマホ連携** で承認ブリッジ\n"
            "🍅 **ポモドーロ** で集中\n\n"
            "また見たいときは「使い方を教えて」と呼びかけてね！"
        )
