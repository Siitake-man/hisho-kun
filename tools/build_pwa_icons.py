#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - PWAホーム画面アイコン生成スクリプト (tools/build_pwa_icons.py)

初代秘書くんのドット絵 (assets/dot/hisho/happy.png) から、スマホの
「ホーム画面に追加」に必要なサイズのアイコンを生成します (タスク3)。

実行方法 (ボス/開発者・手動):
    venv\\Scripts\\python.exe tools\\build_pwa_icons.py

生成先: assets/pwa/  (local_sync_server が GET /assets/... で配信する)
    icon_192.png              192x192  purpose: any
    icon_512.png              512x512  purpose: any
    icon_maskable_512.png     512x512  purpose: maskable (背景塗りつぶし)
    apple_touch_icon_180.png  180x180  iOS Safari apple-touch-icon (背景塗りつぶし)

設計方針 (Why):
- 拡大は NEAREST 固定。ドット絵は補間すると輪郭がボケて魅力が失われる。
- maskable / iOS 用アイコンは透過を許さない (マスクで欠ける・iOSが黒背景を敷く)
  ため、テーマ背景色で塗りつぶしたセーフゾーン内に artwork を配置する。
- 生成物はバイナリのため、再生成手順を本スクリプトとして残し再現性を担保する。
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_ART = PROJECT_ROOT / "assets" / "dot" / "hisho" / "happy.png"
OUTPUT_DIR = PROJECT_ROOT / "assets" / "pwa"

# PWA テーマ背景色 (web_pet/manifest.json の background_color と一致させる)
THEME_BACKGROUND = "#1A1C23"

# (ファイル名, 出力サイズ(px), 余白比率, 背景色 or None=透過)
# 余白 0.08 = 内側 84% に artwork を配置 (maskable 規格は余白10%未満でOK・2026-09-16 査読指摘)
ICON_SPECS = (
    ("icon_192.png", 192, 0.0, None),
    ("icon_512.png", 512, 0.0, None),
    ("icon_maskable_512.png", 512, 0.08, THEME_BACKGROUND),
    ("apple_touch_icon_180.png", 180, 0.08, THEME_BACKGROUND),
)


def build_icon(
    source: Image.Image,
    size: int,
    padding_ratio: float = 0.0,
    background: Optional[str] = None,
) -> Image.Image:
    """ドット絵から正方形アイコンを1枚生成する。

    Args:
        source: 元ドット絵 (任意サイズ)。
        size: 出力の一辺 (px)。
        padding_ratio: 周囲に空ける余白の比率 (0.15 なら内側 70% に描画)。
        background: 背景色 (None なら透過)。

    Returns:
        Image.Image: 生成した RGBA 画像 (保存は呼び出し側)。
    """
    canvas = Image.new("RGBA", (size, size), background or (0, 0, 0, 0))
    inner = max(1, int(round(size * (1 - 2 * padding_ratio))))
    artwork = source.convert("RGBA").resize((inner, inner), Image.Resampling.NEAREST)
    offset = (size - inner) // 2
    canvas.paste(artwork, (offset, offset), artwork)
    return canvas


def check_icons(source: Image.Image) -> int:
    """生成されるはずの画像と既存ファイルの差分を検査する (ドリフト検出)。

    Args:
        source: 元ドット絵 (build_icon の入力)。

    Returns:
        int: 差分・欠落があったファイル数 (0 なら一致)。

    Notes:
        P3 (2026-09-16 独立査読): manifest のアイコン定義と生成スクリプトが二重管理に
        なりやすいため `--check` モードを用意し、リリース前にドリフトを検出できるようにする。
    """
    drifted = 0
    for file_name, size, padding_ratio, background in ICON_SPECS:
        target = OUTPUT_DIR / file_name
        expected = build_icon(source, size, padding_ratio, background)
        if not target.is_file():
            print(f"[NG] 未生成: {target.relative_to(PROJECT_ROOT)}")
            drifted += 1
            continue
        with Image.open(target) as existing:
            actual = existing.convert("RGBA")
        if actual.size != expected.size or actual.tobytes() != expected.tobytes():
            print(f"[NG] ドリフト検出: {target.relative_to(PROJECT_ROOT)}")
            drifted += 1
        else:
            print(f"[OK] 一致: {target.relative_to(PROJECT_ROOT)}")
    return drifted


def main(argv: Optional[List[str]] = None) -> int:
    """全スペックのアイコンを生成する（または `--check` で差分検査する）。

    Args:
        argv: コマンドライン引数（省略時は sys.argv）。

    Returns:
        int: プロセス終了コード (0=成功, 1=元アセット不在/ドリフト検出)。
    """
    parser = argparse.ArgumentParser(description="PWAホーム画面アイコンの生成 / 差分検査")
    parser.add_argument(
        "--check",
        action="store_true",
        help="生成は行わず、既存ファイルが仕様どおりかを検査する（差分があれば終了コード1）",
    )
    args = parser.parse_args(argv)

    if not SOURCE_ART.is_file():
        print(f"[NG] 元ドット絵が見つかりません: {SOURCE_ART}")
        return 1

    with Image.open(SOURCE_ART) as opened:
        source = opened.copy()

    if args.check:
        drifted = check_icons(source)
        if drifted:
            print(f"[NG] {drifted} 件が仕様と不一致です。`python tools/build_pwa_icons.py` で再生成してください。")
            return 1
        print("[OK] 全アイコンが仕様と一致しています")
        return 0

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for file_name, size, padding_ratio, background in ICON_SPECS:
        target = OUTPUT_DIR / file_name
        build_icon(source, size, padding_ratio, background).save(target)
        print(f"[OK] 生成: {target.relative_to(PROJECT_ROOT)} ({size}x{size})")

    print("PWAホーム画面アイコンの生成が完了しました")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
