#!/usr/bin/env python3
"""
ネオ秘書くん - 同期サーバー LAN自己治癒・静的配信 結合テスト (tests/test_sync_lan_selfheal.py)

2026-08-30 のスマホPWA全滅障害（pet.js 重複宣言による SyntaxError）の再発防止として、
スマホ実機と同じ経路を HTTP 結合レベルで自動検証する:

  1. 静的配信: GET / (index.html) は no-store ヘッダー付きで 200、最新の ?v= バスを参照する
  2. 静的配信: GET /pet.js が 200 で取得できる
  3. LAN自己治癒: ループバック(LAN内相当)からのトークンなし GET /api/status は 200 (閲覧許可)
  4. LAN自己治癒: ペアリング非開放でも GET /api/auth/token は LAN内から配布される (200)
  5. POST はトークン必須: トークンなし POST /api/action は 401 拒否
  6. Bearer トークン付き POST complete_task は 200 成功
  7. record_minigame_score は不正スコア (非数値/負値) を 0 にクランプする

設計上の注意:
- 本番アプリ (ポート8765) と競合しないよう、エフェメラルポート (0番) で
  ThreadingHTTPServer を起動する。
- 本番DB (neo_secretary.db) には一切触れないよう、database モジュールの
  永続化関数を unittest.mock で隔離する。
"""

import json
import logging
import re
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from unittest.mock import MagicMock, patch

# ※ 本ファイルは tests/ 配下にあるため、プロジェクトルートを import パスに追加
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import database
import life_dreamer
import local_sync_server
import suggest_engine

# テスト実行中にサーバーロガーがコンソールを荒らすのを防止
logging.getLogger("local_sync_server").setLevel(logging.CRITICAL)


def _try_json(raw: str) -> Dict[str, Any]:
    """レスポンスボディを JSON パースする（失敗時は raw 格納の辞書を返す）。

    Args:
        raw (str): レスポンスボディ文字列。

    Returns:
        Dict[str, Any]: パース済み辞書。パース不能な場合は {"raw": raw}。
    """
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"raw": raw}


