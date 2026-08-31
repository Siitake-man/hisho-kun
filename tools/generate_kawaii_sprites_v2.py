# -*- coding: utf-8 -*-
"""ネオ秘書くん - 新生5大キャラクタースイート スプライト生成ツール v2 (generate_kawaii_sprites_v2.py)

2026-08-31 ボス承認・ゼロベース再設計版。以下の3キャラクターの 128x128 透過PNG
ドット絵スプライト（共通31状態＋固有モーション）を assets/dot/ 配下へ生成する。

- もちもちアザラシ君 (seal): 大福フォルム ＋ 茶柱ぷかぷか (tea_pillar_1/2)
- 森のちびっ子書記官キノコ君 (kinoko): メガネ ＋ 羽ペン ＋ タスク記録 (writing_1/2)
- 絶叫＆悟りマーモット君 (marmot): 悟り立ち ＋ 絶叫 (screaming_1/2) ＋ ツンデレ溶け (petting_1/2)

使い方:
    venv\\Scripts\\python.exe tools\\generate_kawaii_sprites_v2.py
"""

import logging
from pathlib import Path
from typing import Callable, Dict, List

from PIL import Image, ImageDraw

logger = logging.getLogger("generate_kawaii_sprites_v2")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

GRID = 32
SCALE = 4
SIZE = GRID * SCALE

TRANSPARENT = (0, 0, 0, 0)
P_DARK = (74, 59, 50, 255)
P_CREAM = (245, 245, 220, 255)
P_CHEEK = (239, 154, 154, 255)
P_YELLOW = (230, 210, 53, 255)
P_BLUE = (144, 202, 249, 255)
P_PINK = (233, 30, 99, 255)
P_YELLOW_L = (255, 235, 59, 255)
P_GREEN = (129, 199, 132, 255)
P_TEA = (121, 85, 72, 255)
P_WHITE = (255, 255, 255, 255)
P_MOON = (255, 241, 118, 255)
P_ROCK = (141, 141, 141, 255)
P_ROCK_SH = (117, 117, 117, 255)

# --- アザラシ (seal): もちもち大福白 ---
S_BODY = (250, 250, 248, 255)
S_BODY_HI = (255, 255, 253, 255)
S_BODY_SH = (216, 222, 230, 255)
S_OUTLINE = (95, 105, 118, 255)
S_NOSE = (70, 80, 95, 255)
S_SPOT = (120, 130, 145, 255)

# --- キノコ (kinoko): 深紅の赤水玉カサ ＋ メガネ ＋ 羽ペン ---
K_CAP = (183, 28, 28, 255)
K_CAP_HI = (239, 83, 80, 255)
K_CAP_SH = (130, 20, 20, 255)
K_STEM = (252, 248, 238, 255)
K_STEM_SH = (230, 222, 205, 255)
K_GLASS = (55, 71, 79, 255)
K_GLASS_IN = (225, 245, 254, 255)
K_FEATHER = (255, 248, 225, 255)
K_NOTE = (239, 235, 210, 255)

# --- マーモット (marmot): 温かみのあるブラウン ---
M_FUR = (141, 110, 99, 255)
M_FUR_HI = (174, 143, 130, 255)
M_FUR_SH = (109, 76, 65, 255)
M_BELLY = (215, 189, 176, 255)
M_OUTLINE = (62, 39, 35, 255)
M_MOUTH = (49, 27, 20, 255)

