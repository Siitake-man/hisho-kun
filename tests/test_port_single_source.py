#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - ポート番号 単一情報源 (Single Source of Truth) の単体テスト
(tests/test_port_single_source.py)

タスク1 (2026-09-16 Cline): ハードコード解消 ＆ 衛生クリーンアップ。
ui/qr_dialog.py:396 の "http://localhost:8765/api/test_buzz" ベタ書きを廃止し、
同期サーバーの待受ポートを sync_config.SERVER_PORT から解決する。
local_sync_server / QRダイアログ / main の Tailscale 起動がすべて同一の
情報源を参照し、ポート変更時に一箇所修正で済む契約を凍結する。

TDD: sync_config モジュールと build_loopback_api_url が無い状態では Red。
"""

import ast
import inspect
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import main  # noqa: E402
import local_sync_server  # noqa: E402
import sync_config  # noqa: E402
from ui import qr_dialog  # noqa: E402


def _port_pattern(port: int = sync_config.DEFAULT_SERVER_PORT) -> "re.Pattern[str]":
    """ポート番号リテラル検出用の語境界つきパターンを返す（テスト内ヘルパー）。

    Args:
        port: 検出対象のポート番号（既定は既定ポート）。

    Returns:
        re.Pattern[str]: 直前/直後が数字・ピリオドでない場合のみ一致するパターン。
            `18765` や `202609168765` のような別の数値を誤検知しない。
    """
    return re.compile(rf"(?<![\d.]){re.escape(str(port))}(?![\d.])")


class TestPortSingleSource(unittest.TestCase):
    """ポート番号の重複定義が解消されていることの契約"""

    def test_sync_config_is_the_single_source(self) -> None:
        """sync_config.SERVER_PORT が正の整数として定義されていること"""
        self.assertIsInstance(sync_config.SERVER_PORT, int)
        self.assertGreater(sync_config.SERVER_PORT, 0)

    def test_local_sync_server_uses_sync_config(self) -> None:
        """同期サーバー本体が sync_config.SERVER_PORT を参照していること"""
        self.assertEqual(local_sync_server.SERVER_PORT, sync_config.SERVER_PORT)

    def test_qr_dialog_constants_derive_from_sync_config(self) -> None:
        """QRダイアログのポート定数・Serveコマンドが共通ポートから導出されること"""
        self.assertEqual(qr_dialog.TAILSCALE_HTTP_PORT, sync_config.SERVER_PORT)
        self.assertEqual(
            qr_dialog.TAILSCALE_SERVE_COMMAND,
            f"tailscale serve --bg {sync_config.SERVER_PORT}",
        )

    def test_build_loopback_api_url_uses_shared_port(self) -> None:
        """PC自身のAPI呼び出しURLが動的に生成されること (ベタ書き廃止)"""
        self.assertEqual(
            qr_dialog.build_loopback_api_url("/api/test_buzz"),
            f"http://localhost:{sync_config.SERVER_PORT}/api/test_buzz",
        )

    def test_build_loopback_api_url_normalizes_missing_slash(self) -> None:
        """先頭スラッシュ省略時も正しいURLへ正規化されること"""
        self.assertEqual(
            qr_dialog.build_loopback_api_url("api/test_buzz"),
            f"http://localhost:{sync_config.SERVER_PORT}/api/test_buzz",
        )

    def test_qr_dialog_has_no_hardcoded_port_literal(self) -> None:
        """ui/qr_dialog.py 内に既定ポート番号のベタ書きが残っていないこと"""
        source = (PROJECT_ROOT / "ui" / "qr_dialog.py").read_text(encoding="utf-8")
        self.assertNotIn(str(sync_config.DEFAULT_SERVER_PORT), source)

    def test_production_code_has_no_default_port_literal(self) -> None:
        """出荷コード（Python / PWA JS）に既定ポート番号のベタ書きが残っていないこと

        Notes:
            P1-2 (ruthless-code-evaluation 2026-09-16): ポートを変更した瞬間に
            設定画面のガイド・webhook URL・Agent Bridge CLI が 8765 を指し続けて
            連携が全滅する事故を、構造的に防ぐ。
            `sync_config.py`（既定値の定義元）とテストコードは対象外。
            判定は語境界つき正規表現（`18765` や `202609168765` を誤検知しない）。
            出荷対象の**ドキュメント**は別テスト（`TestShippedDocsPortGuidance`）が担当。
        """
        literal = str(sync_config.DEFAULT_SERVER_PORT)
        pattern = _port_pattern()
        targets = [
            *PROJECT_ROOT.glob("*.py"),
            *PROJECT_ROOT.glob("ui/*.py"),
            *PROJECT_ROOT.glob("storage/*.py"),
            *PROJECT_ROOT.glob("tools/*.py"),
            *PROJECT_ROOT.glob("web_pet/*.js"),
        ]

        offenders = []
        for path in sorted(targets):
            if path.name == "sync_config.py":
                continue
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    offenders.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}:{lineno}")

        self.assertEqual(
            offenders, [], f"既定ポート番号のベタ書きが残っています: {offenders}"
        )

    def test_main_tailscale_serve_uses_shared_port(self) -> None:
        """main の自動 Tailscale serve 起動がポート定数を参照していること"""
        source = inspect.getsource(main._auto_tailscale_serve)
        self.assertIn("SERVER_PORT", source)
        self.assertNotIn(f'"{sync_config.SERVER_PORT}"', source)


class TestPortEnvOverride(unittest.TestCase):
    """P1-4: 環境変数 NEO_HISHO_PORT によるポート競合回避の契約"""

    def test_valid_env_value_is_accepted(self) -> None:
        """妥当なポート値はそのまま採用されること"""
        self.assertEqual(sync_config.resolve_server_port("9123"), 9123)

    def test_missing_or_invalid_values_fall_back_to_default(self) -> None:
        """未設定/不正値はクラッシュせず既定ポートへ退避すること (起動優先)"""
        for value in (None, "", "   ", "abc", "0", "70000", "-1", "8765.5"):
            with self.subTest(value=value):
                self.assertEqual(
                    sync_config.resolve_server_port(value),
                    sync_config.DEFAULT_SERVER_PORT,
                )

    def test_default_port_is_documented_value(self) -> None:
        """既定ポートがドキュメント記載の 8765 であること"""
        self.assertEqual(sync_config.DEFAULT_SERVER_PORT, 8765)

    def test_env_override_is_applied_at_import_in_isolated_process(self) -> None:
        """環境変数オーバーライドが import 時に確定すること（サブプロセス隔離で検証）

        Notes:
            旧テストは `os.environ.pop` + `importlib.reload` を使い、他モジュールが
            import 時に束縛済みの値と不整合を起こして「コードは正しいのに FAIL する」
            偽陽性を生んでいた (P0-2)。検証は外部プロセスへ完全隔離する。
        """
        env = dict(os.environ, **{sync_config.PORT_ENV_KEY: "9876"})
        result = subprocess.run(
            [sys.executable, "-c", "import sync_config; print(sync_config.SERVER_PORT)"],
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "9876")

    def test_tests_do_not_mutate_process_environment(self) -> None:
        """本テストモジュールがグローバル状態を壊す呼び出し（reload / os.environ.pop）を持たないこと

        Notes:
            P0-2 の再発防止: import 時に値を束縛するモジュール（local_sync_server /
            qr_dialog / main）へ波及するため、構造的に禁止する（docstring の
            言及ではなく AST で実呼び出しだけを検査する）。
        """
        source = (PROJECT_ROOT / "tests" / "test_port_single_source.py").read_text(encoding="utf-8")
        forbidden = []
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "reload":
                forbidden.append("importlib.reload()")
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "pop"
                and isinstance(func.value, ast.Attribute)
                and func.value.attr == "environ"
            ):
                forbidden.append("os.environ.pop()")

        self.assertEqual(forbidden, [], f"グローバル状態を壊す呼び出しが残っています: {forbidden}")

    def test_port_seams_are_exposed_as_pure_functions(self) -> None:
        """ポート解決が純粋関数（resolve_server_port / read_port_from_env_file）で検証可能なこと"""
        self.assertTrue(callable(sync_config.resolve_server_port))
        self.assertTrue(callable(sync_config.read_port_from_env_file))


class TestEnvFileFallback(unittest.TestCase):
    """`.env` の NEO_HISHO_PORT も解決されること（案内と実装の一致）"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.env_path = Path(self._tmp.name) / ".env"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_reads_key_from_env_file(self) -> None:
        """`.env` に記載されたポートを読み取れること"""
        self.env_path.write_text(
            "OPENCODE_API_KEY=dummy\nNEO_HISHO_PORT=9010\n", encoding="utf-8"
        )

        self.assertEqual(sync_config.read_port_from_env_file(self.env_path), "9010")

    def test_ignores_comments_other_keys_and_strips_quotes(self) -> None:
        """コメント行・他キーを無視し、引用符を剥がすこと"""
        self.env_path.write_text(
            '# NEO_HISHO_PORT=1234\nGOOGLE_API_KEY="a=b"\nNEO_HISHO_PORT="9123"\n',
            encoding="utf-8",
        )

        self.assertEqual(sync_config.read_port_from_env_file(self.env_path), "9123")

    def test_missing_file_returns_none(self) -> None:
        """`.env` が無い場合は None（例外を漏らさない）"""
        self.assertIsNone(sync_config.read_port_from_env_file(self.env_path))

    def test_invalid_env_file_value_falls_back_to_default(self) -> None:
        """`.env` の不正値は既定ポートへ安全退避すること"""
        self.env_path.write_text("NEO_HISHO_PORT=not-a-port\n", encoding="utf-8")

        raw = sync_config.read_port_from_env_file(self.env_path)

        self.assertEqual(
            sync_config.resolve_server_port(raw), sync_config.DEFAULT_SERVER_PORT
        )

    def test_os_env_takes_precedence_over_env_file(self) -> None:
        """OS環境変数が `.env` より優先されること"""
        with mock.patch.dict(os.environ, {sync_config.PORT_ENV_KEY: ""}), \
                mock.patch.object(
                    sync_config, "read_port_from_env_file", return_value="9011"
                ):
            self.assertEqual(sync_config._read_env_port(), "9011")

        with mock.patch.dict(os.environ, {sync_config.PORT_ENV_KEY: "9012"}), \
                mock.patch.object(
                    sync_config, "read_port_from_env_file", return_value="9011"
                ):
            self.assertEqual(sync_config._read_env_port(), "9012")


