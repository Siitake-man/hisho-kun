"""
ネオ秘書くん - 決定論的コマンドルーター (command_router.py)

軽量ローカルLLM（GGUF）など tool calling 非対応のモデルでも「予定の登録」を
確実に実行できるよう、高信頼のインテントを正規表現ベースで決定論的に処理する。

設計方針:
- 高信頼パターンのみを自前処理し、曖昧な入力は None を返して LangGraph
  エージェント（LLM推論）へ委譲する。
- 実行は db_tools.create_event_tool の直接 invoke により行うため、LLM の
  有無・ツール能力に依存しない。
- 完了応答は実行結果の事実のみを伝える（誠実性ガード規約に準拠）。
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

from db_tools import create_event_tool

logger = logging.getLogger(__name__)

# 予定登録の高信頼トリガー（例: 「明日15時に会議を入れて」「予定を登録して」）
_EVENT_INTENT_RE = re.compile(
    r"(予定|イベント|スケジュール|会議|打ち合わせ|打合せ|ミーティング|アポ|約束|予約)"
    r"[^。!?！？]*?(入れて|いれて|入れ|登録して|登録し|追加して|追加し|作成して|作成し|記録して)"
)
# 引用（「」『』）で囲まれたタイトル（最優先で採用）
_QUOTED_TITLE_RE = re.compile(r"[「『]([^」』]{1,40})[」』]")
# 「（何々）を 入れて/追加して/登録して/作成して」形式のタイトル抽出
_TITLE_BEFORE_TRIGGER_RE = re.compile(
    r"([\S 　]{1,30}?)[ 　]*(?:を|って)\s*(?:入れて|いれて|追加して|登録して|作成して)"
)
# タイトル先頭に混入した日時表現の除去パターン
_DATE_PREFIX_RE = re.compile(
    r"^(?:今日|きょう|明日|あした|明後日|あさって"
    r"|\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?"
    r"|\d{1,2}月\d{1,2}日?|\d{1,2}日|\d{1,2}:\d{2}|\d{1,2}時\d{0,2}分?)+[にのは 　]*"
)
# 相対日付ワード → 基準日からのオフセット日数
_DATE_WORD_OFFSETS = {"今日": 0, "きょう": 0, "明日": 1, "あした": 1, "明後日": 2, "あさって": 2}
# 絶対日付表現（例: 8月30日, 2026-08-30, 9/5）
_MONTH_DAY_RE = re.compile(r"(?:(\d{4})[-/年])?(\d{1,2})[月/](\d{1,2})日?")
# 時刻表現（例: 15時, 15時30分, 15:30）※分は省略可能
_TIME_RE = re.compile(r"(\d{1,2})[時:](\d{1,2})?分?")
# 期間表現（例: 2時間, 30分）
_DURATION_HOURS_RE = re.compile(r"(\d{1,2})時間")
_DURATION_MINUTES_RE = re.compile(r"(\d{1,3})分(間)?")

# 既定値: 指定が無い場合のイベント開始時刻・所要時間
DEFAULT_EVENT_HOUR = 10
DEFAULT_EVENT_DURATION = timedelta(hours=1)


def _extract_title(user_text: str) -> Optional[str]:
    """ユーザー発話から予定タイトルとして使える語句を抽出する。

    Args:
        user_text: ユーザー発話（正規化前）。

    Returns:
        Optional[str]: 抽出できたタイトル。抽出不能な場合は None。
    """
    quoted = _QUOTED_TITLE_RE.search(user_text)
    if quoted:
        return quoted.group(1).strip()
    m = _TITLE_BEFORE_TRIGGER_RE.search(user_text)
    if not m:
        return None
    raw = m.group(1).strip(" 　")
    # 読点区切りの最終セグメントのみ対象（「〜から2時間、打ち合わせ」→「打ち合わせ」）
    raw = re.split(r"[。、,，\n]", raw)[-1].strip(" 　")
    title = _DATE_PREFIX_RE.sub("", raw).strip(" 　")
    if title and len(title) <= 30:
        return title
    return None


def _resolve_event_datetimes(user_text: str, now: Optional[datetime] = None) -> Optional[Tuple[datetime, datetime]]:
    """発話から予定の開始・終了日時を決定論的に解析する。

    Args:
        user_text: ユーザー発話。
        now: 解析基準時刻（テスト用。省略時は現在時刻）。

    Returns:
        Optional[Tuple[datetime, datetime]]: (開始日時, 終了日時)。
            対象日の特定ができない・表記が不正な場合は None（LLMへ委譲）。
    """
    base = now if now is not None else datetime.now()
    base_date = base.replace(hour=0, minute=0, second=0, microsecond=0)

    # 1. 対象日を確定（相対語 → 絶対日付 の順で探索）
    day_offset: Optional[int] = None
    for word, off in _DATE_WORD_OFFSETS.items():
        if word in user_text:
            day_offset = off
            break
    if day_offset is None:
        md = _MONTH_DAY_RE.search(user_text)
        if md:
            year = int(md.group(1)) if md.group(1) else base.year
            try:
                target_date = base_date.replace(year=year, month=int(md.group(2)), day=int(md.group(3)))
            except ValueError:
                return None
            # 過去の日付は翌年の同月日と解釈する（年指定が無い場合のみ）
            if target_date < base_date and not md.group(1):
                target_date = target_date.replace(year=target_date.year + 1)
            day_offset = (target_date - base_date).days
    if day_offset is None:
        return None

    # 2. 開始時刻を確定（指定が無ければ既定時刻）
    hour, minute = DEFAULT_EVENT_HOUR, 0
    tm = _TIME_RE.search(user_text)
    if tm:
        hour, minute = int(tm.group(1)), int(tm.group(2) or 0)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None
        if hour < 12 and ("午後" in user_text or "pm" in user_text.lower()):
            hour += 12
            if hour > 23:
                return None
    start = base_date + timedelta(days=day_offset, hours=hour, minutes=minute)

    # 3. 期間を確定（指定が無ければ1時間）
    duration = DEFAULT_EVENT_DURATION
    hm = _DURATION_HOURS_RE.search(user_text)
    mm = _DURATION_MINUTES_RE.search(user_text)
    if hm or mm:
        duration = timedelta(
            hours=int(hm.group(1)) if hm else 0,
            minutes=int(mm.group(1)) if mm else 0,
        )
        if duration <= timedelta(0):
            return None
    end = start + duration

    # 過去時刻に登録してしまう誤爆を防止
    if end <= base:
        return None
    return start, end


def try_route_command(user_text: str) -> Optional[str]:
    """高信頼の予定登録指示を決定論的に実行し、応答文字列を返す。

    Args:
        user_text: ユーザー発話。

    Returns:
        Optional[str]: 処理結果の応答文。対象外・解析不能の場合は None
            （呼び出し側は通常のLLM推論へフォールバックする）。
    """
    if not user_text or not user_text.strip():
        return None
    text = user_text.strip()
    if not _EVENT_INTENT_RE.search(text):
        return None

    datetimes = _resolve_event_datetimes(text)
    if datetimes is None:
        logger.info("コマンドルーター: 予定登録インテントだが日時を解析できず LLM へ委譲")
        return None
    start, end = datetimes

    title = _extract_title(text)
    if not title:
        logger.info("コマンドルーター: 予定登録インテントだがタイトルを抽出できず LLM へ委譲")
        return None

    try:
        result = create_event_tool.invoke({
            "title": title,
            "start_dt": start.strftime("%Y-%m-%dT%H:%M:%S"),
            "end_dt": end.strftime("%Y-%m-%dT%H:%M:%S"),
            "description": "",
        })
        logger.info(f"コマンドルーター: 決定論的予定登録を実行 (title={title}, start={start:%Y-%m-%d %H:%M})")
        return f"📅 {result}"
    except Exception as route_err:
        logger.error(f"コマンドルーター: 予定登録の実行に失敗: {route_err}", exc_info=True)
        return None