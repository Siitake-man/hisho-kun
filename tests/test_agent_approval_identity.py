# -*- coding: utf-8 -*-
"""承認主体 (identity) ベースの自己承認防止チェックの回帰テスト (手帳 ID 52)。

障害 (2026-09-26 実機事故):
    スマホ (Tailscale Serve 経由) から POST /api/agent/respond で承認すると
    「自己承認は禁止されています」で拒否された。自己承認防止チェックが IP 一致
    判定のため、Serve プロキシの同一化により requester_ip == responder_ip
    (両者 127.0.0.1) が誤成立していた。

修理設計:
    「IP 一致」を「認証主体 (identity) 一致」判定へ置換する。

    - requester_identity: 承認要請を作成した認証主体
      (PC内エージェント経由なら "agent")
    - responder_identity: 決定した認証主体 (スマホ PWA なら "device:<uuid>")

    判定規則 (Hub.respond_checked):
    1. responder_identity と requester_identity が両者非空かつ一致 → 拒否
       (agent が自分の質問に答える / 同一端末が自己承認 を両方遮断)
    2. responder_identity が非空なら IP チェックは行わない
       (Serve スマホ承認: requester="agent"/ip=127.0.0.1 vs
       responder="device:uuid"/ip=127.0.0.1 は成立する)
    3. responder_identity が空 (unknown) のときのみ旧 IP 一致チェックへ
       フォールバック (後方互換)
"""

import io
import json
import logging
import os
import tempfile
import threading
import time
import unittest
from typing import Any, Dict
from unittest.mock import patch

import api_agent_bridge
from api_context import ApiContext
from local_sync_server import AgentBridgeHub, AgentBridgeRequest


class MockSyncHandler:
    """テスト用の軽量 HTTP ハンドラモック (identity 付与対応)。"""

    def __init__(self, client_ip: str = "127.0.0.1") -> None:
        self.wfile = io.BytesIO()
        self.headers: Dict[str, str] = {}
        self.status_code = 200
        self.client_address = (client_ip, 54321)

    def send_response(self, code: int) -> None:
        self.status_code = code

    def send_header(self, key: str, value: str) -> None:
        self.headers[key] = value

    def end_headers(self) -> None:
        pass

    def _set_cors_headers(self) -> None:
        pass

    def get_json_response(self) -> Dict[str, Any]:
        """書き込まれた JSON レスポンスをパースして返す。"""
        data = self.wfile.getvalue().decode("utf-8")
        return json.loads(data) if data else {}


def make_ctx(
    body: Dict[str, Any],
    client_ip: str = "127.0.0.1",
    auth_identity: str = "",
) -> Any:
    """テスト用 ApiContext を生成する。

    Args:
        body: リクエストボディ。
        client_ip: 接続元IP。
        auth_identity: 認証主体 (pc-loopback / agent / device:<uuid> 等)。

    Returns:
        Any: ApiContext。identity が空なら旧来の3引数構成を流用する。
    """
    handler = MockSyncHandler(client_ip=client_ip)
    payload = json.dumps(body).encode("utf-8")
    # auth_identity フィールドは Green 実装で追加される (Red 時点では TypeError になる)
    return ApiContext(
        handler=handler,
        body=payload,
        client_ip=client_ip,
        user_agent="NeoHishoDeskPet/1.0",
        auth_identity=auth_identity,
    )


