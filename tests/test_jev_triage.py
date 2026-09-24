"""Jev テスト失敗トリアージ機能の単体テスト."""

import json
from pathlib import Path
import pytest

from tools.jev_triage_extractor import JevTriageExtractor
from tools.jev_triage_runner import JevTriageRunner


DUMMY_PYTEST_ATTRIBUTE_ERROR = """
============================= test session starts =============================
collecting ... collected 1 item

tests/test_dummy.py::test_pet_attribute FAILED                           [100%]

================================== FAILURES ===================================
_____________________________ test_pet_attribute ______________________________

    def test_pet_attribute():
>       pet = DummyPet()
>       pet.non_existing_method()
E       AttributeError: 'DummyPet' object has no attribute 'non_existing_method'

tests/test_dummy.py:6: AttributeError
=========================== 1 failed in 0.05s ============================
"""

DUMMY_PYTEST_ASSERTION_ERROR = """
============================= test session starts =============================
collecting ... collected 1 item

tests/test_logic.py::test_calc FAILED                                    [100%]

================================== FAILURES ===================================
__________________________________ test_calc __________________________________

    def test_calc():
>       assert calculate_total(10) == 100
E       assert 50 == 100

tests/test_logic.py:12: AssertionError
=========================== 1 failed in 0.03s ============================
"""

DUMMY_PYTEST_LOCK_ERROR = """
============================= test session starts =============================
tests/test_db.py::test_concurrent_write FAILED                           [100%]

================================== FAILURES ===================================
____________________________ test_concurrent_write ____________________________

    def test_concurrent_write():
>       db.execute("INSERT INTO users VALUES (1)")
E       sqlite3.OperationalError: database is locked

tests/test_db.py:25: OperationalError
=========================== 1 failed in 0.10s ============================
"""


def test_extractor_attribute_error():
    """AttributeErrorのログから4大シグナルが正しく抽出されること."""
    signals = JevTriageExtractor.extract_signals(
        raw_log=DUMMY_PYTEST_ATTRIBUTE_ERROR,
        changed_files=["tests/test_dummy.py"],
    )
    assert signals["exception_type"] == "AttributeError"
    assert "no attribute 'non_existing_method'" in signals["error_message"]
    assert "tests/test_dummy.py::test_pet_attribute" in signals["failed_location"]
    assert signals["is_assertion_failure"] is False


def test_extractor_assertion_error():
    """AssertionErrorのログからシグナルが正しく抽出されること."""
    signals = JevTriageExtractor.extract_signals(
        raw_log=DUMMY_PYTEST_ASSERTION_ERROR,
        changed_files=["tests/test_logic.py"],
    )
    assert signals["exception_type"] == "AssertionError"
    assert "assert 50 == 100" in signals["error_message"]
    assert "tests/test_logic.py::test_calc" in signals["failed_location"]
    assert signals["is_assertion_failure"] is True


def test_extractor_lock_error():
    """DBロックエラーのログからシグナルが正しく抽出されること."""
    signals = JevTriageExtractor.extract_signals(
        raw_log=DUMMY_PYTEST_LOCK_ERROR,
    )
    assert signals["exception_type"] == "OperationalError"
    assert "database is locked" in signals["error_message"]


def test_runner_evaluation_and_fallback(tmp_path: Path):
    """評価ロジックと閾値によるフォールバック動作のテスト."""
    config_file = tmp_path / "jev_triage.json"
    config_data = {
        "mode": "shadow",
        "confidence_threshold": 0.95,
        "shadow_target_samples": 10,
        "current_sample_count": 0,
        "log_dir": str(tmp_path / "logs"),
    }
    config_file.write_text(json.dumps(config_data), encoding="utf-8")

    runner = JevTriageRunner(config_path=config_file)

    # 1. 高確信度のタイポ/属性エラー -> 確信度 >= 0.95, escalate_to_llm is False
    signals_typo = {
        "exception_type": "AttributeError",
        "error_message": "'Dummy' object has no attribute 'foo'",
        "failed_location": "tests/test_dummy.py::test_foo",
        "changed_files": ["tests/test_dummy.py"],
    }
    eval_typo = runner.evaluate_signals(signals_typo)
    assert eval_typo["choice"] == "SYNTAX_OR_TYPO"
    assert eval_typo["confidence"] >= 0.95
    assert eval_typo["escalate_to_llm"] is False

    # 2. ロジック不一致（AssertionError） -> 確信度 < 0.95, escalate_to_llm is True (安全側へフォールバック)
    signals_logic = {
        "exception_type": "AssertionError",
        "error_message": "assert 50 == 100",
        "failed_location": "tests/test_logic.py::test_calc",
        "changed_files": ["tests/test_logic.py"],
    }
    eval_logic = runner.evaluate_signals(signals_logic)
    assert eval_logic["choice"] == "SPEC_LOGIC_MISMATCH"
    assert eval_logic["confidence"] < 0.95
    assert eval_logic["escalate_to_llm"] is True


