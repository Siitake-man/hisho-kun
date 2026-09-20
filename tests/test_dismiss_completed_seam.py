"""完了通知消去（dismissCompleted）の多重防壁・サーバー連携・フロントガード検証テスト (TDD)"""

import unittest
from pathlib import Path

from local_sync_server import AgentBridgeHub


class TestDismissCompletedSeam(unittest.TestCase):
    """完了通知を消去した際に、サーバー側およびフロント側で再表示が遮断されるかを検証"""

    def setUp(self):
        self.hub = AgentBridgeHub()

    def test_hub_dismiss_completed_clears_latest_completed(self):
        """set_completed_event 後に dismiss_completed を呼ぶと最新完了イベントが消去されること"""
        self.hub.set_completed_event("Antigravity", "テスト完了", "メッセージ")
        self.assertIsNotNone(self.hub.latest_completed)
        self.assertIsNotNone(self.hub.get_active_event())

        # 消去
        self.hub.dismiss_completed()
        self.assertIsNone(self.hub.latest_completed)
        self.assertIsNone(self.hub.get_active_event())

    def test_pet_ui_js_contains_server_dismiss_api_and_guards(self):
        """pet_ui.js にサーバーAPI呼び出し、isCompletedDismissed、および消去ガードが存在すること"""
        pet_ui_path = Path(__file__).resolve().parent.parent / "web_pet" / "pet_ui.js"
        self.assertTrue(pet_ui_path.exists(), "pet_ui.js が存在すること")
        content = pet_ui_path.read_text(encoding="utf-8")

        self.assertIn("/api/agent/dismiss_completed", content, "サーバーへの dismiss API 呼び出しが存在すること")
        self.assertIn("function isCompletedDismissed", content, "isCompletedDismissed 関数が定義されていること")
        self.assertIn("window.isCompletedDismissed = isCompletedDismissed", content, "windowへエクスポートされていること")
        self.assertIn("closeBottomSheet()", content, "モーダルボトムシート消去が連動していること")

    def test_pet_js_contains_dismissed_event_guard(self):
        """pet.js の active_event ハンドラに isCompletedDismissed ガードが存在すること"""
        pet_js_path = Path(__file__).resolve().parent.parent / "web_pet" / "pet.js"
        self.assertTrue(pet_js_path.exists(), "pet.js が存在すること")
        content = pet_js_path.read_text(encoding="utf-8")

        self.assertIn("isCompletedDismissed", content, "pet.js で isCompletedDismissed が参照されていること")
        self.assertIn("isDismissed", content, "active_event ハンドラに isDismissed 判定が存在すること")

    def test_pet_motion_celebrate_debounce_and_anti_flicker_css(self):
        """歓喜ジャンプの多重発火ガードおよびGPU合成レイヤー分離CSSが存在すること"""
        motion_path = Path(__file__).resolve().parent.parent / "web_pet" / "pet_motion.js"
        self.assertTrue(motion_path.exists())
        motion_content = motion_path.read_text(encoding="utf-8")
        self.assertIn("window._celebratingUntil && now < window._celebratingUntil", motion_content, "多重発火ガードが存在すること")

        html_path = Path(__file__).resolve().parent.parent / "web_pet" / "index.html"
        self.assertTrue(html_path.exists())
        html_content = html_path.read_text(encoding="utf-8")
        self.assertIn("translateZ(0)", html_content, "GPU合成レイヤー分離 translateZ(0) が存在すること")
        self.assertIn("backface-visibility: hidden", html_content, "チラつき防止 backface-visibility が存在すること")
        self.assertIn("isolation: isolate", html_content, "スタッキング隔離 isolation: isolate が存在すること")
        from version import __version__
        self.assertIn(f"pet_motion.js?v={__version__}", html_content, "キャッシュバスタークエリが付与されていること")

        particles_path = Path(__file__).resolve().parent.parent / "web_pet" / "pet_particles.js"
        self.assertTrue(particles_path.exists())
        particles_content = particles_path.read_text(encoding="utf-8")
        self.assertIn("bgCacheCanvas", particles_content, "ダブルバッファリング用オフスクリーンCanvasが存在すること")
        self.assertIn("drawImage(bgCacheCanvas", particles_content, "キャッシュ転送描画が実装されていること")


if __name__ == "__main__":
    unittest.main()
