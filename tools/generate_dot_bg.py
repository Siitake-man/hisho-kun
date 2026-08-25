# -*- coding: utf-8 -*-
"""
ネオ秘書くん - ドット絵背景生成ツール (generate_dot_bg.py)

5テーマ（書斎/カフェ/森/海/サイバー）のレトロドット絵背景を
キャラと同じ11色パレットで生成し、assets/dot/bg/ へ出力する。
480x480 px（48x48グリッド × 10ドット拡大）。
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

# 出力設定
SCALE = 10
W, H = 48, 48  # グリッドサイズ
OUT_W, OUT_H = W * SCALE, H * SCALE

# --- 8/15版と同一のレトロパレット ---
P_DARK = (74, 59, 50, 255)        # 輪郭・影
P_CREAM = (245, 245, 220, 255)    # クリーム白
P_CHEEK = (239, 154, 154, 255)    # ほっぺピンク
P_YELLOW = (230, 210, 53, 255)    # 黄
P_BLUE = (144, 202, 249, 255)     # 水色
P_PINK = (233, 30, 99, 255)       # ハート
P_YELLOW_L = (255, 235, 59, 255)  # 星
P_ORANGE = (255, 112, 67, 255)    # オレンジ
# 追加背景色
P_SKIN = (255, 224, 178, 255)      # 壁・肌色
P_GREEN = (102, 187, 106, 255)     # 緑（森）
P_WATER = (66, 165, 245, 255)      # 水色（海）
P_NEON = (0, 229, 255, 255)        # シアンネオン
P_BG = (30, 20, 15, 255)           # 暗背景ベース
P_BG2 = (50, 35, 25, 255)          # 明るめ暗背景
P_RED = (229, 57, 53, 255)         # 赤（アクセント）

OUT_DIR = Path(__file__).parent.parent / "assets" / "dot" / "bg"


def draw_rect(img, x, y, w, h, color):
    """指定座標に矩形を描画（グリッド座標）。"""
    for dy in range(h):
        for dx in range(w):
            px, py = x + dx, y + dy
            if 0 <= px < W and 0 <= py < H:
                img.putpixel((px, py), color)


def draw_line_v(img, x, y, h, color):
    """垂直線（x, y起点 高さh）。"""
    for dy in range(h):
        if 0 <= y + dy < H:
            img.putpixel((x, y + dy), color)


def draw_line_h(img, y, x, w, color):
    """水平線（y, x起点 幅w）。"""
    for dx in range(w):
        if 0 <= x + dx < W:
            img.putpixel((x + dx, y), color)


def draw_circle(img, cx, cy, r, color):
    """塗りつぶし円。"""
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r:
                px, py = cx + dx, cy + dy
                if 0 <= px < W and 0 <= py < H:
                    img.putpixel((px, py), color)


def draw_fill(img, color):
    """画面全体を塗りつぶす。"""
    for y in range(H):
        for x in range(W):
            img.putpixel((x, y), color)


# =============================================================================
# 各テーマの描画
# =============================================================================

def draw_room(img):
    """書斎: 暖炉＋本棚＋机"""
    draw_fill(img, P_BG)
    draw_rect(img, 0, 30, W, 18, P_BG2)
    draw_rect(img, 18, 16, 12, 18, P_DARK)
    draw_rect(img, 20, 20, 8, 12, P_ORANGE)
    draw_rect(img, 22, 22, 4, 8, P_YELLOW)
    for i in range(4):
        draw_rect(img, 2, 6 + i * 5, 11, 4, P_BG2)
        draw_rect(img, 3, 7 + i * 5, 3, 2, P_CREAM)
        draw_rect(img, 7, 7 + i * 5, 4, 2, P_CHEEK)
        draw_rect(img, 35, 6 + i * 5, 11, 4, P_BG2)
        draw_rect(img, 36, 7 + i * 5, 4, 2, P_BLUE)
        draw_rect(img, 41, 7 + i * 5, 3, 2, P_YELLOW)
    draw_rect(img, 14, 2, 6, 8, P_BLUE)
    draw_rect(img, 14, 2, 6, 8, P_DARK)
    draw_line_h(img, 6, 14, 6, P_DARK)
    draw_line_v(img, 17, 2, 8, P_DARK)
    draw_rect(img, 12, 40, 24, 2, P_DARK)
    draw_rect(img, 14, 42, 20, 6, P_BG2)


def draw_cafe(img):
    """カフェ: 窓＋テーブル＋カップ"""
    draw_fill(img, P_BG)
    draw_rect(img, 0, 0, W, H, P_BG2)
    draw_rect(img, 14, 2, 30, 28, P_BLUE)
    draw_rect(img, 14, 2, 30, 28, P_DARK)
    draw_line_h(img, 16, 14, 30, P_DARK)
    draw_line_v(img, 29, 2, 28, P_DARK)
    draw_rect(img, 14, 2, 4, 28, P_CHEEK)
    draw_rect(img, 40, 2, 4, 28, P_CHEEK)
    for i in range(6):
        rx, ry = 18 + i * 4, 4 + (i * 3) % 20
        draw_line_v(img, rx, ry, 3, P_BLUE)
    draw_rect(img, 12, 34, 24, 3, P_DARK)
    draw_rect(img, 12, 37, 24, 11, P_CREAM)
    draw_rect(img, 20, 30, 8, 6, P_CREAM)
    draw_rect(img, 20, 30, 8, 1, P_DARK)
    draw_rect(img, 22, 36, 4, 1, P_DARK)
    draw_rect(img, 22, 28, 1, 2, P_CREAM)
    draw_rect(img, 25, 27, 1, 3, P_CREAM)
    draw_rect(img, 14, 38, 3, 3, P_ORANGE)
    draw_rect(img, 31, 38, 3, 3, P_YELLOW)


def draw_forest(img):
    """森: 木々＋地面＋木漏れ日"""
    draw_fill(img, P_BG)
    draw_rect(img, 0, 0, W, 20, P_BLUE)
    draw_line_h(img, 20, 0, W, P_CREAM)
    draw_rect(img, 0, 22, W, 26, P_GREEN)
    draw_line_h(img, 24, 0, W, P_DARK)
    draw_rect(img, 4, 8, 8, 30, P_DARK)
    draw_circle(img, 8, 6, 8, P_GREEN)
    draw_circle(img, 8, 6, 6, P_YELLOW)
    draw_rect(img, 36, 4, 8, 32, P_DARK)
    draw_circle(img, 40, 2, 10, P_GREEN)
    draw_circle(img, 40, 2, 7, P_YELLOW)
    draw_circle(img, 16, 28, 4, P_GREEN)
    draw_circle(img, 30, 30, 3, P_GREEN)
    draw_rect(img, 12, 40, 2, 2, P_CREAM)
    draw_circle(img, 13, 40, 2, P_ORANGE)
    draw_rect(img, 34, 42, 2, 2, P_CREAM)
    draw_circle(img, 35, 42, 2, P_ORANGE)
    draw_rect(img, 18, 2, 2, 10, P_YELLOW_L)
    draw_rect(img, 24, 4, 1, 8, P_YELLOW_L)
    draw_rect(img, 28, 2, 2, 12, P_YELLOW_L)


def draw_ocean(img):
    """海: 海面＋波＋海底"""
    draw_fill(img, P_BLUE)
    for y in range(20, H):
        t = (y - 20) / 28.0
        r = int(66 * (1 - t) + 30 * t)
        g = int(165 * (1 - t) + 50 * t)
        b = int(245 * (1 - t) + 80 * t)
        draw_line_h(img, y, 0, W, (r, g, b, 255))
    draw_line_h(img, 12, 0, W, P_CREAM)
    draw_line_h(img, 14, 0, W, P_BLUE)
    draw_line_h(img, 13, 0, W, P_WATER)
    for i in range(5):
        sx = 4 + i * 10
        draw_rect(img, sx, 12, 3, 1, P_CREAM)
        draw_rect(img, sx + 1, 11, 1, 1, P_CREAM)
    draw_rect(img, 0, 40, W, 8, P_BG2)
    draw_rect(img, 4, 40, 4, 5, P_ORANGE)
    draw_rect(img, 5, 38, 2, 2, P_ORANGE)
    draw_rect(img, 38, 40, 6, 4, P_PINK)
    draw_rect(img, 40, 38, 2, 2, P_PINK)
    draw_rect(img, 16, 22, 4, 2, P_YELLOW)
    draw_rect(img, 15, 23, 1, 1, P_YELLOW)
    draw_rect(img, 20, 23, 1, 1, P_YELLOW)
    draw_rect(img, 30, 18, 2, 2, P_CREAM)
    draw_rect(img, 33, 16, 1, 1, P_CREAM)
    draw_rect(img, 10, 28, 1, 1, P_CREAM)


def draw_cyber(img):
    """サイバー: ネオンビル群＋グリッド"""
    draw_fill(img, P_BG)
    for gx in range(0, W, 4):
        draw_line_v(img, gx, 30, 18, P_BG2)
    for gy in range(30, H, 4):
        draw_line_h(img, gy, 0, W, P_BG2)
    for i in range(3):
        bx, bh = 2 + i * 6, 16 - i * 3
        draw_rect(img, bx, H - 18 - bh, 5, bh, P_DARK)
        for wy in range(H - 18 - bh + 2, H - 18, 3):
            for wx in range(bx + 1, bx + 5, 2):
                img.putpixel((wx, wy), P_NEON if (wx + wy) % 4 == 0 else P_YELLOW_L)
    for i in range(3):
        bx, bh = 32 + i * 5, 18 - i * 4
        draw_rect(img, bx, H - 18 - bh, 4, bh, P_DARK)
        for wy in range(H - 18 - bh + 2, H - 18, 3):
            for wx in range(bx + 1, bx + 4, 2):
                img.putpixel((wx, wy), P_PINK if (wx + wy) % 5 == 0 else P_NEON)
    draw_rect(img, 20, 8, 8, 40, P_DARK)
    for wy in range(10, 46, 3):
        for wx in range(21, 28, 2):
            img.putpixel((wx, wy), P_NEON)
    draw_line_h(img, 30, 0, W, P_NEON)
    draw_line_h(img, 28, 0, W, P_PINK)
    for i in range(4):
        tx = 6 + i * 10
        img.putpixel((tx, 36), P_YELLOW_L)
        img.putpixel((tx + 1, 36), P_YELLOW_L)
        img.putpixel((tx, 38), P_YELLOW_L)


# =============================================================================
# メイン
# =============================================================================
DRAW_FUNCS = {
    "room": draw_room, "cafe": draw_cafe, "forest": draw_forest,
    "ocean": draw_ocean, "cyber": draw_cyber,
}

def main():
    OUT_DIR = Path(__file__).parent.parent / "assets" / "dot" / "bg"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for theme_id, draw_func in DRAW_FUNCS.items():
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw_func(img)
        scaled = img.resize((OUT_W, OUT_H), Image.NEAREST)
        out_path = OUT_DIR / f"{theme_id}.png"
        scaled.save(out_path)
        print(f"生成: {out_path} ({OUT_W}x{OUT_H})")
    print(f"\n✅ 全{len(DRAW_FUNCS)}件の背景ドット絵を生成しました")


if __name__ == "__main__":
    main()