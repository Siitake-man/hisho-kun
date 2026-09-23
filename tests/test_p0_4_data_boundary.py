#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0-4: 暗号鍵・DB の OneDrive 退避（データ境界の非同期領域化 / ADR-2）を検証する。

検証対象:
  1. ``app_paths``: ``get_data_root`` / ``get_db_path`` / ``get_sync_token_path`` /
     ``get_backups_dir`` / ``is_cloud_synced_path`` / ``migrate_legacy_data``
  2. ``storage.connection.resolve_db_path``: 既定相対名のみデータルートへ解決し、
     明示パス（テストの一時DB等）は一切書き換えないこと。
  3. 安全移行: VAPID 秘密鍵の**非再生成**（全購読の維持）・旧ファイルの**退避（削除しない）**・
     冪等性・WAL 残留データの取り込み・破損 DB に対する Fail-Safe。
  4. 起動配線のソース不変条件（旧リテラルの再流入禁止）。

設計不変条件の正本: ``DESIGN_SPEC`` §10・§10.2 ／ ADR-2（codebase-memory DECISIONS / 2026-09-22）。

テスト隔離: ``tests/conftest.py`` が ``NEO_HISHO_DATA_DIR`` を一時領域へ固定するため、
本テストは**実データ（本番 DB / .sync_token）に一切触れない**。
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app_paths
import storage.connection as storage_connection
from storage.vapid_key_repo import get_or_create_vapid_keys


class _DataRootIsolatedTest(unittest.TestCase):
    """データルートのプロセス内キャッシュを各テストで初期化する基底クラス。

    ``get_data_root`` / ``get_app_root`` はプロセス内キャッシュを持つため、
    環境変数を差し替えるテストは必ず setUp / tearDown でキャッシュを破棄する。
    """

    def setUp(self) -> None:
        """各テスト開始前にパス解決キャッシュを初期化する。"""
        app_paths.reset_path_caches()

    def tearDown(self) -> None:
        """各テスト終了後にパス解決キャッシュを初期化し、他テストへの漏えいを防ぐ。"""
        app_paths.reset_path_caches()


class TestDataRootResolution(_DataRootIsolatedTest):
    """データルート（非同期領域）の解決規則を検証する。"""

    def test_env_override_wins(self) -> None:
        """NEO_HISHO_DATA_DIR が最優先で使用される。"""
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"NEO_HISHO_DATA_DIR": td}):
                app_paths.reset_path_caches()
                self.assertEqual(app_paths.get_data_root(), Path(td))

    def test_localappdata_default_subdir(self) -> None:
        """LOCALAPPDATA 配下の NeoHisho が既定のデータルートになる。"""
        with tempfile.TemporaryDirectory() as td:
            env = {k: v for k, v in os.environ.items() if k != "NEO_HISHO_DATA_DIR"}
            env["LOCALAPPDATA"] = td
            with patch.dict(os.environ, env, clear=True):
                app_paths.reset_path_caches()
                self.assertEqual(app_paths.get_data_root(), Path(td) / "NeoHisho")

    def test_paths_live_inside_data_root(self) -> None:
        """DB・トークン・バックアップがすべてデータルート配下に解決される。"""
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"NEO_HISHO_DATA_DIR": td}):
                app_paths.reset_path_caches()
                root = app_paths.get_data_root()
                self.assertEqual(app_paths.get_db_path(), root / "neo_secretary.db")
                self.assertEqual(app_paths.get_sync_token_path(), root / ".sync_token")
                self.assertEqual(app_paths.get_backups_dir(), root / "backups")

    def test_fallback_when_localappdata_missing(self) -> None:
        """LOCALAPPDATA 不在環境（CI等）でもホーム配下の NeoHisho へフォールバックする。"""
        with tempfile.TemporaryDirectory() as home_td:
            env = {
                k: v
                for k, v in os.environ.items()
                if k not in ("NEO_HISHO_DATA_DIR", "LOCALAPPDATA", "XDG_DATA_HOME")
            }
            env["USERPROFILE"] = home_td
            env["HOME"] = home_td
            with patch.dict(os.environ, env, clear=True):
                app_paths.reset_path_caches()
                root = app_paths.get_data_root()
                self.assertEqual(root.name, "NeoHisho")
                self.assertEqual(
                    root, Path(home_td) / ".local" / "share" / "NeoHisho"
                )

    def test_data_root_is_created(self) -> None:
        """データルートは解決時に自動作成される（DB作成前のディレクトリ欠如を防ぐ）。"""
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "nested" / "NeoHisho"
            with patch.dict(os.environ, {"NEO_HISHO_DATA_DIR": str(target)}):
                app_paths.reset_path_caches()
                self.assertTrue(app_paths.get_data_root().is_dir())


