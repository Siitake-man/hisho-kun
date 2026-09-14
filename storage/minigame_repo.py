"""
Neo-Secretary ストレージ層 - ミニゲームリポジトリ (storage/minigame_repo.py)

レトロミニゲームセンター (minigame_scores テーブル) の
スコア永続化、ハイスコア取得、履歴検索を提供します。
"""

import logging
from typing import List

from storage.connection import get_db_connection
from storage.models import MinigameScore

logger = logging.getLogger(__name__)


def record_minigame_score(game_id: str, score: int, db_path: str = "neo_secretary.db") -> int:
    """ミニゲームのスコアを1件記録します。

    Args:
        game_id: ゲーム識別子（例: 'pixel_defense'）
        score: 達成スコア（0以上の整数）
        db_path: データベースファイルのパス

    Returns:
        作成されたスコア記録のID

    Raises:
        ValueError: game_id が空または score が負の場合
    """
    normalized_game_id = (game_id or "").strip()
    if not normalized_game_id:
        raise ValueError("game_id は空文字であってはいけません")
    if score < 0:
        raise ValueError("score は0以上の整数である必要があります")

    record = MinigameScore(game_id=normalized_game_id, score=score)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO minigame_scores (game_id, score, created_at)
            VALUES (?, ?, ?)
        """, (record.game_id, record.score, record.created_at))
        record_id = cursor.lastrowid or 0
        logger.info(f"👾 ミニゲームスコアを記録: game_id={record.game_id}, score={record.score}, ID={record_id}")
        return record_id


def get_high_score(game_id: str, db_path: str = "neo_secretary.db") -> int:
    """指定ゲームのハイスコア（自己ベスト）を取得します。

    Args:
        game_id: ゲーム識別子（例: 'pixel_defense'）
        db_path: データベースファイルのパス

    Returns:
        ハイスコア（記録が1件もない場合は0）
    """
    normalized_game_id = (game_id or "").strip()
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MAX(score) FROM minigame_scores WHERE game_id = ?
        """, (normalized_game_id,))
        row = cursor.fetchone()
        return int(row[0]) if row and row[0] is not None else 0


def get_recent_minigame_scores(game_id: str, limit: int = 10, db_path: str = "neo_secretary.db") -> List[MinigameScore]:
    """指定ゲームの直近スコア履歴を新しい順に取得します。

    Args:
        game_id: ゲーム識別子（例: 'pixel_defense'）
        limit: 取得する最大件数（1以上）
        db_path: データベースファイルのパス

    Returns:
        スコア記録のリスト（新しい順）
    """
    normalized_game_id = (game_id or "").strip()
    if limit < 1:
        limit = 1
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, game_id, score, created_at
            FROM minigame_scores
            WHERE game_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        """, (normalized_game_id, limit))
        rows = cursor.fetchall()
        return [
            MinigameScore(
                id=r[0],
                game_id=r[1],
                score=r[2],
                created_at=r[3],
            )
            for r in rows
        ]
