"""
ネオ秘書くん - GUIモジュール (gui.py)

CustomTkinterを用いたUIコンポーネント。
背景透過のキャラクターウィンドウと、会話用の吹き出しUIを提供します。
"""
import queue
import customtkinter as ctk
import tkinter as tk
from typing import Callable, Optional, Dict
from pathlib import Path
import logging
from PIL import Image, ImageTk

logger = logging.getLogger(__name__)

# CustomTkinterの基本設定
ctk.set_appearance_mode("light")  # レトロモダンなクリーム色をベースにするため
ctk.set_default_color_theme("green") # デフォルトテーマ（後でカスタムカラーに変更可能）

class QRCodeConnectionDialog(ctk.CTkToplevel):
    """
    スマホ専用Desk Pet ＆ 承認コクピットへワンタップ接続するための
    QRコード生成 ＆ 社内ユーザー向け接続ガイドダイアログ。
    """
    def __init__(self, parent_gui, *args, **kwargs):
        super().__init__(parent_gui.root, *args, **kwargs)
        self.parent_gui = parent_gui
        self.title("📱 スマホDesk Pet ＆ 承認コクピット接続")
        self.geometry("480x620")
        self.resizable(False, False)
        
        self.bg_color = "#F5F5DC"
        self.primary_color = "#A67B5B"
        self.text_color = "#4A3B32"
        self.configure(fg_color=self.bg_color)
        
        self.font_title = ("DotGothic16", 14, "bold") if "DotGothic16" in tk.font.families() else ("Meiryo UI", 12, "bold")
        self.font_body = ("DotGothic16", 11) if "DotGothic16" in tk.font.families() else ("Meiryo UI", 10)
        self.font_small = ("Meiryo UI", 9)
        self.font_mono = ("Consolas", 10)
        
        self.qr_image_tk = None
        self._build_ui()

    def _get_local_ips(self) -> list:
        """PCの利用可能なローカルIPアドレス一覧を取得"""
        import socket
        ips = []
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            main_ip = s.getsockname()[0]
            s.close()
            ips.append(main_ip)
        except Exception:
            pass
            
        try:
            hostname = socket.gethostname()
            for ip in socket.gethostbyname_ex(hostname)[2]:
                if ip not in ips and not ip.startswith("127."):
                    ips.append(ip)
        except Exception:
            pass
            
        if not ips:
            ips.append("127.0.0.1")
        return ips

    def _build_ui(self):
        pad = 12
        # ヘッダー
        ctk.CTkLabel(self, text="📱 スマホを机上のペット端末にする", font=self.font_title, text_color=self.primary_color).pack(pady=(12, 4))
        ctk.CTkLabel(self, text="カメラでQRコードをかざすだけで、スマホが承認コクピットになります！", font=self.font_small, text_color="#7A6B62").pack()
        
        # IPセレクタ
        self.ips = self._get_local_ips()
        self.selected_ip_var = tk.StringVar(value=self.ips[0])
        
        ip_frame = ctk.CTkFrame(self, fg_color="transparent")
        ip_frame.pack(fill="x", padx=pad, pady=(8, 4))
        ctk.CTkLabel(ip_frame, text="接続IP:", font=self.font_body, text_color=self.text_color).pack(side="left", padx=(0, 6))
        
        ip_menu = ctk.CTkOptionMenu(
            ip_frame,
            values=self.ips,
            variable=self.selected_ip_var,
            command=self._on_ip_change,
            fg_color=self.primary_color,
            button_color="#8B634A",
            height=28
        )
        ip_menu.pack(side="left", fill="x", expand=True)

        # QRコード表示フレーム
        self.qr_frame = ctk.CTkFrame(self, fg_color="#FFFFFF", border_color="#A67B5B", border_width=2, corner_radius=10)
        self.qr_frame.pack(pady=8, padx=pad)
        
        self.qr_label = tk.Label(self.qr_frame, bg="#FFFFFF")
        self.qr_label.pack(padx=12, pady=12)

        # URLテキスト ＆ コピー
        url_box = ctk.CTkFrame(self, fg_color="transparent")
        url_box.pack(fill="x", padx=pad, pady=2)
        
        self.url_var = tk.StringVar(value=f"http://{self.ips[0]}:8765")
        self.url_entry = ctk.CTkEntry(url_box, textvariable=self.url_var, font=self.font_mono, height=28, state="readonly")
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        
        # 📶 リアルタイム接続ステータス ＆ 呼び出しテスト ＆ PCペット復帰
        status_box = ctk.CTkFrame(self, fg_color="#FFFFFF", border_color="#A67B5B", border_width=1.5, corner_radius=8)
        status_box.pack(fill="x", padx=pad, pady=4)
        
        self.link_status_label = ctk.CTkLabel(
            status_box,
            text="🔴 スマホ未接続（アクセス待機中...）",
            font=("Meiryo UI", 10, "bold"),
            text_color="#C62828"
        )
        self.link_status_label.pack(side="left", padx=8, pady=6)
        
        btn_frame = ctk.CTkFrame(status_box, fg_color="transparent")
        btn_frame.pack(side="right", padx=6, pady=4)
        
        self.btn_show_pc = ctk.CTkButton(
            btn_frame,
            text="🖥️ PCペット表示",
            width=90,
            height=26,
            font=self.font_small,
            fg_color="#5B8A72",
            command=self.parent_gui.show_pc_pet
        )
        self.btn_show_pc.pack(side="left", padx=(0, 4))
        
        self.btn_buzz = ctk.CTkButton(
            btn_frame,
            text="📲 呼出テスト",
            width=80,
            height=26,
            font=self.font_small,
            fg_color="#A67B5B",
            state="disabled",
            command=self._send_buzz_test
        )
        self.btn_buzz.pack(side="left")

        # 📱 スマホ接続時の自動非表示トグルスイッチ
        opt_box = ctk.CTkFrame(self, fg_color="#F5F5DC", border_color="#A67B5B", border_width=1, corner_radius=6)
        opt_box.pack(fill="x", padx=pad, pady=3)
        
        self.auto_hide_var = tk.BooleanVar(value=getattr(self.parent_gui, 'auto_minimize_on_link', False))
        self.chk_auto_hide = ctk.CTkCheckBox(
            opt_box,
            text="📱 スマホ接続時にPCペットを自動非表示にする（画面占有ゼロ化）",
            variable=self.auto_hide_var,
            font=("Meiryo UI", 9.5, "bold"),
            text_color="#4A3B32",
            fg_color="#A67B5B",
            hover_color="#8B634A",
            command=self._on_toggle_auto_hide
        )
        self.chk_auto_hide.pack(side="left", padx=8, pady=4)

        # 🔰 社内ユーザー向け接続ガイド
        guide_box = ctk.CTkFrame(self, fg_color="#EFEBE9", border_color="#D7CCC8", border_width=1, corner_radius=8)
        guide_box.pack(fill="both", expand=True, padx=pad, pady=(4, 10))
        
        ctk.CTkLabel(guide_box, text="🔰 初めての接続ガイド（社内・外出先）", font=("Meiryo UI", 10, "bold"), text_color=self.primary_color).pack(anchor="w", padx=8, pady=(6, 2))
        
        guide_text = (
            "【Wi-Fi接続（社内・自宅）】\n"
            "  PCとスマホを同じWi-Fiに繋ぎ、上のQRコードをカメラで読み取るだけ！\n\n"
            "【Bluetooth接続（外出先・Wi-Fi不要）】★オススメ\n"
            "  1. PCとスマホをBluetoothで「ペアリング」します。\n"
            "  2. スマホのBluetooth設定で「インターネット共有(PAN)」をONにします。\n"
            "  3. QRコードを読み取るだけで、オフラインで直接通信が完結します！"
        )
        ctk.CTkLabel(guide_box, text=guide_text, font=self.font_small, text_color="#4E342E", justify="left", wraplength=430).pack(anchor="w", padx=8, pady=(0, 6))
        
        self._render_qr()
        self._poll_link_status()

    def _render_qr(self):
        """選択中のIPアドレスからQRコードを生成して描画"""
        url = self.url_var.get()
        try:
            import qrcode
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=5,
                border=1,
            )
            qr.add_data(url)
            qr.make(fit=True)
            pil_img = qr.make_image(fill_color="#4A3B32", back_color="#FFFFFF").convert("RGB")
            self.qr_image_tk = ImageTk.PhotoImage(pil_img)
            self.qr_label.configure(image=self.qr_image_tk, text="")
        except ImportError:
            # qrcodeライブラリ未インストール時のフォールバック
            self.qr_label.configure(
                text=f"【URL】\n{url}\n\n（スマホのブラウザで上記を開いてください）",
                font=("Meiryo UI", 10, "bold"),
                fg="#4A3B32"
            )

    def _on_ip_change(self, selected_ip):
        self.url_var.set(f"http://{selected_ip}:8765")
        self._render_qr()

    def _on_toggle_auto_hide(self):
        """スマホ接続時の自動非表示設定を反映"""
        val = self.auto_hide_var.get()
        self.parent_gui.auto_minimize_on_link = val
        logger.info(f"スマホ接続時PCペット自動非表示設定: {val}")

    def _copy_url(self):
        self.clipboard_clear()
        self.clipboard_append(self.url_var.get())

    def _send_buzz_test(self):
        """PCからスマホへ呼び出し信号を送信"""
        import urllib.request
        try:
            req = urllib.request.Request("http://localhost:8765/api/test_buzz", data=b"{}", headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=1.0)
            self.link_status_label.configure(text="📲 スマホへ呼び出し信号を送信しました！")
        except Exception as e:
            logger.error(f"Buzzテストエラー: {e}")

    def _poll_link_status(self):
        """ローカル同期サーバーのリンク状態を定期確認"""
        if not self.winfo_exists():
            return
            
        try:
            from local_sync_server import get_link_monitor
            status = get_link_monitor().get_status()
            if status["connected"]:
                dev = status["device_name"]
                sec = status["seconds_ago"]
                self.link_status_label.configure(
                    text=f"🟢 接続中: {dev} (最終通信: {sec}秒前)",
                    text_color="#2E7D32"
                )
                self.btn_buzz.configure(state="normal")
            else:
                self.link_status_label.configure(
                    text="🔴 スマホ未接続（アクセス待機中...）",
                    text_color="#C62828"
                )
                self.btn_buzz.configure(state="disabled")
        except Exception as e:
            pass
            
        self.after(1500, self._poll_link_status)


