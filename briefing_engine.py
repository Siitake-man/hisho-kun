"""
ネオ秘書くん - 朝会/終礼ブリーフィングエンジン (briefing_engine.py)

ボスの可処分時間（隙間時間の5分）を最大活用するための日次相棒UX（Phase L3）。
朝のスケジュール・重要TODO・天気・習慣のワンタップ要約（朝会）と、
夜の達成タスク・習慣ヒートマップ・ねぎらいの振り返り（終礼日報）を生成する Deep Module。
"""

import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, date
from typing import Dict, Any, List, Optional

import database
import weather_tools
from character_manager import get_character_manager

logger = logging.getLogger(__name__)


@dataclass
class BriefingReport:
    """ブリーフィングレポート構造体 (Deep Module Interface)"""
    mode: str                         # 'morning' | 'day' | 'evening' | 'night'
    mode_label: str                   # 表示用ラベル（例: '☀️ 朝会ブリーフィング'）
    timestamp: float                  # 生成UNIX秒
    date_str: str                     # 'YYYY年MM月DD日 (曜日)'
    character_id: str                 # 発話キャラクターID
    character_name: str               # キャラクター名
    greeting: str                     # 冒頭の挨拶
    speech_text: str                  # Web Speech API (TTS) 読み上げ用プレーンテキスト
    formatted_markdown: str           # PWA/GUI表示用リッチテキスト
    weather_summary: Dict[str, Any]   # 天気・気温情報
    events_today: List[Dict[str, Any]] # 今日の予定リスト
    active_tasks: List[Dict[str, Any]] # 未完了TODOリスト
    completed_tasks_today: List[Dict[str, Any]] # 今日完了したタスクリスト
    habits_summary: Dict[str, Any]    # 習慣の達成状況 { total, done, rate_percent }
    encouragement: str                # キャラクターからのねぎらい・応援メッセージ

    def to_dict(self) -> Dict[str, Any]:
        """JSONシリアライズ用の辞書へ変換"""
        return asdict(self)


def get_current_briefing_mode(hour: Optional[int] = None) -> str:
    """現在時刻に応じたブリーフィングモードを返す。"""
    if hour is None:
        hour = datetime.now().hour
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 18:
        return "day"
    elif 18 <= hour < 24:
        return "evening"
    else:
        return "night"


def _format_date_japanese(dt: datetime) -> str:
    """日付を『YYYY年MM月DD日 (曜日)』形式にフォーマット"""
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    weekday_str = weekdays[dt.weekday()]
    return f"{dt.year}年{dt.month}月{dt.day}日 ({weekday_str})"


