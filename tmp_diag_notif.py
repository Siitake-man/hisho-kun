# -*- coding: utf-8 -*-
"""showToast / buzz (5.6) の実装を抽出する診断スクリプト。"""
import io
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PATH = r"c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん\web_pet\pet.js"
lines = io.open(PATH, encoding="utf-8").read().split("\n")


def dump(start: int, end: int, title: str) -> None:
    print(f"\n===== {title} ({start}-{end}) =====")
    for n in range(start - 1, min(end, len(lines))):
        print(f"{n+1:5d}: {lines[n]}")


# showToast 定義を探す
for i, ln in enumerate(lines):
    if re.search(r"function showToast|showToast\s*=", ln):
        dump(i + 1, i + 60, f"showToast def @ {i+1}")
        break

# buzz セクションを探す
for i, ln in enumerate(lines):
    if "buzz" in ln and ("5.6" in ln or "buzz_requested" in ln or "_buzz" in ln):
        dump(max(0, i - 5), i + 45, f"buzz section @ {i+1}")
        break
