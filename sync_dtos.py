"""
ネオ秘書くん - スマホ同期APIレスポンスDTO (sync_dtos.py)

2026-09-01 コードレビュー P2①「Pydantic DTO完全移行」の第一段モジュール。
DB 生辞書 (Primitive Obsession) 由来のキー名ミス・型不一致による実行時エラーを、
スマホ同期 API のレスポンス境界で Pydantic 検証を適用することで構造的に防ぐ。

設計 (段階移行):
- 既知フィールドのみ厳格に型検証し、未知フィールドは extra=allow でそのまま
  透過する (PWA クライアント契約を壊さない)。
- 検証失敗時は例外を外へ漏らさず、元の辞書をそのまま返してエラーログを出力する。
  「まず繋がる体験」を最優先する縮退設計 (スマホ同期の可用性 > 契約の完全性)。
"""

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

logger = logging.getLogger(__name__)


class TaskItemDTO(BaseModel):
    """GET /api/status の tasks 配列要素 (tasks テーブル由来のサマリー)。"""

    model_config = ConfigDict(extra="allow")

    id: Optional[int] = None
    title: str = ""
    priority: Optional[int] = None
    due_date: Optional[int] = None


class EventItemDTO(BaseModel):
    """GET /api/status の events 配列要素 (開始時刻はISO整形文字列)。"""

    model_config = ConfigDict(extra="allow")

    id: Optional[int] = None
    title: str = ""
    start_time: str = ""
    description: Optional[str] = None
    source_color: str = ""
    source_name: str = ""


class PomodoroDTO(BaseModel):
    """GET /api/status の pomodoro オブジェクト。"""

    model_config = ConfigDict(extra="allow")

    active: bool = False
    is_break: bool = False
    remaining_seconds: int = 0
    total_seconds: int = 25 * 60
    mode_label: str = ""


class CharacterDTO(BaseModel):
    """GET /api/status の character オブジェクト (現在キャラ + 一覧は extra 透過)。"""

    model_config = ConfigDict(extra="allow")

    id: str = ""
    name: str = ""
    title: str = ""
    emoji: str = ""


class StatusResponse(BaseModel):
    """GET /api/status のレスポンス全体契約。

    未知フィールド (bond / habits / life_coach 等) は段階移行のため
    extra=allow で透過する。次段のマイクロタスクで順次型付けする。
    """

    model_config = ConfigDict(extra="allow")

    status: str = "ok"
    pet_state: str = "idle"
    message: str = ""
    character: Optional[CharacterDTO] = None
    pomodoro: Optional[PomodoroDTO] = None
    tasks: List[TaskItemDTO] = Field(default_factory=list)
    events: List[EventItemDTO] = Field(default_factory=list)
    server_time: Optional[int] = None


class TaskViewItemDTO(BaseModel):
    """POST /api/action get_tasks_view の tasks 配列要素 (拡充TODO・Plan C)。"""

    model_config = ConfigDict(extra="allow")

    id: Optional[int] = None
    title: str = ""
    priority: Optional[int] = None
    due_date: Optional[int] = None
    tags: str = ""
    list_id: Optional[int] = None
    importance_flag: Optional[bool] = None
    urgency_flag: Optional[bool] = None
    recurrence: Optional[str] = None


class TasksViewResponse(BaseModel):
    """POST /api/action get_tasks_view のレスポンス契約。"""

    model_config = ConfigDict(extra="allow")

    status: str = "success"
    tasks: List[TaskViewItemDTO] = Field(default_factory=list)


def validate_status_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """GET /api/status ペイロードを StatusResponse 契約で検証する。

    Args:
        payload: ハンドラが組み立てたレスポンス辞書。

    Returns:
        検証通過時は正規化済み辞書 (内容は入力と等価)。
        契約違反時は入力をそのまま返す (スマホ同期の可用性優先)。
    """
    try:
        return StatusResponse.model_validate(payload).model_dump()
    except ValidationError as e:
        logger.error("⚠️ [DTO] /api/status ペイロードが契約違反のため生辞書で応答します: %s", e)
        return payload


def validate_tasks_view_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    """get_tasks_view アクションのレスポンスを TasksViewResponse 契約で検証する。

    Args:
        payload: アクションハンドラが組み立てたレスポンス辞書。

    Returns:
        検証通過時は正規化済み辞書 (内容は入力と等価)。
        契約違反時は入力をそのまま返す (スマホ同期の可用性優先)。
    """
    try:
        return TasksViewResponse.model_validate(payload).model_dump()
    except ValidationError as e:
        logger.error("⚠️ [DTO] get_tasks_view レスポンスが契約違反のため生辞書で応答します: %s", e)
        return payload
