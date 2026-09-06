#!/usr/bin/env python3
"""
ネオ秘書くん - デスクトップ半透明スマート付箋 (ui/sticky_note.py)

ロードマップ 4.2（画面に貼る Pin to Desktop）および B17（ひとこと付箋秘書）のコア実装。
最前面（Topmost）・半透明（Alpha 88%）・枠なし（Overrideredirect）のモダンな
付箋ウィジェットをデスクトップ上に常駐させ、今日の最重要タスク（アイゼンハワーマトリクス
第1象限: 重要×緊急）を常に視界の端に置きながらワンクリックで完了できる。
"""

import json
import logging
import os
import threading
import tkinter as tk
from typing import Any, Callable, Dict, List, Optional, Tuple
import customtkinter as ctk

import app_paths
import database
from database import Task

logger = logging.getLogger(__name__)

# 付箋表示位置の永続化先 (アプリ共通設定ファイル)。キー: "sticky_note_pos" = {"x": int, "y": int}
STICKY_CONFIG_PATH = app_paths.get_app_root() / "character_config.json"

# 設定ファイル書き込みの直列化ロック (GUIスレッド・HTTPスレッド間の同時書込による JSON 破損の保険)
_POSITION_SAVE_LOCK = threading.Lock()


class DesktopStickyNote:
    """デスクトップ上に半透明で常駐するスマート付箋ウィンドウ。

    Tkinter の Toplevel をベースに、枠なし・透過・ドラッグ移動・タスク完了チェック
    を提供する。
    """

    _instance: Optional["DesktopStickyNote"] = None

    @classmethod
    def get_instance(cls, root: Optional[tk.Tk] = None, on_task_changed: Optional[Callable[[], None]] = None) -> "DesktopStickyNote":
        """シングルトンインスタンスを取得または生成する。"""
        if cls._instance is None:
            if root is None:
                raise ValueError("初回生成時は root ウィンドウの指定が必須です")
            cls._instance = cls(root, on_task_changed)
        return cls._instance

    def __init__(self, root: tk.Tk, on_task_changed: Optional[Callable[[], None]] = None) -> None:
        """DesktopStickyNote を初期化する。

        Args:
            root: Tkinter のメインルートウィンドウ。
            on_task_changed: タスクが完了または追加された際の通知コールバック。
        """
        self.root = root
        self.on_task_changed = on_task_changed
        self.window: Optional[tk.Toplevel] = None
        self._drag_x: int = 0
        self._drag_y: int = 0
        self._is_visible: bool = False
        self._topmost: bool = True
        self._alpha: float = 0.88

        # 画面右上の初期位置
        screen_w = self.root.winfo_screenwidth()
        self._pos_x = screen_w - 320
        self._pos_y = 60
        self._width = 280
        self._height = 360

        # 前回保存された表示位置があれば復元する (モニタ構成変更時は画面内へ補正)
        saved_pos = self._load_saved_position()
        if saved_pos is not None:
            self._pos_x, self._pos_y = self._clamp_to_screen(saved_pos[0], saved_pos[1])
            logger.debug("付箋の前回位置を復元しました: x=%d, y=%d", self._pos_x, self._pos_y)

    def toggle_visibility(self) -> None:
        """付箋の表示 / 非表示を切り替える。"""
        if self._is_visible and self.window and self.window.winfo_exists():
            self.hide()
        else:
            self.show()

    def show(self) -> None:
        """付箋ウィンドウを表示し、最新タスクを読み込む。"""
        if self.window is None or not self.window.winfo_exists():
            self._build_window()
        else:
            self.window.deiconify()
            self.window.lift()

        self._is_visible = True
        self.refresh_tasks()

        # overrideredirect(True) ウィンドウは OS によってフォーカスを得られないことがあるため、
        # 表示時に明示的にフォーカスを要求する (クイック追加入力の UX 保険)。
        try:
            if self.window and self.window.winfo_exists():
                self.window.focus_force()
                entry = getattr(self, "add_entry", None)
                if entry is not None:
                    entry.focus_set()
        except Exception as e:
            logger.debug("付箋フォーカス設定をスキップ: %s", e)

    def hide(self) -> None:
        """付箋ウィンドウを非表示にする。"""
        if self.window and self.window.winfo_exists():
            # 非表示前に実ウィンドウ座標を取得して永続化する (次回起動時に復元)
            self._pos_x = self.window.winfo_x()
            self._pos_y = self.window.winfo_y()
            self._save_position()
            self.window.withdraw()
        self._is_visible = False

    def _build_window(self) -> None:
        """付箋のウィンドウとUIコンポーネントを構築する。"""
        self.window = tk.Toplevel(self.root)
        self.window.overrideredirect(True)
        self.window.geometry(f"{self._width}x{self._height}+{self._pos_x}+{self._pos_y}")
        self.window.wm_attributes("-alpha", self._alpha)
        self.window.wm_attributes("-topmost", self._topmost)
        self.window.configure(bg="#2D2B28")  # スタイリッシュなダークウッド調

        # 外枠フレーム (微細なゴールドボーダー)
        border_frame = tk.Frame(self.window, bg="#A67B5B", padx=1, pady=1)
        border_frame.pack(fill=tk.BOTH, expand=True)

        main_frame = tk.Frame(border_frame, bg="#2D2B28", padx=8, pady=8)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. ドラッグ移動可能なヘッダー
        header_frame = tk.Frame(main_frame, bg="#3E3A36", height=28)
        header_frame.pack(fill=tk.X, pady=(0, 6))
        header_frame.bind("<Button-1>", self._on_drag_start)
        header_frame.bind("<B1-Motion>", self._on_drag_motion)
        header_frame.bind("<ButtonRelease-1>", self._on_drag_end)

        title_lbl = tk.Label(
            header_frame,
            text="📌 今日の最優先タスク",
            font=("Meiryo UI", 9, "bold"),
            bg="#3E3A36",
            fg="#F5F5DC",
        )
        title_lbl.pack(side=tk.LEFT, padx=6, pady=2)
        title_lbl.bind("<Button-1>", self._on_drag_start)
        title_lbl.bind("<B1-Motion>", self._on_drag_motion)
        title_lbl.bind("<ButtonRelease-1>", self._on_drag_end)

        # 閉じる（非表示）ボタン
        close_btn = tk.Label(
            header_frame,
            text="✕",
            font=("Meiryo UI", 9, "bold"),
            bg="#3E3A36",
            fg="#B0A8A0",
            cursor="hand2",
        )
        close_btn.pack(side=tk.RIGHT, padx=6, pady=2)
        close_btn.bind("<Button-1>", lambda e: self.hide())

        # 2. タスクリスト表示エリア
        self.tasks_container = tk.Frame(main_frame, bg="#2D2B28")
        self.tasks_container.pack(fill=tk.BOTH, expand=True, pady=4)

        # 3. フッター (クイック追加入力欄)
        footer_frame = tk.Frame(main_frame, bg="#2D2B28")
        footer_frame.pack(fill=tk.X, pady=(6, 0))

        self.add_entry = ctk.CTkEntry(
            footer_frame,
            placeholder_text="新しいタスクを急ぎ追加...",
            font=("Meiryo UI", 9),
            height=26,
            fg_color="#3E3A36",
            text_color="#F5F5DC",
            border_color="#A67B5B",
        )
        self.add_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.add_entry.bind("<Return>", lambda e: self._on_quick_add())

        add_btn = ctk.CTkButton(
            footer_frame,
            text="＋",
            font=("Meiryo UI", 10, "bold"),
            width=28,
            height=26,
            fg_color="#8D6E63",
            hover_color="#6D4C41",
            command=self._on_quick_add,
        )
        add_btn.pack(side=tk.RIGHT)

    def refresh_tasks(self) -> None:
        """データベースから最優先タスクを取得して描画を更新する。"""
        if not self.window or not self.window.winfo_exists():
            return

        for child in self.tasks_container.winfo_children():
            child.destroy()

        try:
            # ※ 実在する database.get_tasks を使用する (status=None で todo + in_progress 取得)。
            # 旧 get_active_tasks() は存在しない関数で、毎回 AttributeError になっていた。
            active_tasks = database.get_tasks(limit=50)
            # 第1象限（重要×緊急）または優先度高を上位にソート
            priority_tasks: List[Task] = []
            normal_tasks: List[Task] = []

            for t in active_tasks:
                # Task モデルの実フィールドは importance_flag / urgency_flag (Optional[bool])
                is_urgent = bool(getattr(t, "urgency_flag", False))
                is_important = bool(getattr(t, "importance_flag", False))
                if is_urgent or is_important or (t.priority and t.priority >= 2):
                    priority_tasks.append(t)
                else:
                    normal_tasks.append(t)

            display_tasks = (priority_tasks + normal_tasks)[:5]  # 最大5件表示

            if not display_tasks:
                no_task_lbl = tk.Label(
                    self.tasks_container,
                    text="🎉 現在、保留中のタスクはありません！\nゆっくりお茶でもどうぞ☕",
                    font=("Meiryo UI", 9),
                    bg="#2D2B28",
                    fg="#A09890",
                    pady=20,
                )
                no_task_lbl.pack(fill=tk.BOTH, expand=True)
                return

            for task in display_tasks:
                self._render_task_item(task)

        except Exception as e:
            logger.error("付箋タスク更新エラー: %s", e)

    def _render_task_item(self, task: Task) -> None:
        """1件のタスク行を描画する。"""
        row = tk.Frame(self.tasks_container, bg="#36322E", padx=6, pady=4)
        row.pack(fill=tk.X, pady=2)

        # 完了チェックボタン
        check_btn = tk.Label(
            row,
            text="◯",
            font=("Meiryo UI", 10, "bold"),
            bg="#36322E",
            fg="#A67B5B",
            cursor="hand2",
            padx=4,
        )
        check_btn.pack(side=tk.LEFT)
        check_btn.bind("<Button-1>", lambda e, tid=task.id: self._on_complete_task(tid))

        # バッジ（緊急・重要）
        badge_text = ""
        badge_color = "#A09890"
        task_is_important = bool(getattr(task, "importance_flag", False))
        task_is_urgent = bool(getattr(task, "urgency_flag", False))
        if task_is_important and task_is_urgent:
            badge_text = "[最優先] "
            badge_color = "#FF8A80"
        elif task_is_urgent:
            badge_text = "[至急] "
            badge_color = "#FFD180"
        elif task_is_important:
            badge_text = "[重要] "
            badge_color = "#80D8FF"

        # タイトル
        title_text = f"{badge_text}{task.title}"
        title_lbl = tk.Label(
            row,
            text=title_text,
            font=("Meiryo UI", 9),
            bg="#36322E",
            fg=badge_color if badge_text else "#F5F5DC",
            anchor="w",
            wraplength=200,
            justify=tk.LEFT,
        )
        title_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

    def _on_complete_task(self, task_id: Optional[int]) -> None:
        """タスク完了処理。"""
        if task_id is None:
            return
        try:
            database.complete_task(task_id)
            logger.info("付箋からタスクID=%d を完了にしました", task_id)
            self.refresh_tasks()
            if self.on_task_changed:
                self.on_task_changed()
        except Exception as e:
            logger.error("タスク完了エラー: %s", e)

    def _on_quick_add(self) -> None:
        """クイックタスク追加処理。"""
        title = self.add_entry.get().strip()
        if not title:
            return
        try:
            # デフォルトで「重要×緊急」タスクとして作成する。
            # ※ database.create_task の契約は Task モデル第1引数 (キーワード引数は TypeError となる)
            task = Task(
                title=title,
                priority=2,
                importance_flag=True,
                urgency_flag=True,
            )
            database.create_task(task)
            self.add_entry.delete(0, tk.END)
            self.refresh_tasks()
            if self.on_task_changed:
                self.on_task_changed()
        except Exception as e:
            logger.error("タスククイック追加エラー: %s", e)

    def _load_saved_position(self) -> Optional[Tuple[int, int]]:
        """character_config.json から前回の付箋表示位置を読み込む。

        Returns:
            Optional[Tuple[int, int]]: 保存済みの (x, y) 座標。未保存・破損時は None。
        """
        try:
            if not STICKY_CONFIG_PATH.exists():
                return None
            with open(STICKY_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return None
            pos = data.get("sticky_note_pos")
            if isinstance(pos, dict):
                x = int(pos.get("x", -1))
                y = int(pos.get("y", -1))
                if x >= 0 and y >= 0:
                    return (x, y)
        except Exception as e:
            logger.error("付箋位置の読み込みエラー: %s", e)
        return None

    def _clamp_to_screen(self, x: int, y: int) -> Tuple[int, int]:
        """保存済み座標が画面外 (モニタ構成変更等) の場合に可視範囲へ補正する。

        Args:
            x: 補正前の X 座標。
            y: 補正前の Y 座標。

        Returns:
            Tuple[int, int]: 画面内に収まるよう補正された (x, y) 座標。
        """
        try:
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
        except Exception as e:
            logger.debug("画面サイズ取得に失敗したため座標補正をスキップ: %s", e)
            return (x, y)
        # ヘッダー (ドラッグ掴み領域) が必ず画面内に残るよう余白を保証する
        min_x = -(self._width - 60)
        max_x = max(0, screen_w - 60)
        max_y = max(0, screen_h - 60)
        return (min(max(x, min_x), max_x), min(max(y, 0), max_y))

    def _save_position(self) -> None:
        """現在の付箋表示位置を character_config.json へ保存する。

        既存の設定キー (current_character / bond_xp / wandering_enabled 等) を
        読み込んだ上で保護する Read-Modify-Write 方式を採用し、他機能の設定を
        破壊しない。書き込みは一時ファイル経由のアトミック置換 (os.replace) で
        行い、プロセス中断等による JSON 破損を防止する。
        """
        with _POSITION_SAVE_LOCK:
            try:
                data: Dict[str, Any] = {}
                if STICKY_CONFIG_PATH.exists():
                    with open(STICKY_CONFIG_PATH, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                        if isinstance(loaded, dict):
                            data = loaded
                data["sticky_note_pos"] = {"x": int(self._pos_x), "y": int(self._pos_y)}
                tmp_path = STICKY_CONFIG_PATH.with_suffix(".json.tmp")
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                os.replace(tmp_path, STICKY_CONFIG_PATH)
                logger.debug("付箋位置を保存しました: x=%d, y=%d", self._pos_x, self._pos_y)
            except Exception as e:
                logger.error("付箋位置の保存エラー: %s", e)

    def _on_drag_end(self, event: Optional[tk.Event]) -> None:
        """ドラッグ終了 (マウスボタン解放) 時に現在位置を永続化する。

        Args:
            event: Tkinter のマウスイベント (ボタン解放時に自動供給、未使用)。
        """
        if self.window and self.window.winfo_exists():
            self._pos_x = self.window.winfo_x()
            self._pos_y = self.window.winfo_y()
        self._save_position()

    def _on_drag_start(self, event: tk.Event) -> None:
        """ドラッグ開始時の座標を記録。"""
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag_motion(self, event: tk.Event) -> None:
        """ドラッグ中のウィンドウ追従移動。"""
        if not self.window:
            return
        dx = event.x - self._drag_x
        dy = event.y - self._drag_y
        self._pos_x = self.window.winfo_x() + dx
        self._pos_y = self.window.winfo_y() + dy
        self.window.geometry(f"+{self._pos_x}+{self._pos_y}")


# 後方互換エイリアス
StickyNoteWindow = DesktopStickyNote
DraggableStickyNote = DesktopStickyNote
