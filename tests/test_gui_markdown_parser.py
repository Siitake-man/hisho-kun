"""
デスクトップ吹き出し マークダウン軽量パーサー TDD 単体テスト (tests/test_gui_markdown_parser.py)

ユーザー要望:
「デスクトップ側の秘書君のセリフがマークダウン形式で書かれてるようですが、
マークダウンの表示機能がないから強調表示などがされません」
この要望に応え、アスタリスク（**）を取り除きつつ太字（bold）タグを付与する
パーサーの安全性・境界値・装飾範囲を自動検証します。
"""

import unittest
from ui.markdown_helper import parse_markdown_spans, clean_markdown_text


class TestGuiMarkdownParser(unittest.TestCase):
    """マークダウン軽量パーサーの単体テスト"""

    def test_01_plain_text(self):
        """装飾のない平文テキストはそのまま返却されること"""
        text = "おはようございます！本日の予定はいかがなさいますか？"
        clean, spans = parse_markdown_spans(text)
        self.assertEqual(clean, text)
        self.assertEqual(spans, [])

    def test_02_single_bold_span(self):
        """単一の **太字** からアスタリスクが除去され、太字スパンが特定されること"""
        text = "本日のご予定に**予定はありません**でした。"
        clean, spans = parse_markdown_spans(text)
        self.assertEqual(clean, "本日のご予定に予定はありませんでした。")
        self.assertEqual(len(spans), 1)
        # スパンの検証: start, end, tag
        start, end, tag = spans[0]
        self.assertEqual(clean[start:end], "予定はありません")
        self.assertEqual(tag, "bold")

    def test_03_multiple_bold_spans(self):
        """複数の **太字** が混在する場合、すべてのアスタリスクが除去され正しくスパン抽出されること"""
        text = "📅 **本日のご予定**\n本日（9/14）に予定されている**予定はありません**でした。"
        clean, spans = parse_markdown_spans(text)
        self.assertEqual(clean, "📅 本日のご予定\n本日（9/14）に予定されている予定はありませんでした。")
        self.assertEqual(len(spans), 2)
        self.assertEqual(clean[spans[0][0]:spans[0][1]], "本日のご予定")
        self.assertEqual(clean[spans[1][0]:spans[1][1]], "予定はありません")

    def test_04_odd_asterisks_robustness(self):
        """奇数個のアスタリスクや壊れた記法でもクラッシュせず安全にフォールバックすること"""
        text = "これは **壊れたマークダウン です。"
        clean, spans = parse_markdown_spans(text)
        # 閉じられていない場合はそのまま保持、または安全に処理
        self.assertIsInstance(clean, str)
        self.assertIsInstance(spans, list)

    def test_05_clean_markdown_text_utility(self):
        """clean_markdown_text ヘルパーが不要記号を安全に平文化すること"""
        text = "ボス、**本日**の会議は*重要*です！"
        cleaned = clean_markdown_text(text)
        self.assertEqual(cleaned, "ボス、本日の会議は重要です！")


if __name__ == "__main__":
    unittest.main()
