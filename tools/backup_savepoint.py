"""
ネオ秘書くん - セーブポイント完全バックアップ作成スクリプト (backup_savepoint.py)
"""
import os
import shutil
from datetime import datetime
from pathlib import Path

def create_savepoint():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # ※ 本スクリプトは tools/ 配下にあるため、プロジェクトルートは2階層上
    project_root = Path(__file__).resolve().parent.parent
    backup_dir = project_root / "backups" / f"savepoint_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    project_root = Path(__file__).resolve().parent.parent
    
    # 対象ファイル・ディレクトリ（2026-08-25 現在の実在ファイルに同期）
    items_to_backup = [
        "gui.py", "main.py", "database.py", "agent.py", "pet_animator.py",
        "character_manager.py", "google_workspace_tools.py", "hisho_mcp_server.py",
        "llm_factory.py", "local_sync_server.py", "mcp_installer.py", "mcp_manager.py",
        "suggest_engine.py", "proactive_engine.py", "task_narrator.py", "agent_watcher.py",
        "db_tools.py", "ics_tools.py", "vision_tools.py", "agent_bridge_client.py",
        "ui", "web_pet", "character_config.json", "discovered_models.json"
    ]
    
    copied = []
    for item in items_to_backup:
        src = project_root / item
        dst = backup_dir / item
        if src.is_file():
            shutil.copy2(src, dst)
            copied.append(item)
        elif src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
            copied.append(f"{item}/")
            
    print(f"✓ セーブポイントを完全作成しました: {backup_dir}")
    print(f"  退避ファイル数: {len(copied)} 件")
    return backup_dir

if __name__ == "__main__":
    create_savepoint()
