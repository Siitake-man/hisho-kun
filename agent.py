"""
ネオ秘書くん - LangGraphエージェントモジュール (agent.py)

LangGraphを用いたステートマシンベースのエージェント定義です。
AIの「頭脳」として機能し、後にGUI(CustomTkinter)と連携します。
"""
import logging
import re
from typing import Annotated, TypedDict, Literal, List
import os
from datetime import datetime

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from dotenv import load_dotenv
from llm_factory import get_llm_factory, is_llm_network_failure, LLM_NETWORK_FALLBACK_TEXT
from command_router import try_route_command
from mcp_manager import get_mcp_manager
from character_manager import get_character_manager
import database

# 環境変数の読み込み (.env ファイルから GOOGLE_API_KEY をロード)
load_dotenv()

# ログ設定（AI_RULES に従い printデバッグを廃止し logging を使用）
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# 1. State Definition (状態の定義)
# =============================================================================
class AgentState(TypedDict):
    """
    エージェントが保持する状態（コンテキスト）の定義。
    LangGraphはこの辞書を各ノードで回し、状態を更新していきます。
    """
    # メッセージ履歴（add_messages により追記されていく）
    messages: Annotated[list[BaseMessage], add_messages]
    
    # 現在のタスク計画
    current_plan: str
    
    # ユーザー承認ステータス (Pending/Approved/Rejected)
    user_approval: str

# =============================================================================
# 2. Tools (エージェントが使える道具)
# =============================================================================
from db_tools import (
    create_event_tool, 
    get_upcoming_events_tool, 
    create_sticky_note_tool,
    remember_user_insight_tool,
    get_user_insights_tool,
    create_task_tool,
    list_tasks_tool,
    complete_task_tool,
    quick_add_task_tool
)
from vision_tools import (
    capture_screen_tool,
    analyze_screen_error_tool
)
from ics_tools import (
    export_calendar_ics_tool
)
from google_workspace_tools import (
    get_google_calendar_events_tool,
    create_google_calendar_event_tool,
    search_gmail_messages_tool
)
from web_tools import (
    fetch_tech_news_tool,
    search_web_free_tool,
    read_webpage_free_tool
)
from webhook_tools import (
    send_calendar_event_to_webhook_tool
)

# AIが使える道具一覧を登録
tools = [
    create_event_tool, 
    get_upcoming_events_tool, 
    create_sticky_note_tool,
    remember_user_insight_tool,
    get_user_insights_tool,
    create_task_tool,
    list_tasks_tool,
    complete_task_tool,
    quick_add_task_tool,
    capture_screen_tool,
    analyze_screen_error_tool,
    export_calendar_ics_tool,
    get_google_calendar_events_tool,
    create_google_calendar_event_tool,
    search_gmail_messages_tool,
    fetch_tech_news_tool,
    search_web_free_tool,
    read_webpage_free_tool,
    send_calendar_event_to_webhook_tool
]
tool_node = ToolNode(tools)