class TestCloudSyncedPathDetection(unittest.TestCase):
    """クラウド同期フォルダ（ADR-2 が配置を禁止する領域）の検知を検証する。"""

    def test_detects_onedrive(self) -> None:
        """OneDrive 配下のパスを検知する。"""
        self.assertTrue(
            app_paths.is_cloud_synced_path(
                r"C:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん\neo_secretary.db"
            )
        )

    def test_detects_other_major_providers(self) -> None:
        """Dropbox / Google Drive / iCloud / Box 配下を検知する。"""
        for marker in ("Dropbox", "Google Drive", "iCloud Drive", "Box"):
            with self.subTest(marker=marker):
                self.assertTrue(
                    app_paths.is_cloud_synced_path(Path("C:/Users/x") / marker / "proj" / "a.db")
                )

    def test_local_appdata_is_not_cloud(self) -> None:
        """ローカル AppData は非同期領域として False を返す。"""
        self.assertFalse(
            app_paths.is_cloud_synced_path(r"C:\Users\bonob\AppData\Local\NeoHisho\neo_secretary.db")
        )

    def test_onedrive_env_prefix_is_detected(self) -> None:
        """OneDrive 環境変数が指す独自フォルダ名（SkyDrive 等）も検知する。"""
        with patch.dict(os.environ, {"OneDrive": r"C:\Users\x\SkyDrive"}):
            self.assertTrue(
                app_paths.is_cloud_synced_path(r"C:\Users\x\SkyDrive\proj\neo_secretary.db")
            )