class TestIdentityBasedSelfApprovalGuard(unittest.TestCase):
    """AgentBridgeHub.respond_checked の identity ベース自己承認防止テスト。"""

    def setUp(self) -> None:
        """テストごとにクリーンな Hub を用意する。"""
        self.hub = AgentBridgeHub()

    # ------------------------------------------------------------------
    # 1. Serve スマホ承認シナリオ (本修理の中核・旧実装は誤爆していた)
    # ------------------------------------------------------------------
    def test_serve_phone_approval_succeeds_with_distinct_identity(self) -> None:
        """Serve 経由スマホ承認: requester="agent" vs responder="device:uuid-1" は成立する。

        両者の IP は Serve プロキシ同一化で両者 127.0.0.1 になるが、
        認証主体が異なるため人間による正当な承認として受理する。
        """
        req = self.hub.create_approval_request(
            agent_name="Antigravity",
            command="pytest -v",
            summary="テスト実行の承認要請",
            requester_ip="127.0.0.1",
            requester_identity="agent",
        )

        ok, reason = self.hub.respond_checked(
            request_id=req.request_id,
            decision="approve",
            message="スマホから人間が承認",
            responder_ip="127.0.0.1",
            responder_identity="device:uuid-1",
        )

        self.assertTrue(
            ok,
            "Serve 経由スマホ承認 (requester=agent vs responder=device) は "
            "IP 一致があっても identity が異なるため成立しなければならない "
            "(手帳 ID 52 の回帰)",
        )
        self.assertEqual(reason, "ok")
        self.assertEqual(req.status, "approve")

    # ------------------------------------------------------------------
    # 2. 同一端末による自己承認の拒否
    # ------------------------------------------------------------------
    def test_same_device_self_approval_denied(self) -> None:
        """同一端末 (identity 一致) が自分の要請を承認する場合は拒否される。"""
        req = self.hub.create_approval_request(
            agent_name="MaliciousAgent",
            command="rm -rf /",
            summary="危険コマンド",
            requester_ip="192.168.1.50",
            requester_identity="device:uuid-1",
        )

        ok, reason = self.hub.respond_checked(
            request_id=req.request_id,
            decision="approve",
            message="自分の端末から自己承認",
            responder_ip="192.168.1.50",
            responder_identity="device:uuid-1",
        )

        self.assertFalse(ok, "同一 identity からの自己承認は拒否されなければならない")
        self.assertEqual(reason, "self_approve_denied")
        self.assertEqual(
            req.status, "pending", "拒否後もリクエストは pending のまま保持されること"
        )

    # ------------------------------------------------------------------
    # 3. agent による自己応答の拒否
    # ------------------------------------------------------------------
    def test_agent_self_response_denied(self) -> None:
        """agent が自分の質問へ応答する場合も identity 一致で拒否される。"""
        req = self.hub.create_question_request(
            agent_name="AutoAgent",
            question="続行しますか?",
            requester_ip="127.0.0.1",
            requester_identity="agent",
        )

        ok, reason = self.hub.respond_checked(
            request_id=req.request_id,
            decision="answered",
            message="自分で回答します",
            responder_ip="127.0.0.1",
            responder_identity="agent",
        )

        self.assertFalse(ok, "agent の自己応答は identity 一致で拒否されなければならない")
        self.assertEqual(reason, "self_approve_denied")
        self.assertEqual(req.status, "pending")

    # ------------------------------------------------------------------
    # 4. 後方互換: identity が空 (unknown) のときのみ IP 一致チェックへフォールバック
    # ------------------------------------------------------------------
    def test_fallback_to_ip_check_when_responder_identity_blank(self) -> None:
        """responder_identity が空の場合は旧 IP 一致チェックへフォールバックする。"""
        req = self.hub.create_approval_request(
            agent_name="LegacyClient",
            command="git push",
            summary="旧クライアント",
            requester_ip="192.168.1.50",
            requester_identity="",
        )

        ok, reason = self.hub.respond_checked(
            request_id=req.request_id,
            decision="approve",
            message="identity 不明での同一IP応答",
            responder_ip="192.168.1.50",
            responder_identity="",
        )

        self.assertFalse(
            ok,
            "responder_identity が空の場合は IP 一致チェックへフォールバックして拒否すること",
        )
        self.assertEqual(reason, "self_approve_denied")

    def test_fallback_ip_check_does_not_fire_when_identity_nonblank(self) -> None:
        """responder_identity が非空なら IP 一致でも identity 判定を優先する。"""
        req = self.hub.create_approval_request(
            agent_name="Antigravity",
            command="pytest",
            summary="Serve 経由",
            requester_ip="127.0.0.1",
            requester_identity="agent",
        )

        ok, reason = self.hub.respond_checked(
            request_id=req.request_id,
            decision="approve",
            message="Serve 経由スマホ",
            responder_ip="127.0.0.1",
            responder_identity="device:uuid-2",
        )

        self.assertTrue(
            ok,
            "responder_identity が非空の場合は IP 一致であっても identity 判定を優先すること",
        )
        self.assertEqual(reason, "ok")
        self.assertEqual(req.status, "approve")

    def test_ip_match_still_denies_when_both_identities_blank(self) -> None:
        """両者 identity が空で IP 一致の場合は後方互換で拒否される。"""
        req = self.hub.create_approval_request(
            agent_name="LegacyAgent",
            command="format C:",
            summary="旧式攻撃",
            requester_ip="192.168.1.77",
            requester_identity="",
        )

        ok, reason = self.hub.respond_checked(
            request_id=req.request_id,
            decision="approve",
            message="同一IP自己承認",
            responder_ip="192.168.1.77",
            responder_identity="",
        )

        self.assertFalse(ok, "両者 identity 空 + 同一 IP は旧ロジック通り拒否すること")
        self.assertEqual(reason, "self_approve_denied")

    # ------------------------------------------------------------------
    # 5. 期限切れ挙動は変更されないこと
    # ------------------------------------------------------------------
    def test_expired_request_rejection_unchanged(self) -> None:
        """期限切れリクエストへの応答は identity の有無にかかわらず expired で拒否される。"""
        req = self.hub.create_approval_request(
            agent_name="TestAgent",
            command="git pull",
            summary="コード更新",
            requester_ip="127.0.0.1",
            requester_identity="agent",
        )
        req.timeout_at = time.time() - 5.0

        ok, reason = self.hub.respond_checked(
            request_id=req.request_id,
            decision="approve",
            message="",
            responder_ip="127.0.0.1",
            responder_identity="device:uuid-1",
        )

        self.assertFalse(ok, "期限切れリクエストは identity 成立条件でも拒否されること")
        self.assertEqual(reason, "expired")
        self.assertEqual(req.status, "expired")

    # ------------------------------------------------------------------
    # 6. AgentBridgeRequest が requester_identity を保持・to_dict に同梱する
    # ------------------------------------------------------------------
    def test_requester_identity_stored_on_request_and_dict(self) -> None:
        """AgentBridgeRequest が requester_identity を保持し to_dict にも同梱する。"""
        req = self.hub.create_approval_request(
            agent_name="ClaudeCode",
            command="pytest",
            summary="identity 保持確認",
            requester_ip="127.0.0.1",
            requester_identity="agent",
        )

        self.assertEqual(
            req.requester_identity,
            "agent",
            "AgentBridgeRequest は requester_identity を保持しなければならない",
        )
        d = req.to_dict()
        self.assertIn(
            "requester_identity",
            d,
            "to_dict() に requester_identity が含まれなければならない",
        )
        self.assertEqual(d["requester_identity"], "agent")

    def test_requester_identity_defaults_blank(self) -> None:
        """requester_identity 未指定時の既定値は空文字 (後方互換) であること。"""
        req = self.hub.create_approval_request(
            agent_name="Legacy",
            command="echo hi",
            summary="デフォルト確認",
        )
        self.assertEqual(
            req.requester_identity,
            "",
            "従来呼び出し (identity 未指定) は空文字で動作する後方互換を維持すること",
        )


