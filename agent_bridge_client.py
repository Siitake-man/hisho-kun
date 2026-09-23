#!/usr/bin/env python3
"""
ネオ秘書くん - Agent Bridge Client (agent_bridge_client.py)

Codex, Claude Code, Antigravity, Cursor, Aider 等のコーディングエージェントや
シェルスクリプトから呼び出し、スマホDesk Pet端末へ「コマンド実行承認要請」を送信して
スマホ側でのワンタップ判定（承認/拒否/説明要求）を受け取るCLIクライアント。

使用例:
  python agent_bridge_client.py --agent "Codex" --cmd "git push origin main" --summary "GitHubへのプッシュ許可"
"""

import sys
import json
import argparse
import time
import urllib.request
import urllib.error
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

# CLIツールとしてのログ設定（stdoutを汚さず stderr へ出力）
logger = logging.getLogger("agent_bridge_client")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)

# ハブの待受ポートは sync_config を唯一の情報源とする（P1-2: ベタ書き禁止）
from sync_config import SERVER_PORT

# ローカル同期サーバーのBearer認証トークン (.sync_token)
import app_paths

# 🛡️ P0-4 (2026-09-23 / ADR-2): マスタートークンはデータ境界 (非同期領域) を正とする。
SYNC_TOKEN_FILE = app_paths.get_sync_token_path()

# 移行過渡期の互換読取先 (旧配置: リポジトリ/exe 直下)。
# migrate_legacy_data() 完了までの間、旧ファイルしか無い環境でも
# Agent Bridge (MCPツール) が停止しないための読み取り専用フォールバック。
_LEGACY_SYNC_TOKEN_FILE = app_paths.get_app_root() / app_paths.SYNC_TOKEN_FILENAME


def _candidate_token_files() -> List[Path]:
    """トークン読み取りの候補ファイル一覧を優先順に返す。

    Returns:
        List[Path]: データルート (正) → 旧配置 (互換) の順。
    """
    candidates = [SYNC_TOKEN_FILE]
    if _LEGACY_SYNC_TOKEN_FILE != SYNC_TOKEN_FILE:
        candidates.append(_LEGACY_SYNC_TOKEN_FILE)
    return candidates


def get_sync_token() -> str:
    """ローカル同期サーバー用のBearerトークン (.sync_token) を読み込む。

    読み取り先はデータルート (P0-4 / ADR-2)。移行過渡期に限り旧配置
    (アプリルート直下) も読み取り専用フォールバックとして参照し、
    その場合は警告ログで境界違反運用の継続を可視化する。

    書き込み中の競合を避けるため、空文字列取得時は最大3回リトライする。
    ファイルが存在しない場合の空文字列返却は正常動作（ペアリング前）。

    Returns:
        str: トークン文字列。ファイル未作成の場合は空文字列。
    """
    for token_file in _candidate_token_files():
        for attempt in range(3):
            try:
                if token_file.exists():
                    token = token_file.read_text(encoding="utf-8").strip()
                    if token:
                        if token_file == _LEGACY_SYNC_TOKEN_FILE:
                            logger.warning(
                                "⚠️ 旧配置の .sync_token を互換読み取り中です "
                                f"(P0-4/ADR-2 の移行未完了。アプリを起動して移行してください): {token_file}"
                            )
                        return token
                    # 空文字 → 競合の可能性。少し待ってリトライ
                    if attempt < 2:
                        time.sleep(0.05)
                        continue
            except Exception as e:
                # 第1候補の読取失敗で第2候補（旧配置）を放棄しない (可用性優先・Fail-Safe)
                logger.warning(f".sync_token の読み込みに失敗しました (次候補を試行): {e}")
                break
    return ""

def resolve_hub_port(explicit: Optional[int] = None) -> int:
    """Agent Bridge Hub の待受ポートを解決する。

    Args:
        explicit: 呼び出し元が明示指定したポート。
            未指定(None)／0以下／65535超／数値でない値は無視し、sync_config の値を使う。

    Returns:
        int: 使用するポート番号（`sync_config.SERVER_PORT` が唯一の情報源）。

    Notes:
        P1-2 (2026-09-16): 旧実装は既定ポートをベタ書きしていたため、
        待受ポートを変更すると Agent Bridge 連携（承認要請・質問・通知）が
        全滅していた。設定は sync_config へ一元化する。
    """
    if isinstance(explicit, int) and not isinstance(explicit, bool) and 1 <= explicit <= 65535:
        return explicit
    return SERVER_PORT


