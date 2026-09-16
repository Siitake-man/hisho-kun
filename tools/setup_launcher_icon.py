"""
ネオ秘書くん - 起動アイコン ＆ ショートカット自動生成ツール (tools/setup_launcher_icon.py)

1. assets/dot/hisho/idle_1.png から高解像度マルチサイズ（16x16〜256x256）の icon.ico を生成
2. アップロードされた桜飾り付き秘書くん画像から背景を自動透過した icon_sakura.ico を生成
3. プロジェクト直下に「ネオ秘書くん起動.lnk」（かわいい秘書くんアイコン）を作成
4. デスクトップにも同時にショートカットを作成（オプション）
"""

import os
import sys
from pathlib import Path

# プロジェクトルート
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
SRC_PNG = ASSETS_DIR / "dot" / "hisho" / "idle_1.png"
OUTPUT_ICO = ASSETS_DIR / "icon.ico"
OUTPUT_SAKURA_ICO = ASSETS_DIR / "icon_sakura.ico"
SHORTCUT_PATH = PROJECT_ROOT / "ネオ秘書くん起動.lnk"
BAT_PATH = PROJECT_ROOT / "Start.bat"

# アップロードされた桜秘書くん画像の候補パス
UPLOADED_IMG_PATHS = [
    ASSETS_DIR / "dot" / "hisho" / "idle_sakura_raw.png",
    Path(r"C:\Users\bonob\.gemini\antigravity\brain\0457ada4-59fa-43e1-be3c-58842c3b2596\.user_uploaded\media_1789393893659.png")
]


def make_multisize_ico(pil_img, ico_path: Path):
    from PIL import Image
    
    # ドット絵の鮮明さを保つため NEAREST でマルチサイズ生成
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icons = []
    for s in sizes:
        resized = pil_img.resize(s, resample=Image.Resampling.NEAREST)
        icons.append(resized)
    
    # 最初の画像をベースにマルチサイズICOとして保存
    icons[-1].save(ico_path, format="ICO", sizes=sizes)
    print(f"  [OK] アイコン生成: {ico_path.name} ({len(sizes)} resolutions)")

def process_sakura_image(src_img_path: Path):
    from PIL import Image
    
    img = Image.open(src_img_path).convert("RGBA")
    width, height = img.size
    
    # 背景の暗色（黒・ダークグレー）を透過処理
    # 文字列が上部にある場合は上部5%と周囲の暗色をクレンジング
    pixels = img.load()
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            # 背景色判定（暗いグレー、黒）
            if r < 45 and g < 45 and b < 45:
                pixels[x, y] = (0, 0, 0, 0)
            # 上部の文字ノイズ除去（白っぽい文字で y < 20 のエリア）
            elif y < 22 and (r > 60 and g > 60 and b > 60 and r < 140 and b < 140 and g < 140):
                pixels[x, y] = (0, 0, 0, 0)
                
    # クロップ処理（透明領域を除去してキャラを中央配置）
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
        # 正方形の透過キャンバスに中央配置
        max_dim = max(img.width, img.height) + 8
        square_img = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))
        offset_x = (max_dim - img.width) // 2
        offset_y = (max_dim - img.height) // 2
        square_img.paste(img, (offset_x, offset_y), img)
        return square_img
    return img

def create_windows_shortcut(target_bat: Path, shortcut_lnk: Path, ico_file: Path):
    import subprocess
    
    ps_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_lnk}")
$Shortcut.TargetPath = "{target_bat}"
$Shortcut.WorkingDirectory = "{target_bat.parent}"
$Shortcut.IconLocation = "{ico_file}, 0"
$Shortcut.Description = "ネオ秘書くんを起動します"
$Shortcut.Save()
"""
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"  [OK] ショートカット作成: {shortcut_lnk.name}")
    else:
        print(f"  [WARN] ショートカット作成失敗: {res.stderr}")

def main():
    print("🐾 === ネオ秘書くん 起動アイコン ＆ ショートカット生成ツール ===")
    
    try:
        from PIL import Image
    except ImportError:
        print("[INFO] Pillow をインストール中...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "Pillow"], check=True)
        from PIL import Image

    # 1. 標準アイコンの生成
    if SRC_PNG.exists():
        print("1. 標準秘書くんアイコン (icon.ico) を生成中...")
        std_img = Image.open(SRC_PNG).convert("RGBA")
        make_multisize_ico(std_img, OUTPUT_ICO)
    
    # 2. 桜秘書くんアイコンの生成
    selected_ico = OUTPUT_ICO
    for p in UPLOADED_IMG_PATHS:
        if p.exists():
            print(f"2. 桜飾り秘書くんアイコン (icon_sakura.ico) を生成中... ({p.name})")
            sakura_img = process_sakura_image(p)
            make_multisize_ico(sakura_img, OUTPUT_SAKURA_ICO)
            selected_ico = OUTPUT_SAKURA_ICO
            break

    # 3. プロジェクト直下にショートカット作成
    print(f"3. 起動ショートカットを作成中 (アイコン: {selected_ico.name})...")
    create_windows_shortcut(BAT_PATH, SHORTCUT_PATH, selected_ico)

    # 4. デスクトップにも作成
    desktop_dir = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
    if desktop_dir.exists():
        desktop_shortcut = desktop_dir / "ネオ秘書くん.lnk"
        create_windows_shortcut(BAT_PATH, desktop_shortcut, selected_ico)
        print(f"  [OK] デスクトップにもショートカットを配置しました: {desktop_shortcut}")

    print("\n🎉 すべての準備が整いました！")
    print(f"👉 プロジェクト直下の「ネオ秘書くん起動.lnk」またはデスクトップの「ネオ秘書くん.lnk」から、")
    print("   かわいい秘書くんアイコンでいつでも起動できます！")

if __name__ == "__main__":
    main()
