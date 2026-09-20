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
        # Settings Window (Phase 3)
        "ui.settings.tab_general": "一般",
        "ui.settings.tab_llm": "AIモデル設定",
        "ui.settings.tab_mcp": "外部AI・MCP連携",
        "ui.settings.tab_tools": "外部ツール・プラグイン",
        "ui.settings.tab_devices": "接続端末管理",
        "ui.settings.tab_guide": "使い方ガイド",
        "ui.settings.language_card_title": "表示言語 / Language Settings",
        "ui.settings.language_desc": (
            "デスクトップペットの吹き出し、通知メッセージ、およびAI推論の応答言語を切り替えます。\n"
            "Changes the language for pet speech bubbles, notifications, and AI model responses."
        ),
        "ui.settings.mcp_dialog_title": "➕ 新規MCPサーバーの追加",
        "ui.settings.mcp_dialog_header": "➕ 新しいMCPサーバーを追加",
        "ui.settings.mcp_id": "サーバー識別子 (例: google-calendar):",
        "ui.settings.mcp_name": "表示名 (例: Google カレンダー連携):",
        "ui.settings.mcp_name_placeholder": "Google カレンダー連携",
        "ui.settings.mcp_cmd": "実行コマンド (例: npx, uvx, python):",
        "ui.settings.mcp_args": "引数 (スペース区切り, 例: -y @modelcontextprotocol/server-xxx):",
        "ui.settings.mcp_desc": "概要・説明 (省略可):",
        "ui.settings.mcp_desc_placeholder": "Googleカレンダーの予定を参照・登録します",
        "ui.settings.mcp_submit": "✨ MCPサーバーを登録",
        "ui.settings.suggest_dialog_title": "💡 サジェストソース設定",
        "ui.settings.suggest_dialog_header": "💡 インテリジェント・サジェスト設定",
        "ui.settings.suggest_dialog_sub": "画面中央に表示する情報のソースを個別に選べます",
        "ui.settings.suggest_keywords": "関心キーワード (カンマ区切り):",
        "ui.settings.suggest_save": "設定を保存して閉じる",
        "ui.settings.llm_sync_banner": "🌐 接続先APIから最新モデル一覧を一括取得して更新",
        "ui.settings.llm_sync_btn": "⚡ 今すぐ一括同期",
        "ui.settings.llm_sync_note": "※ ドロップダウンは直接キーボード入力で任意の未来モデル・独自モデル名も手打ち指定可能です",
        "ui.settings.gemini_title": "☁ Google Gemini (2026最新・高効率爆速)",
        "ui.settings.claude_title": "🧠 Anthropic Claude 3.5 / 3.7 (高知能推論・エンジニアリング)",
        "ui.settings.openai_title": "⚡ OpenAI GPT-4o / o3-mini (万能・プログラミング強者)",
        "ui.settings.deepseek_title": "🐉 DeepSeek-V3 / R1 (超安価・思考プロセス推論)",
        "ui.settings.local_llm_title": "💻 ローカルLLM (Ollama / Llama.cpp / GGUF - 完全オフライン・秘密厳守)",
        "ui.settings.local_url_label": "ローカルLLM サーバーURL (例: http://localhost:11434):",
        "ui.settings.active_provider": "使用する主軸AIモデル:",
        "ui.settings.model_label": "使用モデル:",

        # Onboarding Tour (Phase 3)
        "tour.settings_menu.title": "🎉 ようこそ！まずは右クリック",
        "tour.settings_menu.text": (
            "こんにちは、ボス！私はネオ秘書くんです。\n"
            "私を**右クリック**すると、メニューが開きます。\n\n"
            "AIモデルの切替・キャラ変更・ポモドーロ・手帳…\n"
            "設定はすべてここから！まずは覗いてみてください。"
        ),
        "tour.mobile_qr.title": "📱 スマホとつなげよう",
        "tour.mobile_qr.text": (
            "**📱 スマホDesk Pet連携** が本アプリの目玉！\n"
            "右クリック →「スマホDesk Pet接続」でQRコードを表示し、\n"
            "スマホのカメラで読むだけ。\n\n"
            "コーディングAIの承認をスマホでワンタップできるようになります！"
        ),
        "tour.chat_notebook.title": "💬 話しかける ＆ 📔 手帳",
        "tour.chat_notebook.text": (
            "下の入力欄に話しかけると、予定登録やTODO作成をします。\n"
            "**「明日9時に資料作成 #仕事 !3」** のように自然に入力OK！\n\n"
            "**📔 手帳**で予定・TODO・習慣を一元管理できます。\n"
            "詳しくは設定画面の「📖 使い方ガイド」へ。それではよろしくお願いします！"
        ),
        "ui.tour.skip": "スキップ",
        "ui.tour.prev": "戻る",
        "ui.tour.next": "次へ",
        "ui.tour.complete": "🎉 完了",
        "ui.tour.msg_skipped": "🎓 ツアーをスキップしました。\nいつでも「使い方を教えて」と言ってくださいね！",
        "ui.tour.msg_first_launch": (
            "🎓 はじめまして、ボス！\n"
            "初めてのご利用ありがとうございます！\n"
            "これから使い方をご案内しますね。\n\n"
            "（すぐにスタートします）"
        ),
        "ui.tour.msg_completed": (
            "🎊 ツアー終了！覚えておいてほしいことは…\n\n"
            "📋 **右クリック** でメニュー\n"
            "📔 **統合手帳** で予定・TODO管理\n"
            "📱 **スマホ連携** で承認ブリッジ\n"
            "🍅 **ポモドーロ** で集中\n\n"
            "また見たいときは「使い方を教えて」と呼びかけてね！"
        ),

        # Daily Briefing Engine (Phase 3)
        "briefing.mode.morning": "☀️ 朝会ブリーフィング",
        "briefing.mode.day": "⛅ 午後ブリーフィング",
        "briefing.mode.evening": "🌙 終礼日報",
        "briefing.mode.night": "🌌 夜間ブリーフィング",
        "briefing.mode.default": "☀️ ブリーフィング",
        "briefing.speech.weather": "現在の{city}の天気は、{weather}、気温は{temp}度です。",
        "briefing.speech.events_count": "本日の予定は{count}件あります。",
        "briefing.speech.events_first": "最初の予定は、{start_time}からの、{title}です。",
        "briefing.speech.events_none": "本日は大きな予定は入っていません。",
        "briefing.speech.tasks_active": "未完了のタスクは{count}件です。最優先は、{title}です。",
        "briefing.speech.tasks_completed": "本日完了したタスクは{count}件です。",
        "briefing.speech.habits_summary": "習慣は{total}件中、{done}件達成しました。",
        "briefing.weather.sunny": "晴れ ☀️",
        "briefing.weather.cloudy": "曇り ☁️",
        "briefing.weather.rainy": "雨 🌧️",
        "briefing.weather.snowy": "雪 ❄️",
        "briefing.weather.thunder": "雷雨 ⚡",
        "briefing.weather.summary": "🌡️ **現在の天気**: {city} は **{weather}**（{temp}）",
        "briefing.events.timeline": "\n📅 **本日の予定タイムライン**:",
        "briefing.events.none": "\n📅 **本日の予定**: 大きな予定はありません（集中作業チャンスです！🎯）",
        "briefing.events.all_day": "終日",
        "briefing.tasks.active": "\n📝 **重要TODO (残り{count}件)**:",
        "briefing.tasks.none": "\n📝 **TODO**: 残タスクはありません！素晴らしいです✨",
        "briefing.tasks.completed_today": "\n🎉 **本日完了したタスク ({count}件)**:",
        "briefing.tasks.evening_none": "\n📝 **タスク状況**: 本日もお疲れ様でした！",
        "briefing.habits.status": "\n🌱 **今日の習慣**: {done}/{total} 達成中 ({rate}%)",
        "briefing.habits.evening_status": "\n🌱 **本日の習慣達成率**: **{done}/{total} 件達成** ({rate}%)",
        "briefing.char.hisho.morning.greeting": "ボス、おはようございます！{name}が本日のブリーフィングをお届けします。",
        "briefing.char.hisho.morning.encouragement": "本日もボスの最高のパートナーとして全力でサポートいたします！✨",
        "briefing.char.hisho.evening.greeting": "ボス、本日も一日大変お疲れ様でした！本日の業務日報です。",
        "briefing.char.hisho.evening.encouragement": "素晴らしい集中力と達成です。今夜はごゆっくりお休みくださいね。✨",
        "briefing.char.retro_dolphin.morning.greeting": "ボス、おはようキュッ！{name}が今日の海路を案内するキュ！",
        "briefing.char.retro_dolphin.morning.encouragement": "今日も一日、無理せずスイスイ進もうキュ！🐬✨",
        "briefing.char.retro_dolphin.evening.greeting": "ボス、今日もお疲れ様キュ〜！本日の航海日誌だキュ！",
        "briefing.char.retro_dolphin.evening.encouragement": "今日完了したタスクと習慣、しっかり記録したキュ！ゆっくり休んでキュ〜！🌊",
        "briefing.char.kyle.morning.greeting": "おっ、ボス！おはようさん。{name}が今日のスケジュールをまとめたぜ。",
        "briefing.char.kyle.morning.encouragement": "肩の力を抜いて、重要なことから片付けていこうぜ！🔥",
        "briefing.char.kyle.evening.greeting": "ボス、一日お疲れさん！今日の成果をまとめたぜ。",
        "briefing.char.kyle.evening.encouragement": "よくやり切ったな！今夜は好きなことして頭を休めてくれよな。",
        "briefing.char.seal.morning.greeting": "もちもち〜！ボス、おはようございます〜！{name}だよ〜！",
        "briefing.char.seal.morning.encouragement": "今日もボスのペースでがんばってね〜！応援してるよ〜！🦭💖",
        "briefing.char.seal.evening.greeting": "ボス〜！今日もお仕事お疲れ様でした〜！もちもち日報だよ〜！",
        "briefing.char.seal.evening.encouragement": "いっぱい頑張ってえらいえらい〜！あったかいお風呂に入ってね〜！🛀",
        "briefing.char.kinoko.morning.greeting": "ボス、朝でござる！{name}、本日の任務書を持参いたした！",
        "briefing.char.kinoko.morning.encouragement": "いざ出陣！健康第一で励むでござる！🍄✨",
        "briefing.char.kinoko.evening.greeting": "ボス、本日の任務完了、誠にお疲れ様でござる！",
        "briefing.char.kinoko.evening.encouragement": "見事な働きぶり！今宵はぐっすり休んで英気を養うでござる！🍵",
        "briefing.char.wombat.morning.greeting": "ボス、おはようございます。{name}が今日の予定をどっしり支えます。",
        "briefing.char.wombat.morning.encouragement": "焦らず着実に、一歩ずつ進めていきましょう。🦫",
        "briefing.char.wombat.evening.greeting": "ボス、一日お疲れ様でした。本日の日報をまとめました。",
        "briefing.char.wombat.evening.encouragement": "積み重ねた努力は確実に力になっています。良き休息を。🌙",
        "briefing.char.common.day.greeting": "ボス、午後の業務もお疲れ様です！午後の進捗ブリーフィングです。",
        "briefing.char.common.day.encouragement": "適度にストレッチやお茶タイムを取りながら進めましょう！☕",
        "briefing.char.common.night.greeting": "ボス、夜遅くまでお疲れ様です。夜間ブリーフィングです。",
        "briefing.char.common.night.encouragement": "無理は禁物ですよ。明日のために、そろそろお布団に入りましょうね。🌌"
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
        # Settings Window (Phase 3)
        "ui.settings.tab_general": "General",
        "ui.settings.tab_llm": "AI Models",
        "ui.settings.tab_mcp": "MCP Integrations",
        "ui.settings.tab_tools": "Tools & Plugins",
        "ui.settings.tab_devices": "Connected Devices",
        "ui.settings.tab_guide": "User Guide",
        "ui.settings.language_card_title": "Language Settings",
        "ui.settings.language_desc": (
            "Changes the language for pet speech bubbles, notifications, and AI model responses."
        ),
        "ui.settings.mcp_dialog_title": "➕ Add New MCP Server",
        "ui.settings.mcp_dialog_header": "➕ Add New MCP Server",
        "ui.settings.mcp_id": "Server Identifier (e.g. google-calendar):",
        "ui.settings.mcp_name": "Display Name (e.g. Google Calendar Integration):",
        "ui.settings.mcp_name_placeholder": "Google Calendar Integration",
        "ui.settings.mcp_cmd": "Command (e.g. npx, uvx, python):",
        "ui.settings.mcp_args": "Arguments (space-separated, e.g. -y @modelcontextprotocol/server-xxx):",
        "ui.settings.mcp_desc": "Description (optional):",
        "ui.settings.mcp_desc_placeholder": "Read and manage Google Calendar events",
        "ui.settings.mcp_submit": "✨ Register MCP Server",
        "ui.settings.suggest_dialog_title": "💡 Suggestion Source Settings",
        "ui.settings.suggest_dialog_header": "💡 Intelligent Suggestion Settings",
        "ui.settings.suggest_dialog_sub": "Select information sources to display on screen",
        "ui.settings.suggest_keywords": "Interest Keywords (comma-separated):",
        "ui.settings.suggest_save": "Save Settings & Close",
        "ui.settings.llm_sync_banner": "🌐 Fetch & Sync Latest Models from APIs",
        "ui.settings.llm_sync_btn": "⚡ Sync All Now",
        "ui.settings.llm_sync_note": "※ You can also type custom model names directly in the dropdown",
        "ui.settings.gemini_title": "☁ Google Gemini (2026 Latest & High Efficiency)",
        "ui.settings.claude_title": "🧠 Anthropic Claude 3.5 / 3.7 (High Intelligence)",
        "ui.settings.openai_title": "⚡ OpenAI GPT-4o / o3-mini (Versatile & Coding)",
        "ui.settings.deepseek_title": "🐉 DeepSeek-V3 / R1 (Cost-effective & Reasoning)",
        "ui.settings.local_llm_title": "💻 Local LLM (Ollama / Llama.cpp / GGUF - Offline & Private)",
        "ui.settings.local_url_label": "Local LLM Server URL (e.g. http://localhost:11434):",
        "ui.settings.active_provider": "Primary AI Model Provider:",
        "ui.settings.model_label": "Model:",

        # Onboarding Tour (Phase 3)
        "tour.settings_menu.title": "🎉 Welcome! First, Right-Click",
        "tour.settings_menu.text": (
            "Hello Boss! I am Neo-Secretary.\n"
            "**Right-click** me to open the menu.\n\n"
            "Switch AI models, change skins, Pomodoro, Notebook...\n"
            "Everything is here! Give it a try."
        ),
        "tour.mobile_qr.title": "📱 Link with Smartphone",
        "tour.mobile_qr.text": (
            "**📱 Mobile Desk Pet Link** is a key feature!\n"
            "Right-click -> 'Mobile Desk Pet' to view the QR code,\n"
            "and scan with your phone.\n\n"
            "Approve coding AI actions with a single tap on your phone!"
        ),
        "tour.chat_notebook.title": "💬 Talk to Secretary ＆ 📔 Notebook",
        "tour.chat_notebook.text": (
            "Type in the bottom bar to create events or tasks.\n"
            "Natural inputs like **'Tomorrow 9am Meeting #work !3'** work great!\n\n"
            "**📔 Notebook** manages events, tasks, and habits in one place.\n"
            "Enjoy using Neo-Secretary!"
        ),
        "ui.tour.skip": "Skip",
        "ui.tour.prev": "Back",
        "ui.tour.next": "Next",
        "ui.tour.complete": "🎉 Complete",
        "ui.tour.msg_skipped": "🎓 Tour skipped.\nYou can ask 'Show guide' anytime!",
        "ui.tour.msg_first_launch": (
            "🎓 Welcome Boss!\n"
            "Thank you for trying Neo-Secretary!\n"
            "Let me guide you through the features.\n\n"
            "(Starting shortly)"
        ),
        "ui.tour.msg_completed": (
            "🎊 Tour complete! Key highlights:\n\n"
            "📋 **Right-click** for Menu\n"
            "📔 **Notebook** for Events & Tasks\n"
            "📱 **Mobile Link** for Approval\n"
            "🍅 **Pomodoro** for Focus\n\n"
            "Ask 'Show guide' anytime to see this again!"
        ),

        # Daily Briefing Engine (Phase 3)
        "briefing.mode.morning": "☀️ Morning Briefing",
        "briefing.mode.day": "⛅ Afternoon Briefing",
        "briefing.mode.evening": "🌙 Evening Report",
        "briefing.mode.night": "🌌 Night Briefing",
        "briefing.mode.default": "☀️ Briefing",
        "briefing.speech.weather": "The current weather in {city} is {weather}, with a temperature of {temp} degrees.",
        "briefing.speech.events_count": "You have {count} events scheduled for today.",
        "briefing.speech.events_first": "The first event is {title} at {start_time}.",
        "briefing.speech.events_none": "There are no major events scheduled for today.",
        "briefing.speech.tasks_active": "You have {count} active tasks remaining. The top priority is {title}.",
        "briefing.speech.tasks_completed": "You completed {count} tasks today.",
        "briefing.speech.habits_summary": "You completed {done} out of {total} habits.",
        "briefing.weather.sunny": "Sunny ☀️",
        "briefing.weather.cloudy": "Cloudy ☁️",
        "briefing.weather.rainy": "Rainy 🌧️",
        "briefing.weather.snowy": "Snowy ❄️",
        "briefing.weather.thunder": "Thunderstorm ⚡",
        "briefing.weather.summary": "🌡️ **Current Weather**: {city} is **{weather}** ({temp})",
        "briefing.events.timeline": "\n📅 **Today's Schedule**:",
        "briefing.events.none": "\n📅 **Today's Schedule**: No major events (A great time for deep work! 🎯)",
        "briefing.events.all_day": "All day",
        "briefing.tasks.active": "\n📝 **Important Tasks ({count} remaining)**:",
        "briefing.tasks.none": "\n📝 **Tasks**: No remaining tasks! Great job✨",
        "briefing.tasks.completed_today": "\n🎉 **Completed Tasks Today ({count})**:",
        "briefing.tasks.evening_none": "\n📝 **Task Status**: Great work today!",
        "briefing.habits.status": "\n🌱 **Today's Habits**: {done}/{total} completed ({rate}%)",
        "briefing.habits.evening_status": "\n🌱 **Habit Completion Today**: **{done}/{total} completed** ({rate}%)",
        "briefing.char.hisho.morning.greeting": "Good morning Boss! {name} here with today's briefing.",
        "briefing.char.hisho.morning.encouragement": "I'll support you fully today as your best partner! ✨",
        "briefing.char.hisho.evening.greeting": "Great work today Boss! Here is your daily report.",
        "briefing.char.hisho.evening.encouragement": "Wonderful focus and achievement today. Have a restful evening. ✨",
        "briefing.char.retro_dolphin.morning.greeting": "Good morning Boss-kyu! {name} will guide today's course-kyu!",
        "briefing.char.retro_dolphin.morning.encouragement": "Let's swim smoothly through today without pushing too hard-kyu! 🐬✨",
        "briefing.char.retro_dolphin.evening.greeting": "Great job today Boss-kyu! Here is today's logbook-kyu!",
        "briefing.char.retro_dolphin.evening.encouragement": "Recorded all finished tasks and habits-kyu! Have a good rest-kyu! 🌊",
        "briefing.char.kyle.morning.greeting": "Hey Boss! Good morning. {name} here with today's schedule.",
        "briefing.char.kyle.morning.encouragement": "Relax and tackle the important stuff first! 🔥",
        "briefing.char.kyle.evening.greeting": "Boss, awesome work today! Here's a summary of today's results.",
        "briefing.char.kyle.evening.encouragement": "You crushed it! Rest up and enjoy your evening.",
        "briefing.char.seal.morning.greeting": "Mochi mochi~! Good morning Boss~! It's {name}~!",
        "briefing.char.seal.morning.encouragement": "Do your best at your own pace today~! Rooting for you~! 🦭💖",
        "briefing.char.seal.evening.greeting": "Boss~! Great job working today~! Here's the mochi report~!",
        "briefing.char.seal.evening.encouragement": "You worked so hard, super proud~! Take a warm bath and relax~! 🛀",
        "briefing.char.kinoko.morning.greeting": "Boss, morning is upon us! {name} brings today's mission brief!",
        "briefing.char.kinoko.morning.encouragement": "To battle! Health comes first, let us strive! 🍄✨",
        "briefing.char.kinoko.evening.greeting": "Boss, mission completed for today. Well done indeed!",
        "briefing.char.kinoko.evening.encouragement": "Splendid work! Sleep well tonight and recharge your energy! 🍵",
        "briefing.char.wombat.morning.greeting": "Good morning Boss. {name} is here to firmly support your schedule.",
        "briefing.char.wombat.morning.encouragement": "No rush, let's move forward steadily step by step. 🦫",
        "briefing.char.wombat.evening.greeting": "Boss, thank you for your hard work today. Here is the daily summary.",
        "briefing.char.wombat.evening.encouragement": "Your stacked efforts grow your strength. Have a good rest. 🌙",
        "briefing.char.common.day.greeting": "Boss, keep up the great work this afternoon! Here's the progress briefing.",
        "briefing.char.common.day.encouragement": "Take stretch breaks and tea time as you work! ☕",
        "briefing.char.common.night.greeting": "Boss, working late! Here is the night briefing.",
        "briefing.char.common.night.encouragement": "Don't overexert yourself. Time to get some rest for tomorrow. 🌌"
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
