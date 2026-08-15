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
import urllib.request
import urllib.error

def ask_approval(agent_name: str, command: str, summary: str, details: str = "", timeout: int = 180, port: int = 8765) -> dict:
    url = f"http://localhost:{port}/api/agent/ask"
    payload = {
        "agent_name": agent_name,
        "command": command,
        "summary": summary,
        "details": details,
        "timeout": timeout,
        "wait_decision": True
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST"
    )
    
    print(f"🤖 [{agent_name}] スマホDesk Petへ承認要請を送信中...")
    print(f"   📋 概要: {summary}")
    print(f"   💻 コマンド: {command}")
    print(f"   ⏳ スマホでのタップを待機しています（最大 {timeout} 秒）...")
    
    try:
        with urllib.request.urlopen(req, timeout=timeout + 5) as res:
            res_data = json.loads(res.read().decode("utf-8"))
            return res_data
    except urllib.error.URLError as e:
        print(f"❌ [Agent Bridge Error] ネオ秘書くんローカルサーバー (ポート{port}) に接続できません: {e}", file=sys.stderr)
        return {"status": "error", "decision": "unreachable", "message": str(e)}
    except Exception as e:
        print(f"❌ [Agent Bridge Error] 予期せぬエラー: {e}", file=sys.stderr)
        return {"status": "error", "decision": "error", "message": str(e)}

def main():
    parser = argparse.ArgumentParser(description="ネオ秘書くん Agent Bridge CLI クライアント")
    parser.add_argument("--agent", default="Codex", help="エージェント名 (例: Codex, Claude Code, Antigravity)")
    parser.add_argument("--cmd", required=True, help="実行するコマンド文字列")
    parser.add_argument("--summary", default="", help="コマンドの目的・概要")
    parser.add_argument("--details", default="", help="詳細な説明やリスク")
    parser.add_argument("--timeout", type=int, default=180, help="タイムアウト秒数")
    parser.add_argument("--port", type=int, default=8765, help="Agent Bridge Hub ポート番号")
    
    args = parser.parse_args()
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
