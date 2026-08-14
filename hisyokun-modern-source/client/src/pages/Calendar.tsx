import { useState, useMemo } from "react";
import { useAuth } from "@/_core/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Loader2, ChevronLeft, ChevronRight, Plus, Calendar as CalendarIcon, Home, StickyNote } from "lucide-react";
import { getLoginUrl } from "@/const";
import { Link, useParams } from "wouter";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";

type ViewType = "month" | "week" | "day";

const WEEKDAYS = ["日", "月", "火", "水", "木", "金", "土"];
const RECURRENCE_TYPES = [
  { value: "once", label: "一回きり" },
  { value: "yearly_date", label: "毎年○月○日" },
  { value: "yearly_weekday", label: "毎年○月第○○曜日" },
  { value: "monthly_date", label: "毎月○日" },
  { value: "monthly_end", label: "毎月末" },
  { value: "monthly_weekday", label: "毎月第○○曜日" },
  { value: "biweekly", label: "隔週○曜日" },
  { value: "weekly", label: "毎週○曜日" },
  { value: "daily", label: "毎日" },
];

const EVENT_COLORS = [
  { value: "#D4A574", label: "ブラウン" },
  { value: "#E57373", label: "レッド" },
  { value: "#64B5F6", label: "ブルー" },
  { value: "#81C784", label: "グリーン" },
  { value: "#BA68C8", label: "パープル" },
  { value: "#FFB74D", label: "オレンジ" },
];

interface EventFormData {
  title: string;
  description: string;
  startDate: string;
  startTime: string;
  endDate: string;
  endTime: string;
  isAllDay: boolean;
  recurrenceType: string;
  color: string;
}

const initialFormData: EventFormData = {
  title: "",
  description: "",
  startDate: new Date().toISOString().split("T")[0],
  startTime: "09:00",
  endDate: new Date().toISOString().split("T")[0],
  endTime: "10:00",
  isAllDay: false,
  recurrenceType: "once",
  color: "#D4A574",
};

