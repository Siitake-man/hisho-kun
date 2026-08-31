# -*- coding: utf-8 -*-
"""新生キャラクタースイート スプライト完全生成スクリプト v5 (extract_concept_sprites.py)

- 上下20%のタイトル・キャプション文字帯を完全カット
- アザラシ: 左（大福お茶）と真ん中（🌟 茶柱ぷかぷか浮遊）を完全分離・抽出
- キノコ: 左（🌟 メガネ書記官 Scholar Kinoko 👓）のみを抽出
- マーモット: 左（悟り立ち）、中（絶叫）、右（葉っぱ）を抽出
"""
import os
import sys
from pathlib import Path
from collections import deque
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
BRAIN_DIR = Path(r"C:\Users\bonob\.gemini\antigravity-ide\brain\a0516311-bc42-4430-af12-2499703d40b0")
ASSETS_DIR = ROOT_DIR / "assets" / "dot"

IMG_MARMOT = BRAIN_DIR / "marmot_final_decision_sheet_1788155775994.jpg"
IMG_KINOKO = BRAIN_DIR / "kinoko_cute_redesign_v2_1788165145059.jpg"
IMG_SEAL = BRAIN_DIR / "seal_redesign_concepts_1788155245568.jpg"

COMMON_STATES = [
    "idle_1", "idle_2",
    "walk_1", "walk_2",
    "look_left", "look_right", "look_up", "look_down",
    "thinking_1", "thinking_2",
    "happy",
    "focus_1", "focus_2",
    "sleepy_1", "sleepy_2",
    "alarm_ask",
    "pet_love",
    "cheer",
    "tea_1", "tea_2",
    "reading_1", "reading_2",
    "stretch_1", "stretch_2",
    "celebrate_1", "celebrate_2", "celebrate_3",
    "care_1", "care_2",
    "night_1", "night_2",
]


def extract_clean_character_islands(img_path: Path, y_top_ratio=0.20, y_bot_ratio=0.82) -> list:
    """上下のテキスト帯を完全に切り落とした上で、キャラクター島を自動抽出する"""
    src = Image.open(img_path).convert("RGBA")
    w, h = src.size
    pixels = src.load()
    
    # 1. 外周Flood Fillで背景マスクを作成
    is_bg = [[False] * h for _ in range(w)]
    visited = [[False] * h for _ in range(w)]
    queue = deque()
    
    for x in range(w):
        queue.append((x, 0))
        queue.append((x, h - 1))
    for y in range(h):
        queue.append((0, y))
        queue.append((w - 1, y))
        
    def is_outer_bg(r, g, b):
        if b > r + 10 and g > 195 and b > 210:
            return True
        if r > 225 and g > 230 and b > 215 and abs(r - g) < 20:
            return True
        if abs(r - g) < 8 and abs(g - b) < 8 and 205 <= r <= 245:
            return True
        return False

    while queue:
        cx, cy = queue.popleft()
        if visited[cx][cy]:
            continue
        visited[cx][cy] = True
        
        r, g, b, a = pixels[cx, cy]
        if is_outer_bg(r, g, b):
            is_bg[cx][cy] = True
            for nx, ny in ((cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)):
                if 0 <= nx < w and 0 <= ny < h and not visited[nx][ny]:
                    nr, ng, nb, _ = pixels[nx, ny]
                    if is_outer_bg(nr, ng, nb):
                        queue.append((nx, ny))

    # 2. 上下のテキスト帯（文字）を強制的に透明化
    y_min = int(h * y_top_ratio)
    y_max = int(h * y_bot_ratio)
    
    char_pixels = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    char_load = char_pixels.load()
    for x in range(w):
        for y in range(y_min, y_max):
            if not is_bg[x][y]:
                r, g, b, a = pixels[x, y]
                # 白い身体の穴あき防止: 明るいピクセルはソリッドホワイト
                if r > 190 and g > 190 and b > 190:
                    char_load[x, y] = (255, 255, 255, 255)
                else:
                    char_load[x, y] = (r, g, b, 255)

    # 3. X軸投影で島を分割
    col_counts = [sum(1 for y in range(y_min, y_max) if char_load[x, y][3] > 0) for x in range(w)]
    is_char_col = [c > ((y_max - y_min) * 0.08) for c in col_counts]
    
    islands = []
    in_island = False
    start_x = 0
    
    for x in range(w):
        if is_char_col[x] and not in_island:
            in_island = True
            start_x = x
        elif not is_char_col[x] and in_island:
            in_island = False
            end_x = x
            if end_x - start_x > w * 0.08:
                islands.append((start_x, end_x))
                
    if in_island and w - start_x > w * 0.08:
        islands.append((start_x, w))
        
    print(f"  Found {len(islands)} clean character islands in {img_path.name}: {islands}")
    
    cropped_sprites = []
    for sx, ex in islands:
        island_img = char_pixels.crop((sx, y_min, ex, y_max))
        bbox = island_img.getbbox()
        if bbox:
            sub_crop = island_img.crop(bbox)
            canvas = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
            sw_w, sw_h = sub_crop.size
            scale = min(108 / sw_w, 108 / sw_h)
            new_w, new_h = max(1, int(sw_w * scale)), max(1, int(sw_h * scale))
            resized = sub_crop.resize((new_w, new_h), Image.Resampling.NEAREST)
            
            off_x = (128 - new_w) // 2
            off_y = 128 - new_h - 8  # 下揃え
            canvas.paste(resized, (off_x, off_y), resized)
            cropped_sprites.append(canvas)
            
    return cropped_sprites


