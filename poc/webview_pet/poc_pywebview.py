#!/usr/bin/env python3
"""
ネオ秘書くん - pywebview による最小透過Desk Pet PoC (poc/webview_pet/poc_pywebview.py)

DESIGN_SPEC §6.0（二段階クロスプラットフォームADR）および手帳 ID 86 に基づく
次世代デスクトップ描画基盤のプロトタイプ。

OS標準Webエンジン（Windows: WebView2, macOS: WebKit, Linux: WebKitGTK）を用い、
Tkinterの描画制約（高頻度テスト時のTclファイルロック競合・クロスプラットフォーム透過制約）
を克服しつつ、Electron（150MB+）を避けた軽量（30〜45MB目標）な透過常駐ペットを実現します。
"""

import base64
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("poc_pywebview")

# 依存ライブラリの確認
try:
    import psutil
except ImportError:
    logger.error("psutil がインストールされていません。『pip install psutil』を実行してください。")
    sys.exit(1)

try:
    import webview
except ImportError:
    logger.error("pywebview がインストールされていません。『pip install pywebview』を実行してください。")
    sys.exit(1)


# プロジェクトルートとアセットパスの解決
CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent.parent
ASSETS_HISHO_DIR = REPO_ROOT / "assets" / "dot" / "hisho"


def _load_image_as_base64(image_path: Path) -> Optional[str]:
    """画像ファイルをBase64 Data URI形式の文字列に変換します。

    Args:
        image_path: 読み込む画像ファイルのパス

    Returns:
        Base64 Data URI文字列。ファイルが存在しない場合は None。
    """
    if not image_path.exists():
        logger.warning("アセット画像が見つかりません: %s", image_path)
        return None
    try:
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
            return f"data:image/png;base64,{encoded}"
    except Exception as exc:
        logger.error("画像のBase64エンコードに失敗しました (%s): %s", image_path, exc)
        return None


class DeskPetApi:
    """JavaScript と Python 間の双方向通信を提供する API クラス。"""

    def __init__(self, process: psutil.Process) -> None:
        """APIクラスの初期化。

        Args:
            process: メモリ測定対象の自プロセスインスタンス
        """
        self._process = process
        self.window: Optional[webview.Window] = None
        # 初回 cpu_percent 呼び出しが 0.0 を返す psutil の仕様を回避するためプリシード
        try:
            self._process.cpu_percent(interval=None)
        except Exception as exc:
            # プリシード失敗時は初回サンプルが 0.0 表示になるだけなので継続可能
            logger.debug("cpu_percent プリシードに失敗しました: %s", exc)

    def get_memory_stats(self) -> Dict[str, Any]:
        """自プロセスおよび子プロセス群（WebView2/WebKitレンダラ）の合算メモリとCPU使用率を測定して返却します。

        Returns:
            Dict[str, Any]: rss_mb (プロセスツリー合算実メモリMB), vms_mb (仮想メモリMB), cpu_percent
        """
        try:
            total_rss = self._process.memory_info().rss
            total_vms = self._process.memory_info().vms
            # WebView2 / WebKit の子プロセス群も含めた実消費を合算測定 (Electron比較の公平性を担保)
            try:
                for child in self._process.children(recursive=True):
                    try:
                        child_mem = child.memory_info()
                        total_rss += child_mem.rss
                        total_vms += child_mem.vms
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except Exception as child_err:
                logger.debug("子プロセス巡回中に一時的スキップ: %s", child_err)

            rss_mb = total_rss / (1024.0 * 1024.0)
            vms_mb = total_vms / (1024.0 * 1024.0)
            cpu_percent = self._process.cpu_percent(interval=None)
            return {
                "rss_mb": round(rss_mb, 2),
                "vms_mb": round(vms_mb, 2),
                "cpu_percent": round(cpu_percent, 1),
            }
        except Exception as exc:
            logger.error("メモリ統計の取得に失敗しました: %s", exc)
            return {"rss_mb": 0.0, "vms_mb": 0.0, "cpu_percent": 0.0}

    def on_pet_click(self, action_name: str) -> None:
        """ペットクリック時のリアクションログを受け取ります。

        Args:
            action_name: 発火したアクション名 (例: 'jump')
        """
        stats = self.get_memory_stats()
        logger.info(
            "🐾 ペットがリアクションを発火しました: [%s] (RSS: %.1f MB, CPU: %.1f%%)",
            action_name,
            stats["rss_mb"],
            stats["cpu_percent"],
        )

    def close_app(self) -> None:
        """ウィンドウを破棄してアプリケーションを終了します。"""
        logger.info("クローズ要求を受信しました。ウィンドウを終了します。")
        if self.window is not None:
            self.window.destroy()


