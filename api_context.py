#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - 同期サーバーAPI共通コンテキスト (api_context.py)

P2③ 分割リファクタ (Divergent Change 解消) のため、local_sync_server.py の
DeskPetSyncHandler.do_POST God Function を機能別モジュール (api_tasks /
api_agent_bridge / api_calendar) へ抽出する際の Seam (接合点) を定義する。

設計:
- 各ハンドラは ``handler(ctx: ApiContext) -> bool`` 署名を持つモジュール関数とし、
  HTTP ハンドラインスタンスには ApiContext 経由でのみアクセスする。
- アクション系ハンドラは「レスポンスを書き込んだら True / 書き込めなかったら
  False」を返す。パラメータ欠落等のガード未成立時も明示エラー ({"status": "error"})
  を書き込んで True を返すのが規約 (2026-09-03 改修: 旧仕様の無応答200空ボディは
  廃止済み。unknown action エラー応答に変換されるのは「未知のアクション名」のみ)。
- 共通のレスポンス前導処理 (send_response + Content-Type + CORS + end_headers)
  を begin_json_response に集約し、God Function 内での重複を排除する。
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict

logger = logging.getLogger(__name__)


@dataclass
class ApiContext:
    """POST ハンドラに引き渡すリクエストコンテキスト (Seam オブジェクト)。

    Attributes:
        handler: DeskPetSyncHandler インスタンス (レスポンス書き込みに使用)。
        body: リクエストボディの生バイト列。
        client_ip: 接続元クライアントIP。
        user_agent: リクエストの User-Agent ヘッダー値。
        auth_identity: _check_auth が解決した認証主体の識別子。
            ``"pc-loopback"`` (loopback 専用トークン) / ``"agent"`` (マスター
            トークン + trusted_loopback) / ``"device:<uuid>"`` (端末個別トークン
            および台帳照合成功のマスタートークン行) / ``""`` (未認証・unknown)。
            自己承認防止チェックの同一性判定に使用する (Tailscale Serve 等の
            プロキシが IP を 127.0.0.1 へ同一化するため IP 比較は不能)。
    """

    handler: Any
    body: bytes = b""
    client_ip: str = "unknown"
    user_agent: str = ""
    auth_identity: str = ""
    _headers_sent: bool = field(default=False, init=False)

    def begin_json_response(self, status_code: int = 200) -> None:
        """JSONレスポンスの共通前導処理 (ステータス行・ヘッダー送出) を行う。

        既にヘッダーが送出済みの場合は二重送出を防止してスキップする。

        Args:
            status_code: 送出するHTTPステータスコード。
        """
        if self._headers_sent:
            logger.debug("ヘッダーは既に送出済みのため、begin_json_response をスキップします")
            return
        self.handler.send_response(status_code)
        self.handler.send_header("Content-Type", "application/json; charset=utf-8")
        self.handler._set_cors_headers()
        self.handler.end_headers()
        self._headers_sent = True

    def write_json(self, payload: Dict[str, Any], ensure_ascii: bool = True,
                   status_code: int = 200) -> None:
        """JSONペイロードをレスポンスボディへ書き込む。

        ヘッダーがまだ送出されていない場合、指定された status_code で自動的に
        ヘッダーを送出する (遅延ヘッダー送出 / Lazy Headers)。

        Args:
            payload: 書き込む辞書ペイロード。
            ensure_ascii: False の場合は非ASCII文字をそのまま出力する。
            status_code: 初回ヘッダー送出時に使用するHTTPステータスコード。
        """
        if not self._headers_sent:
            self.begin_json_response(status_code=status_code)
        self.handler.wfile.write(json.dumps(payload, ensure_ascii=ensure_ascii).encode("utf-8"))

    def send_json(self, payload: Dict[str, Any], ensure_ascii: bool = True,
                  status_code: int = 200) -> None:
        """前導処理からボディ書き込みまでを一括で行う。

        Args:
            payload: 書き込む辞書ペイロード。
            ensure_ascii: False の場合は非ASCII文字をそのまま出力する。
            status_code: 送出するHTTPステータスコード。
        """
        if not self._headers_sent:
            self.begin_json_response(status_code=status_code)
        self.write_json(payload, ensure_ascii=ensure_ascii, status_code=status_code)

    def send_error_json(self, message: str, ensure_ascii: bool = True,
                        status_code: int = 400) -> None:
        """共通エラーレスポンス ({"status": "error", "message": ...}) を送信する。

        Args:
            message: クライアントへ返すエラーメッセージ。
            ensure_ascii: False の場合は非ASCII文字をそのまま出力する。
            status_code: 送出するHTTPステータスコード (デフォルト: 400)。
        """
        self.write_json({"status": "error", "message": message}, ensure_ascii=ensure_ascii,
                        status_code=status_code)

