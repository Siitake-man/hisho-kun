"""
ネオ秘書くん - コンセプト画像（横1列4キャラ）から16bitドット絵スプライト一式を完全抽出・透過・モーション生成
"""

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance

PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_ROOT / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

CONCEPT_IMAGE_PATH = Path(r"C:\Users\bonob\.gemini\antigravity-ide\brain\2ad1ac55-8ff6-41f4-9d01-68413a5890b7\mascot_concept_hisho3hair_1786869669082.jpg")

def remove_background(img: Image.Image, tolerance: int = 30) -> Image.Image:
    """背景の白/オフホワイトを透過処理（足元の影も自然に処理）"""
    img = img.convert("RGBA")
    data = list(img.getdata())
    new_data = []
    for item in data:
        r, g, b, a = item
        # 純白・明るいグレー背景を透過
        if r > 255 - tolerance and g > 255 - tolerance and b > 255 - tolerance:
            new_data.append((255, 255, 255, 0))
        elif r > 235 and g > 235 and b > 235:
            # 輪郭のアンチエイリアス境界
            avg = (r + g + b) / 3
            alpha = int(255 * (1.0 - (avg - 235) / 20.0))
            new_data.append((r, g, b, max(0, min(255, alpha))))
        elif 160 < r < 210 and 160 < g < 210 and 170 < b < 225:
            # 足元の薄紫/グレー影を半透明化
            new_data.append((r, g, b, 70))
        else:
            new_data.append(item)
    img.putdata(new_data)
    return img

def crop_and_clean(concept_img: Image.Image, box: tuple, target_size: tuple = (144, 144)) -> Image.Image:
    """指定領域を切り抜き、透過処理してリサイズ"""
    cropped = concept_img.crop(box)
    cleaned = remove_background(cropped, tolerance=30)
    
    # バウンディングボックスで余白をトリミング
    bbox = cleaned.getbbox()
    if bbox:
        cleaned = cleaned.crop(bbox)
        
    w, h = cleaned.size
    # ターゲットサイズに収まるようスケール
    scale = min((target_size[0] - 20) / w, (target_size[1] - 20) / h)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cleaned.resize((new_w, new_h), Image.Resampling.NEAREST)
    
    canvas = Image.new("RGBA", target_size, (0, 0, 0, 0))
    offset_x = (target_size[0] - new_w) // 2
    offset_y = target_size[1] - new_h - 10  # 地面に接地
    canvas.paste(resized, (offset_x, offset_y), resized)
    return canvas

def shift_image(img: Image.Image, dx: int, dy: int) -> Image.Image:
    """画像をオフセットシフト"""
    w, h = img.size
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.paste(img, (dx, dy), img)
    return canvas