def _post_to_hub(path: str, payload: Dict[str, Any], timeout: int = 185, port: Optional[int] = None) -> Dict[str, Any]:
    """ネオ秘書くんローカル同期サーバーのAPIエンドポイントにJSON POSTリクエストを送信する共通ヘルパー。

    全API呼び出し（承認要請・質問・通知）はこの関数を経由することで、
    urllib.request.Request の構築とBearer認証ヘッダー付与のコード重複を排除する。

    Args:
        path (str): APIパス（例: '/api/agent/ask', '/api/agent/notify'）。
        payload (Dict[str, Any]): POSTするJSONペイロード。
        timeout (int, optional): タイムアウト秒数。 Defaults to 185（180+5バッファ）。
        port (Optional[int]): サーバーポート番号。省略時は sync_config.SERVER_PORT。

    Returns:
        Dict[str, Any]: レスポンスJSON辞書。エラー時は status=error を含む。
    """
    port = resolve_hub_port(port)
    url = f"http://localhost:{port}{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {get_sync_token()}"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.URLError as e:
        logger.error(f"ネオ秘書くんローカルサーバー (ポート{port}) に接続できません: {e}")
        return {"status": "error", "decision": "unreachable", "message": str(e)}
    except Exception as e:
        logger.error(f"予期せぬエラー: {e}")
        return {"status": "error", "decision": "error", "message": str(e)}


def ask_approval(agent_name: str, command: str, summary: str, details: str = "", timeout: int = 180, port: Optional[int] = None) -> dict:
    payload = {
        "agent_name": agent_name,
        "command": command,
        "summary": summary,
        "details": details,
        "timeout": timeout,
        "wait_decision": True
    }

    print(f"🤖 [{agent_name}] スマホDesk Petへ承認要請を送信中...")
    print(f"   📋 概要: {summary}")
    print(f"   💻 コマンド: {command}")
    print(f"   ⏳ スマホでのタップを待機しています（最大 {timeout} 秒）...")

    return _post_to_hub("/api/agent/ask", payload, timeout=timeout + 5, port=port)

def ask_question_api(agent_name: str, question: str, choices: Optional[List[str]] = None, details: str = "", timeout: int = 180, port: Optional[int] = None) -> dict:
    payload = {
        "agent_name": agent_name,
        "question": question,
        "choices": choices or [],
        "details": details,
        "timeout": timeout,
        "wait_decision": True
    }

    print(f"🤖 [{agent_name}] スマホDesk Petへ質問・確認を送信中...")
    print(f"   ❓ 質問: {question}")
    if choices:
        print(f"   🔘 選択肢: {', '.join(choices)}")
    print(f"   ⏳ スマホまたはPCでの回答を待機しています（最大 {timeout} 秒）...")

    return _post_to_hub("/api/agent/ask_input", payload, timeout=timeout + 5, port=port)

def notify_event(agent_name: str, title: str, message: str = "", details: str = "", reaction: str = "celebrate", port: Optional[int] = None) -> dict:
    payload = {
        "agent_name": agent_name,
        "title": title,
        "message": message,
        "details": details,
        "reaction": reaction
    }
    return _post_to_hub("/api/agent/notify", payload, timeout=10, port=port)

