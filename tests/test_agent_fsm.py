#!/usr/bin/env python3
"""
AgentFSM の単体テスト (tests/test_agent_fsm.py)
"""

import time
import unittest
from agent_fsm import AgentFSM, AgentState


class TestAgentFSM(unittest.TestCase):
    """AgentFSM の状態管理・TTL・リスナー・安全性を検証するテストケース。"""

    def setUp(self) -> None:
        self.fsm = AgentFSM(default_ttl=1.0)

    def test_initial_state_is_idle(self) -> None:
        """初期状態が IDLE であること。"""
        activity = self.fsm.get_current_activity()
        self.assertEqual(activity["state"], AgentState.IDLE.value)
        self.assertFalse(activity["is_active"])
        self.assertEqual(activity["detail"], "")

    def test_set_valid_state(self) -> None:
        """有効な状態（coding）へ遷移できること。"""
        activity = self.fsm.set_state(
            state="coding",
            agent_name="Antigravity",
            detail="ui/sticky_note.py を実装中",
            ttl_seconds=5.0,
        )
        self.assertEqual(activity["state"], AgentState.CODING.value)
        self.assertEqual(activity["agent_name"], "Antigravity")
        self.assertEqual(activity["detail"], "ui/sticky_note.py を実装中")
        self.assertTrue(activity["is_active"])
        self.assertGreater(activity["remaining_seconds"], 0.0)

    def test_invalid_state_falls_back_to_idle(self) -> None:
        """未知の状態文字列が渡された場合、IDLE にフォールバックすること。"""
        activity = self.fsm.set_state("unknown_crazy_state")
        self.assertEqual(activity["state"], AgentState.IDLE.value)
        self.assertFalse(activity["is_active"])

    def test_ttl_expiry_resets_to_idle(self) -> None:
        """TTLが経過すると、get_current_activity 呼び出し時に自動で IDLE に復帰すること。"""
        self.fsm.set_state("thinking", "Claude Code", "アーキテクチャ検討中", ttl_seconds=0.1)
        activity_before = self.fsm.get_current_activity()
        self.assertEqual(activity_before["state"], AgentState.THINKING.value)
        self.assertTrue(activity_before["is_active"])

        # 0.15秒待機してTTLを切らす
        time.sleep(0.15)

        activity_after = self.fsm.get_current_activity()
        self.assertEqual(activity_after["state"], AgentState.IDLE.value)
        self.assertFalse(activity_after["is_active"])
        self.assertEqual(activity_after["detail"], "")

    def test_listener_callback(self) -> None:
        """状態変更時に登録リスナーが呼び出されること。"""
        notified_payloads = []

        def on_change(payload: dict) -> None:
            notified_payloads.append(payload)

        self.fsm.register_listener(on_change)
        self.fsm.set_state("waiting_approval", "Codex", "git push の承認待ち")

        self.assertEqual(len(notified_payloads), 1)
        self.assertEqual(notified_payloads[0]["state"], "waiting_approval")
        self.assertEqual(notified_payloads[0]["agent_name"], "Codex")


if __name__ == "__main__":
    unittest.main()
