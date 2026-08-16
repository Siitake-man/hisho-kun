"""
ネオ秘書くん - QRコード接続ダイアログ (ui/qr_dialog.py)
スマホ専用Desk Pet ＆ 承認コクピットへ接続するためのQRコード生成ダイアログ。
"""

import logging
import socket
import tkinter as tk
import urllib.request
import customtkinter as ctk
from PIL import ImageTk

logger = logging.getLogger(__name__)

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
