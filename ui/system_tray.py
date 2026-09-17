"""
ネオ秘書くん - システムタスクトレイ常駐マネージャー (ui/system_tray.py)

Windowsの通知領域（タスクトレイ）に秘書くんアイコンを常駐させ、
PCペットが画面上で非表示・最小化されている時でも、
右クリックメニューやトレイクリックからワンタップで呼び出し・設定変更を可能にする。
"""

import logging
import re
import threading
from pathlib import Path
from typing import Any, List, Optional
from PIL import Image

logger = logging.getLogger(__name__)

# トレイアイコン用のアセット探索パス
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

# 既定キャラクター (初代秘書くん) のドット絵。トレイアイコンの第一候補。
DEFAULT_CHARACTER_ID = "hisho"
TRAY_FRAME_NAME = "idle_1.png"

# 通知領域に収まる 64x64 (NEAREST 拡大でドット感を維持する)
TRAY_ICON_SIZE = (64, 64)

# キャラクターIDの許可文字 (パストラバーサル等の不正入力を遮断・ゼロトラスト)
_CHARACTER_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


def sanitize_character_id(character_id: Any) -> Optional[str]:
    """キャラクターIDを安全な文字列 (小文字英数とアンダースコアのみ) へ正規化する。

    Args:
        character_id: 検証対象のID (None や非文字列も許容)。

    Returns:
        Optional[str]: 正規化済みID。不正な場合は None (呼び出し側は既定キャラへ退避)。
    """
    if not character_id:
        return None
    text = str(character_id).strip().lower()
    return text if _CHARACTER_ID_PATTERN.match(text) else None


def iter_tray_icon_candidates(character_id: Any = None) -> List[Path]:
    """トレイアイコンの候補パスを優先順に列挙する（アセット解決の単一情報源）。

    Args:
        character_id: キャラクターID。不正・未登録・None の場合は既定キャラへ退避。

    Returns:
        List[Path]: 「指定キャラの idle_1 → 指定キャラの happy → 既定キャラの idle_1 →
            既定キャラの happy」の順の候補パス（実在確認は呼び出し側で行う）。

    Notes:
        P2 (2026-09-16 ruthless-code-evaluation): 旧実装は `_ASSET_CANDIDATES`（固定リスト）と
        `resolve_character_icon_path`（キャラ別解決）でアセット解決が二重化していた。
        本関数を唯一の情報源とし、両者はここから導出する。
    """
    candidates: List[Path] = []
    safe_id = sanitize_character_id(character_id)

    for char_id in ([safe_id] if safe_id else []):
        candidates.append(ASSETS_DIR / "dot" / char_id / TRAY_FRAME_NAME)
        candidates.append(ASSETS_DIR / "dot" / char_id / "happy.png")

    if safe_id != DEFAULT_CHARACTER_ID:
        candidates.append(ASSETS_DIR / "dot" / DEFAULT_CHARACTER_ID / TRAY_FRAME_NAME)
        candidates.append(ASSETS_DIR / "dot" / DEFAULT_CHARACTER_ID / "happy.png")

    return candidates


def resolve_character_icon_path(character_id: Any = None) -> Optional[Path]:
    """キャラクターIDからトレイアイコン用ドット絵 (assets/dot/<id>/idle_1.png) を解決する。

    未登録キャラ・不正ID・アセット欠落時は既定キャラ (秘書くん) へフォールバックする。

    Args:
        character_id: キャラクターID (例: "hisho" / "kyle")。

    Returns:
        Optional[Path]: 実在する画像パス。assets 内に候補が無ければ None。
    """
    for path in iter_tray_icon_candidates(character_id):
        if path.is_file():
            return path
    return None


def build_fallback_tray_image() -> Image.Image:
    """画像アセットが一切読めない場合の保険アイコン (琥珀色の丸) を生成する。"""
    image = Image.new("RGBA", TRAY_ICON_SIZE, color=(0, 0, 0, 0))
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    draw.ellipse((4, 4, 60, 60), fill="#A67B5B", outline="#FFFFFF", width=3)
    return image


def load_character_tray_image(character_id: Any = None) -> Image.Image:
    """指定キャラクターのドット絵を通知領域用 (64x64・NEAREST) に変換して返す。

    Args:
        character_id: キャラクターID。

    Returns:
        Image.Image: RGBA 画像。解決できない場合はフォールバック画像。
    """
    path = resolve_character_icon_path(character_id)
    if path is not None:
        try:
            return (
                Image.open(path)
                .convert("RGBA")
                .resize(TRAY_ICON_SIZE, Image.Resampling.NEAREST)
            )
        except Exception as e:
            logger.debug(f"トレイ画像読み込み失敗 ({path}): {e}")
    return build_fallback_tray_image()