class TestResolveDbPath(_DataRootIsolatedTest):
    """``storage.connection.resolve_db_path`` の解決規則（単一チョークポイント）を検証する。"""

    def test_default_relative_name_resolves_to_data_root(self) -> None:
        """既定の相対名 ``neo_secretary.db`` はデータルートへ解決される。"""
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as app_td:
            with patch.dict(os.environ, {"NEO_HISHO_DATA_DIR": td}), \
                    patch.object(app_paths, "get_app_root", return_value=Path(app_td)):
                app_paths.reset_path_caches()
                self.assertEqual(
                    storage_connection.resolve_db_path(),
                    str(Path(td) / "neo_secretary.db"),
                )

    def test_explicit_tmp_path_is_untouched(self) -> None:
        """テスト等が渡す明示パス（一時ディレクトリ配下）は一切書き換えない。"""
        with tempfile.TemporaryDirectory() as td:
            explicit = str(Path(td) / "neo_secretary.db")
            with patch.dict(os.environ, {"NEO_HISHO_DATA_DIR": str(Path(td) / "data")}):
                app_paths.reset_path_caches()
                self.assertEqual(storage_connection.resolve_db_path(explicit), explicit)

    def test_absolute_path_is_untouched(self) -> None:
        """絶対パスの明示指定は書き換えない。"""
        explicit = str(Path(tempfile.gettempdir()) / "custom_name.db")
        self.assertEqual(storage_connection.resolve_db_path(explicit), explicit)

    def test_custom_bare_name_is_untouched(self) -> None:
        """既定名以外の相対名は書き換えない（明示的なカスタム指定を尊重）。"""
        self.assertEqual(storage_connection.resolve_db_path("custom.db"), "custom.db")

    def test_legacy_fallback_only_when_no_explicit_override(self) -> None:
        """明示上書きが無い場合に限り、未移行の旧DBを暫定使用する（上書き時は常にデータルート）。"""
        with tempfile.TemporaryDirectory() as legacy_td:
            legacy_db = Path(legacy_td) / "neo_secretary.db"
            legacy_db.write_bytes(b"legacy")
            # 上書きを空にして「明示なし」を再現し、旧配置を app_root とみなす
            with patch.dict(os.environ, {"NEO_HISHO_DATA_DIR": ""}), \
                    patch.object(app_paths, "get_app_root", return_value=Path(legacy_td)):
                app_paths.reset_path_caches()
                self.assertEqual(storage_connection.resolve_db_path(), str(legacy_db))

    def test_explicit_data_root_override_disables_legacy_fallback(self) -> None:
        """データルート上書き時は旧配置フォールバックを無効化し、本番DBへ解決しない。

        Notes:
            2026-09-23 障害: 上書きを無視して旧DB（本番）を返していたため、pytest 中の
            端末ペアリング試行が本番台帳へ書き込まれた。明示されたデータルートは
            常に権威（テスト隔離・運用切替の決定論を守る）。
        """
        with tempfile.TemporaryDirectory() as legacy_td, tempfile.TemporaryDirectory() as data_td:
            (Path(legacy_td) / "neo_secretary.db").write_bytes(b"legacy")
            with patch.dict(os.environ, {"NEO_HISHO_DATA_DIR": data_td}), \
                    patch.object(app_paths, "get_app_root", return_value=Path(legacy_td)):
                app_paths.reset_path_caches()
                self.assertEqual(
                    storage_connection.resolve_db_path(),
                    str(Path(data_td) / "neo_secretary.db"),
                    "上書きされたデータルートが最優先であること",
                )

    def test_case_variant_default_name_resolves_to_data_root(self) -> None:
        """大文字小文字違いの既定名（NEO_SECRETARY.DB）もデータルートへ解決される。"""
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as app_td:
            with patch.dict(os.environ, {"NEO_HISHO_DATA_DIR": td}), \
                    patch.object(app_paths, "get_app_root", return_value=Path(app_td)):
                app_paths.reset_path_caches()
                self.assertEqual(
                    storage_connection.resolve_db_path("NEO_SECRETARY.DB"),
                    str(Path(td) / "neo_secretary.db"),
                )

    def test_relative_parent_traversal_resolves_to_data_root(self) -> None:
        """冗長な相対表記（sub/../neo_secretary.db）も既定名としてデータルートへ解決される。"""
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as app_td:
            with patch.dict(os.environ, {"NEO_HISHO_DATA_DIR": td}), \
                    patch.object(app_paths, "get_app_root", return_value=Path(app_td)):
                app_paths.reset_path_caches()
                self.assertEqual(
                    storage_connection.resolve_db_path("sub/../neo_secretary.db"),
                    str(Path(td) / "neo_secretary.db"),
                )

    def test_relative_subdir_default_name_is_untouched(self) -> None:
        """相対サブディレクトリ配下の明示指定は書き換えない。"""
        self.assertEqual(
            storage_connection.resolve_db_path("sub/neo_secretary.db"),
            str(Path("sub") / "neo_secretary.db"),
        )

    def test_target_wins_when_exists(self) -> None:
        """移行後の新DBが存在する場合は新DBを返す（旧DBが残っていても）。"""
        with tempfile.TemporaryDirectory() as legacy_td, tempfile.TemporaryDirectory() as data_td:
            (Path(legacy_td) / "neo_secretary.db").write_bytes(b"legacy")
            target = Path(data_td) / "neo_secretary.db"
            target.write_bytes(b"new")
            with patch.dict(os.environ, {"NEO_HISHO_DATA_DIR": data_td}), \
                    patch.object(app_paths, "get_app_root", return_value=Path(legacy_td)):
                app_paths.reset_path_caches()
                self.assertEqual(storage_connection.resolve_db_path(), str(target))

    def test_default_backup_dir_resolves_to_data_root(self) -> None:
        """既定の ``backups`` ディレクトリはデータルート配下へ解決される。"""
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"NEO_HISHO_DATA_DIR": td}):
                app_paths.reset_path_caches()
                self.assertEqual(
                    storage_connection.resolve_backups_dir(),
                    str(Path(td) / "backups"),
                )


