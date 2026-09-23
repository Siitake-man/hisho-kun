#!/usr/bin/env python3
"""スキル安全アーカイブ退避スクリプト (archive_pruned_skills.py)

Jev 全スキル棚卸し監査レポート (docs/reports/SKILLS_AUDIT_REPORT.md) に基づき、
引き算対象となった38件のスキルを
`~/.gemini/config/skills/` から `~/.gemini/config/skills_archive/` へ安全に移動（退避）する。

※安全設計:
1. ファイル削除は一切行わない（shutil.move によるディレクトリ移動）。
2. 精鋭一軍・ボス指定スキル・自作メタスキルは絶対に移動しないセーフガード内蔵。
3. いつでも1秒で全件元に戻せる復元スクリプト (tools/restore_skills.py) を自動生成する。
"""

import os
import sys
import shutil
from pathlib import Path
from typing import List

HOME = Path.home()
SKILLS_DIR = HOME / ".gemini" / "config" / "skills"
ARCHIVE_DIR = HOME / ".gemini" / "config" / "skills_archive"
RESTORE_SCRIPT = Path(r"c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん\tools\restore_skills.py").resolve()

# 退避対象の38件（Jev客観監査レポート確定リスト）
PRUNED_SKILLS = [
    # 企業クラウドデータ基盤 (24件: 個人OSSスタック外)
    "bigquery-ai-ml",
    "bigquery-bigframes",
    "bigquery-data-transfer-service",
    "bigquery-graph",
    "bigquery-sql",
    "bigtable-basics",
    "building-data-apps",
    "data-autocleaning",
    "dataform-bigquery",
    "dbt-bigquery",
    "discovering-gcp-data-assets",
    "federate-lakehouse-catalog",
    "gcp-composer-troubleshooting",
    "gcp-data-pipelines",
    "gcp-dataflow",
    "gcp-managed-airflow-dag-authoring",
    "gcp-managed-airflow-migrations",
    "gcp-managed-airflow-recommendations",
    "gcp-pipeline-orchestration",
    "gcp-pipeline-resource-provisioning",
    "google-cloud-storage-basics",
    "google-cloud-storage-bucket-architect",
    "google-cloud-storage-fuse",
    "schema-mapping",
    # UI重複・下位互換 (14件: ui-ux-pro-max がマスターとして君臨するため引き算可能)
    "apple-design",
    "appllama-design",
    "baseline-ui",
    "brand-guidelines",
    "canvas-design",
    "cinematic-web-experience",
    "design-taste-frontend",
    "emil-design-eng",
    "hallmark",
    "slack-gif-creator",
    "theme-factory",
    "visual-design-wallbash",
    "web-artifacts-builder",
    "web-design-guidelines"
]

# 絶対移動禁止ガード（念のための物理的二重防御）
NEVER_ARCHIVE = {
    "codebase-design", "archify", "fireworks-open-eli5", "teach", "ui-ux-pro-max", "ruthless-code-evaluation",
    "init-session-skills", "code-review-skill-generator", "graph-engineering-skill-generator",
    "generate-ai-company-context", "generate-project-agents", "skill-generator", "skill-repair",
    "tdd", "officecli", "product-showcase", "mcp-builder"
}


def generate_restore_script(moved_skills: List[str]):
    """復元スクリプトを自動生成する"""
    code = f'''#!/usr/bin/env python3
"""スキル一括復元スクリプト (restore_skills.py)

~/.gemini/config/skills_archive/ へ退避させたスキルを
直ちに ~/.gemini/config/skills/ へ戻します。
"""
import shutil
from pathlib import Path

HOME = Path.home()
SKILLS_DIR = HOME / ".gemini" / "config" / "skills"
ARCHIVE_DIR = HOME / ".gemini" / "config" / "skills_archive"

SKILLS_TO_RESTORE = {moved_skills}

def main():
    restored = 0
    for name in SKILLS_TO_RESTORE:
        src = ARCHIVE_DIR / name
        dst = SKILLS_DIR / name
        if src.exists():
            shutil.move(str(src), str(dst))
            print(f"  ↩️ 復元完了: {{name}}")
            restored += 1
    print(f"\\n✅ 全 {{restored}} 件のスキルを元通り復元しました。")

if __name__ == "__main__":
    main()
'''
    RESTORE_SCRIPT.write_text(code, encoding="utf-8")
    print(f"📝 復元スクリプトを作成しました: {RESTORE_SCRIPT}")


def main():
    print("==================================================================")
    print("📦 スキル安全アーカイブ退避処理を開始します")
    print(f"📂 移動元: {SKILLS_DIR}")
    print(f"📁 移動先: {ARCHIVE_DIR}")
    print("==================================================================")

    if not SKILLS_DIR.exists():
        print(f"❌ スキルディレクトリが存在しません: {SKILLS_DIR}")
        return

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    moved = []
    skipped = []

    for name in PRUNED_SKILLS:
        if name in NEVER_ARCHIVE:
            print(f"🛡️ ガード発動: `{name}` は保護対象のため移動をスキップします。")
            continue

        src = SKILLS_DIR / name
        dst = ARCHIVE_DIR / name

        if not src.exists():
            skipped.append(name)
            continue

        if dst.exists():
            print(f"⚠️ 既にアーカイブ先に存在するため上書き回避: {name}")
            continue

        shutil.move(str(src), str(dst))
        moved.append(name)
        print(f"  📦 退避移動完了: {name}")

    print("\n------------------------------------------------------------------")
    print(f"🎉 アーカイブ退避完了！ 移動件数: {len(moved)} 件 / スキップ: {len(skipped)} 件")
    print(f"📁 退避先ディレクトリ: {ARCHIVE_DIR}")
    
    # 復元スクリプト生成
    if moved:
        generate_restore_script(moved)

    print("\n💡 いつでも元の状態に戻す場合は以下を実行してください:")
    print("   python tools/restore_skills.py")


if __name__ == "__main__":
    main()
