"""
ネオ秘書くん - ミニゲームスコア永続化ユニットテスト (tests/test_minigame_score.py)

Phase L5「Pixel Defense」のスコア記録機能 (database.py minigame_scores層) の検証。
"""

import os
import tempfile
import unittest

import database


class TestMinigameScore(unittest.TestCase):
    """ミニゲームスコア記録・ハイスコア取得・履歴取得のテストケース"""

    def setUp(self):
        """テストごとに独立した一時DBを用意する"""
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        database.init_db(self.db_path)

    def tearDown(self):
        """一時DBファイルを後片付けする"""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_record_and_high_score(self):
        """スコア記録とハイスコア（自己ベスト）取得のテスト"""
        self.assertEqual(database.get_high_score("pixel_defense", self.db_path), 0)

        database.record_minigame_score("pixel_defense", 300, self.db_path)
        database.record_minigame_score("pixel_defense", 1200, self.db_path)
        database.record_minigame_score("pixel_defense", 700, self.db_path)

        self.assertEqual(database.get_high_score("pixel_defense", self.db_path), 1200)

    def test_high_score_isolated_by_game_id(self):
        """game_id が異なるスコアは互いに影響しないテスト"""
        database.record_minigame_score("pixel_defense", 500, self.db_path)
        database.record_minigame_score("other_game", 9999, self.db_path)

        self.assertEqual(database.get_high_score("pixel_defense", self.db_path), 500)
        self.assertEqual(database.get_high_score("other_game", self.db_path), 9999)

    def test_recent_scores_ordering_and_limit(self):
        """履歴が新しい順に件数上限付きで返るテスト"""
        for score in (100, 200, 300, 400, 500):
            database.record_minigame_score("pixel_defense", score, self.db_path)

        scores = database.get_recent_minigame_scores("pixel_defense", limit=3, db_path=self.db_path)
        self.assertEqual(len(scores), 3)
        self.assertEqual([s.score for s in scores], [500, 400, 300])

    def test_invalid_inputs_rejected(self):
        """不正入力（空game_id・負スコア）がValueErrorで拒否されるテスト"""
        with self.assertRaises(ValueError):
            database.record_minigame_score("", 100, self.db_path)
        with self.assertRaises(ValueError):
            database.record_minigame_score("   ", 100, self.db_path)
        with self.assertRaises(ValueError):
            database.record_minigame_score("pixel_defense", -1, self.db_path)


if __name__ == "__main__":
    unittest.main()
