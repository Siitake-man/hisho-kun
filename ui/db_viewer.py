"""
ネオ秘書くん - データベースビューア (ui/db_viewer.py)
SQLiteデータベース内の全テーブル（タスク、予定、付箋、知見）を閲覧・検索する開発・管理用ウィンドウ。
"""

import logging
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
import database

logger = logging.getLogger(__name__)

class DatabaseViewerWindow(ctk.CTkToplevel):
    """
    SQLite DBの各テーブルをタブ切り替え・テーブル表示で確認できるビューア。
    """
    def __init__(self, parent_gui, *args, **kwargs):
        super().__init__(parent_gui.root, *args, **kwargs)
        self.parent_gui = parent_gui
        self.title("🔍 ネオ秘書くん - データベースビューア")
        self.geometry("640x520")
        
        self.bg_color = "#F5F5DC"
        self.primary_color = "#A67B5B"
        self.text_color = "#4A3B32"
        self.configure(fg_color=self.bg_color)
        
        self._build_ui()
        self.refresh_data()

    def _build_ui(self):
        # ヘッダー
        header = ctk.CTkFrame(self, fg_color=self.primary_color, corner_radius=0, height=40)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text="🗄️ ローカルデータベース・インスペクター",
            font=("Meiryo UI", 12, "bold"),
            text_color="#FFFFFF"
        ).pack(pady=8)
        
        # タブビュー
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=self.bg_color,
            segmented_button_selected_color=self.primary_color,
            segmented_button_selected_hover_color="#8B634A"
        )
        self.tabview.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.tab_tasks = self.tabview.add("📋 タスク (Tasks)")
        self.tab_events = self.tabview.add("📅 予定 (Events)")
        self.tab_notes = self.tabview.add("📌 付箋 (StickyNotes)")
        self.tab_insights = self.tabview.add("🧠 知見 (UserInsights)")
        
        # 各タブのTreeview構築
        self.tree_tasks = self._create_tree(self.tab_tasks, ["ID", "Title", "Status", "Priority", "Due"])
        self.tree_events = self._create_tree(self.tab_events, ["ID", "Title", "Start", "End", "Source"])
        self.tree_notes = self._create_tree(self.tab_notes, ["ID", "Content", "Color", "X", "Y"])
        self.tree_insights = self._create_tree(self.tab_insights, ["ID", "Category", "Content", "Importance"])
        
        # フッター・リフレッシュボタン
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=10, pady=6)
        
        ctk.CTkButton(
            footer,
            text="🔄 データを最新に更新",
            font=("Meiryo UI", 10, "bold"),
            fg_color=self.primary_color,
            hover_color="#8B634A",
            command=self.refresh_data
        ).pack(side="right")

    def _create_tree(self, parent, columns):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=4, pady=4)
        
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=12)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100, anchor="w")
            
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        return tree

    def refresh_data(self):
        """全テーブルのデータを読み込んで再描画"""
        try:
            # 1. Tasks
            for item in self.tree_tasks.get_children():
                self.tree_tasks.delete(item)
            for t in database.get_tasks(limit=100):
                self.tree_tasks.insert("", "end", values=(t.id, t.title, t.status, t.priority, t.due_date or "-"))
                
            # 2. Events
            for item in self.tree_events.get_children():
                self.tree_events.delete(item)
            for e in database.get_upcoming_events(days=60):
                self.tree_events.insert("", "end", values=(e.id, e.title, e.start_time, e.end_time, e.source))
                
            # 3. Notes
            for item in self.tree_notes.get_children():
                self.tree_notes.delete(item)
            for n in database.get_all_sticky_notes():
                self.tree_notes.insert("", "end", values=(n.id, n.content[:30], n.color, n.position_x, n.position_y))
                
            # 4. Insights
            for item in self.tree_insights.get_children():
                self.tree_insights.delete(item)
            for ins in database.get_user_insights(limit=100):
                self.tree_insights.insert("", "end", values=(ins.id, ins.category, ins.content[:40], "★" * ins.importance))
        except Exception as e:
            logger.error(f"DBビューアデータ更新エラー: {e}")
