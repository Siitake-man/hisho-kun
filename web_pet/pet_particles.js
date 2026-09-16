/**
 * ネオ秘書くん 背景環境シーン ＆ パーティクル物理描画エンジン (pet_particles.js)
 *
 * 【役割】
 * - HTML5 Canvas による5大背景環境シーン（書斎・カフェ・森・海・サイバー）のリアルタイム描画
 * - 天候パーティクル（雨・雪・雷光・落ち葉）および環境アンビエント光の物理演算
 * - なでなでインタラクション（ハート・星・音符）の湧き出し物理
 * - タスク完了・承認時の歓喜セレブレーション紙吹雪（Confetti）大噴射エンジン（重力放物線シミュレーション）
 *
 * 【アーキテクチャ】
 * - 外部依存ゼロ（Vanilla JS + Canvas 2D API）
 * - requestAnimationFrame による 60fps 不滅スプリング物理ループ (try-finally保護)
 * - グローバル双方向同期 (Object.defineProperty による currentEnvIndex 監視 ＆ setEnvTheme API)
 * - グローバル互換性保証 (window.envCanvas / envCtx 公開)
 */

(function() {
  'use strict';

  // 5大背景テーマ定義
  const ENV_THEMES = [
    { id: 'room', label: '書斎', class: 'theme-room' },
    { id: 'cafe', label: 'カフェ', class: 'theme-cafe' },
    { id: 'forest', label: '森', class: 'theme-forest' },
    { id: 'ocean', label: '海', class: 'theme-ocean' },
    { id: 'cyber', label: 'サイバー', class: 'theme-cyber' }
  ];
  let currentEnvIndex = 0;

  // パーティクル管理配列
  let envParticles = [];
  let touchParticles = [];
  let envCanvas = null;
  let envCtx = null;

  // 🛡️ ダブルバッファリング用オフスクリーンCanvas（チラつき・フリッカー完全根絶）
  let bgCacheCanvas = null;
  let bgCacheCtx = null;
  let bgNeedsRedraw = true;

  /**
   * 背景シーンをオフスクリーンCanvasにプリレンダリング（ダブルバッファ化）
   */
  function updateBgCache() {
    if (!envCanvas) return;
    if (!bgCacheCanvas) {
      bgCacheCanvas = document.createElement('canvas');
      bgCacheCtx = bgCacheCanvas.getContext('2d');
    }
    bgCacheCanvas.width = envCanvas.width;
    bgCacheCanvas.height = envCanvas.height;
    if (bgCacheCtx) {
      bgCacheCtx.clearRect(0, 0, bgCacheCanvas.width, bgCacheCanvas.height);
      drawEnvSceneTo(bgCacheCtx, bgCacheCanvas.width, bgCacheCanvas.height);
    }
    bgNeedsRedraw = false;
  }

  /**
   * Canvasの初期化およびリサイズ追従
   */
  function initEnvCanvas() {
    envCanvas = document.getElementById('env-canvas');
    if (envCanvas) {
      envCanvas.width = window.innerWidth;
      envCanvas.height = window.innerHeight;
      envCtx = envCanvas.getContext('2d');
      // グローバル参照への安全な公開 (NoSleep等の外部参照互換)
      window.envCanvas = envCanvas;
      window.envCtx = envCtx;
      updateBgCache();
    }
  }

  // 画面リサイズリスナー
  window.addEventListener('resize', initEnvCanvas);

  /**
   * 背景環境テーマの明示的設定（DOM・ラベル・パーティクル配列を完全同期）
   * @param {string|number} themeIdOrIndex テーマID ('room'等) または インデックス番号
   * @returns {object|null} 変更後のテーマオブジェクト
   */
  function setEnvTheme(themeIdOrIndex) {
    let idx = -1;
    if (typeof themeIdOrIndex === 'number') {
      idx = (themeIdOrIndex + ENV_THEMES.length) % ENV_THEMES.length;
    } else if (typeof themeIdOrIndex === 'string') {
      idx = ENV_THEMES.findIndex(t => t.id === themeIdOrIndex);
    }
    if (idx !== -1) {
      currentEnvIndex = idx;
      const theme = ENV_THEMES[currentEnvIndex];
      const backdrop = document.getElementById('env-backdrop');
      if (backdrop) backdrop.className = `env-backdrop ${theme.class}`;
      const label = document.getElementById('env-label');
      if (label) label.innerText = theme.label;
      envParticles.length = 0; // 閉包内配列を安全にクリア
      updateBgCache();
      return theme;
    }
    return null;
  }

  /**
   * 背景環境テーマの循環切り替え
   */
  function cycleEnvTheme() {
    const theme = setEnvTheme(currentEnvIndex + 1);
    if (!theme) return;
    if (navigator.vibrate) {
      try { navigator.vibrate(25); } catch (e) {}
    }

    // トースト通知（showToast が定義されていれば表示）
    if (typeof window.showToast === 'function') {
      window.showToast(`🏞️ ${theme.label}テーマに変わりました`);
    }
  }

  /**
   * ターゲットCanvasコンテキストへの背景シーン描画ヘルパー
   */
  function drawEnvSceneTo(targetCtx, targetW, targetH) {
    var origCtx = envCtx;
    try {
      envCtx = targetCtx;
      drawEnvScene();
    } finally {
      envCtx = origCtx;
    }
  }

  /**
   * テーマごとの背景シーン描画（本格的ピクセルアート書斎・生活空間）
   */
  function drawEnvScene() {
    if (!envCtx || !envCanvas) return;
    const w = envCanvas.width, h = envCanvas.height;
    const theme = ENV_THEMES[currentEnvIndex].id;
    const t = Date.now();

    envCtx.save();
    try {
      if (theme === 'room') {
        // 📖 本格的レトロ書斎シーン
        // 1. 木製デスク天板（下部）
        const deskY = h * 0.72;
        envCtx.fillStyle = 'rgba(54, 32, 18, 0.95)';
        envCtx.fillRect(0, deskY, w, h - deskY);
        // デスクの縁取りハイライト
        envCtx.fillStyle = 'rgba(120, 75, 42, 0.85)';
        envCtx.fillRect(0, deskY, w, 4);

        // 2. クラシックな本棚（左上〜中央）
        const shelfX = w * 0.04, shelfY = h * 0.16, shelfW = w * 0.42, shelfH = h * 0.38;
        // 本棚の木枠
        envCtx.fillStyle = 'rgba(38, 22, 12, 0.92)';
        envCtx.fillRect(shelfX, shelfY, shelfW, shelfH);
        envCtx.strokeStyle = 'rgba(84, 50, 28, 0.95)';
        envCtx.lineWidth = 4;
        envCtx.strokeRect(shelfX, shelfY, shelfW, shelfH);
        
        // 棚板2段
        const shelfRow1 = shelfY + shelfH * 0.48;
        envCtx.fillStyle = 'rgba(70, 42, 24, 0.95)';
        envCtx.fillRect(shelfX, shelfRow1, shelfW, 5);

        // 本の背表紙（色彩豊かにぎっしり並べる）
        const bookColors = ['#C62828', '#1565C0', '#2E7D32', '#F57F17', '#6A1B9A', '#37474F', '#D84315', '#4527A0'];
        // 上段の本
        let bx = shelfX + 6;
        let bIdx = 0;
        while (bx < shelfX + shelfW - 14) {
          const bw = 8 + (bIdx % 3) * 3;
          const bh = shelfH * 0.34 + (bIdx % 4) * 4;
          envCtx.fillStyle = bookColors[bIdx % bookColors.length];
          envCtx.fillRect(bx, shelfRow1 - bh, bw, bh);
          // 金文字・タイトルの線
          envCtx.fillStyle = 'rgba(255, 215, 0, 0.7)';
          envCtx.fillRect(bx + 2, shelfRow1 - bh + 6, bw - 4, 2);
          bx += bw + 3;
          bIdx++;
        }
        // 下段の本（一部斜めに倒れた本）
        bx = shelfX + 6;
        while (bx < shelfX + shelfW - 24) {
          const bw = 9 + (bIdx % 2) * 4;
          const bh = shelfH * 0.36 + (bIdx % 3) * 3;
          envCtx.fillStyle = bookColors[(bIdx + 3) % bookColors.length];
          envCtx.fillRect(bx, shelfY + shelfH - bh - 4, bw, bh);
          bx += bw + 3;
          bIdx++;
        }

        // 3. 窓と星空（右上）
        const winX = w * 0.62, winY = h * 0.14, winW = w * 0.32, winH = h * 0.32;
        // 窓枠と夜空
        envCtx.fillStyle = 'rgba(10, 14, 28, 0.95)';
        envCtx.fillRect(winX, winY, winW, winH);
        // 星々
        envCtx.fillStyle = 'rgba(255, 255, 255, 0.8)';
        envCtx.fillRect(winX + winW * 0.3, winY + winH * 0.25, 2, 2);
        envCtx.fillRect(winX + winW * 0.7, winY + winH * 0.35, 2, 2);
        envCtx.fillRect(winX + winW * 0.5, winY + winH * 0.7, 1.5, 1.5);
        // 三日月
        envCtx.fillStyle = '#FFE082';
        envCtx.beginPath();
        envCtx.arc(winX + winW * 0.75, winY + winH * 0.3, 7, 0, Math.PI * 2);
        envCtx.fill();
        envCtx.fillStyle = 'rgba(10, 14, 28, 0.95)';
        envCtx.beginPath();
        envCtx.arc(winX + winW * 0.72, winY + winH * 0.28, 6, 0, Math.PI * 2);
        envCtx.fill();
        // 窓の格子木枠
        envCtx.strokeStyle = 'rgba(92, 58, 34, 0.95)';
        envCtx.lineWidth = 3;
        envCtx.strokeRect(winX, winY, winW, winH);
        envCtx.beginPath();
        envCtx.moveTo(winX + winW / 2, winY); envCtx.lineTo(winX + winW / 2, winY + winH);
        envCtx.moveTo(winX, winY + winH / 2); envCtx.lineTo(winX + winW, winY + winH / 2);
        envCtx.stroke();

        // 4. アンティーク卓上ランプ（デスク右側 ＆ 優しい光のコーン）
        const lampX = w * 0.84, lampY = deskY;
        // 台座
        envCtx.fillStyle = 'rgba(212, 175, 55, 0.95)';
        envCtx.fillRect(lampX - 12, lampY - 4, 24, 4);
        // 支柱
        envCtx.fillRect(lampX - 2, lampY - 32, 4, 28);
        // 緑のバンカーズシェード
        envCtx.fillStyle = '#1B5E20';
        envCtx.beginPath();
        envCtx.ellipse(lampX, lampY - 32, 16, 7, 0, Math.PI, Math.PI * 2);
        envCtx.fill();
        // 暖色ランプ光のコーン
        const lampGlow = envCtx.createRadialGradient(lampX, lampY - 26, 4, lampX, lampY - 10, 65);
        lampGlow.addColorStop(0, 'rgba(255, 235, 120, 0.45)');
        lampGlow.addColorStop(0.6, 'rgba(255, 180, 50, 0.15)');
        lampGlow.addColorStop(1, 'rgba(255, 180, 50, 0)');
        envCtx.fillStyle = lampGlow;
        envCtx.beginPath();
        envCtx.arc(lampX, lampY - 10, 65, 0, Math.PI * 2);
        envCtx.fill();

        // 5. コーヒーカップと湯気（デスク左側）
        const cupX = w * 0.16, cupY = deskY + 6;
        envCtx.fillStyle = '#F5F5DC';
        envCtx.fillRect(cupX - 7, cupY - 12, 14, 11);
        envCtx.fillStyle = '#6D4C41';
        envCtx.fillRect(cupX - 5, cupY - 11, 10, 3);
        // 湯気アニメーション
        const steamY = cupY - 14 - (t % 1500) / 1500 * 14;
        const steamAlpha = 1.0 - (t % 1500) / 1500;
        envCtx.strokeStyle = `rgba(255, 255, 255, ${steamAlpha * 0.4})`;
        envCtx.lineWidth = 1.5;
        envCtx.beginPath();
        envCtx.moveTo(cupX - 2 + Math.sin(t / 200) * 3, steamY);
        envCtx.lineTo(cupX + Math.sin(t / 200 + 1) * 3, steamY - 6);
        envCtx.stroke();

      } else if (theme === 'cafe') {
        // ☕ カフェ（カウンター・ペンダントライト・メニューボード・街灯りの窓）
        const tx = w * 0.78, ty = h * 0.75;
        // マーブルカウンター天板 ＆ 脚
        envCtx.fillStyle = 'rgba(70, 45, 28, 0.92)';
        envCtx.beginPath();
        envCtx.ellipse(tx, ty, 95, 24, 0, 0, Math.PI * 2);
        envCtx.fill();
        envCtx.fillStyle = 'rgba(45, 28, 16, 0.95)';
        envCtx.fillRect(tx - 8, ty, 16, h - ty);
        // カウンター上のラテカップ（湯気つき）
        const latteX = tx - 40, latteY = ty - 18;
        envCtx.fillStyle = '#F5F5DC';
        envCtx.fillRect(latteX - 9, latteY - 10, 18, 12);
        envCtx.fillStyle = '#8D6E63';
        envCtx.fillRect(latteX - 7, latteY - 8, 14, 4);
        const steamY2 = latteY - 12 - (t % 1600) / 1600 * 12;
        const steamA2 = 1.0 - (t % 1600) / 1600;
        envCtx.strokeStyle = `rgba(255, 255, 255, ${steamA2 * 0.35})`;
        envCtx.lineWidth = 1.5;
        envCtx.beginPath();
        envCtx.moveTo(latteX - 2 + Math.sin(t / 260) * 3, steamY2);
        envCtx.lineTo(latteX + Math.sin(t / 260 + 1) * 3, steamY2 - 6);
        envCtx.stroke();
        // ペンダントライト2灯（ゆらぐ柔らかい光）
        for (const [px, py] of [[0.30, 0.06], [0.55, 0.10]]) {
          const cordX = w * px, cordEnd = h * py + 34;
          envCtx.strokeStyle = 'rgba(30, 20, 12, 0.9)';
          envCtx.lineWidth = 2;
          envCtx.beginPath();
          envCtx.moveTo(cordX, h * py);
          envCtx.lineTo(cordX, cordEnd);
          envCtx.stroke();
          envCtx.fillStyle = '#3E2723';
          envCtx.beginPath();
          envCtx.moveTo(cordX - 12, cordEnd + 10);
          envCtx.lineTo(cordX + 12, cordEnd + 10);
          envCtx.lineTo(cordX, cordEnd - 4);
          envCtx.closePath();
          envCtx.fill();
          const glowPulse = 0.28 + Math.sin(t / 900 + px * 10) * 0.06;
          const lampGlow2 = envCtx.createRadialGradient(cordX, cordEnd + 12, 2, cordX, cordEnd + 12, 46);
          lampGlow2.addColorStop(0, `rgba(255, 200, 100, ${glowPulse})`);
          lampGlow2.addColorStop(1, 'rgba(255, 200, 100, 0)');
          envCtx.fillStyle = lampGlow2;
          envCtx.beginPath();
          envCtx.arc(cordX, cordEnd + 12, 46, 0, Math.PI * 2);
          envCtx.fill();
        }
        // 手書きメニューボード（黒板）
        const boardX = w * 0.06, boardY = h * 0.10, boardW = w * 0.17, boardH = h * 0.20;
        envCtx.fillStyle = 'rgba(38, 30, 24, 0.95)';
        envCtx.fillRect(boardX, boardY, boardW, boardH);
        envCtx.strokeStyle = 'rgba(141, 110, 99, 0.9)';
        envCtx.lineWidth = 4;
        envCtx.strokeRect(boardX, boardY, boardW, boardH);
        envCtx.fillStyle = 'rgba(220, 210, 190, 0.75)';
        envCtx.fillRect(boardX + 8, boardY + 10, boardW * 0.62, 3);
        envCtx.fillRect(boardX + 8, boardY + 22, boardW * 0.48, 2);
        envCtx.fillRect(boardX + 8, boardY + 32, boardW * 0.55, 2);
        envCtx.fillRect(boardX + 8, boardY + 42, boardW * 0.40, 2);
        // 街灯りの窓（夜のストリート）
        envCtx.strokeStyle = 'rgba(190, 155, 120, 0.55)';
        envCtx.lineWidth = 3;
        envCtx.strokeRect(w * 0.07, h * 0.52, w * 0.20, h * 0.28);
        envCtx.fillStyle = 'rgba(255, 200, 120, 0.14)';
        envCtx.fillRect(w * 0.07, h * 0.52, w * 0.20, h * 0.28);
        envCtx.fillStyle = 'rgba(50, 38, 28, 0.9)';
        envCtx.fillRect(w * 0.165, h * 0.52, 3, h * 0.28);
        envCtx.fillRect(w * 0.07, h * 0.655, w * 0.20, 3);

      } else if (theme === 'forest') {
        // 🌲 森（奥行きのある樹木シルエット・キノコ・焚き火・蛍）
        // 遠景の丘レイヤー
        envCtx.fillStyle = 'rgba(24, 72, 40, 0.55)';
        envCtx.beginPath();
        envCtx.ellipse(w * 0.30, h * 0.80, w * 0.34, h * 0.10, 0, 0, Math.PI * 2);
        envCtx.fill();
        envCtx.beginPath();
        envCtx.ellipse(w * 0.78, h * 0.82, w * 0.28, h * 0.09, 0, 0, Math.PI * 2);
        envCtx.fill();
        // 樹木シルエット（前後2レイヤー）
        const trees = [[0.08, 0.92, 1.0], [0.2, 0.97, 0.65], [0.86, 0.94, 1.1], [0.95, 0.98, 0.55], [0.5, 0.90, 0.8], [0.62, 0.94, 0.6]];
        for (const [px, py, sc] of trees) {
          const bx = w * px, by = h * py, s = sc * h * 0.22;
          envCtx.fillStyle = 'rgba(18, 62, 34, 0.92)';
          envCtx.beginPath();
          envCtx.moveTo(bx, by - s);
          envCtx.lineTo(bx - s * 0.55, by);
          envCtx.lineTo(bx + s * 0.55, by);
          envCtx.closePath();
          envCtx.fill();
          envCtx.fillStyle = 'rgba(40, 28, 18, 0.95)';
          envCtx.fillRect(bx - 4, by, 8, s * 0.18);
        }
        // 根元のキノコ群（赤傘×白点）
        for (const [px, py, sc] of [[0.13, 0.985, 1.0], [0.165, 1.0, 0.7], [0.9, 0.99, 0.85]]) {
          const mx = w * px, my = h * py, ms = sc * 10;
          envCtx.fillStyle = 'rgba(245, 235, 210, 0.95)';
          envCtx.fillRect(mx - ms * 0.2, my - ms, ms * 0.4, ms);
          envCtx.fillStyle = 'rgba(200, 50, 40, 0.95)';
          envCtx.beginPath();
          envCtx.ellipse(mx, my - ms, ms * 0.7, ms * 0.45, 0, Math.PI, 0);
          envCtx.fill();
          envCtx.fillStyle = 'rgba(255, 255, 255, 0.85)';
          envCtx.fillRect(mx - ms * 0.3, my - ms * 1.2, 2, 2);
          envCtx.fillRect(mx + ms * 0.2, my - ms * 1.1, 2, 2);
        }
        envCtx.fillStyle = 'rgba(22, 58, 30, 0.85)';
        envCtx.fillRect(0, h * 0.76, w, h * 0.24);

      } else if (theme === 'ocean') {
        // 🌊 海（水面の波・差し込む光柱・熱帯魚・サンゴ・ヒトデ）
        // 差し込む太陽光柱（斜めの半透明ポリゴン）
        for (let i = 0; i < 3; i++) {
          const rayX = w * (0.18 + i * 0.3);
          const sway = Math.sin(t / 1800 + i) * 14;
          envCtx.fillStyle = `rgba(190, 235, 255, ${0.10 - i * 0.02})`;
          envCtx.beginPath();
          envCtx.moveTo(rayX + sway, 0);
          envCtx.lineTo(rayX + 34 + sway, 0);
          envCtx.lineTo(rayX + 90 + sway * 2, h * 0.76);
          envCtx.lineTo(rayX + 30 + sway * 2, h * 0.76);
          envCtx.closePath();
          envCtx.fill();
        }
        // 熱帯魚の群れ（ゆったり遊泳）
        const fish = [[0.25, 0.42, 1.0, '#FFB300'], [0.52, 0.30, 0.7, '#FF7043'], [0.70, 0.55, 0.85, '#4DD0E1'], [0.40, 0.62, 0.55, '#FFF176']];
        for (const [px, py, sc, col] of fish) {
          const fx = w * px + Math.sin(t / 2000 + px * 9) * 30;
          const fy = h * py + Math.cos(t / 1600 + py * 7) * 10;
          const fs = sc * 12;
          envCtx.fillStyle = col;
          envCtx.globalAlpha = 0.85;
          envCtx.beginPath();
          envCtx.ellipse(fx, fy, fs, fs * 0.55, 0, 0, Math.PI * 2);
          envCtx.fill();
          envCtx.beginPath();
          envCtx.moveTo(fx - fs, fy);
          envCtx.lineTo(fx - fs * 1.5, fy - fs * 0.5);
          envCtx.lineTo(fx - fs * 1.5, fy + fs * 0.5);
          envCtx.closePath();
          envCtx.fill();
          envCtx.fillStyle = 'rgba(10, 20, 30, 0.9)';
          envCtx.fillRect(fx + fs * 0.35, fy - fs * 0.22, 2, 2);
          envCtx.globalAlpha = 1.0;
        }
        // 海底のサンゴ ＆ ヒトデ
        envCtx.fillStyle = 'rgba(255, 111, 156, 0.75)';
        for (let i = 0; i < 5; i++) {
          const cx = w * (0.10 + i * 0.05);
          envCtx.fillRect(cx, h * 0.80 - 12 - (i % 2) * 6, 3, 14 + (i % 3) * 4);
        }
        envCtx.fillStyle = 'rgba(255, 171, 64, 0.85)';
        const starX = w * 0.30, starY = h * 0.87;
        for (let i = 0; i < 5; i++) {
          const ang = (i / 5) * Math.PI * 2 + t / 4000;
          envCtx.beginPath();
          envCtx.moveTo(starX, starY);
          envCtx.lineTo(starX + Math.cos(ang) * 8, starY + Math.sin(ang) * 8);
          envCtx.lineTo(starX + Math.cos(ang + 0.6) * 8, starY + Math.sin(ang + 0.6) * 8);
          envCtx.closePath();
          envCtx.fill();
        }
        // 水面の波（3レイヤーの揺らぎ）
        envCtx.strokeStyle = 'rgba(180, 230, 255, 0.35)';
        envCtx.lineWidth = 2;
        for (let i = 0; i < 3; i++) {
          envCtx.beginPath();
          const wy = h * (0.55 + i * 0.12);
          for (let x = 0; x <= w; x += 12) {
            const y = wy + Math.sin(x / 40 + t / 500 + i) * 5;
            if (x === 0) envCtx.moveTo(x, y); else envCtx.lineTo(x, y);
          }
          envCtx.stroke();
        }
        envCtx.fillStyle = 'rgba(28, 58, 78, 0.75)';
        envCtx.fillRect(0, h * 0.76, w, h * 0.24);

      } else if (theme === 'cyber') {
        // 🌃 サイバー（ネオンビル・月・アンテナビーコン・ホバー車・グリッドフロア）
        // 大きな満月（ドーム光暈つき）
        const moonX = w * 0.82, moonY = h * 0.16, moonR = Math.min(w, h) * 0.055;
        const moonGlow = envCtx.createRadialGradient(moonX, moonY, moonR * 0.4, moonX, moonY, moonR * 3);
        moonGlow.addColorStop(0, 'rgba(120, 200, 255, 0.20)');
        moonGlow.addColorStop(1, 'rgba(120, 200, 255, 0)');
        envCtx.fillStyle = moonGlow;
        envCtx.beginPath();
        envCtx.arc(moonX, moonY, moonR * 3, 0, Math.PI * 2);
        envCtx.fill();
        envCtx.fillStyle = 'rgba(220, 240, 255, 0.92)';
        envCtx.beginPath();
        envCtx.arc(moonX, moonY, moonR, 0, Math.PI * 2);
        envCtx.fill();
        envCtx.fillStyle = 'rgba(150, 180, 210, 0.5)';
        envCtx.fillRect(moonX - moonR * 0.4, moonY - moonR * 0.2, moonR * 0.3, moonR * 0.3);
        envCtx.fillRect(moonX + moonR * 0.1, moonY + moonR * 0.15, moonR * 0.4, moonR * 0.25);
        const buildings = [[0.04, 0.38], [0.14, 0.58], [0.27, 0.46], [0.71, 0.52], [0.83, 0.4], [0.93, 0.62]];
        for (const [px, ph] of buildings) {
          const bx = w * px, bw = w * 0.07, bh = h * ph;
          envCtx.fillStyle = 'rgba(18, 8, 34, 0.95)';
          envCtx.fillRect(bx, h * 0.76 - bh, bw, bh);
          for (let wy = h * 0.76 - bh + 10; wy < h * 0.76 - 12; wy += 16) {
            for (let wx = bx + 5; wx < bx + bw - 8; wx += 12) {
              if ((Math.floor(t / 500) + wx + wy) % 3 !== 0) {
                envCtx.fillStyle = (wx + wy) % 2 === 0 ? 'rgba(0, 229, 255, 0.75)' : 'rgba(255, 23, 68, 0.75)';
                envCtx.fillRect(wx, wy, 5, 7);
              }
            }
          }
          // 屋上アンテナ＆点滅ビーコン（最も高いビルのみ）
          if (px === 0.27) {
            const antTop = h * 0.76 - bh - 18;
            envCtx.strokeStyle = 'rgba(0, 229, 255, 0.7)';
            envCtx.lineWidth = 2;
            envCtx.beginPath();
            envCtx.moveTo(bx + bw / 2, h * 0.76 - bh);
            envCtx.lineTo(bx + bw / 2, antTop);
            envCtx.stroke();
            if (Math.floor(t / 400) % 2 === 0) {
              envCtx.fillStyle = 'rgba(255, 60, 60, 0.95)';
              envCtx.beginPath();
              envCtx.arc(bx + bw / 2, antTop, 3, 0, Math.PI * 2);
              envCtx.fill();
            }
          }
        }
        // 空を走るホバー車の光跡（流れるテールライト）
        const hoverY = h * 0.30;
        const hoverPhase = (t % 2600) / 2600;
        const hoverX = w * (hoverPhase * 1.3 - 0.15);
        envCtx.strokeStyle = 'rgba(0, 229, 255, 0.55)';
        envCtx.lineWidth = 2;
        envCtx.beginPath();
        envCtx.moveTo(hoverX - 26, hoverY);
        envCtx.lineTo(hoverX + 8, hoverY);
        envCtx.stroke();
        envCtx.fillStyle = 'rgba(255, 255, 255, 0.9)';
        envCtx.fillRect(hoverX + 6, hoverY - 1.5, 5, 3);
        // グリッド地面
        envCtx.strokeStyle = 'rgba(0, 229, 255, 0.3)';
        envCtx.lineWidth = 1;
        const gy = h * 0.88;
        envCtx.beginPath(); envCtx.moveTo(0, gy); envCtx.lineTo(w, gy); envCtx.stroke();
        for (let i = 0; i <= 10; i++) {
          envCtx.beginPath();
          envCtx.moveTo(w * i / 10, gy);
          envCtx.lineTo(w * (0.5 + (i / 10 - 0.5) * 2.4), h);
          envCtx.stroke();
        }
      }
    } catch (e) {
      console.error('[PetParticles] drawEnvScene error:', e);
    } finally {
      envCtx.restore();
    }
  }

  /**
   * 天候エフェクト（雨・雪・雷・落ち葉）をパーティクルとして生成
   */
  function spawnWeatherParticles() {
    if (!envCanvas) return;
    const w = envCanvas.width;
    const weather = (typeof window.currentWeather !== 'undefined') ? window.currentWeather : 'sunny';

    if (weather === 'rainy') {
      // 斜めに降る雨粒
      for (let i = 0; i < 3; i++) {
        envParticles.push({
          x: Math.random() * w,
          y: -10,
          vx: -1.2,
          vy: Math.random() * 4 + 7,
          size: Math.random() * 6 + 6,
          color: 'rgba(144, 202, 249, 0.45)',
          alpha: 0.9,
          decay: 0.02,
          isRain: true
        });
      }
    } else if (weather === 'snowy') {
      // ゆらゆら舞い落ちる雪
      if (Math.random() < 0.5) {
        envParticles.push({
          x: Math.random() * w,
          y: -8,
          vx: Math.sin(Date.now() * 0.001) * 0.6,
          vy: Math.random() * 0.8 + 0.6,
          size: Math.random() * 2.2 + 1.2,
          color: 'rgba(255, 255, 255, 0.85)',
          alpha: 0.95,
          decay: 0.003
        });
      }
    } else if (weather === 'thunder') {
      // 強い雨
      for (let i = 0; i < 5; i++) {
        envParticles.push({
          x: Math.random() * w,
          y: -10,
          vx: -2.0,
          vy: Math.random() * 5 + 9,
          size: Math.random() * 6 + 7,
          color: 'rgba(129, 212, 250, 0.55)',
          alpha: 0.95,
          decay: 0.02,
          isRain: true
        });
      }
      // 稲妻フラッシュ（画面全体を一瞬明るく）
      if (Math.random() < 0.004 && envCtx) {
        envCtx.fillStyle = 'rgba(255, 255, 220, 0.35)';
        envCtx.fillRect(0, 0, envCanvas.width, envCanvas.height);
      }
    } else if (weather === 'cloudy' && Math.random() < 0.15) {
      // 曇りの日はたまに落ち葉
      envParticles.push({
        x: Math.random() * w,
        y: -8,
        vx: Math.sin(Date.now() * 0.002) * 1.0,
        vy: Math.random() * 0.9 + 0.5,
        size: Math.random() * 3 + 2,
        color: 'rgba(161, 136, 90, 0.55)',
        alpha: 0.85,
        decay: 0.004
      });
    }
  }

  let isParticleLoopRunning = false;
  let animFrameId = null;

  /**
   * ループが停止している場合にのみ requestAnimationFrame を叩き起こす (Wake-on-Demand)
   */
  function wakeParticleLoop() {
    if (typeof document !== 'undefined' && document.hidden) {
      return; // 画面非表示時は叩き起こさない（省電力優先）
    }
    if (!isParticleLoopRunning) {
      isParticleLoopRunning = true;
      animFrameId = requestAnimationFrame(particleLoop);
    }
  }

  /**
   * アニメーションループを明示的に即時停止し保留フレームを完全破棄 (0fps化・省電力)
   */
  function stopParticleLoop() {
    if (animFrameId !== null) {
      if (typeof cancelAnimationFrame === 'function') {
        cancelAnimationFrame(animFrameId);
      }
      animFrameId = null;
    }
    isParticleLoopRunning = false;
  }

  /**
   * なでなでパーティクル（ハート・星・音符等）の湧き出し生成
   * @param {number} cx 中心X座標
   * @param {number} cy 中心Y座標
   * @param {number} count 生成個数（デフォルト 7個）
   */
  function spawnTouchParticles(cx, cy, count = 7) {
    wakeParticleLoop();
    const emojis = ['💖', '✨', '🌟', '🐾', '🥰', '🎶', '⭐'];
    for (let i = 0; i < count; i++) {
      touchParticles.push({
        x: cx + (Math.random() - 0.5) * 40,
        y: cy + (Math.random() - 0.5) * 40,
        vx: (Math.random() - 0.5) * 3,
        vy: -Math.random() * 3 - 1.5,
        gravity: 0.04,
        size: 18,
        scale: 1.0,
        alpha: 1.0,
        emoji: emojis[Math.floor(Math.random() * emojis.length)]
      });
    }
  }

  /**
   * 歓喜セレブレーション紙吹雪（Confetti）大噴射（重力放物線シミュレーション）
   * @param {number} cx 中心X座標
   * @param {number} cy 中心Y座標
   * @param {number} count 噴射個数（デフォルト 18個）
   */
  function spawnCelebrationConfetti(cx, cy, count = 18) {
    wakeParticleLoop();
    const celebrationEmojis = ['🎉', '✨', '🌟', '💖', '🎊', '👏', '⭐', '🎈'];
    for (let i = 0; i < count; i++) {
      setTimeout(() => {
        const angle = (Math.random() * Math.PI * 1.4) - (Math.PI * 0.7); // 上方向扇状
        const speed = Math.random() * 5 + 3.5;
        touchParticles.push({
          x: cx + (Math.random() - 0.5) * 50,
          y: cy + (Math.random() - 0.5) * 20,
          vx: Math.sin(angle) * speed,
          vy: -Math.cos(angle) * speed - 2.5,
          gravity: 0.14, // 向上した情緒物理: 放物線を描いて舞い散る重力加速度
          size: 20 + Math.random() * 8,
          scale: 1.0,
          alpha: 1.0,
          emoji: celebrationEmojis[Math.floor(Math.random() * celebrationEmojis.length)]
        });
      }, i * 60);
    }
  }

  /**
   * メインパーティクル描画ループ (requestAnimationFrame)
   * 🛡️ 不滅アニメーション保証: try-finally で囲み、万一の描画例外時もループ停止を100%防止
   */
  function particleLoop() {
    // 🛡️ 画面非表示時（バックグラウンド/スリープ）はループを安全に停止（0fps化・省電力）
    if (typeof document !== 'undefined' && document.hidden) {
      stopParticleLoop();
      return;
    }
    isParticleLoopRunning = true;
    try {
      if (envCtx && envCanvas) {
        envCtx.clearRect(0, 0, envCanvas.width, envCanvas.height);

        // 🛡️ ダブルバッファリング: プリレンダリング済み背景を1回のdrawImageで高速転送（チラつき・フリッカー完全根絶）
        if (!bgCacheCanvas || bgNeedsRedraw) {
          updateBgCache();
        }
        if (bgCacheCanvas) {
          envCtx.drawImage(bgCacheCanvas, 0, 0);
        } else {
          drawEnvScene();
        }

        // 天候エフェクト（雨・雪・雷・落ち葉）を生成
        spawnWeatherParticles();

        const theme = ENV_THEMES[currentEnvIndex].id;

        // 1. 環境ごとのアンビエントパーティクル生成
        if (Math.random() < 0.25) {
          if (theme === 'room') {
            // 暖炉の温かい光の粉
            envParticles.push({
              x: Math.random() * envCanvas.width,
              y: envCanvas.height + 10,
              vx: (Math.random() - 0.5) * 0.4,
              vy: -Math.random() * 0.8 - 0.3,
              size: Math.random() * 2.5 + 1,
              color: 'rgba(255, 184, 0, 0.4)',
              alpha: 1,
              decay: 0.005
            });
          } else if (theme === 'cafe') {
            // 雨粒
            envParticles.push({
              x: Math.random() * envCanvas.width,
              y: -10,
              vx: -0.5,
              vy: Math.random() * 3 + 4,
              size: Math.random() * 1.5 + 0.5,
              color: 'rgba(180, 210, 240, 0.3)',
              alpha: 0.8,
              decay: 0.015
            });
          } else if (theme === 'forest') {
            // 舞い落ちる木漏れ日・胞子
            envParticles.push({
              x: Math.random() * envCanvas.width,
              y: -10,
              vx: Math.sin(Date.now() * 0.002) * 0.8,
              vy: Math.random() * 0.6 + 0.3,
              size: Math.random() * 3 + 1,
              color: 'rgba(120, 230, 160, 0.35)',
              alpha: 1,
              decay: 0.004
            });
          } else if (theme === 'ocean') {
            // 水中の泡
            envParticles.push({
              x: Math.random() * envCanvas.width,
              y: envCanvas.height + 10,
              vx: (Math.random() - 0.5) * 0.6,
              vy: -Math.random() * 1.2 - 0.5,
              size: Math.random() * 3.5 + 1.5,
              color: 'rgba(100, 220, 255, 0.35)',
              alpha: 1,
              decay: 0.006
            });
          } else if (theme === 'cyber') {
            // ネオンデータグリッド光
            envParticles.push({
              x: Math.random() * envCanvas.width,
              y: Math.random() * envCanvas.height,
              vx: (Math.random() - 0.5) * 1.5,
              vy: (Math.random() - 0.5) * 1.5,
              size: Math.random() * 2 + 1,
              color: Math.random() > 0.5 ? 'rgba(0, 229, 255, 0.6)' : 'rgba(255, 23, 68, 0.6)',
              alpha: 1,
              decay: 0.02
            });
          }
        }

        // 環境パーティクル描画＆更新
        for (let i = envParticles.length - 1; i >= 0; i--) {
          const p = envParticles[i];
          p.x += p.vx;
          p.y += p.vy;
          p.alpha -= p.decay;

          if (p.alpha <= 0 || p.y < -20 || p.y > envCanvas.height + 20) {
            envParticles.splice(i, 1);
            continue;
          }

          envCtx.fillStyle = p.color;
          envCtx.globalAlpha = Math.max(0, p.alpha);
          envCtx.beginPath();
          envCtx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
          envCtx.fill();
        }

        // 2. タップ・なでなで・紙吹雪パーティクルの描画
        for (let i = touchParticles.length - 1; i >= 0; i--) {
          const tp = touchParticles[i];
          tp.x += tp.vx;
          tp.y += tp.vy;
          if (tp.gravity) {
            tp.vy += tp.gravity; // 重力加速度の適用（放物線）
          }
          tp.alpha -= 0.025;
          tp.scale += 0.02;

          if (tp.alpha <= 0) {
            touchParticles.splice(i, 1);
            continue;
          }

          envCtx.save();
          envCtx.globalAlpha = Math.max(0, tp.alpha);
          envCtx.font = `${Math.floor(tp.size * tp.scale)}px sans-serif`;
          envCtx.textAlign = 'center';
          envCtx.textBaseline = 'middle';
          envCtx.fillText(tp.emoji, tp.x, tp.y);
          envCtx.restore();
        }
        envCtx.globalAlpha = 1.0;
      }
    } catch (err) {
      console.error('[PetParticles] Loop error:', err);
    } finally {
      if (typeof document === 'undefined' || !document.hidden) {
        isParticleLoopRunning = true;
        animFrameId = requestAnimationFrame(particleLoop);
      } else {
        stopParticleLoop();
      }
    }
  }

  // グローバル双方向同期: window.currentEnvIndex への代入で setEnvTheme を自動発火
  if (typeof window !== 'undefined') {
    try {
      Object.defineProperty(window, 'currentEnvIndex', {
        get: () => currentEnvIndex,
        set: (v) => { setEnvTheme(v); },
        configurable: true
      });
    } catch (e) {
      window.currentEnvIndex = currentEnvIndex;
    }
  }

  // 🛡️ Page Visibility API 連動: 画面復帰時にループ再開、画面非表示時は即時破棄 (0fps化)
  if (typeof document !== 'undefined' && typeof document.addEventListener === 'function') {
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        stopParticleLoop();
      } else {
        wakeParticleLoop();
      }
    });
  }

  // グローバル公開
  if (typeof window !== 'undefined') {
    window.ENV_THEMES = ENV_THEMES;
    window.envParticles = envParticles;
    window.touchParticles = touchParticles;
    window.envCanvas = envCanvas;
    window.envCtx = envCtx;
    window.initEnvCanvas = initEnvCanvas;
    window.setEnvTheme = setEnvTheme;
    window.drawEnvScene = drawEnvScene;
    window.spawnWeatherParticles = spawnWeatherParticles;
    window.spawnTouchParticles = spawnTouchParticles;
    window.spawnCelebrationConfetti = spawnCelebrationConfetti;
    window.particleLoop = particleLoop;
    window.wakeParticleLoop = wakeParticleLoop;
    window.stopParticleLoop = stopParticleLoop;
    window.cycleEnvTheme = cycleEnvTheme;
  }
})();

