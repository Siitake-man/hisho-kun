# -*- coding: utf-8 -*-
"""決定版診断: 正しい draw_seal(state) シグネチャで tea_pillar 差分を検証。"""
import os
import sys

ROOT = r"c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from PIL import Image, ImageChops  # noqa: E402

import generate_kawaii_sprites_v2 as gen  # noqa: E402

print("module file =", gen.__file__)

# 1) ディスク上の実PNGを直接比較
seal_dir = os.path.join(ROOT, "assets", "dot", "seal")
p1 = os.path.join(seal_dir, "tea_pillar_1.png")
p2 = os.path.join(seal_dir, "tea_pillar_2.png")
for p in (p1, p2):
    print(os.path.basename(p), "exists =", os.path.exists(p),
          "mtime =", os.path.getmtime(p) if os.path.exists(p) else "-")

if os.path.exists(p1) and os.path.exists(p2):
    d1 = Image.open(p1).convert("RGBA")
    d2 = Image.open(p2).convert("RGBA")
    bbox = ImageChops.difference(d1, d2).getbbox()
    print("[disk] tea_pillar_1 vs 2 diff bbox =", bbox)

# 2) メモリ上で正しいシグネチャ（引数1つ）により両フレーム生成して比較
m1 = gen.draw_seal("tea_pillar_1")
m2 = gen.draw_seal("tea_pillar_2")
bbox_m = ImageChops.difference(m1, m2).getbbox()
print("[memory] tea_pillar_1 vs 2 diff bbox =", bbox_m)

# 3) メモリ生成物の王冠gold点在確認（P_GOLD=(255,213,40)）
gold = (255, 213, 40, 255)
for name, img in (("tea_pillar_1", m1), ("tea_pillar_2", m2)):
    cnt = sum(1 for px in img.getdata() if px == gold)
    print(f"[memory] {name} gold px =", cnt)
