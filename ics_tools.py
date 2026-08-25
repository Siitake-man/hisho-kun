"""
ネオ秘書くん - iCalendar (.ics) エクスポート / インポートツール (ics_tools.py)

Googleカレンダー、Outlook、Appleカレンダー等の標準カレンダーアプリと
予定データを双方向同期・エクスポート・インポートするためのツール群。
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

from langchain_core.tools import tool
import database

logger = logging.getLogger(__name__)

EXPORT_DIR = Path(__file__).parent / "assets" / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# 秘密 iCal URL 連携の .env キー
ICAL_URL_ENV_KEY = "GOOGLE_CALENDAR_ICAL_URL"
ICAL_LAST_SYNC_ENV_KEY = "GOOGLE_CALENDAR_LAST_SYNC"


def load_ical_url() -> str:
    """設定された Google カレンダー秘密 iCal URL を取得する。

    Returns:
        str: iCal URL。未設定の場合は空文字列。
    """
    return os.getenv(ICAL_URL_ENV_KEY, "").strip()


def save_ical_url(url: str) -> None:
    """秘密 iCal URL を .env に保存する（Git 除外済み）。

    Args:
        url (str): Google カレンダーの「予定の取得用の秘密のアドレス (iCal)」。
    """
    from dotenv import set_key
    env_path = Path(__file__).parent / ".env"
    set_key(str(env_path), ICAL_URL_ENV_KEY, url.strip())
    os.environ[ICAL_URL_ENV_KEY] = url.strip()
    logger.info("Googleカレンダー iCal URL を保存しました")


def get_last_sync_time() -> str:
    """最終同期時刻を取得する。

    Returns:
        str: 最終同期時刻（未同期の場合は「未同期」）。
    """
    return os.getenv(ICAL_LAST_SYNC_ENV_KEY, "未同期")


# iCal 取り込み窓（この範囲外の予定はDBへ取り込まない）。
# Googleの秘密iCalは「過去約1年＋未来すべて」を固定で返す仕様のため、
# 必要な範囲だけを取り込んでDBの肥大化と同期時間を抑える。
ICAL_IMPORT_PAST_DAYS = 120
ICAL_IMPORT_FUTURE_DAYS = 730


def ensure_default_calendar_source() -> None:
    """レガシー設定（.env の GOOGLE_CALENDAR_ICAL_URL）を購読ソースへ自動移行する。

    ソースが1件も登録されておらず .env にURLが残っている場合、
    それを「メインカレンダー」として source 1 に取り込む。
    """
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
    if database.get_all_calendar_sources():
        return
    legacy_url = os.getenv(ICAL_URL_ENV_KEY, "").strip()
    if legacy_url:
        database.create_calendar_source(database.CalendarSource(
            name="メインカレンダー",
            color="#A67B5B",
            url=legacy_url,
            enabled=True
        ))
        logger.info("レガシーな .env の iCal URL を購読ソース「メインカレンダー」へ移行しました")


def _fetch_ics_text(target_url: str) -> str:
    """秘密 iCal URL から .ics テキストを取得する。

    Args:
        target_url: 秘密 iCal アドレス。

    Returns:
        str: .ics ファイルの全文。

    Raises:
        Exception: ネットワークエラー・URL不正等。
    """
    import urllib.request
    req = urllib.request.Request(target_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as res:
        return res.read().decode("utf-8", errors="replace")

def sync_calendar_source(source: "database.CalendarSource") -> Tuple[int, str]:
    """購読ソース1件分の iCal を取得し、ローカルDBへ同期する（読み取り専用）。

    取り込み窓（過去 ICAL_IMPORT_PAST_DAYS 日 〜 未来 ICAL_IMPORT_FUTURE_DAYS 日）
    外の予定は破棄する。既存の同ソース予定は置き換えられる（重複しない）。

    Args:
        source: 同期する購読ソース。

    Returns:
        Tuple[int, str]: (同期した予定件数, 結果メッセージ)
    """
    target_url = (source.url or "").strip()
    if not target_url:
        return 0, f"「{source.name}」の iCal URL が未設定です。"
    # URL形式の事前チェック（よくある間違いを案内）
    if "cid=" in target_url:
        return 0, (
            f"「{source.name}」に貼り付けられたURLは「カレンダーを追加するリンク (cid=...)」です。\n"
            "必要なのは「秘密の iCal アドレス」です。Googleカレンダーの「設定と共有」ページの"
            "下部にある「予定の取得用の秘密のアドレス (iCal)」のURLをコピーしてください。"
        )
    if "calendar.google.com/calendar/ical/" not in target_url:
        return 0, (
            f"「{source.name}」の URL 形式が正しくありません。"
            "「https://calendar.google.com/calendar/ical/...basic.ics」で始まる"
            "秘密の iCal アドレスを貼り付けてください。"
        )

    try:
        ics_text = _fetch_ics_text(target_url)
    except Exception as e:
        logger.error(f"iCal URL 取得エラー ({source.name}): {e}")
        return 0, f"「{source.name}」の iCal URL 取得に失敗しました: {e}"

    parsed_events = _parse_ics_events(ics_text)
    if not parsed_events:
        return 0, f"「{source.name}」の iCal から予定を抽出できませんでした（カレンダーが空、または形式不正の可能性）。"

    # 取り込み窓フィルタ（過去/未来の範囲外は破棄）
    now = datetime.now()
    window_start_ms = int((now - timedelta(days=ICAL_IMPORT_PAST_DAYS)).timestamp() * 1000)
    window_end_ms = int((now + timedelta(days=ICAL_IMPORT_FUTURE_DAYS)).timestamp() * 1000)
    filtered = [ev for ev in parsed_events if window_start_ms <= ev["start_ms"] <= window_end_ms]
    skipped = len(parsed_events) - len(filtered)
    if skipped:
        logger.info(f"「{source.name}」: 取り込み窓外の予定 {skipped} 件をスキップしました")
    if not filtered:
        return 0, (
            f"「{source.name}」: 取り込み窓（過去{ICAL_IMPORT_PAST_DAYS}日〜未来{ICAL_IMPORT_FUTURE_DAYS}日）内の"
            "予定がありませんでした。"
        )

    # 既存の同ソース予定を置き換え（重複防止）
    with database.get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM events WHERE source_id = ?", (source.id,))

    imported = 0
    for ev in filtered:
        try:
            event = database.Event(
                title=ev["title"][:200],
                description=ev["description"],
                start_time=ev["start_ms"],
                end_time=max(ev["end_ms"], ev["start_ms"] + 60000),
                google_event_id=ev["uid"],
                source_id=source.id,
            )
            database.create_event(event)
            imported += 1
        except Exception as e:
            logger.warning(f"Googleカレンダー予定のインポートをスキップ: {e}")

    # 最終同期時刻を記録（ソース別 ＆ グローバル.env）
    sync_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    database.set_calendar_source_last_sync(source.id, sync_time)
    from dotenv import set_key
    env_path = Path(__file__).parent / ".env"
    set_key(str(env_path), ICAL_LAST_SYNC_ENV_KEY, sync_time)
    os.environ[ICAL_LAST_SYNC_ENV_KEY] = sync_time

    logger.info(f"Googleカレンダー iCal 同期完了 ({source.name}): {imported}件")
    return imported, f"「{source.name}」から {imported} 件"

def sync_all_calendar_sources() -> Tuple[int, str]:
    """有効な全購読ソースを順に同期し、合計結果を返す。

    Returns:
        Tuple[int, str]: (同期した予定件数の合計, 結果メッセージ)
    """
    ensure_default_calendar_source()
    sources = [s for s in database.get_all_calendar_sources() if s.enabled and s.url.strip()]
    if not sources:
        return 0, (
            "iCal URL が未設定です。Googleカレンダーの「設定と共有」→"
            "「予定の取得用の秘密のアドレス (iCal)」の URL を設定画面から登録してください。"
        )

    total = 0
    messages = []
    for source in sources:
        try:
            count, msg = sync_calendar_source(source)
        except Exception as e:
            logger.error(f"カレンダーソース同期エラー ({source.name}): {e}")
            count, msg = 0, f"「{source.name}」の同期でエラー: {e}"
        total += count
        messages.append(msg)
    return total, " ／ ".join(messages)


def sync_calendar_from_ical_url(url: Optional[str] = None) -> Tuple[int, str]:
    """iCal 同期の後方互換エイリアス。

    url 未指定なら全購読ソースを同期する。url 指定時は該当URLを持つソースのみ同期する
    （既存呼び出しコードとの互換性維持用）。

    Args:
        url (Optional[str]): iCal URL。省略時は全ソース同期。

    Returns:
        Tuple[int, str]: (同期した予定件数, 結果メッセージ)
    """
    if not url:
        return sync_all_calendar_sources()
    ensure_default_calendar_source()
    for source in database.get_all_calendar_sources():
        if source.url.strip() == url.strip():
            return sync_calendar_source(source)
    # URLが未登録ならレガシー動作として単発同期する（ソースには登録しない）
    legacy_source = database.CalendarSource(name="一時同期", url=url, enabled=True)
    return sync_calendar_source(legacy_source)

@tool
def export_calendar_ics_tool(days: int = 30) -> str:
    """
    秘書くんのデータベースに登録されている予定を、標準の iCalendar (.ics) ファイルとしてエクスポートします。
    GoogleカレンダーやOutlook、スマホのカレンダーにまとめて取り込む際に使用します。
    
    Args:
        days: 今後何日分（または過去何日分）の予定を出力するか（デフォルト: 30日）
        
    Returns:
        str: 出力された .ics ファイルのパスとエクスポート結果サマリー
    """
    try:
        events = database.get_upcoming_events(days=days)
        if not events:
            return f"今後 {days} 日間の予定が登録されていないため、エクスポートをスキップしました。"
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = EXPORT_DIR / f"neo_secretary_calendar_{timestamp}.ics"
        
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//NeoSecretary//JP",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "X-WR-CALNAME:ネオ秘書くん カレンダー",
            "X-WR-TIMEZONE:Asia/Tokyo"
        ]
        
        for ev in events:
            # 日時のフォーマット (YYYYMMDDTHHMMSS)
            start_str = ev.start_time.replace("-", "").replace(":", "").replace(" ", "T")
            if "T" not in start_str:
                start_str += "T090000"
            if len(start_str) == 13: # YYYYMMDDTHHMM
                start_str += "00"
                
            end_str = ""
            if ev.end_time:
                end_str = ev.end_time.replace("-", "").replace(":", "").replace(" ", "T")
                if "T" not in end_str:
                    end_str += "T100000"
                if len(end_str) == 13:
                    end_str += "00"
            else:
                # デフォルト1時間後
                end_str = start_str
                
            lines.extend([
                "BEGIN:VEVENT",
                f"UID:neo_event_{ev.id}_{timestamp}@neosecretary.local",
                f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
                f"DTSTART:{start_str}",
                f"DTEND:{end_str}",
                f"SUMMARY:{ev.title}",
                f"DESCRIPTION:{ev.description or ''}",
                f"LOCATION:{ev.location or ''}",
                "STATUS:CONFIRMED",
                "END:VEVENT"
            ])
            
        lines.append("END:VCALENDAR")
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\r\n".join(lines) + "\r\n")
            
        logger.info(f"iCalendar エクスポート完了: {file_path} ({len(events)} 件)")
        return (
            f"📅 カレンダーを iCalendar 形式でエクスポートしました！\n"
            f"出力件数: {len(events)} 件\n"
            f"ファイルパス: {file_path}\n"
            f"※ GoogleカレンダーやOutlookの「設定 ➔ インポート」からこのファイルを取り込むことができます。"
        )
    except Exception as e:
        logger.error(f"ICSエクスポートエラー: {e}")
        return f"❌ カレンダーのエクスポートに失敗しました: {e}"


def _parse_ics_events(ics_text: str) -> List[Dict[str, Any]]:
    """iCalendar テキストから VEVENT を抽出する（軽量パーサー・外部依存ゼロ）。

    Args:
        ics_text (str): .ics ファイルの全文。

    Returns:
        List[Dict[str, Any]]: uid/title/description/start_ms/end_ms を含む辞書リスト。
    """
    # RFC5545 の行継続（先頭がスペース/タブ）を結合
    unfolded: List[str] = []
    for raw in ics_text.splitlines():
        if raw.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += raw[1:]
        else:
            unfolded.append(raw.rstrip("\r"))

    raw_events: List[Dict[str, str]] = []
    current: Dict[str, str] = {}
    in_event = False
    for line in unfolded:
        if line == "BEGIN:VEVENT":
            in_event = True
            current = {}
            continue
        if line == "END:VEVENT":
            in_event = False
            if current.get("SUMMARY") and current.get("DTSTART"):
                raw_events.append(current)
            continue
        if not in_event or ":" not in line:
            continue
        key_part, _, value = line.partition(":")
        key = key_part.split(";")[0].upper()
        tzid = ""
        for part in key_part.split(";"):
            if part.upper().startswith("TZID="):
                tzid = part.split("=", 1)[1]
        if key == "UID":
            current["uid"] = value.strip()
        elif key == "SUMMARY":
            current["SUMMARY"] = value.strip()
        elif key == "DESCRIPTION":
            current["DESCRIPTION"] = value.replace("\\n", " ").replace("\\,", ",").replace("\\;", ";").strip()
        elif key == "DTSTART":
            current["DTSTART"], current["DTSTART_TZID"] = value.strip(), tzid
        elif key == "DTEND":
            current["DTEND"], current["DTEND_TZID"] = value.strip(), tzid

    # 日時を Unix ミリ秒へ変換
    result: List[Dict[str, Any]] = []
    for ev in raw_events:
        try:
            start_ms = _ics_dt_to_ms(ev.get("DTSTART", ""), ev.get("DTSTART_TZID", ""))
            end_raw = ev.get("DTEND") or ev.get("DTSTART", "")
            end_ms = _ics_dt_to_ms(end_raw, ev.get("DTEND_TZID", ""))
            result.append({
                "uid": ev.get("uid") or f"gcal_{abs(hash(ev['SUMMARY'])) % 100000000}",
                "title": ev["SUMMARY"],
                "description": ev.get("DESCRIPTION", ""),
                "start_ms": start_ms,
                "end_ms": end_ms,
            })
        except Exception as e:
            logger.warning(f"ICS 日時パース失敗（スキップ）: {e}")
    return result


def _ics_dt_to_ms(value: str, tzid: str) -> int:
    """ICS の日時文字列を Unix ミリ秒に変換する。

    Args:
        value (str): DTSTART/DTEND の値（例: 20260825T100000Z / 20260825 / 20260825T100000）。
        tzid (str): TZID パラメータ（Asia/Tokyo 等を JST として処理）。

    Returns:
        int: Unix Timestamp ミリ秒。
    """
    value = value.strip()
    if value.endswith("Z"):
        dt = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    elif "T" in value:
        tz = timezone(timedelta(hours=9)) if "Tokyo" in (tzid or "") else timezone.utc
        dt = datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=tz)
    else:
        # 終日予定は JST 09:00 開始として扱う
        tz = timezone(timedelta(hours=9)) if "Tokyo" in (tzid or "") else timezone.utc
        dt = datetime.strptime(value, "%Y%m%d").replace(tzinfo=tz, hour=9)
    return int(dt.timestamp() * 1000)
