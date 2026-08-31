# -*- coding: utf-8 -*-
"""draw_seal 内の tea_pillar_2 リテラルのバイトレベル検査＋正規化経路の可視化."""
import io
import inspect
import sys

ROOT = r'c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん'
sys.path.insert(0, ROOT)

import tools.generate_kawaii_sprites_v2 as gen  # noqa: E402

fn = gen.draw_seal
src = inspect.getsource(fn)
print('module file =', fn.__module__, inspect.getfile(fn))

print('\n=== tea_pillar を含む行（コードポイント検査） ===')
for i, line in enumerate(src.splitlines(), 1):
    if 'tea_pillar' in line or 'sway' in line:
        bad = [(k, hex(ord(c))) for k, c in enumerate(line) if ord(c) > 127]
        print(f'L{i}: {line!r}')
        if bad:
            print(f'   NON-ASCII at {bad}')
        # ASCII 文字列リテラル内に非ASCIIが混入していないか
        if 'tea_pillar_2' in line and not line.strip().startswith('#'):
            lit_ok = 'tea_pillar_2' in line.encode('ascii', 'ignore').decode()
            print('   literal ascii-pure:', lit_ok)

print('\n=== draw_seal 冒頭（state 正規化部, 先頭30行） ===')
for i, line in enumerate(src.splitlines()[:30], 1):
    print(f'L{i}: {line}')

print('\n=== 実行時の分岐実測 ===')
for st in ('tea_pillar_1', 'tea_pillar_2'):
    img = fn(st)
    print(st, '-> size', img.size, 'pixels(hash sample)', hash(img.tobytes()) % 10**8)
