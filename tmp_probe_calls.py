# -*- coding: utf-8 -*-
"""決定版診断2: リテラルのホモグリフ検査 + 描画コールログ差分。"""
import io
import os
import sys

ROOT = r"c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん"
sys.path.insert(0, os.path.join(ROOT, "tools"))

SRC = os.path.join(ROOT, "tools", "generate_kawaii_sprites_v2.py")
lines = io.open(SRC, encoding="utf-8").read().splitlines()

# 1) 542-558行目の非ASCII文字（不可視・全角）検査
print("=== non-ASCII check (lines 542-558) ===")
found = False
for i in range(541, 558):
    ln = lines[i]
    for j, ch in enumerate(ln):
        if ord(ch) > 127:
            found = True
            print(f"line {i+1} col {j+1}: U+{ord(ch):04X} {ch!r} context={ln[max(0,j-10):j+10]!r}")
if not found:
    print("non-ASCII: NONE (literals are clean)")

# 2) 描画コールログ差分（p / p_box / p_ellipse をラップして呼び出し列を比較）
import generate_kawaii_sprites_v2 as gen  # noqa: E402

orig = {n: getattr(gen, n) for n in ("p", "p_box", "p_ellipse")}
logs: dict = {"tea_pillar_1": [], "tea_pillar_2": []}
cur = {"state": None}


def wrap(name):
    def inner(draw, *args):
        if cur["state"] is not None:
            logs[cur["state"]].append((name, args))
        return orig[name](draw, *args)
    return inner


for n in orig:
    setattr(gen, n, wrap(n))

for st in ("tea_pillar_1", "tea_pillar_2"):
    cur["state"] = st
    gen.draw_seal(st)
cur["state"] = None

l1, l2 = logs["tea_pillar_1"], logs["tea_pillar_2"]
print("=== call log ===")
print("calls tea_pillar_1 =", len(l1), "/ tea_pillar_2 =", len(l2))
only1 = [c for c in l1 if c not in l2]
only2 = [c for c in l2 if c not in l1]
print("only in _1 :", only1[:12])
print("only in _2 :", only2[:12])
if not only1 and not only2:
    print(">>> 描画コール列は完全一致（sway が効いていない）")
else:
    print(">>> sway 差分あり：コールは違うのに画像が一致するなら別要因")