export default function Calendar() {
  const { user, loading, isAuthenticated } = useAuth();
  const params = useParams<{ view?: string }>();
  const [currentView, setCurrentView] = useState<ViewType>((params.view as ViewType) || "month");
  const [currentDate, setCurrentDate] = useState(new Date());
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [formData, setFormData] = useState<EventFormData>(initialFormData);
  const [selectedEvent, setSelectedEvent] = useState<number | null>(null);

  // Calculate date range for query
  const dateRange = useMemo(() => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    
    if (currentView === "month") {
      const firstDay = new Date(year, month, 1);
      const lastDay = new Date(year, month + 1, 0);
      // Include days from previous/next month that appear in the calendar
      const startDate = new Date(firstDay);
      startDate.setDate(startDate.getDate() - firstDay.getDay());
      const endDate = new Date(lastDay);
      endDate.setDate(endDate.getDate() + (6 - lastDay.getDay()));
      return { startDate: startDate.getTime(), endDate: endDate.getTime() + 86400000 - 1 };
    } else if (currentView === "week") {
      const startOfWeek = new Date(currentDate);
      startOfWeek.setDate(currentDate.getDate() - currentDate.getDay());
      startOfWeek.setHours(0, 0, 0, 0);
      const endOfWeek = new Date(startOfWeek);
      endOfWeek.setDate(startOfWeek.getDate() + 6);
      endOfWeek.setHours(23, 59, 59, 999);
      return { startDate: startOfWeek.getTime(), endDate: endOfWeek.getTime() };
    } else {
      const startOfDay = new Date(currentDate);
      startOfDay.setHours(0, 0, 0, 0);
      const endOfDay = new Date(currentDate);
      endOfDay.setHours(23, 59, 59, 999);
      return { startDate: startOfDay.getTime(), endDate: endOfDay.getTime() };
    }
  }, [currentDate, currentView]);

  const { data: events, isLoading: eventsLoading, refetch } = trpc.events.list.useQuery(
    dateRange,
    { enabled: isAuthenticated }
  );

  const createEventMutation = trpc.events.create.useMutation({
    onSuccess: () => {
      toast.success("予定を作成しました");
      setIsCreateDialogOpen(false);
      setFormData(initialFormData);
      refetch();
    },
    onError: (error) => {
      toast.error("予定の作成に失敗しました: " + error.message);
    },
  });

  const deleteEventMutation = trpc.events.delete.useMutation({
    onSuccess: () => {
      toast.success("予定を削除しました");
      setSelectedEvent(null);
      refetch();
    },
    onError: (error) => {
      toast.error("予定の削除に失敗しました: " + error.message);
    },
  });

  const handleCreateEvent = () => {
    const startDateTime = formData.isAllDay
      ? new Date(formData.startDate).setHours(0, 0, 0, 0)
      : new Date(`${formData.startDate}T${formData.startTime}`).getTime();
    
    const endDateTime = formData.isAllDay
      ? new Date(formData.endDate).setHours(23, 59, 59, 999)
      : new Date(`${formData.endDate}T${formData.endTime}`).getTime();

    createEventMutation.mutate({
      title: formData.title,
      description: formData.description || undefined,
      startTime: startDateTime,
      endTime: endDateTime,
      isAllDay: formData.isAllDay,
      recurrenceType: formData.recurrenceType as any,
      color: formData.color,
    });
  };

  const navigateDate = (direction: "prev" | "next") => {
    const newDate = new Date(currentDate);
    if (currentView === "month") {
      newDate.setMonth(newDate.getMonth() + (direction === "next" ? 1 : -1));
    } else if (currentView === "week") {
      newDate.setDate(newDate.getDate() + (direction === "next" ? 7 : -7));
    } else {
      newDate.setDate(newDate.getDate() + (direction === "next" ? 1 : -1));
    }
    setCurrentDate(newDate);
  };

  const goToToday = () => {
    setCurrentDate(new Date());
  };

  // Generate calendar days for month view
  const calendarDays = useMemo(() => {
    if (currentView !== "month") return [];
    
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    
    const days: { date: Date; isCurrentMonth: boolean }[] = [];
    
    // Add days from previous month
    for (let i = firstDay.getDay() - 1; i >= 0; i--) {
      const date = new Date(year, month, -i);
      days.push({ date, isCurrentMonth: false });
    }
    
    // Add days of current month
    for (let i = 1; i <= lastDay.getDate(); i++) {
      days.push({ date: new Date(year, month, i), isCurrentMonth: true });
    }
    
    // Add days from next month
    const remainingDays = 42 - days.length; // 6 weeks * 7 days
    for (let i = 1; i <= remainingDays; i++) {
      days.push({ date: new Date(year, month + 1, i), isCurrentMonth: false });
    }
    
    return days;
  }, [currentDate, currentView]);

  // Get events for a specific day
  const getEventsForDay = (date: Date) => {
    if (!events) return [];
    const dayStart = new Date(date).setHours(0, 0, 0, 0);
    const dayEnd = new Date(date).setHours(23, 59, 59, 999);
    return events.filter(event => 
      event.startTime >= dayStart && event.startTime <= dayEnd
    );
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
        <Card className="retro-paper p-6">
          <p className="mb-4">カレンダーを使用するにはログインが必要です</p>
          <a href={getLoginUrl()}>
            <Button className="retro-button">ログイン</Button>
          </a>
        </Card>
      </div>
    );
  }

  const isToday = (date: Date) => {
    const today = new Date();
    return date.toDateString() === today.toDateString();
  };

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
                <CalendarIcon className="w-5 h-5 text-primary" />
                <h1 className="text-lg font-bold">カレンダー</h1>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Link href="/sticky-notes">
                <Button variant="ghost" size="sm" className="retro-button">
                  <StickyNote className="w-4 h-4 mr-1" />
                  付箋
                </Button>
              </Link>
              <span className="text-sm text-muted-foreground">
                {user?.name || 'ユーザー'}さん
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Calendar Controls */}
      <div className="container py-4">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => navigateDate("prev")} className="retro-button">
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={goToToday} className="retro-button">
              今日
            </Button>
            <Button variant="outline" size="sm" onClick={() => navigateDate("next")} className="retro-button">
              <ChevronRight className="w-4 h-4" />
            </Button>
            <h2 className="text-xl font-bold ml-4">
              {currentDate.toLocaleDateString('ja-JP', { 
                year: 'numeric', 
                month: 'long',
                ...(currentView === "day" ? { day: 'numeric', weekday: 'long' } : {})
              })}
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex border border-border rounded overflow-hidden">
              {(["month", "week", "day"] as ViewType[]).map((view) => (
                <Button
                  key={view}
                  variant={currentView === view ? "default" : "ghost"}
                  size="sm"
                  onClick={() => setCurrentView(view)}
                  className={currentView === view ? "" : "retro-button"}
                >
                  {view === "month" ? "月" : view === "week" ? "週" : "日"}
                </Button>
              ))}
            </div>
            <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
              <DialogTrigger asChild>
                <Button className="retro-button">
                  <Plus className="w-4 h-4 mr-1" />
                  予定を追加
                </Button>
              </DialogTrigger>
              <DialogContent className="retro-paper max-w-md">
                <DialogHeader>
                  <DialogTitle>新しい予定</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 mt-4">
                  <div>
                    <Label htmlFor="title">タイトル</Label>
                    <Input
                      id="title"
                      value={formData.title}
                      onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                      placeholder="予定のタイトル"
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label htmlFor="description">説明</Label>
                    <Textarea
                      id="description"
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      placeholder="詳細な説明（任意）"
                      className="mt-1"
                      rows={2}
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <Switch
                      id="allDay"
                      checked={formData.isAllDay}
                      onCheckedChange={(checked) => setFormData({ ...formData, isAllDay: checked })}
                    />
                    <Label htmlFor="allDay">終日</Label>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="startDate">開始日</Label>
                      <Input
                        id="startDate"
                        type="date"
                        value={formData.startDate}
                        onChange={(e) => setFormData({ ...formData, startDate: e.target.value })}
                        className="mt-1"
                      />
                    </div>
                    {!formData.isAllDay && (
                      <div>
                        <Label htmlFor="startTime">開始時刻</Label>
                        <Input
                          id="startTime"
                          type="time"
                          value={formData.startTime}
                          onChange={(e) => setFormData({ ...formData, startTime: e.target.value })}
                          className="mt-1"
                        />
                      </div>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="endDate">終了日</Label>
                      <Input
                        id="endDate"
                        type="date"
                        value={formData.endDate}
                        onChange={(e) => setFormData({ ...formData, endDate: e.target.value })}
                        className="mt-1"
                      />
                    </div>
                    {!formData.isAllDay && (
                      <div>
                        <Label htmlFor="endTime">終了時刻</Label>
                        <Input
                          id="endTime"
                          type="time"
                          value={formData.endTime}
                          onChange={(e) => setFormData({ ...formData, endTime: e.target.value })}
                          className="mt-1"
                        />
                      </div>
                    )}
                  </div>
                  <div>
                    <Label>繰り返し</Label>
                    <Select
                      value={formData.recurrenceType}
                      onValueChange={(value) => setFormData({ ...formData, recurrenceType: value })}
                    >
                      <SelectTrigger className="mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {RECURRENCE_TYPES.map((type) => (
                          <SelectItem key={type.value} value={type.value}>
                            {type.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>色</Label>
                    <div className="flex gap-2 mt-1">
                      {EVENT_COLORS.map((color) => (
                        <button
                          key={color.value}
                          type="button"
                          onClick={() => setFormData({ ...formData, color: color.value })}
                          className={`w-8 h-8 rounded-full border-2 transition-transform ${
                            formData.color === color.value ? "border-foreground scale-110" : "border-transparent"
                          }`}
                          style={{ backgroundColor: color.value }}
                          title={color.label}
                        />
                      ))}
                    </div>
                  </div>
                  <div className="flex justify-end gap-2 pt-4">
                    <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)} className="retro-button">
                      キャンセル
                    </Button>
                    <Button 
                      onClick={handleCreateEvent} 
                      disabled={!formData.title || createEventMutation.isPending}
                      className="retro-button"
                    >
                      {createEventMutation.isPending ? (
                        <Loader2 className="w-4 h-4 animate-spin mr-1" />
                      ) : null}
                      作成
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Calendar Grid */}
        {eventsLoading ? (
          <div className="flex items-center justify-center h-96">
            <Loader2 className="animate-spin h-8 w-8 text-primary" />
          </div>
        ) : currentView === "month" ? (
          <div className="retro-folder p-4 pt-8 relative">
            <div className="retro-folder-tab">
              {currentDate.toLocaleDateString('ja-JP', { month: 'short' })}
            </div>
            {/* Weekday Headers */}
            <div className="grid grid-cols-7 mb-2">
              {WEEKDAYS.map((day, index) => (
                <div
                  key={day}
                  className={`text-center py-2 font-bold text-sm ${
                    index === 0 ? "text-red-600" : index === 6 ? "text-blue-600" : ""
                  }`}
                >
                  {day}
                </div>
              ))}
            </div>
            {/* Calendar Days */}
            <div className="grid grid-cols-7 gap-1">
              {calendarDays.map(({ date, isCurrentMonth }, index) => {
                const dayEvents = getEventsForDay(date);
                const dayOfWeek = date.getDay();
                return (
                  <div
                    key={index}
                    className={`calendar-day p-1 ${
                      !isCurrentMonth ? "other-month" : ""
                    } ${isToday(date) ? "today" : ""}`}
                    onClick={() => {
                      setCurrentDate(date);
                      setCurrentView("day");
                    }}
                  >
                    <div className={`text-right text-sm mb-1 ${
                      dayOfWeek === 0 ? "text-red-600" : dayOfWeek === 6 ? "text-blue-600" : ""
                    }`}>
                      {date.getDate()}
                    </div>
                    <div className="space-y-0.5">
                      {dayEvents.slice(0, 3).map((event) => (
                        <div
                          key={event.id}
                          className="event-chip text-white"
                          style={{ backgroundColor: event.color || "#D4A574" }}
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedEvent(event.id);
                          }}
                        >
                          {event.title}
                        </div>
                      ))}
                      {dayEvents.length > 3 && (
                        <div className="text-xs text-muted-foreground text-center">
                          +{dayEvents.length - 3}件
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : currentView === "week" ? (
          <div className="retro-folder p-4 pt-8 relative">
            <div className="retro-folder-tab">週表示</div>
            <div className="grid grid-cols-7 gap-2">
              {Array.from({ length: 7 }).map((_, index) => {
                const date = new Date(currentDate);
                date.setDate(date.getDate() - date.getDay() + index);
                const dayEvents = getEventsForDay(date);
                return (
                  <div key={index} className="retro-paper p-2 min-h-[300px]">
                    <div className={`text-center font-bold mb-2 pb-2 border-b border-border ${
                      index === 0 ? "text-red-600" : index === 6 ? "text-blue-600" : ""
                    } ${isToday(date) ? "bg-accent rounded" : ""}`}>
                      <div className="text-xs">{WEEKDAYS[index]}</div>
                      <div className="text-lg">{date.getDate()}</div>
                    </div>
                    <div className="space-y-1">
                      {dayEvents.map((event) => (
                        <div
                          key={event.id}
                          className="event-chip text-white text-xs"
                          style={{ backgroundColor: event.color || "#D4A574" }}
                        >
                          {!event.isAllDay && (
                            <span className="mr-1">
                              {new Date(event.startTime).toLocaleTimeString('ja-JP', { 
                                hour: '2-digit', 
                                minute: '2-digit' 
                              })}
                            </span>
                          )}
                          {event.title}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="retro-folder p-4 pt-8 relative">
            <div className="retro-folder-tab">日表示</div>
            <div className="retro-paper p-4">
              <div className="space-y-2">
                {events && events.length > 0 ? (
                  events.map((event) => (
                    <Card key={event.id} className="retro-paper">
                      <CardContent className="p-4 flex items-start gap-4">
                        <div
                          className="w-4 h-4 rounded-full flex-shrink-0 mt-1"
                          style={{ backgroundColor: event.color || "#D4A574" }}
                        />
                        <div className="flex-1">
                          <h3 className="font-bold">{event.title}</h3>
                          {!event.isAllDay && (
                            <p className="text-sm text-muted-foreground">
                              {new Date(event.startTime).toLocaleTimeString('ja-JP', { 
                                hour: '2-digit', 
                                minute: '2-digit' 
                              })}
                              {event.endTime && (
                                <> 〜 {new Date(event.endTime).toLocaleTimeString('ja-JP', { 
                                  hour: '2-digit', 
                                  minute: '2-digit' 
                                })}</>
                              )}
                            </p>
                          )}
                          {event.description && (
                            <p className="text-sm mt-2">{event.description}</p>
                          )}
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            if (confirm("この予定を削除しますか？")) {
                              deleteEventMutation.mutate({ id: event.id });
                            }
                          }}
                          className="text-destructive hover:text-destructive"
                        >
                          削除
                        </Button>
                      </CardContent>
                    </Card>
                  ))
                ) : (
                  <div className="text-center py-12 text-muted-foreground">
                    <CalendarIcon className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>この日の予定はありません</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
