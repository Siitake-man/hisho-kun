"""
ネオ秘書くん - メイン実行モジュール (main.py)

GUI(gui.py) と エージェント(agent.py) を「asyncio」を使い共存させます。
これにより、AIが思考中であっても画面（UI）が固まることなく、
スムーズなユーザー体験(UX)を実現します。
"""

import asyncio
import logging
import os
import subprocess
import sys
import threading
import tkinter as tk
from typing import Dict, Any, Optional


def _early_cli_dispatch() -> None:
    """GUI起動前に CLI サブコマンド (--mcp-serve / --setup-model) を処理する。

    PyInstaller の単一 exe が「GUIアプリ / MCPサーバー / モデルDLツール」の
    3役を担うためのエントリポイント。重い GUI/LangGraph の import より前に
    処理することで、MCP クライアントからの起動を高速化する。

    Note:
        いずれかのサブコマンドが処理された場合は sys.exit() で終了し、
        本関数は呼び出し元に戻らない。GUI 起動時は何もせず即 return する。
    """
    if "--mcp-serve" not in sys.argv and "--setup-model" not in sys.argv:
        return

    import io
    import app_paths

    # MCPサーバー / モデルDLモードでは DB や .env をアプリデータルートに解決するため CWD を固定
    os.chdir(app_paths.get_app_root())
    app_paths.ensure_env_file()

    # windowed ビルドでは標準入出力が None の場合がある
    # (--mcp-serve 時は MCP クライアントが実パイプを接続するため通常は None でない)
    if sys.stdout is None:
        sys.stdout = io.StringIO()
    if sys.stderr is None:
        sys.stderr = io.StringIO()

    if "--mcp-serve" in sys.argv:
        import hisho_mcp_server
        hisho_mcp_server.main()
        sys.exit(0)

    # --setup-model [350m|1.2b] → setup_local_model.py の --model へ翻訳 (省略時は推奨の 350m)
    idx = sys.argv.index("--setup-model")
    model_key = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "350m"
    sys.argv = [sys.argv[0], "--model", model_key]

    from tools.setup_local_model import main as setup_model_main
    exit_code = setup_model_main()

    # windowed exe では進捗が見えないため、結果をメッセージボックスで通知する
    if isinstance(sys.stdout, io.StringIO):
        import ctypes
        if exit_code == 0:
            text = (
                "ローカルAIモデルのセットアップが完了しました。\n"
                f"モデル: {model_key}\n\n"
                "ネオ秘書くんを再起動するとオフラインAI (local_gguf) が有効になります。"
            )
        else:
            text = (
                "モデルのセットアップに失敗しました。\n"
                "ネットワーク接続を確認して再度お試しください。"
            )
        ctypes.windll.user32.MessageBoxW(
            0, text, "ネオ秘書くん モデルセットアップ", 0x40 if exit_code == 0 else 0x10
        )
    sys.exit(exit_code)


_early_cli_dispatch()

from langchain_core.messages import HumanMessage, AIMessage

