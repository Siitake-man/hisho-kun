#!/usr/bin/env python3
"""
ネオ秘書くん - エージェント識別ユーティリティ (agent_identity.py)

MCPサーバー (hisho_mcp_server.py) が通知・承認要請を Desk Pet へ中継する際、
「どのエージェント (Cline / Claude Code / Codex / Cursor 等) からの通信か」を
自動識別するためのモジュール。外部依存を持たず、hisho_mcp_server から
安全にインポートできるよう標準ライブラリのみで構成している。

識別の優先順位:
  1. 環境変数 ``HISHO_AGENT_NAME``（MCP設定の env で明示指定する最強の上書き）
  2. 既知のコーディングエージェントが設定する環境変数の検出
  3. 環境変数名のプレフィックス推定
  4. 親プロセス名の推定（psutil が導入されている環境のみ・任意）
  5. フォールバック "AI Agent"
"""

import os
from typing import Dict, List, Optional, Tuple

# =============================================================================
# 定数
# =============================================================================

#: 環境変数による明示上書きに使うキー（MCP設定の "env" で設定してもらう）
OVERRIDE_ENV_KEY = "HISHO_AGENT_NAME"

#: 既知エージェントのシグネチャ環境変数 → 表示名マッピング（優先順）
_AGENT_ENV_SIGNATURES: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    # Claude Code は実行中プロセスへ CLAUDECODE=1 等を設定する
    (("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT"), "Claude Code"),
    # Cursor はチャット実行時にトレースIDを設定する
    (("CURSOR_TRACE_ID",), "Cursor"),
    # Codex CLI はサンドボックス関連の環境変数を設定する
    (("CODEX_SANDBOX", "CODEX_SANDBOX_NETWORK_DISABLED", "CODEX_HOME"), "Codex"),
    # Gemini CLI
    (("GEMINI_CLI",), "Gemini CLI"),
)

#: 環境変数名のプレフィックス推定（シグネチャ不一致時の第二次判定）
_AGENT_ENV_PREFIXES: Tuple[Tuple[str, str], ...] = (
    ("CLAUDE_", "Claude Code"),
    ("CODEX_", "Codex"),
    ("CURSOR_", "Cursor"),
    ("WINDSURF", "Windsurf"),
    ("ANTIGRAVITY_", "Antigravity"),
)

#: 親プロセス名（小文字比較）→ 表示名。後続の要素ほど汎用的な一致になるよう並べる
_PARENT_PROCESS_SIGNATURES: Tuple[Tuple[str, str], ...] = (
    ("claude", "Claude Code"),
    ("codex", "Codex"),
    ("cursor", "Cursor"),
    ("windsurf", "Windsurf"),
    ("antigravity", "Antigravity"),
    ("aider", "Aider"),
    ("gemini", "Gemini CLI"),
    # VS Code 本体 (Code.exe) の子プロセスとして動く MCP サーバーは
    # Cline 等の VS Code 拡張経由である可能性が高い（最終手段の推定）
    ("code", "Cline"),
)

#: すべての判定に失敗した場合のフォールバック表示名
DEFAULT_AGENT_NAME = "AI Agent"


# =============================================================================
# 公開API
# =============================================================================

def detect_agent_name() -> str:
    """実行環境から呼び出し元エージェント名を自動検出する。

    Returns:
        str: 検出されたエージェント表示名。判定不能な場合は "AI Agent"。
    """
    # 1. 明示上書き（MCP設定の env で指定）
    override = os.environ.get(OVERRIDE_ENV_KEY, "").strip()
    if override:
        return override

    # 2. 既知エージェントのシグネチャ環境変数
    for env_keys, name in _AGENT_ENV_SIGNATURES:
        for key in env_keys:
            if os.environ.get(key, "").strip():
                return name

    # 3. 環境変数名プレフィックスによる推定
    env_keys = list(os.environ.keys())
    for prefix, name in _AGENT_ENV_PREFIXES:
        if any(key.startswith(prefix) for key in env_keys):
            return name

    # 4. 親プロセス名による推定（psutil があれば利用）
    proc_name = _detect_from_parent_process()
    if proc_name:
        return proc_name

    return DEFAULT_AGENT_NAME


def resolve_agent_name(explicit: str = "") -> str:
    """ツール引数の agent_name を解決する。

    明示的な指定があればそれを最優先し、空・未指定の場合は環境から自動検出する。

    Args:
        explicit: ツール呼び出し時に明示指定されたエージェント名（空文字なら未指定扱い）。

    Returns:
        str: 実際に通知へ使用するエージェント表示名。
    """
    if explicit and explicit.strip():
        return explicit.strip()
    return detect_agent_name()


# =============================================================================
# 内部実装
# =============================================================================

def _detect_from_parent_process() -> str:
    """親プロセス連鎖を辿り、エージェントの実行体を推定する（任意・失敗時は空文字）。

    psutil が導入されていない環境では何もせず空文字を返すため、
    本関数の不在・失敗が MCP サーバー本体に影響することはない。

    Returns:
        str: 推定できたエージェント表示名。推定不能な場合は空文字。
    """
    try:
        import psutil  # type: ignore
    except ImportError:
        return ""

    try:
        proc = psutil.Process(os.getpid())
        for _ in range(6):  # 親を最大6世代まで辿る（cmd ラッパー等を突破するため）
            proc = proc.parent()  # type: ignore[assignment]
            if proc is None:
                break
            pname = (proc.name() or "").lower()
            for signature, label in _PARENT_PROCESS_SIGNATURES:
                if signature in pname:
                    return label
    except Exception:
        # プロセス列挙は環境により失敗しうるため、静かに諦める
        return ""
    return ""