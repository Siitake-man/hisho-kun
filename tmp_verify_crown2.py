# -*- coding: utf-8 -*-
"""茶柱王冠スプライトの検証スクリプト（一時ファイル）。"""
import os

from PIL import Image, ImageChops

BASE = r'c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん'
SEAL = os.path.join(BASE, 'assets', 'dot', 'seal')

GOLD = (255, 215, 0)
GOLD_DK = (184, 134, 11)
JEWEL = (46, 175, 124)
VELVET = (200, 16, 46)


def load(name):
    return Image.open(os.path.join(SEAL, name + '.png')).convert('RGBA')


def count_colors(img, colors):
    px = img.load()
    n = 0
    for y in range(img.height):
        for x in range(img.width):
            if px[x, y][:3] in colors:
                n += 1
    return n


idle1 = load('idle_1')
tp1 = load('tea_pillar_1')
tp2 = load('tea_pillar_2')

print('tea_pillar_1 gold   =', count_colors(tp1, {GOLD, GOLD_DK}))
print('tea_pillar_2 gold   =', count_colors(tp2, {GOLD, GOLD_DK}))
print('tea_pillar_1 jewel  =', count_colors(tp1, {JEWEL}))
print('tea_pillar_2 jewel  =', count_colors(tp2, {JEWEL}))
print('tea_pillar_1 velvet =', count_colors(tp1, {VELVET}))
print('idle_1 gold         =', count_colors(idle1, {GOLD, GOLD_DK}))

print('diff tp1 vs tp2 bbox =', ImageChops.difference(tp1, tp2).getbbox())

head = (0, 0, 32, 12)
print('diff head tp1 vs idle bbox =',
      ImageChops.difference(tp1.crop(head), idle1.crop(head)).getbbox())

WAVE_BLUES = {(91, 173, 236), (62, 142, 222)}
print('wave-blue px in tp1 =', count_colors(tp1, WAVE_BLUES))

for name, img in (('tp1', tp1), ('tp2', tp2)):
    px = img.load()
    cols = [x for x in range(32) if px[x, 7][:3] == JEWEL]
    print(name, 'jewel columns at y=7 =', cols)
