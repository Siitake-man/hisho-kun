#!/usr/bin/env python3
"""
ネオ秘書くん - インテリジェント・サジェストエンジン (suggest_engine.py)

ボスの作業状況、直近の予定、高優先度TODO、MentisDB知見、プロアクティブ健康ケアから
「今、ボスが目を通すべきこと／対応が必要なこと」をスマートにサジェストします。
各ソースの個別ON/OFF設定を管理・永続化します。
"""

import os
import json
import time
import datetime
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "suggest_config.json"

DEFAULT_SUGGEST_CONFIG = {
    "sources": {
        "calendar": {
            "name": "📅 予定・会議リマインド",
            "enabled": True,
            "description": "直近の予定や次の会議の開始前リマインド"
        },
        "high_priority_tasks": {
            "name": "🔥 重要TODOタスク",
            "enabled": True,
            "description": "今日期限や高優先度の未完了タスク"
        },
        "proactive_care": {
            "name": "🍵 健康・集中見守り",
            "enabled": True,
            "description": "45分作業時の休憩提案や夕方のリフレッシュ"
        },
        "boss_insights": {
            "name": "🧠 開発知見・マインドセット",
            "enabled": True,
            "description": "MentisDBに蓄積されたボスのルールや天風哲学のTips"
        },
        "news_topics": {
            "name": "🌐 関心ニュース・AIトレンド",
            "enabled": False,
            "description": "登録キーワードやAI最新動向のトピック"
        }
    }
}


class SuggestionEngine:
    """サジェスト情報の集約と配信を行うエンジン"""

    def __init__(self):
        self.config = self._load_config()
        self._cache_suggestions: List[Dict[str, Any]] = []
        self._last_update_time: float = 0.0

    def _load_config(self) -> Dict[str, Any]:
        """設定のロード"""
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"サジェスト設定読み込み失敗: {e}")
        return DEFAULT_SUGGEST_CONFIG.copy()

    def save_config(self, config: Dict[str, Any]) -> None:
        """設定の保存"""
        self.config = config
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info("サジェスト設定を保存しました")
        except Exception as e:
            logger.error(f"サジェスト設定保存失敗: {e}")

    def is_source_enabled(self, source_key: str) -> bool:
        """指定ソースが有効か"""
        sources = self.config.get("sources", {})
        src = sources.get(source_key, {})
        return src.get("enabled", True)

    def toggle_source(self, source_key: str, enabled: bool) -> None:
        """ソースの有効/無効を切り替え"""
        if "sources" not in self.config:
            self.config["sources"] = {}
        if source_key in self.config["sources"]:
            self.config["sources"][source_key]["enabled"] = enabled
            self.save_config(self.config)

    def generate_suggestions(self) -> List[Dict[str, Any]]:
        """現在の各データソースからサジェストカード一覧を動的生成"""
        suggestions: List[Dict[str, Any]] = []
        import database

        now_dt = datetime.datetime.now()
        now_ts = int(time.time() * 1000)

        # 1. 予定リマインド (Calendar)
        if self.is_source_enabled("calendar"):
            try:
                events = database.get_upcoming_events(days=1)
                for ev in events[:2]:
                    st = datetime.datetime.fromtimestamp(ev.start_time / 1000.0)
                    time_str = st.strftime("%H:%M")
                    diff_mins = int((ev.start_time - now_ts) / (1000 * 60))
                    
                    if 0 <= diff_mins <= 60:
                        urgency = f"【あと {diff_mins}分】"
                    elif diff_mins < 0:
                        urgency = "【進行中】"
                    else:
                        urgency = f"【本日 {time_str}〜】"

                    suggestions.append({
                        "id": f"event_{ev.id}",
                        "source": "calendar",
                        "icon": "📅",
                        "title": f"{urgency} {ev.title}",
                        "description": ev.description or "予定の詳細はありません",
                        "tag": "カレンダー"
                    })
            except Exception as e:
                logger.error(f"予定サジェスト生成エラー: {e}")

        # 2. 重要TODO (High Priority Tasks)
        if self.is_source_enabled("high_priority_tasks"):
            try:
                tasks = database.get_tasks(status="todo", limit=10)
                high_tasks = [t for t in tasks if t.priority == 3 or str(t.priority).lower() == "high"] or tasks[:2]
                for t in high_tasks[:2]:
                    p_badge = "🔥 高優先度" if (t.priority == 3 or str(t.priority).lower() == "high") else "⚡ 通常タスク"
                    suggestions.append({
                        "id": f"task_{t.id}",
                        "source": "tasks",
                        "icon": "📋",
                        "title": f"{p_badge}: {t.title}",
                        "description": t.description or "ワンタップで完了できます",
                        "tag": "TODO手帳"
                    })
            except Exception as e:
                logger.error(f"TODOサジェスト生成エラー: {e}")

        # 3. ボスの知見・マインドセット (MentisDB Insights)
        if self.is_source_enabled("boss_insights"):
            try:
                insights = database.get_user_insights(min_importance=2, limit=5)
                if insights:
                    import random
                    ins = random.choice(insights)
                    suggestions.append({
                        "id": f"insight_{ins.id}",
                        "source": "insights",
                        "icon": "🧠",
                        "title": f"【ボスの知見・{ins.category}】",
                        "description": ins.content,
                        "tag": "MentisDB"
                    })
            except Exception as e:
                logger.error(f"知見サジェスト生成エラー: {e}")

        # 4. 健康・見守り (Care)
        if self.is_source_enabled("proactive_care"):
            hour = now_dt.hour
            if hour >= 22 or hour < 5:
                care_msg = "ボス、遅くまでお疲れさまです。生命の最適利用のため、十分な睡眠も大切ですよ🌙"
            elif 11 <= hour <= 13:
                care_msg = "もうすぐお昼時ですね！美味しいものを食べてエネルギーを補給してくださいね🍱"
            elif 17 <= hour <= 19:
                care_msg = "夕方になりました。肩を回してストレッチしませんか？🍵"
            else:
                care_msg = "集中が続いています。深呼吸して水分補給をしてくださいね✨"

            suggestions.append({
                "id": "care_current",
                "source": "care",
                "icon": "🍵",
                "title": "【秘書くんの気配り】",
                "description": care_msg,
                "tag": "健康見守り"
            })

        # デフォルトフォールバック
        if not suggestions:
            suggestions.append({
                "id": "default_msg",
                "source": "general",
                "icon": "✨",
                "title": "ボス、今日も素晴らしい一日にしましょう！",
                "description": "下のメニューから手帳や付箋を開けます。",
                "tag": "ネオ秘書くん"
            })

        self._cache_suggestions = suggestions
        self._last_update_time = time.time()
        return suggestions


# シングルトンインスタンス
_engine_instance: Optional[SuggestionEngine] = None

def get_suggestion_engine() -> SuggestionEngine:
    """シングルトンインスタンスの取得"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = SuggestionEngine()
    return _engine_instance
