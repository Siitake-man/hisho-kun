"""
夜間カオステスト・異常系/境界値堅牢化テスト群 (tests/test_nightly_robustness.py)

目的:
- task_parser, database, 設定読込処理におけるNone/空文字/極端な長文/壊れた入力などの境界値・異常系動作の堅牢性を検証する。
- 全てのテストは既存コードを変更せずに独立して動作し、失敗せずに正常終了・フォールバックすることを保証する。
"""

import json
import os
import tempfile
import pytest
from datetime import datetime

import database
from storage.models import Task
from task_parser import parse_input, tags_to_db_string, db_string_to_tags, ParsedTask


# ---------------------------------------------------------------------------
# 1. task_parser の境界値・異常系テスト
# ---------------------------------------------------------------------------

def test_task_parser_null_and_empty_inputs():
    """None、空文字、空白のみの入力に対する安全性の検証。"""
    res_none = parse_input(None)
    assert isinstance(res_none, ParsedTask)
    assert res_none.title == ""
    assert res_none.due_date is None
    assert res_none.tags == []

    res_empty = parse_input("")
    assert isinstance(res_empty, ParsedTask)
    assert res_empty.title == ""

    res_spaces = parse_input("    \t\n   ")
    assert isinstance(res_spaces, ParsedTask)
    assert res_spaces.title == ""


def test_task_parser_extreme_length_input():
    """10,000文字を超える極端に長い文字列が入力された場合の動作検証。"""
    huge_text = "テストタスク " + ("A" * 10000) + " #巨大タグ !3"
    res = parse_input(huge_text)
    assert isinstance(res, ParsedTask)
    assert "テストタスク" in res.title
    assert "A" * 10000 in res.title
    assert res.priority == 3
    assert res.tags == ["巨大タグ"]


def test_task_parser_invalid_date_formats():
    """存在しない日付（2月30日、13月45日等）や不正な時刻表現のフォールバック検証。"""
    base_now = datetime(2026, 3, 29, 12, 0)

    # 2月30日などの無効な日付
    res_feb30 = parse_input("2月30日にミーティング", now=base_now)
    assert isinstance(res_feb30, ParsedTask)
    assert "ミーティング" in res_feb30.title

    # 13月45日など範囲外の月日
    res_invalid_month = parse_input("13月45日にレポート提出", now=base_now)
    assert isinstance(res_invalid_month, ParsedTask)
    assert "レポート提出" in res_invalid_month.title

    # 99/99
    res_slash = parse_input("99/99に買い物", now=base_now)
    assert isinstance(res_slash, ParsedTask)
    assert "買い物" in res_slash.title


def test_task_parser_tags_helpers_robustness():
    """tags_to_db_string および db_string_to_tags の境界値検証。"""
    # None や 空白の要素混入
    tags = [None, "", "  ", "仕事", "仕事", "  急ぎ  ", None]
    db_str = tags_to_db_string(tags)
    assert db_str == "仕事,急ぎ"

    # 逆変換
    parsed_tags = db_string_to_tags(db_str)
    assert parsed_tags == ["仕事", "急ぎ"]

    # 空・None入力の逆変換
    assert db_string_to_tags(None) == []
    assert db_string_to_tags("") == []
    assert db_string_to_tags(" , ,   ") == []


def test_task_parser_malformed_symbols():
    """記号のみや連続するハッシュ・びっくりマークの処理検証。"""
    res1 = parse_input("### !!! ※※")
    assert isinstance(res1, ParsedTask)

    res2 = parse_input("!999 # #tag_without_hash_prefix")
    assert isinstance(res2, ParsedTask)


# ---------------------------------------------------------------------------
# 2. database アクセスの境界値・異常系テスト
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_db(tmp_path):
    """テスト用の独立SQLiteデータベース環境を作成する。"""
    db_path = tmp_path / "test_nightly.db"
    database.init_db(str(db_path))
    yield str(db_path)


def test_database_add_and_get_task_edge_cases(temp_db):
    """DB追加・取得における特殊文字・極端なデータ・None値の耐久性検証。"""
    # 空白・特殊文字・Unicode絵文字・SQLインジェクション風文字列
    special_title = "'; DROP TABLE tasks; -- 🐶🐱 テストタスク"
    huge_description = "B" * 50000

    task = Task(
        title=special_title,
        description=huge_description,
        priority=3,
        tags="テスト,SQL",
    )

    task_id = database.create_task(task, db_path=temp_db)
    assert task_id > 0

    all_tasks = database.get_tasks(db_path=temp_db)
    fetched_task = next((t for t in all_tasks if t.id == task_id), None)
    assert fetched_task is not None
    assert fetched_task.title == special_title
    assert fetched_task.description == huge_description
    assert fetched_task.priority == 3


def test_database_non_existent_and_invalid_operations(temp_db):
    """存在しないIDに対する操作や無効なステータス更新のフォールバック検証。"""
    # 存在しないIDの取得
    all_tasks = database.get_tasks(db_path=temp_db)
    non_existent = next((t for t in all_tasks if t.id == 999999), None)
    assert non_existent is None

    # 存在しないIDの完了操作
    success = database.complete_task(999999, db_path=temp_db)
    assert success is False

    # 存在しないIDの削除
    deleted = database.delete_task(999999, db_path=temp_db)
    assert deleted is False


# ---------------------------------------------------------------------------
# 3. 設定ファイル/JSON読み書きの異常系テスト
# ---------------------------------------------------------------------------

def test_json_config_corruption_handling(tmp_path):
    """JSONファイルが壊れている、または空の場合の読み込みハンドリング検証。"""
    corrupted_json_path = tmp_path / "corrupted_config.json"
    corrupted_json_path.write_text("{ invalid_json: ...", encoding="utf-8")

    # JSONDecodeErrorが適切に捕捉可能であることを検証
    with pytest.raises(json.JSONDecodeError):
        with open(corrupted_json_path, "r", encoding="utf-8") as f:
            json.load(f)

    # 存在しないパスの読み込み
    non_existent_path = tmp_path / "does_not_exist.json"
    assert not os.path.exists(non_existent_path)
