"""
ネオ秘書くん - web_tools および suggest_engine ニュースサジェスト単体テスト
"""
import unittest
import json
from unittest.mock import patch, MagicMock

import web_tools
from suggest_engine import SuggestionEngine


class TestSuggestNewsSummary(unittest.TestCase):
    """ニュース RSS パース・キーワード永続化・3行サマリ生成の契約を検証する。

    LLM オフライン時のルールベースフォールバックが必ず3行を返し、
    サジェスト文が案内文で埋め尽くされないこと（サジェスト品質）を守る。
    """

    def test_fetch_news_rss_structure(self):
        """Google News RSS パース結果が正しい辞書構造（id, title, media, link, description）を持つか検証"""
        xml_str = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>Google ニュース</title>
            <item>
              <title>LangGraph 0.3 リリース - Python開発者マガジン</title>
              <link>https://news.google.com/articles/12345</link>
              <pubDate>Sun, 30 Aug 2026 12:00:00 GMT</pubDate>
              <description>&lt;a href="..."&gt;LangGraphの新バージョンが発表されました。状態管理が強化されています。&lt;/a&gt;</description>
            </item>
          </channel>
        </rss>
        """
        mock_xml = xml_str.encode("utf-8")

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = mock_xml
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            items = web_tools.fetch_news_rss(query="LangGraph", limit=1)
            self.assertEqual(len(items), 1)
            item = items[0]
            self.assertEqual(item["title"], "LangGraph 0.3 リリース")
            self.assertEqual(item["media"], "Python開発者マガジン")
            self.assertEqual(item["link"], "https://news.google.com/articles/12345")
            self.assertIn("状態管理が強化されています", item["description"])
            self.assertNotIn("<", item["description"])  # HTMLタグが除去されていること

    def test_suggest_engine_keywords_management(self):
        """ニュース関心キーワードの取得・更新・永続化が正しく動作するか検証"""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp_dir:
            config_file = Path(tmp_dir) / "suggest_config.json"
            initial_config = {
                "sources": {
                    "news_topics": {
                        "name": "🌐 関心ニュース・AIトレンド",
                        "enabled": True,
                        "description": "テスト用",
                        "keywords": ["AI", "ネットワーク"]
                    }
                }
            }
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(initial_config, f)

            with patch("suggest_engine.CONFIG_PATH", config_file):
                engine = SuggestionEngine(start_worker=False)
                self.assertEqual(engine.get_news_keywords(), ["AI", "ネットワーク"])

                # カンマ区切りの文字列で更新
                engine.set_news_keywords("クラウド, Kubernetes, BGP")
                self.assertEqual(engine.get_news_keywords(), ["クラウド", "Kubernetes", "BGP"])

                # ファイルに正しく永続化されたか検証
                with open(config_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self.assertEqual(saved["sources"]["news_topics"]["keywords"], ["クラウド", "Kubernetes", "BGP"])

    def test_generate_3line_summary_fallback(self):
        """LLMが利用できない場合にルールベースの3行サマリが生成されるか検証"""
        engine = SuggestionEngine(start_worker=False)
        title = "新世代ネットワークルーターの性能測定結果"
        desc = "BGP経路の収束速度が従来の2倍に向上しました。メモリ消費量も半減しています。エンタープライズNW向けに提供が開始されます。"
        
        # LLMをモックで例外にし、ルールベースフォールバックを検証
        with patch("llm_factory.get_llm_factory", side_effect=Exception("LLM offline")):
            summary = engine._generate_3line_summary(title, desc, media="NW通信")
            lines = summary.splitlines()
            self.assertEqual(len(lines), 3)
            self.assertTrue(all(line.startswith("・") for line in lines))

    def test_extract_content_points_splits_sentences(self):
        """descriptionが文単位のポイントに分解され、タイトル反復・ノイズ行が除外されるか検証"""
        engine = SuggestionEngine(start_worker=False)
        title = "新技術の発表会が開催"
        desc = "新技術の発表会が開催された。処理速度が3倍に向上した。対応機器が拡大している。 - Tech Media"
        points = engine._extract_content_points(desc, title, media="Tech Media")
        self.assertGreaterEqual(len(points), 2)
        # タイトル反復の先頭文はポイントに含まれない
        self.assertFalse(any("発表会が開催された" in p for p in points))
        # 実内容の文は含まれる
        self.assertTrue(any("処理速度" in p for p in points))
        # 媒体名サフィックスは除去されている
        self.assertFalse(any("Tech Media" in p for p in points))

    def test_fallback_no_meta_filler_when_desc_has_content(self):
        """descriptionに実内容がある場合、案内文（タップで詳細）で行を埋めないか検証"""
        engine = SuggestionEngine(start_worker=False)
        title = "次世代AIチップが発表"
        desc = "消費電力を従来の半分に抑えた。推論性能は2倍に向上した。"
        with patch("llm_factory.get_llm_factory", side_effect=Exception("LLM offline")):
            summary = engine._generate_3line_summary(title, desc, media="HW Times")
            lines = summary.splitlines()
            self.assertEqual(len(lines), 3)
            # 3行すべてが実内容ポイントであり、案内文は混入しない
            self.assertNotIn("タップ", summary)

    def test_fallback_tap_hint_limited_to_one_line(self):
        """descriptionがタイトル反復のみの場合、案内文は1行に限られるか検証"""
        engine = SuggestionEngine(start_worker=False)
        title = "国産セキュリティサービス提供開始（2026年8月27日）"
        # Google News RSS 特有の「タイトルの反復＋媒体名」パターン
        desc = "国産セキュリティサービス提供開始（2026年8月27日）：プレスリリース - NEC"
        with patch("llm_factory.get_llm_factory", side_effect=Exception("LLM offline")):
            summary = engine._generate_3line_summary(title, desc, media="NEC")
            lines = summary.splitlines()
            # 1ポイント（タイトル）+ 案内文1行 = 2行（案内文の複数行埋めは廃止）
            self.assertEqual(len(lines), 2)
            self.assertEqual(summary.count("タップ"), 1)

    def test_llm_short_output_filled_from_description(self):
        """LLM出力が3行未満の場合、description由来のポイントで補完されるか検証"""
        engine = SuggestionEngine(start_worker=False)
        title = "量子ネットワーク実証実験に成功"
        desc = "東京と大阪間で量子もつれを安定生成した。誤り訂正技術を実装した。通信距離は500kmに到達した。"
        llm_response = MagicMock()
        llm_response.content = "・量子もつれの安定生成に成功\n・誤り訂正技術を実装"
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = llm_response
        mock_factory = MagicMock()
        mock_factory.create_model.return_value = mock_llm

        from llm_factory import LLMProvider
        mock_factory.current_provider = LLMProvider.OPENAI

        with patch("llm_factory.get_llm_factory", return_value=mock_factory):
            summary = engine._generate_3line_summary(title, desc, media="Science Daily")
            lines = summary.splitlines()
            self.assertEqual(len(lines), 3)
            self.assertNotIn("タップ", summary)
            # LLMの2行 + description由来ポイントの補完1行で3ポイント構成
            self.assertTrue(any(("500km" in ln) or ("安定生成した" in ln) for ln in lines))


if __name__ == "__main__":
    unittest.main()
