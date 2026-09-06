#!/usr/bin/env python3
"""
ネオ秘書くん - AIエージェント稼働可視化FSM (agent_fsm.py)

Phase H（フルハイブリッドAgent監視 ＆ 状態連動FSM）のコアエンジン。
Claude Code, Codex, Cursor, Antigravity, Cline 等の外部エージェントの稼働状態
（思考中・コーディング中・承認待ち・完了）を一元管理し、
一定時間（TTL）アクティビティがない場合は自動で IDLE へフェードアウトする。
"""

import logging
import threading
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    """エージェントの稼働状態を表すEnum。"""
    IDLE = "idle"                        # 通常待機
    THINKING = "thinking"                # 思考中・調査中
    CODING = "coding"                    # 実装・コード書き込み中
    WAITING_APPROVAL = "waiting_approval" # 承認・ユーザー入力待ち
    SUCCESS = "success"                  # タスク完了・成功


class AgentFSM:
    """エージェントの稼働状態をスレッドセーフに管理する有限状態機械。

    外部からのアクティビティ通知を受け取り、状態変化時に登録されたリスナーへ
    イベントを通知する。ハートビート退避（TTL）により、エージェントがクラッシュ等で
    停止しても状態がスタックしない自律回復性を備える。
    """

    def __init__(self, default_ttl: float = 60.0) -> None:
        """AgentFSM を初期化する。

        Args:
            default_ttl: 状態がIDLE以外の場合に、自動でIDLEへ戻すまでの有効秒数。
        """
        self._lock = threading.Lock()
        self._default_ttl = default_ttl
        self._state: AgentState = AgentState.IDLE
        self._agent_name: str = "AI Agent"
        self._detail: str = ""
        self._last_updated_at: float = time.time()
        self._expires_at: float = 0.0
        self._listeners: List[Callable[[Dict[str, Any]], None]] = []

    def register_listener(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """状態変化時のコールバックリスナーを登録する。

        Args:
            callback: 状態情報辞書を受け取る関数。
        """
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def set_state(
        self,
        state: str,
        agent_name: str = "AI Agent",
        detail: str = "",
        ttl_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """エージェントの稼働状態を更新する。

        Args:
            state: AgentState の文字列値 (idle, thinking, coding, waiting_approval, success)。
            agent_name: エージェント名 (Antigravity, Claude Code 等)。
            detail: 現在の作業詳細（ファイル名や要約）。
            ttl_seconds: この状態の有効期間（秒）。None の場合は default_ttl を使用。

        Returns:
            Dict[str, Any]: 更新後の状態ペイロード。
        """
        try:
            target_state = AgentState(state.lower())
        except ValueError:
            logger.warning("未知のエージェント状態 '%s' を受信したため、IDLE にフォールバックします", state)
            target_state = AgentState.IDLE

        now = time.time()
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl

        with self._lock:
            prev_state = self._state
            self._state = target_state
            self._agent_name = agent_name.strip() or "AI Agent"
            self._detail = detail.strip()
            self._last_updated_at = now
            self._expires_at = now + ttl if target_state != AgentState.IDLE else 0.0

            payload = self._build_payload_locked(now)
            listeners_copy = list(self._listeners)

        # 状態変化時または重要状態でリスナーを通知（ロック外で呼ぶ）
        if prev_state != target_state or target_state != AgentState.IDLE:
            for listener in listeners_copy:
                try:
                    listener(payload)
                except Exception as e:
                    logger.error("AgentFSM リスナー実行エラー: %s", e)

        return payload

    def get_current_activity(self) -> Dict[str, Any]:
        """現在のアクティビティ情報を取得する。TTL切れ時は自動でIDLEに遷移する。

        Returns:
            Dict[str, Any]: 現在の状態情報。
        """
        now = time.time()
        should_reset_to_idle = False

        with self._lock:
            if self._state != AgentState.IDLE and self._expires_at > 0 and now > self._expires_at:
                logger.info(
                    "エージェント状態 '%s' のTTL (%.1fs) が経過したため、IDLE に自動復帰します",
                    self._state.value,
                    self._default_ttl,
                )
                self._state = AgentState.IDLE
                self._detail = ""
                self._expires_at = 0.0
                self._last_updated_at = now
                should_reset_to_idle = True

            payload = self._build_payload_locked(now)
            listeners_copy = list(self._listeners) if should_reset_to_idle else []

        if should_reset_to_idle:
            for listener in listeners_copy:
                try:
                    listener(payload)
                except Exception as e:
                    logger.error("AgentFSM リスナー実行エラー (IDLE復帰時): %s", e)

        return payload

    def _build_payload_locked(self, now: float) -> Dict[str, Any]:
        """ロック保持状態で状態ペイロードを構築するヘルパー。"""
        return {
            "state": self._state.value,
            "agent_name": self._agent_name,
            "detail": self._detail,
            "last_updated_at": self._last_updated_at,
            "expires_at": self._expires_at,
            "is_active": self._state != AgentState.IDLE,
            "remaining_seconds": max(0.0, self._expires_at - now) if self._expires_at > 0 else 0.0,
        }


# グローバルシングルトンインスタンス
agent_fsm = AgentFSM()
