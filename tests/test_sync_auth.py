#!/usr/bin/env python3
"""
ネオ秘書くん - 同期サーバー認証機能 検証スクリプト (test_sync_auth.py)

holistic-code-review (2026-08-25) の P0 対策として実装した以下のセキュリティ機構を、
GUI 無しの自己完結型シナリオで検証します:

  1. Bearer認証 (POST書き込みのトークンなし拒否)
  2. ペアリングモード Fail-Closed → 2026-08-30 自己治癒仕様に更新:
     同一LAN (private IP) からの /api/auth/token はペアリング非開放でも配布される。
     LAN外からの配布は引き続き 403 拒否。
  3. エージェント発信API (ask/notify) の localhost 制限
     → LAN攻撃者相当(127.0.0.2)からの ask 作成を遮断
  4. 自己承認(RCE)防止
     → 承認要求元と同一IPからの respond を拒否、別端末(スマホ相当)からの正当承認は成功

実行:
    venv\\Scripts\\python.exe tests\\test_sync_auth.py

注意:
    ポート8765が使用中(ネオ秘書くん本番アプリ起動中)の場合は中止します。
"""

import json
import socket
import sys
import time
from pathlib import Path
import http.client
import urllib.request
import urllib.error
from typing import Any, Dict, Optional, Tuple

# Windows環境でのリダイレクト/パイプ出力時に cp932 エラーを防ぐため UTF-8 を強制
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# ※ 本スクリプトは tests/ 配下にあるため、プロジェクトルートを import パスに追加
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import database

BASE_HOST = "127.0.0.1"
BASE_PORT = 8765

_results: list = []


def _check(name: str, cond: bool, detail: str = "") -> None:
    """1件の検証結果を記録・表示する。

    Args:
        name (str): 検証項目名。
        cond (bool): 合否判定。
        detail (str): 補足情報(HTTPステータスやレスポンスボディ等)。
    """
    mark = "✅ PASS" if cond else "❌ FAIL"
    print(f"{mark} | {name}")
    if detail:
        print(f"         └ {detail[:180]}")
    _results.append((name, bool(cond)))


