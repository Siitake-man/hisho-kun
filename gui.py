"""
ネオ秘書くん - GUIモジュール (gui.py)

CustomTkinterを用いたUIコンポーネント。
背景透過のキャラクターウィンドウと、会話用の吹き出しUIを提供します。
各サブウィンドウ（設定、手帳、付箋、QR接続）は ui/ パッケージに Deep Module 化されています。
"""
import queue
import time
import os
import customtkinter as ctk
import tkinter as tk
from typing import Callable, Optional, Dict, Any, List
from pathlib import Path
import logging

from PIL import Image, ImageTk

# UIパッケージからのサブウィンドウ・ダイアログのインポート (Deep Module Seam)
from ui.qr_dialog import QRCodeConnectionDialog
from ui.settings_window import SettingsWindow, AddMCPServerDialog, SuggestSettingsDialog
from ui.calendar_window import CalendarWindow
from ui.sticky_note import StickyNoteWindow, DraggableStickyNote
from tour_engine import get_tour_engine
from ui.pomodoro import PomodoroMixin
from ui.radial_menu import RadialMenuMixin
from ui.tour_overlay import TourOverlayMixin
from llm_factory import LLMFactory

logger = logging.getLogger(__name__)

# CustomTkinterの基本設定
ctk.set_appearance_mode("light")  # レトロモダンなクリーム色をベースにするため
ctk.set_default_color_theme("green") # デフォルトテーマ


