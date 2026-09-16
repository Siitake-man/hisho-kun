"""
ネオ秘書くん - 設定画面「📱 接続端末管理（ゼロトラスト）」セクション
(ui/device_manager_panel.py)

Sprint C 先取り (2026-09-16 Cline):
バックエンドに実装済みの端末台帳 (storage/device_repo.py ＋ GET /api/devices /
POST /api/devices/revoke) を、PC設定画面から視覚確認・Revoke できるようにする。

設計方針 (Codebase Design 規約):
- 台帳 → 表示DTOの変換 (build_device_rows) と Revoke 実行 (revoke_device_entry) は
  純粋関数 / Seam 関数へ分離し、GUI を表示せずに検証可能にする。
- 巨大ファイル (settings_window.py) へは本セクションを 1 つ差し込むだけで済ませ、
  これ以上のベタ書きを避ける。
"""

import datetime
import logging
from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Optional

import customtkinter as ctk

import database

logger = logging.getLogger(__name__)

# --- 表示定義 (文言とカラーを 1 箇所に集約) --------------------------------
DEVICE_STATUS_ACTIVE_LABEL = "🟢 有効"
DEVICE_STATUS_REVOKED_LABEL = "🚫 拒否済み"
STATUS_COLOR_ACTIVE = "#2E7D32"
STATUS_COLOR_REVOKED = "#C62828"
UNKNOWN_DEVICE_LABEL = "❓ 不明な端末"
IP_PLACEHOLDER = "IP不明"
TIMESTAMP_PLACEHOLDER = "—"
EMPTY_PLACEHOLDER = (
    "登録された端末はまだありません。\n"
    "スマホでQRコードを読み取って接続すると、ここに台帳登録されます。"
)

# UA 判定表 (上位ほど優先。Android の UA は Linux を含むため Android を先に判定する)
_UA_SIGNATURES = (
    ("ipad", "📱 iPad"),
    ("iphone", "📱 iPhone"),
    ("android", "📱 Android"),
    ("windows", "💻 Windows PC"),
    ("macintosh", "💻 Mac"),
    ("mac os x", "💻 Mac"),
    ("linux", "🐧 Linux"),
)


def summarize_user_agent(user_agent: Optional[str]) -> str:
    """User-Agent 文字列から端末種別の表示名を推定する。

    Args:
        user_agent: 台帳に記録された User-Agent (None/空も許容)。

    Returns:
        str: 例 "📱 iPhone"。判別できない場合は "❓ 不明な端末"。
    """
    if not user_agent:
        return UNKNOWN_DEVICE_LABEL
    text = str(user_agent).lower()
    for signature, label in _UA_SIGNATURES:
        if signature in text:
            return label
    return UNKNOWN_DEVICE_LABEL


def format_device_timestamp(value: Any) -> str:
    """ミリ秒タイムスタンプを表示用 'YYYY-MM-DD HH:MM' へ整形する。

    Args:
        value: Unix タイムスタンプ (ミリ秒)。未記録/不正値も許容。

    Returns:
        str: 整形済み日時。未記録/不正値は "—" (例外は漏らさない)。
    """
    try:
        millis = int(value)
    except (TypeError, ValueError):
        return TIMESTAMP_PLACEHOLDER
    if millis <= 0:
        return TIMESTAMP_PLACEHOLDER
    try:
        return datetime.datetime.fromtimestamp(millis / 1000).strftime("%Y-%m-%d %H:%M")
    except (OverflowError, OSError, ValueError):
        return TIMESTAMP_PLACEHOLDER


@dataclass(frozen=True)
class DeviceRow:
    """端末カード1枚分の表示用DTO (GUI 非依存)。"""

    device_id: int
    title: str
    subtitle: str
    status_label: str
    status_color: str
    created_label: str
    last_seen_label: str
    is_revoked: bool


