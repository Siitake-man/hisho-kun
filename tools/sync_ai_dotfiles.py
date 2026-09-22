#!/usr/bin/env python3
"""全エージェント統合 AI Dotfiles バックアップ ＆ 復元ツール (sync_ai_dotfiles.py)

Antigravity, OpenCode, Cline, Codex の4大コーディングエージェント環境と、
ネオ秘書くんの「知識の宝庫 (user_insights)」を単一の Git リポジトリ (~/.ai_dotfiles) として
安全に一元管理・バックアップ・別端末へ復元（DR）する。

特徴:
1. ゼロトークン・差分Git管理: 毎日ZIPが溜まる問題を排除し、プライベートGitでクリーンに管理。
2. セキュリティ ＆ プライバシー重視: auth.json, cap_sid, トークン等の認証ファイルや巨大DBバイナリを除外。
3. 知識の宝庫 (Knowledge Vault) テキストSQLダンプ: neo_secretary.db から知見のみをSQL化。
4. 双方向同期: --export (実機->Dotfiles) と --restore (Dotfiles->実機) に対応。
"""

import os
import sys
import shutil
import sqlite3
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("ai_dotfiles")

HOME = Path.home()
DEFAULT_DOTFILES_DIR = HOME / ".ai_dotfiles"
HISHO_ROOT = Path(r"c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん").resolve()

# 除外パターン
EXCLUDED_PATTERNS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".pytest_cache",
    "auth.json",
    "cap_sid",
    ".sandbox-secrets",
    "credentials",
    "token",
    "secrets",
    "logs_2.sqlite",
    "state_5.sqlite",
    "thread_history_1.sqlite",
    "memories_1.sqlite",
}


def _should_exclude(path: Path) -> bool:
    """指定パスが除外対象かチェックする。"""
    name_lower = path.name.lower()
    for pattern in EXCLUDED_PATTERNS:
        if pattern.lower() in name_lower:
            return True
    # 拡張子チェック
    if path.suffix.lower() in [".sqlite", ".sqlite-shm", ".sqlite-wal", ".bak", ".log"]:
        return True
    return False


def _safe_copy_file(src: Path, dst: Path) -> bool:
    """ファイルを安全にコピーする（存在しない場合や除外対象はスキップ）。"""
    if not src.exists() or _should_exclude(src):
        return False
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True
    except Exception as e:
        logger.warning(f"  ⚠️ コピー失敗: {src} -> {e}")
        return False


def _safe_copy_tree(src_dir: Path, dst_dir: Path) -> int:
    """ディレクトリを再帰的にコピーする（除外パターンをスキップ）。"""
    if not src_dir.exists() or not src_dir.is_dir():
        return 0

    copied_count = 0
    dst_dir.mkdir(parents=True, exist_ok=True)

    for item in src_dir.rglob("*"):
        if _should_exclude(item):
            continue
        rel_path = item.relative_to(src_dir)
        target = dst_dir / rel_path

        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(item, target)
                copied_count += 1
            except Exception as e:
                logger.warning(f"  ⚠️ ファイルコピー失敗: {item} -> {e}")

    return copied_count


def ensure_gitignore(dotfiles_dir: Path) -> None:
    """Git-Safe な .gitignore を配置する。"""
    gitignore_path = dotfiles_dir / ".gitignore"
    content = """# AI Dotfiles Security & Size Filters
# 認証・秘密鍵
auth.json
cap_sid
.sandbox-secrets
*.token
*.key
*.pem
*secret*
*credential*

# 巨大DBバイナリ・ログ
*.sqlite
*.sqlite-shm
*.sqlite-wal
*.db
*.db-shm
*.db-wal
*.log
*.tmp*
*.bak*

# Node / Python キャッシュ
node_modules/
__pycache__/
.pytest_cache/
.vscode/

# 個人キャッシュ・ブラウザセッション
cache/
attachments/
browser/
sessions/
"""
    if not gitignore_path.exists():
        dotfiles_dir.mkdir(parents=True, exist_ok=True)
        gitignore_path.write_text(content.strip() + "\n", encoding="utf-8")
        logger.info(f"🛡️  .gitignore を配置しました: {gitignore_path}")