def _get_character_lines(char_id: str, mode: str, count_events: int, count_tasks: int, count_habits_done: int) -> Dict[str, str]:
    """キャラクターの個性・口調に合わせた台詞を生成"""
    char_mgr = get_character_manager()
    char_info = char_mgr.get_current_character()
    name = char_info.get("name", "秘書くん")
    emoji = char_info.get("emoji", "🤖")

    if mode == "morning":
        if char_id == "retro_dolphin":
            greeting = f"ボス、おはようキュッ！{name}が今日の海路を案内するキュ！"
            encouragement = "今日も一日、無理せずスイスイ進もうキュ！🐬✨"
        elif char_id == "kyle":
            greeting = f"おっ、ボス！おはようさん。{name}が今日のスケジュールをまとめたぜ。"
            encouragement = "肩の力を抜いて、重要なことから片付けていこうぜ！🔥"
        elif char_id == "seal":
            greeting = f"もちもち〜！ボス、おはようございます〜！{name}だよ〜！"
            encouragement = "今日もボスのペースでがんばってね〜！応援してるよ〜！🦭💖"
        elif char_id == "kinoko":
            greeting = f"ボス、朝でござる！{name}、本日の任務書を持参いたした！"
            encouragement = "いざ出陣！健康第一で励むでござる！🍄✨"
        elif char_id == "wombat":
            greeting = f"ボス、おはようございます。{name}が今日の予定をどっしり支えます。"
            encouragement = "焦らず着実に、一歩ずつ進めていきましょう。🦫"
        else: # hisho
            greeting = f"ボス、おはようございます！{name}が本日のブリーフィングをお届けします。"
            encouragement = "本日もボスの最高のパートナーとして全力でサポートいたします！✨"

    elif mode == "evening":
        if char_id == "retro_dolphin":
            greeting = f"ボス、今日もお疲れ様キュ〜！本日の航海日誌だキュ！"
            encouragement = f"今日完了したタスクと習慣、しっかり記録したキュ！ゆっくり休んでキュ〜！🌊"
        elif char_id == "kyle":
            greeting = f"ボス、一日お疲れさん！今日の成果をまとめたぜ。"
            encouragement = f"よくやり切ったな！今夜は好きなことして頭を休めてくれよな。"
        elif char_id == "seal":
            greeting = f"ボス〜！今日もお仕事お疲れ様でした〜！もちもち日報だよ〜！"
            encouragement = f"いっぱい頑張ってえらいえらい〜！あったかいお風呂に入ってね〜！🛀"
        elif char_id == "kinoko":
            greeting = f"ボス、本日の任務完了、誠にお疲れ様でござる！"
            encouragement = f"見事な働きぶり！今宵はぐっすり休んで英気を養うでござる！🍵"
        elif char_id == "wombat":
            greeting = f"ボス、一日お疲れ様でした。本日の日報をまとめました。"
            encouragement = f"積み重ねた努力は確実に力になっています。良き休息を。🌙"
        else: # hisho
            greeting = f"ボス、本日も一日大変お疲れ様でした！本日の業務日報です。"
            encouragement = f"素晴らしい集中力と達成です。今夜はごゆっくりお休みくださいね。✨"

    elif mode == "day":
        greeting = f"ボス、午後の業務もお疲れ様です！午後の進捗ブリーフィングです。"
        encouragement = "適度にストレッチやお茶タイムを取りながら進めましょう！☕"
    else: # night
        greeting = f"ボス、夜遅くまでお疲れ様です。夜間ブリーフィングです。"
        encouragement = "無理は禁物ですよ。明日のために、そろそろお布団に入りましょうね。🌌"

    return {"greeting": greeting, "encouragement": encouragement, "name": name, "emoji": emoji}


def _build_habit_summary(habits_raw: List[Any]) -> Dict[str, Any]:
    """習慣リスト (HabitWithStatus モデル) から朝会/終礼用の達成サマリーを組み立てる。

    2026-09-01 P2①第二段で新設。旧実装は存在しない is_done キーを
    h.get() で参照していたため達成数が常に 0 になる潜在バグがあった
    (Pydantic モデル化により属性アクセスへ統一し、型チェック対象にする)。

    Args:
        habits_raw: database.get_habits_with_status() の戻り値。

    Returns:
        total / done / rate_percent / list (JSON送信用に dict 化) を含むサマリー。
    """
    total = len(habits_raw)
    done = sum(1 for h in habits_raw if h.completed_today)
    rate = int((done / total) * 100) if total > 0 else 0
    return {
        "total": total,
        "done": done,
        "rate_percent": rate,
        "list": [h.model_dump() for h in habits_raw],
    }


