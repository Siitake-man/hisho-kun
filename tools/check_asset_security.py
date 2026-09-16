#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - アセット配信ゼロトラスト自己点検ツール (tools/check_asset_security.py)

【なぜ専用ツールが必要か】
    `GET /assets/...` は PWA 表示のため「認証なし」で公開しており、パス検証が唯一の防壁である
    (P0-1 / 2026-09-16: Windows の `\\` 始まり絶対パスで任意ファイル読み出しが成立していた)。
    ところが **curl やブラウザは URL の `\\` を `/` へ正規化**するため、攻撃文字列を再現できない。
    本ツールは **生ソケットでリクエスト行をそのまま送る**ため、正規化に邪魔されずに点検できる。

【実行方法】
    # 1) アプリを起動した状態で、その実サーバーを点検（推奨・リリース前ゲート）
    .\\venv\\Scripts\\python.exe tools\\check_asset_security.py

    # 2) LAN/Tailscale 側の到達性も点検（PC の LAN IP を指定）
    .\\venv\\Scripts\\python.exe tools\\check_asset_security.py --host 192.168.1.23

    # 3) アプリを起動せず、使い捨ての点検用サーバーで自己点検（手元検証用）
    .\\venv\\Scripts\\python.exe tools\\check_asset_security.py --serve

終了コード: 0 = 全項目が期待どおり / 1 = 異常検知（リリース前チェックに利用可能）

Notes:
    Windows コンソール(cp932)は絵文字を表現できないため、出力は ASCII のみとする
    （`tools/scan_git_secrets.py` の cp932 クラッシュと同種の事故を避ける）。
"""

import argparse
import socket
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import local_sync_server  # noqa: E402
from sync_config import SERVER_PORT  # noqa: E402

# (表示名, 送信する生パス, 期待ステータス, 応答本文に含まれてはいけない文字列)
Expectation = Tuple[str, str, int, Sequence[str]]

EXPECTATIONS: Tuple[Expectation, ...] = (
    ("legit PWA icon (png)", "/assets/pwa/icon_192.png", 200, ()),
    ("legit sprite (nested)", "/assets/dot/hisho/idle_1.png", 200, ()),
    ("backslash absolute", "/assets/\\Windows\\win.ini", 404, ("16-bit app support",)),
    ("drive absolute", "/assets/C:/Windows/win.ini", 404, ("16-bit app support",)),
    ("parent traversal (db)", "/assets/../../neo_secretary.db", 404, ("SQLite format",)),
    ("secret file (.env)", "/assets/../.env", 404, ("API_KEY", "OPENCODE")),
    ("percent-encoded escape", "/assets/%2e%2e/neo_secretary.db", 404, ("SQLite format",)),
    ("token file (.sync_token)", "/assets/../.sync_token", 404, ()),
)


def raw_request(host: str, port: int, raw_path: str, timeout: float = 3.0) -> Tuple[int, bytes]:
    """生ソケットで GET を送り、(ステータスコード, 本文) を返す。

    Args:
        host: 接続先ホスト（127.0.0.1 または LAN IP）。
        port: 接続先ポート。
        raw_path: 正規化したくない生のリクエストパス。
        timeout: ソケットタイムアウト秒。

    Returns:
        Tuple[int, bytes]: HTTP ステータス（取得不能時は 0）とレスポンス本文。
    """
    request = f"GET {raw_path} HTTP/1.0\r\nHost: {host}\r\nConnection: close\r\n\r\n"
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(request.encode("ascii", errors="replace"))
        chunks: List[bytes] = []
        while True:
            data = sock.recv(8192)
            if not data:
                break
            chunks.append(data)

    raw = b"".join(chunks)
    head, _, body = raw.partition(b"\r\n\r\n")
    first_line = head.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
    status = 0
    if first_line.startswith("HTTP/"):
        parts = first_line.split(" ")
        if len(parts) > 1:
            try:
                status = int(parts[1])
            except ValueError:
                status = 0
    return status, body


def run_checks(host: str, port: int, expectations: Iterable[Expectation]) -> int:
    """点検を実行し、異常件数を返す（0 なら全項目正常）。

    Args:
        host: 対象ホスト。
        port: 対象ポート。
        expectations: 点検項目の並び。

    Returns:
        int: 期待と異なった件数。
    """
    failures = 0
    print(f"[INFO] target: http://{host}:{port}  (raw socket / no path normalization)")

    for label, raw_path, expected_status, forbidden in expectations:
        try:
            status, body = raw_request(host, port, raw_path)
        except Exception as exc:  # 接続拒否・タイムアウト等
            print(f"[FAIL] {label:<28} request error: {exc}")
            failures += 1
            continue

        leaked = [token for token in forbidden if token.encode("utf-8") in body]
        if status == expected_status and not leaked:
            print(f"[PASS] {label:<28} status={status} (expected {expected_status})")
        else:
            detail = f"status={status} (expected {expected_status})"
            if leaked:
                detail += f" / CONTENT LEAK: {leaked}"
            print(f"[FAIL] {label:<28} {detail}")
            failures += 1

    return failures


def start_ephemeral_server() -> Tuple[ThreadingHTTPServer, str, int]:
    """自己点検用の使い捨てサーバー（127.0.0.1 の空きポート）を起動する。

    Returns:
        Tuple[ThreadingHTTPServer, str, int]: サーバー、ホスト、ポート。
    """
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), local_sync_server.DeskPetSyncHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, "127.0.0.1", int(httpd.server_address[1])


def main(argv: Sequence[str] = None) -> int:
    """エントリポイント。

    Args:
        argv: コマンドライン引数（省略時は sys.argv）。

    Returns:
        int: プロセス終了コード（0=正常, 1=異常検知）。
    """
    parser = argparse.ArgumentParser(description="GET /assets のパス検証を生ソケットで点検する")
    parser.add_argument("--host", default="127.0.0.1", help="対象ホスト（LAN IP も指定可）")
    parser.add_argument(
        "--port", type=int, default=SERVER_PORT, help=f"対象ポート（既定 {SERVER_PORT}）"
    )
    parser.add_argument(
        "--serve", action="store_true", help="アプリ未起動時に使い捨てサーバーで自己点検する"
    )
    args = parser.parse_args(argv)

    httpd = None
    host, port = args.host, args.port
    try:
        if args.serve:
            httpd, host, port = start_ephemeral_server()
            print("[INFO] ephemeral self-check server started (no app required)")

        failures = run_checks(host, port, EXPECTATIONS)
    finally:
        if httpd is not None:
            httpd.shutdown()
            httpd.server_close()

    print("")
    if failures == 0:
        print("[RESULT] OK: all asset path checks passed (zero-trust guard is active)")
        return 0
    print(
        f"[RESULT] NG: {failures} check(s) failed - /assets may be exposing files. Investigate immediately."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