def main():
    parser = argparse.ArgumentParser(description="ネオ秘書くん Agent Bridge CLI クライアント")
    parser.add_argument("--agent", default="Codex", help="エージェント名 (例: Codex, Claude Code, Antigravity)")
    parser.add_argument("--cmd", help="実行するコマンド文字列（承認要請時）")
    parser.add_argument("--question", help="ユーザーへの質問・確認メッセージ")
    parser.add_argument("--choices", nargs="*", help="選択肢一覧 (例: --choices 'A案: 〇〇' 'B案: △△')")
    parser.add_argument("--notify", help="作業完了通知メッセージ")
    parser.add_argument("--title", default="タスク完了", help="通知のタイトル")
    parser.add_argument("--reaction", default="celebrate", help="ペットのリアクション (celebrate, happy, care等)")
    parser.add_argument("--summary", default="", help="コマンドの目的・概要")
    parser.add_argument("--details", default="", help="詳細な説明やリスク・成果物サマリ")
    parser.add_argument("--timeout", type=int, default=180, help="タイムアウト秒数")
    parser.add_argument("--port", type=int, default=None, help="Agent Bridge Hub ポート番号（省略時は sync_config.SERVER_PORT）")
    
    args = parser.parse_args()
    
    # 1. 質問・確認モード
    if args.question:
        result = ask_question_api(
            agent_name=args.agent,
            question=args.question,
            choices=args.choices,
            details=args.details,
            timeout=args.timeout,
            port=args.port
        )
        if result.get("status") == "error":
            logger.error(f"サーバー処理エラー: {result.get('message')}")
            print(f"\n❌ [Agent Bridge Error] サーバー処理エラー: {result.get('message')}", file=sys.stderr)
            sys.exit(5)
        decision = str(result.get("decision", "unknown")).lower().strip()
        answer = result.get("answer", "")
        if decision in ("answered", "approve", "approved"):
            logger.info(f"スマホから【回答】を受信: 『{answer}』")
            print(f"\n🎉 [Agent Bridge] ✓ スマホから【回答】を受信しました: 『{answer}』")
            sys.exit(0)
        elif decision in ("expired", "timeout"):
            logger.info("待機タイムアウト")
            print("\n⏰ [Agent Bridge] ⌛ 待機タイムアウト（PCまたは他で操作継続）。")
            sys.exit(3)
        else:
            logger.info(f"応答: {decision} ({answer})")
            print(f"\n💬 [Agent Bridge] 応答: {decision} ({answer})")
            sys.exit(0)

    # 2. 作業完了通知モード
    if args.notify:
        result = notify_event(
            agent_name=args.agent,
            title=args.title,
            message=args.notify,
            details=args.details,
            reaction=args.reaction,
            port=args.port
        )
        if result.get("status") == "success":
            logger.info(f"ペットへ作業完了通知を送信: {args.agent}: {args.notify}")
            print(f"🎉 [Agent Bridge Notify] ペットへ作業完了通知を送信しました！（{args.agent}: {args.notify}）")
            sys.exit(0)
        else:
            logger.error(f"通知送信失敗: {result.get('message')}")
            print(f"❌ [Agent Bridge Error] 通知送信失敗: {result.get('message')}", file=sys.stderr)
            sys.exit(1)

    # 承認要請モード
    if not args.cmd:
        parser.print_help()
        sys.exit(1)
        
    summary = args.summary if args.summary else f"『{args.cmd}』の実行許可"
    
    result = ask_approval(
        agent_name=args.agent,
        command=args.cmd,
        summary=summary,
        details=args.details,
        timeout=args.timeout,
        port=args.port
    )
    
    if result.get("status") == "error":
        err_msg = result.get("message", "不明なエラー")
        print(f"\n❌ [Agent Bridge Error] サーバー処理エラー: {err_msg}", file=sys.stderr)
        sys.exit(5)

    raw_decision = str(result.get("decision", "unknown")).lower().strip()
    
    if raw_decision in ("approve", "approved"):
        print("\n🎉 [Agent Bridge] ✓ スマホから【承認 (Approve)】を受信しました！コマンドを実行します。")
        sys.exit(0)
    elif raw_decision in ("reject", "rejected"):
        print("\n🛑 [Agent Bridge] ✕ スマホから【拒否 (Reject)】を受信しました。処理を中断します。")
        sys.exit(1)
    elif raw_decision in ("explain", "explained"):
        msg = result.get("message", "")
        print(f"\n💬 [Agent Bridge] ❓ スマホから【詳しい説明 (Explain)】を求められました: {msg}")
        sys.exit(2)
    elif raw_decision in ("expired", "timeout"):
        print("\n⏰ [Agent Bridge] ⌛ 承認タイムアウト（応答なし）のため処理を中断します。")
        sys.exit(3)
    elif raw_decision == "unreachable":
        print("\n❌ [Agent Bridge] ローカルサーバーが起動していません。`python main.py` を起動してください。")
        sys.exit(5)
    else:
        print(f"\n⚠️ [Agent Bridge] 不明なステータス: {raw_decision} (レスポンス: {result})")
        sys.exit(4)

if __name__ == "__main__":
    main()
