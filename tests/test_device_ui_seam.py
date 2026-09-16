#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - 設定画面 接続端末管理UI の Seam 単体テスト (tests/test_device_ui_seam.py)

タスク4 (Sprint C 先取り, 2026-09-16 Cline): ゼロトラスト端末台帳
(storage/device_repo.py + api_devices.py) を PC 設定画面から視覚確認・Revoke できる
「📱 接続端末管理」セクションを追加する。

Codebase Design 規約:
- GUI を表示せずに検証できるよう、台帳→表示DTOの変換と Revoke 実行を
  純粋関数 / Seam 関数 (ui/device_manager_panel.py) へ分離する。
- 神ファイル (settings_window.py) へは「セクションを1つ差し込む」だけに留める。

TDD: ui/device_manager_panel.py が無い状態では Red で落ちる。
"""

import sys
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import ui.device_manager_panel as panel  # noqa: E402


ANDROID_UA = "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36"
IPHONE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari"
WINDOWS_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"


def _device(
    device_id: int = 1,
    name: str = "Pixel Desk Pet",
    ip: str = "192.168.1.9",
    ua: str = ANDROID_UA,
    created_at: int = 1758000000000,
    last_seen: int = 1758000600000,
    is_revoked: int = 0,
):
    """Device モデル相当のスタブ。"""
    return mock.Mock(
        id=device_id,
        device_name=name,
        ip_address=ip,
        user_agent=ua,
        created_at=created_at,
        last_seen=last_seen,
        is_revoked=is_revoked,
    )


class TestUserAgentSummary(unittest.TestCase):
    """User-Agent → 端末表示名の要約契約"""

    def test_detects_major_platforms(self) -> None:
        """主要プラットフォームを判別して表示名を返すこと"""
        self.assertEqual(panel.summarize_user_agent(IPHONE_UA), "📱 iPhone")
        self.assertEqual(panel.summarize_user_agent(ANDROID_UA), "📱 Android")
        self.assertEqual(panel.summarize_user_agent(WINDOWS_UA), "💻 Windows PC")
        self.assertEqual(
            panel.summarize_user_agent("Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X)"),
            "📱 iPad",
        )
        self.assertEqual(
            panel.summarize_user_agent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15)"),
            "💻 Mac",
        )

    def test_android_is_not_misdetected_as_linux(self) -> None:
        """Android の UA に含まれる Linux 文字列を誤検出しないこと"""
        self.assertEqual(panel.summarize_user_agent(ANDROID_UA), "📱 Android")

    def test_unknown_or_missing_user_agent(self) -> None:
        """未知/未記録の UA でも例外を漏らさず不明表示にすること"""
        self.assertEqual(panel.summarize_user_agent("curl/8.0"), "❓ 不明な端末")
        self.assertEqual(panel.summarize_user_agent(None), "❓ 不明な端末")
        self.assertEqual(panel.summarize_user_agent(""), "❓ 不明な端末")


class TestDeviceTimestampFormat(unittest.TestCase):
    """ミリ秒タイムスタンプの表示整形契約"""

    def test_formats_epoch_millis(self) -> None:
        """ミリ秒を 'YYYY-MM-DD HH:MM' へ整形すること"""
        formatted = panel.format_device_timestamp(1758000000000)
        self.assertRegex(formatted, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")

    def test_missing_or_invalid_values_show_placeholder(self) -> None:
        """未記録/不正値はプレースホルダを返し例外を漏らさないこと"""
        for value in (None, 0, "", "not-a-number"):
            with self.subTest(value=value):
                self.assertEqual(panel.format_device_timestamp(value), "—")


class TestBuildDeviceRows(unittest.TestCase):
    """台帳 (Device モデル) → 表示DTO変換の契約"""

    def test_maps_active_device_to_row(self) -> None:
        """有効端末が表示用DTOへ正しく変換されること"""
        rows = panel.build_device_rows([_device()])

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.device_id, 1)
        self.assertEqual(row.title, "Pixel Desk Pet")
        self.assertEqual(row.subtitle, "📱 Android · 192.168.1.9")
        self.assertEqual(row.status_label, panel.DEVICE_STATUS_ACTIVE_LABEL)
        self.assertEqual(row.status_color, panel.STATUS_COLOR_ACTIVE)
        self.assertFalse(row.is_revoked)
        self.assertEqual(row.last_seen_label, panel.format_device_timestamp(1758000600000))

    def test_maps_revoked_device_to_row(self) -> None:
        """失効済み端末が「拒否済み」表示になること (ゼロトラストの可視化)"""
        rows = panel.build_device_rows([_device(is_revoked=1)])

        self.assertTrue(rows[0].is_revoked)
        self.assertEqual(rows[0].status_label, panel.DEVICE_STATUS_REVOKED_LABEL)
        self.assertEqual(rows[0].status_color, panel.STATUS_COLOR_REVOKED)

    def test_missing_device_name_falls_back_to_user_agent_label(self) -> None:
        """端末名未登録時は UA 由来の表示名で補うこと"""
        rows = panel.build_device_rows([_device(name="", ua=IPHONE_UA)])
        self.assertEqual(rows[0].title, "📱 iPhone")

    def test_missing_ip_shows_placeholder(self) -> None:
        """IP 未記録でも例外を漏らさず表示を継続すること"""
        rows = panel.build_device_rows([_device(ip=None)])
        self.assertIn("IP不明", rows[0].subtitle)

    def test_empty_registry_returns_empty_list(self) -> None:
        """登録ゼロで空リストを返すこと (Fail-Safe)"""
        self.assertEqual(panel.build_device_rows([]), [])


class TestDeviceSeams(unittest.TestCase):
    """GUI 非依存の Seam 関数 (一覧取得 / Revoke) の契約"""

    def test_list_device_rows_reads_registry(self) -> None:
        """一覧 Seam が database.get_all_devices を参照すること"""
        with mock.patch.object(
            panel.database, "get_all_devices", return_value=[_device()]
        ) as mocked:
            rows = panel.list_device_rows()

        self.assertTrue(mocked.called)
        self.assertEqual(len(rows), 1)

    def test_revoke_device_entry_delegates_to_repository(self) -> None:
        """Revoke Seam が device_repo へ委譲し、成功可否を bool で返すこと"""
        with mock.patch.object(
            panel.database, "revoke_device", return_value=True
        ) as mocked:
            self.assertTrue(panel.revoke_device_entry(3))

        mocked.assert_called_once_with(3)

    def test_revoke_device_entry_accepts_string_id(self) -> None:
        """GUI/JSON 由来の文字列IDでも int へ正規化して委譲すること"""
        with mock.patch.object(
            panel.database, "revoke_device", return_value=True
        ) as mocked:
            self.assertTrue(panel.revoke_device_entry("3"))

        mocked.assert_called_once_with(3)

    def test_revoke_device_entry_returns_false_on_failure(self) -> None:
        """対象が存在しない場合は False を返すこと (API 契約の踏襲)"""
        with mock.patch.object(panel.database, "revoke_device", return_value=False):
            self.assertFalse(panel.revoke_device_entry(999))

    def test_revoke_device_entry_is_exception_safe(self) -> None:
        """DB 異常時も例外を漏らさず False を返すこと"""
        with mock.patch.object(
            panel.database, "revoke_device", side_effect=RuntimeError("database is locked")
        ):
            self.assertFalse(panel.revoke_device_entry(1))



class TestDeviceManagerSectionGui(unittest.TestCase):
    """実 Tk 上での端末カード描画 ＆ Revoke 操作の統合検証 (スモーク)"""

    @classmethod
    def setUpClass(cls) -> None:
        # テスト毎の Tk 生成/破棄は Tcl の後始末レースを招くためクラスで1回だけ作る。
        try:
            cls.root = tk.Tk()
        except tk.TclError:
            cls.root = None
        else:
            cls.root.withdraw()

    @classmethod
    def tearDownClass(cls) -> None:
        if getattr(cls, "root", None) is not None:
            try:
                cls.root.destroy()
            except tk.TclError:
                pass
            cls.root = None

    def setUp(self) -> None:
        if self.__class__.root is None:
            self.skipTest("Tk を初期化できない環境のためスキップします")

    def _make_section(self, devices, confirm=True):
        """台帳を差し替えたセクションを生成する。"""
        with mock.patch.object(panel.database, "get_all_devices", return_value=devices):
            section = panel.DeviceManagerSection(
                self.root, confirm_callback=lambda _row: confirm
            )
        section.pack()
        section.update()
        return section

    def test_renders_one_card_per_device(self) -> None:
        """登録端末1件につきカード1枚が描画されること"""
        section = self._make_section([_device(1), _device(2, name="Boss iPhone", ua=IPHONE_UA)])

        self.assertEqual(len(section.rows), 2)
        self.assertEqual(len(section.rows_container.winfo_children()), 2)

    def test_empty_registry_shows_placeholder(self) -> None:
        """登録ゼロ時は案内メッセージを表示すること"""
        section = self._make_section([])

        self.assertEqual(len(section.rows), 0)
        self.assertGreaterEqual(len(section.rows_container.winfo_children()), 1)

    def test_confirmed_revoke_calls_seam_and_refreshes_rows(self) -> None:
        """確認OKで Revoke が実行され、一覧が再描画されること"""
        section = self._make_section([_device(1), _device(2, name="Boss iPhone")])
        revoked_device = _device(1, is_revoked=1)

        with mock.patch.object(
            panel.database, "revoke_device", return_value=True
        ) as revoke_mock, mock.patch.object(
            panel.database, "get_all_devices", return_value=[revoked_device, _device(2)]
        ):
            result = section.revoke(section.rows[0])

        self.assertTrue(result)
        revoke_mock.assert_called_once_with(1)
        self.assertTrue(section.rows[0].is_revoked)
        self.assertEqual(
            section.rows[0].status_label, panel.DEVICE_STATUS_REVOKED_LABEL
        )

    def test_cancelled_revoke_does_not_touch_registry(self) -> None:
        """確認キャンセル時は台帳を書き換えないこと (誤操作防止)"""
        section = self._make_section([_device(1)], confirm=False)

        with mock.patch.object(panel.database, "revoke_device") as revoke_mock:
            result = section.revoke(section.rows[0])

        self.assertFalse(result)
        self.assertFalse(revoke_mock.called)


class TestSettingsWindowIntegration(unittest.TestCase):
    """設定画面へのセクション組み込み契約 (神ファイル肥大化の抑止)"""

    def test_settings_window_mounts_device_section(self) -> None:
        """設定画面がセクションを読み込み・配置していること"""
        source = (PROJECT_ROOT / "ui" / "settings_window.py").read_text(encoding="utf-8")
        self.assertIn("DeviceManagerSection", source)
        self.assertIn("接続端末管理", source)

    def test_panel_module_stays_gui_thin(self) -> None:
        """GUI 非依存ロジックが Seam 関数として公開されていること"""
        for func_name in ("list_device_rows", "revoke_device_entry", "build_device_rows"):
            with self.subTest(func=func_name):
                self.assertTrue(callable(getattr(panel, func_name)))


if __name__ == "__main__":
    unittest.main(verbosity=2)

