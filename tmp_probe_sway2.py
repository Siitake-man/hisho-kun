# -*- coding: utf-8 -*-
"""茶柱スウェイ差分のメモリ生成 vs ディスクPNG 直接突合せ検証。"""
import os
import sys

root = r'c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん'
sys.path.insert(0, os.path.join(root, 'tools'))

from PIL import Image, ImageChops

import generate_kawaii_sprites_v2 as gen

seal_dir = os.path.join(root, 'assets', 'dot', 'seal')

# 1) メモリ上で直接生成して差分を取る
m1 = gen.draw_seal('tea_pillar_1').convert('RGBA')
m2 = gen.draw_seal('tea_pillar_2').convert('RGBA')
mem_bbox = ImageChops.difference(m1, m2).getbbox()
print('MEMORY diff bbox tea_pillar_1 vs 2 =', mem_bbox)

# 2) ディスクPNG同士の差分
d1 = Image.open(os.path.join(seal_dir, 'tea_pillar_1.png')).convert('RGBA')
d2 = Image.open(os.path.join(seal_dir, 'tea_pillar_2.png')).convert('RGBA')
print('DISK   diff bbox tea_pillar_1 vs 2 =', ImageChops.difference(d1, d2).getbbox())

# 3) メモリ vs ディスク（再生成がディスクに反映されているか）
for name, mem in (('tea_pillar_1', m1), ('tea_pillar_2', m2)):
    disk = Image.open(os.path.join(seal_dir, name + '.png')).convert('RGBA')
    bbox = ImageChops.difference(mem, disk).getbbox()
    print('MEM vs DISK', name, 'diff bbox =', bbox)

# 4) 鮮度確認
py_mtime = os.path.getmtime(os.path.join(root, 'tools', 'generate_kawaii_sprites_v2.py'))
for name in ('tea_pillar_1.png', 'tea_pillar_2.png'):
    p_mtime = os.path.getmtime(os.path.join(seal_dir, name))
    print(name, 'png_mtime=', p_mtime, 'newer_than_py=', p_mtime > py_mtime)
