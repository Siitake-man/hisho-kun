"""
ネオ秘書くん - デスクトップ吹き出し用 マークダウン軽量パーサー (ui/markdown_helper.py)

LLMやブリーフィングエンジンが出力する Markdown 記法（**太字**, *イタリック*）を
解析し、アスタリスク文字を除去したうえで Tkinter Text のタグ機能（Bold / Accent）を用いて
レトロモダンな高品質タイポグラフィで強調表示します。
"""

import re
import tkinter as tk
from typing import List, Tuple, Any, Optional


def parse_markdown_spans(text: str) -> Tuple[str, List[Tuple[int, int, str]]]:
    """マークダウン文字列から太字記法を抽出し、平文化テキストと装飾スパンを返す。

    Args:
        text: 解析対象の生テキスト（マークダウン含む）。

    Returns:
        Tuple[str, List[Tuple[int, int, str]]]:
            - クリーン化された平文テキスト
            - 装飾スパンのリスト [(start_char_index, end_char_index, tag_name), ...]
    """
    if not text:
        return "", []

    # 1. 太字記法 (**テキスト**) のマッチング
    #    アスタリスク2個で囲まれた最短一致
    pattern = re.compile(r'\*\*(.+?)\*\*')

    clean_chars: List[str] = []
    spans: List[Tuple[int, int, str]] = []

    last_end = 0
    current_clean_pos = 0

    for match in pattern.finditer(text):
        start_match, end_match = match.span()

        # マッチ前の通常テキストを追加
        if start_match > last_end:
            prefix = text[last_end:start_match]
            clean_chars.append(prefix)
            current_clean_pos += len(prefix)

        # 太字部分を追加
        bold_content = match.group(1)
        bold_start = current_clean_pos
        clean_chars.append(bold_content)
        current_clean_pos += len(bold_content)
        bold_end = current_clean_pos

        spans.append((bold_start, bold_end, "bold"))
        last_end = end_match

    # 残りの通常テキストを追加
    if last_end < len(text):
        tail = text[last_end:]
        clean_chars.append(tail)

    clean_text = "".join(clean_chars)
    return clean_text, spans


def clean_markdown_text(text: str) -> str:
    """マークダウン装飾記号を取り除いたプレーンテキストを返す。

    Args:
        text: 生テキスト。

    Returns:
        str: プレーンテキスト。
    """
    clean_text, _ = parse_markdown_spans(text)
    # 単一アスタリスク (*イタリック*) も平文化
    clean_text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', clean_text)
    return clean_text


def render_markdown_to_textbox(
    textbox: Any,
    text: str,
    font_family: str = "DotGothic16",
    font_size: int = 13,
    bold_color: str = "#2A1B12",
    normal_color: str = "#4A3B32",
) -> str:
    """CTkTextbox または tk.Text へマークダウンをパースして装飾適用して描画する。

    Args:
        textbox: CTkTextbox または tk.Text インスタンス。
        text: 描画するテキスト（Markdown 含む）。
        font_family: 基本フォント名。
        font_size: 基本フォントサイズ。
        bold_color: 強調文字の前景色。
        normal_color: 通常文字の前景色。

    Returns:
        str: 実際に挿入されたプレーンテキスト（URL検出等の後続処理用）。
    """
    clean_text, spans = parse_markdown_spans(text)

    # CTkTextbox は内部の tk.Text を _textbox 属性に持つ
    inner_text: tk.Text = getattr(textbox, "_textbox", textbox)

    # 編集可能にして内容をクリア
    try:
        textbox.configure(state="normal")
    except Exception:
        pass

    inner_text.delete("1.0", tk.END)

    # 太字タグのスタイル設定（フォント・カラー）
    # フォントがシステムにない場合はフォールバック
    available_fonts = tk.font.families() if hasattr(tk, "font") and hasattr(tk.font, "families") else []
    actual_font_family = font_family if font_family in available_fonts else "Meiryo UI"

    bold_font = (actual_font_family, font_size, "bold")
    normal_font = (actual_font_family, font_size)

    inner_text.tag_config("md_bold", font=bold_font, foreground=bold_color)
    inner_text.tag_config("md_normal", font=normal_font, foreground=normal_color)

    # テキスト挿入
    inner_text.insert("1.0", clean_text, "md_normal")

    # 装飾タグの適用 (character offset -> Tkinter index)
    for start_char, end_char, tag in spans:
        if tag == "bold":
            start_index = f"1.0 + {start_char} chars"
            end_index = f"1.0 + {end_char} chars"
            inner_text.tag_add("md_bold", start_index, end_index)

    # 読み取り専用に再設定
    try:
        textbox.configure(state="disabled")
    except Exception:
        pass

    try:
        textbox.see("1.0")
    except Exception:
        pass

    return clean_text