// 非モジュール環境での直接呼び出し互換用トップレベルバインド (SSR/Node例外安全)
var ENV_THEMES = typeof window !== 'undefined' ? window.ENV_THEMES : undefined;
var currentEnvIndex = typeof window !== 'undefined' ? window.currentEnvIndex : 0;
var envParticles = typeof window !== 'undefined' ? window.envParticles : [];
var touchParticles = typeof window !== 'undefined' ? window.touchParticles : [];
var envCanvas = typeof window !== 'undefined' ? window.envCanvas : null;
var envCtx = typeof window !== 'undefined' ? window.envCtx : null;
var initEnvCanvas = typeof window !== 'undefined' ? window.initEnvCanvas : undefined;
var setEnvTheme = typeof window !== 'undefined' ? window.setEnvTheme : undefined;
var drawEnvScene = typeof window !== 'undefined' ? window.drawEnvScene : undefined;
var spawnWeatherParticles = typeof window !== 'undefined' ? window.spawnWeatherParticles : undefined;
var spawnTouchParticles = typeof window !== 'undefined' ? window.spawnTouchParticles : undefined;
var spawnCelebrationConfetti = typeof window !== 'undefined' ? window.spawnCelebrationConfetti : undefined;
var particleLoop = typeof window !== 'undefined' ? window.particleLoop : undefined;
var wakeParticleLoop = typeof window !== 'undefined' ? window.wakeParticleLoop : undefined;
var stopParticleLoop = typeof window !== 'undefined' ? window.stopParticleLoop : undefined;
var cycleEnvTheme = typeof window !== 'undefined' ? window.cycleEnvTheme : undefined;
