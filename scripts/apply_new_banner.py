"""
生成された修正済みインフォグラフィック画像を docs/guides/assets/banner_main.jpg に適用するスクリプト
"""
import os
import shutil

SOURCE_IMAGE = r"C:\Users\bonob\.gemini\antigravity-ide\brain\cf4d92f6-830a-43cf-9ddc-af16e8524651\banner_pixel_pet_1789271158818.jpg"
TARGET_IMAGE = os.path.join("docs", "guides", "assets", "banner_main.jpg")
BACKUP_IMAGE = os.path.join("docs", "guides", "assets", "banner_main_original.jpg")

def apply_banner():
    if not os.path.exists(SOURCE_IMAGE):
        print(f"[ERROR] 元画像が見つかりません: {SOURCE_IMAGE}")
        return

    if os.path.exists(TARGET_IMAGE) and not os.path.exists(BACKUP_IMAGE):
        shutil.copy2(TARGET_IMAGE, BACKUP_IMAGE)
        print(f"[OK] 元バナーのバックアップを作成: {BACKUP_IMAGE}")

    shutil.copy2(SOURCE_IMAGE, TARGET_IMAGE)
    print(f"[SUCCESS] 新しいバナー画像を適用しました: {TARGET_IMAGE}")

if __name__ == "__main__":
    apply_banner()
