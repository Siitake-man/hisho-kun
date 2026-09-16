"""
ネオ秘書くん - ウィンドウアイコン適用 Seam (ui/window_icon.py)

メインウィンドウ (gui.py) と各ダイアログ (手帳 / 設定 / QR接続) に対し、
初代秘書くんのアイコンを「例外安全」に適用します。

設計方針 (Why):
- Windows では ``iconbitmap(.ico)`` がタスクバー/Alt+Tab のアイコンに反映される
  ため第一候補とする。未対応環境では PNG を ``iconphoto`` へフォールバックし、
  アイコンが無いより「アプリが落ちない」ことを優先する (起動を止めない)。
- 適用処理を本モジュールへ集約することで、各ウィンドウは 1 行呼ぶだけで済む
  (Deep Module / 重複排除)。
"""

import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

# Windows タスクバー/EXE 用アイコン (PyInstaller も同じファイルを参照する)
ICON_ICO_PATH = ASSETS_DIR / "icon.ico"

# PNG フォールバック用 (初代秘書くんドット絵)
ICON_PNG_PATH = ASSETS_DIR / "dot" / "hisho" / "idle_1.png"

# iconphoto に渡した画像は参照を保持しないと GC され、アイコンが消える
_PHOTO_REF_ATTR = "_neo_hisho_icon_photo"


def apply_window_icon(window: Any, ico_path: Optional[Path] = None) -> bool:
    """Tk / CustomTkinter ウィンドウへネオ秘書くんアイコンを適用する。

    Args:
        window: 対象ウィンドウ (``iconbitmap`` / ``iconphoto`` を持つ Tk ウィジェット)。
        ico_path: 任意の .ico パス (省略時は ``assets/icon.ico``)。

    Returns:
        bool: いずれかの手段でアイコンを適用できた場合 True。
            全手段が失敗しても例外は漏らさず False を返す (起動継続を優先)。

    Notes:
        ``iconbitmap`` は Windows 専用 (.ico 必須) のため、失敗時は PNG の
        ``iconphoto`` へフォールバックする。
    """
    ico = Path(ico_path) if ico_path else ICON_ICO_PATH

    if ico.is_file():
        try:
            window.iconbitmap(str(ico))
            logger.debug(f"ウィンドウアイコン(.ico)を適用しました: {ico}")
            return True
        except Exception as e:
            logger.debug(f"ウィンドウアイコン(.ico)適用に失敗 → PNGへフォールバック: {e}")

    return _apply_photo_fallback(window)


def _apply_photo_fallback(window: Any) -> bool:
    """PNG (ドット絵) を iconphoto で適用するフォールバック。

    Args:
        window: 対象ウィンドウ。

    Returns:
        bool: 適用できた場合 True (失敗時は False を返し例外を漏らさない)。
    """
    try:
        from PIL import Image, ImageTk

        image = ImageTk.PhotoImage(Image.open(ICON_PNG_PATH).convert("RGBA"))
        window.iconphoto(False, image)
        # GC 対策: 参照をウィンドウ側へ保持させる
        setattr(window, _PHOTO_REF_ATTR, image)
        logger.debug("ウィンドウアイコン(PNG)を iconphoto で適用しました")
        return True
    except Exception as e:
        logger.debug(f"ウィンドウアイコン(PNG)適用スキップ: {e}")
        return False