class TestAgentBridgePortResolution(unittest.TestCase):
    """Agent Bridge CLI のポート解決契約 (P1-2)

    外部エージェント（Codex / Claude Code / Antigravity 等）から叩かれる CLI が
    `8765` をベタ書きしていると、ポート変更時に**連携が全滅**する。
    ポートは sync_config（唯一の情報源）から解決し、明示指定があればそれを優先する。
    """

    def test_explicit_port_wins(self) -> None:
        """明示指定されたポートはそのまま採用されること"""
        import agent_bridge_client

        self.assertEqual(agent_bridge_client.resolve_hub_port(9300), 9300)

    def test_missing_or_invalid_port_falls_back_to_sync_config(self) -> None:
        """未指定・不正値は sync_config.SERVER_PORT へ安全退避すること"""
        import agent_bridge_client

        for value in (None, 0, -1, "not-a-port", 70000):
            with self.subTest(value=value):
                self.assertEqual(
                    agent_bridge_client.resolve_hub_port(value), sync_config.SERVER_PORT
                )

    def test_cli_source_has_no_default_port_literal(self) -> None:
        """CLI 実装（docstring含む）に既定ポート番号のベタ書きが無いこと"""
        import agent_bridge_client

        source = inspect.getsource(agent_bridge_client)

        self.assertNotIn(str(sync_config.DEFAULT_SERVER_PORT), source)


