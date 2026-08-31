# -*- coding: utf-8 -*-
"""決定版診断2: 正しいシグネチャでフレーム差分を検証する。"""
import io
import os
import re
import sys

import glob

ROOT = r"c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん"
sys.path.insert(0, ROOT)

from PIL import Image, ImageChops

import tools.generate_kawaii_sprites_v2 as gen

print("draw_seal signature:", gen.draw_seal.__doc__ or "n/a")

GOLD = (255, 213, 40)
JEWEL = (46, 175, 124)
TEA = (188, 232, 241)


def count_px(img, color):
    return sum(1 for px in img.getdata() if px[:3] == color)


# 1. メモリ生成（正しいシグネチャ）で tea_pillar 差分
try:
    i1 = gen.draw_seal("tea_pillar_1")
    i2 = gen.draw_seal("tea_pillar_2")
    diff = ImageChops.difference(i1, i2).getbbox()
    print("mem tea_pillar_1 vs 2: bbox=", diff)
    print("  tea1: gold=", count_px(i1, GOLD), " jewel=", count_px(i1, JEWEL), " tea=", count_px(i1, TEA))
    print("  tea2: gold=", count_px(i2, GOLD), " jewel=", count_px(i2, JEWEL), " tea=", count_px(i2, TEA))
except Exception as e:
    print("mem call error:", repr(e))

# 2. tea_1/tea_2 も生成して差分
try:
    t1 = gen.draw_seal("tea_1")
    t2 = gen.draw_seal("tea_2")
    print("mem tea_1 vs tea_2: bbox=", ImageChops.difference(t1, t2).getbbox())
    print("  tea_1: gold=", count_px(t1, GOLD), " jewel=", count_px(t1, JEWEL), " tea=", count_px(t1, TEA))
except Exception as e:
    print("mem tea_1 error:", repr(e))

# 3. ディスク PNG の直接比較
seal_dir = os.path.join(ROOT, "assets", "dot", "seal")
for pair in (("tea_pillar_1", "tea_pillar_2"), ("tea_1", "tea_2")):
    pa = os.path.join(seal_dir, pair[0] + ".png")
    pb = os.path.join(seal_dir, pair[1] + ".png")
    if os.path.exists(pa) and os.path.exists(pb):
        ia = Image.open(pa).convert("RGBA")
        ib = Image.open(pb).convert("RGBA")
        print(f"disk {pair[0]} vs {pair[1]}: bbox=", ImageChops.difference(ia, ib).getbbox())
        print(f"  {pair[0]}: gold=", count_px(ia, GOLD), " jewel=", count_px(ia, JEWEL), " tea=", count_px(ia, TEA), " size=", ia.size)
    else:
        print(f"disk {pair}: missing", os.path.exists(pa), os.path.exists(pb))

# 4. メモリとディスクの一致確認（生成経路の同一性）
p = os.path.join(seal_dir, "tea_pillar_1.png")
if os.path.exists(p):
    try:
        disk = Image.open(p).convert("RGBA")
        mem = gen.draw_seal("tea_pillar_1")
        print("mem vs disk tea_pillar_1 bbox=", ImageChops.difference(mem, disk).getbbox())
    except Exception as e:
        print("compare error:", repr(e))

# 5. main がどう draw_seal を呼ぶか（ディスパッチテーブル確認）
src = io.open(gen.__file__, encoding="utf-8").read()
for m in re.finditer(r".*(DRAW|dispatch|TABLE|_FUNC|render)\w*\s*=.*", src):
    line = m.group(0).strip()
    if "=" in line and "def" not in line:
        print("dispatch?", line[:120])
