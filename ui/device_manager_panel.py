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
import threading
from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Optional, Tuple

import customtkinter as ctk

import database
from api_devices import record_device_revoke, record_device_restore

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


def mark_row_revoked(row: DeviceRow) -> DeviceRow:
    """失効直後の楽観表示用に、行DTOを「拒否済み」へ差し替える（純粋関数）。

    Args:
        row: 失効対象の表示DTO。

    Returns:
        DeviceRow: is_revoked=True / ステータス=拒否済み へ差し替えた新しいDTO。

    Notes:
        P1-1 (2026-09-16 独立査読): 再読込の完了前に古いスナップショットが表示されると
        「DBは失効済み・UIは有効」という嘘が固定表示される。楽観更新で即座に反映し、
        バックグラウンドの再読込で整合を取る。
    """
    return DeviceRow(
        device_id=row.device_id,
        title=row.title,
        subtitle=row.subtitle,
        status_label=DEVICE_STATUS_REVOKED_LABEL,
        status_color=STATUS_COLOR_REVOKED,
        created_label=row.created_label,
        last_seen_label=row.last_seen_label,
        is_revoked=True,
    )


def mark_row_restored(row: DeviceRow) -> DeviceRow:
    """復帰直後の楽観表示用に、行DTOを「有効」へ差し替える（純粋関数）。

    Args:
        row: 復帰対象の表示DTO。

    Returns:
        DeviceRow: is_revoked=False / ステータス=有効 へ差し替えた新しいDTO。
    """
    return DeviceRow(
        device_id=row.device_id,
        title=row.title,
        subtitle=row.subtitle,
        status_label=DEVICE_STATUS_ACTIVE_LABEL,
        status_color=STATUS_COLOR_ACTIVE,
        created_label=row.created_label,
        last_seen_label=row.last_seen_label,
        is_revoked=False,
    )


@dataclass(frozen=True)
class DeviceFetchResult:
    """台帳取得の結果（行DTO ＋ エラー情報）。

    Attributes:
        rows: 表示用DTOのリスト（失敗時は空）。
        error: 失敗時のメッセージ（成功時は None）。
    """

    rows: List[DeviceRow]
    error: Optional[str] = None


def fetch_device_rows() -> DeviceFetchResult:
    """台帳を読み、行DTOとエラー情報を返す Seam。

    Returns:
        DeviceFetchResult: 成功時は (rows, None)、失敗時は ([], エラーメッセージ)。

    Notes:
        P1-3 (2026-09-16 ruthless-code-evaluation): 旧実装は失敗を空リストへ
        潰していたため、DB障害が「端末ゼロ（登録なし）」と見分けられなかった。
        エラーを明示的に返すことで、UI が「読み出し失敗」を表示できる。
    """
    try:
        return DeviceFetchResult(build_device_rows(database.get_all_devices()))
    except Exception as e:
        logger.error(f"接続端末一覧の取得に失敗しました: {e}")
        return DeviceFetchResult([], f"台帳の読み出しに失敗しました: {e}")


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


def restore_device_entry(device_id: Any) -> bool:
    """端末の失効を解除 (Restore) させ、通信を再開させる Seam。

    Args:
        device_id: 対象デバイスID (文字列も許容)。

    Returns:
        bool: 復帰に成功した場合 True。対象不在/DB異常時は False (例外を漏らさない)。
    """
    try:
        return bool(database.restore_device(int(device_id)))
    except Exception as e:
        logger.error(f"端末の接続復帰に失敗しました (id={device_id}): {e}")
        return False



