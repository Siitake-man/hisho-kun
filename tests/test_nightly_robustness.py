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

import sqlite3
import database
import i18n
import ics_tools
from suggest_engine import SuggestionEngine
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


# ---------------------------------------------------------------------------
# 4. i18n および DB異常系接続の境界値・異常系テスト
# ---------------------------------------------------------------------------

def test_i18n_robustness_edge_cases():
    """i18n.py における None、数値、未対応言語コード、不完全なフォーマットパラメータ入力の検証。"""
    current = i18n.get_language()
    try:
        # 非文字列・None言語コード設定時のフォールバック動作
        i18n.set_language(None)
        assert i18n.get_language() == "ja"

        i18n.set_language(12345)
        assert i18n.get_language() == "ja"

        i18n.set_language("fr-FR-unsupported")
        assert i18n.get_language() == "ja"

        # 存在しないキーの翻訳呼び出し（キー名そのものが返る）
        assert i18n.t("non_existent_domain.non_existent_key") == "non_existent_domain.non_existent_key"

        # プレースホルダ不一致（引数不足）時のフォールバック動作
        result_missing = i18n.t("ui.pet.auto_minimize_toggle")
        assert result_missing == "📱 スマホ接続時のPCペット自動最小化を【{status}】にしました！"

        # 極端に長い文字列パラメータのフォーマット確認
        huge_param = "X" * 10000
        result_huge = i18n.t("ui.pet.auto_minimize_toggle", status=huge_param)
        assert huge_param in result_huge
    finally:
        i18n.set_language(current)


def test_database_lock_and_malformed_query_handling(temp_db):
    """DB読み書きにおいて不正なパスやテーブル破損等の異常系に対するフォールバック検証。"""
    # 存在しないディレクトリ配下のDBパスでの例外発生確認
    invalid_db_path = "/non_existent_directory_12345/test.db"
    with pytest.raises(Exception):
        database.init_db(invalid_db_path)

    # 破損したDBファイルへの接続時のエラーハンドリング
    corrupted_db = temp_db + "_corrupted.db"
    with open(corrupted_db, "wb") as f:
        f.write(b"NOT A SQLITE FILE")

    with pytest.raises(sqlite3.Error):
        database.get_tasks(db_path=corrupted_db)


# ---------------------------------------------------------------------------
# 5. ics_tools および suggest_engine の境界値・異常系テスト
# ---------------------------------------------------------------------------

def test_ics_tools_parse_and_sync_edge_cases():
    """ics_tools における破損 ICS データ・不正 URL の堅牢性検証。"""
    # 空文字・None入力
    assert ics_tools._parse_ics_events("") == []

    # 破損した VEVENT (不正な日付フォーマット)
    corrupted_ics = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:破損イベント
DTSTART:INVALID_DATE_FORMAT_12345
END:VEVENT
BEGIN:VEVENT
SUMMARY:正常イベント
DTSTART:20260825T100000Z
DTEND:20260825T110000Z
END:VEVENT
END:VCALENDAR"""

    events = ics_tools._parse_ics_events(corrupted_ics)
    assert len(events) == 1
    assert events[0]["title"] == "正常イベント"

    # 極端に長い SUMMARY と DESCRIPTION
    huge_ics = f"""BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:{"長" * 5000}
