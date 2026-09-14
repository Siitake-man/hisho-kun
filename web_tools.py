"""
ネオ秘書くん - キー不要の自律Web検索・ニュース取得モジュール (web_tools.py)

Google News RSS, Jina Search, Jina Reader を統合した完全無料・ゼロ設定の外部情報収集ツール。
APIキーの登録や課金を一切行わずに、最新ニュースの取得・Web検索・WebページのMarkdown読込を実行します。
"""
import logging
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
import re
from typing import List, Dict, Any, Optional
try:
    from langchain_core.tools import tool
except (ImportError, ModuleNotFoundError):
    # LangChain 未導入環境向けフォールバックデコレータ
    def tool(func):
        return func

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def fetch_news_rss(query: str = "AI OR ネットワーク OR クラウド", limit: int = 5) -> List[Dict[str, Any]]:
    """
    Google News RSS から指定キーワードの最新ニュース記事一覧を取得します（APIキー不要）。

    Args:
        query: 検索キーワード（例: "AI OR クラウド"、"ネットワーク"）
        limit: 取得件数上限（デフォルト: 5）

    Returns:
        List[Dict[str, Any]]: 各記事の情報辞書リスト
            - id: 記事ID（ハッシュ値）
            - title: 記事タイトル（媒体名分離済み）
            - media: 配信メディア名
            - link: 記事URL
            - pub_date: 公開日時文字列
            - description: 概要・抜粋テキスト
    """
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    
    news_items: List[Dict[str, Any]] = []
    try:
        req = urllib.request.Request(
            url, 
            headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=8) as res:
            xml_data = res.read()
            root = ET.fromstring(xml_data)

            for item in root.findall("./channel/item")[:limit]:
                title_elem = item.find("title")
                raw_title = title_elem.text if title_elem is not None else "無題ニュース"
                
                link_elem = item.find("link")
                link = link_elem.text if link_elem is not None else ""
                
                pub_elem = item.find("pubDate")
                pub_date = pub_elem.text if pub_elem is not None else ""
                
                desc_elem = item.find("description")
                raw_desc = desc_elem.text if desc_elem is not None else ""
                # HTMLタグの除去
                clean_desc = re.sub(r"<[^>]+>", "", raw_desc).strip()

                # 媒体名（- 〇〇）の分離
                parts = raw_title.rsplit(" - ", 1)
                main_title = parts[0] if parts else raw_title
                media = parts[1] if len(parts) > 1 else "トピック"

                news_items.append({
                    "id": abs(hash(raw_title)) % 100000,
                    "title": main_title,
                    "media": media,
                    "link": link,
                    "pub_date": pub_date,
                    "description": clean_desc
                })
    except Exception as e:
        logger.warning(f"ニュースRSS取得エラー (query='{query}'): {e}")

    return news_items


def search_web_free(query: str, max_chars: int = 1500) -> str:
    """
    Jina Search を用いてWebを検索し、クリーンな要約テキストを取得します（APIキー不要）。

    Args:
        query: 検索クエリ
        max_chars: 取得文字数上限

    Returns:
        str: 検索結果のテキスト（Markdown形式）
    """
    encoded_query = urllib.parse.quote(query)
    url = f"https://s.jina.ai/{encoded_query}"
    
    try:
        req = urllib.request.Request(
            url, 
            headers={"User-Agent": USER_AGENT, "Accept": "text/plain"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            content = response.read().decode("utf-8", errors="replace")
            return content[:max_chars]
    except Exception as e:
        logger.warning(f"Web検索エラー (query='{query}'): {e}")
        return f"Web検索中にエラーが発生しました: {e}"


def read_webpage_clean(target_url: str, max_chars: int = 2000) -> str:
    """
    Jina Reader を用いて指定したWebページの本文を広告・ノイズなしのMarkdownで読み込みます（APIキー不要）。

    Args:
        target_url: 読み込むWebページのURL
        max_chars: 取得文字数上限

    Returns:
        str: ページの本文Markdownテキスト
    """
    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        target_url = "https://" + target_url

    jina_url = f"https://r.jina.ai/{target_url}"
    try:
        req = urllib.request.Request(
            jina_url, 
            headers={"User-Agent": USER_AGENT, "Accept": "text/markdown"}
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            content = response.read().decode("utf-8", errors="replace")
            return content[:max_chars]
    except Exception as e:
        logger.warning(f"Webページ読込エラー (url='{target_url}'): {e}")
        return f"Webページ読込中にエラーが発生しました: {e}"


# =============================================================================
# LangChain Tool 定義（LangGraph / agent.py 連携用）
# =============================================================================

@tool
def fetch_tech_news_tool(topic: str = "AI OR ネットワーク OR クラウド") -> str:
    """
    Google News RSS から指定したトピックの最新ニュース一覧を取得します（APIキー不要・完全無料）。
    
    Args:
        topic: 検索キーワード（例: "LangGraph", "ネットワーク設計", "Python 3.13"）
    """
    items = fetch_news_rss(query=topic, limit=5)
    if not items:
        return "指定されたトピックの最新ニュースが見つかりませんでした。"
    
    lines = []
    for item in items:
        lines.append(f"- 【{item['media']}】{item['title']}\n  リンク: {item['link']}")
    return "\n".join(lines)


@tool
def search_web_free_tool(query: str) -> str:
    """
    Webを検索して最新情報や技術仕様、ドキュメントのサマリを取得します（APIキー不要・完全無料）。
    
    Args:
        query: 検索したいキーワードや質問
    """
    return search_web_free(query=query)


@tool
def read_webpage_free_tool(url: str) -> str:
    """
    指定したWebページのURLを開き、本文を広告なしのクリーンなMarkdownで取得します（APIキー不要・完全無料）。
    
    Args:
        url: 読み込みたいWebページのURL
    """
    return read_webpage_clean(target_url=url)
