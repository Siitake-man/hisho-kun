"""
ネオ秘書くん - retro_dolphin / kyle スプライトジェネレーター v3

v2（横からのシルエット）をベースに、v3 で以下を追加:
- 歩行フレーム walk_1 / walk_2（テクテク歩き用の2コマ）
- kyle スタイル（強寄せバリアント）: ラベンダー蓝配色・直視の愛らしい目・
  ホタテ貝型ノートPC アクセサリー・丸みシルエット
  ※ Microsoft 公式画像の複製ではなく、特徴を参考にした完全自前ドット絵であること

出力先:
- retro: assets/retro_dolphin/ + assets/dot/retro_dolphin/
- kyle : assets/kyle/          + assets/dot/kyle/
"""

from pathlib import Path
from typing import Dict, List, Tuple
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT_DIRS: Dict[str, Tuple[Path, Path]] = {
    "retro": (ROOT / "assets" / "retro_dolphin", ROOT / "assets" / "dot" / "retro_dolphin"),
    "kyle": (ROOT / "assets" / "kyle", ROOT / "assets" / "dot" / "kyle"),
}
for _pair in OUT_DIRS.values():
    _pair[0].mkdir(parents=True, exist_ok=True)
    _pair[1].mkdir(parents=True, exist_ok=True)

GRID_SIZE = 48
SCALE = 3  # 出力サイズ: 144x144

C_TRANS = (0, 0, 0, 0)
C_WHITE_SOFT = (255, 255, 255, 220)
C_STAR = (255, 215, 0, 255)
C_GLITCH = (255, 90, 160, 255)
C_ANGER = (235, 60, 60, 255)

# スタイル別パレット
PALETTES: Dict[str, Dict[str, tuple]] = {
    "retro": {
        "outline": (35, 65, 95, 255),
        "body": (125, 200, 235, 255),
        "body_light": (185, 228, 248, 255),
        "belly": (225, 244, 250, 255),
        "visor": (25, 35, 60, 235),
        "visor_glow": (120, 240, 255, 255),
        "cheek": (255, 140, 150, 255),
        "bubble": (200, 240, 255, 180),
    },
    "kyle": {
        "outline": (52, 58, 110, 255),
        "body": (146, 168, 235, 255),
        "body_light": (198, 212, 248, 255),
        "belly": (242, 246, 255, 255),
        "visor": (52, 58, 110, 0),
        "visor_glow": (40, 44, 90, 255),
        "cheek": (255, 150, 160, 255),
        "bubble": (220, 228, 255, 180),
    },
}

STATES = ("idle", "appear", "offended", "revive", "walk_1", "walk_2")

# PC (gui.py) / PWA (pet.js) が要求するスプライト名 → 状態マッピング
SPRITE_NAME_MAP: Dict[str, str] = {
    "idle_1": "idle", "idle_2": "idle",
    "walk_1": "walk_1", "walk_2": "walk_2",
    "look_left": "idle", "look_right": "idle", "look_up": "idle", "look_down": "idle",
    "sleepy_1": "idle", "sleepy_2": "idle",
    "focus_1": "idle", "focus_2": "idle",
    "tea_1": "idle", "tea_2": "idle",
    "reading_1": "idle", "reading_2": "idle",
    "night_1": "idle", "night_2": "idle",
    "thinking_1": "offended", "thinking_2": "offended", "alarm_ask": "offended",
    "happy": "appear", "cheer": "appear", "pet_love": "appear",
    "celebrate_1": "appear", "celebrate_2": "appear", "celebrate_3": "appear",
    "care_1": "appear", "care_2": "appear",
    "stretch_1": "appear", "stretch_2": "appear",
}


def p(draw, x, y, color):
    """1ピクセル（SCALE倍）を描画する。"""
    if 0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE:
        draw.rectangle([x * SCALE, y * SCALE, (x + 1) * SCALE - 1, (y + 1) * SCALE - 1], fill=color)


def p_box(draw, x1, y1, x2, y2, color):
    """矩形塗りつぶし。"""
    for x in range(x1, x2 + 1):
        for y in range(y1, y2 + 1):
            p(draw, x, y, color)