def _build_html_content(
    img_idle_1: Optional[str],
    img_idle_2: Optional[str],
    img_happy: Optional[str],
) -> str:
    """Desk Pet 表示用の完全な HTML/CSS/JavaScript 文字列を構築します。

    Args:
        img_idle_1: idle_1 の Base64 Data URI (None の場合は Canvas フォールバック)
        img_idle_2: idle_2 の Base64 Data URI
        img_happy: happy の Base64 Data URI

    Returns:
        str: 構築された HTML 文字列
    """
    has_images = bool(img_idle_1 and img_idle_2 and img_happy)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Neo Secretary Desk Pet PoC</title>
  <style>
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      user-select: none;
      -webkit-user-select: none;
    }}

    html, body {{
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: transparent;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }}

    /* メインコンテナ: ドラッグ移動可能領域 */
    .pet-container {{
      width: 100%;
      height: 100%;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      position: relative;
      cursor: grab;
    }}

    .pet-container:active {{
      cursor: grabbing;
    }}

    /* pywebview 標準ドラッグ領域指定クラス (pywebview はクラス名自体をマーカーに使用。
       -webkit-app-region は WebView2 では未解釈・Electron 互換のための予備宣言) */
    .pywebview-drag-region {{
      -webkit-app-region: drag;
    }}

    /* 呼吸アニメーション (ゆったりとした伸縮) */
    .pet-wrapper {{
      width: 140px;
      height: 140px;
      position: relative;
      display: flex;
      justify-content: center;
      align-items: center;
      animation: breathe 3.0s ease-in-out infinite;
      transform-origin: center bottom;
      transition: transform 0.15s ease-out;
    }}

    @keyframes breathe {{
      0%, 100% {{
        transform: translateY(0px) scale(1.0, 1.0);
      }}
      50% {{
        transform: translateY(-3px) scale(1.03, 0.97);
      }}
    }}

    /* クリック時のジャンプリアクション */
    .pet-wrapper.jump {{
      animation: petJump 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }}

    @keyframes petJump {{
      0% {{
        transform: translateY(0) scale(1, 1);
      }}
      30% {{
        transform: translateY(-28px) scale(1.12, 0.92);
      }}
      60% {{
        transform: translateY(-6px) scale(0.95, 1.05);
      }}
      80% {{
        transform: translateY(-12px) scale(1.02, 0.98);
      }}
      100% {{
        transform: translateY(0) scale(1, 1);
      }}
    }}

    /* ドット絵スプライト表示領域 */
    .pet-sprite {{
      width: 128px;
      height: 128px;
      image-rendering: pixelated;
      image-rendering: crisp-edges;
      pointer-events: auto;
      filter: drop-shadow(0 6px 10px rgba(0, 0, 0, 0.28));
      transition: filter 0.2s ease;
    }}

    .pet-sprite:hover {{
      filter: drop-shadow(0 8px 14px rgba(255, 184, 0, 0.45));
    }}

    /* ハート・キラキラエフェクト */
    .particle {{
      position: absolute;
      pointer-events: none;
      font-size: 20px;
      animation: floatUp 0.8s ease-out forwards;
      z-index: 100;
    }}

    @keyframes floatUp {{
      0% {{
        opacity: 1;
        transform: translateY(0) scale(0.6);
      }}
      100% {{
        opacity: 0;
        transform: translateY(-40px) scale(1.3);
      }}
    }}

    /* ステータス・メモリ表示バッジ */
    .status-badge {{
      position: absolute;
      bottom: 6px;
      background: rgba(30, 20, 14, 0.78);
      color: #F5F5DC;
      border: 1px solid rgba(255, 184, 0, 0.35);
      border-radius: 10px;
      padding: 2px 8px;
      font-size: 11px;
      font-family: monospace;
      letter-spacing: 0.5px;
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
      pointer-events: none;
      transition: opacity 0.3s ease;
    }}

    /* コントロールボタン (右上の最小×ボタン) */
    .close-btn {{
      position: absolute;
      top: 6px;
      right: 6px;
      width: 18px;
      height: 18px;
      background: rgba(255, 60, 60, 0.75);
      color: #FFF;
      border-radius: 50%;
      display: flex;
      justify-content: center;
      align-items: center;
      font-size: 10px;
      font-weight: bold;
      cursor: pointer;
      opacity: 0;
      transition: opacity 0.2s ease, transform 0.1s ease;
      /* WebView2 では未解釈・Electron 互換用 (ドラッグ領域からの除外予備宣言) */
      -webkit-app-region: no-drag;
      pointer-events: auto;
      z-index: 200;
    }}

    .pet-container:hover .close-btn {{
      opacity: 1;
    }}

    .close-btn:hover {{
      transform: scale(1.2);
      background: rgba(255, 30, 30, 0.95);
    }}
  </style>
