# -*- coding: utf-8 -*-
"""決定版診断: モジュール解決・分岐実行カウント・フレーム差分を一括検証する。"""
import io
import os
import sys

import glob

ROOT = r"c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん"
sys.path.insert(0, ROOT)

from PIL import Image, ImageChops

import tools.generate_kawaii_sprites_v2 as gen

print("module file =", gen.__file__)

# 1. ディスク上の tea 関連ファイルと鮮度
seal_dir = os.path.join(ROOT, "assets", "dot", "seal")
for p in sorted(glob.glob(os.path.join(seal_dir, "tea*"))):
    print("disk:", os.path.basename(p), os.path.getmtime(p))

# 2. メインループが seal に渡すステート名を特定
src = io.open(gen.__file__, encoding="utf-8").read()
import re
for m in re.finditer(r"(tea\w*)", src):
    pass
tea_names = sorted(set(re.findall(r"['\"](tea\w*)['\"]", src)))
print("tea literals in generator:", tea_names)

# 3. draw_seal をラップして渡される state を記録
orig = gen.draw_seal
calls = []


def spy(state, *a, **k):
    calls.append(state)
    return orig(state, *a, **k)


gen.draw_seal = spy

# draw_seal 内部参照が module global なので OK。メインの生成関数を探して実行
cand = [n for n in dir(gen) if "generate" in n.lower() or "main" in n.lower()]
print("entry candidates:", cand)


def try_call(fn):
    try:
        fn()
        return True
    except TypeError as e:
        print("  needs args:", fn.__name__, e)
        return False


for name in cand:
    fn = getattr(gen, name)
    if callable(fn):
        print("calling", name)
        try_call(fn)

print("draw_seal states requested:", sorted(set(calls)))

# 4. メモリ上でのフレーム差分（tea_pillar_* と tea_* の両方）
def snap(state):
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    orig(state, img)
    return img


for a, b in (("tea_pillar_1", "tea_pillar_2"), ("tea_1", "tea_2")):
    try:
        ia, ib = snap(a), snap(b)
        diff = ImageChops.difference(ia, ib).getbbox()
        tea_px = sum(1 for px in ia.getdata() if px[:3] == (188, 232, 241))
        gold_px = sum(1 for px in ia.getdata() if px[:3] == (255, 213, 40))
        print(f"in-memory {a} vs {b}: bbox={diff} tea_px={tea_px} gold_px={gold_px}")
    except Exception as e:
        print(f"in-memory {a}: ERROR {e!r}")

# 5. ディスク PNG とメモリ生成の突き合わせ
for state in ("tea_1", "tea_2", "tea_pillar_1"):
    p = os.path.join(seal_dir, state + ".png")
    if os.path.exists(p):
        disk = Image.open(p).convert("RGBA")
        mem = snap(state)
        d = ImageChops.difference(disk, mem).getbbox()
        tea_px = sum(1 for px in disk.getdata() if px[:3] == (188, 232, 241))
        print(f"disk {state}: size={disk.size} mem_vs_disk_bbox={d} tea_px(disk)={tea_px}")
    else:
        print(f"disk {state}: NOT FOUND")
