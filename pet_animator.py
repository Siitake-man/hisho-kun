#!/usr/bin/env python3
"""
ネオ秘書くん - ペットアニメーション ＆ 自律ステートマシン (pet_animator.py)

机の上の相棒として「自律的なコミカルモーション（お茶、読書、ストレッチ、居眠り）」と
「ボスの作業に寄り添う共感リアクション（タスク完了ジャンプ、集中応援、お茶差し出し、夜間ウトウト）」
を制御し、滑らかなフレームアニメーションを提供します。
"""

import time
import math
import random
import logging
from typing import Dict, List, Optional, Callable, Any, Tuple

logger = logging.getLogger(__name__)

# 各ステートに対応するアニメーションフレーム定義
ANIMATION_FRAMES: Dict[str, List[str]] = {
    # 基本待機 (瞬き含む)
    "idle": ["idle_1", "idle_1", "idle_1", "idle_2", "idle_1", "idle_1"],
    "walk": ["walk_1", "walk_2"],
    
    # 自律行動 (Idle Actions)
    "tea": ["tea_1", "tea_2", "tea_1", "tea_2"],
    "reading": ["reading_1", "reading_2", "reading_1", "reading_2"],
    "stretch": ["stretch_1", "stretch_2", "stretch_2", "stretch_1"],
    "sleepy": ["sleepy_1", "sleepy_2", "sleepy_1", "sleepy_2"],

    # 生活モーション拡張（案1: 既存スプライト流用・専用スプライトは今後差し替え）
    "train": ["stretch_1", "stretch_2", "stretch_2", "stretch_1"],   # 筋トレ風（腕伸縮をベンチプレス風に見せる）
    "study": ["reading_1", "reading_2", "thinking_1", "reading_2"],  # 勉強風（読書＋考え込みの混合）
    
    # ボスへの共感リアクション (Context Reactions)
    "celebrate": ["celebrate_1", "celebrate_2", "celebrate_3", "celebrate_2"],
    "care": ["care_1", "care_2", "care_1", "care_2"],
    "cheer": ["cheer", "happy", "cheer", "happy"],
    "night": ["night_1", "night_2", "night_1", "night_2"],
    
    # 作業・思考・アラート・集中ポモドーロ
    "thinking": ["thinking_1", "thinking_2"],
    "focus": ["focus_1", "focus_2"],
    "coding": ["focus_1", "focus_2"],
    "alarm_ask": ["alarm_ask"],
    "pet_love": ["pet_love"],
    "happy": ["happy"],
    
    # 視線追従
    "look_left": ["look_left"],
    "look_right": ["look_right"],
    "look_up": ["look_up"],
    "look_down": ["look_down"]
}

# 自律行動としてランダム発火する候補と持続時間(秒)
IDLE_ACTIONS = [
    ("tea", 6.0),       # 湯呑みでお茶をすする (6秒)
    ("reading", 8.0),   # 本をペラペラ読む (8秒)
    ("stretch", 4.0),   # ぐーっと伸びをする (4秒)
    ("sleepy", 6.0),    # コックリ舟を漕ぐ (6秒)
    ("train", 5.0),     # 🏋️ 筋トレに励む (5秒)
    ("study", 7.0)      # ✍️ 勉強に打ち込む (7秒)
]


