"""
pytest 共通フィクスチャ (tests/conftest.py)

目的 (P0-4 / ADR-2):
    テスト実行が**実データ（本番 DB・本番 .sync_token）に一切触れない**よう、
    データ境界の環境変数 `NEO_HISHO_DATA_DIR` をセッション専用の一時領域へ固定する。

設計注記:
    - 本処理は **conftest の import 時**（テストモジュールの collection より前）に実行する。
      `local_sync_server.TOKEN_FILE` 等のモジュール定数は import 時に解決されるため、
      fixture (autouse) では遅すぎる。
    - 環境変数が既に設定されていても**強制上書き**する（実データ領域への書込みを
      決定論的に防ぐ。受入条件5「実データを一切変更しない」の保証を環境依存にしない）。
    - 一時領域はプロセス終了時（atexit）に削除する。
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path

import pytest

# --- データ境界のテスト隔離（import 時に確定させる） -----------------------------
_DATA_DIR = tempfile.mkdtemp(prefix="neo_hisho_test_data_")
atexit.register(shutil.rmtree, _DATA_DIR, True)
os.environ["NEO_HISHO_DATA_DIR"] = _DATA_DIR

# app_paths が既に import 済みでもキャッシュを無効化して env を反映させる
try:
    import app_paths

    app_paths.reset_path_caches()
except Exception:  # pragma: no cover - app_paths 不在時は何もしない
    pass


@pytest.fixture(autouse=True)
def _assert_isolated_data_boundary():
    """全テストで「既定DBパスがテスト用データルート配下」であることを強制する。

    P0-4 の隔離保証（受入条件5: 実データを一切変更しない）。上書きを無視して
    本番領域へ解決する退行が混入した場合、この fixture が即座に失敗させる
    (2026-09-23: 本番台帳へのテスト書込み障害の再発防止)。
    """
    import storage.connection as storage_connection

    resolved = Path(storage_connection.resolve_db_path()).resolve()
    assert str(resolved).startswith(str(Path(_DATA_DIR).resolve())), (
        f"テスト隔離違反: 既定DBパスがテスト用データルート外へ解決されました: {resolved}"
    )
    yield
