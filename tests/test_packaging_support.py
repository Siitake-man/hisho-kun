"""
配布パッケージング基盤の単体テスト (test_packaging_support.py)。

app_paths (frozen/開発のパス解決) と mcp_installer (MCP登録コマンド生成)、
neo_hisho.spec が参照する資産の実在を検証する。

バージョン非依存の構造テストのため、バージョン更新で壊れない。
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import app_paths  # noqa: E402
import mcp_installer  # noqa: E402


class TestAppPathsDevMode(unittest.TestCase):
    """開発環境 (non-frozen) におけるパス解決の検証。"""

    def test_is_frozen_returns_false_in_dev(self) -> None:
        """開発環境では is_frozen() が False を返す。"""
        self.assertFalse(app_paths.is_frozen())

    def test_app_root_equals_project_root_in_dev(self) -> None:
        """開発環境では書き込みルートがプロジェクトルートと一致する。"""
        self.assertEqual(app_paths.get_app_root(), PROJECT_ROOT)

    def test_resource_root_equals_project_root_in_dev(self) -> None:
        """開発環境ではリソースルートがプロジェクトルートと一致する。"""
        self.assertEqual(app_paths.get_resource_root(), PROJECT_ROOT)


class TestEnsureEnvFile(unittest.TestCase):
    """初回起動時の .env 自動生成ロジックの検証。"""

    def test_creates_env_from_example(self) -> None:
        """.env 不在時、.env.example から自動生成される。"""
        with tempfile.TemporaryDirectory() as tmp_a, \
                tempfile.TemporaryDirectory() as tmp_r:
            example = Path(tmp_r) / ".env.example"
            example.write_text("DEFAULT_LLM_PROVIDER=opencode\n", encoding="utf-8")
            with patch.object(app_paths, "get_app_root", return_value=Path(tmp_a)), \
                    patch.object(app_paths, "get_resource_root", return_value=Path(tmp_r)):
                env_path = app_paths.ensure_env_file()
                self.assertEqual(env_path, Path(tmp_a) / ".env")
                self.assertTrue(env_path.exists())
                self.assertIn("DEFAULT_LLM_PROVIDER", env_path.read_text(encoding="utf-8"))

    def test_existing_env_not_overwritten(self) -> None:
        """.env 既存時は上書きされない (ユーザーのAPIキー保護)。"""
        with tempfile.TemporaryDirectory() as tmp_a, \
                tempfile.TemporaryDirectory() as tmp_r:
            existing = Path(tmp_a) / ".env"
            existing.write_text("GOOGLE_API_KEY=USER_SECRET_KEY\n", encoding="utf-8")
            (Path(tmp_r) / ".env.example").write_text(
                "DEFAULT_LLM_PROVIDER=opencode\n", encoding="utf-8"
            )
            with patch.object(app_paths, "get_app_root", return_value=Path(tmp_a)), \
                    patch.object(app_paths, "get_resource_root", return_value=Path(tmp_r)):
                env_path = app_paths.ensure_env_file()
                self.assertIn(
                    "USER_SECRET_KEY", env_path.read_text(encoding="utf-8")
                )


class TestMcpInstallerConfig(unittest.TestCase):
    """MCP登録コマンド生成の検証 (frozen/開発の切替)。"""

    def test_dev_mode_registers_script(self) -> None:
        """開発環境では Python + hisho_mcp_server.py を登録する。"""
        config = mcp_installer.get_current_mcp_config()
        self.assertEqual(config["command"], Path(sys.executable).as_posix())
        self.assertEqual(len(config["args"]), 1)
        self.assertTrue(config["args"][0].endswith("hisho_mcp_server.py"))

    def test_frozen_mode_registers_mcp_serve_flag(self) -> None:
        """frozen環境では exe 自身 + --mcp-serve を登録する。"""
        with patch.object(sys, "frozen", True, create=True), \
                patch.object(sys, "executable", "C:/NeoHisho/NeoHisho.exe"):
            config = mcp_installer.get_current_mcp_config()
            self.assertEqual(config["command"], "C:/NeoHisho/NeoHisho.exe")
            self.assertEqual(config["args"], ["--mcp-serve"])


class TestSpecAssetsExist(unittest.TestCase):
    """neo_hisho.spec が同梱する資産の実在検証 (ビルド前ガード)。"""

    def test_bundled_directories_exist(self) -> None:
        """spec の datas が参照するディレクトリが存在する。"""
        for rel in ("web_pet", "assets", "docs/guides"):
            self.assertTrue(
                (PROJECT_ROOT / rel).is_dir(), f"同梱対象が存在しません: {rel}"
            )

    def test_env_example_exists(self) -> None:
        """.env.example (初回起動 .env 自動生成のソース) が存在する。"""
        self.assertTrue((PROJECT_ROOT / ".env.example").is_file())

    def test_mcp_server_entrypoint_exists(self) -> None:
        """--mcp-serve ディスパッチ先の hisho_mcp_server.py が存在する。"""
        self.assertTrue((PROJECT_ROOT / "hisho_mcp_server.py").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
