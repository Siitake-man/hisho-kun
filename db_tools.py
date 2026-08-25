"""
ネオ秘書くん - データベースツールラッパー (db_tools.py)

AI（LangGraph）が database.py の機能を直接扱えるようにするための
「変換アダプター（@tool ラッパー）」を定義します。
"""

from langchain_core.tools import tool
from datetime import datetime
import database

@tool
def create_event_tool(title: str, start_dt: str, end_dt: str, description: str = "") -> str:
    """カレンダーに新しい予定を追加します。
    引数:
    - title: 予定のタイトル (例: '開発会議', '歯医者')
    - start_dt: 開始日時 (必ずISO8601形式で年月日を指定。例: '2026-03-09T10:00:00')
    - end_dt: 終了日時 (必ずISO8601形式で年月日を指定。例: '2026-03-09T11:00:00')
    - description: 予定の詳細メモ（任意）
    """
    try:
        # 文字列のISO8601形式をPythonのdatetime型に変換
        start_time_dt = datetime.fromisoformat(start_dt.replace("Z", ""))
        end_time_dt = datetime.fromisoformat(end_dt.replace("Z", ""))
        
        # DBはUnix Timestamp(ミリ秒)を期待しているため変換
        start_time_ms = int(start_time_dt.timestamp() * 1000)
        end_time_ms = int(end_time_dt.timestamp() * 1000)
        
        # database.py が理解できる Pydantic モデルを生成
        event = database.Event(
            title=title,
            description=description,
            start_time=start_time_ms,
            end_time=end_time_ms
        )
        
        # 本物の関数を呼び出す
        event_id = database.create_event(event)
        
        return f"予定「{title}」(ID: {event_id}) をカレンダーに作成しました！"
    except ValueError as ve:
        import traceback
        if "time" in str(ve).lower() or "format" in str(ve).lower():
            # 日付フォーマットエラー時はAIにやり直しを指示する
            return f"エラー: 日付フォーマットが正しくありません (入力: start={start_dt}, end={end_dt})。 必ず 'YYYY-MM-DDTHH:MM:SS' 形式で再試行してください。"
        else:
            return f"システムエラー(Validation): 入力値が不正です。詳細: {ve}"
    except Exception as e:
        return f"システムの内部エラーで予定の作成に失敗しました: {e}"

@tool
def get_upcoming_events_tool(days: int = 7) -> str:
    """今後指定した日数分（デフォルト7日間）のカレンダー予定を取得し、一覧を返します。
    引数:
    - days: 取得する日数 (デフォルト: 7)
    """
    try:
        events = database.get_upcoming_events(days=days)
        if not events:
            return f"今後{days}日間に予定はありません。"
        
        result = f"直近{days}日間の予定一覧:\n"
        for i, e in enumerate(events, 1):
            # DBから返される値はUnix Timestamp (ミリ秒) なので datetime に変換
            start_dt = datetime.fromtimestamp(e.start_time / 1000)
            end_dt = datetime.fromtimestamp(e.end_time / 1000)
            
            start_str = start_dt.strftime('%Y-%m-%d %H:%M')
            end_str = end_dt.strftime('%H:%M')
            result += f"{i}. {e.title} ({start_str} ~ {end_str})\n"
            if e.description:
                result += f"   - 詳細: {e.description}\n"
        return result
    except Exception as e:
        return f"予定の取得に失敗しました: {e}"

@tool
def create_sticky_note_tool(content: str) -> str:
    """デスクトップ上に新しい付箋（メモ・備忘録）を作成します。
    引数:
    - content: 付箋に書く内容
    """
    try:
        note = database.StickyNote(content=content)
        note_id = database.create_sticky_note(note)
        return f"付箋「{content[:15]}...」(ID: {note_id}) をデスクトップに作成しました！"
    except Exception as e:
        return f"付箋の作成に失敗しました: {e}"

@tool
def remember_user_insight_tool(category: str, content: str, importance: int = 3, context_tags: str = "") -> str:
    """ユーザー（ボス）に関する重要な情報・制約・好み・習慣・ルールを長期記憶に保存します。
    会話の中でユーザーが自分の予定の制約（例: '金曜夜は予定を入れない'）、好み（例: '朝会は10時固定がいい'）、
    習慣、家庭の都合、作業ルールなどを述べた際に、自律的に呼び出して記憶してください。
    
    引数:
    - category: カテゴリ ('Constraint': 制約・NG事項, 'Preference': 好み・希望, 'Habit': 習慣・生活リズム, 'Project': プロジェクトルール)
    - content: 覚えるべき内容の要約（例: '平日夜は家族のケアサポートのため予定を入れない'）
    - importance: 重要度 (1〜5, 制約や絶対厳守は 4 または 5)
    - context_tags: 関連キーワード（例: 'schedule, family, time'）
    """
    try:
        # カテゴリの正規化
        valid_cats = {'Constraint': 'Constraint', 'Preference': 'Preference', 'Habit': 'Habit', 'Project': 'Project'}
        cat = valid_cats.get(category, 'Preference')
        
        insight = database.UserInsight(
            category=cat,
            content=content,
            importance=max(1, min(5, importance)),
            context_tags=context_tags
        )
        insight_id = database.create_user_insight(insight)
        return f"ボスに関する知見（[{cat}] {content}）を長期記憶(ID: {insight_id})にしっかり覚えました！今後のサポートに反映します。"
    except Exception as e:
        return f"記憶の保存に失敗しました: {e}"

