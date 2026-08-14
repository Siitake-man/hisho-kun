import { useState, useRef, useEffect } from "react";
import { useAuth } from "@/_core/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Plus, Home, Calendar, X, Minimize2, Maximize2 } from "lucide-react";
import { getLoginUrl } from "@/const";
import { Link } from "wouter";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";

const STICKY_COLORS = [
  { value: "#FFFACD", label: "イエロー", class: "" },
  { value: "#FFB6C1", label: "ピンク", class: "pink" },
  { value: "#ADD8E6", label: "ブルー", class: "blue" },
  { value: "#90EE90", label: "グリーン", class: "green" },
];

interface StickyNoteData {
  id: number;
  content: string;
  color: string;
  positionX: number | null;
  positionY: number | null;
  width: number | null;
  height: number | null;
  zIndex: number | null;
  isMinimized: boolean;
}

export default function StickyNotes() {
  const { user, loading, isAuthenticated } = useAuth();
  const [draggedNote, setDraggedNote] = useState<number | null>(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const [editingNote, setEditingNote] = useState<number | null>(null);
  const [newNoteContent, setNewNoteContent] = useState("");
  const [newNoteColor, setNewNoteColor] = useState("#FFFACD");
  const [isCreating, setIsCreating] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const [maxZIndex, setMaxZIndex] = useState(1);

  const { data: notes, isLoading, refetch } = trpc.stickyNotes.list.useQuery(
    undefined,
    { enabled: isAuthenticated }
  );

  const createNoteMutation = trpc.stickyNotes.create.useMutation({
    onSuccess: () => {
      toast.success("付箋を作成しました");
      setNewNoteContent("");
      setIsCreating(false);
      refetch();
    },
    onError: (error) => {
      toast.error("付箋の作成に失敗しました: " + error.message);
    },
  });

  const updateNoteMutation = trpc.stickyNotes.update.useMutation({
    onSuccess: () => {
      refetch();
    },
    onError: (error) => {
      toast.error("付箋の更新に失敗しました: " + error.message);
    },
  });

  const deleteNoteMutation = trpc.stickyNotes.delete.useMutation({
    onSuccess: () => {
      toast.success("付箋を削除しました");
      refetch();
    },
    onError: (error) => {
      toast.error("付箋の削除に失敗しました: " + error.message);
    },
  });

  useEffect(() => {
    if (notes) {
      const max = Math.max(...notes.map(n => n.zIndex || 1), 1);
      setMaxZIndex(max);
    }
  }, [notes]);

  const handleMouseDown = (e: React.MouseEvent, noteId: number, note: StickyNoteData) => {
    if (editingNote === noteId) return;
    
    const rect = (e.target as HTMLElement).closest('.sticky-note')?.getBoundingClientRect();
    if (!rect) return;
    
    setDraggedNote(noteId);
    setDragOffset({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });

    // Bring to front
    const newZIndex = maxZIndex + 1;
    setMaxZIndex(newZIndex);
    updateNoteMutation.mutate({
      id: noteId,
      zIndex: newZIndex,
    });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!draggedNote || !containerRef.current) return;
    
    const containerRect = containerRef.current.getBoundingClientRect();
    const newX = e.clientX - containerRect.left - dragOffset.x;
    const newY = e.clientY - containerRect.top - dragOffset.y;
    
    // Update position in real-time (optimistic)
    const noteElement = document.querySelector(`[data-note-id="${draggedNote}"]`) as HTMLElement;
    if (noteElement) {
      noteElement.style.left = `${Math.max(0, newX)}px`;
      noteElement.style.top = `${Math.max(0, newY)}px`;
    }
  };

  const handleMouseUp = (e: React.MouseEvent) => {
    if (!draggedNote || !containerRef.current) {
      setDraggedNote(null);
      return;
    }
    
    const containerRect = containerRef.current.getBoundingClientRect();
    const newX = Math.max(0, e.clientX - containerRect.left - dragOffset.x);
    const newY = Math.max(0, e.clientY - containerRect.top - dragOffset.y);
    
    updateNoteMutation.mutate({
      id: draggedNote,
      positionX: Math.round(newX),
      positionY: Math.round(newY),
    });
    
    setDraggedNote(null);
  };

  const handleCreateNote = () => {
    if (!newNoteContent.trim()) return;
    
    // Random position within visible area
    const randomX = Math.floor(Math.random() * 400) + 50;
    const randomY = Math.floor(Math.random() * 300) + 50;
    
    createNoteMutation.mutate({
      content: newNoteContent,
      color: newNoteColor,
      positionX: randomX,
      positionY: randomY,
    });
  };

  const handleUpdateContent = (noteId: number, content: string) => {
    updateNoteMutation.mutate({
      id: noteId,
      content,
    });
    setEditingNote(null);
  };

  const toggleMinimize = (noteId: number, currentState: boolean) => {
    updateNoteMutation.mutate({
      id: noteId,
      isMinimized: !currentState,
    });
  };

  const getColorClass = (color: string) => {
    const colorObj = STICKY_COLORS.find(c => c.value === color);
    return colorObj?.class || "";
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="animate-spin h-12 w-12 text-primary" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="retro-paper p-6 rounded">
          <p className="mb-4">付箋を使用するにはログインが必要です</p>
          <a href={getLoginUrl()}>
            <Button className="retro-button">ログイン</Button>
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b-2 border-border bg-card sticky top-0 z-50">
        <div className="container py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Link href="/">
                <Button variant="ghost" size="icon" className="retro-button">
                  <Home className="w-4 h-4" />
                </Button>
              </Link>
              <div className="flex items-center gap-2">
                <span className="text-xl">📝</span>
                <h1 className="text-lg font-bold">付箋メモ</h1>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Link href="/calendar">
                <Button variant="ghost" size="sm" className="retro-button">
                  <Calendar className="w-4 h-4 mr-1" />
                  カレンダー
                </Button>
              </Link>
              <span className="text-sm text-muted-foreground">
                {user?.name || 'ユーザー'}さん
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Toolbar */}
      <div className="container py-4">
        <div className="flex items-center gap-4 mb-4">
          <Button 
            onClick={() => setIsCreating(true)} 
            className="retro-button"
            disabled={isCreating}
          >
            <Plus className="w-4 h-4 mr-1" />
            新しい付箋
          </Button>
          <span className="text-sm text-muted-foreground">
            {notes?.length || 0}件の付箋
          </span>
        </div>

        {/* Create Note Form */}
        {isCreating && (
          <div className="retro-paper p-4 mb-4 max-w-md">
            <h3 className="font-bold mb-3">新しい付箋を作成</h3>
            <Textarea
              value={newNoteContent}
              onChange={(e) => setNewNoteContent(e.target.value)}
              placeholder="メモを入力..."
              rows={4}
              className="mb-3"
              autoFocus
            />
            <div className="flex items-center gap-2 mb-3">
              <span className="text-sm">色:</span>
              {STICKY_COLORS.map((color) => (
                <button
                  key={color.value}
                  type="button"
                  onClick={() => setNewNoteColor(color.value)}
                  className={`w-6 h-6 rounded border-2 transition-transform ${
                    newNoteColor === color.value ? "border-foreground scale-110" : "border-transparent"
                  }`}
                  style={{ backgroundColor: color.value }}
                  title={color.label}
                />
              ))}
            </div>
            <div className="flex gap-2">
              <Button 
                onClick={handleCreateNote} 
                disabled={!newNoteContent.trim() || createNoteMutation.isPending}
                className="retro-button"
              >
                {createNoteMutation.isPending && <Loader2 className="w-4 h-4 animate-spin mr-1" />}
                作成
              </Button>
              <Button 
                variant="outline" 
                onClick={() => {
                  setIsCreating(false);
                  setNewNoteContent("");
                }}
                className="retro-button"
              >
                キャンセル
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Sticky Notes Canvas */}
      <div 
        ref={containerRef}
        className="relative min-h-[calc(100vh-200px)] mx-4 mb-4 retro-paper rounded overflow-hidden"
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{ 
          backgroundImage: `
            linear-gradient(90deg, transparent 79px, #ddd 79px, #ddd 80px, transparent 80px),
            linear-gradient(#eee 1px, transparent 1px)
          `,
          backgroundSize: '80px 24px',
        }}
      >
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="animate-spin h-8 w-8 text-primary" />
          </div>
        ) : notes && notes.length > 0 ? (
          notes.map((note) => (
            <div
              key={note.id}
              data-note-id={note.id}
              className={`sticky-note absolute p-3 cursor-move select-none ${getColorClass(note.color)}`}
              style={{
                left: note.positionX || 100,
                top: note.positionY || 100,
                width: note.isMinimized ? 150 : (note.width || 200),
                height: note.isMinimized ? 'auto' : (note.height || 150),
                zIndex: note.zIndex || 1,
                backgroundColor: note.color,
              }}
              onMouseDown={(e) => handleMouseDown(e, note.id, note)}
            >
              {/* Note Header */}
              <div className="flex items-center justify-between mb-2 -mt-1">
                <div className="flex gap-1">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleMinimize(note.id, note.isMinimized);
                    }}
                    className="w-5 h-5 rounded hover:bg-black/10 flex items-center justify-center"
                    title={note.isMinimized ? "展開" : "最小化"}
                  >
                    {note.isMinimized ? (
                      <Maximize2 className="w-3 h-3" />
                    ) : (
                      <Minimize2 className="w-3 h-3" />
                    )}
                  </button>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm("この付箋を削除しますか？")) {
                      deleteNoteMutation.mutate({ id: note.id });
                    }
                  }}
                  className="w-5 h-5 rounded hover:bg-red-200 flex items-center justify-center text-red-600"
                  title="削除"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
              
              {/* Note Content */}
              {!note.isMinimized && (
                editingNote === note.id ? (
                  <Textarea
                    defaultValue={note.content}
                    onBlur={(e) => handleUpdateContent(note.id, e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Escape') {
                        setEditingNote(null);
                      }
                    }}
                    className="w-full h-full resize-none border-none bg-transparent p-0 focus:ring-0"
                    autoFocus
                    onClick={(e) => e.stopPropagation()}
                    onMouseDown={(e) => e.stopPropagation()}
                  />
                ) : (
                  <div
                    className="text-sm whitespace-pre-wrap overflow-hidden"
                    style={{ maxHeight: (note.height || 150) - 40 }}
                    onDoubleClick={(e) => {
                      e.stopPropagation();
                      setEditingNote(note.id);
                    }}
                  >
                    {note.content}
                  </div>
                )
              )}
              
              {note.isMinimized && (
                <div className="text-xs truncate">
                  {note.content.substring(0, 20)}...
                </div>
              )}
            </div>
          ))
        ) : (
          <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
            <span className="text-4xl mb-4">📝</span>
            <p>付箋がありません</p>
            <p className="text-sm">「新しい付箋」ボタンで作成してください</p>
          </div>
        )}
      </div>
    </div>
  );
}