# =============================================================================
# 3. Nodes (処理の単位)
# =============================================================================
def planner_node(state: AgentState):
    """
    ユーザーからの入力を受け取り、どう行動するか（ツールを使うか、そのまま返すか）を考える最初の窓口ノード。
    MentisDB型のユーザー長期知見を自動ロードしてプロンプトに注入します。
    """
    logger.info("Planner Node がユーザー入力を処理中...")
    messages = state.get("messages", [])

    # 直近のユーザー発話を抽出（決定論的コマンドルートの判定に使用）
    last_human_text = ""
    for _msg in reversed(messages):
        if isinstance(_msg, HumanMessage):
            last_human_text = _msg.content if isinstance(_msg.content, str) else ""
            break
    
    # 実際のAI連携 (Multi-LLM Factory) を有効化
    try:
        factory = get_llm_factory()

        # 0. 決定論的コマンドルート: 予定登録などの高信頼指示は LLM 推論を経由せず
        #    確実に実行する（ローカルGGUF等の tool calling 非対応モデルでも動作）
        direct_reply = try_route_command(last_human_text)
        if direct_reply is not None:
            logger.info("コマンドルーターが直接処理しました（LLM推論をスキップ）")
            return {"messages": [AIMessage(content=direct_reply)], "current_plan": "決定論コマンド実行"}
        
        # 1. ユーザーの長期知見（制約・好み・習慣・PJルール）をDBからロード
        insights = database.get_user_insights(min_importance=2, limit=6)
        insights_text = ""
        if insights:
            insights_text = "【あなたが学習・記憶しているボス（ユーザー）の重要知見・ルール】\n"
            for ins in insights:
                insights_text += f"- [{ins.category}] {ins.content} (重要度: {ins.importance}/5)\n"
            insights_text += "※ボスの制約や好みに反する提案は避け、これらに寄り添ったサポートを行ってください。\n\n"

        # 2. 有効化されたMCPツールの動的取得
        mcp_tools = get_mcp_manager().get_dynamic_mcp_tools()
        active_tools = tools + mcp_tools

        # 3. システムプロンプトの動的生成
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        mcp_info = ""
        if mcp_tools:
            mcp_info = f"- 外部MCPツール（{len(mcp_tools)}件）: 有効化された外部サービス連携ツールも活用してください。\n"

        # キャラクターのペルソナシステムプロンプトを注入（キャラ切替でAIの性格が変わる）
        character_prompt = get_character_manager().get_character_system_prompt()

        sys_prompt = (
            f"あなたは有能な専属秘書アシスタント「ネオ秘書くん」です。\n"
            f"現在時刻は {current_time} です。\n\n"
            f"{character_prompt}\n"
            f"{insights_text}"
            f"【行動指針】\n"
            f"1. ユーザーからの指示に対して、与えられたツール（予定作成/取得、TODOタスク作成/取得/完了、付箋作成、知見記憶/参照、画面キャプチャ/エラー解析）を使ってサポートしてください。\n"
            f"2. タスク（やるべきこと）を頼まれたら create_task_tool を使い、確認を求められたら list_tasks_tool を使い、完了時は complete_task_tool を使ってください。「明日18時に資料 #仕事 !3」のような自然言語のクイック入力には quick_add_task_tool（期限・タグ・優先度を自動解析）が便利です。\n"
            f"3. 会話の中でユーザーが自身の生活リズム、制約（NG事項）、好み、作業ルールなどを述べた場合は、自律的に remember_user_insight_tool を呼び出して長期記憶に保存してください。\n"
            f"4. 予定やタスクを尋ねられたら自分で勝手に作らずデータベースから取得し、登録を頼まれたら必ずツールを呼び出して登録を行ってください。\n"
            f"5. ボスから「画面を見て」「エラーが出た」「今何してるかわかる？」と言われた場合は、capture_screen_tool や analyze_screen_error_tool を呼び出して画面を視覚的に確認・解析してください。\n"
            f"{mcp_info}"
        )
        # tool calling 非対応モデル（ローカルGGUF等）では完了を偽って報告しないよう
        # システムプロンプトレベルでも抑制する。
        tool_capable = factory.supports_tool_calling()
        if not tool_capable:
            sys_prompt += (
                "\n【厳守】現在のモデルはツール実行（予定・タスクの登録など）に対応していません。"
                "「登録しました」「作成しました」等の完了報告は絶対に行わず、"
                "実行できない旨を正直に伝えてください。\n"
            )
        sys_msg = SystemMessage(content=sys_prompt)
        
        # 現在選択されているプロバイダ（OpenCode GO / LM Studio / Gemini）のモデルを生成
        llm = factory.create_model()
        if tool_capable:
            bound_llm = llm.bind_tools(active_tools)
        else:
            # ローカルGGUF等: bind_tools が空バインディングを返すためツール無しで直接応答する
            bound_llm = llm
        
        # 過去の会話履歴の先頭にシステムプロンプトを差し込んで推論
        response = bound_llm.invoke([sys_msg] + messages)

        # 誠実性ガード: ツールを一度も実行していないのに完了を表明する幻覚応答を防止
        response = _enforce_response_honesty(response, messages)
        
        # Stateを更新して次のノードへ渡す
        return {"messages": [response], "current_plan": "AI応答生成完了"}
    except Exception as e:
        logger.error(f"LLM API 呼び出しエラー: {e}", exc_info=True)
        if is_llm_network_failure(e):
            # タイムアウト・429等の一時的障害は統一メッセージで縮退通知する
            error_msg = AIMessage(content=LLM_NETWORK_FALLBACK_TEXT)
        else:
            # 例外メッセージをそのままユーザーに表示しない（APIキー等の機密情報漏洩防止）
            error_msg = AIMessage(
                content="【システムエラー】AIとの通信に失敗しました。"
                        ".envファイルのAPIキー設定またはローカルサーバーの稼働状況を確認してください。"
            )
        return {"messages": [error_msg], "current_plan": "エラー発生"}

