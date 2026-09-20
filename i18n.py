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

# LLMプロンプトに渡す正式言語名 (言語コード "ja" は LLM にとって曖昧なため、
# ここで正式名へマッピングする。DeepSeek 等の中国系モデルが曖昧な指示で
# 中国語を出力する事故を防ぐ (2026-09-16 ボス報告)。
LANGUAGE_NAMES: Dict[str, str] = {
    "ja": "日本語",
    "en": "English",
}
# 中国語等を明示禁止する追記文 (DeepSeek 等の既定言語対策・現在言語に応じて動的制御)
_NO_CHINESE_INSTRUCTION_JA: str = (
    "IMPORTANT: Write ALL text fields in 日本語. "
    "Do NOT use Chinese (简体中文), English, or any other language."
)
_NO_CHINESE_INSTRUCTION_EN: str = (
    "IMPORTANT: Write ALL text fields in English. "
    "Do NOT use Chinese (简体中文), Japanese, or any other language."
)

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
        # UI ドメイン辞書 (Sprint Global)
        "ui.settings.title": "⚙️ ネオ秘書くん 設定",
        "ui.settings.general": "一般",
        "ui.settings.language": "表示言語 / Language",
        "ui.settings.save": "保存して閉じる",
        "ui.pet.working": "お仕事中",
        "ui.pet.sleeping": "睡眠中",
        # システムトレイ
        "ui.tray.show": "🖥️ ペットを画面に呼び出す",
        "ui.tray.hide": "🙈 ペットを隠す (最小化)",
        "ui.tray.sticky": "📌 デスクトップ付箋 (表示/非表示)",
        "ui.tray.settings": "⚙️ 設定を開く",
        "ui.tray.calendar": "📅 手帳 / カレンダー",
        "ui.tray.qr": "📱 スマホ接続 (QRコード)",
        "ui.tray.exit": "❌ ネオ秘書くんを終了",
        "ui.tray.tooltip": "ネオ秘書くん",
        # メインウィンドウ & 右クリックメニュー
        "ui.gui.title": "ネオ秘書くん",
        "ui.gui.header_name": "🤖 ネオ秘書くん",
        "ui.gui.header_cal": "📔 手帳",
        "ui.gui.initial_greeting": "おはようございます！\n本日のご予定はいかがなさいますか？",
        "ui.gui.open_link": "🌐 リンクをブラウザで開く",
        "ui.gui.input_placeholder": "秘書くんに指示する...",
        "ui.gui.pomo_focus": "🍅 集中",
        "ui.gui.pomo_break": "☕ 休憩",
        "ui.gui.fsm_coding": "🤖 [{agent_name}] 猛烈にコード書き込み中！🔥",
        "ui.gui.fsm_thinking": "🤔 [{agent_name}] 作戦を考えています…",
        "ui.gui.fsm_waiting_approval": "🚨 [{agent_name}] ご主人様の承認をお待ちしています！",
        "ui.gui.fsm_success": "✨ [{agent_name}] タスク完了！お疲れ様でした！🎉",
        "ui.menu.briefing_morning": "☀️ 今日の朝会ブリーフィング",
        "ui.menu.briefing_evening": "🌙 本日の終礼日報まとめ",
        "ui.menu.calendar": "📔 統合手帳（予定・TODO・知見）",
        "ui.menu.sticky": "📌 新しい付箋を貼る",
        "ui.menu.qr": "📱 スマホDesk Pet接続 (QRコード)",
        "ui.menu.auto_min": "スマホ接続時にPCペットを自動最小化",
        "ui.menu.pomo_start": "🍅 ポモドーロ集中開始 (25分)",
        "ui.menu.pomo_stop": "⏹ ポモドーロタイマー停止",
        "ui.menu.llm_switch": "🧠 LLMモデル切り替え",
        "ui.menu.llm_add": "⚙ 新しいLLMを追加・設定...",
        "ui.menu.skin_change": "🎭 キャラクタースキン変更",
        "ui.menu.wandering": "🚶 徘徊モード（デスクトップ散歩）",
        "ui.menu.tour": "🎓 使い方ツアー",
        "ui.menu.suggest": "💡 サジェストソース設定",
        "ui.menu.settings": "⚙ API・MCP設定",
        "ui.menu.exit": "❌ 終了",
        # サークルメニュー (Radial Menu)
        "ui.radial.cal_title": "📔 統合手帳（予定・TODO・知見）",
        "ui.radial.cal_desc": "カレンダー・TODOタスク・知見ノートを開きます。",
        "ui.radial.pomo_title": "🍅 ポモドーロ集中タイマー",
        "ui.radial.pomo_desc": "25分間の集中タイマーを開始/停止します。",
        "ui.radial.skin_title": "🎨 キャラクタースキン着せ替え",
        "ui.radial.skin_desc": "秘書くん・キノコ君・アザラシ・ウォンバットを切り替えます。",
        "ui.radial.mobile_title": "📱 スマホDesk Pet接続",
        "ui.radial.mobile_desc": "スマホ画面と連携するQRコードを表示します。",
        "ui.radial.suggest_title": "💡 サジェストソース設定",
        "ui.radial.suggest_desc": "予定やTODOの自動サジェスト項目を設定します。",
        "ui.radial.settings_title": "⚙ アプリ・LLM設定",
        "ui.radial.settings_desc": "AIモデルやAPIキー、連携設定を開きます。",
        "ui.radial.tickle": "えへへ、くすぐったいです！🥰\nボス、呼び出したい機能を選んでくださいね！",
        # 統合手帳 (Calendar Window)
        "ui.cal.title": "ネオ秘書くん - 統合手帳 (Notebook)",
        "ui.cal.header": "📔 秘書くんの統合手帳",
        "ui.cal.tab_events": "📅 予定",
        "ui.cal.tab_tasks": "📋 TODO",
        "ui.cal.tab_habits": "🌱 習慣 ＆ 草",
        "ui.cal.tab_insights": "🧠 ボスのトリセツ",
        "ui.cal.view_month": "🗓️ 月間",
        "ui.cal.view_week": "📅 週間",
        "ui.cal.view_day": "☀️ 日間",
        "ui.cal.today": "今日",
        "ui.cal.add_task": "追加",
        "ui.cal.all_tasks": "📥 すべて",
        "ui.cal.unclassified": "🗂 未分類",
        "ui.cal.lists": "リスト",
        "ui.cal.manage_lists": "⚙ リスト管理",
        "ui.cal.streak": "ストリーク",
        "ui.cal.done": "✔ 達成！",
        "ui.cal.not_done": "未完了",
        # QR & 端末承認ダイアログ
        "ui.qr.title": "📱 スマホDesk Pet ＆ 承認コクピット接続",
        "ui.qr.header": "📱 スマホを机上のペット端末にする",
        "ui.qr.desc": "カメラでQRコードをかざすだけで、スマホが承認コクピットになります！",
        "ui.qr.target": "接続先:",
        "ui.qr.waiting": "🔴 スマホ未接続（アクセス待機中...）",
        "ui.qr.show_pc": "🖥️ PCペット表示",
        "ui.qr.test_call": "📲 呼出テスト",
        "ui.qr.auto_hide": "📱 スマホ接続時にPCペットを自動非表示にする（画面占有ゼロ化）",
        "ui.qr.guide_title": "🔰 初めての接続ガイド（Wi-Fi・Bluetooth）",
        "ui.dev.req_title": "📱 端末接続承認要請 - ネオ秘書くん",
        "ui.dev.new_req": "📱 新しい端末からの接続要求",
        "ui.dev.confirm": "Desk Pet への接続を許可しますか？\n心当たりのない接続要求は [拒否] してください。",
        "ui.dev.name": "端末名:",
        "ui.dev.ip": "接続元 IP:",
        "ui.dev.audit": "安全審査:",
        "ui.dev.auto_deny": "自動拒否まで: {sec} 秒",
        "ui.dev.btn_deny": "🛑 拒否 (Esc)",
        "ui.dev.btn_allow": "✅ 許可 (Enter)",
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
        # UI domain dictionary (Sprint Global)
        "ui.settings.title": "⚙️ Neo-Secretary Settings",
        "ui.settings.general": "General",
        "ui.settings.language": "Language",
        "ui.settings.save": "Save & Close",
        "ui.pet.working": "Working",
        "ui.pet.sleeping": "Sleeping",
        # System Tray
        "ui.tray.show": "🖥️ Summon Pet to Screen",
        "ui.tray.hide": "🙈 Hide Pet (Minimize)",
        "ui.tray.sticky": "📌 Desktop Sticky Note",
        "ui.tray.settings": "⚙️ Open Settings",
        "ui.tray.calendar": "📅 Notebook / Calendar",
        "ui.tray.qr": "📱 Mobile Desk Pet (QR)",
        "ui.tray.exit": "❌ Exit Neo-Secretary",
        "ui.tray.tooltip": "Neo-Secretary",
        # Main Window & Context Menu
        "ui.gui.title": "Neo-Secretary",
        "ui.gui.header_name": "🤖 Neo-Secretary",
        "ui.gui.header_cal": "📔 Notebook",
        "ui.gui.initial_greeting": "Good morning!\nHow may I assist your schedule today?",
        "ui.gui.open_link": "🌐 Open Link in Browser",
        "ui.gui.input_placeholder": "Instruct your Secretary...",
        "ui.gui.pomo_focus": "🍅 Focus",
        "ui.gui.pomo_break": "☕ Break",
        "ui.gui.fsm_coding": "🤖 [{agent_name}] Writing code furiously! 🔥",
        "ui.gui.fsm_thinking": "🤔 [{agent_name}] Planning strategy…",
        "ui.gui.fsm_waiting_approval": "🚨 [{agent_name}] Awaiting Boss approval!",
        "ui.gui.fsm_success": "✨ [{agent_name}] Task complete! Great job! 🎉",
        "ui.menu.briefing_morning": "☀️ Morning Briefing",
        "ui.menu.briefing_evening": "🌙 Evening Report Summary",
        "ui.menu.calendar": "📔 Integrated Notebook (Events/Tasks/Vault)",
        "ui.menu.sticky": "📌 Add Sticky Note",
        "ui.menu.qr": "📱 Mobile Desk Pet (QR Code)",
        "ui.menu.auto_min": "Auto-minimize PC pet on mobile connect",
        "ui.menu.pomo_start": "🍅 Start Pomodoro Focus (25m)",
        "ui.menu.pomo_stop": "⏹ Stop Pomodoro Timer",
        "ui.menu.llm_switch": "🧠 Switch LLM Model",
        "ui.menu.llm_add": "⚙ Add / Configure LLM...",
        "ui.menu.skin_change": "🎭 Change Character Skin",
        "ui.menu.wandering": "🚶 Wandering Mode (Desktop Walk)",
        "ui.menu.tour": "🎓 Feature Tour",
        "ui.menu.suggest": "💡 Suggestion Settings",
        "ui.menu.settings": "⚙ API & MCP Settings",
        "ui.menu.exit": "❌ Exit",
        # Radial Menu
        "ui.radial.cal_title": "📔 Integrated Notebook",
        "ui.radial.cal_desc": "Open Calendar, Tasks, and Insights.",
        "ui.radial.pomo_title": "🍅 Pomodoro Timer",
        "ui.radial.pomo_desc": "Start/stop 25-min focus session.",
        "ui.radial.skin_title": "🎨 Character Skins",
        "ui.radial.skin_desc": "Switch between Secretary, Kinoko, Seal, and Wombat.",
        "ui.radial.mobile_title": "📱 Mobile Desk Pet",
        "ui.radial.mobile_desc": "Display QR code to link mobile device.",
        "ui.radial.suggest_title": "💡 Suggestion Settings",
        "ui.radial.suggest_desc": "Configure automated suggestion sources.",
        "ui.radial.settings_title": "⚙ App & LLM Settings",
        "ui.radial.settings_desc": "Open AI model, API key, and integration settings.",
        "ui.radial.tickle": "Hehe, that tickles! 🥰\nBoss, please choose a feature!",
        # Integrated Notebook (Calendar Window)
        "ui.cal.title": "Neo-Secretary - Integrated Notebook",
        "ui.cal.header": "📔 Secretary's Integrated Notebook",
        "ui.cal.tab_events": "📅 Events",
        "ui.cal.tab_tasks": "📋 Tasks",
        "ui.cal.tab_habits": "🌱 Habits & Streak",
        "ui.cal.tab_insights": "🧠 Boss Insights",
        "ui.cal.view_month": "🗓️ Month",
        "ui.cal.view_week": "📅 Week",
        "ui.cal.view_day": "☀️ Day",
        "ui.cal.today": "Today",
        "ui.cal.add_task": "Add",
        "ui.cal.all_tasks": "📥 All",
        "ui.cal.unclassified": "🗂 Unsorted",
        "ui.cal.lists": "Lists",
        "ui.cal.manage_lists": "⚙ Manage Lists",
        "ui.cal.streak": "Streak",
        "ui.cal.done": "✔ Done!",
        "ui.cal.not_done": "Pending",
        # QR & Device Approval Dialog
        "ui.qr.title": "📱 Mobile Desk Pet & Approval Cockpit",
        "ui.qr.header": "📱 Turn your phone into a Desk Pet",
        "ui.qr.desc": "Scan the QR code with your camera to link your smartphone!",
        "ui.qr.target": "Connection Target:",
        "ui.qr.waiting": "🔴 Mobile disconnected (Awaiting connection...)",
        "ui.qr.show_pc": "🖥️ Show PC Pet",
        "ui.qr.test_call": "📲 Test Call",
        "ui.qr.auto_hide": "📱 Auto-hide PC pet on mobile connect",
        "ui.qr.guide_title": "🔰 Setup Guide (Wi-Fi / Bluetooth)",
        "ui.dev.req_title": "📱 Device Connection Request - Neo-Secretary",
        "ui.dev.new_req": "📱 Connection Request from New Device",
        "ui.dev.confirm": "Allow connection to Desk Pet?\nReject if you do not recognize this device.",
        "ui.dev.name": "Device Name:",
        "ui.dev.ip": "Origin IP:",
        "ui.dev.audit": "Safety Audit:",
        "ui.dev.auto_deny": "Auto-reject in: {sec}s",
        "ui.dev.btn_deny": "🛑 Reject (Esc)",
        "ui.dev.btn_allow": "✅ Allow (Enter)",
    },
}

