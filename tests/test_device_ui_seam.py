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
import threading
import time
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

    def test_restore_device_entry_delegates_to_repository(self) -> None:
        """Restore Seam が device_repo へ委譲し、成功可否を bool で返すこと"""
        with mock.patch.object(
            panel.database, "restore_device", return_value=True
        ) as mocked:
            self.assertTrue(panel.restore_device_entry(3))

        mocked.assert_called_once_with(3)

    def test_restore_device_entry_accepts_string_id(self) -> None:
        """GUI/JSON 由来の文字列IDでも int へ正規化して委譲すること"""
        with mock.patch.object(
            panel.database, "restore_device", return_value=True
        ) as mocked:
            self.assertTrue(panel.restore_device_entry("3"))

        mocked.assert_called_once_with(3)

    def test_restore_device_entry_returns_false_on_failure(self) -> None:
        """対象が存在しない場合は False を返すこと"""
        with mock.patch.object(panel.database, "restore_device", return_value=False):
            self.assertFalse(panel.restore_device_entry(999))

    def test_restore_device_entry_is_exception_safe(self) -> None:
        """DB 異常時も例外を漏らさず False を返すこと"""
        with mock.patch.object(
            panel.database, "restore_device", side_effect=RuntimeError("database is locked")
        ):
            self.assertFalse(panel.restore_device_entry(1))

    def test_mark_row_restored(self) -> None:
        """mark_row_restored が有効ステータスへ差し替えること"""
        row = panel.DeviceRow(
            device_id=1,
            title="Device",
            subtitle="UA",
            status_label="🚫 拒否済み",
            status_color="#C62828",
            created_label="now",
            last_seen_label="now",
            is_revoked=True,
        )
        restored = panel.mark_row_restored(row)
        self.assertFalse(restored.is_revoked)
        self.assertEqual(restored.status_label, panel.DEVICE_STATUS_ACTIVE_LABEL)
        self.assertEqual(restored.status_color, panel.STATUS_COLOR_ACTIVE)



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
        ), mock.patch.object(panel, "record_device_revoke"):
            result = section.revoke(section.rows[0])

        self.assertTrue(result)
        revoke_mock.assert_called_once_with(1)
        self.assertTrue(section.rows[0].is_revoked)
        self.assertEqual(
            section.rows[0].status_label, panel.DEVICE_STATUS_REVOKED_LABEL
        )

    def test_restore_calls_seam_and_refreshes_rows(self) -> None:
        """失効済み端末に対して restore が実行され、一覧が再描画されること"""
        revoked_device = _device(1, is_revoked=1)
        active_device = _device(1, is_revoked=0)
        section = self._make_section([revoked_device])

        with mock.patch.object(
            panel.database, "restore_device", return_value=True
        ) as restore_mock, mock.patch.object(
            panel.database, "get_all_devices", return_value=[active_device]
        ), mock.patch.object(panel, "record_device_restore") as audit_mock:
            result = section.restore(section.rows[0])

        self.assertTrue(result)
        restore_mock.assert_called_once_with(1)
        self.assertFalse(section.rows[0].is_revoked)
        self.assertEqual(
            section.rows[0].status_label, panel.DEVICE_STATUS_ACTIVE_LABEL
        )
        audit_mock.assert_called_once_with(
            1, actor="pc_settings_ui", source="ui", device_name=section.rows[0].title
        )

    def test_cancelled_revoke_does_not_touch_registry(self) -> None:
        """確認キャンセル時は台帳を書き換えないこと (誤操作防止)"""
        section = self._make_section([_device(1)], confirm=False)

        with mock.patch.object(panel.database, "revoke_device") as revoke_mock:
            result = section.revoke(section.rows[0])

        self.assertFalse(result)
        self.assertFalse(revoke_mock.called)

    def test_revoke_records_audit_log_with_source(self) -> None:
        """接続解除が監査ログ（source=ui, actor=pc_settings_ui）へ記録されること (P1-4)"""
        section = self._make_section([_device(1, name="Pixel Desk Pet")])

        with mock.patch.object(panel.database, "revoke_device", return_value=True), \
                mock.patch.object(
                    panel.database, "get_all_devices", return_value=[_device(1, is_revoked=1)]
                ), \
                mock.patch.object(panel, "record_device_revoke") as audit_mock:
            section.revoke(section.rows[0])

        audit_mock.assert_called_once()
        args, kwargs = audit_mock.call_args
        self.assertEqual(args[0], 1)
        self.assertEqual(kwargs.get("source"), "ui")
        self.assertEqual(kwargs.get("actor"), "pc_settings_ui")
        self.assertEqual(kwargs.get("device_name"), "Pixel Desk Pet")

    def test_failed_revoke_is_not_audited(self) -> None:
        """失効に失敗した場合は監査ログへ記録しないこと（記録は成功時のみ）"""
        section = self._make_section([_device(1)])

        with mock.patch.object(panel.database, "revoke_device", return_value=False), \
                mock.patch.object(panel.database, "get_all_devices", return_value=[_device(1)]), \
                mock.patch.object(panel, "record_device_revoke") as audit_mock:
            result = section.revoke(section.rows[0])

        self.assertFalse(result)
        self.assertFalse(audit_mock.called)