def export_antigravity(dotfiles_dir: Path) -> None:
    """Antigravity の設定、ルール、スキル、フックをエクスポート"""
    dest = dotfiles_dir / "antigravity"
    gemini_dir = HOME / ".gemini"

    # 1. GEMINI.md
    _safe_copy_file(gemini_dir / "GEMINI.md", dest / "GEMINI.md")

    # 2. config (hooks.json, mcp_config.json, skills)
    config_dir = gemini_dir / "config"
    _safe_copy_file(config_dir / "hooks.json", dest / "config" / "hooks.json")
    _safe_copy_file(config_dir / "mcp_config.json", dest / "config" / "mcp_config.json")
    if (config_dir / "skills").exists():
        c = _safe_copy_tree(config_dir / "skills", dest / "config" / "skills")
        logger.info(f"  [Antigravity] スキル {c} ファイルを同期")

    # 3. tools/jev_router
    jev_dir = gemini_dir / "tools" / "jev_router"
    if jev_dir.exists():
        c = _safe_copy_tree(jev_dir, dest / "tools" / "jev_router")
        logger.info(f"  [Antigravity] Jev Router / Hook {c} ファイルを同期")


def export_opencode(dotfiles_dir: Path) -> None:
    """OpenCode の設定、AGENTS.md、プラグイン、スキルをエクスポート"""
    dest = dotfiles_dir / "opencode"
    opencode_dir = HOME / ".config" / "opencode"
    if not opencode_dir.exists():
        return

    _safe_copy_file(opencode_dir / "AGENTS.md", dest / "AGENTS.md")
    _safe_copy_file(opencode_dir / "opencode.jsonc", dest / "opencode.jsonc")
    _safe_copy_file(opencode_dir / "package.json", dest / "package.json")

    # plugins (hisho-approval-notify 等)
    if (opencode_dir / "plugins").exists():
        c = _safe_copy_tree(opencode_dir / "plugins", dest / "plugins")
        logger.info(f"  [OpenCode] プラグイン {c} ファイルを同期")

    # skills
    if (opencode_dir / "skills").exists():
        c = _safe_copy_tree(opencode_dir / "skills", dest / "skills")
        logger.info(f"  [OpenCode] スキル {c} ファイルを同期")


def export_cline(dotfiles_dir: Path) -> None:
    """Cline の設定、CLAUDE.md、MCP設定、スキルをエクスポート"""
    dest = dotfiles_dir / "cline"
    cline_dir = HOME / "AppData" / "Roaming" / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings"
    if not cline_dir.exists():
        return

    _safe_copy_file(cline_dir / "CLAUDE.md", dest / "CLAUDE.md")
    _safe_copy_file(cline_dir / "cline_mcp_settings.json", dest / "cline_mcp_settings.json")

    if (cline_dir / "skills").exists():
        c = _safe_copy_tree(cline_dir / "skills", dest / "skills")
        logger.info(f"  [Cline] スキル {c} ファイルを同期")


def export_codex(dotfiles_dir: Path) -> None:
    """Codex の設定、instructions.md、AGENTS.md、スキル、ルール、プラグインをエクスポート"""
    dest = dotfiles_dir / "codex"
    codex_dir = HOME / ".codex"
    if not codex_dir.exists():
        return

    _safe_copy_file(codex_dir / "instructions.md", dest / "instructions.md")
    _safe_copy_file(codex_dir / "AGENTS.md", dest / "AGENTS.md")
    _safe_copy_file(codex_dir / "config.toml", dest / "config.toml")

    for sub in ["skills", "rules", "plugins"]:
        src_sub = codex_dir / sub
        if src_sub.exists():
            c = _safe_copy_tree(src_sub, dest / sub)
            logger.info(f"  [Codex] {sub} {c} ファイルを同期")


