"""
ネオ秘書くん - 究極のKawaiiドット絵ジェネレーター (Kawaii Pixel Art 4.0)

48x48の精密ピクセルグリッド（2頭身・大福シルエット・うるうるお目々・ころんとした丸み）で
レトロゲーム（たまごっち・ポケモン・MOTHER風）の最高に愛らしいドット絵を生成します。
"""

import os
from pathlib import Path
from PIL import Image, ImageDraw

ASSETS_DIR = Path(__file__).parent / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

GRID_SIZE = 48
SCALE = 3  # 出力サイズ: 144x144 (Canvas 170,135 にジャストフィット)

# カラーパレット
C_TRANS = (0, 0, 0, 0)
C_OUTLINE = (50, 40, 35, 255)       # 優しいダークブラウン輪郭
C_WHITE = (255, 255, 255, 255)
C_CHEEK = (255, 140, 150, 255)      # ほんのりピンクほっぺ
C_EYE = (45, 35, 30, 255)           # つぶらな黒目
C_HEADBAND = (235, 60, 60, 255)     # 赤ハチマキ
C_HEART = (245, 80, 120, 255)       # ハート
C_STAR = (255, 215, 0, 255)         # 星
C_ZZZ = (100, 180, 245, 255)        # 睡眠ブルー
C_TEA_CUP = (250, 245, 235, 255)
C_TEA_GREEN = (100, 200, 120, 255)

def p(draw: ImageDraw.ImageDraw, x: int, y: int, color):
    """1ピクセル（SCALE倍）を描画"""
    if 0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE:
        draw.rectangle([x * SCALE, y * SCALE, (x + 1) * SCALE - 1, (y + 1) * SCALE - 1], fill=color)

def p_box(draw: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int, color):
    """矩形塗りつぶし"""
    for x in range(x1, x2 + 1):
        for y in range(y1, y2 + 1):
            p(draw, x, y, color)

