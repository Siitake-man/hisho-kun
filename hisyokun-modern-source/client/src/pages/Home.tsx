import { useAuth } from "@/_core/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, Calendar, StickyNote, Bell, Cloud, Bot } from "lucide-react";
import { getLoginUrl } from "@/const";
import { Link } from "wouter";
import { trpc } from "@/lib/trpc";

export default function Home() {
  const { user, loading, isAuthenticated } = useAuth();
  const { data: todayEvents, isLoading: eventsLoading } = trpc.events.today.useQuery(
    undefined,
    { enabled: isAuthenticated }
  );

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center">
          <Loader2 className="animate-spin h-12 w-12 mx-auto text-primary" />
          <p className="mt-4 text-muted-foreground">読み込み中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b-2 border-border bg-card">
        <div className="container py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center">
                <span className="text-primary-foreground text-lg">秘</span>
              </div>
              <div>
                <h1 className="text-xl font-bold">秘書くん Modern</h1>
                <p className="text-xs text-muted-foreground">あなたの予定を管理します</p>
              </div>
            </div>
            <nav className="flex items-center gap-2">
              {isAuthenticated ? (
                <>
                  <Link href="/calendar">
                    <Button variant="ghost" size="sm" className="retro-button">
                      <Calendar className="w-4 h-4 mr-1" />
                      カレンダー
                    </Button>
                  </Link>
                  <Link href="/sticky-notes">
                    <Button variant="ghost" size="sm" className="retro-button">
                      <StickyNote className="w-4 h-4 mr-1" />
                      付箋
                    </Button>
                  </Link>
                  <span className="text-sm text-muted-foreground ml-4">
                    {user?.name || 'ユーザー'}さん
                  </span>
                </>
              ) : (
                <a href={getLoginUrl()}>
                  <Button className="retro-button">ログイン</Button>
                </a>
              )}
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container py-8">
        {!isAuthenticated ? (
          /* Landing Page for non-authenticated users */
          <div className="max-w-4xl mx-auto">
            {/* Hero Section */}
            <div className="retro-folder p-8 pt-12 mb-8 relative">
              <div className="retro-folder-tab">秘書くん</div>
              <div className="retro-paper p-6 rounded">
                <h2 className="text-3xl font-bold mb-4 text-center">
                  懐かしくて新しい<br />スケジューラ
                </h2>
                <p className="text-center text-muted-foreground mb-6">
                  2000年代の名作フリーソフト「秘書くん2」を<br />
                  現代のWebアプリケーションとして復活させました
                </p>
                <div className="flex justify-center">
                  <a href={getLoginUrl()}>
                    <Button size="lg" className="retro-button text-lg px-8 py-3">
                      今すぐ始める
                    </Button>
                  </a>
                </div>
              </div>
            </div>

            {/* Features Grid */}
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              <Card className="retro-paper">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Calendar className="w-5 h-5 text-primary" />
                    多機能カレンダー
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    月・週・日表示を切り替え可能。9種類の繰り返しパターンで予定を管理できます。
                  </p>
                </CardContent>
              </Card>

              <Card className="retro-paper">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <StickyNote className="w-5 h-5 text-primary" />
                    付箋メモ
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    日付に縛られないメモを付箋として管理。ドラッグで自由に配置できます。
                  </p>
                </CardContent>
              </Card>

              <Card className="retro-paper">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Bell className="w-5 h-5 text-primary" />
                    通知機能
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    予定の1日前〜30日前まで、ブラウザ通知でお知らせします。
                  </p>
                </CardContent>
              </Card>

              <Card className="retro-paper">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Cloud className="w-5 h-5 text-primary" />
                    Googleカレンダー連携
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Googleカレンダーと双方向同期。既存の予定もそのまま使えます。
                  </p>
                </CardContent>
              </Card>

              <Card className="retro-paper">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Bot className="w-5 h-5 text-primary" />
                    MCP対応
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    ローカルLLMからMCP経由で予定を操作。AIアシスタントと連携できます。
                  </p>
                </CardContent>
              </Card>

              <Card className="retro-paper">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <span className="text-primary">📋</span>
                    伝言メモ
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    今日の予定をウィジェット表示。オリジナル秘書くん2の伝言メモを再現。
                  </p>
                </CardContent>
              </Card>
            </div>
          </div>
        ) : (
          /* Dashboard for authenticated users */
          <div className="grid lg:grid-cols-3 gap-6">
            {/* Today's Events Widget (伝言メモ風) */}
            <div className="lg:col-span-2">
              <div className="message-memo p-6 pt-8">
                <div className="absolute -top-3 left-4 bg-accent px-3 py-1 rounded text-sm font-bold border border-border">
                  📋 今日の予定
                </div>
                <div className="retro-paper-lined min-h-[200px] p-4 rounded">
                  {eventsLoading ? (
                    <div className="flex items-center justify-center h-32">
                      <Loader2 className="animate-spin h-6 w-6 text-muted-foreground" />
                    </div>
                  ) : todayEvents && todayEvents.length > 0 ? (
                    <ul className="space-y-3">
                      {todayEvents.map((event) => (
                        <li key={event.id} className="flex items-start gap-3 py-2">
                          <div 
                            className="w-3 h-3 rounded-full mt-1 flex-shrink-0"
                            style={{ backgroundColor: event.color || '#D4A574' }}
                          />
                          <div>
                            <p className="font-medium">{event.title}</p>
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
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="flex flex-col items-center justify-center h-32 text-muted-foreground">
                      <Calendar className="w-8 h-8 mb-2 opacity-50" />
                      <p>今日の予定はありません</p>
                    </div>
                  )}
                </div>
                <div className="mt-4 flex justify-end">
                  <Link href="/calendar">
                    <Button variant="outline" size="sm" className="retro-button">
                      カレンダーを開く →
                    </Button>
                  </Link>
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="space-y-4">
              <Card className="retro-paper">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">クイックアクション</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <Link href="/calendar" className="block">
                    <Button variant="outline" className="w-full justify-start retro-button">
                      <Calendar className="w-4 h-4 mr-2" />
                      カレンダーを見る
                    </Button>
                  </Link>
                  <Link href="/sticky-notes" className="block">
                    <Button variant="outline" className="w-full justify-start retro-button">
                      <StickyNote className="w-4 h-4 mr-2" />
                      付箋メモを見る
                    </Button>
                  </Link>
                </CardContent>
              </Card>

              {/* Mini Calendar Preview */}
              <Card className="retro-paper">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">
                    {new Date().toLocaleDateString('ja-JP', { 
                      year: 'numeric', 
                      month: 'long' 
                    })}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-center">
                    <p className="text-4xl font-bold text-primary">
                      {new Date().getDate()}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {new Date().toLocaleDateString('ja-JP', { weekday: 'long' })}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t-2 border-border bg-card mt-auto">
        <div className="container py-4">
          <p className="text-center text-sm text-muted-foreground">
            秘書くん Modern - オリジナル「秘書くん2」へのオマージュ
          </p>
        </div>
      </footer>
    </div>
  );
}
