#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""起動スモークテスト (tools/smoke_startup.py)

実アプリ (main.py) をプレースホルダーの API キー・一時データフォルダ・空きポートで起動し、
「非同期メインループ到達」と「同期サーバー応答 (/version.js = 200)」を確認してから終了させる。

- 目的: GUI 起動経路の OS 依存クラッシュ（例: Linux での -transparentcolor TclError）を CI で検知する。
- 実 LLM キー・ネットワークは不要（プレースホルダーキーで起動のみ検証）。
- Linux では仮想ディスプレイ上で実行する: `xvfb-run -a python tools/smoke_startup.py`
- CI では tests/test_startup_smoke.py 経由で実行される（Ubuntu ジョブの `xvfb-run -a pytest`）

終了コード: 0 = 起動成功 / 1 = クラッシュ・タイムアウト
"""

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAINLOOP_MARKER = "非同期メインループを開始します"
DEFAULT_TIMEOUT_SEC = 90


def _free_port() -> int:
    """OS に空きポートを割り当てさせて返す。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _http_ok(url: str) -> bool:
    """URL が HTTP 200 を返すかを確認する（接続失敗は False）。"""
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def _tail(path: Path, lines: int = 40) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except OSError:
        return "(ログなし)"


def _stop(proc: subprocess.Popen) -> None:
    """起動したプロセスのみを終了させる（名前指定の kill は行わない）。"""
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=15)


def main() -> int:
    timeout = int(os.environ.get("SMOKE_TIMEOUT_SEC", DEFAULT_TIMEOUT_SEC))
    port = _free_port()
    with tempfile.TemporaryDirectory(prefix="hisho-smoke-", ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        log_path = tmp_path / "app.log"

        env = os.environ.copy()
        env.update({
            "NEO_HISHO_DATA_DIR": str(data_dir),
            "NEO_HISHO_PORT": str(port),
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        })
        env.setdefault("DEFAULT_LLM_PROVIDER", "opencode")
        env.setdefault("OPENCODE_API_KEY", "placeholder-not-a-real-key")

        url = f"http://127.0.0.1:{port}/version.js"
        print(f"[smoke] main.py を起動します (port={port}, data={data_dir})", flush=True)
        with open(log_path, "wb") as log:
            proc = subprocess.Popen(
                [sys.executable, "main.py"],
                cwd=str(PROJECT_ROOT),
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        print(f"[smoke] FAIL: アプリが終了しました (exit={proc.returncode})")
                        print(_tail(log_path))
                        return 1
                    log.flush()
                    reached = MAINLOOP_MARKER in log_path.read_text(encoding="utf-8", errors="replace")
                    if reached and _http_ok(url):
                        print(f"[smoke] OK: メインループ到達 & {url} = 200")
                        return 0
                    time.sleep(1)
                print(f"[smoke] FAIL: {timeout} 秒以内に起動が完了しませんでした")
                print(_tail(log_path))
                return 1
            finally:
                _stop(proc)


if __name__ == "__main__":
    sys.exit(main())
