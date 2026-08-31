# -*- coding: utf-8 -*-
"""決定版検証: ディスク上の tea_pillar_1/2 のピクセル差分を素直に比較する。"""
import hashlib
import io
import os

from PIL import Image, ImageChops

SEAL = os.path.join(
    r"c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん\assets\dot", "seal"
)

p1 = os.path.join(SEAL, "tea_pillar_1.png")
p2 = os.path.join(SEAL, "tea_pillar_2.png")

b1 = open(p1, "rb").read()
b2 = open(p2, "rb").read()
print("md5_1 =", hashlib.md5(b1).hexdigest())
print("md5_2 =", hashlib.md5(b2).hexdigest())
print("bytes_identical =", b1 == b2)

i1 = Image.open(p1).convert("RGBA")
i2 = Image.open(p2).convert("RGBA")
print("sizes:", i1.size, i2.size)
diff = ImageChops.difference(i1, i2)
bbox = diff.getbbox()
print("pixel_diff_bbox =", bbox)
if bbox:
    # 差分ピクセルの座標と色を列挙（最大10件）
    px1, px2 = i1.load(), i2.load()
    cnt = 0
    for y in range(bbox[1], bbox[3]):
        for x in range(bbox[0], bbox[2]):
            if px1[x, y] != px2[x, y]:
                print(f"  ({x},{y}): {px1[x, y]} -> {px2[x, y]}")
                cnt += 1
                if cnt >= 10:
                    break
        if cnt >= 10:
            break

# おまけ: idle_1 との差分（王冠が頭に載っているか）
p_idle = os.path.join(SEAL, "idle_1.png")
i0 = Image.open(p_idle).convert("RGBA")
d0 = ImageChops.difference(i1, i0)
print("tea1_vs_idle_bbox =", d0.getbbox())
