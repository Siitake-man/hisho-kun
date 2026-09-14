#!/usr/bin/env python3
"""
ネオ秘書くん - インテリジェント・サジェストエンジン (suggest_engine.py)

ボスの作業状況、直近の予定、高優先度TODO、知識の宝庫知見、プロアクティブ健康ケアから
「今、ボスが目を通すべきこと／対応が必要なこと」をスマートにサジェストします。
関心ニュースキーワードのカスタマイズと超軽量3行AIサマリ動的生成に対応。
各ソースの個別ON/OFF設定を管理・永続化します。
"""

import os
import json
import time
import datetime
import logging
import re
import threading
from typing import Callable, Dict, List, Any, Optional
from pathlib import Path

import web_tools
import database
from proactive_scheduler import get_proactive_scheduler

logger = logging.getLogger(__name__)

# サジェストのバックグラウンド再生成周期（秒）。
# /api/status ポーリング（1〜2秒毎）はキャッシュ参照のみになり、
# DBクエリ・LLM推論・ネットワークI/OがHTTPハンドラスレッド上で走らなくなる。
SUGGEST_REFRESH_INTERVAL_SEC = 30

import app_paths

CONFIG_PATH = app_paths.get_app_root() / "suggest_config.json"

DEFAULT_SUGGEST_CONFIG = {
    "sources": {
        "calendar": {
            "name": "📅 予定・会議リマインド",
            "enabled": True,
            "description": "直近の予定や次の会議の開始前リマインド"
        },
        "high_priority_tasks": {
            "name": "🔥 重要TODOタスク",
            "enabled": True,
            "description": "今日期限や高優先度の未完了タスク"
        },
        "proactive_care": {
            "name": "🍵 健康・集中見守り",
            "enabled": True,
            "description": "45分作業時の休憩提案や夕方のリフレッシュ"
        },
        "boss_insights": {
            "name": "🧠 開発知見・マインドセット",
            "enabled": True,
            "description": "知識の宝庫に蓄積されたボスのルールや天風哲学のTips"
        },
        "news_topics": {
            "name": "🌐 関心ニュース・AIトレンド",
            "enabled": True,
            "description": "登録キーワードや最新技術動向のトピック",
            "keywords": ["AI", "ネットワーク", "クラウド"]
        },
        "gmail_unread": {
            "name": "📧 Gmail 重要未読メール",
            "enabled": True,
            "description": "Google OAuth認証済みの場合、Gmailの重要な未読メールを通知"
        },
        "google_calendar": {
            "name": "📅 Googleカレンダー直前予定",
            "enabled": True,
            "description": "Google OAuth認証済みの場合、直近1時間以内の予定をリマインド"
        }
    }
}


def _normalize_for_compare(text: str) -> str:
    """重複判定用にテキストを正規化する。

    HTMLタグ・HTMLエンティティ・空白・省略記号・括弧・ハイフン等を除去し、
    小文字化した文字内容のみで比較できるようにする。

    Args:
        text: 正規化前のテキスト。

    Returns:
        str: 正規化済みテキスト（入力が空の場合は空文字）。
    """
    if not text:
        return ""
    t = re.sub(r"<[^>]+>", "", str(text))
    t = t.replace("&nbsp;", " ").replace("&quot;", "").replace("&amp;", "&").replace("&lt;", "").replace("&gt;", "")
    t = re.sub(r"[\s\.\．…・、。，,「」『』【】\-\u2014\u2015]+", "", t)
    return t.lower()


def _texts_near_duplicate(a: str, b: str, threshold: float = 0.6) -> bool:
    """正規化済み2テキストがほぼ同一内容かを判定する。

    片方包含の関係と文字集合のJaccard係数で判定する。
    Google News RSS の description がタイトルの反復になっているケースや、
    軽量LLMが同一内容を複数行に繰り返す劣化出力の検出に用いる。

    Args:
        a: 正規化済みテキスト1。
        b: 正規化済みテキスト2。
        threshold: 近似重複とみなすJaccard係数の閾値。

    Returns:
        bool: 近似重複とみなせる場合 True。
    """
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    set_a, set_b = set(a), set(b)
    union = set_a | set_b
    if not union:
        return False
    return (len(set_a & set_b) / len(union)) >= threshold


