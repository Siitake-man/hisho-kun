"""
ネオ秘書くん - 8/15レトロドット絵テイスト キャラ再生成ツール
(generate_dot_seal_kinoko.py)

8/15版秘書くん (assets/dot/hisho/) と同一のレトロパレット・128x128解像度で、
もちもちアザラシ (assets/dot/seal/) とキノコ君 (assets/dot/kinoko/) の
スプライト16状態を再生成する。

使い方:
    venv\\Scripts\\python.exe tools\\generate_dot_seal_kinoko.py
"""

import logging
from pathlib import Path
from typing import List

from PIL import Image, ImageDraw

logger = logging.getLogger("generate_dot_seal_kinoko")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# ※ 本スクリプトは tools/ 配下にあるため、プロジェクトルートは2階層上
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

GRID = 32
SCALE = 4  # 32 x 4 = 128x128（dot/hisho と同一解像度）
SIZE = GRID * SCALE

# --- 8/15版 (dot/hisho) と同一のレトロパレット ---
P_DARK = (74, 59, 50, 255)        # 輪郭・影・目
P_CREAM = (245, 245, 220, 255)    # クリーム白（カサの点など）
P_CHEEK = (239, 154, 154, 255)    # ほっぺピンク
P_YELLOW = (230, 210, 53, 255)    # 黄（ビックリ・集中マーク）
P_BLUE = (144, 202, 249, 255)     # 水色（ZZZ・汗）
P_PINK = (233, 30, 99, 255)       # ハート
P_YELLOW_L = (255, 235, 59, 255)  # 星
P_ORANGE = (255, 112, 67, 255)    # オレンジ

# アザラシ専用パレット（もちもち白）
S_BODY = (250, 250, 248, 255)
S_BODY_HI = (255, 255, 253, 255)
S_BODY_SH = (216, 222, 230, 255)
S_OUTLINE = (95, 105, 118, 255)
S_NOSE = (70, 80, 95, 255)
S_SPOT = (120, 130, 145, 255)

# キノコ君専用パレット（赤カサ＆白茎）
K_CAP = (229, 57, 53, 255)
K_CAP_HI = (255, 110, 100, 255)
K_CAP_SH = (185, 35, 35, 255)
K_STEM = (252, 248, 238, 255)
K_STEM_SH = (230, 222, 205, 255)

TRANSPARENT = (0, 0, 0, 0)

# 生成する16状態（8/15版と同一セット）
STATES: List[str] = [
    "idle_1", "idle_2",
    "look_left", "look_right", "look_up", "look_down",
    "thinking_1", "thinking_2",
    "happy",
    "focus_1", "focus_2",
    "sleepy_1", "sleepy_2",
    "alarm_ask", "pet_love", "cheer",
]


def p(draw: ImageDraw.ImageDraw, x: int, y: int, color) -> None:
    """1ドット（SCALE倍）を描画する。"""
    if 0 <= x < GRID and 0 <= y < GRID:
        draw.rectangle([x * SCALE, y * SCALE, (x + 1) * SCALE - 1, (y + 1) * SCALE - 1], fill=color)


def p_box(draw: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int, color) -> None:
    """矩形塗りつぶし（グリッド座標）。"""
    for x in range(x1, x2 + 1):
        for y in range(y1, y2 + 1):
            p(draw, x, y, color)