class TestDevicePanelAsyncRefresh(unittest.TestCase):
    """P1-3: 台帳読み出しの非同期化 ＆ 失敗の可視化の契約

    DBがロックされていると `busy_timeout` (30秒) まで待つため、Tkメインスレッドで
    読み出すと設定画面が固まる。読み出しはワーカースレッド、画面反映は
    `dispatch`（本番: `parent_gui.post_action`）経由でメインスレッドに限定する。
    """

    @classmethod
    def setUpClass(cls) -> None:
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

    def test_fetch_result_reports_error_instead_of_empty(self) -> None:
        """取得失敗がエラーメッセージとして返ること（端末ゼロと区別できる）"""
        with mock.patch.object(
            panel.database, "get_all_devices", side_effect=RuntimeError("database is locked")
        ):
            result = panel.fetch_device_rows()

        self.assertEqual(result.rows, [])
        self.assertIsNotNone(result.error)
        self.assertIn("database is locked", result.error or "")

    def test_constructor_does_not_block_on_slow_registry(self) -> None:
        """読み出しが遅くてもコンストラクタ（＝設定画面表示）がブロックしないこと。

        Notes:
            2026-09-23: 旧実装は「コンストラクタの所要時間 < 0.3秒」で判定していたが、
            Tk/CustomTkinter のウィジェット生成自体が高負荷環境で 1〜2秒かかるため
            偽陽性（環境依存の失敗）になった。本質（台帳読み出しがメインスレッドを
            塞がない）を**実行スレッド名**で決定論的に検証する。
        """
        captured: list = []
        caller_threads: list = []

        def slow_registry():
            caller_threads.append(threading.current_thread().name)
            time.sleep(0.4)
            return [_device(1)]

        with mock.patch.object(panel.database, "get_all_devices", side_effect=slow_registry):
            section = panel.DeviceManagerSection(
                self.root,
                confirm_callback=lambda _row: True,
                dispatch=lambda callback: captured.append(callback),
            )

            self.assertEqual(section.rows, [], "ワーカー完了前にメインスレッドで反映されています")

            # 読み出しがワーカースレッド（メインスレッド以外）で実行されること
            for _ in range(40):
                if caller_threads:
                    break
                time.sleep(0.05)
            self.assertTrue(caller_threads, "台帳読み出しが実行されていません")
            self.assertNotEqual(
                caller_threads[0],
                threading.main_thread().name,
                "台帳読み出しがメインスレッドを塞いでいます",
            )

            for _ in range(60):
                if captured:
                    break
                time.sleep(0.05)

        self.assertEqual(len(captured), 1, "反映依頼が1回だけ発行されること")
        captured[0]()
        self.assertEqual(len(section.rows), 1, "dispatch 経由の反映が行われていません")

    def test_in_flight_requests_are_deduplicated(self) -> None:
        """読み出し実行中の連打（再読込）は1本に統合されること"""
        captured: list = []
        gate = threading.Event()

        def blocking_registry():
            gate.wait(timeout=3.0)
            return [_device(1)]

        with mock.patch.object(panel.database, "get_all_devices", side_effect=blocking_registry):
            section = panel.DeviceManagerSection(
                self.root,
                confirm_callback=lambda _row: True,
                dispatch=lambda callback: captured.append(callback),
            )
            section.refresh_async()
            section.refresh_async()
            gate.set()
            for _ in range(60):
                if captured:
                    break
                time.sleep(0.05)

        self.assertEqual(len(captured), 1, "多重発行が抑止されていません")

    def test_db_error_is_shown_not_silently_empty(self) -> None:
        """DB障害時は「端末ゼロ」ではなく読み出し失敗として表示されること"""
        with mock.patch.object(
            panel.database, "get_all_devices", side_effect=RuntimeError("database is locked")
        ):
            section = panel.DeviceManagerSection(self.root, confirm_callback=lambda _row: True)

        texts = [
            child.cget("text")
            for child in section.rows_container.winfo_children()
            if hasattr(child, "cget")
        ]
        self.assertTrue(any("失敗" in text for text in texts), f"失敗表示がありません: {texts}")
        self.assertNotIn(panel.EMPTY_PLACEHOLDER, texts)
        self.assertIn("失敗", section.status_label.cget("text"))
        self.assertIsNotNone(section.fetch_error)

    def test_fetch_runs_off_main_thread(self) -> None:
        """台帳読み出しがメインスレッド以外で実行されること（UIブロック根絶の根拠）"""
        observed: list = []
        captured: list = []

        def recording_registry():
            observed.append(threading.current_thread() is threading.main_thread())
            return [_device(1)]

        with mock.patch.object(panel.database, "get_all_devices", side_effect=recording_registry):
            section = panel.DeviceManagerSection(
                self.root,
                confirm_callback=lambda _row: True,
                dispatch=lambda callback: captured.append(callback),
            )
            for _ in range(60):
                if captured:
                    break
                time.sleep(0.05)

        self.assertEqual(observed, [False], "台帳読み出しがメインスレッドで実行されています")
        self.assertEqual(len(captured), 1)

    def test_ui_thread_stays_responsive_while_fetch_blocked(self) -> None:
        """読み出しが返らない間もメインスレッドが操作可能であること（デッドロック検出）"""
        gate = threading.Event()
        captured: list = []

        def blocking_registry():
            gate.wait(timeout=3.0)
            return [_device(1)]

        try:
            with mock.patch.object(panel.database, "get_all_devices", side_effect=blocking_registry):
                section = panel.DeviceManagerSection(
                    self.root,
                    confirm_callback=lambda _row: True,
                    dispatch=lambda callback: captured.append(callback),
                )
                self.assertEqual(section.rows, [])

                # 読み出し中にメインスレッドで Tk 操作（描画・ウィジェット生成）を行う
                marker = tk.Label(self.root, text="responsive")
                marker.pack()
                self.root.update()
                self.assertTrue(marker.winfo_exists())
                marker.destroy()

                gate.set()
                for _ in range(60):
                    if captured:
                        break
                    time.sleep(0.05)
        finally:
            gate.set()

        self.assertEqual(len(captured), 1)
        captured[0]()
        self.assertEqual(len(section.rows), 1)

    def test_refresh_flag_is_reset_and_next_refresh_runs(self) -> None:
        """読み出し完了後にフラグが戻り、次の再読込が実行されること（恒久True化の回帰防止）"""
        calls: list = []
        captured: list = []

        def counting_registry():
            calls.append(1)
            return [_device(1)]

        with mock.patch.object(panel.database, "get_all_devices", side_effect=counting_registry):
            section = panel.DeviceManagerSection(
                self.root,
                confirm_callback=lambda _row: True,
                dispatch=lambda callback: captured.append(callback),
            )
            for _ in range(60):
                if captured:
                    break
                time.sleep(0.05)
            captured.pop(0)()
            self.assertFalse(section._refresh_in_flight, "フラグがリセットされていません")

            section.refresh_async()
            for _ in range(60):
                if captured:
                    break
                time.sleep(0.05)

        self.assertEqual(len(calls), 2, "2回目の再読込が実行されていません（フラグ恒久True疑い）")
        self.assertEqual(len(captured), 1)

    def test_error_after_successful_render_keeps_previous_rows(self) -> None:
        """更新失敗時は前回の一覧を消さずに失敗を明示すること（stale-but-visible）"""
        with mock.patch.object(panel.database, "get_all_devices", return_value=[_device(1)]):
            section = panel.DeviceManagerSection(self.root, confirm_callback=lambda _row: True)
        children_before = list(section.rows_container.winfo_children())

        with mock.patch.object(
            panel.database, "get_all_devices", side_effect=RuntimeError("database is locked")
        ):
            section.refresh()

        self.assertEqual(
            section.rows_container.winfo_children(),
            children_before,
            "更新失敗で表示中の一覧が消えています",
        )
        self.assertEqual(len(section.rows), 1)
        self.assertIn("更新失敗", section.status_label.cget("text"))

    def test_failed_revoke_is_reported_in_status(self) -> None:
        """接続解除に失敗した場合は状態行で明示すること（無言の失敗を防ぐ）"""
        with mock.patch.object(panel.database, "get_all_devices", return_value=[_device(1)]):
            section = panel.DeviceManagerSection(self.root, confirm_callback=lambda _row: True)

        with mock.patch.object(panel.database, "revoke_device", return_value=False), \
                mock.patch.object(panel, "record_device_revoke") as audit_mock:
            result = section.revoke(section.rows[0])

        self.assertFalse(result)
        self.assertFalse(audit_mock.called)
        self.assertIn("失敗", section.status_label.cget("text"))

    def test_revoke_during_inflight_fetch_converges_to_truth(self) -> None:
        """読み出し実行中に解除しても、最終表示が「拒否済み」へ収束すること (P1-1 回帰防止)

        旧実装は in-flight 中の再読込要求を捨てていたため、失効前スナップショットが
        表示されたまま「DBは失効済み・UIは有効」という嘘が固定された（独立査読で実測）。
        """
        state = {"rows": [_device(1)], "block": False}
        gate = threading.Event()
        captured: list = []

        def controlled_registry():
            snapshot = list(state["rows"])
            if state["block"]:
                gate.wait(timeout=3.0)
            return snapshot

        with mock.patch.object(panel.database, "get_all_devices", side_effect=controlled_registry):
            section = panel.DeviceManagerSection(
                self.root,
                confirm_callback=lambda _row: True,
                dispatch=lambda callback: captured.append(callback),
            )
            for _ in range(60):
                if captured:
                    break
                time.sleep(0.05)
            captured.pop(0)()
            self.assertEqual(len(section.rows), 1)

            # 読み出しをブロックし、その最中に revoke を実行する
            state["block"] = True
            section.refresh_async()
            self.assertTrue(section._refresh_in_flight)

            state["rows"] = [_device(1, is_revoked=1)]
            with mock.patch.object(panel.database, "revoke_device", return_value=True), \
                    mock.patch.object(panel, "record_device_revoke"):
                self.assertTrue(section.revoke(section.rows[0]))

            # 古いスナップショットを配送 → 延期された再読込が走り最新状態へ収束する
            state["block"] = False
            gate.set()
            # 楽観更新で先に is_revoked が立つため、フラグ解放（＝再読込完了）まで待つ
            for _ in range(80):
                while captured:
                    captured.pop(0)()
                if not section._refresh_in_flight and section.rows and section.rows[0].is_revoked:
                    break
                time.sleep(0.05)

        self.assertTrue(section.rows[0].is_revoked, "UIが失効前状態のまま収束していません")
        self.assertEqual(
            section.rows[0].status_label, panel.DEVICE_STATUS_REVOKED_LABEL
        )
        self.assertFalse(section._refresh_in_flight)

    def test_identical_rows_do_not_rebuild_widgets(self) -> None:
        """同一内容の再読込ではウィジェットを再生成しないこと（連打での肥大化防止）"""
        with mock.patch.object(panel.database, "get_all_devices", return_value=[_device(1)]):
            section = panel.DeviceManagerSection(self.root, confirm_callback=lambda _row: True)
            before = list(section.rows_container.winfo_children())
            section.refresh()
            after = list(section.rows_container.winfo_children())

        self.assertEqual(len(before), len(after))
        self.assertTrue(
            all(b is a for b, a in zip(before, after)),
            "同一内容にもかかわらずウィジェットが再生成されています",
        )

    def test_changed_rows_rebuild_widgets(self) -> None:
        """内容が変化した場合は再描画されること"""
        with mock.patch.object(panel.database, "get_all_devices", return_value=[_device(1)]):
            section = panel.DeviceManagerSection(self.root, confirm_callback=lambda _row: True)
        before = {id(child) for child in section.rows_container.winfo_children()}

        with mock.patch.object(
            panel.database, "get_all_devices", return_value=[_device(1), _device(2)]
        ):
            section.refresh()

        after = list(section.rows_container.winfo_children())
        self.assertEqual(len(after), 2)
        self.assertNotEqual(before, {id(child) for child in after})