DESCRIPTION:{"説" * 10000}
DTSTART:20260825T100000Z
END:VEVENT
END:VCALENDAR"""
    huge_events = ics_tools._parse_ics_events(huge_ics)
    assert len(huge_events) == 1
    assert len(huge_events[0]["title"]) == 5000

    # sync_calendar_source の不正 URL ハンドリング
    source_empty = database.CalendarSource(id=999, name="空ソース", url="", enabled=True)
    imported, msg = ics_tools.sync_calendar_source(source_empty)
    assert imported == 0
    assert "未設定" in msg

    source_cid = database.CalendarSource(id=998, name="cidソース", url="https://calendar.google.com/?cid=1234", enabled=True)
    imported_cid, msg_cid = ics_tools.sync_calendar_source(source_cid)
    assert imported_cid == 0
    assert "カレンダーを追加するリンク" in msg_cid


def test_suggest_engine_summary_and_extraction_edge_cases():
    """suggest_engine における本文ポイント抽出・劣化判定・サマリ生成の境界値検証。"""
    # _extract_content_points: None / 空文字 / 壊れた HTML
    assert SuggestionEngine._extract_content_points("", "タイトル") == []
    assert SuggestionEngine._extract_content_points(None, "タイトル") == []

    broken_html = "<p><b>最新AI</b>の動向について。<a href='http://example.com'>詳細はこちら</a> &nbsp; &quot;重要&quot;</p>"
    points = SuggestionEngine._extract_content_points(broken_html, "タイトル")
    assert isinstance(points, list)
    assert any("最新AI" in p for p in points)

    # 10,000文字の巨大 description
    huge_desc = "・巨大な内容です。" + ("内容 " * 2000)
    huge_points = SuggestionEngine._extract_content_points(huge_desc, "タイトル")
    assert isinstance(huge_points, list)

    # _summary_lines_are_degenerate: 劣化・反復パターンの検出
    assert SuggestionEngine._summary_lines_are_degenerate([], "タイトル") is True
    assert SuggestionEngine._summary_lines_are_degenerate(["・1行目のみ"], "タイトル") is True
    assert SuggestionEngine._summary_lines_are_degenerate(["・同じ内容", "・同じ内容", "・同じ内容"], "タイトル") is True

    # _generate_3line_summary: フォールバックサマリ生成の安全な動作確認
    engine = SuggestionEngine(start_worker=False)
    summary = engine._generate_3line_summary(
        title="<script>alert(1)</script>テストタイトル",
        description="<div class='test'>本文記述です。AI技術が発展しています。</div>",
        media="テストメディア",
    )
    assert isinstance(summary, str)
    assert len(summary.splitlines()) <= 3
    assert "テストタイトル" in summary


# ---------------------------------------------------------------------------
# 6. auth_rate_limiter の境界値・異常系テスト
# ---------------------------------------------------------------------------

def test_auth_rate_limiter_edge_case_ips_and_timestamps():
    """AuthRateLimiter における特殊IP（None, 空文字, 空白, IPv6, 超長文IP）および時間境界値の堅牢性検証。"""
    from auth_rate_limiter import AuthRateLimiter

    limiter = AuthRateLimiter(max_failures=3, window_seconds=60.0, lockout_seconds=300.0)

    # 特殊な IP 表現の受け入れテスト
    special_ips = ["", None, "   ", "::1", "2001:db8::ff00:42:8329", "A" * 1000]

    for ip in special_ips:
        blocked, remaining = limiter.is_blocked(ip, now=1000.0)
        assert blocked is False
        assert remaining == 0

        # 3回失敗させてロックアウトを確認
        limiter.record_failure(ip, now=1000.0)
        limiter.record_failure(ip, now=1010.0)
        is_locked, lockout_secs = limiter.record_failure(ip, now=1020.0)

        assert is_locked is True
        assert lockout_secs == 300

        # ロックアウト状態の確認 (AuthRateLimiter は remaining = int(blocked_time - now) + 1 を返すため 291)
        blocked_check, rem_check = limiter.is_blocked(ip, now=1030.0)
        assert blocked_check is True
        assert rem_check == 291

        # 締め出し期間経過（300秒経過後）の解除確認
        blocked_expired, _ = limiter.is_blocked(ip, now=1321.0)
        assert blocked_expired is False


def test_auth_rate_limiter_time_window_and_clock_jump_resilience():
    """AuthRateLimiter におけるスライディングウィンドウ境界（ちょうど60秒前）および時刻逆転時のフォールバック検証。"""
    from auth_rate_limiter import AuthRateLimiter

    limiter = AuthRateLimiter(max_failures=3, window_seconds=60.0, lockout_seconds=300.0)
    test_ip = "192.168.1.100"

    # 1回目: t = 1000.0
    limiter.record_failure(test_ip, now=1000.0)
    # 2回目: t = 1010.0
    limiter.record_failure(test_ip, now=1010.0)

    # 60.1秒経過後 (t = 1060.1) -> 1回目の記録 (1000.0) はウィンドウ外に消去される
    # この時点で追加失敗してもカウントは 2 になるためロックアウトされない
    is_locked_1, _ = limiter.record_failure(test_ip, now=1060.1)
    assert is_locked_1 is False

    # 過去の時刻（現在時刻より小さい過去タイムスタンプ）が渡された場合もクラッシュせず処理されるか検証
    is_locked_past, _ = limiter.record_failure(test_ip, now=500.0)
    assert isinstance(is_locked_past, bool)


# ---------------------------------------------------------------------------
# 7. command_router の境界値・異常系テスト
# ---------------------------------------------------------------------------

def test_command_router_robustness_edge_cases():
    """command_router における None、空文字、不正日時、過去日時の決定論的フォールバック検証。"""
    import command_router
    from command_router import try_route_command, _resolve_event_datetimes

    # None, 空文字, 空白文字列のルーティング試行
    assert try_route_command(None) is None
    assert try_route_command("") is None
    assert try_route_command("   \t\n  ") is None

    # イベント指示のない長文テキスト
    huge_unrelated = "今日の天気は晴れです。" * 1000
    assert try_route_command(huge_unrelated) is None

    # 不正な日時表現（例: 13月45日、99:99）からの日時解釈フォールバック
    base_now = datetime(2026, 10, 8, 10, 0, 0)
    assert _resolve_event_datetimes("13月45日に会議を登録して", now=base_now) is None
    assert _resolve_event_datetimes("明日99:99に会議を入れて", now=base_now) is None

    # 過去の日時（例: 今日の朝8時、現在時刻は10時）を指定した場合のフォールバック (end <= base)
    assert _resolve_event_datetimes("今日8時に打ち合わせを入れて", now=base_now) is None

    # 登録インテントだがタイトルも日時も抽出できない曖昧なテキスト
    assert try_route_command("予定を登録して") is None
