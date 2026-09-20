"""
ネオ秘書くん - オンボーディングツアーエンジン (tour_engine.py)

初回起動時やユーザー要求時に、秘書くんが吹き出しで機能を案内する
「静的スクリプト型ツアー」（LLM呼び出しゼロ・オフライン完結）。

設計原則:
- TourStep は dataclass で純データ
- TourEngine は状態機械（current_step / next / prev / skip / reset）
- GUI に依存しないためテスト容易
"""

import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# 初回起動検出用のDBキー（database.py で管理）
TOUR_COMPLETED_KEY = "onboarding_tour_completed"
TOUR_SKIPPED_KEY = "onboarding_tour_skipped"


@dataclass
class TourStep:
    """ツアーの1ステップを表すデータクラス。

    Attributes:
        id: ステップの一意識別子。
        title: 吹き出し上部に表示するタイトル。
        text: 秘書くんのセリフ本文。
        target_region: スポットライト領域ヒント
            ("pet" / "menu" / "bubble" / "calendar" / "settings" / None=全体)。
        highlight_callback: オプションのUIハイライト関数名。
        auto_next_ms: 自動次へ進むまでのミリ秒 (0=手動のみ)。
    """
    id: str
    title: str
    text: str
    target_region: Optional[str] = None
    highlight_callback: Optional[str] = None
    auto_next_ms: int = 0
# 秘書くん初回ツアーの3ステップ (2026-09-01 3周レビュー P3対応:
# 初回起動時の認知摩擦低減のため 7ステップ → 3ステップへ凝縮。
# 詳細機能は設定画面「📖 使い方ガイド」タブと右クリックメニューに委譲する)
import i18n

def get_default_tour_steps() -> List[TourStep]:
    """現在言語に応じたデフォルトツアーステップを動的に生成して返す。"""
    return [
        TourStep(
            id="settings_menu",
            title=i18n.t("tour.settings_menu.title"),
            text=i18n.t("tour.settings_menu.text"),
            target_region="menu",
        ),
        TourStep(
            id="mobile_qr",
            title=i18n.t("tour.mobile_qr.title"),
            text=i18n.t("tour.mobile_qr.text"),
            target_region="pet",
        ),
        TourStep(
            id="chat_notebook",
            title=i18n.t("tour.chat_notebook.title"),
            text=i18n.t("tour.chat_notebook.text"),
            target_region="calendar",
        ),
    ]

DEFAULT_TOUR_STEPS: List[TourStep] = get_default_tour_steps()


class TourEngine:
    """ツアー状態機械。

    進む(step +1)／戻る(step -1)／スキップ(リセット＆完了扱い)／完了 を管理。
    コールバック経由でGUIに状態変更を通知する。
    """

    def __init__(self, steps: List[TourStep] = None):
        self._steps: List[TourStep] = steps if steps is not None else get_default_tour_steps()
        self._current_index: int = -1  # -1 = 未開始
        self._is_active: bool = False
        self._on_step_callback: Optional[Callable[[TourStep, int, int], None]] = None
        self._on_complete_callback: Optional[Callable[[], None]] = None
        self._on_skip_callback: Optional[Callable[[], None]] = None

    def set_on_step(self, callback: Callable[[TourStep, int, int], None]) -> None:
        self._on_step_callback = callback

    def set_on_complete(self, callback: Callable[[], None]) -> None:
        self._on_complete_callback = callback

    def set_on_skip(self, callback: Callable[[], None]) -> None:
        self._on_skip_callback = callback

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def current_step(self) -> Optional[TourStep]:
        if 0 <= self._current_index < len(self._steps):
            return self._steps[self._current_index]
        return None

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def total_steps(self) -> int:
        return len(self._steps)

    @property
    def is_first_step(self) -> bool:
        return self._current_index == 0

    @property
    def is_last_step(self) -> bool:
        return self._current_index == len(self._steps) - 1

    def start(self) -> bool:
        if self._is_active:
            return False
        self._steps = get_default_tour_steps()
        self._current_index = 0
        self._is_active = True
        self._notify_step()
        return True

    def next(self) -> bool:
        if not self._is_active:
            return False
        if self._current_index >= len(self._steps) - 1:
            self._complete()
            return False
        self._current_index += 1
        self._notify_step()
        return True

    def prev(self) -> bool:
        if not self._is_active or self._current_index <= 0:
            return False
        self._current_index -= 1
        self._notify_step()
        return True

    def skip(self) -> None:
        if not self._is_active:
            return
        self._is_active = False
        self._current_index = -1
        if self._on_skip_callback:
            self._on_skip_callback()
        if self._on_complete_callback:
            self._on_complete_callback()

    def reset(self) -> None:
        self._is_active = False
        self._current_index = -1

    def _notify_step(self) -> None:
        step = self.current_step
        if step and self._on_step_callback:
            self._on_step_callback(step, self._current_index, len(self._steps))

    def _complete(self) -> None:
        self._is_active = False
        self._current_index = -1
        if self._on_complete_callback:
            self._on_complete_callback()


_global_tour_engine: Optional[TourEngine] = None


def get_tour_engine() -> TourEngine:
    global _global_tour_engine
    if _global_tour_engine is None:
        _global_tour_engine = TourEngine()
    return _global_tour_engine