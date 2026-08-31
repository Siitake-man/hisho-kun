# -*- coding: utf-8 -*-
"""決定版診断: draw_seal 呼び出しトレース + 乱数固定メモリ差分 + ディスク検証。"""
import hashlib
import importlib.util
import io
import os
import random
import sys

ROOT = r'c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん'
GEN = os.path.join(ROOT, 'tools', 'generate_kawaii_sprites_v2.py')
SEAL_DIR = os.path.join(ROOT, 'assets', 'dot', 'seal')

spec = importlib.util.spec_from_file_location('genv2', GEN)
gen = importlib.util.module_from_spec(spec)
sys.modules['genv2'] = gen
spec.loader.exec_module(gen)

# --- 1. main 実行時の draw_seal 呼び出しトレース ---
calls = []
_orig = gen.draw_seal

def traced(state):
    calls.append(state)
    return _orig(state)

gen.draw_seal = traced
gen.main()
gen.draw_seal = _orig

tea_calls = [c for c in calls if 'tea' in str(c)]
print('[TRACE] total calls =', len(calls))
print('[TRACE] tea-related calls =', tea_calls)
seal_states = getattr(gen, 'STATES', {}).get('seal', [])
print('[STATES][seal] =', seal_states)

# --- 2. 乱数固定メモリ差分 ---
random.seed(42)
m1 = _orig('tea_pillar_1')
random.seed(42)
m2 = _orig('tea_pillar_2')
h1 = hashlib.md5(m1.tobytes()).hexdigest()
h2 = hashlib.md5(m2.tobytes()).hexdigest()
bbox = (lambda a, b: a and a) if False else None
from PIL import ImageChops
diff = ImageChops.difference(m1.convert('RGB'), m2.convert('RGB'))
print('[MEM] h1 =', h1[:10], ' h2 =', h2[:10], ' identical =', h1 == h2)
print('[MEM] diff bbox =', diff.getbbox())

# --- 3. ディスクPNG検証（main再生成後の最新物） ---
def p(name):
    return os.path.join(SEAL_DIR, name + '.png')

for name in ('tea_pillar_1', 'tea_pillar_2', 'idle_1'):
    fp = p(name)
    raw = open(fp, 'rb').read()
    img = io.BytesIO(raw)
    from PIL import Image
    im = Image.open(img).convert('RGBA')
    print('[DISK]', name, 'size=', im.size, 'md5=', hashlib.md5(raw).hexdigest()[:10])

d1 = open(p('tea_pillar_1'), 'rb').read()
d2 = open(p('tea_pillar_2'), 'rb').read()
print('[DISK] tea1 == tea2 bytes ?', d1 == d2)

from PIL import Image
i1 = Image.open(io.BytesIO(d1)).convert('RGBA')
i2 = Image.open(io.BytesIO(d2)).convert('RGBA')
print('[DISK] pixel diff bbox =', ImageChops.difference(i1, i2).getbbox())
