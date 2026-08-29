# -*- coding: utf-8 -*-
import io
p = r"c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん\gui.py"
c = io.open(p, encoding="utf-8").read()
lines = c.split("\n")
out = []
for i, ln in enumerate(lines, 1):
    if 418 <= i <= 424 or 599 <= i <= 604 or 655 <= i <= 660:
        out.append(str(i) + ": " + repr(ln))
io.open(r"C:\Users\bonob\AppData\Local\Temp\repr_out.txt", "w", encoding="utf-8").write("\n".join(out))
print("done")
