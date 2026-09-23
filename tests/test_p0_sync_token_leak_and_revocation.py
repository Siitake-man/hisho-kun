#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - P0-1 修正の回帰テスト (tests/test_p0_sync_token_leak_and_revocation.py)

総合コードレビュー (docs/reviews/2026-09-22_deep_audit.md) で確定した P0-1 の
「sync_token 漏洩」と「失効巻き戻し」を二度と再発させないための不変条件テスト。

不変条件 (Invariants):
  1. GET /api/status のレスポンスに同期トークン (マスターキー) を絶対に含めない。
  2. PWA (pet.js) はステータス応答で自分の Bearer トークンを上書きしない。
     トークン更新の唯一の経路は pet_auth.js の requestSyncToken() (ペアリング + 人間承認) のみ。
  3. 失効 (is_revoked = 1) は「自動経路」では絶対に解除されない。
     解除できるのは restore_device() を呼ぶ明示的な人間操作 (♻️ 接続復帰 / 承認済み再ペアリング) のみ。
  4. 失効端末は、どの資格情報 (個別トークン / マスタートークン) を提示しても 403 で拒絶される。

実行:
    venv\\Scripts\\python.exe -m pytest tests/test_p0_sync_token_leak_and_revocation.py -v
"""

import io
import json
import hashlib
import logging
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Tuple
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import life_dreamer
import local_sync_server
import storage
import suggest_engine
from local_sync_server import DeskPetSyncHandler
from storage.connection import init_db
from storage.device_repo import (
    get_all_devices,
    issue_device_token,
    register_device,
    restore_device,
    revoke_device,
    sync_device_session,
    verify_device_token,
)

logging.getLogger("local_sync_server").setLevel(logging.CRITICAL)


# =============================================================================
# HTTP 結合テスト用ハーネス (エフェメラルポート・DBモック隔離)
# =============================================================================

class _StatusApiHarness:
    """/api/status を実HTTP経路で叩くためのハーネス。

    本番ポート (8765) と本番DB (neo_secretary.db) には一切触れず、エフェメラルポートと
    unittest.mock によるDB隔離のみで「実レスポンス契約」を検証する。
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._patchers: list = []
        self.httpd = None
        self.port = 0
        self._thread = None

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

        # 実DBを汚さないため、台帳系 I/O はテンポラリDBへ束縛する
        self._patchers.append(mock.patch(
            "storage.device_repo.get_db_connection",
            side_effect=lambda *args, **kwargs: storage.connection.get_db_connection(self.db_path),
        ))
        self._patchers.append(mock.patch(
            "database.verify_device_token",
            side_effect=lambda b: verify_device_token(b, db_path=self.db_path),
        ))
        self._patchers.append(mock.patch(
            "database.touch_device_last_seen",
            side_effect=lambda h, **kw: storage.device_repo.touch_device_last_seen(h, db_path=self.db_path, **kw),
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

    def get_status(self, bearer: str) -> Tuple[int, Dict[str, Any], str]:
        """Bearer トークン付きで GET /api/status を実行する。

        Args:
            bearer: Authorization: Bearer に載せるトークン文字列。

        Returns:
            Tuple[int, Dict[str, Any], str]: (HTTPステータスコード, パース済みJSON, 生ボディ文字列)。
            生ボディは「ネスト・別名での再混入」も検出できるよう文字列走査用に返す。
        """
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/status",
            headers={"Authorization": f"Bearer {bearer}", "User-Agent": "TestApp/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=5.0) as res:
                raw = res.read().decode("utf-8")
                return res.status, json.loads(raw), raw
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                return e.code, json.loads(raw), raw
            except json.JSONDecodeError:
                return e.code, {"raw": raw}, raw


# =============================================================================
# 1. /api/status のレスポンス契約 (漏洩の遮断)
# =============================================================================

class TestStatusPayloadDoesNotLeakSyncToken(unittest.TestCase):
    """不変条件1: /api/status はマスターキーを配らない。"""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmpdir.name) / "test_p0.db")
        init_db(self.db_path)
        self.harness = _StatusApiHarness(self.db_path)
        self.harness.start()

    def tearDown(self) -> None:
        self.harness.stop()
        self._tmpdir.cleanup()

    def test_status_payload_does_not_contain_sync_token(self) -> None:
        """端末個別トークンで GET /api/status してもレスポンスに sync_token キーが存在しないこと。"""
        device_token = issue_device_token(
            device_name="Test Phone",
            ip_address="127.0.0.1",
            user_agent="TestApp/1.0",
            db_path=self.db_path,
        )
        status, data, raw = self.harness.get_status(device_token)

        self.assertEqual(status, 200, f"/api/status は 200 であること (actual={status}, body={data})")
        self.assertEqual(data.get("status"), "ok", "正常レスポンスであること")
        self.assertNotIn(
            "sync_token",
            data,
            "🛡️ P0-1: /api/status が同期トークン(マスターキー)を配布してはならない",
        )
        # 多層防御: ネストや別名 (syncToken 等) での再混入も生ボディ文字列で検出する
        self.assertNotIn("sync_token", raw, "🛡️ 生ボディ文字列にも sync_token を含めないこと")
        self.assertNotIn("syncToken", raw, "🛡️ 別名 (syncToken) での再混入も禁止すること")

    def test_server_source_never_assembles_sync_token_into_status(self) -> None:
        """ソース不変条件: local_sync_server.py が sync_token を payload へ再混入させないこと。"""
        source = (PROJECT_ROOT / "local_sync_server.py").read_text(encoding="utf-8")
        self.assertNotIn(
            '"sync_token"',
            source,
            "🛡️ P0-1: local_sync_server.py に sync_token のペイロード同梱を再導入してはならない",
        )


# =============================================================================
# 2. 失効の自動巻き戻し禁止 (不変条件3・4)
# =============================================================================

class TestRevocationIsNotRolledBack(unittest.TestCase):
    """不変条件3・4: 失効は自動経路で解除されず、失効端末は常に拒絶される。"""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmpdir.name) / "test_p0.db")
        init_db(self.db_path)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _repo_scope(self):
        """storage.device_repo のDB接続をテンポラリDBへ束縛するコンテキストマネージャ。"""
        return mock.patch(
            "storage.device_repo.get_db_connection",
            side_effect=lambda *args, **kwargs: storage.connection.get_db_connection(self.db_path),
        )

    def test_register_device_keeps_revoked_state(self) -> None:
        """既存の失効レコードに同一トークンで再登録しても is_revoked が 0 に戻らないこと。"""
        token = issue_device_token("Phone A", ip_address="192.168.1.50", db_path=self.db_path)
        device = verify_device_token(token, db_path=self.db_path)
        revoke_device(device.id, db_path=self.db_path)

        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._repo_scope():
            register_device("Phone A", token_hash, ip_address="192.168.1.50", db_path=self.db_path)

        after = verify_device_token(token, db_path=self.db_path)
        self.assertEqual(
            after.is_revoked,
            1,
            "🛡️ P0-1: register_device は失効フラグを無言で巻き戻してはならない",
        )

    def test_register_device_with_new_token_keeps_revoked_state(self) -> None:
        """失効端末と同一IP・同一名で新トークンを登録しても失効が維持されること (IP+名前再利用の穴の封鎖)。"""
        old_token = issue_device_token("Phone A", ip_address="192.168.1.50", db_path=self.db_path)
        device = verify_device_token(old_token, db_path=self.db_path)
        revoke_device(device.id, db_path=self.db_path)

        new_token = issue_device_token("Phone A", ip_address="192.168.1.50", db_path=self.db_path)
        after = verify_device_token(new_token, db_path=self.db_path)

        self.assertEqual(after.id, device.id, "同一端末行が再利用されること (重複行を作らない)")
        self.assertEqual(
            after.is_revoked,
            1,
            "🛡️ P0-1: 同一IP+名前の再利用経路でも失効は維持されること",
        )

    def test_sync_device_session_is_read_only_and_does_not_clobber_revoked_rows(self) -> None:
        """sync_device_session は台帳へ書き込まず、他端末 (失効行) の資格情報を乗っ取らないこと。

        P0-1 (A案 / devils-advocate 指摘): 旧実装は「同一IP+端末名の行再利用 + token_hash 上書き」
        により、マスタートークン保持端末が失効端末の身元を乗っ取れた。認証経路を読み取り専用へ
        変更したことで、未登録資格情報は解決不能 (None) となり乗っ取りは構造的に成立しない。
        """
        token = issue_device_token(
            "iPhone", ip_address="192.168.1.50", user_agent="iphone-ua", db_path=self.db_path
        )
        device = verify_device_token(token, db_path=self.db_path)
        revoke_device(device.id, db_path=self.db_path)
        token_hash_before = device.token_hash

        global_token = "global_master_token_64chars_long_alpha_bravo_charlie_12345678"
        with self._repo_scope():
            resolved = sync_device_session(
                bearer=global_token,
                ip_address="192.168.1.50",
                user_agent="iphone-ua",
                db_path=self.db_path,
            )

        self.assertIsNone(resolved, "未登録資格情報は解決不能 (None) であること")
        after = verify_device_token(token, db_path=self.db_path)
        self.assertIsNotNone(after, "既存行の資格情報が乗っ取られていないこと (旧トークンが有効なまま)")
        self.assertEqual(after.id, device.id)
        self.assertEqual(after.token_hash, token_hash_before, "🛡️ token_hash を上書きしてはならない")
        self.assertEqual(after.is_revoked, 1, "🛡️ 自動経路で失効が解除されてはならない")
        self.assertEqual(len(get_all_devices(db_path=self.db_path)), 1, "台帳に行を追加してはならない")

    def test_check_auth_rejects_unregistered_master_token_from_lan(self) -> None:
        """台帳未登録のマスタートークンは非ループバックから拒否されること (A案: 漏洩キーの実効無効化)。

        Notes:
            ループバック (PC自身・Agent Bridge・MCPサーバー) は台帳対象外として従来どおり許可される。
            マスタートークンが台帳に登録済み (レガシー登録) の場合は行の失効状態に従う。
        """
        iphone_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
        token = issue_device_token(
            "iPhone", ip_address="192.168.1.50", user_agent=iphone_ua, db_path=self.db_path
        )
        device = verify_device_token(token, db_path=self.db_path)
        revoke_device(device.id, db_path=self.db_path)

        global_token = "global_master_token_64chars_long_alpha_bravo_charlie_12345678"

        class DummyHandler:
            """_check_auth を単体実行するための最小ハンドラスタブ。"""

            def __init__(self, bearer: str, client_ip: str = "192.168.1.50") -> None:
                self.headers = {"Authorization": f"Bearer {bearer}", "User-Agent": iphone_ua}
                self.command = "GET"
                self.path = "/api/status"
                self.client_address = (client_ip, 54321)
                self.status_codes: list = []
                self.wfile = io.BytesIO()

            def _get_bearer_token(self) -> str:
                auth = self.headers.get("Authorization", "")
                return auth.split(" ")[1] if " " in auth else ""

            def _is_loopback(self, ip: str) -> bool:
                return ip in ("127.0.0.1", "::1", "localhost")

            def _is_private_ip(self, ip: str) -> bool:
                return True

            def _infer_device_name(self, ua: str) -> str:
                return "iPhone"

            def send_response(self, code: int) -> None:
                self.status_codes.append(code)

            def send_header(self, k: str, v: str) -> None:
                pass

            def end_headers(self) -> None:
                pass

            def _set_cors_headers(self) -> None:
                pass

        with self._repo_scope():
            with mock.patch.object(
                local_sync_server.get_sync_token_manager(), "verify",
                side_effect=lambda t: t == global_token,
            ):
                handler = DummyHandler(global_token)
                allowed = DeskPetSyncHandler._check_auth(handler)

        self.assertFalse(allowed, "🛡️ P0-1: 台帳未登録のマスタートークンは LAN から通ってはならない")
        self.assertEqual(handler.status_codes, [401], "401 Unauthorized を返すこと")
        after = verify_device_token(token, db_path=self.db_path)
        self.assertIsNotNone(after, "既存行の資格情報が乗っ取られていないこと")
        self.assertEqual(after.is_revoked, 1, "認証試行によって失効が巻き戻ってはならない")
        self.assertEqual(len(get_all_devices(db_path=self.db_path)), 1, "台帳に行を追加してはならない")

    def test_check_auth_fails_closed_when_ledger_lookup_raises(self) -> None:
        """台帳照合が例外を送出した場合、マスタートークン経路は Fail-Closed で拒否されること。"""
        iphone_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
        global_token = "global_master_token_64chars_long_alpha_bravo_charlie_12345678"

        class DummyHandler:
            """_check_auth を単体実行するための最小ハンドラスタブ。"""

            def __init__(self, bearer: str, client_ip: str = "192.168.1.50") -> None:
                self.headers = {"Authorization": f"Bearer {bearer}", "User-Agent": iphone_ua}
                self.command = "GET"
                self.path = "/api/status"
                self.client_address = (client_ip, 54321)
                self.status_codes: list = []
                self.wfile = io.BytesIO()

            def _get_bearer_token(self) -> str:
                auth = self.headers.get("Authorization", "")
                return auth.split(" ")[1] if " " in auth else ""

            def _is_loopback(self, ip: str) -> bool:
                return ip in ("127.0.0.1", "::1", "localhost")

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

        with mock.patch("database.sync_device_session", side_effect=RuntimeError("database is locked")):
            with mock.patch.object(
                local_sync_server.get_sync_token_manager(), "verify",
                side_effect=lambda t: t == global_token,
            ):
                handler = DummyHandler(global_token)
                allowed = DeskPetSyncHandler._check_auth(handler)

        self.assertFalse(allowed, "🛡️ 台帳照合失敗時は認証を成立させない (Fail-Closed)")
        self.assertEqual(handler.status_codes, [401], "401 Unauthorized を返すこと")

    def test_status_dto_deny_list_removes_sync_token(self) -> None:
        """DTO 境界の多層防御: 万一 payload に sync_token が混入しても除去されること。"""
        from sync_dtos import validate_status_payload

        payload = {
            "status": "ok",
            "sync_token": "leaked-master-key",
            "language": "ja",
        }
        validated = validate_status_payload(payload)
        self.assertNotIn("sync_token", validated, "🛡️ DTO 境界で sync_token を除去すること")
        self.assertEqual(validated.get("status"), "ok", "他のフィールドは保持されること")

    def test_check_auth_rejects_revoked_individual_token(self) -> None:
        """失効端末が自分の個別トークンを提示しても 403 で拒絶されること (不変条件4の本体)。

        devils-advocate 第2ラウンド指摘「宣言とテストの乖離」への対応。失効の実効性は
        個別トークン経路でも `_check_auth` レベルで保証されることを実測する。
        """
        iphone_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
        token = issue_device_token(
            "iPhone", ip_address="192.168.1.50", user_agent=iphone_ua, db_path=self.db_path
        )
        device = verify_device_token(token, db_path=self.db_path)
        revoke_device(device.id, db_path=self.db_path)

        class DummyHandler:
            """_check_auth を単体実行するための最小ハンドラスタブ。"""

            def __init__(self, bearer: str, client_ip: str = "192.168.1.50") -> None:
                self.headers = {"Authorization": f"Bearer {bearer}", "User-Agent": iphone_ua}
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

        with self._repo_scope():
            handler = DummyHandler(token)
            allowed = DeskPetSyncHandler._check_auth(handler)

        self.assertFalse(allowed, "🛡️ 失効端末の個別トークンは通ってはならない")
        self.assertEqual(handler.status_codes, [403], "403 Forbidden を返すこと")
        after = verify_device_token(token, db_path=self.db_path)
        self.assertEqual(after.is_revoked, 1, "失効状態が維持されること")

    def test_pairing_restore_failure_keeps_revoked_state(self) -> None:
        """承認済み再ペアリングでも restore に失敗した場合は失効を維持すること (Fail-Closed)。

        devils-advocate 指摘「restore 失敗ガードが未テスト」への対応。UI の嘘
        (「承認したのに繋がらない」) を作らないため、失敗時は失効のまま warning を残す。
        """
        iphone_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
        old_token = issue_device_token("iPhone", ip_address="192.168.1.60", user_agent=iphone_ua, db_path=self.db_path)
        device = verify_device_token(old_token, db_path=self.db_path)
        revoke_device(device.id, db_path=self.db_path)

        tm = local_sync_server.get_sync_token_manager()
        tm.unlock_pairing(duration_sec=60)
        tm.set_device_approval_callback(lambda dev_name, client_ip: True)
        self.addCleanup(tm.close_pairing)
        self.addCleanup(tm.set_device_approval_callback, None)

        handler = _FakeHttpHandler()
        handler.path = "/api/auth/token"
        handler.headers = {"User-Agent": iphone_ua}

        with mock.patch(
            "storage.device_repo.get_db_connection",
            side_effect=lambda *args, **kwargs: storage.connection.get_db_connection(self.db_path),
        ):
            with mock.patch(
                "database.issue_device_token",
                side_effect=lambda *a, **kw: issue_device_token(*a, db_path=self.db_path, **kw),
            ):
                with mock.patch(
                    "database.verify_device_token",
                    side_effect=lambda b: verify_device_token(b, db_path=self.db_path),
                ):
                    with mock.patch("database.restore_device", return_value=False) as mock_restore:
                        with mock.patch("api_devices.record_device_restore") as mock_audit:
                            DeskPetSyncHandler._handle_auth_token(handler, "192.168.1.60", iphone_ua)

        self.assertEqual(handler.status_codes, [200], "トークン配布自体は継続すること (可用性)")
        mock_restore.assert_called_once()
        mock_audit.assert_not_called()
        after = verify_device_token(
            json.loads(handler.wfile.getvalue().decode("utf-8")).get("token", ""), db_path=self.db_path
        )
        self.assertIsNotNone(after)
        self.assertEqual(after.is_revoked, 1, "🛡️ 復帰失敗時は失効を維持すること (Fail-Closed)")

    def test_explicit_restore_still_unrevokes(self) -> None:
        """人間の明示操作 (restore_device) は従来どおり失効を解除できること (復帰経路の非破壊)。"""
        token = issue_device_token("Phone A", ip_address="192.168.1.50", db_path=self.db_path)
        device = verify_device_token(token, db_path=self.db_path)
        revoke_device(device.id, db_path=self.db_path)
        self.assertEqual(verify_device_token(token, db_path=self.db_path).is_revoked, 1)

        self.assertTrue(restore_device(device.id, db_path=self.db_path))
        self.assertEqual(
            verify_device_token(token, db_path=self.db_path).is_revoked,
            0,
            "♻️ 明示的な接続復帰は有効であること",
        )

    def test_new_device_registers_as_active(self) -> None:
        """新規端末の初回登録は有効 (is_revoked=0) であること (正常系の非破壊)。"""
        token = issue_device_token("New Phone", ip_address="192.168.1.77", db_path=self.db_path)
        device = verify_device_token(token, db_path=self.db_path)
        self.assertIsNotNone(device)
        self.assertEqual(device.is_revoked, 0)


