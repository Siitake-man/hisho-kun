#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - README用 ドット絵ペット アニメーションGIF生成ツール (tools/generate_pet_gif.py)

初回リリース2大キャラクター（秘書くん・カイル風精霊）のスプライトを合成し、
透明背景を美しく保った高品質・軽量なループGIFを生成します。
"""

import sys
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOT_DIR = PROJECT_ROOT / "assets" / "dot"


def create_character_gif(
    char_name: str,
    frame_filenames: list[str],
    durations: list[int],
    output_filename: str,
    scale: int = 2
) -> Path:
    """指定されたキャラのフレームから透明ループGIFを生成する。"""
    char_dir = DOT_DIR / char_name
    output_path = DOT_DIR / output_filename

    frames = []
    for fname in frame_filenames:
        img_path = char_dir / fname
        if not img_path.exists():
            print(f"⚠️ スキップ: {img_path} が見つかりません")
            continue

        img = Image.open(img_path).convert("RGBA")
        if scale > 1:
            # ドット絵の輪郭をシャープに保つニアレストネイバー拡大
            img = img.resize((img.width * scale, img.height * scale), Image.Resampling.NEAREST)

        # 透過チャンネルの安全なパレット化 (disposal=2 用)
        alpha = img.split()[3]
        p_img = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=254)
        mask = Image.eval(alpha, lambda a: 255 if a <= 128 else 0)
        p_img.paste(255, mask)
        p_img.info["transparency"] = 255
        frames.append(p_img)

    if not frames:
        print(f"❌ エラー: {char_name} のフレームがありません")
        return output_path

    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        disposal=2  # 残像防止 (Clear to background)
    )
    print(f"✅ 生成成功: {output_path} ({output_path.stat().st_size / 1024:.1f} KB)")
    return output_path


def main():
    print("🎨 ネオ秘書くん 公式2大キャラのアニメーションGIF生成開始...")

    # 1. 秘書くん (メインループ: 待機 → 瞬き → 応援 → 歓喜ジャンプ)
    hisho_frames = [
        "idle_1.png", "idle_1.png", "idle_2.png", "idle_1.png",
        "cheer.png", "cheer.png",
        "celebrate_1.png", "celebrate_2.png", "celebrate_3.png", "celebrate_2.png",
        "happy.png", "idle_1.png"
    ]
    hisho_durations = [350, 350, 200, 350, 250, 250, 180, 180, 180, 180, 400, 300]
    create_character_gif("hisho", hisho_frames, hisho_durations, "hisho_animated.gif", scale=2)

    # 2. カイル君 (レトロ案内精霊ループ: 待機プカプカ → てくてく泳ぎ → 応援ピョン → クルッと歓喜)
    kyle_frames = [
        "idle_1.png", "idle_2.png", "idle_1.png",
        "walk_1.png", "walk_2.png",
        "cheer.png", "cheer.png",
        "celebrate_1.png", "celebrate_2.png", "celebrate_3.png",
        "happy.png"
    ]
    kyle_durations = [350, 350, 300, 200, 200, 250, 250, 180, 180, 180, 400]
    create_character_gif("kyle", kyle_frames, kyle_durations, "kyle_animated.gif", scale=2)

    print("🎉 秘書くん ＆ カイル君のアニメーションGIF生成が完了しました！")


if __name__ == "__main__":
    main()
