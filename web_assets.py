"""
ネオ秘書くん - 静的アセット配信のパス解決 Seam (web_assets.py)

PWA用の画像配信 (`GET /assets/...`) は、ブラウザが Bearer トークンを付けずに
取得するため「認証なしで公開」する設計を採っている。そのため
「どのファイルを配信して良いか」の判断が唯一の防壁となる。

設計方針 (Why):
- 判断ロジックを本モジュールの純粋関数へ集約し、HTTPハンドラは結果を使うだけにする
  (Deep Module / Seam)。HTTPを起動せず高速・決定的にテストできる。
- 多層防御: ①危険表現の事前排除 ②拡張子アローリスト ③解決後のルート配下検証。

【P0-1 (2026-09-16)】旧実装は `".." / 先頭"/" / ":"` のみを検査しており、
Windows の「\\」始まり絶対パスを通過させ `GET /assets/\\Windows\\win.ini` で
実ファイル本文が 200 で返っていた。本モジュールへの集約で根治する。
"""

import logging
import mimetypes
import re
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger(__name__)

# 配信ルート (リポジトリ直下の assets/)
ASSETS_ROOT = Path(__file__).resolve().parent / "assets"

# 配信を許可する拡張子 (PWAアイコン・ドット絵スプライトのみ)
ALLOWED_ASSET_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico"})

# 危険表現の事前排除: Windows区切り「\」・ドライブ指定「:」・%エンコード・絶対パス
_FORBIDDEN_PATTERN = re.compile(r"[\\:%]|^/")


def resolve_asset_path(
    filename: str, assets_root: Optional[Union[str, Path]] = None
) -> Optional[Path]:
    """アセット要求文字列を、配信可能な実ファイルパスへ解決する。

    Args:
        filename: ``/assets/`` 以降の要求文字列（クエリは呼び出し側で除去済みであること）。
        assets_root: 配信ルート（省略時は本モジュール隣の ``assets/``）。

    Returns:
        Optional[Path]: 配信可能な実ファイルパス。以下に該当する場合は None:
            - 空文字・ヌル文字・危険表現（``\\`` / ``:`` / ``%`` / 先頭 ``/``）を含む
            - 拡張子が ``ALLOWED_ASSET_SUFFIXES`` に無い（.env / .db / .py 等を遮断）
            - 解決結果が配信ルート配下でない（パストラバーサル）
            - ファイルが存在しない

    Notes:
        例外は漏らさず None を返す（呼び出し側は 404 応答で完結させる）。
    """
    root = Path(assets_root) if assets_root is not None else ASSETS_ROOT

    try:
        text = (filename or "").strip()
        if not text or "\x00" in text:
            return None
        # ① 危険表現の事前排除（Windows の「\」絶対パス等をここで落とす）
        if _FORBIDDEN_PATTERN.search(text):
            logger.warning(f"🚫 [Security] 不許可のアセット要求を遮断: {text!r}")
            return None
        # ② 拡張子アローリスト（画像のみ）
        if Path(text).suffix.lower() not in ALLOWED_ASSET_SUFFIXES:
            logger.warning(f"🚫 [Security] 非画像アセット要求を遮断: {text!r}")
            return None
        # ③ 解決後のルート配下検証（多層防御の最終関門）
        root_resolved = root.resolve()
        candidate = (root_resolved / text).resolve()
        if not candidate.is_relative_to(root_resolved) or not candidate.is_file():
            logger.warning(f"🚫 [Security] ルート外/不存在のアセット要求を遮断: {text!r}")
            return None
    except (OSError, ValueError, TypeError) as e:
        logger.debug(f"アセットパス解決を拒否: {filename!r} ({e})")
        return None

    return candidate


def guess_asset_content_type(path: Path) -> str:
    """配信するアセットの Content-Type を推定する。

    Args:
        path: 配信対象の実ファイルパス。

    Returns:
        str: MIME タイプ（推定不能時は application/octet-stream）。
    """
    return mimetypes.guess_type(str(path))[0] or "application/octet-stream"
