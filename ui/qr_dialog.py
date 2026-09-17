"""
ネオ秘書くん - QRコード接続ダイアログ (ui/qr_dialog.py)
スマホ専用Desk Pet ＆ 承認コクピットへ接続するためのQRコード生成ダイアログ。

2026-08-28 改修:
- Tailscale 接続時に HTTPS (Tailscale Serve 必須) と HTTP 直接入力 (設定不要) を両対応
- Tailscale の仮想アダプタ IP (100.64.0.0/10 帯) を ipconfig から確実に検出
- tailscale serve コマンドのコピーボタンを設置
  （ポート番号は sync_config.SERVER_PORT を唯一の情報源とし、ベタ書きしない）
"""

import logging
import os
import re
import socket
import subprocess
import tkinter as tk
import urllib.request
from typing import Dict, List

import customtkinter as ctk
from PIL import ImageTk

from sync_config import SERVER_PORT, build_tailscale_serve_command
from ui.window_icon import apply_window_icon

logger = logging.getLogger(__name__)

# 同期サーバーの待受ポート (ハードコード禁止: sync_config を唯一の情報源とする)
TAILSCALE_HTTP_PORT = SERVER_PORT

# Tailscale Serve のリバースプロキシ起動コマンド（HTTPS モード用）
# フラグ・ポートは sync_config（単一情報源）から導出する（--bg 付きで統一）。
TAILSCALE_SERVE_COMMAND = build_tailscale_serve_command()


def is_tailscale_ip(ip: str) -> bool:
    """Tailscale 仮想アダプタの IPv4 (100.64.0.0/10 帯) かどうかを判定します。

    Args:
        ip: 判定対象の IPv4 アドレス文字列。

    Returns:
        bool: Tailscale 帯 (100.64.x.x 〜 100.127.x.x) の場合 True。
    """
    try:
        parts = [int(x) for x in ip.split(".")]
    except (ValueError, AttributeError):
        return False
    if len(parts) != 4:
        return False
    return parts[0] == 100 and 64 <= parts[1] <= 127


def extract_ipv4_addresses(text: str) -> List[str]:
    """任意のテキスト (ipconfig 出力等) から IPv4 アドレスを抽出します。

    ループバック (127.x) とリンクローカル (169.254.x) は除外します。

    Args:
        text: 検索対象のテキスト。

    Returns:
        List[str]: 抽出した IPv4 アドレスのリスト（重複除去・出現順）。
    """
    found: List[str] = []
    for ip in re.findall(r"(\d{1,3}(?:\.\d{1,3}){3})", text):
        if ip.startswith("127.") or ip.startswith("169.254."):
            continue
        if ip not in found:
            found.append(ip)
    return found


def get_tailscale_ips() -> List[str]:
    """ipconfig を実行し、Tailscale 帯 (100.64.0.0/10) の IPv4 を検出します。

    Windows の ``socket.gethostbyname_ex`` は Tailscale 仮想アダプタの
    アドレスを返さないケースがあるため、ipconfig 出力からの補完で確実性を上げる。

    Returns:
        List[str]: 検出した Tailscale IPv4 アドレス（ソート済み・重複なし）。
    """
    try:
        result = subprocess.run(["ipconfig"], capture_output=True, timeout=5.0)
        raw = result.stdout or b""
        try:
            text = raw.decode("cp932")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="ignore")
        ips = [ip for ip in extract_ipv4_addresses(text) if is_tailscale_ip(ip)]
        return sorted(set(ips))
    except Exception as e:
        logger.warning(f"Tailscale IP の検出に失敗: {e}")
        return []


def build_lan_url(ip: str) -> str:
    """LAN 内の PC への直接接続 URL を生成します。"""
    return f"http://{ip}:{TAILSCALE_HTTP_PORT}"


def build_loopback_api_url(path: str) -> str:
    """PC自身（ループバック）からローカル同期APIへアクセスするURLを生成します。

    Args:
        path: APIパス (例: "/api/test_buzz")。先頭スラッシュは省略可。

    Returns:
        str: ``http://localhost:<SERVER_PORT><path>`` 形式のURL。

    Notes:
        ポート番号をベタ書きしないため、待受ポートを変更しても本関数の
        呼び出し側は無修正で追従する (sync_config が唯一の情報源)。
    """
    normalized = path if path.startswith("/") else f"/{path}"
    return f"http://localhost:{TAILSCALE_HTTP_PORT}{normalized}"