class EffectOverlay:
    """
    集中時の闘気・炎（🔥）・猛烈タイピング火花・汗マーク等を管理するエフェクト描画制御クラス。
    Tkinter Canvas 上で直接パーティクル（火の粉・オーラ円弧・集中線）を描画するための幾何データを生成します。
    """

    def __init__(self):
        self.current_effect: Optional[str] = None
        self.particles: List[Dict[str, Any]] = []
        self.tick_count: int = 0

    def set_effect(self, effect_name: Optional[str]) -> None:
        """エフェクトを設定 ('flame', 'focus_aura', 'sparks', 'sweat', None)"""
        self.current_effect = effect_name
        self.particles.clear()
        self.tick_count = 0
        logger.debug(f"エフェクト変更: {effect_name}")

    def update_particles(self, center_x: int = 170, center_y: int = 135) -> List[Dict[str, Any]]:
        """
        毎フレーム呼ばれ、現在のアクティブなエフェクトに応じたパーティクルリストを更新・返却します。
        
        Returns:
            List[Dict[str, Any]]: 描画用アイテムリスト
            例: [{"type": "oval", "coords": (x0, y0, x1, y1), "color": "#FF5722", "width": 1}]
        """
        if not self.current_effect:
            return []

        self.tick_count += 1
        items: List[Dict[str, Any]] = []

        if self.current_effect in ("flame", "focus_aura", "focus", "coding"):
            # 燃え盛る火の粉・闘気パーティクル (16〜24個維持)
            if len(self.particles) < 20 and random.random() < 0.85:
                px = center_x + random.uniform(-40, 40)
                py = center_y + random.uniform(20, 40)
                size = random.uniform(3.5, 8.0)
                vy = random.uniform(-4.5, -2.5)
                vx = random.uniform(-1.5, 1.5)
                color = random.choice(["#FF1744", "#FF5252", "#FF9100", "#FFD700", "#FFEA00"])
                self.particles.append({
                    "type": "flame",
                    "x": px, "y": py, "vx": vx, "vy": vy,
                    "size": size, "life": random.randint(14, 26),
                    "color": color
                })

            alive = []
            for p in self.particles:
                p["x"] += p["vx"]
                p["y"] += p["vy"]
                p["life"] -= 1
                p["size"] = max(1.5, p["size"] * 0.94)
                if p["life"] > 0 and p["y"] > center_y - 75:
                    alive.append(p)
                    rad = p["size"]
                    items.append({
                        "type": "oval",
                        "coords": (p["x"] - rad, p["y"] - rad, p["x"] + rad, p["y"] + rad),
                        "color": p["color"],
                        "fill": p["color"],
                        "width": 0
                    })
            self.particles = alive

        elif self.current_effect in ("love", "heart", "pet_love", "happy"):
            # なでなで・親愛度アップの浮遊ハート💖パーティクル
            if len(self.particles) < 8 and random.random() < 0.6:
                px = center_x + random.uniform(-35, 35)
                py = center_y + random.uniform(-10, 20)
                size = random.uniform(5.0, 10.0)
                vy = random.uniform(-2.5, -1.2)
                vx = random.uniform(-0.8, 0.8)
                color = random.choice(["#FF4081", "#FF80AB", "#F50057", "#FF1744"])
                self.particles.append({
                    "type": "heart",
                    "x": px, "y": py, "vx": vx, "vy": vy,
                    "size": size, "life": random.randint(20, 35),
                    "color": color
                })

            alive = []
            for p in self.particles:
                p["x"] += p["vx"]
                p["y"] += p["vy"]
                p["life"] -= 1
                if p["life"] > 0:
                    alive.append(p)
                    rad = p["size"]
                    # 2つの円と逆三角形でハート型を近似描画
                    items.append({
                        "type": "oval",
                        "coords": (p["x"] - rad, p["y"] - rad, p["x"] + rad, p["y"] + rad),
                        "color": p["color"],
                        "fill": p["color"],
                        "width": 0
                    })
            self.particles = alive

        elif self.current_effect in ("celebrate", "sparkle", "cheer"):
            # 完了祝いのキラキラ星・紙吹雪パーティクル
            if len(self.particles) < 18 and random.random() < 0.8:
                px = center_x + random.uniform(-50, 50)
                py = center_y + random.uniform(-30, 20)
                size = random.uniform(3.0, 7.0)
                vy = random.uniform(-3.0, 2.0)
                vx = random.uniform(-2.5, 2.5)
                color = random.choice(["#FFD700", "#00E676", "#00E5FF", "#FF4081", "#7C4DFF"])
                self.particles.append({
                    "type": "sparkle",
                    "x": px, "y": py, "vx": vx, "vy": vy,
                    "size": size, "life": random.randint(15, 30),
                    "color": color
                })

            alive = []
            for p in self.particles:
                p["x"] += p["vx"]
                p["y"] += p["vy"]
                p["life"] -= 1
                if p["life"] > 0:
                    alive.append(p)
                    rad = p["size"]
                    items.append({
                        "type": "oval",
                        "coords": (p["x"] - rad, p["y"] - rad, p["x"] + rad, p["y"] + rad),
                        "color": p["color"],
                        "fill": p["color"],
                        "width": 0
                    })
            self.particles = alive

        elif self.current_effect in ("sleepy", "zzz", "night"):
            # 睡眠・居眠りのZzz浮遊バブル
            if len(self.particles) < 4 and random.random() < 0.3:
                px = center_x + 25 + random.uniform(-5, 10)
                py = center_y - 20
                self.particles.append({
                    "type": "zzz",
                    "x": px, "y": py, "vx": 0.5, "vy": -1.2,
                    "size": random.uniform(4.0, 7.0),
                    "life": 40,
                    "color": "#90CAF9"
                })

            alive = []
            for p in self.particles:
                p["x"] += p["vx"]
                p["y"] += p["vy"]
                p["life"] -= 1
                if p["life"] > 0:
                    alive.append(p)
                    rad = p["size"]
                    items.append({
                        "type": "oval",
                        "coords": (p["x"] - rad, p["y"] - rad, p["x"] + rad, p["y"] + rad),
                        "color": p["color"],
                        "fill": p["color"],
                        "width": 0
                    })
            self.particles = alive

        elif self.current_effect == "sweat":
            # 焦り・エラー時の汗マーク（青いしずく）
            drop_y = center_y - 35 + (self.tick_count % 6) * 2
            items.append({
                "type": "oval",
                "coords": (center_x + 30, drop_y, center_x + 36, drop_y + 8),
                "color": "#00B0FF",
                "fill": "#00B0FF",
                "width": 0
            })

        return items


