#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenCode 承認通知プラグイン v1.3.2 デプロイスクリプト (tools/deploy_opencode_plugin.py).

リポジトリ内の正本 (tools/opencode_plugins/hisho-approval-notify/index.ts) を
利用者の OpenCode プラグインディレクトリ (~/.config/opencode/plugins/hisho-approval-notify/index.ts) へコピーする。
"""

import shutil
import sys
from pathlib import Path


def deploy():
    repo_root = Path(__file__).resolve().parent.parent
    src = repo_root / "tools" / "opencode_plugins" / "hisho-approval-notify" / "index.ts"
    dest_dir = Path.home() / ".config" / "opencode" / "plugins" / "hisho-approval-notify"
    dest_file = dest_dir / "index.ts"

    if not src.exists():
        print(f"Error: Source file does not exist: {src}", file=sys.stderr)
        sys.exit(1)

    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest_file)
    print(f"✅ Successfully deployed hisho-approval-notify v1.3.2 to:\n   {dest_file}")


if __name__ == "__main__":
    deploy()
