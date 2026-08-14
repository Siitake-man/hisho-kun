"""
レトロドット絵マスコット「秘書くん」スプライト生成スクリプト
assets/ フォルダに透過PNG形式で各状態のアニメーションフレームを出力します。
"""

import os
from pathlib import Path
from PIL import Image, ImageDraw

ASSETS_DIR = Path(__file__).parent / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

# カラーパレット（DESIGN_SPEC準拠）
COLOR_TRANSPARENT = (0, 0, 0, 0)
COLOR_OUTLINE = (74, 59, 50, 255)       # #4A3B32 (ダークブラウン)
COLOR_BODY = (166, 123, 91, 255)        # #A67B5B (ブラウン)
COLOR_BODY_LIGHT = (196, 154, 118, 255)  # #C49A76 (ライトブラウン)
COLOR_FACE = (245, 245, 220, 255)       # #F5F5DC (クリーム)
COLOR_CHEEK = (239, 154, 154, 255)      # #EF9A9A (ピンク)
COLOR_EYE = (74, 59, 50, 255)           # #4A3B32
COLOR_TIE = (230, 210, 53, 255)         # #E6D235 (イエロー)
COLOR_SPARKLE = (255, 235, 59, 255)     # #FFEB3B (ハイライト)
COLOR_GLASSES = (100, 181, 246, 255)    # #64B5F6 (メガネのレンズ光)

def draw_pixel_block(draw: ImageDraw.ImageDraw, x: int, y: int, color, scale: int = 4):
    """ピクセルをスケール倍して描画（ドット絵の解像感を保持）"""
    draw.rectangle(
        [x * scale, y * scale, (x + 1) * scale - 1, (y + 1) * scale - 1],
        fill=color
    )

