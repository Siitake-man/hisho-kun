# -*- coding: utf-8 -*-
"""最終確定: getdata() の生ピクセル列で直接比較し、PNGメタデータも確認する。"""
import os

from PIL import Image

SEAL = os.path.join(
    r"c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん\assets\dot", "seal"
)

i1 = Image.open(os.path.join(SEAL, "tea_pillar_1.png"))
i2 = Image.open(os.path.join(SEAL, "tea_pillar_2.png"))

print("mode1/mode2 =", i1.mode, i2.mode)
print("info1 =", i1.info)
print("info2 =", i2.info)

d1 = list(i1.convert("RGBA").getdata())
d2 = list(i2.convert("RGBA").getdata())
print("data_len:", len(d1), len(d2))
print("data_identical =", d1 == d2)
if d1 != d2:
    diffs = [(i, a, b) for i, (a, b) in enumerate(zip(d1, d2)) if a != b]
    print("num_diff_pixels =", len(diffs))
    for i, a, b in diffs[:10]:
        print(f"  idx={i} (x={i % 128},y={i // 128}): {a} -> {b}")
