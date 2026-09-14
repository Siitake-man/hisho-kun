"""
Neo-Secretary ストレージ層 - Pydanticモデル定義 (storage/models.py)

カレンダー、タスク、習慣、知見（MentisDB）、端末台帳などのデータモデルを
Pydantic V2形式で型安全に定義します。
外部のデータベース接続に依存しない純粋なデータ構造（Value Object）です。
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, ValidationInfo, field_validator


# =============================================================================
# カレンダー・予定関連モデル
# =============================================================================

class Category(BaseModel):
    """
    カテゴリ情報を表すモデル。
    
    予定や付箋を分類するために使用します。アイコンと色で視覚的に区別できます。
    
    Attributes:
        id: カテゴリID（自動採番）
        name: カテゴリ名（例: "仕事", "プライベート"）
        color: カラーコード（例: "#A67B5B"）
        icon: アイコン名（例: "work", "home"）
    """
    id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=100)
    color: str = Field(..., pattern=r'^#[0-9A-Fa-f]{6}$')
    icon: str = Field(..., min_length=1, max_length=50)


class Event(BaseModel):
    """
    予定情報を表すモデル。
    
    カレンダーの予定を管理します。Manus仕様準拠のrecurrence_rule（JSON形式）で
    繰り返し予定に対応しています。
    
    Attributes:
        id: 予定ID（自動採番）
        title: 予定のタイトル
        description: 予定の詳細説明
        start_time: 開始時刻（Unix Timestamp ミリ秒）
        end_time: 終了時刻（Unix Timestamp ミリ秒）
        recurrence_type: 繰り返しタイプ（'none', 'daily', 'weekly', 'monthly_date'等）
        recurrence_rule: 繰り返しルールの詳細（JSON形式の辞書）
        category_id: カテゴリID（外部キー）
        google_event_id: Google Calendar同期用のイベントID
        source_id: カレンダー購読ソースID
    """
    id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = ""
    start_time: int = Field(..., gt=0)
    end_time: int = Field(..., gt=0)
    recurrence_type: str = Field(default='none')
    recurrence_rule: Optional[Dict[str, Any]] = None
    category_id: Optional[int] = None
    google_event_id: Optional[str] = None
    source_id: Optional[int] = None
    
    @field_validator('end_time')
    @classmethod
    def end_after_start(cls, v: int, info: ValidationInfo) -> int:
        """終了時刻が開始時刻より後であることを検証します (Pydantic V2 形式)。"""
        start_time = info.data.get('start_time')
        if start_time is not None and v <= start_time:
            raise ValueError('end_timeはstart_timeより後である必要があります')
        return v


class CalendarSource(BaseModel):
    """
    カレンダー購読ソース（iCal URL）を表すモデル。
    
    仕事用・プライベート等の複数のGoogleカレンダーを識別して同期するために使用します。
    
    Attributes:
        id: ソースID（自動採番）
        name: 表示名（例: '仕事用', 'プライベート'）
        color: 手帳表示用の識別色（Hex）
        url: 秘密 iCal アドレス（空なら未設定）
        enabled: 同期・表示のON/OFF
        last_sync: 最終同期時刻（表示用文字列）
    """
    id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=50)
    color: str = Field(default="#A67B5B", pattern=r'^#[0-9A-Fa-f]{6}$')
    url: str = Field(default="", max_length=2000)
    enabled: bool = True
    last_sync: str = "未同期"


# =============================================================================
# デスクトップ付箋モデル
# =============================================================================

class StickyNote(BaseModel):
    """
    付箋情報を表すモデル。
    
    デスクトップ上に配置される付箋メモを管理します。
    位置、サイズ、最小化状態を保持します。
    
    Attributes:
        id: 付箋ID（自動採番）
        content: 付箋の内容
        color: 付箋の色（Hexカラーコード）
        position_x: X座標（ピクセル）
        position_y: Y座標（ピクセル）
        width: 幅（ピクセル）
        height: 高さ（ピクセル）
        is_minimized: 最小化されているか
    """
    id: Optional[int] = None
    content: str = Field(default="", max_length=5000)
    color: str = Field(default="#FFEB3B", pattern=r'^#[0-9A-Fa-f]{6}$')
    position_x: int = Field(default=100, ge=0)
    position_y: int = Field(default=100, ge=0)
    width: int = Field(default=200, ge=100)
    height: int = Field(default=200, ge=100)
    is_minimized: bool = Field(default=False)


# =============================================================================
# MentisDB 長期知見記憶モデル
# =============================================================================

class UserInsight(BaseModel):
    """
    ユーザーに関する長期知見（MentisDB型エピソード・ルール記憶）を表すモデル。
    
    AIが会話の中でボスの制約、好み、生活習慣、プロジェクトルールを学習し蓄積します。
    
    Attributes:
        id: 知見ID（自動採番）
        category: カテゴリ ('Constraint': 制約, 'Preference': 好み, 'Habit': 習慣, 'Project': PJルール)
        content: 知見の本文（例: '平日夜は家族のケアサポートのため予定を入れない'）
        context_tags: 検索用カンマ区切りタグ（例: 'schedule, family, time'）
        importance: 重要度 (1〜5, 5が最重要)
        created_at: 作成時刻（Unix Timestamp ミリ秒）
        updated_at: 更新時刻（Unix Timestamp ミリ秒）
    """
    id: Optional[int] = None
    category: str = Field(..., pattern=r'^(Constraint|Preference|Habit|Project)$')
    content: str = Field(..., min_length=1, max_length=2000)
    context_tags: Optional[str] = Field(default="")
    importance: int = Field(default=3, ge=1, le=5)
    created_at: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    updated_at: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))


# =============================================================================
# タスク・TODOモデル (TickTick仕様準拠)
# =============================================================================

class Task(BaseModel):
    """
    TODOタスク情報を表すモデル（TickTick仕様準拠）。
    """
    id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = ""
    due_date: Optional[int] = None
    priority: int = Field(default=0, ge=0, le=3)
    status: str = Field(default="todo", pattern=r'^(todo|in_progress|completed)$')
    parent_id: Optional[int] = None
    list_id: Optional[int] = None
    tags: str = Field(default="", max_length=500)  # カンマ区切りタグ (例: "仕事,急ぎ")
    importance_flag: Optional[bool] = None  # 明示的重要度 (True=重要 / None=未指定→推定ルールへフォールバック)
    urgency_flag: Optional[bool] = None  # 明示的緊急度 (True=緊急 / None=未指定→推定ルールへフォールバック)
    recurrence: Optional[str] = Field(default=None, pattern=r'^(daily|weekly|monthly)$')  # 繰り返し種別 (None=単発)
    created_at: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    updated_at: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))


class TaskList(BaseModel):
    """
    タスクリスト (TickTick風のリスト分類) を表すモデル。

    parent_id により階層ツリー構造を表現する (フォルダ/サブリスト・Block 1.6-R)。
    parent_id=None は最上位 (ルート) リストを意味する。
    """
    id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=50)
    emoji: str = Field(default="📋")
    parent_id: Optional[int] = None
    sort_order: int = Field(default=0)
    created_at: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))


# =============================================================================
# 習慣トラッカーモデル
# =============================================================================

class Habit(BaseModel):
    """
    習慣トラッカー情報を表すモデル。
    """
    id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=100)
    emoji: str = Field(default="🌱")
    target_days_per_week: int = Field(default=7, ge=1, le=7)
    created_at: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))


class HabitLog(BaseModel):
    """
    習慣達成ログを表すモデル。
    """
    id: Optional[int] = None
    habit_id: int
    completed_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$') # YYYY-MM-DD
    created_at: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))


class HabitWithStatus(BaseModel):
    """
    習慣1件と当日の達成状態を表すモデル (get_habits_with_status 戻り値)。
    """
    id: Optional[int] = None
    title: str = ""
    emoji: Optional[str] = None
    target_days_per_week: int = 7
    completed_today: bool = False
    streak: int = 0
    total_completed: int = 0
    created_at: Optional[int] = None


class HabitHeatmapPoint(BaseModel):
    """
    習慣ヒートマップ1日分の集計を表すモデル (get_habit_heatmap_data 戻り値)。

    level: 0=なし, 1=薄緑, 2=緑, 3=濃緑, 4=金 (達成数に応じる)。
    day_of_week: 0=月 ... 6=日。
    """
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    count: int = 0
    level: int = 0
    day_of_week: int = 0


# =============================================================================
# ミニゲームスコアモデル
# =============================================================================

class MinigameScore(BaseModel):
    """
    ミニゲームのスコア記録を表すモデル。

    シークレットミニゲーム（Phase L5 Pixel Defense 等）のプレイ結果を
    SQLite へ永続化し、ハイスコアや履歴表示に利用します。

    Attributes:
        id: スコア記録ID（自動採番）
        game_id: ゲーム識別子（例: 'pixel_defense'）
        score: 達成スコア（0以上）
        created_at: 記録時刻（Unix Timestamp ミリ秒）
    """
    id: Optional[int] = None
    game_id: str = Field(..., min_length=1, max_length=50)
    score: int = Field(..., ge=0)
    created_at: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))


# =============================================================================
# ゼロトラスト端末台帳モデル
# =============================================================================

class Device(BaseModel):
    """
    登録済みクライアント端末（デバイス台帳）を表すモデル。
    
    ゼロトラスト原則に基づき、スマホPWAや外部連携端末の接続トークンハッシュ、
    端末名、IP、User-Agent、失効状態を追跡します。
    
    Attributes:
        id: デバイスID（自動採番）
        device_name: 端末表示名（例: "Boss iPhone 15 Pro"）
        token_hash: 認証トークンのSHA-256ハッシュ
        ip_address: 最終接続元IPアドレス
        user_agent: 最終接続元ブラウザ/クライアント識別子
        created_at: 登録時刻（Unix Timestamp ミリ秒）
        last_seen: 最終アクセス時刻（Unix Timestamp ミリ秒）
        is_revoked: 失効フラグ（0: 有効, 1: 失効）
    """
    id: Optional[int] = None
    device_name: str = Field(..., min_length=1, max_length=100)
    token_hash: str = Field(..., min_length=1)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    last_seen: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    is_revoked: int = 0