class TestRevocationWriteInvariant(unittest.TestCase):
    """不変条件3: is_revoked=0 を書くのは restore_device だけである (ソース凍結)。"""

    def test_only_restore_device_clears_the_revoked_flag(self) -> None:
        """storage/device_repo.py 内で失効を解除する関数が restore_device ただ1つであること。

        書き込みパターン「SET is_revoked = 0」を機械走査し、将来新しい関数が
        失効解除を書いた瞬間に Red になるよう凍結する (P0-1 不変条件)。
        """
        import inspect
        from storage import device_repo

        clearing_functions = [
            name
            for name, member in vars(device_repo).items()
            if inspect.isfunction(member)
            and member.__module__ == device_repo.__name__
            and "SET is_revoked = 0" in inspect.getsource(member)
        ]
        self.assertEqual(
            clearing_functions,
            ["restore_device"],
            "🛡️ P0-1: 失効解除 (SET is_revoked = 0) は restore_device のみに限定すること",
        )
        self.assertNotIn(
            "SET is_revoked",
            inspect.getsource(device_repo.register_device),
            "🛡️ register_device は失効フラグを書いてはならない",
        )


# =============================================================================
# 3. PWA クライアント側の契約 (トークン更新経路の一本化)
# =============================================================================

class TestPwaDoesNotOverwriteTokenFromStatus(unittest.TestCase):
    """不変条件2: pet.js は /api/status の応答でトークンを上書きしない。"""

    def test_pet_js_does_not_consume_sync_token_from_status(self) -> None:
        """pet.js に data.sync_token の参照が存在しないこと。"""
        content = (PROJECT_ROOT / "web_pet" / "pet.js").read_text(encoding="utf-8")
        self.assertNotIn(
            "data.sync_token",
            content,
            "🛡️ P0-1: pet.js がステータス応答で Bearer トークンを上書きしてはならない",
        )
        self.assertNotIn(
            "setSyncToken(data.sync_token)",
            content,
            "🛡️ P0-1: ステータス応答を根拠としたトークン更新を再導入してはならない",
        )

    def test_pet_auth_keeps_explicit_token_refresh_path(self) -> None:
        """トークン更新の唯一の経路 (requestSyncToken → /api/auth/token) が維持されていること。"""
        content = (PROJECT_ROOT / "web_pet" / "pet_auth.js").read_text(encoding="utf-8")
        self.assertIn("async function requestSyncToken()", content)
        # 🛡️ ID 50 (2026-09-23): 端末自己生成UUIDヘッダを付与するため fetch はオプション付きへ拡張
        self.assertIn("fetch('/api/auth/token'", content)
        self.assertIn("X-Device-UUID", content)
        self.assertIn("setSyncToken(tokenData.token)", content)


