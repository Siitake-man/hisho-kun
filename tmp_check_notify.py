# -*- coding: utf-8 -*-
"""pet.js の通知表示経路（latest_notification 処理）の診断."""
import io
import re
import os

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_pet", "pet.js")
s = io.open(P, encoding="utf-8").read()
lines = s.split("\n")

pat = re.compile(r"latest_notification|showNotification|notification|Notification")
hits = []
for i, l in enumerate(lines, 1):
    if pat.search(l):
        hits.append((i, l.rstrip()))

print(f"total hits: {len(hits)}")
for i, l in hits[:60]:
    print(f"{i}: {l[:150]}")

# ポーリング周期の確認
for m in re.finditer(r"setInterval\([^,]+,\s*(\d+)\)", s):
    line_no = s[: m.start()].count("\n") + 1
    print(f"setInterval @ line {line_no}: {lines[line_no - 1].strip()[:120]}")