class TestSyncLanSelfHeal(unittest.TestCase):
    """LAN自己治癒認証と静的配信の結合テスト (エフェメラルポート・DB隔離)"""

    @classmethod
    def setUpClass(cls) -> None:
        """エフェメラルポートでHTTPサーバーを起動し、DB依存をMockで隔離する。"""
        # --- DB隔離: ハンドラが参照する永続化関数を全てMockに差し替える ---
        cls.mock_get_tasks = MagicMock(return_value=[])
        cls.mock_get_upcoming_events = MagicMock(return_value=[])
        cls.mock_get_all_calendar_sources = MagicMock(return_value=[])
        cls.mock_get_habits = MagicMock(return_value=[])
        cls.mock_get_heatmap = MagicMock(return_value={})
        cls.mock_complete_task = MagicMock(return_value=None)
        cls.mock_record_score = MagicMock(return_value=42)
        cls.mock_get_high_score = MagicMock(return_value=100)

        cls._patchers = [
            patch.object(local_sync_server.database, "get_tasks", cls.mock_get_tasks),
            patch.object(local_sync_server.database, "get_upcoming_events", cls.mock_get_upcoming_events),
            patch.object(local_sync_server.database, "get_all_calendar_sources", cls.mock_get_all_calendar_sources),
            patch.object(local_sync_server.database, "get_habits_with_status", cls.mock_get_habits),
            patch.object(local_sync_server.database, "get_habit_heatmap_data", cls.mock_get_heatmap),
            patch.object(local_sync_server.database, "complete_task", cls.mock_complete_task),
            patch.object(local_sync_server.database, "record_minigame_score", cls.mock_record_score),
            patch.object(local_sync_server.database, "get_high_score", cls.mock_get_high_score),
        ]

        # --- 重い外部依存の隔離 (サジェスト生成 / 生活ドリーマー) ---
        suggest_engine_mock = MagicMock()
        suggest_engine_mock.generate_suggestions.return_value = []
        # 短期改善 Step 2: /api/status はキャッシュAPI経由になったためこちらも設定する
        suggest_engine_mock.get_cached_suggestions.return_value = []
        # /api/status は suggest_eng.config をそのまま JSON 化するため実値を設定する
        suggest_engine_mock.config = {"sources": {}, "news_keywords": []}
        cls._patchers.append(patch.object(
            suggest_engine, "get_suggestion_engine", MagicMock(return_value=suggest_engine_mock)
        ))

        life_dreamer_mock = MagicMock()
        life_dreamer_mock.get_life_state.return_value = {
            "current_activity": "resting", "weather": "sunny", "message": "", "history": []
        }
        cls._patchers.append(patch.object(
            life_dreamer, "get_life_dreamer", MagicMock(return_value=life_dreamer_mock)
        ))

        for p in cls._patchers:
            p.start()

        # --- エフェメラルポートでHTTPサーバー起動 (本番8765と競合しない) ---
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), local_sync_server.DeskPetSyncHandler)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        """HTTPサーバーとMockを後片付けする。"""
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.server_thread.join(timeout=5)
        for p in cls._patchers:
            p.stop()

    @classmethod
    def _request(cls, method: str, path: str, body: Optional[Dict[str, Any]] = None,
                 token: str = "") -> Tuple[int, Dict[str, Any], Dict[str, str]]:
        """テスト用HTTPサーバーへリクエストを送信する。

        Args:
            method (str): HTTPメソッド ('GET' / 'POST')。
            path (str): リクエストパス。
            body (Optional[Dict[str, Any]]): JSONボディ。
            token (str): Bearer認証トークン。空ならヘッダー未添付。

        Returns:
            Tuple[int, Dict[str, Any], Dict[str, str]]: (ステータス, JSONレスポンス, ヘッダー辞書)。
        """
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            f"http://127.0.0.1:{cls.port}{path}", data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                raw = r.read().decode("utf-8", errors="replace")
                return r.status, _try_json(raw), dict(r.headers.items())
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            return e.code, _try_json(raw), dict(e.headers.items())

    # ==========================================================================
    # 1. 静的配信 (キャッシュバス・no-store)
    # ==========================================================================
    def test_index_html_no_store_and_cache_bust(self):
        """GET / は no-store ヘッダー付きで 200、キャッシュバス3点同期が保たれること"""
        st, _, headers = self._request("GET", "/")
        self.assertEqual(st, 200, "GET / (index.html) が 200 で配信されること")
        cache_control = str(headers.get("Cache-Control", ""))
        self.assertIn("no-store", cache_control,
                      f"Cache-Control に no-store が含まれること (actual: {cache_control})")

        # --- キャッシュバス 3 点同期検証 (pet.js:10 / sw.js:5 / index.html ?v=) ---
        # index.html の 8 本の script タグ (easter_eggs/pixel_defense/arcade/新4ゲーム/pet)
        # が同一 ?v= を参照し、そのバージョンが sw.js の CACHE_NAME と
        # pet.js のキャッシュパージ許可キーと一致すること。
        # バージョン番号はハードコードせず、今後の更新にも追従できる構造にする。
        st, body, _ = self._request("GET", "/")
        html = str(body.get("raw", body))

        versions = re.findall(
            r'src="(?:easter_eggs|pixel_defense|minigame_arcade|minigame_itotooshi'
            r'|minigame_cyber_wire|minigame_setsuna|minigame_retro_breakout|pet)'
            r'\.js\?v=([\d.]+)"', html
        )
        self.assertEqual(len(versions), 8,
                         f"index.html は 8 本の JS に ?v= を付与すること (found: {versions})")
        self.assertEqual(len(set(versions)), 1,
                         f"8 本の script タグの ?v= が不一致 (actual: {versions})")
        cache_version = versions[0]

        sw_src = (PROJECT_ROOT / "web_pet" / "sw.js").read_text(encoding="utf-8")
        self.assertTrue(
            f"CACHE_NAME = 'neo-pet-v{cache_version}'" in sw_src
            or "self.WEB_PET_CACHE_NAME" in sw_src
            or "importScripts('./version.js')" in sw_src,
            f"sw.js CACHE_NAME が index.html の ?v={cache_version} または version.js と不一致",
        )

        pet_src = (PROJECT_ROOT / "web_pet" / "pet.js").read_text(encoding="utf-8")
        self.assertTrue(
            f"'neo-pet-v{cache_version}'" in pet_src
            or "WEB_PET_CACHE_NAME" in pet_src
            or "window.APP_VERSION" in pet_src,
            f"pet.js のキャッシュパージ許可キーが ?v={cache_version} または version.js と不一致",
        )

    def test_pet_js_served(self):
        """GET /pet.js および /pet_motion.js が 200 で取得でき、中核ロジックを含むこと"""
        st, body, headers = self._request("GET", "/pet.js")
        self.assertEqual(st, 200, "GET /pet.js が 200 で配信されること")
        cache_control = str(headers.get("Cache-Control", ""))
        self.assertIn("no-store", cache_control,
                      f"pet.js も no-store で配信されること (actual: {cache_control})")
        js_body = str(body.get("raw", body))
        self.assertIn("fetchStatus", js_body, "pet.js に fetchStatus が存在すること")

        # Seam 分割 (pet_motion.js) の配信検証
        st_motion, body_motion, _ = self._request("GET", "/pet_motion.js")
        self.assertEqual(st_motion, 200, "GET /pet_motion.js が 200 で配信されること")
        js_motion = str(body_motion.get("raw", body_motion))
        self.assertIn("updateLifeSprite", js_motion, "pet_motion.js に updateLifeSprite が存在すること")
        self.assertIn("CHARACTERS", js_motion, "pet_motion.js に CHARACTERS が存在すること")

    # ==========================================================================
    # 1.5 ゼロトラスト強化: トークン発行は「ペアリング中 or ループバック」のみ
    #     (2026-09-12: 共有Wi-Fi (192.168.x.x) での無条件発行ホールを塞ぐ)
    # ==========================================================================
    def _reset_pairing(self) -> None:
        """トークンマネージャのペアリング開放状態を初期化する。"""
        local_sync_server.get_sync_token_manager()._pairing_unlocked_until = 0.0

    def test_token_denied_for_lan_when_pairing_closed(self):
        """ペアリング未開放時、LAN (非ループバック) からの /api/auth/token は 403 で拒否されること"""
        self._reset_pairing()
        self.addCleanup(self._reset_pairing)
        with patch.object(
            local_sync_server.DeskPetSyncHandler,
            "_is_loopback",
            staticmethod(lambda ip: False),  # 127.0.0.1 接続を LAN クライアント扱いに偽装
        ):
            st, data, _ = self._request("GET", "/api/auth/token")
        self.assertEqual(st, 403, f"LAN からの無条件トークン発行は禁止 (actual: {st} {data})")

    def test_status_denied_for_lan_without_token(self):
        """トークンなし GET /api/status は LAN (非ループバック) からは拒否されること

        ゼロトラスト強化 (2026-09-12): 従来は同一LANなら無条件で閲覧できたが、
        共有Wi-Fiの第三者による個人データ (TODO・予定・生活状態) の覗き見を塞ぐ。
        未認証リクエストへの応答は 401 Unauthorized (トークン無し/不正の正セマンティクス)。
        403 は失効端末・エージェント専用API用であり、ここでは 401 が正。
        """
        with patch.object(
            local_sync_server.DeskPetSyncHandler,
            "_is_loopback",
            staticmethod(lambda ip: False),
        ):
            st, data, _ = self._request("GET", "/api/status")
        self.assertEqual(st, 401, f"LAN からの未認証閲覧は拒否 (actual: {st})")

    def test_oversized_body_rejected_with_413(self):
        """Content-Length が上限 (5MB) を超える POST は 413 で即時拒否されること (OOM DoS 防止)"""
        import socket as _socket

        raw = (
            b"POST /api/action HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: 6000000\r\n"
            b"Connection: close\r\n\r\n"
        )
        with _socket.create_connection(("127.0.0.1", self.port), timeout=10) as sock:
            sock.sendall(raw)
            sock.settimeout(10)
            response = b""
            try:
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    response += chunk
            except _socket.timeout:
                pass
        status_line = response.split(b"\r\n", 1)[0].decode("latin-1")
        self.assertIn("413", status_line, f"巨大ボディは 413 で拒否 (actual: {status_line})")

    def test_token_granted_for_lan_when_pairing_open(self):
        """ペアリング開放中 (QR接続ダイアログ表示中) は LAN からでもトークンを取得できること"""
        tm = local_sync_server.get_sync_token_manager()
        tm.unlock_pairing(duration_sec=60)
        self.addCleanup(self._reset_pairing)
        with patch.object(
            local_sync_server.DeskPetSyncHandler,
            "_is_loopback",
            staticmethod(lambda ip: False),
        ):
            st, data, _ = self._request("GET", "/api/auth/token")
        self.assertEqual(st, 200)
        self.assertTrue(len(str(data.get("token", ""))) >= 32, "トークンが取得できること")

    # ==========================================================================
    # 2. LAN自己治癒 (GET閲覧許可 + トークン配布)
    # ==========================================================================
    def test_status_without_token_from_lan_allowed(self):
        """トークンなし GET /api/status は LAN内から閲覧許可される (自己治癒)"""
        st, data, _ = self._request("GET", "/api/status")
        self.assertEqual(st, 200, f"LAN内トークンなし GET /api/status は 200 であること (actual: {st})")
        self.assertEqual(data.get("status"), "ok", "/api/status が status=ok を返すこと")
        self.assertIn("pet_state", data, "/api/status が pet_state を含むこと")

    def test_token_self_healing_distribution(self):
        """ペアリング非開放でも GET /api/auth/token は LAN内から配布される (自己治癒)"""
        st, data, _ = self._request("GET", "/api/auth/token")
        self.assertEqual(st, 200, f"LAN内トークン要求は 200 であること (actual: {st})")
        token = str(data.get("token", ""))
        self.assertGreaterEqual(len(token), 32, f"トークンが十分な長さで配布されること (len={len(token)})")

    # ==========================================================================
    # 3. POST は Bearer 必須 (書き込み系はトークン無しでは拒否)
    # ==========================================================================
    def test_post_action_requires_token(self):
        """トークンなし POST /api/action は 401 で拒否されること"""
        st, _, _ = self._request("POST", "/api/action", body={"action": "complete_task", "task_id": 1})
        self.assertEqual(st, 401, f"トークンなし POST は 401 で拒否されること (actual: {st})")
        self.mock_complete_task.assert_not_called()

    def test_post_complete_task_with_token(self):
        """Bearer トークン付き POST complete_task は 200 成功すること"""
        _, token_data, _ = self._request("GET", "/api/auth/token")
        token = str(token_data.get("token", ""))
        st, data, _ = self._request(
            "POST", "/api/action", body={"action": "complete_task", "task_id": 101}, token=token
        )
        self.assertEqual(st, 200, f"トークン付き POST は 200 であること (actual: {st})")
        self.assertEqual(data.get("status"), "success", "complete_task が success を返すこと")
        self.mock_complete_task.assert_called_once_with(101)

    # ==========================================================================
    # 4. ミニゲームスコアのクランプ (2026-08-30 P1-3 対策)
    # ==========================================================================
    def test_minigame_score_clamped_to_zero(self):
        """record_minigame_score は負値・非数値スコアを 0 にクランプすること"""
        _, token_data, _ = self._request("GET", "/api/auth/token")
        token = str(token_data.get("token", ""))

        # 負値 (文字列) のクランプ
        st, data, _ = self._request(
            "POST", "/api/action",
            body={"action": "record_minigame_score", "game_id": "pixel_defense", "score": "-500"},
            token=token
        )
        self.assertEqual(st, 200, f"スコア記録リクエストは 200 であること (actual: {st})")
        self.assertEqual(data.get("score"), 0, f"負値スコアが 0 にクランプされること (actual: {data})")

        # 非数値のクランプ (int変換失敗 → 0)
        st, data, _ = self._request(
            "POST", "/api/action",
            body={"action": "record_minigame_score", "game_id": "pixel_defense", "score": "abc"},
            token=token
        )
        self.assertEqual(st, 200, f"非数値スコアでも 200 が返ること (actual: {st})")
        self.assertEqual(data.get("score"), 0, f"非数値スコアが 0 にクランプされること (actual: {data})")

    # ==========================================================================
    # 5. ミニゲームハイスコア取得 (GET /api/minigame/high・レトロアーケード拡張)
    # ==========================================================================
    def test_minigame_high_endpoint_returns_score(self):
        """Bearer 付き GET /api/minigame/high は high_score を JSON で返すこと"""
        _, token_data, _ = self._request("GET", "/api/auth/token")
        token = str(token_data.get("token", ""))

        st, data, _ = self._request(
            "GET", "/api/minigame/high?game_id=pixel_defense", token=token
        )
        self.assertEqual(st, 200, f"ハイスコア取得は 200 であること (actual: {st})")
        self.assertEqual(data.get("status"), "ok", "ハイスコア取得が status=ok を返すこと")
        self.assertEqual(data.get("game_id"), "pixel_defense", "game_id がエコーされること")
        self.assertEqual(data.get("high_score"), 100,
                         f"Mock化した get_high_score の値が返ること (actual: {data})")
        self.mock_get_high_score.assert_called_with("pixel_defense")

    def test_minigame_high_endpoint_requires_game_id(self):
        """game_id 未指定の GET /api/minigame/high は 400 で拒否されること"""
        _, token_data, _ = self._request("GET", "/api/auth/token")
        token = str(token_data.get("token", ""))

        st, data, _ = self._request("GET", "/api/minigame/high", token=token)
        self.assertEqual(st, 400, f"game_id 未指定は 400 であること (actual: {st})")
        self.assertEqual(data.get("status"), "error", "エラー時に status=error を返すこと")

    def test_minigame_high_endpoint_all_five_game_ids(self):
        """新4ゲームを含む全5種の game_id でハイスコア取得が成功すること"""
        _, token_data, _ = self._request("GET", "/api/auth/token")
        token = str(token_data.get("token", ""))

        for game_id in ("pixel_defense", "itotooshi", "cyber_wire", "setsuna", "retro_breakout"):
            st, data, _ = self._request(
                "GET", f"/api/minigame/high?game_id={game_id}", token=token
            )
            self.assertEqual(st, 200, f"game_id={game_id} の取得は 200 であること (actual: {st})")
            self.assertEqual(data.get("high_score"), 100,
                             f"game_id={game_id} のハイスコアが返ること (actual: {data})")


if __name__ == "__main__":
    unittest.main(verbosity=2)
