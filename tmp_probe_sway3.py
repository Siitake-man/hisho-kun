# -*- coding: utf-8 -*-
"""tea_pillar sway 差分の最終検証プローブ。

モジュール解決パス・P_TEAピクセル位置・フレーム間差分を実データで確認する。
"""
import io
import os
import sys

sys.path.insert(0, r'c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん\tools')

import generate_kawaii_sprites_v2 as gen

print('module file =', gen.__file__)

img1 = gen.draw_seal('tea_pillar_1')
img2 = gen.draw_seal('tea_pillar_2')

P_TEA = gen.P_TEA
print('P_TEA =', P_TEA)


def tea_pixels(img):
    """P_TEA 色ピクセルの座標リストを返す。"""
    px = img.load()
    return [(x, y) for y in range(img.height) for x in range(img.width) if px[x, y][:3] == tuple(P_TEA)]


t1 = tea_pixels(img1)
t2 = tea_pixels(img2)
print('tea_pillar_1 P_TEA count =', len(t1))
print('tea_pillar_2 P_TEA count =', len(t2))
print('t1 x-range =', (min(x for x, _ in t1), max(x for x, _ in t1)) if t1 else None)
print('t2 x-range =', (min(x for x, _ in t2), max(x for x, _ in t2)) if t2 else None)

from PIL import ImageChops

bbox = ImageChops.difference(img1, img2).getbbox()
print('diff bbox =', bbox)

# ディスク上のPNGも再確認
seal_dir = r'c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん\assets\dot\seal'
for name in ('tea_pillar_1.png', 'tea_pillar_2.png'):
    path = os.path.join(seal_dir, name)
    from PIL import Image
    disk = Image.open(path).convert('RGBA')
    mem = img1 if name.endswith('1.png') else img2
    same = list(disk.getdata()) == list(mem.getdata())
    print(name, 'disk==memory:', same)

print('PROBE DONE')
