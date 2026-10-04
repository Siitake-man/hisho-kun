#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネオ秘書くん - 同期サーバー認証トークン管理 (sync_token_manager / S1a Seam).

(server/sync_token_manager.py)

目的:
    Fat モジュール `local_sync_server.py` から、Zero-Trust Bearer 認証トークンの
    発行・検証・失効（再生成）および QR コードペアリング一時開放を独立した
    Deep Module として切り出す。

防衛策:
    - 🛡️ P0-1: 同期トークン再生成時、ゼロトラスト端末台帳 (devices) を一括失効
    - 🛡️ P0-2: 未承認外部端末接続時の Human-in-the-Loop 承認コールバック
    - 🛡️ P0-3: PC内ブラウザ専用 loopback トークンの分離 (マスター鍵はHTTP非配布)
    - 🛡️ P0-4: マスタートークンのデータ境界 (app_paths.get_sync_token_path()) 配置
    - 🛡️ 知見ID 45: import database 形式維持によるテスト patch 互換性保全
"""

from __future__ import annotations

import hmac
import logging
import secrets
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import app_paths
import database

# 親ロガー local_sync_server へのログ伝播 (propagation) を担保する階層ロガー
logger = logging.getLogger("local_sync_server.sync_token_manager")

def _get_token_file() -> Path:
    """データ境界内のトークンファイルパスを取得する (都度解決・遅延バインド).

    知見ID 45 (Seam分割×モックの罠) 防衛:
        既存テスト（tests/test_sync_token_regenerate.py等）が
        `patch.object(local_sync_server, "TOKEN_FILE", ...)` または
        `patch("server.sync_token_manager.TOKEN_FILE", ...)` を実行した場合、
        パッチされたパスを透過的に検知して使用する。
    """
    import sys

    # 1. local_sync_server.TOKEN_FILE の patch を検知
    lss = sys.modules.get("local_sync_server")
    if lss is not None and hasattr(lss, "TOKEN_FILE"):
        lss_val = getattr(lss, "TOKEN_FILE")
        if lss_val is not None and str(lss_val) != str(app_paths.get_sync_token_path()):
            return Path(lss_val)

    # 2. 本モジュール TOKEN_FILE の patch を検知
    mod_token = globals().get("TOKEN_FILE")
    if mod_token is not None and str(mod_token) != str(app_paths.get_sync_token_path()):
        return Path(mod_token)

    return app_paths.get_sync_token_path()


TOKEN_FILE: Path = _get_token_file()


class SyncTokenManager:
    """同期サーバーのBearerトークンを生成・検証するマネージャー。

    起動時に暗号論的乱数でトークンを生成し .sync_token に保存する。
    スマホ/PWAは初回アクセス時にこのトークンを取得して以降のAPI呼び出しに
    Authorization: Bearer ヘッダーで添付する。トークン無し・不一致の
    APIリクエストは401で拒否される。
    """

    def __init__(self) -> None:
        self._token: str = ""
        # 🛡️ P0-3 (2026-09-22): PC内ブラウザ専用の loopback トークン。
        # マスター鍵 (self._token) は HTTP で一切配布しない (ループバックでも配らない)。
        # 台帳 (devices) にも登録しないため、PCブラウザ利用で台帳を汚さない。
        self._loopback_token: str = secrets.token_hex(32)
        self._lock = threading.Lock()
        # ペアリングモードの解除期限(epoch秒)。QR接続ダイアログ表示中のみトークン配布APIを開放する(Fail-Closed)
        self._pairing_unlocked_until: float = 0.0
        # 🛡️ P0-2: 未承認外部端末接続時の Human-in-the-Loop 承認コールバック
        self._device_approval_callback: Optional[Callable[[str, str], bool]] = None
        self._load_or_create()

    def set_device_approval_callback(
        self, callback: Optional[Callable[[str, str], bool]]
    ) -> None:
        """未承認端末接続時の Human-in-the-Loop 承認コールバックを登録する。

        Args:
            callback: Callable[[str, str], bool] - (device_name, client_ip) を受け取り、
                      ユーザー承認時は True、拒否時は False を返す関数。
        """
        with self._lock:
            self._device_approval_callback = callback

    @property
    def device_approval_callback(self) -> Optional[Callable[[str, str], bool]]:
        """登録されている端末接続承認コールバックを返す。"""
        with self._lock:
            return self._device_approval_callback

    @property
    def pairing_open(self) -> bool:
        """トークン配布（ペアリング受付）が現在有効かどうかを返す。

        Returns:
            bool: QRペアリング期間中(解除期限以内)の場合 True。
        """
        with self._lock:
            return time.time() < self._pairing_unlocked_until

    def unlock_pairing(self, duration_sec: int = 600) -> None:
        """QR接続ダイアログ表示中等に限り、トークン配布API (/api/auth/token) を開放する。

        常時開放すると同一LAN上の第三者が GET /api/auth/token でトークンを取得できてしまうため、
        PCユーザーが明示的にペアリング操作を行っている期間のみ応答する Fail-Closed 設計とした。

        Args:
            duration_sec (int): 開放する秒数。デフォルト600秒(10分)。連続呼び出し時は期限が延長される。
        """
        with self._lock:
            self._pairing_unlocked_until = max(
                self._pairing_unlocked_until, time.time() + float(duration_sec)
            )
        logger.info(f"🔐 [SyncAuth] ペアリングモードを {duration_sec} 秒間開放しました")

    def close_pairing(self) -> None:
        """QRペアリング待機を即座に終了する (ワンタイム化・P0-2対策)。"""
        with self._lock:
            self._pairing_unlocked_until = 0.0
        logger.info("🔐 [SyncAuth] ペアリングモードを終了（クローズ）しました")

    def _save_token(self) -> None:
        """トークンを .sync_token へアトミックに書き込む。

        読み取りとの競合を防ぐため、一時ファイルに書き込んでからリネームする。
        """
        token_file = _get_token_file()
        try:
            tmp = token_file.with_suffix(".sync_token.tmp")
            tmp.write_text(self._token, encoding="utf-8")
            tmp.replace(token_file)
        except Exception as e:
            logger.warning(f".sync_token のアトミック書き込みに失敗（直接書き込みにフォールバック）: {e}")
            token_file.write_text(self._token, encoding="utf-8")

    def _load_or_create(self) -> None:
        """既存トークンを読み込み、無ければ新規生成して保存する。"""
        token_file = _get_token_file()
        try:
            if token_file.exists():
                stored = token_file.read_text(encoding="utf-8").strip()
                if len(stored) >= 32:
                    self._token = stored
                    logger.info("🔐 [SyncAuth] 既存の同期トークンをロードしました")
                    return
            # 32バイト=256bit の暗号論的乱数をhex化（64文字）
            self._token = secrets.token_hex(32)
            self._save_token()
            logger.info(f"🔐 [SyncAuth] 新しい同期トークンを生成しました: {token_file.name}")
        except Exception as e:
            # トークンファイルI/O失敗時もセッション限定トークンで運用継続（Fail-Closedではないが可用性優先）
            self._token = secrets.token_hex(32)
            logger.warning(f"🔐 [SyncAuth] トークンファイル操作エラー、セッション限定トークンで起動: {e}")

    @property
    def token(self) -> str:
        """現在の有効トークンを返す。"""
        return self._token

    def verify(self, presented: str) -> bool:
        """提示されたトークンを定数時間比較で検証する。"""
        if not presented:
            return False
        return hmac.compare_digest(presented.strip(), self._token)

    @property
    def loopback_token(self) -> str:
        """PC内ブラウザ専用の loopback トークンを返す（マスター鍵とは別の資格情報）。"""
        return self._loopback_token

    def verify_loopback(self, presented: str) -> bool:
        """loopback 専用トークンを定数時間比較で検証する。

        Args:
            presented (str): 提示された Bearer トークン文字列。

        Returns:
            bool: 一致した場合 True。
        """
        if not presented:
            return False
        return hmac.compare_digest(presented.strip(), self._loopback_token)

    def regenerate(self) -> str:
        """既存トークンを無効化し、新しいトークンを生成・保存する。

        設定画面の「スマホ連携 全解除（トークン再生成）」ボタンから呼び出される
        ワンクリック操作。トークンを差し替えることで、スマホ側に保存された旧
        トークンによる全セッションを即座に無効化する（セッション全破棄 /
        紛失・売却・リセット時のセキュリティ対処）。
        さらに、ゼロトラスト端末台帳（devices テーブル）の全個別端末も一括失効させる (P0-1 対策)。

        Returns:
            str: 新しく生成された同期トークン (64文字hex)。
        """
        with self._lock:
            self._token = secrets.token_hex(32)
            self._save_token()
        try:
            database.revoke_all_devices()
        except Exception as e:
            logger.error(f"全端末一括失効エラー (グローバルトークン再生成は完了): {e}")
        logger.warning(
            "🔐 [SyncAuth] 同期トークンを再生成し、全接続端末を一括失効しました。"
            "既存のスマホ接続セッションはすべて無効になります"
        )
        return self._token


_global_token_manager: Optional[SyncTokenManager] = None


def get_sync_token_manager() -> SyncTokenManager:
    """SyncTokenManager のシングルトンを取得する。"""
    global _global_token_manager
    if _global_token_manager is None:
        _global_token_manager = SyncTokenManager()
    return _global_token_manager


__all__: list[str] = [
    "SyncTokenManager",
    "get_sync_token_manager",
    "TOKEN_FILE",
]
