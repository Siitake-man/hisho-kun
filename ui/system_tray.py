"""
ネオ秘書くん - システムタスクトレイ常駐マネージャー (ui/system_tray.py)

Windowsの通知領域（タスクトレイ）に秘書くんアイコンを常駐させ、
PCペットが画面上で非表示・最小化されている時でも、
右クリックメニューやトレイクリックからワンタップで呼び出し・設定変更を可能にする。
"""

import logging
import threading
from pathlib import Path
from typing import Optional, Any
from PIL import Image

logger = logging.getLogger(__name__)

# トレイアイコン用のアセット探索パス
_ASSET_CANDIDATES = [
    Path(__file__).parent.parent / "assets" / "happy.png",
    Path(__file__).parent.parent / "assets" / "dot" / "seal" / "idle_1.png",
    Path(__file__).parent.parent / "assets" / "dot" / "seal" / "happy.png",
]


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

    def _load_tray_image(self) -> Image.Image:
        """トレイアイコン用の画像をロード（見つからない場合はフォールバック生成）"""
        for p in _ASSET_CANDIDATES:
            if p.exists():
                try:
                    img = Image.open(p)
                    # 透過PNG対応・RGBA
                    return img.convert("RGBA").resize((64, 64), Image.Resampling.NEAREST)
                except Exception as e:
                    logger.debug(f"トレイ画像読み込み失敗 ({p}): {e}")

        # フォールバック: 単純な琥珀色の丸アイコンを生成
        img = Image.new("RGBA", (64, 64), color=(0, 0, 0, 0))
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.ellipse((4, 4, 60, 60), fill="#A67B5B", outline="#FFFFFF", width=3)
        return img

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

        def on_quit(icon, item):
            self.stop()
            self.gui.post_action(self.gui.root.quit)

        menu = pystray.Menu(
            pystray.MenuItem("🖥️ ペットを画面に呼び出す", on_show_pet, default=True),
            pystray.MenuItem("🙈 ペットを隠す (最小化)", on_hide_pet),
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
