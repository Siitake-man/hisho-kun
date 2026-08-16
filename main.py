"""
ネオ秘書くん - メイン実行モジュール (main.py)

GUI(gui.py) と エージェント(agent.py) を「asyncio」を使い共存させます。
これにより、AIが思考中であっても画面（UI）が固まることなく、
スムーズなユーザー体験(UX)を実現します。
"""

import asyncio
import logging
import tkinter as tk

from langchain_core.messages import HumanMessage, AIMessage

from gui import NeoSecretaryGUI
from agent import build_agent_graph

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NeoSecretaryApp:
    def __init__(self):
        # 0. データベース初期化
        import database
        database.init_db()

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
        
        # 初期メッセージ
        self.gui.update_message("おはようございます！\n本日のご予定はいかがなさいますか？\n（入力してEnterを押してください）")
        
        # 起動時に一度だけDBから付箋を読み込んで画面に表示する
        self.gui.refresh_sticky_notes()

    def _on_proactive_care(self, message: str, pet_state: str = "happy"):
        """プロアクティブ見守りエンジンからの自律通知ハンドラ"""
        logger.info("プロアクティブ声掛けをUIに反映します")
        self.gui.update_message(message)
        self.gui.set_pet_state(pet_state, duration_ms=5000)

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
        
        initial_state = {"messages": [HumanMessage(content=user_text)]}
        
        try:
            # astream（非同期ストリーム実行）を使うことで、推論の合間にUIの描画へ処理を譲ることができる
            final_response = ""
            async for chunk in self.agent.astream(initial_state, config=self.config, stream_mode="values"):
                last_message = chunk["messages"][-1]
                
                # エージェントからの返答(AIMessage)を抽出し、UIを更新する
                if isinstance(last_message, AIMessage):
                    content = last_message.content
                    current_response = ""
                    if isinstance(content, list):
                        # Geminiモデルがメタデータ込みのリスト型で返す場合があるための対応
                        texts = [item.get("text", "") for item in content if isinstance(item, dict) and "text" in item]
                        current_response = "".join(texts)
                    elif isinstance(content, str):
                        current_response = content
                        
                    # ツール呼び出し指示のみでテキストが含まれない場合は表示を更新しない
                    if current_response.strip():
                        final_response = current_response
                    
            if final_response:
                self.gui.update_message(final_response)
                # 応答完了時: 4秒間笑顔になり、その後通常待機へ復帰
                self.gui.set_pet_state("happy", duration_ms=4000)
            else:
                self.gui.update_message("（返答がありませんでした）")
                self.gui.set_pet_state("idle")
                
            # AIの推論（DB操作を含む可能性がある）が完了したタイミングで付箋UIを更新する
            self.gui.refresh_sticky_notes()
                
        except Exception as e:
            logger.error(f"推論中にエラーが発生: {e}", exc_info=True)
            self.gui.update_message("申し訳ありません、脳内でエラーが発生しました...")
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
            
            # 3. ほんの僅かな時間（0.01秒）だけ処理を手放し、LLM推論等のAsyncioタスク群を動かす
            await asyncio.sleep(0.01)
            
        except tk.TclError:
            # ユーザーがウィンドウを閉じた（destroyされた）直後にupdateが呼ばれた場合の安全策
            logger.info("Tkinter TclErrorを検知しました。アプリを終了します。")
            break

def main():
    # アプリケーションの構築
    app = NeoSecretaryApp()
    
    # 💡Asyncioのイベントループの上で、自前のメインループを回す
    asyncio.run(async_mainloop(app))

if __name__ == "__main__":
    main()
