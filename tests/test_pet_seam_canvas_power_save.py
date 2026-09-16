#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - Canvas適応型描画ループ省電力化 (P1-1) の整合性テスト (tests/test_pet_seam_canvas_power_save.py)

Page Visibility API (document.hidden) に連動したCanvasアニメーションループの完全停止（0fps）、
多重ループ防止フラグ (isParticleLoopRunning)、およびイベント発生時の
Wake-on-Demand (wakeParticleLoop) 連携ロジックを検証する。

検証項目:
  1. web_pet/pet_particles.js に wakeParticleLoop が定義・公開されていること
  2. isParticleLoopRunning フラグによる requestAnimationFrame 多重起動防止が配備されていること
  3. particleLoop 内で document.hidden を判定し、非表示時は次フレームを要求せず停止すること
  4. visibilitychange イベントリスナーで画面復帰時 (!document.hidden) に wakeParticleLoop が呼ばれること
  5. パーティクル生成系（spawnTouchParticle, spawnCelebrationConfetti）で wakeParticleLoop が呼ばれること
"""

import re
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestPetSeamCanvasPowerSave(unittest.TestCase):
    """Canvas描画ループの適応型省電力化およびWake-on-Demandの整合性を検証する"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.particles_js_path = PROJECT_ROOT / "web_pet" / "pet_particles.js"
        cls.assertTrue(cls.particles_js_path.is_file(), "web_pet/pet_particles.js が存在しません")
        cls.content = cls.particles_js_path.read_text(encoding="utf-8")

    def test_01_wake_particle_loop_exported(self) -> None:
        """wakeParticleLoop が定義され、window.wakeParticleLoop として公開されていること"""
        self.assertIn(
            "function wakeParticleLoop",
            self.content,
            "pet_particles.js 内に 'function wakeParticleLoop' が定義されていません"
        )
        self.assertIn(
            "window.wakeParticleLoop = wakeParticleLoop",
            self.content,
            "window.wakeParticleLoop へのエクスポートが見つかりません"
        )

    def test_02_loop_running_flag_prevents_duplicate_raf(self) -> None:
        """isParticleLoopRunning フラグが存在し、多重requestAnimationFrameが抑止されていること"""
        self.assertRegex(
            self.content,
            r"let\s+isParticleLoopRunning\s*=",
            "多重実行防止フラグ 'let isParticleLoopRunning' が宣言されていません"
        )
        self.assertIn(
            "isParticleLoopRunning = true",
            self.content,
            "ループ起動時に isParticleLoopRunning = true の設定がありません"
        )
        self.assertIn(
            "isParticleLoopRunning = false",
            self.content,
            "ループ停止時に isParticleLoopRunning = false の設定がありません"
        )

    def test_03_particle_loop_checks_document_hidden(self) -> None:
        """particleLoop 内で document.hidden を判定し、非表示時は次フレームを要求しないこと"""
        fn_match = re.search(r"function\s+particleLoop\s*\(\)\s*\{([\s\S]*?)\n\s*\}", self.content)
        self.assertIsNotNone(fn_match, "particleLoop 関数が見つかりません")
        fn_body = fn_match.group(1)

        self.assertIn(
            "document.hidden",
            fn_body,
            "particleLoop 内で document.hidden の判定が行われていません"
        )

    def test_04_visibilitychange_wakes_loop_on_foreground(self) -> None:
        """visibilitychange リスナーで画面復帰時 (!document.hidden) に wakeParticleLoop が呼ばれること"""
        self.assertIn(
            "'visibilitychange'",
            self.content,
            "pet_particles.js 内に visibilitychange リスナーが存在しません"
        )
        self.assertIn(
            "wakeParticleLoop",
            self.content,
            "画面復帰時の wakeParticleLoop 呼び出しが見つかりません"
        )

    def test_05_interactive_spawns_call_wake_loop(self) -> None:
        """インタラクション・パーティクル生成関数内で wakeParticleLoop が呼ばれること"""
        # spawnTouchParticles の検証
        touch_match = re.search(r"function\s+spawnTouchParticles\s*\([^)]*\)\s*\{([\s\S]*?)\n\s*\}", self.content)
        self.assertIsNotNone(touch_match, "spawnTouchParticles 関数が見つかりません")
        self.assertIn(
            "wakeParticleLoop",
            touch_match.group(1),
            "spawnTouchParticles 内で wakeParticleLoop() が呼ばれていません"
        )

        # spawnCelebrationConfetti の検証
        confetti_match = re.search(r"function\s+spawnCelebrationConfetti\s*\([^)]*\)\s*\{([\s\S]*?)\n\s*\}", self.content)
        self.assertIsNotNone(confetti_match, "spawnCelebrationConfetti 関数が見つかりません")
        self.assertIn(
            "wakeParticleLoop",
            confetti_match.group(1),
            "spawnCelebrationConfetti 内で wakeParticleLoop() が呼ばれていません"
        )

    def test_06_stop_particle_loop_cancels_raf(self) -> None:
        """stopParticleLoop が定義され、cancelAnimationFrame による保留破棄と公開が行われていること"""
        self.assertIn(
            "function stopParticleLoop",
            self.content,
            "pet_particles.js 内に 'function stopParticleLoop' が定義されていません"
        )
        self.assertIn(
            "cancelAnimationFrame",
            self.content,
            "stopParticleLoop 内に cancelAnimationFrame による保留フレーム破棄がありません"
        )
        self.assertIn(
            "window.stopParticleLoop = stopParticleLoop",
            self.content,
            "window.stopParticleLoop へのエクスポートが見つかりません"
        )

    def test_07_visibilitychange_stops_loop_on_hidden(self) -> None:
        """visibilitychange リスナー内で document.hidden 時に stopParticleLoop が呼ばれること"""
        vis_match = re.search(r"document\.addEventListener\(\s*['\"]visibilitychange['\"],\s*\(\)\s*=>\s*\{([\s\S]*?)\n\s*\}\);", self.content)
        self.assertIsNotNone(vis_match, "visibilitychange リスナーが見つかりません")
        vis_body = vis_match.group(1)
        self.assertIn(
            "stopParticleLoop",
            vis_body,
            "visibilitychange リスナー内で stopParticleLoop() が呼ばれていません"
        )
        self.assertIn(
            "wakeParticleLoop",
            vis_body,
            "visibilitychange リスナー内で wakeParticleLoop() が呼ばれていません"
        )

    def test_08_pet_js_routes_through_wake_particle_loop(self) -> None:
        """web_pet/pet.js の initDeskPetApp が wakeParticleLoop 経由でループを開始すること"""
        pet_js_path = PROJECT_ROOT / "web_pet" / "pet.js"
        self.assertTrue(pet_js_path.is_file(), "web_pet/pet.js が存在しません")
        pet_js = pet_js_path.read_text(encoding="utf-8")
        self.assertIn(
            "wakeParticleLoop",
            pet_js,
            "web_pet/pet.js 内で wakeParticleLoop 経由の起動が行われていません"
        )


if __name__ == "__main__":
    unittest.main()
