"""web_pet 配下の更新と version.py バンプの機械検証および音声関連表記統一の規約テスト."""

import re
import subprocess
import unittest
from pathlib import Path

import version

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestWebPetVersionBumpAndVoiceNotation(unittest.TestCase):
    """web_pet のバージョン同期・バンプ義務および音声文字起こし表記統一の規約検証."""

    def test_version_py_matches_web_pet_version_js(self) -> None:
        """version.py の __version__ が web_pet/version.js と完全一致すること."""
        version_js = (PROJECT_ROOT / "web_pet" / "version.js").read_text(encoding="utf-8")
        current_ver = version.__version__

        self.assertIn(
            f'APP_VERSION = "{current_ver}"',
            version_js,
            f"web_pet/version.js の APP_VERSION が {current_ver} と一致しません",
        )
        self.assertIn(
            f'WEB_PET_CACHE_NAME = "neo-pet-v{current_ver}"',
            version_js,
            f"web_pet/version.js の WEB_PET_CACHE_NAME が neo-pet-v{current_ver} と一致しません",
        )

    def test_version_py_matches_index_html_query_params(self) -> None:
        """index.html の全スクリプト・スタイルシートタグの ?v= が version.py の __version__ と一致すること."""
        index_html = (PROJECT_ROOT / "web_pet" / "index.html").read_text(encoding="utf-8")
        current_ver = version.__version__

        matches = re.findall(r'(?:href|src)="[^"]+\?(?:v=([\d.]+))"', index_html)
        self.assertGreater(len(matches), 0, "index.html に ?v= クエリが付与されたタグが見つかりません")

        for v in matches:
            self.assertEqual(
                v,
                current_ver,
                f"index.html 内のクエリバージョン ({v}) が version.py ({current_ver}) と一致しません",
            )

    def test_web_pet_changes_require_version_bump(self) -> None:
        """web_pet 配下の JS/HTML/CSS が変更された場合、version.py も変更（バンプ）されていること."""
        try:
            res = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            changed_files = res.stdout.splitlines()
        except Exception as e:
            self.skipTest(f"git コマンドの実行に失敗したためスキップ: {e}")

        web_pet_changed = any(
            f.startswith("web_pet/") and f.endswith((".js", ".html", ".css"))
            for f in changed_files
        )
        if web_pet_changed:
            version_py_changed = "version.py" in changed_files
            self.assertTrue(
                version_py_changed,
                "web_pet/ 配下の JS/HTML/CSS が変更された場合は、version.py の __version__ をバンプしてください",
            )

    def test_unified_voice_notation_in_character_manager(self) -> None:
        """character_manager.py 内の音声関連表記が「内蔵の音声文字起こし機能」に統一されていること."""
        cm_src = (PROJECT_ROOT / "character_manager.py").read_text(encoding="utf-8")
        self.assertNotIn(
            "内蔵音声認識は",
            cm_src,
            "character_manager.py に旧表記「内蔵音声認識は」が残っています。「内蔵の音声文字起こし機能」へ統一してください",
        )
        self.assertIn(
            "内蔵の音声文字起こし機能",
            cm_src,
            "character_manager.py に統一表記「内蔵の音声文字起こし機能」が含まれていません",
        )


if __name__ == "__main__":
    unittest.main()