def export_knowledge_vault(dotfiles_dir: Path) -> None:
    """ネオ秘書くんの「知識の宝庫 (user_insights テーブル)」をテキストSQLとしてエクスポート"""
    dest = dotfiles_dir / "neo_secretary"
    dest.mkdir(parents=True, exist_ok=True)

    db_path = HISHO_ROOT / "neo_secretary.db"
    if not db_path.exists():
        logger.warning(f"  ⚠️ 秘書くんDBが見つかりません: {db_path}")
        return

    sql_file = dest / "user_insights.sql"
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()

        # テーブルの存在確認
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_insights'")
        if not cursor.fetchone():
            logger.warning("  ⚠️ user_insights テーブルが存在しません。")
            conn.close()
            return

        # スキーマとデータの抽出
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='user_insights'")
        create_sql = cursor.fetchone()[0]

        cursor.execute("SELECT category, insight_key, content, context, confidence, created_at, updated_at FROM user_insights")
        rows = cursor.fetchall()
        conn.close()

        lines = [
            "-- ネオ秘書くん 知識の宝庫 (Knowledge Vault: user_insights) エクスポート",
            f"-- Total Records: {len(rows)}",
            "",
            "CREATE TABLE IF NOT EXISTS user_insights (",
            "    category TEXT NOT NULL,",
            "    insight_key TEXT NOT NULL,",
            "    content TEXT NOT NULL,",
            "    context TEXT,",
            "    confidence REAL DEFAULT 1.0,",
            "    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,",
            "    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,",
            "    PRIMARY KEY (category, insight_key)",
            ");",
            "",
        ]

        for r in rows:
            cat, key, cnt, ctx, conf, cat_at, upd_at = r
            # SQLエスケープ
            cnt_esc = cnt.replace("'", "''") if cnt else ""
            ctx_esc = ctx.replace("'", "''") if ctx else ""
            lines.append(
                f"INSERT OR REPLACE INTO user_insights (category, insight_key, content, context, confidence, created_at, updated_at) "
                f"VALUES ('{cat}', '{key}', '{cnt_esc}', '{ctx_esc}', {conf or 1.0}, '{cat_at}', '{upd_at}');"
            )

        sql_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info(f"💎 [Knowledge Vault] 知識の宝庫 {len(rows)} 件をSQLエクスポート ➔ {sql_file}")

    except Exception as e:
        logger.warning(f"  ⚠️ Knowledge Vault エクスポート失敗: {e}")


