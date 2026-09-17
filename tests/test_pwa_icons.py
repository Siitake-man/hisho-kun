#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - スマホPWAホーム画面アイコンの単体テスト (tests/test_pwa_icons.py)

タスク3 (2026-09-16 Cline): 「ホーム画面に追加」時に美しい高解像度ドット絵が
表示されるよう、Web App Manifest / apple-touch-icon / Service Worker の
キャッシュ対象を整合させる。

発見された既存不整合 (本テストで回帰防止):
- manifest の 32x32 エントリが実在しない ./assets/idle_1.png を指していた (404)
- 192x192 / 512x512 と宣言しながら実体は 128x128 の happy.png だった (サイズ不一致)
- apple-touch-icon が未定義だった (iOS Safari でアイコンが出ない)

TDD: assets/pwa/*.png と index.html の apple-touch-icon が無い状態では Red。
"""

import json
import re
import sys
import unittest
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MANIFEST_PATH = PROJECT_ROOT / "web_pet" / "manifest.json"
INDEX_PATH = PROJECT_ROOT / "web_pet" / "index.html"
SW_PATH = PROJECT_ROOT / "web_pet" / "sw.js"
GENERATOR_PATH = PROJECT_ROOT / "tools" / "build_pwa_icons.py"


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _manifest_icon_path(src: str) -> Path:
    """./assets/... 形式の src を実ファイルパスへ解決する (サーバーの /assets 配信に対応)。"""
    return PROJECT_ROOT / src.lstrip("./").replace("\\", "/")


class TestManifestIcons(unittest.TestCase):
    """Web App Manifest のアイコン定義契約"""

    def setUp(self) -> None:
        self.manifest = _load_manifest()

    def test_manifest_declares_square_192_and_512(self) -> None:
        """192x192 と 512x512 のアイコンが宣言されていること (インストール要件)"""
        sizes = {icon.get("sizes") for icon in self.manifest["icons"]}
        self.assertIn("192x192", sizes)
        self.assertIn("512x512", sizes)

    def test_manifest_declares_maskable_icon(self) -> None:
        """maskable アイコンが宣言されていること (Android の丸型マスク対応)"""
        purposes = [icon.get("purpose", "") for icon in self.manifest["icons"]]
        self.assertTrue(any("maskable" in p for p in purposes))

    def test_manifest_icon_files_exist(self) -> None:
        """宣言されたアイコンファイルがすべて実在すること (404 根絶)"""
        for icon in self.manifest["icons"]:
            with self.subTest(src=icon["src"]):
                path = _manifest_icon_path(icon["src"])
                self.assertTrue(path.is_file(), f"アイコンが存在しません: {path}")

    def test_declared_sizes_match_actual_pixels(self) -> None:
        """宣言サイズと実画像サイズが一致すること (不一致はインストール拒否の原因)"""
        for icon in self.manifest["icons"]:
            with self.subTest(src=icon["src"]):
                path = _manifest_icon_path(icon["src"])
                declared = int(icon["sizes"].split("x")[0])
                with Image.open(path) as img:
                    self.assertEqual(img.size, (declared, declared))

    def test_maskable_icon_is_opaque(self) -> None:
        """maskable アイコンは透過を持たないこと (マスク時に欠けないため)"""
        maskable = [
            icon for icon in self.manifest["icons"] if "maskable" in icon.get("purpose", "")
        ]
        self.assertTrue(maskable)
        for icon in maskable:
            with self.subTest(src=icon["src"]):
                path = _manifest_icon_path(icon["src"])
                with Image.open(path) as img:
                    alpha_min = img.convert("RGBA").getchannel("A").getextrema()[0]
                self.assertEqual(
                    alpha_min,
                    255,
                    "maskable アイコンに透過ピクセルが含まれています",
                )


class TestIndexHtmlIcons(unittest.TestCase):
    """iOS Safari / ブラウザタブ向けアイコン指定の契約"""

    def setUp(self) -> None:
        self.html = INDEX_PATH.read_text(encoding="utf-8")

    def test_apple_touch_icon_is_declared(self) -> None:
        """apple-touch-icon が宣言されていること"""
        self.assertIn('rel="apple-touch-icon"', self.html)

    def test_apple_touch_icon_file_exists(self) -> None:
        """apple-touch-icon の参照先ファイルが実在すること"""
        match = re.search(r'<link[^>]*rel="apple-touch-icon"[^>]*href="([^"]+)"', self.html)
        self.assertIsNotNone(match, "apple-touch-icon の href を抽出できません")
        path = _manifest_icon_path(match.group(1))
        self.assertTrue(path.is_file(), f"apple-touch-icon が存在しません: {path}")

    def test_favicon_png_is_declared(self) -> None:
        """ブラウザタブ用 favicon (PNG) が宣言されていること"""
        match = re.search(r'<link[^>]*rel="icon"[^>]*href="([^"]+)"', self.html)
        self.assertIsNotNone(match, "favicon の href を抽出できません")
        self.assertTrue(_manifest_icon_path(match.group(1)).is_file())

    def test_apple_web_app_title_is_set(self) -> None:
        """iOS ホーム画面のラベル名が設定されていること"""
        self.assertIn('name="apple-mobile-web-app-title"', self.html)


class TestServiceWorkerIconCache(unittest.TestCase):
    """Service Worker のオフラインキャッシュ整合の契約"""

    def setUp(self) -> None:
        self.sw_source = SW_PATH.read_text(encoding="utf-8")

    def test_all_manifest_icons_are_precached(self) -> None:
        """manifest の全アイコンがキャッシュ対象に含まれること"""
        for icon in _load_manifest()["icons"]:
            with self.subTest(src=icon["src"]):
                needle = "./" + icon["src"].lstrip("./")
                self.assertIn(needle, self.sw_source)

    def test_apple_touch_icon_is_precached(self) -> None:
        """apple-touch-icon もキャッシュ対象に含まれること"""
        self.assertIn("./assets/pwa/apple_touch_icon_180.png", self.sw_source)

    def test_cache_name_is_version_driven(self) -> None:
        """キャッシュ名がバージョン由来 (キャッシュバスター) であること"""
        self.assertIn("WEB_PET_CACHE_NAME", self.sw_source)


class TestIconGenerator(unittest.TestCase):
    """アイコン生成スクリプトの契約 (再現性)"""

    def test_generator_script_exists(self) -> None:
        """ドット絵からアイコンを再生成するスクリプトが存在すること"""
        self.assertTrue(GENERATOR_PATH.is_file(), f"見つかりません: {GENERATOR_PATH}")

    def test_generator_specs_cover_manifest_icons(self) -> None:
        """生成スクリプトの出力定義が manifest の全アイコンを網羅すること"""
        source = GENERATOR_PATH.read_text(encoding="utf-8")
        for icon in _load_manifest()["icons"]:
            with self.subTest(src=icon["src"]):
                self.assertIn(Path(icon["src"]).name, source)

    def test_committed_icons_match_generator_spec(self) -> None:
        """コミット済みアイコンが生成仕様と一致すること（ドリフト検出・P3 2026-09-16）

        手作業での画像差し替えや、spec 変更後の再生成忘れを検出する。
        """
        import importlib.util

        spec = importlib.util.spec_from_file_location("build_pwa_icons", GENERATOR_PATH)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        with module.Image.open(module.SOURCE_ART) as opened:
            source = opened.copy()

        drifted = module.check_icons(source)

        self.assertEqual(drifted, 0, "アイコンが生成仕様と乖離しています（再生成が必要）")


if __name__ == "__main__":
    unittest.main(verbosity=2)

