"""
レトロドット絵マスコット「秘書くん」スプライト生成スクリプト (Pixel Art 2.0)
assets/ フォルダに透過PNG形式で各状態のアニメーションフレームを出力します。

状態一覧 (8大感情 & 視線追従):
- idle_1, idle_2: 待機 (正面ぱっちり目 / 瞬き)
- look_left, look_right, look_up, look_down: 視線追従 (マウス追従パーツ)
- thinking_1, thinking_2: 思考中 (アンテナ点滅 & きらめき)
- happy: 歓喜・大喜び (満面の笑み & 両手振り)
- focus_1, focus_2: 集中ポモドーロ (赤ハチマキ & カタカタ作業)
- sleepy_1, sleepy_2: 居眠り・リラックス (うとうと & Zzz吹き出し)
- alarm_ask: 承認要請アラート (びっくり目 & 片手挙手 & 注目マーク)
- pet_love: なでなで触感リアクション (うっとり目 & ハートマーク)
- cheer: 応援 (ガッツポーズ & きらめき)
"""

import os
from pathlib import Path
from PIL import Image, ImageDraw

ASSETS_DIR = Path(__file__).parent / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

# カラーパレット（DESIGN_SPEC準拠 & Pixel Art 2.0）
COLOR_TRANSPARENT = (0, 0, 0, 0)
COLOR_OUTLINE = (74, 59, 50, 255)         # #4A3B32 (ダークブラウン)
COLOR_BODY = (166, 123, 91, 255)          # #A67B5B (ブラウン)
COLOR_BODY_LIGHT = (196, 154, 118, 255)    # #C49A76 (ライトブラウン)
COLOR_FACE = (245, 245, 220, 255)         # #F5F5DC (クリーム)
COLOR_CHEEK = (239, 154, 154, 255)        # #EF9A9A (ピンク)
COLOR_EYE = (74, 59, 50, 255)             # #4A3B32
COLOR_TIE = (230, 210, 53, 255)           # #E6D235 (イエロー)
COLOR_SPARKLE = (255, 235, 59, 255)       # #FFEB3B (ハイライト)
COLOR_HEADBAND = (229, 57, 53, 255)       # #E53935 (集中赤ハチマキ)
COLOR_HEART = (233, 30, 99, 255)          # #E91E63 (ハートピンク)
COLOR_ZZZ = (144, 202, 249, 255)          # #90CAF9 (睡眠ブルー)
COLOR_ALERT = (255, 112, 67, 255)         # #FF7043 (アラートオレンジ)

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

    # -------------------------------------------------------------
    # 1. 耳（リス/キツネ風の可愛い丸耳）
    # -------------------------------------------------------------
    for ex, ey in [(8, 5), (9, 4), (10, 5), (11, 6), (20, 6), (21, 5), (22, 4), (23, 5)]:
        draw_pixel_block(draw, ex, ey, COLOR_OUTLINE, scale)
    for ex, ey in [(9, 5), (10, 6), (21, 6), (22, 5)]:
        draw_pixel_block(draw, ex, ey, COLOR_CHEEK, scale)

    # -------------------------------------------------------------
    # 2. アンテナ / ひらめき電球 / エフェクト
    # -------------------------------------------------------------
    if "thinking" in state:
        # 思考中: アンテナが光る
        draw_pixel_block(draw, 15, 3, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 16, 3, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 15, 2, COLOR_SPARKLE, scale)
        draw_pixel_block(draw, 16, 2, COLOR_SPARKLE, scale)
        draw_pixel_block(draw, 15, 1, COLOR_SPARKLE, scale)
        if state == "thinking_2":
            draw_pixel_block(draw, 13, 1, COLOR_SPARKLE, scale)
            draw_pixel_block(draw, 18, 1, COLOR_SPARKLE, scale)

    elif state == "alarm_ask":
        # 承認要請アラート: 頭上にびっくりマーク「！」
        draw_pixel_block(draw, 15, 1, COLOR_ALERT, scale)
        draw_pixel_block(draw, 16, 1, COLOR_ALERT, scale)
        draw_pixel_block(draw, 15, 2, COLOR_ALERT, scale)
        draw_pixel_block(draw, 16, 2, COLOR_ALERT, scale)
        draw_pixel_block(draw, 15, 4, COLOR_ALERT, scale)
        draw_pixel_block(draw, 16, 4, COLOR_ALERT, scale)

    elif state == "pet_love":
        # なでなで: 頭上にピンクのハートマーク💖
        for hx, hy in [(14, 1), (15, 2), (16, 2), (17, 1), (13, 2), (18, 2), (14, 3), (15, 4), (16, 4), (17, 3), (15, 5), (16, 5)]:
            draw_pixel_block(draw, hx, hy, COLOR_HEART, scale)

    elif "sleepy" in state:
        # 居眠り: Zzz…
        draw_pixel_block(draw, 22, 2, COLOR_ZZZ, scale)
        draw_pixel_block(draw, 23, 2, COLOR_ZZZ, scale)
        draw_pixel_block(draw, 22, 3, COLOR_ZZZ, scale)
        draw_pixel_block(draw, 21, 4, COLOR_ZZZ, scale)
        draw_pixel_block(draw, 21, 5, COLOR_ZZZ, scale)
        draw_pixel_block(draw, 22, 5, COLOR_ZZZ, scale)
        if state == "sleepy_2":
            draw_pixel_block(draw, 25, 0, COLOR_ZZZ, scale)
            draw_pixel_block(draw, 26, 0, COLOR_ZZZ, scale)
            draw_pixel_block(draw, 25, 1, COLOR_ZZZ, scale)
            draw_pixel_block(draw, 24, 2, COLOR_ZZZ, scale)

    # -------------------------------------------------------------
    # 3. 頭・輪郭 (丸っこいボディ)
    # -------------------------------------------------------------
    for y in range(7, 24):
        for x in range(7, 25):
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

    # -------------------------------------------------------------
    # 4. 集中ハチマキ (focus 状態)
    # -------------------------------------------------------------
    if "focus" in state:
        for x in range(9, 23):
            draw_pixel_block(draw, x, 8, COLOR_HEADBAND, scale)
            draw_pixel_block(draw, x, 9, COLOR_HEADBAND, scale)
        # ハチマキの結び目 (右耳の下)
        draw_pixel_block(draw, 23, 7, COLOR_HEADBAND, scale)
        draw_pixel_block(draw, 24, 8, COLOR_HEADBAND, scale)
        draw_pixel_block(draw, 24, 9, COLOR_HEADBAND, scale)
        draw_pixel_block(draw, 25, 10, COLOR_HEADBAND, scale)

    # -------------------------------------------------------------
    # 5. お腹/顔の白い毛（クリーム色）
    # -------------------------------------------------------------
    for y in range(11, 21):
        for x in range(10, 22):
            if not ((y == 11 and x in (10, 21)) or (y == 20 and x in (10, 21))):
                draw_pixel_block(draw, x, y, COLOR_FACE, scale)

    # -------------------------------------------------------------
    # 6. 表情 (目・口・ほっぺ・視線パーツ)
    # -------------------------------------------------------------
    if state == "idle_1":
        # ぱっちり正面目
        draw_pixel_block(draw, 12, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 12, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 19, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 19, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 12, 13, COLOR_FACE, scale)
        draw_pixel_block(draw, 19, 13, COLOR_FACE, scale)
        draw_pixel_block(draw, 15, 16, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 16, 16, COLOR_OUTLINE, scale)

    elif state == "idle_2":
        # 瞬き（にっこり線目 - -）
        for x in [11, 12, 13, 18, 19, 20]:
            draw_pixel_block(draw, x, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 15, 16, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 16, 16, COLOR_OUTLINE, scale)

    elif state == "look_left":
        # 視線左向き (マウス追従)
        draw_pixel_block(draw, 11, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 11, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 18, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 18, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 15, 16, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 16, 16, COLOR_OUTLINE, scale)

    elif state == "look_right":
        # 視線右向き (マウス追従)
        draw_pixel_block(draw, 13, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 13, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 20, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 20, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 15, 16, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 16, 16, COLOR_OUTLINE, scale)

    elif state == "look_up":
        # 視線上向き (マウス追従)
        draw_pixel_block(draw, 12, 12, COLOR_EYE, scale)
        draw_pixel_block(draw, 12, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 19, 12, COLOR_EYE, scale)
        draw_pixel_block(draw, 19, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 15, 16, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 16, 16, COLOR_OUTLINE, scale)

    elif state == "look_down":
        # 視線下向き (マウス追従)
        draw_pixel_block(draw, 12, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 12, 15, COLOR_EYE, scale)
        draw_pixel_block(draw, 19, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 19, 15, COLOR_EYE, scale)
        draw_pixel_block(draw, 15, 16, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 16, 16, COLOR_OUTLINE, scale)

    elif "thinking" in state:
        # 上を見つめる目 (o o)
        draw_pixel_block(draw, 12, 12, COLOR_EYE, scale)
        draw_pixel_block(draw, 13, 12, COLOR_EYE, scale)
        draw_pixel_block(draw, 18, 12, COLOR_EYE, scale)
        draw_pixel_block(draw, 19, 12, COLOR_EYE, scale)
        draw_pixel_block(draw, 15, 16, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 16, 16, COLOR_OUTLINE, scale)

    elif state in ("happy", "cheer"):
        # 満面の笑み (^ ^)
        draw_pixel_block(draw, 11, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 12, 12, COLOR_EYE, scale)
        draw_pixel_block(draw, 13, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 18, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 19, 12, COLOR_EYE, scale)
        draw_pixel_block(draw, 20, 13, COLOR_EYE, scale)
        # 大きな笑顔の口
        draw_pixel_block(draw, 14, 16, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 15, 17, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 16, 17, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 17, 16, COLOR_OUTLINE, scale)

    elif state == "pet_love":
        # なでなでうっとり目 (> <)
        draw_pixel_block(draw, 11, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 12, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 13, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 18, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 19, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 20, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 15, 16, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 16, 16, COLOR_OUTLINE, scale)

    elif "focus" in state:
        # 真剣な目つき (キリッ)
        draw_pixel_block(draw, 11, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 12, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 13, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 18, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 19, 13, COLOR_EYE, scale)
        draw_pixel_block(draw, 20, 13, COLOR_EYE, scale)
        # 引き締まった口元
        draw_pixel_block(draw, 15, 16, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 16, 16, COLOR_OUTLINE, scale)

    elif "sleepy" in state:
        # 居眠り目 (u u)
        draw_pixel_block(draw, 11, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 12, 15, COLOR_EYE, scale)
        draw_pixel_block(draw, 13, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 18, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 19, 15, COLOR_EYE, scale)
        draw_pixel_block(draw, 20, 14, COLOR_EYE, scale)
        draw_pixel_block(draw, 15, 17, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 16, 17, COLOR_OUTLINE, scale)

    elif state == "alarm_ask":
        # びっくり丸目 (O O)
        for ex, ey in [(11, 13), (12, 12), (13, 13), (12, 14), (18, 13), (19, 12), (20, 13), (19, 14)]:
            draw_pixel_block(draw, ex, ey, COLOR_EYE, scale)
        # まぁるい口 (o)
        draw_pixel_block(draw, 15, 16, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 16, 16, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 15, 17, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 16, 17, COLOR_OUTLINE, scale)

    # ほっぺ（ピンク）
    draw_pixel_block(draw, 10, 15, COLOR_CHEEK, scale)
    draw_pixel_block(draw, 11, 15, COLOR_CHEEK, scale)
    draw_pixel_block(draw, 20, 15, COLOR_CHEEK, scale)
    draw_pixel_block(draw, 21, 15, COLOR_CHEEK, scale)

    # -------------------------------------------------------------
    # 7. ネクタイ（秘書スタイル）
    # -------------------------------------------------------------
    draw_pixel_block(draw, 15, 19, COLOR_TIE, scale)
    draw_pixel_block(draw, 16, 19, COLOR_TIE, scale)
    draw_pixel_block(draw, 15, 20, COLOR_TIE, scale)
    draw_pixel_block(draw, 16, 20, COLOR_TIE, scale)
    draw_pixel_block(draw, 15, 21, COLOR_TIE, scale)

    # -------------------------------------------------------------
    # 8. 手足（状態に応じたポーズ）
    # -------------------------------------------------------------
    if state == "happy":
        # 両手を振る
        draw_pixel_block(draw, 6, 13, COLOR_BODY_LIGHT, scale)
        draw_pixel_block(draw, 6, 14, COLOR_OUTLINE, scale)
        draw_pixel_block(draw, 25, 13, COLOR_BODY_LIGHT, scale)
        draw_pixel_block(draw, 25, 14, COLOR_OUTLINE, scale)
    elif state == "cheer":
        # 右手を高く突き上げる（ガッツポーズ）
        draw_pixel_block(draw, 7, 17, COLOR_BODY_LIGHT, scale)
        draw_pixel_block(draw, 25, 11, COLOR_BODY_LIGHT, scale)
        draw_pixel_block(draw, 25, 12, COLOR_OUTLINE, scale)
    elif state == "alarm_ask":
        # 片手を挙げて注目を促す (・ω・)ノ
        draw_pixel_block(draw, 7, 17, COLOR_BODY_LIGHT, scale)
        draw_pixel_block(draw, 25, 12, COLOR_BODY_LIGHT, scale)
        draw_pixel_block(draw, 26, 11, COLOR_BODY_LIGHT, scale)
        draw_pixel_block(draw, 26, 12, COLOR_OUTLINE, scale)
    elif "focus" in state:
        # PCキーボードをカタカタ入力する手
        hand_y = 18 if state == "focus_1" else 19
        draw_pixel_block(draw, 12, hand_y, COLOR_BODY_LIGHT, scale)
        draw_pixel_block(draw, 19, (hand_y - 1 if state == "focus_2" else hand_y), COLOR_BODY_LIGHT, scale)
        # 小型ノートPCのドット絵
        for px in range(13, 19):
            draw_pixel_block(draw, px, 21, COLOR_OUTLINE, scale)
            draw_pixel_block(draw, px, 20, COLOR_FACE, scale)
    else:
        # 通常の手
        draw_pixel_block(draw, 7, 17, COLOR_BODY_LIGHT, scale)
        draw_pixel_block(draw, 24, 17, COLOR_BODY_LIGHT, scale)

    # 足
    draw_pixel_block(draw, 11, 24, COLOR_OUTLINE, scale)
    draw_pixel_block(draw, 12, 24, COLOR_BODY_LIGHT, scale)
    draw_pixel_block(draw, 19, 24, COLOR_BODY_LIGHT, scale)
    draw_pixel_block(draw, 20, 24, COLOR_OUTLINE, scale)

    return img

def main():
    """全スプライトを生成して assets/ フォルダに保存"""
    states = [
        "idle_1", "idle_2",
        "look_left", "look_right", "look_up", "look_down",
        "thinking_1", "thinking_2",
        "happy",
        "focus_1", "focus_2",
        "sleepy_1", "sleepy_2",
        "alarm_ask",
        "pet_love",
        "cheer"
    ]
    for s in states:
        img = create_sprite(s)
        out_path = ASSETS_DIR / f"{s}.png"
        img.save(out_path, format="PNG")
        print(f"Generated sprite: {out_path}")

if __name__ == "__main__":
    main()
