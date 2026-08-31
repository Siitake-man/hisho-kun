# -*- coding: utf-8 -*-
"""決定版診断: 乱数固定化のもとで tea_pillar_1/2 のメモリ差分を検証する。

仮説検証:
  H1: 以前のメモリハッシュ差分は _fx_stars の乱数による偽差分である
  H2: main 保存ループが同一画像を両フレームに書き込んでいる（エイリアス）
"""
import hashlib
import io
import random
import sys

ROOT = r'c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん'
sys.path.insert(0, ROOT)
sys.path.insert(0, ROOT + r'\tools')

import generate_kawaii_sprites_v2 as gen  # noqa: E402


def md5_of_image(img):
    """PILイメージの生ピクセルMD5を返す。"""
    return hashlib.md5(img.tobytes()).hexdigest()[:10]


# --- 実験1: 乱数固定で tea_pillar_1 / tea_pillar_2 を生成して比較 ---
random.seed(20260831)
img_tp1 = gen.draw_seal('tea_pillar_1')
h1_a = md5_of_image(img_tp1)

random.seed(20260831)
img_tp2 = gen.draw_seal('tea_pillar_2')
h2_a = md5_of_image(img_tp2)

# --- 実験2: 同一stateを乱数固定で2回生成 → 乱数が差分源か判定 ---
random.seed(20260831)
img_tp1_again = gen.draw_seal('tea_pillar_1')
h1_b = md5_of_image(img_tp1_again)

print('tea_pillar_1 (run1) =', h1_a)
print('tea_pillar_2 (same seed) =', h2_a)
print('tea_pillar_1 (run2, same seed) =', h1_b)
print('tp1 vs tp2 diff :', 'DIFFERENT' if h1_a != h2_a else 'IDENTICAL')
print('tp1 vs tp1 again:', 'DIFFERENT (random sources exist)' if h1_a != h1_b else 'IDENTICAL (deterministic)')

# --- 実験3: ピクセル単位の差分bbox ---
from PIL import ImageChops  # noqa: E402

bbox = ImageChops.difference(img_tp1.convert('RGB'), img_tp2.convert('RGB')).getbbox()
print('tp1 vs tp2 pixel diff bbox =', bbox)

# --- 実験4: オブジェクト同一性（エイリアスチェック） ---
print('same object? ->', img_tp1 is img_tp2)
