"""
ネオ秘書くん - retro_dolphin（レトロ案内精霊）スプライトジェネレーター v2

v1（正面視）は「イルカに見えない」というボス判定を受け、
v2 では横からのシルエット（口吻・背びれ・胸びれ・尾びれ）で
一見してイルカとわかる形に全面リデザインした。

既存の Kawaii Pixel Art 4.0 規約（48x48 グリッド / SCALE=3 / 透過背景）に準拠し、
Phase L の新キャラクター retro_dolphin の 4 状態（idle / appear / offended / revive）を生成する。
出力先: assets/retro_dolphin/retro_dolphin_{state}.png

注意: Microsoft 製キャラの複製ではなく、完全オリジナルのデザインであること。
"""

from pathlib import Path
from typing import Dict, List, Tuple
from PIL import Image, ImageDraw

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "retro_dolphin"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
DOT_DIR = Path(__file__).resolve().parent.parent / "assets" / "dot" / "retro_dolphin"

GRID_SIZE = 48
SCALE = 3  # 出力サイズ: 144x144

C_TRANS = (0, 0, 0, 0)
C_OUTLINE = (35, 65, 95, 255)        # 深藍系輪郭
C_BODY = (125, 200, 235, 255)        # 水色ボディ
C_BODY_LIGHT = (185, 228, 248, 255)  # 背中ハイライト
C_BELLY = (225, 244, 250, 255)       # 腹部
C_VISOR = (25, 35, 60, 235)          # ガジェット風バイザー
C_VISOR_GLOW = (120, 240, 255, 255)  # バイザー上の目のグロウ
C_BUBBLE = (200, 240, 255, 180)      # 泡
C_WHITE_SOFT = (255, 255, 255, 220)
C_GLITCH = (255, 90, 160, 255)       # グリッチピクセル
C_STAR = (255, 215, 0, 255)          # 星
C_ANGER = (235, 60, 60, 255)         # 怒りマーク

Point = Tuple[int, int]


def p(draw: ImageDraw.ImageDraw, x: int, y: int, color) -> None:
    """1ピクセル（SCALE倍）を描画する。"""
    if 0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE:
        draw.rectangle([x * SCALE, y * SCALE, (x + 1) * SCALE - 1, (y + 1) * SCALE - 1], fill=color)


def p_box(draw: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int, color) -> None:
    """矩形塗りつぶし。"""
    for x in range(x1, x2 + 1):
        for y in range(y1, y2 + 1):
            p(draw, x, y, color)


