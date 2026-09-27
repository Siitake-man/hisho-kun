#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_web_pet_lang_toggle.py

PWA ヘッダーの EN/JA トグルが 1 タップで 1 回だけ切り替わることの規約テスト。

背景: index.html の inline onclick と lang.js の addEventListener('click'/'touchend')
が二重に発火し、1 タップで en→ja→en→ja と往復して元の言語に戻っていた。
イベントは lang.js の bindToggleButton()（300ms 二重発火抑止付き）に一本化する。
"""

import re
import unittest
from pathlib import Path

WEB_PET = Path(__file__).resolve().parent.parent / "web_pet"


class TestLangToggleSingleBinding(unittest.TestCase):

    def test_lang_toggle_button_has_no_inline_onclick(self) -> None:
        """#lang-toggle-btn に inline onclick が無いこと（lang.js のリスナーと二重発火するため）。"""
        html = (WEB_PET / "index.html").read_text(encoding="utf-8")
        tags = re.findall(r"<button[^>]*\bid=\"lang-toggle-btn\"[^>]*>", html)
        self.assertEqual(len(tags), 1, "index.html に #lang-toggle-btn がちょうど 1 つ存在すること")
        self.assertNotIn("onclick", tags[0].lower(), f"inline onclick が残っています: {tags[0]}")

    def test_lang_js_binds_toggle_button(self) -> None:
        """lang.js がトグルボタンへ click リスナーを登録していること（一本化先の存在確認）。"""
        js = (WEB_PET / "lang.js").read_text(encoding="utf-8")
        self.assertIn("getElementById('lang-toggle-btn')", js)
        self.assertIn("addEventListener('click', safeHandler", js)


if __name__ == "__main__":
    unittest.main()
