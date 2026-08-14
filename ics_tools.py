"""
ネオ秘書くん - iCalendar (.ics) エクスポート / インポートツール (ics_tools.py)

Googleカレンダー、Outlook、Appleカレンダー等の標準カレンダーアプリと
予定データを双方向同期・エクスポート・インポートするためのツール群。
"""

import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

from langchain_core.tools import tool
import database

logger = logging.getLogger(__name__)

EXPORT_DIR = Path(__file__).parent / "assets" / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


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