# =============================================================================
# 4. Routing (条件分岐)
# =============================================================================
# 応答が完了を表明しているとみなすパターン（ツール未実行時に検知した場合は置換対象）
_COMPLETION_CLAIM_RE = re.compile(
    r"(登録しまし|作成しまし|追加しまし|保存しまし|設定しまし|記録しまし|入れまし|作ったよ|登録したよ|完了しました)"
)


def _enforce_response_honesty(response: BaseMessage, prior_messages: List[BaseMessage]) -> BaseMessage:
    """
    ツールを一度も実行していない応答が「登録しました」等の完了を表明していないか検査する。

    ローカルGGUFなど tool calling 非対応モデルは、登録処理を実行していないにも
    かかわらず完了を報告する幻覚を起こす。ここで検知した場合は誠実な応答へ差し替える。

    Args:
        response: Plannerが生成した応答メッセージ。
        prior_messages: このターン開始時点までの会話履歴（ToolMessageの有無判定に使用）。

    Returns:
        BaseMessage: 検証済みの応答メッセージ（問題なければ元のオブジェクト）。
    """
    # ツール呼び出しを伴う応答はこの後実際に実行されるため問題なし
    if getattr(response, "tool_calls", None):
        return response
    # 文字列以外（マルチモーダル）の応答は検査対象外
    if not isinstance(response.content, str) or not response.content.strip():
        return response
    # すでにツール実行結果（ToolMessage）を受けた応答は実績があるため問題なし
    if any(isinstance(m, ToolMessage) for m in prior_messages):
        return response
    if _COMPLETION_CLAIM_RE.search(response.content):
        logger.warning("誠実性ガード発動: ツール未実行の完了表明を検知し応答を差し替えました")
        honest_reply = (
            "【登録は未完了です】申し訳ありません、現在お使いのモデルでは予定・タスクの"
            "登録ツールを実行できていません。\n"
            "・Gemini などのクラウドモデルに切り替えてから再度お伝えください。\n"
            "・または「明日15時に○○を入れて」のように日時を具体的にお伝えいただければ、"
            "決定論コマンドルートで確実に登録します。"
        )
        response.content = honest_reply
    return response


def should_continue(state: AgentState) -> Literal["tools", END]:
    """
    Planner Nodeの後、ツールを呼び出すか、処理を終了するかを判定するルーティング関数。
    """
    messages = state.get("messages", [])
    last_message = messages[-1]
    
    # LLMが「ツールを使いたい（tool_callsがある）」と判断した場合
    # Geminiの場合、last_message.tool_calls がリストで返る
    if hasattr(last_message, "tool_calls") and len(last_message.tool_calls) > 0:
        logger.info(f"ルーティング判定: ツールを呼び出します ({last_message.tool_calls})")
        return "tools"
    
    logger.info("ルーティング判定: 処理を終了 (END) します")
    return END

# =============================================================================
# 5. Graph Construction (グラフの構築)
# =============================================================================
def build_agent_graph():
    """
    エージェントの思考プロセス（ステートマシン）のワークフローを構築します。
    """
    workflow = StateGraph(AgentState)
    
    # ノードをグラフに登録
    workflow.add_node("planner", planner_node)
    workflow.add_node("tools", tool_node)
    
    # 繋がり（エッジ）の定義
    workflow.add_edge(START, "planner") # 開始 -> Planner
    workflow.add_conditional_edges("planner", should_continue) # Planner -> 条件分岐
    workflow.add_edge("tools", "planner") # ツール実行後はまたPlannerに戻す
    
    # 記憶の準備 (MemorySaver を使って会話の文脈を永続化)
    memory = MemorySaver()
    
    # コンパイル（実行可能な状態にする）
    app = workflow.compile(checkpointer=memory)
    return app

# =============================================================================
# 実行テスト
# =============================================================================
if __name__ == "__main__":
    logger.info("=== ネオ秘書くん エージェント単体テスト開始 ===")
    print("=== ネオ秘書くん エージェント単体テスト開始 ===")
    app = build_agent_graph()
    
    config = {"configurable": {"thread_id": "test_thread_01"}}
    user_input = "明後日の15時から1時間、開発会議の予定を入れてください"
    logger.info(f"[Human]: {user_input}")
    print(f"\n[Human]: {user_input}")
    
    initial_state = {"messages": [HumanMessage(content=user_input)]}
    for chunk in app.stream(initial_state, config=config, stream_mode="values"):
        last_message = chunk["messages"][-1]
        if isinstance(last_message, AIMessage):
            logger.info(f"[Agent]: {last_message.content}")
            print(f"[Agent]: {last_message.content}")
    
    logger.info("=== テスト終了 ===")
    print("\n=== テスト終了 ===")
