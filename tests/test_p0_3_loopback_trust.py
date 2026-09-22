#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - P0-3 修正の回帰テスト (tests/test_p0_3_loopback_trust.py)

総合コードレビューの P0-3（ID 41: Tailscale Serve 経由の client_ip 同一性崩壊）を
「loopback 信頼の3条件化」で根治するための不変条件テスト。

攻撃チェーン（devils-advocate 2026-09-22 実証）:
    Tailscale Serve（`tailscale serve --bg 8765`）はリクエストを 127.0.0.1 中継にするため
    `_is_loopback` が真になり、① GET /api/auth/token がマスター鍵を無条件配布
    ② POST /api/devices/restore で失効端末が復活 ③ POST /api/agent/ask（loopback限定）が通る
    ＝ 人間操作ゼロで承認RCEチェーンが再開放されていた。

不変条件 (P0-3):
    1. /api/auth/token は **マスター鍵を決して配布しない**。loopback には
       loopback 専用トークン（プロセス内生成・台帳非登録）を返す。
    2. loopback 信頼は「TCPピアが loopback」かつ「プロキシヘッダ (X-Forwarded-For /
       Forwarded / X-Real-IP) が無い」かつ「Host ヘッダが loopback 名 (localhost /
       127.0.0.1 / ::1)」の3条件すべてを満たす場合のみ成立する。
    3. loopback 専用トークンは非ループバック接続では無効（401）。
    4. 正規の loopback アクセス（Host=localhost）は従来どおり動作する（トークン無し GET /api/status）。

実行:
    venv\\Scripts\\python.exe -m pytest tests/test_p0_3_loopback_trust.py -v