class PetAnimator:
    """ペットのアニメーションと自律状態遷移を管理するステートマシン"""

    def __init__(self, on_frame_change: Optional[Callable[[str], None]] = None):
        """初期化

        Args:
            on_frame_change (Optional[Callable[[str], None]]): フレーム変更時のコールバック関数
        """
        self.current_state: str = "idle"
        self.frame_index: int = 0
        self.state_end_time: float = 0.0  # 一時ステートの終了予定時刻
        self.next_idle_action_time: float = time.time() + random.uniform(15.0, 30.0)
        # 徘徊モード（デスクトップ散歩）: GUI 側のトグルで ON/OFF
        self.wandering_enabled: bool = False
        self.walk_direction: int = 1
        self.on_frame_change: Optional[Callable[[str], None]] = on_frame_change
        self._current_frame_name: str = "idle_1"
        self.is_night_mode: bool = False
        # エフェクトオーバーレイエンジン
        self.effects: EffectOverlay = EffectOverlay()

    def set_state(self, state_name: str, duration_sec: float = 0.0) -> None:
        """ペットの状態を切り替えます。

        Args:
            state_name (str): 遷移先ステート名 ('idle', 'celebrate', 'care', 'tea', 'focus', 'coding' 等)
            duration_sec (float, optional): 一時持続秒数。0の場合は恒久。 Defaults to 0.0.
        """
        if state_name not in ANIMATION_FRAMES:
            logger.warning(f"未定義のアニメーションステートです: {state_name}")
            return

        self.current_state = state_name
        self.frame_index = 0
        now = time.time()

        if duration_sec > 0:
            self.state_end_time = now + duration_sec
        else:
            self.state_end_time = 0.0

        # エフェクトの自動連動
        if state_name in ("focus", "coding"):
            self.effects.set_effect("flame")
        elif state_name == "idle" and self.effects.current_effect == "flame":
            self.effects.set_effect(None)

        # 直ちに新しいフレームを反映
        frames = ANIMATION_FRAMES[self.current_state]
        self._current_frame_name = frames[0]
        if self.on_frame_change:
            self.on_frame_change(self._current_frame_name)

        logger.debug(f"ペット状態遷移: {state_name} (duration={duration_sec}s)")

    def trigger_reaction(self, event_type: str) -> None:
        """外部イベントに応じたリアクションを発火させます。

        Args:
            event_type (str): イベント種別 ('task_complete', 'care_tea', 'cheer', 'alarm', 'focus_start', 'coding_start', 'error_panic' 等)
        """
        if event_type == "task_complete":
            # タスク完了: クラッカー＆大ジャンプ！ (5秒間)
            self.effects.set_effect(None)
            self.set_state("celebrate", duration_sec=5.0)
        elif event_type in ("focus_start", "pomodoro_start"):
            # ポモドーロ集中開始: 闘気・炎エフェクト ＆ 集中ポーズ
            self.set_state("focus", duration_sec=0.0)
            self.effects.set_effect("flame")
        elif event_type in ("coding_start", "agent_working"):
            # コーディングエージェント作業中: 猛烈タイピング
            self.set_state("coding", duration_sec=0.0)
            self.effects.set_effect("flame")
        elif event_type in ("care_tea", "proactive_care"):
            # 45分作業ケア: お茶をどうぞ！ (7秒間)
            self.effects.set_effect(None)
            self.set_state("care", duration_sec=7.0)
        elif event_type == "cheer":
            # 集中応援 (5秒間)
            self.set_state("cheer", duration_sec=5.0)
        elif event_type == "love":
            # なでなで (3秒間)
            self.set_state("pet_love", duration_sec=3.0)
        elif event_type == "alarm":
            # 承認要請アラート (手動解除まで継続)
            self.effects.set_effect("sweat")
            self.set_state("alarm_ask", duration_sec=0.0)
        elif event_type == "error_panic":
            # エラー発生: 汗マーク
            self.effects.set_effect("sweat")
            self.set_state("alarm_ask", duration_sec=4.0)
        elif event_type == "thinking":
            # AI推論中
            self.effects.set_effect(None)
            self.set_state("thinking", duration_sec=0.0)
        elif event_type in ("idle", "pomodoro_stop"):
            self.effects.set_effect(None)
            self.set_state("idle", duration_sec=0.0)

    def tick(self) -> str:
        """タイマー周期（例: 300msごと）で呼ばれ、次のフレーム名を返します。

        Returns:
            str: 現在表示すべきスプライト名 (例: 'tea_1', 'celebrate_2')
        """
        now = time.time()

        # 1. 一時ステートの終了判定
        if self.state_end_time > 0 and now >= self.state_end_time:
            self.state_end_time = 0.0
            # 夜間なら night に戻し、通常なら idle に戻す
            if self.is_night_mode:
                self.current_state = "night"
            else:
                self.current_state = "idle"
            self.frame_index = 0
            self.next_idle_action_time = now + random.uniform(15.0, 35.0)

        # 2. 通常待機中の自律行動（ランダム気まぐれアクション）判定
        elif self.current_state == "idle" and self.state_end_time == 0:
            if now >= self.next_idle_action_time:
                actions = list(IDLE_ACTIONS)
                if self.wandering_enabled:
                    actions.append(("walk", 5.0))
                action_name, action_dur = random.choice(actions)
                if action_name == "walk":
                    self.walk_direction = random.choice((-1, 1))
                self.set_state(action_name, duration_sec=action_dur)

        # 3. フレームインデックスを進める
        frames = ANIMATION_FRAMES.get(self.current_state, ["idle_1"])
        self.frame_index = (self.frame_index + 1) % len(frames)
        self._current_frame_name = frames[self.frame_index]

        if self.on_frame_change:
            self.on_frame_change(self._current_frame_name)

        return self._current_frame_name

    def get_current_frame(self) -> str:
        """現在のフレーム名を返します。"""
        return self._current_frame_name

    def set_night_mode(self, enabled: bool) -> None:
        """夜間モードのON/OFFを設定します。"""
        self.is_night_mode = enabled
        if enabled and self.current_state == "idle":
            self.set_state("night", duration_sec=0.0)
        elif not enabled and self.current_state == "night":
            self.set_state("idle", duration_sec=0.0)

    def get_bounce_transform(self) -> Tuple[float, float, int]:
        """
        現在の時間とアニメーション状態から、呼吸（サイン波）および弾力伸縮（Squash & Stretch）の
        スケール倍率 (scale_x, scale_y) と上下ピクセルオフセット (offset_y) を計算して返します。

        Returns:
            Tuple[float, float, int]: (scale_x, scale_y, offset_y)
        """
        now = time.time()
        
        # 1. 待機時・夜間・思考時の呼吸モーション (2.4秒周期の滑らかなサイン波)
        if self.current_state in ("idle", "night", "thinking", "reading", "tea"):
            breathe = math.sin(now * 2.6) * 0.03  # ±3% の自然な伸縮
            offset_y = int(math.sin(now * 2.6) * 2.5)  # 2.5pxの上下動
            return (1.0 + breathe, 1.0 - breathe, offset_y)

        # 2. 集中・コーディング時の激しいタイピング振動 (0.2秒周期)
        elif self.current_state in ("focus", "coding"):
            jitter = math.sin(now * 18.0) * 0.02
            offset_y = int(math.sin(now * 22.0) * 1.5)
            return (1.0 + jitter, 1.0 - jitter, offset_y)

        # 3. お祝い・大ジャンプ・応援時の弾力バウンス
        elif self.current_state in ("celebrate", "cheer"):
            jump_phase = (now * 4.0) % math.pi
            offset_y = -int(math.sin(jump_phase) * 8.0)
            squash = math.cos(jump_phase) * 0.06
            return (1.0 - squash, 1.0 + squash, offset_y)

        # 4. なでなで（Pet Love）時のぷにぷに弾力
        elif self.current_state == "pet_love":
            purr = math.sin(now * 8.0) * 0.05
            return (1.0 + purr, 1.0 - purr, 0)

        # デフォルト
        return (1.0, 1.0, 0)
