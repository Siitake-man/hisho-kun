"""
ネオ秘書くん - 付箋ウィンドウ (ui/sticky_note.py)
デスクトップ常駐型ドラッグ可能付箋ウィジェット（DB自動永続化）。
"""

import logging
import tkinter as tk

logger = logging.getLogger(__name__)

class StickyNoteWindow(tk.Toplevel):
    """
    デスクトップに常駐する付箋（Sticky Note）ウィンドウ
    """
    def __init__(self, parent_gui, note):
        super().__init__(parent_gui.root)
        self.note = note
        
        # タイトルバーを隠して付箋っぽくする
        self.overrideredirect(True)
        # 常に最前面表示
        self.attributes('-topmost', True)
        
        # 背景色の設定
        self.bg_color = note.color if note.color else "#FFEB3B"
        self.configure(bg=self.bg_color)
        
        # DBに保存された位置とサイズを適用
        self.geometry(f"{note.width}x{note.height}+{note.position_x}+{note.position_y}")
        
        font_style = ("DotGothic16", 12) if "DotGothic16" in tk.font.families() else ("Meiryo UI", 11)
        
        # ドラッグして移動できるようにするためのヘッダー領域（少し濃い色）
        self.header = tk.Frame(self, bg="#E6D235", height=15, cursor="fleur")
        self.header.pack(fill=tk.X)
        self.header.bind("<ButtonPress-1>", self._start_move)
        self.header.bind("<B1-Motion>", self._do_move)
        
        # 閉じるボタン（DBからも削除する）
        close_btn = tk.Label(self.header, text="✖", bg="#E6D235", fg="#4A3B32", cursor="hand2", font=("Arial", 8))
        close_btn.pack(side=tk.RIGHT, padx=5)
        close_btn.bind("<Button-1>", self._on_close)
        
        # 本文の表示（編集可能なTextウィジェットに変更）
        self.textbox = tk.Text(
            self, 
            bg=self.bg_color,
            fg="#4A3B32",
            font=font_style,
            wrap=tk.WORD,
            bd=0,
            highlightthickness=0
        )
        self.textbox.insert("1.0", note.content)
        self.textbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        
        # フォーカスが外れたタイミングでDBを更新する設定
        self.textbox.bind("<FocusOut>", self._save_content)
        
        # 入力中フラグ
        self.is_editing = False
        self.textbox.bind("<FocusIn>", lambda e: setattr(self, 'is_editing', True))

    def _save_content(self, event=None):
        """テキストの変更をDBに保存する"""
        self.is_editing = False
        new_content = self.textbox.get("1.0", tk.END).strip()
        if new_content != self.note.content:
            self.note.content = new_content
            import database
            try:
                database.update_sticky_note(self.note)
            except Exception as e:
                logger.error(f"付箋の保存に失敗: {e}")

    def _on_close(self, event):
        """付箋を閉じる際の処理。DBから完全に削除する"""
        import database
        try:
            database.delete_sticky_note(self.note.id)
            self.destroy()
        except Exception as e:
            logger.error(f"付箋の削除に失敗: {e}")

    def _start_move(self, event):
        self.x = event.x
        self.y = event.y

    def _do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")
        
        self.note.position_x = x
        self.note.position_y = y

# 後方互換エイリアス
DraggableStickyNote = StickyNoteWindow