_lang_lock = threading.Lock()
_current_language: str = DEFAULT_LANGUAGE
_lang_listeners: list = []


def subscribe_language_change(callback) -> None:
    """言語切り替えイベントのリスナーを登録する。"""
    with _lang_lock:
        if callback not in _lang_listeners:
            _lang_listeners.append(callback)


def unsubscribe_language_change(callback) -> None:
    """言語切り替えイベントのリスナーを解除する。"""
    with _lang_lock:
        if callback in _lang_listeners:
            _lang_listeners.remove(callback)


def set_language(lang: str) -> None:
    """現在言語を切り替え、登録済みリスナーに通知する。

    Args:
        lang: 言語コード (例: "ja", "en")。未対応言語は既定言語へフォールバック。
    """
    global _current_language
    if not isinstance(lang, str):
        lang = str(lang or DEFAULT_LANGUAGE)
    normalized = lang.strip().lower()
    if normalized not in SUPPORTED_LANGUAGES:
        logger.warning("未対応の言語コード '%s' を既定 '%s' へフォールバック", lang, DEFAULT_LANGUAGE)
        normalized = DEFAULT_LANGUAGE
    with _lang_lock:
        _current_language = normalized
        listeners = list(_lang_listeners)
    
    for cb in listeners:
        try:
            cb(normalized)
        except Exception as e:
            logger.warning("言語変更リスナーの実行中に例外が発生しました: %s", e)


