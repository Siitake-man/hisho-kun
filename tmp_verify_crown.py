# -*- coding: utf-8 -*-
"""茶柱王冠スプライトの差分検証スクリプト（一時・検証専用）。"""
import os

from PIL import Image, ImageChops

BASE = os.path.join(
    r"c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん",
    "assets",
    "dot",
    "seal",
)


def load(name: str) -> Image.Image:
    """指定名のPNGをRGBAで読み込む。"""
    return Image.open(os.path.join(BASE, name + ".png")).convert("RGBA")


idle = load("idle_1")
t1 = load("tea_pillar_1")
t2 = load("tea_pillar_2")

# 1. 相互差分
print("idle_1 vs tea_pillar_1 diff bbox =", ImageChops.difference(idle, t1).getbbox())
print("tea_pillar_1 vs 2 diff bbox =", ImageChops.difference(t1, t2).getbbox())


# 2. 王冠領域（上部1/3）の金・赤・緑ピクセル数
def count_colors(img: Image.Image, box) -> tuple:
    """box領域の gold/red/green ピクセル数を数える。"""
    crop = img.crop(box)
    px = list(crop.getdata())
    gold = sum(1 for r, g, b, a in px if a > 0 and r > 150 and g > 110 and b < 120 and r > b + 60)
    red = sum(1 for r, g, b, a in px if a > 0 and r > 140 and g < 90 and b < 90)
    green = sum(1 for r, g, b, a in px if a > 0 and g > 110 and r < 110 and b < 110)
    return gold, red, green


W, H = idle.size
for name, img in (("idle_1", idle), ("tea_1", t1), ("tea_2", t2)):
    g, r, gr = count_colors(img, (0, 0, W, H // 3))
    print(name, "crown-area gold/red/green px =", g, r, gr)


# 3. 下部1/3の変化量（旧波模様の撤去確認）
def diff_count(a: Image.Image, b: Image.Image) -> int:
    """2画像の不一致ピクセル数。"""
    pa, pb = list(a.getdata()), list(b.getdata())
    return sum(1 for x, y in zip(pa, pb) if x != y)


bot_idle = idle.crop((0, H * 2 // 3, W, H))
bot_t1 = t1.crop((0, H * 2 // 3, W, H))
print("bottom-third changed px (idle_1 vs tea_1) =", diff_count(bot_idle, bot_t1))