class TestMigrateLegacyData(_DataRootIsolatedTest):
    """旧データ（OneDrive 配下）の非同期領域への安全移行を検証する。"""

    def _create_legacy_db(self, root: Path) -> Path:
        """スキーマ初期化済みの旧DBを作成して返す。"""
        legacy_db = root / "neo_secretary.db"
        storage_connection.init_db(db_path=str(legacy_db))
        return legacy_db

    def test_migrates_db_without_regenerating_vapid_key(self) -> None:
        """移行後も VAPID 秘密鍵が同一であること（再生成＝全購読無効化を防ぐ）。"""
        with tempfile.TemporaryDirectory() as legacy_td, tempfile.TemporaryDirectory() as data_td:
            legacy_db = self._create_legacy_db(Path(legacy_td))
            pem_before = get_or_create_vapid_keys(db_path=str(legacy_db)).private_key_pem

            report = app_paths.migrate_legacy_data(
                legacy_root=Path(legacy_td), data_root=Path(data_td)
            )

            target = Path(data_td) / "neo_secretary.db"
            self.assertTrue(report.migrated_db)
            self.assertTrue(target.exists())
            self.assertEqual(
                get_or_create_vapid_keys(db_path=str(target)).private_key_pem,
                pem_before,
            )
            # 旧ファイルは削除ではなく退避（アーカイブへ移動）される
            self.assertFalse(legacy_db.exists())
            archived = list((Path(data_td) / "migration_archive").rglob("neo_secretary.db"))
            self.assertEqual(len(archived), 1)

    def test_migrates_sync_token(self) -> None:
        """旧 .sync_token がデータルートへ移動され、内容が保持される。"""
        with tempfile.TemporaryDirectory() as legacy_td, tempfile.TemporaryDirectory() as data_td:
            legacy_token = Path(legacy_td) / ".sync_token"
            legacy_token.write_text("a" * 64, encoding="utf-8")

            report = app_paths.migrate_legacy_data(
                legacy_root=Path(legacy_td), data_root=Path(data_td)
            )

            target_token = Path(data_td) / ".sync_token"
            self.assertTrue(report.migrated_token)
            self.assertEqual(target_token.read_text(encoding="utf-8"), "a" * 64)
            self.assertFalse(legacy_token.exists())

    def test_evacuates_legacy_backup_copies(self) -> None:
        """旧 backups/ の DB コピー（VAPID PEM 同梱）も非同期領域へ退避される。"""
        with tempfile.TemporaryDirectory() as legacy_td, tempfile.TemporaryDirectory() as data_td:
            legacy_backups = Path(legacy_td) / "backups"
            legacy_backups.mkdir()
            backup_file = legacy_backups / "neo_secretary_backup_20260101_000000.db"
            backup_file.write_bytes(b"backup-content")

            report = app_paths.migrate_legacy_data(
                legacy_root=Path(legacy_td), data_root=Path(data_td)
            )

            self.assertEqual(report.migrated_backups, 1)
            self.assertTrue((Path(data_td) / "backups" / backup_file.name).exists())
            self.assertFalse(backup_file.exists())

    def test_idempotent_second_run(self) -> None:
        """同一条件で2回実行しても安全（破壊・重複なし）。"""
        with tempfile.TemporaryDirectory() as legacy_td, tempfile.TemporaryDirectory() as data_td:
            legacy_db = self._create_legacy_db(Path(legacy_td))
            first = app_paths.migrate_legacy_data(
                legacy_root=Path(legacy_td), data_root=Path(data_td)
            )
            second = app_paths.migrate_legacy_data(
                legacy_root=Path(legacy_td), data_root=Path(data_td)
            )

            target = Path(data_td) / "neo_secretary.db"
            self.assertTrue(first.migrated_db)
            self.assertFalse(second.migrated_db)
            self.assertEqual(second.errors, [])
            self.assertTrue(target.exists())
            self.assertFalse(legacy_db.exists())

    def test_no_leftover_migrating_files_after_broken_legacy(self) -> None:
        """破損DB移行の失敗後に一時ファイル（*.migrating）が残らない。"""
        with tempfile.TemporaryDirectory() as legacy_td, tempfile.TemporaryDirectory() as data_td:
            legacy_db = Path(legacy_td) / "neo_secretary.db"
            legacy_db.write_text("this is not a sqlite database", encoding="utf-8")

            report = app_paths.migrate_legacy_data(
                legacy_root=Path(legacy_td), data_root=Path(data_td)
            )

            self.assertTrue(report.errors)
            self.assertEqual(list(Path(data_td).glob("*.migrating")), [])

    def test_locked_legacy_db_falls_back_to_copy_and_keeps_sidecars(self) -> None:
        """旧DBがロックされていてもコピー退避で警告を残し、-wal/-shm は本体と運命を共にする。"""
        with tempfile.TemporaryDirectory() as legacy_td, tempfile.TemporaryDirectory() as data_td:
            legacy_db = self._create_legacy_db(Path(legacy_td))
            wal = Path(str(legacy_db) + "-wal")
            shm = Path(str(legacy_db) + "-shm")
            wal.write_bytes(b"wal")
            shm.write_bytes(b"shm")

            real_move = app_paths.shutil.move

            def locked_move(src, dst, *args, **kwargs):
                if Path(src) == legacy_db:
                    raise PermissionError(32, "another process is using the file")
                return real_move(src, dst, *args, **kwargs)

            def byte_copy(source, destination):
                app_paths.shutil.copy2(source, destination)

            # SQLite を介さず退避レイヤだけを検証する (偽の WAL を SQLite が回収するのを防ぐ)
            with patch.object(app_paths, "_copy_sqlite_safely", side_effect=byte_copy), \
                    patch.object(app_paths, "_verify_sqlite", return_value=True), \
                    patch.object(app_paths.shutil, "move", side_effect=locked_move):
                report = app_paths.migrate_legacy_data(
                    legacy_root=Path(legacy_td), data_root=Path(data_td)
                )

            self.assertTrue(report.migrated_db)
            self.assertTrue(report.warnings, "コピー退避の警告が記録されること")
            self.assertTrue(legacy_db.exists(), "旧DB本体は削除しない (コピー残置)")
            self.assertTrue(wal.exists(), "-wal は本体と運命を共にする (単独退避しない)")
            self.assertTrue(shm.exists(), "-shm は本体と運命を共にする (単独退避しない)")
            self.assertTrue((Path(data_td) / "migration_archive").exists())

    def test_second_run_archives_leftover_legacy_db(self) -> None:
        """移行先が既存でも、残存した旧DB（機密同梱）はアーカイブへ再退避される。"""
        with tempfile.TemporaryDirectory() as legacy_td, tempfile.TemporaryDirectory() as data_td:
            legacy_db = self._create_legacy_db(Path(legacy_td))
            target = Path(data_td) / "neo_secretary.db"
            storage_connection.init_db(db_path=str(target))

            report = app_paths.migrate_legacy_data(
                legacy_root=Path(legacy_td), data_root=Path(data_td)
            )

            self.assertFalse(report.migrated_db, "移行先は上書きしない")
            self.assertFalse(legacy_db.exists(), "残存旧DBはアーカイブへ退避される")
            self.assertEqual(report.warnings, [])
            self.assertTrue(target.exists())
            self.assertTrue(list((Path(data_td) / "migration_archive").rglob("neo_secretary.db")))

    def test_existing_target_archives_leftover_sidecars_too(self) -> None:
        """移行先が既存でも、旧DBの -wal は本体と一緒に退避される (P1-N3 回帰ガード)。"""
        with tempfile.TemporaryDirectory() as legacy_td, tempfile.TemporaryDirectory() as data_td:
            legacy_db = self._create_legacy_db(Path(legacy_td))
            wal = Path(str(legacy_db) + "-wal")
            wal.write_bytes(b"wal")
            target = Path(data_td) / "neo_secretary.db"
            storage_connection.init_db(db_path=str(target))

            report = app_paths.migrate_legacy_data(
                legacy_root=Path(legacy_td), data_root=Path(data_td)
            )

            self.assertFalse(wal.exists(), "旧 -wal も本体と一緒に退避されること")
            self.assertEqual(report.warnings, [])
            self.assertTrue(
                list((Path(data_td) / "migration_archive").rglob("neo_secretary.db-wal"))
            )

    def test_locked_leftover_is_reported_as_residual_warning(self) -> None:
        """退避できない旧DB（機密同梱）が残った場合は警告で明示される。"""
        with tempfile.TemporaryDirectory() as legacy_td, tempfile.TemporaryDirectory() as data_td:
            legacy_db = self._create_legacy_db(Path(legacy_td))
            target = Path(data_td) / "neo_secretary.db"
            storage_connection.init_db(db_path=str(target))

            real_move = app_paths.shutil.move

            def locked_move(src, dst, *args, **kwargs):
                if Path(src) == legacy_db:
                    raise PermissionError(32, "another process is using the file")
                return real_move(src, dst, *args, **kwargs)

            with patch.object(app_paths.shutil, "move", side_effect=locked_move):
                report = app_paths.migrate_legacy_data(
                    legacy_root=Path(legacy_td), data_root=Path(data_td)
                )

            self.assertTrue(
                any("残存" in w for w in report.warnings),
                f"機密残存の警告が必要: {report.warnings}",
            )
            self.assertTrue(legacy_db.exists())

    def test_cloud_synced_data_root_is_rejected(self) -> None:
        """ADR-2 違反（クラウド同期フォルダへ移行）は errors で拒否し、DBを作らない。"""
        with tempfile.TemporaryDirectory() as legacy_td, tempfile.TemporaryDirectory() as cloud_td:
            legacy_db = self._create_legacy_db(Path(legacy_td))
            data_root = Path(cloud_td) / "OneDrive" / "NeoHisho"

            report = app_paths.migrate_legacy_data(
                legacy_root=Path(legacy_td), data_root=data_root
            )

            self.assertTrue(report.errors, "ADR-2 違反は errors として拒否されること")
            self.assertFalse((data_root / "neo_secretary.db").exists())
            self.assertTrue(legacy_db.exists())

    def test_existing_target_is_never_overwritten(self) -> None:
        """移行先に既存DBがある場合、旧DBで上書きせずアーカイブへ退避する（データ喪失なし）。"""
        with tempfile.TemporaryDirectory() as legacy_td, tempfile.TemporaryDirectory() as data_td:
            legacy_db = self._create_legacy_db(Path(legacy_td))
            target = Path(data_td) / "neo_secretary.db"
            storage_connection.init_db(db_path=str(target))
            target_bytes = target.read_bytes()

            report = app_paths.migrate_legacy_data(
                legacy_root=Path(legacy_td), data_root=Path(data_td)
            )

            self.assertFalse(report.migrated_db)
            self.assertTrue(report.skipped)
            self.assertEqual(target.read_bytes(), target_bytes, "移行先は上書きされないこと")
            self.assertFalse(legacy_db.exists(), "旧DBはアーカイブへ退避されること")
            self.assertTrue((Path(data_td) / "migration_archive").is_dir())

    def test_wal_resident_data_is_migrated(self) -> None:
        """WAL に残った（チェックポイント前の）データもスナップショットに含まれる。"""
        with tempfile.TemporaryDirectory() as legacy_td, tempfile.TemporaryDirectory() as data_td:
            legacy_db = Path(legacy_td) / "neo_secretary.db"
            keeper = sqlite3.connect(str(legacy_db))
            try:
                keeper.execute("PRAGMA journal_mode=WAL")
                keeper.execute("PRAGMA wal_autocheckpoint=0")
                keeper.execute("CREATE TABLE wal_probe (id INTEGER PRIMARY KEY, v TEXT)")
                keeper.execute("INSERT INTO wal_probe (v) VALUES ('kept-in-wal')")
                keeper.commit()

                report = app_paths.migrate_legacy_data(
                    legacy_root=Path(legacy_td), data_root=Path(data_td)
                )

                target = Path(data_td) / "neo_secretary.db"
                self.assertTrue(report.migrated_db)
                target_conn = sqlite3.connect(str(target))
                try:
                    rows = target_conn.execute("SELECT v FROM wal_probe").fetchall()
                finally:
                    target_conn.close()
                self.assertEqual(rows, [("kept-in-wal",)])
            finally:
                keeper.close()

    def test_broken_legacy_db_is_reported_without_corrupting_target(self) -> None:
        """破損（DBでない）旧ファイルはエラー報告され、不完全な移行先を残さない。"""
        with tempfile.TemporaryDirectory() as legacy_td, tempfile.TemporaryDirectory() as data_td:
            legacy_db = Path(legacy_td) / "neo_secretary.db"
            legacy_db.write_text("this is not a sqlite database", encoding="utf-8")

            report = app_paths.migrate_legacy_data(
                legacy_root=Path(legacy_td), data_root=Path(data_td)
            )

            self.assertFalse(report.migrated_db)
            self.assertTrue(report.errors)
            self.assertFalse((Path(data_td) / "neo_secretary.db").exists())
            self.assertFalse((Path(data_td) / "neo_secretary.db.migrating").exists())


