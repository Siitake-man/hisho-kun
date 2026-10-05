#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - 30秒本命デモ動画 撮影補助スクリプト (tools/demo_30s_recorder.py).

目的:
- Grokレビュー（2026-10-04）が指摘した「30秒本命デモ動画」を一発撮りするための撮影自動化ツール。
- 0秒〜30秒のタイムライン（自律生成 ➔ 危険コマンド停止 ➔ スマホ上部バナー着信 ➔ タップ承認再開 ➔ PC解決による自動消去）を
  寸分狂わず完全シミュレートし、ボスの可処分時間（1分）で完璧なデモ動画を完成させる。

使用方法:
  1. ネオ秘書くんアプリ（main.py または local_sync_server.py）を起動
  2. スマホPWA（またはPC上のミラーリング画面）を開く
  3. OBS等の録画開始ボタンを押す
  4. ターミナルで本スクリプトを実行:
     python tools/demo_30s_recorder.py
  5. スマホ上部にバナーが出たら、[✅ 承認] をワンタップするだけ！
"""

import sys
import time
import json
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import agent_bridge_client
from sync_config import SERVER_PORT


def log_step(seconds: int, tag: str, msg: str, color_code: str = "\033[0m"):
    """タイムコード付きの装飾ログを出力する"""
    ts = f"00:{seconds:02d}"
    print(f"{color_code}[{ts}] [{tag}] {msg}\033[0m", flush=True)


def check_server_health(port: int) -> bool:
    """同期サーバーが起動しているか確認する"""
    token = agent_bridge_client.get_sync_token()
    if not token:
        print("⚠️ .sync_token が見つかりません。ネオ秘書くん本体を先に起動してください。", file=sys.stderr)
        return False
    url = f"http://localhost:{port}/api/link_status"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
        method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=2) as res:
            return res.status == 200
    except Exception:
        return False


def get_latest_pending(port: int) -> dict:
    """現在の承認保留要求を取得する"""
    token = agent_bridge_client.get_sync_token()
    url = f"http://localhost:{port}/api/agent/pending"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
        method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=2) as res:
            data = json.loads(res.read().decode("utf-8"))
            return data.get("pending") or {}
    except Exception:
        return {}


def main():
    port = SERVER_PORT
    print("\n" + "=" * 60)
    print("🎬 ネオ秘書くん v1.2.0 公式30秒本命デモ動画 撮影アシスタント")
    print("=" * 60)

    if not check_server_health(port):
        print(f"❌ ポート {port} でネオ秘書くん同期サーバーが起動していません。")
        print("先に 'python main.py' を起動してから本スクリプトを実行してください。\n")
        return 1

    print("✅ 秘書くん同期サーバー接続確認 OK")
    print("💡 準備: スマホPWAを画面に映し、OBS録画を開始してください。")
    input("👉 Enterキーを押すと【30秒撮影タイムライン】を開始します...")
    print("\n🎥 --- 撮影スタート (00:00) ---")

    # -------------------------------------------------------------------------
    # Cut 1: つかみ (00:00 - 00:05)
    # -------------------------------------------------------------------------
    log_step(0, "AI-Agent", "OpenCode v2.0 autonomous development session active...", "\033[36m")
    time.sleep(1.5)
    log_step(2, "AI-Agent", "Refactoring auth_middleware.ts in demo_project...", "\033[36m")
    time.sleep(1.5)
    log_step(4, "AI-Agent", "Running unit tests: 42 passed in 0.8s.", "\033[32m")
    time.sleep(1.0)

    # -------------------------------------------------------------------------
    # Cut 2: 事件発生 (00:05 - 00:12)
    # -------------------------------------------------------------------------
    log_step(5, "AI-Agent", "⚠️ High-risk command detected: 'npm run deploy --prod'", "\033[33m")
    log_step(5, "DeskPet", "🔔 Sending approval request to smartphone Desk Pet...", "\033[35m")

    # 承認要請を非同期に送信 (wait_decision=False で投げ、スマホにバナーを着信させる)
    ask_payload = {
        "command": "npm run deploy --prod",
        "summary": "本番クラウド環境へのデプロイ実行",
        "agent_name": "OpenCode",
        "risk_level": "prompt",
        "wait_decision": False,
        "timeout": 30
    }
    res = agent_bridge_client._post_to_hub("/api/agent/ask", ask_payload, port=port)
    req_id = res.get("request_id")

    log_step(6, "Smartphone", "📱 上部に【🛡️ 承認要請】バナー着信！(スマホの [✅ 承認] を押してください)", "\033[1;33m")

    # -------------------------------------------------------------------------
    # Cut 3: 救出・ワンタップ承認 (00:07 - 00:20)
    # -------------------------------------------------------------------------
    approved = False
    start_wait = time.time()
    while time.time() - start_wait < 14:
        pending = get_latest_pending(port)
        # 保留要求が消滅した、または完了したか
        if not pending or pending.get("request_id") != req_id:
            approved = True
            break
        time.sleep(0.3)

    elapsed_s = int(time.time() - start_wait) + 6
    if approved:
        log_step(elapsed_s, "DeskPet", "✨ スマホ側でワンタップ承認されました！ (Decision: APPROVED)", "\033[1;32m")
        log_step(elapsed_s + 1, "AI-Agent", "⚡ Resuming autonomous execution! Deploying to cloud...", "\033[36m")
        time.sleep(1.5)
        log_step(elapsed_s + 2, "AI-Agent", "🚀 Deployment successful: https://demo-app.internal/", "\033[32m")
    else:
        log_step(18, "DeskPet", "⏩ (タイムアウト進行: 自動承認フォールバック)", "\033[33m")

    time.sleep(max(0, 20 - (time.time() - start_wait + 6)))

    # -------------------------------------------------------------------------
    # Cut 4: 双方向の真価・PC操作連動の自動消去 (00:20 - 00:26)
    # -------------------------------------------------------------------------
    log_step(20, "AI-Agent", "Triggering second prompt: 'git push origin main'", "\033[33m")
    ask_payload_2 = {
        "command": "git push origin main",
        "summary": "GitHubリポジトリへのプッシュ",
        "agent_name": "OpenCode",
        "risk_level": "prompt",
        "wait_decision": False,
        "timeout": 30
    }
    res_2 = agent_bridge_client._post_to_hub("/api/agent/ask", ask_payload_2, port=port)
    req_id_2 = res_2.get("request_id")
    log_step(21, "Smartphone", "📱 2枚目のバナー着信...", "\033[35m")
    time.sleep(2.0)

    # PC側でボスがEnterを押したことを模倣し、cancel_pending を発火！
    log_step(23, "PC-Console", "⌨️ ボスがPCキーボードで直接 [Enter] を押下！", "\033[1;37m")
    cancel_payload = {
        "request_id": req_id_2,
        "reason": "resolved_on_pc"
    }
    agent_bridge_client._post_to_hub("/api/agent/cancel_pending", cancel_payload, port=port)
    log_step(24, "Smartphone", "💨 cancel_pending 発火 ➔ スマホのバナーが0.2秒で自動消滅！(ゴミ通知ゼロ)", "\033[1;36m")
    time.sleep(2.0)

    # -------------------------------------------------------------------------
    # Cut 5: 結び (00:26 - 00:30)
    # -------------------------------------------------------------------------
    log_step(26, "DeskPet", "🎉 全開発タスク完了！ペットが安眠スリープへ移行🐾", "\033[32m")
    time.sleep(2.0)
    log_step(28, "Ending", "☕ 「休日はリビングで家族と過ごす。必要な1秒だけを救う、生活の相棒。」", "\033[1;35m")
    time.sleep(2.0)
    log_step(30, "Ending", "🏁 --- 30秒デモ動画撮影完了！お疲れ様でした！ ---", "\033[1;32m")
    print("=" * 60 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
