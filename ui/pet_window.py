"""
ネオ秘書くん - デスクトップ常駐ペット吹き出し ＆ キャンバス描画 (ui/pet_window.py)

Sprint Global (Phase 2: デスクトップGUI ＆ LLM動的制御) 準拠。
Tkinter Canvas 上での吹き出し描画、動的バブル幅スケーリング (220px〜320px)、
英単語単位自動折り返し (Word Wrapping) を提供する Deep Module。
"""

from __future__ import annotations

import logging
import tkinter as tk
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# バブル描画パラメータ (DESIGN_SPEC 準拠)
MIN_BUBBLE_WIDTH: int = 220
MAX_BUBBLE_WIDTH: int = 320
BUBBLE_PADDING_X: int = 14
BUBBLE_PADDING_Y: int = 10
BUBBLE_BG_COLOR: str = "#FFFFFF"
BUBBLE_BORDER_COLOR: str = "#4A3B32"
BUBBLE_BORDER_WIDTH: int = 2
BUBBLE_CORNER_RADIUS: int = 8
TEXT_COLOR: str = "#4A3B32"
DEFAULT_FONT_FAMILY: str = "Meiryo UI"
DEFAULT_FONT_SIZE: int = 10


def calculate_bubble_width(
    text: str,
    min_width: int = MIN_BUBBLE_WIDTH,
    max_width: int = MAX_BUBBLE_WIDTH,
) -> int:
    """テキスト長（文字数）に応じて、バブルの横幅を動的に伸縮（220px〜320px）させる。

    Args:
        text: 表示するテキスト。
        min_width: 最小幅 (既定: 220px)。
        max_width: 最大幅 (既定: 320px)。

    Returns:
        int: 計算されたバブル幅 (min_width <= width <= max_width)。
    """
    if not text:
        return min_width

    # 文字数による動的伸縮 (25文字以下: 最小220px, 90文字以上: 最大320px, 中間は線形スケーリング)
    char_count = len(text)
    if char_count <= 25:
        target_width = min_width
    elif char_count >= 90:
        target_width = max_width
    else:
        ratio = (char_count - 25) / (90 - 25)
        target_width = int(min_width + ratio * (max_width - min_width))

    return max(min_width, min(max_width, target_width))