def generate_briefing(force_mode: Optional[str] = None) -> BriefingReport:
    """
    現在の時間帯と実データから日次ブリーフィングレポートを生成する（Deep Module）。
    
    Args:
        force_mode: 'morning' | 'day' | 'evening' | 'night' の強制指定（テスト・手動起動用）
        
    Returns:
        BriefingReport: 構造化されたブリーフィングデータ
    """
    now = datetime.now()
    mode = force_mode if force_mode in ("morning", "day", "evening", "night") else get_current_briefing_mode(now.hour)

    mode_labels = {
        "morning": "☀️ 朝会ブリーフィング",
        "day": "⛅ 午後ブリーフィング",
        "evening": "🌙 終礼日報",
        "night": "🌌 夜間ブリーフィング",
    }
    mode_label = mode_labels.get(mode, "☀️ ブリーフィング")

    # 1. 実データの収集 (Seam統合)
    # 1.1 天気
    weather_info = weather_tools.get_weather()
    weather_desc = {
        "sunny": "晴れ ☀️", "cloudy": "曇り ☁️", "rainy": "雨 🌧️",
        "snowy": "雪 ❄️", "thunder": "雷雨 ⚡"
    }.get(weather_info.get("weather", "sunny"), "晴れ ☀️")
    temp_str = f"{weather_info.get('temperature', 20.0):.1f}°C"
    city_str = weather_info.get("city", "東京")

    # 1.2 今日の予定 (Google / iCal / Local DB)
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0)
    today_end = datetime(now.year, now.month, now.day, 23, 59, 59)
    start_ms = int(today_start.timestamp() * 1000)
    end_ms = int(today_end.timestamp() * 1000)
    
    events_today = []
    try:
        raw_events = database.get_events_between(start_ms, end_ms)
        for ev in raw_events:
            # start_time のパース（intミリ秒 or str）
            st_str = ""
            et_str = ""
            if isinstance(ev.start_time, (int, float)):
                st_dt = datetime.fromtimestamp(ev.start_time / 1000)
                st_str = st_dt.strftime("%H:%M")
            elif isinstance(ev.start_time, str) and len(ev.start_time) >= 16:
                st_str = ev.start_time[11:16]
                
            if isinstance(ev.end_time, (int, float)):
                et_dt = datetime.fromtimestamp(ev.end_time / 1000)
                et_str = et_dt.strftime("%H:%M")
            elif isinstance(ev.end_time, str) and len(ev.end_time) >= 16:
                et_str = ev.end_time[11:16]

            events_today.append({
                "id": ev.id,
                "title": ev.title,
                "start_time": st_str,
                "end_time": et_str,
                "location": getattr(ev, "location", "") or "",
                "description": ev.description or ""
            })
    except Exception as e:
        logger.warning(f"予定データ取得スキップ: {e}")
        events_today = []

    # 1.3 未完了TODO & 今日の完了TODO
    active_tasks = []
    try:
        active_tasks_raw = database.get_tasks(status=None) # todo, in_progress
        for t in active_tasks_raw:
            active_tasks.append({
                "id": t.id,
                "title": t.title,
                "priority": getattr(t, "priority", 1),
                "due_date": str(t.due_date) if getattr(t, "due_date", None) else ""
            })
    except Exception as e:
        logger.warning(f"タスクデータ取得スキップ: {e}")
        active_tasks = []

    # 完了タスク（終礼用）
    completed_tasks_today = []
    try:
        comp_tasks_raw = database.get_tasks(status="completed", limit=10)
        for t in comp_tasks_raw:
            completed_tasks_today.append({
                "id": t.id,
                "title": t.title
            })
    except Exception as e:
        logger.warning(f"完了タスク取得スキップ: {e}")
        completed_tasks_today = []

    # 1.4 習慣達成状況
    try:
        habits_raw = database.get_habits_with_status()
        habits_summary = _build_habit_summary(habits_raw)
    except Exception as e:
        logger.debug(f"習慣データ取得スキップ: {e}")
        habits_summary = {"total": 0, "done": 0, "rate_percent": 0, "list": []}

    # 2. キャラクター台詞の生成
    char_mgr = get_character_manager()
    char_info = char_mgr.get_current_character()
    char_id = char_info.get("id", "hisho")
    char_lines = _get_character_lines(
        char_id=char_id,
        mode=mode,
        count_events=len(events_today),
        count_tasks=len(active_tasks),
        count_habits_done=habits_summary["done"]
    )

    # 3. 表示用リッチマークダウンの構築
    date_jp = _format_date_japanese(now)
    lines = []
    lines.append(f"### {char_lines['emoji']} {mode_label} ({date_jp})")
    lines.append(f"{char_lines['greeting']}\n")

    # 天気サマリ
    lines.append(f"🌡️ **現在の天気**: {city_str} は **{weather_desc}**（{temp_str}）")

    if mode in ("morning", "day"):
        # 朝会・日中: 予定と未完了タスク
        if events_today:
            lines.append("\n📅 **本日の予定タイムライン**:")
            for ev in events_today[:4]:
                time_range = f"{ev['start_time']}〜{ev['end_time']}" if ev['start_time'] else "終日"
                lines.append(f"- **{time_range}**: {ev['title']}")
        else:
            lines.append("\n📅 **本日の予定**: 大きな予定はありません（集中作業チャンスです！🎯）")

        if active_tasks:
            lines.append(f"\n📝 **重要TODO (残り{len(active_tasks)}件)**:")
            for t in active_tasks[:3]:
                lines.append(f"- ⏳ {t['title']}")
        else:
            lines.append("\n📝 **TODO**: 残タスクはありません！素晴らしいです✨")

        if habits_summary["total"] > 0:
            lines.append(f"\n🌱 **今日の習慣**: {habits_summary['done']}/{habits_summary['total']} 達成中 ({habits_summary['rate_percent']}%)")

    else:
        # 終礼・夜間: 成果の振り返りとねぎらい
        if completed_tasks_today:
            lines.append(f"\n🎉 **本日完了したタスク ({len(completed_tasks_today)}件)**:")
            for t in completed_tasks_today[:4]:
                lines.append(f"- ✅ {t['title']}")
        else:
            lines.append("\n📝 **タスク状況**: 本日もお疲れ様でした！")

        if habits_summary["total"] > 0:
            lines.append(f"\n🌱 **本日の習慣達成率**: **{habits_summary['done']}/{habits_summary['total']} 件達成** ({habits_summary['rate_percent']}%)")

    lines.append(f"\n{char_lines['encouragement']}")
    formatted_markdown = "\n".join(lines)

    # 4. 音声TTS用プレーンテキストの構築（耳で聴いてわかりやすい自然言語）
    speech_parts = []
    speech_parts.append(f"{char_lines['greeting']}")
    speech_parts.append(f"現在の{city_str}の天気は、{weather_desc.split()[0]}、気温は{int(weather_info.get('temperature', 20))}度です。")

    if mode in ("morning", "day"):
        if events_today:
            speech_parts.append(f"本日の予定は{len(events_today)}件あります。")
            first_ev = events_today[0]
            if first_ev.get("start_time"):
                speech_parts.append(f"最初の予定は、{first_ev['start_time']}からの、{first_ev['title']}です。")
        else:
            speech_parts.append("本日は大きな予定は入っていません。")

        if active_tasks:
            speech_parts.append(f"未完了のタスクは{len(active_tasks)}件です。最優先は、{active_tasks[0]['title']}です。")
    else:
        if completed_tasks_today:
            speech_parts.append(f"本日完了したタスクは{len(completed_tasks_today)}件です。")
        if habits_summary["total"] > 0:
            speech_parts.append(f"習慣は{habits_summary['total']}件中、{habits_summary['done']}件達成しました。")

    speech_parts.append(f"{char_lines['encouragement']}")
    speech_text = " ".join(speech_parts)

    return BriefingReport(
        mode=mode,
        mode_label=mode_label,
        timestamp=time.time(),
        date_str=date_jp,
        character_id=char_id,
        character_name=char_lines["name"],
        greeting=char_lines["greeting"],
        speech_text=speech_text,
        formatted_markdown=formatted_markdown,
        weather_summary={
            "weather": weather_info.get("weather", "sunny"),
            "temperature": weather_info.get("temperature", 20.0),
            "city": city_str,
            "desc": weather_desc
        },
        events_today=events_today,
        active_tasks=active_tasks,
        completed_tasks_today=completed_tasks_today,
        habits_summary=habits_summary,
        encouragement=char_lines["encouragement"]
    )
