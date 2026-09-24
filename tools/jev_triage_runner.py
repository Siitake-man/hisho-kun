"""Jev System One テスト失敗トリアージ シャドーモード実行モジュール.

抽出されたシグナルをもとにトリアージ判定を行い、
シャドーモード中は自動修正を実行せずログ記録と確信度フォールバック判定を行う。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from tools.jev_triage_extractor import JevTriageExtractor

logger = logging.getLogger(__name__)


class JevTriageRunner:
    """Jevテスト失敗トリアージの実行およびシャドーログ記録クラス."""

    CONFIG_PATH = Path("config/jev_triage.json")

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """初期化処理.

        Args:
            config_path: 設定ファイルのパス（省略時は標準パス）
        """
        self.config_path = config_path or self.CONFIG_PATH
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """設定ファイルを読み込む."""
        if not self.config_path.exists():
            return {
                "mode": "shadow",
                "confidence_threshold": 0.95,
                "shadow_target_samples": 10,
                "current_sample_count": 0,
                "log_dir": "logs/jev_triage",
                "choices": [
                    "SYNTAX_OR_TYPO",
                    "SPEC_LOGIC_MISMATCH",
                    "ENVIRONMENT_OR_LOCK",
                    "CATASTROPHIC_REGRESSION",
                ],
            }
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("設定ファイルの読み込みに失敗しました。デフォルト値を使用します: %s", e)
            return {
                "mode": "shadow",
                "confidence_threshold": 0.95,
                "shadow_target_samples": 10,
                "current_sample_count": 0,
                "log_dir": "logs/jev_triage",
            }

    def _save_config(self) -> None:
        """設定ファイルを保存（サンプル数更新等）."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("設定ファイルの保存に失敗しました: %s", e)

    def evaluate_signals(self, signals: Dict[str, Any]) -> Dict[str, Any]:
        """シグナルを評価し、Jev判定 Choice と確信度スコアを算出する.

        ※ 本メソッドはJev System Oneの決定論的プロトタイプ評価ロジックを実装し、
           外部Jev MCP/API連携と完全互換の形式で判定を返す。

        Args:
            signals: JevTriageExtractor が抽出したシグナル辞書

        Returns:
            Dict[str, Any]: 判定結果辞書
                - choice (str): 判定カテゴリ
                - confidence (float): 確信度 (0.0 - 1.0)
                - rationale (str): 判定理由
                - escalate_to_llm (bool): LLMへのエスカレーション要否
        """
        exc = signals.get("exception_type", "")
        msg = signals.get("error_message", "")
        changed = signals.get("changed_files", [])

        threshold = float(self.config.get("confidence_threshold", 0.95))

        choice = "SPEC_LOGIC_MISMATCH"
        confidence = 0.85
        rationale = "一般的な仕様またはアサーションの不一致"

        # 1. タイポ・属性欠落・インポートエラー（高確信度判定）
        if exc in ("AttributeError", "NameError", "ImportError", "ModuleNotFoundError"):
            choice = "SYNTAX_OR_TYPO"
            # 直前に該当ファイルを編集していた場合は極めて高い確信度
            if any(f in signals.get("failed_location", "") for f in changed) or changed:
                confidence = 0.97
                rationale = f"{exc}: 直近の編集に伴うメソッド・属性の未定義またはインポート漏れの可能性が極めて高い"
            else:
                confidence = 0.91
                rationale = f"{exc}: 定義未存在だが直前変更との直接相関がやや薄い"

        # 2. 環境要因・DBロック・タイムアウト
        elif exc in ("TimeoutError", "OperationalError", "ConnectionRefusedError", "OSError"):
            choice = "ENVIRONMENT_OR_LOCK"
            confidence = 0.96 if "locked" in msg.lower() or "timeout" in msg.lower() else 0.88
            rationale = f"{exc}: プロセス排他ロック、ポート競合、外部接続タイムアウトの可能性"

        # 3. アサーション不一致
        elif exc == "AssertionError":
            choice = "SPEC_LOGIC_MISMATCH"
            confidence = 0.92
            rationale = "期待値と実際の返却値の不一致（ロジックまたはテスト前提の確認が必要）"

        # 4. デグレ判定（直前に全く触っていないファイルでの想定外エラー）
        if changed and not any(f in signals.get("failed_location", "") for f in changed):
            if exc not in ("AttributeError", "NameError"):
                choice = "CATASTROPHIC_REGRESSION"
                confidence = 0.89
                rationale = "直前変更対象外のテストが破損しており、巻き添えデグレの疑いあり"

        # 確信度が閾値未満の場合は安全側に倒してLLMへエスカレーション
        escalate_to_llm = confidence < threshold

        return {
            "choice": choice,
            "confidence": round(confidence, 3),
            "rationale": rationale,
            "escalate_to_llm": escalate_to_llm,
        }

    def record_shadow_sample(
        self,
        signals: Dict[str, Any],
        evaluation: Dict[str, Any],
    ) -> Dict[str, Any]:
        """シャドーモードのサンプルを記録し、進捗を更新する.

        Args:
            signals: 抽出されたシグナル
            evaluation: evaluate_signals の評価結果

        Returns:
            Dict[str, Any]: 記録されたサンプル情報
        """
        log_dir = Path(self.config.get("log_dir", "logs/jev_triage"))
        log_dir.mkdir(parents=True, exist_ok=True)

        current_count = int(self.config.get("current_sample_count", 0)) + 1
        self.config["current_sample_count"] = current_count
        target_count = int(self.config.get("shadow_target_samples", 10))

        record = {
            "sample_index": current_count,
            "target_samples": target_count,
            "timestamp": datetime.now().isoformat(),
            "signals": signals,
            "evaluation": evaluation,
            "is_shadow_mode": (self.config.get("mode") == "shadow"),
        }

        # ログファイル保存
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"shadow_sample_{current_count:02d}_{timestamp_str}.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

        self._save_config()
        return record

    def format_status_line(self, record: Dict[str, Any]) -> str:
        """作業ログ・チャット表示用の1行エビデンス文字列を整形する.

        Args:
            record: record_shadow_sample の返却辞書

        Returns:
            str: 整形された表示文字列
        """
        idx = record.get("sample_index", 0)
        target = record.get("target_samples", 10)
        eval_data = record.get("evaluation", {})
        choice = eval_data.get("choice", "UNKNOWN")
        conf = eval_data.get("confidence", 0.0) * 100
        escalate = "LLMエスカレーション" if eval_data.get("escalate_to_llm") else "判定有効（自動化候補）"

        signals = record.get("signals", {})
        exc = signals.get("exception_type", "")
        msg = signals.get("error_message", "")[:40]

        return (
            f"🧪 [Jev Shadow Triage ({idx}/{target})] "
            f"入力: {exc} ({msg}) | 判定: {choice} (確信度: {conf:.1f}%) | "
            f"措置: {escalate}"
        )
