"""
ネオ秘書くん - 画面見守り (Vision) ＆ スクリーンキャプチャツール (vision_tools.py)

MiniCPM-V やマルチモーダルLLMに着想を得た、画面キャプチャ・アクティブウィンドウ解析・
エラー検知・作業見守りのためのツール群。
"""

import os
import io
import base64
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from PIL import Image, ImageGrab
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# スクリーンショット一時保存ディレクトリ
SCREENSHOT_DIR = Path(__file__).parent / "assets" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def take_screenshot(max_dimension: int = 1280, quality: int = 85) -> Dict[str, Any]:
    """
    Windowsのデスクトップ画面をキャプチャし、Base64文字列および一時ファイルパスを返します。
    LLMに渡しやすいよう、アスペクト比を維持しながらリサイズと圧縮を行います。
    
    Args:
        max_dimension: 画像の最大長辺（px）
        quality: JPEG/PNG圧縮クオリティ
        
    Returns:
        Dict[str, Any]: {
            "file_path": str,
            "base64_data": str,
            "width": int,
            "height": int,
            "timestamp": str
        }
    """
    try:
        # 全画面キャプチャ
        screenshot = ImageGrab.grab()
        orig_w, orig_h = screenshot.size
        
        # リサイズ計算（長辺をmax_dimensionに収める）
        scale = min(1.0, max_dimension / max(orig_w, orig_h))
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        
        if scale < 1.0:
            resized_img = screenshot.resize((new_w, new_h), Image.Resampling.LANCZOS)
        else:
            resized_img = screenshot
            
        # 一時ファイル保存
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screen_{timestamp}.jpg"
        file_path = SCREENSHOT_DIR / filename
        
        # JPEG保存（RGB変換）
        rgb_img = resized_img.convert("RGB")
        rgb_img.save(file_path, format="JPEG", quality=quality)
        
        # Base64エンコード
        buffered = io.BytesIO()
        rgb_img.save(buffered, format="JPEG", quality=quality)
        base64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        logger.info(f"画面キャプチャ成功: {file_path} (サイズ: {new_w}x{new_h})")
        return {
            "file_path": str(file_path),
            "base64_data": base64_str,
            "width": new_w,
            "height": new_h,
            "timestamp": timestamp
        }
    except Exception as e:
        logger.error(f"画面キャプチャ失敗: {e}")
        raise RuntimeError(f"画面のキャプチャに失敗しました: {e}")


@tool
def capture_screen_tool(focus_area: Optional[str] = None) -> str:
    """
    ボスの現在のデスクトップ画面をキャプチャし、視覚的な観察用データを取得します。
    ボスから「画面を見て」「このエラーどうすればいい？」「今何してるかわかる？」と
    言われた際に呼び出します。
    
    Args:
        focus_area: 注目したい領域や対象（例: 'エラーメッセージ', 'コード画面', 'ブラウザ'）
        
    Returns:
        str: キャプチャ成功メッセージと画像ファイル情報
    """
    try:
        data = take_screenshot(max_dimension=1280)
        file_path = data["file_path"]
        w = data["width"]
        h = data["height"]
        
        focus_msg = f"（注目領域: {focus_area}）" if focus_area else ""
        return (
            f"📸 画面のキャプチャに成功しました！{focus_msg}\n"
            f"ファイル: {file_path} (解像度: {w}x{h})\n"
            f"※ 画面を観察し、ユーザーの状況やエラーに対する具体的なアドバイスを行ってください。"
        )
    except Exception as e:
        return f"❌ 画面キャプチャ中にエラーが発生しました: {e}"


@tool
def analyze_screen_error_tool(error_hint: Optional[str] = None) -> str:
    """
    画面上のエラーダイアログ、ターミナルの例外スタックトレース、または不具合を検知して解析します。
    
    Args:
        error_hint: ユーザーが言及しているエラーの概要（省略可）
        
    Returns:
        str: エラー解析用キャプチャ情報
    """
    try:
        data = take_screenshot(max_dimension=1440)
        return (
            f"🔍 エラー検知用スクリーンショットを取得しました（{data['file_path']}）。\n"
            f"画面上の赤文字エラー、警告ダイアログ、コマンドの失敗ログを読み取り、"
            f"原因（Why）と具体的な解決コマンド/手順（How）を提示してください。"
        )
    except Exception as e:
        return f"❌ エラー画面のキャプチャに失敗しました: {e}"
