"""
ネオ秘書くん - 統合手帳ウィンドウ (ui/calendar_window.py)
予定（カレンダー）、TODOタスク、およびボスのトリセツ（長期知見）をタブ管理するレトロ手帳UI。
"""

import logging
import datetime
from collections import defaultdict
import tkinter as tk
import customtkinter as ctk

logger = logging.getLogger(__name__)

class CalendarWindow(ctk.CTkToplevel):
    """
    レトロ手帳風デザインの統合手帳ウィンドウ（Notebook Window）。
    予定帳（カレンダー）、TODOタスク、およびボスのトリセツ（長期知見）をタブ切り替えで管理します。
    """
    def __init__(self, parent_gui, *args, **kwargs):
        super().__init__(parent_gui.root, *args, **kwargs)
        self.parent_gui = parent_gui
        self.title("ネオ秘書くん - 統合手帳 (Notebook)")
        self.geometry("520x620")
        
        self.bg_color = "#F5F5DC"
        self.primary_color = "#A67B5B"
        self.text_color = "#4A3B32"
        self.configure(fg_color=self.bg_color)
        
        self.font_title = ("DotGothic16", 16, "bold") if "DotGothic16" in tk.font.families() else ("Meiryo UI", 14, "bold")
        self.font_body = ("DotGothic16", 13) if "DotGothic16" in tk.font.families() else ("Meiryo UI", 11)
        self.font_small = ("Meiryo UI", 9)
        
        self._build_ui()
        self.refresh_all_data()

    def _build_ui(self):
        # 1. ヘッダー領域
        self.header_frame = ctk.CTkFrame(self, fg_color=self.primary_color, corner_radius=0, height=45)
        self.header_frame.pack(side="top", fill="x")
        self.header_frame.pack_propagate(False)
        
        self.title_label = ctk.CTkLabel(
            self.header_frame, 
            text="📔 秘書くんの統合手帳", 
            font=self.font_title, 
            text_color="#FFFFFF"
        )
        self.title_label.pack(pady=8)
        
        # 2. タブビュー（カレンダー / TODO / ボスのトリセツ）
        self.tabview = ctk.CTkTabview(
            self, 
            fg_color=self.bg_color,
            segmented_button_selected_color=self.primary_color,
            segmented_button_selected_hover_color="#8B634A",
            segmented_button_unselected_color="#E0D8C8",
            segmented_button_unselected_hover_color="#D5CBB8",
            text_color=self.text_color
        )
        self.tabview.pack(fill="both", expand=True, padx=12, pady=(5, 10))
        
        self.tab_events = self.tabview.add("📅 予定")
        self.tab_tasks = self.tabview.add("📋 TODO")
        self.tab_habits = self.tabview.add("🌱 習慣 ＆ 草")
        self.tab_insights = self.tabview.add("🧠 ボスのトリセツ")
        
        self._build_events_tab()
        self._build_tasks_tab()
        self._build_habits_tab()
        self._build_insights_tab()

    # =========================================================================
    # 📅 予定タブ
    # =========================================================================
    def _build_events_tab(self):
        view_bar = ctk.CTkFrame(self.tab_events, fg_color="transparent")
        view_bar.pack(fill="x", padx=5, pady=(2, 6))

        self.event_view_seg = ctk.CTkSegmentedButton(
            view_bar,
            values=["🗓️ 月間 (30日)", "📅 週間 (7日)", "☀️ 日間 (今日)"],
            selected_color=self.primary_color,
            selected_hover_color="#8B634A",
            unselected_color="#E0D8C8",
            unselected_hover_color="#D5CBB8",
            text_color=self.text_color,
            font=("Meiryo UI", 9.5, "bold"),
            command=self._on_event_view_change
        )
        self.event_view_seg.set("🗓️ 月間 (30日)")
        self.event_view_seg.pack(side="left")

        self.events_scroll = ctk.CTkScrollableFrame(self.tab_events, fg_color="transparent")
        self.events_scroll.pack(fill="both", expand=True, padx=5, pady=2)

    def _on_event_view_change(self, value):
        self.load_events(getattr(self, 'all_cached_events', []))

    def load_events(self, events: list):
        """予定一覧を描画（月間・週間・日間に対応）"""
        self.all_cached_events = events
        for widget in self.events_scroll.winfo_children():
            widget.destroy()
            
        if not events:
            lbl = ctk.CTkLabel(self.events_scroll, text="予定はありません。", font=self.font_body, text_color="#8D6E63")
            lbl.pack(pady=30)
            return
            
        now = datetime.datetime.now()
        start_of_today = datetime.datetime(now.year, now.month, now.day)
        mode = self.event_view_seg.get() if hasattr(self, 'event_view_seg') else "🗓️ 月間 (30日)"

        filtered_events = []
        for e in events:
            dt = datetime.datetime.fromtimestamp(e.start_time / 1000)
            if "日間" in mode:
                if dt.date() == now.date():
                    filtered_events.append(e)
            elif "週間" in mode:
                week_end = start_of_today + datetime.timedelta(days=7)
                if start_of_today <= dt < week_end:
                    filtered_events.append(e)
            else:
                filtered_events.append(e)

        if not filtered_events:
            period_name = "今日" if "日間" in mode else ("今週" if "週間" in mode else "今月")
            lbl = ctk.CTkLabel(self.events_scroll, text=f"{period_name}の予定はありません ☕", font=self.font_body, text_color="#8D6E63")
            lbl.pack(pady=30)
            return

        grouped = defaultdict(list)
        for e in filtered_events:
            dt = datetime.datetime.fromtimestamp(e.start_time / 1000)
            date_str = dt.strftime("%Y年%m月%d日 (%a)")
            grouped[date_str].append((e, dt))
            
        for date_str, daily_events in sorted(grouped.items(), key=lambda x: x[1][0][1]):
            date_lbl = ctk.CTkLabel(self.events_scroll, text=f"■ {date_str}", font=self.font_title, text_color=self.primary_color, anchor="w")
            date_lbl.pack(fill="x", pady=(10, 3))
            
            for e, dt in daily_events:
                end_dt = datetime.datetime.fromtimestamp(e.end_time / 1000)
                time_range = f"{dt.strftime('%H:%M')} ~ {end_dt.strftime('%H:%M')}"
                
                card = ctk.CTkFrame(self.events_scroll, fg_color="#FFFFFF", border_color="#E0D8C8", border_width=1, corner_radius=6)
                card.pack(fill="x", pady=3, padx=2)
                
                header_box = ctk.CTkFrame(card, fg_color="transparent")
                header_box.pack(fill="x", padx=8, pady=(4, 0))
                
                ctk.CTkLabel(header_box, text=time_range, font=self.font_small, text_color="#8B634A").pack(side="left")
                ctk.CTkLabel(card, text=e.title, font=self.font_body, text_color=self.text_color, anchor="w", wraplength=420).pack(fill="x", padx=8, pady=(1, 2))
                
                if getattr(e, 'description', None):
                    ctk.CTkLabel(card, text=e.description, font=self.font_small, text_color="#7A6B62", anchor="w", wraplength=420).pack(fill="x", padx=8, pady=(0, 4))

    # =========================================================================
    # 📋 TODOタスクタブ
    # =========================================================================
    def _build_tasks_tab(self):
        add_bar = ctk.CTkFrame(self.tab_tasks, fg_color="transparent")
        add_bar.pack(fill="x", padx=5, pady=(5, 8))
        
        self.task_entry_var = tk.StringVar()
        self.task_entry = ctk.CTkEntry(
            add_bar,
            textvariable=self.task_entry_var,
            placeholder_text="新しいタスクを入力してEnter...",
            font=self.font_body,
            fg_color="#FFFFFF",
            border_color="#A67B5B",
            height=32
        )
        self.task_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.task_entry.bind("<Return>", self._on_add_quick_task)
        
        btn_add = ctk.CTkButton(
            add_bar,
            text="追加",
            width=60,
            height=32,
            font=self.font_body,
            fg_color=self.primary_color,
            hover_color="#8B634A",
            command=self._on_add_quick_task
        )
        btn_add.pack(side="right")
        
        self.tasks_scroll = ctk.CTkScrollableFrame(self.tab_tasks, fg_color="transparent")
        self.tasks_scroll.pack(fill="both", expand=True, padx=5, pady=5)

    def _on_add_quick_task(self, event=None):
        text = self.task_entry_var.get().strip()
        if not text:
            return
        self.task_entry_var.set("")
        
        import database
        task = database.Task(title=text, priority=0)
        database.create_task(task)
        self.refresh_tasks()

    def refresh_tasks(self):
        """TODOタスク一覧を再描画"""
        for widget in self.tasks_scroll.winfo_children():
            widget.destroy()
            
        import database
        tasks = database.get_tasks(status="todo", limit=50)
        
        if not tasks:
            lbl = ctk.CTkLabel(self.tasks_scroll, text="すべてのタスクが完了しています！✨", font=self.font_body, text_color="#2E7D32")
            lbl.pack(pady=30)
            return
            
        pri_colors = {3: "#D32F2F", 2: "#F57C00", 1: "#388E3C", 0: "#757575"}
        pri_labels = {3: "🔥 高", 2: "中", 1: "低", 0: ""}
        
        for t in tasks:
            row = ctk.CTkFrame(self.tasks_scroll, fg_color="#FFFFFF", border_color="#E0D8C8", border_width=1, corner_radius=6)
            row.pack(fill="x", pady=3, padx=2)
            
            def make_complete_cb(task_id=t.id):
                return lambda: self._on_complete_task(task_id)
                
            cb = ctk.CTkCheckBox(
                row,
                text="",
                width=24,
                checkbox_width=20,
                checkbox_height=20,
                fg_color=self.primary_color,
                command=make_complete_cb(t.id)
            )
            cb.pack(side="left", padx=(8, 4), pady=6)
            
            ctk.CTkLabel(row, text=t.title, font=self.font_body, text_color=self.text_color, anchor="w", wraplength=340).pack(side="left", fill="x", expand=True, padx=4)
            
            if t.priority > 0:
                pri_lbl = ctk.CTkLabel(
                    row,
                    text=pri_labels.get(t.priority, ""),
                    font=self.font_small,
                    text_color=pri_colors.get(t.priority, "#757575")
                )
                pri_lbl.pack(side="right", padx=(2, 8))

    def _on_complete_task(self, task_id: int):
        import database
        database.complete_task(task_id)
        self.after(200, self.refresh_tasks)

    # =========================================================================
    # 🌱 習慣 ＆ キズナ草ヒートマップタブ
    # =========================================================================
    def _build_habits_tab(self):
        # 1. 草ヒートマップ表示エリア
        self.heatmap_frame = ctk.CTkFrame(self.tab_habits, fg_color="#FFFFFF", border_color="#E0D8C8", border_width=1, corner_radius=6)
        self.heatmap_frame.pack(fill="x", padx=5, pady=(2, 6))

        header_row = ctk.CTkFrame(self.heatmap_frame, fg_color="transparent")
        header_row.pack(fill="x", padx=10, pady=(6, 2))
        
        self.heatmap_title_lbl = ctk.CTkLabel(header_row, text="🌱 ボスのキズナ草ヒートマップ (直近70日)", font=self.font_body, text_color=self.text_color)
        self.heatmap_title_lbl.pack(side="left")
        
        self.streak_badge_lbl = ctk.CTkLabel(header_row, text="🔥 総ストリーク: 0日", font=self.font_small, text_color="#E65100")
        self.streak_badge_lbl.pack(side="right")

        self.heatmap_canvas = tk.Canvas(self.heatmap_frame, bg="#FFFFFF", height=105, highlightthickness=0)
        self.heatmap_canvas.pack(fill="x", padx=8, pady=(0, 6))

        # 2. 新規習慣のクイック作成バー
        add_bar = ctk.CTkFrame(self.tab_habits, fg_color="#FFFFFF", border_color="#E0D8C8", border_width=1, corner_radius=6)
        add_bar.pack(fill="x", padx=5, pady=(0, 6))

        self.habit_emoji_var = tk.StringVar(value="🌱")
        self.habit_emoji_btn = ctk.CTkButton(
            add_bar, 
            textvariable=self.habit_emoji_var, 
            width=36, 
            height=28, 
            fg_color="#F5F5DC", 
            text_color=self.text_color,
            hover_color="#E0D8C8",
            command=self._on_cycle_habit_emoji
        )
        self.habit_emoji_btn.pack(side="left", padx=4, pady=4)

        self.habit_entry = ctk.CTkEntry(
            add_bar, 
            placeholder_text="新しい習慣（例: 毎日の読書30分、NW学習、ストレッチ）", 
            font=self.font_body,
            height=28,
            fg_color="#F5F5DC",
            border_color="#E0D8C8"
        )
        self.habit_entry.pack(side="left", fill="x", expand=True, padx=4, pady=4)
        self.habit_entry.bind("<Return>", lambda e: self._on_add_habit())

        btn_add = ctk.CTkButton(
            add_bar, 
            text="追加", 
            width=50, 
            height=28, 
            fg_color=self.primary_color, 
            hover_color="#8B634A",
            command=self._on_add_habit
        )
        btn_add.pack(side="right", padx=4, pady=4)

        # 3. 習慣カードリスト（スクロール領域）
        self.habits_scroll = ctk.CTkScrollableFrame(self.tab_habits, fg_color="transparent")
        self.habits_scroll.pack(fill="both", expand=True, padx=5, pady=0)

    def _on_cycle_habit_emoji(self):
        emojis = ["🌱", "📚", "🏃", "💻", "🧘", "🍵", "💪", "📝", "🍅", "🎯"]
        cur = self.habit_emoji_var.get()
        idx = (emojis.index(cur) + 1) % len(emojis) if cur in emojis else 0
        self.habit_emoji_var.set(emojis[idx])

    def _on_add_habit(self):
        text = self.habit_entry.get().strip()
        if not text:
            return
        emoji = self.habit_emoji_var.get()
        
        import database
        from database import Habit
        database.create_habit(Habit(title=text, emoji=emoji))
        self.habit_entry.delete(0, tk.END)
        self.refresh_habits()

    def refresh_habits(self):
        """習慣リストと草ヒートマップを再描画"""
        import database
        
        # 1. 草ヒートマップの描画 (直近70日 = 10週 × 7日)
        self.heatmap_canvas.delete("all")
        heatmap_data = database.get_habit_heatmap_data(days=70)
        
        cell_size = 11
        pad = 2
        start_x = 25
        start_y = 12
        
        # 曜日ラベル (月・水・金)
        days_labels = [("月", 0), ("水", 2), ("金", 4), ("日", 6)]
        for lbl, row_idx in days_labels:
            self.heatmap_canvas.create_text(
                12, start_y + row_idx * (cell_size + pad) + 5,
                text=lbl, fill="#8D6E63", font=("Meiryo UI", 7)
            )

        level_colors = {
            0: "#EFEBE2",  # 未達成 (オフホワイト)
            1: "#A8E6CF",  # 1個達成 (薄緑)
            2: "#56C596",  # 2個達成 (緑)
            3: "#208B5C",  # 3個達成 (濃緑)
            4: "#FFD700"   # 4個以上 (ゴールド)
        }

        # 70日分の正方形を描画
        for idx, item in enumerate(heatmap_data):
            col = idx // 7
            row = item.get("day_of_week", idx % 7)
            x0 = start_x + col * (cell_size + pad)
            y0 = start_y + row * (cell_size + pad)
            x1 = x0 + cell_size
            y1 = y0 + cell_size
            
            fill_col = level_colors.get(item.get("level", 0), "#EFEBE2")
            self.heatmap_canvas.create_rectangle(
                x0, y0, x1, y1,
                fill=fill_col,
                outline="#D7CCC8",
                width=1
            )

        # 2. 習慣一覧カードの再描画
        for widget in self.habits_scroll.winfo_children():
            widget.destroy()

        habits = database.get_habits_with_status()
        if not habits:
            lbl = ctk.CTkLabel(
                self.habits_scroll, 
                text="習慣がまだ登録されていません。\n上の入力欄から毎日の習慣を追加してみましょう！🌱", 
                font=self.font_body, 
                text_color="#8D6E63"
            )
            lbl.pack(pady=25)
            self.streak_badge_lbl.configure(text="🔥 ストリーク: 0日")
            return

        max_streak = max([h["streak"] for h in habits]) if habits else 0
        self.streak_badge_lbl.configure(text=f"🔥 最高ストリーク: {max_streak}日連続")

        for h in habits:
            card = ctk.CTkFrame(self.habits_scroll, fg_color="#FFFFFF", border_color="#E0D8C8", border_width=1, corner_radius=6)
            card.pack(fill="x", pady=3, padx=2)

            left_box = ctk.CTkFrame(card, fg_color="transparent")
            left_box.pack(side="left", fill="both", expand=True, padx=8, pady=6)

            # タイトル・絵文字・ストリークバッジ
            title_row = ctk.CTkFrame(left_box, fg_color="transparent")
            title_row.pack(fill="x")

            emoji_lbl = ctk.CTkLabel(title_row, text=h["emoji"], font=("Meiryo UI", 16))
            emoji_lbl.pack(side="left", padx=(0, 6))

            title_text = h["title"]
            title_lbl = ctk.CTkLabel(title_row, text=title_text, font=self.font_body, text_color=self.text_color)
            title_lbl.pack(side="left")

            if h["streak"] > 0:
                streak_tag = ctk.CTkLabel(title_row, text=f"🔥 {h['streak']}日連続", font=self.font_small, text_color="#E65100")
                streak_tag.pack(side="left", padx=8)

            total_tag = ctk.CTkLabel(title_row, text=f"（累計 {h['total_completed']}回）", font=self.font_small, text_color="#9E9E9E")
            total_tag.pack(side="left")

            # 右側アクションボタン（達成トグル ＆ 削除）
            right_box = ctk.CTkFrame(card, fg_color="transparent")
            right_box.pack(side="right", padx=8, pady=6)

            def make_toggle_cb(h_id=h["id"]):
                return lambda: self._on_toggle_habit(h_id)

            def make_del_cb(h_id=h["id"]):
                return lambda: self._on_delete_habit(h_id)

            is_done = h["completed_today"]
            btn_check = ctk.CTkButton(
                right_box,
                text="✔ 達成！" if is_done else "未完了",
                width=65,
                height=26,
                font=self.font_small,
                fg_color="#4CAF50" if is_done else "#E0D8C8",
                text_color="#FFFFFF" if is_done else self.text_color,
                hover_color="#388E3C" if is_done else "#D5CBB8",
                command=make_toggle_cb(h["id"])
            )
            btn_check.pack(side="left", padx=4)

            btn_del = ctk.CTkButton(
                right_box,
                text="🗑",
                width=24,
                height=26,
                font=self.font_small,
                fg_color="transparent",
                text_color="#BDBDBD",
                hover_color="#FFEBEE",
                command=make_del_cb(h["id"])
            )
            btn_del.pack(side="left")

    def _on_toggle_habit(self, habit_id: int):
        import database
        is_now_done = database.toggle_habit_log(habit_id)
        
        if is_now_done:
            # 達成時に親愛度XP加算 (+10 XP) ＆ 歓喜リアクション
            from character_manager import get_character_manager
            char_mgr = get_character_manager()
            _, did_lvl = char_mgr.add_bond_xp(10)
            
            if hasattr(self.parent_gui, 'animator'):
                self.parent_gui.animator.trigger_reaction("task_complete")
            
            if did_lvl:
                bond = char_mgr.get_bond_info()
                self.parent_gui.update_message(
                    f"🎊 【キズナレベルアップ！ Lv.{bond['level']}】\n"
                    f"習慣達成お見事です！称号: 『{bond['title']}』✨"
                )
            else:
                self.parent_gui.update_message("習慣達成ですね！ボス、素晴らしい継続力です！👏✨")
                
        self.refresh_habits()

    def _on_delete_habit(self, habit_id: int):
        import database
        database.delete_habit(habit_id)
        self.refresh_habits()

    # =========================================================================
    # 🧠 ボスのトリセツ（長期知見）タブ
    # =========================================================================
    def _build_insights_tab(self):
        self.insights_scroll = ctk.CTkScrollableFrame(self.tab_insights, fg_color="transparent")
        self.insights_scroll.pack(fill="both", expand=True, padx=5, pady=5)

    def refresh_insights(self):
        """ボスの知見一覧を再描画"""
        for widget in self.insights_scroll.winfo_children():
            widget.destroy()
            
        import database
        insights = database.get_user_insights(limit=30)
        
        if not insights:
            lbl = ctk.CTkLabel(self.insights_scroll, text="まだボスの知見は記録されていません。\n秘書くんに生活リズムや好みを教えてみてください！", font=self.font_body, text_color="#8D6E63")
            lbl.pack(pady=30)
            return
            
        cat_labels = {
            "Constraint": ("⛔ 制約", "#D32F2F"),
            "Preference": ("⭐ 好み", "#1976D2"),
            "Habit": ("⏰ 習慣", "#388E3C"),
            "Project": ("📁 PJルール", "#7B1FA2")
        }
        
        for ins in insights:
            card = ctk.CTkFrame(self.insights_scroll, fg_color="#FFFFFF", border_color="#E0D8C8", border_width=1, corner_radius=6)
            card.pack(fill="x", pady=3, padx=2)
            
            top_bar = ctk.CTkFrame(card, fg_color="transparent")
            top_bar.pack(fill="x", padx=8, pady=(4, 0))
            
            cat_name, cat_col = cat_labels.get(ins.category, ("知見", "#757575"))
            ctk.CTkLabel(top_bar, text=cat_name, font=self.font_small, text_color=cat_col).pack(side="left")
            ctk.CTkLabel(top_bar, text=f"重要度: {'★' * ins.importance}", font=self.font_small, text_color="#F57C00").pack(side="left", padx=8)
            
            def make_delete_cb(ins_id=ins.id):
                return lambda: self._on_delete_insight(ins_id)
                
            btn_del = ctk.CTkButton(
                top_bar, 
                text="🗑", 
                width=24, 
                height=20, 
                font=self.font_small,
                fg_color="transparent",
                text_color="#BDBDBD",
                hover_color="#FFEBEE",
                command=make_delete_cb(ins.id)
            )
            btn_del.pack(side="right")
            
            ctk.CTkLabel(card, text=ins.content, font=self.font_body, text_color=self.text_color, anchor="w", wraplength=420).pack(fill="x", padx=8, pady=(2, 6))

    def _on_delete_insight(self, insight_id: int):
        import database
        database.delete_user_insight(insight_id)
        self.refresh_insights()

    def refresh_all_data(self):
        """全タブのデータを一括更新"""
        import database
        events = database.get_upcoming_events(days=30)
        self.load_events(events)
        self.refresh_tasks()
        self.refresh_habits()
        self.refresh_insights()

