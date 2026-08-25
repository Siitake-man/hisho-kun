"""
ネオ秘書くん - 秘書くんドット絵 追加13状態 生成ツール
(generate_dot_hisho_extra.py)

assets/dot/hisho/idle_1.png（8/15レトロドット絵）をベースに、
お茶・読書・ストレッチ・お祝い・心配・夜の13状態をエフェクト合成で生成する。
シルエットはベース画像と完全一致し、テイストが統一される。

使い方:
    venv\\Scripts\\python.exe tools\\generate_dot_hisho_extra.py
"""

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance

logger = logging.getLogger("generate_dot_hisho_extra")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# ※ 本スクリプトは tools/ 配下にあるため、プロジェクトルートは2階層上
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
DOT_HISHO = ASSETS_DIR / "dot" / "hisho"

# --- 8/15版と同一のレトロパレット（エフェクト用） ---
P_YELLOW = (230, 210, 53, 255)
P_BLUE = (144, 202, 249, 255)
P_PINK = (233, 30, 99, 255)
P_YELLOW_L = (255, 235, 59, 255)
P_ORANGE = (255, 112, 67, 255)
P_CREAM = (245, 245, 220, 255)
P_DARK = (74, 59, 50, 255)
P_CUP = (250, 245, 235, 255)
P_TEA = (100, 200, 120, 255)
TRANSPARENT = (0, 0, 0, 0)


def _load_base() -> Image.Image:
    """ベース画像（idle_1）を読み込む。"""
    return Image.open(DOT_HISHO / "idle_1.png").convert("RGBA")


def _star(draw: ImageDraw.ImageDraw, cx: int, cy: int, s: int, color) -> None:
    """菱形スターを描画する（128px座標系）。"""
    draw.polygon([(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)], fill=color)


def _confetti(draw: ImageDraw.ImageDraw, cx: int, cy: int, color) -> None:
    """紙吹雪の小片を描画する。"""
    draw.rectangle([cx, cy, cx + 5, cy + 5], fill=color)


