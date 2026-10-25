"""
ネオ秘書くん - ローカルGGUF LLM 動作検証スクリプト (test_local_llm.py)

LLMFactory 経由で models/ 内の GGUF モデルをロードし、
同期推論・ストリーミング推論の両方が動作することを確認する。
LM Studio 等の外部サーバーに一切依存しない完全内包推論の検証用。

使い方:
    python test_local_llm.py [モデルファイル名]
    (省略時は .env の LOCAL_GGUF_MODEL を使用)
"""

import sys
import time
import logging
from pathlib import Path

# ※ 本スクリプトは tests/ 配下にあるため、プロジェクトルートを import パスに追加
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import set_key

from llm_factory import LLMFactory, LLMProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("test_local_llm")

ENV_PATH = PROJECT_ROOT / ".env"


def main() -> int:
    """ローカルGGUF推論の検証を実行し、成否の終了コードを返す。

    Returns:
        int: 成功時 0、失敗時 1。
    """
    # 引数でモデル指定があれば .env へ反映（次回起動時も引き継ぐ）
    if len(sys.argv) > 1:
        model_name: str = sys.argv[1]
        set_key(str(ENV_PATH), "LOCAL_GGUF_MODEL", model_name)
        set_key(str(ENV_PATH), "DEFAULT_LLM_PROVIDER", LLMProvider.LOCAL_GGUF.value)
        logger.info(f"モデルを '{model_name}' に切り替えました (.env 永続化済み)")

    factory = LLMFactory(default_provider=LLMProvider.LOCAL_GGUF.value)
    logger.info(f"検証対象モデル: {factory.current_model_name}")

    # --- 検証 1: モデル生成（ロード） ---
    t0 = time.time()
    llm = factory.create_model(temperature=0.7)
    logger.info(f"モデルロード完了: {time.time() - t0:.1f} 秒")

    # --- 検証 2: 同期推論 ---
    t0 = time.time()
    result = llm.invoke("あなたは秘書くんです。挨拶をひとこと、日本語で返してください。")
    elapsed = time.time() - t0
    text = result.content if isinstance(result.content, str) else str(result.content)
    logger.info(f"--- 同期推論結果 ({elapsed:.1f} 秒) ---\n{text}")

    if not text.strip():
        logger.error("同期推論の応答が空です。")
        return 1

    # --- 検証 3: ストリーミング推論 ---
    logger.info("--- ストリーミング推論開始 ---")
    chunks: list = []
    t0 = time.time()
    for chunk in llm.stream("今日のやる気を出させる言葉をひとつ、日本語で短く。"):
        piece = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
        chunks.append(piece)
        print(piece, end="", flush=True)
    print()
    stream_text = "".join(chunks)
    logger.info(f"ストリーミング完了: {time.time() - t0:.1f} 秒 / {len(stream_text)} 文字")

    if not stream_text.strip():
        logger.error("ストリーミング推論の応答が空です。")
        return 1

    logger.info("✅ 全検証パス: ローカルGGUF推論は正常に動作しています")
    return 0


if __name__ == "__main__":
    sys.exit(main())