</head>
<body>
  <div class="pet-container pywebview-drag-region" id="container">
    <div class="close-btn" id="closeBtn" title="閉じる">✕</div>
    
    <div class="pet-wrapper" id="petWrapper">
      <img id="petImg" class="pet-sprite" src="{img_idle_1 or ''}" alt="Desk Pet">
      <canvas id="fallbackCanvas" class="pet-sprite" width="128" height="128" style="display: none;"></canvas>
    </div>

    <div class="status-badge" id="memBadge">RSS: --.- MB</div>
  </div>

  <script>
    const hasImages = {str(has_images).lower()};
    const imgIdle1 = "{img_idle_1 or ''}";
    const imgIdle2 = "{img_idle_2 or ''}";
    const imgHappy = "{img_happy or ''}";

    const petWrapper = document.getElementById("petWrapper");
    const petImg = document.getElementById("petImg");
    const fallbackCanvas = document.getElementById("fallbackCanvas");
    const memBadge = document.getElementById("memBadge");
    const closeBtn = document.getElementById("closeBtn");
    const container = document.getElementById("container");

    let isJumping = false;
    let isBlinking = false;

    // 画像が存在しない場合の Canvas レトロピクセル描画フォールバック
    function drawFallbackPet(state) {{
      const ctx = fallbackCanvas.getContext("2d");
      ctx.clearRect(0, 0, 128, 128);
      ctx.imageSmoothingEnabled = false;

      // 体（ブラウン）
      ctx.fillStyle = "#A67B5B";
      ctx.fillRect(32, 32, 64, 64);
      // 顔（クリーム）
      ctx.fillStyle = "#F5F5DC";
      ctx.fillRect(44, 44, 40, 40);

      // 目
      ctx.fillStyle = "#4A3B32";
      if (state === "blink") {{
        ctx.fillRect(48, 60, 10, 3);
        ctx.fillRect(70, 60, 10, 3);
      }} else if (state === "happy") {{
        // ニッコリ目 (^^)
        ctx.fillRect(48, 58, 8, 3);
        ctx.fillRect(52, 55, 8, 3);
        ctx.fillRect(68, 55, 8, 3);
        ctx.fillRect(72, 58, 8, 3);
      }} else {{
        // 通常目
        ctx.fillRect(50, 56, 6, 8);
        ctx.fillRect(72, 56, 6, 8);
      }}

      // ほっぺ
      ctx.fillStyle = "#FF8A80";
      ctx.fillRect(44, 66, 8, 4);
      ctx.fillRect(76, 66, 8, 4);

      // ネクタイ (イエロー)
      ctx.fillStyle = "#FFD54F";
      ctx.fillRect(60, 80, 8, 14);
    }}

    if (!hasImages) {{
      petImg.style.display = "none";
      fallbackCanvas.style.display = "block";
      drawFallbackPet("normal");
    }}

    // 瞬きアニメーションループ (3.5秒〜5秒間隔)
    function triggerBlink() {{
      if (isJumping) return;
      isBlinking = true;
      if (hasImages) {{
        petImg.src = imgIdle2;
      }} else {{
        drawFallbackPet("blink");
      }}

      setTimeout(() => {{
        if (!isJumping) {{
          if (hasImages) {{
            petImg.src = imgIdle1;
          }} else {{
            drawFallbackPet("normal");
          }}
        }}
        isBlinking = false;
      }}, 220);
    }}

    setInterval(() => {{
      if (Math.random() > 0.3) {{
        triggerBlink();
      }}
    }}, 3800);

    // クリックリアクション（ジャンプ + 笑顔 + パーティクル）
    function triggerJumpReaction() {{
      if (isJumping) return;
      isJumping = true;

      // 笑顔スプライトへ切替
      if (hasImages) {{
        petImg.src = imgHappy;
      }} else {{
        drawFallbackPet("happy");
      }}

      petWrapper.classList.add("jump");

      // パーティクル発生
      spawnParticle("💖");
      setTimeout(() => spawnParticle("✨"), 150);

      // Python 側へ通知
      if (window.pywebview && window.pywebview.api) {{
        window.pywebview.api.on_pet_click("jump");
      }}

      setTimeout(() => {{
        petWrapper.classList.remove("jump");
        if (hasImages) {{
          petImg.src = imgIdle1;
        }} else {{
          drawFallbackPet("normal");
        }}
        isJumping = false;
      }}, 650);
    }}

    // ハート・キラキラの生成
    function spawnParticle(symbol) {{
      const p = document.createElement("div");
      p.className = "particle";
      p.innerText = symbol;
      p.style.left = (45 + Math.random() * 38) + "%";
      p.style.top = (30 + Math.random() * 20) + "%";
      container.appendChild(p);
      setTimeout(() => p.remove(), 850);
    }}

    // ドラッグとクリックの判定分離（WebView2 対応）
    let startX = 0;
    let startY = 0;
    let startTime = 0;

    container.addEventListener("mousedown", (e) => {{
      startX = e.clientX;
      startY = e.clientY;
      startTime = Date.now();
    }});

    container.addEventListener("mouseup", (e) => {{
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const elapsed = Date.now() - startTime;

      // 移動距離が5px未満かつ400ms以内の短タップをクリックと判定
      if (dist < 5 && elapsed < 400 && e.target !== closeBtn) {{
        triggerJumpReaction();
      }}
    }});

    // 閉じるボタン
    closeBtn.addEventListener("click", (e) => {{
      e.stopPropagation();
      if (window.pywebview && window.pywebview.api) {{
        window.pywebview.api.close_app();
      }} else {{
        window.close();
      }}
    }});

    // Python側から呼び出されるメモリバッジ更新関数
    window.updateMemoryBadge = function(rssMb, cpuPercent) {{
      memBadge.innerText = `RSS: ${{rssMb.toFixed(1)}} MB | ${{cpuPercent.toFixed(0)}}%`;
    }};
  </script>
