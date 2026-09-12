#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - ストリーミング・エージェント実行オーケストレータ (agent_stream.py)

LangGraph エージェントを ``astream_events`` (v2) で走らせ、LLM のトークン生成を
逐次コールバックへ流す (応答速度スプリント B・2026-09-12)。
従来の ``ainvoke`` は「全パス完了まで何も表示されない」ため、推論モデルの
思考時間 (数秒〜数十秒) がそのまま体感待ち時間になっていた。

契約:
- ``run_agent_streaming()`` はグラフの最終 state (dict) を返す (ainvoke と同一契約)。
- ``on_update(text)`` はトークン生成のたびに呼ばれる (累積テキストを渡す)。
  描画負荷抑制のため ``min_update_interval`` 秒未満の連続呼び出しは間引かれる。
- ``on_tool_start(tool_name)`` はツール実行開始時に呼ばれる。バッファはこの時点で
  リセットされ、ツール前の中間テキストが最終回答と混ざらない。
- 推論中の ``reasoning_content`` は表示対象外 (回答テキストのみを流す)。
- ローカル GGUF 等ストリーミング非互換モデルは呼び出し側 (main.py) で ainvoke に
  フォールバックする。
"""

import logging
import time
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# トークンごとの GUI 更新を間引く最小間隔 (秒)。0 で間引き無し (テスト用)。
_MIN_UPDATE_INTERVAL_SEC: float = 0.05


def _extract_content_delta(chunk: Any) -> Optional[str]:
    """AIMessageChunk から表示対象の文字列デルタを取り出す (非文字列は None)。"""
    content = getattr(chunk, "content", None)
    if isinstance(content, str) and content:
        return content
    return None


async def run_agent_streaming(
    agent: Any,
    initial_state: Dict[str, Any],
    config: Optional[Dict[str, Any]],
    on_update: Callable[[str], None],
    on_tool_start: Optional[Callable[[str], None]] = None,
    min_update_interval: float = _MIN_UPDATE_INTERVAL_SEC,
) -> Dict[str, Any]:
    """エージェントをストリーミング実行し、逐次表示しながら最終 state を返す。

    Args:
        agent: LangGraph コンパイル済みグラフ (``astream_events`` を実装)。
        initial_state: 初期 state。
        config: LangGraph config (thread_id / recursion_limit 等)。None 可。
        on_update: トークン生成のたびに呼ばれるコールバック (累積テキスト)。
        on_tool_start: ツール実行開始時に呼ばれるコールバック (ツール名)。
        min_update_interval: 更新間引き間隔 (秒)。テストでは 0 を指定可。

    Returns:
        Dict[str, Any]: グラフの最終 state。

    Raises:
        RuntimeError: ルート (parent_ids 空) の on_chain_end から最終 state を
            取得できなかった場合 (イベント形式変更などの異常系)。
    """
    final_state: Dict[str, Any] = {}
    buffer = ""
    last_sent_text = ""
    last_update_time = 0.0

    async for event in agent.astream_events(initial_state, config=config, version="v2"):
        kind = event.get("event", "")

        if kind == "on_chat_model_stream":
            delta = _extract_content_delta(event.get("data", {}).get("chunk"))
            if delta is None:
                continue
            buffer += delta
            now = time.monotonic()
            if now - last_update_time >= min_update_interval:
                last_update_time = now
                on_update(buffer)
                last_sent_text = buffer

        elif kind == "on_tool_start":
            # ツール前の中間テキストが最終回答と混ざらないようバッファをリセット
            buffer = ""
            if on_tool_start is not None:
                tool_name = event.get("name", "")
                if tool_name:
                    on_tool_start(tool_name)

        elif kind == "on_chain_end":
            # ルートイベント (parent_ids 空) の出力がグラフ全体の最終 state
            if not event.get("parent_ids"):
                output = event.get("data", {}).get("output")
                if isinstance(output, dict):
                    final_state = output

    if not final_state:
        logger.error("ストリーミング実行で最終 state を取得できませんでした (イベント形式変更の疑い)")
        raise RuntimeError("ストリーミング実行で最終 state を取得できませんでした")

    # 最終フラッシュ: throttle で未送出だった末尾バッファを確実に表示する。
    # ただし既に送出済みのテキスト (最終トークンが throttle に引っかからなかった
    # ケース等) との重複表示は行わない。
    if buffer and buffer != last_sent_text:
        on_update(buffer)
    return final_state
