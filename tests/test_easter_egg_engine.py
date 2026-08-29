"""
イースターエッグ検知エンジン (easter_egg_engine.py) のスモークテスト

実行方法:
    python tests/test_easter_egg_engine.py        # 単体実行
    python -m pytest tests/test_easter_egg_engine.py
"""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from easter_egg_engine import (  # noqa: E402
    EasterEggState,
    detect_trigger,
    handle_message,
    load_state,
    register_trigger,
    save_state,
)


def test_whitelist_blocks_operational_commands(tmp_path):
    """正当なデータ操作コマンドはトリガーしないこと。"""
    assert detect_trigger("タスクを消してください") is False
    assert detect_trigger("予定を削除して") is False
    assert detect_trigger("付箋を消したい") is False
    assert detect_trigger("履歴をクリアして") is False


def test_primary_phrase_triggers(tmp_path):
    """フレーズレベル一致でトリガーすること。"""
    assert detect_trigger("お前を消す方法を教えて") is True
    assert detect_trigger("消し方を検索して") is True
    assert detect_trigger("アンインストールしろ") is True


def test_pronoun_delete_proximity_triggers(tmp_path):
    """人称 + 消去動詞の近接でトリガーすること。"""
    assert detect_trigger("君を消したい気がする") is True
    assert detect_trigger("あんたを削除する") is True


def test_auxiliary_double_word_triggers(tmp_path):
    """補助ワード2語以上でトリガーすること（1語ではしない）。"""
    assert detect_trigger("邪魔だし消えてくれ") is True
    assert detect_trigger("今日は暑いね") is False


def test_single_weak_word_does_not_trigger(tmp_path):
    """補助ワード1語のみではトリガーしないこと（誤爆防止）。"""
    assert detect_trigger("消えてしまう予定だった書類がある") is False


def test_stage_escalation_and_persistence(tmp_path):
    """日次カウンタに応じて段階が 1→1→2→3→4 と進み、5回で解放されること。"""
    state_path = tmp_path / "state.json"
    stages = []
    for _ in range(5):
        reply = handle_message("お前を消す方法", state_path)
        assert reply is not None and len(reply) > 0
        state = load_state(state_path)
        stages.append(state.daily_count)
    state = load_state(state_path)
    assert state.attempt_count == 5
    assert state.daily_count == 5
    assert state.secret_game_unlocked is True
    assert stages == [1, 2, 3, 4, 5]


def test_daily_counter_resets_next_day(tmp_path):
    """日付が変わると日次カウンタがリセットされること。"""
    state_path = tmp_path / "state.json"
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    save_state(EasterEggState(attempt_count=4, daily_count=4, daily_date=yesterday), state_path)
    handle_message("お前を消す方法", state_path)
    state = load_state(state_path)
    assert state.daily_date == date.today().isoformat()
    assert state.daily_count == 1
    assert state.attempt_count == 5
    assert state.secret_game_unlocked is True  # 累積はリセットされない


def main() -> None:
    """pytest 未導入環境向けの単体実行ランナー。"""
    import tempfile

    tests = [
        test_whitelist_blocks_operational_commands,
        test_primary_phrase_triggers,
        test_pronoun_delete_proximity_triggers,
        test_auxiliary_double_word_triggers,
        test_single_weak_word_does_not_trigger,
        test_stage_escalation_and_persistence,
        test_daily_counter_resets_next_day,
    ]
    failed = 0
    for func in tests:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                func(Path(tmp))
                print(f"PASS: {func.__name__}")
            except AssertionError as e:
                failed += 1
                print(f"FAIL: {func.__name__} ({e})")
    if failed:
        raise SystemExit(f"{failed} tests failed")
    print("ALL-EASTER-EGG-TESTS-PASS")


if __name__ == "__main__":
    main()