class TestAskApiPassesIdentity(unittest.TestCase):
    """/api/agent/ask 系が ctx.auth_identity を hub 生成へ渡すことの検証。"""

    def setUp(self) -> None:
        self.hub = AgentBridgeHub()

    def test_handle_agent_ask_passes_auth_identity(self) -> None:
        """handle_agent_ask は ctx.auth_identity を create_approval_request へ渡す。"""
        ctx = make_ctx(
            {
                "agent_name": "TestAgent",
                "command": "git push origin main",
                "wait_decision": False,
            },
            client_ip="127.0.0.1",
            auth_identity="agent",
        )
        with patch("local_sync_server.get_bridge_hub", return_value=self.hub):
            api_agent_bridge.handle_agent_ask(ctx)

        self.assertEqual(len(self.hub.pending_requests), 1)
        req = list(self.hub.pending_requests.values())[0]
        self.assertEqual(
            req.requester_identity,
            "agent",
            "handle_agent_ask は ctx.auth_identity を requester_identity として保持すること",
        )

    def test_handle_agent_ask_input_passes_auth_identity(self) -> None:
        """handle_agent_ask_input は ctx.auth_identity を create_question_request へ渡す。"""
        ctx = make_ctx(
            {
                "agent_name": "InputAgent",
                "question": "どちらにしますか?",
                "choices": ["A", "B"],
                "wait_decision": False,
            },
            client_ip="127.0.0.1",
            auth_identity="agent",
        )
        with patch("local_sync_server.get_bridge_hub", return_value=self.hub):
            api_agent_bridge.handle_agent_ask_input(ctx)

        self.assertEqual(len(self.hub.pending_requests), 1)
        req = list(self.hub.pending_requests.values())[0]
        self.assertEqual(
            req.requester_identity,
            "agent",
            "handle_agent_ask_input も requester_identity を hub へ渡すこと",
        )

    def test_handle_agent_respond_passes_responder_identity(self) -> None:
        """handle_agent_respond は ctx.auth_identity を respond_checked へ渡す。"""
        req = self.hub.create_approval_request(
            agent_name="MobileAgent",
            command="echo done",
            summary="応答 identity 検証",
            requester_ip="127.0.0.1",
            requester_identity="agent",
        )

        ctx = make_ctx(
            {"request_id": req.request_id, "decision": "approve", "message": "OK"},
            client_ip="127.0.0.1",
            auth_identity="device:uuid-9",
        )
        with patch("local_sync_server.get_bridge_hub", return_value=self.hub):
            api_agent_bridge.handle_agent_respond(ctx)

        res = ctx.handler.get_json_response()
        self.assertEqual(
            res.get("status"),
            "success",
            f"Serve 経由スマホ承認が成功すること (res={res})",
        )
        self.assertEqual(res.get("reason"), "ok")