</body>
</html>
"""


def _monitor_memory_loop(
    window: webview.Window,
    api: DeskPetApi,
    stop_event: threading.Event,
) -> None:
    """バックグラウンドでプロセス常駐メモリ（RSS）を監視し、ログ出力と画面更新を行うループ。

    Args:
        window: pywebview ウィンドウインスタンス
        api: DeskPetApi インスタンス
        stop_event: 監視停止シグナル
    """
    logger.info("メモリ監視スレッドを開始しました (測定周期: 2.5秒)")
    # 初期化待機
    time.sleep(1.0)

    while not stop_event.is_set():
        try:
            stats = api.get_memory_stats()
            rss = stats["rss_mb"]
            cpu = stats["cpu_percent"]

            logger.info("📊 Desk Pet リソース実測: RSS = %.2f MB | CPU = %.1f%%", rss, cpu)

            # JavaScript 側のバッジを更新 (スレッドセーフな evaluate_js)
            js_code = f"if (window.updateMemoryBadge) window.updateMemoryBadge({rss}, {cpu});"
            window.evaluate_js(js_code)
        except Exception as exc:
            # ウィンドウ破棄時の例外は正常終了とみなす
            if "Window is destroyed" in str(exc) or "NoneType" in str(exc):
                break
            logger.debug("メモリ監視中にエラーが発生しました: %s", exc)

        stop_event.wait(2.5)

    logger.info("メモリ監視スレッドを終了しました。")


def run_poc(debug: bool = False) -> None:
    """PoC 透過 Desk Pet ウィンドウを起動します。

    Args:
        debug: デバッグモード (WebView の開発者ツール有効化)
    """
    process = psutil.Process(os.getpid())
    api = DeskPetApi(process)

    # アセットのBase64ロード
    img_idle_1 = _load_image_as_base64(ASSETS_HISHO_DIR / "idle_1.png")
    img_idle_2 = _load_image_as_base64(ASSETS_HISHO_DIR / "idle_2.png")
    img_happy = _load_image_as_base64(ASSETS_HISHO_DIR / "happy.png")

    if img_idle_1 and img_idle_2 and img_happy:
        logger.info("公式秘書くんスプライト（idle_1, idle_2, happy）のロードに成功しました。")
    else:
        logger.info("スプライトの一部が見つからないため、内蔵レトロピクセル描画フォールバックを使用します。")

    html_content = _build_html_content(img_idle_1, img_idle_2, img_happy)

    logger.info("pywebview ウィンドウを設定中 (透過=True, 枠なし=True, 最前面=True, サイズ=200x200)...")

    # ウィンドウの生成
    window = webview.create_window(
        title="Neo Secretary Desk Pet PoC",
        html=html_content,
        width=200,
        height=200,
        frameless=True,
        easy_drag=False,  # CSSの .pywebview-drag-region を使用
        on_top=True,
        transparent=True,
        background_color="#00000000",
        js_api=api,
    )
    api.window = window

    # メモリ監視スレッドのセットアップ
    stop_event = threading.Event()
    monitor_thread = threading.Thread(
        target=_monitor_memory_loop,
        args=(window, api, stop_event),
        daemon=True,
    )

    def on_shown() -> None:
        """ウィンドウ表示完了時にバックグラウンド監視を開始します。"""
        logger.info("✅ 透過Desk Petウィンドウが表示されました。ドラッグ移動・クリック操作が可能です。")
        if not monitor_thread.is_alive():
            try:
                monitor_thread.start()
            except RuntimeError as exc:
                # 既に起動済み/終了済みスレッドへの start() は無害なため継続
                logger.debug("監視スレッドの二重起動を抑止しました: %s", exc)

    def on_closed() -> None:
        """ウィンドウ破棄時にスレッドを停止します。"""
        logger.info("ウィンドウが閉じられました。")
        stop_event.set()

    window.events.shown += on_shown
    window.events.closed += on_closed

    # pywebview メインループの開始 (GUIブロッキング)
    try:
        webview.start(debug=debug)
    finally:
        stop_event.set()
        logger.info("Desk Pet PoC を安全に終了しました。")


if __name__ == "__main__":
    is_debug = "--debug" in sys.argv
    run_poc(debug=is_debug)
