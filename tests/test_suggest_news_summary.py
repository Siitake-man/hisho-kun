"""
ネオ秘書くん - web_tools および suggest_engine ニュースサジェスト単体テスト
"""
import unittest
import json
from unittest.mock import patch, MagicMock

import web_tools
from suggest_engine import SuggestionEngine


class TestSuggestNewsSummary(unittest.TestCase):

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
                engine = SuggestionEngine()
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
        engine = SuggestionEngine()
        title = "新世代ネットワークルーターの性能測定結果"
        desc = "BGP経路の収束速度が従来の2倍に向上しました。メモリ消費量も半減しています。エンタープライズNW向けに提供が開始されます。"
        
        # LLMをモックで例外にし、ルールベースフォールバックを検証
        with patch("llm_factory.get_llm_factory", side_effect=Exception("LLM offline")):
            summary = engine._generate_3line_summary(title, desc, media="NW通信")
            lines = summary.splitlines()
            self.assertEqual(len(lines), 3)
            self.assertTrue(all(line.startswith("・") for line in lines))


if __name__ == "__main__":
    unittest.main()
