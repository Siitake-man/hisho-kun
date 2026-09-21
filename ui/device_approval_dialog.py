"""
ネオ秘書くん - 未承認端末接続時の Human-in-the-Loop 承認ダイアログ (ui/device_approval_dialog.py)

ゼロトラスト原則に基づき、スマホ等の外部端末からトークン配布 (/api/auth/token)
要求が届いた際、PCデスクトップ上に承認ダイアログを表示して人間の明示的許可を求める。
"""

import logging
import threading
import time
import tkinter as tk
from typing import Optional, Any, Callable, Dict
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
        on_decision: Optional[object] = None,
    ) -> None:
        super().__init__(parent)
        self.device_name = device_name
        self.client_ip = client_ip
        self.timeout_sec = timeout_sec
        self.remaining_sec = timeout_sec
        self.result: Optional[bool] = None
        self.on_decision = on_decision

        from i18n import t
        self.title(t("ui.dev.req_title"))
        self.geometry("460x340")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        apply_window_icon(self)

        # 画面中央へセンタリング ＆ 最前面フォーカス
        try:
            self.update_idletasks()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w, h = 460, 340
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
            self.lift()
            self.focus_force()
        except Exception as e:
            logger.debug(f"ダイアログセンタリング例外: {e}")

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
            if callable(self.on_decision):
                try:
                    self.on_decision(True)
                except Exception as e:
                    logger.debug(f"on_decision(True) 呼び出し例外: {e}")
            self.destroy()

    def _on_deny(self) -> None:
        if self.result is None:
            self.result = False
            logger.info(f"端末接続拒絶: {self.device_name} ({self.client_ip})")
            if callable(self.on_decision):
                try:
                    self.on_decision(False)
                except Exception as e:
                    logger.debug(f"on_decision(False) 呼び出し例外: {e}")
            self.destroy()


_dialog_lock = threading.Lock()
_is_dialog_active = False
_active_device_key: Optional[str] = None
_active_result_event: Optional[threading.Event] = None
_active_outcome: Optional[list] = None
# 🛡️ 直近に承認された端末のデバウンスキャッシュ {device_key: 有効期限(epoch秒)}
_recent_approvals: Dict[str, float] = {}
APPROVAL_DEBOUNCE_TTL_SEC: float = 10.0