class TestPortLiteralScanner(unittest.TestCase):
    """走査ロジック自体の契約（偽陽性・偽陰性の既知例を明示する）

    独立査読（2026-09-16）で「テスト緑＝漏れなし、ではない」と指摘されたため、
    検出できる形/できない形をテストで固定し、限界を可視化する。
    """

    def test_detects_direct_and_inline_literals(self) -> None:
        """直接代入・f-string・URL 文字列中のリテラルは検出できること"""
        pattern = _port_pattern()

        for payload in (
            "PORT = 8765",
            'url = f"http://localhost:8765/api/x"',
            '"tailscale serve 8765"',
            "text=\"http://<PCのIP>:8765/api/webhook\"",
        ):
            with self.subTest(payload=payload):
                self.assertIsNotNone(pattern.search(payload))

    def test_ignores_unrelated_numbers(self) -> None:
        """別の数値（上位桁・タイムスタンプ）を誤検知しないこと"""
        pattern = _port_pattern()

        for payload in ("PORT = 18765", "b = 202609168765", "v = 0.8765", "id = 87650"):
            with self.subTest(payload=payload):
                self.assertIsNone(pattern.search(payload))

    def test_documents_known_blind_spots(self) -> None:
        """既知の検出限界（難読化・演算生成・16進）を明示する

        Notes:
            これらは本走査では検出できない。コードレビューと独立査読で補う前提であり、
            「テストが緑だから安全」と誤解しないための記録である。
        """
        pattern = _port_pattern()

        for payload in ('P = "87" + "65"', "P = 0x22DD", "P = 8000 + 765"):
            with self.subTest(payload=payload):
                self.assertIsNone(pattern.search(payload))

    def test_scan_uses_current_default_port(self) -> None:
        """走査対象ポートは sync_config の既定値から導出されること（ベタ書き禁止）"""
        self.assertEqual(_port_pattern().pattern, _port_pattern(sync_config.DEFAULT_SERVER_PORT).pattern)
        self.assertIn(str(sync_config.DEFAULT_SERVER_PORT), _port_pattern().pattern)


class TestShippedDocsPortGuidance(unittest.TestCase):
    """出荷・利用者向けドキュメントのポート案内契約（P1-2 の残穴対策）

    exe には `docs/guides/` と `.env.example` が同梱される（`neo_hisho.spec` の datas）。
    既定ポート番号を記載する文書は、必ず「変更方法（`NEO_HISHO_PORT`）」も併記すること。
    """

    def _doc_targets(self) -> list:
        guides = PROJECT_ROOT / "docs" / "guides"
        return [
            *sorted(guides.glob("*.md")),
            *sorted(guides.glob("*.html")),
            PROJECT_ROOT / "README.md",
            PROJECT_ROOT / ".env.example",
        ]

    def test_docs_mentioning_default_port_also_document_override(self) -> None:
        """ポート記載がある文書は NEO_HISHO_PORT による変更方法も併記していること"""
        pattern = _port_pattern()
        offenders = []
        for path in self._doc_targets():
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            if pattern.search(text) and "NEO_HISHO_PORT" not in text:
                offenders.append(path.relative_to(PROJECT_ROOT).as_posix())

        self.assertEqual(
            offenders,
            [],
            f"ポート記載があるのに変更方法（NEO_HISHO_PORT）が無い出荷ドキュメント: {offenders}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