class DeviceManagerSection(ctk.CTkFrame):
    """設定画面に差し込む「📱 接続端末管理（ゼロトラスト）」セクション。

    端末ごとのカード (端末名 / UA・IP / 初回接続・最終アクセス / 認証ステータス) と
    「🔒 接続解除 (Revoke)」ボタン (赤系) を一覧表示する。

    Args:
        master: 親ウィジェット (設定画面のタブなど)。
        confirm_callback: 解除前の確認処理 (省略時は messagebox の Yes/No)。
            テスト時にダイアログを出さずに検証するための注入 Seam。
        dispatch: ワーカースレッド → Tkメインスレッドへの受け渡し関数
            (例: `parent_gui.post_action`)。省略時は同期実行へ退避するため、
            テストでは未指定のまま決定的に検証できる。
    """

    def __init__(
        self,
        master: Any,
        confirm_callback: Optional[Callable[[DeviceRow], bool]] = None,
        dispatch: Optional[Callable[[Callable[[], None]], Any]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._confirm_callback = confirm_callback
        self._dispatch = dispatch
        self._refresh_in_flight = False
        self._refresh_pending = False
        self.rows: List[DeviceRow] = []
        self.fetch_error: Optional[str] = None

        self._build_header()
        self.rows_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.rows_container.pack(fill="both", expand=True, padx=2, pady=(0, 4))
        # 初期表示も非同期で行い、台帳読み出し中に設定画面が固まらないようにする (P1-3)
        self.refresh_async()

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
            command=self.refresh_async,
        ).pack(side="right")

        ctk.CTkLabel(
            card,
            text=(
                "このPCに接続を許可したスマホ/端末のゼロトラスト台帳です。\n"
                "端末ごとに固有トークンが発行され、個別の接続解除（失効）や復帰が可能です。\n"
                "「🔒 接続解除」すると次の通信は即座に拒否され、「♻️ 接続復帰」でいつでも再開できます。"
            ),
            font=("Meiryo UI", 9),
            text_color="#616161",
            anchor="w",
            justify="left",
            wraplength=400,
        ).pack(fill="x", padx=8, pady=(2, 6))

        # 読み込み状態・件数・失敗を表示する行 (P1-3: 失敗を「端末ゼロ」と区別する)
        self.status_label = ctk.CTkLabel(
            card,
            text="",
            font=("Meiryo UI", 9),
            text_color="#757575",
            anchor="w",
        )
        self.status_label.pack(fill="x", padx=8, pady=(0, 6))

    def _set_status(self, text: str) -> None:
        """ヘッダーの状態表示を更新する (ウィジェット破棄済みなら何もしない)。"""
        label = getattr(self, "status_label", None)
        if label is None:
            return
        try:
            label.configure(text=text)
        except Exception as e:  # 破棄後アクセスは無視（終了時のノイズ防止）
            logger.debug(f"状態表示の更新をスキップ: {e}")

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
        if row.is_revoked:
            ctk.CTkButton(
                action,
                text="♻️ 接続復帰",
                font=("Meiryo UI", 9),
                fg_color=STATUS_COLOR_ACTIVE,
                hover_color="#1B5E20",
                width=92,
                height=24,
                command=lambda r=row: self.restore(r),
            ).pack(anchor="e")
        else:
            ctk.CTkButton(
                action,
                text="🔒 接続解除",
                font=("Meiryo UI", 9),
                fg_color=STATUS_COLOR_REVOKED,
                hover_color="#8E1B1B",
                width=92,
                height=24,
                command=lambda r=row: self.revoke(r),
            ).pack(anchor="e")

    # ------------------------------------------------------------- 再描画/解除
    def refresh(self) -> None:
        """台帳を同期で読み直して表示を更新する (テスト・後方互換用)。

        Notes:
            本番経路 (設定画面) は `refresh_async()` を使う。DBがロックされていると
            `busy_timeout` (30秒) まで待つため、Tkメインスレッドから呼ぶと
            最悪30秒UIが固まる (P1-3 / 2026-09-16 ruthless-code-evaluation)。
            本メソッドは Tk を直接操作するためメインスレッド専用であり、
            他スレッドからの呼び出しは安全側に倒して無視する (P2-5)。
        """
        if threading.current_thread() is not threading.main_thread():
            logger.warning(
                "端末一覧の同期更新はメインスレッド専用です。refresh_async() を使用してください"
            )
            return
        self._apply_result(fetch_device_rows())

    def refresh_async(self) -> None:
        """台帳をワーカースレッドで読み、Tkメインスレッドへ安全に反映する (P1-3)。

        Notes:
            `dispatch` (例: `parent_gui.post_action`) が注入されている場合は
            ワーカー→メインスレッドの受け渡しを行い、**読み出し中もUIを一切ブロックしない**。
            未注入 (テスト・単体利用) の場合は同期実行へ退避する。
            多重発行は `_refresh_in_flight` で抑止する (連打しても読み出しは1本)。
        """
        if self._dispatch is None:
            self.refresh()
            return
        if self._refresh_in_flight:
            # 破棄せず「延期」する: revoke 直後の再読込を取りこぼすと
            #   失効前スナップショットが表示され UI が嘘をつく (P1-1 / 2026-09-16 独立査読)
            self._refresh_pending = True
            logger.debug("端末一覧の読み出しが実行中のため、再読込を延期します")
            return
        self._refresh_in_flight = True
        self._refresh_pending = False
        self._set_status("🔄 読み込み中…")
        threading.Thread(
            target=self._fetch_then_dispatch,
            daemon=True,
            name="DeviceRegistryFetch",
        ).start()

    def _fetch_then_dispatch(self) -> None:
        """ワーカースレッド側: 台帳を読み、結果を `dispatch` 経由でメインスレッドへ渡す。"""
        result = fetch_device_rows()

        def _apply() -> None:
            self._refresh_in_flight = False
            self._apply_result(result)
            if self._refresh_pending:
                # 延期していた再読込をここで実行し、最新状態へ収束させる (P1-1)
                self._refresh_pending = False
                self.refresh_async()

        try:
            self._dispatch(_apply)
        except Exception as e:
            # ウィンドウ破棄済み等による反映依頼の失敗でアプリを落とさない
            logger.debug(f"端末一覧の反映依頼に失敗しました: {e}")
            self._refresh_in_flight = False

    def _apply_result(self, result: DeviceFetchResult) -> None:
        """取得結果を画面へ反映する (Tkメインスレッド専用)。

        Notes:
            内容 (行・エラー) が前回と同一の場合はウィジェットを再生成しない。
            連打・定期更新でのウィジェット爆発と描画チラつきを防ぐ。
        """
        unchanged = (result.rows == self.rows) and (result.error == self.fetch_error)
        had_rows = bool(self.rows)
        self.fetch_error = result.error

        if result.error and had_rows:
            # stale-but-visible: 直前まで表示していた一覧を消さずに失敗を明示する (P2-4)
            logger.debug("端末一覧の更新に失敗したため、前回内容を保持して表示します")
            self._set_status(f"⚠️ 更新失敗（前回の内容を表示中）: {result.error}")
            return

        self.rows = list(result.rows)

        if unchanged and self.rows_container.winfo_children():
            return

        for child in self.rows_container.winfo_children():
            child.destroy()

        if self.fetch_error:
            ctk.CTkLabel(
                self.rows_container,
                text=(
                    f"⚠️ {self.fetch_error}\n"
                    "（DBロック等の一時障害の可能性があります。少し待って「🔄 再読込」を押してください）"
                ),
                font=("Meiryo UI", 10),
                text_color=STATUS_COLOR_REVOKED,
                justify="left",
                wraplength=400,
            ).pack(anchor="w", padx=6, pady=8)
            self._set_status("⚠️ 読み出し失敗")
            return

        if not self.rows:
            ctk.CTkLabel(
                self.rows_container,
                text=EMPTY_PLACEHOLDER,
                font=("Meiryo UI", 10),
                text_color="#616161",
                justify="left",
                wraplength=400,
            ).pack(anchor="w", padx=6, pady=8)
            self._set_status("登録端末: 0件")
            return

        for row in self.rows:
            self._render_row(row)
        self._set_status(f"登録端末: {len(self.rows)}件")

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
            # ゼロトラスト監査: 誰がいつどの端末を切ったかを記録する (P1-4)
            record_device_revoke(
                row.device_id,
                actor="pc_settings_ui",
                source="ui",
                device_name=row.title,
            )
            # 楽観反映: 再読込の完了前に「有効」のまま見える嘘を防ぐ (P1-1)
            self._apply_result(
                DeviceFetchResult(
                    [
                        mark_row_revoked(item) if item.device_id == row.device_id else item
                        for item in self.rows
                    ]
                )
            )
            self.refresh_async()
        else:
            self._set_status(
                "⚠️ 接続解除に失敗しました（DBロック等の可能性があります。再試行してください）"
            )
        return ok

    def restore(self, row: DeviceRow) -> bool:
        """端末の失効を解除（復帰）させ、一覧を即座に再描画する。

        Args:
            row: 対象端末の表示DTO。

        Returns:
            bool: 復帰に成功した場合 True (失敗時は False)。
        """
        if not row.is_revoked:
            return False

        ok = restore_device_entry(row.device_id)
        if ok:
            logger.info(f"端末の接続を復帰しました (id={row.device_id})")
            # ゼロトラスト監査: 誰がいつどの端末を復帰させたかを記録する
            record_device_restore(
                row.device_id,
                actor="pc_settings_ui",
                source="ui",
                device_name=row.title,
            )
            # 楽観反映
            self._apply_result(
                DeviceFetchResult(
                    [
                        mark_row_restored(item) if item.device_id == row.device_id else item
                        for item in self.rows
                    ]
                )
            )
            self.refresh_async()
        else:
            self._set_status(
                "⚠️ 接続復帰に失敗しました（DBロック等の可能性があります。再試行してください）"
            )
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
                "この端末からの今後の通信はすべて拒否（403）されます。\n"
                "（再び接続を許可したい場合は、この一覧で『♻️ 接続復帰』をクリックするか、\n"
                "　スマホ側でQRコードを再ペアリングしてください）",
            )
        )