# 共通31状態（kyle 31種と同一セット）
COMMON_STATES: List[str] = [
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
                if not (((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0) and     (((x - cx) / (rx + 1)) ** 2 + ((y - cy) / (ry + 1)) ** 2 <= 1.0):
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


def _draw_zzz(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    """睡眠のZZZを描画する。"""
    p_box(draw, x, y, x + 2, y, P_BLUE)
    p(draw, x + 2, y + 1, P_BLUE)
    p_box(draw, x, y + 2, x + 2, y + 2, P_BLUE)
    p(draw, x, y + 1, P_BLUE)


def _draw_wave(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    """青い波紋（〜）を描画する。"""
    p(draw, x, y + 1, P_BLUE)
    p_box(draw, x + 1, y, x + 2, y, P_BLUE)
    p(draw, x + 3, y + 1, P_BLUE)
    p(draw, x + 1, y + 2, P_BLUE)
    p(draw, x + 2, y + 2, P_BLUE)


def _draw_moon(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    """夜の三日月を描画する。"""
    p_ellipse(draw, x + 1, y + 1, 2, 2, P_MOON)
    p_ellipse(draw, x, y, 2, 2, TRANSPARENT)
    p_box(draw, x, y, x + 2, y + 3, TRANSPARENT)
    p(draw, x + 2, y, P_MOON)
    p(draw, x + 3, y + 1, P_MOON)
    p(draw, x + 3, y + 2, P_MOON)
    p(draw, x + 2, y + 3, P_MOON)


def _fx_alarm(draw: ImageDraw.ImageDraw) -> None:
    """アラートのビックリマーク。"""
    p_box(draw, 25, 2, 26, 5, P_YELLOW)
    p(draw, 25, 7, P_YELLOW)


def _fx_hearts(draw: ImageDraw.ImageDraw) -> None:
    """両脇のハート。"""
    _draw_heart(draw, 3, 4, P_PINK)
    _draw_heart(draw, 26, 5, P_PINK)


def _fx_stars(draw: ImageDraw.ImageDraw) -> None:
    """周囲の星。"""
    _draw_star(draw, 3, 3, P_YELLOW_L)
    _draw_star(draw, 26, 3, P_YELLOW_L)
    _draw_star(draw, 15, 0, P_YELLOW_L)


def _fx_think(draw: ImageDraw.ImageDraw, n: int) -> None:
    """右上の思考点（n個）。"""
    dots = [(23, 4), (25, 3), (27, 2)]
    for i in range(min(n, len(dots))):
        p(draw, dots[i][0], dots[i][1], P_DARK)


def _fx_focus(draw: ImageDraw.ImageDraw) -> None:
    """集中のやる気スパーク。"""
    p(draw, 24, 3, P_YELLOW)
    p(draw, 26, 4, P_YELLOW)


def _fx_moon_night(draw: ImageDraw.ImageDraw) -> None:
    """夜空の三日月（右上）。"""
    _draw_moon(draw, 26, 3)


def _look(state: str):
    """look系状態から視線オフセットを返す。"""
    if state == "look_left":
        return -1, 0
    if state == "look_right":
        return 1, 0
    if state == "look_up":
        return 0, -1
    if state == "look_down":
        return 0, 1
    return 0, 0

# =============================================================================
# マーモット描画（悟り顔仁王立ち ＋ 絶叫 ＋ ツンデレ溶け）
# =============================================================================
def _marmot_eyes(
    draw: ImageDraw.ImageDraw, state: str, ly: int, look_dx: int = 0, look_dy: int = 0
) -> None:
    """状態に応じたマーモット君の目（悟り半目がデフォルト）を描画する。"""
    ey = ly + look_dy
    lx, rx_ = 12 + look_dx, 19 + look_dx
    if state == "alarm_ask":
        # 危機感知: 丸見開き目
        p_box(draw, lx - 1, ey - 1, lx + 1, ey + 1, P_DARK)
        p(draw, lx - 1, ey - 1, P_WHITE)
        p_box(draw, rx_ - 1, ey - 1, rx_ + 1, ey + 1, P_DARK)
        p(draw, rx_ - 1, ey - 1, P_WHITE)
    elif state.startswith("screaming"):
        # 絶叫: ギュッと閉じたＸ目
        p(draw, lx - 1, ey - 1, P_DARK)
        p(draw, lx + 1, ey + 1, P_DARK)
        p(draw, lx + 1, ey - 1, P_DARK)
        p(draw, lx - 1, ey + 1, P_DARK)
        p(draw, rx_ - 1, ey - 1, P_DARK)
        p(draw, rx_ + 1, ey + 1, P_DARK)
        p(draw, rx_ + 1, ey - 1, P_DARK)
        p(draw, rx_ - 1, ey + 1, P_DARK)
    elif state == "happy" or state == "cheer" or state.startswith("celebrate") or state.startswith("night") or state.startswith("sleepy") or state == "idle_2" or state.startswith("tea") or melt_state(state):
        # 極楽つり目（横線）
        p_box(draw, lx - 1, ey, lx + 1, ey, P_DARK)
        p_box(draw, rx_ - 1, ey, rx_ + 1, ey, P_DARK)
        if melt_state(state):
            # ふにゃ〜っととろけた眉尻
            p(draw, lx - 1, ey - 1, P_DARK)
            p(draw, rx_ + 1, ey - 1, P_DARK)
    else:
        # 悟り半目: 上まぶたの線 ＋ 半分だけ出た瞳
        p_box(draw, lx - 1, ey - 1, lx + 1, ey - 1, P_DARK)
        p(draw, lx, ey, P_DARK)
        p_box(draw, rx_ - 1, ey - 1, rx_ + 1, ey - 1, P_DARK)
        p(draw, rx_, ey, P_DARK)


def melt_state(state: str) -> bool:
    """ツンデレ溶け（petting）状態かどうかを返す。"""
    return state.startswith("petting")


def draw_marmot(state: str) -> Image.Image:
    """絶叫＆悟りマーモット君のスプライト1枚を生成する。

    Args:
        state (str): スプライト状態名（idle_1, screaming_1, petting_2 等）。

    Returns:
        Image.Image: 128x128 RGBA のドット絵スプライト。
    """
    img = Image.new("RGBA", (SIZE, SIZE), TRANSPARENT)
    draw = ImageDraw.Draw(img)
    look_dx, look_dy = _look(state)

    melt = melt_state(state)
    melt_lv = 2 if state == "petting_2" else (1 if melt else 0)
    lift = 1 if (state == "stretch_2" or state.startswith("celebrate")) else 0

    # 溶けで低く・広く、伸びで1px浮く
    body_cy = 19 + melt_lv - lift
    body_rx = 7 + melt_lv
    body_ry = 7 if melt_lv == 0 else (6 if melt_lv == 1 else 5)

    # --- 岩の台座（仁王立ち用） ---
    p_ellipse(draw, 16, 28, 10, 3, P_ROCK, outline=P_DARK)
    p_box(draw, 6, 28, 26, 29, P_ROCK_SH)
    p_box(draw, 8, 27, 11, 27, P_ROCK)

    # --- 胴体（カピバラ風ズングリボディ） ---
    p_ellipse(draw, 16, body_cy, body_rx, body_ry, M_FUR, outline=M_OUTLINE)
    p_box(draw, 16 - body_rx + 2, body_cy - body_ry + 1, 16 - body_rx + 4, body_cy - body_ry + 2, M_FUR_HI)
    p_box(draw, 14, body_cy + body_ry - 2, 17, body_cy + body_ry - 1, M_FUR_SH)

    # --- お腹（薄色） ---
    p_ellipse(draw, 16, body_cy + 2, body_rx - 3, body_ry - 3, M_BELLY)

    # --- 小さい丸耳 ---
    ear_y = body_cy - body_ry - 1
    p_box(draw, 10, ear_y, 11, ear_y + 1, M_FUR)
    p_box(draw, 20, ear_y, 21, ear_y + 1, M_FUR)

    # --- 鼻 ---
    p_box(draw, 15, body_cy - 1, 16, body_cy - 1, M_OUTLINE)

    # --- 口（通常は小さい線 / 絶叫時は大口） ---
    if state.startswith("screaming"):
        p_ellipse(draw, 16, body_cy + 3, 4, 3, M_MOUTH)
        p_ellipse(draw, 16, body_cy + 4, 2, 1, P_PINK)
        # ア゛ーッ！の衝撃線
        p(draw, 4, body_cy - 9, P_DARK)
        p(draw, 5, body_cy - 7, P_DARK)
        p(draw, 27, body_cy - 9, P_DARK)
        p(draw, 26, body_cy - 7, P_DARK)
        p(draw, 16, ear_y - 3, P_DARK)
        if state == "screaming_2":
            p(draw, 3, body_cy - 6, P_DARK)
            p(draw, 28, body_cy - 6, P_DARK)
            p(draw, 16, ear_y - 4, P_DARK)
    else:
        p_box(draw, 15, body_cy + 2, 16, body_cy + 2, M_OUTLINE)
        if state == "happy" or state == "cheer" or state.startswith("celebrate"):
            p_box(draw, 14, body_cy + 2, 17, body_cy + 2, M_OUTLINE)
            p(draw, 15, body_cy + 3, M_OUTLINE)
            p(draw, 16, body_cy + 3, M_OUTLINE)

    # --- ほっぺ ---
    p_box(draw, 10, body_cy + 1, 11, body_cy + 2, P_CHEEK)
    p_box(draw, 20, body_cy + 1, 21, body_cy + 2, P_CHEEK)

    # --- 前足（岩の上にちょん） ---
    paw_y = body_cy + body_ry
    p_box(draw, 11, paw_y, 12, paw_y, M_FUR_SH)
    p_box(draw, 19, paw_y, 20, paw_y, M_FUR_SH)

    # --- 目 ---
    _marmot_eyes(draw, state, body_cy - 3, look_dx, look_dy)

    # --- 状態エフェクト ---
    if state.startswith("screaming"):
        pass  # 衝撃線は口の描画時に処理済み
    elif melt:
        _fx_hearts(draw)
    elif state == "alarm_ask":
        _fx_alarm(draw)
    elif state == "pet_love" or state == "care_2":
        _fx_hearts(draw)
    elif state == "care_1":
        _draw_heart(draw, 26, 10, P_PINK)
    elif state == "cheer" or state.startswith("celebrate"):
        _fx_stars(draw)
        if state == "celebrate_2":
            p(draw, 3, 12, P_PINK)
        elif state == "celebrate_3":
            p(draw, 28, 12, P_YELLOW_L)
    elif state.startswith("thinking"):
        _fx_think(draw, 3 if state == "thinking_2" else 2)
        if state == "thinking_2":
            # 悟りの宅急便…ではなく、葉っぱをくわえる
            p_box(draw, 17, body_cy + 2, 19, body_cy + 2, P_GREEN)
    elif state.startswith("focus"):
        _fx_focus(draw)
        p_box(draw, 10, body_cy - 5, 14, body_cy - 5, M_OUTLINE)
        p_box(draw, 17, body_cy - 5, 21, body_cy - 5, M_OUTLINE)
        if state == "focus_2":
            p_box(draw, 25, 7, 26, 8, P_BLUE)
    elif state == "night_2":
        _draw_zzz(draw, 24, 4)
    elif state.startswith("night"):
        _fx_moon_night(draw)
    elif state == "stretch_1":
        p(draw, 16, 1, P_DARK)
        p(draw, 13, 2, P_DARK)
        p(draw, 19, 2, P_DARK)
    elif state == "walk_1":
        p(draw, 6, 27, P_WHITE)
        p(draw, 7, 26, P_WHITE)
    elif state == "walk_2":
        p(draw, 25, 27, P_WHITE)
        p(draw, 24, 26, P_WHITE)
    elif state == "reading_1" or state == "reading_2":
        p_box(draw, 12, body_cy + 4, 21, body_cy + 9, P_CREAM)
        p_box(draw, 12, body_cy + 4, 21, body_cy + 4, P_DARK)
        p_box(draw, 14, body_cy + 6, 19, body_cy + 6, M_OUTLINE)
        if state == "reading_2":
            p_box(draw, 14, body_cy + 8, 19, body_cy + 8, M_OUTLINE)
            p(draw, 22, body_cy + 3, P_WHITE)
    elif state == "tea_1" or state == "tea_2":
        # 好きな葉っぱをモグモグ
        if state == "tea_1":
            p_box(draw, 4, body_cy, 7, body_cy + 3, P_GREEN)
            p(draw, 5, body_cy - 2, P_DARK)
        else:
            p_box(draw, 5, body_cy + 6, 8, body_cy + 8, P_GREEN)

    return img

# =============================================================================
# アザラシ描画（もちもち大福ボディ・黒ごまの瞳・ぷにぷにω口）
# =============================================================================
def _seal_eyes(draw: ImageDraw.ImageDraw, state: str, look_dx: int = 0, look_dy: int = 0) -> None:
    """状態に応じたアザラシの黒ごまの目を描画する。"""
    ly = 13 + look_dy
    lx, rx_ = 11 + look_dx, 19 + look_dx
    if state == "happy" or state.startswith("night") or state.startswith("tea_pillar") or state == "cheer":
        # ニコニコ閉じ目（^形）
        p(draw, lx - 1, ly + 1, P_DARK)
        p(draw, lx, ly, P_DARK)
        p(draw, lx + 1, ly + 1, P_DARK)
        p(draw, rx_ - 1, ly + 1, P_DARK)
        p(draw, rx_, ly, P_DARK)
        p(draw, rx_ + 1, ly + 1, P_DARK)
    elif state == "idle_2" or state.startswith("sleepy") or state == "tea_1":
        # 瞬き／お茶飲み込み中: 1ドットの閉じ目
        p_box(draw, lx - 1, ly + 1, lx, ly + 1, P_DARK)
        p_box(draw, rx_, ly + 1, rx_ + 1, ly + 1, P_DARK)
    elif state == "alarm_ask":
        # ビックリ目（3x3丸目）
        p_box(draw, lx - 1, ly - 1, lx + 1, ly + 1, P_DARK)
        p(draw, lx - 1, ly - 1, P_WHITE)
        p_box(draw, rx_ - 1, ly - 1, rx_ + 1, ly + 1, P_DARK)
        p(draw, rx_ - 1, ly - 1, P_WHITE)
    else:
        # つぶらな黒ごまの瞳（2x2＋ハイライト）
        p_box(draw, lx, ly, lx + 1, ly + 1, P_DARK)
        p(draw, lx, ly, P_WHITE)
        p_box(draw, rx_, ly, rx_ + 1, ly + 1, P_DARK)
        p(draw, rx_, ly, P_WHITE)


def _seal_cup_ground(draw: ImageDraw.ImageDraw, x: int = 23) -> None:
    """地面に置いた湯呑みを描画する。"""
    p_box(draw, x, 24, x + 2, 26, P_CREAM)
    p_box(draw, x, 24, x + 2, 24, P_TEA)
    p_box(draw, x - 1, 26, x + 3, 26, S_OUTLINE)
    p(draw, x + 1, 22, P_WHITE)


def _seal_cup_raised(draw: ImageDraw.ImageDraw) -> None:
    """口元へ差し出した湯呑みを描画する。"""
    p_box(draw, 22, 17, 24, 19, P_CREAM)
    p_box(draw, 22, 17, 24, 17, P_TEA)
    p(draw, 23, 15, P_WHITE)
    p(draw, 23, 14, P_WHITE)


def draw_seal(state: str) -> Image.Image:
    """もちもちアザラシ君のスプライト1枚を生成する。

    Args:
        state (str): スプライト状態名（idle_1, tea_pillar_1 等）。

    Returns:
        Image.Image: 128x128 RGBA のドット絵スプライト。
    """
    img = Image.new("RGBA", (SIZE, SIZE), TRANSPARENT)
    draw = ImageDraw.Draw(img)
    look_dx, look_dy = _look(state)

    # --- 前足ヒレ（状態別ポーズ） ---
    if state.startswith("stretch"):
        # 両ヒレを高く上げてぐーっと伸び
        p_ellipse(draw, 6, 13, 2, 3, S_OUTLINE)
        p_ellipse(draw, 6, 13, 1, 2, S_BODY)
        p_ellipse(draw, 26, 13, 2, 3, S_OUTLINE)
        p_ellipse(draw, 26, 13, 1, 2, S_BODY)
    elif state == "walk_1":
        p_ellipse(draw, 4, 26, 3, 3, S_OUTLINE)
        p_ellipse(draw, 4, 26, 2, 2, S_BODY)
        p_ellipse(draw, 27, 24, 3, 3, S_OUTLINE)
        p_ellipse(draw, 27, 24, 2, 2, S_BODY)
    elif state == "walk_2":
        p_ellipse(draw, 5, 24, 3, 3, S_OUTLINE)
        p_ellipse(draw, 5, 24, 2, 2, S_BODY)
        p_ellipse(draw, 26, 26, 3, 3, S_OUTLINE)
        p_ellipse(draw, 26, 26, 2, 2, S_BODY)
    elif state == "cheer" or state.startswith("celebrate"):
        # パタパタ拍手（ヒレを中段に上げる）
        p_ellipse(draw, 6, 16, 3, 2, S_OUTLINE)
        p_ellipse(draw, 6, 16, 2, 1, S_BODY)
        p_ellipse(draw, 26, 16, 3, 2, S_OUTLINE)
        p_ellipse(draw, 26, 16, 2, 1, S_BODY)
    else:
        p_ellipse(draw, 6, 25, 3, 3, S_OUTLINE)
        p_ellipse(draw, 6, 25, 2, 2, S_BODY)
        p_ellipse(draw, 26, 25, 3, 3, S_OUTLINE)
        p_ellipse(draw, 26, 25, 2, 2, S_BODY)

    # --- まんまる大福ボディ（下膨れ） ---
    p_ellipse(draw, 16, 20, 12, 9, S_BODY, outline=S_OUTLINE)
    # --- 頭（大福の折り目を消して一体化） ---
    p_ellipse(draw, 16, 12, 9, 8, S_BODY, outline=S_OUTLINE)
    p_box(draw, 10, 18, 22, 19, S_BODY)
    for x in range(8, 25):
        p(draw, x, 26, S_BODY_SH)
        p(draw, x, 27, S_BODY_SH)
    p_box(draw, 9, 9, 11, 11, S_BODY_HI)

    # --- 頭の灰斑（黒ごま） ---
    p_box(draw, 14, 6, 18, 9, S_SPOT)
    p(draw, 13, 7, S_SPOT)
    p(draw, 19, 8, S_SPOT)

    # --- ほっぺ ---
    p_box(draw, 8, 16, 9, 17, P_CHEEK)
    p_box(draw, 22, 16, 23, 17, P_CHEEK)

    # --- 鼻＆ぷにぷにω口 ---
    p_box(draw, 15, 16, 16, 17, S_NOSE)
    p(draw, 14, 18, S_OUTLINE)
    p(draw, 16, 18, S_OUTLINE)
    p(draw, 18, 18, S_OUTLINE)
    if state == "happy" or state == "cheer" or state.startswith("celebrate"):
        p_box(draw, 14, 18, 18, 18, S_OUTLINE)
        p(draw, 15, 19, S_OUTLINE)
        p(draw, 17, 19, S_OUTLINE)

    # --- 目（状態別） ---
    _seal_eyes(draw, state, look_dx, look_dy)

    # --- 小道具 ---
    if state == "tea_1":
        _seal_cup_raised(draw)
    elif state == "tea_2" or state == "care_1" or state == "care_2":
        _seal_cup_ground(draw)
    elif state.startswith("tea_pillar"):
        # 茶柱立て：中央の湯呑みから茶柱が直立
        p_box(draw, 14, 25, 17, 27, P_CREAM)
        p_box(draw, 14, 25, 17, 25, P_TEA)
        p_box(draw, 13, 27, 18, 27, S_OUTLINE)
        p_box(draw, 15, 11, 16, 24, P_TEA)
        p(draw, 15, 13, P_WHITE)
        p(draw, 15, 17, P_WHITE)
        p(draw, 15, 21, P_WHITE)
        _draw_wave(draw, 8, 10)
        _draw_wave(draw, 20, 10)

    # --- 状態エフェクト ---
    if state.startswith("sleepy"):
        _draw_zzz(draw, 24, 4)
    elif state == "alarm_ask":
        _fx_alarm(draw)
    elif state == "pet_love" or state == "care_2":
        _fx_hearts(draw)
    elif state == "care_1":
        _draw_heart(draw, 26, 11, P_PINK)
    elif state == "cheer" or state.startswith("celebrate") or state.startswith("tea_pillar"):
        _fx_stars(draw)
    elif state.startswith("thinking"):
        _fx_think(draw, 3 if state == "thinking_2" else 2)
    elif state.startswith("focus"):
        _fx_focus(draw)
        p_box(draw, 10, 11, 12, 11, P_DARK)
        p_box(draw, 19, 11, 21, 11, P_DARK)
        if state == "focus_2":
            p_box(draw, 25, 8, 26, 9, P_BLUE)
    elif state == "night_2":
        _draw_zzz(draw, 24, 4)
    elif state.startswith("night"):
        _fx_moon_night(draw)
    elif state == "reading_1" or state == "reading_2" or state == "stretch_2":
        pass

    # --- 読書の羊皮紙ノート ---
    if state.startswith("reading"):
        p_box(draw, 11, 22, 20, 27, K_NOTE)
        p_box(draw, 11, 22, 20, 22, P_TEA)
        p_box(draw, 13, 24, 18, 24, S_OUTLINE)
        if state == "reading_2":
            p_box(draw, 13, 26, 18, 26, S_OUTLINE)
            p(draw, 20, 21, P_WHITE)

    return img

# =============================================================================
# キノコ描画（深紅の赤水玉カサ ＋ まんまるメガネ ＋ 羽ペンと羊皮紙ノート）
# =============================================================================
def _kinoko_eyes(draw: ImageDraw.ImageDraw, state: str, look_dx: int = 0, look_dy: int = 0) -> None:
    """状態に応じたキノコ君の目（メガネのレンズ内）を描画する。"""
    ly = 21 + look_dy
    lx, rx_ = 12 + look_dx, 20 + look_dx
    if state == "happy" or state == "cheer" or state.startswith("night") or state.startswith("sleepy") or state == "tea_1" or state == "idle_2":
        # レンズ内の閉じ目（横線）
        p_box(draw, lx - 1, ly, lx + 1, ly, P_DARK)
        p_box(draw, rx_ - 1, ly, rx_ + 1, ly, P_DARK)
    elif state == "alarm_ask":
        # ビックリ目（レンズいっぱいの丸目）
        p_box(draw, lx - 1, ly - 1, lx + 1, ly + 1, P_DARK)
        p(draw, lx - 1, ly - 1, P_WHITE)
        p_box(draw, rx_ - 1, ly - 1, rx_ + 1, ly + 1, P_DARK)
        p(draw, rx_ - 1, ly - 1, P_WHITE)
    else:
        # 真面目なまんまる瞳
        p(draw, lx, ly, P_DARK)
        p(draw, lx - 1, ly - 1, P_WHITE)
        p(draw, rx_, ly, P_DARK)
        p(draw, rx_ - 1, ly - 1, P_WHITE)


def _kinoko_quill(draw: ImageDraw.ImageDraw, x: int, y: int, tip_dy: int = 1) -> None:
    """羽ペンを描画する（x,y は羽根の上端）。"""
    p_box(draw, x, y, x + 1, y + 3, K_FEATHER)
    p(draw, x, y + 4, P_DARK)
    p(draw, x, y + 5, P_DARK)
    p(draw, x + 1, y + 1, K_GLASS_IN)


def draw_kinoko(state: str) -> Image.Image:
    """森のちびっ子書記官キノコ君のスプライト1枚を生成する。

    Args:
        state (str): スプライト状態名（idle_1, writing_1 等）。

    Returns:
        Image.Image: 128x128 RGBA のドット絵スプライト。
    """
    img = Image.new("RGBA", (SIZE, SIZE), TRANSPARENT)
    draw = ImageDraw.Draw(img)
    look_dx, look_dy = _look(state)

    # カサの持ち上げ（ストレッチ・ジャンプで1px上昇）
    cap_cy = 12
    if state == "stretch_2" or state.startswith("celebrate"):
        cap_cy = 11

    # --- 白茎（角丸） ---
    p_box(draw, 10, 18, 21, 27, P_DARK)
    p_box(draw, 11, 18, 20, 26, K_STEM)
    p_box(draw, 11, 26, 20, 26, K_STEM_SH)

    # --- 深紅の赤水玉カサ ---
    p_ellipse(draw, 16, cap_cy, 13, 11, K_CAP, outline=P_DARK)
    p_box(draw, 5, cap_cy + 4, 27, cap_cy + 5, K_CAP_SH)
    p_box(draw, 8, cap_cy - 7, 11, cap_cy - 5, K_CAP_HI)
    # 水玉（クリーム白）
    p_box(draw, 20, cap_cy - 6, 21, cap_cy - 5, P_CREAM)
    p_box(draw, 15, cap_cy - 2, 16, cap_cy - 1, P_CREAM)
    p_box(draw, 10, cap_cy, 11, cap_cy + 1, P_CREAM)
    p_box(draw, 22, cap_cy - 1, 23, cap_cy, P_CREAM)

    # --- まんまるメガネ 👓 ---
    p_ellipse(draw, 12, 21, 3, 3, K_GLASS)
    p_ellipse(draw, 12, 21, 2, 2, K_GLASS_IN)
    p_ellipse(draw, 20, 21, 3, 3, K_GLASS)
    p_ellipse(draw, 20, 21, 2, 2, K_GLASS_IN)
    p_box(draw, 15, 20, 17, 20, K_GLASS)
    p(draw, 9, 21, K_GLASS)
    p(draw, 23, 21, K_GLASS)

    # --- ほっぺ＆口 ---
    p_box(draw, 11, 24, 12, 25, P_CHEEK)
    p_box(draw, 19, 24, 20, 25, P_CHEEK)
    p_box(draw, 15, 25, 16, 25, P_DARK)
    if state == "happy" or state == "cheer" or state.startswith("celebrate"):
        p_box(draw, 14, 25, 17, 25, P_DARK)
        p(draw, 15, 26, P_DARK)
        p(draw, 16, 26, P_DARK)

    # --- 羽ペン（通常は右脇に構える） ---
    if not state.startswith("writing"):
        p_box(draw, 23, 19, 24, 20, K_STEM)
        _kinoko_quill(draw, 25, 14)

    # --- 目（状態別） ---
    _kinoko_eyes(draw, state, look_dx, look_dy)

    # --- タスク記録（writing): 羊皮紙ノートに羽ペンでメモ ---
    if state.startswith("writing"):
        p_box(draw, 9, 24, 19, 28, K_NOTE)
        p_box(draw, 9, 24, 19, 24, P_DARK)
        p_box(draw, 11, 26, 17, 26, S_OUTLINE)
        if state == "writing_2":
            p_box(draw, 11, 28, 15, 28, S_OUTLINE)
            p_box(draw, 23, 19, 24, 20, K_STEM)
            _kinoko_quill(draw, 20, 15)
            p(draw, 22, 14, P_DARK)
            p(draw, 24, 13, P_DARK)
        else:
            p_box(draw, 23, 21, 24, 22, K_STEM)
            _kinoko_quill(draw, 19, 17)

    # --- 状態エフェクト ---
    if state.startswith("sleepy"):
        _draw_zzz(draw, 24, 4)
    elif state == "alarm_ask":
        _fx_alarm(draw)
    elif state == "pet_love" or state == "care_2":
        _fx_hearts(draw)
    elif state == "care_1":
        _draw_heart(draw, 26, 10, P_PINK)
    elif state == "cheer" or state.startswith("celebrate"):
        # カサから胞子星（✨）が飛び散る
        _fx_stars(draw)
        p(draw, 5, 10, P_GREEN)
        p(draw, 27, 8, P_GREEN)
        if state == "celebrate_2":
            p(draw, 3, 12, P_PINK)
        elif state == "celebrate_3":
            p(draw, 28, 12, P_YELLOW_L)
    elif state.startswith("thinking"):
        _fx_think(draw, 3 if state == "thinking_2" else 2)
        if state == "thinking_2":
            # 指先でメガネをクイッと押し上げる
            p_box(draw, 19, 18, 20, 19, K_STEM)
            p(draw, 20, 18, K_GLASS)
    elif state.startswith("focus"):
        _fx_focus(draw)
        p_box(draw, 10, 18, 14, 18, P_DARK)
        p_box(draw, 18, 18, 22, 18, P_DARK)
        if state == "focus_2":
            p_box(draw, 25, 7, 26, 8, P_BLUE)
    elif state == "night_2":
        _draw_zzz(draw, 24, 4)
    elif state.startswith("night"):
        _fx_moon_night(draw)
    elif state == "stretch_1":
        p(draw, 16, 1, P_DARK)
        p(draw, 14, 2, P_DARK)
        p(draw, 18, 2, P_DARK)
    elif state == "walk_1":
        p(draw, 6, 27, P_WHITE)
        p(draw, 7, 26, P_WHITE)
    elif state == "walk_2":
        p(draw, 25, 27, P_WHITE)
        p(draw, 24, 26, P_WHITE)
    elif state == "reading_1" or state == "reading_2":
        # 読書中: ノートをかかえてペラペラ
        p_box(draw, 12, 23, 21, 28, K_NOTE)
        p_box(draw, 12, 23, 21, 23, P_DARK)
        p_box(draw, 14, 25, 19, 25, S_OUTLINE)
        if state == "reading_2":
            p_box(draw, 14, 27, 19, 27, S_OUTLINE)
            p(draw, 22, 22, P_WHITE)
    elif state == "tea_1":
        p_box(draw, 4, 20, 7, 23, P_CREAM)
        p_box(draw, 4, 20, 7, 20, P_TEA)
        p(draw, 5, 18, P_WHITE)
    elif state == "tea_2":
        p_box(draw, 5, 25, 8, 27, P_CREAM)
        p_box(draw, 5, 25, 8, 25, P_TEA)

    return img

# =============================================================================
# メイン: 全キャラクター × 全状態のスプライト一括生成
# =============================================================================
RENDERERS: Dict[str, Callable[[str], Image.Image]] = {
    "marmot": draw_marmot,
    "seal": draw_seal,
    "kinoko": draw_kinoko,
}


CHARACTER_SPECIFIC_STATES: Dict[str, List[str]] = {
    "marmot": ["screaming_1", "screaming_2", "petting_1", "petting_2"],
    "seal": ["tea_pillar_1", "tea_pillar_2"],
    "kinoko": ["writing_1", "writing_2"],
}

STATES: Dict[str, List[str]] = {
    name: COMMON_STATES + CHARACTER_SPECIFIC_STATES[name]
    for name in RENDERERS
}


def upscale(img: Image.Image, scale: int) -> Image.Image:
    """最近傍補間で指定倍率に拡大する。"""
    return img.resize((SIZE * scale, SIZE * scale), Image.NEAREST)


def _dir_for(base: Path, name: str) -> Path:
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def main() -> None:
    """全スプライトを生成し、assets/dot 配下へ書き出す。"""
    base = Path(__file__).resolve().parent.parent / "assets" / "dot"
    total = 0
    for name, renderer in RENDERERS.items():
        out = _dir_for(base, name)
        states = STATES[name]
        for state in states:
            img = renderer(state)
            img.save(out / f"{state}.png")
            img.resize((32, 32), Image.NEAREST).save(out / f"{state}_32.png")
            img.resize((24, 24), Image.NEAREST).save(out / f"{state}_24.png")
            img.resize((20, 20), Image.NEAREST).save(out / f"{state}_20.png")
            total += 1
    print(f"Generated {total} sprites under assets/dot/")


if __name__ == "__main__":
    main()
