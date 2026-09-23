#!/usr/bin/env python3
"""スキル一括復元スクリプト (restore_skills.py)

~/.gemini/config/skills_archive/ へ退避させたスキルを
直ちに ~/.gemini/config/skills/ へ戻します。
"""
import shutil
from pathlib import Path

HOME = Path.home()
SKILLS_DIR = HOME / ".gemini" / "config" / "skills"
ARCHIVE_DIR = HOME / ".gemini" / "config" / "skills_archive"

SKILLS_TO_RESTORE = ['bigquery-ai-ml', 'bigquery-bigframes', 'bigquery-data-transfer-service', 'bigquery-graph', 'bigquery-sql', 'bigtable-basics', 'building-data-apps', 'data-autocleaning', 'dataform-bigquery', 'dbt-bigquery', 'discovering-gcp-data-assets', 'federate-lakehouse-catalog', 'gcp-composer-troubleshooting', 'gcp-data-pipelines', 'gcp-dataflow', 'gcp-managed-airflow-dag-authoring', 'gcp-managed-airflow-migrations', 'gcp-managed-airflow-recommendations', 'gcp-pipeline-orchestration', 'gcp-pipeline-resource-provisioning', 'google-cloud-storage-basics', 'google-cloud-storage-bucket-architect', 'google-cloud-storage-fuse', 'schema-mapping', 'apple-design', 'appllama-design', 'baseline-ui', 'brand-guidelines', 'canvas-design', 'cinematic-web-experience', 'design-taste-frontend', 'emil-design-eng', 'hallmark', 'slack-gif-creator', 'theme-factory', 'visual-design-wallbash', 'web-artifacts-builder', 'web-design-guidelines']

def main():
    restored = 0
    for name in SKILLS_TO_RESTORE:
        src = ARCHIVE_DIR / name
        dst = SKILLS_DIR / name
        if src.exists():
            shutil.move(str(src), str(dst))
            print(f"  ↩️ 復元完了: {name}")
            restored += 1
    print(f"\n✅ 全 {restored} 件のスキルを元通り復元しました。")

if __name__ == "__main__":
    main()
