"""
ネオ秘書くん - クイックタスク追加パーサ (task_parser.py)

TickTick風の自然言語クイック追加構文を解析するルールベースパーサ。
LLMを介さないため、スマホPWAのクイック追加バーからでも即座に (数msで) 解析できる。

対応構文の例:
    「明日18時に会議資料を作る #仕事 !3」
      -> title="会議資料を作る", due_date=明日18:00, tags=["仕事"], priority=3

    「金曜までに請求書確認 !高」
      -> title="請求書確認", due_date=金曜23:59, priority=2

構文リファレンス:
    - #タグ名       : タグ (複数可、カンマ区切りでDB保存)
    - !1 / !2 / !3  : 優先度 (0=なし, 1=低, 2=中, 3=高)。!低/!中/!高 も可
    - ※重要/※非重要 : 重要度フラグ (4象限用・省略時は優先度から推定)
    - ※緊急/※非緊急 : 緊急度フラグ (4象限用・省略時は期限から推定)
    - 日時表現      : 今日/明日/明後日, M月D日, M/D, 月曜〜日曜 (来るべき直近の曜日),
                      HH時 / HH:MM / 午前HH時 / 午後HH時MM分, 「〜までに」対応
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

# ---------------------------------------------------------------------------
# 解析結果データ構造
# ---------------------------------------------------------------------------


@dataclass
class ParsedTask:
    """クイック追加構文の解析結果を保持するデータクラス。"""

    title: str = ""
    due_date: Optional[int] = None  # epochミリ秒 (期限なしはNone)
    priority: int = 0  # 0=なし / 1=低 / 2=中 / 3=高
    tags: list = field(default_factory=list)
    description: str = ""
    importance: Optional[bool] = None  # 明示的重要度 (※重要 / None=未指定)
    urgency: Optional[bool] = None  # 明示的緊急度 (※緊急 / None=未指定)
    recurrence: Optional[str] = None  # 繰り返し種別 ('daily' / 'weekly' / 'monthly' / None)


# ---------------------------------------------------------------------------
# 内部定数・正規表現
# ---------------------------------------------------------------------------

_WEEKDAY_NAMES = {
    "月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6
}

_PRIORITY_WORDS = {"低": 1, "中": 2, "高": 3}

_RE_TAG = re.compile(r"#([^\s#]+)")
_RE_PRIORITY = re.compile(r"!(1|2|3|低|中|高)(?![0-9])")
_RE_IMPORTANCE = re.compile(r"※(重要|非重要)(?![^\s,、。※])")
_RE_URGENCY = re.compile(r"※(緊急|非緊急)(?![^\s,、。※])")
# 繰り返し表現 (roadmap 1.12): 毎日 / 毎週[月〜日]曜 / 毎月D日
# 週の曜日・月の日付は後続の期限計算で使うためキャプチャする
_RE_RECURRENCE = re.compile(r"毎日|毎週([月火水木金土日])?曜?|毎月(\d{1,2})日?")
_RE_MDY_JP = re.compile(r"(\d{1,2})月(\d{1,2})日")
_RE_MDY_SLASH = re.compile(r"(\d{1,2})/(\d{1,2})")
_RE_TIME_COLON = re.compile(r"(\d{1,2}):(\d{2})")
_RE_TIME_JP = re.compile(r"(午前|午後)?(\d{1,2})時(?:(\d{1,2})分?|半)?(に|まで|ごろ|頃)?")
_RE_DAY_WORD = re.compile(r"(今日|明日|明後日|今日中|明日中)")


def _next_weekday(target_weekday: int, base: datetime) -> datetime:
    """
    base 以降で最初に来る target_weekday の日付を返す (当日を含まない)。

    Args:
        target_weekday: 目標曜日 (0=月 〜 6=日)
        base: 起点日時

    Returns:
        対象曜日の日付 (時刻はbaseから引き継ぎ)
    """
    delta_days = (target_weekday - base.weekday()) % 7
    if delta_days == 0:
        delta_days = 7  # 当日ではなく「次の」曜日
    return base + timedelta(days=delta_days)


def _apply_time(base: datetime, hour: int, minute: int) -> datetime:
    """
    base の日付に指定時刻を適用する (時刻指定なしの期限日は23:59とする)。

    Args:
        base: 起点日時
        hour: 時 (0-23 に正規化済みであること)
        minute: 分 (指定なしは59分 = 「〜までに」扱い)

    Returns:
        時刻適用後の日時
    """
    return base.replace(hour=max(0, min(23, hour)), minute=max(0, min(59, minute)), second=0, microsecond=0)


def _parse_date_tokens(text: str, now: Optional[datetime] = None) -> tuple:
    """
    テキストから日付・時刻表現を抽出する。

    Args:
        text: 解析対象テキスト
        now: 起点日時 (テスト用に注入可能、Noneで現在時刻)

    Returns:
        (due_date: Optional[int] epochミリ秒, matched_texts: set[str] 消費した表現,
         time_part: Optional[tuple] 抽出できた (hour, minute) — 繰り返し期限の解決に使用)
    """
    base = now or datetime.now()
    matched = set()
    day: Optional[datetime] = None
    time_part: Optional[tuple] = None  # (hour, minute)

    # 時刻 (コロン記法): 18:30
    m = _RE_TIME_COLON.search(text)
    if m:
        time_part = (int(m.group(1)), int(m.group(2)))
        matched.add(m.group(0))

    # 時刻 (日本語記法): 午後6時30分 / 18時
    if time_part is None:
        m = _RE_TIME_JP.search(text)
        if m:
            hour = int(m.group(2))
            minute = int(m.group(3)) if m.group(3) else (30 if m.group(0).rstrip("にまでごろ頃").endswith("半") else 59)
            if m.group(1) == "午後" and hour < 12:
                hour += 12
            if m.group(1) == "午前" and hour == 12:
                hour = 0
            time_part = (hour, minute)
            matched.add(m.group(0))

    # 相対日: 今日/明日/明後日 (+「中」は当日23:59の「〜までに」扱い)
    m = _RE_DAY_WORD.search(text)
    if m:
        word = m.group(1)
        matched.add(word)
        if word == "今日" or word == "今日中":
            day = base
        elif word == "明日" or word == "明日中":
            day = base + timedelta(days=1)
        elif word == "明後日":
            day = base + timedelta(days=2)
        else:  # 念のためのフォールバック (正規表現と矛盾しない)
            day = base

    # M月D日
    if day is None:
        m = _RE_MDY_JP.search(text)
        if m:
            month = int(m.group(1))
            md_day = int(m.group(2))
            candidate = base.replace(month=max(1, min(12, month)), day=1)
            try:
                candidate = base.replace(
                    month=max(1, min(12, month)), day=max(1, min(31, md_day))
                )
            except ValueError:
                candidate = base  # 不正日付 (2月30日等) は起点日で継続
            day = candidate
            matched.add(m.group(0))

    # M/D
    if day is None:
        m = _RE_MDY_SLASH.search(text)
        if m:
            try:
                day = base.replace(
                    month=max(1, min(12, int(m.group(1)))),
                    day=max(1, min(31, int(m.group(2))))
                )
            except ValueError:
                day = base
            matched.add(m.group(0))

    # 曜日: 月曜 / 金曜日 など
    if day is None:
        for ch, weekday in _WEEKDAY_NAMES.items():
            pattern = f"{ch}曜"
            if pattern in text:
                day = _next_weekday(weekday, base)
                matched.add(pattern)
                if f"{ch}曜日" in text:
                    matched.add(f"{ch}曜日")
                break

    # 日付表現が一切なければ期限なし (時刻情報は繰り返し計算用に返す)
    if day is None:
        return (None, matched, time_part)

    if time_part is not None:
        due = _apply_time(day, time_part[0], time_part[1])
    else:
        # 日付のみ指定: その日の終わりまでに (23:59)
        due = _apply_time(day, 23, 59)

    return (int(due.timestamp() * 1000), matched, time_part)


def _resolve_recurrence_due(
    recurrence: str,
    weekday: Optional[int],
    monthday: Optional[int],
    time_part: Optional[tuple],
    base: datetime,
    parsed_due_ms: Optional[int],
) -> Optional[int]:
    """
    繰り返し種別に応じて最初の期限 (epochミリ秒) を解決する。

    明示的な期限表現が既に解析できている場合はそれを尊重する
    (例: 「毎週 8月31日に」→ 8月31日を初回とする)。

    Args:
        recurrence: 繰り返し種別 ('daily' / 'weekly' / 'monthly')
        weekday: 毎週の曜日 (0=月〜6=日、指定なしはNone)
        monthday: 毎月の日付 (1-31、指定なしはNone)
        time_part: 抽出済みの (hour, minute)。Noneなら23:59扱い
        base: 起点日時
        parsed_due_ms: 通常の期限解析で得られた期限 (あれば優先)

    Returns:
        解決できた期限のepochミリ秒 (曜日・日付指定が不足する場合はNone)
    """
    if parsed_due_ms is not None:
        return parsed_due_ms
    hour, minute = (time_part or (23, 59))
    if recurrence == "daily":
        # 「毎日9時」等: 今日の指定時刻。既に過ぎていれば明日以降の同一時刻
        due = _apply_time(base, hour, minute)
        if due <= base:
            due += timedelta(days=1)
    elif recurrence == "weekly":
        if weekday is None:
            return None  # 「毎週」のみで曜日未指定 → 期限は未定とする
        due = _apply_time(_next_weekday(weekday, base), hour, minute)
    elif recurrence == "monthly":
        if monthday is None:
            return None  # 「毎月」のみで日付未指定 → 期限は未定とする
        day = max(1, min(28, monthday))  # 月末クランプ (2月等の無効日を回避)
        try:
            due = _apply_time(base.replace(day=day), hour, minute)
        except ValueError:
            return None
        if due <= base:
            # 翌月の同一日へロールオーバー (12月→翌年1月も考慮)
            next_month = due.month % 12 + 1
            next_year = due.year + (1 if due.month == 12 else 0)
            due = _apply_time(due.replace(year=next_year, month=next_month, day=day), hour, minute)
    else:
        return None
    return int(due.timestamp() * 1000)


# ---------------------------------------------------------------------------
# 公開API
# ---------------------------------------------------------------------------


def parse_input(text: str, now: Optional[datetime] = None) -> ParsedTask:
    """
    クイック追加構文を解析して ParsedTask を生成する。

    タグ (#xxx) と優先度 (!1〜!3/!低〜!高) を除去した残りをタイトルとし、
    日時表現は解析後に除去する (タイトルは純粋なタスク名のみ残す)。

    Args:
        text: ユーザー入力 (例: 「明日18時に会議資料を作る #仕事 !3」)
        now: 起点日時 (テスト用、Noneで現在時刻)

    Returns:
        解析結果の ParsedTask
    """
    clean = (text or "").strip()
    result = ParsedTask()
    if not clean:
        return result

    # 1. タグ抽出 (#タグ)
    tags: list = []

    def _collect_tag(m: "re.Match") -> str:
        tag = m.group(1).strip()
        if tag:
            tags.append(tag)
        return ""

    clean = _RE_TAG.sub(_collect_tag, clean)

    # 2. 優先度抽出 (!1〜!3 / !低〜!高)
    def _collect_priority(m: "re.Match") -> str:
        token = m.group(1)
        if token in _PRIORITY_WORDS:
            result.priority = _PRIORITY_WORDS[token]
        else:
            result.priority = int(token)
        return ""

    clean = _RE_PRIORITY.sub(_collect_priority, clean)

    # 2.5 重要度・緊急度フラグ抽出 (※重要/※非重要/※緊急/※非緊急 — 4象限用)
    def _collect_importance(m: "re.Match") -> str:
        result.importance = (m.group(1) == "重要")
        return ""

    def _collect_urgency(m: "re.Match") -> str:
        result.urgency = (m.group(1) == "緊急")
        return ""

    clean = _RE_IMPORTANCE.sub(_collect_importance, clean)
    clean = _RE_URGENCY.sub(_collect_urgency, clean)

    # 2.6 繰り返し抽出 (毎日 / 毎週[月〜日]曜 / 毎月D日 — roadmap 1.12)
    recurrence: Optional[str] = None
    recurrence_weekday: Optional[int] = None
    recurrence_monthday: Optional[int] = None
    m_rec = _RE_RECURRENCE.search(clean)
    if m_rec:
        token = m_rec.group(0)
        if token == "毎日":
            recurrence = "daily"
        elif token.startswith("毎週"):
            recurrence = "weekly"
            ch = m_rec.group(1)
            recurrence_weekday = _WEEKDAY_NAMES[ch] if ch else None
        else:  # 毎月 / 毎月D日
            recurrence = "monthly"
            recurrence_monthday = int(m_rec.group(2)) if m_rec.group(2) else None
        clean = clean.replace(token, " ")

    # 3. 日時抽出 (表現はタイトルから除去する)
    due_ms, matched_texts, parsed_time = _parse_date_tokens(clean, now=now)
    for token in matched_texts:
        clean = clean.replace(token, " ")
    result.due_date = due_ms

    # 3.5 繰り返しTaskの初回期限を解決する (既存の期限解析結果を優先)
    if recurrence:
        result.recurrence = recurrence
        result.due_date = _resolve_recurrence_due(
            recurrence, recurrence_weekday, recurrence_monthday,
            parsed_time, now or datetime.now(), due_ms
        )

    # 4. タイトルの整飾 (余分な空白・記号のクリーンアップ)
    clean = re.sub(r"[\s\u3000]+", " ", clean).strip()
    clean = clean.strip(" 　,、。")
    result.tags = tags
    result.title = clean
    return result


def tags_to_db_string(tags: list) -> str:
    """
    タグのリストをDB保存用のカンマ区切り文字列へ変換する。

    Args:
        tags: タグ文字列のリスト

    Returns:
        カンマ区切り文字列 (例: "仕事,急ぎ")
    """
    seen: set = set()
    ordered: list = []
    for tag in tags:
        clean = (tag or "").strip()
        if clean and clean not in seen:
            seen.add(clean)
            ordered.append(clean)
    return ",".join(ordered)


def db_string_to_tags(db_value: str) -> list:
    """
    DB保存用カンマ区切り文字列をタグのリストへ逆変換する。

    Args:
        db_value: カンマ区切り文字列

    Returns:
        タグ文字列のリスト (空文字列入力は空リスト)
    """
    if not (db_value or "").strip():
        return []
    return [part.strip() for part in db_value.split(",") if part.strip()]
