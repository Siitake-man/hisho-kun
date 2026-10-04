#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - エージェント承認リクエスト管理ハブ (AgentBridgeHub / S2 Seam).

(server/agent_bridge_hub.py)

目的:
    Fat モジュール `local_sync_server.py` (2,296行) から、エージェントからの承認要請・
    質問・入力待ちキュー、自己承認(RCE)防止判定、および重複リクエストの冪等処理を
    独立した Deep Module として切り出す。

防衛策:
    - 🛡️ PC ローカル信頼ドメイン規則 (紅組査読 2026-09-26 / ADR):
      PC 内で完結する認証主体 ("agent" / "pc-loopback") 間の承認関係を無条件拒否。
    - 🛡️ 自己承認防止 (identity ベース):
      Tailscale Serve 等のプロキシが IP を 127.0.0.1 へ同一化しても、
      認証主体 (identity) により人間の正当なスマホ承認と自己承認を厳密に弁別。
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

# ロガーは local_sync_server の子階層として定義し、既存テスト (assertLogs("local_sync_server"))
# との完全互換性とログ伝播 (propagation) を両立する。
logger = logging.getLogger("local_sync_server.agent_bridge_hub")


class AgentBridgeRequest:
    """エージェントからの承認要請または質問・入力待ちリクエスト."""

    def __init__(
        self,
        req_type: str,  # 'approval' または 'question'
        agent_name: str,
        title: str,
        content: str = "",
        command: str = "",
        choices: Optional[List[str]] = None,
        timeout_sec: int = 180,
        requester_ip: str = "",
        requester_identity: str = "",
        risk_level: str = "prompt",
        agent_type: str = "generic",
        summary: str = "",
        safety_level: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        if request_id and isinstance(request_id, str) and request_id.strip():
            self.request_id = request_id.strip()
        else:
            self.request_id = f"req_{uuid.uuid4().hex[:8]}"
        self.req_type = req_type
        self.agent_name = agent_name
        self.agent_type = agent_type
        self.title = title
        self.summary = summary or title
        self.safety_level = safety_level
        self.content = content
        self.command = command
        self.choices = choices or []
        self.risk_level = risk_level
        self.created_at = time.time()
        self.timeout_at = self.created_at + timeout_sec
        self.status = "pending"  # 'pending', 'approved', 'rejected', 'answered', 'expired'
        self.decision_message = ""
        # 承認要請を作成したクライアントのIP。従来の自己承認(RCE)防止のために記録する。
        # 手帳 ID 52 以降、同一性判定の主軸は requester_identity (認証主体) へ移行し、
        # requester_ip は identity 不明応答時の後方互換フォールバック用に維持する。
        self.requester_ip = requester_ip
        # 承認要請を作成した認証主体 (identity)。
        # "agent" (PC内エージェント) / "device:<uuid>" (ペアリング済み端末) /
        # "pc-loopback" (PC内ブラウザ) / "" (unknown)。Tailscale Serve 等のプロキシが
        # IP を 127.0.0.1 へ同一化するため、同一性判定は IP ではなく identity で行う。
        self.requester_identity = requester_identity
        # 応答者 (決定者) の同一性。respond_checked が解決前に記録し、監査ログ
        # (decision_by / client_ip) の単一情報源となる (紅組指摘3: 応答側 identity を
        # 廃棄せず保持する)。未解決の間は空文字。
        self.responder_identity: str = ""
        self.responder_ip: str = ""
        self._event = threading.Event()

    def resolve(self, decision: str, message: str = "") -> None:
        """スマホ側から意思決定・回答を受信した際に解決."""
        self.status = decision
        self.decision_message = message
        self._event.set()

    def wait(self, timeout: Optional[float] = None) -> str:
        """エージェント側が判定・回答結果を待機."""
        self._event.wait(timeout=timeout)
        if not self._event.is_set():
            self.status = "expired"
        return self.status

    def to_dict(self) -> Dict[str, Any]:
        """リクエスト状態をシリアライズ可能な辞書形式で返却する."""
        return {
            "request_id": self.request_id,
            "type": self.req_type,
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "title": self.title,
            "summary": self.summary,
            "safety_level": self.safety_level,
            "content": self.content,
            "command": self.command,
            "choices": self.choices,
            "risk_level": self.risk_level,
            "requester_ip": self.requester_ip,
            "requester_identity": self.requester_identity,
            "responder_identity": self.responder_identity,
            "responder_ip": self.responder_ip,
            "created_at": self.created_at,
            "timeout_at": self.timeout_at,
            "status": self.status,
            "decision_message": self.decision_message,
        }


# 🛡️ PC ローカル信頼ドメイン規則 (紅組査読 2026-09-26 / ADR 対象):
# PC 内で完結する認証主体 ("agent" = マスタートークン + trusted_loopback /
# "pc-loopback" = loopback 専用トークン) は同一物理マシン上の主体であり、
# 承認関係を結んではならない。
_PC_LOCAL_IDENTITIES: frozenset[str] = frozenset({"agent", "pc-loopback"})


class AgentBridgeHub:
    """エージェント承認要請および質問・入力待ちの管理ハブ（シングルトン）."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.pending_requests: Dict[str, AgentBridgeRequest] = {}
        self.latest_completed: Optional[Dict[str, Any]] = None
        self.history: List[Dict[str, Any]] = []

    def create_approval_request(
        self,
        agent_name: str,
        command: str,
        summary: str,
        details: str = "",
        timeout_sec: int = 180,
        requester_ip: str = "",
        requester_identity: str = "",
        risk_level: str = "prompt",
        agent_type: str = "generic",
        safety_level: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> AgentBridgeRequest:
        """新規承認リクエストを作成して保留キューに登録する."""
        req = AgentBridgeRequest(
            req_type="approval",
            agent_name=agent_name,
            title=summary if summary else f"『{command}』の実行許可",
            summary=summary,
            content=details,
            command=command,
            timeout_sec=timeout_sec,
            requester_ip=requester_ip,
            requester_identity=requester_identity,
            risk_level=risk_level,
            agent_type=agent_type,
            safety_level=safety_level,
            request_id=request_id,
        )
        with self._lock:
            self.pending_requests[req.request_id] = req
        logger.info(
            f"🤖 [Agent Bridge] 新規承認要請: {agent_name} -> '{command}' "
            f"(ID: {req.request_id}, 要求元IP: {requester_ip}, 認証主体: {requester_identity or 'unknown'})"
        )
        return req

    def create_question_request(
        self,
        agent_name: str,
        question: str,
        choices: Optional[List[str]] = None,
        details: str = "",
        timeout_sec: int = 180,
        requester_ip: str = "",
        requester_identity: str = "",
        request_id: Optional[str] = None,
    ) -> AgentBridgeRequest:
        """新規質問・入力待ちリクエストを作成して保留キューに登録する."""
        req = AgentBridgeRequest(
            req_type="question",
            agent_name=agent_name,
            title=question,
            content=details,
            choices=choices or [],
            timeout_sec=timeout_sec,
            requester_ip=requester_ip,
            requester_identity=requester_identity,
            request_id=request_id,
        )
        with self._lock:
            self.pending_requests[req.request_id] = req
        logger.info(
            f"🤖 [Agent Bridge] 新規質問・確認要請: {agent_name} -> '{question}' "
            f"(選択肢: {choices}, 要求元IP: {requester_ip}, 認証主体: {requester_identity or 'unknown'})"
        )
        return req

    def set_completed_event(self, agent_name: str, title: str, summary: str, details: str = "") -> None:
        """作業完了イベントを保持する."""
        with self._lock:
            self.latest_completed = {
                "id": f"comp_{uuid.uuid4().hex[:6]}",
                "type": "completed",
                "agent_name": agent_name,
                "title": title,
                "summary": summary,
                "details": details,
                "timestamp": time.time(),
            }

    def dismiss_completed(self) -> None:
        """作業完了イベントを既読・消去する."""
        with self._lock:
            self.latest_completed = None

    def get_latest_pending(self) -> Optional[Dict[str, Any]]:
        """直近の未解決・保留中リクエストを取得する (期限切れクリーンアップ付き)."""
        with self._lock:
            now = time.time()
            stale_ids: list[tuple[str, str]] = []
            for rid, r in list(self.pending_requests.items()):
                if now > r.timeout_at:
                    stale_ids.append((rid, "expired"))
                elif r.status != "pending":
                    stale_ids.append((rid, "resolved"))

            for rid, reason in stale_ids:
                r = self.pending_requests.pop(rid, None)
                if r:
                    if reason == "expired" and r.status == "pending":
                        r.resolve("expired")
                    self.history.append(r.to_dict())

            active_pendings = [r for r in self.pending_requests.values() if r.status == "pending"]
            if not active_pendings:
                return None
            return active_pendings[-1].to_dict()

    def get_active_event(self) -> Optional[Dict[str, Any]]:
        """スマホ画面で表示すべき最優先イベント（承認 > 質問 > 作業完了）を返す."""
        with self._lock:
            now = time.time()
            pending = self.get_latest_pending()
            if pending:
                return pending

            if self.latest_completed:
                if now - self.latest_completed["timestamp"] <= 90.0:
                    return self.latest_completed
                else:
                    self.latest_completed = None
            return None

    def _is_self_approval_hit(
        self,
        request_id: str,
        requester_identity: str,
        requester_ip: str,
        responder_identity: str,
        responder_ip: Optional[str],
    ) -> bool:
        """自己承認 (RCE) の成立を認証主体 (identity) ベースで判定する."""
        # 1. PC ローカル信頼ドメイン規則 (無条件拒否)
        if (
            requester_identity in _PC_LOCAL_IDENTITIES
            and responder_identity in _PC_LOCAL_IDENTITIES
        ):
            logger.warning(
                f"🚫 [Security] 自己承認を検知して拒否 (PC ローカル信頼ドメイン): "
                f"ID={request_id} (requester={requester_identity}, responder={responder_identity})"
            )
            return True
        # 2. identity 完全一致 (agent の自己応答 / 同一端末の自己承認)
        if requester_identity and responder_identity and requester_identity == responder_identity:
            logger.warning(
                f"🚫 [Security] 自己承認を検知して拒否 (identity 一致): "
                f"ID={request_id} (identity={responder_identity})"
            )
            return True
        # 3. requester_identity 不明 → IP 一致チェックを併用 (Fail-Open 防止)
        if not requester_identity:
            if responder_ip and requester_ip and responder_ip == requester_ip:
                logger.warning(
                    f"🚫 [Security] 自己承認を検知して拒否 (requester identity 不明・IP 一致): "
                    f"ID={request_id} (IP: {responder_ip})"
                )
                return True
            if responder_identity or responder_ip:
                logger.warning(
                    f"⚠️ [Security] requester identity 不明のため IP 一致チェックのみで成立判定: "
                    f"ID={request_id} (responder={responder_identity or 'unknown'}, IP: {responder_ip})"
                )
            return False
        # 4. responder_identity のみ不明 → 従来 IP 一致チェックへフォールバック
        if not responder_identity:
            if responder_ip and requester_ip and responder_ip == requester_ip:
                logger.warning(
                    f"🚫 [Security] 自己承認を検知して拒否 (IP 一致・responder identity 不明): "
                    f"ID={request_id} (IP: {responder_ip})"
                )
                return True
        return False

    def respond_checked(
        self,
        request_id: str,
        decision: str,
        message: str = "",
        responder_ip: Optional[str] = None,
        responder_identity: str = "",
    ) -> tuple[bool, str]:
        """承認応答を処理し、自己承認(RCE)防止チェックと期限切れ検知を行う."""
        with self._lock:
            req = self.pending_requests.get(request_id)
            if not req:
                # 冪等性チェックの前に自己承認判定を実施する
                for hist in reversed(self.history):
                    if hist.get("request_id") == request_id:
                        if self._is_self_approval_hit(
                            request_id,
                            str(hist.get("requester_identity", "") or ""),
                            str(hist.get("requester_ip", "") or ""),
                            responder_identity,
                            responder_ip,
                        ):
                            return False, "self_approve_denied"
                        prev_status = hist.get("status")
                        is_match = (
                            prev_status == decision
                            or (decision in ("approve", "approved") and prev_status in ("approve", "approved"))
                            or (decision in ("reject", "deny") and prev_status in ("reject", "deny"))
                        )
                        if is_match:
                            logger.info(
                                f"🔄 [Agent Bridge] 重複リクエストの冪等処理: ID={request_id} -> {decision}"
                            )
                            return True, "already_resolved"
                return False, "not_found"

            # 自己承認防止 (identity ベース)
            if self._is_self_approval_hit(
                request_id,
                getattr(req, "requester_identity", ""),
                req.requester_ip,
                responder_identity,
                responder_ip,
            ):
                return False, "self_approve_denied"

            # 期限切れ検知
            if req.timeout_at is not None and time.time() > req.timeout_at:
                logger.warning(
                    f"⏰ 期限切れリクエストの応答を拒否: ID={request_id} (status={req.status})"
                )
                req.status = "expired"
                return False, "expired"
            if req.status != "pending":
                return False, "not_found"

            req.responder_identity = responder_identity
            req.responder_ip = responder_ip or getattr(req, "responder_ip", "")
            req.resolve(decision, message)
            self.history.append(req.to_dict())
            del self.pending_requests[request_id]
            logger.info(
                f"📱 [Agent Bridge] スマホから判定・回答を受信: ID={request_id} -> {decision} (msg: {message})"
            )
            return True, "ok"

    def cancel_pending(self, request_id: str, reason: str = "") -> str:
        """エージェント側（PC側）で解決・キャンセルされた保留中リクエストを取り消す."""
        with self._lock:
            req = self.pending_requests.get(request_id)
            target_id = request_id
            if not req:
                for rid, r in list(self.pending_requests.items()):
                    if rid.endswith(f":{request_id}") or request_id.endswith(f":{rid}"):
                        req = r
                        target_id = rid
                        break

            if not req:
                for hist in reversed(self.history):
                    hid = str(hist.get("request_id", ""))
                    if hid == request_id or hid.endswith(f":{request_id}") or request_id.endswith(f":{hid}"):
                        return "already_resolved"
                return "not_found"

            if req.status != "pending":
                return "already_resolved"

            req.resolve("cancelled", reason or "cancelled")
            self.history.append(req.to_dict())
            self.pending_requests.pop(target_id, None)
            logger.info(
                f"🚫 [Agent Bridge] リクエストが取り消されました: ID={target_id} (理由: {reason})"
            )
            return "cancelled"


_global_bridge_hub: AgentBridgeHub = AgentBridgeHub()


def get_bridge_hub() -> AgentBridgeHub:
    """AgentBridgeHub のシングルトンインスタンスを返却する.

    Returns:
        AgentBridgeHub: グローバル承認ハブインスタンス。
    """
    return _global_bridge_hub


__all__: list[str] = [
    "AgentBridgeRequest",
    "AgentBridgeHub",
    "get_bridge_hub",
    "_PC_LOCAL_IDENTITIES",
]
