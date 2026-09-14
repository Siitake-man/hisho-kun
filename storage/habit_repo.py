"""
Neo-Secretary ストレージ層 - 習慣トラッカーリポジトリ (storage/habit_repo.py)

習慣 (habits テーブル) および達成ログ (habit_logs テーブル) の
CRUD操作、ストリーク（連続日数）計算、および草生やしヒートマップ集計を提供します。
"""

import logging
from datetime import datetime, timedelta, date
from typing import List, Optional

from storage.connection import get_db_connection
from storage.models import Habit, HabitWithStatus, HabitHeatmapPoint

logger = logging.getLogger(__name__)


def create_habit(habit: Habit, db_path: str = "neo_secretary.db") -> int:
    """新規習慣を登録"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO habits (title, emoji, target_days_per_week, created_at)
            VALUES (?, ?, ?, ?)
        """, (habit.title, habit.emoji, habit.target_days_per_week, habit.created_at))
        habit_id = cursor.lastrowid or 0
        logger.info(f"習慣を作成しました: ID={habit_id}, title={habit.title}")
        return habit_id


def delete_habit(habit_id: int, db_path: str = "neo_secretary.db") -> bool:
    """習慣および関連ログを削除"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM habit_logs WHERE habit_id = ?", (habit_id,))
        cursor.execute("DELETE FROM habits WHERE id = ?", (habit_id,))
        return cursor.rowcount > 0


def toggle_habit_log(habit_id: int, target_date: Optional[str] = None, db_path: str = "neo_secretary.db") -> bool:
    """指定日（デフォルト: 今日 YYYY-MM-DD）の習慣達成をトグル（ON/OFF）。
    達成された場合は True、解除された場合は False を返却。
    """
    if not target_date:
        target_date = datetime.now().strftime("%Y-%m-%d")

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM habit_logs WHERE habit_id = ? AND completed_date = ?", (habit_id, target_date))
        row = cursor.fetchone()

        if row:
            # 既に達成済み ➔ 解除
            cursor.execute("DELETE FROM habit_logs WHERE id = ?", (row[0],))
            logger.info(f"習慣達成を解除: Habit={habit_id}, Date={target_date}")
            return False
        else:
            # 未達成 ➔ 達成マーク
            now_ms = int(datetime.now().timestamp() * 1000)
            cursor.execute("""
                INSERT INTO habit_logs (habit_id, completed_date, created_at)
                VALUES (?, ?, ?)
            """, (habit_id, target_date, now_ms))
            logger.info(f"習慣達成を記録: Habit={habit_id}, Date={target_date}")
            return True


def get_habits_with_status(db_path: str = "neo_secretary.db") -> List[HabitWithStatus]:
    """全習慣リストを取得し、今日の達成状態（completed_today）、現在の連続日数（streak）、
    および過去7日間の達成履歴を付与して返却。
    """
    today_str = datetime.now().strftime("%Y-%m-%d")

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, emoji, target_days_per_week, created_at FROM habits ORDER BY id ASC")
        rows = cursor.fetchall()

        results = []
        for r in rows:
            h_id, title, emoji, target_days, created_at = r

            # 今日の達成
            cursor.execute("SELECT 1 FROM habit_logs WHERE habit_id = ? AND completed_date = ?", (h_id, today_str))
            completed_today = cursor.fetchone() is not None

            # 全達成日を取得してストリーク計算
            cursor.execute("SELECT completed_date FROM habit_logs WHERE habit_id = ? ORDER BY completed_date DESC", (h_id,))
            dates = [row[0] for row in cursor.fetchall()]

            # 連続日数 (Streak) 計算
            streak = 0
            check_date = datetime.now().date()
            if not completed_today:
                # 今日まだやってない場合は昨日から数える
                check_date = check_date - timedelta(days=1)

            date_set = set(dates)
            while check_date.strftime("%Y-%m-%d") in date_set:
                streak += 1
                check_date = check_date - timedelta(days=1)

            results.append(HabitWithStatus(
                id=h_id,
                title=title,
                emoji=emoji,
                target_days_per_week=target_days,
                completed_today=completed_today,
                streak=streak,
                total_completed=len(dates),
                created_at=created_at,
            ))

        return results


def get_habit_heatmap_data(days: int = 90, db_path: str = "neo_secretary.db") -> List[HabitHeatmapPoint]:
    """過去N日間のGitHub草風ヒートマップ集計データを返却。

    Returns:
        List[HabitHeatmapPoint]: 各日の日付(date)、達成数(count)、レベル0〜4(level)
    """
    today = date.today()
    start_date = today - timedelta(days=days - 1)

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT completed_date, COUNT(*) 
            FROM habit_logs 
            WHERE completed_date >= ?
            GROUP BY completed_date
        """, (start_date.strftime("%Y-%m-%d"),))

        counts = {r[0]: r[1] for r in cursor.fetchall()}

    heatmap = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        cnt = counts.get(d_str, 0)

        # 達成数に応じたレベル判定 (0〜4)
        if cnt == 0:
            lvl = 0
        elif cnt == 1:
            lvl = 1
        elif cnt == 2:
            lvl = 2
        elif 3 <= cnt < 5:
            lvl = 3
        else:
            lvl = 4

        heatmap.append(HabitHeatmapPoint(
            date=d_str,
            count=cnt,
            level=lvl,
            day_of_week=d.weekday(),  # 0=月, 6=日
        ))

    return heatmap