def test_runner_record_shadow_sample(tmp_path: Path):
    """シャドーモード時のサンプル記録とログ保存のテスト."""
    config_file = tmp_path / "jev_triage.json"
    log_dir = tmp_path / "logs"
    config_data = {
        "mode": "shadow",
        "confidence_threshold": 0.95,
        "shadow_target_samples": 10,
        "current_sample_count": 2,
        "log_dir": str(log_dir),
    }
    config_file.write_text(json.dumps(config_data), encoding="utf-8")

    runner = JevTriageRunner(config_path=config_file)

    signals = {
        "exception_type": "AttributeError",
        "error_message": "test message",
        "failed_location": "tests/test_dummy.py::test_1",
    }
    evaluation = {
        "choice": "SYNTAX_OR_TYPO",
        "confidence": 0.97,
        "escalate_to_llm": False,
    }

    record = runner.record_shadow_sample(signals, evaluation)
    assert record["sample_index"] == 3
    assert record["target_samples"] == 10
    assert record["is_shadow_mode"] is True

    # ログファイルが作成されたか確認
    log_files = list(log_dir.glob("shadow_sample_03_*.json"))
    assert len(log_files) == 1

    # ステータス行の生成確認
    status_line = runner.format_status_line(record)
    assert "🧪 [Jev Shadow Triage (3/10)]" in status_line
    assert "SYNTAX_OR_TYPO" in status_line


def test_extractor_summary_format():
    """pytestのサマリ形式ログ（FAILEDが先頭にあるケース）からも正しく抽出できること."""
    summary_log = """
================================ short test summary info =================================
FAILED tests/test_network.py::test_client - ConnectionRefusedError: [Errno 111] Connection refused
=================================== 1 failed in 0.12s ====================================
"""
    signals = JevTriageExtractor.extract_signals(raw_log=summary_log)
    assert signals["exception_type"] == "ConnectionRefusedError"
    assert "Connection refused" in signals["error_message"]
    assert signals["failed_location"] == "tests/test_network.py::test_client"
    assert signals["is_assertion_failure"] is False


def test_runner_catastrophic_regression(tmp_path: Path):
    """変更対象外テストの破損時にCATASTROPHIC_REGRESSIONと判定されること."""
    runner = JevTriageRunner()
    signals = {
        "exception_type": "KeyError",
        "error_message": "'user_id'",
        "failed_location": "tests/test_unrelated.py::test_other",
        "changed_files": ["tools/jev_triage_runner.py"],  # 失敗テストとは無関係のファイルのみ変更
    }
    evaluation = runner.evaluate_signals(signals)
    assert evaluation["choice"] == "CATASTROPHIC_REGRESSION"
    assert evaluation["escalate_to_llm"] is True  # 確信度 0.89 < 0.95 のためフォールバック


def test_runner_unhandled_error_escalates_to_llm():
    """未知のエラータイプの場合、安全側に倒してLLMへエスカレーションされること."""
    runner = JevTriageRunner()
    signals = {
        "exception_type": "ValueError",
        "error_message": "invalid literal for int() with base 10: 'abc'",
        "failed_location": "tests/test_parse.py::test_int",
        "changed_files": ["tests/test_parse.py"],
    }
    evaluation = runner.evaluate_signals(signals)
    assert evaluation["choice"] == "SPEC_LOGIC_MISMATCH"
    assert evaluation["confidence"] == 0.85
    assert evaluation["escalate_to_llm"] is True