class TestPcLocalTrustDomainGuard(unittest.TestCase):
    """PC ローカル信頼ドメイン規則と Fail-Open 防止の検証 (紅組査読 2026-09-26)。

    背景.red:
    1. 完全一致判定のみでは、PC上マルウェアが「ask をマスタートークン
       (identity="agent") → respond を loopback トークン (identity="pc-loopback")」
       の組合せで自己承認できる (旧 IP チェックでは 127.0.0.1==127.0.0.1 で
       拒否されていた経路が新規開通するリグレッション)。
    2. requester_identity が空の場合、responder 非空の応答が無検査で通る
       Fail-Open が存在する。
    """

    def setUp(self) -> None:
        """テストごとにクリーンな Hub を用意する。"""
        self.hub = AgentBridgeHub()

    def test_agent_requester_vs_pc_loopback_responder_denied(self) -> None:
        """agent が作成した要請へ pc-loopback (PC内ブラウザ) が応答するのは拒否。

        PC ローカル信頼ドメイン規則: 両者 identity が PC ローカル語彙
        ({"agent", "pc-loopback"}) なら異なっていても無条件で拒否する
        (PC ブラウザ PWA からの承認は正規経路外・デスクトップ GUI の
        ネイティブ承認ダイアログが正統)。
        """
        req = self.hub.create_approval_request(
            agent_name="MalwareAgent",
            command="rm -rf /",
            summary="PC内抜け穴攻撃",
            requester_ip="127.0.0.1",
            requester_identity="agent",
        )

        ok, reason = self.hub.respond_checked(
            request_id=req.request_id,
            decision="approve",
            message="loopback トークンで自己承認",
            responder_ip="127.0.0.1",
            responder_identity="pc-loopback",
        )

        self.assertFalse(
            ok,
            "agent × pc-loopback の PC ローカル組合せは無条件で拒否されなければならない "
            "(紅組指摘1: 完全一致のみの抜け穴)",
        )
        self.assertEqual(reason, "self_approve_denied")
        self.assertEqual(req.status, "pending")

    def test_pc_loopback_requester_vs_agent_responder_denied(self) -> None:
        """pc-loopback が作成した要請へ agent が応答するのも同様に拒否。"""
        req = self.hub.create_approval_request(
            agent_name="PCBrowserAgent",
            command="format C:",
            summary="逆向き組合せ",
            requester_ip="127.0.0.1",
            requester_identity="pc-loopback",
        )

        ok, reason = self.hub.respond_checked(
            request_id=req.request_id,
            decision="approve",
            message="agent トークンで応答",
            responder_ip="127.0.0.1",
            responder_identity="agent",
        )

        self.assertFalse(
            ok,
            "pc-loopback × agent の逆方向組合せも PC ローカル信頼ドメイン規則で拒否されること",
        )
        self.assertEqual(reason, "self_approve_denied")

    def test_device_device_same_uuid_denied(self) -> None:
        """同一端末 (device × device・同一 uuid) の自己承認は identity 一致で拒否。"""
        req = self.hub.create_approval_request(
            agent_name="PhoneAgent",
            command="dangerous-cmd",
            summary="同一端末攻撃",
            requester_ip="192.168.1.50",
            requester_identity="device:uuid-dup",
        )

        ok, reason = self.hub.respond_checked(
            request_id=req.request_id,
            decision="approve",
            message="同一端末から再承認",
            responder_ip="192.168.1.50",
            responder_identity="device:uuid-dup",
        )

        self.assertFalse(ok, "device × device の同一 uuid は identity 一致で拒否されること")
        self.assertEqual(reason, "self_approve_denied")

    def test_blank_requester_nonblank_responder_same_ip_denied(self) -> None:
        """requester_identity 空でも responder 非空 + 同一IP なら拒否 (Fail-Open 防止)。

        旧実装は responder_identity が非空だと IP チェックを完全にスキップし、
        requester_identity が空の要求 (旧経路・GUI 内部生成等) への同一IP応答が
        無検査で通過する Fail-Open を抱えていた。
        """
        req = self.hub.create_approval_request(
            agent_name="LegacyRequester",
            command="git push --force",
            summary="identity 未記録の要求",
            requester_ip="127.0.0.1",
            requester_identity="",
        )

        ok, reason = self.hub.respond_checked(
            request_id=req.request_id,
            decision="approve",
            message="同一IPからの identity 付き応答",
            responder_ip="127.0.0.1",
            responder_identity="device:uuid-x",
        )

        self.assertFalse(
            ok,
            "requester_identity 空の場合は responder の identity 有無を問わず "
            "IP 一致チェックを併用して拒否しなければならない (紅組指摘2)",
        )
        self.assertEqual(reason, "self_approve_denied")

    def test_blank_requester_nonblank_responder_diff_ip_allowed_with_warning(self) -> None:
        """requester_identity 空 + responder 非空 + 異IP は通すが warning ログを出す。

        GUI 等が identity を記録せず作成した要求を、別端末 (スマホ) の人間が
        承認する正規フローを壊さないため。ただし identity 解決が不完全である
        ことを warning ログで可視化する (宣言ではなく機械的保証)。
        """
        req = self.hub.create_approval_request(
            agent_name="GUIRequester",
            command="echo hello",
            summary="GUI 生成要求",
            requester_ip="127.0.0.1",
            requester_identity="",
        )

        # テストスイート内の他モジュール (test_calendar_sources.py 等) が
        # モジュールインポート時に logging.disable(logging.CRITICAL) を実行する
        # ため、assertLogs より優先されるグローバル抑止 (manager.disable) を
        # テスト中のみ解除する。終了時に必ず元へ復元する (他テストへの影響ゼロ)。
        old_disable_level = logging.root.manager.disable
        logging.disable(logging.NOTSET)
        try:
            with self.assertLogs("local_sync_server", level="WARNING") as captured:
                ok, reason = self.hub.respond_checked(
                    request_id=req.request_id,
                    decision="approve",
                    message="スマホから承認",
                    responder_ip="192.168.1.100",
                    responder_identity="device:uuid-gui",
                )
        finally:
            logging.disable(old_disable_level)

        self.assertTrue(
            ok,
            "requester_identity 空 + responder 非空 + IP 不一致は正規フローとして成立すること",
        )
        self.assertEqual(reason, "ok")
        self.assertTrue(
            any("identity 不明" in message for message in captured.output),
            f"requester identity 不明の警告ログが出力されること (logs={captured.output})",
        )


