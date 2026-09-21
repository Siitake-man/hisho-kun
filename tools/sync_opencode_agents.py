"""ネオ秘書くん — OpenCode サブエージェント定義 同期ジェネレータ (sync_opencode_agents.py)

Antigravity のカスタムエージェント正本 (``.agents/agents/*.md``) を読み取り、
OpenCode V2 規格のサブエージェント定義 (``.opencode/agents/*.md``) を生成する。

Why (なぜ必要か):
    - Antigravity 形式の frontmatter (``tools:`` に Antigravity 固有ツール名のリスト) は
      OpenCode V2 では解釈されない。V2 は ``permissions`` (action / resource / effect) を要求する。
    - 2つの環境で「同一の専門家陣形」を維持しつつ、権限だけを OpenCode の
      最小権限モデルへ正しく翻訳する必要がある。
    - 正本1つ・生成物1つという一方向同期にすることで、二重管理によるドリフトを根絶する。

使い方::

    venv\\Scripts\\python.exe tools\\sync_opencode_agents.py            # 生成 (上書き)
    venv\\Scripts\\python.exe tools\\sync_opencode_agents.py --check    # 差分検知のみ (CI用 / 差分ありで終了コード1)
    venv\\Scripts\\python.exe tools\\sync_opencode_agents.py --prune    # 孤立した生成物を明示的に削除する

設計:
    - 正本  : ``.agents/agents/<name>.md``   (ボス資産 / このツールは絶対に書き換えない)
    - 生成物: ``.opencode/agents/<name>.md`` (先頭に自動生成バナー / 直接編集禁止)
    - 権限ポリシーは ``AGENT_POLICIES`` に集約する。自動推測ではなく明示テーブルで管理する。

不変条件 (2026-09-21 独立査読 P1-1 の再発防止 / ``tests/test_sync_opencode_agents.py`` で凍結):
    **エージェント権限は「ACLを締める方向」にのみ働かせる。**
    OpenCode の permission は後勝ち (最後にマッチしたルールが有効) であり、エージェント定義の
    ルールはグローバル設定のルールより**後**に評価される。したがって、エージェント側で
    ``shell`` の ``allow`` を再宣言すると、グローバル設定の破壊的コマンド ``deny`` を
    上書きし得る。よって本ツールのポリシーテーブルには **allow を一切書かない**。
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Final, List, Optional, Sequence, Tuple

import yaml

logger = logging.getLogger("sync_opencode_agents")

# =============================================================================
# 定数
# =============================================================================

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
SOURCE_DIR: Final[Path] = PROJECT_ROOT / ".agents" / "agents"
TARGET_DIR: Final[Path] = PROJECT_ROOT / ".opencode" / "agents"

#: Antigravity ツール名 → OpenCode ツール名の読み替え表 (生成バナーに記載する)
#: 注: V2 の permission action は `shell` / `subagent` であり、V1 の `bash` / `task` ではない。
TOOL_TRANSLATION_NOTE: Final[str] = (
    "view_file → read ／ grep_search → grep ／ list_dir → glob ／ "
    "replace_file_content・multi_replace_file_content・write_to_file → edit ／ "
    "run_command → bash (V1) / shell (V2) ／ invoke_subagent → subagent ツール"
)

#: 権限ポリシーの型 (action / resource / effect)
Policy = Tuple[Dict[str, str], ...]

#: MCP 経由の書き込みツール (Read-Only エージェントでは禁止する)
_MCP_WRITE_TOOLS: Final[Tuple[str, ...]] = (
    "neo_hisho_bridge_create_task",
    "neo_hisho_bridge_complete_task",
    "neo_hisho_bridge_create_calendar_event",
    "neo_hisho_bridge_remember_boss_insight",
)

#: 読み取り専用エージェント (調査・査読・分析に徹し、一切の変更・コマンド実行・委譲を行わない)
READ_ONLY_PERMISSIONS: Final[Policy] = (
    {"action": "edit", "resource": "*", "effect": "deny"},
    {"action": "shell", "resource": "*", "effect": "deny"},
    {"action": "subagent", "resource": "*", "effect": "deny"},
) + tuple({"action": tool, "resource": "*", "effect": "deny"} for tool in _MCP_WRITE_TOOLS)

#: プロジェクト ACL をそのまま継承するエージェント (実装系・テスト系)
#: 注: ここに allow を書いてはならない (モジュール docstring の不変条件を参照)。
INHERIT_PROJECT_ACL: Final[Policy] = ()

#: オーケストレーター (自らは書かず、専門エージェントへ委譲して閉ループを回す)
ORCHESTRATOR_PERMISSIONS: Final[Policy] = (
    {"action": "edit", "resource": "*", "effect": "deny"},
)

#: エージェント名 → (権限ポリシー, UI色)
AGENT_POLICIES: Final[Dict[str, Tuple[Policy, str]]] = {
    # --- 全体統括 ---
    "hisho-orchestrator": (ORCHESTRATOR_PERMISSIONS, "#ffd700"),
    # --- 計画・設計 (Read-Only) ---
    "task-planner": (READ_ONLY_PERMISSIONS, "#4a90d9"),
    # --- 実装 (プロジェクト ACL を継承) ---
    "python-architect": (INHERIT_PROJECT_ACL, "#ff8c42"),
    "pixel-frontend-designer": (INHERIT_PROJECT_ACL, "#ff6b9d"),
    "agent-tester": (INHERIT_PROJECT_ACL, "#4caf50"),
    # --- 分析・査読 (Read-Only) ---
    "error-analyst": (READ_ONLY_PERMISSIONS, "#e53935"),
    "quality-reviewer": (READ_ONLY_PERMISSIONS, "#9c27b0"),
    "devils-advocate": (READ_ONLY_PERMISSIONS, "#37474f"),
    "product-strategist": (READ_ONLY_PERMISSIONS, "#009688"),
    "legal-compliance": (READ_ONLY_PERMISSIONS, "#607d8b"),
    "visionary-dreamer": (READ_ONLY_PERMISSIONS, "#7e57c2"),
}

#: Antigravity 側で利用されうる既知ツール名 (未知ツールの警告用)
KNOWN_SOURCE_TOOLS: Final[frozenset] = frozenset(
    {
        "view_file",
        "grep_search",
        "list_dir",
        "replace_file_content",
        "multi_replace_file_content",
        "write_to_file",
        "run_command",
        "search_web",
        "read_url_content",
    }
)


# =============================================================================
# データ構造
# =============================================================================


@dataclass(frozen=True)
class AgentSource:
    """正本エージェント定義1件分の解決済みデータ。

    Attributes:
        path: 正本ファイルのパス。
        name: エージェント名 (frontmatter の name / ファイル名と一致することを検証済み)。
        description: OpenCode が起動候補として表示する説明文。
        meta: frontmatter 全体。
        body: frontmatter を除いた本文。
        digest: 正本内容の SHA-256 先頭12桁 (改行コードを正規化して算出)。
    """

    path: Path
    name: str
    description: str
    meta: Dict[str, Any]
    body: str
    digest: str


# =============================================================================
# 内部実装
# =============================================================================


def _yaml_scalar(value: str) -> str:
    """YAML スカラーとして安全な単一引用符付き文字列を生成する。

    Args:
        value: 対象文字列。

    Returns:
        str: 単一引用符で囲み、内部の単一引用符をエスケープした文字列。
    """
    return "'" + str(value).replace("'", "''") + "'"


def _split_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    """Markdown を YAML frontmatter と本文に分解する。

    Args:
        text: Markdown 全文。

    Returns:
        Tuple[Dict[str, Any], str]: (frontmatter 辞書, 本文)。

    Raises:
        ValueError: frontmatter が存在しない、または YAML として不正な場合。
    """
    if not text.startswith("---"):
        raise ValueError("frontmatter (---) が見つかりません。")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("frontmatter が閉じられていません。")
    meta = yaml.safe_load(parts[1]) or {}
    if not isinstance(meta, dict):
        raise ValueError("frontmatter が辞書として解釈できません。")
    return meta, parts[2].lstrip("\n")


def _normalized_digest(path: Path) -> str:
    """正本の内容ハッシュを算出する (改行コードを LF へ正規化)。

    Args:
        path: 正本ファイルのパス。

    Returns:
        str: SHA-256 の先頭12桁。
    """
    normalized = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def resolve_mode(meta: Dict[str, Any]) -> str:
    """正本の mainAgent / subagent 宣言から OpenCode V2 の mode を導出する。

    Why: 正本が ``mainAgent: true`` を宣言しているエージェントを ``mode: subagent`` に固定すると、
    Antigravity では選べた「主エージェント」としての起動が OpenCode では不可能になり、
    Jev が primary に指名しても実体が伴わない (名乗りの形骸化) 状態を生む。

    Args:
        meta: 正本の frontmatter 辞書。

    Returns:
        str: ``all`` / ``primary`` / ``subagent`` のいずれか。
    """
    is_main = bool(meta.get("mainAgent"))
    is_subagent = bool(meta.get("subagent"))
    if is_main and is_subagent:
        return "all"
    if is_main:
        return "primary"
    return "subagent"


def render_permissions(permissions: Sequence[Dict[str, str]]) -> str:
    """権限ポリシーを OpenCode V2 の YAML ブロックへ整形する。

    Args:
        permissions: action / resource / effect の辞書列 (空なら ``[]``)。

    Returns:
        str: YAML の ``permissions:`` ブロック文字列。
    """
    if not permissions:
        return "permissions: []"
    lines: List[str] = ["permissions:"]
    for rule in permissions:
        lines.append("  - action: %s" % rule["action"])
        lines.append("    resource: %s" % _yaml_scalar(rule["resource"]))
        lines.append("    effect: %s" % rule["effect"])
    return "\n".join(lines)


def render_agent_file(agent: AgentSource) -> str:
    """1エージェント分の OpenCode 定義ファイル内容を生成する。

    Args:
        agent: 解決済みの正本データ。

    Returns:
        str: 生成ファイルの全文。

    Raises:
        KeyError: 権限ポリシーが未定義のエージェント名の場合。
    """
    permissions, color = AGENT_POLICIES[agent.name]
    try:
        rel_source = agent.path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        rel_source = agent.path.as_posix()

    frontmatter = "\n".join(
        [
            "---",
            "description: %s" % _yaml_scalar(agent.description),
            "mode: %s" % resolve_mode(agent.meta),
            "color: %s" % _yaml_scalar(color),
            render_permissions(permissions),
            "---",
        ]
    )

    banner = "\n".join(
        [
            "<!-- ============================================================================",
            "  ⚠️ 自動生成ファイル — 直接編集しないこと (編集しても次回同期で上書きされます)",
            "  正本        : %s" % rel_source,
            "  正本ハッシュ: sha256:%s" % agent.digest,
            "  生成ツール  : tools/sync_opencode_agents.py",
            "  同期の狙い  : Antigravity と OpenCode で同一の専門エージェント陣形を維持する",
            "  OpenCode 読み替え: %s" % TOOL_TRANSLATION_NOTE,
            "============================================================================ -->",
        ]
    )

    return "\n".join([frontmatter, "", banner, "", agent.body.rstrip(), ""])


def load_sources(source_dir: Path) -> List[AgentSource]:
    """正本ディレクトリから全エージェント定義を読み込む。

    Args:
        source_dir: 正本ディレクトリ。

    Returns:
        List[AgentSource]: 解決済みの正本データ一覧 (ファイル名昇順)。

    Raises:
        FileNotFoundError: 正本ディレクトリが存在しない場合。
        ValueError: frontmatter が不正な正本が含まれる場合。
    """
    if not source_dir.is_dir():
        raise FileNotFoundError("正本ディレクトリが存在しません: %s" % source_dir)

    sources: List[AgentSource] = []
    for path in sorted(source_dir.glob("*.md")):
        meta, body = _split_frontmatter(path.read_text(encoding="utf-8"))
        sources.append(
            AgentSource(
                path=path,
                name=str(meta.get("name") or path.stem),
                description=str(meta.get("description") or "").strip(),
                meta=meta,
                body=body,
                digest=_normalized_digest(path),
            )
        )
    return sources


def validate(sources: Sequence[AgentSource]) -> List[str]:
    """正本データの健全性を検査し、警告メッセージ一覧を返す。

    Args:
        sources: 解決済みの正本データ一覧。

    Returns:
        List[str]: 警告メッセージ一覧 (空なら健全)。
    """
    warnings: List[str] = []
    for agent in sources:
        if agent.name != agent.path.stem:
            warnings.append(
                "%s: name (%s) とファイル名が一致しません。" % (agent.path.name, agent.name)
            )
        if agent.name not in AGENT_POLICIES:
            warnings.append("%s: AGENT_POLICIES に権限ポリシーが未定義です。" % agent.path.name)
        if not agent.description:
            warnings.append(
                "%s: description が空です (OpenCode が起動候補として表示できません)。"
                % agent.path.name
            )
        unknown = [t for t in (agent.meta.get("tools") or []) if t not in KNOWN_SOURCE_TOOLS]
        if unknown:
            warnings.append("%s: 未知の Antigravity ツール名 %s" % (agent.path.name, unknown))
    return warnings


def _find_orphans(sources: Sequence[AgentSource], target_dir: Path) -> List[str]:
    """正本に対応するファイルを持たない生成物 (孤立ファイル) を検出する。

    Args:
        sources: 解決済みの正本データ一覧。
        target_dir: 生成物ディレクトリ。

    Returns:
        List[str]: 孤立ファイル名の一覧 (昇順)。
    """
    known = {"%s.md" % agent.name for agent in sources}
    return sorted(p.name for p in target_dir.glob("*.md") if p.name not in known)


def sync(
    check_only: bool = False,
    source_dir: Optional[Path] = None,
    target_dir: Optional[Path] = None,
    prune: bool = False,
) -> int:
    """正本から OpenCode 用エージェント定義を生成する。

    Args:
        check_only: True の場合は書き込みを行わず差分検知のみ行う。
        source_dir: 正本ディレクトリ (省略時は ``.agents/agents``)。
        target_dir: 生成物ディレクトリ (省略時は ``.opencode/agents``)。
        prune: True の場合は正本に対応しない生成物を削除する (既定は安全側の False)。

    Returns:
        int: 終了コード (0: 正常 / 1: ドリフトまたは検証警告あり)。

    Raises:
        FileNotFoundError: 正本ディレクトリが存在しない場合。
        ValueError: 権限ポリシー未定義のエージェントがあり、書き込みモードの場合。
    """
    src = source_dir or SOURCE_DIR
    dst = target_dir or TARGET_DIR

    sources = load_sources(src)
    warnings = validate(sources)
    for warning in warnings:
        logger.warning(warning)

    missing_policy = [a.name for a in sources if a.name not in AGENT_POLICIES]
    if missing_policy and not check_only:
        raise ValueError(
            "AGENT_POLICIES に権限ポリシーが未定義です: %s — "
            "tools/sync_opencode_agents.py の AGENT_POLICIES に追記してください。"
            % ", ".join(missing_policy)
        )

    dst.mkdir(parents=True, exist_ok=True)

    drift: List[str] = []
    written = 0

    for agent in sources:
        if agent.name in missing_policy:
            drift.append("%s.md (AGENT_POLICIES 未定義)" % agent.name)
            continue

        rendered = render_agent_file(agent)
        target = dst / ("%s.md" % agent.name)
        current = target.read_text(encoding="utf-8") if target.exists() else None

        if current == rendered:
            logger.info("同期済み : %s", target.name)
            continue

        if check_only:
            drift.append(target.name)
            logger.error("差分あり : %s", target.name)
            continue

        target.write_text(rendered, encoding="utf-8")
        written += 1
        logger.info("%s : %s", "更新" if current is not None else "生成", target.name)

    orphans = _find_orphans(sources, dst)
    for name in orphans:
        if prune and not check_only:
            (dst / name).unlink()
            logger.warning("孤立した生成物を削除: %s", name)
            continue
        logger.warning("孤立した生成物: %s (正本に対応するファイルがありません)", name)
        if check_only:
            drift.append(name)

    logger.info(
        "完了 — 正本 %d 件 / 書き込み %d 件 / ドリフト %d 件 / 孤立 %d 件",
        len(sources),
        written,
        len(drift),
        len(orphans),
    )

    exit_code = 0
    if check_only and drift:
        logger.error(
            "ドリフト検知: %s (`python tools/sync_opencode_agents.py` で再同期してください)",
            ", ".join(drift),
        )
        exit_code = 1
    if warnings:
        logger.error(
            "正本の検証警告 %d 件 — 解消してください (CI を落としています)。", len(warnings)
        )
        exit_code = 1
    return exit_code


def main() -> int:
    """CLI エントリポイント。

    Returns:
        int: 終了コード。
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stderr,
    )
    parser = argparse.ArgumentParser(
        description="Antigravity のカスタムエージェント正本を OpenCode V2 形式へ同期する。"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="書き込みを行わず、生成物が正本と一致しているか検証する (差分があれば終了コード1)。",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="正本に対応しない生成物 (孤立ファイル) を削除する。既定では削除せず警告のみ。",
    )
    args = parser.parse_args()

    try:
        return sync(check_only=bool(args.check), prune=bool(args.prune))
    except (FileNotFoundError, ValueError) as exc:
        logger.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