"""

import io
import json
import logging
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import life_dreamer
import local_sync_server
import storage
import suggest_engine
from local_sync_server import DeskPetSyncHandler, get_sync_token_manager
from storage.connection import init_db
from storage.device_repo import get_all_devices

logging.getLogger("local_sync_server").setLevel(logging.CRITICAL)


class _ServerHarness:
    """/api/* を実HTTP経路で叩くハーネス（エフェメラルポート・DB隔離）。"""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._patchers: list = []
        self.httpd: Optional[ThreadingHTTPServer] = None
        self.port = 0
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """DB・重い外部依存を隔離した上でHTTPサーバーを起動する。"""
        db_patchers = [
            ("get_tasks", mock.MagicMock(return_value=[])),
            ("get_upcoming_events", mock.MagicMock(return_value=[])),
            ("get_all_calendar_sources", mock.MagicMock(return_value=[])),
            ("get_habits_with_status", mock.MagicMock(return_value=[])),
            ("get_habit_heatmap_data", mock.MagicMock(return_value={})),
        ]
        for name, fake in db_patchers:
            self._patchers.append(mock.patch.object(local_sync_server.database, name, fake))

        self._patchers.append(mock.patch(
            "storage.device_repo.get_db_connection",
            side_effect=lambda *args, **kwargs: storage.connection.get_db_connection(self.db_path),
        ))

        suggest_engine_mock = mock.MagicMock()
        suggest_engine_mock.generate_suggestions.return_value = []
        suggest_engine_mock.get_cached_suggestions.return_value = []
        suggest_engine_mock.config = {"sources": {}, "news_keywords": []}
        self._patchers.append(mock.patch.object(
            suggest_engine, "get_suggestion_engine", mock.MagicMock(return_value=suggest_engine_mock)
        ))

        life_dreamer_mock = mock.MagicMock()
        life_dreamer_mock.get_life_state.return_value = {
            "current_activity": "resting", "weather": "sunny", "message": "", "history": []
        }
        self._patchers.append(mock.patch.object(
            life_dreamer, "get_life_dreamer", mock.MagicMock(return_value=life_dreamer_mock)
        ))

        for p in self._patchers:
            p.start()

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), local_sync_server.DeskPetSyncHandler)
        self.port = self.httpd.server_address[1]
        self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """HTTPサーバーを停止し、Mockを解除する。"""
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
        for p in self._patchers:
            p.stop()
        self._patchers = []

    def request(
        self,
        method: str,
        path: str,
        *,
        host_header: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        bearer: str = "",
        body: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, Dict[str, Any]]:
        """HTTPリクエストを実行し (status, json) を返す。

        Args:
            method: HTTPメソッド。
            path: リクエストパス。
            host_header: 明示的に上書きする Host ヘッダ（None なら urllib の既定）。
            extra_headers: 追加ヘッダ（X-Forwarded-For 等の検証用）。
            bearer: Authorization: Bearer に載せるトークン。
            body: JSONボディ（POST用）。

        Returns:
            Tuple[int, Dict[str, Any]]: (HTTPステータス, パース済みJSON)。
        """
        headers: Dict[str, str] = {"User-Agent": "TestApp/1.0"}
        if host_header is not None:
            headers["Host"] = host_header
        if extra_headers:
            headers.update(extra_headers)
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        if data is not None:
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=5.0) as res:
                return res.status, json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                return e.code, json.loads(raw)
            except json.JSONDecodeError:
                return e.code, {"raw": raw}


class _DummyHandler:
    """_check_auth を単体実行するための最小ハンドラスタブ。"""

    def __init__(self, bearer: str, client_ip: str = "192.168.1.50", host: str = "192.168.1.50:8765") -> None:
        self.headers = {
            "Authorization": f"Bearer {bearer}",
            "User-Agent": "TestApp/1.0",
            "Host": host,
        }
        self.command = "GET"
        self.path = "/api/status"
        self.client_address = (client_ip, 54321)
        self.status_codes: list = []
        self.wfile = io.BytesIO()

    def _get_bearer_token(self) -> str:
        auth = self.headers.get("Authorization", "")
        return auth.split(" ")[1] if " " in auth else ""

    def _is_private_ip(self, ip: str) -> bool:
        return True

    def send_response(self, code: int) -> None:
        self.status_codes.append(code)

    def send_header(self, k: str, v: str) -> None:
        pass

    def end_headers(self) -> None:
        pass

    def _set_cors_headers(self) -> None:
        pass


class TestLoopbackTrustIsThreeConditional(unittest.TestCase):
    """不変条件2・4: loopback 信頼は TCPピア + Host + プロキシヘッダ無しの3条件。"""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmpdir.name) / "test_p0_3.db")
        init_db(self.db_path)
        self.harness = _ServerHarness(self.db_path)
        self.harness.start()

    def tearDown(self) -> None:
        self.harness.stop()
        self._tmpdir.cleanup()

    def test_token_endpoint_never_returns_master_key_from_loopback(self) -> None:
        """loopback からの /api/auth/token はマスター鍵を返さず、loopback 専用トークンを返すこと。"""
        tm = get_sync_token_manager()
        status, data = self.harness.request("GET", "/api/auth/token")

        self.assertEqual(status, 200, f"loopback は 200 で配布されること (actual={status}, body={data})")
        issued = str(data.get("token", ""))
        self.assertTrue(len(issued) >= 32, "トークンが配布されること")
        self.assertNotEqual(issued, tm.token, "🛡️ P0-3: マスター鍵を loopback へ配布してはならない")
        self.assertEqual(
            get_all_devices(db_path=self.db_path), [],
            "🛡️ loopback 専用トークンは端末台帳へ登録しないこと（PCブラウザで台帳を汚さない）",
        )

    def test_foreign_host_header_disables_loopback_trust(self) -> None:
        """Host が loopback 名でない場合、loopback 信頼を無効化すること (DNS Rebinding 対策)。"""
        status_token, data_token = self.harness.request(
            "GET", "/api/auth/token", host_header="evil.example:8765"
        )
        self.assertEqual(status_token, 403, f"🛡️ 外部 Host は pairing 非開放なら 403 (actual={status_token})")
        self.assertNotIn("token", data_token)

        status_restore, data_restore = self.harness.request(
            "POST", "/api/devices/restore", host_header="evil.example:8765", body={"device_id": 1}
        )
        # 認証が先に評価されるため 401（未認証）で遮断される。403 でも同等に安全側。
        self.assertIn(status_restore, (401, 403), "🛡️ 外部 Host からの管理APIは遮断されること")
        self.assertNotEqual(data_restore.get("status"), "ok")

    def test_tailscale_host_header_disables_loopback_trust(self) -> None:
        """Tailscale Serve 経由（Host が *.ts.net）は loopback 信頼を無効化すること (P0-3 本丸)。"""
        status, data = self.harness.request(
            "GET", "/api/auth/token", host_header="neo-pc.tailnet-xxxx.ts.net"
        )
        self.assertEqual(status, 403, f"🛡️ Serve 経由は loopback 扱いしない (actual={status}, body={data})")
        self.assertNotIn("token", data)

    def test_proxy_forwarded_headers_disable_loopback_trust(self) -> None:
        """プロキシヘッダ付きの接続は loopback 信頼を無効化すること (Fail-Closed)。"""
        for header_name in ("X-Forwarded-For", "Forwarded", "X-Real-IP"):
            with self.subTest(header=header_name):
                status, data = self.harness.request(
                    "GET", "/api/auth/token", extra_headers={header_name: "203.0.113.9"}
                )
                self.assertEqual(status, 403, f"🛡️ {header_name} 付きは loopback 扱いしない (actual={status})")
                self.assertNotIn("token", data)

    def test_loopback_host_still_allows_tokenless_status_get(self) -> None:
        """正規の loopback（Host=localhost 相当）はトークン無し GET /api/status が従来どおり 200 であること。"""
        status, data = self.harness.request("GET", "/api/status")
        self.assertEqual(status, 200, f"loopback の閲覧は維持されること (actual={status})")
        self.assertEqual(data.get("status"), "ok")

    def test_loopback_token_is_rejected_from_non_loopback_client(self) -> None:
        """loopback 専用トークンは非ループバック接続では 401 で拒否されること（窃取しても無効）。"""
        loopback_token = get_sync_token_manager().loopback_token
        with mock.patch(
            "storage.device_repo.get_db_connection",
            side_effect=lambda *args, **kwargs: storage.connection.get_db_connection(self.db_path),
        ):
            with mock.patch("database.verify_device_token", return_value=None):
                handler = _DummyHandler(loopback_token)
                allowed = DeskPetSyncHandler._check_auth(handler)

        self.assertFalse(allowed, "🛡️ loopback 専用トークンは LAN からは通ってはならない")
        self.assertEqual(handler.status_codes, [401], "401 Unauthorized を返すこと")

    def test_additional_proxy_headers_disable_loopback_trust(self) -> None:
        """中継の痕跡ヘッダ（X-Forwarded-Host / Via / Tailscale-*）でも loopback 信頼を無効化すること。"""
        for header_name in ("X-Forwarded-Host", "X-Forwarded-Proto", "Via", "Tailscale-User-Login"):
            with self.subTest(header=header_name):
                status, data = self.harness.request(
                    "GET", "/api/auth/token", extra_headers={header_name: "proxy.example"}
                )
                self.assertEqual(status, 403, f"🛡️ {header_name} 付きは loopback 扱いしない (actual={status})")
                self.assertNotIn("token", data)

    def test_ipv6_bracket_host_with_suffix_is_not_loopback(self) -> None:
        """`Host: [::1]evil.com` のような不正な IPv6 リテラルを loopback と判定しないこと (N2)。"""
        status, data = self.harness.request("GET", "/api/auth/token", host_header="[::1]evil.com")
        self.assertEqual(status, 403, f"🛡️ 不正な IPv6 Host は loopback 扱いしない (actual={status})")
        self.assertNotIn("token", data)

    def test_duplicate_headers_are_fail_closed(self) -> None:
        """同名ヘッダの複数出現（空の先行 + 本物の後続 / 複数 Host）は Fail-Closed であること (N3)。"""
        class _MultiHeaderMap:
            """email.message 風の複数ヘッダマップ（get_all を持つ）。"""

            def __init__(self, values: Dict[str, List[str]]) -> None:
                self._values = values

            def get_all(self, name: str) -> List[str]:
                return self._values.get(name, [])

            def get(self, name: str) -> Optional[str]:
                values = self._values.get(name)
                return values[0] if values else None

        empty_first_xff = _MultiHeaderMap({
            "Host": ["127.0.0.1:8765"],
            "X-Forwarded-For": ["", "203.0.113.9"],
        })
        self.assertFalse(
            DeskPetSyncHandler._is_trusted_loopback("127.0.0.1", "127.0.0.1:8765", empty_first_xff),
            "🛡️ 空の先行ヘッダでプロキシ検知を迂回できてはならない",
        )

        duplicate_host = _MultiHeaderMap({"Host": ["127.0.0.1:8765", "evil.example"]})
        self.assertFalse(
            DeskPetSyncHandler._is_trusted_loopback("127.0.0.1", "127.0.0.1:8765", duplicate_host),
            "🛡️ 複数 Host は Fail-Closed であること",
        )


if __name__ == "__main__":
    unittest.main()