class TestChokePointWiring(_DataRootIsolatedTest):
    """既定値の呼び出しが単一チョークポイント経由でデータルートへ到達することを検証する。"""

    def test_get_db_connection_default_uses_data_root(self) -> None:
        """引数なしの get_db_connection がデータルートに DB を作成する。"""
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as app_td:
            with patch.dict(os.environ, {"NEO_HISHO_DATA_DIR": td}), \
                    patch.object(app_paths, "get_app_root", return_value=Path(app_td)):
                app_paths.reset_path_caches()
                with storage_connection.get_db_connection():
                    pass
                self.assertTrue((Path(td) / "neo_secretary.db").exists())

    def test_init_db_default_uses_data_root(self) -> None:
        """引数なしの init_db がデータルートにスキーマを作成する。"""
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as app_td:
            with patch.dict(os.environ, {"NEO_HISHO_DATA_DIR": td}), \
                    patch.object(app_paths, "get_app_root", return_value=Path(app_td)):
                app_paths.reset_path_caches()
                storage_connection.init_db()
                self.assertTrue((Path(td) / "neo_secretary.db").exists())

    def test_backup_database_default_dir_uses_data_root(self) -> None:
        """backup_database の既定バックアップ先がデータルート配下になる。"""
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as src_td:
            source_db = Path(src_td) / "neo_secretary.db"
            storage_connection.init_db(db_path=str(source_db))
            with patch.dict(os.environ, {"NEO_HISHO_DATA_DIR": td}):
                app_paths.reset_path_caches()
                created = storage_connection.backup_database(
                    db_path=str(source_db), backup_dir="backups"
                )
            self.assertIsNotNone(created)
            self.assertTrue(str(created).startswith(str(Path(td) / "backups")))

    def test_token_file_constant_points_into_data_root(self) -> None:
        """local_sync_server.TOKEN_FILE がデータルートの .sync_token を指す。"""
        import local_sync_server

        self.assertEqual(local_sync_server.TOKEN_FILE, app_paths.get_sync_token_path())

    def test_agent_bridge_client_token_file_points_into_data_root(self) -> None:
        """agent_bridge_client.SYNC_TOKEN_FILE がデータルートの .sync_token を指す。"""
        import agent_bridge_client

        self.assertEqual(agent_bridge_client.SYNC_TOKEN_FILE, app_paths.get_sync_token_path())

    def test_no_hardcoded_legacy_token_paths_in_source(self) -> None:
        """旧リテラル（リポジトリ直下の .sync_token）がソースへ再流入していない。"""
        local_src = (Path(__file__).resolve().parent.parent / "local_sync_server.py").read_text(
            encoding="utf-8"
        )
        bridge_src = (Path(__file__).resolve().parent.parent / "agent_bridge_client.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn('Path(__file__).parent / ".sync_token"', local_src)
        self.assertIn("app_paths.get_sync_token_path()", local_src)
        self.assertNotIn('get_app_root() / ".sync_token"', bridge_src)
        self.assertIn("app_paths.get_sync_token_path()", bridge_src)

    def test_mcp_server_never_migrates_only_warns(self) -> None:
        """MCP サーバーは移行を実行せず警告のみ行う (DB分裂防止・P1-1 改定)。"""
        source = (
            Path(__file__).resolve().parent.parent / "hisho_mcp_server.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "migrate_legacy_data(",
            source,
            "データ所有者はアプリただ1つ (クライアントの移行は DB 分裂を生む)",
        )
        self.assertLess(
            source.index("warn_if_legacy_data_pending()"),
            source.index("database.init_db()"),
            "未移行の警告は init_db より前に行うこと",
        )

    def test_legacy_fallback_visibility_is_instrumented(self) -> None:
        """旧配置フォールバックの不可視化を防ぐ ERROR ログ機構が存在する (P1-2 回帰ガード)。"""
        source = (
            Path(__file__).resolve().parent.parent / "storage" / "connection.py"
        ).read_text(encoding="utf-8")
        self.assertIn("_LEGACY_FALLBACK_WARNED", source)
        self.assertIn("logger.error(", source)

    def test_no_direct_sqlite_connections_outside_choke_point(self) -> None:
        """sqlite3.connect が単一チョークポイント（storage/connection.py）と移行エンジン以外に存在しない。"""
        project_root = Path(__file__).resolve().parent.parent
        allowed = {"storage/connection.py", "app_paths.py"}
        skipped_dirs = ("tests", "build", "dist", "venv", ".venv", "backups", "docs")
        offenders = []
        for source in project_root.rglob("*.py"):
            relative = source.relative_to(project_root).as_posix()
            if relative.split("/")[0] in skipped_dirs:
                continue
            if "sqlite3.connect(" in source.read_text(encoding="utf-8"):
                if relative not in allowed:
                    offenders.append(relative)
        self.assertEqual(offenders, [], f"データ境界を迂回する直接接続: {offenders}")


if __name__ == "__main__":
    unittest.main()
