"""
ネオ秘書くん - 未承認端末接続時の Human-in-the-Loop 承認ダイアログ (ui/device_approval_dialog.py)

ゼロトラスト原則に基づき、スマホ等の外部端末からトークン配布 (/api/auth/token)
要求が届いた際、PCデスクトップ上に承認ダイアログを表示して人間の明示的許可を求める。
"""

import logging
import threading
import time
import tkinter as tk
from typing import Optional
import customtkinter as ctk

from ui.window_icon import apply_window_icon

logger = logging.getLogger(__name__)


class DeviceApprovalDialog(ctk.CTkToplevel):
    """未承認端末からの接続要求を審査・承認するモーダルダイアログ。"""

    def __init__(
        self,
        parent: tk.Tk,
        device_name: str,
        client_ip: str,
        timeout_sec: int = 30,
        jev_score_text: str = "🟢 allow / 信頼度 1.0 (同一LAN/私有端末)",
    ) -> None:
        super().__init__(parent)
        self.device_name = device_name
        self.client_ip = client_ip
        self.timeout_sec = timeout_sec
        self.remaining_sec = timeout_sec
        self.result: Optional[bool] = None

        from i18n import t
        self.title(t("ui.dev.req_title"))
        self.geometry("460x340")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        apply_window_icon(self)

        self._build_ui(jev_score_text)
        self._bind_keys()

        # カウントダウン開始
        self._countdown()

    def _build_ui(self, jev_score_text: str) -> None:
        from i18n import t
        main_frame = ctk.CTkFrame(self, corner_radius=12)
        main_frame.pack(fill="both", expand=True, padx=16, pady=16)

        # ヘッダー
        title_label = ctk.CTkLabel(
            main_frame,
            text=t("ui.dev.new_req"),
            font=ctk.CTkFont(family="M PLUS 1p", size=18, weight="bold"),
            text_color="#38bdf8",
        )
        title_label.pack(pady=(12, 6))

        desc_label = ctk.CTkLabel(
            main_frame,
            text=t("ui.dev.confirm"),
            font=ctk.CTkFont(family="M PLUS 1p", size=12),
            text_color="#94a3b8",
            justify="center",
        )
        desc_label.pack(pady=(0, 12))

        # 端末情報カード
        info_card = ctk.CTkFrame(main_frame, fg_color=("gray85", "#1e293b"), corner_radius=8)
        info_card.pack(fill="x", padx=16, pady=(0, 12))

        row1 = ctk.CTkFrame(info_card, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(8, 4))
        ctk.CTkLabel(row1, text=t("ui.dev.name"), font=ctk.CTkFont(size=12, weight="bold"), width=80, anchor="w").pack(side="left")
        ctk.CTkLabel(row1, text=self.device_name, font=ctk.CTkFont(size=12), anchor="w").pack(side="left")

        row2 = ctk.CTkFrame(info_card, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row2, text=t("ui.dev.ip"), font=ctk.CTkFont(size=12, weight="bold"), width=80, anchor="w").pack(side="left")
        ctk.CTkLabel(row2, text=self.client_ip, font=ctk.CTkFont(size=12, family="Consolas"), anchor="w").pack(side="left")

        row3 = ctk.CTkFrame(info_card, fg_color="transparent")
        row3.pack(fill="x", padx=12, pady=(4, 8))
        ctk.CTkLabel(row3, text=t("ui.dev.audit"), font=ctk.CTkFont(size=12, weight="bold"), width=80, anchor="w").pack(side="left")
        ctk.CTkLabel(row3, text=jev_score_text, font=ctk.CTkFont(size=11), text_color="#10b981", anchor="w").pack(side="left")

        # カウントダウンラベル
        self.timer_label = ctk.CTkLabel(
            main_frame,
            text=t("ui.dev.auto_deny", sec=self.remaining_sec),
            font=ctk.CTkFont(size=11),
            text_color="#f59e0b",
        )
        self.timer_label.pack(pady=(0, 12))

        # ボタンエリア
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(0, 8))

        self.deny_btn = ctk.CTkButton(
            btn_frame,
            text=t("ui.dev.btn_deny"),
            fg_color="#ef4444",
            hover_color="#dc2626",
            font=ctk.CTkFont(family="M PLUS 1p", size=13, weight="bold"),
            command=self._on_deny,
            width=140,
            height=36,
        )
        self.deny_btn.pack(side="left", expand=True, padx=(0, 8))

        self.allow_btn = ctk.CTkButton(
            btn_frame,
            text=t("ui.dev.btn_allow"),
            fg_color="#10b981",
            hover_color="#059669",
            font=ctk.CTkFont(family="M PLUS 1p", size=13, weight="bold"),
            command=self._on_allow,
            width=140,
            height=36,
        )
        self.allow_btn.pack(side="right", expand=True, padx=(8, 0))

    def _bind_keys(self) -> None:
        self.bind("<Return>", lambda e: self._on_allow())
        self.bind("<Escape>", lambda e: self._on_deny())
        self.protocol("WM_DELETE_WINDOW", self._on_deny)

    def _countdown(self) -> None:
        if self.result is not None:
            return
        if self.remaining_sec <= 0:
            logger.info("端末接続承認タイムアウト: 自動拒否")
            self._on_deny()
            return

        self.timer_label.configure(text=f"自動拒否まで: {self.remaining_sec} 秒")
        self.remaining_sec -= 1
        self.after(1000, self._countdown)

    def _on_allow(self) -> None:
        if self.result is None:
            self.result = True
            logger.info(f"端末接続許可: {self.device_name} ({self.client_ip})")
            self.destroy()

    def _on_deny(self) -> None:
        if self.result is None:
            self.result = False
            logger.info(f"端末接続拒絶: {self.device_name} ({self.client_ip})")
            self.destroy()


