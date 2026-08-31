# -*- coding: utf-8 -*-
"""ディスク再生成後の seal スプライト最終検証（sway差分・王冠・宝石）."""
import os

from PIL import Image, ImageChops

SEAL = r'c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん\assets\dot\seal'
P_GOLD = (255, 213, 40)    # 本体パレットと一致
P_JEWEL = (46, 175, 124)   # 緑宝石


def load(name: str) -> Image.Image:
    return Image.open(os.path.join(SEAL, name + '.png')).convert('RGBA')


def count_color(img: Image.Image, rgb: tuple, tol: int = 12) -> int:
    w, h = img.size
    px = img.load()
    n = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a > 0 and abs(r - rgb[0]) <= tol and abs(g - rgb[1]) <= tol and abs(b - rgb[2]) <= tol:
                n += 1
    return n


idle1 = load('idle_1')
tp1 = load('tea_pillar_1')
tp2 = load('tea_pillar_2')

print('== ディスクPNG最終検証 ==')
print('gold tp1 =', count_color(tp1, P_GOLD), 'px  (idle:', count_color(idle1, P_GOLD), 'px)')
print('jewel tp1 =', count_color(tp1, P_JEWEL), 'px  (idle:', count_color(idle1, P_JEWEL), 'px)')

diff12 = ImageChops.difference(tp1, tp2)
bbox12 = diff12.getbbox()
print('tp1 vs tp2 diff bbox =', bbox12)

# 差分ピクセルの位置が茶柱（湯呑み上・y~14前後付近）か確認
if bbox12:
    px = diff12.load()
    pts = [(x, y) for y in range(bbox12[1], bbox12[3] + 1) for x in range(bbox12[0], bbox12[2] + 1)
           if px[x, y] != (0, 0, 0, 0)]
    print('diff pixels =', len(pts), 'sample =', pts[:10])

diff_idle = ImageChops.difference(idle1, tp1).getbbox()
print('idle_1 vs tp1 diff bbox =', diff_idle)

ok = count_color(tp1, P_GOLD) > 0 and count_color(tp1, P_JEWEL) > 0 and bbox12 is not None
print('\nRESULT:', 'ALL PASS ✅' if ok else 'FAIL ❌')