class SuggestionEngine:
    """サジェスト情報の集約と配信を行うエンジン"""

    def __init__(self, start_worker: bool = True):
        self.config = self._load_config()
        self._cache_suggestions: List[Dict[str, Any]] = []
        self._last_update_time: float = 0.0
        self._news_cache: List[Dict[str, Any]] = []
        self._last_news_fetch: float = 0.0
        self._summary_cache: Dict[str, str] = {}  # 記事URL/ID -> 3行サマリのキャッシュ

        # ── バックグラウンド再生成 (GIL分離の要・P2②でスケジューラ移管) ──
        # generate_suggestions() の重い実体（DBクエリ/LLM推論/RSS取得）は
        # ProactiveScheduler 共有デーモンスレッド上でのみ実行され、HTTPハンドラは
        # キャッシュを参照するだけになる。これにより /api/status ポーリングが
        # GUI の描画スレッドへ与える GIL 競合を解消する。
        # _last_refresh_at: 前回再生成時刻 (epoch秒) — interval 経過判定に使用。
        self._cache_lock = threading.Lock()
        self._force_refresh = threading.Event()
        self._refresh_plugin: Optional[Callable[[float], None]] = None
        self._last_refresh_at: float = 0.0

        self._start_worker = bool(start_worker)
        if self._start_worker:
            self._start_background_worker()

    def _load_config(self) -> Dict[str, Any]:
        """設定のロード"""
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    # 既存設定に keywords がない場合はデフォルト補完
                    sources = cfg.get("sources", {})
                    news_src = sources.get("news_topics", {})
                    if "keywords" not in news_src:
                        news_src["keywords"] = ["AI", "ネットワーク", "クラウド"]
                    return cfg
            except Exception as e:
                logger.error(f"サジェスト設定読み込み失敗: {e}")
        return DEFAULT_SUGGEST_CONFIG.copy()

    def save_config(self, config: Dict[str, Any]) -> None:
        """設定の保存"""
        self.config = config
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info("サジェスト設定を保存しました")
        except Exception as e:
            logger.error(f"サジェスト設定保存失敗: {e}")

    def is_source_enabled(self, source_key: str) -> bool:
        """指定ソースが有効か"""
        sources = self.config.get("sources", {})
        src = sources.get(source_key, {})
        return src.get("enabled", True)

    def toggle_source(self, source_key: str, enabled: bool) -> None:
        """ソースの有効/無効を切り替える

        切替後、バックグラウンドワーカーへ即時再生成を依頼する（非ブロッキング）。
        """
        if "sources" not in self.config:
            self.config["sources"] = {}
        if source_key in self.config["sources"]:
            self.config["sources"][source_key]["enabled"] = enabled
            self.save_config(self.config)
            self.request_refresh()

    def get_news_keywords(self) -> List[str]:
        """設定されている関心ニュースキーワード一覧を取得"""
        sources = self.config.get("sources", {})
        news_src = sources.get("news_topics", {})
        kw = news_src.get("keywords", ["AI", "ネットワーク", "クラウド"])
        if isinstance(kw, list):
            return kw
        elif isinstance(kw, str):
            return [k.strip() for k in re.split(r"[,、\s]+", kw) if k.strip()]
        return ["AI", "ネットワーク", "クラウド"]

    def set_news_keywords(self, keywords: Any) -> None:
        """関心ニュースキーワードを更新・永続化"""
        if "sources" not in self.config:
            self.config["sources"] = {}
        if "news_topics" not in self.config["sources"]:
            self.config["sources"]["news_topics"] = DEFAULT_SUGGEST_CONFIG["sources"]["news_topics"].copy()

        if isinstance(keywords, list):
            clean_kw = [str(k).strip() for k in keywords if str(k).strip()]
        elif isinstance(keywords, str):
            clean_kw = [k.strip() for k in re.split(r"[,、\s]+", keywords) if k.strip()]
        else:
            clean_kw = ["AI", "ネットワーク", "クラウド"]

        if not clean_kw:
            clean_kw = ["AI", "ネットワーク", "クラウド"]

        self.config["sources"]["news_topics"]["keywords"] = clean_kw
        self.save_config(self.config)
        # キーワード変更時はニュースキャッシュを破棄して次回即座に再取得
        self._last_news_fetch = 0.0
        # バックグラウンドワーカーに即時再生成を依頼（非ブロッキング）
        self.request_refresh()

    # =========================================================================
    # 🔄 バックグラウンドキャッシュワーカー (2026-08-30 短期改善 Step 2)
    # =========================================================================
    def _start_background_worker(self) -> None:
        """サジェスト再生成プラグインを共有スケジューラへ登録する（二重登録は無視）。

        専用ワーカースレッド (SuggestBgWorker) は廃止し、ProactiveScheduler の
        単一デーモンスレッド上で周期再生成を行う。重い生成処理 (DB/LLM/RSS) は
        従来どおり GUI / HTTP ハンドラスレッドから分離される (GIL 分離原則)。
        """
        if self._refresh_plugin is not None:
            logger.debug("サジェスト再生成プラグインは既に登録済みのため登録をスキップしました")
            return
        scheduler = get_proactive_scheduler()
        self._refresh_plugin = self._on_scheduler_tick
        scheduler.register(self._refresh_plugin, name="SuggestRefresh")
        scheduler.start()
        logger.info("サジェスト再生成プラグインをスケジューラへ登録しました (周期 %s秒)", SUGGEST_REFRESH_INTERVAL_SEC)

    def stop_background_worker(self) -> None:
        """サジェスト再生成プラグインを共有スケジューラから安全に解除する（shutdown_workerのエイリアス）。"""
        self.shutdown_worker()

    def _on_scheduler_tick(self, now: float) -> None:
        """スケジューラの tick から呼ばれる再生成判定。

        request_refresh() による強制更新フラグが立っていれば即座に、
        なければ前回再生成から SUGGEST_REFRESH_INTERVAL_SEC 経過した場合に
        1回だけ再生成する (起動直後は _last_refresh_at=0.0 のため初回 tick で
        初期キャッシュを生成する)。

        Args:
            now: 現在時刻 (Unix 秒)。
        """
        forced = self._force_refresh.is_set()
        if forced:
            self._force_refresh.clear()
        if not forced and (now - self._last_refresh_at) < SUGGEST_REFRESH_INTERVAL_SEC:
            return
        self._refresh_cache_once()
        self._last_refresh_at = now

    def _refresh_cache_once(self) -> None:
        """サジェストを1回生成してキャッシュへ格納する（ワーカースレッド専用）。

        例外が発生してもワーカーループを停止させない（ログ出力して継続）。
        """
        try:
            fresh = self.generate_suggestions()
            with self._cache_lock:
                self._cache_suggestions = fresh
                self._last_update_time = time.time()
        except Exception as e:
            logger.error(f"サジェストのバックグラウンド生成に失敗しました: {e}")

    def get_cached_suggestions(self) -> List[Dict[str, Any]]:
        """キャッシュ済みサジェストを即時返す（ロック取得のみ・1ms未満）。

        HTTPハンドラ（/api/status）はこのメソッドのみを呼ぶこと。
        ``generate_suggestions()`` を直接呼ぶと重い処理がハンドラスレッド上で
        実行され、GIL 競合による GUI カクつきの原因になる。

        Returns:
            List[Dict[str, Any]]: 直近のワーカー生成結果（初回生成前は空リスト）。
        """
        with self._cache_lock:
            return list(self._cache_suggestions)

    def request_refresh(self) -> None:
        """次のワーカー周期を待たずに即時再生成を依頼する（非ブロッキング）。

        設定変更（キーワード更新・ソースON/OFF等）後に呼ぶことで、
        呼び出しスレッドを塞ぐことなくキャッシュを最新化できる。
        """
        self._force_refresh.set()

    def shutdown_worker(self) -> None:
        """サジェスト再生成プラグインをスケジューラから解除する（アプリ終了時用・冪等）。"""
        plugin = self._refresh_plugin
        if plugin is not None:
            try:
                get_proactive_scheduler().unregister(plugin)
            except Exception as e:
                logger.debug(f"サジェストプラグイン解除エラー: {e}")
            finally:
                self._refresh_plugin = None
        logger.info("サジェスト再生成プラグインを解除しました (解除実施: %s)", plugin is not None)

    def generate_suggestions(self) -> List[Dict[str, Any]]:
        """現在の各データソースからサジェストカード一覧を動的生成する。

        Attention:
            このメソッドは重い（DB/LLM/ネットワーク）。HTTPハンドラやGUIから
            直接呼ばず、バックグラウンドワーカー経由の
            :meth:`get_cached_suggestions` を使用すること。
        """
        suggestions: List[Dict[str, Any]] = []

        now_dt = datetime.datetime.now()
        now_ts = int(time.time() * 1000)

        # 1. 予定リマインド (Calendar)
        if self.is_source_enabled("calendar"):
            try:
                events = database.get_upcoming_events(days=1)
                today_date = now_dt.date()
                tomorrow_date = today_date + datetime.timedelta(days=1)

                for ev in events[:2]:
                    st = datetime.datetime.fromtimestamp(ev.start_time / 1000.0)
                    time_str = st.strftime("%H:%M")
                    diff_mins = int((ev.start_time - now_ts) / (1000 * 60))
                    ev_date = st.date()
                    
                    if 0 <= diff_mins <= 60:
                        urgency = f"【あと {diff_mins}分】"
                    elif diff_mins < 0:
                        urgency = "【進行中】"
                    elif ev_date == today_date:
                        urgency = f"【本日 {time_str}〜】"
                    elif ev_date == tomorrow_date:
                        urgency = f"【明日 {time_str}〜】"
                    else:
                        urgency = f"【{st.month}/{st.day} {time_str}〜】"

                    suggestions.append({
                        "id": f"event_{ev.id}",
                        "source": "calendar",
                        "icon": "📅",
                        "title": f"{urgency} {ev.title}",
                        "description": ev.description or "予定の詳細はありません",
                        "tag": "カレンダー"
                    })
            except Exception as e:
                logger.error(f"予定サジェスト生成エラー: {e}", exc_info=True)

        # 2. 重要TODO (High Priority Tasks)
        if self.is_source_enabled("high_priority_tasks"):
            try:
                tasks = database.get_tasks(status="todo", limit=10)
                high_tasks = [t for t in tasks if t.priority == 3 or str(t.priority).lower() == "high"] or tasks[:2]
                for t in high_tasks[:2]:
                    p_badge = "🔥 高優先度" if (t.priority == 3 or str(t.priority).lower() == "high") else "⚡ 通常タスク"
                    suggestions.append({
                        "id": f"task_{t.id}",
                        "source": "tasks",
                        "icon": "📋",
                        "title": f"{p_badge}: {t.title}",
                        "description": t.description or "ワンタップで完了できます",
                        "tag": "TODO手帳"
                    })
            except Exception as e:
                logger.error(f"TODOサジェスト生成エラー: {e}")

        # 3. ボスの知見・マインドセット (知識の宝庫 Insights)
        if self.is_source_enabled("boss_insights"):
            try:
                insights = database.get_user_insights(min_importance=2, limit=5)
                if insights:
                    import random
                    ins = random.choice(insights)
                    suggestions.append({
                        "id": f"insight_{ins.id}",
                        "source": "insights",
                        "icon": "🧠",
                        "title": f"【ボスの知見・{ins.category}】",
                        "description": ins.content,
                        "tag": "知識の宝庫"
                    })
            except Exception as e:
                logger.error(f"知見サジェスト生成エラー: {e}")

        # 4. 健康・見守り (Care)
        if self.is_source_enabled("proactive_care"):
            hour = now_dt.hour
            if hour >= 22 or hour < 5:
                care_msg = "ボス、遅くまでお疲れさまです。生命の最適利用のため、十分な睡眠も大切ですよ🌙"
            elif 11 <= hour <= 13:
                care_msg = "もうすぐお昼時ですね！美味しいものを食べてエネルギーを補給してくださいね🍱"
            elif 17 <= hour <= 19:
                care_msg = "夕方になりました。肩を回してストレッチしませんか？🍵"
            else:
                care_msg = "集中が続いています。深呼吸して水分補給をしてくださいね✨"

            suggestions.append({
                "id": "care_current",
                "source": "care",
                "icon": "🍵",
                "title": "【秘書くんの気配り】",
                "description": care_msg,
                "tag": "健康見守り"
            })

        # 4.5 Gmail 重要未読メール (Google Workspace / OAuth認証済み時のみ)
        if self.is_source_enabled("gmail_unread"):
            try:
                from google_workspace_tools import get_google_auth_status, search_gmail_messages_tool

                auth_status = get_google_auth_status()
                if auth_status.get("authenticated"):
                    if hasattr(search_gmail_messages_tool, 'invoke'):
                        gmail_result = search_gmail_messages_tool.invoke(
                            {"query": "is:unread is:important", "max_results": 2}
                        )
                    else:
                        gmail_result = search_gmail_messages_tool(
                            query="is:unread is:important", max_results=2
                        )
                    for i, line in enumerate(
                        [ln for ln in str(gmail_result).splitlines() if ln.strip()][:2]
                    ):
                        suggestions.append({
                            "id": f"gmail_unread_{i}",
                            "source": "gmail",
                            "icon": "📧",
                            "title": "重要な未読メールを受信！",
                            "description": line.strip(),
                            "tag": "Gmail"
                        })
            except Exception as e:
                logger.debug(f"Gmailサジェスト生成スキップ: {e}")

        # 4.6 Googleカレンダー直前予定 (Google Workspace / OAuth認証済み時のみ)
        if self.is_source_enabled("google_calendar"):
            try:
                from google_workspace_tools import get_google_auth_status, get_google_calendar_events_tool

                auth_status = get_google_auth_status()
                if auth_status.get("authenticated"):
                    if hasattr(get_google_calendar_events_tool, 'invoke'):
                        cal_result = get_google_calendar_events_tool.invoke({"days": 1})
                    else:
                        cal_result = get_google_calendar_events_tool(days=1)
                    first_lines = [ln for ln in str(cal_result).splitlines() if ln.strip()]
                    if first_lines:
                        suggestions.append({
                            "id": "google_calendar_next",
                            "source": "calendar",
                            "icon": "📅",
                            "title": "Googleカレンダーの直近予定",
                            "description": "\n".join(first_lines[:3]),
                            "tag": "Google Calendar"
                        })
            except Exception as e:
                logger.debug(f"Googleカレンダーサジェスト生成スキップ: {e}")

        # 5. パーソナライズ関心ニュース ＆ 3行AIサマリ (News Topics)
        if self.is_source_enabled("news_topics"):
            try:
                news_items = self._get_cached_ai_news()
                for n in news_items[:3]:
                    suggestions.append({
                        "id": f"news_{n['id']}",
                        "source": "news",
                        "icon": "🌐",
                        "title": f"【{n['media']}】{n['title']}",
                        "description": n["snippet"],
                        "tag": "技術トレンド",
                        "link": n.get("link", "")
                    })
            except Exception as e:
                logger.error(f"ニュースサジェスト生成エラー: {e}")

        # デフォルトフォールバック
        if not suggestions:
            suggestions.append({
                "id": "default_msg",
                "source": "general",
                "icon": "✨",
                "title": "ボス、今日も素晴らしい一日にしましょう！",
                "description": "下のメニューから手帳や付箋を開けます。",
                "tag": "ネオ秘書くん"
            })

        self._cache_suggestions = suggestions
        self._last_update_time = time.time()
        return suggestions

    def _get_cached_ai_news(self) -> List[Dict[str, Any]]:
        """設定された関心キーワードでRSSを取得し、3行AIサマリを付与してキャッシュ (30分更新)"""
        now = time.time()
        # 古いフォーマット（... が含まれるサマリ）がキャッシュされている場合は即座に破棄
        has_legacy_summary = False
        if hasattr(self, '_news_cache') and self._news_cache:
            for item in self._news_cache:
                if "..." in item.get("snippet", "") or "…" in item.get("snippet", ""):
                    has_legacy_summary = True
                    break

        if not has_legacy_summary and hasattr(self, '_news_cache') and self._news_cache and (now - getattr(self, '_last_news_fetch', 0)) < 1800:
            return self._news_cache

        # キャッシュパージ
        if has_legacy_summary:
            self._summary_cache.clear()
            self._news_cache.clear()

        keywords = self.get_news_keywords()
        query = " OR ".join(keywords) if keywords else "AI OR ネットワーク OR クラウド"
        
        raw_news = web_tools.fetch_news_rss(query=query, limit=5)
        news_list: List[Dict[str, Any]] = []

        if not raw_news:
            # フォールバック
            news_list = [
                {
                    "id": 1, 
                    "title": "最新のLLMエージェント技術が急速進化中", 
                    "media": "AIトレンド",
                    "snippet": "・自律コーディングと並列協調が注目\n・軽量モデルの内包化が進む\n・常駐秘書エージェントの実用化拡大",
                    "link": ""
                },
                {
                    "id": 2, 
                    "title": "LangGraphによるグラフ型AI設計が普及拡大", 
                    "media": "Python開発",
                    "snippet": "・ステートマシン制御による堅牢ループ\n・ToolNodeとHuman-in-the-loop統合\n・非同期UI共存のベストプラクティス",
                    "link": ""
                }
            ]
        else:
            # タイトル正規化による重複排除（同一記事が複数行として並ぶ障害の防止）
            seen_titles: set = set()
            for item in raw_news:
                title_norm = _normalize_for_compare(item.get("title", ""))
                if title_norm and title_norm in seen_titles:
                    continue
                if title_norm:
                    seen_titles.add(title_norm)
                cache_key = item["link"] or str(item["id"])
                # 古いキャッシュに ... があれば再生成
                if cache_key in self._summary_cache and "..." not in self._summary_cache[cache_key]:
                    summary = self._summary_cache[cache_key]
                else:
                    summary = self._generate_3line_summary(
                        title=item["title"],
                        description=item.get("description", ""),
                        media=item.get("media", "")
                    )
                    self._summary_cache[cache_key] = summary

                news_list.append({
                    "id": item["id"],
                    "title": item["title"],
                    "media": item["media"],
                    "snippet": summary,
                    "link": item["link"]
                })
                # サマリ生成はサジェスト表示枠（最大3件）分のみで十分
                # （クラウドLLM利用時の応答レイテンシ抑制）
                if len(news_list) >= 3:
                    break

        self._news_cache = news_list
        self._last_news_fetch = now
        return news_list

    @staticmethod
    def _extract_content_points(description: str, clean_title: str, media: str = "", max_points: int = 3) -> List[str]:
        """RSS概要文を文単位に分解し、ニュース本文由来のポイントを抽出する。

        「タップで詳細」等の案内文ではなく、読者に伝わる実内容のポイントのみを
        返す。タイトルの反復・媒体名のみ・日付のみ等のノイズ行は除外する。

        Args:
            description: RSS item の description（HTML含む可能性あり）。
            clean_title: HTMLタグ除去済みの記事タイトル。
            media: メディア名（サフィックス除去に使用）。
            max_points: 抽出する最大ポイント数。

        Returns:
            List[str]: 本文由来のポイント文字列（各行80字以内にトリム済み）。
        """
        if not description:
            return []
        clean_desc = re.sub(r"<[^>]+>", "", description).strip()
        clean_desc = (clean_desc
                      .replace("&nbsp;", " ")
                      .replace("&quot;", '"')
                      .replace("&amp;", '&')
                      .replace("&lt;", '<')
                      .replace("&gt;", '>'))
        # 末尾の媒体名サフィックス（" - Yahoo!ニュース" 等）を分離
        if media and clean_desc.endswith(f"- {media}"):
            clean_desc = clean_desc[: -len(f"- {media}")].strip()
        # 末尾・途中の連続ドット・三点リーダーを除去
        clean_desc = re.sub(r"[\.\．…\s]+$", "", clean_desc)

        title_norm = _normalize_for_compare(clean_title)
        points: List[str] = []
        # 文単位に分解（。！？!?\n および全角パイプを区切りに使用）
        for raw in re.split(r"[。！？!?\n｜]+", clean_desc):
            part = raw.strip()
            # 末尾の連続ドット・媒体名のみの断片を清掃
            part = re.sub(r"[\.\．…\s]+$", "", part).strip()
            if media:
                part = re.sub(rf"[-−‐ー]\s*{re.escape(media)}\s*$", "", part).strip()
            if len(part) < 6:
                continue
            # 「（2026年8月27日）」等の括弧書きのみの行はポイントにならない
            if re.fullmatch(r"[（(][^）)]*[)）]", part):
                continue
            # 「プレスリリース」「速報」等のラベル語のみの行もポイントにならない
            if re.fullmatch(r"(プレスリリース|ニュース|速報|レポート|コラム|解説)", part):
                continue
            norm = _normalize_for_compare(part)
            if not norm or _texts_near_duplicate(norm, title_norm):
                continue
            # 抽出済みポイントとの重複も排除
            if any(_texts_near_duplicate(norm, _normalize_for_compare(p)) for p in points):
                continue
            if len(part) > 80:
                part = part[:80].rstrip() + "…"
            points.append(part)
            if len(points) >= max_points:
                break
        return points

    def _generate_3line_summary(self, title: str, description: str, media: str = "") -> str:
        """
        ニュースタイトルと概要から、LLMまたはルールベースで『3ポイントサマリ』を動的生成。
        Google News RSS 特有の末尾の ... や HTMLゴミを徹底クリーンアップし、
        「ニュースの実内容3ポイント」を優先して構築します。
        案内文（タップで詳細 等）は本文ポイントが不足する場合の最後の1行に限り使用し、
        複数行を案内文で埋めることはしません。
        """
        clean_title = re.sub(r"<[^>]+>", "", title).strip()
        clean_title = clean_title.replace("&quot;", '"').replace("&amp;", '&').replace("&lt;", '<').replace("&gt;", '>')

        # 0. 本文（description）由来のポイント抽出 — LLM不発時の核となる3ポイント源
        desc_points = self._extract_content_points(description, clean_title, media=media, max_points=3)

        # 1. ルールベースによるフォールバックサマリの構築
        #    ポイント1 = タイトル、ポイント2-3 = 本文抽出分（重複は除外済み）
        fallback_lines = [f"・{clean_title}"] + [f"・{p}" for p in desc_points[:2]]
        # 3行に満たない場合は案内文で補完するのは「1行」のみ（複数行の案内文埋めはしない）
        if len(fallback_lines) < 3:
            fallback_lines.append(f"・{media or '公式'}の記事はタップで詳細を閲覧できます")

        fallback_summary = "\n".join(fallback_lines[:3])

        # 2. 超軽量AI（LLMFactory）による高精度サマリ生成の試行
        try:
            from llm_factory import get_llm_factory, LLMProvider
            factory = get_llm_factory()
            # 旧実装は存在しない factory.get_llm() を呼び出しており LLM 経路が恒久的に
            # 不発していた。また軽量ローカルモデル（GGUF）はトークン反復により同一内容を
            # 複数行に繰り返す劣化出力を起こすため、クラウドプロバイダ時のみ
            # create_model() で生成した LLM による要約を試行する（失敗時はルールベース）。
            llm = None
            if factory.current_provider != LLMProvider.LOCAL_GGUF:
                llm = factory.create_model()
            if llm is not None:
                # テスト実行中に未モックのLLMによるネットワーク通信・タイムアウトハングを防止
                if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("TESTING"):
                    from unittest.mock import Mock, MagicMock
                    if not isinstance(llm, (Mock, MagicMock)) and not isinstance(factory, (Mock, MagicMock)):
                        logger.debug("テスト実行中のため外部LLM通信をスキップしルールベースサマリを採用")
                        return fallback_summary

                prompt = (
                    "以下のニュース記事の要点を、忙しいエンジニアがひと目で把握できるように、"
                    "「・」で始まる簡潔な3つのポイント（合計3行のみ）で要約してください。\n"
                    f"【タイトル】: {clean_title}\n"
                    f"【概要】: {description[:400]}\n"
                    "出力は3行の箇条書きテキストのみにしてください。同じ内容を繰り返さず、"
                    "「タップで詳細」等の案内文は書かないでください。"
                )
                response = llm.invoke(prompt)
                res_text = response.content if hasattr(response, "content") else str(response)

                # 3行箇条書きの抽出・整形
                clean_lines = [
                    ln.strip() if ln.strip().startswith("・") or ln.strip().startswith("- ") else f"・{ln.strip()}"
                    for ln in res_text.splitlines() if ln.strip()
                ]
                clean_lines = [re.sub(r"^[-*]\s*", "・", ln) for ln in clean_lines]
                # 同一内容の反復に崩壊した出力は破棄し、ルールベースへフォールバックする
                if clean_lines and self._summary_lines_are_degenerate(clean_lines, clean_title):
                    logger.debug("AI 3行サマリが反復・劣化したためルールベースへフォールバック")
                    clean_lines = []
                if clean_lines:
                    # 3行未満の場合は本文抽出ポイントで補完する（案内文の複数行埋めはしない）
                    for p in desc_points:
                        if len(clean_lines) >= 3:
                            break
                        pn = _normalize_for_compare(p)
                        if any(_texts_near_duplicate(pn, _normalize_for_compare(ln)) for ln in clean_lines):
                            continue
                        clean_lines.append(f"・{p}")
                    return "\n".join(clean_lines[:3])
        except Exception as e:
            logger.debug(f"AI 3行サマリ生成スキップ (ルールベース適用): {e}")

        return fallback_summary

    @staticmethod
    def _summary_lines_are_degenerate(lines: List[str], title: str) -> bool:
        """3行サマリが「同一内容の反復」に崩壊していないかを判定する。

        Args:
            lines: LLM出力から抽出した箇条書き行。
            title: 元記事のタイトル。

        Returns:
            bool: 崩壊している（ルールベースへフォールバックすべき）場合 True。
        """
        norm_lines = [ln for ln in (_normalize_for_compare(ln) for ln in lines) if ln]
        if len(norm_lines) < 2:
            return True
        # 近似重複行をグルーピングして実質的な行数を数える
        distinct: List[str] = []
        for ln in norm_lines:
            if not any(_texts_near_duplicate(ln, d) for d in distinct):
                distinct.append(ln)
        if len(distinct) < 2:
            return True
        # タイトル行を除いた残りがすべてタイトルの近似反復なら崩壊扱い
        title_norm = _normalize_for_compare(title)
        non_title = [ln for ln in distinct if not _texts_near_duplicate(ln, title_norm)]
        return len(non_title) == 0


# シングルトンインスタンス
_engine_instance: Optional[SuggestionEngine] = None

def get_suggestion_engine() -> SuggestionEngine:
    """シングルトンインスタンスの取得"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = SuggestionEngine()
    return _engine_instance


# 互換用エイリアス
SuggestEngine = SuggestionEngine
