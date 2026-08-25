"""
ネオ秘書くん - フルハイブリッドAgentログ監視エンジン (agent_watcher.py)

Claude Code, Cursor, Codex, Antigravity などのセッションログ・作業ログを
バックグラウンドで非同期監視し、状態（Thinking / Working / Waiting Approval / Done / Error）を
ペットの表情・アニメーション・スマホDesk Pet・タスクナレーションと自動連動させます。
"""

import os
import sys
import time
import logging
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List

logger = logging.getLogger(__name__)


class AgentWatcher:
    """外部AIコーディングエージェントのログ監視クラス"""

    def __init__(
        self,
        on_status_change: Optional[Callable[[str, str, Dict[str, Any]], None]] = None,
        on_task_completed: Optional[Callable[[str, str, str], None]] = None,
        on_approval_needed: Optional[Callable[[str, str, str], None]] = None
    ):
        """
        Args:
            on_status_change: (agent_name, state, details) 状態変化コールバック
            on_task_completed: (agent_name, summary, log_snippet) 完了時コールバック
            on_approval_needed: (agent_name, command, summary) 承認待ち時コールバック
        """
        self.on_status_change = on_status_change
        self.on_task_completed = on_task_completed
        self.on_approval_needed = on_approval_needed

        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # 監視対象ファイルのオフセット管理 (file_path -> last_pos)
        self._file_offsets: Dict[str, int] = {}
        
        # 既知のエージェント状態キャッシュ (agent_name -> state)
        self._current_agent_states: Dict[str, str] = {}

    def get_watch_targets(self) -> List[Path]:
        """監視対象となるログファイル・ディレクトリの一覧を取得"""
        targets: List[Path] = []
        user_home = Path.home()
        
        # 1. Claude Code ログディレクトリ
        claude_dir = user_home / ".claude"
        if claude_dir.exists():
            for f in claude_dir.glob("*.log"):
                targets.append(f)
            for f in claude_dir.glob("projects/**/*.log"):
                targets.append(f)

        # 2. Antigravity IDE ログディレクトリ
        ag_dir = user_home / ".gemini" / "antigravity-ide" / "brain"
        if ag_dir.exists():
            for f in ag_dir.glob("*/.system_generated/logs/transcript.jsonl"):
                targets.append(f)

        # 3. ワークスペースローカルログ
        local_logs = Path(__file__).parent / "logs"
        if local_logs.exists():
            for f in local_logs.glob("*.log"):
                targets.append(f)

        return targets

    def start(self):
        """バックグラウンド監視スレッドを開始"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True, name="AgentWatcherThread")
        self._thread.start()
        logger.info("AgentWatcher (外部Agentログ監視エンジン) が開始されました。")

    def stop(self):
        """監視スレッドを停止"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logger.info("AgentWatcher が停止しました。")

    def _watch_loop(self):
        """ログファイルを定期的にポーリング監視するメインループ"""
        while self._running:
            try:
                targets = self.get_watch_targets()
                for file_path in targets:
                    self._check_file_updates(file_path)
            except Exception as e:
                logger.error(f"AgentWatcher 監視ループエラー: {e}")
            
            # 1.5秒間隔でポーリング（低負荷）
            time.sleep(1.5)

    def _check_file_updates(self, file_path: Path):
        """単一ファイルの更新差分を読み取って状態を解析"""
        str_path = str(file_path)
        if not file_path.exists():
            return

        try:
            current_size = file_path.stat().st_size
            last_pos = self._file_offsets.get(str_path, None)

            # 初回検出時はファイル末尾にポインタを合わせる（過去ログの大量誤検知を防ぐ）
            if last_pos is None:
                self._file_offsets[str_path] = current_size
                return

            if current_size <= last_pos:
                # ログのローテーション等で小さくなった場合
                if current_size < last_pos:
                    self._file_offsets[str_path] = current_size
                return

            # 差分行を読み込み
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(last_pos)
                new_text = f.read()
                self._file_offsets[str_path] = f.tell()

            if new_text.strip():
                self._parse_log_diff(file_path, new_text)

        except Exception as err:
            logger.debug(f"ファイル読み取りスキップ ({file_path.name}): {err}")

    def _parse_log_diff(self, file_path: Path, diff_text: str):
        """新規ログテキストを解析してエージェントの状態を特定"""
        # エージェント名の推定
        agent_name = "Coding Agent"
        if "claude" in str(file_path).lower():
            agent_name = "Claude Code"
        elif "antigravity" in str(file_path).lower():
            agent_name = "Antigravity"
        elif "cursor" in str(file_path).lower():
            agent_name = "Cursor"
        elif "codex" in str(file_path).lower():
            agent_name = "Codex"

        lines = [line.strip() for line in diff_text.splitlines() if line.strip()]
        if not lines:
            return

        recent_chunk = "\n".join(lines[-10:])
        lower_chunk = recent_chunk.lower()

        # 1. 承認待ち検知 (Waiting Approval)
        if any(k in lower_chunk for k in ("allow this command", "approve", "[y/n]", "do you want to proceed", "permission needed", "waiting for confirmation")):
            logger.info(f"[{agent_name}] 承認待ちを検知しました！")
            self._update_state(agent_name, "alarm_ask")
            if self.on_approval_needed:
                cmd_match = lines[-1]
                self.on_approval_needed(agent_name, cmd_match, f"{agent_name} がコマンド実行の承認を求めています")

        # 2. タスク完了検知 (Success / Done)
        elif any(k in lower_chunk for k in ("task completed", "successfully finished", "all tests passed", "done!", "commit successful", "✓ completed")):
            logger.info(f"[{agent_name}] タスク完了を検知しました！")
            self._update_state(agent_name, "cheer")
            if self.on_task_completed:
                summary_line = lines[-1][:60]
                self.on_task_completed(agent_name, summary_line, recent_chunk)

        # 3. エラー検知 (Error / Failure)
        elif any(k in lower_chunk for k in ("traceback (most recent call last)", "fatal error", "failed with exit code", "uncaught exception", "syntaxerror:")):
            logger.info(f"[{agent_name}] エラーを検知しました！")
            self._update_state(agent_name, "sweat")

        # 4. 作業中・推論中検知 (Thinking / Typing)
        elif any(k in lower_chunk for k in ("running tool", "executing command", "editing file", "thinking...", "generating code", "building project")):
            self._update_state(agent_name, "typing")

    def _update_state(self, agent_name: str, new_state: str):
        """状態の変更をコールバックへ通知"""
        old_state = self._current_agent_states.get(agent_name)
        if old_state != new_state:
            self._current_agent_states[agent_name] = new_state
            if self.on_status_change:
                self.on_status_change(agent_name, new_state, {"agent": agent_name})


# シングルトン
_watcher_instance: Optional[AgentWatcher] = None

def get_agent_watcher(
    on_status_change: Optional[Callable] = None,
    on_task_completed: Optional[Callable] = None,
    on_approval_needed: Optional[Callable] = None
) -> AgentWatcher:
    global _watcher_instance
    if _watcher_instance is None:
        _watcher_instance = AgentWatcher(
            on_status_change=on_status_change,
            on_task_completed=on_task_completed,
            on_approval_needed=on_approval_needed
        )
    return _watcher_instance