from gui import NeoSecretaryGUI
from agent import build_agent_graph
from easter_egg_engine import observe_message

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _auto_tailscale_serve() -> None:
    """Tailscale がインストールされていれば、起動時に `tailscale serve 8765` を自動実行する。

    ユーザーが手動でコマンドを叩く手間を省くヘルパー。
    エラーは無視（入っていなければ単に何もしない）。
    """
    try:
        result = subprocess.run(
            ["tailscale", "serve", "8765"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if result.returncode == 0:
            logger.info("🌐 Tailscale serve を自動起動しました (https://node.tail08a991.ts.net/)")
        else:
            if "already" not in result.stderr.lower():
                logger.debug(f"Tailscale serve 自動起動スキップ: {result.stderr.strip()}")
    except FileNotFoundError:
        logger.debug("Tailscale 未インストール — serve 自動起動をスキップ")
    except Exception as e:
        logger.debug(f"Tailscale serve 自動起動に失敗: {e}")


class NeoSecretaryApp:
    _instance = None

    @staticmethod
    def get_instance():
        """NeoSecretaryApp のシングルトンインスタンスを取得する。"""
        return NeoSecretaryApp._instance

    def __init__(self):
        NeoSecretaryApp._instance = self
        # 0. 自動起動ヘルパー（Tailscale serve / DBバックアップ）
        _auto_tailscale_serve()
        # 0.1. データベース初期化 ＆ 起動時自動オンラインバックアップ
        import database
        database.init_db()
        database.auto_backup()
        # 0.2. 地域設定の読み込み
        import weather_tools
        weather_tools.load_location_from_env()

        # 1. UIの初期化
        logger.info("UIを初期化します...")
        self.gui = NeoSecretaryGUI()
        
        # 2. エージェント(LangGraph)の初期化
        logger.info("エージェントを初期化します...")
        self.agent = build_agent_graph()
        
        # セッション(スレッド)IDの固定。本来はユーザーや日付で切り替えますが、MVPでは固定します。
        self.thread_id = "default_user_session"
        self.config = {"configurable": {"thread_id": self.thread_id}}

        # 3. 自律プロアクティブ見守りエンジンの初期化
        from proactive_engine import get_care_engine
        self.care_engine = get_care_engine(notify_callback=self._on_proactive_care)

        # 4. スマホ専用ペット端末 (Desk Pet) ローカル同期サーバーの起動
        from local_sync_server import get_sync_server
        self.sync_server = get_sync_server(gui=self.gui)
        self.sync_server.start(gui=self.gui)

        # 5. UIのイベント紐付け
        # ユーザーが入力欄で「Enterキー」を押したときの処理を登録
        self.gui.input_entry.bind("<Return>", self._on_submit)
        
        # 6. バックグラウンドでの最新LLMモデル動的自動同期（常に最新リストを維持）
        # 短期改善 Step 3: 起動直後のGUI描画・サーバー起動と同期処理がGILを奪い合わないよう
        # 15秒遅延させてからバックグラウンド同期を開始する
        from llm_factory import get_llm_factory

        def _delayed_llm_sync() -> None:
            threading.Event().wait(15.0)
            try:
                get_llm_factory().sync_all_discovered_models(background=True)
            except Exception as e:
                logger.warning(f"起動時LLMモデル同期に失敗しました: {e}")

        threading.Thread(target=_delayed_llm_sync, name="DelayedLLMSync", daemon=True).start()
        
        # 7. フルハイブリッドAgentログ監視 ＆ タスクナレーションエンジンの開始
        from agent_watcher import get_agent_watcher
        from task_narrator import get_task_narrator
        
        self.narrator = get_task_narrator()
        self.agent_watcher = get_agent_watcher(
            on_status_change=self._on_agent_status_change,
            on_task_completed=self._on_agent_task_completed,
            on_approval_needed=self._on_agent_approval_needed
        )
        self.agent_watcher.start()

        # 7.5. Google カレンダー 秘密iCal URL 定期同期（30分間隔・バックグラウンドスレッド）
        import threading as _threading
        import ics_tools as _ics_tools

        def _ical_sync_loop():
            """30分ごとに秘密 iCal URL からカレンダーを同期するデーモンループ。"""
            import time as _time
            while True:
                try:
                    count, msg = _ics_tools.sync_all_calendar_sources()
                    if count > 0:
                        logger.info(f"📅 Googleカレンダー定期同期: {msg}")
                        # 手帳ウィンドウが開かれている場合はUIスレッド経由で再描画する
                        self.gui.post_action(self.gui.refresh_calendar_if_open)
                except Exception as e:
                    logger.warning(f"Googleカレンダー定期同期エラー: {e}")
                _time.sleep(1800)

        _threading.Thread(target=_ical_sync_loop, daemon=True, name="IcalSyncLoop").start()

        # 7.6. アップデート確認 (GitHub Releases・バックグラウンドスレッド／Level 1: 通知のみ)
        from update_checker import start_update_checker
        start_update_checker(gui=self.gui)

        # 7.7. 時刻ベースのリマインダーエンジン (roadmap 3.1: 「10分前」通知)
        # タスク期限・予定開始の接近を30秒周期で監視し、PC吹き出し＋スマホPWAへ通知する
        from reminder_engine import get_reminder_engine
        get_reminder_engine(on_reminder=self._on_reminder).start()

        # 初期メッセージ ＆ 日次ブリーフィング（起動時に今日の予定・タスクを自動報告）
        self._generate_daily_briefing()
        
        # 起動時に一度だけDBから付箋を読み込んで画面に表示する
        self.gui.refresh_sticky_notes()

    def _on_agent_status_change(self, agent_name: str, state: str, details: Dict[str, Any]):
        """外部Agentの状態変化ハンドラ

        ※ 本メソッドは agent_watcher のバックグラウンドスレッド上で実行されるため、
        Tkinterへの直接操作は禁止。必ず post_action 経由でメインスレッドへディスパッチする。
        """
        logger.info(f"Agent状態変化: {agent_name} -> {state}")
        self.gui.post_action(self.gui.set_pet_state, state, duration_ms=6000)

    def _on_agent_task_completed(self, agent_name: str, summary: str, log_snippet: str):
        """外部Agentのタスク完了ハンドラ（タスクナレーション生成＆音声発話＆親愛度XP加算）

        ※ watcherスレッドで実行されるため、GUI操作はすべて post_action 経由。
        """
        logger.info(f"Agent作業完了検知: {agent_name}, {summary}")
        self.gui.post_action(self.gui.set_pet_state, "cheer", duration_ms=8000)

        speech = self.narrator.narrate_completion(agent_name, summary, log_snippet)
        if speech:
            self.gui.post_action(self.gui.update_message, speech)
            # 音声合成で声掛け（音声ライブラリはスレッド安全なため直接呼び出し可）
            self.narrator.speak_text(speech)

        # 親愛度XP加算 (+20 XP)（character_managerはDB操作のみでスレッド安全）
        from character_manager import get_character_manager
        char_mgr = get_character_manager()
        _, did_lvl_up = char_mgr.add_bond_xp(20)
        if did_lvl_up:
            bond = char_mgr.get_bond_info()
            self.gui.post_action(
                self.gui.update_message,
                f"🎊 【キズナレベルアップ！ Lv.{bond['level']}】\n称号: 『{bond['title']}』\n{bond['desc']}✨"
            )

    def _on_agent_approval_needed(self, agent_name: str, command: str, summary: str):
        """外部Agentの承認待ち検知ハンドラ

        ※ watcherスレッドで実行されるため、GUI操作はすべて post_action 経由。
        """
        logger.info(f"Agent承認待ち検知: {agent_name}, {command}")
        self.gui.post_action(self.gui.set_pet_state, "alarm_ask")
        self.gui.post_action(
            self.gui.update_message,
            f"⚠️ 【{agent_name} 承認要請】\n{summary}\n『{command[:40]}』"
        )

    def _generate_daily_briefing(self) -> None:
        """起動時に今日の予定と未完了タスクを自動取得し、ブリーフィングメッセージを生成・表示する。"""
        import datetime as _dt
        import database

        try:
            now = _dt.datetime.now()
            hour = now.hour

            # 時間帯に応じた挨拶
            if hour < 5:
                greeting = "深夜までお疲れ様です🌙"
            elif hour < 11:
                greeting = "おはようございます！☀️"
            elif hour < 15:
                greeting = "こんにちは！今日も頑張りましょう！💪"
            elif hour < 18:
                greeting = "お疲れ様です！午後もラストスパートです🔥"
            elif hour < 22:
                greeting = "今晩もお疲れ様です🌆"
            else:
                greeting = "遅くまでお疲れ様です🌙"

            lines: list[str] = [greeting, ""]

            # 今日の予定
            try:
                events = database.get_upcoming_events(days=1)
                today_events = []
                for ev in events:
                    st = _dt.datetime.fromtimestamp(ev.start_time / 1000.0)
                    if st.date() == now.date():
                        time_str = st.strftime("%H:%M")
                        today_events.append(f"  📅 {time_str}〜 {ev.title}")

                if today_events:
                    lines.append("【本日の予定】")
                    lines.extend(today_events[:5])
                    lines.append("")
                else:
                    lines.append("【本日の予定】予定は登録されていません。")
                    lines.append("")
            except Exception as e:
                logger.debug(f"ブリーフィング予定取得スキップ: {e}")

            # 未完了タスク
            try:
                tasks = database.get_tasks(status="todo", limit=5)
                if tasks:
                    lines.append("【未完了タスク】")
                    for t in tasks[:3]:
                        priority_mark = "🔥" if (t.priority == 3 or str(t.priority).lower() == "high") else "⚡"
                        lines.append(f"  {priority_mark} {t.title}")
                    lines.append("")
                else:
                    lines.append("【未完了タスク】クリアです！素晴らしい✨")
                    lines.append("")
            except Exception as e:
                logger.debug(f"ブリーフィングタスク取得スキップ: {e}")

            lines.append("（入力してEnterを押してください）")

            briefing = "\n".join(lines)
            self.gui.update_message(briefing)
            logger.info("日次ブリーフィングを生成しました")
        except Exception as e:
            logger.error(f"日次ブリーフィング生成エラー: {e}")
            self.gui.update_message("おはようございます！\n本日のご予定はいかがなさいますか？\n（入力してEnterを押してください）")

    def _on_proactive_care(self, message: str, pet_state: str = "happy"):
        """プロアクティブ見守りエンジンからの自律通知ハンドラ

        ※ care_engine のタイマースレッドから呼ばれる可能性があるため、
        GUI操作は必ず post_action 経由でメインスレッドへディスパッチする。
        """
        logger.info("プロアクティブ声掛けをUIに反映します")
        self.gui.post_action(self.gui.update_message, message)
        self.gui.post_action(self.gui.set_pet_state, pet_state, duration_ms=5000)

    def _on_reminder(self, message: str) -> None:
        """リマインダーエンジンからの期限接近通知ハンドラ

        ※ reminder_engine のワーカースレッドから呼ばれるため、
        GUI操作は必ず post_action 経由でメインスレッドへディスパッチする。

        Args:
            message: 通知メッセージ
        """
        logger.info(f"⏰ リマインダーをPCペットへ通知: {message}")
        self.gui.post_action(self.gui.update_message, message)
        self.gui.post_action(self.gui.set_pet_state, "alarm_ask", duration_ms=8000)

    def post_human_message(self, text: str) -> None:
        """スマホPWAからの音声入力テキストをエージェントへ投入する。

        スマホPWAの🎤マイクボタンから送信された音声認識テキストを、
        LangGraphエージェントのチャットパイプラインへ投入する（K2音声ウェイクワード布石）。

        Args:
            text: 音声認識されたテキスト。
        """
        if not text or not text.strip():
            return
        logger.info(f"🎤 音声入力テキストをエージェントへ投入: {text}")
        # GUIにメッセージを表示してからエージェント推論へ
        self.gui.post_action(self.gui.update_message, f"🎤 {text}")
        self.gui.post_action(self.gui.set_pet_state, "thinking")
        # asyncio タスクとしてエージェント推論を実行
        import asyncio
        asyncio.create_task(self._process_message(text))

    def _on_submit(self, event=None):
        """ユーザーが入力をしてEnterを押した時に呼ばれる"""
        user_text = self.gui.entry_var.get().strip()
        if not user_text:
            return
            
        # ユーザー操作を記録
        self.care_engine.record_user_activity()
        
        # 入力後、すぐに入力欄を空にする（UX向上）
        self.gui.entry_var.set("")
        
        # UIを「思考中...」状態へと更新し、マスコットを思考中アニメーションへ
        self.gui.update_message("考え中...")
        self.gui.set_pet_state("thinking")
        
        # 💡重要：そのまま推論を走らせるとUIが固まるため、asyncioの「非同期タスク」としてバックグラウンドに投げる
        asyncio.create_task(self._process_message(user_text))

    async def _process_message(self, user_text: str):
        """エージェントによる思考処理 (非同期)"""
        logger.info(f"ユーザー入力の処理開始: {user_text}")
        
        # イースターエッグ検知（「お前を消す方法」等）: 発火時は LLM に文脈指示を注入し、
        # キャラクターが文脈を理解した上でリアクションする。LLM失敗時は固定台詞へフォールバック。
        egg_fallback = None
        egg_event = observe_message(user_text)
        if egg_event is not None:
            logger.info(f"イースターエッグ発火: stage={egg_event['stage']}")
            self.gui.update_message("……！？")
            self.gui.set_pet_state("thinking", duration_ms=3000)
            egg_fallback = egg_event["fallback_reply"]
            user_text = f"{user_text}\n\n{egg_event['directive']}"
            try:
                from local_sync_server import get_link_monitor
                get_link_monitor().set_easter_egg_event(
                    stage=egg_event["stage"],
                    daily_count=egg_event["daily_count"],
                    attempt_count=egg_event["attempt_count"],
                    message=egg_event["fallback_reply"]
                )
            except Exception as ee_err:
                logger.debug(f"PWAイースターエッグ通知スキップ: {ee_err}")

        initial_state = {"messages": [HumanMessage(content=user_text)]}
        
        try:
            # ainvoke（非同期実行）で推論を実行
            # astreamはローカルGGUFモデルでチャンク処理の互換性問題があるためainvokeに統一
            result = await self.agent.ainvoke(initial_state, config=self.config)
            final_response = ""
            
            for msg in result.get("messages", []):
                if isinstance(msg, AIMessage):
                    content = msg.content
                    if isinstance(content, list):
                        texts = [item.get("text", "") for item in content if isinstance(item, dict) and "text" in item]
                        current_response = "".join(texts)
                    elif isinstance(content, str):
                        current_response = content
                    else:
                        current_response = str(content)
                    
                    if current_response.strip():
                        final_response = current_response
                    
            if final_response:
                self.gui.update_message(final_response)
                # 応答完了時: 4秒間笑顔になり、その後通常待機へ復帰
                self.gui.set_pet_state("happy", duration_ms=4000)
            else:
                self.gui.update_message(egg_fallback or "（返答がありませんでした）")
                self.gui.set_pet_state("idle")
                
            # AIの推論（DB操作を含む可能性がある）が完了したタイミングで付箋UIを更新する
            self.gui.refresh_sticky_notes()
                
        except Exception as e:
            logger.error(f"推論中にエラーが発生: {e}", exc_info=True)
            self.gui.update_message(egg_fallback or "申し訳ありません、脳内でエラーが発生しました...")
            self.gui.set_pet_state("idle")


async def async_mainloop(app: NeoSecretaryApp):
    """
    Tkinterのメインループと、Asyncioのイベントループを共存させる心臓部。
    Tkinter標準の root.mainloop() を使うとそこで処理が完全にブロックされて非同期が死んでしまうため、
    自前で更新ループを回します。
    """
    logger.info("非同期メインループを開始します")
    loop_tick = 0
    
    while True:
        try:
            # ウィンドウが存在するか（閉じられていないか）チェック
            if not app.gui.root.winfo_exists():
                logger.info("ウィンドウが閉じられました。アプリを終了します。")
                break
                
            # 1. UI側で発生したイベント（クリックや文字入力）および別スレッドアクションを処理・再描画
            app.gui.process_action_queue()
            app.gui.root.update()
            
            # 2. 定期的なプロアクティブ見守りチェック（約10秒 = 1000 tick ごと）
            loop_tick += 1
            if loop_tick >= 1000:
                loop_tick = 0
                app.care_engine.check_and_trigger_care()
                app.care_engine.check_event_reminders()
            
            # 3. ほんの僅かな時間（0.01秒）だけ処理を手放し、LLM推論等のAsyncioタスク群を動かす
            await asyncio.sleep(0.01)
            
        except tk.TclError as te:
            # 本当にウィンドウが破棄された場合のみ終了
            try:
                if not app.gui.root.winfo_exists():
                    logger.info("ウィンドウが破棄されました。アプリを終了します。")
                    break
            except Exception:
                break
            # 一過性のTclタイマー破棄エラーならループを継続
            logger.debug(f"一過性のTkinter TclError（継続）: {te}")
            await asyncio.sleep(0.02)

def main():
    # frozen (exe) 環境のブートストラップ: CWD を exe 直下に固定し .env を保証する
    import app_paths
    if app_paths.is_frozen():
        os.chdir(app_paths.get_app_root())
        app_paths.ensure_env_file()
        # windowed exe では標準入出力が None になり得るため print() クラッシュを防止
        if sys.stdout is None:
            sys.stdout = open(os.devnull, "w", encoding="utf-8")
        if sys.stderr is None:
            sys.stderr = open(os.devnull, "w", encoding="utf-8")

    # 二重起動の防止 (Single Instance Lock)
    import socket
    lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # ローカルの専用ポート(54321)をバインドして多重起動を検知
        lock_socket.bind(("127.0.0.1", 54321))
    except socket.error:
        logger.warning("多重起動を検知しました。ネオ秘書くんは既に起動しています！")
        print("\n⚠️ 【多重起動の検知】ネオ秘書くんは既に起動しています！")
        print("以前のプロセスが実行中のため、新しく起動したプロセスを終了します。")
        print("以前の画面を前面に表示するか、タスクマネージャー等で一度終了させてから再起動してください。\n")
        return

    # アプリケーションの構築
    app = NeoSecretaryApp()
    
    # 💡Asyncioのイベントループの上で、自前のメインループを回す
    try:
        asyncio.run(async_mainloop(app))
    finally:
        try:
            lock_socket.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