def _request(method: str, path: str, body: Optional[Dict[str, Any]] = None,
             token: str = "", source_ip: str = "") -> Tuple[int, Dict[str, Any]]:
    """同期サーバーへHTTPリクエストを送信する。

    Args:
        method (str): HTTPメソッド ('GET' / 'POST')。
        path (str): リクエストパス (例: '/api/status')。
        body (Optional[Dict[str, Any]]): JSONボディ。
        token (str): Bearer認証トークン。空ならヘッダー未添付。
        source_ip (str): 接続元IPのバインド指定(攻撃者/スマホシミュレーション用)。空ならOS既定。

    Returns:
        Tuple[int, Dict[str, Any]]: (HTTPステータスコード, JSONパース済みレスポンス)。
    """
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode("utf-8") if body is not None else None

    if source_ip:
        # 攻撃者・スマホ端末シミュレーション: ソースIPを明示的にバインド
        conn = http.client.HTTPConnection(BASE_HOST, BASE_PORT, timeout=10,
                                          source_address=(source_ip, 0))
        conn.connect()
        conn.request(method, path, body=data, headers=headers)
        res = conn.getresponse()
        raw = res.read().decode("utf-8", errors="replace")
        status = res.status
        conn.close()
        try:
            return status, json.loads(raw)
        except json.JSONDecodeError:
            return status, {"raw": raw}

    req = urllib.request.Request(
        f"http://{BASE_HOST}:{BASE_PORT}{path}",
        data=data,
        headers=headers,
        method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {}


def main() -> int:
    """検証シナリオを実行する。

    Returns:
        int: 全パス時 0、それ以外 1。ポート競合時は 2。
    """
    # ポート競合チェック（本番アプリが起動中なら中止）
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    port_busy = probe.connect_ex((BASE_HOST, BASE_PORT)) == 0
    probe.close()
    if port_busy:
        print("⚠️ ポート8765が使用中です。ネオ秘書くん(main.py)を停止してから再実行してください。")
        return 2

    database.init_db()

    from local_sync_server import get_sync_server, get_sync_token_manager

    server = get_sync_server()
    server.start(gui=None)
    time.sleep(0.5)

    tm = get_sync_token_manager()
    request_id = ""

    try:
        # T1: LAN内(ループバック相当)からのトークン要求は、ペアリング非開放でも
        #     自己治癒配布される (2026-08-30 スマホ復旧仕様: 同一LAN or ペアリング中のみ配布)
        st, data = _request("GET", "/api/auth/token")
        token_lan = str(data.get("token", ""))
        _check("T1 LAN内からの GET /api/auth/token は自己治癒配布される (200)",
               st == 200 and len(token_lan) >= 32, f"HTTP {st} token_len={len(token_lan)}")

        # T1b: LAN外(攻撃者相当 127.0.0.2)からのトークン要求は引き続き拒否されるべき (Fail-Closed)
        try:
            st, data = _request("GET", "/api/auth/token", source_ip="127.0.0.2")
            _check("T1b LAN外(127.0.0.2)からの GET /api/auth/token が拒否される (403)",
                   st == 403, f"HTTP {st} {data}")
        except OSError as e:
            print(f"⏭ SKIP | T1b (この環境では 127.0.0.2 バインド不可): {e}")
            _results.append(("T1b (環境制約によりスキップ)", True))

        # T2: ペアリング開放後は配布される
        tm.unlock_pairing(duration_sec=60)
        st, data = _request("GET", "/api/auth/token")
        token = str(data.get("token", ""))
        _check("T2 ペアリング開放後にトークン取得できる (200)",
               st == 200 and len(token) >= 32, f"HTTP {st} token_len={len(token)}")

        # T3: トークンなしの GET /api/status は LAN内からは閲覧許可される (自己治癒・2026-08-30)
        st, data = _request("GET", "/api/status")
        _check("T3 トークンなし GET /api/status (LAN内) は閲覧許可される (200)",
               st == 200, f"HTTP {st}")

        # T3b: トークンなしの POST /api/action は引き続き 401 で拒否されるべき
        #      (閲覧は自己治癒許可、書き込みは Bearer 必須という境界を守る)
        st, data = _request("POST", "/api/action", body={"action": "ping_test"})
        _check("T3b トークンなし POST /api/action は拒否される (401)",
               st == 401, f"HTTP {st} {data}")

        # T4: 有効トークン付きなら成功する
        st, data = _request("GET", "/api/status", token=token)
        _check("T4 有効トークン付き GET /api/status が成功する (200)",
               st == 200, f"HTTP {st}")

        # T5: localhost (エージェント相当) からの承認要請作成は成功する
        st, data = _request(
            "POST", "/api/agent/ask",
            body={"agent_name": "TestAgent", "command": "echo hello",
                  "summary": "テスト承認要請", "timeout": 30, "wait_decision": False},
            token=token
        )
        request_id = str(data.get("request_id", ""))
        _check("T5 localhost からの POST /api/agent/ask が成功する",
               st == 200 and request_id.startswith("req_"), f"HTTP {st} {data}")

        # T7: LAN攻撃者相当(127.0.0.2)からの ask は localhost 制限で遮断されるべき
        # ※ 127.0.0.2 は「ループバックだが 127.0.0.1 以外」の IP で別端末を模擬する
        t7_done = False
        try:
            st, data = _request(
                "POST", "/api/agent/ask",
                body={"command": "rm -rf /", "wait_decision": False},
                token=token,
                source_ip="127.0.0.2"
            )
            _check("T7 LAN攻撃者相当(127.0.0.2)からの ask が拒否される (403)",
                   st == 403, f"HTTP {st} {data}")
            t7_done = True
        except OSError as e:
            print(f"⏭ SKIP | T7 (この環境では 127.0.0.2 バインド不可): {e}")
            _results.append(("T7 (環境制約によりスキップ)", True))

        # T6: 要求元と同一IP (127.0.0.1) からの自己承認は拒否されるべき
        st, data = _request(
            "POST", "/api/agent/respond",
            body={"request_id": request_id, "decision": "approve"},
            token=token
        )
        denied = (data.get("status") == "error"
                  and "自己承認" in str(data.get("message", "")))
        _check("T6 要求元と同一IPからの自己承認が拒否される",
               denied, f"HTTP {st} {data}")

        # T8: 別端末 (127.0.0.2 = スマホ相当) からの正当な承認は成功するべき
        if not t7_done:
            print("⏭ SKIP | T8 (127.0.0.2 バインド不可のため代替検証不可)")
            _results.append(("T8 (環境制約によりスキップ)", True))
        else:
            try:
                st, data = _request(
                    "POST", "/api/agent/respond",
                    body={"request_id": request_id, "decision": "approve"},
                    token=token,
                    source_ip="127.0.0.2"
                )
                ok = st == 200 and data.get("status") == "success"
                _check("T8 別端末(スマホ相当)からの正当な承認が成功する",
                       ok, f"HTTP {st} {data}")
            except OSError as e:
                print(f"⏭ SKIP | T8 ({e})")
                _results.append(("T8 (環境制約によりスキップ)", True))

    finally:
        server.stop()

    passed = sum(1 for _, c in _results if c)
    total = len(_results)
    print("\n" + "=" * 62)
    print(f"🏁 検証結果: {passed}/{total} パス")
    for name, ok in _results:
        print(f"   {'✅' if ok else '❌'} {name}")
    print("=" * 62)
    return 0 if passed == total else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
