# -*- coding: utf-8 -*-
"""ディスク上の再生成済み seal PNG の王冠・宝石・sway差分を検証する。"""
import io
import os

from PIL import Image, ImageChops

SEAL = os.path.join(
    r"c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん\assets\dot", "seal"
)
P_GOLD = (255, 213, 40)
P_JEWEL = (46, 175, 124)


def load(name: str) -> Image.Image:
    path = os.path.join(SEAL, name + ".png")
    img = Image.open(path).convert("RGBA")
    print(f"{name}: mtime={os.path.getmtime(path):.0f} size={img.size}")
    return img


def count_gold(img: Image.Image) -> int:
    return sum(
        1
        for r, g, b, a in img.getdata()
        if a > 0 and abs(r - P_GOLD[0]) < 12 and abs(g - P_GOLD[1]) < 12 and abs(b - P_GOLD[2]) < 12
    )


def count_jewel(img: Image.Image) -> int:
    return sum(
        1
        for r, g, b, a in img.getdata()
        if a > 0 and abs(r - P_JEWEL[0]) < 12 and abs(g - P_JEWEL[1]) < 12 and abs(b - P_JEWEL[2]) < 12
    )


tp1 = load("tea_pillar_1")
tp2 = load("tea_pillar_2")
id1 = load("idle_1")

diff = ImageChops.difference(tp1, tp2)
bbox = diff.getbbox()
print("gold  tp1 =", count_gold(tp1), " tp2 =", count_gold(tp2), " idle =", count_gold(id1))
print("jewel tp1 =", count_jewel(tp1), " tp2 =", count_jewel(tp2))
print("sway diff bbox =", bbox)

ok = True
if count_gold(tp1) == 0 or count_gold(tp2) == 0:
    print("FAIL: crown gold missing")
    ok = False
if count_gold(id1) != 0:
    print("FAIL: crown leaks into idle")
    ok = False
if count_jewel(tp1) < 3:
    print("FAIL: jewels missing (<3px)")
    ok = False
if bbox is None:
    print("FAIL: tea_pillar_1 == tea_pillar_2 (sway dead)")
    ok = False

print("RESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