def restore_dotfiles(dotfiles_dir: Path) -> None:
    """Dotfiles リポジトリの内容を各エージェントの実機環境へ展開・復元する。"""
    logger.info("🔄 AI Dotfiles 復元処理を開始します...")

    # 1. Antigravity
    src_anti = dotfiles_dir / "antigravity"
    if src_anti.exists():
        gemini_dir = HOME / ".gemini"
        _safe_copy_file(src_anti / "GEMINI.md", gemini_dir / "GEMINI.md")
        _safe_copy_file(src_anti / "config" / "hooks.json", gemini_dir / "config" / "hooks.json")
        _safe_copy_file(src_anti / "config" / "mcp_config.json", gemini_dir / "config" / "mcp_config.json")
        if (src_anti / "config" / "skills").exists():
            _safe_copy_tree(src_anti / "config" / "skills", gemini_dir / "config" / "skills")
        if (src_anti / "tools" / "jev_router").exists():
            _safe_copy_tree(src_anti / "tools" / "jev_router", gemini_dir / "tools" / "jev_router")
        logger.info("  ✅ Antigravity 環境復元完了")

    # 2. OpenCode
    src_open = dotfiles_dir / "opencode"
    if src_open.exists():
        opencode_dir = HOME / ".config" / "opencode"
        _safe_copy_file(src_open / "AGENTS.md", opencode_dir / "AGENTS.md")
        _safe_copy_file(src_open / "opencode.jsonc", opencode_dir / "opencode.jsonc")
        _safe_copy_file(src_open / "package.json", opencode_dir / "package.json")
        if (src_open / "plugins").exists():
            _safe_copy_tree(src_open / "plugins", opencode_dir / "plugins")
        if (src_open / "skills").exists():
            _safe_copy_tree(src_open / "skills", opencode_dir / "skills")
        logger.info("  ✅ OpenCode 環境復元完了")

    # 3. Cline
    src_cline = dotfiles_dir / "cline"
    if src_cline.exists():
        cline_dir = HOME / "AppData" / "Roaming" / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings"
        _safe_copy_file(src_cline / "CLAUDE.md", cline_dir / "CLAUDE.md")
        _safe_copy_file(src_cline / "cline_mcp_settings.json", cline_dir / "cline_mcp_settings.json")
        if (src_cline / "skills").exists():
            _safe_copy_tree(src_cline / "skills", cline_dir / "skills")
        logger.info("  ✅ Cline 環境復元完了")

    # 4. Codex
    src_codex = dotfiles_dir / "codex"
    if src_codex.exists():
        codex_dir = HOME / ".codex"
        _safe_copy_file(src_codex / "instructions.md", codex_dir / "instructions.md")
        _safe_copy_file(src_codex / "AGENTS.md", codex_dir / "AGENTS.md")
        _safe_copy_file(src_codex / "config.toml", codex_dir / "config.toml")
        for sub in ["skills", "rules", "plugins"]:
            if (src_codex / sub).exists():
                _safe_copy_tree(src_codex / sub, codex_dir / sub)
        logger.info("  ✅ Codex 環境復元完了")

    # 5. 知識の宝庫 インポート
    src_vault_sql = dotfiles_dir / "neo_secretary" / "user_insights.sql"
    db_path = HISHO_ROOT / "neo_secretary.db"
    if src_vault_sql.exists():
        try:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            sql_script = src_vault_sql.read_text(encoding="utf-8")
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.executescript(sql_script)
            conn.commit()
            conn.close()
            logger.info("  ✅ [Knowledge Vault] 知識の宝庫 (user_insights) インポート完了")
        except Exception as e:
            logger.warning(f"  ⚠️ Knowledge Vault インポート失敗: {e}")

    logger.info("🎉 全エージェント環境の復元が完了しました！")


def print_git_instructions(dotfiles_dir: Path) -> None:
    """Git commit / push 用のワンライナーコマンドを出力する。"""
    dotfiles_posix = str(dotfiles_dir).replace("\\", "/")
    print("\n" + "=" * 60)
    print("📦 [AI Dotfiles] バックアップ完了！Git同期コマンド:")
    print("=" * 60)
    print(f"cd '{dotfiles_posix}'; git init; git add -A; git commit -m 'sync: update AI dotfiles'; git push\n")


def main():
    parser = argparse.ArgumentParser(description="全エージェント統合 AI Dotfiles バックアップ & 復元ツール")
    parser.add_argument("--dir", type=str, default=str(DEFAULT_DOTFILES_DIR), help="Dotfilesリポジトリのディレクトリパス")
    parser.add_argument("--export", "--backup", action="store_true", help="実機設定・知見をDotfilesへ集約コピー")
    parser.add_argument("--restore", action="store_true", help="Dotfilesから実機環境へ設定・知見を展開復元")
    parser.add_argument("--git-cmd", action="store_true", help="Git同期用コマンドを出力")

    args = parser.parse_args()
    dotfiles_dir = Path(args.dir).resolve()

    if args.restore:
        restore_dotfiles(dotfiles_dir)
        return

    # デフォルトはエクスポート
    print("=" * 60)
    print("🚀 全エージェント統合 AI Dotfiles バックアップ")
    print(f"📂 出力先: {dotfiles_dir}")
    print("=" * 60)

    dotfiles_dir.mkdir(parents=True, exist_ok=True)
    ensure_gitignore(dotfiles_dir)

    export_antigravity(dotfiles_dir)
    export_opencode(dotfiles_dir)
    export_cline(dotfiles_dir)
    export_codex(dotfiles_dir)
    export_knowledge_vault(dotfiles_dir)

    print("-" * 60)
    logger.info("✨ 全エージェント ＆ 知識の宝庫の集約が正常に完了しました！")
    print_git_instructions(dotfiles_dir)


if __name__ == "__main__":
    main()
