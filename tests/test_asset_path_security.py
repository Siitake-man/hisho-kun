#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - 静的アセット配信のパス検証テスト (tests/test_asset_path_security.py)

【P0-1 (2026-09-16 ruthless-code-evaluation で実測再現)】
    GET /assets/... は PWA 表示用に「認証なし」で配信される設計のため、
    パス検証が唯一の防壁である。しかし旧実装の検査は
    `".." / 先頭 "/" / ":"` のみで、Windows の「\\」始まり絶対パスを通過させていた:

        GET /assets/\\Windows\\win.ini  →  HTTP/1.0 200 OK ＋ 実ファイル本文

    local_sync_server は 0.0.0.0 で待受するため、同一LAN/Tailscale上の
    誰でもホスト内の任意ASCIIファイルを読める状態だった。

修正方針 (本テストが凍結する契約):
  1. 解決は純粋関数 `web_assets.resolve_asset_path()` に集約する (Seam)。
  2. 拡張子アローリスト（画像のみ）＋ 実パスが assets ルート配下であることを検証。
  3. 解決できない要求は例外を漏らさず 404 を返し、本文へ内容を漏らさない。

TDD: web_assets モジュールが無い状態では Red。
"""

import socket
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import local_sync_server  # noqa: E402
from web_assets import ALLOWED_ASSET_SUFFIXES, resolve_asset_path  # noqa: E402

SECRET_MARKER = "TOP-SECRET-CONTENT"


class TestResolveAssetPath(unittest.TestCase):
    """純粋関数 resolve_asset_path のセキュリティ契約"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "pwa").mkdir()
        (self.root / "pwa" / "icon_192.png").write_bytes(b"\x89PNG\r\n\x1a\npwa-icon")
        (self.root / "ok.png").write_bytes(b"\x89PNG\r\n\x1a\nroot-icon")
        (self.root / "sub").mkdir()
        (self.root / "sub" / "sprite.gif").write_bytes(b"GIF89a")
        (self.root / "secret.txt").write_text(SECRET_MARKER, encoding="utf-8")
        (self.root / ".env").write_text("OPENCODE_API_KEY=x", encoding="utf-8")
        (self.root / "neo_secretary.db").write_bytes(b"SQLite format 3")
        # assets ルートの外に存在する「読まれてはいけない」ファイル
        self.outside = Path(self._tmp.name).parent / f"{Path(self._tmp.name).name}_outside.txt"
        self.outside.write_text(SECRET_MARKER, encoding="utf-8")

    def tearDown(self) -> None:
        self.outside.unlink(missing_ok=True)
        self._tmp.cleanup()

    # --- 正常系 -----------------------------------------------------------
    def test_accepts_nested_image(self) -> None:
        """assets 配下の画像は解決できること (PWAアイコン配信の維持)"""
        self.assertEqual(
            resolve_asset_path("pwa/icon_192.png", self.root),
            self.root / "pwa" / "icon_192.png",
        )

    def test_accepts_all_whitelisted_suffixes(self) -> None:
        """許可拡張子（画像）はすべて受け入れること"""
        for suffix in ALLOWED_ASSET_SUFFIXES:
            with self.subTest(suffix=suffix):
                target = self.root / f"sample{suffix}"
                target.write_bytes(b"x")
                self.assertIsNotNone(resolve_asset_path(f"sample{suffix}", self.root))

    # --- 攻撃系（P0-1 の再発防止） ---------------------------------------
    def test_rejects_windows_absolute_backslash_path(self) -> None:
        """Windows の \\ 始まり絶対パスを拒否すること (P0-1 の核心)"""
        self.assertIsNone(resolve_asset_path(r"\Windows\win.ini", self.root))
        self.assertIsNone(resolve_asset_path(r"..\..\Windows\win.ini", self.root))

    def test_rejects_parent_directory_escape(self) -> None:
        """.. による assets 外への脱出を拒否すること"""
        for payload in (
            "../../secret.txt",
            "../.env",
            "pwa/../../neo_secretary.db",
            "%2e%2e/%2e%2e/secret.txt",
            "..%5c..%5csecret.txt",
        ):
            with self.subTest(payload=payload):
                self.assertIsNone(resolve_asset_path(payload, self.root))

    def test_rejects_drive_and_unc_paths(self) -> None:
        """ドライブ指定・UNC パス・絶対パスを拒否すること"""
        for payload in ("C:/Windows/win.ini", "C:\\Windows\\win.ini", "//host/share/x.png", "/etc/passwd"):
            with self.subTest(payload=payload):
                self.assertIsNone(resolve_asset_path(payload, self.root))

    def test_rejects_non_image_suffix_even_inside_root(self) -> None:
        """ルート内でも画像以外（.txt/.env/.db）は配信しないこと（多層防御）"""
        for payload in ("secret.txt", ".env", "neo_secretary.db", "app.py"):
            with self.subTest(payload=payload):
                self.assertIsNone(resolve_asset_path(payload, self.root))

    def test_rejects_missing_or_invalid_input(self) -> None:
        """空文字・ヌル文字・未登録ファイルで例外を漏らさず None を返すこと"""
        for payload in ("", "   ", "\x00", "no_such_icon.png", "pwa/icon_192.png\x00.txt"):
            with self.subTest(payload=repr(payload)):
                self.assertIsNone(resolve_asset_path(payload, self.root))

    def test_rejects_traversal_with_allowed_suffix(self) -> None:
        """許可拡張子でもルート外へ脱出するパスは拒否すること（最終関門の検証）"""
        outside_png = self.root.parent / f"{self.root.name}_outside.png"
        outside_png.write_bytes(b"\x89PNG\r\n\x1a\nsecret")
        try:
            self.assertIsNone(resolve_asset_path(f"../{outside_png.name}", self.root))
            self.assertIsNone(resolve_asset_path(f"sub/../../{outside_png.name}", self.root))
        finally:
            outside_png.unlink(missing_ok=True)

    def test_accepts_query_string_stripped_name(self) -> None:
        """?v=1.0.3 等のクエリ除去は呼び出し側の責務であることを明示（実名で解決）"""
        self.assertIsNotNone(resolve_asset_path("ok.png", self.root))


