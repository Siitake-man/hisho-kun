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

from pathlib import Path
from typing import Optional

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_ART = PROJECT_ROOT / "assets" / "dot" / "hisho" / "happy.png"
OUTPUT_DIR = PROJECT_ROOT / "assets" / "pwa"

# PWA テーマ背景色 (web_pet/manifest.json の background_color と一致させる)
THEME_BACKGROUND = "#1A1C23"

# (ファイル名, 出力サイズ(px), 余白比率, 背景色 or None=透過)
# 余白 0.15 = 内側 70% に artwork を配置 (maskable のセーフゾーン規格に適合)
ICON_SPECS = (
    ("icon_192.png", 192, 0.0, None),
    ("icon_512.png", 512, 0.0, None),
    ("icon_maskable_512.png", 512, 0.15, THEME_BACKGROUND),
    ("apple_touch_icon_180.png", 180, 0.15, THEME_BACKGROUND),
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


def main() -> int:
    """全スペックのアイコンを生成する。

    Returns:
        int: プロセス終了コード (0=成功, 1=元アセット不在)。
    """
    if not SOURCE_ART.is_file():
        print(f"[NG] 元ドット絵が見つかりません: {SOURCE_ART}")
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with Image.open(SOURCE_ART) as opened:
        source = opened.copy()

    for file_name, size, padding_ratio, background in ICON_SPECS:
        target = OUTPUT_DIR / file_name
        build_icon(source, size, padding_ratio, background).save(target)
        print(f"[OK] 生成: {target.relative_to(PROJECT_ROOT)} ({size}x{size})")

    print("PWAホーム画面アイコンの生成が完了しました")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
