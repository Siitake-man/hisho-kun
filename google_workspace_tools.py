"""
ネオ秘書くん - Google Workspace (Google Calendar & Gmail) 連携ツール (google_workspace_tools.py)

Google カレンダーの予定取得・作成、および Gmail の未読メール検索・要約を行うツール群。
OAuth2 トークンによる公式API接続と、初期セットアップ時のセーフフォールバックを提供します。
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from langchain_core.tools import tool
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

CREDENTIALS_PATH = Path(__file__).parent / "google_credentials.json"
TOKEN_PATH = Path(__file__).parent / "google_token.json"


def _get_google_service(service_name: str, version: str):
    """
    Google API クライアントサービスを取得（OAuth2認証）
    """
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        SCOPES = [
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/gmail.readonly'
        ]

        creds = None
        if TOKEN_PATH.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
            
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            elif CREDENTIALS_PATH.exists():
                flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
                creds = flow.run_local_server(port=0)
                with open(TOKEN_PATH, 'w', encoding='utf-8') as token:
                    token.write(creds.to_json())
            else:
                return None

        return build(service_name, version, credentials=creds)
    except Exception as e:
        logger.warning(f"Google API サービス初期化エラー ({service_name}): {e}")
        return None


@tool
def get_google_calendar_events_tool(days: int = 7) -> str:
    """
    Googleカレンダーから直近の予定を取得します。
    ボスから「Googleカレンダーの予定教えて」「来週のGoogleのスケジュールは？」と
    言われた際に呼び出します。
    
    Args:
        days: 今後何日分の予定を取得するか（デフォルト: 7日）
        
    Returns:
        str: 予定一覧サマリー
    """
    service = _get_google_service('calendar', 'v3')
    
    if service:
        try:
            now = datetime.utcnow().isoformat() + 'Z'
            time_max = (datetime.utcnow() + timedelta(days=days)).isoformat() + 'Z'
            
            events_result = service.events().list(
                calendarId='primary', 
                timeMin=now,
                timeMax=time_max,
                maxResults=20, 
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])

            if not events:
                return f"Googleカレンダーに今後 {days} 日間の予定はありませんでした。"

            lines = [f"📅 Googleカレンダーの直近予定（今後 {days} 日間）:"]
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                summary = event.get('summary', '(タイトルなし)')
                loc = f" [{event.get('location')}]" if event.get('location') else ""
                lines.append(f"- {start}: {summary}{loc}")
                
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Googleカレンダー取得エラー: {e}")
            return f"❌ Googleカレンダーの取得中にエラーが発生しました: {e}"
    else:
        # OAuth認証ファイル未設定時の案内
        return (
            "ℹ️ Googleカレンダーとの直接連携には、`google_credentials.json` の設定が必要です。\n"
            "（現在はローカルDBおよびiCalendarエクスポート機能が利用可能です。\n"
            "Google Cloud Console で OAuth クライアントID を作成し、プロジェクト直下に配置すると本番同期が有効化されます）"
        )


@tool
def create_google_calendar_event_tool(
    title: str, 
    start_time: str, 
    end_time: Optional[str] = None, 
    description: Optional[str] = None
) -> str:
    """
    Googleカレンダーに新しい予定を登録します。
    
    Args:
        title: 予定のタイトル
        start_time: 開始日時 (例: '2026-08-16 14:00' または ISO形式)
        end_time: 終了日時 (省略時は開始の1時間後)
        description: 予定の説明・メモ
        
    Returns:
        str: 登録結果メッセージ
    """
    service = _get_google_service('calendar', 'v3')
    
    if service:
        try:
            # ISO形式変換
            start_iso = start_time.replace(" ", "T")
            if "T" not in start_iso:
                start_iso += "T09:00:00"
            if len(start_iso) == 16:
                start_iso += ":00"
                
            if end_time:
                end_iso = end_time.replace(" ", "T")
                if len(end_iso) == 16:
                    end_iso += ":00"
            else:
                dt_start = datetime.fromisoformat(start_iso)
                end_iso = (dt_start + timedelta(hours=1)).isoformat()

            event_body = {
                'summary': title,
                'description': description or '',
                'start': {'dateTime': f"{start_iso}+09:00", 'timeZone': 'Asia/Tokyo'},
                'end': {'dateTime': f"{end_iso}+09:00", 'timeZone': 'Asia/Tokyo'},
            }

            created_event = service.events().insert(calendarId='primary', body=event_body).execute()
            link = created_event.get('htmlLink', '')
            return f"✨ Googleカレンダーに予定『{title}』を登録しました！\n日時: {start_time}\nリンク: {link}"
        except Exception as e:
            return f"❌ Googleカレンダーへの登録に失敗しました: {e}"
    else:
        # ローカルDB側へ登録するフォールバック
        import database
        from database import EventCreate
        database.create_event(EventCreate(title=title, start_time=start_time, end_time=end_time, description=description))
        return (
            f"✨ 予定『{title}』を秘書くん手帳（ローカル）に登録しました！\n"
            f"（※ Google Cloud OAuth が設定されると、Googleカレンダーへも自動同時登録されます）"
        )


@tool
def search_gmail_messages_tool(query: str = "is:unread", max_results: int = 5) -> str:
    """
    Gmail から特定のキーワードや未読メールを検索して件名と送信者を要約します。
    ボスから「メール届いてる？」「重要なメールある？」と言われた際に呼び出します。
    
    Args:
        query: 検索クエリ (例: 'is:unread', 'from:boss', '重要')
        max_results: 取得する最大件数（デフォルト: 5件）
        
    Returns:
        str: メール検索結果サマリー
    """
    service = _get_google_service('gmail', 'v1')
    
    if service:
        try:
            results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
            messages = results.get('messages', [])

            if not messages:
                return f"Gmail で条件 '{query}' に一致するメールは見つかりませんでした。"

            lines = [f"✉️ Gmail 検索結果 ({len(messages)} 件):"]
            for msg in messages:
                msg_data = service.users().messages().get(userId='me', id=msg['id'], format='metadata').execute()
                headers = {h['name'].lower(): h['value'] for h in msg_data.get('payload', {}).get('headers', [])}
                subject = headers.get('subject', '(件名なし)')
                sender = headers.get('from', '(送信者不明)')
                lines.append(f"- 差出人: {sender}\n  件名: {subject}")
                
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Gmail の検索中にエラーが発生しました: {e}"
    else:
        return (
            "ℹ️ Gmail 連携を利用するには、Google Cloud の `google_credentials.json` を配置して認証を行ってください。\n"
            "設定後は未読メールの自動チェックや要約が可能になります。"
        )