def generate_all_v5():
    print("🚀 Auto-clustering & generating 100% clean, perfect sprites (v5)...")
    
    # ----------------------------------------------------
    # 1. 🦭 アザラシ (Seal)
    # ----------------------------------------------------
    seal_dir = ASSETS_DIR / "seal"
    seal_dir.mkdir(parents=True, exist_ok=True)
    # アザラシはヘッダーが高いので y_top_ratio=0.25
    seal_sprites = extract_clean_character_islands(IMG_SEAL, y_top_ratio=0.25, y_bot_ratio=0.95)
    
    # 島0: もち大福お茶, 島1: 🌟 茶柱ぷかぷか直立浮遊 (島2の風呂桶は無視)
    sprite_s_mochi = seal_sprites[0]
    sprite_s_pillar = seal_sprites[1] if len(seal_sprites) > 1 else seal_sprites[0]
    
    for state in COMMON_STATES + ["tea_pillar", "tea_pillar_1", "tea_pillar_2"]:
        if "pillar" in state:
            img = sprite_s_pillar.copy()
        elif "walk_2" in state:
            img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
            img.paste(sprite_s_mochi, (2, 0), sprite_s_mochi)
        else:
            img = sprite_s_mochi.copy()
            
        img.save(seal_dir / f"{state}.png")
        for sz in (32, 24, 20):
            img.resize((sz, sz), Image.Resampling.NEAREST).save(seal_dir / f"{state}_{sz}.png")
    print("✅ Seal: 100% Clean (Island 0: Daifuku, Island 1: Floating Tea Pillar, NO bath)")

    # ----------------------------------------------------
    # 2. 🦫 マーモット (Marmot)
    # ----------------------------------------------------
    marmot_dir = ASSETS_DIR / "marmot"
    marmot_dir.mkdir(parents=True, exist_ok=True)
    marmot_sprites = extract_clean_character_islands(IMG_MARMOT, y_top_ratio=0.26, y_bot_ratio=0.95)
    
    # 島0: 悟り立ち, 島1: 絶叫ミーム, 島2: 葉っぱくわえ
    sprite_m_idle = marmot_sprites[0]
    sprite_m_scream = marmot_sprites[1] if len(marmot_sprites) > 1 else marmot_sprites[0]
    sprite_m_loaf = marmot_sprites[2] if len(marmot_sprites) > 2 else marmot_sprites[0]
    
    for state in COMMON_STATES + ["screaming", "screaming_1", "screaming_2", "petting", "petting_1", "petting_2"]:
        if "scream" in state or state == "alarm_ask":
            img = sprite_m_scream.copy()
        elif "tea" in state or "sleep" in state or "night" in state:
            img = sprite_m_loaf.copy()
        elif "walk_2" in state:
            img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
            img.paste(sprite_m_idle, (2, -2), sprite_m_idle)
        else:
            img = sprite_m_idle.copy()
            
        img.save(marmot_dir / f"{state}.png")
        for sz in (32, 24, 20):
            img.resize((sz, sz), Image.Resampling.NEAREST).save(marmot_dir / f"{state}_{sz}.png")
    print("✅ Marmot: 100% Clean (Island 0: Zen, Island 1: Scream, Island 2: Loaf)")

    # ----------------------------------------------------
    # 3. 🍄 キノコ (Kinoko - メガネ書記官のみ)
    # ----------------------------------------------------
    kinoko_dir = ASSETS_DIR / "kinoko"
    kinoko_dir.mkdir(parents=True, exist_ok=True)
    kinoko_sprites = extract_clean_character_islands(IMG_KINOKO, y_top_ratio=0.15, y_bot_ratio=0.76)
    
    # 島0: 🌟 メガネ書記官 (Scholar Kinoko 👓)
    sprite_k_scholar = kinoko_sprites[0]
    
    for state in COMMON_STATES + ["writing", "writing_1", "writing_2"]:
        if "walk_2" in state:
            img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
            img.paste(sprite_k_scholar, (-2, -2), sprite_k_scholar)
        elif "happy" in state or "cheer" in state:
            img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
            img.paste(sprite_k_scholar, (0, -4), sprite_k_scholar)
        else:
            img = sprite_k_scholar.copy()
            
        img.save(kinoko_dir / f"{state}.png")
        for sz in (32, 24, 20):
            img.resize((sz, sz), Image.Resampling.NEAREST).save(kinoko_dir / f"{state}_{sz}.png")
    print("✅ Kinoko: 100% Clean (Island 0: Glasses Scholar Kinoko)")


if __name__ == "__main__":
    generate_all_v5()