def ask_device_approval_gui(
    root: Optional[Any],
    device_name: str,
    client_ip: str,
    timeout_sec: int = 10,
) -> bool:
    """HTTPバックグラウンドスレッドからGUIスレッドで承認ダイアログを開き、結果を安全に待機する。

    スレッド安全性の保証:
        Tkinter のメソッド (winfo_exists, after 等) はメインスレッド専用であり、
        HTTPワーカースレッドから直接呼び出すと 'RuntimeError: main thread is not in main loop'
        が発生する。そのため本関数内では Tkinter メソッドを直接実行せず、
        gui.post_action() 経由でメインGUIスレッドへディスパッチして実行する。

    同一端末の合流待機 (Coalesce) ＆ 短時間デバウンス:
        スマホ側が短周期ポーリングで /api/auth/token を再要求してきた場合、
        - 現在表示中であれば、同一端末 (IP+名前) はビジー拒絶せず既存ダイアログの結果に合流待機する。
        - 直近10秒以内に承認済みであれば、ダイアログを再表示せず即座に承認 (True) を返す。

    Args:
        root: GUIインスタンス (NeoSecretaryGUI) または Tkinter ルートウィンドウ (Noneの場合は即時拒絶)
        device_name: 接続元端末名
        client_ip: 接続元IP
        timeout_sec: 待機タイムアウト秒数 (ソケットタイムアウト10sに整合)

    Returns:
        bool: 承認時 True、拒絶またはタイムアウト時 False (Fail-Closed)
    """
    global _is_dialog_active, _active_device_key, _active_result_event, _active_outcome, _recent_approvals

    if root is None:
        logger.warning("GUIが存在しないため端末接続要求を自動拒否 (Fail-Closed)")
        return False

    # gui オブジェクト (NeoSecretaryGUI) か tk.Tk (またはそのモック) かを安全に判別
    # ※ MagicMock は全属性に hasattr=True を返すため、クラス名または after 未保持で判別
    is_gui = (
        root.__class__.__name__ == "NeoSecretaryGUI"
        or (hasattr(root, "post_action") and not hasattr(root, "after"))
    )
    gui = root if is_gui else None
    actual_root = getattr(root, "root", root) if is_gui else root

    device_key = f"{client_ip}:{device_name}"
    now = time.time()

    with _dialog_lock:
        # 1. 直近に承認された端末であればダイアログを再ポップアップさせず即座に承認（デバウンス）
        # 期限切れレコードの掃除も同時に実施
        _recent_approvals = {k: exp for k, exp in _recent_approvals.items() if exp > now}
        if _recent_approvals.get(device_key, 0.0) > now:
            logger.info(f"⚡ [DeviceApproval] 直近承認済み端末のためダイアログをスキップして即時承認: {device_key}")
            return True

        if _is_dialog_active:
            # 🛡️ 同一端末からの重複リクエスト（ポーリング）なら既存の承認結果イベントに相乗り合流
            if _active_device_key == device_key and _active_result_event is not None and _active_outcome is not None:
                logger.info(f"同一端末からの重複承認要求を既存ダイアログに合流待機: {device_key}")
                shared_event = _active_result_event
                shared_outcome = _active_outcome
                # ロックを抜けて待機
            else:
                logger.warning(f"承認ダイアログが既に表示中のため接続要求をビジー拒絶: {device_name} ({client_ip})")
                return False
        else:
            _is_dialog_active = True
            _active_device_key = device_key
            _active_result_event = threading.Event()
            _active_outcome = [False]
            shared_event = None
            shared_outcome = None

    if shared_event is not None and shared_outcome is not None:
        # 合流側: 既存イベントの完了を待つ
        finished = shared_event.wait(timeout=float(timeout_sec + 1))
        if not finished:
            return False
        return shared_outcome[0]

    result_event = _active_result_event
    outcome = _active_outcome

    def _handle_decision(approved: bool):
        outcome[0] = approved
        result_event.set()

    def _show():
        """メインGUIスレッド上で安全に実行されるダイアログ初期化処理。"""
        try:
            # メインスレッド上であれば winfo_exists() を安全に呼べる
            if actual_root is not None and hasattr(actual_root, "winfo_exists"):
                if not actual_root.winfo_exists():
                    logger.warning("GUIウィンドウが破棄されているため端末承認を自動拒否")
                    _handle_decision(False)
                    return

            # 親ウィンドウまたは最前面Toplevelの検出
            dialog_parent = actual_root
            try:
                # もしQRコードダイアログ等が開いていれば、そのウィンドウの手前に配置
                if actual_root is not None and hasattr(actual_root, "winfo_children"):
                    for child in actual_root.winfo_children():
                        if isinstance(child, (ctk.CTkToplevel, tk.Toplevel)):
                            try:
                                if child.winfo_exists() and child.winfo_viewable():
                                    dialog_parent = child
                                    break
                            except Exception:
                                pass
            except Exception as e:
                logger.debug(f"親ウィンドウ探索例外: {e}")

            dialog = DeviceApprovalDialog(
                dialog_parent,
                device_name,
                client_ip,
                timeout_sec=timeout_sec,
                on_decision=_handle_decision,
            )
            # GC防止のため親に参照を一時保持
            if hasattr(actual_root, "_active_device_dialog"):
                actual_root._active_device_dialog = dialog
        except Exception as e:
            logger.error(f"承認ダイアログ表示エラー (メインスレッド): {e}")
            _handle_decision(False)

    try:
        # メインGUIスレッドへディスパッチ (gui.post_action 優先でメッセージドロップを完全防止)
        if gui is not None and hasattr(gui, "post_action"):
            gui.post_action(_show)
        elif hasattr(actual_root, "after"):
            actual_root.after(0, _show)
        else:
            logger.error("GUIディスパッチ手段が存在しないため接続要求を自動拒否")
            return False

        # HTTPスレッド側で結果待機（+1秒のマージン）
        finished = result_event.wait(timeout=float(timeout_sec + 1))
        if not finished:
            logger.warning(f"端末接続承認待機タイムアウト ({timeout_sec}s): Fail-Closed")
            return False

        if outcome[0]:
            with _dialog_lock:
                _recent_approvals[device_key] = time.time() + APPROVAL_DEBOUNCE_TTL_SEC
                logger.info(f"✅ [DeviceApproval] 端末承認をデバウンスキャッシュに登録 ({APPROVAL_DEBOUNCE_TTL_SEC}s): {device_key}")

        return outcome[0]
    finally:
        with _dialog_lock:
            _is_dialog_active = False
            _active_device_key = None
            _active_result_event = None
            _active_outcome = None