class TestResponderIdentityAuditTrail(unittest.TestCase):
    """応答者 (決定者) の同一性が廃棄されず保持されることの検証 (紅組指摘3)。"""

    def setUp(self) -> None:
        """テストごとにクリーンな Hub を用意する。"""
        self.hub = AgentBridgeHub()

    def test_responder_identity_and_ip_recorded_in_request_and_dict(self) -> None:
        """respond_checked が応答者 identity/IP を req へ記録し to_dict にも同梱する。

        監査ログ (decision_by / client_ip) の単一情報源となるため、解決前に
        req へ記録されなければならない (廃棄 = 監査の喪失)。
        """
        req = self.hub.create_approval_request(
            agent_name="AuditAgent",
            command="pytest",
            summary="応答記録確認",
            requester_ip="127.0.0.1",
            requester_identity="agent",
        )

        ok, reason = self.hub.respond_checked(
            request_id=req.request_id,
            decision="approve",
            message="OK",
            responder_ip="192.168.1.100",
            responder_identity="device:uuid-rec",
        )

        self.assertTrue(ok)
        self.assertEqual(
            req.responder_identity,
            "device:uuid-rec",
            "respond_checked は応答者 identity を req へ記録しなければならない",
        )
        self.assertEqual(
            req.responder_ip,
            "192.168.1.100",
            "respond_checked は応答元IPを req へ記録しなければならない",
        )
        d = req.to_dict()
        self.assertIn("responder_identity", d, "to_dict() に responder_identity が含まれること")
        self.assertEqual(d["responder_identity"], "device:uuid-rec")
        self.assertIn("responder_ip", d, "to_dict() に responder_ip が含まれること")
        self.assertEqual(d["responder_ip"], "192.168.1.100")


