#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - ポモドーロ集中タイマーUIモジュール (ui/pomodoro.py)

P2③ 分割リファクタ (Divergent Change 解消) により gui.py から抽出した。
ポモドーロタイマーの開始/停止/完了処理と、Canvas 上へのネオン円形アーク
ゲージ描画、完了時のサウンド通知 (winsound) を担当する。

設計 (Mixin Seam):
- PomodoroMixin は NeoSecretaryGUI へ Mixin される前提で、self 経由で
  ホスト (char_canvas / animator / update_message / header_title 等) を利用する。
- Tkinter 操作は全てメインスレッドで実行されること (他スレッドからは
  必ず gui.post_action 経由でディスパッチすること)。
"""

import logging

import tkinter as tk
import tkinter.font  # tk.font.families() の確実な利用のため明示インポート

logger = logging.getLogger(__name__)


class PomodoroMixin:
    """NeoSecretaryGUI にポモドーロタイマー機能を提供する Mixin。

    Required host attributes:
        root, char_canvas, animator, mascot_img_item, header_title
    Required host methods:
        update_message
    """

    def start_pomodoro(self, minutes: int = 25):
        """ポモドーロ集中タイマーを開始"""
        self.pomodoro_active = True
        self.pomodoro_is_break = False
        self.pomodoro_total_seconds = minutes * 60
        self.pomodoro_remaining_seconds = minutes * 60
        
        # 集中アニメーション ＆ 炎・闘気エフェクト発火
        self.animator.trigger_reaction("focus_start")
        self.update_message(
            f"🍅 【ポモドーロ集中開始！】（{minutes}分）\n"
            f"ボス、ゾーンに入りましょう！余計な通知は気にせず作業に没頭してください！🔥"
        )
        self._draw_pomodoro_arc()
        logger.info(f"ポモドーロ開始: {minutes}分")

    def stop_pomodoro(self):
        """ポモドーロ集中タイマーを停止"""
        self.pomodoro_active = False
        self.pomodoro_is_break = False
        self.char_canvas.delete("pomodoro_ui")
        self.char_canvas.delete("pomodoro_ui_top")
        self.animator.trigger_reaction("pomodoro_stop")
        
        # ヘッダータイトルの復元
        from character_manager import get_character_manager
        info = get_character_manager().get_current_character()
        if hasattr(self, 'header_title') and self.header_title.winfo_exists():
            self.header_title.configure(text=f"{info['emoji']} ネオ{info['name']}")
            
        self.update_message("🍅 ポモドーロタイマーを停止しました。\nお疲れ様でした！いつでも再開できますよ。")
        logger.info("ポモドーロ停止")

    def _on_pomodoro_completed(self):
        """ポモドーロタイマー完了時のイベント"""
        self.pomodoro_active = False
        self.char_canvas.delete("pomodoro_ui")
        self.char_canvas.delete("pomodoro_ui_top")
        
        # 歓喜・大ジャンプリアクション発火
        self.animator.trigger_reaction("task_complete")
        
        # ヘッダータイトルの復元
        from character_manager import get_character_manager
        info = get_character_manager().get_current_character()
        if hasattr(self, 'header_title') and self.header_title.winfo_exists():
            self.header_title.configure(text=f"{info['emoji']} ネオ{info['name']}")

        self.update_message(
            "🎉 【25分間の集中達成！】\n"
            "ボス、素晴らしい集中力でした！お見事です！✨\n"
            "5分間の休憩（お茶タイム☕）を取りましょう！"
        )
        # サウンド通知（可能ならビープ音）
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass

    def _draw_pomodoro_arc(self):
        """Canvas 上に残り時間に応じたネオン円形アークゲージとデジタルタイマーを描画"""
        self.char_canvas.delete("pomodoro_ui")
        if not self.pomodoro_active or self.pomodoro_total_seconds <= 0:
            return

        cx, cy = 170, 105
        r = 94  # マスコット（180x180）の外周を美しく包み込むオーラ半径
        
        ratio = max(0.0, min(1.0, self.pomodoro_remaining_seconds / float(self.pomodoro_total_seconds)))
        extent_angle = int(360.0 * ratio)

        # 1. 残り割合に応じたネオンカラーの動的選定
        if ratio >= 0.75:
            neon_color = "#00E5FF"     # ネオンシアン (集中初期)
        elif ratio >= 0.30:
            neon_color = "#00E676"     # ネオングリーン (中盤・安定)
        elif ratio >= 0.10:
            neon_color = "#FF9100"     # ネオンオレンジ (後半)
        else:
            neon_color = "#FF1744"     # ネオンレッド (ラストスパート)

        # 2. 背後のガイドトラック円
        self.char_canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            outline="#3E2723",
            fill="",
            width=2,
            tags="pomodoro_ui"
        )

        # 3. 発光ネオンアーク（時計の12時位置から時計回り）
        if extent_angle > 0:
            self.char_canvas.create_arc(
                cx - r, cy - r, cx + r, cy + r,
                start=90,
                extent=-extent_angle,
                outline=neon_color,
                fill="",
                width=4,
                style=tk.ARC,
                tags="pomodoro_ui"
            )

        # 4. デジタルカウントダウン表示（Canvas最下部にスマート配置）
        mins = self.pomodoro_remaining_seconds // 60
        secs = self.pomodoro_remaining_seconds % 60
        timer_text = f"🍅 {mins:02d}:{secs:02d}"
        
        # 背景バッジ
        self.char_canvas.create_rectangle(
            cx - 36, 192, cx + 36, 208,
            fill="#1E140E",
            outline=neon_color,
            width=1,
            tags="pomodoro_ui_top"
        )
        self.char_canvas.create_text(
            cx, 200,
            text=timer_text,
            fill="#FFD54F",
            font=("DotGothic16", 9, "bold") if "DotGothic16" in tk.font.families() else ("Meiryo UI", 9, "bold"),
            tags="pomodoro_ui_top"
        )

        # ゲージ円をキャラクター画像の背後（下層）へ配置し、キャラを絶対に隠さない
        if self.mascot_img_item is not None:
            self.char_canvas.tag_lower("pomodoro_ui", self.mascot_img_item)