def _cup(draw: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    """お茶カップ＋湯気を描画する（128px座標系）。"""
    # 本体
    draw.rectangle([cx - 14, cy - 10, cx + 12, cy + 10], fill=P_CUP, outline=P_DARK, width=3)
    # お茶
    draw.rectangle([cx - 11, cy - 7, cx + 9, cy - 4], fill=P_TEA)
    # 取っ手
    draw.arc([cx + 12, cy - 7, cx + 26, cy + 7], start=-75, end=75, fill=P_DARK, width=3)


def _steam(draw: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    """湯気を描画する。"""
    draw.arc([cx - 6, cy - 16, cx + 2, cy - 6], start=90, end=270, fill=(220, 220, 220, 220), width=2)
    draw.arc([cx + 2, cy - 20, cx + 10, cy - 10], start=90, end=270, fill=(220, 220, 220, 220), width=2)


def _book(draw: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    """開いた本を描画する（128px座標系）。"""
    # 表紙
    draw.polygon([(cx - 30, cy + 12), (cx, cy + 4), (cx + 30, cy + 12), (cx, cy + 20)], fill=P_BLUE, outline=P_DARK)
    # ページ
    draw.polygon([(cx - 26, cy + 10), (cx, cy + 3), (cx + 26, cy + 10), (cx, cy + 17)], fill=P_CREAM)
    # 中央の綴じ線
    draw.line([cx, cy + 3, cx, cy + 17], fill=P_DARK, width=2)


def _moon(draw: ImageDraw.ImageDraw, img: Image.Image, cx: int, cy: int, r: int) -> None:
    """三日月を描画する（透明で欠けを作る）。"""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=P_CREAM)
    eraser = ImageDraw.Draw(img)
    eraser.ellipse([cx - r // 2, cy - r - 3, cx + r + r // 2, cy + r - 3], fill=TRANSPARENT)


# =============================================================================
# 状態ごとの生成関数
# =============================================================================
def make_tea(frame: int) -> Image.Image:
    """🍵 お茶タイム（カップ＋湯気）。"""
    base = _load_base()
    draw = ImageDraw.Draw(base)
    if frame == 0:
        _cup(draw, 96, 92)
        _steam(draw, 92, 78)
    else:
        _cup(draw, 30, 92)
        _steam(draw, 28, 78)
    return base


def make_reading(frame: int) -> Image.Image:
    """📖 読書タイム（開いた本）。"""
    base = _load_base()
    draw = ImageDraw.Draw(base)
    _book(draw, 64, 96)
    if frame == 1:
        # ページめくり中の小片
        draw.polygon([(70, 96), (80, 88), (82, 98)], fill=P_CREAM)
    return base


def make_stretch(frame: int) -> Image.Image:
    """🤸 背伸び（縦方向リサイズ＋星）。"""
    base = _load_base()
    w, h = base.size
    if frame == 0:
        # 伸びる（縦1.08倍）
        resized = base.resize((int(w * 0.92), int(h * 1.08)), Image.NEAREST)
    else:
        # しまる（縦0.92倍）
        resized = base.resize((int(w * 1.04), int(h * 0.92)), Image.NEAREST)
    canvas = Image.new("RGBA", (w, h), TRANSPARENT)
    canvas.paste(resized, ((w - resized.width) // 2, (h - resized.height) // 2), resized)
    draw = ImageDraw.Draw(canvas)
    _star(draw, 20, 16, 7, P_YELLOW_L)
    _star(draw, 108, 20, 7, P_YELLOW_L)
    return canvas


def make_celebrate(frame: int) -> Image.Image:
    """🎉 お祝い（星＋紙吹雪）。位置はフレームごとに変化。"""
    base = _load_base()
    draw = ImageDraw.Draw(base)
    star_positions = [
        [(24, 14), (104, 18), (64, 6)],
        [(18, 22), (110, 10), (64, 12)],
        [(30, 8), (98, 24), (50, 4), (84, 6)],
    ]
    for sx, sy in star_positions[frame % len(star_positions)]:
        _star(draw, sx, sy, 9, P_YELLOW_L)
    confetti_colors = [P_ORANGE, P_PINK, P_YELLOW_L]
    confetti_positions = [
        [(14, 40), (114, 34), (40, 8), (90, 50)],
        [(20, 50), (108, 44), (56, 4), (76, 40)],
        [(12, 30), (116, 20), (34, 46), (94, 12), (64, 30)],
    ]
    for i, (cx, cy) in enumerate(confetti_positions[frame % len(confetti_positions)]):
        _confetti(draw, cx, cy, confetti_colors[i % len(confetti_colors)])
    return base


def make_care(frame: int) -> Image.Image:
    """😟 心配（！マーク＋汗）。"""
    base = _load_base()
    draw = ImageDraw.Draw(base)
    if frame == 0:
        # ！マーク（右上）
        draw.rectangle([104, 10, 112, 34], fill=P_YELLOW)
        draw.rectangle([104, 40, 112, 46], fill=P_YELLOW)
        # 汗（左上・水色の雫）
        draw.ellipse([16, 12, 26, 28], fill=P_BLUE)
    else:
        # ！マーク（左上）
        draw.rectangle([16, 10, 24, 34], fill=P_YELLOW)
        draw.rectangle([16, 40, 24, 46], fill=P_YELLOW)
        # 汗（右上）
        draw.ellipse([102, 12, 112, 28], fill=P_BLUE)
    return base


def make_night(frame: int) -> Image.Image:
    """🌙 夜（暗色化＋月と星）。"""
    base = ImageEnhance.Brightness(_load_base()).enhance(0.55)
    draw = ImageDraw.Draw(base)
    if frame == 0:
        _moon(draw, base, 104, 20, 14)
        _star(draw, 24, 14, 6, P_YELLOW_L)
        _star(draw, 44, 8, 5, P_YELLOW_L)
    else:
        _moon(draw, base, 24, 18, 14)
        _star(draw, 104, 12, 6, P_YELLOW_L)
        _star(draw, 84, 6, 5, P_YELLOW_L)
        # ZZZ（睡眠ブルーの小片）
        draw.rectangle([60, 6, 68, 10], fill=P_BLUE)
        draw.rectangle([70, 12, 78, 16], fill=P_BLUE)
    return base


# =============================================================================
# 一括生成
# =============================================================================
GENERATORS = {
    "tea_1": lambda: make_tea(0), "tea_2": lambda: make_tea(1),
    "reading_1": lambda: make_reading(0), "reading_2": lambda: make_reading(1),
    "stretch_1": lambda: make_stretch(0), "stretch_2": lambda: make_stretch(1),
    "celebrate_1": lambda: make_celebrate(0), "celebrate_2": lambda: make_celebrate(1),
    "celebrate_3": lambda: make_celebrate(2),
    "care_1": lambda: make_care(0), "care_2": lambda: make_care(1),
    "night_1": lambda: make_night(0), "night_2": lambda: make_night(1),
}


def generate_all() -> None:
    """追加13状態のスプライトを一括生成し assets/dot/hisho/ へ保存する。"""
    for name, maker in GENERATORS.items():
        img = maker()
        out_path = DOT_HISHO / f"{name}.png"
        img.save(out_path, "PNG")
        logger.info(f"✓ {name}.png 生成完了")
    logger.info(f"🎉 合計 {len(GENERATORS)} 枚の追加状態を生成完了！（dot/hisho 計29状態）")


if __name__ == "__main__":
    generate_all()