def build_device_rows(devices: Optional[Iterable[Any]]) -> List[DeviceRow]:
    """台帳 (Device モデル) の並びを表示用DTOのリストへ変換する (純粋関数)。

    Args:
        devices: Device モデルのイテラブル (None/空も許容)。

    Returns:
        List[DeviceRow]: 表示用DTOのリスト (入力順を維持)。
    """
    rows: List[DeviceRow] = []
    for device in devices or []:
        is_revoked = bool(getattr(device, "is_revoked", 0))
        ua_label = summarize_user_agent(getattr(device, "user_agent", None))
        name = str(getattr(device, "device_name", "") or "").strip() or ua_label
        ip = str(getattr(device, "ip_address", "") or "").strip() or IP_PLACEHOLDER
        rows.append(
            DeviceRow(
                device_id=int(getattr(device, "id", 0) or 0),
                title=name,
                subtitle=f"{ua_label} · {ip}",
                status_label=(
                    DEVICE_STATUS_REVOKED_LABEL if is_revoked else DEVICE_STATUS_ACTIVE_LABEL
                ),
                status_color=STATUS_COLOR_REVOKED if is_revoked else STATUS_COLOR_ACTIVE,
                created_label=format_device_timestamp(getattr(device, "created_at", None)),
                last_seen_label=format_device_timestamp(getattr(device, "last_seen", None)),
                is_revoked=is_revoked,
            )
        )
    return rows


def list_device_rows() -> List[DeviceRow]:
    """ゼロトラスト端末台帳を読み、表示用DTOのリストを返す Seam。

    Returns:
        List[DeviceRow]: 最終接続が新しい順の端末一覧 (取得失敗時は空リスト)。
    """
    try:
        return build_device_rows(database.get_all_devices())
    except Exception as e:
        logger.error(f"接続端末一覧の取得に失敗しました: {e}")
        return []


def revoke_device_entry(device_id: Any) -> bool:
    """端末を失効 (Revoke) させ、次回リクエストを 401/403 で遮断させる Seam。

    Args:
        device_id: 対象デバイスID (文字列も許容)。

    Returns:
        bool: 失効に成功した場合 True。対象不在/DB異常時は False (例外を漏らさない)。
    """
    try:
        return bool(database.revoke_device(int(device_id)))
    except Exception as e:
        logger.error(f"端末の接続解除に失敗しました (id={device_id}): {e}")
        return False



