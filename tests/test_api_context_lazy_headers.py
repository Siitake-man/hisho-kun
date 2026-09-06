#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - ApiContext 遅延ヘッダー送出 (Lazy Headers) テスト
(tests/test_api_context_lazy_headers.py)

Sprint A 第1弾: 400化構造改革の TDD テスト。
ApiContext.write_json が初回呼び出し時に初めてヘッダー (send_response / send_header / end_headers)
を送出する「遅延送出 (Lazy Headers)」を行い、status_code 引数で HTTP ステータスを制御できることを検証する。
"""

import json
import sys
import unittest
from io import BytesIO
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api_context import ApiContext


class FakeHandler:
    """テスト用の擬似 HTTP ハンドラ"""

    def __init__(self):
        self.wfile = BytesIO()
        self.sent_responses = []
        self.sent_headers = []
        self.headers_ended = False
        self.cors_called = False

    def send_response(self, code, message=None):
        self.sent_responses.append(code)

    def send_header(self, keyword, value):
        self.sent_headers.append((keyword, value))

    def end_headers(self):
        self.headers_ended = True

    def _set_cors_headers(self):
        self.cors_called = True


class TestApiContextLazyHeaders(unittest.TestCase):
    """ApiContext の遅延ヘッダー送出とステータスコード制御のテスト"""

    def setUp(self):
        self.fake_handler = FakeHandler()
        self.ctx = ApiContext(handler=self.fake_handler, body=b'{"test": 1}')

    def test_headers_not_sent_on_initialization(self):
        """初期化時点ではヘッダー送出が行われないこと (遅延の前提)"""
        self.assertEqual(len(self.fake_handler.sent_responses), 0)
        self.assertFalse(self.fake_handler.headers_ended)
        self.assertFalse(getattr(self.ctx, "_headers_sent", False))

    def test_write_json_default_sends_200_headers_lazily(self):
        """write_json() を呼んだ瞬間にデフォルトで HTTP 200 ヘッダーが送出されること"""
        payload = {"status": "success", "data": 123}
        self.ctx.write_json(payload)

        # ヘッダーが1回だけ送出されたこと
        self.assertEqual(self.fake_handler.sent_responses, [200])
        self.assertTrue(self.fake_handler.headers_ended)
        self.assertTrue(self.fake_handler.cors_called)
        self.assertTrue(self.ctx._headers_sent)

        # ボディが正しく書き込まれていること
        written = json.loads(self.fake_handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(written, payload)

    def test_write_json_custom_status_code_400(self):
        """write_json(..., status_code=400) で HTTP 400 ヘッダーが送出されること"""
        payload = {"status": "error", "message": "bad request"}
        self.ctx.write_json(payload, status_code=400)

        self.assertEqual(self.fake_handler.sent_responses, [400])
        self.assertTrue(self.fake_handler.headers_ended)

        written = json.loads(self.fake_handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(written, payload)

    def test_multiple_write_json_does_not_duplicate_headers(self):
        """write_json() を複数回呼んでも、ヘッダーは初回のみ送出されること (二重送出防止)"""
        self.ctx.write_json({"part": 1}, status_code=200)
        self.ctx.write_json({"part": 2})

        # send_response は1回だけ
        self.assertEqual(self.fake_handler.sent_responses, [200])

    def test_send_error_json_defaults_to_400_or_custom_status(self):
        """send_error_json が status_code 引数を受け付け、適切にヘッダーを送出すること"""
        self.ctx.send_error_json("invalid payload", status_code=400)

        self.assertEqual(self.fake_handler.sent_responses, [400])
        written = json.loads(self.fake_handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(written, {"status": "error", "message": "invalid payload"})

    def test_explicit_begin_json_response_marks_headers_sent(self):
        """明示的に begin_json_response() を呼んだ場合、後続の write_json でヘッダーが再送されないこと"""
        self.ctx.begin_json_response(status_code=201)
        self.assertEqual(self.fake_handler.sent_responses, [201])

        # 後続の write_json で 201 が上書き・再送されないこと
        self.ctx.write_json({"created": True}, status_code=200)
        self.assertEqual(self.fake_handler.sent_responses, [201])


if __name__ == "__main__":
    unittest.main()
