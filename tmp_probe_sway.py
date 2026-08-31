# -*- coding: utf-8 -*-
"""draw_seal をメモリ上で直接呼び、tea_pillar_1/2 のスウェイ差分を検証する。"""
import importlib.util
import inspect
import os
import sys

ROOT = r'c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん'
GEN = os.path.join(ROOT, 'tools', 'generate_kawaii_sprites_v2.py')
sys.path.insert(0, os.path.join(ROOT, 'tools'))

spec = importlib.util.spec_from_file_location('gen_v2', GEN)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

print('signature:', inspect.signature(mod.draw_seal))
print('seal states:', [s for s in mod.STATES['seal'] if 'tea' in s])

from PIL import ImageChops

im1 = mod.draw_seal('tea_pillar_1')
im2 = mod.draw_seal('tea_pillar_2')
print('in-memory tp1 vs tp2 bbox:', ImageChops.difference(im1, im2).getbbox())
