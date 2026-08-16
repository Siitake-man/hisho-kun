#!/usr/bin/env python3
"""
ネオ秘書くん - ペットアニメーション ＆ 自律ステートマシン (pet_animator.py)

机の上の相棒として「自律的なコミカルモーション（お茶、読書、ストレッチ、居眠り）」と
「ボスの作業に寄り添う共感リアクション（タスク完了ジャンプ、集中応援、お茶差し出し、夜間ウトウト）」
を制御し、滑らかなフレームアニメーションを提供します。
"""

import time
import random
import logging
from typing import Dict, List, Optional, Callable

logger = logging.getLogger(__name__)

# 各ステートに対応するアニメーションフレーム定義
ANIMATION_FRAMES: Dict[str, List[str]] = {
    # 基本待機 (瞬き含む)
    "idle": ["idle_1", "idle_1", "idle_1", "idle_2", "idle_1", "idle_1"],
    
    # 自律行動 (Idle Actions)
    "tea": ["tea_1", "tea_2", "tea_1", "tea_2"],
    "reading": ["reading_1", "reading_2", "reading_1", "reading_2"],
    "stretch": ["stretch_1", "stretch_2", "stretch_2", "stretch_1"],
    "sleepy": ["sleepy_1", "sleepy_2", "sleepy_1", "sleepy_2"],
    
    # ボスへの共感リアクション (Context Reactions)
    "celebrate": ["celebrate_1", "celebrate_2", "celebrate_3", "celebrate_2"],
    "care": ["care_1", "care_2", "care_1", "care_2"],
    "cheer": ["cheer", "happy", "cheer", "happy"],
    "night": ["night_1", "night_2", "night_1", "night_2"],
    
    # 作業・思考・アラート
    "thinking": ["thinking_1", "thinking_2"],
    "focus": ["focus_1", "focus_2"],
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
    ("sleepy", 6.0)     # コックリ舟を漕ぐ (6秒)
]


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
        self.on_frame_change: Optional[Callable[[str], None]] = on_frame_change
        self._current_frame_name: str = "idle_1"
        self.is_night_mode: bool = False

    def set_state(self, state_name: str, duration_sec: float = 0.0) -> None:
        """ペットの状態を切り替えます。

        Args:
            state_name (str): 遷移先ステート名 ('idle', 'celebrate', 'care', 'tea' 等)
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

        # 直ちに新しいフレームを反映
        frames = ANIMATION_FRAMES[self.current_state]
        self._current_frame_name = frames[0]
        if self.on_frame_change:
            self.on_frame_change(self._current_frame_name)

        logger.debug(f"ペット状態遷移: {state_name} (duration={duration_sec}s)")

    def trigger_reaction(self, event_type: str) -> None:
        """外部イベントに応じたリアクションを発火させます。

        Args:
            event_type (str): イベント種別 ('task_complete', 'care_tea', 'cheer', 'alarm', 'love' 等)
        """
        if event_type == "task_complete":
            # タスク完了: クラッカー＆大ジャンプ！ (5秒間)
            self.set_state("celebrate", duration_sec=5.0)
        elif event_type in ("care_tea", "proactive_care"):
            # 45分作業ケア: お茶をどうぞ！ (7秒間)
            self.set_state("care", duration_sec=7.0)
        elif event_type == "cheer":
            # 集中応援 (5秒間)
            self.set_state("cheer", duration_sec=5.0)
        elif event_type == "love":
            # なでなで (3秒間)
            self.set_state("pet_love", duration_sec=3.0)
        elif event_type == "alarm":
            # 承認要請アラート (手動解除まで継続)
            self.set_state("alarm_ask", duration_sec=0.0)
        elif event_type == "thinking":
            # AI推論中
            self.set_state("thinking", duration_sec=0.0)
        elif event_type == "idle":
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
                action_name, action_dur = random.choice(IDLE_ACTIONS)
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