def get_language() -> str:
    """現在言語コードを返す。"""
    with _lang_lock:
        return _current_language


def get_language_name() -> str:
    """現在言語の正式名を返す (LLMプロンプト用)。

    Returns:
        str: 例 "日本語"。未対応言語コードは既定の日本語を返す。
    """
    return LANGUAGE_NAMES.get(get_language(), LANGUAGE_NAMES[DEFAULT_LANGUAGE])


def get_no_chinese_instruction() -> str:
    """中国語禁止・出力言語強制の明示文を返す (現在言語コードに応じて動的に制御)。

    Returns:
        str: LLMプロンプトに追記する禁止指示文。
             - en: English指定 ＆ 簡体字・日本語等の使用禁止
             - ja: 日本語指定 ＆ 簡体字・英語等の使用禁止
    """
    lang = get_language()
    if lang == "en":
        return _NO_CHINESE_INSTRUCTION_EN
    return _NO_CHINESE_INSTRUCTION_JA


def get_prompt_language_instruction() -> str:
    """言語正式名と禁止指示を一体化したLLMプロンプト指示文を返す。

    Returns:
        str: 正式言語名（例: "日本語" または "English"）と禁止ガードが一体化した指示文。
    """
    lang_name = get_language_name()
    guard = get_no_chinese_instruction()
    return f"Response Language: {lang_name}\n{guard}"


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
        except (KeyError, IndexError, ValueError):
            logger.warning("翻訳キー '%s' のパラメータ整形に失敗しました: %s", key, params)
    return entry
