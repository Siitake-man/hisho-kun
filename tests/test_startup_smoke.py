#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_startup_smoke.py

実アプリ (main.py) の起動スモークテスト。tools/smoke_startup.py をサブプロセスで実行し、
プレースホルダーキーで「非同期メインループ到達」＋「同期サーバー応答 (/version.js = 200)」まで
到達することを検証する。

背景: Windows 専用の Tk 属性 (-transparentcolor) により Linux では起動直後に TclError で
クラッシュしていたが、GUI 起動経路を通すテストが無く CI で検知できなかった。
CI の Ubuntu ジョブは `xvfb-run -a pytest` で実行されるため、本テストがそのまま起動スモークになる。
"""

import os
import socket
import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SINGLE_INSTANCE_LOCK_PORT = 54321  # main.py の多重起動ロック


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux (Xvfb) 上の起動スモーク。Windows は既存の GUI テストで担保")
class TestStartupSmoke(unittest.TestCase):

    def setUp(self) -> None:
        if not os.environ.get("DISPLAY"):
            self.skipTest("DISPLAY が無い環境のためスキップ (xvfb-run -a pytest で実行してください)")
        try:
            import tkinter as tk

            probe = tk.Tk()
            probe.destroy()
        except Exception as e:  # DISPLAY が設定されていても接続できない環境
            self.skipTest(f"ディスプレイに接続できないためスキップ: {e}")
        if _port_in_use(SINGLE_INSTANCE_LOCK_PORT):
            self.skipTest("別のネオ秘書くんが起動中 (127.0.0.1:54321 使用中) のためスキップ")

    def test_app_reaches_main_loop_and_serves_http(self) -> None:
        """プレースホルダーキーで起動し、メインループ到達と /version.js = 200 を確認して終了すること。"""
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "tools" / "smoke_startup.py")],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, f"起動スモーク失敗:\n{result.stdout}\n{result.stderr}")
        self.assertIn("[smoke] OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