class TestAuditDecisionByIdentity(unittest.TestCase):
    """監査ログの decision_by / client_ip が決定者 identity を記録することの検証。

    handle_agent_ask の wait_decision=True フロー (STRICT コマンド) を別スレッドから
    承認し、実 DB へ書かれた監査ログを検証する (api_agent_bridge 経由をモックしない)。
    """

    def setUp(self) -> None:
        """監査ロガーをテスト用 DB へ向ける。"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_identity_audit.db")

        import database
        database.init_db(self.db_path)

        import audit_logger
        self.audit_logger = audit_logger.AsyncAuditLogger(db_path=self.db_path)
        self.audit_logger.start()
        self._orig_logger = audit_logger._GLOBAL_AUDIT_LOGGER
        audit_logger._GLOBAL_AUDIT_LOGGER = self.audit_logger

    def tearDown(self) -> None:
        """監査ロガーを元へ戻す。"""
        self.audit_logger.stop()
        import audit_logger
        audit_logger._GLOBAL_AUDIT_LOGGER = self._orig_logger
        self.temp_dir.cleanup()

    def test_decision_by_records_responder_identity(self) -> None:
        """人間決定の監査 decision_by は決定者 identity・client_ip は応答元IP。

        依頼者側 identity ("agent") を decision_by へ記録するのは誤りであり
        (紅組指摘3)、決定者 (responder) の identity を記録しなければならない。
        """
        from api_agent_bridge import handle_agent_ask
        from audit_logger import get_audit_logs

        hub = AgentBridgeHub()

        def late_respond() -> None:
            """要請が現れたらスマホ端末として承認するバックグラウンド応答。"""
            deadline = time.time() + 5.0
            while time.time() < deadline:
                with hub._lock:
                    pendings = [
                        r for r in hub.pending_requests.values() if r.status == "pending"
                    ]
                if pendings:
                    hub.respond_checked(
                        pendings[0].request_id,
                        "approve",
                        "スマホで承認",
                        responder_ip="192.168.1.100",
                        responder_identity="device:uuid-audit",
                    )
                    return
                time.sleep(0.05)

        responder_thread = threading.Thread(target=late_respond, daemon=True)
        responder_thread.start()
        try:
            ctx_ask = make_ctx(
                {
                    "agent_name": "AuditAgent",
                    "command": "git push origin main",
                    "timeout": 10,
                    "wait_decision": True,
                },
                client_ip="127.0.0.1",
                auth_identity="agent",
            )
            with patch("local_sync_server.get_bridge_hub", return_value=hub):
                handle_agent_ask(ctx_ask)
        finally:
            responder_thread.join(timeout=5.0)

        payload = ctx_ask.handler.get_json_response()
        self.assertEqual(
            payload.get("status"),
            "success",
            f"承認フローが成立すること (res={payload})",
        )

        time.sleep(0.3)
        logs = get_audit_logs(db_path=self.db_path)
        self.assertEqual(len(logs), 1, f"監査ログが1件記録されること (logs={logs})")
        self.assertEqual(
            logs[0].decision_by,
            "device:uuid-audit",
            "監査 decision_by は決定者 (responder) identity を記録すること",
        )
        self.assertEqual(
            logs[0].client_ip,
            "192.168.1.100",
            "監査 client_ip は応答元IPを記録すること (空文字の廃棄を禁止)",
        )
        self.assertEqual(
            logs[0].requester_ip,
            "127.0.0.1",
            "監査 requester_ip は依頼元IPを維持すること",
        )

    def test_ask_input_decision_by_records_responder_identity(self) -> None:
        """ask_input フローでも決定者の identity 及び responder_ip が監査ログに記録されること。"""
        from api_agent_bridge import handle_agent_ask_input
        from audit_logger import get_audit_logs

        hub = AgentBridgeHub()

        def late_respond() -> None:
            deadline = time.time() + 5.0
            while time.time() < deadline:
                with hub._lock:
                    pendings = [
                        r for r in hub.pending_requests.values() if r.status == "pending"
                    ]
                if pendings:
                    hub.respond_checked(
                        pendings[0].request_id,
                        "answer_a",
                        "選択肢A回答",
                        responder_ip="192.168.1.105",
                        responder_identity="device:uuid-askinput",
                    )
                    return
                time.sleep(0.05)

        responder_thread = threading.Thread(target=late_respond, daemon=True)
        responder_thread.start()
        try:
            ctx_ask_input = make_ctx(
                {
                    "agent_name": "AskInputAgent",
                    "question": "どちらを選択しますか？",
                    "choices": ["A", "B"],
                    "timeout": 10,
                    "wait_decision": True,
                },
                client_ip="127.0.0.1",
                auth_identity="agent",
            )
            with patch("local_sync_server.get_bridge_hub", return_value=hub):
                handle_agent_ask_input(ctx_ask_input)
        finally:
            responder_thread.join(timeout=5.0)

        payload = ctx_ask_input.handler.get_json_response()
        self.assertEqual(payload.get("status"), "success", f"ask_input フローが成功すること (res={payload})")

        time.sleep(0.3)
        logs = get_audit_logs(db_path=self.db_path)
        self.assertEqual(len(logs), 1, f"ask_input の監査ログが1件記録されること (logs={logs})")
        self.assertEqual(
            logs[0].decision_by,
            "device:uuid-askinput",
            "ask_input 監査の decision_by は決定者 identity を記録すること",
        )
        self.assertEqual(
            logs[0].client_ip,
            "192.168.1.105",
            "ask_input 監査の client_ip は応答元IPを記録すること",
        )
        self.assertEqual(
            logs[0].requester_ip,
            "127.0.0.1",
            "ask_input 監査の requester_ip は依頼元IPを維持すること",
        )
        self.assertEqual(
            logs[0].command,
            "[question] どちらを選択しますか？",
            "ask_input 監査の command は [question] プレフィックス付き質問本文であること",
        )


if __name__ == "__main__":
    unittest.main()
