"""
ネオ秘書くん - スマホ専用ペット端末 (Desk Pet) ローカル同期サーバー (local_sync_server.py)

PCと手元のスマートフォン（PWA / Web Bluetooth / Wi-Fi）を直接接続し、
タスクや予定、ペットの状態をリアルタイム同期するための軽量HTTP/APIサーバー。
"""

import os
import json
import logging
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any

import database

logger = logging.getLogger(__name__)

WEB_PET_DIR = Path(__file__).parent / "web_pet"
SERVER_PORT = 8765


class DeskPetSyncHandler(SimpleHTTPRequestHandler):
    """Desk Pet PWA用の静的ファイル配信 ＆ JSON APIハンドラ"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_PET_DIR), **kwargs)

    def do_GET(self):
        """APIエンドポイントまたは静的ファイルの処理"""
        if self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            try:
                tasks = database.get_tasks(status="pending")
                events = database.get_upcoming_events(days=1)
                
                tasks_data = [
                    {"id": t.id, "title": t.title, "priority": t.priority, "due_date": t.due_date}
                    for t in tasks
                ]
                events_data = [
                    {"id": e.id, "title": e.title, "start_time": e.start_time, "location": e.location}
                    for e in events
                ]
                
                payload = {
                    "status": "ok",
                    "pet_state": "idle",
                    "message": "ボス、いつもお疲れ様です！スマホからも見守っていますよ！",
                    "tasks": tasks_data,
                    "events": events_data
                }
                self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                logger.error(f"Status API エラー: {e}")
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))
        else:
            super().do_GET()

    def do_POST(self):
        """スマホ側からのアクション（タスク完了等）の受信"""
        if self.path == "/api/action":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            try:
                data = json.loads(body.decode("utf-8"))
                action = data.get("action")
                
                if action == "complete_task":
                    task_id = data.get("task_id")
                    if task_id:
                        database.complete_task(int(task_id))
                        logger.info(f"スマホ側からタスク完了を受信: TaskID={task_id}")
                        self.wfile.write(json.dumps({"status": "success", "task_id": task_id}).encode("utf-8"))
                        return
                        
                self.wfile.write(json.dumps({"status": "unknown_action"}).encode("utf-8"))
            except Exception as e:
                logger.error(f"Action API エラー: {e}")
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        """標準出力のノイズを抑えるカスタムロガー"""
        pass


class LocalSyncServer:
    """バックグラウンドで稼働するローカル同期サーバー"""
    
    def __init__(self, port: int = SERVER_PORT):
        self.port = port
        self.httpd = None
        self.thread = None

    def start(self):
        """バックグラウンドスレッドでサーバーを起動"""
        try:
            self.httpd = HTTPServer(("0.0.0.0", self.port), DeskPetSyncHandler)
            self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.thread.start()
            logger.info(f"📱 Desk Pet ローカル同期サーバーが起動しました: http://localhost:{self.port} (ローカルWi-Fi公開)")
        except Exception as e:
            logger.warning(f"Desk Pet 同期サーバーの起動をスキップしました（ポート競合など）: {e}")

    def stop(self):
        """サーバーを停止"""
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            logger.info("Desk Pet 同期サーバーを停止しました")


# シングルトン
_global_sync_server = None

def get_sync_server() -> LocalSyncServer:
    global _global_sync_server
    if _global_sync_server is None:
        _global_sync_server = LocalSyncServer()
    return _global_sync_server
