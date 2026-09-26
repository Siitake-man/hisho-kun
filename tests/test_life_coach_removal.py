"""LifeCoachEngine 撤去 (ID 36) の検証テスト."""

import importlib
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestLifeCoachRemoval(unittest.TestCase):
    """LifeCoachEngine が完全に撤去され、LifeDreamer・TTSが正常残損していることを検証."""

    def test_life_coach_engine_file_and_module_removed(self) -> None:
        """life_coach_engine.py が削除され、モジュールとしてインポート不能であること."""
        file_path = PROJECT_ROOT / "life_coach_engine.py"
        self.assertFalse(file_path.exists(), "life_coach_engine.py がまだ存在しています")

        with self.assertRaises(ImportError):
            importlib.import_module("life_coach_engine")

    def test_main_py_does_not_import_life_coach(self) -> None:
        """main.py に life_coach_engine のインポートが残っていないこと."""
        main_src = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("life_coach_engine", main_src)

    def test_local_sync_server_does_not_import_life_coach(self) -> None:
        """local_sync_server.py に life_coach_engine のインポートが残っていないこと."""
        server_src = (PROJECT_ROOT / "local_sync_server.py").read_text(encoding="utf-8")
        self.assertNotIn("life_coach_engine", server_src)

    def test_i18n_does_not_contain_coach_keys(self) -> None:
        """i18n.py に coach.* 翻訳キーが残っていないこと."""
        i18n_src = (PROJECT_ROOT / "i18n.py").read_text(encoding="utf-8")
        self.assertNotIn('"coach.analysis_title"', i18n_src)

    def test_life_dreamer_and_tts_preserved(self) -> None:
        """LifeDreamer (life_dreamer.py) および PWA TTS (toggleBriefingSpeech) が削除されずに残存していること."""
        life_dreamer_file = PROJECT_ROOT / "life_dreamer.py"
        self.assertTrue(life_dreamer_file.exists(), "life_dreamer.py は削除してはいけません")

        # インポートテスト
        module = importlib.import_module("life_dreamer")
        self.assertTrue(hasattr(module, "LifeDreamerEngine") or hasattr(module, "get_life_dreamer_engine"))

        pet_js = (PROJECT_ROOT / "web_pet" / "pet.js").read_text(encoding="utf-8")
        self.assertIn("toggleBriefingSpeech", pet_js, "TTS機能 toggleBriefingSpeech は残す必要があります")


if __name__ == "__main__":
    unittest.main()