def draw_rounded_rect(
    canvas: tk.Canvas,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    radius: float = BUBBLE_CORNER_RADIUS,
    **kwargs: Any,
) -> int:
    """Tkinter Canvas 上に滑らかな角丸矩形ポリゴンを描画する。

    Args:
        canvas: 描画対象 Canvas
        x0, y0: 左上座標
        x1, y1: 右下座標
        radius: 角丸半径
        **kwargs: create_polygon に渡す描画オプション (fill, outline, width等)

    Returns:
        int: 作成されたポリゴンのCanvasアイテムID
    """
    radius = min(radius, (x1 - x0) / 2, (y1 - y0) / 2)
    points = [
        x0 + radius, y0,
        x1 - radius, y0,
        x1, y0,
        x1, y0 + radius,
        x1, y1 - radius,
        x1, y1,
        x1 - radius, y1,
        x0 + radius, y1,
        x0, y1,
        x0, y1 - radius,
        x0, y0 + radius,
        x0, y0,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def _sanitize_wrap_text(text: str, max_chars: int = 180) -> str:
    """長大な英単語や超過文字列を安全に分割・切り落とす。

    1000文字爆弾や改行・空白のないトークン列によるキャンバス突き抜け・
    ペット画像窒息死を構造的に防止する（devils-advocate 防御）。
    """
    if not text:
        return ""
    # 1. 文字数制限（180文字超過時は Truncate）
    if len(text) > max_chars:
        text = text[:max_chars - 3].rstrip() + "..."
    # 2. 空白のない25文字以上の英数字トークンを強制分割（Word Wrapping破綻防止）
    lines = text.split("\n")
    safe_lines = []
    for line in lines:
        words = line.split(" ")
        safe_words = []
        for word in words:
            if len(word) > 25:
                chunks = [word[i:i+25] for i in range(0, len(word), 25)]
                safe_words.append(" ".join(chunks))
            else:
                safe_words.append(word)
        safe_lines.append(" ".join(safe_words))
    return "\n".join(safe_lines)


def draw_speech_bubble(
    canvas: tk.Canvas,
    text: str,
    x: float,
    y: float,
    tag: str = "speech_bubble",
    font: Optional[Tuple[str, int]] = None,
    min_width: int = MIN_BUBBLE_WIDTH,
    max_width: int = MAX_BUBBLE_WIDTH,
    max_chars: int = 180,
    max_height: int = 140,
    padding_x: int = BUBBLE_PADDING_X,
    padding_y: int = BUBBLE_PADDING_Y,
    bg_color: str = BUBBLE_BG_COLOR,
    border_color: str = BUBBLE_BORDER_COLOR,
    border_width: int = BUBBLE_BORDER_WIDTH,
    text_color: str = TEXT_COLOR,
    tail: bool = True,
    tail_direction: str = "bottom",
) -> Tuple[int, int]:
    """キャンバス上に動的サイジングと英単語Word Wrappingを備えた吹き出しを描画する。

    テキスト長（文字数）に応じてバブル横幅を220px〜320pxの範囲で動的スケーリングし、
    Tkinter Canvas の create_text に適切な width（バブル幅 - パディング）を指定して
    英単語単位の自動折り返し（Word Wrapping）を効かせます。

    Args:
        canvas: 描画先 Tkinter Canvas
        text: 表示する吹き出し本文
        x: 吹き出し上辺中央のX座標
        y: 吹き出し上辺のY座標
        tag: Canvasタグ（既存バブルのクリーンアップ・再描画用）
        font: フォント設定タプル (family, size)
        min_width: 吹き出し最小幅 (px)
        max_width: 吹き出し最大幅 (px)
        max_chars: 許容最大文字数 (超過時 Truncate)
        max_height: 許容最大高 (px, 超過時 clamp)
        padding_x: 左右内側パディング (px)
        padding_y: 上下内側パディング (px)
        bg_color: 吹き出し背景色
        border_color: 吹き出し枠線色
        border_width: 枠線幅
        text_color: テキスト色
        tail: 吹き出しの尻尾（三角ポインタ）を描画するか
        tail_direction: 尻尾の方向 ("bottom", "top")

    Returns:
        Tuple[int, int]: (描画されたバブル幅, 描画されたバブル高)
    """
    try:
        # 1. 既存の同名タグアイテムを安全に消去
        canvas.delete(tag)

        if not text:
            return (0, 0)

        # 1.5 サニタイズ（180文字制限 ＆ 25文字超トークン強制分割）
        safe_text = _sanitize_wrap_text(text, max_chars=max_chars)

        # 2. テキスト長に応じたバブル横幅の動的伸縮 (220px〜320px)
        bubble_w = calculate_bubble_width(safe_text, min_width=min_width, max_width=max_width)

        # 3. Canvas text の折り返し有効幅 (Word Wrapping) を計算
        wrap_width = max(100, bubble_w - (padding_x * 2))

        font_tuple = font or (DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE)

        # 4. まずテキストアイテムを仮配置して実描画高さを算出
        # anchor="n" で上中央基準
        text_id = canvas.create_text(
            x,
            y + padding_y,
            text=safe_text,
            width=wrap_width,
            font=font_tuple,
            fill=text_color,
            anchor="n",
            justify="left",
            tags=(tag, f"{tag}_text"),
        )

        bbox = canvas.bbox(text_id)
        if bbox:
            text_height = bbox[3] - bbox[1]
        else:
            text_height = DEFAULT_FONT_SIZE * 2

        # 5. バブル全体の高さを決定 (尻尾を含めて max_height で clamp)
        actual_tail_h = 8 if tail else 0
        usable_max_h = max(40, max_height - actual_tail_h)
        bubble_h = min(usable_max_h, text_height + (padding_y * 2))

        # 6. バブル四隅座標 (xは上辺中央を基準とする)
        left = x - (bubble_w / 2.0)
        right = x + (bubble_w / 2.0)
        top = y
        bottom = y + bubble_h

        # 7. 吹き出し角丸背景ポリゴンを描画
        rect_id = draw_rounded_rect(
            canvas,
            left,
            top,
            right,
            bottom,
            radius=BUBBLE_CORNER_RADIUS,
            fill=bg_color,
            outline=border_color,
            width=border_width,
            tags=(tag, f"{tag}_bg"),
        )

        # 8. 吹き出しの尻尾（ポインタ）の描画
        if tail:
            tail_w = 12
            tail_h = actual_tail_h
            if tail_direction == "bottom":
                tail_points = [
                    x - (tail_w / 2), bottom - border_width,
                    x + (tail_w / 2), bottom - border_width,
                    x, bottom + tail_h,
                ]
            else:
                tail_points = [
                    x - (tail_w / 2), top + border_width,
                    x + (tail_w / 2), top + border_width,
                    x, top - tail_h,
                ]

            canvas.create_polygon(
                tail_points,
                fill=bg_color,
                outline=border_color,
                width=border_width,
                tags=(tag, f"{tag}_tail"),
            )
            # 境目の線を隠すため内側に背景色パッチを配置
            if tail_direction == "bottom":
                canvas.create_line(
                    x - (tail_w / 2) + 1, bottom,
                    x + (tail_w / 2) - 1, bottom,
                    fill=bg_color,
                    width=border_width + 1,
                    tags=(tag, f"{tag}_tail_cover"),
                )

        # 9. テキストを最前面に持ってくる
        canvas.tag_raise(text_id)

        total_h = min(max_height, int(bubble_h + actual_tail_h))
        return (bubble_w, total_h)

    except Exception as e:
        logger.error("吹き出し描画エラー: %s", e, exc_info=True)
        # フォールバック: 単純なテキストのみ描画
        try:
            canvas.create_text(
                x, y, text=text[:50], fill=text_color, anchor="n", tags=(tag,)
            )
        except Exception:
            pass
        return (min_width, 40)


class PetBubbleManager:
    """デスクトップペット用の吹き出し管理マネージャクラス (Deep Module)。

    長いセリフのページ分割、動的サイズ計算、フォント設定を隠蔽し、
    Tkinter Canvas への一貫した吹き出しレンダリングを提供します。
    """

    def __init__(
        self,
        canvas: tk.Canvas,
        center_x: float = 170.0,
        top_y: float = 10.0,
        font_family: str = DEFAULT_FONT_FAMILY,
        font_size: int = DEFAULT_FONT_SIZE,
    ):
        self.canvas = canvas
        self.center_x = center_x
        self.top_y = top_y
        self.font = (font_family, font_size)
        self.current_text: str = ""
        self.bubble_width: int = MIN_BUBBLE_WIDTH
        self.bubble_height: int = 40

    def show_message(self, text: str, tail: bool = True) -> Tuple[int, int]:
        """メッセージを吹き出しとしてキャンバスに描画する。

        Args:
            text: 表示するテキスト。
            tail: 吹き出しの尻尾を描画するか。

        Returns:
            Tuple[int, int]: (描画幅, 描画高)
        """
        self.current_text = text or ""
        w, h = draw_speech_bubble(
            canvas=self.canvas,
            text=self.current_text,
            x=self.center_x,
            y=self.top_y,
            tag="pet_speech_bubble",
            font=self.font,
            min_width=MIN_BUBBLE_WIDTH,
            max_width=MAX_BUBBLE_WIDTH,
            tail=tail,
        )
        self.bubble_width = w
        self.bubble_height = h
        return (w, h)

    def clear(self) -> None:
        """吹き出しをキャンバスから消去する。"""
        self.canvas.delete("pet_speech_bubble")
        self.current_text = ""