def p_circle(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color) -> None:
    """ドット絵の丸を描画する。"""
    for x in range(cx - r, cx + r + 1):
        for y in range(cy - r, cy + r + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r ** 2:
                p(draw, x, y, color)


def p_pixels(draw: ImageDraw.ImageDraw, pts: List[Point], color) -> None:
    """ピクセル列を描画する。"""
    for (x, y) in pts:
        p(draw, x, y, color)


def p_star(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color) -> None:
    """十字スターを描画する（登場演出・復活演出用）。"""
    for i in range(-r, r + 1):
        p(draw, cx + i, cy, color)
        p(draw, cx, cy + i, color)


def p_bubbles(draw: ImageDraw.ImageDraw, spots: List[Tuple[int, int, int]]) -> None:
    """案内精霊の泡を複数描画する。"""
    for (bx, by, br) in spots:
        p_circle(draw, bx, by, br, C_BUBBLE)
        p(draw, bx - br // 2, by - br // 2, C_WHITE_SOFT)


def _dolphin_silhouette_points() -> List[Point]:
    """尾びれ（上・下のフーク）のピクセル列を返す。"""
    upper: List[Point] = [
        (39, 24), (40, 23), (40, 24), (41, 22), (41, 23),
        (42, 21), (42, 22), (43, 20), (43, 21), (44, 19), (44, 20),
    ]
    lower = [(x, 52 - y) for (x, y) in upper]  # y=26 を軸に上下対称
    return upper + lower


def draw_retro_dolphin(state: str) -> Image.Image:
    """retro_dolphin の 1 状態分スプライト（横からのシルエット）を描画する。

    Args:
        state (str): idle / appear / offended / revive のいずれか。

    Returns:
        Image.Image: 144x144 の透過 PNG イメージ。

    Raises:
        ValueError: 未定義の状態が指定された場合。
    """
    if state not in ("idle", "appear", "offended", "revive"):
        raise ValueError(f"未定義の状態です: {state}")

    img = Image.new("RGBA", (GRID_SIZE * SCALE, GRID_SIZE * SCALE), C_TRANS)
    draw = ImageDraw.Draw(img)

    # appear / revive では浮上表現として 2px 上にずらす
    lift = 2 if state in ("appear", "revive") else 0

    def dy(y: int) -> int:
        return y - lift

    # ---- 1) 輪郭パス（シルエット全体を輪郭色で先に描く） ----
    p_circle(draw, 15, dy(26), 8, C_OUTLINE)            # 頭部（額のめろん）
    p_circle(draw, 24, dy(26), 9, C_OUTLINE)            # 体幹
    p_circle(draw, 30, dy(26), 7, C_OUTLINE)            # 後半身
    p_box(draw, 4, dy(24), 12, dy(29), C_OUTLINE)       # 口吻（ロストルム）
    p_box(draw, 34, dy(23), 40, dy(29), C_OUTLINE)      # 尾柄
    p_pixels(draw, [(x + 1, dy(y)) for (x, y) in _dolphin_silhouette_points()] + _dolphin_silhouette_points(), C_OUTLINE)  # 尾びれ

    # 背びれ（反りのある三日月フィン）
    fin_outline: List[Point] = []
    for col, (top, bottom) in ((20, (17, 20)), (21, (15, 20)), (22, (13, 20)), (23, (12, 20)), (24, (13, 20)), (25, (15, 20)), (26, (17, 20))):
        for yy in range(top, bottom + 1):
            fin_outline.append((col, dy(yy)))
    p_pixels(draw, [(x + 1, y) for (x, y) in fin_outline] + [(x - 1, y) for (x, y) in fin_outline] + fin_outline, C_OUTLINE)

    # 胸びれ（腹側の小さなパドル）
    pect_outline: List[Point] = []
    for col, (top, bottom) in ((17, (33, 36)), (18, (33, 37)), (19, (33, 37)), (20, (33, 36))):
        for yy in range(top, bottom + 1):
            pect_outline.append((col, dy(yy)))
    p_pixels(draw, [(x + 1, y) for (x, y) in pect_outline] + [(x - 1, y) for (x, y) in pect_outline] + pect_outline, C_OUTLINE)

    # ---- 2) ボディパス（輪郭の内側を塗る） ----
    p_box(draw, 6, dy(25), 11, dy(28), C_BODY)          # 口吻
    p_circle(draw, 15, dy(26), 7, C_BODY)               # 頭部
    p_circle(draw, 24, dy(26), 8, C_BODY)               # 体幹
    p_circle(draw, 30, dy(26), 6, C_BODY)               # 後半身
    p_box(draw, 35, dy(24), 39, dy(28), C_BODY)         # 尾柄
    p_pixels(draw, _dolphin_silhouette_points(), C_BODY)  # 尾びれ

    # 背中ハイライト
    for x in range(14, 30):
        p(draw, x, dy(19), C_BODY_LIGHT)
    for x in range(18, 28):
        p(draw, x, dy(18), C_BODY_LIGHT)

    # 腹部（明色）
    for x in range(9, 33):
        for y in range(29, 34):
            yy = dy(y)
            inside = ((x - 15) ** 2 + (yy - dy(26)) ** 2 <= 49
                      or (x - 24) ** 2 + (yy - dy(26)) ** 2 <= 64
                      or (x - 30) ** 2 + (yy - dy(26)) ** 2 <= 36
                      or (6 <= x <= 11 and 25 <= y <= 28))
            if inside:
                p(draw, x, yy, C_BELLY)

    # 背びれ・胸びれ（内側）
    fin_fill: List[Point] = []
    for col, (top, bottom) in ((21, (16, 20)), (22, (14, 20)), (23, (13, 20)), (24, (14, 20)), (25, (16, 20))):
        for yy in range(top, bottom + 1):
            fin_fill.append((col, dy(yy)))
    p_pixels(draw, fin_fill, C_BODY)
    pect_fill: List[Point] = []
    for col, (top, bottom) in ((18, (33, 36)), (19, (33, 36))):
        for yy in range(top, bottom + 1):
            pect_fill.append((col, dy(yy)))
    p_pixels(draw, pect_fill, C_BODY)

    # ---- 3) バイザー（頭部〜体前部のガジェット風バンド） ----
    p_box(draw, 8, dy(21), 20, dy(25), C_OUTLINE)
    p_box(draw, 9, dy(22), 19, dy(24), C_VISOR)
    # バイザー端の光
    p(draw, 9, dy(22), C_VISOR_GLOW)
    p(draw, 19, dy(24), C_VISOR_GLOW)

    # ---- 4) 目（状態ごと） ----
    if state == "offended":
        # つり目（前傾）
        p_pixels(draw, [(12, dy(24)), (13, dy(23)), (14, dy(23))], C_VISOR_GLOW)
        p_pixels(draw, [(11, dy(23)), (12, dy(22))], C_VISOR_GLOW)
    elif state == "revive":
        # 再構築中の乱れ点滅目
        p_box(draw, 12, dy(22), 14, dy(24), C_VISOR_GLOW)
        p(draw, 13, dy(23), C_BODY)
    else:
        # idle / appear: にこにこアーチ目
        p_pixels(draw, [(12, dy(23)), (13, dy(23)), (14, dy(23))], C_VISOR_GLOW)
        p(draw, 11, dy(22), C_VISOR_GLOW)
        p(draw, 15, dy(22), C_VISOR_GLOW)

    # ---- 5) 口元（口吻の下） ----
    if state == "offended":
        p_pixels(draw, [(4, dy(29)), (5, dy(30)), (6, dy(30)), (7, dy(30)), (8, dy(29))], C_OUTLINE)
    else:
        p_pixels(draw, [(4, dy(29)), (5, dy(29)), (6, dy(29)), (7, dy(29))], C_OUTLINE)
        p(draw, 8, dy(30), C_OUTLINE)  # 微かなほほえみの上がり

    # ---- 6) 状態別エフェクト ----
    if state == "idle":
        p_bubbles(draw, [(4, dy(16), 1), (8, dy(12), 2), (2, dy(22), 1)])
    elif state == "appear":
        p_bubbles(draw, [(4, dy(14), 1), (8, dy(10), 2), (2, dy(20), 1), (6, dy(38), 1), (42, dy(12), 1)])
        p_star(draw, 24, dy(8), 3, C_STAR)
        p_star(draw, 6, dy(28), 2, C_STAR)
        p_star(draw, 44, dy(28), 2, C_STAR)
    elif state == "offended":
        # 怒りマーク（頭上）
        p_pixels(draw, [(14, dy(10)), (15, dy(11)), (16, dy(12)), (18, dy(12)), (19, dy(11)), (20, dy(10)), (16, dy(9)), (17, dy(9)), (18, dy(9))], C_ANGER)
    elif state == "revive":
        for gx, gy in ((10, dy(14)), (34, dy(12)), (8, dy(32)), (40, dy(34)), (24, dy(10)), (12, dy(24)), (36, dy(24)), (44, dy(16))):
            p(draw, gx, gy, C_GLITCH)
        p_star(draw, 24, dy(7), 3, C_STAR)
        p_bubbles(draw, [(6, dy(18), 1), (42, dy(20), 1)])

    return img


# PC (gui.py _load_mascot_assets) / PWA (pet.js preloadSprites) が要求する
# スプライト名 → retro_dolphin の4状態へのマッピング（未実装状態は近い状態で代用）
SPRITE_NAME_MAP: Dict[str, str] = {
    "idle_1": "idle", "idle_2": "idle",
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


def main() -> None:
    """4 状態を生成し assets/retro_dolphin/ と assets/dot/retro_dolphin/ へ保存する。"""
    states = ("idle", "appear", "offended", "revive")
    rendered = {state: draw_retro_dolphin(state) for state in states}
    for state, img in rendered.items():
        out = ASSETS_DIR / f"retro_dolphin_{state}.png"
        img.save(out, "PNG")
        print(f"saved: {out} ({img.width}x{img.height})")
    DOT_DIR.mkdir(parents=True, exist_ok=True)
    for sprite_name, state in SPRITE_NAME_MAP.items():
        rendered[state].save(DOT_DIR / f"{sprite_name}.png", "PNG")
    print(f"exported {len(SPRITE_NAME_MAP)} sprite name variants to {DOT_DIR}")


if __name__ == "__main__":
    main()