class _FakeHttpHandler:
    """_handle_auth_token を単体実行するための最小HTTPハンドラスタブ。"""

    def __init__(self) -> None:
        self.wfile = io.BytesIO()
        self.status_codes: list = []

    def send_response(self, code: int) -> None:
        self.status_codes.append(code)

    def send_header(self, name: str, value: str) -> None:
        pass

    def end_headers(self) -> None:
        pass

    def _set_cors_headers(self) -> None:
        pass


class TestApprovedPairingRestoresRevokedDevice(unittest.TestCase):
    """AD-1: 失効解除の唯一の自動経路は「人間承認済み再ペアリング」であること。

    自動巻き戻し (無言の復活) は禁止する一方で、PC側の QR ペアリング開放 +
    承認ダイアログ許可という2段の人間操作を経た再ペアリングは明示的な復帰操作とみなす。
    これにより「承認したのに繋がらない」UI上の嘘を構造的に排除する。
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmpdir.name) / "test_p0.db")
        init_db(self.db_path)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_approved_pairing_restores_revoked_device(self) -> None:
        """失効端末が人間承認付きで再ペアリングした場合のみ復帰し、監査ログに記録されること。"""
        import api_devices

        # 端末名推定 (_infer_device_name) が既存行と一致するよう、実機相当の iPhone UA を使う
        iphone_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
        old_token = issue_device_token("iPhone", ip_address="192.168.1.60", user_agent=iphone_ua, db_path=self.db_path)
        device = verify_device_token(old_token, db_path=self.db_path)
        revoke_device(device.id, db_path=self.db_path)

        tm = local_sync_server.get_sync_token_manager()
        tm.unlock_pairing(duration_sec=60)
        tm.set_device_approval_callback(lambda dev_name, client_ip: True)
        self.addCleanup(tm.close_pairing)
        self.addCleanup(tm.set_device_approval_callback, None)

        handler = _FakeHttpHandler()
        handler.path = "/api/auth/token"
        handler.headers = {"User-Agent": iphone_ua}

        with mock.patch(
            "storage.device_repo.get_db_connection",
            side_effect=lambda *args, **kwargs: storage.connection.get_db_connection(self.db_path),
        ):
            with mock.patch(
                "database.issue_device_token",
                side_effect=lambda *a, **kw: issue_device_token(*a, db_path=self.db_path, **kw),
            ):
                with mock.patch(
                    "database.verify_device_token",
                    side_effect=lambda b: verify_device_token(b, db_path=self.db_path),
                ):
                    with mock.patch(
                        "database.restore_device",
                        side_effect=lambda dev_id: restore_device(dev_id, db_path=self.db_path),
                    ):
                        with mock.patch("api_devices.record_device_restore") as mock_audit:
                            DeskPetSyncHandler._handle_auth_token(handler, "192.168.1.60", iphone_ua)

        self.assertEqual(handler.status_codes, [200], "承認済みペアリングはトークンを配布すること")
        issued_token = json.loads(handler.wfile.getvalue().decode("utf-8")).get("token", "")
        self.assertTrue(issued_token, "個別トークンが配布されること")

        after = verify_device_token(issued_token, db_path=self.db_path)
        self.assertIsNotNone(after)
        self.assertEqual(
            after.is_revoked,
            0,
            "♻️ 人間承認済みの再ペアリングは明示的な復帰操作として失効を解除すること",
        )
        mock_audit.assert_called_once()
        self.assertEqual(mock_audit.call_args.kwargs.get("source"), "pairing", "監査ログに経路を記録すること")


if __name__ == "__main__":
    unittest.main()