def build_tailscale_https_url(hostname: str) -> str:
    """Tailscale Serve 経由 (HTTPS / ポート443) の URL を生成します。

    Notes:
        PC 側で ``TAILSCALE_SERVE_COMMAND`` (tailscale serve) の実行が必要。
    """
    hostname = hostname.strip()
    return f"https://{hostname}/" if hostname else ""


def build_tailscale_http_url(host: str) -> str:
    """Tailscale の HTTP 直接入力 (TAILSCALE_HTTP_PORT) の URL を生成します。

    Notes:
        追加設定なしで即座に開通するが、PWA の一部機能 (マイク等の
        セキュアコンテキスト API) は制限される。
    """
    host = host.strip()
    return f"http://{host}:{TAILSCALE_HTTP_PORT}" if host else ""


class QRCodeConnectionDialog(ctk.CTkToplevel):
    """
    スマホ専用Desk Pet ＆ 承認コクピットへワンタップ接続するための
    QRコード生成 ＆ 社内ユーザー向け接続ガイドダイアログ。
    """
    def __init__(self, parent_gui, *args, **kwargs):
        super().__init__(parent_gui.root, *args, **kwargs)
        self.parent_gui = parent_gui
        self.title("📱 スマホDesk Pet ＆ 承認コクピット接続")
        self.geometry("480x660")
        self.resizable(False, False)
        
        self.bg_color = "#F5F5DC"
        self.primary_color = "#A67B5B"
        self.text_color = "#4A3B32"
        self.configure(fg_color=self.bg_color)
        
        self.font_title = ("DotGothic16", 14, "bold") if "DotGothic16" in tk.font.families() else ("Meiryo UI", 12, "bold")
        self.font_body = ("DotGothic16", 11) if "DotGothic16" in tk.font.families() else ("Meiryo UI", 10)
        self.font_small = ("Meiryo UI", 9)
        self.font_mono = ("Consolas", 10)

        # 🖼️ ウィンドウアイコン (Alt+Tab/タスクバー) を統一 (例外安全 Seam)
        apply_window_icon(self)
        
        self.qr_image_tk = None
        self._build_ui()

    def _get_local_ips(self) -> List[str]:
        """PCの利用可能なローカルIPアドレス一覧を取得（Tailscale 帯を含む）。

        Returns:
            List[str]: メイン IP → ホスト名解決 IP → Tailscale 帯 IP の順。
        """
        ips: List[str] = []
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

        # Tailscale 仮想アダプタ (100.64.0.0/10) の補完検出
        for ip in get_tailscale_ips():
            if ip not in ips:
                ips.append(ip)
            
        if not ips:
            ips.append("127.0.0.1")
        return ips

    def _build_url_candidates(self) -> Dict[str, str]:
        """IPセレクタの表示名 → 接続URL の対応表を構築します。

        Returns:
            Dict[str, str]: 表示名をキー、QR に埋め込む URL を値とする辞書。
        """
        candidates: Dict[str, str] = {}
        for ip in self.ips:
            if is_tailscale_ip(ip):
                candidates[f"🌐 Tailscale IP ({ip})"] = build_tailscale_http_url(ip)
            else:
                candidates[f"🏠 LAN ({ip})"] = build_lan_url(ip)

        ts_host = os.getenv("TAILSCALE_HOSTNAME", "").strip()
        if ts_host:
            # 要件1: HTTPS (Tailscale Serve 必須・全機能) と HTTP (設定不要・手軽) の両立て
            https_url = build_tailscale_https_url(ts_host)
            http_url = build_tailscale_http_url(ts_host)
            if https_url:
                candidates["🌐 Tailscale (HTTPS・全機能対応)"] = https_url
            if http_url:
                candidates["🌐 Tailscale (HTTP・設定不要で手軽)"] = http_url
        return candidates

    def _build_ui(self):
        pad = 12
        # ヘッダー
        ctk.CTkLabel(self, text="📱 スマホを机上のペット端末にする", font=self.font_title, text_color=self.primary_color).pack(pady=(12, 4))
        ctk.CTkLabel(self, text="カメラでQRコードをかざすだけで、スマホが承認コクピットになります！", font=self.font_small, text_color="#7A6B62").pack()
        
        # 接続先セレクタ（LAN IP ＋ Tailscale HTTPS/HTTP 両対応）
        self.ips = self._get_local_ips()
        self.url_candidates = self._build_url_candidates()
        self.https_entry = "🌐 Tailscale (HTTPS・全機能対応)" if "🌐 Tailscale (HTTPS・全機能対応)" in self.url_candidates else ""
        display_names = list(self.url_candidates.keys())
        selected = self.https_entry if self.https_entry else display_names[0]
        self.selected_ip_var = tk.StringVar(value=selected)
        
        ip_frame = ctk.CTkFrame(self, fg_color="transparent")
        ip_frame.pack(fill="x", padx=pad, pady=(8, 4))
        ctk.CTkLabel(ip_frame, text="接続先:", font=self.font_body, text_color=self.text_color).pack(side="left", padx=(0, 6))
        
        ip_menu = ctk.CTkOptionMenu(
            ip_frame,
            values=display_names,
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
        
        self.url_var = tk.StringVar(value=self.url_candidates.get(selected, build_lan_url(self.ips[0])))
        self.url_entry = ctk.CTkEntry(url_box, textvariable=self.url_var, font=self.font_mono, height=28, state="readonly")
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        
        # 要件2: Tailscale Serve 起動支援（HTTPS が繋がらない場合のコマンドコピー）
        serve_box = ctk.CTkFrame(self, fg_color="#F3E8F7", border_color="#AB47BC", border_width=1, corner_radius=6)
        serve_box.pack(fill="x", padx=pad, pady=2)
        ctk.CTkLabel(
            serve_box,
            text=(
                "🌐 Tailscale (HTTPS) が繋がらない場合はPC側で下記を実行:\n"
                f" {TAILSCALE_SERVE_COMMAND} （443→{TAILSCALE_HTTP_PORT} のプロキシ）"
            ),
            font=self.font_small,
            text_color="#6A1B9A",
            justify="left"
        ).pack(side="left", padx=8, pady=4)
        ctk.CTkButton(
            serve_box,
            text="📋 コマンドをコピー",
            width=110,
            height=26,
            font=self.font_small,
            fg_color="#AB47BC",
            hover_color="#8E24AA",
            command=self._copy_serve_command
        ).pack(side="right", padx=6, pady=4)
        
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
        
        ctk.CTkLabel(guide_box, text="🔰 初めての接続ガイド（Wi-Fi・Bluetooth）", font=("Meiryo UI", 10, "bold"), text_color=self.primary_color).pack(anchor="w", padx=8, pady=(6, 2))
        
        guide_text = (
            "【Wi-Fi接続（自宅・社内）】\n"
            "  PCとスマホを同じWi-Fiに繋ぎ、QRコードをカメラで読み取るだけ！\n\n"
            "【Bluetooth接続（外出先・Wi-Fi不要）】\n"
            "  1. PCとスマホをBluetoothで「ペアリング」します。\n"
            "  2. Windowsの「Bluetooth PAN」（パーソナルエリアネットワーク）\n"
            "     スマホの設定 → テザリング → BluetoothテザリングをON。\n"
            "  3. QRコードを読み取るだけで通信が完結します。\n"
            "  ※ただしBluetooth PANは速度が遅く（〜2Mbps）、安定性に欠けます。\n"
            "    カフェ等ではスマホのテザリングにPCを繋ぐ方が確実です。\n"
            "  ⚠ Tailscale 等のVPNは不要です。導入は任意です。"
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

    def _on_ip_change(self, selected_ip: str) -> None:
        """接続先選択変更時に URL と QR を更新します。"""
        url = self.url_candidates.get(selected_ip)
        if url is None:
            url = build_lan_url(selected_ip) if not selected_ip.startswith("🌐") else build_lan_url(self.ips[0])
        self.url_var.set(url)
        self._render_qr()

    def _on_toggle_auto_hide(self):
        """スマホ接続時の自動非表示設定を反映"""
        val = self.auto_hide_var.get()
        self.parent_gui.auto_minimize_on_link = val
        logger.info(f"スマホ接続時PCペット自動非表示設定: {val}")

    def _copy_url(self):
        """現在の接続 URL をクリップボードへコピーします。"""
        self.clipboard_clear()
        self.clipboard_append(self.url_var.get())

    def _copy_serve_command(self):
        """Tailscale Serve 起動コマンドをクリップボードへコピーします（要件2）。"""
        self.clipboard_clear()
        self.clipboard_append(TAILSCALE_SERVE_COMMAND)
        logger.info("Tailscale Serve コマンドをクリップボードへコピーしました")

    def _send_buzz_test(self):
        """PCからスマホへ呼び出し信号を送信"""
        try:
            from local_sync_server import get_sync_token_manager
            req = urllib.request.Request(
                build_loopback_api_url("/api/test_buzz"),
                data=b"{}",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {get_sync_token_manager().token}"
                }
            )
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