def generate_all_sprite_frames(base_img: Image.Image, char_id: str):
    """pet.js および gui.py が要求する全フレーム名を完全に網羅して生成・保存"""
    w, h = base_img.size
    
    # 1. idle_1 / idle_2 (通常待機＆微細呼吸アニメ)
    idle_1 = base_img.copy()
    idle_2 = shift_image(base_img, 0, 2)
    
    # 2. look_left / look_right / look_up / look_down (視線・見回し)
    look_left = shift_image(base_img, -3, 0)
    look_right = shift_image(base_img, 3, 0)
    look_up = shift_image(base_img, 0, -3)
    look_down = shift_image(base_img, 0, 3)
    
    # 3. focus_1 / focus_2 (集中・赤ハチマキ)
    focus_1 = base_img.copy()
    draw_f1 = ImageDraw.Draw(focus_1)
    # 頭部に赤い集中ハチマキ
    draw_f1.rectangle([w//2 - 28, 22, w//2 + 28, 30], fill=(235, 55, 55, 255))
    draw_f1.rectangle([w//2 - 26, 24, w//2 + 26, 28], fill=(255, 90, 90, 255))
    draw_f1.polygon([(w//2 + 28, 22), (w//2 + 42, 16), (w//2 + 38, 28)], fill=(235, 55, 55, 255))
    draw_f1.polygon([(w//2 + 28, 28), (w//2 + 40, 36), (w//2 + 36, 42)], fill=(235, 55, 55, 255))
    focus_2 = shift_image(focus_1, 0, 1)

    # 4. cheer / happy (応援・大喜び)
    cheer = shift_image(base_img, 0, -6)
    draw_ch = ImageDraw.Draw(cheer)
    for sx, sy in [(20, 25), (w - 25, 30), (w//2 + 32, 18)]:
        draw_ch.polygon([(sx, sy-5), (sx+2, sy-2), (sx+5, sy), (sx+2, sy+2), (sx, sy+5), (sx-2, sy+2), (sx-5, sy), (sx-2, sy-2)], fill=(255, 215, 0, 255))
    
    happy = base_img.copy()
    draw_hp = ImageDraw.Draw(happy)
    draw_hp.polygon([(w - 28, 18), (w - 20, 10), (w - 12, 18), (w - 20, 26)], fill=(255, 90, 130, 255))

    # 5. celebrate_1 / celebrate_2 / celebrate_3 (ジャンプ・紙吹雪)
    celebrate_1 = shift_image(base_img, 0, -4)
    celebrate_2 = shift_image(base_img, 0, -9)
    celebrate_3 = shift_image(base_img, 0, -4)
    for c_img in [celebrate_1, celebrate_2, celebrate_3]:
        draw_c = ImageDraw.Draw(c_img)
        confetti = [
            ((22, 18), (255, 80, 80, 255)),
            ((w - 22, 22), (80, 160, 255, 255)),
            ((35, 10), (255, 220, 0, 255)),
            ((w - 38, 12), (100, 220, 100, 255)),
            ((w//2, 8), (255, 120, 220, 255))
        ]
        for (cx, cy), col in confetti:
            draw_c.rectangle([cx-2, cy-2, cx+2, cy+2], fill=col)

    # 6. alarm_ask (承認・質問要請: 黄色ビックリマーク)
    alarm_ask = base_img.copy()
    draw_al = ImageDraw.Draw(alarm_ask)
    ex_x, ex_y = w - 26, 18
    draw_al.rectangle([ex_x - 4, ex_y - 12, ex_x + 4, ex_y + 4], fill=(255, 140, 0, 255))
    draw_al.rectangle([ex_x - 2, ex_y - 10, ex_x + 2, ex_y + 2], fill=(255, 235, 59, 255))
    draw_al.rectangle([ex_x - 4, ex_y + 8, ex_x + 4, ex_y + 14], fill=(255, 140, 0, 255))
    draw_al.rectangle([ex_x - 2, ex_y + 10, ex_x + 2, ex_y + 12], fill=(255, 235, 59, 255))

    # 7. pet_love (なでなで: ダブルハート)
    pet_love = shift_image(base_img, 0, -2)
    draw_pl = ImageDraw.Draw(pet_love)
    draw_pl.polygon([(w - 28, 16), (w - 22, 10), (w - 16, 16), (w - 22, 22)], fill=(255, 80, 120, 255))
    draw_pl.polygon([(20, 20), (26, 14), (32, 20), (26, 26)], fill=(255, 120, 160, 255))

    # 8. sleepy_1 / sleepy_2 / night_1 / night_2 (おやすみ)
    sleepy_1 = shift_image(base_img, 0, 2)
    draw_sl1 = ImageDraw.Draw(sleepy_1)
    draw_sl1.text((w - 32, 10), "Z", fill=(100, 180, 245, 255))
    draw_sl1.text((w - 20, 4), "z", fill=(120, 200, 255, 255))
    
    sleepy_2 = shift_image(base_img, 0, 3)
    draw_sl2 = ImageDraw.Draw(sleepy_2)
    draw_sl2.text((w - 32, 10), "Z", fill=(100, 180, 245, 255))
    draw_sl2.text((w - 20, 4), "z", fill=(120, 200, 255, 255))
    draw_sl2.text((w - 10, 0), "z", fill=(150, 220, 255, 255))

    night_1 = sleepy_1.copy()
    night_2 = sleepy_2.copy()

    # 9. thinking_1 / thinking_2 (考え中)
    thinking_1 = base_img.copy()
    draw_th1 = ImageDraw.Draw(thinking_1)
    draw_th1.text((w - 28, 8), "？", fill=(140, 100, 220, 255))
    
    thinking_2 = shift_image(base_img, 0, 1)
    draw_th2 = ImageDraw.Draw(thinking_2)
    draw_th2.text((w - 28, 8), "？", fill=(140, 100, 220, 255))

    # 10. care_1 / care_2 (気遣い・お茶)
    care_1 = base_img.copy()
    care_2 = shift_image(base_img, 0, 1)

    # 11. tea_1 / tea_2 / reading_1 / reading_2 / stretch_1 / stretch_2
    tea_1 = base_img.copy()
    tea_2 = shift_image(base_img, 0, 1)
    reading_1 = base_img.copy()
    reading_2 = shift_image(base_img, 0, 1)
    stretch_1 = shift_image(base_img, 0, -2)
    stretch_2 = shift_image(base_img, 0, 2)

    # 辞書マッピング
    frames = {
        'idle_1': idle_1,
        'idle_2': idle_2,
        'look_left': look_left,
        'look_right': look_right,
        'look_up': look_up,
        'look_down': look_down,
        'focus_1': focus_1,
        'focus_2': focus_2,
        'cheer': cheer,
        'happy': happy,
        'celebrate_1': celebrate_1,
        'celebrate_2': celebrate_2,
        'celebrate_3': celebrate_3,
        'alarm_ask': alarm_ask,
        'pet_love': pet_love,
        'sleepy_1': sleepy_1,
        'sleepy_2': sleepy_2,
        'night_1': night_1,
        'night_2': night_2,
        'thinking_1': thinking_1,
        'thinking_2': thinking_2,
        'care_1': care_1,
        'care_2': care_2,
        'tea_1': tea_1,
        'tea_2': tea_2,
        'reading_1': reading_1,
        'reading_2': reading_2,
        'stretch_1': stretch_1,
        'stretch_2': stretch_2
    }

    # 保存処理
    for fname, fimg in frames.items():
        # 1. スマホ用キャラ固有名: {char_id}_{fname}.png
        fimg.save(ASSETS_DIR / f"{char_id}_{fname}.png")
        # 2. PC用キャラ固有名: mascot_{char_id}_{fname}.png
        fimg.save(ASSETS_DIR / f"mascot_{char_id}_{fname}.png")
        
        # デフォルト(hisho)の場合はフォールバック用プレフィックス無しも上書き
        if char_id == "hisho":
            fimg.save(ASSETS_DIR / f"{fname}.png")
            fimg.save(ASSETS_DIR / f"mascot_{fname}.png")

def main():
    if not CONCEPT_IMAGE_PATH.exists():
        print(f"❌ コンセプト画像が見つかりません: {CONCEPT_IMAGE_PATH}")
        return

    concept = Image.open(CONCEPT_IMAGE_PATH)
    width, height = concept.size
    print(f"🖼️ コンセプト画像をロードしました ({width}x{height})")

    # 4キャラクターの正確なバウンディングボックス定義 (横1列 1x4 レイアウト)
    # 1. hisho: 左端 (3本毛・ベストネクタイ秘書くん)
    # 2. kinoko: 2番目 (赤水玉キノコ君)
    # 3. seal: 3番目 (大福アザラシ)
    # 4. wombat: 右端 (茶色ウォンバット)
    characters = {
        "hisho": (15, 300, 275, 680),
        "kinoko": (265, 340, 520, 680),
        "seal": (505, 420, 765, 680),
        "wombat": (750, 360, 995, 680)
    }

    for char_id, box in characters.items():
        print(f"🎨 キャラクター抽出・全フレーム生成中: {char_id} (領域: {box})...")
        base = crop_and_clean(concept, box, target_size=(144, 144))
        generate_all_sprite_frames(base, char_id)

    print("✨ 全4キャラクター・全モーションフレームの抽出・生成が完全完了しました！")

if __name__ == "__main__":
    main()