class TestAssetsEndpointHardening(unittest.TestCase):
    """実HTTP経由で /assets が攻撃を遮断し、正規配信を維持することを検証する"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), local_sync_server.DeskPetSyncHandler)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.server_thread.join(timeout=2.0)

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "ok.png").write_bytes(b"\x89PNG\r\n\x1a\npublic")
        (self.root / "secret.txt").write_text(SECRET_MARKER, encoding="utf-8")
        self.outside = Path(self._tmp.name).parent / f"{Path(self._tmp.name).name}_outside.txt"
        self.outside.write_text(SECRET_MARKER, encoding="utf-8")

    def tearDown(self) -> None:
        self.outside.unlink(missing_ok=True)
        self._tmp.cleanup()

    def _raw_get(self, raw_path: str) -> tuple:
        """urllib の正規化を避けるため生ソケットでリクエストを送る。

        Returns:
            tuple: (status_code, レスポンス本文テキスト, レスポンス全体の生バイト)
        """
        with socket.create_connection(("127.0.0.1", self.port), timeout=3.0) as sock:
            request = f"GET /assets/{raw_path} HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n"
            sock.sendall(request.encode("ascii", errors="replace"))
            chunks = []
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                chunks.append(data)
        raw = b"".join(chunks)
        response = raw.decode("utf-8", errors="replace")
        status = int(response.split(" ")[1]) if response.startswith("HTTP/") else 0
        return status, response, raw

    def test_serves_legitimate_icon_from_real_assets(self) -> None:
        """正規のPWAアイコンは 200 + image/png で配信され続けること（回帰防止）"""
        with mock.patch.object(local_sync_server, "ASSETS_DIR", PROJECT_ROOT / "assets"):
            status, body, raw = self._raw_get("pwa/icon_192.png")
        payload = raw.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in raw else b""
        self.assertEqual(status, 200)
        self.assertIn("image/png", body)
        self.assertTrue(payload.startswith(b"\x89PNG"), "PNG本体が配信されていません")

    def test_blocks_absolute_backslash_escape(self) -> None:
        """\\ 始まり絶対パスで assets 外を読めないこと（P0-1 の攻撃再現）"""
        escaped = str(self.outside.resolve())
        if not escaped.isascii():
            self.skipTest("一時パスが非ASCIIのため生ソケット検証をスキップ")
        payload = escaped.split(":", 1)[1] if ":" in escaped else escaped  # \Users\... 形式

        with mock.patch.object(local_sync_server, "ASSETS_DIR", self.root):
            status, body, _raw = self._raw_get(payload)
            status2, body2, _raw2 = self._raw_get(payload.replace("\\", "/"))

        self.assertEqual(status, 404, f"任意ファイル読み出しが成立しています: {body[:200]}")
        self.assertNotIn(SECRET_MARKER, body)
        self.assertEqual(status2, 404)
        self.assertNotIn(SECRET_MARKER, body2)

    def test_blocks_parent_directory_escape_over_http(self) -> None:
        """../ による脱出要求が 404 になり内容を漏らさないこと"""
        with mock.patch.object(local_sync_server, "ASSETS_DIR", self.root):
            status, body, _raw = self._raw_get("../" + self.outside.name)
        self.assertEqual(status, 404)
        self.assertNotIn(SECRET_MARKER, body)

    def test_blocks_non_image_file_inside_root(self) -> None:
        """ルート内でも画像以外（.txt）は配信しないこと（多層防御）"""
        with mock.patch.object(local_sync_server, "ASSETS_DIR", self.root):
            status, body, _raw = self._raw_get("secret.txt")
        self.assertEqual(status, 404)
        self.assertNotIn(SECRET_MARKER, body)

    def test_route_is_wired_to_safe_seam(self) -> None:
        """/assets 配信が純粋 Seam (resolve_asset_path) を経由していること"""
        self.assertIs(local_sync_server.resolve_asset_path, resolve_asset_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)

