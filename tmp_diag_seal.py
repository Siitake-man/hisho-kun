# -*- coding: utf-8 -*-
"""seal tea_pillar 王冠/茶柱/スウェイの実ピクセル診断スクリプト。"""
import io
import os
from PIL import Image, ImageChops

SEAL = r'c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん\assets\dot\seal'
GEN = r'c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん\tools\generate_kawaii_sprites_v2.py'

P_GOLD = (255, 213, 40)
P_JEWEL = (46, 175, 124)


def load(name: str) -> Image.Image:
    return Image.open(os.path.join(SEAL, name + '.png')).convert('RGBA')


def count_color(img: Image.Image, color) -> int:
    px = img.load()
    w, h = img.size
    n = 0
    for y in range(h):
        for x in range(w):
            if px[x, y][:3] == color:
                n += 1
    return n


idle = load('idle_1')
tp1 = load('tea_pillar_1')
tp2 = load('tea_pillar_2')

print('sizes:', idle.size, tp1.size, tp2.size)

st = os.stat(GEN)
for n, im in (('idle_1', idle), ('tea_pillar_1', tp1), ('tea_pillar_2', tp2)):
    p = os.path.join(SEAL, n + '.png')
    mt = os.stat(p).st_mtime
    print(f'{n}: mtime={mt:.0f} newer_than_gen={mt > st.st_mtime}')

d12 = ImageChops.difference(tp1, tp2)
print('tp1 vs tp2 bbox:', d12.getbbox())
di = ImageChops.difference(idle, tp1)
print('idle_1 vs tp1 bbox:', di.getbbox())

for n, im in (('idle_1', idle), ('tp1', tp1), ('tp2', tp2)):
    print(f'{n}: gold={count_color(im, P_GOLD)} jewel={count_color(im, P_JEWEL)}')

# 頭部領域（上段8px）の色ヒストグラム Top5
px = tp1.load()
w, h = tp1.size
hist: dict = {}
for y in range(0, min(8, h)):
    for x in range(w):
        c = px[x, y]
        if c[3] > 0:
            hist[c] = hist.get(c, 0) + 1
top = sorted(hist.items(), key=lambda kv: -kv[1])[:5]
print('tp1 head-row colors:', top)