def p_circle(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color):
    """ドット絵の丸を描画"""
    for x in range(cx - r, cx + r + 1):
        for y in range(cy - r, cy + r + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r ** 2:
                p(draw, x, y, color)


# =============================================================================
# 1. 🦭 もちもちアザラシ (Seal) - まるで大福のような究極の癒やし
# =============================================================================
def draw_seal_sprite(state: str) -> Image.Image:
    img = Image.new("RGBA", (GRID_SIZE * SCALE, GRID_SIZE * SCALE), C_TRANS)
    draw = ImageDraw.Draw(img)

    c_body = (250, 252, 255, 255)
    c_shadow = (220, 230, 240, 255)
    c_nose = (70, 80, 95, 255)

    # 左右の前足（ヒレ）
    p_circle(draw, 10, 30, 4, C_OUTLINE)
    p_circle(draw, 10, 30, 3, c_body)
    p_circle(draw, 38, 30, 4, C_OUTLINE)
    p_circle(draw, 38, 30, 3, c_body)

    # まんまる大福ボディ
    p_circle(draw, 24, 25, 15, C_OUTLINE)
    p_circle(draw, 24, 25, 14, c_body)
    # 下部ソフトシャドウ
    for x in range(13, 36):
        p(draw, x, 36, c_shadow)
        p(draw, x, 37, c_shadow)

    # ほっぺ
    p_box(draw, 14, 27, 17, 28, C_CHEEK)
    p_box(draw, 31, 27, 34, 28, C_CHEEK)

    # 鼻＆ちいさな口 (ω)
    p_box(draw, 23, 24, 25, 25, c_nose)
    p(draw, 22, 27, C_OUTLINE)
    p(draw, 24, 27, C_OUTLINE)
    p(draw, 26, 27, C_OUTLINE)

    # 表情描画
    _draw_kawaii_eyes(draw, state, left_x=17, right_x=31, eye_y=22)
    _draw_kawaii_effects(draw, state, cx=24, cy=25)
    return img


# =============================================================================
# 2. 🍄 キノコ君 (Kinoko) - ころんとした赤カサ＆ちょこんとした白い茎
# =============================================================================
def draw_kinoko_sprite(state: str) -> Image.Image:
    img = Image.new("RGBA", (GRID_SIZE * SCALE, GRID_SIZE * SCALE), C_TRANS)
    draw = ImageDraw.Draw(img)

    c_cap = (235, 55, 55, 255)
    c_cap_light = (255, 110, 100, 255)
    c_cap_shadow = (185, 35, 35, 255)
    c_stem = (255, 252, 242, 255)
    c_stem_shadow = (235, 225, 210, 255)

    # 茎・ボディ（もちっとした丸四角）
    p_circle(draw, 24, 32, 9, C_OUTLINE)
    p_circle(draw, 24, 32, 8, c_stem)
    # 茎下部シャドウ
    for x in range(18, 31):
        p(draw, x, 38, c_stem_shadow)

    # ころんとした丸い赤カサ（ドーム状）
    p_circle(draw, 24, 18, 14, C_OUTLINE)
    p_circle(draw, 24, 18, 13, c_cap)
    # カサ下部シャドウ
    for x in range(12, 37):
        p(draw, x, 24, c_cap_shadow)
    # カサ上部ハイライト
    for x in range(18, 30):
        p(draw, x, 8, c_cap_light)

    # カサの丸い水玉（左上、中央上、右上）
    p_circle(draw, 17, 14, 3, C_WHITE)
    p_circle(draw, 25, 11, 3, C_WHITE)
    p_circle(draw, 31, 15, 3, C_WHITE)

    # ほっぺ
    p_box(draw, 16, 33, 19, 34, C_CHEEK)
    p_box(draw, 29, 33, 32, 34, C_CHEEK)

    # 表情描画
    _draw_kawaii_eyes(draw, state, left_x=19, right_x=29, eye_y=29)
    _draw_kawaii_effects(draw, state, cx=24, cy=25)
    return img


# =============================================================================
# 3. 👔 秘書くん (Hisho) - ピン耳柴犬/キツネ風マスコット＆赤ネクタイ
# =============================================================================
def draw_hisho_sprite(state: str) -> Image.Image:
    img = Image.new("RGBA", (GRID_SIZE * SCALE, GRID_SIZE * SCALE), C_TRANS)
    draw = ImageDraw.Draw(img)

    c_body = (195, 140, 95, 255)
    c_face = (255, 250, 240, 255)
    c_ear_in = (255, 165, 175, 255)
    c_tie = (235, 60, 60, 255)

    # ピンとした可愛い三角耳
    # 左耳
    for y in range(6, 16):
        dx = (y - 6) // 2
        p_box(draw, 14 - dx - 1, y, 17 + dx + 1, y, C_OUTLINE)
        p_box(draw, 14 - dx, y, 17 + dx, y, c_body)
    p_box(draw, 14, 10, 16, 13, c_ear_in)

    # 右耳
    for y in range(6, 16):
        dx = (y - 6) // 2
        p_box(draw, 31 - dx - 1, y, 34 + dx + 1, y, C_OUTLINE)
        p_box(draw, 31 - dx, y, 34 + dx, y, c_body)
    p_box(draw, 32, 10, 34, 13, c_ear_in)

    # まんまる頭部
    p_circle(draw, 24, 25, 14, C_OUTLINE)
    p_circle(draw, 24, 25, 13, c_body)

    # 白いふっくらマズル・お顔
    p_circle(draw, 24, 28, 9, C_OUTLINE)
    p_circle(draw, 24, 28, 8, c_face)

    # 小さな黒鼻
    p_box(draw, 23, 24, 25, 25, C_EYE)

    # ほっぺ
    p_box(draw, 15, 27, 18, 28, C_CHEEK)
    p_box(draw, 30, 27, 33, 28, C_CHEEK)

    # ちょこんと赤い蝶ネクタイ
    p_box(draw, 21, 35, 27, 38, C_OUTLINE)
    p_box(draw, 22, 36, 23, 37, c_tie)
    p_box(draw, 25, 36, 26, 37, c_tie)
    p(draw, 24, 36, C_WHITE)

    # 表情描画
    _draw_kawaii_eyes(draw, state, left_x=18, right_x=30, eye_y=22)
    _draw_kawaii_effects(draw, state, cx=24, cy=25)
    return img


# =============================================================================
# 4. 🦫 まるまるウォンバット (Wombat) - ころころぬいぐるみ風＆大きなお鼻
# =============================================================================
def draw_wombat_sprite(state: str) -> Image.Image:
    img = Image.new("RGBA", (GRID_SIZE * SCALE, GRID_SIZE * SCALE), C_TRANS)
    draw = ImageDraw.Draw(img)

    c_body = (145, 105, 80, 255)
    c_body_light = (175, 135, 110, 255)
    c_belly = (210, 180, 155, 255)
    c_nose = (50, 50, 60, 255)

    # ちいさな丸耳
    p_circle(draw, 12, 14, 4, C_OUTLINE)
    p_circle(draw, 12, 14, 3, c_body)
    p_circle(draw, 36, 14, 4, C_OUTLINE)
    p_circle(draw, 36, 14, 3, c_body)

    # まんまるコロコロボディ
    p_circle(draw, 24, 25, 14, C_OUTLINE)
    p_circle(draw, 24, 25, 13, c_body)

    # ふっくらお腹・口元
    p_circle(draw, 24, 29, 8, c_belly)

    # 大きな丸い黒鼻（ウォンバットのチャームポイント）
    p_circle(draw, 24, 23, 4, C_OUTLINE)
    p_circle(draw, 24, 23, 3, c_nose)
    p(draw, 23, 22, C_WHITE)  # 鼻の光沢

    # ほっぺ
    p_box(draw, 14, 26, 17, 27, C_CHEEK)
    p_box(draw, 31, 26, 34, 27, C_CHEEK)

    # 表情描画
    _draw_kawaii_eyes(draw, state, left_x=17, right_x=31, eye_y=21)
    _draw_kawaii_effects(draw, state, cx=24, cy=25)
    return img


# =============================================================================
# 共通 表情レンダラー (うるうるお目々・瞬き・笑顔・視線追従)
# =============================================================================
def _draw_kawaii_eyes(draw: ImageDraw.ImageDraw, state: str, left_x: int, right_x: int, eye_y: int):
    # 1. 瞬き (idle_2)
    if state == "idle_2":
        p_box(draw, left_x - 1, eye_y + 1, left_x + 2, eye_y + 1, C_EYE)
        p_box(draw, right_x - 2, eye_y + 1, right_x + 1, eye_y + 1, C_EYE)

    # 2. にっこり笑顔 (happy / celebrate / pet_love)
    elif state in ("happy", "celebrate_1", "celebrate_2", "celebrate_3", "pet_love"):
        # にっこり目 (^^)
        p(draw, left_x - 1, eye_y + 1, C_EYE)
        p_box(draw, left_x, eye_y, left_x + 1, eye_y, C_EYE)
        p(draw, left_x + 2, eye_y + 1, C_EYE)

        p(draw, right_x - 2, eye_y + 1, C_EYE)
        p_box(draw, right_x - 1, eye_y, right_x, eye_y, C_EYE)
        p(draw, right_x + 1, eye_y + 1, C_EYE)

        # にっこり口
        mx = (left_x + right_x) // 2
        p(draw, mx - 1, eye_y + 5, C_EYE)
        p(draw, mx, eye_y + 6, C_EYE)
        p(draw, mx + 1, eye_y + 5, C_EYE)

    # 3. 視線追従 (look_left / look_right / look_up / look_down)
    elif state.startswith("look_"):
        dx, dy = 0, 0
        if state == "look_left": dx = -1
        elif state == "look_right": dx = 1
        elif state == "look_up": dy = -1
        elif state == "look_down": dy = 1

        for ex in (left_x, right_x):
            # 縦3x横2の黒目
            p_box(draw, ex, eye_y, ex + 1, eye_y + 2, C_EYE)
            # ハイライトが視線方向に移動
            p(draw, ex + dx, eye_y + dy, C_WHITE)

    # 4. 睡眠 (sleepy / night)
    elif "sleepy" in state or "night" in state:
        p_box(draw, left_x - 1, eye_y + 1, left_x + 2, eye_y + 2, C_EYE)
        p_box(draw, right_x - 2, eye_y + 2, right_x + 1, eye_y + 1, C_EYE)
        # Zzz
        p_box(draw, right_x + 6, eye_y - 8, right_x + 9, eye_y - 8, C_ZZZ)
        p(draw, right_x + 7, eye_y - 7, C_ZZZ)
        p_box(draw, right_x + 6, eye_y - 6, right_x + 9, eye_y - 6, C_ZZZ)

    # 5. 通常待機 (うるうる大きな愛らしい瞳)
    else:
        for ex in (left_x, right_x):
            # 縦3x横2の大きな黒目
            p_box(draw, ex, eye_y, ex + 1, eye_y + 2, C_EYE)
            # 左上に白ハイライト（うるうる感）
            p(draw, ex, eye_y, C_WHITE)


# =============================================================================
# 共通 エフェクト・アイテム描画 (ハチマキ・ハート・お茶・本・星)
# =============================================================================
def _draw_kawaii_effects(draw: ImageDraw.ImageDraw, state: str, cx: int, cy: int):
    # 集中ハチマキ
    if "focus" in state:
        p_box(draw, 10, cy - 11, 38, cy - 9, C_HEADBAND)
        # 結び目
        p_box(draw, 37, cy - 14, 40, cy - 12, C_HEADBAND)
        p_box(draw, 38, cy - 8, 42, cy - 6, C_HEADBAND)

    # なでなでハート
    elif state == "pet_love":
        _draw_mini_heart(draw, 36, 10)
        _draw_mini_heart(draw, 10, 12)

    # お茶タイム
    elif "tea" in state:
        # 湯飲み
        p_box(draw, 32, 30, 39, 38, C_OUTLINE)
        p_box(draw, 33, 31, 38, 37, C_TEA_CUP)
        p_box(draw, 34, 31, 37, 33, C_TEA_GREEN)
        # 湯気
        p(draw, 34, 27, (200, 200, 200, 200))
        p(draw, 36, 25, (200, 200, 200, 200))

    # 読書タイム
    elif "reading" in state:
        p_box(draw, 18, 34, 30, 40, (100, 180, 245, 255))
        p_box(draw, 20, 35, 28, 39, C_WHITE)
        p_box(draw, 23, 34, 25, 40, C_OUTLINE)

    # 歓喜・大成功
    elif "celebrate" in state or "cheer" in state:
        _draw_mini_star(draw, 8, 12)
        _draw_mini_star(draw, 40, 12)
        _draw_mini_star(draw, 24, 6)


def _draw_mini_heart(draw: ImageDraw.ImageDraw, x: int, y: int):
    p_box(draw, x, y, x + 1, y, C_HEART)
    p_box(draw, x + 3, y, x + 4, y, C_HEART)
    p_box(draw, x - 1, y + 1, x + 5, y + 2, C_HEART)
    p_box(draw, x, y + 3, x + 4, y + 3, C_HEART)
    p_box(draw, x + 1, y + 4, x + 3, y + 4, C_HEART)
    p(draw, x + 2, y + 5, C_HEART)


def _draw_mini_star(draw: ImageDraw.ImageDraw, x: int, y: int):
    p(draw, x + 2, y, C_STAR)
    p_box(draw, x + 1, y + 1, x + 3, y + 1, C_STAR)
    p_box(draw, x, y + 2, x + 4, y + 2, C_STAR)
    p_box(draw, x + 1, y + 3, x + 3, y + 3, C_STAR)
    p(draw, x + 2, y + 4, C_STAR)


# =============================================================================
# 全スプライト一括生成
# =============================================================================
STATES = [
    "idle_1", "idle_2",
    "look_left", "look_right", "look_up", "look_down",
    "thinking_1", "thinking_2",
    "happy",
    "focus_1", "focus_2",
    "sleepy_1", "sleepy_2",
    "alarm_ask", "pet_love", "cheer",
    "tea_1", "tea_2",
    "reading_1", "reading_2",
    "stretch_1", "stretch_2",
    "celebrate_1", "celebrate_2", "celebrate_3",
    "care_1", "care_2",
    "night_1", "night_2"
]

CHARACTERS = {
    "hisho": draw_hisho_sprite,
    "kinoko": draw_kinoko_sprite,
    "seal": draw_seal_sprite,
    "wombat": draw_wombat_sprite
}

def generate_all_sprites():
    print("🎨 [Kawaii Pixel Art 4.0] 究極のKawaiiドット絵スプライトを生成中...")
    total = 0
    for char_id, draw_func in CHARACTERS.items():
        for state in STATES:
            img = draw_func(state)
            filename = f"{char_id}_{state}.png"
            img.save(ASSETS_DIR / filename, "PNG")
            if char_id == "hisho":
                img.save(ASSETS_DIR / f"{state}.png", "PNG")
            total += 1
            
    print(f"✓ 合計 {total} 枚のKawaiiドット絵を生成完了しました！")

if __name__ == "__main__":
    generate_all_sprites()
