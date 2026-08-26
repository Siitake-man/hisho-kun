"""
ネオ秘書くん - タスクナレーションエンジン (task_narrator.py)

Claude Code, Cursor, Codex, Antigravity などの外部エージェントの作業ログから、
「何が達成されたか」を Tier 1 ローカルLLM (LFM 2.5 / MiniCPM-5 / Bonsai / Qwen) を用いて
親しみやすい秘書スピーチ（1〜2行）へ即時要約・発話するモジュール。
"""

import logging
import re
from typing import Optional, Dict, Any

from langchain_core.messages import HumanMessage, SystemMessage
from character_manager import get_character_manager

logger = logging.getLogger(__name__)

# ナレーション用のシステムプロンプト（キャラクターペルソナ動的注入）
def _build_narrator_prompt() -> str:
    """現在のキャラクター設定に基づいたナレーション用システムプロンプトを生成する。"""
    character_prompt = get_character_manager().get_character_system_prompt()
    return f"""あなたはユーザー（ボス）のデスクトップ秘書です。
{character_prompt}

外部のコーディングAIエージェント（Claude Code、Codex、Cursor、Antigravity等）がタスクを完了しました。
渡された作業ログの要約から、ボスへ作業完了を報告する「元気で親しみやすい1〜2行の報告メッセージ」を作成してください。

【制約事項】
- 必ず日本語で、絵文字（✨, 🎉, 💻, ☕ 等）を適度に使ってください。
- 1行〜最大2行（50〜80文字程度）で簡潔にまとめてください。
- 難しい専門用語を羅列せず、「〇〇の実装が完了しました！」「〇〇のエラーが直りました！」と直感的に伝えてください。
- 上記のキャラクター設定に従った口調・口癖・一人称を厳守してください。
"""


class TaskNarrator:
    """エージェント作業ログのナレーション生成クラス"""

    def __init__(self):
        self._last_narrated_task: Optional[str] = None

    def narrate_completion(
        self, 
        agent_name: str, 
        task_summary: str, 
        log_snippet: str = ""
    ) -> str:
        """
        タスク完了ログから秘書の親しみやすいスピーチを生成します。
        
        Args:
            agent_name: エージェント名 (例: "Claude Code", "Antigravity")
            task_summary: タスクのタイトルや概要
            log_snippet: ログの末尾テキスト (省略可)
            
        Returns:
            str: 秘書くんの発話テキスト
        """
        # 重複ナレーションの防止
        cache_key = f"{agent_name}:{task_summary}"
        if self._last_narrated_task == cache_key:
            return ""
        self._last_narrated_task = cache_key

        logger.info(f"タスクナレーションを生成中: Agent={agent_name}, Task={task_summary}")

        # 1. ルールベースの高速フォールバック（LLMがオフラインまたはタイムアウト時の即答用）
        char = get_character_manager().get_current_character()
        char_name = char.get("name", "秘書くん")
        char_emoji = char.get("emoji", "👔")
        fallback_msg = f"{char_emoji} {char_name}です！{agent_name}さんが「{task_summary[:30]}」の作業を無事完了させました！🎉✨"

        # 2. LLM Factory を利用した自然なスピーチ生成
        try:
            from llm_factory import get_llm_factory, LLMProvider
            factory = get_llm_factory()
            
            # 軽量な温度設定でモデル取得
            model = factory.create_model(temperature=0.7)
            
            user_prompt = f"エージェント名: {agent_name}\nタスク概要: {task_summary}\n作業ログ抜粋:\n{log_snippet[:400]}"
            
            messages = [
                SystemMessage(content=_build_narrator_prompt()),
                HumanMessage(content=user_prompt)
            ]
            
            response = model.invoke(messages)
            speech = response.content.strip()
            
            # 余計な引用符を除去
            speech = re.sub(r'^["「](.*)[」"]$', r'\1', speech)
            if speech:
                logger.info(f"生成されたナレーション: {speech}")
                return speech
                
        except Exception as e:
            logger.warning(f"LLMナレーション生成エラー (フォールバックを使用): {e}")

        return fallback_msg

    def narrate_error(
        self, 
        agent_name: str, 
        error_message: str
    ) -> str:
        """
        エージェントのエラー発生時の注意喚起スピーチを生成します。
        """
        char = get_character_manager().get_current_character()
        char_emoji = char.get("emoji", "👔")
        clean_err = error_message.split("\n")[0][:40]
        return f"{char_emoji} ボス、{agent_name}さんでエラーが発生したみたいです…！😰\n（{clean_err}）"

    def speak_text(self, text: str) -> None:
        """
        Windows標準の音声合成エンジン（SAPI5 / System.Speech）を用いてテキストを音声発話します。
        別スレッドで実行するため、メインGUIやLLM推論を一切ブロックしません。
        """
        if not text:
            return

        # 絵文字や記号を音声用にクリーニング
        clean_speech = re.sub(r'[^\w\sぁ-んァ-ヶー一-龠、。！？]', '', text)
        clean_speech = clean_speech.strip()
        if not clean_speech:
            return

        import threading

        def _worker():
            try:
                # 1. win32com (SAPI.SpVoice) があれば最優先
                import win32com.client
                speaker = win32com.client.Dispatch("SAPI.SpVoice")
                speaker.Speak(clean_speech)
            except Exception:
                try:
                    # 2. PowerShell System.Speech による完全標準フォールバック
                    import subprocess
                    ps_cmd = f"Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.Speak('{clean_speech}')"
                    subprocess.run(
                        ["powershell", "-NoProfile", "-Command", ps_cmd],
                        creationflags=0x08000000 if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
                        timeout=10
                    )
                except Exception as ex:
                    logger.debug(f"音声合成エラー: {ex}")

        threading.Thread(target=_worker, daemon=True).start()


# シングルトン
_narrator_instance: Optional[TaskNarrator] = None

def get_task_narrator() -> TaskNarrator:
    global _narrator_instance
    if _narrator_instance is None:
        _narrator_instance = TaskNarrator()
    return _narrator_instance