class SystemTrayManager:
    """Windows タスクトレイ常駐アイコンを管理するクラス"""

    def __init__(self, gui_instance: Any) -> None:
        """
        Args:
            gui_instance: NeoSecretaryGUI のインスタンス
        """
        self.gui = gui_instance
        self._icon: Optional[Any] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def _current_character_id(self) -> Optional[str]:
        """保存済みの選択キャラクターIDを取得する（取得失敗時は None＝既定キャラ）。

        Notes:
            P2 (2026-09-16 独立査読): 旧実装は起動時のトレイアイコンが常に既定キャラ
            (hisho) 固定で、保存済みの着せ替え状態が反映されなかった。
        """
        try:
            from character_manager import get_character_manager

            return get_character_manager().current_character_id
        except Exception as e:
            logger.debug(f"キャラクター設定の取得をスキップ（既定キャラを使用）: {e}")
            return None

    def _load_tray_image(self) -> Image.Image:
        """トレイアイコン用の画像をロード（選択中キャラ→既定キャラ→生成フォールバック）。

        アセット候補は `iter_tray_icon_candidates`（単一情報源）から取得する。
        """
        for p in iter_tray_icon_candidates(self._current_character_id()):
            if p.is_file():
                try:
                    # 透過PNG対応・RGBA（ファイルハンドルは with で確実に閉じる）
                    with Image.open(p) as img:
                        return img.convert("RGBA").resize(
                            TRAY_ICON_SIZE, Image.Resampling.NEAREST
                        )
                except Exception as e:
                    logger.debug(f"トレイ画像読み込み失敗 ({p}): {e}")

        # フォールバック: 単純な琥珀色の丸アイコンを生成
        return build_fallback_tray_image()

    def update_character_icon(self, character_id: str) -> bool:
        """キャラクター着せ替えに連動してトレイアイコンを差し替える。

        設定画面やペットUIでキャラクター (hisho ⇄ kyle ⇄ ...) が切り替わった際、
        通知領域のアイコンをそのキャラクターのドット絵 (idle_1.png) へ更新する。

        Args:
            character_id: 新しいキャラクターID (例: "hisho" / "kyle")。

        Returns:
            bool: アイコンを更新できた場合 True。トレイ未起動 (pystray 未導入)
                や OS 側の拒否時は False を返し、例外は漏らさない (Fail-Safe)。
        """
        if self._icon is None:
            logger.debug(
                f"タスクトレイ未起動のためアイコン更新をスキップします (char={character_id})"
            )
            return False

        try:
            self._icon.icon = load_character_tray_image(character_id)
        except Exception as e:
            logger.debug(f"トレイアイコン更新に失敗しました (char={character_id}): {e}")
            return False

        logger.info(f"🖥️ [SystemTray] トレイアイコンを '{character_id}' のドット絵へ更新しました")
        return True

    def start(self) -> bool:
        """タスクトレイアイコンを別スレッドで開始する"""
        try:
            import pystray
        except ImportError:
            logger.warning("⚠️ pystray がインストールされていません。タスクトレイ常駐は無効化されます ('pip install pystray' で有効化)")
            return False

        if self._icon is not None:
            return True

        image = self._load_tray_image()

        def on_show_pet(icon, item):
            self.gui.post_action(self.gui.show_pc_pet)

        def on_hide_pet(icon, item):
            self.gui.post_action(self.gui.hide_pc_pet)

        def on_open_settings(icon, item):
            self.gui.post_action(self.gui._open_settings)

        def on_open_calendar(icon, item):
            self.gui.post_action(self.gui._open_calendar)

        def on_open_qr(icon, item):
            self.gui.post_action(self.gui._open_qr_connection)

        def on_toggle_sticky(icon, item):
            def _toggle():
                from ui.sticky_note import DesktopStickyNote
                sticky = DesktopStickyNote.get_instance(self.gui.root)
                sticky.toggle_visibility()
            self.gui.post_action(_toggle)

        def on_quit(icon, item):
            self.request_quit()

        menu = pystray.Menu(
            pystray.MenuItem("🖥️ ペットを画面に呼び出す", on_show_pet, default=True),
            pystray.MenuItem("🙈 ペットを隠す (最小化)", on_hide_pet),
            pystray.MenuItem("📌 デスクトップ付箋 (表示/非表示)", on_toggle_sticky),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⚙️ 設定を開く", on_open_settings),
            pystray.MenuItem("📅 手帳 / カレンダー", on_open_calendar),
            pystray.MenuItem("📱 スマホ接続 (QRコード)", on_open_qr),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ ネオ秘書くんを終了", on_quit),
        )

        self._icon = pystray.Icon(
            "neo_hisho_kun",
            image,
            "ネオ秘書くん",
            menu=menu
        )

        def _run_tray():
            try:
                logger.info("🖥️ [SystemTray] タスクトレイアイコンを開始しました")
                self._icon.run()
            except Exception as e:
                logger.error(f"タスクトレイ実行エラー: {e}")

        self._thread = threading.Thread(target=_run_tray, daemon=True, name="SystemTrayThread")
        self._thread.start()
        return True

    def stop(self) -> None:
        """タスクトレイアイコンを安全に停止・破棄する"""
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
            logger.info("🖥️ [SystemTray] タスクトレイアイコンを停止しました")

    def request_quit(self) -> None:
        """トレイメニューからの終了要求を正式な終了経路 (gui.quit_app) へ委譲する。

        Notes:
            root.quit() は禁止。本アプリは mainloop() を使わない自前ループ
            (main.async_mainloop) で動作するため root.quit() は事実上 no-op で、
            トレイだけが消えてプロセスが残存する (多重起動検知の誤発火・
            2026-09-09 発見)。quit_app (トレイ停止 ＋ quiet_destroy) が
            唯一の正式な終了経路である。
        """
        logger.info("🛑 [SystemTray] 終了要求を受信 → gui.quit_app へ委譲します")
        self.stop()
        self.gui.post_action(self.gui.quit_app)
        logger.info("🛑 [SystemTray] quit_app を post_action キューへ投入しました")


_global_tray_manager: Optional[SystemTrayManager] = None


def init_system_tray(gui_instance: Any) -> Optional[SystemTrayManager]:
    """グローバルなシステムトレイマネージャーを初期化・起動する"""
    global _global_tray_manager
    if _global_tray_manager is None:
        _global_tray_manager = SystemTrayManager(gui_instance)
        _global_tray_manager.start()
    return _global_tray_manager


def get_system_tray() -> Optional[SystemTrayManager]:
    """現在のシステムトレイマネージャーを取得"""
    return _global_tray_manager