@tool
def get_user_insights_tool(category: str = "") -> str:
    """記憶しているユーザー（ボス）の制約・好み・習慣・ルールの一覧を取得します。
    ユーザーから「私の好みを覚えてる？」「私のルールは何だっけ？」と聞かれた際や、
    提案時にボスの前提条件を確認したい際に使用します。
    
    引数:
    - category: 絞り込みたいカテゴリ（'Constraint', 'Preference', 'Habit', 'Project'、省略時は全件）
    """
    try:
        cat_arg = category if category in ('Constraint', 'Preference', 'Habit', 'Project') else None
        insights = database.get_user_insights(category=cat_arg, limit=10)
        if not insights:
            return "現在、記録されているユーザー知見はありません。"
        
        result = "🧠 覚えているボスの知見・ルール一覧:\n"
        for i, ins in enumerate(insights, 1):
            result += f"{i}. [{ins.category}] {ins.content} (重要度: {ins.importance}/5)\n"
        return result
    except Exception as e:
        return f"知見の取得に失敗しました: {e}"

@tool
def create_task_tool(title: str, due_date: str = "", priority: int = 0, description: str = "") -> str:
    """TODOタスク（やるべきこと・課題・アクションアイテム）を新しく作成します。
    
    引数:
    - title: タスクのタイトル (例: '経費精算を提出する', '設計書レビュー')
    - due_date: 期限 (任意。ISO8601形式 'YYYY-MM-DD' または 'YYYY-MM-DDTHH:MM:SS')
    - priority: 優先度 (0: なし, 1: 低, 2: 中, 3: 高)
    - description: 詳細メモ・手順など（任意）
    """
    try:
        due_ms = None
        if due_date:
            try:
                if "T" in due_date:
                    dt = datetime.fromisoformat(due_date.replace("Z", ""))
                else:
                    dt = datetime.strptime(due_date, "%Y-%m-%d")
                due_ms = int(dt.timestamp() * 1000)
            except Exception:
                pass
                
        task = database.Task(
            title=title,
            description=description,
            due_date=due_ms,
            priority=priority,
            status="todo"
        )
        task_id = database.create_task(task)
        due_info = f" (期限: {due_date})" if due_date else ""
        return f"タスク「{title}」{due_info}(ID: {task_id}) をTODOリストに登録しました！"
    except Exception as e:
        return f"タスクの作成に失敗しました: {e}"

@tool
def list_tasks_tool(status: str = "todo") -> str:
    """TODOタスクの一覧を取得します。
    
    引数:
    - status: 取得するタスクの状態 ('todo': 未完了, 'completed': 完了済み, 'all': すべて)
    """
    try:
        query_status = None if status == "all" else (status if status in ("todo", "in_progress", "completed") else None)
        tasks = database.get_tasks(status=query_status, limit=30)
        if not tasks:
            return "現在、該当するTODOタスクはありません。"
            
        pri_labels = {0: "なし", 1: "低", 2: "中", 3: "高 🔥"}
        result = "📋 TODOタスク一覧:\n"
        for t in tasks:
            due_str = ""
            if t.due_date:
                dt = datetime.fromtimestamp(t.due_date / 1000)
                due_str = f" [期日: {dt.strftime('%Y/%m/%d')}]"
            pri_str = f" [優先度: {pri_labels.get(t.priority, 'なし')}]" if t.priority > 0 else ""
            status_icon = "✅ " if t.status == "completed" else "🔲 "
            result += f"- {status_icon}ID:{t.id} {t.title}{due_str}{pri_str}\n"
        return result
    except Exception as e:
        return f"タスクの取得に失敗しました: {e}"

@tool
def complete_task_tool(task_id: int) -> str:
    """指定されたIDのTODOタスクを完了（完了済みにマーク）します。
    
    引数:
    - task_id: 完了にするタスクのID
    """
    try:
        success = database.complete_task(task_id)
        if success:
            return f"タスク(ID: {task_id}) を完了にしました！お疲れ様でした ✨"
        else:
            return f"タスク(ID: {task_id}) が見つかりませんでした。"
    except Exception as e:
        return f"タスク完了処理に失敗しました: {e}"


