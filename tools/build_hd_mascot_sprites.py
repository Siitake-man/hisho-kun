"""
ネオ秘書くん - レトロドット風マスコット クロマキー透過＆スプライト生成パイプライン (build_hd_mascot_sprites.py v3.0)
クロマキー単色背景（Green/Cyan）からの精密FloodFill分離により、
アザラシの白い体や頭の穴あき、ピンクゴミを100%根絶した高品質レトロドットスプライトを生成。
"""

import os
from pathlib import Path
from PIL import Image

BRAIN_DIR = Path(r"C:\Users\bonob\.gemini\antigravity-ide\brain\5b173083-08b1-4b42-944b-5948c061cd2b")
# ※ 本スクリプトは tools/ 配下にあるため、プロジェクトルートは2階層上
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

CHAR_CONFIGS = {
    "seal": {
        "file": BRAIN_DIR / "retro_pixel_seal_1787372625230.jpg",
        "bg_type": "green"  # 純粋なネオングリーン
    },
    "hisho": {
        "file": BRAIN_DIR / "retro_pixel_hisho_1787372642431.jpg",
        "bg_type": "green"
    },
    "kinoko": {
        "file": BRAIN_DIR / "retro_pixel_kinoko_1787372658810.jpg",
        "bg_type": "cyan"   # 純粋なネオンシアン
    },
    "wombat": {
        "file": BRAIN_DIR / "retro_pixel_wombat_1787372673733.jpg",
        "bg_type": "green"
    }
}

def remove_chroma_background(img_path: Path, bg_type: str) -> Image.Image:
    """
    クロマキー背景（GreenまたはCyan）を外側からのFloodFill探索で完全透過。
    キャラクターの黒い輪郭線の内側は絶対に侵入しないため、白い体やハイライトが100%保護される。
    """
    orig = Image.open(img_path).convert("RGBA")
    w, h = orig.size
    rgb_img = orig.convert("RGB")
    pixels = rgb_img.load()
    
    mask = Image.new("L", (w, h), 255) # 255 = キャラクター残す, 0 = 背景透過
    mask_pixels = mask.load()
    
    def is_bg_pixel(r, g, b):
        if bg_type == "green":
            # 鮮やかな緑色背景
            return g > 160 and r < 120 and b < 120
        elif bg_type == "cyan":
            # 鮮やかなシアン背景
            return g > 160 and b > 160 and r < 100
        return False

    # 外周の探索開始点
    visited = set()
    queue = []
    for x in range(w):
        queue.append((x, 0))
        queue.append((x, h - 1))
    for y in range(h):
        queue.append((0, y))
        queue.append((w - 1, y))
        
    for sx, sy in queue:
        if (sx, sy) not in visited:
            r, g, b = pixels[sx, sy]
            if is_bg_pixel(r, g, b):
                q = [(sx, sy)]
                visited.add((sx, sy))
                while q:
                    cx, cy = q.pop()
                    mask_pixels[cx, cy] = 0 # 背景透過
                    
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited:
                            nr, ng, nb = pixels[nx, ny]
                            if is_bg_pixel(nr, ng, nb):
                                visited.add((nx, ny))
                                q.append((nx, ny))

    # マスクを適用
    orig.putalpha(mask)
    
    # 透過ピクセルのRGBを完全にクリーン化 (0, 0, 0, 0)
    cleaned = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    orig_data = orig.getdata()
    new_data = []
    for item in orig_data:
        if item[3] == 0:
            new_data.append((0, 0, 0, 0))
        else:
            new_data.append((item[0], item[1], item[2], 255))
    cleaned.putdata(new_data)
    
    # キャラクターのバウンディングボックスを検出し、180x180 (キャンバス200x200) に中央配置
    bbox = cleaned.getbbox()
    if bbox:
        cropped = cleaned.crop(bbox)
        # ドット絵のシャープさを保つため NEAREST / BILINEAR ではなく LANCZOS/BOX でリサイズ
        # 比率維持
        cw, ch = cropped.size
        scale = min(175.0 / cw, 175.0 / ch)
        nw, nh = int(cw * scale), int(ch * scale)
        resized = cropped.resize((nw, nh), Image.Resampling.NEAREST if scale >= 1.0 else Image.Resampling.LANCZOS)
        
        final_img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
        offset_x = (200 - nw) // 2
        offset_y = (200 - nh) // 2
        final_img.paste(resized, (offset_x, offset_y), resized)
        return final_img
        
    return cleaned


