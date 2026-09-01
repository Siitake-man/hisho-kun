"""
ネオ秘書くん - 統合手帳ウィンドウ (ui/calendar_window.py)
予定（カレンダー）、TODOタスク、およびボスのトリセツ（長期知見）をタブ管理するレトロ手帳UI。
"""

import logging
import datetime
from typing import Dict, List, Optional, Tuple
import tkinter as tk
import customtkinter as ctk

import database

logger = logging.getLogger(__name__)

# 手帳が取得する予定の期間窓（過去/未来・日数）。
# 月間ビューが過去日を含めて描画できるよう、get_upcoming_events（今日以降限定）ではなく
# この窓で get_events_between() を使う。
EVENT_RANGE_PAST_DAYS = 120
EVENT_RANGE_FUTURE_DAYS = 200

# 手帳を開いている間の予定自動リフレッシュ周期（ミリ秒）。
# 開きっぱなしの間にAIチャット/スマホ/MCP/webhookで登録された予定を取り込む。
EVENT_AUTO_REFRESH_INTERVAL_MS = 60_000

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

        # 開きっぱなしの間に外部経路（AIチャット/スマホ/MCP/webhook）で登録された
        # 予定を反映するための軽量自動リフレッシュ（手帳が閉じたら自動停止する）。
        self._auto_refresh_job: Optional[str] = None
        self.bind("<FocusIn>", self._on_focus_in)
        self._schedule_auto_refresh()

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
        view_bar.pack(fill="x", padx=5, pady=(2, 4))

        self.event_view_seg = ctk.CTkSegmentedButton(
            view_bar,
            values=["🗓️ 月間", "📅 週間", "☀️ 日間"],
            selected_color=self.primary_color,
            selected_hover_color="#8B634A",
            unselected_color="#E0D8C8",
            unselected_hover_color="#D5CBB8",
            text_color=self.text_color,
            font=("Meiryo UI", 9.5, "bold"),
            command=self._on_event_view_change
        )
        self.event_view_seg.set("🗓️ 月間")
        self.event_view_seg.pack(side="left")

        # 期間ナビゲーションバー（◀ ラベル ▶ ＆ 今日へ戻る）
        nav_bar = ctk.CTkFrame(self.tab_events, fg_color="transparent")
        nav_bar.pack(fill="x", padx=5, pady=(0, 2))

        btn_prev = ctk.CTkButton(
            nav_bar, text="◀", width=32, height=26,
            font=self.font_body, fg_color=self.primary_color, hover_color="#8B634A",
            command=self._on_prev_period
        )
        btn_prev.pack(side="left", padx=(2, 4))

        self.period_label = ctk.CTkLabel(nav_bar, text="", font=self.font_title, text_color=self.text_color)
        self.period_label.pack(side="left", fill="x", expand=True)

        btn_next = ctk.CTkButton(
            nav_bar, text="▶", width=32, height=26,
            font=self.font_body, fg_color=self.primary_color, hover_color="#8B634A",
            command=self._on_next_period
        )
        btn_next.pack(side="left", padx=(4, 4))

        btn_today = ctk.CTkButton(
            nav_bar, text="今日", width=48, height=26,
            font=self.font_small, fg_color="#8B634A", hover_color="#6E4F3B",
            command=self._on_jump_today
        )
        btn_today.pack(side="left", padx=(0, 2))

        # 描画キャンバス（月間グリッド / 週間・日間タイムテーブルを描画する）
        self.events_canvas = tk.Canvas(
            self.tab_events, bg="#FDF9EE", highlightthickness=0, yscrollincrement=20
        )
        self.events_canvas.pack(fill="both", expand=True, padx=5, pady=(2, 5))
        self.events_canvas.bind("<Button-1>", self._on_canvas_click)
        self.events_canvas.bind("<MouseWheel>", self._on_canvas_wheel)
        self.events_canvas.bind("<Button-4>", self._on_canvas_wheel)
        self.events_canvas.bind("<Button-5>", self._on_canvas_wheel)

        # 同期状態フッター（最終同期時刻 ＆ 登録件数）
        self.sync_info_label = ctk.CTkLabel(self.tab_events, text="", font=self.font_small, text_color="#8D6E63")
        self.sync_info_label.pack(fill="x", padx=8, pady=(0, 4))

        # ソース凡例（購読カレンダーの色見本 ＋ 名前）
        self.source_legend_frame = ctk.CTkFrame(self.tab_events, fg_color="transparent", height=18)
        self.source_legend_frame.pack(fill="x", padx=4, pady=(0, 2))

        # 表示状態（アンカー日と表示モード）
        self.view_mode = "month"
        self.current_date = datetime.date.today()

    def _on_event_view_change(self, value: str):
        """セグメントボタン切替 → 描画モードを更新して再描画"""
        if "日間" in value:
            self.view_mode = "day"
        elif "週間" in value:
            self.view_mode = "week"
        else:
            self.view_mode = "month"
        self.render_events()

    def _on_prev_period(self):
        """前の期間へ移動（月/週/日）"""
        self._shift_period(-1)

    def _on_next_period(self):
        """次の期間へ移動（月/週/日）"""
        self._shift_period(1)

    def _shift_period(self, sign: int):
        """表示モードに応じてアンカー日を前後にずらす

        Args:
            sign (int): -1 で過去方向、+1 で未来方向。
        """
        if self.view_mode == "month":
            total = (self.current_date.year * 12 + (self.current_date.month - 1)) + sign
            new_year, new_month_zero = divmod(total, 12)
            self.current_date = datetime.date(new_year, new_month_zero + 1, 1)
        elif self.view_mode == "week":
            self.current_date = self.current_date + datetime.timedelta(days=7 * sign)
        else:
            self.current_date = self.current_date + datetime.timedelta(days=sign)
        self.render_events()

    def _on_jump_today(self):
        """今日（当月）へ戻る"""
        self.current_date = datetime.date.today()
        self.render_events()

    def load_events(self, events: List[database.Event]):
        """予定データを受け取り、現在の表示モードで再描画する

        Args:
            events (List[database.Event]): 予定モデルのリスト。
        """
        self.all_cached_events = events or []
        self.render_events()
        self._update_sync_info()

    def _update_sync_info(self):
        """フッターにソース別の最終同期時刻と登録件数を表示し、色凡例を描画する"""
        sources = getattr(self, 'calendar_sources', []) or []
        configured = [s for s in sources if s.url.strip()]
        if configured:
            sync_parts = [f"{s.name}: {s.last_sync}" for s in configured]
            sync_text = "🔄 最終同期 ／ " + " ／ ".join(sync_parts) + f" ／ 手帳登録 {len(self.all_cached_events)} 件"
        else:
            sync_text = "🔄 iCal未設定（設定 → 外部ツール からカレンダーを購読できます）"
        self.sync_info_label.configure(text=sync_text)

        # ソース凡例（色見本 ＋ 名前 ＆ ON/OFF状態）
        for widget in self.source_legend_frame.winfo_children():
            widget.destroy()
        for s in configured:
            swatch = tk.Frame(
                self.source_legend_frame, bg=s.color, width=10, height=10,
                highlightthickness=1, highlightbackground="#B0A496"
            )
            swatch.pack(side="left", padx=(10, 3), pady=2)
            state_mark = "" if s.enabled else "（OFF）"
            ctk.CTkLabel(self.source_legend_frame, text=f"{s.name}{state_mark}", font=self.font_small, text_color="#6E5F53").pack(side="left")

    # =========================================================================
    # 📅 予定描画エンジン（月間グリッド / 週間・日間タイムテーブル）
    # =========================================================================
    EVENT_PALETTE = ["#FFCDD2", "#C8E6C9", "#BBDEFB", "#FFE0B2", "#D1C4E9", "#B2EBF2", "#FFF9C4"]

    def _event_color(self, event) -> str:
        """予定タイトルから安定したパステルカラーを割り当てる"""
        title_hash = sum(ord(ch) for ch in (event.title or ""))
        return self.EVENT_PALETTE[title_hash % len(self.EVENT_PALETTE)]

    def _source_color(self, event):
        """イベントの購読ソース識別色を返す（ローカル予定は None）"""
        src_id = getattr(event, 'source_id', None)
        if src_id is None:
            return None
        for s in getattr(self, 'calendar_sources', []) or []:
            if s.id == src_id:
                return s.color
        return None

    def _events_by_date(self) -> Dict[datetime.date, List[Tuple[database.Event, datetime.datetime, datetime.datetime]]]:
        """キャッシュ済み予定を日付ごとにグルーピングする

        Returns:
            dict: { datetime.date: [(Event, 開始datetime, 終了datetime), ...] }（各日とも開始時刻昇順）
        """
        by_date: Dict[datetime.date, List[Tuple[database.Event, datetime.datetime, datetime.datetime]]] = {}
        for e in getattr(self, 'all_cached_events', []) or []:
            try:
                sdt = datetime.datetime.fromtimestamp(e.start_time / 1000)
                edt = datetime.datetime.fromtimestamp(e.end_time / 1000)
            except (ValueError, OSError, TypeError) as exc:
                logger.warning(f"予定のタイムスタンプ不正のためスキップ (id={getattr(e, 'id', '?')}): {exc}")
                continue
            by_date.setdefault(sdt.date(), []).append((e, sdt, edt))
        for daily in by_date.values():
            daily.sort(key=lambda item: item[1])
        return by_date

    def render_events(self):
        """表示モードに応じた描画関数へディスパッチする"""
        if self.view_mode == "month":
            self._render_month_view()
        elif self.view_mode == "week":
            self._render_week_view()
        else:
            self._render_day_view()

    def _render_month_view(self):
        """月間カレンダーグリッドを描画する（各日に予定概要を最大3件表示）"""
        canvas = self.events_canvas
        canvas.delete("all")
        canvas.configure(scrollregion="")
        canvas.yview_moveto(0)

        year, month = self.current_date.year, self.current_date.month
        self.period_label.configure(text=f"🗓️ {year}年 {month}月")

        canvas.update_idletasks()
        width = max(canvas.winfo_width(), 470)
        height = max(canvas.winfo_height(), 430)

        header_h = 26
        cell_w = width / 7.0
        cell_h = (height - header_h) / 6.0

        weekdays = ["日", "月", "火", "水", "木", "金", "土"]
        weekday_colors = ["#FF8A80", "#4A3B32", "#4A3B32", "#4A3B32", "#4A3B32", "#4A3B32", "#82B1FF"]
        for i, (name, color) in enumerate(zip(weekdays, weekday_colors)):
            x0 = i * cell_w
            canvas.create_rectangle(x0, 0, x0 + cell_w, header_h, fill=self.primary_color, outline="#8B634A")
            canvas.create_text(x0 + cell_w / 2, header_h / 2, text=name, fill="#FFFFFF", font=("Meiryo UI", 9, "bold"))

        first_day = datetime.date(year, month, 1)
        grid_start = first_day - datetime.timedelta(days=(first_day.weekday() + 1) % 7)
        today = datetime.date.today()
        now = datetime.datetime.now()
        by_date = self._events_by_date()

        for idx in range(42):
            row, col = divmod(idx, 7)
            x0, y0 = col * cell_w, header_h + row * cell_h
            x1, y1 = x0 + cell_w, y0 + cell_h
            d = grid_start + datetime.timedelta(days=idx)
            in_month = (d.month == month)
            is_today = (d == today)
            fill = "#FFE082" if is_today else ("#FFFFFF" if in_month else "#EFE8D6")
            tag = f"day:{d.isoformat()}"
            canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline="#D5CBB8", tags=(tag,))

            num_color = "#D32F2F" if col == 0 else ("#1976D2" if col == 6 else self.text_color)
            if not in_month:
                num_color = "#B0A496"
            canvas.create_text(x0 + 4, y0 + 3, text=str(d.day), anchor="nw", fill=num_color, font=("Meiryo UI", 8, "bold"), tags=(tag,))

            day_events = by_date.get(d, [])
            max_show = 3
            for j, (ev, sdt, _edt) in enumerate(day_events[:max_show]):
                ty = y0 + 19 + j * 13
                if ty + 13 > y1 - 2:
                    break
                is_past = sdt < now
                title = ev.title if len(ev.title) <= 10 else ev.title[:9] + "…"
                block_fill = "#E5DED2" if is_past else self._event_color(ev)
                canvas.create_rectangle(x0 + 3, ty, x1 - 3, ty + 12, fill=block_fill, outline="", tags=(tag,))
                src_col = self._source_color(ev)
                text_x = x0 + 5
                if src_col:
                    canvas.create_rectangle(x0 + 3, ty, x0 + 6, ty + 12, fill=src_col, outline="", tags=(tag,))
                    text_x = x0 + 8
                canvas.create_text(text_x, ty + 1, text=title, anchor="nw", fill="#6E5F53" if is_past else "#3E2F23", font=("Meiryo UI", 7), tags=(tag,))
            if len(day_events) > max_show:
                canvas.create_text(x1 - 4, y1 - 3, text=f"+{len(day_events) - max_show}", anchor="se", fill="#8B634A", font=("Meiryo UI", 7, "bold"), tags=(tag,))

    def _render_week_view(self):
        """週間タイムテーブル（7日 × 時間軸ガントチャート）を描画する"""
        canvas = self.events_canvas
        canvas.delete("all")
        canvas.configure(scrollregion="")
        canvas.yview_moveto(0)

        week_start = self.current_date - datetime.timedelta(days=(self.current_date.weekday() + 1) % 7)
        week_end = week_start + datetime.timedelta(days=6)
        self.period_label.configure(text=f"📅 {week_start.month}/{week_start.day} 〜 {week_end.month}/{week_end.day}")

        canvas.update_idletasks()
        width = max(canvas.winfo_width(), 470)
        height = max(canvas.winfo_height(), 430)

        gutter_w, header_h = 38, 26
        start_hour, end_hour = 6, 24
        hour_h = (height - header_h) / float(end_hour - start_hour)
        col_w = (width - gutter_w) / 7.0
        today = datetime.date.today()
        now = datetime.datetime.now()
        by_date = self._events_by_date()
        weekday_names = "日月火水木金土"

        # 曜日ヘッダー（タップでその日の日間ビューへ）
        for i in range(7):
            d = week_start + datetime.timedelta(days=i)
            x0 = gutter_w + i * col_w
            is_today = (d == today)
            tag = f"day:{d.isoformat()}"
            canvas.create_rectangle(x0, 0, x0 + col_w, header_h, fill="#FFE082" if is_today else self.primary_color, outline="#8B634A", tags=(tag,))
            canvas.create_text(x0 + col_w / 2, header_h / 2, text=f"{weekday_names[i]} {d.month}/{d.day}", fill="#4A3B32" if is_today else "#FFFFFF", font=("Meiryo UI", 8, "bold"), tags=(tag,))

        # 時間軸
        for h in range(start_hour, end_hour + 1):
            y = header_h + (h - start_hour) * hour_h
            canvas.create_line(gutter_w, y, width, y, fill="#E8E0CE")
            if h < end_hour:
                canvas.create_text(gutter_w - 3, y + 1, text=f"{h}", anchor="ne", fill="#8B634A", font=("Meiryo UI", 7))

        # 予定ブロック（タップで日間ビューへ）
        for i in range(7):
            d = week_start + datetime.timedelta(days=i)
            for ev, sdt, edt in by_date.get(d, []):
                start_frac = max((sdt.hour + sdt.minute / 60.0) - start_hour, 0.0)
                end_frac = min((edt.hour + edt.minute / 60.0) - start_hour, float(end_hour - start_hour))
                if end_frac <= 0:
                    continue
                y0 = header_h + start_frac * hour_h
                y1 = max(header_h + end_frac * hour_h, y0 + 14)
                x0 = gutter_w + i * col_w + 2
                x1 = x0 + col_w - 4
                is_past = sdt < now
                tag = f"event:{ev.id}:{d.isoformat()}"
                canvas.create_rectangle(x0, y0, x1, y1, fill="#E5DED2" if is_past else self._event_color(ev), outline="#B0A496" if is_past else "#A67B5B", tags=(tag,))
                src_col = self._source_color(ev)
                if src_col:
                    canvas.create_rectangle(x0, y0, x0 + 3, y1, fill=src_col, outline="", tags=(tag,))
                title = ev.title if len(ev.title) <= 8 else ev.title[:7] + "…"
                canvas.create_text(x0 + 2, y0 + 1, text=title, anchor="nw", fill="#6E5F53" if is_past else "#3E2F23", font=("Meiryo UI", 7), tags=(tag,))

        # 現在時刻線
        if week_start <= today <= week_end:
            y_now = header_h + ((now.hour + now.minute / 60.0) - start_hour) * hour_h
            canvas.create_line(gutter_w, y_now, width, y_now, fill="#FF1744", width=2)

    def _render_day_view(self):
        """日間タイムテーブル（0〜24時の詳細ビュー・スクロール可）を描画する"""
        canvas = self.events_canvas
        canvas.delete("all")

        d = self.current_date
        weekday_ja = "月火水木金土日"[d.weekday()]
        self.period_label.configure(text=f"☀️ {d.month}月{d.day}日 ({weekday_ja})")

        canvas.update_idletasks()
        width = max(canvas.winfo_width(), 470)
        gutter_w = 46
        header_h = 26
        hour_h = 44
        total_h = header_h + 24 * hour_h + 20
        canvas.configure(scrollregion=(0, 0, width, total_h))

        now = datetime.datetime.now()
        by_date = self._events_by_date()
        day_events = by_date.get(d, [])

        canvas.create_rectangle(0, 0, width, header_h, fill=self.primary_color, outline="#8B634A")
        canvas.create_text(width / 2, header_h / 2, text=d.strftime("%Y / %m / %d"), fill="#FFFFFF", font=("Meiryo UI", 9, "bold"))

        # 時間軸
        for h in range(24):
            y = header_h + h * hour_h
            canvas.create_line(gutter_w, y, width, y, fill="#E8E0CE")
            canvas.create_text(gutter_w - 5, y + 2, text=f"{h}:00", anchor="ne", fill="#8B634A", font=("Meiryo UI", 8))

        # 予定ブロック（時刻・タイトル・説明を詳細表示）
        for ev, sdt, edt in day_events:
            start_frac = sdt.hour + sdt.minute / 60.0
            end_frac = max(edt.hour + edt.minute / 60.0, start_frac + 0.5)
            y0 = header_h + start_frac * hour_h
            y1 = max(header_h + end_frac * hour_h, y0 + 40)
            x0, x1 = gutter_w + 4, width - 6
            is_past = sdt < now
            tag = f"event:{ev.id}:{d.isoformat()}"
            canvas.create_rectangle(x0, y0, x1, y1, fill="#E5DED2" if is_past else self._event_color(ev), outline="#B0A496" if is_past else "#A67B5B", tags=(tag,))
            src_col = self._source_color(ev)
            if src_col:
                canvas.create_rectangle(x0, y0, x0 + 4, y1, fill=src_col, outline="", tags=(tag,))
            canvas.create_text(x0 + 6, y0 + 3, text=f"{sdt.strftime('%H:%M')} 〜 {edt.strftime('%H:%M')}", anchor="nw", fill="#8B634A", font=("Meiryo UI", 7), tags=(tag,))
            title = ev.title if len(ev.title) <= 30 else ev.title[:29] + "…"
            canvas.create_text(x0 + 6, y0 + 15, text=title, anchor="nw", fill="#6E5F53" if is_past else "#3E2F23", font=("Meiryo UI", 9, "bold"), tags=(tag,))
            desc_text = (getattr(ev, 'description', '') or '').strip()
            if desc_text and (y1 - y0) > 52:
                desc_line = desc_text.splitlines()[0]
                if len(desc_line) > 42:
                    desc_line = desc_line[:41] + "…"
                canvas.create_text(x0 + 6, y0 + 30, text=desc_line, anchor="nw", fill="#7A6B62", font=("Meiryo UI", 7), tags=(tag,))

        # 現在時刻線（今日のみ）
        if d == datetime.date.today():
            y_now = header_h + (now.hour + now.minute / 60.0) * hour_h
            canvas.create_line(gutter_w, y_now, width, y_now, fill="#FF1744", width=2)
            canvas.create_text(width - 6, y_now - 7, text=now.strftime("%H:%M"), anchor="e", fill="#FF1744", font=("Meiryo UI", 8, "bold"))

        # 自動スクロール（今日は現在時刻付近、過去日は最初の予定付近へ）
        if day_events:
            anchor_hour = (now.hour if d == datetime.date.today() else day_events[0][1].hour) - 1.5
        else:
            anchor_hour = (now.hour if d == datetime.date.today() else 8) - 1.5
        canvas.yview_moveto(max(anchor_hour, 0.0) * hour_h / float(total_h))

    def _on_canvas_click(self, event):
        """キャンバスクリック → 日付セル/予定ブロックのタグを解決し遷移・詳細表示する"""
        canvas = self.events_canvas
        clicked = canvas.find_withtag("current")
        if not clicked:
            return
        tags = canvas.gettags(clicked[0])
        target_date = None
        event_id = None
        for t in tags:
            if t.startswith("day:"):
                target_date = t.split(":", 1)[1]
                break
            if t.startswith("event:"):
                parts = t.split(":")
                if len(parts) >= 3:
                    event_id = parts[1]
                    target_date = parts[2]
                break
        if not target_date:
            return
        try:
            self.current_date = datetime.date.fromisoformat(target_date)
        except ValueError:
            return
        # 日間ビューでの予定ブロッククリックは詳細ポップアップを表示
        if self.view_mode == "day" and event_id is not None:
            self._show_event_detail(int(event_id))
            return
        self.view_mode = "day"
        self.event_view_seg.set("☀️ 日間")
        self.render_events()

    def _show_event_detail(self, event_id: int):
        """日間ビューの予定ブロック詳細ポップアップ（全文タイトル・時刻・説明）を表示する"""
        target = next((e for e in getattr(self, 'all_cached_events', []) or [] if e.id == event_id), None)
        if target is None:
            return

        popup = ctk.CTkToplevel(self)
        popup.title("予定の詳細")
        popup.geometry("430x320")
        popup.configure(fg_color=self.bg_color)
        popup.transient(self)
        popup.grab_set()

        sdt = datetime.datetime.fromtimestamp(target.start_time / 1000)
        edt = datetime.datetime.fromtimestamp(target.end_time / 1000)

        header = ctk.CTkFrame(popup, fg_color=self.primary_color, corner_radius=0, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="📌 予定の詳細", font=self.font_title, text_color="#FFFFFF").pack(pady=8)

        body = ctk.CTkFrame(popup, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14, pady=10)

        ctk.CTkLabel(body, text=target.title, font=self.font_title, text_color=self.text_color, wraplength=390, justify="left").pack(anchor="w")
        ctk.CTkLabel(body, text=f"🕐 {sdt.strftime('%Y年%m月%d日 (%a) %H:%M')} 〜 {edt.strftime('%H:%M')}", font=self.font_body, text_color="#8B634A").pack(anchor="w", pady=(6, 10))
        desc_text = (getattr(target, 'description', '') or '').strip()
        ctk.CTkLabel(
            body,
            text=desc_text if desc_text else "（説明文はありません）",
            font=self.font_body,
            text_color="#7A6B62" if desc_text else "#B0A496",
            wraplength=390,
            justify="left"
        ).pack(anchor="w", fill="x", expand=True)

        ctk.CTkButton(
            popup, text="閉じる", width=90, height=30,
            font=self.font_body, fg_color=self.primary_color, hover_color="#8B634A",
            command=popup.destroy
        ).pack(pady=(0, 10))

    def _on_canvas_wheel(self, event):
        """マウスホイールスクロール（日間ビューのみ・縦長スクロール領域があるため）"""
        if self.view_mode != "day":
            return
        delta = getattr(event, "delta", 0)
        if delta > 0 or getattr(event, "num", 0) == 4:
            self.events_canvas.yview_scroll(-2, "units")
        elif delta < 0 or getattr(event, "num", 0) == 5:
            self.events_canvas.yview_scroll(2, "units")

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
            placeholder_text="新しいタスクを入力してEnter...（例: 明日18時に資料 #仕事 !3 ※重要）",
            font=self.font_body,
            fg_color="#FFFFFF",
            border_color="#A67B5B",
            height=32
        )
        self.task_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.task_entry.bind("<Return>", self._on_add_quick_task)

        # 重要度・緊急度セレクト (4象限属性・roadmap 1.14): 構文入力が苦手でも
        # プルダウンで明示指定できる併用UI。値は「未指定」で推定ルールに委ねる
        self.importance_var = tk.StringVar(value="未指定")
        ctk.CTkOptionMenu(
            add_bar,
            values=["未指定", "重要", "非重要"],
            variable=self.importance_var,
            width=78,
            height=32,
            font=self.font_body,
            fg_color="#A67B5B",
            button_color="#8B634A"
        ).pack(side="left", padx=(0, 4))
        self.urgency_var = tk.StringVar(value="未指定")
        ctk.CTkOptionMenu(
            add_bar,
            values=["未指定", "緊急", "非緊急"],
            variable=self.urgency_var,
            width=78,
            height=32,
            font=self.font_body,
            fg_color="#A67B5B",
            button_color="#8B634A"
        ).pack(side="left", padx=(0, 6))

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

        # 📂 リスト階層サイドバー (TickTick風・Block 1.6-R):
        # 左にリストツリー (折りたたみ可能な階層構造)、右にタスク一覧の2分割レイアウト。
        # 描画は refresh_tasks → _refresh_list_sidebar 経由。
        self.task_filter_list_id: "int | str | None" = None  # None=すべて / "UNSORTED"=未分類 / int=リストID
        self._list_expanded: "dict[int, bool]" = {}  # リストID -> 展開状態 (未登録キーは展開扱い)

        self.task_body = ctk.CTkFrame(self.tab_tasks, fg_color="transparent")
        self.task_body.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        # 左: リスト階層ツリーサイドバー
        self.lists_sidebar = ctk.CTkScrollableFrame(
            self.task_body,
            width=188,
            fg_color="#F5F1E8",
            border_color="#E0D8C8",
            border_width=1,
            corner_radius=8
        )
        self.lists_sidebar.pack(side="left", fill="y", padx=(0, 6))

        # 右: ヘッダ (選択中リスト名) ＋ タスク一覧
        self.task_main = ctk.CTkFrame(self.task_body, fg_color="transparent")
        self.task_main.pack(side="left", fill="both", expand=True)

        self.task_header_var = tk.StringVar(value="📥 すべて")
        ctk.CTkLabel(
            self.task_main,
            textvariable=self.task_header_var,
            font=self.font_title,
            text_color=self.text_color,
            anchor="w"
        ).pack(fill="x", padx=2, pady=(0, 4))

        self.tasks_scroll = ctk.CTkScrollableFrame(self.task_main, fg_color="transparent")
        self.tasks_scroll.pack(fill="both", expand=True)

    def _refresh_list_bar(self, counts: "dict[int, int] | None" = None):
        """後方互換エイリアス: 旧チップバー描画 → 新サイドバーツリー描画へ委譲する。"""
        self._refresh_list_sidebar(counts)

    def _refresh_list_sidebar(self, counts: "dict[int, int] | None" = None):
        """リスト階層ツリーサイドバーを再描画する (TickTick風・Block 1.6-R)。

        「📥 すべて」「🗂 未分類」のスマート行 ＋ parent_id で接続された
        リストツリー (▶/▼ 折りたたみ・未完了件数バッジ・行ごとの子リスト追加) を描画する。

        Args:
            counts: リストIDごとの未完了タスク数 (None時はDBから再集計)
        """
        if not hasattr(self, "lists_sidebar"):
            return
        for w in self.lists_sidebar.winfo_children():
            w.destroy()
        lists = database.get_task_lists()
        if counts is None:
            counts = self._compute_list_task_counts()

        children_map: "dict[int | None, list]" = {}
        for lst in lists:
            children_map.setdefault(lst.parent_id, []).append(lst)
        for v in children_map.values():
            v.sort(key=lambda l: (l.sort_order, l.id))

        def descendant_count(lst) -> int:
            """対象リストとその全子孫リストの未完了タスク数を合計する (再帰)。"""
            total = counts.get(lst.id, 0)
            for child in children_map.get(lst.id, []):
                total += descendant_count(child)
            return total

        def smart_row(text: str, active: bool, cb):
            """スマートリスト行 (すべて/未分類) を描画してpackする。"""
            ctk.CTkButton(
                self.lists_sidebar,
                text=text,
                height=26,
                anchor="w",
                font=self.font_small,
                fg_color="#8B634A" if active else "transparent",
                text_color="#FFFFFF" if active else "#5D4037",
                hover_color="#A67B5B" if active else "#E8E0D0",
                command=cb
            ).pack(fill="x", padx=4, pady=1)

        smart_row("📥 すべて", self.task_filter_list_id is None, lambda: self._on_select_task_list(None))
        smart_row("🗂 未分類", self.task_filter_list_id == "UNSORTED", lambda: self._on_select_task_list("UNSORTED"))

        # セクションヘッダ (TickTick風: 「リスト」ラベル＋ルート作成ボタン)
        section = ctk.CTkFrame(self.lists_sidebar, fg_color="transparent")
        section.pack(fill="x", padx=4, pady=(8, 1))
        ctk.CTkLabel(
            section, text="リスト", font=self.font_small, text_color="#A67B5B", anchor="w"
        ).pack(side="left")
        ctk.CTkButton(
            section, text="＋", width=20, height=20, font=self.font_small,
            fg_color="transparent", text_color="#8B634A", hover_color="#E0D8C8",
            command=lambda: self._prompt_create_list(parent_id=None)
        ).pack(side="right")

        def render_children(parent_id: "int | None", depth: int):
            """指定親の子リスト行を順に描画し、展開中なら子階層を再帰描画する。"""
            for lst in children_map.get(parent_id, []):
                self._render_list_tree_row(
                    lst, depth, bool(children_map.get(lst.id)), descendant_count(lst)
                )
                if children_map.get(lst.id) and self._list_expanded.get(lst.id, True):
                    render_children(lst.id, depth + 1)

        render_children(None, 0)

        # フッター: 管理ボタン
        ctk.CTkButton(
            self.lists_sidebar,
            text="⚙ リスト管理",
            height=26,
            anchor="w",
            font=self.font_small,
            fg_color="transparent",
            text_color="#8B634A",
            hover_color="#E8E0D0",
            command=self._open_list_manager
        ).pack(fill="x", padx=4, pady=(8, 2))

    def _compute_list_task_counts(self) -> "dict[int, int]":
        """リストIDごとの未完了 (親) タスク数を集計する。

        Returns:
            {リストID: 未完了タスク数} の辞書
        """
        all_tasks = database.get_tasks(status="todo", limit=100)
        counts: "dict[int, int]" = {}
        for t in all_tasks:
            if t.parent_id is None and t.list_id is not None:
                counts[t.list_id] = counts.get(t.list_id, 0) + 1
        return counts

    def _render_list_tree_row(self, lst, depth: int, has_children: bool, total_count: int):
        """サイドバーにリスト1行 (トグル/選択/件数/子追加) を描画する。

        Args:
            lst: TaskListモデル
            depth: 階層の深さ (0=ルート・インデントに使用)
            has_children: 子リストを持つか (折りたたみトグル表示の判定)
            total_count: 子孫合計の未完了タスク数
        """
        active = self.task_filter_list_id == lst.id
        indent = "　" * depth
        row = ctk.CTkFrame(self.lists_sidebar, fg_color="transparent")
        row.pack(fill="x", padx=2, pady=0)

        # 折りたたみトグル (子リストが無い場合はスペーサーで桁を揃える)
        if has_children:
            is_open = self._list_expanded.get(lst.id, True)
            ctk.CTkButton(
                row, text="▼" if is_open else "▶", width=18, height=22,
                font=self.font_small, fg_color="transparent",
                text_color="#A67B5B", hover_color="#E0D8C8",
                command=lambda lid=lst.id: self._toggle_list_expanded(lid)
            ).pack(side="left")
        else:
            ctk.CTkLabel(row, text="　", font=self.font_small, width=18).pack(side="left")

        # 未完了件数バッジ (0件は非表示でノイズ削減)
        if total_count > 0:
            ctk.CTkLabel(
                row, text=str(total_count), font=self.font_small,
                text_color="#A67B5B", width=22
            ).pack(side="right", padx=(0, 2))

        # 子リスト追加ボタン (行の右端・階層作成の入口)
        ctk.CTkButton(
            row, text="＋", width=18, height=22, font=self.font_small,
            fg_color="transparent", text_color="#B0A496", hover_color="#E0D8C8",
            command=lambda lid=lst.id, lname=lst.name: self._prompt_create_list(parent_id=lid, parent_name=lname)
        ).pack(side="right")

        display_name = lst.name if len(lst.name) <= 10 else lst.name[:9] + "…"
        ctk.CTkButton(
            row,
            text=f"{indent}{lst.emoji} {display_name}",
            height=24,
            anchor="w",
            font=self.font_small,
            fg_color="#8B634A" if active else "transparent",
            text_color="#FFFFFF" if active else "#5D4037",
            hover_color="#A67B5B" if active else "#E8E0D0",
            command=lambda lid=lst.id: self._on_select_task_list(lid)
        ).pack(side="left", fill="x", expand=True)

    def _toggle_list_expanded(self, list_id: int):
        """リスト行の展開/折りたたみ状態を切り替えてサイドバーを再描画する。"""
        self._list_expanded[list_id] = not self._list_expanded.get(list_id, True)
        self._refresh_list_sidebar()

    def _collect_list_subtree_ids(self, root_id: int) -> "set[int]":
        """対象リストとその全子孫リストのID集合を取得する (BFS)。

        Args:
            root_id: 起点となるリストID

        Returns:
            {root_id, 子, 孫, ...} のID集合
        """
        lists = database.get_task_lists()
        children_map: "dict[int | None, list]" = {}
        for lst in lists:
            children_map.setdefault(lst.parent_id, []).append(lst)
        result = {root_id}
        queue = [root_id]
        while queue:
            current = queue.pop()
            for child in children_map.get(current, []):
                if child.id not in result:
                    result.add(child.id)
                    queue.append(child.id)
        return result

    def _filter_header_base(self) -> str:
        """現在の絞り込み状態に対応するヘッダ表示名を返す。

        Returns:
            「📥 すべて」/「🗂 未分類」/「{絵文字} {リスト名}」のいずれか
        """
        flt = getattr(self, "task_filter_list_id", None)
        if flt is None:
            return "📥 すべて"
        if flt == "UNSORTED":
            return "🗂 未分類"
        for lst in database.get_task_lists():
            if lst.id == flt:
                return f"{lst.emoji} {lst.name}"
        return "📥 すべて"

    def _on_select_task_list(self, list_id: "int | str | None"):
        """リストチップ押下: 絞り込み対象を切り替えてタスク一覧を再描画する。"""
        self.task_filter_list_id = list_id
        self.refresh_tasks()

    def _prompt_create_list(self, parent_id: "int | None" = None, parent_name: "str | None" = None):
        """新しいタスクリストを作成するダイアログ (先頭トークンを絵文字として解釈)。

        Args:
            parent_id: 親リストID (None=最上位・指定時はそのリストの子として作成)
            parent_name: ダイアログ表示用の親リスト名
        """
        scope = f"\n作成先: {parent_name} の下" if parent_name else ""
        dialog = ctk.CTkInputDialog(
            text=f"新しいリスト名を入力（先頭に絵文字可）{scope}\n例: 🏠 プライベート",
            title="リスト新規作成"
        )
        raw = dialog.get_input()
        if not raw or not raw.strip():
            return
        text = raw.strip()
        parts = text.split(None, 1)
        emoji, name = "📋", text
        # 「🏠 プライベート」のように先頭が区切り付き記号トークンなら絵文字と解釈する
        if len(parts) == 2 and not parts[0].isalnum():
            emoji, name = parts[0], parts[1].strip()
        if not name:
            logger.warning("リスト作成: 名前が空のため中止しました (入力=%r)", raw)
            return
        try:
            database.create_task_list(name, emoji=emoji, parent_id=parent_id)
        except ValueError as exc:
            logger.warning("リスト作成に失敗しました: %s", exc)
            return
        # 作成した親を展開して新リストを見える化
        if parent_id is not None:
            self._list_expanded[parent_id] = True
        self.refresh_tasks()

    def _open_list_manager(self):
        """リスト管理ダイアログ (名称変更・削除) を開く (roadmap 1.6)。"""
        import tkinter.messagebox as mb  # noqa: F401  (削除確認は _delete_list_in_manager で使用)

        win = ctk.CTkToplevel(self)
        win.title("リスト管理")
        win.geometry("400x360")
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(
            win, text="📂 リスト管理",
            font=self.font_body, text_color=self.text_color
        ).pack(pady=(10, 4))

        body = ctk.CTkScrollableFrame(win, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=10, pady=4)

        lists = database.get_task_lists()
        if not lists:
            ctk.CTkLabel(
                body, text="リストがありません。\n「＋ リスト」から作成できます。",
                font=self.font_small, text_color="#757575"
            ).pack(pady=20)

        for lst in lists:
            row = ctk.CTkFrame(body, fg_color="#FFFFFF", corner_radius=6)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(
                row, text=f"{lst.emoji} {lst.name}",
                font=self.font_body, text_color=self.text_color, anchor="w"
            ).pack(side="left", fill="x", expand=True, padx=(8, 4), pady=6)

            def make_rename_cb(list_id=lst.id, list_name=lst.name):
                return lambda: self._rename_list_in_manager(win, list_id, list_name)

            def make_move_cb(list_id=lst.id, list_name=lst.name):
                return lambda: self._move_list_in_manager(win, list_id, list_name)

            def make_delete_cb(list_id=lst.id, list_name=lst.name):
                return lambda: self._delete_list_in_manager(win, list_id, list_name)

            ctk.CTkButton(
                row, text="✏", width=34, height=26, font=self.font_small,
                fg_color="#F5F5DC", text_color="#8B634A", hover_color="#E0D8C8",
                command=make_rename_cb(lst.id, lst.name)
            ).pack(side="right", padx=(2, 4), pady=4)
            ctk.CTkButton(
                row, text="⇄", width=34, height=26, font=self.font_small,
                fg_color="#F5F5DC", text_color="#8B634A", hover_color="#E0D8C8",
                command=make_move_cb(lst.id, lst.name)
            ).pack(side="right", padx=(2, 0), pady=4)
            ctk.CTkButton(
                row, text="🗑", width=34, height=26, font=self.font_small,
                fg_color="#F5F5DC", text_color="#D32F2F", hover_color="#FFCDD2",
                command=make_delete_cb(lst.id, lst.name)
            ).pack(side="right", padx=(2, 0), pady=4)

        ctk.CTkButton(
            win, text="閉じる", height=30, font=self.font_body,
            fg_color=self.primary_color, hover_color="#8B634A",
            command=win.destroy
        ).pack(pady=(4, 10))

    def _rename_list_in_manager(self, manager_win, list_id: int, current_name: str):
        """管理ダイアログ内の名称変更ボタン: 新名を入力させて rename_task_list を呼ぶ。"""
        dialog = ctk.CTkInputDialog(text="新しいリスト名を入力:", title="リスト名変更")
        new_name = dialog.get_input()
        if not new_name or not new_name.strip():
            return
        try:
            database.rename_task_list(list_id, new_name.strip())
        except ValueError as exc:
            logger.warning("リスト名変更に失敗しました: %s", exc)
            return
        manager_win.destroy()
        self.refresh_tasks()

    def _delete_list_in_manager(self, manager_win, list_id: int, list_name: str):
        """管理ダイアログ内の削除ボタン: 確認後 delete_task_list を呼ぶ (所属タスクは未分類へ)。"""
        import tkinter.messagebox as mb
        if not mb.askyesno("リスト削除", f"リスト「{list_name}」を削除しますか？\n所属タスクは「未分類」に移動されます。"):
            return
        database.delete_task_list(list_id)
        # 削除対象を絞り込んでいた場合は「すべて」へ戻す
        if self.task_filter_list_id == list_id:
            self.task_filter_list_id = None
        manager_win.destroy()
        self.refresh_tasks()

    def _move_list_in_manager(self, manager_win, list_id: int, list_name: str):
        """管理ダイアログ内の移動ボタン: 新しい親リストを選択して move_task_list を呼ぶ (Block 1.6-R)。

        Args:
            manager_win: 親のリスト管理ダイアログ
            list_id: 移動対象リストID
            list_name: 移動対象リスト名 (表示用)
        """
        lists = database.get_task_lists()
        # 移動先の候補: 最上位 ＋ 自分自身とその子孫を除いた全リスト (循環参照の構造的排除)
        subtree = self._collect_list_subtree_ids(list_id)
        candidates = [l for l in lists if l.id not in subtree]

        dialog = ctk.CTkToplevel(manager_win)
        dialog.title("リスト移動")
        dialog.geometry("300x440")
        dialog.transient(manager_win)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text=f"「{list_name[:15]}」の移動先",
            font=self.font_body, text_color=self.text_color
        ).pack(pady=(10, 6))

        ctk.CTkButton(
            dialog, text="⬆ 最上位へ移動", height=30, anchor="w", font=self.font_small,
            fg_color="#F5F5DC", text_color="#8B634A", hover_color="#E0D8C8",
            command=lambda: self._apply_list_move(dialog, manager_win, list_id, None)
        ).pack(fill="x", padx=14, pady=2)

        for lst in candidates:
            ctk.CTkButton(
                dialog, text=f"{lst.emoji} {lst.name} の下へ移動", height=30, anchor="w",
                font=self.font_small, fg_color="#F5F5DC", text_color="#5D4037",
                hover_color="#E0D8C8",
                command=lambda lid=lst.id: self._apply_list_move(dialog, manager_win, list_id, lid)
            ).pack(fill="x", padx=14, pady=2)

        ctk.CTkButton(
            dialog, text="キャンセル", height=28, font=self.font_small,
            fg_color="transparent", text_color="#8B634A", border_width=1,
            border_color="#A67B5B", hover_color="#E8E0D0",
            command=dialog.destroy
        ).pack(pady=(8, 10))

    def _apply_list_move(
        self,
        dialog,
        manager_win,
        list_id: int,
        new_parent_id: "int | None"
    ):
        """リスト移動の確定処理: move_task_list を呼び出し、ダイアログを閉じて再描画する。

        Args:
            dialog: 移動先選択ダイアログ
            manager_win: 親のリスト管理ダイアログ
            list_id: 移動対象リストID
            new_parent_id: 新しい親リストID (None=最上位)
        """
        try:
            success = database.move_task_list(list_id, new_parent_id)
        except ValueError as exc:
            logger.warning("リスト移動に失敗しました: %s", exc)
            return
        if not success:
            logger.warning("リスト移動: 対象リストが存在しません ID=%s", list_id)
            return
        # 移動先の親を展開して移動結果を見える化
        if new_parent_id is not None:
            self._list_expanded[new_parent_id] = True
        dialog.destroy()
        manager_win.destroy()
        self.refresh_tasks()

    def _on_add_quick_task(self, event=None):
        text = self.task_entry_var.get().strip()
        if not text:
            return
        self.task_entry_var.set("")

        import database
        from task_parser import parse_input, tags_to_db_string

        # クイック構文解析 (日時/タグ/優先度/※重要※緊急) ＋ プルダウン値をマージ
        # (プルダウンが「未指定」のときだけ構文側の値を尊重する)
        parsed = parse_input(text)
        importance: "bool | None" = parsed.importance
        urgency: "bool | None" = parsed.urgency
        if self.importance_var.get() != "未指定":
            importance = (self.importance_var.get() == "重要")
        if self.urgency_var.get() != "未指定":
            urgency = (self.urgency_var.get() == "緊急")

        # 📂 追加先リスト: リスト絞り込み中ならそのリストへ、それ以外は未分類 (roadmap 1.6)
        target_list_id = self.task_filter_list_id if isinstance(self.task_filter_list_id, int) else None
        task = database.Task(
            title=parsed.title or text,
            due_date=parsed.due_date,
            priority=parsed.priority,
            tags=tags_to_db_string(parsed.tags),
            importance_flag=importance,
            urgency_flag=urgency,
            list_id=target_list_id,
        )
        database.create_task(task)
        self.refresh_tasks()

    def refresh_tasks(self):
        """TODOタスク一覧（親タスク ＆ サブタスク/チェックリスト）を再描画"""
        for widget in self.tasks_scroll.winfo_children():
            widget.destroy()
            
        import database
        all_tasks = database.get_tasks(status="todo", limit=100)
        # 親タスクのみを抽出 (parent_id is None)
        parent_tasks = [t for t in all_tasks if t.parent_id is None]

        # 📂 リスト絞り込み (Block 1.6-R): 選択中リスト (+その子孫リスト) / 未分類のみ表示
        flt = getattr(self, "task_filter_list_id", None)
        if flt == "UNSORTED":
            parent_tasks = [t for t in parent_tasks if t.list_id is None]
        elif flt is not None:
            subtree_ids = self._collect_list_subtree_ids(int(flt))
            parent_tasks = [t for t in parent_tasks if t.list_id in subtree_ids]

        # 📊 リストごとの未完了件数を全リスト分集計してサイドバーへ反映
        counts: "dict[int, int]" = {}
        for t in all_tasks:
            if t.parent_id is None and t.list_id is not None:
                counts[t.list_id] = counts.get(t.list_id, 0) + 1
        self._refresh_list_sidebar(counts)

        # ヘッダ: 選択中リスト名 ＋ 表示件数
        header_base = self._filter_header_base()
        self.task_header_var.set(f"{header_base} — {len(parent_tasks)}件" if parent_tasks else header_base)
        
        if not parent_tasks:
            lbl = ctk.CTkLabel(self.tasks_scroll, text="すべてのタスクが完了しています！✨", font=self.font_body, text_color="#2E7D32")
            lbl.pack(pady=30)
            return
            
        pri_colors = {3: "#D32F2F", 2: "#F57C00", 1: "#388E3C", 0: "#757575"}
        pri_labels = {3: "🔥 高", 2: "中", 1: "低", 0: ""}
        
        for t in parent_tasks:
            # 親タスクカード
            card = ctk.CTkFrame(self.tasks_scroll, fg_color="#FFFFFF", border_color="#E0D8C8", border_width=1, corner_radius=6)
            card.pack(fill="x", pady=3, padx=2)
            
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=4)
            
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
            cb.pack(side="left", padx=(4, 4), pady=2)
            
            ctk.CTkLabel(row, text=t.title, font=self.font_body, text_color=self.text_color, anchor="w", wraplength=310).pack(side="left", fill="x", expand=True, padx=4)
            
            # サブタスク追加ボタン（＋）
            def make_add_sub_cb(parent_id=t.id, p_title=t.title):
                return lambda: self._prompt_add_subtask(parent_id, p_title)
                
            btn_add_sub = ctk.CTkButton(
                row,
                text="＋子タスク",
                width=62,
                height=22,
                font=self.font_small,
                fg_color="#F5F5DC",
                text_color="#8B634A",
                hover_color="#E0D8C8",
                command=make_add_sub_cb(t.id, t.title)
            )
            btn_add_sub.pack(side="right", padx=4)

            if t.priority > 0:
                pri_lbl = ctk.CTkLabel(
                    row,
                    text=pri_labels.get(t.priority, ""),
                    font=self.font_small,
                    text_color=pri_colors.get(t.priority, "#757575")
                )
                pri_lbl.pack(side="right", padx=(2, 4))

            # 属性・期日の視認性向上 (重要度/緊急度/繰り返し/期日を常時表示)
            # 期日切れは赤字で強調し、期日なしの場合は項目自体を省略する
            meta_bits: "list[str]" = []
            if t.importance_flag is True:
                meta_bits.append("🔥重要")
            if t.urgency_flag is True:
                meta_bits.append("⚡緊急")
            if t.recurrence:
                meta_bits.append("🔁 繰り返し")
            if t.due_date:
                due_dt = datetime.datetime.fromtimestamp(t.due_date / 1000)
                meta_bits.append(f"📅 {due_dt:%m/%d %H:%M}")
            if meta_bits:
                is_overdue = t.due_date is not None and t.due_date < int(datetime.datetime.now().timestamp() * 1000)
                meta_lbl = ctk.CTkLabel(
                    card,
                    text="　".join(meta_bits),
                    font=self.font_small,
                    text_color="#D32F2F" if is_overdue else "#8B634A",
                    anchor="w"
                )
                meta_lbl.pack(fill="x", padx=10, pady=(0, 3))
                
            # サブタスク一覧のインデント表示
            subtasks = database.get_subtasks(t.id)
            if subtasks:
                sub_frame = ctk.CTkFrame(card, fg_color="#FBF9F5", corner_radius=4)
                sub_frame.pack(fill="x", padx=20, pady=(0, 6))
                
                for st in subtasks:
                    sub_row = ctk.CTkFrame(sub_frame, fg_color="transparent")
                    sub_row.pack(fill="x", padx=6, pady=2)
                    
                    is_sub_done = st.status == "completed"
                    def make_sub_complete_cb(sub_id=st.id):
                        return lambda: self._on_complete_task(sub_id)
                        
                    sub_cb = ctk.CTkCheckBox(
                        sub_row,
                        text="",
                        width=18,
                        checkbox_width=16,
                        checkbox_height=16,
                        fg_color=self.primary_color,
                        command=make_sub_complete_cb(st.id)
                    )
                    if is_sub_done:
                        sub_cb.select()
                    sub_cb.pack(side="left", padx=(2, 4))
                    
                    st_text_color = "#9E9E9E" if is_sub_done else "#5D4037"
                    st_font = (self.font_small[0], self.font_small[1], "overstrike") if is_sub_done else self.font_small
                    ctk.CTkLabel(
                        sub_row, 
                        text=f"└ {st.title}", 
                        font=st_font, 
                        text_color=st_text_color, 
                        anchor="w"
                    ).pack(side="left", fill="x", expand=True)

    def _prompt_add_subtask(self, parent_id: int, parent_title: str):
        """サブタスク追加ダイアログ"""
        dialog = ctk.CTkInputDialog(text=f"『{parent_title[:15]}…』に追加する子タスク名:", title="サブタスク追加")
        sub_title = dialog.get_input()
        if sub_title and sub_title.strip():
            import database
            database.add_subtask(parent_id, sub_title.strip())
            self.refresh_tasks()

    def _on_complete_task(self, task_id: int):
        import database
        database.complete_task(task_id)
        # タスク完了時の歓喜リアクション
        if hasattr(self.parent_gui, 'animator'):
            self.parent_gui.animator.trigger_reaction("task_complete")
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
            row = item.day_of_week
            x0 = start_x + col * (cell_size + pad)
            y0 = start_y + row * (cell_size + pad)
            x1 = x0 + cell_size
            y1 = y0 + cell_size
            
            fill_col = level_colors.get(item.level, "#EFEBE2")
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

        max_streak = max([h.streak for h in habits])
        self.streak_badge_lbl.configure(text=f"🔥 最高ストリーク: {max_streak}日連続")

        for h in habits:
            card = ctk.CTkFrame(self.habits_scroll, fg_color="#FFFFFF", border_color="#E0D8C8", border_width=1, corner_radius=6)
            card.pack(fill="x", pady=3, padx=2)

            left_box = ctk.CTkFrame(card, fg_color="transparent")
            left_box.pack(side="left", fill="both", expand=True, padx=8, pady=6)

            # タイトル・絵文字・ストリークバッジ
            title_row = ctk.CTkFrame(left_box, fg_color="transparent")
            title_row.pack(fill="x")

            emoji_lbl = ctk.CTkLabel(title_row, text=h.emoji, font=("Meiryo UI", 16))
            emoji_lbl.pack(side="left", padx=(0, 6))

            title_text = h.title
            title_lbl = ctk.CTkLabel(title_row, text=title_text, font=self.font_body, text_color=self.text_color)
            title_lbl.pack(side="left")

            if h.streak > 0:
                streak_tag = ctk.CTkLabel(title_row, text=f"🔥 {h.streak}日連続", font=self.font_small, text_color="#E65100")
                streak_tag.pack(side="left", padx=8)

            total_tag = ctk.CTkLabel(title_row, text=f"（累計 {h.total_completed}回）", font=self.font_small, text_color="#9E9E9E")
            total_tag.pack(side="left")

            # 右側アクションボタン（達成トグル ＆ 削除）
            right_box = ctk.CTkFrame(card, fg_color="transparent")
            right_box.pack(side="right", padx=8, pady=6)

            def make_toggle_cb(h_id=h.id):
                return lambda: self._on_toggle_habit(h_id)

            def make_del_cb(h_id=h.id):
                return lambda: self._on_delete_habit(h_id)

            is_done = h.completed_today
            btn_check = ctk.CTkButton(
                right_box,
                text="✔ 達成！" if is_done else "未完了",
                width=65,
                height=26,
                font=self.font_small,
                fg_color="#4CAF50" if is_done else "#E0D8C8",
                text_color="#FFFFFF" if is_done else self.text_color,
                hover_color="#388E3C" if is_done else "#D5CBB8",
                command=make_toggle_cb(h.id)
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
                command=make_del_cb(h.id)
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

    def refresh_events_only(self) -> None:
        """予定データのみを軽量に再取得して再描画する（他タブには触れない）。

        手帳を開きっぱなしの間にAIチャット/スマホ/MCP/webhook/iCal同期で
        登録された予定を反映するための低コスト更新経路。
        全タブ再構築（refresh_all_data）と異なり、TODO/習慣/トリセツの
        再取得・再描画は行わないため、UIスレッドを数ミリ秒しか塞がない。

        Raises:
            Exception: DBアクセスに失敗した場合（呼び出し側でログとフォールバックを行うこと）。
        """
        import database
        # 購読ソース（仕事用/プライベート等）を読み込み、無効ソースの予定は表示から除外する
        self.calendar_sources = database.get_all_calendar_sources()
        enabled_source_ids = {s.id for s in self.calendar_sources if s.enabled}
        # 月間ビューが過去日を含めて描画できるよう、モジュール定数の期間窓で取得する
        now = datetime.datetime.now()
        range_start_ms = int((now - datetime.timedelta(days=EVENT_RANGE_PAST_DAYS)).timestamp() * 1000)
        range_end_ms = int((now + datetime.timedelta(days=EVENT_RANGE_FUTURE_DAYS)).timestamp() * 1000)
        events = database.get_events_between(range_start_ms, range_end_ms)
        events = [e for e in events if e.source_id is None or e.source_id in enabled_source_ids]
        self.load_events(events)

    def refresh_all_data(self) -> None:
        """全タブのデータを一括更新する。

        予定の再取得は軽量経路 refresh_events_only() に委譲し、
        TODO/習慣/トリセツの再取得を追加で実行する。
        """
        self.refresh_events_only()
        self.refresh_tasks()
        self.refresh_habits()
        self.refresh_insights()

    def _schedule_auto_refresh(self) -> None:
        """予定の自動リフレッシュを次回分予約する（手帳破棄後は静かに停止する）。"""
        try:
            self._auto_refresh_job = self.after(
                EVENT_AUTO_REFRESH_INTERVAL_MS, self._auto_refresh_tick
            )
        except Exception as e:
            # ウィンドウ破棄後やテスト環境など、after() が使えない場合は周期停止
            logger.debug(f"手帳の自動リフレッシュ予約をスキップしました: {e}")

    def _auto_refresh_tick(self) -> None:
        """定期リフレッシュのTick。予定のみを軽量再取得し、生存中なら次回を予約する。"""
        try:
            if not self.winfo_exists():
                return  # 手帳が閉じられたため周期を停止する
            self.refresh_events_only()
        except Exception as e:
            logger.warning(f"手帳の自動リフレッシュに失敗: {e}")
        self._schedule_auto_refresh()

    def _on_focus_in(self, event: tk.Event) -> None:
        """手帳ウィンドウ自体にフォーカスが戻ったタイミングで予定を即時再取得する。

        Args:
            event: TkinterのFocusInイベント（子ウィジェット由来のイベントは無視する）。
        """
        if event.widget is not self:
            return
        try:
            self.refresh_events_only()
        except Exception as e:
            logger.warning(f"手帳のフォーカス時リフレッシュに失敗: {e}")