def create_sprite(state: str) -> Image.Image:
    """指定された状態のドット絵スプライト（32x32グリッド ➔ 128x128px）を生成"""
    grid_size = 32
    scale = 4
    img = Image.new("RGBA", (grid_size * scale, grid_size * scale), COLOR_TRANSPARENT)
    draw = ImageDraw.Draw(img)

    # 1. 耳（リス/キツネ風の可愛い丸耳）
    for ex, ey in [(8, 5), (9, 4), (10, 5), (11, 6), (20, 6), (21, 5), (22, 4), (23, 5)]:
        draw_pixel_block(draw, ex, ey, COLOR_OUTLINE, scale)
    for ex, ey in [(9, 5), (10, 6), (21, 6), (22, 5)]:
        draw_pixel_block(draw, ex, ey, COLOR_CHEEK, scale)

    # 2. アンテナ / ひらめき電球
    if "thinking" in state:
        # 思考中: アンテナが光る
        draw_pixel_block(draw, 15, 3, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 16, 3, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 15, 2, COLOR_SPARKLE, scale)
        draw_pixel_block(draw, 16, 2, COLOR_SPARKLE, scale)
        draw_pixel_block(draw, 15, 1, COLOR_SPARKLE, scale)
        if state == "thinking_2":
            # 光のきらめき
            draw_pixel_block(draw, 13, 1, COLOR_SPARKLE, scale)
            draw_pixel_block(draw, 18, 1, COLOR_SPARKLE, scale)

    # 3. 頭・輪郭 (丸っこいボディ)
    for y in range(7, 24):
        for x in range(7, 25):
            # 輪郭の角丸チェック
            is_edge = (
                (y == 7 and (x in range(11, 21))) or
                (y == 23 and (x in range(10, 22))) or
                (x == 7 and (y in range(11, 20))) or
                (x == 24 and (y in range(11, 20))) or
                (y in (8, 9) and x in (9, 10, 21, 22)) or
                (y in (21, 22) and x in (8, 9, 22, 23))
            )
            is_inside = (8 <= x <= 23 and 8 <= y <= 22)
            
            if is_edge:
                draw_pixel_block(draw, x, y, COLOR_OUTLINE, scale)
            elif is_inside:
                draw_pixel_block(draw, x, y, COLOR_BODY, scale)

    # 4. お腹/顔の白い毛（クリーム色）
    for y in range(11, 21):
        for x in range(10, 22):
            if not ((y == 11 and x in (10, 21)) or (y == 20 and x in (10, 21))):
                draw_pixel_block(draw, x, y, COLOR_FACE, scale)

    # 5. 表情 (目・口・ほっぺ)
    if state == "idle_1":
        # ぱっちり目
        draw_pixel_block(draw, 12, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 12, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 19, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 19, 14, COLOR_EYE, scale)
        # 目のハイライト
        draw_pixel_block(draw, 12, 13, COLOR_FACE, scale)
        draw_pixel_block(draw, 19, 13, COLOR_FACE, scale)
        # 口
        draw_pixel_block(draw, 15, 16, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 16, 16, COLOR_OUTLINE, scale)
        
    elif state == "idle_2":
        # 瞬き（にっこり目 - -）
        draw_pixel_block(draw, 11, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 12, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 13, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 18, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 19, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 20, 14, COLOR_EYE, scale)
        # 口
        draw_pixel_block(draw, 15, 16, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 16, 16, COLOR_OUTLINE, scale)

    elif "thinking" in state:
        # 上を見つめる目 (o o)
        draw_pixel_block(draw, 12, 12, COLOR_EYE, scale)
        draw_pixel_block(draw, 13, 12, COLOR_EYE, scale)
        draw_pixel_block(draw, 18, 12, COLOR_EYE, scale)
        draw_pixel_block(draw, 19, 12, COLOR_EYE, scale)
        # 口（むすっと真一文字）
        draw_pixel_block(draw, 15, 16, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 16, 16, COLOR_OUTLINE, scale)

    elif state == "happy":
        # 満面の笑み (^ ^)
        draw_pixel_block(draw, 11, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 12, 12, COLOR_EYE, scale)
        draw_pixel_block(draw, 13, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 18, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 19, 12, COLOR_EYE, scale)
        draw_pixel_block(draw, 20, 13, COLOR_EYE, scale)
        # 大きな笑顔の口 (V)
        draw_pixel_block(draw, 14, 16, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 15, 17, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 16, 17, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 17, 16, COLOR_OUTLINE, scale)

    # ほっぺ（ピンク）
    draw_pixel_block(draw, 10, 15, COLOR_CHEEK, scale)
    draw_pixel_block(draw, 11, 15, COLOR_CHEEK, scale)
    draw_pixel_block(draw, 20, 15, COLOR_CHEEK, scale)
    draw_pixel_block(draw, 21, 15, COLOR_CHEEK, scale)

    # 6. ネクタイ（秘書スタイル）
    draw_pixel_block(draw, 15, 19, COLOR_TIE, scale)
    draw_pixel_block(draw, 16, 19, COLOR_TIE, scale)
    draw_pixel_block(draw, 15, 20, COLOR_TIE, scale)
    draw_pixel_block(draw, 16, 20, COLOR_TIE, scale)
    draw_pixel_block(draw, 15, 21, COLOR_TIE, scale)

    # 7. 手足（ちょこんとした手足）
    if state == "happy":
        # 手を振る
        draw_pixel_block(draw, 6, 13, COLOR_BODY_LIGHT, scale)
        draw_pixel_block(draw, 6, 14, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 25, 13, COLOR_BODY_LIGHT, scale)
        draw_pixel_block(draw, 25, 14, COLOR_OUTLINE, scale)
    else:
        draw_pixel_block(draw, 7, 17, COLOR_BODY_LIGHT, scale)
        draw_pixel_block(draw, 24, 17, COLOR_BODY_LIGHT, scale)

    # 足
    draw_pixel_block(draw, 11, 24, COLOR_OUTLINE, scale)
    draw_pixel_block(draw, 12, 24, COLOR_BODY_LIGHT, scale)
    draw_pixel_block(draw, 19, 24, COLOR_BODY_LIGHT, scale)
    draw_pixel_block(draw, 20, 24, COLOR_OUTLINE, scale)

    return img

def main():
    states = ["idle_1", "idle_2", "thinking_1", "thinking_2", "happy"]
    for s in states:
        img = create_sprite(s)
        out_path = ASSETS_DIR / f"{s}.png"
        img.save(out_path, format="PNG")
        print(f"Generated sprite: {out_path}")

if __name__ == "__main__":
    main()
