#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - タスクトレイ キャラ着せ替え連動アイコンの単体テスト
(tests/test_tray_character_icon.py)

タスク0 (2026-09-16 Cline): 既定の青い羽ペン/汎用アイコンを廃止し、
初代秘書くんドット絵 (assets/dot/<char>/idle_1.png) をトレイアイコンへ適用する。
キャラクター変更時は update_character_icon() で動的に差し替える契約を凍結する。

TDD: resolve_character_icon_path / load_character_tray_image /
     SystemTrayManager.update_character_icon が未実装の状態では Red で落ちる。
"""

import sys
import unittest
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui import system_tray  # noqa: E402
from ui.system_tray import (  # noqa: E402
    SystemTrayManager,
    load_character_tray_image,
    resolve_character_icon_path,
)


class _FakeGui:
    """post_action のみを模倣する GUI スタブ (トレイ初期化には十分)。"""

    def post_action(self, callback, *args, **kwargs) -> None:
        pass


class _FakeTrayIcon:
    """pystray.Icon の最小スタブ (icon 属性のみ模倣)。"""

    def __init__(self, fail_on_set: bool = False) -> None:
        self.icon = None
        self._fail_on_set = fail_on_set

    def __setattr__(self, name, value):
        if name == "icon" and getattr(self, "_fail_on_set", False):
            raise RuntimeError("トレイアイコン更新失敗 (模擬)")
        object.__setattr__(self, name, value)


class TestCharacterIconPathResolution(unittest.TestCase):
    """キャラクターID → ドット絵アセットパス解決の契約"""

    def test_default_candidate_is_hisho_idle1(self) -> None:
        """_ASSET_CANDIDATES の最優先候補が秘書くん idle_1.png であること"""
        self.assertEqual(
            system_tray._ASSET_CANDIDATES[0],
            PROJECT_ROOT / "assets" / "dot" / "hisho" / "idle_1.png",
        )
        self.assertTrue(system_tray._ASSET_CANDIDATES[0].is_file())

    def test_resolves_each_registered_character_asset(self) -> None:
        """hisho / kyle それぞれの idle_1.png を解決できること"""
        for char_id in ("hisho", "kyle"):
            resolved = resolve_character_icon_path(char_id)
            self.assertEqual(
                resolved, PROJECT_ROOT / "assets" / "dot" / char_id / "idle_1.png"
            )

    def test_unknown_character_falls_back_to_hisho(self) -> None:
        """未登録キャラクターIDでも既定キャラ (hisho) へフォールバックすること"""
        self.assertEqual(
            resolve_character_icon_path("no_such_character"),
            PROJECT_ROOT / "assets" / "dot" / "hisho" / "idle_1.png",
        )

    def test_empty_character_id_falls_back_to_hisho(self) -> None:
        """空/None のIDでも例外を漏らさず既定キャラを返すこと (Fail-Safe)"""
        self.assertEqual(
            resolve_character_icon_path(None),
            PROJECT_ROOT / "assets" / "dot" / "hisho" / "idle_1.png",
        )
        self.assertEqual(
            resolve_character_icon_path(""),
            PROJECT_ROOT / "assets" / "dot" / "hisho" / "idle_1.png",
        )

    def test_character_id_cannot_escape_assets_directory(self) -> None:
        """パストラバーサル文字列は無害化され assets 外へ出られないこと (ゼロトラスト)"""
        resolved = resolve_character_icon_path("../../../../etc/passwd")
        self.assertIsNotNone(resolved)
        self.assertTrue(
            str(resolved).startswith(str(PROJECT_ROOT / "assets")),
            f"assets ディレクトリ外を指しています: {resolved}",
        )


class TestCharacterTrayImageLoading(unittest.TestCase):
    """ドット絵のトレイ用画像変換 (64x64 / NEAREST) の契約"""

    def test_loaded_image_is_nearest_scaled_64px(self) -> None:
        """元ドット絵を 64x64 へ NEAREST 拡大した画像を返すこと (ドット感維持)"""
        expected = (
            Image.open(PROJECT_ROOT / "assets" / "dot" / "hisho" / "idle_1.png")
            .convert("RGBA")
            .resize(system_tray.TRAY_ICON_SIZE, Image.Resampling.NEAREST)
        )
        actual = load_character_tray_image("hisho")

        self.assertEqual(actual.size, system_tray.TRAY_ICON_SIZE)
        self.assertEqual(actual.tobytes(), expected.tobytes())

    def test_character_specific_artwork_differs(self) -> None:
        """キャラクターが違えば画像内容も変わること (着せ替え連動の根拠)"""
        hisho = load_character_tray_image("hisho")
        kyle = load_character_tray_image("kyle")
        self.assertNotEqual(hisho.tobytes(), kyle.tobytes())

    def test_unknown_character_returns_generic_fallback_image(self) -> None:
        """アセット消失時はフォールバック画像を返し、例外を漏らさないこと"""
        fallback = system_tray.build_fallback_tray_image()
        self.assertEqual(fallback.size, system_tray.TRAY_ICON_SIZE)


class TestUpdateCharacterIcon(unittest.TestCase):
    """SystemTrayManager.update_character_icon の契約"""

    def test_returns_false_when_tray_not_started(self) -> None:
        """トレイ未起動 (pystray 未導入等) では False を返し例外を漏らさないこと"""
        manager = SystemTrayManager(_FakeGui())
        self.assertIsNone(manager._icon)
        self.assertFalse(manager.update_character_icon("hisho"))

    def test_replaces_tray_icon_with_character_artwork(self) -> None:
        """キャラ変更時にトレイアイコン画像が該当キャラのドット絵へ差し替わること"""
        manager = SystemTrayManager(_FakeGui())
        fake_icon = _FakeTrayIcon()
        manager._icon = fake_icon

        self.assertTrue(manager.update_character_icon("kyle"))

        expected = load_character_tray_image("kyle")
        self.assertIsNotNone(fake_icon.icon)
        self.assertEqual(fake_icon.icon.tobytes(), expected.tobytes())

    def test_is_exception_safe_when_platform_rejects_update(self) -> None:
        """OS/ライブラリ側が更新を拒否しても False を返し、アプリを落とさないこと"""
        manager = SystemTrayManager(_FakeGui())
        manager._icon = _FakeTrayIcon(fail_on_set=True)

        self.assertFalse(manager.update_character_icon("hisho"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
