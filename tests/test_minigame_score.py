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

    # ==========================================================================
    # レトロミニゲームセンター拡張 (全5種オムニバス) の検証
    # ==========================================================================

    ALL_GAME_IDS = ("pixel_defense", "itotooshi", "cyber_wire", "setsuna", "retro_breakout")

    def test_new_game_ids_record_and_high_score(self):
        """新規4ゲーム (itotooshi/cyber_wire/setsuna/retro_breakout) の記録とハイスコア取得"""
        new_ids = ("itotooshi", "cyber_wire", "setsuna", "retro_breakout")
        scores = {"itotooshi": 37, "cyber_wire": 850, "setsuna": 1450, "retro_breakout": 620}

        for game_id in new_ids:
            self.assertEqual(database.get_high_score(game_id, self.db_path), 0,
                             f"{game_id} の初期ハイスコアは 0 であること")
            database.record_minigame_score(game_id, 10, self.db_path)
            database.record_minigame_score(game_id, scores[game_id], self.db_path)
            database.record_minigame_score(game_id, 20, self.db_path)
            self.assertEqual(database.get_high_score(game_id, self.db_path), scores[game_id],
                             f"{game_id} の最高スコアが取得できること")

    def test_all_five_games_fully_isolated(self):
        """全5ゲームのスコアが互いに完全に独立すること (混線なし)"""
        base_scores = {"pixel_defense": 1200, "itotooshi": 37, "cyber_wire": 850,
                       "setsuna": 1450, "retro_breakout": 620}

        for game_id, score in base_scores.items():
            database.record_minigame_score(game_id, score, self.db_path)

        for game_id, score in base_scores.items():
            self.assertEqual(database.get_high_score(game_id, self.db_path), score,
                             f"{game_id} のハイスコアが他ゲームの影響を受けていないこと")

    def test_new_game_ids_share_validation_rules(self):
        """新ゲームIDでも既存と同一の入力バリデーションが適用されること"""
        for game_id in self.ALL_GAME_IDS:
            with self.assertRaises(ValueError, msg="空白のみのgame_idを拒否すること"):
                database.record_minigame_score("  ", 10, self.db_path)
            with self.assertRaises(ValueError, msg=f"{game_id} で負スコアを拒否すること"):
                database.record_minigame_score(game_id, -5, self.db_path)


ARCADE_GAME_IDS = (
    "pixel_defense",
    "itotooshi",
    "cyber_wire",
    "setsuna",
    "retro_breakout",
)


class TestArcadeOmnibusScores(unittest.TestCase):
    """レトロミニゲームセンター拡張 (全5種オムニバス) のスコア永続化テスト"""

    def setUp(self):
        """テストごとに独立した一時DBを用意する"""
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        database.init_db(self.db_path)

    def tearDown(self):
        """一時DBファイルを後片付けする"""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_all_five_games_record_independently(self):
        """全5ゲームが同一DB上で互いに混線せずハイスコアを保持するテスト"""
        expected = {
            "pixel_defense": 1200,
            "itotooshi": 42,
            "cyber_wire": 860,
            "setsuna": 950,
            "retro_breakout": 740,
        }
        for game_id, score in expected.items():
            database.record_minigame_score(game_id, score, self.db_path)
            # 自分より低いスコアは記録されるがHIを更新しない
            database.record_minigame_score(game_id, score - 1, self.db_path)

        for game_id, score in expected.items():
            self.assertEqual(
                database.get_high_score(game_id, self.db_path),
                score,
                f"{game_id} のハイスコアが他ゲームと混線しています",
            )

    def test_new_game_records_do_not_leak_into_pixel_defense(self):
        """新ゲームの記録が pixel_defense のHIに混入しないテスト (混線回帰防止)"""
        database.record_minigame_score("pixel_defense", 500, self.db_path)
        database.record_minigame_score("itotooshi", 9999, self.db_path)
        database.record_minigame_score("cyber_wire", 9999, self.db_path)
        database.record_minigame_score("setsuna", 9999, self.db_path)
        database.record_minigame_score("retro_breakout", 9999, self.db_path)

        self.assertEqual(database.get_high_score("pixel_defense", self.db_path), 500)

    def test_high_score_update_takes_max(self):
        """2回目の記録がHIを超える場合のみ更新されるテスト"""
        database.record_minigame_score("itotooshi", 30, self.db_path)
        database.record_minigame_score("itotooshi", 55, self.db_path)
        database.record_minigame_score("itotooshi", 20, self.db_path)
        self.assertEqual(database.get_high_score("itotooshi", self.db_path), 55)

    def test_all_game_ids_accept_zero_score(self):
        """全ゲームIDが0点記録を受理するテスト (初期状態の送信)"""
        for game_id in ARCADE_GAME_IDS:
            database.record_minigame_score(game_id, 0, self.db_path)
            self.assertEqual(database.get_high_score(game_id, self.db_path), 0)


if __name__ == "__main__":
    unittest.main()
