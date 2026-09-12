#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - ストリーミング・エージェント実行の単体テスト (tests/test_agent_stream.py)

応答速度スプリント B (2026-09-12): 従来の ainvoke は「全パス完了まで何も表示されない」
ため、推論モデルの思考時間がそのまま体感待ち時間になっていた。
run_agent_streaming() が astream_events(v2) を消費し、トークン逐次コールバック /
ツール開始通知 / 最終 state 返却を行う契約を凍結する。

TDD: agent_stream モジュールが無い状態では Red で落ちる。
"""

import sys
import types
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_stream import run_agent_streaming  # noqa: E402


def _chunk(content) -> types.SimpleNamespace:
    """on_chat_model_stream の data.chunk を模倣するスタブ。"""
    return types.SimpleNamespace(content=content)


# ルート on_chain_end (グラフ全体の最終 state) の標準イベント。
# run_agent_streaming は Fail-Fast 契約 (最終 state 不在で RuntimeError) のため、
# 正常系テストは必ずこのイベントで締める。
_FINAL_ROOT_CHAIN_END = {
    "event": "on_chain_end",
    "parent_ids": [],
    "name": "LangGraph",
    "data": {"output": {"messages": ["final"]}},
}


def _make_agent(events: list) -> types.SimpleNamespace:
    """scripted イベント列を yield する astream_events を持つ疑似グラフ。"""

    class _Agent:
        def astream_events(self, state, config=None, version=None):
            async def _gen():
                for event in events:
                    yield event
            return _gen()

    return _Agent()


class TestRunAgentStreaming(unittest.IsolatedAsyncioTestCase):
    """ストリーミング実行オーケストレータの契約検証"""

    async def test_tokens_stream_to_update_callback(self) -> None:
        """トークンが生成されるたびに累積テキストで on_update が呼ばれること"""
        events = [
            {"event": "on_chat_model_stream", "data": {"chunk": _chunk("こん")}},
            {"event": "on_chat_model_stream", "data": {"chunk": _chunk("にちは")}},
            _FINAL_ROOT_CHAIN_END,
        ]
        updates: list = []

        final = await run_agent_streaming(
            _make_agent(events), {}, None, on_update=updates.append,
            min_update_interval=0.0,
        )

        self.assertEqual(updates, ["こん", "こんにちは"])
        self.assertEqual(final, {"messages": ["final"]})

    async def test_tool_start_notifies_and_resets_buffer(self) -> None:
        """ツール開始で通知され、バッファがリセットされること (回答と混ざらない)"""
        events = [
            {"event": "on_chat_model_stream", "data": {"chunk": _chunk("確認します")}},
            {"event": "on_tool_start", "name": "list_tasks_tool", "data": {}},
            {"event": "on_chat_model_stream", "data": {"chunk": _chunk("登録しました")}},
            _FINAL_ROOT_CHAIN_END,
        ]
        updates: list = []
        tools: list = []

        await run_agent_streaming(
            _make_agent(events), {}, None, on_update=updates.append,
            on_tool_start=tools.append, min_update_interval=0.0,
        )

        self.assertEqual(tools, ["list_tasks_tool"])
        # リセット直後に即 flush はしない (ツール実行中の表示は on_tool_start が担う)。
        # リセット後の最初の回答トークンから on_update が素直に再開されること。
        self.assertEqual(updates, ["確認します", "登録しました"])

    async def test_final_state_from_root_chain_end(self) -> None:
        """ルート (parent_ids 空) の on_chain_end から最終 state を返すこと"""
        events = [
            {
                "event": "on_chain_end",
                "parent_ids": [],
                "name": "LangGraph",
                "data": {"output": {"messages": ["final"]}},
            }
        ]

        final = await run_agent_streaming(
            _make_agent(events), {}, None, on_update=lambda t: None,
            min_update_interval=0.0,
        )

        self.assertEqual(final, {"messages": ["final"]})

    async def test_non_string_chunk_content_is_ignored(self) -> None:
        """文字列以外 (マルチモーダル等) のチャンクは表示に影響しないこと"""
        events = [
            {"event": "on_chat_model_stream", "data": {"chunk": _chunk([{"type": "text", "text": "x"}])}},
            {"event": "on_chat_model_stream", "data": {"chunk": _chunk("ok")}},
            _FINAL_ROOT_CHAIN_END,
        ]
        updates: list = []

        await run_agent_streaming(
            _make_agent(events), {}, None, on_update=updates.append,
            min_update_interval=0.0,
        )

        self.assertEqual(updates, ["ok"])

    async def test_throttle_limits_update_frequency(self) -> None:
        """min_update_interval 中の連続更新は間引かれること (UI 描画負荷抑制)"""
        events = [
            {"event": "on_chat_model_stream", "data": {"chunk": _chunk("a")}},
            {"event": "on_chat_model_stream", "data": {"chunk": _chunk("b")}},
            {"event": "on_chat_model_stream", "data": {"chunk": _chunk("c")}},
            _FINAL_ROOT_CHAIN_END,
        ]
        updates: list = []

        final = await run_agent_streaming(
            _make_agent(events), {}, None, on_update=updates.append,
            min_update_interval=60.0,  # 実用的に全て間引かれる
        )

        self.assertEqual(final, {"messages": ["final"]})
        # throttle: 2トークン目以降は間引かれ、完了時の最終フラッシュで一括送出される
        self.assertEqual(updates, ["a", "abc"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
