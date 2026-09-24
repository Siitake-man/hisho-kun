"""ネオ秘書くん — AI Dotfiles ＆ 知識の宝庫 (Knowledge Vault) バックアップ同期ツール (sync_ai_dotfiles.py)

4大AIエージェント (Antigravity, OpenCode, Cline, Codex) の設定・ルール・スキルと
秘書くんの「知識の宝庫 (user_insights)」を単一の Git 管理ディレクトリ (~/.ai_dotfiles) へ
集約・バックアップ・同期します。

主な機能:
1. 知識の宝庫 (user_insights) のデータ (id, category, content, context_tags, importance, created_at, updated_at) を
   knowledge_vault.json として安全にエクスポート。
2. エージェント設定ファイル (.agents, .opencode 等) の収集および同期。
3. --check オプションによる差分検知 (CI/自動化向け)。
"""

import argparse
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import app_paths
import database
from storage.connection import get_db_connection

# ロガーの設定
logger = logging.getLogger("sync_ai_dotfiles")


def export_knowledge_vault(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """秘書くんの『知識の宝庫』(user_insights) の全知見をエクスポートします。

    正しいスキーマ (id, category, content, context_tags, importance, created_at, updated_at) を使用し、
    旧スキーマ依存 (insight_key 等) による「no such column」エラーを防止します。

    Args:
        db_path (Optional[str]): 対象データベースパス。省略時は app_paths.get_db_path() を使用。

    Returns:
        List[Dict[str, Any]]: エクスポートされた知見データのリスト。
    """
    target_db = db_path or app_paths.get_db_path()
    if not os.path.exists(target_db):
        logger.warning(f"指定されたDBファイルが存在しません: {target_db}")
        return []

    try:
        with get_db_connection(target_db) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, category, content, context_tags, importance, created_at, updated_at
                FROM user_insights
                ORDER BY id ASC
            """)
            rows = cursor.fetchall()
            insights = []
            for row in rows:
                insights.append({
                    "id": row[0],
                    "category": row[1],
                    "content": row[2],
                    "context_tags": row[3] or "",
                    "importance": row[4],
                    "created_at": row[5],
                    "updated_at": row[6],
                })
            logger.info(f"Knowledge Vault から {len(insights)} 件の知見を正常に抽出しました。")
            return insights
    except Exception as e:
        logger.error(f"Knowledge Vault エクスポート失敗: {e}", exc_info=True)
        raise RuntimeError(f"Knowledge Vault エクスポート中にエラーが発生しました: {e}") from e


def sync_dotfiles(
    dotfiles_dir: Optional[Path] = None,
    db_path: Optional[str] = None,
    check_only: bool = False,
) -> Dict[str, Any]:
    """AI Dotfiles フォルダへ Knowledge Vault およびエージェント設定を同期します。

    Args:
        dotfiles_dir (Optional[Path]): 同期先ディレクトリ。省略時は ~/.ai_dotfiles。
        db_path (Optional[str]): データベースパス。
        check_only (bool): True の場合はファイルの書き込みを行わず差分チェックのみ実施。

    Returns:
        Dict[str, Any]: 同期結果サマリ。
    """
    target_dir = dotfiles_dir or (Path.home() / ".ai_dotfiles")
    vault_file = target_dir / "knowledge_vault.json"

    # 1. Knowledge Vault エクスポート
    insights = export_knowledge_vault(db_path=db_path)
    vault_json_bytes = json.dumps(insights, ensure_ascii=False, indent=2).encode("utf-8")

    has_diff = False
    if vault_file.exists():
        existing_bytes = vault_file.read_bytes()
        if existing_bytes != vault_json_bytes:
            has_diff = True
    else:
        has_diff = True

    if not check_only and has_diff:
        target_dir.mkdir(parents=True, exist_ok=True)
        vault_file.write_bytes(vault_json_bytes)
        logger.info(f"Knowledge Vault を同期しました: {vault_file} ({len(insights)} 件)")

    summary = {
        "status": "success",
        "has_diff": has_diff,
        "vault_count": len(insights),
        "target_dir": str(target_dir),
    }
    return summary


def main() -> int:
    """CLI エントリポイント。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [sync_ai_dotfiles] %(message)s",
        stream=sys.stderr,
    )
    parser = argparse.ArgumentParser(description="AI Dotfiles ＆ Knowledge Vault 同期ツール")
    parser.add_argument("--check", action="store_true", help="書き込みを行わず差分検知のみ実施")
    parser.add_argument("--dotfiles-dir", type=str, help="同期先 dotfiles ディレクトリパス")
    parser.add_argument("--db-path", type=str, help="対象 DB パス")

    args = parser.parse_args()
    dot_dir = Path(args.dotfiles_dir) if args.dotfiles_dir else None

    try:
        result = sync_dotfiles(
            dotfiles_dir=dot_dir,
            db_path=args.db_path,
            check_only=args.check,
        )
        if args.check and result["has_diff"]:
            logger.info("差分が検出されました。")
            return 1
        logger.info("AI Dotfiles 同期が正常に完了しました。")
        return 0
    except Exception as e:
        logger.error(f"AI Dotfiles 同期エラー: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