def p_circle(draw, cx, cy, r, color):
    """ドット絵の丸を描画する。"""
    for x in range(cx - r, cx + r + 1):
        for y in range(cy - r, cy + r + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r ** 2:
                p(draw, x, y, color)


def p_pixels(draw, pts, color):
    """ピクセル列を描画する。"""
    for (x, y) in pts:
        p(draw, x, y, color)


def p_star(draw, cx, cy, r, color):
    """十字スターを描画する。"""
    for i in range(-r, r + 1):
        p(draw, cx + i, cy, color)
        p(draw, cx, cy + i, color)


def p_bubbles(draw, spots, color):
    """泡を複数描画する。"""
    for (bx, by, br) in spots:
        p_circle(draw, bx, by, br, color)
        p(draw, bx - br // 2, by - br // 2, C_WHITE_SOFT)


def _fluke_points() -> List[Tuple[int, int]]:
    """尾びれ（上・下のフーク）のピクセル列を返す。"""
    upper = [
        (39, 24), (40, 23), (40, 24), (41, 22), (41, 23),
        (42, 21), (42, 22), (43, 20), (43, 21), (44, 19), (44, 20),
    ]
    return upper + [(x, 52 - y) for (x, y) in upper]



def draw_dolphin(state: str, style: str = "retro") -> Image.Image:
    """指定スタイル・状態のスプライト（横からのシルエット）を描画します。

    Args:
        state: idle / appear / offended / revive / walk_1 / walk_2 のいずれか。
        style: 'retro'（バイザー付き案内精霊）または 'kyle'（貝型PCのカイル寄せ）。

    Returns:
        Image.Image: 144x144 の透過 PNG イメージ。

    Raises:
        ValueError: 未定義の状態・スタイルが指定された場合。
    """
    if state not in STATES:
        raise ValueError(f"未定義の状態です: {state}")
    if style not in PALETTES:
        raise ValueError(f"未定義のスタイルです: {style}")

    pal = PALETTES[style]
    c_outline = pal["outline"]
    c_body = pal["body"]
    c_light = pal["body_light"]
    c_belly = pal["belly"]
    c_cheek = pal["cheek"]

    img = Image.new("RGBA", (GRID_SIZE * SCALE, GRID_SIZE * SCALE), C_TRANS)
    draw = ImageDraw.Draw(img)

    # 縦オフセット: appear/revive は浮上、walk は歩行バウンス
    lift = 2 if state in ("appear", "revive") else (1 if state == "walk_2" else 0)

    def dy(y: int) -> int:
        return y - lift

    # ---- 1) 輪郭パス ----
    p_circle(draw, 15, dy(26), 8, c_outline)
    p_circle(draw, 24, dy(26), 9, c_outline)
    p_circle(draw, 30, dy(26), 7, c_outline)
    p_box(draw, 4, dy(24), 12, dy(29), c_outline)
    p_box(draw, 34, dy(23), 40, dy(29), c_outline)
    p_pixels(draw, [(x + 1, dy(y)) for (x, y) in _fluke_points()] + _fluke_points(), c_outline)

    fin_outline: List[Tuple[int, int]] = []
    for col, (top, bottom) in ((20, (17, 20)), (21, (15, 20)), (22, (13, 20)), (23, (12, 20)), (24, (13, 20)), (25, (15, 20)), (26, (17, 20))):
        for yy in range(top, bottom + 1):
            fin_outline.append((col, dy(yy)))
    p_pixels(draw, [(x + 1, y) for (x, y) in fin_outline] + [(x - 1, y) for (x, y) in fin_outline] + fin_outline, c_outline)

    # 胸びれ（歩行フレームでは前後に振る）
    pect_cols = ((17, (33, 36)), (18, (33, 37)), (19, (33, 37)))
    if state == "walk_1":
        pect_cols = ((16, (33, 36)), (17, (33, 37)), (18, (33, 37)), (19, (33, 36)))
    elif state == "walk_2":
        pect_cols = ((18, (33, 36)), (19, (33, 37)), (20, (33, 37)), (21, (33, 36)))
    pect_outline: List[Tuple[int, int]] = []
    for col, (top, bottom) in pect_cols:
        for yy in range(top, bottom + 1):
            pect_outline.append((col, dy(yy)))
    p_pixels(draw, [(x + 1, y) for (x, y) in pect_outline] + [(x - 1, y) for (x, y) in pect_outline] + pect_outline, c_outline)

    # ---- 2) ボディパス ----
    p_box(draw, 6, dy(25), 11, dy(28), c_body)
    p_circle(draw, 15, dy(26), 7, c_body)
    p_circle(draw, 24, dy(26), 8, c_body)
    p_circle(draw, 30, dy(26), 6, c_body)
    p_box(draw, 35, dy(24), 39, dy(28), c_body)
    p_pixels(draw, _fluke_points(), c_body)

    for x in range(14, 30):
        p(draw, x, dy(19), c_light)
    for x in range(18, 28):
        p(draw, x, dy(18), c_light)

    for x in range(9, 33):
        for y in range(29, 34):
            yy = dy(y)
            inside = ((x - 15) ** 2 + (yy - dy(26)) ** 2 <= 49
                      or (x - 24) ** 2 + (yy - dy(26)) ** 2 <= 64
                      or (x - 30) ** 2 + (yy - dy(26)) ** 2 <= 36
                      or (6 <= x <= 11 and 25 <= y <= 28))
            if inside:
                p(draw, x, yy, c_belly)

    fin_fill: List[Tuple[int, int]] = []
    for col, (top, bottom) in ((21, (16, 20)), (22, (14, 20)), (23, (13, 20)), (24, (14, 20)), (25, (16, 20))):
        for yy in range(top, bottom + 1):
            fin_fill.append((col, dy(yy)))
    p_pixels(draw, fin_fill, c_body)
    pect_fill: List[Tuple[int, int]] = []
    for col, (top, bottom) in pect_cols:
        for yy in range(top, bottom + 1):
            pect_fill.append((col, dy(yy)))
    p_pixels(draw, pect_fill, c_body)

    # ---- 3) 顔: retro はバイザー / kyle は直視の愛らしい目 ----
    if style == "retro":
        p_box(draw, 8, dy(21), 20, dy(25), c_outline)
        p_box(draw, 9, dy(22), 19, dy(24), pal["visor"])
        p(draw, 9, dy(22), pal["visor_glow"])
        p(draw, 19, dy(24), pal["visor_glow"])
        if state == "offended":
            p_pixels(draw, [(12, dy(24)), (13, dy(23)), (14, dy(23))], pal["visor_glow"])
            p_pixels(draw, [(11, dy(23)), (12, dy(22))], pal["visor_glow"])
        elif state == "revive":
            p_box(draw, 12, dy(22), 14, dy(24), pal["visor_glow"])
            p(draw, 13, dy(23), c_body)
        else:
            p_pixels(draw, [(12, dy(23)), (13, dy(23)), (14, dy(23))], pal["visor_glow"])
            p(draw, 11, dy(22), pal["visor_glow"])
            p(draw, 15, dy(22), pal["visor_glow"])
    else:
        # kyle: 大きめの丸い黒目 + ハイライト（バイザーなしで直視）
        eye_y = dy(23)
        p_circle(draw, 13, eye_y, 2, pal["visor_glow"])
        p_circle(draw, 13, eye_y - 1, 1, C_WHITE_SOFT)
        if state == "offended":
            p_pixels(draw, [(11, dy(21)), (12, dy(22)), (15, dy(21)), (14, dy(22))], c_outline)
        elif state == "revive":
            p_pixels(draw, [(12, dy(23)), (14, dy(23)), (13, dy(22))], C_WHITE_SOFT)

    # ほっぺ
    p_box(draw, 15, dy(28), 17, dy(29), c_cheek)

    # 口元
    if state == "offended":
        p_pixels(draw, [(4, dy(29)), (5, dy(30)), (6, dy(30)), (7, dy(30)), (8, dy(29))], c_outline)
    else:
        p_pixels(draw, [(4, dy(29)), (5, dy(29)), (6, dy(29)), (7, dy(29))], c_outline)
        p(draw, 8, dy(30), c_outline)


    # ---- 4) 状態別エフェクト ----
    if state == "idle":
        p_bubbles(draw, [(4, dy(16), 1), (8, dy(12), 2), (2, dy(22), 1)], pal["bubble"])
    elif state == "appear":
        p_bubbles(draw, [(4, dy(14), 1), (8, dy(10), 2), (2, dy(20), 1), (42, dy(12), 1)], pal["bubble"])
        p_star(draw, 24, dy(8), 3, C_STAR)
        p_star(draw, 6, dy(28), 2, C_STAR)
        p_star(draw, 44, dy(28), 2, C_STAR)
    elif state == "offended":
        p_pixels(draw, [(14, dy(10)), (15, dy(11)), (16, dy(12)), (18, dy(12)), (19, dy(11)), (20, dy(10)), (16, dy(9)), (17, dy(9)), (18, dy(9))], C_ANGER)
    elif state == "revive":
        for gx, gy in ((10, dy(14)), (34, dy(12)), (8, dy(32)), (40, dy(34)), (24, dy(10)), (12, dy(24)), (36, dy(24)), (44, dy(16))):
            p(draw, gx, gy, C_GLITCH)
        p_star(draw, 24, dy(7), 3, C_STAR)
        p_bubbles(draw, [(6, dy(18), 1), (42, dy(20), 1)], pal["bubble"])
    elif state in ("walk_1", "walk_2"):
        # 歩行の砂煙（後脚元）
        p_pixels(draw, [(36, dy(31)), (37, dy(32)), (35, dy(32))], C_WHITE_SOFT)
        if state == "walk_1":
            p_bubbles(draw, [(3, dy(18), 1)], pal["bubble"])

    return img


def main() -> None:
    """retro / kyle 両スタイルの全状態スプライトを生成し保存します。"""
    total = 0
    for style, (asset_dir, dot_dir) in OUT_DIRS.items():
        rendered = {state: draw_dolphin(state, style) for state in STATES}
        for state, img in rendered.items():
            out = asset_dir / f"{style}_{state}.png"
            img.save(out, "PNG")
            total += 1
        for sprite_name, state in SPRITE_NAME_MAP.items():
            rendered[state].save(dot_dir / f"{sprite_name}.png", "PNG")
            total += 1
        print(f"[{style}] states={len(STATES)} name_variants={len(SPRITE_NAME_MAP)} -> {dot_dir}")
    print(f"v3 done: {total} files")


if __name__ == "__main__":
    main()