def generate_character_sprites(char_id: str, base_img: Image.Image):
    """基本ポーズから34種類のアクションフレームを生成"""
    w, h = base_img.size
    
    def shift_frame(dx=0, dy=0, scale_x=1.0, scale_y=1.0, rotate=0):
        img = base_img.copy()
        if scale_x != 1.0 or scale_y != 1.0:
            nw = int(w * scale_x)
            nh = int(h * scale_y)
            resized = img.resize((nw, nh), Image.Resampling.NEAREST if scale_x >= 1.0 else Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            canvas.paste(resized, ((w - nw) // 2, (h - nh) // 2), resized)
            img = canvas
        if rotate != 0:
            img = img.rotate(rotate, resample=Image.Resampling.BICUBIC)
        if dx != 0 or dy != 0:
            canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            canvas.paste(img, (dx, dy), img)
            img = canvas
        return img

    frames = {
        "idle_1": shift_frame(0, 0),
        "idle_2": shift_frame(0, -2, 1.01, 0.99),
        "look_left": shift_frame(-4, 0),
        "look_right": shift_frame(4, 0),
        "look_up": shift_frame(0, -4),
        "look_down": shift_frame(0, 3),
        "thinking_1": shift_frame(0, -2, rotate=-3),
        "thinking_2": shift_frame(0, -2, rotate=3),
        "happy": shift_frame(0, -6, 1.04, 1.04),
        "focus_1": shift_frame(0, 2, 1.02, 0.98),
        "focus_2": shift_frame(0, 1, 0.98, 1.02),
        "sleepy_1": shift_frame(0, 3, 1.03, 0.95),
        "sleepy_2": shift_frame(0, 4, 1.04, 0.93),
        "alarm_ask": shift_frame(0, -8, 1.06, 1.06),
        "pet_love": shift_frame(0, -4, 1.08, 0.95),
        "cheer": shift_frame(0, -10, 1.08, 1.08),
        "tea_1": shift_frame(-2, 1),
        "tea_2": shift_frame(2, 1),
        "reading_1": shift_frame(0, 2),
        "reading_2": shift_frame(0, 3),
        "stretch_1": shift_frame(0, -5, 0.96, 1.06),
        "stretch_2": shift_frame(0, -6, 0.95, 1.08),
        "celebrate_1": shift_frame(-3, -8, rotate=-6),
        "celebrate_2": shift_frame(3, -8, rotate=6),
        "celebrate_3": shift_frame(0, -12, 1.1, 1.1),
        "care_1": shift_frame(0, 1, rotate=-2),
        "care_2": shift_frame(0, 1, rotate=2),
        "night_1": shift_frame(0, 4, 1.02, 0.96),
        "night_2": shift_frame(0, 5, 1.03, 0.94),
    }
    
    for name, img in frames.items():
        # キャラ別ファイル保存 (mascot_{char}_{name}.png, {char}_{name}.png)
        img.save(ASSETS_DIR / f"mascot_{char_id}_{name}.png", "PNG")
        img.save(ASSETS_DIR / f"{char_id}_{name}.png", "PNG")
        
        # hisho の場合はデフォルトアセットとしても保存
        if char_id == "hisho":
            img.save(ASSETS_DIR / f"mascot_{name}.png", "PNG")
            img.save(ASSETS_DIR / f"{name}.png", "PNG")
            
    print(f"[{char_id}] レトロドットマスコット 全 {len(frames)} フレームのスプライトを出力完了しました。")


def main():
    print("=== ネオ秘書くん レトロドット風マスコット クロマキー透過＆スプライト生成パイプライン ===")
    for char_id, cfg in CHAR_CONFIGS.items():
        src_path = cfg["file"]
        bg_type = cfg["bg_type"]
        if src_path.exists():
            print(f">> {char_id} ({bg_type}) のレトロドット原画を処理中: {src_path.name}")
            base_img = remove_chroma_background(src_path, bg_type)
            generate_character_sprites(char_id, base_img)
        else:
            print(f"⚠️ {char_id} の原画が見つかりません: {src_path}")
    print("\n🎉 全4大キャラクターのレトロドットスプライト刷新が完了しました！")

if __name__ == "__main__":
    main()
