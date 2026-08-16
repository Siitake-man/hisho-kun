#!/usr/bin/env python3
"""
ネオ秘書くん - MCP (Model Context Protocol) サーバー (hisho_mcp_server.py)

2026年7月28日正式リリース最新仕様（Stateless / MRTR対応）に完全準拠。
Antigravity, Claude Code, Cursor, Codex 等のコーディングエージェントへ
「スマホDesk Pet承認要請 (Agent Bridge)」「MentisDB長期知見 (user_insights)」
「TODOタスク手帳同期」を標準プロトコル経由で提供します。
"""

import sys
import os
import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional

# プロジェクトルートパスの設定
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import database

# ロギング設定（stdio通信を汚さないため stderr に出力）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [MCP] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("hisho_mcp_server")

# ポート番号（ネオ秘書くんローカル同期サーバー）
BRIDGE_HUB_PORT = 8765


# =============================================================================
# 1. コアロジック関数（Tools / Resources 実装）
# =============================================================================

def execute_ask_human_approval(
    command: str,
    summary: str = "",
    details: str = "",
    timeout_sec: int = 180,
    agent_name: str = "Coding Agent"
) -> Dict[str, Any]:
    """スマホDesk Pet端末へコマンド実行の承認要請を送信し、ワンタップ判定を受け取ります。

    Args:
        command (str): 実行予定のコマンド文字列。
        summary (str, optional): コマンドの目的・概要。 Defaults to "".
        details (str, optional): 詳細な説明や想定リスク。 Defaults to "".
        timeout_sec (int, optional): 待機タイムアウト秒数。 Defaults to 180.
        agent_name (str, optional): エージェント名。 Defaults to "Coding Agent".

    Returns:
        Dict[str, Any]: 判定結果 (status, decision, message)
    """
    effective_summary = summary if summary.strip() else f"『{command}』の実行許可"
    url = f"http://localhost:{BRIDGE_HUB_PORT}/api/agent/ask"
    payload = {
        "agent_name": agent_name,
        "command": command,
        "summary": effective_summary,
        "details": details,
        "timeout": timeout_sec,
        "wait_decision": True
    }

    logger.info(f"スマホへ承認要請を送信: {command} (概要: {effective_summary})")

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout_sec + 5) as res:
            res_data = json.loads(res.read().decode("utf-8"))
            decision = res_data.get("decision", "unknown")
            logger.info(f"スマホからの判定を受信: {decision}")
            return {
                "status": "success",
                "decision": decision,
                "command": command,
                "message": res_data.get("message", ""),
                "approved": decision in ("approve", "approved")
            }
    except urllib.error.URLError as e:
        err_msg = f"ネオ秘書くんローカルサーバー (ポート{BRIDGE_HUB_PORT}) に接続できません: {e}"
        logger.warning(err_msg)
        return {
            "status": "error",
            "decision": "unreachable",
            "approved": False,
            "message": "ネオ秘書くん（python main.py）が起動していないため、スマホと通信できませんでした。"
        }
    except Exception as e:
        logger.error(f"承認要請エラー: {e}")
        return {
            "status": "error",
            "decision": "error",
            "approved": False,
            "message": str(e)
        }


