"""
Neo-Secretary ストレージ層 - ユーザー知見リポジトリ (storage/insight_repo.py)

ユーザー知見（知識の宝庫: user_insights テーブル）の
永続化・取得・検索・削除を提供します。
"""

import logging
from typing import List, Optional

from storage.connection import get_db_connection
from storage.models import UserInsight

logger = logging.getLogger(__name__)


def create_user_insight(insight: UserInsight, db_path: str = "neo_secretary.db") -> int:
    """ユーザーに関する知見（制約・好み・習慣・PJルール）を追加します。
    ※蒸留蔵（distill-kura）思想の引用検証ゲート：AIの主観推測や曖昧表現を排除し、確定事実のみを永続化。

    Args:
        insight: 追加する知見オブジェクト
        db_path: データベースファイルのパス

    Returns:
        作成された知見のID（拒絶時は -1）
    """
    # 🛡️ 蒸留蔵思想のエビデンス検証ゲート (Distill Verification Gate)
    content_clean = (insight.content or "").strip()
    if not content_clean or len(content_clean) < 5:
        logger.warning(f"知見の保存を拒絶: 短すぎるか空のコンテンツです ({content_clean})")
        return -1

    # AIの主観・曖昧な当て推量を正規表現で遮断（波ダッシュ依存の解消）
    import re
    if re.search(r"(?:と考えられる|と思われる|かもしれない|AIの推測|推測される|たぶん|おそらく)", content_clean):
        logger.warning(f"知見の保存を拒絶（エビデンス検証違反）: AIの主観・推測が含まれています: {content_clean[:40]}...")
        return -1

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_insights (category, content, context_tags, importance, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            insight.category,
            insight.content,
            insight.context_tags or "",
            insight.importance,
            insight.created_at,
            insight.updated_at
        ))
        insight_id = cursor.lastrowid or 0
        logger.info(f"ユーザー知見を保存しました: ID={insight_id}, [{insight.category}] {insight.content[:30]}...")
        return insight_id


def add_user_insight(
    category: str,
    content: str,
    importance: int = 3,
    context_tags: str = "",
    db_path: str = "neo_secretary.db"
) -> int:
    """新しいユーザー知見を user_insights テーブルに登録します。
    ※ create_user_insight() を経由してエビデンス検証ゲートを一元適用。

    Args:
        category: 知見カテゴリ ('Constraint', 'Preference', 'Habit', 'Project')
        content: 知見の本文
        importance: 重要度 (1〜5, 5が最重要)
        context_tags: 検索用カンマ区切りタグ
        db_path: データベースファイルのパス

    Returns:
        作成された知見のID（検証失敗時は -1）
    """
    insight = UserInsight(
        category=category,
        content=content,
        context_tags=context_tags,
        importance=importance
    )
    return create_user_insight(insight, db_path=db_path)


def get_user_insights(
    category: Optional[str] = None,
    min_importance: int = 1,
    limit: int = 20,
    db_path: str = "neo_secretary.db"
) -> List[UserInsight]:
    """重要度順（降順）でユーザー知見を取得します。

    Args:
        category: 取得対象のカテゴリ（'Constraint', 'Preference', 'Habit', 'Project'）。Noneで全件。
        min_importance: 最小重要度（1〜5）
        limit: 最大取得件数
        db_path: データベースファイルのパス

    Returns:
        UserInsightオブジェクトのリスト
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        if category:
            cursor.execute("""
                SELECT id, category, content, context_tags, importance, created_at, updated_at
                FROM user_insights
                WHERE category = ? AND importance >= ?
                ORDER BY importance DESC, updated_at DESC
                LIMIT ?
            """, (category, min_importance, limit))
        else:
            cursor.execute("""
                SELECT id, category, content, context_tags, importance, created_at, updated_at
                FROM user_insights
                WHERE importance >= ?
                ORDER BY importance DESC, updated_at DESC
                LIMIT ?
            """, (min_importance, limit))

        rows = cursor.fetchall()
        insights = []
        for r in rows:
            insights.append(UserInsight(
                id=r[0],
                category=r[1],
                content=r[2],
                context_tags=r[3],
                importance=r[4],
                created_at=r[5],
                updated_at=r[6]
            ))
        return insights


def delete_user_insight(insight_id: int, db_path: str = "neo_secretary.db") -> bool:
    """知見をID指定で削除します。

    Args:
        insight_id: 削除する知見ID
        db_path: データベースファイルのパス

    Returns:
        削除成功時はTrue
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_insights WHERE id = ?", (insight_id,))
        success = cursor.rowcount > 0
        if success:
            logger.info(f"ユーザー知見を削除しました: ID={insight_id}")
        return success
