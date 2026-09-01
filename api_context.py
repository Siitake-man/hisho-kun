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
  False」を返す。False の場合は呼び出し元が旧仕様どおり unknown action エラー
  を応答する (既知の技術的負債: パラメータ欠落時は無応答200になる現行の
  振る舞いを characterization テストで固定済み)。
- 共通のレスポンス前導処理 (send_response + Content-Type + CORS + end_headers)
  を begin_json_response に集約し、God Function 内での重複を排除する。
"""

import json
import logging
from dataclasses import dataclass
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
    """

    handler: Any
    body: bytes = b""
    client_ip: str = "unknown"
    user_agent: str = ""

    def begin_json_response(self, status_code: int = 200) -> None:
        """JSONレスポンスの共通前導処理 (ステータス行・ヘッダー送出) を行う。

        Args:
            status_code: 送出するHTTPステータスコード。
        """
        self.handler.send_response(status_code)
        self.handler.send_header("Content-Type", "application/json; charset=utf-8")
        self.handler._set_cors_headers()
        self.handler.end_headers()

    def write_json(self, payload: Dict[str, Any], ensure_ascii: bool = True) -> None:
        """JSONペイロードをレスポンスボディへ書き込む。

        Args:
            payload: 書き込む辞書ペイロード。
            ensure_ascii: False の場合は非ASCII文字をそのまま出力する。
        """
        self.handler.wfile.write(json.dumps(payload, ensure_ascii=ensure_ascii).encode("utf-8"))

    def send_json(self, payload: Dict[str, Any], ensure_ascii: bool = True,
                  status_code: int = 200) -> None:
        """前導処理からボディ書き込みまでを一括で行う。

        Args:
            payload: 書き込む辞書ペイロード。
            ensure_ascii: False の場合は非ASCII文字をそのまま出力する。
            status_code: 送出するHTTPステータスコード。
        """
        self.begin_json_response(status_code=status_code)
        self.write_json(payload, ensure_ascii=ensure_ascii)

    def send_error_json(self, message: str, ensure_ascii: bool = True) -> None:
        """共通エラーレスポンス ({"status": "error", "message": ...}) を送信する。

        Args:
            message: クライアントへ返すエラーメッセージ。
            ensure_ascii: False の場合は非ASCII文字をそのまま出力する。
        """
        self.write_json({"status": "error", "message": message}, ensure_ascii=ensure_ascii)