def execute_notify_task_completed(
    title: str = "作業完了",
    message: str = "",
    agent_name: str = "Codex"
) -> Dict[str, Any]:
    """作業完了をペットとスマホDesk Petへ通知し、大喜び（celebrate）させます。"""
    url = f"http://localhost:{BRIDGE_HUB_PORT}/api/agent/notify"
    payload = {
        "agent_name": agent_name,
        "title": title,
        "message": message,
        "reaction": "celebrate"
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            res_data = json.loads(res.read().decode("utf-8"))
            return {
                "status": "success",
                "message": f"ペットとスマホへ作業完了通知を送りました（{agent_name}: {title}）"
            }
    except Exception as e:
        return {"status": "error", "message": f"通知送信失敗: {e}"}


def execute_notify_user_input_needed(
    question: str,
    choices: str = "",
    agent_name: str = "Codex",
    timeout_sec: int = 180
) -> Dict[str, Any]:
    """ユーザーへの確認・入力待ちをペットとスマホDesk Petへ送信し、選択肢または自由回答を受け取ります。"""
    url = f"http://localhost:{BRIDGE_HUB_PORT}/api/agent/ask_input"
    parsed_choices = [c.strip() for c in choices.split(",") if c.strip()] if isinstance(choices, str) and choices else (choices if isinstance(choices, list) else [])
    payload = {
        "agent_name": agent_name,
        "question": question,
        "choices": parsed_choices,
        "timeout": timeout_sec,
        "wait_decision": True
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout_sec + 5) as res:
            res_data = json.loads(res.read().decode("utf-8"))
            decision = res_data.get("decision", "unknown")
            answer = res_data.get("answer", "")
            return {
                "status": "success",
                "decision": decision,
                "answer": answer,
                "message": f"スマホまたはPCから回答を受信しました: 『{answer}』" if answer else f"ステータス: {decision}"
            }
    except Exception as e:
        return {"status": "error", "message": f"質問送信失敗: {e}"}


def execute_create_task(
    title: str,
    priority: str = "medium",
    memo: str = ""
) -> Dict[str, Any]:
    """秘書くんのTODO手帳に新しいタスクを登録します。

    Args:
        title (str): タスク名。
        priority (str, optional): 優先度 ('high', 'medium', 'low')。 Defaults to 'medium'.
        memo (str, optional): 詳細メモ。 Defaults to "".

    Returns:
        Dict[str, Any]: 登録結果 (status, task_id, message)
    """
    try:
        task_id = database.create_task(title=title, priority=priority, memo=memo)
        logger.info(f"TODOタスクを作成しました: ID={task_id}, Title='{title}'")
        return {
            "status": "success",
            "task_id": task_id,
            "title": title,
            "priority": priority,
            "message": f"TODO手帳にタスク「{title}」(ID: {task_id}) を登録しました。"
        }
    except Exception as e:
        logger.error(f"タスク作成エラー: {e}")
        return {"status": "error", "message": f"タスク作成に失敗しました: {e}"}


def execute_remember_boss_insight(
    category: str,
    content: str,
    importance: int = 2
) -> Dict[str, Any]:
    """ボスの制約・好み・作業習慣を MentisDB (user_insights) に永続化します。

    Args:
        category (str): 知見カテゴリ ('制約', '好み', '習慣', '開発方針' 等)。
        content (str): 知見の内容。
        importance (int, optional): 重要度 (1: 低, 2: 中, 3: 高)。 Defaults to 2.

    Returns:
        Dict[str, Any]: 保存結果
    """
    try:
        insight_id = database.add_user_insight(
            category=category,
            content=content,
            importance=importance
        )
        logger.info(f"MentisDBに知見を記憶しました: ID={insight_id}, Cat={category}")
        return {
            "status": "success",
            "insight_id": insight_id,
            "category": category,
            "content": content,
            "message": f"ボスの知見（{category}: {content}）をMentisDBに永続化しました。"
        }
    except Exception as e:
        logger.error(f"知見記憶エラー: {e}")
        return {"status": "error", "message": f"知見の記憶に失敗しました: {e}"}


def execute_get_boss_insights(
    category: str = "",
    limit: int = 10
) -> List[Dict[str, Any]]:
    """MentisDBからボスの制約・好み・方針を検索・取得します。

    Args:
        category (str, optional): カテゴリフィルタ。 Defaults to "".
        limit (int, optional): 取得件数上限。 Defaults to 10.

    Returns:
        List[Dict[str, Any]]: 知見リスト
    """
    try:
        insights = database.get_user_insights(
            category=category if category.strip() else None,
            limit=limit
        )
        return [
            {
                "id": ins.id,
                "category": ins.category,
                "content": ins.content,
                "importance": ins.importance,
                "created_at": ins.created_at
            }
            for ins in insights
        ]
    except Exception as e:
        logger.error(f"知見取得エラー: {e}")
        return []


def execute_get_pending_tasks(limit: int = 20) -> List[Dict[str, Any]]:
    """秘書くんのTODO手帳から未完了のタスク一覧を取得します。

    Args:
        limit (int, optional): 取得件数上限。 Defaults to 20.

    Returns:
        List[Dict[str, Any]]: 未完了タスク一覧
    """
    try:
        tasks = database.get_tasks(is_completed=False, limit=limit)
        return [
            {
                "id": t.id,
                "title": t.title,
                "priority": t.priority,
                "due_date": t.due_date,
                "memo": t.memo,
                "created_at": t.created_at
            }
            for t in tasks
        ]
    except Exception as e:
        logger.error(f"未完了タスク取得エラー: {e}")
        return []


def execute_complete_task(task_id: int) -> Dict[str, Any]:
    """指定したIDのTODOタスクを完了状態にします。

    Args:
        task_id (int): 完了にするタスクのID。

    Returns:
        Dict[str, Any]: 完了処理結果
    """
    try:
        success = database.complete_task(task_id)
        if success:
            logger.info(f"タスクを完了にしました: ID={task_id}")
            return {
                "status": "success",
                "task_id": task_id,
                "message": f"タスク(ID: {task_id})を完了にしました！✨"
            }
        else:
            return {
                "status": "error",
                "task_id": task_id,
                "message": f"タスク(ID: {task_id})が見つかりませんでした。"
            }
    except Exception as e:
        logger.error(f"タスク完了エラー: {e}")
        return {"status": "error", "message": f"タスク完了処理に失敗しました: {e}"}


def execute_create_calendar_event(
    title: str,
    start_time_iso: str,
    end_time_iso: Optional[str] = None,
    description: str = ""
) -> Dict[str, Any]:
    """秘書くんの手帳カレンダーに新しい予定を登録します。

    Args:
        title (str): 予定のタイトル。
        start_time_iso (str): 開始日時 (ISO 8601形式、例: '2026-08-16T15:00:00')。
        end_time_iso (str, optional): 終了日時。省略時は開始の1時間後。
        description (str, optional): 予定の詳細メモ。

    Returns:
        Dict[str, Any]: 予定作成結果
    """
    try:
        start_dt = datetime.fromisoformat(start_time_iso)
        start_ts = int(start_dt.timestamp() * 1000)
        
        if end_time_iso:
            end_dt = datetime.fromisoformat(end_time_iso)
            end_ts = int(end_dt.timestamp() * 1000)
        else:
            end_ts = start_ts + (60 * 60 * 1000)  # 1時間後
            
        event = database.Event(
            title=title,
            description=description,
            start_time=start_ts,
            end_time=end_ts
        )
        event_id = database.create_event(event)
        logger.info(f"カレンダー予定を作成しました: ID={event_id}, Title='{title}'")
        return {
            "status": "success",
            "event_id": event_id,
            "title": title,
            "start_time": start_time_iso,
            "message": f"手帳カレンダーに予定「{title}」(ID: {event_id}) を登録しました！📅"
        }
    except Exception as e:
        logger.error(f"予定作成エラー: {e}")
        return {"status": "error", "message": f"予定作成に失敗しました: {e}"}


# =============================================================================
# 2. FastMCP サーバー定義 (2026-07-28 仕様完全準拠)
# =============================================================================

def run_fastmcp_server() -> None:
    """FastMCPフレームワークを用いたサーバー起動"""
    from mcp.server.fastmcp import FastMCP

    # 2026-07-28 仕様準拠の FastMCP サーバー初期化
    mcp = FastMCP(
        name="neo_hisho_bridge",
        instructions=(
            "ネオ秘書くん Agent Bridge ＆ MentisDB サーバー。\n"
            "危険なコマンド実行時は `ask_human_approval` でスマホDesk Petに承認を求めてください。\n"
            "ボスの制約や好みは `hisho://insights` リソースおよび `remember_boss_insight` を活用してください。"
        )
    )

    # ------------------ Tools ------------------
    @mcp.tool(description="机の上の古いスマホDesk Pet端末へコマンド実行の承認要請を送信し、ボスのワンタップ判定（承認/拒否）を受け取ります。")
    def ask_human_approval(command: str, summary: str = "", details: str = "", timeout_sec: int = 180, agent_name: str = "Codex") -> Dict[str, Any]:
        """スマホDesk Pet端末へコマンド実行の承認を求めます。"""
        return execute_ask_human_approval(command, summary, details, timeout_sec, agent_name)

    @mcp.tool(description="コーディング作業やタスクが完了した際に、PCペットとスマホDesk Petへ完了通知を送り、大喜び（celebrate）リアクションさせます。")
    def notify_task_completed(title: str = "タスク完了", message: str = "", agent_name: str = "Codex") -> Dict[str, Any]:
        """作業完了をペットとスマホへ通知します。"""
        return execute_notify_task_completed(title, message, agent_name)

    @mcp.tool(description="ユーザーへの質問・選択肢の確認・入力待ちが発生した際に、ペットとスマホDesk Petへ通知してアラート呼び出し（alarm_ask）を行います。")
    def notify_user_input_needed(question: str, choices: str = "", agent_name: str = "Codex") -> Dict[str, Any]:
        """ユーザー入力待機をペットとスマホへ通知します。"""
        return execute_notify_user_input_needed(question, choices, agent_name)

    @mcp.tool(description="秘書くんのTODO手帳に新しいタスクを登録します。作業中に見つけた課題の記録に使用してください。")
    def create_task(title: str, priority: str = "medium", memo: str = "") -> Dict[str, Any]:
        """TODO手帳にタスクを登録します。"""
        return execute_create_task(title, priority, memo)

    @mcp.tool(description="指定したIDのTODOタスクを完了状態（完了済み）にします。")
    def complete_task(task_id: int) -> Dict[str, Any]:
        """TODOタスクを完了にします。"""
        return execute_complete_task(task_id)

    @mcp.tool(description="秘書くんの手帳カレンダーに新しい予定を登録します。")
    def create_calendar_event(title: str, start_time_iso: str, end_time_iso: Optional[str] = None, description: str = "") -> Dict[str, Any]:
        """手帳カレンダーに予定を登録します。"""
        return execute_create_calendar_event(title, start_time_iso, end_time_iso, description)

    @mcp.tool(description="ボスの制約・好み・作業習慣・開発ルールをMentisDB長期記憶に永続化します。")
    def remember_boss_insight(category: str, content: str, importance: int = 2) -> Dict[str, Any]:
        """ボスの知見・制約をMentisDBに記憶します。"""
        return execute_remember_boss_insight(category, content, importance)

    @mcp.tool(description="MentisDBからボスの制約や好みを検索・取得します。")
    def get_boss_insights(category: str = "", limit: int = 10) -> List[Dict[str, Any]]:
        """ボスの知見を検索・取得します。"""
        return execute_get_boss_insights(category, limit)

    # ------------------ Resources (Cacheable) ------------------
    @mcp.resource("hisho://insights", description="ボスの制約条件（平日1-2h制約等）、好み、開発方針の全知見リスト")
    def resource_insights() -> str:
        """ボスの制約と知見をJSON文字列で返します。"""
        insights = execute_get_boss_insights(limit=50)
        return json.dumps(insights, ensure_ascii=False, indent=2)

    @mcp.resource("hisho://tasks/pending", description="現在未完了のTODOタスク一覧")
    def resource_pending_tasks() -> str:
        """未完了タスク一覧をJSON文字列で返します。"""
        tasks = execute_get_pending_tasks(limit=30)
        return json.dumps(tasks, ensure_ascii=False, indent=2)

    # ------------------ Prompts ------------------
    @mcp.prompt(name="safety_check_workflow", description="破壊的コマンド実行前のリスク自己診断とスマホ承認準備プロンプト")
    def prompt_safety_check(command: str) -> str:
        return (
            f"あなたは安全第一のAIアシスタントです。次のコマンドを実行しようとしています:\n"
            f"```bash\n{command}\n```\n"
            f"1. このコマンドがファイル削除・強制上書き・リモートプッシュ等の破壊的影響を持つか評価してください。\n"
            f"2. 危険性がある場合は、勝手に実行せず `ask_human_approval` ツールを呼び出してボスのスマホへ承認要請を送ってください。"
        )

    logger.info("FastMCP サーバーを stdio トランスポートで起動します...")
    mcp.run(transport="stdio")


# =============================================================================
# 3. フォールバック JSON-RPC 2.0 stdio サーバー (mcpパッケージ未導入時)
# =============================================================================

def run_fallback_jsonrpc_server() -> None:
    """FastMCP未導入環境用の標準 JSON-RPC 2.0 stdio サーバー"""
    logger.info("FastMCPパッケージ未検出のため、フォールバック JSON-RPC 2.0 stdio サーバーを起動します...")

    TOOLS_SCHEMA = [
        {
            "name": "ask_human_approval",
            "description": "机の上のスマホDesk Petへコマンド実行の承認要請を送信し、ワンタップ判定を受け取ります。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "実行するコマンド文字列"},
                    "summary": {"type": "string", "description": "コマンドの概要・目的"},
                    "details": {"type": "string", "description": "詳細やリスク"},
                    "timeout_sec": {"type": "integer", "default": 180, "description": "タイムアウト秒数"},
                    "agent_name": {"type": "string", "default": "Codex", "description": "エージェント名"}
                },
                "required": ["command"]
            }
        },
        {
            "name": "notify_task_completed",
            "description": "作業やタスクが完了した際に、ペットとスマホDesk Petへ通知して大喜びさせます。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "default": "タスク完了", "description": "通知タイトル"},
                    "message": {"type": "string", "default": "", "description": "完了メッセージ・詳細"},
                    "agent_name": {"type": "string", "default": "Codex", "description": "エージェント名"}
                }
            }
        },
        {
            "name": "notify_user_input_needed",
            "description": "ユーザーへの質問や確認待ちが発生した際に、ペットとスマホへ通知して呼び出します。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "確認したい質問内容"},
                    "choices": {"type": "string", "default": "", "description": "選択肢一覧"},
                    "agent_name": {"type": "string", "default": "Codex", "description": "エージェント名"}
                },
                "required": ["question"]
            }
        },
        {
            "name": "create_task",
            "description": "秘書くんのTODO手帳にタスクを登録します。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "タスク名"},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"], "default": "medium"},
                    "memo": {"type": "string", "description": "詳細メモ"}
                },
                "required": ["title"]
            }
        },
        {
            "name": "remember_boss_insight",
            "description": "ボスの制約・好みをMentisDBに記憶します。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "カテゴリ"},
                    "content": {"type": "string", "description": "知見内容"},
                    "importance": {"type": "integer", "default": 2, "description": "重要度(1-3)"}
                },
                "required": ["category", "content"]
            }
        },
        {
            "name": "get_boss_insights",
            "description": "MentisDBからボスの知見・制約を取得します。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "default": ""},
                    "limit": {"type": "integer", "default": 10}
                }
            }
        },
        {
            "name": "complete_task",
            "description": "指定したIDのTODOタスクを完了状態にします。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "完了にするタスクID"}
                },
                "required": ["task_id"]
            }
        },
        {
            "name": "create_calendar_event",
            "description": "手帳カレンダーに新しい予定を登録します。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "予定タイトル"},
                    "start_time_iso": {"type": "string", "description": "開始日時 (ISO 8601, 例: 2026-08-16T15:00:00)"},
                    "end_time_iso": {"type": "string", "description": "終了日時 (省略可)"},
                    "description": {"type": "string", "description": "詳細メモ"}
                },
                "required": ["title", "start_time_iso"]
            }
        }
    ]

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line_str = line.strip()
            if not line_str:
                continue

            req = json.loads(line_str)
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})

            # 2026-07-28 仕様: initialize
            if method == "initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2026-07-28",
                        "capabilities": {
                            "tools": {"listChanged": False},
                            "resources": {"subscribe": False, "listChanged": False}
                        },
                        "serverInfo": {
                            "name": "neo_hisho_bridge",
                            "version": "2.0.0"
                        }
                    }
                }
            # tools/list
            elif method == "tools/list":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"tools": TOOLS_SCHEMA}
                }
            # tools/call
            elif method == "tools/call":
                name = params.get("name")
                args = params.get("arguments", {})
                
                if name == "ask_human_approval":
                    res = execute_ask_human_approval(
                        command=args.get("command", ""),
                        summary=args.get("summary", ""),
                        details=args.get("details", ""),
                        timeout_sec=int(args.get("timeout_sec", 180)),
                        agent_name=args.get("agent_name", "Codex")
                    )
                elif name == "notify_task_completed":
                    res = execute_notify_task_completed(
                        title=args.get("title", "タスク完了"),
                        message=args.get("message", ""),
                        agent_name=args.get("agent_name", "Codex")
                    )
                elif name == "notify_user_input_needed":
                    res = execute_notify_user_input_needed(
                        question=args.get("question", ""),
                        choices=args.get("choices", ""),
                        agent_name=args.get("agent_name", "Codex")
                    )
                elif name == "create_task":
                    res = execute_create_task(
                        title=args.get("title", ""),
                        priority=args.get("priority", "medium"),
                        memo=args.get("memo", "")
                    )
                elif name == "complete_task":
                    res = execute_complete_task(
                        task_id=int(args.get("task_id", 0))
                    )
                elif name == "create_calendar_event":
                    res = execute_create_calendar_event(
                        title=args.get("title", ""),
                        start_time_iso=args.get("start_time_iso", ""),
                        end_time_iso=args.get("end_time_iso"),
                        description=args.get("description", "")
                    )
                elif name == "remember_boss_insight":
                    res = execute_remember_boss_insight(
                        category=args.get("category", ""),
                        content=args.get("content", ""),
                        importance=int(args.get("importance", 2))
                    )
                elif name == "get_boss_insights":
                    res = execute_get_boss_insights(
                        category=args.get("category", ""),
                        limit=int(args.get("limit", 10))
                    )
                else:
                    res = {"status": "error", "message": f"未定義のツールです: {name}"}

                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(res, ensure_ascii=False, indent=2)
                            }
                        ]
                    }
                }
            # resources/list
            elif method == "resources/list":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "resources": [
                            {
                                "uri": "hisho://insights",
                                "name": "ボスの制約・知見",
                                "mimeType": "application/json"
                            },
                            {
                                "uri": "hisho://tasks/pending",
                                "name": "未完了タスク一覧",
                                "mimeType": "application/json"
                            }
                        ]
                    }
                }
            # resources/read
            elif method == "resources/read":
                uri = params.get("uri", "")
                if uri == "hisho://insights":
                    content_str = json.dumps(execute_get_boss_insights(limit=50), ensure_ascii=False)
                elif uri == "hisho://tasks/pending":
                    content_str = json.dumps(execute_get_pending_tasks(limit=30), ensure_ascii=False)
                else:
                    content_str = "{}"

                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "contents": [
                            {
                                "uri": uri,
                                "mimeType": "application/json",
                                "text": content_str
                            }
                        ]
                    }
                }
            # ping / notifications
            elif method == "ping":
                resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}
            else:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }

            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()

        except Exception as e:
            logger.error(f"JSON-RPC ループエラー: {e}")


# =============================================================================
# 4. エントリーポイント
# =============================================================================

def main() -> None:
    """サーバー起動エントリーポイント"""
    database.init_db()

    try:
        import mcp.server.fastmcp
        run_fastmcp_server()
    except ImportError:
        logger.info("公式 mcp パッケージが見つからないため、内蔵 JSON-RPC 2.0 stdio サーバーを起動します。")
        run_fallback_jsonrpc_server()


if __name__ == "__main__":
    main()
