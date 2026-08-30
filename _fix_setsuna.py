# -*- coding: utf-8 -*-
"""setsuna.js の draw() 分断修復 + easter_eggs.js のPixelDefense参照確認。"""
import io
import re

# --- 1. easter_eggs.js の PixelDefense 参照を表示 ---
eg = io.open(r"web_pet\easter_eggs.js", encoding="utf-8").read().split("\n")
for i, ln in enumerate(eg):
    if "PixelDefense" in ln or "MinigameArcade" in ln:
        print("EG %d: %s" % (i + 1, ln.strip()[:120]))

# --- 2. setsuna.js の現状解析 ---
PATH = r"web_pet\minigame_setsuna.js"
p = io.open(PATH, encoding="utf-8").read().split("\n")
print("SETSUNA TOTAL", len(p))
for i, ln in enumerate(p):
    s = ln.strip()
    if s.startswith("function draw") or s == "if (state === 'ready') {" or s == "})();" or s.startswith("ctx.fillStyle = 'rgba(0,0,0"):
        print("L%04d: %s" % (i + 1, s[:100]))
