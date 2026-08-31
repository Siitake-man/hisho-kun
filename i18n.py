"""
ネオ秘書くん - 多言語対応基盤 (i18n.py)

AI生活変化エンジン要件定義書 (docs/specs/ai_life_engine_multilang_spec.md F4) に基づく
辞書型リソース方式の最小 i18n 基盤。

- `t(key, **params)` ヘルパーでキーから翻訳文を取得する
- 辞書に無い言語/キーは既定言語 (ja) へフォールバックし、最終的にキー自身を返す
- 言語切替は `set_language()` で行う (Phase L3 で設定UI・settingsテーブルと接続予定)
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict

logger = logging.getLogger(__name__)

# 対応言語 (第1段: ja/en / 第2段で zh-CN, ko, es を辞書追加のみで拡張)
SUPPORTED_LANGUAGES: tuple = ("ja", "en")
DEFAULT_LANGUAGE: str = "ja"

# 翻訳辞書 (キーはドメインプレフィックス方式: "<domain>.<key>")
_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "ja": {
        "coach.analysis_title": "📊 今日の生活分析",
        "coach.fallback_analysis": (
            "未完了タスクが{unfinished}件、うち期限切れが{overdue}件です。"
            "習慣達成は今日で{habits_done}/{habits_total}でした。"
        ),
        "coach.fallback_action_rest": "まずは15分だけ、いちばん軽いタスクから着手してみましょう。",
        "coach.fallback_action_overdue": "期限切れタスクを1件、今日の最優先に据え置きましょう。",
        "coach.fallback_action_habit": "未達成の習慣「{habit}」を寝る前に済ませてしまいましょう。",
        "coach.fallback_encouragement": "きちんと観測していますよ、ボス。小さな一歩を一緒に積み上げましょう。",
        "coach.fallback_risk_overdue": "期限切れタスクの滞留",
        "coach.fallback_risk_habit": "習慣達成率の低下",
    },
    "en": {
        "coach.analysis_title": "📊 Today's Life Analysis",
        "coach.fallback_analysis": (
            "You have {unfinished} unfinished tasks, {overdue} of them overdue. "
            "Habit completion today: {habits_done}/{habits_total}."
        ),
        "coach.fallback_action_rest": "Start with just 15 minutes on the lightest task.",
        "coach.fallback_action_overdue": "Pick one overdue task and make it today's top priority.",
        "coach.fallback_action_habit": "Finish the pending habit \"{habit}\" before bedtime.",
        "coach.fallback_encouragement": "I'm watching your progress, Boss. Let's stack small steps together.",
        "coach.fallback_risk_overdue": "Overdue task backlog",
        "coach.fallback_risk_habit": "Declining habit completion",
    },
}

_lang_lock = threading.Lock()
_current_language: str = DEFAULT_LANGUAGE


def set_language(lang: str) -> None:
    """現在言語を切り替える。

    Args:
        lang: 言語コード (例: "ja", "en")。未対応言語は既定言語へフォールバック。
    """
    global _current_language
    normalized = (lang or DEFAULT_LANGUAGE).strip().lower()
    if normalized not in SUPPORTED_LANGUAGES:
        logger.warning("未対応の言語コード '%s' を既定 '%s' へフォールバック", lang, DEFAULT_LANGUAGE)
        normalized = DEFAULT_LANGUAGE
    with _lang_lock:
        _current_language = normalized


def get_language() -> str:
    """現在言語コードを返す。"""
    with _lang_lock:
        return _current_language


def t(key: str, **params: Any) -> str:
    """翻訳キーに対応する文字列を取得する。

    Args:
        key: 翻訳キー (例: "coach.analysis_title")
        **params: 文字列整形用パラメータ ({name} プレースホルダ)

    Returns:
        翻訳済み文字列。辞書に無いキーは既定言語 → キー自身の順にフォールバック。
    """
    with _lang_lock:
        lang = _current_language
    entry = _TRANSLATIONS.get(lang, {}).get(key)
    if entry is None:
        entry = _TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key)
    if params:
        try:
            return entry.format(**params)
        except (KeyError, IndexError):
            logger.warning("翻訳キー '%s' のパラメータ整形に失敗しました: %s", key, params)
    return entry
