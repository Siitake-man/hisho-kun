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
# 秘書くん初回ツアーの7ステップ
DEFAULT_TOUR_STEPS: List[TourStep] = [
    TourStep(
        id="greeting",
        title="🎉 ようこそ！",
        text="こんにちは、ボス！私はネオ秘書くん、あなたのデスクトップAI秘書です。\n"
             "これから一緒に、私の使い方をご案内しますね！\n\n"
             "まずは私をクリックしてみてください。撫でると喜びますよ🥰",
        target_region="pet",
    ),
    TourStep(
        id="menu",
        title="📋 メニューの開き方",
        text="私を**右クリック**、またはウィンドウ上部の**⚙️メニューボタン**を押すと\n"
             "いろんな機能が使えるメニューが開きます。\n\n"
             "手帳・スマホ連携・ポモドーロ・AIモデルの切り替えが一発です！",
        target_region="menu",
        highlight_callback="flash_menu_btn",
    ),
    TourStep(
        id="notebook",
        title="📔 統合手帳",
        text="**📔 統合手帳**では、今日の予定・TODOリスト・習慣トラッカーが"
             "一目で確認できます。\n"
             "Googleカレンダーと連携すると、スマホからも予定を見られますよ！",
        target_region="calendar",
        highlight_callback="flash_calendar_btn",
    ),
    TourStep(
        id="mobile",
        title="📱 スマホ連携",
        text="**📱 スマホDesk Pet** と接続すると、\n"
             "・コーディングエージェントの承認要請をスマホでワンタップ承認\n"
             "・スマホからタスクや手帳を確認\n"
             "・PCとスマホでペットの状態が同期\n"
             "が使えるようになります！QRコードを読むだけです。",
        target_region="pet",
        highlight_callback="flash_qr_btn",
    ),
    TourStep(
        id="pomodoro",
        title="🍅 ポモドーロ集中",
        text="**🍅 ポモドーロタイマー** で作業に集中！\n"
             "25分集中 → 5分休憩のサイクルで、私も集中モードの表情に変わります。\n"
             "作業が捗っているときは、私も嬉しくなりますよ！",
        target_region="pet",
    ),
    TourStep(
        id="settings",
        title="⚙️ 設定画面",
        text="**⚙️ 設定画面**では、\n"
             "・使用するAIモデルの切り替え（Gemini / OpenCode / Claude 等）\n"
             "・Googleカレンダー連携\n"
             "・キャラクタースキン変更\n"
             "・MCPエージェント連携の設定\n\n"
             "がすべてここから行えます。",
        target_region="settings",
        highlight_callback="flash_settings_btn",
    ),
    TourStep(
        id="complete",
        title="🎊 ツアー完了！",
        text="以上でツアーは終了です！お疲れ様でした！🎉\n\n"
             "何か質問や困ったことがあれば、いつでも私に話しかけてください。\n"
             "入力欄に「使い方を教えて」と打ち込むと、いつでもツアーを再開できますよ！\n\n"
             "ボスとの毎日を、楽しくサポートしますね✨",
        target_region=None,
    ),
]


class TourEngine:
    """ツアー状態機械。

    進む(step +1)／戻る(step -1)／スキップ(リセット＆完了扱い)／完了 を管理。
    コールバック経由でGUIに状態変更を通知する。
    """

    def __init__(self, steps: List[TourStep] = None):
        self._steps: List[TourStep] = steps or list(DEFAULT_TOUR_STEPS)
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