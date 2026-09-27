"""
生成された修正済みインフォグラフィック画像を docs/guides/assets/banner_main.jpg に適用するスクリプト
"""
import os
import shutil
import sys

# 元画像はコマンドライン引数または環境変数 HISHO_BANNER_SOURCE で指定する（個人パスは埋め込まない）
#   例: python scripts/apply_new_banner.py path/to/banner.jpg
SOURCE_IMAGE = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("HISHO_BANNER_SOURCE", "")
TARGET_IMAGE = os.path.join("docs", "guides", "assets", "banner_main.jpg")
BACKUP_IMAGE = os.path.join("docs", "guides", "assets", "banner_main_original.jpg")

def apply_banner():
    if not SOURCE_IMAGE or not os.path.exists(SOURCE_IMAGE):
        print(f"[ERROR] 元画像が見つかりません: {SOURCE_IMAGE or '(未指定)'}")
        print("使い方: python scripts/apply_new_banner.py <元画像パス>  (または環境変数 HISHO_BANNER_SOURCE)")
        return

    if os.path.exists(TARGET_IMAGE) and not os.path.exists(BACKUP_IMAGE):
        shutil.copy2(TARGET_IMAGE, BACKUP_IMAGE)
        print(f"[OK] 元バナーのバックアップを作成: {BACKUP_IMAGE}")

    shutil.copy2(SOURCE_IMAGE, TARGET_IMAGE)
    print(f"[SUCCESS] 新しいバナー画像を適用しました: {TARGET_IMAGE}")

if __name__ == "__main__":
    apply_banner()
