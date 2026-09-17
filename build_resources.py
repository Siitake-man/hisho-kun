"""
ネオ秘書くん - 同梱リソース定義の Deep Module (build_resources.py)

PyInstaller (`neo_hisho.spec`) が `datas` に渡す「同梱リソースの一覧生成」を
本モジュールへ集約します。

設計意図 (Why):
- 「何を配布物に含めるか」の判断を spec 内のインライン式に書くと、テスト不能なまま
  配布物だけが変わってしまう（例: `docs/guides/*.bak` のような旧バックアップが
  ディレクトリごと同梱されていた / 2026-09-16 独立査読で発見）。
- 純粋関数として切り出せば、一時ディレクトリで挙動を検証できる。
"""

import logging
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

# 同梱から除外するサフィックス（エディタ/手動バックアップ・一時ファイル）
EXCLUDED_BUNDLE_SUFFIXES = (".bak", ".tmp", ".orig", ".pyc")


def is_bundle_excluded(path: Path) -> bool:
    """同梱対象から除外すべきファイルかどうかを判定する。

    Args:
        path: 判定対象のパス（ディレクトリは常に対象）。

    Returns:
        bool: 除外すべき場合 True（バックアップ/一時ファイルなど）。
    """
    if not path.is_file():
        return False
    if path.suffix.lower() in EXCLUDED_BUNDLE_SUFFIXES:
        return True
    if path.name.endswith(".bak") or path.name.endswith(".tmp"):
        return True
    return False


def iter_bundle_sources(directory: Path, dest: str) -> List[Tuple[str, str]]:
    """ディレクトリ配下を `datas` 用の (src, dest) エントリへ展開する。

    Args:
        directory: 同梱元ディレクトリ。
        dest: 配布物内の配置先（同ディレクトリ名を指定する運用）。

    Returns:
        List[Tuple[str, str]]: 除外規則を適用した (絶対パス, 配置先) の並び。
            並びは決定的（ソート済み）で、再ビルド時の差分を安定させる。

    Notes:
        ディレクトリ自体が存在しない場合は空リストを返す（ビルドを止めない）。
    """
    if not directory.is_dir():
        logger.warning(f"同梱対象ディレクトリが存在しません: {directory}")
        return []

    entries: List[Tuple[str, str]] = []
    for child in sorted(directory.iterdir()):
        if is_bundle_excluded(child):
            logger.info(f"同梱から除外しました（バックアップ等）: {child.name}")
            continue
        entries.append((str(child), dest))
    return entries