class NeoSecretaryGUI(PomodoroMixin, RadialMenuMixin, TourOverlayMixin):
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

    def post_action(self, func, *args, **kwargs):
        """別スレッド（HTTPサーバー等）から安全にメインGUIスレッドへ処理をキューイング

        キーワード引数も透過的に転送する（例: set_pet_state(state, duration_ms=6000)）。
        """
        self._action_queue.put((func, args, kwargs))

    def process_action_queue(self):
        """メインループ内で定期的にキューを安全に消化"""
        while not self._action_queue.empty():
            try:
                func, args, kwargs = self._action_queue.get_nowait()
                func(*args, **kwargs)
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
            font=("DotGothic16", 9, "bold") if "DotGothic16" in tk.font.families() else ("Meiryo UI", 9, "bold"),
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
        self.message_box.pack(pady=(4, 2), padx=8, fill=tk.BOTH, expand=True)
        self.message_box.insert("1.0", "おはようございます！\n本日のご予定はいかがなさいますか？")
        self.message_box.configure(state="disabled")

        # URLリンクがある場合に動的表示するアクションボタン
        self.current_link_url = ""
        self.link_btn = ctk.CTkButton(
            self.bubble_frame,
            text="🌐 リンクをブラウザで開く",
            font=("Meiryo UI", 9.5, "bold"),
            fg_color="#1565C0",
            hover_color="#0D47A1",
            height=24,
            corner_radius=4,
            command=self._open_current_link
        )
        # 初期状態は非表示

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
        # 徘徊モード（デスクトップ散歩）: 設定は character_config.json に永続化
        from character_manager import get_character_manager as _get_cm
        self.wandering_enabled = _get_cm().wandering_enabled
        self.animator.wandering_enabled = self.wandering_enabled
        self.pet_state = "idle"
        self.anim_tick = 0
        self.mascot_images: Dict[str, ImageTk.PhotoImage] = {}
        self.mascot_pil_images: Dict[str, Image.Image] = {}
        self.mascot_flip_images: Dict[str, ImageTk.PhotoImage] = {}
        self._walk_flip_state: bool = False
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

        # 🎓 初回起動検出 → ツアー自動開始（K4-1: 1.5秒に短縮）
        self.root.after(1500, self._check_first_launch_tour)

        # ⚠️ LLM APIキー有無チェック (C-4 / K0-3)
        self.root.after(2500, self._check_api_key_warning)

    def _load_mascot_assets(self):
        """ドット絵スプライト画像をロード（キャラクタースキン対応）"""
        from character_manager import get_character_manager
        char_mgr = get_character_manager()
        current_char = char_mgr.current_character_id
        assets_dir = Path(__file__).parent / "assets"
        
        all_sprites = [
            # 基本・視線
            "idle_1", "idle_2",
            "walk_1", "walk_2",
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
        
        # 画像キャッシュをクリアして再構築
        self.mascot_images.clear()
        self.mascot_pil_images.clear()
        self.mascot_flip_images.clear()
        
        # 自キャラのフォールバック用基本画像 (idle_1) を先に取得
        char_dot_dir = assets_dir / "dot" / current_char
        default_idle_path = char_dot_dir / "idle_1.png"
        if not default_idle_path.exists():
            default_idle_path = char_dot_dir / "idle.png"

        default_pil = None
        if default_idle_path.exists():
            try:
                default_pil = Image.open(default_idle_path).convert("RGBA")
            except Exception as e:
                logger.error(f"デフォルト idle ロード失敗 ({default_idle_path}): {e}")

        for name in all_sprites:
            p = char_dot_dir / f"{name}.png"
            if p.exists():
                try:
                    pil_img = Image.open(p).convert("RGBA")
                    self.mascot_pil_images[name] = pil_img
                    self.mascot_images[name] = ImageTk.PhotoImage(pil_img)
                    continue
                except Exception as e:
                    logger.error(f"画像ロード失敗 ({p}): {e}")
            
            # 自キャラの dot 内に対象フレームが無い場合は、自キャラの idle_1 で安全に代用
            if default_pil is not None:
                self.mascot_pil_images[name] = default_pil
                self.mascot_images[name] = ImageTk.PhotoImage(default_pil)

    def switch_character_skin(self, char_id: str):
        """キャラクタースキンを切り替える"""
        from character_manager import get_character_manager
        char_mgr = get_character_manager()
        if char_mgr.set_character(char_id):
            self._load_mascot_assets()
            info = char_mgr.get_current_character()
            # ヘッダータイトルの更新
            if hasattr(self, 'header_title') and self.header_title.winfo_exists():
                self.header_title.configure(text=f"{info['emoji']} ネオ{info['name']}")
            # Canvas画像アイテムを確実に再生成
            if self.mascot_img_item is not None:
                try:
                    self.char_canvas.delete(self.mascot_img_item)
                except Exception:
                    pass
                self.mascot_img_item = None
            self._render_mascot("happy")
            import random
            greeting = random.choice(info["greetings"])
            self.update_message(f"【{info['emoji']} {info['name']} に変身！】\n{greeting}")

    def _render_effects(self):
        """集中時の炎（🔥）・オーラ・パーティクルをCanvasに描画"""
        self.char_canvas.delete("effect_item")
        if not hasattr(self, 'animator') or not self.animator.effects:
            return

        cx, cy = 170, 135
        items = self.animator.effects.update_particles(cx, cy)
        for item in items:
            if item["type"] == "oval":
                coords = item["coords"]
                self.char_canvas.create_oval(
                    coords[0], coords[1], coords[2], coords[3],
                    outline=item.get("color", "#FF5722"),
                    fill=item.get("fill", ""),
                    width=item.get("width", 1),
                    tags="effect_item"
                )

        # エフェクトをキャラクター画像の背後（下層）へ配置
        if self.mascot_img_item is not None:
            self.char_canvas.tag_lower("effect_item", self.mascot_img_item)

    def _get_flipped_image(self, frame_name: str):
        """左右反転したフレーム画像を取得します（徘徊の左移動用・キャッシュ付き）。"""
        if frame_name in self.mascot_flip_images:
            return self.mascot_flip_images[frame_name]
        pil_img = self.mascot_pil_images.get(frame_name)
        if pil_img is None:
            return None
        flipped = ImageTk.PhotoImage(pil_img.transpose(Image.FLIP_LEFT_RIGHT))
        self.mascot_flip_images[frame_name] = flipped
        return flipped

    def _render_mascot(self, frame_name: str, flip: bool = False):
        """Canvas 上のマスコット画像を更新描画（呼吸・バウンス物理座標反映）"""
        img = self.mascot_images.get(frame_name)
        if flip:
            flipped = self._get_flipped_image(frame_name)
            if flipped is not None:
                img = flipped
        
        # 呼吸・弾力バウンスの上下オフセットを算出
        offset_y = 0
        if hasattr(self, 'animator') and hasattr(self.animator, 'get_bounce_transform'):
            _, _, offset_y = self.animator.get_bounce_transform()

        target_y = 135 + offset_y

        if img:
            if self.mascot_img_item is None:
                self.mascot_img_item = self.char_canvas.create_image(170, target_y, image=img)
            else:
                self.char_canvas.coords(self.mascot_img_item, 170, target_y)
                self.char_canvas.itemconfig(self.mascot_img_item, image=img)
        else:
            # フォールバック描画
            self.char_canvas.delete("fallback")
            self.char_canvas.create_oval(120, target_y - 50, 220, target_y + 50, fill="#A67B5B", outline="#4A3B32", width=3, tags="fallback")
            self.char_canvas.create_text(170, target_y, text="秘書くん", fill="#FFFFFF", font=("Meiryo UI", 12, "bold"), tags="fallback")

    def _schedule_animation(self):
        """アニメーションの定期実行ループ (PetAnimator 連携による自律＆共感アニメーション)"""
        self.anim_tick += 1
        delay = 350
        
        # 1. ポモドーロタイマーカウント処理 (1秒ごとに減算)
        if self.pomodoro_active and self.pomodoro_remaining_seconds > 0:
            if self.anim_tick % 3 == 0:  # 約1秒ごと
                self.pomodoro_remaining_seconds -= 1
                mins = self.pomodoro_remaining_seconds // 60
                secs = self.pomodoro_remaining_seconds % 60
                mode_label = "☕ 休憩" if self.pomodoro_is_break else "🍅 集中"
                if hasattr(self, 'header_title') and self.header_title.winfo_exists():
                    self.header_title.configure(text=f"🤖 ネオ秘書くん [{mode_label} {mins:02d}:{secs:02d}]")
                
                # ポモドーロ円形ネオンアークの更新
                self._draw_pomodoro_arc()

                if self.pomodoro_remaining_seconds <= 0:
                    self._on_pomodoro_completed()

        # 2. 集中・炎エフェクトパーティクルの描画更新
        self._render_effects()

        # 3. カーソルホバー時のなでなで優先処理
        if self.is_hovered and self.animator.current_state == "idle":
            self._render_mascot("happy")
            delay = 300
        elif self.last_mouse_dir in ("left", "right", "up", "down") and self.animator.current_state == "idle" and not self.is_hovered:
            # 待機中かつマウス移動時は視線追従
            self._render_mascot(f"look_{self.last_mouse_dir}")
            delay = 350
        else:
            # 4. PetAnimatorによるフレーム進行（お茶、読書、ストレッチ、タスク完了ジャンプ等）
            frame_name = self.animator.tick()
            self._render_mascot(frame_name)

            # 5. 徘徊モード: walk 状態の間はウィンドウを画面下端で横移動
            if getattr(self, "wandering_enabled", False) and self.animator.current_state == "walk":
                self._step_walk()

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
        """クリック時のサークルメニュー展開と、なでなで親愛度リアクション"""
        self._start_move(event)
        self.toggle_circle_menu()
        
        if not self.pomodoro_active and self.pet_state in ("idle", "happy", "tea", "reading"):
            from character_manager import get_character_manager
            char_mgr = get_character_manager()
            
            # なでなで触感リアクション（ハートマーク💖＆パーティクル）
            if hasattr(self, 'animator') and hasattr(self.animator, 'effects'):
                self.animator.effects.set_effect("heart")
            self.set_pet_state("pet_love", duration_ms=2500)
            
            # 親愛度XP加算 (+5 XP)
            now = time.time()
            if now - getattr(char_mgr, 'last_pet_time', 0.0) > 3.0:
                char_mgr.last_pet_time = now
                _, did_lvl_up = char_mgr.add_bond_xp(5)
                bond = char_mgr.get_bond_info()
                
                if did_lvl_up:
                    self.animator.trigger_reaction("task_complete")
                    self.update_message(
                        f"🎊 【キズナレベルアップ！ Lv.{bond['level']}】\n"
                        f"称号: 『{bond['title']}』\n"
                        f"{bond['desc']}✨"
                    )
                else:
                    self.update_message(
                        f"えへへ、くすぐったいです！🥰 (親愛度: {bond['xp']} XP)\n"
                        f"ボス、呼び出したい機能を選んでくださいね！"
                    )
            else:
                self.update_message("えへへ、くすぐったいです！🥰\nボス、呼び出したい機能を選んでくださいね！")
                
            # 🎓 ツアー実行中（Step 1: greeting）なら、撫でた後に自動で次へ進む
            e = get_tour_engine()
            if e.is_active and e.current_index == 0:
                self.root.after(1200, lambda: self._do_tour_action("next"))
                
        elif self.pomodoro_active:
            # ポモドーロ中は集中メッセージを再確認表示
            mins = self.pomodoro_remaining_seconds // 60
            secs = self.pomodoro_remaining_seconds % 60
            mode_label = "☕ 休憩中" if self.pomodoro_is_break else "🍅 集中中"
            self.update_message(f"【{mode_label} ({mins:02d}:{secs:02d})】\nボス、ゾーンを維持していきましょう！🔥")

    def _on_pet_release(self, event):
        """ドラッグ終了"""
        if self.pet_state == "alarm_ask" and not getattr(self, '_waiting_approval', False):
            self.set_pet_state("idle")

    def _build_context_menu(self):
        """最新のプロバイダ・モデル選択状態を反映したメニューを動的に生成"""
        from llm_factory import get_llm_factory
        factory = get_llm_factory()
        
        menu = tk.Menu(self.root, tearoff=0, bg="#F5F5DC", fg="#4A3B32", font=("Meiryo UI", 10))
        
        # ☀️ 朝会/終礼ブリーフィング（Phase L3）
        import briefing_engine
        current_mode = briefing_engine.get_current_briefing_mode()
        b_label = "☀️ 今日の朝会ブリーフィング" if current_mode in ("morning", "day") else "🌙 本日の終礼日報まとめ"
        menu.add_command(label=b_label, command=self._show_briefing)
        
        menu.add_command(label="📔 統合手帳（予定・TODO・知見）", command=self._open_calendar)
        menu.add_command(label="📌 新しい付箋を貼る", command=self._on_create_quick_sticky)
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
        
        # LLMモデル切り替えサブメニュー（設定済みプロバイダのみスマート表示）
        llm_menu = tk.Menu(menu, tearoff=0, bg="#F5F5DC", fg="#4A3B32", font=("Meiryo UI", 10))
        
        presets = factory.list_presets(only_configured=True)
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
            
        llm_menu.add_separator()
        llm_menu.add_command(label="⚙ 新しいLLMを追加・設定...", command=self._open_settings)
        menu.add_cascade(label="🧠 LLMモデル切り替え", menu=llm_menu)
            
        # キャラクタースキン切り替えサブメニュー
        from character_manager import get_character_manager
        char_mgr = get_character_manager()
        current_char = char_mgr.current_character_id
        
        skin_menu = tk.Menu(menu, tearoff=0, bg="#F5F5DC", fg="#4A3B32", font=("Meiryo UI", 10))
        for char_info in char_mgr.get_all_characters():
            cid = char_info["id"]
            is_cur = (cid == current_char)
            prefix = "● " if is_cur else "   "
            skin_menu.add_command(
                label=f"{prefix}{char_info['emoji']} {char_info['name']} ({char_info['title']})",
                command=lambda c=cid: self.switch_character_skin(c)
            )
        menu.add_cascade(label="🎭 キャラクタースキン変更", menu=skin_menu)
        self.wandering_var = tk.BooleanVar(value=getattr(char_mgr, "wandering_enabled", False))
        menu.add_checkbutton(
            label="🚶 徘徊モード（デスクトップ散歩）",
            variable=self.wandering_var,
            command=self._toggle_wandering
        )
        menu.add_command(label="🎓 使い方ツアー", command=self._start_tour)
        menu.add_command(label="💡 サジェストソース設定", command=lambda: SuggestSettingsDialog(self))
        menu.add_command(label="⚙ API・MCP設定", command=self._open_settings)
        menu.add_separator()
        menu.add_command(label="❌ 終了", command=self.root.destroy)
        return menu

    def _toggle_wandering(self) -> None:
        """徘徊モード（デスクトップ散歩）の ON/OFF を切り替え、設定を永続化します。"""
        enabled = bool(self.wandering_var.get())
        self.wandering_enabled = enabled
        if hasattr(self, "animator"):
            self.animator.wandering_enabled = enabled
        try:
            from character_manager import get_character_manager
            get_character_manager().set_wandering_enabled(enabled)
        except Exception as e:
            logger.error(f"徘徊モード設定の保存に失敗: {e}")
        self.update_message(f"🚶 徘徊モードを【{'ON' if enabled else 'OFF'}】にしました！散歩中は画面下をテクテク移動します。")
        logger.info(f"徘徊モード切替: {enabled}")

    def _step_walk(self) -> None:
        """徘徊モード: walk 状態の間、ペットウィンドウを画面下端に沿って横移動させます。"""
        try:
            animator = self.animator
            direction = getattr(animator, "walk_direction", 1)
            screen_w = self.root.winfo_screenwidth()
            pet_w = self.root.winfo_width() or 300
            cur_x = self.root.winfo_x()
            new_x = max(0, min(screen_w - pet_w, cur_x + direction * 8))
            if new_x in (0, screen_w - pet_w):
                animator.walk_direction *= -1
                direction = animator.walk_direction
            self.root.geometry(f"+{new_x}+{self.root.winfo_y()}")
            flip = direction < 0
            if flip != getattr(self, "_walk_flip_state", False):
                self._walk_flip_state = flip
            self._render_mascot(animator.get_current_frame(), flip=flip)
        except Exception as e:
            logger.debug(f"徘徊移動スキップ: {e}")

    def _show_briefing(self) -> None:
        """朝会/終礼ブリーフィングを生成して吹き出しに表示（Phase L3）"""
        try:
            import briefing_engine
            report = briefing_engine.generate_briefing()
            short_text = f"【{report.mode_label}】\n{report.greeting}\n\n🌡️ 天気: {report.weather_summary['desc']} ({report.weather_summary['temperature']:.1f}°C)\n📅 予定: {len(report.events_today)}件 | 📝 残TODO: {len(report.active_tasks)}件\n\n{report.encouragement}"
            self.update_message(short_text)
            self.set_pet_state("happy", duration_ms=5000)
        except Exception as e:
            logger.error(f"ブリーフィング生成エラー: {e}")
            self.update_message("申し訳ありません、ブリーフィングの生成中にエラーが発生しました。")

    def _on_create_quick_sticky(self):
        """メニューから手動でクイックに新しい付箋を作成・表示"""
        import database
        # ペットの近く（やや右下）にデフォルト配置
        x = max(50, self.root.winfo_x() - 150)
        y = max(50, self.root.winfo_y() + 50)
        note = database.StickyNote(
            content="",
            color="#FFEB3B",
            position_x=x,
            position_y=y,
            width=200,
            height=200
        )
        note_id = database.create_sticky_note(note)
        note.id = note_id
        win = StickyNoteWindow(self, note)
        self.sticky_windows[note_id] = win
        win.textbox.focus_set()
        self.update_message("📌 デスクトップに新しい付箋を貼りました！\n自由にメモを書いてくださいね。")

    def _open_qr_connection(self):
        """スマホDesk Pet接続用のQRコードダイアログを開く"""
        # QRペアリング中のみトークン配布API(/api/auth/token)を開放する (Fail-Closed設計)
        try:
            from local_sync_server import get_sync_token_manager
            get_sync_token_manager().unlock_pairing(duration_sec=600)
        except Exception as e:
            logger.warning(f"ペアリングモード開放に失敗しました: {e}")
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

    def refresh_calendar_if_open(self):
        """統合手帳が開かれている場合のみデータを再読み込みする（バックグラウンド登録・iCal同期後の呼び出し用）"""
        try:
            if self.calendar_window is not None and self.calendar_window.winfo_exists():
                # 重い全タブ再構築を避け、予定データの軽量リフレッシュを優先する
                # （refresh_events_only は後方互換のため不在時は従来の全更新へフォールバック）
                if hasattr(self.calendar_window, "refresh_events_only"):
                    self.calendar_window.refresh_events_only()
                else:
                    self.calendar_window.refresh_all_data()
        except Exception as e:
            logger.warning(f"手帳の自動リフレッシュに失敗: {e}")

    def show_pc_pet(self):
        """PC側のペットウィンドウを表示・最前面化する"""
        try:
            self.auto_minimize_on_link = False
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

    def _open_current_link(self):
        """サジェスト内のURLリンクを既定のWebブラウザで開く"""
        if self.current_link_url:
            import webbrowser
            try:
                webbrowser.open(self.current_link_url)
                logger.info(f"ブラウザでURLを開きました: {self.current_link_url}")
            except Exception as e:
                logger.error(f"ブラウザ起動エラー: {e}")

    def update_message(self, text: str):
        """吹き出しのメッセージを更新するメソッド（スクロール対応 ＆ URLリンク自動検出）"""
        import re
        self.message_box.configure(state="normal")
        self.message_box.delete("1.0", tk.END)
        self.message_box.insert("1.0", text)
        self.message_box.configure(state="disabled")
        self.message_box.see("1.0")  # 先頭を表示

        # テキスト内のURL（http/https）を正規表現で検出
        urls = re.findall(r'https?://[^\s)\]"\'>]+', text)
        if urls and hasattr(self, 'link_btn'):
            self.current_link_url = urls[0]
            self.link_btn.pack(pady=(0, 4), padx=8, fill=tk.X)
        elif hasattr(self, 'link_btn'):
            self.current_link_url = ""
            self.link_btn.pack_forget()

    def run(self):
        """Tkinterのメインループを開始"""
        logger.info("GUIアプリケーションを開始します")
        self.root.mainloop()
    def _check_api_key_warning(self) -> None:
        """LLM APIキーが未設定の場合、吹き出しに警告を表示する (C-4 / K0-3)。"""
        try:
            if not LLMFactory.check_any_api_key_configured():
                self.update_message(
                    "⚠️ AIモデルが利用できません！\n\n"
                    "【原因】.env ファイルにLLMのAPIキーが設定されていません。\n"
                    "【対処】⚙ 設定（右下）→ AIモデルタブからキーを設定してください。\n\n"
                    "ローカルLLM（LM Studio等）を使う場合はキー不要です。"
                )
                logger.warning("⚠️ LLM APIキーが未設定です。GUIに警告を表示しました。")
        except Exception as e:
            logger.debug(f"APIキーチェックスキップ: {e}")

# 後方互換エイリアス
ModernSecretaryGUI = NeoSecretaryGUI

if __name__ == "__main__":
    # ログ設定
    logging.basicConfig(level=logging.INFO)
    
    # 起動テスト
    app = NeoSecretaryGUI()
    app.run()
