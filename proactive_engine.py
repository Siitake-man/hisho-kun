"""
ネオ秘書くん - 自律的プロアクティブ声掛け・健康見守りエンジン (proactive_engine.py)

ボスの作業時間や生活リズム、未完了タスクをバックグラウンドで見守り、
疲れや長時間作業を検知した際にドット絵ペットが自律的に優しい声掛けを行うモジュール。
"""

import time
import random
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# 声掛けメッセージのプリセット集
CARE_MESSAGES = {
    "break_short": [
        "☕ ボス、少し作業が続いていますよ。\n温かいお茶でも飲んで一息つきませんか？",
        "👀 目が疲れていませんか？\n20秒ほど遠くの景色を眺めてみてくださいね！",
        "🙆‍♂️ 軽く肩や首を回してストレッチしましょう！\n集中力アップになりますよ。"
    ],
    "break_long": [
        "⏳ ボス、2時間以上集中されています！\n素晴らしい集中力ですが、生命の最適利用のために5分間の休憩を取りましょう。",
        "🚶‍♂️ 少し立ち上がって深呼吸しませんか？\n天風先生も『積極的な心身のリフレッシュ』を推奨されています！"
    ],
    "evening_care": [
        "🌙 もう夕方ですね。今日のタスクの進捗はいかがですか？\n夜はご家族のケアもありますので、無理せずキリのいいところで切り上げましょう！",
        "🌆 今日もお疲れ様です！\n残りのタスクを手帳で確認して、今日やる分を絞り込みましょうか？"
    ]
}


class ProactiveCareEngine:
    """
    ボスの作業状態を非同期で見守り、適切なタイミングで声掛けをトリガーするエンジン。
    """
    
    def __init__(self, notify_callback: Optional[Callable[[str, str], None]] = None):
        """
        Args:
            notify_callback: メッセージ通知用コールバック (text: str, pet_state: str) -> None
        """
        self.notify_callback = notify_callback
        self.last_user_action_time = time.time()
        self.last_care_time = time.time()
        self.care_interval_seconds = 45 * 60  # 45分ごとの見守り
        self.is_enabled = True
        
        logger.info("ProactiveCareEngine が初期化されました（見守り間隔: 45分）")

    def record_user_activity(self):
        """ユーザーの操作（入力など）を記録"""
        self.last_user_action_time = time.time()

    def check_and_trigger_care(self) -> Optional[str]:
        """
        定期的に呼ばれ、必要に応じて声掛けメッセージを返します。
        
        Returns:
            Optional[str]: 発動された声掛けメッセージ（なければNone）
        """
        if not self.is_enabled:
            return None
            
        now = time.time()
        elapsed_since_care = now - self.last_care_time
        elapsed_since_action = now - self.last_user_action_time
        
        # 連続作業（45分以上操作が続いており、前回の声掛けから45分経過）
        if elapsed_since_care >= self.care_interval_seconds:
            msg = None
            pet_state = "happy"
            
            # 時間帯に応じた声掛け
            current_hour = datetime.now().hour
            if current_hour >= 18:
                msg = random.choice(CARE_MESSAGES["evening_care"])
            elif elapsed_since_action >= 90 * 60:
                msg = random.choice(CARE_MESSAGES["break_long"])
            else:
                msg = random.choice(CARE_MESSAGES["break_short"])
                
            self.last_care_time = now
            logger.info(f"プロアクティブ声掛け発動: {msg[:20]}...")
            
            if self.notify_callback and msg:
                self.notify_callback(msg, pet_state)
                
            return msg
            
        return None


# シングルトンインスタンス
_global_care_engine: Optional[ProactiveCareEngine] = None


def get_care_engine(notify_callback: Optional[Callable[[str, str], None]] = None) -> ProactiveCareEngine:
    """シングルトンを取得"""
    global _global_care_engine
    if _global_care_engine is None:
        _global_care_engine = ProactiveCareEngine(notify_callback=notify_callback)
    elif notify_callback:
        _global_care_engine.notify_callback = notify_callback
    return _global_care_engine