class AddMCPServerDialog(ctk.CTkToplevel):
    """
    ユーザーが任意のMCPサーバー（Google Calendar, Notion, Slack等）を追加するためのダイアログ。
    """
    def __init__(self, parent_settings, *args, **kwargs):
        super().__init__(parent_settings, *args, **kwargs)
        self.parent_settings = parent_settings
        self.title("➕ 新規MCPサーバーの追加")
        self.geometry("420x460")
        self.resizable(False, False)
        
        self.bg_color = "#F5F5DC"
        self.primary_color = "#A67B5B"
        self.text_color = "#4A3B32"
        self.configure(fg_color=self.bg_color)
        
        self.font_title = ("DotGothic16", 13, "bold") if "DotGothic16" in tk.font.families() else ("Meiryo UI", 11, "bold")
        self.font_body = ("DotGothic16", 11) if "DotGothic16" in tk.font.families() else ("Meiryo UI", 10)
        self.font_small = ("Meiryo UI", 9)
        
        self._build_ui()

    def _build_ui(self):
        pad = 12
        ctk.CTkLabel(self, text="➕ 新しいMCPサーバーを追加", font=self.font_title, text_color=self.primary_color).pack(pady=(12, 6))
        
        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=pad, pady=4)
        
        # 1. サーバーID
        ctk.CTkLabel(form, text="サーバー識別子 (例: google-calendar):", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_id = ctk.CTkEntry(form, placeholder_text="google-calendar")
        self.entry_id.pack(fill="x", pady=(0, 6))
        
        # 2. 表示名
        ctk.CTkLabel(form, text="表示名 (例: Google カレンダー連携):", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_name = ctk.CTkEntry(form, placeholder_text="Google カレンダー連携")
        self.entry_name.pack(fill="x", pady=(0, 6))
        
        # 3. 実行コマンド (command)
        ctk.CTkLabel(form, text="実行コマンド (例: npx, uvx, python):", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_cmd = ctk.CTkEntry(form, placeholder_text="npx")
        self.entry_cmd.insert(0, "npx")
        self.entry_cmd.pack(fill="x", pady=(0, 6))
        
        # 4. 引数 (args)
        ctk.CTkLabel(form, text="引数 (スペース区切り, 例: -y @modelcontextprotocol/server-xxx):", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_args = ctk.CTkEntry(form, placeholder_text="-y @modelcontextprotocol/server-google-calendar")
        self.entry_args.pack(fill="x", pady=(0, 6))
        
        # 5. 説明
        ctk.CTkLabel(form, text="概要・説明 (省略可):", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_desc = ctk.CTkEntry(form, placeholder_text="Googleカレンダーの予定を参照・登録します")
        self.entry_desc.pack(fill="x", pady=(0, 10))
        
        # 登録ボタン
        btn_add = ctk.CTkButton(
            self,
            text="✨ MCPサーバーを登録",
            font=self.font_title,
            fg_color=self.primary_color,
            hover_color="#8B634A",
            height=36,
            command=self._on_submit
        )
        btn_add.pack(fill="x", padx=pad, pady=(0, 14))

    def _on_submit(self):
        s_id = self.entry_id.get().strip()
        name = self.entry_name.get().strip() or s_id
        cmd = self.entry_cmd.get().strip()
        args_str = self.entry_args.get().strip()
        desc = self.entry_desc.get().strip()
        
        if not s_id or not cmd:
            return
            
        args_list = args_str.split() if args_str else []
        
        from mcp_manager import get_mcp_manager, MCPServerConfig
        mcp_mgr = get_mcp_manager()
        
        conf = MCPServerConfig(
            name=name,
            command=cmd,
            args=args_list,
            env={},
            enabled=True,
            description=desc
        )
        
        mcp_mgr.add_or_update_server(s_id, conf)
        
        # 設定画面を再描画して閉じる
        if hasattr(self.parent_settings, "_render_mcp_servers"):
            self.parent_settings._render_mcp_servers()
        self.destroy()


class SuggestSettingsDialog(ctk.CTkToplevel):
    """サジェストソースの個別ON/OFF設定ダイアログ"""
    def __init__(self, parent_gui, *args, **kwargs):
        super().__init__(parent_gui.root, *args, **kwargs)
        self.parent_gui = parent_gui
        self.title("💡 サジェストソース設定")
        self.geometry("380x430")
        self.resizable(False, False)
        
        self.bg_color = "#F5F5DC"
        self.primary_color = "#A67B5B"
        self.text_color = "#4A3B32"
        self.configure(fg_color=self.bg_color)
        
        from suggest_engine import get_suggestion_engine
        self.engine = get_suggestion_engine()
        self.config = self.engine.config
        
        self.font_title = ("DotGothic16", 13, "bold") if "DotGothic16" in tk.font.families() else ("Meiryo UI", 11, "bold")
        self.font_body = ("Meiryo UI", 10)
        self.font_small = ("Meiryo UI", 8.5)
        
        self._build_ui()

    def _build_ui(self):
        pad = 14
        ctk.CTkLabel(self, text="💡 インテリジェント・サジェスト設定", font=self.font_title, text_color=self.primary_color).pack(pady=(12, 4))
        ctk.CTkLabel(self, text="画面中央に表示する情報のソースを個別に選べます", font=self.font_small, text_color="#7A6B62").pack(pady=(0, 8))
        
        scroll = ctk.CTkScrollableFrame(self, fg_color="#FFFFFF", border_color="#A67B5B", border_width=1.5, corner_radius=8)
        scroll.pack(fill="both", expand=True, padx=pad, pady=4)
        
        sources = self.config.get("sources", {})
        self.check_vars = {}
        
        for key, info in sources.items():
            card = ctk.CTkFrame(scroll, fg_color="#FDFBF7", corner_radius=6, border_color="#E0D8C8", border_width=1)
            card.pack(fill="x", pady=4, padx=4)
            
            var = tk.BooleanVar(value=info.get("enabled", True))
            self.check_vars[key] = var
            
            chk = ctk.CTkCheckBox(
                card,
                text=info.get("name", key),
                variable=var,
                font=("Meiryo UI", 10, "bold"),
                text_color=self.text_color,
                fg_color=self.primary_color,
                hover_color="#8B634A",
                command=lambda k=key, v=var: self._on_toggle(k, v)
            )
            chk.pack(anchor="w", padx=8, pady=(6, 2))
            
            desc = info.get("description", "")
            if desc:
                ctk.CTkLabel(card, text=desc, font=self.font_small, text_color="#6D4C41", anchor="w").pack(fill="x", padx=28, pady=(0, 6))

        btn_close = ctk.CTkButton(
            self,
            text="設定を保存して閉じる",
            font=("Meiryo UI", 10, "bold"),
            fg_color=self.primary_color,
            hover_color="#8B634A",
            height=32,
            command=self.destroy
        )
        btn_close.pack(fill="x", padx=pad, pady=10)

    def _on_toggle(self, key, var):
        self.engine.toggle_source(key, var.get())
        if hasattr(self.parent_gui, '_update_suggestion_card'):
            self.parent_gui._update_suggestion_card()


class SettingsWindow(ctk.CTkToplevel):
    """
    APIキーやLLM接続先を設定し、利用可能なモデル一覧を動的取得・選択するための設定ウィンドウ。
    """
    def __init__(self, parent_gui, *args, **kwargs):
        super().__init__(parent_gui.root, *args, **kwargs)
        self.parent_gui = parent_gui
        self.title("ネオ秘書くん - AIモデル・API設定")
        self.geometry("480x620")
        
        # 色設定
        self.bg_color = "#F5F5DC"
        self.primary_color = "#A67B5B"
        self.text_color = "#4A3B32"
        self.configure(fg_color=self.bg_color)
        
        self.font_title = ("DotGothic16", 15, "bold") if "DotGothic16" in tk.font.families() else ("Meiryo UI", 13, "bold")
        self.font_body = ("DotGothic16", 12) if "DotGothic16" in tk.font.families() else ("Meiryo UI", 10)
        self.font_small = ("Meiryo UI", 9)
        
        self._build_ui()

    def _build_ui(self):
        import os
        from dotenv import load_dotenv
        from llm_factory import get_llm_factory, LLMProvider
        load_dotenv(override=True)
        factory = get_llm_factory()
        
        # ヘッダー
        header = ctk.CTkFrame(self, fg_color=self.primary_color, corner_radius=0, height=45)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)
        
        title_label = ctk.CTkLabel(header, text="⚙ AIモデル・API動的設定", font=self.font_title, text_color="#FFFFFF")
        title_label.pack(pady=8)
        
        # 設定フォーム領域
        content = ctk.CTkScrollableFrame(self, fg_color=self.bg_color)
        content.pack(side="top", fill="both", expand=True, padx=15, pady=(10, 5))
        
        # =====================================================================
        # 1. OpenCode GO (DeepSeek)
        # =====================================================================
        sec1 = ctk.CTkLabel(content, text="⚡ OpenCode GO (DeepSeek)", font=self.font_title, text_color=self.primary_color, anchor="w")
        sec1.pack(fill="x", pady=(5, 2))
        
        ctk.CTkLabel(content, text="API Key:", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_opencode_key = ctk.CTkEntry(content, placeholder_text="sk-...", show="*")
        self.entry_opencode_key.insert(0, os.getenv("OPENCODE_API_KEY", ""))
        self.entry_opencode_key.pack(fill="x", pady=(0, 3))
        
        ctk.CTkLabel(content, text="Base URL:", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_opencode_url = ctk.CTkEntry(content, placeholder_text="https://api.opencode.go.jp/v1")
        self.entry_opencode_url.insert(0, os.getenv("OPENCODE_BASE_URL", "https://api.opencode.go.jp/v1"))
        self.entry_opencode_url.pack(fill="x", pady=(0, 3))
        
        # モデル取得ボタン & コンボボックス
        opencode_models = [m["id"] for m in factory.get_models_for_provider(LLMProvider.OPENCODE)]
        current_opencode_model = os.getenv("OPENCODE_MODEL", "deepseek-chat")
        
        btn_box1 = ctk.CTkFrame(content, fg_color="transparent")
        btn_box1.pack(fill="x", pady=(2, 2))
        
        ctk.CTkLabel(btn_box1, text="使用モデル:", font=self.font_body, text_color=self.text_color).pack(side="left")
        self.btn_fetch_opencode = ctk.CTkButton(
            btn_box1, 
            text="🔄 モデル一覧を取得", 
            width=130, 
            height=24, 
            font=self.font_small,
            fg_color="#8B634A",
            command=lambda: self._fetch_models("opencode")
        )
        self.btn_fetch_opencode.pack(side="right")
        
        self.combo_opencode_model = ctk.CTkComboBox(content, values=opencode_models)
        self.combo_opencode_model.set(current_opencode_model)
        self.combo_opencode_model.pack(fill="x", pady=(0, 2))
        
        self.lbl_opencode_status = ctk.CTkLabel(content, text="", font=self.font_small, text_color="#2E7D32", anchor="w")
        self.lbl_opencode_status.pack(fill="x", pady=(0, 15))
        
        # =====================================================================
        # 2. Google Gemini
        # =====================================================================
        sec2 = ctk.CTkLabel(content, text="☁ Google Gemini", font=self.font_title, text_color=self.primary_color, anchor="w")
        sec2.pack(fill="x", pady=(5, 2))
        
        ctk.CTkLabel(content, text="API Key:", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_gemini_key = ctk.CTkEntry(content, placeholder_text="AIzaSy...", show="*")
        self.entry_gemini_key.insert(0, os.getenv("GOOGLE_API_KEY", ""))
        self.entry_gemini_key.pack(fill="x", pady=(0, 3))
        
        gemini_models = [m["id"] for m in factory.get_models_for_provider(LLMProvider.GEMINI)]
        current_gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        
        btn_box2 = ctk.CTkFrame(content, fg_color="transparent")
        btn_box2.pack(fill="x", pady=(2, 2))
        
        ctk.CTkLabel(btn_box2, text="使用モデル:", font=self.font_body, text_color=self.text_color).pack(side="left")
        self.btn_fetch_gemini = ctk.CTkButton(
            btn_box2, 
            text="🔄 モデル一覧を取得", 
            width=130, 
            height=24, 
            font=self.font_small,
            fg_color="#8B634A",
            command=lambda: self._fetch_models("gemini")
        )
        self.btn_fetch_gemini.pack(side="right")
        
        self.combo_gemini_model = ctk.CTkComboBox(content, values=gemini_models)
        self.combo_gemini_model.set(current_gemini_model)
        self.combo_gemini_model.pack(fill="x", pady=(0, 2))
        
        self.lbl_gemini_status = ctk.CTkLabel(content, text="", font=self.font_small, text_color="#2E7D32", anchor="w")
        self.lbl_gemini_status.pack(fill="x", pady=(0, 15))
        
        # =====================================================================
        # 3. LM Studio
        # =====================================================================
        sec3 = ctk.CTkLabel(content, text="💻 LM Studio (Local LLM)", font=self.font_title, text_color=self.primary_color, anchor="w")
        sec3.pack(fill="x", pady=(5, 2))
        
        ctk.CTkLabel(content, text="Base URL:", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_lm_url = ctk.CTkEntry(content, placeholder_text="http://localhost:1234/v1")
        self.entry_lm_url.insert(0, os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1"))
        self.entry_lm_url.pack(fill="x", pady=(0, 3))
        
        lm_models = [m["id"] for m in factory.get_models_for_provider(LLMProvider.LM_STUDIO)]
        current_lm_model = os.getenv("LM_STUDIO_MODEL", "local-model")
        
        btn_box3 = ctk.CTkFrame(content, fg_color="transparent")
        btn_box3.pack(fill="x", pady=(2, 2))
        
        ctk.CTkLabel(btn_box3, text="使用モデル:", font=self.font_body, text_color=self.text_color).pack(side="left")
        self.btn_fetch_lm = ctk.CTkButton(
            btn_box3, 
            text="🔄 モデル一覧を取得", 
            width=130, 
            height=24, 
            font=self.font_small,
            fg_color="#8B634A",
            command=lambda: self._fetch_models("lm_studio")
        )
        self.btn_fetch_lm.pack(side="right")
        
        self.combo_lm_model = ctk.CTkComboBox(content, values=lm_models)
        self.combo_lm_model.set(current_lm_model)
        self.combo_lm_model.pack(fill="x", pady=(0, 2))
        
        self.lbl_lm_status = ctk.CTkLabel(content, text="", font=self.font_small, text_color="#2E7D32", anchor="w")
        self.lbl_lm_status.pack(fill="x", pady=(0, 15))

        # =====================================================================
        # 4. 外部MCP連携 (Model Context Protocol)
        # =====================================================================
        from mcp_manager import get_mcp_manager
        mcp_mgr = get_mcp_manager()
        server_configs = mcp_mgr.get_server_configs()
        
        mcp_header_box = ctk.CTkFrame(content, fg_color="transparent")
        mcp_header_box.pack(fill="x", pady=(5, 2))
        
        sec4 = ctk.CTkLabel(mcp_header_box, text="🔌 外部MCPサーバー連携 (プラグイン)", font=self.font_title, text_color=self.primary_color)
        sec4.pack(side="left")
        
        btn_add_mcp = ctk.CTkButton(
            mcp_header_box,
            text="➕ 新規追加",
            width=80,
            height=24,
            font=self.font_small,
            fg_color=self.primary_color,
            hover_color="#8B634A",
            command=self._open_add_mcp_dialog
        )
        btn_add_mcp.pack(side="right")
        
        mcp_desc = ctk.CTkLabel(
            content, 
            text="有効にした外部サービスのツールをAIが自律的に利用します", 
            font=self.font_small, 
            text_color="#6D4C41", 
            anchor="w"
        )
        mcp_desc.pack(fill="x", pady=(0, 6))

        self.mcp_checkboxes = {}
        for s_id, conf in server_configs.items():
            row_frame = ctk.CTkFrame(content, fg_color="#F9F6F0", corner_radius=6)
            row_frame.pack(fill="x", pady=2, padx=2)
            
            cb_var = tk.BooleanVar(value=conf.enabled)
            cb = ctk.CTkCheckBox(
                row_frame,
                text=f"{conf.name} ({s_id})",
                variable=cb_var,
                font=self.font_body,
                text_color=self.text_color,
                fg_color=self.primary_color,
                hover_color="#8B634A"
            )
            cb.pack(side="left", padx=8, pady=6)
            
            # デフォルトプリセット以外は削除ボタンを表示
            if s_id not in ("filesystem", "fetch", "github"):
                btn_del = ctk.CTkButton(
                    row_frame,
                    text="🗑",
                    width=26,
                    height=24,
                    font=("Meiryo UI", 10),
                    fg_color="#C62828",
                    hover_color="#B71C1C",
                    command=lambda sid=s_id: self._delete_mcp_server(sid)
                )
                btn_del.pack(side="right", padx=6)
            
            if conf.description:
                ctk.CTkLabel(
                    content, 
                    text=f"   └ {conf.description}", 
                    font=self.font_small, 
                    text_color="#8D6E63", 
                    anchor="w"
                ).pack(fill="x", pady=(0, 3))
                
            self.mcp_checkboxes[s_id] = cb_var
            
        ctk.CTkLabel(content, text="", height=5).pack()

        # =====================================================================
        # 5. 外部サービス連携 (Google Calendar / Slack)
        # =====================================================================
        sec_ext = ctk.CTkLabel(content, text="🌐 外部サービス連携 (Google / Slack)", font=self.font_title, text_color=self.primary_color, anchor="w")
        sec_ext.pack(fill="x", pady=(10, 2))
        
        ctk.CTkLabel(content, text="Googleカレンダー ID / メールアドレス:", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_google_cal = ctk.CTkEntry(content, placeholder_text="primary または your_email@gmail.com")
        self.entry_google_cal.insert(0, os.getenv("GOOGLE_CALENDAR_ID", "primary"))
        self.entry_google_cal.pack(fill="x", pady=(0, 4))
        
        ctk.CTkLabel(content, text="Slack Webhook URL (通知/サジェスト連携):", font=self.font_body, text_color=self.text_color, anchor="w").pack(fill="x")
        self.entry_slack_webhook = ctk.CTkEntry(content, placeholder_text="https://hooks.slack.com/services/...", show="*")
        self.entry_slack_webhook.insert(0, os.getenv("SLACK_WEBHOOK_URL", ""))
        self.entry_slack_webhook.pack(fill="x", pady=(0, 10))
        
        # =====================================================================
        # 保存ボタン
        # =====================================================================
        btn_save = ctk.CTkButton(
            self,
            text="💾 設定を保存して適用",
            font=self.font_title,
            fg_color=self.primary_color,
            hover_color="#8B634A",
            height=40,
            command=self._on_save
        )
        btn_save.pack(side="bottom", fill="x", padx=20, pady=12)

    def _open_add_mcp_dialog(self):
        """MCPサーバー新規追加ダイアログを開く"""
        dialog = AddMCPServerDialog(self)
        dialog.focus()

    def _delete_mcp_server(self, server_id: str):
        """MCPサーバー設定を削除"""
        from mcp_manager import get_mcp_manager
        mcp_mgr = get_mcp_manager()
        if mcp_mgr.delete_server(server_id):
            self.destroy()
            SettingsWindow(self.parent_gui)

    def _fetch_models(self, provider: str):
        """APIから利用可能なモデル一覧を動的に探索・取得"""
        from llm_factory import get_llm_factory
        factory = get_llm_factory()
        
        lbl = self.lbl_opencode_status if provider == "opencode" else (self.lbl_gemini_status if provider == "gemini" else self.lbl_lm_status)
        combo = self.combo_opencode_model if provider == "opencode" else (self.combo_gemini_model if provider == "gemini" else self.combo_lm_model)
        
        lbl.configure(text="⏳ モデル一覧を取得中...", text_color="#A67B5B")
        self.update_idletasks()
        
        try:
            if provider == "opencode":
                key = self.entry_opencode_key.get().strip()
                url = self.entry_opencode_url.get().strip()
                models = factory.fetch_available_models(provider, api_key=key, base_url=url)
            elif provider == "gemini":
                key = self.entry_gemini_key.get().strip()
                models = factory.fetch_available_models(provider, api_key=key)
            else:
                url = self.entry_lm_url.get().strip()
                models = factory.fetch_available_models(provider, base_url=url)
                
            model_ids = [m["id"] for m in models]
            combo.configure(values=model_ids)
            if model_ids:
                combo.set(model_ids[0])
            lbl.configure(text=f"✓ {len(model_ids)} 件のモデルを取得しました！", text_color="#2E7D32")
        except Exception as e:
            logger.error(f"モデル取得失敗: {e}")
            lbl.configure(text=f"❌ 取得失敗: {e}", text_color="#C62828")

    def _on_save(self):
        """設定を保存"""
        from llm_factory import get_llm_factory
        from mcp_manager import get_mcp_manager
        factory = get_llm_factory()
        mcp_mgr = get_mcp_manager()
        
        # 1. LLM設定 ＆ 外部連携の保存
        new_settings = {
            "OPENCODE_API_KEY": self.entry_opencode_key.get().strip(),
            "OPENCODE_BASE_URL": self.entry_opencode_url.get().strip(),
            "OPENCODE_MODEL": self.combo_opencode_model.get().strip(),
            "GOOGLE_API_KEY": self.entry_gemini_key.get().strip(),
            "GEMINI_MODEL": self.combo_gemini_model.get().strip(),
            "LM_STUDIO_BASE_URL": self.entry_lm_url.get().strip(),
            "LM_STUDIO_MODEL": self.combo_lm_model.get().strip(),
            "GOOGLE_CALENDAR_ID": self.entry_google_cal.get().strip(),
            "SLACK_WEBHOOK_URL": self.entry_slack_webhook.get().strip(),
        }
        
        saved_llm = factory.save_settings(new_settings)
        if saved_llm:
            factory.DEFAULT_CONFIGS[factory.current_provider]["default_model"] = new_settings.get(f"{factory.current_provider.value.upper()}_MODEL")

        # 2. MCP設定の保存
        for s_id, var in self.mcp_checkboxes.items():
            mcp_mgr.update_server_status(s_id, var.get())

        self.parent_gui.update_message("⚙ AI設定 ＆ 外部連携（Google/Slack/MCP）を保存・適用しました！")
        self.destroy()


class CalendarWindow(ctk.CTkToplevel):
    """
    レトロ手帳風デザインの統合手帳ウィンドウ（Notebook Window）。
    予定帳（カレンダー）、TODOタスク、およびボスのトリセツ（長期知見）をタブ切り替えで管理します。
    """
    def __init__(self, parent_gui, *args, **kwargs):
        super().__init__(parent_gui.root, *args, **kwargs)
        self.parent_gui = parent_gui
        self.title("ネオ秘書くん - 統合手帳 (Notebook)")
        self.geometry("520x620")
        
        # 色の定義（DESIGN_SPEC準拠）
        self.bg_color = "#F5F5DC"      # クリーム色
        self.primary_color = "#A67B5B" # ブラウン
        self.text_color = "#4A3B32"    # ダークブラウン
        
        self.configure(fg_color=self.bg_color)
        
        # フォント設定
        self.font_title = ("DotGothic16", 16, "bold") if "DotGothic16" in tk.font.families() else ("Meiryo UI", 14, "bold")
        self.font_body = ("DotGothic16", 13) if "DotGothic16" in tk.font.families() else ("Meiryo UI", 11)
        self.font_small = ("Meiryo UI", 9)
        
        self._build_ui()
        self.refresh_all_data()

    def _build_ui(self):
        # 1. ヘッダー領域
        self.header_frame = ctk.CTkFrame(self, fg_color=self.primary_color, corner_radius=0, height=45)
        self.header_frame.pack(side="top", fill="x")
        self.header_frame.pack_propagate(False)
        
        self.title_label = ctk.CTkLabel(
            self.header_frame, 
            text="📔 秘書くんの統合手帳", 
            font=self.font_title, 
            text_color="#FFFFFF"
        )
        self.title_label.pack(pady=8)
        
        # 2. タブビュー（カレンダー / TODO / ボスのトリセツ）
        self.tabview = ctk.CTkTabview(
            self, 
            fg_color=self.bg_color,
            segmented_button_selected_color=self.primary_color,
            segmented_button_selected_hover_color="#8B634A",
            segmented_button_unselected_color="#E0D8C8",
            segmented_button_unselected_hover_color="#D5CBB8",
            text_color=self.text_color
        )
        self.tabview.pack(fill="both", expand=True, padx=12, pady=(5, 10))
        
        self.tab_events = self.tabview.add("📅 予定")
        self.tab_tasks = self.tabview.add("📋 TODO")
        self.tab_insights = self.tabview.add("🧠 ボスのトリセツ")
        
        self._build_events_tab()
        self._build_tasks_tab()
        self._build_insights_tab()

    # =========================================================================
    # 📅 予定タブ
    # =========================================================================
    def _build_events_tab(self):
        # 表示期間切り替えバー (月間 / 週間 / 日間)
        view_bar = ctk.CTkFrame(self.tab_events, fg_color="transparent")
        view_bar.pack(fill="x", padx=5, pady=(2, 6))

        self.event_view_seg = ctk.CTkSegmentedButton(
            view_bar,
            values=["🗓️ 月間 (30日)", "📅 週間 (7日)", "☀️ 日間 (今日)"],
            selected_color=self.primary_color,
            selected_hover_color="#8B634A",
            unselected_color="#E0D8C8",
            unselected_hover_color="#D5CBB8",
            text_color=self.text_color,
            font=("Meiryo UI", 9.5, "bold"),
            command=self._on_event_view_change
        )
        self.event_view_seg.set("🗓️ 月間 (30日)")
        self.event_view_seg.pack(side="left")

        # スクロール領域
        self.events_scroll = ctk.CTkScrollableFrame(self.tab_events, fg_color="transparent")
        self.events_scroll.pack(fill="both", expand=True, padx=5, pady=2)

    def _on_event_view_change(self, value):
        self.load_events(getattr(self, 'all_cached_events', []))

    def load_events(self, events: list):
        """予定一覧を描画（月間・週間・日間に対応）"""
        self.all_cached_events = events
        for widget in self.events_scroll.winfo_children():
            widget.destroy()
            
        if not events:
            lbl = ctk.CTkLabel(self.events_scroll, text="予定はありません。", font=self.font_body, text_color="#8D6E63")
            lbl.pack(pady=30)
            return
            
        import datetime
        from collections import defaultdict
        
        now = datetime.datetime.now()
        start_of_today = datetime.datetime(now.year, now.month, now.day)
        mode = self.event_view_seg.get() if hasattr(self, 'event_view_seg') else "🗓️ 月間 (30日)"

        filtered_events = []
        for e in events:
            dt = datetime.datetime.fromtimestamp(e.start_time / 1000)
            if "日間" in mode:
                if dt.date() == now.date():
                    filtered_events.append(e)
            elif "週間" in mode:
                week_end = start_of_today + datetime.timedelta(days=7)
                if start_of_today <= dt < week_end:
                    filtered_events.append(e)
            else:
                filtered_events.append(e)

        if not filtered_events:
            period_name = "今日" if "日間" in mode else ("今週" if "週間" in mode else "今月")
            lbl = ctk.CTkLabel(self.events_scroll, text=f"{period_name}の予定はありません ☕", font=self.font_body, text_color="#8D6E63")
            lbl.pack(pady=30)
            return

        grouped = defaultdict(list)
        for e in filtered_events:
            dt = datetime.datetime.fromtimestamp(e.start_time / 1000)
            date_str = dt.strftime("%Y年%m月%d日 (%a)")
            grouped[date_str].append((e, dt))
            
        for date_str, daily_events in sorted(grouped.items(), key=lambda x: x[1][0][1]):
            date_lbl = ctk.CTkLabel(self.events_scroll, text=f"■ {date_str}", font=self.font_title, text_color=self.primary_color, anchor="w")
            date_lbl.pack(fill="x", pady=(10, 3))
            
            for e, dt in daily_events:
                end_dt = datetime.datetime.fromtimestamp(e.end_time / 1000)
                time_range = f"{dt.strftime('%H:%M')} ~ {end_dt.strftime('%H:%M')}"
                
                card = ctk.CTkFrame(self.events_scroll, fg_color="#FFFFFF", border_color="#E0D8C8", border_width=1, corner_radius=6)
                card.pack(fill="x", pady=3, padx=2)
                
                header_box = ctk.CTkFrame(card, fg_color="transparent")
                header_box.pack(fill="x", padx=8, pady=(4, 0))
                
                ctk.CTkLabel(header_box, text=time_range, font=self.font_small, text_color="#8B634A").pack(side="left")
                
                ctk.CTkLabel(card, text=e.title, font=self.font_body, text_color=self.text_color, anchor="w", wraplength=420).pack(fill="x", padx=8, pady=(1, 2))
                
                if getattr(e, 'description', None):
                    ctk.CTkLabel(card, text=e.description, font=self.font_small, text_color="#7A6B62", anchor="w", wraplength=420).pack(fill="x", padx=8, pady=(0, 4))


    # =========================================================================
    # 📋 TODOタスクタブ
    # =========================================================================
    def _build_tasks_tab(self):
        # タスククイック追加バー
        add_bar = ctk.CTkFrame(self.tab_tasks, fg_color="transparent")
        add_bar.pack(fill="x", padx=5, pady=(5, 8))
        
        self.task_entry_var = tk.StringVar()
        self.task_entry = ctk.CTkEntry(
            add_bar,
            textvariable=self.task_entry_var,
            placeholder_text="新しいタスクを入力してEnter...",
            font=self.font_body,
            fg_color="#FFFFFF",
            border_color="#A67B5B",
            height=32
        )
        self.task_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.task_entry.bind("<Return>", self._on_add_quick_task)
        
        btn_add = ctk.CTkButton(
            add_bar,
            text="追加",
            width=60,
            height=32,
            font=self.font_body,
            fg_color=self.primary_color,
            hover_color="#8B634A",
            command=self._on_add_quick_task
        )
        btn_add.pack(side="right")
        
        # タスクリストスクロール領域
        self.tasks_scroll = ctk.CTkScrollableFrame(self.tab_tasks, fg_color="transparent")
        self.tasks_scroll.pack(fill="both", expand=True, padx=5, pady=5)

    def _on_add_quick_task(self, event=None):
        """クイックタスク登録"""
        text = self.task_entry_var.get().strip()
        if not text:
            return
        self.task_entry_var.set("")
        
        import database
        task = database.Task(title=text, priority=0)
        database.create_task(task)
        self.refresh_tasks()

    def refresh_tasks(self):
        """TODOタスク一覧を再描画"""
        for widget in self.tasks_scroll.winfo_children():
            widget.destroy()
            
        import database
        import datetime
        tasks = database.get_tasks(status="todo", limit=50)
        
        if not tasks:
            lbl = ctk.CTkLabel(self.tasks_scroll, text="すべてのタスクが完了しています！✨", font=self.font_body, text_color="#2E7D32")
            lbl.pack(pady=30)
            return
            
        pri_colors = {3: "#D32F2F", 2: "#F57C00", 1: "#388E3C", 0: "#757575"}
        pri_labels = {3: "🔥 高", 2: "中", 1: "低", 0: ""}
        
        for t in tasks:
            row = ctk.CTkFrame(self.tasks_scroll, fg_color="#FFFFFF", border_color="#E0D8C8", border_width=1, corner_radius=6)
            row.pack(fill="x", pady=3, padx=2)
            
            # 完了チェックボックス
            def make_complete_cb(task_id=t.id):
                return lambda: self._on_complete_task(task_id)
                
            cb = ctk.CTkCheckBox(
                row,
                text="",
                width=24,
                checkbox_width=20,
                checkbox_height=20,
                fg_color=self.primary_color,
                command=make_complete_cb(t.id)
            )
            cb.pack(side="left", padx=(8, 4), pady=6)
            
            # タイトル
            ctk.CTkLabel(row, text=t.title, font=self.font_body, text_color=self.text_color, anchor="w", wraplength=340).pack(side="left", fill="x", expand=True, padx=4)
            
            # 優先度バッジ
            if t.priority > 0:
                pri_lbl = ctk.CTkLabel(
                    row,
                    text=pri_labels.get(t.priority, ""),
                    font=self.font_small,
                    text_color=pri_colors.get(t.priority, "#757575")
                )
                pri_lbl.pack(side="right", padx=(2, 8))

    def _on_complete_task(self, task_id: int):
        """タスクを完了にしてリフレッシュ"""
        import database
        database.complete_task(task_id)
        self.after(200, self.refresh_tasks)

    # =========================================================================
    # 🧠 ボスのトリセツ（長期知見）タブ
    # =========================================================================
    def _build_insights_tab(self):
        self.insights_scroll = ctk.CTkScrollableFrame(self.tab_insights, fg_color="transparent")
        self.insights_scroll.pack(fill="both", expand=True, padx=5, pady=5)

    def refresh_insights(self):
        """ボスの知見一覧を再描画"""
        for widget in self.insights_scroll.winfo_children():
            widget.destroy()
            
        import database
        insights = database.get_user_insights(limit=30)
        
        if not insights:
            lbl = ctk.CTkLabel(self.insights_scroll, text="まだボスの知見は記録されていません。\n秘書くんに生活リズムや好みを教えてみてください！", font=self.font_body, text_color="#8D6E63")
            lbl.pack(pady=30)
            return
            
        cat_labels = {
            "Constraint": ("⛔ 制約", "#D32F2F"),
            "Preference": ("⭐ 好み", "#1976D2"),
            "Habit": ("⏰ 習慣", "#388E3C"),
            "Project": ("📁 PJルール", "#7B1FA2")
        }
        
        for ins in insights:
            card = ctk.CTkFrame(self.insights_scroll, fg_color="#FFFFFF", border_color="#E0D8C8", border_width=1, corner_radius=6)
            card.pack(fill="x", pady=3, padx=2)
            
            top_bar = ctk.CTkFrame(card, fg_color="transparent")
            top_bar.pack(fill="x", padx=8, pady=(4, 0))
            
            cat_name, cat_col = cat_labels.get(ins.category, ("知見", "#757575"))
            ctk.CTkLabel(top_bar, text=cat_name, font=self.font_small, text_color=cat_col).pack(side="left")
            ctk.CTkLabel(top_bar, text=f"重要度: {'★' * ins.importance}", font=self.font_small, text_color="#F57C00").pack(side="left", padx=8)
            
            # 削除ボタン
            def make_delete_cb(ins_id=ins.id):
                return lambda: self._on_delete_insight(ins_id)
                
            btn_del = ctk.CTkButton(
                top_bar, 
                text="🗑", 
                width=24, 
                height=20, 
                font=self.font_small,
                fg_color="transparent",
                text_color="#BDBDBD",
                hover_color="#FFEBEE",
                command=make_delete_cb(ins.id)
            )
            btn_del.pack(side="right")
            
            ctk.CTkLabel(card, text=ins.content, font=self.font_body, text_color=self.text_color, anchor="w", wraplength=420).pack(fill="x", padx=8, pady=(2, 6))

    def _on_delete_insight(self, insight_id: int):
        import database
        database.delete_user_insight(insight_id)
        self.refresh_insights()

    def refresh_all_data(self):
        """全タブのデータを一括更新"""
        import database
        events = database.get_upcoming_events(days=30)
        self.load_events(events)
        self.refresh_tasks()
        self.refresh_insights()

    def show_error(self, message: str):
        """データがない場合などのメッセージ表示"""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        lbl = ctk.CTkLabel(self.scrollable_frame, text=message, font=self.font_body, text_color=self.text_color)
        lbl.pack(pady=30)


class StickyNoteWindow(tk.Toplevel):
    """
    デスクトップに常駐する付箋（Sticky Note）ウィンドウ
    """
    def __init__(self, parent_gui, note):
        super().__init__(parent_gui.root)
        self.note = note
        
        # タイトルバーを隠して付箋っぽくする
        self.overrideredirect(True)
        # 常に最前面表示
        self.attributes('-topmost', True)
        
        # 背景色の設定
        self.bg_color = note.color if note.color else "#FFEB3B"
        self.configure(bg=self.bg_color)
        
        # DBに保存された位置とサイズを適用
        self.geometry(f"{note.width}x{note.height}+{note.position_x}+{note.position_y}")
        
        font_style = ("DotGothic16", 12) if "DotGothic16" in tk.font.families() else ("Meiryo UI", 11)
        
        # ドラッグして移動できるようにするためのヘッダー領域（少し濃い色）
        self.header = tk.Frame(self, bg="#E6D235", height=15, cursor="fleur")
        self.header.pack(fill=tk.X)
        self.header.bind("<ButtonPress-1>", self._start_move)
        self.header.bind("<B1-Motion>", self._do_move)
        
        # 閉じるボタン（DBからも削除する）
        close_btn = tk.Label(self.header, text="✖", bg="#E6D235", fg="#4A3B32", cursor="hand2", font=("Arial", 8))
        close_btn.pack(side=tk.RIGHT, padx=5)
        close_btn.bind("<Button-1>", self._on_close)
        
        # 本文の表示（編集可能なTextウィジェットに変更）
        self.textbox = tk.Text(
            self, 
            bg=self.bg_color,
            fg="#4A3B32",
            font=font_style,
            wrap=tk.WORD,
            bd=0, # 枠線なし
            highlightthickness=0 # フォーカス時の枠線なし
        )
        self.textbox.insert("1.0", note.content)
        self.textbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        
        # フォーカスが外れたタイミングでDBを更新する設定
        self.textbox.bind("<FocusOut>", self._save_content)
        
        # 入力中フラグ
        self.is_editing = False
        self.textbox.bind("<FocusIn>", lambda e: setattr(self, 'is_editing', True))

    def _save_content(self, event=None):
        """テキストの変更をDBに保存する"""
        self.is_editing = False
        new_content = self.textbox.get("1.0", tk.END).strip()
        if new_content != self.note.content:
            self.note.content = new_content
            import database
            try:
                database.update_sticky_note(self.note)
            except Exception as e:
                logger.error(f"付箋の保存に失敗: {e}")

    def _on_close(self, event):
        """付箋を閉じる際の処理。DBから完全に削除する"""
        import database
        try:
            database.delete_sticky_note(self.note.id)
            self.destroy()
        except Exception as e:
            logger.error(f"付箋の削除に失敗: {e}")

    def _start_move(self, event):
        self.x = event.x
        self.y = event.y

    def _do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")
        
        # 移動後位置をノートオブジェクトに記憶 (保存はFocusOutや終了時に行うなど工夫が可能だが、現状はメモリ上のみ更新しておく)
        self.note.position_x = x
        self.note.position_y = y


class NeoSecretaryGUI:
    def __init__(self):
        # 1. メインウィンドウの設定 (スマートコックピット 2.0)
        self.root = ctk.CTk()
        self.root.title("ネオ秘書くん")
        
        # ウィンドウサイズと位置の設定（画面右下付近）
        window_width = 340
        window_height = 440
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # 右下から少し浮かせた位置に配置
        x_pos = screen_width - window_width - 40
        y_pos = screen_height - window_height - 80
        self.root.geometry(f"{window_width}x{window_height}+{x_pos}+{y_pos}")
        
        # 常に最前面に表示
        self.root.attributes('-topmost', True)
        
        # 背景透過の検証 (Windows環境での透過色設定)
        transparent_color = "#FF00FF"
        self.root.config(bg=transparent_color)
        self.root.attributes('-transparentcolor', transparent_color)
        
        # タイトルバーを消して完全なフローティングウィンドウにする
        self.root.overrideredirect(True)

        # スレッドセーフなアクションキュー
        self._action_queue = queue.Queue()

        # UI要素の構築
        self._build_ui(transparent_color)
        self._bind_events()

    def post_action(self, func, *args):
        """別スレッド（HTTPサーバー等）から安全にメインGUIスレッドへ処理をキューイング"""
        self._action_queue.put((func, args))

    def process_action_queue(self):
        """メインループ内で定期的にキューを安全に消化"""
        while not self._action_queue.empty():
            try:
                func, args = self._action_queue.get_nowait()
                func(*args)
            except Exception as e:
                logger.error(f"Action Queue 実行エラー: {e}")

    def _build_ui(self, transparent_color: str):
        """UIコンポーネント（キャラクター画像、吹き出し、入力欄）の構築"""
        
        # 全体のコンテナ（透過色）
        self.main_container = tk.Frame(self.root, bg=transparent_color)
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # -------------------------------------------------------------
        # 吹き出し部分 (Speech Bubble)
        # -------------------------------------------------------------
        self.bubble_frame = ctk.CTkFrame(
            self.main_container,
            fg_color="#FFFFFF",      # 白背景
            border_width=2,          # 枠線
            border_color="#4A3B32",  # ダークブラウン
            corner_radius=4
        )
        self.bubble_frame.pack(side=tk.TOP, pady=(10, 0), padx=15, fill=tk.X)

        # 吹き出し上部ヘッダー（タイトル＆⚙メニューボタン）
        self.bubble_header = ctk.CTkFrame(
            self.bubble_frame,
            fg_color="#F5F5DC",      # クリーム色ヘッダー
            corner_radius=0,
            height=26
        )
        self.bubble_header.pack(fill=tk.X, side=tk.TOP)
        self.bubble_header.pack_propagate(False)

        # ヘッダー左側: キャラクター名ラベル
        header_font = ("DotGothic16", 12, "bold") if "DotGothic16" in tk.font.families() else ("Meiryo UI", 10, "bold")
        self.header_title = ctk.CTkLabel(
            self.bubble_header,
            text="🤖 ネオ秘書くん",
            font=header_font,
            text_color="#A67B5B"
        )
        self.header_title.pack(side=tk.LEFT, padx=(8, 0))

        # ヘッダー右側: 📔 手帳ボタン ＆ ⚙ メニューボタン
        self.menu_btn = ctk.CTkButton(
            self.bubble_header,
            text="⚙",
            width=22,
            height=20,
            font=("Meiryo UI", 11),
            fg_color="transparent",
            text_color="#A67B5B",
            hover_color="#E0D8C8",
            command=self._show_menu_from_btn
        )
        self.menu_btn.pack(side=tk.RIGHT, padx=4)

        self.btn_open_calendar = ctk.CTkButton(
            self.bubble_header,
            text="📔 手帳",
            width=50,
            height=20,
            font=("Meiryo UI", 9, "bold"),
            fg_color="#A67B5B",
            text_color="#FFFFFF",
            hover_color="#8B634A",
            corner_radius=3,
            command=self._open_calendar
        )
        self.btn_open_calendar.pack(side=tk.RIGHT, padx=2)


        # 吹き出し本文のテキスト表示用
        font_style = ("DotGothic16", 13) if "DotGothic16" in tk.font.families() else ("Meiryo UI", 11)
        self.message_box = ctk.CTkTextbox(
            self.bubble_frame,
            font=font_style,
            text_color="#4A3B32",
            fg_color="#FFFFFF",
            border_width=0,
            corner_radius=0,
            wrap="word",
            height=140,              # 高さを140pxに固定して下部UIを死守
            activate_scrollbars=True
        )
        self.message_box.pack(pady=(4, 6), padx=8, fill=tk.BOTH, expand=True)
        self.message_box.insert("1.0", "おはようございます！\n本日のご予定はいかがなさいますか？")
        self.message_box.configure(state="disabled")

        # -------------------------------------------------------------
        # ユーザー入力欄 (Entry)
        # -------------------------------------------------------------
        self.input_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.input_frame.pack(side=tk.TOP, pady=(5, 5), padx=15, fill=tk.X)
        
        self.entry_var = tk.StringVar()
        self.input_entry = ctk.CTkEntry(
            self.input_frame, 
            textvariable=self.entry_var,
            placeholder_text="秘書くんに指示する...",
            font=font_style,
            text_color="#4A3B32",
            fg_color="#F5F5DC",
            border_color="#A67B5B",
            height=32
        )
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))


        # -------------------------------------------------------------
        # 6. キャラクター画像 ＆ サークルメニュー (Radial Action Menu)
        # -------------------------------------------------------------
        self.char_container = tk.Frame(self.main_container, bg=transparent_color, width=340, height=210)
        self.char_container.pack(side=tk.BOTTOM, pady=(0, 2))
        self.char_container.pack_propagate(False)

        self.char_canvas = tk.Canvas(
            self.char_container, 
            width=340, 
            height=210, 
            bg=transparent_color,
            highlightthickness=0,
            cursor="hand2"
        )
        self.char_canvas.pack(fill=tk.BOTH, expand=True)

        # サークルメニュー用ボタン群
        self.circle_menu_active = False
        self.circle_menu_buttons = []
        self._build_radial_menu()
        
        # ドット絵アセットのロードとアニメーション初期化 (Pixel Art 2.0 & PetAnimator)
        from pet_animator import PetAnimator
        self.animator = PetAnimator(on_frame_change=self._render_mascot)
        self.pet_state = "idle"
        self.anim_tick = 0
        self.mascot_images: Dict[str, ImageTk.PhotoImage] = {}
        self.mascot_img_item = None
        
        # 視線追従用の追跡変数
        self.last_mouse_dir = "center"
        self.is_hovered = False
        
        # ポモドーロタイマー管理変数
        self.pomodoro_active = False
        self.pomodoro_remaining_seconds = 0
        self.pomodoro_is_break = False
        
        self._load_mascot_assets()
        self._render_mascot("idle_1")
        self._schedule_animation()

    def _build_radial_menu(self):
        """サークルメニューのボタン群を構築（広々とした半径100px配置）"""
        btn_configs = [
            {"icon": "📔", "cmd": self._on_circle_calendar, "color": "#A67B5B", "dx": -100, "dy": 5, "title": "📔 統合手帳（予定・TODO・知見）", "desc": "カレンダー・TODOタスク・知見ノートを開きます。"},
            {"icon": "🍅", "cmd": self._on_circle_pomodoro, "color": "#E53935", "dx": -72, "dy": -70, "title": "🍅 ポモドーロ集中タイマー", "desc": "25分間の集中タイマーを開始/停止します。"},
            {"icon": "📱", "cmd": self._on_circle_mobile, "color": "#5B8A72", "dx": 0, "dy": -100, "title": "📱 スマホDesk Pet接続", "desc": "スマホ画面と連携するQRコードを表示します。"},
            {"icon": "💡", "cmd": self._on_circle_suggest, "color": "#F57F17", "dx": 72, "dy": -70, "title": "💡 サジェストソース設定", "desc": "予定やTODOの自動サジェスト項目を設定します。"},
            {"icon": "⚙", "cmd": self._on_circle_settings, "color": "#7A6B62", "dx": 100, "dy": 5, "title": "⚙ アプリ・LLM設定", "desc": "AIモデルやAPIキー、連携設定を開きます。"}
        ]
        
        self.circle_menu_buttons = []
        for cfg in btn_configs:
            btn = ctk.CTkButton(
                self.char_container,
                text=cfg["icon"],
                width=36,
                height=36,
                corner_radius=18,
                font=("Meiryo UI", 14, "bold"),
                fg_color=cfg["color"],
                hover_color="#2E1C14",
                command=cfg["cmd"]
            )
            # マウスホバーで吹き出しに機能名と説明を表示
            btn.bind("<Enter>", lambda e, title=cfg["title"], desc=cfg["desc"]: self._on_circle_btn_hover(title, desc))
            btn.bind("<Leave>", lambda e: self._on_circle_btn_leave())
            self.circle_menu_buttons.append({"btn": btn, "dx": cfg["dx"], "dy": cfg["dy"]})

    def _on_circle_btn_hover(self, title: str, desc: str):
        """サークルボタンホバー時に吹き出しへ詳細説明を表示"""
        if self.circle_menu_active:
            self.update_message(f"【{title}】\n{desc}")

    def _on_circle_btn_leave(self):
        """マウスが離れた時に吹き出しを戻す"""
        if self.circle_menu_active:
            self.update_message("えへへ、くすぐったいです！🥰\nボス、呼び出したい機能を選んでくださいね！")

    def toggle_circle_menu(self):
        """サークルメニューの展開/収納アニメーションをトグル"""
        if self.circle_menu_active:
            self._animate_circle_menu(step=4, forward=False)
        else:
            self._animate_circle_menu(step=1, forward=True)

    def _animate_circle_menu(self, step: int, forward: bool):
        """放射状アニメーションのステップ進行"""
        cx, cy = 170, 135
        max_steps = 4
        progress = step / float(max_steps)

        if forward:
            self.circle_menu_active = True
            for item in self.circle_menu_buttons:
                btn = item["btn"]
                x = int(cx + item["dx"] * progress - 18)
                y = int(cy + item["dy"] * progress - 18)
                btn.place(x=x, y=y)
                btn.lift()
            
            if step < max_steps:
                self.root.after(20, lambda: self._animate_circle_menu(step + 1, forward=True))
        else:
            for item in self.circle_menu_buttons:
                btn = item["btn"]
                x = int(cx + item["dx"] * progress - 18)
                y = int(cy + item["dy"] * progress - 18)
                btn.place(x=x, y=y)
            
            if step > 0:
                self.root.after(20, lambda: self._animate_circle_menu(step - 1, forward=False))
            else:
                self.circle_menu_active = False
                for item in self.circle_menu_buttons:
                    item["btn"].place_forget()

    def _on_circle_calendar(self):
        self.toggle_circle_menu()
        self._open_calendar()

    def _on_circle_pomodoro(self):
        self.toggle_circle_menu()
        if self.pomodoro_active:
            self.stop_pomodoro()
        else:
            self.start_pomodoro(25)

    def _on_circle_mobile(self):
        self.toggle_circle_menu()
        self._open_qr_connection()

    def _on_circle_suggest(self):
        self.toggle_circle_menu()
        SuggestSettingsDialog(self)

    def _on_circle_settings(self):
        self.toggle_circle_menu()
        self._open_settings()





    def _load_mascot_assets(self):
        """ドット絵スプライト画像をロード（存在しない場合は自動生成）"""
        assets_dir = Path(__file__).parent / "assets"
        all_sprites = [
            # 基本・視線
            "idle_1", "idle_2",
            "look_left", "look_right", "look_up", "look_down",
            # 思考・リアクション
            "thinking_1", "thinking_2",
            "happy",
            "focus_1", "focus_2",
            "sleepy_1", "sleepy_2",
            "alarm_ask",
            "pet_love",
            "cheer",
            # 新規自律モーション (Idle Actions)
            "tea_1", "tea_2",
            "reading_1", "reading_2",
            "stretch_1", "stretch_2",
            # 新規共感リアクション (Context Reactions)
            "celebrate_1", "celebrate_2", "celebrate_3",
            "care_1", "care_2",
            "night_1", "night_2"
        ]
        
        # 欠損ファイルがあれば自動生成
        missing = [f"{s}.png" for s in all_sprites if not (assets_dir / f"{s}.png").exists()]
        if missing:
            try:
                import generate_mascot_assets
                generate_mascot_assets.main()
            except Exception as e:
                logger.error(f"マスコットアセット自動生成エラー: {e}")

        # 全画像の読み込み
        for name in all_sprites:
            p = assets_dir / f"{name}.png"
            if p.exists():
                try:
                    pil_img = Image.open(p)
                    self.mascot_images[name] = ImageTk.PhotoImage(pil_img)
                except Exception as e:
                    logger.error(f"画像ロード失敗 ({p}): {e}")

    def _render_mascot(self, frame_name: str):
        """Canvas 上のマスコット画像を更新描画"""
        img = self.mascot_images.get(frame_name)
        if img:
            if self.mascot_img_item is None:
                self.mascot_img_item = self.char_canvas.create_image(170, 135, image=img)
            else:
                self.char_canvas.coords(self.mascot_img_item, 170, 135)
                self.char_canvas.itemconfig(self.mascot_img_item, image=img)
        else:
            # フォールバック描画
            self.char_canvas.delete("fallback")
            self.char_canvas.create_oval(120, 85, 220, 185, fill="#A67B5B", outline="#4A3B32", width=3, tags="fallback")
            self.char_canvas.create_text(170, 135, text="秘書くん", fill="#FFFFFF", font=("Meiryo UI", 12, "bold"), tags="fallback")

    def _schedule_animation(self):
        """アニメーションの定期実行ループ (PetAnimator 連携による自律＆共感アニメーション)"""
        self.anim_tick += 1
        delay = 350
        
        # 1. ポモドーロタイマーカウント処理
        if self.pomodoro_active and self.pomodoro_remaining_seconds > 0:
            if self.anim_tick % 2 == 0:
                self.pomodoro_remaining_seconds -= 1
                mins = self.pomodoro_remaining_seconds // 60
                secs = self.pomodoro_remaining_seconds % 60
                mode_label = "☕ 休憩" if self.pomodoro_is_break else "🍅 集中"
                if hasattr(self, 'header_title') and self.header_title.winfo_exists():
                    self.header_title.configure(text=f"🤖 ネオ秘書くん [{mode_label} {mins:02d}:{secs:02d}]")
                
                if self.pomodoro_remaining_seconds <= 0:
                    self._on_pomodoro_completed()

        # 2. カーソルホバー時のなでなで優先処理
        if self.is_hovered and self.animator.current_state == "idle":
            self._render_mascot("happy")
            delay = 300
        elif self.last_mouse_dir in ("left", "right", "up", "down") and self.animator.current_state == "idle" and not self.is_hovered:
            # 待機中かつマウス移動時は視線追従
            self._render_mascot(f"look_{self.last_mouse_dir}")
            delay = 350
        else:
            # 3. PetAnimatorによるフレーム進行（お茶、読書、ストレッチ、タスク完了ジャンプ等）
            frame_name = self.animator.tick()
            self._render_mascot(frame_name)

        # 📱 スマホ接続時のPCペット自動最小化チェック (withdraw で完全非表示)
        if getattr(self, 'auto_minimize_on_link', False):
            try:
                from local_sync_server import get_link_monitor
                is_linked = get_link_monitor().is_connected()
                if is_linked and not getattr(self, '_was_linked_minimized', False):
                    self._was_linked_minimized = True
                    logger.info("📱 スマホ接続を検知: PC画面占有ゼロ化のためPCペットを非表示(withdraw)にします")
                    self.root.withdraw()
                elif not is_linked and getattr(self, '_was_linked_minimized', False):
                    self._was_linked_minimized = False
                    logger.info("📱 スマホ切断を検知: PCペットを再表示(deiconify)します")
                    self.root.deiconify()
            except Exception:
                pass

        # 次のフレームを予約 (単一タイマー)
        self.root.after(delay, self._schedule_animation)


    def toggle_auto_minimize(self):
        """スマホ接続時の自動最小化設定をトグル"""
        self.auto_minimize_on_link = not getattr(self, 'auto_minimize_on_link', False)
        status_str = "有効" if self.auto_minimize_on_link else "無効"
        
        if self.auto_minimize_on_link:
            try:
                from local_sync_server import get_link_monitor
                if get_link_monitor().is_connected():
                    self._was_linked_minimized = True
                    self.root.withdraw()
                    return
            except Exception:
                pass
        else:
            self._was_linked_minimized = False
            self.root.deiconify()
            
        self.update_message(f"📱 スマホ接続時のPCペット自動最小化を【{status_str}】にしました！")

    def show_pc_pet(self):
        """非表示になっているPCペットを画面に再表示"""
        self._was_linked_minimized = False
        self.root.deiconify()
        self.root.lift()
        self.update_message("ボス！PC画面に戻ってきました！✨")

    def set_pet_state(self, state: str, duration_ms: int = 0):
        """
        ペットの状態を変更します（PetAnimator 連携）。
        
        Args:
            state: 'idle', 'thinking', 'happy', 'focus', 'sleepy', 'alarm_ask', 'pet_love', 'cheer', 'celebrate', 'care', 'tea', 'reading', 'stretch', 'night'
            duration_ms: 指定ミリ秒後に自動で 'idle' に戻す（0なら維持）
        """
        self.pet_state = state
        self.anim_tick = 0
        dur_sec = duration_ms / 1000.0 if duration_ms > 0 else 0.0
        
        if hasattr(self, 'animator'):
            self.animator.set_state(state, duration_sec=dur_sec)
        else:
            self._render_mascot(state if state in self.mascot_images else "idle_1")


    # =========================================================================
    # 🍅 ポモドーロタイマー機能
    # =========================================================================
    def start_pomodoro(self, work_minutes: int = 25):
        """ポモドーロ集中タイマーを開始"""
        self.pomodoro_active = True
        self.pomodoro_is_break = False
        self.pomodoro_remaining_seconds = work_minutes * 60
        self.set_pet_state("focus")
        self.update_message(f"🍅 ポモドーロ集中モードを開始しました！（{work_minutes}分間）\nボス、一緒に集中してやり切りましょう！🔥")

    def _on_pomodoro_completed(self):
        """ポモドーロまたは休憩の完了時処理"""
        if not self.pomodoro_is_break:
            # 集中作業終了 ➔ 5分休憩へ
            self.pomodoro_is_break = True
            self.pomodoro_remaining_seconds = 5 * 60
            self.set_pet_state("cheer", duration_ms=4000)
            self.update_message("🎉 25分間の集中作業、大変お疲れさまでした！✨\n5分間のリフレッシュ休憩に入りましょう🍵 伸びをしてくださいね！")
        else:
            # 休憩終了
            self.pomodoro_active = False
            if hasattr(self, 'header_title') and self.header_title.winfo_exists():
                self.header_title.configure(text="🤖 ネオ秘書くん")
            self.set_pet_state("happy", duration_ms=3000)
            self.update_message("⏰ 休憩時間が終了しました！\n次の作業に向けて準備ができたらお声がけください！💪")

    def stop_pomodoro(self):
        """ポモドーロタイマーを停止"""
        self.pomodoro_active = False
        self.pomodoro_remaining_seconds = 0
        if hasattr(self, 'header_title') and self.header_title.winfo_exists():
            self.header_title.configure(text="🤖 ネオ秘書くん")
        self.set_pet_state("idle")
        self.update_message("ポモドーロタイマーを終了しました。")



    # =========================================================================
    # 🖱️ マウスイベント ＆ 触感インタラクション
    # =========================================================================
    def _bind_events(self):
        """マウスイベント（ドラッグ移動、視線追従、なでなで、右クリックメニュー）のバインド"""
        
        # ドラッグ移動
        self.char_canvas.bind("<ButtonPress-1>", self._on_pet_click)
        self.char_canvas.bind("<B1-Motion>", self._do_move)
        self.char_canvas.bind("<ButtonRelease-1>", self._on_pet_release)
        
        # ホバー触感 ＆ 視線追跡
        self.char_canvas.bind("<Enter>", self._on_mouse_enter)
        self.char_canvas.bind("<Leave>", self._on_mouse_leave)
        self.char_canvas.bind("<Motion>", self._on_mouse_motion)
        self.root.bind("<Motion>", self._on_window_motion)
        
        # 右クリック
        self.char_canvas.bind("<Button-3>", self._show_context_menu)
        self.char_canvas.tag_bind("all", "<Button-3>", self._show_context_menu)
        
        # サブウィンドウ管理
        self.calendar_window = None
        self.settings_window = None
        self.sticky_windows = {}

    def _on_mouse_enter(self, event):
        """カーソルがペットに乗った時の触感反応"""
        self.is_hovered = True

    def _on_mouse_leave(self, event):
        """カーソルが離れた時の反応"""
        self.is_hovered = False
        self.last_mouse_dir = "center"

    def _on_mouse_motion(self, event):
        """キャンバス内でのマウス位置から視線方向を計算"""
        cx, cy = 70, 70
        dx = event.x - cx
        dy = event.y - cy
        
        if abs(dx) > abs(dy):
            self.last_mouse_dir = "left" if dx < -15 else ("right" if dx > 15 else "center")
        else:
            self.last_mouse_dir = "up" if dy < -15 else ("down" if dy > 15 else "center")

    def _on_window_motion(self, event):
        """ウィンドウ全体でのマウス視線追跡"""
        if not self.is_hovered and self.pet_state == "idle":
            # キャンバスの相対位置を計算
            canv_x = self.char_canvas.winfo_x() + 170
            canv_y = self.char_canvas.winfo_y() + 135
            dx = event.x - canv_x
            dy = event.y - canv_y
            
            if abs(dx) > abs(dy):
                self.last_mouse_dir = "left" if dx < -20 else ("right" if dx > 20 else "center")
            else:
                self.last_mouse_dir = "up" if dy < -20 else ("down" if dy > 20 else "center")

    def _on_pet_click(self, event):
        """クリック時のサークルメニュー展開と、なでなでリアクション"""
        self._start_move(event)
        self.toggle_circle_menu()
        if not self.pomodoro_active and self.pet_state in ("idle", "happy"):
            # なでなで触感リアクション（ハートマーク💖）
            self.set_pet_state("pet_love", duration_ms=2500)
            self.update_message("えへへ、くすぐったいです！🥰\nボス、呼び出したい機能を選んでくださいね！")


    def _on_pet_release(self, event):
        """ドラッグ終了"""
        if self.pet_state == "alarm_ask" and not getattr(self, '_waiting_approval', False):
            self.set_pet_state("idle")

    def _build_context_menu(self):
        """最新のプロバイダ・モデル選択状態を反映したメニューを動的に生成"""
        from llm_factory import get_llm_factory
        factory = get_llm_factory()
        
        menu = tk.Menu(self.root, tearoff=0, bg="#F5F5DC", fg="#4A3B32", font=("Meiryo UI", 10))
        menu.add_command(label="📔 統合手帳（予定・TODO・知見）", command=self._open_calendar)
        menu.add_command(label="📱 スマホDesk Pet接続 (QRコード)", command=self._open_qr_connection)
        
        auto_min = getattr(self, 'auto_minimize_on_link', False)
        min_prefix = "☑ " if auto_min else "☐ "
        menu.add_command(label=f"{min_prefix}スマホ接続時にPCペットを自動最小化", command=self.toggle_auto_minimize)
        
        # ポモドーロ開始/停止
        if not self.pomodoro_active:
            menu.add_command(label="🍅 ポモドーロ集中開始 (25分)", command=lambda: self.start_pomodoro(25))
        else:
            menu.add_command(label="⏹ ポモドーロタイマー停止", command=self.stop_pomodoro)
            
        menu.add_separator()
        
        # LLMモデル切り替えサブメニュー
        llm_menu = tk.Menu(menu, tearoff=0, bg="#F5F5DC", fg="#4A3B32", font=("Meiryo UI", 10))
        
        presets = factory.list_presets()
        for p_id, p_info in presets.items():
            p_sub = tk.Menu(llm_menu, tearoff=0, bg="#F5F5DC", fg="#4A3B32", font=("Meiryo UI", 10))
            is_active_prov = p_info["is_current_provider"]
            
            for m in p_info["models"]:
                is_selected = is_active_prov and (m["id"] == factory.current_model_name)
                prefix = "● " if is_selected else "   "
                label = f"{prefix}{m['name']}"
                p_sub.add_command(
                    label=label,
                    command=lambda pid=p_id, mid=m["id"]: self._on_switch_llm(pid, mid)
                )
            
            prov_prefix = "★ " if is_active_prov else "  "
            llm_menu.add_cascade(label=f"{prov_prefix}{p_info['name']}", menu=p_sub)
            
        menu.add_cascade(label="🧠 LLMモデル切り替え", menu=llm_menu)
        menu.add_command(label="💡 サジェストソース設定", command=lambda: SuggestSettingsDialog(self))
        menu.add_command(label="⚙ API・MCP設定", command=self._open_settings)
        menu.add_separator()
        menu.add_command(label="❌ 終了", command=self.root.destroy)
        return menu

    def _open_qr_connection(self):
        """スマホDesk Pet接続用のQRコードダイアログを開く"""
        if getattr(self, 'qr_dialog', None) is None or not self.qr_dialog.winfo_exists():
            self.qr_dialog = QRCodeConnectionDialog(self)
        else:
            self.qr_dialog.focus()

    def _show_menu_from_btn(self):
        """⚙ボタンクリックでメニューを表示"""
        x = self.menu_btn.winfo_rootx()
        y = self.menu_btn.winfo_rooty() + self.menu_btn.winfo_height()
        menu = self._build_context_menu()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _show_context_menu(self, event):
        """右クリックメニューの表示"""
        menu = self._build_context_menu()
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _start_move(self, event):
        """ドラッグ開始時の座標を記憶"""
        self.x = event.x
        self.y = event.y

    def _do_move(self, event):
        """ドラッグ中のウィンドウ移動処理"""
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def _open_settings(self):
        """設定ウィンドウを開く"""
        if self.settings_window is None or not self.settings_window.winfo_exists():
            self.settings_window = SettingsWindow(self)
        else:
            self.settings_window.focus()

    def _on_switch_llm(self, provider_id: str, model_name: str = None):
        """右クリックメニューからLLMプロバイダ・モデルを切り替える"""
        try:
            from llm_factory import get_llm_factory
            factory = get_llm_factory()
            if factory.switch_provider(provider_id, model_name):
                info = factory.DEFAULT_CONFIGS[factory.current_provider]
                self.update_message(f"🧠 頭脳を『{info['name']}』に切り替えました！\nモデル: {factory.current_model_name}")
            else:
                self.update_message("切り替えに失敗しました。")
        except Exception as e:
            logger.error(f"LLM切り替えエラー: {e}")
            self.update_message(f"エラー: {e}")

    def refresh_sticky_notes(self):
        """データベースから付箋を読み込み、表示を更新する"""
        import database
        try:
            notes = database.get_all_sticky_notes()
            active_ids = []
            
            for note in notes:
                if note.is_minimized:
                    continue
                active_ids.append(note.id)
                # 新規作成または再表示
                if note.id not in self.sticky_windows or not self.sticky_windows[note.id].winfo_exists():
                    self.sticky_windows[note.id] = StickyNoteWindow(self, note)
                else:
                    # 既に表示されている場合は内容の更新チェック（ただし編集中はスキップ）
                    win = self.sticky_windows[note.id]
                    if getattr(win, 'is_editing', False):
                        continue
                        
                    if win.note.content != note.content:
                        win.note = note
                        # テキストボックスの内容を書き換える
                        current_status = win.textbox.cget("state")
                        win.textbox.configure(state=tk.NORMAL)
                        win.textbox.delete("1.0", tk.END)
                        win.textbox.insert("1.0", note.content)
                        win.textbox.configure(state=current_status)
            
            # DBから削除・最小化された付箋の画面を掃除する
            for note_id in list(self.sticky_windows.keys()):
                if note_id not in active_ids:
                    win = self.sticky_windows.pop(note_id)
                    if win.winfo_exists():
                        win.destroy()
        except Exception as e:
            logger.error(f"付箋読み込みエラー: {e}")

    def _open_calendar(self):
        """統合手帳ウィンドウを開く"""
        if self.calendar_window is None or not self.calendar_window.winfo_exists():
            self.calendar_window = CalendarWindow(self)
        else:
            self.calendar_window.refresh_all_data()
            self.calendar_window.focus()

    def open_task_calendar_window(self):
        """統合手帳ウィンドウを開く（公開エイリアス）"""
        self._open_calendar()

    def show_pc_pet(self):
        """PC側のペットウィンドウを表示・最前面化する"""
        try:
            self._was_linked_minimized = False
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.update_message("🖥️ スマホからPC画面に呼び出されました！✨")
            self.set_pet_state("happy", duration_ms=3000)
            logger.info("PCペットを画面上に再表示しました")
        except Exception as e:
            logger.error(f"show_pc_pet エラー: {e}")

    def hide_pc_pet(self):
        """PC側のペットウィンドウを非表示（最小化）にする"""
        try:
            self.root.withdraw()
            logger.info("PCペットを非表示にしました")
        except Exception as e:
            logger.error(f"hide_pc_pet エラー: {e}")

    def update_message(self, text: str):
        """吹き出しのメッセージを更新するメソッド（スクロール対応）"""
        self.message_box.configure(state="normal")
        self.message_box.delete("1.0", tk.END)
        self.message_box.insert("1.0", text)
        self.message_box.configure(state="disabled")
        self.message_box.see("1.0")  # 先頭を表示

    def run(self):
        """Tkinterのメインループを開始"""
        logger.info("GUIアプリケーションを開始します")
        self.root.mainloop()

if __name__ == "__main__":
    # ログ設定
    logging.basicConfig(level=logging.INFO)
    
    # 起動テスト
    app = NeoSecretaryGUI()
    app.run()
