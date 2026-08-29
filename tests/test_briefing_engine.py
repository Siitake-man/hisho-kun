"""
ネオ秘書くん - briefing_engine.py ユニットテスト (tests/test_briefing_engine.py)
"""

import unittest
from briefing_engine import (
    get_current_briefing_mode,
    generate_briefing,
    BriefingReport
)


class TestBriefingEngine(unittest.TestCase):
    """朝会/終礼ブリーフィングエンジンのテストケース"""

    def test_mode_determination(self):
        """時間帯ごとのモード判定テスト"""
        self.assertEqual(get_current_briefing_mode(5), "morning")
        self.assertEqual(get_current_briefing_mode(11), "morning")
        self.assertEqual(get_current_briefing_mode(12), "day")
        self.assertEqual(get_current_briefing_mode(17), "day")
        self.assertEqual(get_current_briefing_mode(18), "evening")
        self.assertEqual(get_current_briefing_mode(23), "evening")
        self.assertEqual(get_current_briefing_mode(0), "night")
        self.assertEqual(get_current_briefing_mode(4), "night")

    def test_morning_briefing_generation(self):
        """朝会ブリーフィングレポートの生成テスト"""
        report = generate_briefing(force_mode="morning")
        self.assertIsInstance(report, BriefingReport)
        self.assertEqual(report.mode, "morning")
        self.assertIn("朝会", report.mode_label)
        self.assertTrue(len(report.speech_text) > 10)
        self.assertTrue(len(report.formatted_markdown) > 20)
        self.assertIn("weather", report.weather_summary)
        
        # JSONシリアライズ可能かテスト
        d = report.to_dict()
        self.assertEqual(d["mode"], "morning")
        self.assertIsInstance(d["events_today"], list)
        self.assertIsInstance(d["active_tasks"], list)

    def test_evening_briefing_generation(self):
        """終礼日報ブリーフィングレポートの生成テスト"""
        report = generate_briefing(force_mode="evening")
        self.assertIsInstance(report, BriefingReport)
        self.assertEqual(report.mode, "evening")
        self.assertIn("終礼", report.mode_label)
        self.assertTrue(len(report.speech_text) > 10)
        self.assertTrue(len(report.formatted_markdown) > 20)
        
    def test_weather_location_setting(self):
        """地域の手動設定と天気取得テスト"""
        import weather_tools
        weather_tools.set_location("東京都渋谷区")
        self.assertEqual(weather_tools.get_current_location_setting(), "東京都渋谷区")
        
        # レポート生成がエラーなく動作するか
        report = generate_briefing()
        self.assertIsInstance(report, BriefingReport)
        
        # 解除テスト
        weather_tools.set_location("")
        self.assertEqual(weather_tools.get_current_location_setting(), "")


if __name__ == '__main__':
    unittest.main()
