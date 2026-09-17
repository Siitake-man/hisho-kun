#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - 同梱リソース定義の単体テスト (tests/test_build_resources.py)

背景 (P1 / 2026-09-16 独立査読):
    `neo_hisho.spec` は `('docs/guides', 'docs/guides')` とディレクトリ丸ごとを同梱していたため、
    追跡下に残っていた旧バックアップ `NEO_HISHO_CHEAT_SHEETS.html.bak` が配布物へ混入していた
    （ポート番号も旧値のまま）。同梱可否の判断を `build_resources.py` へ集約し、
    テスト不能なインライン式を排除する。
"""

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import build_resources  # noqa: E402


class TestBundleSourceFiltering(unittest.TestCase):
    """同梱エントリ生成（バックアップ除外）の契約"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "guide.md").write_text("ok", encoding="utf-8")
        (self.root / "cheatsheet.html").write_text("ok", encoding="utf-8")
        (self.root / "assets").mkdir()
        (self.root / "NEO_HISHO_CHEAT_SHEETS.html.bak").write_text("stale", encoding="utf-8")
        (self.root / "draft.md.tmp").write_text("stale", encoding="utf-8")
        (self.root / "old.orig").write_text("stale", encoding="utf-8")
        (self.root / "cached.pyc").write_bytes(b"\x00\x01")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_includes_guides_and_subdirectories(self) -> None:
        """通常ファイルとサブディレクトリは同梱されること"""
        names = {Path(src).name for src, _dest in build_resources.iter_bundle_sources(self.root, "docs/guides")}

        self.assertIn("guide.md", names)
        self.assertIn("cheatsheet.html", names)
        self.assertIn("assets", names)

    def test_excludes_backups_and_temp_files(self) -> None:
        """旧バックアップ・一時ファイル・キャッシュは同梱されないこと（P1 の再発防止）"""
        names = {Path(src).name for src, _dest in build_resources.iter_bundle_sources(self.root, "docs/guides")}

        for excluded in ("NEO_HISHO_CHEAT_SHEETS.html.bak", "draft.md.tmp", "old.orig", "cached.pyc"):
            with self.subTest(name=excluded):
                self.assertNotIn(excluded, names)

    def test_dest_directory_is_preserved(self) -> None:
        """配置先ディレクトリ名が全エントリで維持されること"""
        for _src, dest in build_resources.iter_bundle_sources(self.root, "docs/guides"):
            self.assertEqual(dest, "docs/guides")

    def test_order_is_deterministic(self) -> None:
        """並び順が決定的（ビルド差分を安定化）であること"""
        first = build_resources.iter_bundle_sources(self.root, "docs/guides")
        second = build_resources.iter_bundle_sources(self.root, "docs/guides")

        self.assertEqual(first, second)
        self.assertEqual([src for src, _ in first], sorted(src for src, _ in first))

    def test_missing_directory_returns_empty(self) -> None:
        """ディレクトリ不在でも例外を出さず空リストを返すこと（ビルドを止めない）"""
        self.assertEqual(
            build_resources.iter_bundle_sources(self.root / "no_such_dir", "docs/guides"), []
        )

    def test_real_docs_guides_has_no_backup_entries(self) -> None:
        """実リポジトリの docs/guides 同梱エントリにバックアップが含まれないこと（統合確認）"""
        entries = build_resources.iter_bundle_sources(PROJECT_ROOT / "docs" / "guides", "docs/guides")
        names = [Path(src).name for src, _ in entries]

        self.assertTrue(names, "docs/guides が空です（同梱リソース定義を確認してください）")
        self.assertFalse(
            [n for n in names if n.endswith((".bak", ".tmp", ".orig"))],
            f"バックアップが同梱対象に含まれています: {names}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
