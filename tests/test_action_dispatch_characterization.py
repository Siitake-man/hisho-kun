#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - POST /api/action ＆ POSTパス系API characterization テスト
(tests/test_action_dispatch_characterization.py)

P2③ 分割リファクタ (local_sync_server.do_POST の God Function →
アクションディスパッチテーブル + 機能別モジュール api_tasks / api_agent_bridge / api_calendar)
に先立ち、現行の振る舞いを固定する (characterization test)。
リファクタ前後で本テストが同一結果になることで、外部契約
(PWA / エージェント互換) の無変更を構造的に保証する。

検証観点:
  1. 既知アクションの正常系 (complete_task / reopen_task / toggle_habit / add_habit /
     update_task / delete_task / list_task_lists / get_tasks_view / ping_test / quick_add_task)
  2. パラメータ欠落時の fall-through 振る舞い (旧仕様の unknown action エラー応答)
  3. 未知アクションの明示エラー応答
  4. POST パス系 (agent/ask, agent/respond, agent/dismiss_completed, agent/notify,
     test_buzz, webhook/task) のディスパッチ

設計上の注意:
- エフェメラルポートで ThreadingHTTPServer を起動 (本番8765と競合しない)
- database 永続化関数は unittest.mock で隔離 (本番DB不変)
"""

import json
import logging
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

# ※ 本ファイルは tests/ 配下にあるため、プロジェクトルートを import パスに追加
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import local_sync_server
import webhook_tools

# テスト実行中にサーバーロガーがコンソールを荒らすのを防止
logging.getLogger("local_sync_server").setLevel(logging.CRITICAL)


def _try_json(raw: str) -> Dict[str, Any]:
    """レスポンスボディを JSON パースする (失敗時は raw 格納の辞書を返す)。"""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"raw": raw}


class TestActionDispatchCharacterization(unittest.TestCase):
    """POST /api/action 及び POST パス系APIの振る舞いを固定する"""

    @classmethod
    def setUpClass(cls) -> None:
        """エフェメラルポートでHTTPサーバーを起動し、DB依存をMockで隔離する。"""
        cls.mock_complete_task = MagicMock(return_value=None)
        cls.mock_reopen_task = MagicMock(return_value=True)
        cls.mock_toggle_habit_log = MagicMock(return_value=False)
        cls.mock_create_habit = MagicMock(return_value=77)
        cls.mock_create_task = MagicMock(return_value=55)
        cls.mock_update_task = MagicMock(return_value=True)
        cls.mock_delete_task = MagicMock(return_value=True)
        cls.mock_get_task_lists = MagicMock(return_value=[
            SimpleNamespace(id=1, name="仕事", emoji="💼", parent_id=None, sort_order=0),
        ])
        cls.mock_get_tasks = MagicMock(return_value=[
            SimpleNamespace(
                id=9, title="テストタスク", priority=2, due_date=1756500000000,
                tags="a,b", list_id=1, importance_flag=True, urgency_flag=False,
                recurrence="daily",
            ),
        ])

        cls._patchers: List[Any] = [
            patch.object(local_sync_server.database, "complete_task", cls.mock_complete_task),
            patch.object(local_sync_server.database, "reopen_task", cls.mock_reopen_task),
            patch.object(local_sync_server.database, "toggle_habit_log", cls.mock_toggle_habit_log),
            patch.object(local_sync_server.database, "create_habit", cls.mock_create_habit),
            patch.object(local_sync_server.database, "create_task", cls.mock_create_task),
            patch.object(local_sync_server.database, "update_task", cls.mock_update_task),
            patch.object(local_sync_server.database, "delete_task", cls.mock_delete_task),
            patch.object(local_sync_server.database, "get_task_lists", cls.mock_get_task_lists),
            patch.object(local_sync_server.database, "get_tasks", cls.mock_get_tasks),
        ]
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

    def setUp(self) -> None:
        """各テスト前にMockの呼び出し履歴と戻り値をリセットして再設定する。

        ※ reset_mock() は呼び出し履歴のみリセットし、return_value は
          unittest の仕様上デフォルト (子MagicMock) へ戻らないため、
          ここで明示的に再設定してテスト順序非依存を保証する。
        """
        for m in (
            self.mock_complete_task, self.mock_reopen_task, self.mock_toggle_habit_log,
            self.mock_create_habit, self.mock_create_task, self.mock_update_task,
            self.mock_delete_task, self.mock_get_task_lists, self.mock_get_tasks,
        ):
            m.reset_mock(side_effect=True)
        self.mock_complete_task.return_value = None
        self.mock_reopen_task.return_value = True
        self.mock_toggle_habit_log.return_value = False
        self.mock_create_habit.return_value = 77
        self.mock_create_task.return_value = 55
        self.mock_update_task.return_value = True
        self.mock_delete_task.return_value = True
        self.mock_get_task_lists.return_value = [
            SimpleNamespace(id=1, name="仕事", emoji="💼", parent_id=None, sort_order=0),
        ]
        self.mock_get_tasks.return_value = [
            SimpleNamespace(
                id=9, title="テストタスク", priority=2, due_date=1756500000000,
                tags="a,b", list_id=1, importance_flag=True, urgency_flag=False,
                recurrence="daily",
            ),
        ]

    @classmethod
    def _request(cls, method: str, path: str, body: Optional[Dict[str, Any]] = None,
                 token: str = "") -> Tuple[int, Dict[str, Any]]:
        """テスト用HTTPサーバーへリクエストを送信する。"""
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            f"http://127.0.0.1:{cls.port}{path}", data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status, _try_json(r.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            return e.code, _try_json(e.read().decode("utf-8", errors="replace"))

    @classmethod
    def _get_token(cls) -> str:
        """ループバック接続で配布される同期トークンを取得する。"""
        _, data = cls._request("GET", "/api/auth/token")
        return str(data.get("token", ""))

    def _post_action(self, payload: Dict[str, Any], token: str) -> Tuple[int, Dict[str, Any]]:
        """Bearer 付きで POST /api/action を発行する。"""
        return self._request("POST", "/api/action", body=payload, token=token)

    # ==========================================================================
    # 1. アクション正常系
    # ==========================================================================
    def test_complete_task_success(self):
        """complete_task は DB を完了し success を返す"""
        token = self._get_token()
        st, data = self._post_action({"action": "complete_task", "task_id": 101}, token)
        self.assertEqual(st, 200)
        self.assertEqual(data.get("status"), "success")
        self.assertEqual(data.get("task_id"), 101)
        self.mock_complete_task.assert_called_once_with(101)

    def test_reopen_task_reflects_db_result(self):
        """reopen_task は DB 戻り値の真偽を status に反映する"""
        token = self._get_token()
        self.mock_reopen_task.return_value = True
        st, data = self._post_action({"action": "reopen_task", "task_id": 7}, token)
        self.assertEqual(data.get("status"), "success")
        self.mock_reopen_task.return_value = False
        st, data = self._post_action({"action": "reopen_task", "task_id": 7}, token)
        self.assertEqual(data.get("status"), "error")

    def test_toggle_habit_without_bond_xp_when_undone(self):
        """toggle_habit で未達成 (False) の場合は親愛度XPを加算しない"""
        fake_cm_module = MagicMock()
        with patch.dict(sys.modules, {"character_manager": fake_cm_module}):
            token = self._get_token()
            st, data = self._post_action({"action": "toggle_habit", "habit_id": 3}, token)
        self.assertEqual(data.get("status"), "success")
        self.assertFalse(data.get("is_done"))
        fake_cm_module.get_character_manager.assert_not_called()

    def test_toggle_habit_grants_bond_xp_when_done(self):
        """toggle_habit で達成 (True) の場合は親愛度XP +10 を加算する"""
        fake_cm = MagicMock()
        fake_cm_module = MagicMock()
        fake_cm_module.get_character_manager.return_value = fake_cm
        self.mock_toggle_habit_log.return_value = True
        with patch.dict(sys.modules, {"character_manager": fake_cm_module}):
            token = self._get_token()
            st, data = self._post_action({"action": "toggle_habit", "habit_id": 3}, token)
        self.assertTrue(data.get("is_done"))
        fake_cm.add_bond_xp.assert_called_once_with(10)

    def test_add_habit_creates_habit(self):
        """add_habit は Habit モデルで create_habit を呼ぶ"""
        token = self._get_token()
        st, data = self._post_action({"action": "add_habit", "title": "_water", "emoji": "💧"}, token)
        self.assertEqual(data.get("status"), "success")
        self.assertEqual(data.get("habit_id"), 77)
        created_habit = self.mock_create_habit.call_args.args[0]
        self.assertEqual(created_habit.title, "_water")
        self.assertEqual(created_habit.emoji, "💧")

    def test_update_task_field_whitelist(self):
        """update_task はホワイトリスト項目のみ反映し priority をクランプする"""
        token = self._get_token()
        st, data = self._post_action({
            "action": "update_task", "task_id": 9,
            "title": " 新しいタイトル ", "due_date": 0, "priority": 7,
            "tags": " x ", "list_id": 0, "importance_flag": None, "urgency_flag": True,
        }, token)
        self.assertEqual(data.get("status"), "success")
        task_id, fields = self.mock_update_task.call_args.args
        self.assertEqual(task_id, 9)
        self.assertEqual(fields, {
            "title": "新しいタイトル", "due_date": None, "priority": 3,
            "tags": "x", "list_id": None, "importance_flag": None, "urgency_flag": True,
        })

    def test_delete_task_success(self):
        """delete_task は DB 削除を実行し success を返す"""
        token = self._get_token()
        st, data = self._post_action({"action": "delete_task", "task_id": 12}, token)
        self.assertEqual(data.get("status"), "success")
        self.mock_delete_task.assert_called_once_with(12)

    def test_list_task_lists_payload_shape(self):
        """list_task_lists は id/name/emoji/parent_id/sort_order を返す"""
        token = self._get_token()
        st, data = self._post_action({"action": "list_task_lists"}, token)
        self.assertEqual(data.get("status"), "success")
        self.assertEqual(data.get("lists"), [{
            "id": 1, "name": "仕事", "emoji": "💼", "parent_id": None, "sort_order": 0,
        }])

    def test_get_tasks_view_payload_shape(self):
        """get_tasks_view は拡充フィールド付きタスク配列を返す (DTO検証通過)"""
        token = self._get_token()
        st, data = self._post_action({"action": "get_tasks_view"}, token)
        self.assertEqual(data.get("status"), "success")
        tasks = data.get("tasks")
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0], {
            "id": 9, "title": "テストタスク", "priority": 2, "due_date": 1756500000000,
            "tags": "a,b", "list_id": 1, "importance_flag": True,
            "urgency_flag": False, "recurrence": "daily",
        })

    def test_ping_test_returns_pong(self):
        """ping_test は pong と整数の server_time を返す"""
        token = self._get_token()
        st, data = self._post_action({"action": "ping_test"}, token)
        self.assertEqual(data.get("status"), "pong")
        self.assertIsInstance(data.get("server_time"), int)

    def test_quick_add_task_parses_and_creates(self):
        """quick_add_task は task_parser 経由でタスクを生成する"""
        parsed = SimpleNamespace(
            title="牛乳を買う", due_date=None, priority=2, tags=[],
            importance=True, urgency=False, recurrence=None,
        )
        fake_tp = MagicMock()
        fake_tp.parse_input.return_value = parsed
        fake_tp.tags_to_db_string.return_value = ""
        with patch.dict(sys.modules, {"task_parser": fake_tp}):
            token = self._get_token()
            st, data = self._post_action({"action": "quick_add_task", "text": "明日 牛乳を買う"}, token)
        self.assertEqual(data.get("status"), "success")
        self.assertEqual(data.get("task_id"), 55)
        self.assertEqual(data.get("title"), "牛乳を買う")

    # ==========================================================================
    # 2. fall-through ＆ 未知アクション (旧仕様の意味論を固定)
    # ==========================================================================
    def test_missing_param_returns_silent_empty_response(self):
        """task_id 欠落の complete_task は現行仕様では無応答200 (空ボディ) になる

        ※ 既知の技術的負債: elif連鎖の意味論上、既知アクションのパラメータ欠落は
          else節 (unknown action エラー) に到達せず、ヘッダーのみでボディ空の
          200 が返る。クライアント互換維持のため本テストで現行の振る舞いを固定する。
        """
        token = self._get_token()
        st, data = self._post_action({"action": "complete_task"}, token)
        self.assertEqual(st, 200)
        self.assertEqual(data, {"raw": ""}, "パラメータ欠落時は空ボディの200であること")
        self.mock_complete_task.assert_not_called()

    def test_quick_add_task_empty_text_returns_silent_empty_response(self):
        """text 欠落の quick_add_task は現行仕様では無応答200 (空ボディ) になる"""
        token = self._get_token()
        st, data = self._post_action({"action": "quick_add_task", "text": "  "}, token)
        self.assertEqual(st, 200)
        self.assertEqual(data, {"raw": ""})

    def test_pomodoro_without_gui_returns_silent_empty_response(self):
        """GUI 未起動時の start_pomodoro は現行仕様では無応答200 (空ボディ) になる"""
        token = self._get_token()
        st, data = self._post_action({"action": "start_pomodoro", "minutes": 25}, token)
        self.assertEqual(st, 200)
        self.assertEqual(data, {"raw": ""})

    def test_unknown_action_returns_error(self):
        """未知のアクションは明示的に error を返す"""
        token = self._get_token()
        st, data = self._post_action({"action": "no_such_action"}, token)
        self.assertEqual(st, 200)
        self.assertEqual(data.get("status"), "error")
        self.assertEqual(data.get("message"), "unknown action: no_such_action")

    def test_unauthorized_post_is_rejected(self):
        """トークンなし POST は 401 で拒否される"""
        st, data = self._request("POST", "/api/action", body={"action": "ping_test"})
        self.assertEqual(st, 401)

    # ==========================================================================
    # 3. POST パス系ディスパッチ
    # ==========================================================================
    def test_agent_ask_creates_approval_and_waits(self):
        """agent/ask は BridgeHub に承認要請を作成し決定を待つ"""
        fake_req = MagicMock()
        fake_req.request_id = "req_1"
        fake_req.wait.return_value = "approve"
        fake_req.decision_message = "ok"
        fake_hub = MagicMock()
        fake_hub.create_approval_request.return_value = fake_req
        token = self._get_token()
        with patch.object(local_sync_server, "get_bridge_hub", MagicMock(return_value=fake_hub)):
            st, data = self._request("POST", "/api/agent/ask", body={
                "agent_name": "Claude", "command": "dir", "wait_decision": True,
            }, token=token)
        self.assertEqual(data.get("status"), "success")
        self.assertEqual(data.get("decision"), "approve")
        fake_req.wait.assert_called_once()

    def test_agent_respond_dispatches_to_hub(self):
        """agent/respond は BridgeHub.respond_checked に委譲する"""
        fake_hub = MagicMock()
        fake_hub.respond_checked.return_value = (True, None)
        token = self._get_token()
        with patch.object(local_sync_server, "get_bridge_hub", MagicMock(return_value=fake_hub)):
            st, data = self._request("POST", "/api/agent/respond", body={
                "request_id": "req_x", "decision": "approve",
            }, token=token)
        self.assertEqual(data.get("status"), "success")
        fake_hub.respond_checked.assert_called_once()

    def test_agent_dismiss_completed(self):
        """agent/dismiss_completed は完了カードを閉じ success を返す"""
        fake_hub = MagicMock()
        token = self._get_token()
        with patch.object(local_sync_server, "get_bridge_hub", MagicMock(return_value=fake_hub)):
            st, data = self._request("POST", "/api/agent/dismiss_completed", body={}, token=token)
        self.assertEqual(data.get("status"), "success")
        fake_hub.dismiss_completed.assert_called_once()

    def test_agent_notify_sets_completed_event(self):
        """agent/notify は BridgeHub へ完了イベントを登録し success を返す"""
        fake_hub = MagicMock()
        token = self._get_token()
        with patch.object(local_sync_server, "get_bridge_hub", MagicMock(return_value=fake_hub)):
            st, data = self._request("POST", "/api/agent/notify", body={
                "agent_name": "Codex", "title": "完了", "message": "テスト終了",
            }, token=token)
        self.assertEqual(data.get("status"), "success")
        fake_hub.set_completed_event.assert_called_once()

    def test_test_buzz_triggers_buzz(self):
        """test_buzz は LinkMonitor の trigger_buzz を発火する"""
        fake_monitor = MagicMock()
        token = self._get_token()
        with patch.object(local_sync_server, "get_link_monitor", MagicMock(return_value=fake_monitor)):
            st, data = self._request("POST", "/api/test_buzz", body={}, token=token)
        self.assertEqual(data.get("status"), "buzz_triggered")
        fake_monitor.trigger_buzz.assert_called_once()

    def test_webhook_task_creates_task(self):
        """webhook/task は Webhook認証を通過した上でタスク登録に委譲する"""
        fake_result = {"status": "success", "task_id": 5, "title": "Webhookタスク"}
        with patch.object(webhook_tools, "get_webhook_config", MagicMock(return_value={})), \
             patch.object(webhook_tools, "process_incoming_task_webhook", MagicMock(return_value=fake_result)):
            token = self._get_token()
            st, data = self._request("POST", "/api/webhook/task", body={"title": "Webhookタスク"}, token=token)
        self.assertEqual(data.get("status"), "success")
        self.assertEqual(data.get("task_id"), 5)

    def test_unknown_post_path_returns_404(self):
        """未知の POST パスは 404 になる"""
        token = self._get_token()
        st, data = self._request("POST", "/api/no_such_path", body={}, token=token)
        self.assertEqual(st, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