def p_ellipse(draw: ImageDraw.ImageDraw, cx: int, cy: int, rx: int, ry: int, color,
              outline=None) -> None:
    """楕円塗りつぶし（グリッド座標）。outline指定時は外周1ドットの輪郭を描く。"""
    for x in range(cx - rx, cx + rx + 1):
        for y in range(cy - ry, cy + ry + 1):
            if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                p(draw, x, y, color)
    if outline is not None:
        for x in range(cx - rx - 1, cx + rx + 2):
            for y in range(cy - ry - 1, cy + ry + 2):
                if not (((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0) and \
                   (((x - cx) / (rx + 1)) ** 2 + ((y - cy) / (ry + 1)) ** 2 <= 1.0):
                    p(draw, x, y, outline)


def _draw_heart(draw: ImageDraw.ImageDraw, x: int, y: int, color) -> None:
    """ミニハートを描画する。"""
    p_box(draw, x, y, x + 1, y, color)
    p_box(draw, x + 3, y, x + 4, y, color)
    p_box(draw, x - 1, y + 1, x + 5, y + 2, color)
    p_box(draw, x, y + 3, x + 4, y + 3, color)
    p(draw, x + 2, y + 4, color)


def _draw_star(draw: ImageDraw.ImageDraw, x: int, y: int, color) -> None:
    """ミニスターを描画する。"""
    p(draw, x + 2, y, color)
    p_box(draw, x + 1, y + 1, x + 3, y + 1, color)
    p_box(draw, x, y + 2, x + 4, y + 2, color)
    p_box(draw, x + 1, y + 3, x + 3, y + 3, color)
    p(draw, x + 2, y + 4, color)


# =============================================================================
# アザラシ描画（もちもち大福シルエット・白体）
# =============================================================================
def _seal_eyes(draw: ImageDraw.ImageDraw, state: str, look_dx: int = 0, look_dy: int = 0) -> None:
    """状態に応じたアザラシの目を描画する。"""
    ly = 13 + look_dy
    lx, rx_ = 11 + look_dx, 19 + look_dx
    if state.startswith("sleepy") or state == "idle_2":
        # 瞬き／居眠り: 1ドットの閉じ目
        p_box(draw, lx - 1, ly + 1, lx, ly + 1, P_DARK)
        p_box(draw, rx_, ly + 1, rx_ + 1, ly + 1, P_DARK)
    elif state.startswith("happy"):
        # ニコニコ目（^形）
        p(draw, lx - 1, ly + 1, P_DARK)
        p(draw, lx, ly, P_DARK)
        p(draw, lx + 1, ly + 1, P_DARK)
        p(draw, rx_ - 1, ly + 1, P_DARK)
        p(draw, rx_, ly, P_DARK)
        p(draw, rx_ + 1, ly + 1, P_DARK)
    elif state == "alarm_ask":
        # ビックリ目（3x3丸目）
        p_box(draw, lx - 1, ly - 1, lx + 1, ly + 1, P_DARK)
        p(draw, lx - 1, ly - 1, (255, 255, 255, 255))
        p_box(draw, rx_ - 1, ly - 1, rx_ + 1, ly + 1, P_DARK)
        p(draw, rx_ - 1, ly - 1, (255, 255, 255, 255))
    else:
        # 通常のつぶらな黒目（2x2＋ハイライト）
        p_box(draw, lx, ly, lx + 1, ly + 1, P_DARK)
        p(draw, lx, ly, (255, 255, 255, 255))
        p_box(draw, rx_, ly, rx_ + 1, ly + 1, P_DARK)
        p(draw, rx_, ly, (255, 255, 255, 255))


def draw_seal(state: str) -> Image.Image:
    """もちもちアザラシのスプライト1枚を生成する。

    Args:
        state (str): スプライト状態名（idle_1 等）。

    Returns:
        Image.Image: 128x128 RGBA のドット絵スプライト。
    """
    img = Image.new("RGBA", (SIZE, SIZE), TRANSPARENT)
    draw = ImageDraw.Draw(img)

    # --- 視線オフセット（look系） ---
    look_dx, look_dy = 0, 0
    if state == "look_left":
        look_dx = -1
    elif state == "look_right":
        look_dx = 1
    elif state == "look_up":
        look_dy = -1
    elif state == "look_down":
        look_dy = 1

    # --- 左右の前足ヒレ ---
    p_ellipse(draw, 6, 25, 3, 3, S_OUTLINE)
    p_ellipse(draw, 6, 25, 2, 2, S_BODY)
    p_ellipse(draw, 26, 25, 3, 3, S_OUTLINE)
    p_ellipse(draw, 26, 25, 2, 2, S_BODY)

    # --- まんまる大福ボディ ---
    p_ellipse(draw, 16, 19, 11, 10, S_BODY, outline=S_OUTLINE)
    for x in range(8, 25):
        p(draw, x, 26, S_BODY_SH)
        p(draw, x, 27, S_BODY_SH)
    p_box(draw, 10, 11, 12, 13, S_BODY_HI)

    # --- 頭の灰斑（アザラシの特徴） ---
    p_box(draw, 14, 6, 18, 9, S_SPOT)
    p(draw, 13, 7, S_SPOT)
    p(draw, 19, 8, S_SPOT)

    # --- ほっぺ ---
    p_box(draw, 8, 16, 9, 17, P_CHEEK)
    p_box(draw, 22, 16, 23, 17, P_CHEEK)

    # --- 鼻＆ω口 ---
    p_box(draw, 15, 16, 16, 17, S_NOSE)
    p(draw, 14, 18, S_OUTLINE)
    p(draw, 16, 18, S_OUTLINE)
    p(draw, 18, 18, S_OUTLINE)
    if state == "happy" or state == "cheer":
        p_box(draw, 14, 18, 18, 18, S_OUTLINE)
        p(draw, 15, 19, S_OUTLINE)
        p(draw, 17, 19, S_OUTLINE)

    # --- 目（状態別） ---
    _seal_eyes(draw, state, look_dx, look_dy)

    # --- 状態エフェクト ---
    if state.startswith("sleepy"):
        p_box(draw, 24, 5, 26, 5, P_BLUE)
        p_box(draw, 26, 6, 27, 7, P_BLUE)
        p_box(draw, 23, 8, 25, 8, P_BLUE)
    elif state == "alarm_ask":
        p_box(draw, 25, 3, 26, 6, P_YELLOW)
        p(draw, 25, 8, P_YELLOW)
    elif state == "pet_love":
        _draw_heart(draw, 4, 5, P_PINK)
        _draw_heart(draw, 26, 6, P_PINK)
    elif state == "cheer":
        _draw_star(draw, 4, 4, P_YELLOW_L)
        _draw_star(draw, 26, 4, P_YELLOW_L)
        _draw_star(draw, 15, 1, P_YELLOW_L)
    elif state.startswith("thinking"):
        p(draw, 23, 4, P_DARK)
        p(draw, 25, 3, P_DARK)
        p(draw, 27, 2, P_DARK)
    elif state.startswith("focus"):
        p(draw, 24, 4, P_YELLOW)
        p(draw, 26, 5, P_YELLOW)
        p_box(draw, 10, 11, 12, 11, P_DARK)
        p_box(draw, 19, 11, 21, 11, P_DARK)

    return img


# =============================================================================
# キノコ君描画（赤カサ＆白茎）
# =============================================================================
def _kinoko_eyes(draw: ImageDraw.ImageDraw, state: str, look_dx: int = 0, look_dy: int = 0) -> None:
    """状態に応じたキノコ君の目を描画する。"""
    ly = 20 + look_dy
    lx, rx_ = 13 + look_dx, 18 + look_dx
    if state.startswith("sleepy") or state == "idle_2":
        p_box(draw, lx, ly + 1, lx + 1, ly + 1, P_DARK)
        p_box(draw, rx_, ly + 1, rx_ + 1, ly + 1, P_DARK)
    elif state.startswith("happy"):
        p(draw, lx, ly + 1, P_DARK)
        p(draw, lx + 1, ly, P_DARK)
        p(draw, rx_, ly + 1, P_DARK)
        p(draw, rx_ + 1, ly, P_DARK)
    elif state == "alarm_ask":
        p_box(draw, lx - 1, ly - 1, lx + 1, ly + 1, P_DARK)
        p(draw, lx - 1, ly - 1, (255, 255, 255, 255))
        p_box(draw, rx_ - 1, ly - 1, rx_ + 1, ly + 1, P_DARK)
        p(draw, rx_ - 1, ly - 1, (255, 255, 255, 255))
    else:
        p_box(draw, lx, ly, lx + 1, ly + 1, P_DARK)
        p(draw, lx, ly, (255, 255, 255, 255))
        p_box(draw, rx_, ly, rx_ + 1, ly + 1, P_DARK)
        p(draw, rx_, ly, (255, 255, 255, 255))


def draw_kinoko(state: str) -> Image.Image:
    """キノコ君のスプライト1枚を生成する。

    Args:
        state (str): スプライト状態名（idle_1 等）。

    Returns:
        Image.Image: 128x128 RGBA のドット絵スプライト。
    """
    img = Image.new("RGBA", (SIZE, SIZE), TRANSPARENT)
    draw = ImageDraw.Draw(img)

    # --- 視線オフセット（look系） ---
    look_dx, look_dy = 0, 0
    if state == "look_left":
        look_dx = -1
    elif state == "look_right":
        look_dx = 1
    elif state == "look_up":
        look_dy = -1
    elif state == "look_down":
        look_dy = 1

    # --- 赤カサ（上半分の傘） ---
    p_ellipse(draw, 16, 12, 13, 11, K_CAP, outline=P_DARK)
    # カサ下側の影ライン
    p_box(draw, 5, 16, 27, 17, K_CAP_SH)
    # カサのハイライト（左上）
    p_box(draw, 8, 5, 11, 7, K_CAP_HI)
    # カサのクリーム白点
    p_box(draw, 20, 6, 21, 7, P_CREAM)
    p_box(draw, 15, 10, 16, 11, P_CREAM)
    p_box(draw, 10, 12, 11, 13, P_CREAM)

    # --- 白茎（角丸） ---
    p_box(draw, 10, 18, 21, 27, P_DARK)
    p_box(draw, 11, 18, 20, 26, K_STEM)
    p_box(draw, 11, 26, 20, 26, K_STEM_SH)

    # --- ほっぺ ---
    p_box(draw, 11, 23, 12, 24, P_CHEEK)
    p_box(draw, 19, 23, 20, 24, P_CHEEK)

    # --- 口 ---
    p_box(draw, 15, 24, 16, 24, P_DARK)
    if state == "happy" or state == "cheer":
        p_box(draw, 14, 24, 17, 24, P_DARK)
        p(draw, 15, 25, P_DARK)
        p(draw, 16, 25, P_DARK)

    # --- 目（状態別） ---
    _kinoko_eyes(draw, state, look_dx, look_dy)

    # --- 状態エフェクト ---
    if state.startswith("sleepy"):
        p_box(draw, 24, 5, 26, 5, P_BLUE)
        p_box(draw, 26, 6, 27, 7, P_BLUE)
        p_box(draw, 23, 8, 25, 8, P_BLUE)
    elif state == "alarm_ask":
        p_box(draw, 25, 2, 26, 5, P_YELLOW)
        p(draw, 25, 7, P_YELLOW)
    elif state == "pet_love":
        _draw_heart(draw, 3, 4, P_PINK)
        _draw_heart(draw, 26, 5, P_PINK)
    elif state == "cheer":
        _draw_star(draw, 3, 3, P_YELLOW_L)
        _draw_star(draw, 26, 3, P_YELLOW_L)
        _draw_star(draw, 15, 0, P_YELLOW_L)
    elif state.startswith("thinking"):
        p(draw, 23, 3, P_DARK)
        p(draw, 25, 2, P_DARK)
        p(draw, 27, 1, P_DARK)
    elif state.startswith("focus"):
        p(draw, 24, 3, P_YELLOW)
        p(draw, 26, 4, P_YELLOW)
        p_box(draw, 12, 19, 14, 19, P_DARK)
        p_box(draw, 17, 19, 19, 19, P_DARK)

    return img


# =============================================================================
# 全スプライト一括生成
# =============================================================================
def generate_all() -> None:
    """アザラシとキノコ君の16状態スプライトを一括生成する。"""
    generators = {"seal": draw_seal, "kinoko": draw_kinoko}
    total = 0
    for char_id, draw_func in generators.items():
        out_dir = ASSETS_DIR / "dot" / char_id
        out_dir.mkdir(parents=True, exist_ok=True)
        for state in STATES:
            img = draw_func(state)
            img.save(out_dir / f"{state}.png", "PNG")
            total += 1
        logger.info(f"✓ {char_id}: {len(STATES)}枚生成 → {out_dir}")
    logger.info(f"🎉 合計 {total} 枚の8/15テイスト・レトロドット絵を生成完了！")


if __name__ == "__main__":
    generate_all()