_dialog_lock = threading.Lock()
_is_dialog_active = False


def ask_device_approval_gui(
    root: Optional[tk.Tk],
    device_name: str,
    client_ip: str,
    timeout_sec: int = 10,
) -> bool:
    """HTTPバックグラウンドスレッドからGUIスレッドで承認ダイアログを開き、結果を安全に待機する。

    Args:
        root: Tkinter ルートウィンドウ (Noneの場合は即時拒絶)
        device_name: 接続元端末名
        client_ip: 接続元IP
        timeout_sec: 待機タイムアウト秒数 (ソケットタイムアウト10sに整合)

    Returns:
        bool: 承認時 True、拒絶またはタイムアウト時 False (Fail-Closed)
    """
    global _is_dialog_active

    if root is None or not root.winfo_exists():
        logger.warning("GUIが存在しないため端末接続要求を自動拒否 (Fail-Closed)")
        return False

    with _dialog_lock:
        if _is_dialog_active:
            logger.warning(f"承認ダイアログが既に表示中のため接続要求をビジー拒絶: {device_name} ({client_ip})")
            return False
        _is_dialog_active = True

    result_event = threading.Event()
    outcome = [False]

    def _show():
        global _is_dialog_active
        try:
            dialog = DeviceApprovalDialog(
                root, device_name, client_ip, timeout_sec=timeout_sec
            )
            # ダイアログ終了まで待機
            dialog.wait_window()
            outcome[0] = bool(dialog.result)
        except Exception as e:
            logger.error(f"承認ダイアログ表示エラー: {e}")
            outcome[0] = False
        finally:
            with _dialog_lock:
                _is_dialog_active = False
            result_event.set()

    # GUIメインスレッドで実行
    root.after(0, _show)

    # HTTPスレッド側で結果待機（+1秒のマージン）
    finished = result_event.wait(timeout=float(timeout_sec + 1))
    if not finished:
        logger.warning(f"端末接続承認待機タイムアウト ({timeout_sec}s): Fail-Closed")
        with _dialog_lock:
            _is_dialog_active = False
        return False

    return outcome[0]

