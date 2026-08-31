# -*- coding: utf-8 -*-
"""各コンセプト画像の正確なサイズとキャラクター領域を検出し、
完璧なスプライトを生成するツール。
"""
from pathlib import Path
from PIL import Image

BRAIN_DIR = Path(r"C:\Users\bonob\.gemini\antigravity-ide\brain\a0516311-bc42-4430-af12-2499703d40b0")
ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "assets" / "dot"

IMG_MARMOT = BRAIN_DIR / "marmot_final_decision_sheet_1788155775994.jpg"
IMG_KINOKO = BRAIN_DIR / "kinoko_cute_redesign_v2_1788165145059.jpg"
IMG_SEAL = BRAIN_DIR / "seal_redesign_concepts_1788155245568.jpg"

for name, p in [("MARMOT", IMG_MARMOT), ("KINOKO", IMG_KINOKO), ("SEAL", IMG_SEAL)]:
    im = Image.open(p)
    print(f"{name}: size={im.size}")