class TestSettingsWindowIntegration(unittest.TestCase):
    """設定画面へのセクション組み込み契約 (神ファイル肥大化の抑止)"""

    def test_settings_window_mounts_device_section(self) -> None:
        """設定画面がセクションを読み込み・配置していること"""
        source = (PROJECT_ROOT / "ui" / "settings_window.py").read_text(encoding="utf-8")
        self.assertIn("DeviceManagerSection", source)
        self.assertIn("接続端末管理", source)

    def test_panel_module_stays_gui_thin(self) -> None:
        """GUI 非依存ロジックが Seam 関数として公開されていること"""
        for func_name in ("list_device_rows", "revoke_device_entry", "restore_device_entry", "delete_device_entry", "build_device_rows"):
            with self.subTest(func=func_name):
                self.assertTrue(callable(getattr(panel, func_name)))

    def test_delete_device_entry_success(self) -> None:
        """delete_device_entry が database.delete_device を呼んで結果を返すこと"""
        with mock.patch.object(panel.database, "delete_device", return_value=True) as mock_del:
            self.assertTrue(panel.delete_device_entry(42))
            mock_del.assert_called_once_with(42)

    def test_delete_device_entry_exception_returns_false(self) -> None:
        """delete_device_entry で例外発生時に安全に False を返すこと"""
        with mock.patch.object(panel.database, "delete_device", side_effect=RuntimeError("DB locked")):
            self.assertFalse(panel.delete_device_entry(42))


if __name__ == "__main__":
    unittest.main(verbosity=2)