class DeviceManagerSection(ctk.CTkFrame):
    """設定画面に差し込む「📱 接続端末管理（ゼロトラスト）」セクション。

    端末ごとのカード (端末名 / UA・IP / 初回接続・最終アクセス / 認証ステータス) と
    「🔒 接続解除 (Revoke)」ボタン (赤系) を一覧表示する。

    Args:
        master: 親ウィジェット (設定画面のタブなど)。
        confirm_callback: 解除前の確認処理 (省略時は messagebox の Yes/No)。
            テスト時にダイアログを出さずに検証するための注入 Seam。
    """

    def __init__(
        self,
        master: Any,
        confirm_callback: Optional[Callable[[DeviceRow], bool]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._confirm_callback = confirm_callback
        self.rows: List[DeviceRow] = []

        self._build_header()
        self.rows_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.rows_container.pack(fill="both", expand=True, padx=2, pady=(0, 4))
        self.refresh()

    # ------------------------------------------------------------------ 構築
    def _build_header(self) -> None:
        """セクションの見出しと説明・再読込ボタンを構築する。"""
        card = ctk.CTkFrame(self, fg_color="#FFFFFF", border_width=1, border_color="#E0D8C8", corner_radius=6)
        card.pack(fill="x", pady=(4, 6), padx=2)

        head_row = ctk.CTkFrame(card, fg_color="transparent")
        head_row.pack(fill="x", padx=8, pady=(6, 0))
        ctk.CTkLabel(
            head_row,
            text="📱 接続端末管理（ゼロトラスト）",
            font=("Meiryo UI", 11, "bold"),
            text_color="#4A3B32",
            anchor="w",
        ).pack(side="left")
        ctk.CTkButton(
            head_row,
            text="🔄 再読込",
            font=("Meiryo UI", 9),
            fg_color="#5D4037",
            hover_color="#4E342E",
            width=80,
            height=24,
            command=self.refresh,
        ).pack(side="right")

        ctk.CTkLabel(
            card,
            text=(
                "このPCに接続を許可したスマホ/端末の台帳です。\n"
                "「🔒 接続解除」すると、その端末からの次の通信は即座に拒否（401/403）されます。"
            ),
            font=("Meiryo UI", 9),
            text_color="#616161",
            anchor="w",
            justify="left",
            wraplength=400,
        ).pack(fill="x", padx=8, pady=(2, 6))

    def _render_row(self, row: DeviceRow) -> None:
        """端末1件分のカードを描画する。"""
        card = ctk.CTkFrame(
            self.rows_container,
            fg_color="#FFFFFF",
            border_width=1,
            border_color="#E0D8C8",
            corner_radius=6,
        )
        card.pack(fill="x", pady=3, padx=2)

        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, padx=8, pady=4)
        ctk.CTkLabel(
            info, text=row.title, font=("Meiryo UI", 11, "bold"), text_color="#4A3B32", anchor="w"
        ).pack(anchor="w")
        ctk.CTkLabel(
            info, text=row.subtitle, font=("Meiryo UI", 9), text_color="#616161", anchor="w"
        ).pack(anchor="w")
        ctk.CTkLabel(
            info,
            text=f"初回接続: {row.created_label}　/　最終: {row.last_seen_label}",
            font=("Meiryo UI", 8),
            text_color="#757575",
            anchor="w",
        ).pack(anchor="w")

        action = ctk.CTkFrame(card, fg_color="transparent")
        action.pack(side="right", padx=8, pady=4)
        ctk.CTkLabel(
            action,
            text=row.status_label,
            font=("Meiryo UI", 9, "bold"),
            text_color=row.status_color,
        ).pack(anchor="e", pady=(0, 2))
        ctk.CTkButton(
            action,
            text="🔒 接続解除",
            font=("Meiryo UI", 9),
            fg_color=STATUS_COLOR_REVOKED,
            hover_color="#8E1B1B",
            width=92,
            height=24,
            state="disabled" if row.is_revoked else "normal",
            command=lambda r=row: self.revoke(r),
        ).pack(anchor="e")

    # ------------------------------------------------------------- 再描画/解除
    def refresh(self) -> None:
        """台帳を読み直して端末カードを再描画する (Seam 経由・GUI 非依存の取得)。"""
        for child in self.rows_container.winfo_children():
            child.destroy()

        self.rows = list_device_rows()

        if not self.rows:
            ctk.CTkLabel(
                self.rows_container,
                text=EMPTY_PLACEHOLDER,
                font=("Meiryo UI", 10),
                text_color="#616161",
                justify="left",
                wraplength=400,
            ).pack(anchor="w", padx=6, pady=8)
            return

        for row in self.rows:
            self._render_row(row)

    def revoke(self, row: DeviceRow) -> bool:
        """確認のうえ端末を失効させ、一覧を即座に再描画する。

        Args:
            row: 対象端末の表示DTO。

        Returns:
            bool: 失効に成功した場合 True (キャンセル/失敗時は False)。
        """
        if row.is_revoked:
            return False
        if not self._request_confirmation(row):
            logger.info(f"端末の接続解除をキャンセルしました (id={row.device_id})")
            return False

        ok = revoke_device_entry(row.device_id)
        if ok:
            logger.warning(f"端末の接続を解除しました (id={row.device_id})")
        self.refresh()
        return ok

    def _request_confirmation(self, row: DeviceRow) -> bool:
        """接続解除の確認を取る (注入されたコールバック優先)。"""
        if self._confirm_callback is not None:
            return bool(self._confirm_callback(row))

        from tkinter import messagebox

        return bool(
            messagebox.askyesno(
                "接続解除の確認",
                f"「{row.title}」の接続を解除しますか？\n\n"
                "この端末からの今後の通信はすべて拒否されます。\n"
                "（再度接続するにはQRコードの読み直しが必要です）",
            )
        )

