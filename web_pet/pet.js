/**
 * ネオ秘書くん Desk Pet ＆ Agent Bridge Cockpit ロジック (pet.js v7.3 - Voice Edition)
 * 5大背景環境 ＆ Glass Bottom Sheetニュースリーダー ＆ なでなでパーティクル
 */

// 🧹 古いPWA/ブラウザキャッシュを安全に自動パージ
if ('caches' in window) {
  caches.keys().then(keys => {
    keys.forEach(key => {
      if (key !== 'neo-pet-v5.25') caches.delete(key);
    });
  });
}

// 🎙️ 音声入力フィーチャーフラグ (B20 内部課題)
// 実機マイクでの文字起こし品質が実用基準を満たすまで表には出さない。
// 解放条件 (仕様確定済み):
//   1. 実機での文字起こし品質検証に合格すること (合成音声E2Eは合格済み・実機ノイズ下で未合格)
//   2. 解放時は上部バーの小さな 🎤 ボタンを廃止し、キャラエリア直下の大型マイクボタンへ移設すること
const VOICE_INPUT_ENABLED = false;

let fetchFailCount = 0;
const FETCH_BACKOFF_THRESHOLD = 3;  // 連続3回失敗でバックオフ
const FETCH_NORMAL_INTERVAL = 2000;
const FETCH_BACKOFF_INTERVAL = 30000;
let fetchBackoffActive = false;
let animTick = 0;
let tasksData = [];
let eventsData = [];
let habitsData = [];
let suggestionsData = [];
let suggestConfig = {};
let suggestIndex = 0;
let currentApprovalRequest = null;
let currentActiveEvent = null;
let currentPomodoro = { active: false, is_break: false, remaining_seconds: 0, mode_label: "" };
let petStateNow = 'idle';
// 歩行フレーム(walk_1/2)を持つキャラ（未保有キャラは歩行中も idle フレームで代用）
const WALK_CAPABLE_CHARS = ['kyle'];
let wakeLock = null;
let currentCharacterId = 'hisho';

// 🌈 自律生活ドリーマー状態（/api/status の life_state から更新）
const WEATHER_LABELS_JS = {
  sunny: '☀️ 晴れ', cloudy: '☁️ 曇り', rainy: '🌧️ 雨',
  snowy: '❄️ 雪', thunder: '⚡ 嵐'
};
let currentWeather = 'sunny';
let currentActivity = 'resting';
let lastLifeMessage = '';

// 🤖 AIエージェント稼働ライブバッジ (Phase H) — 表示中キーのキャッシュ。
// ⚠️ 本変数は本ファイル内でこの1箇所でのみ宣言すること (重複宣言はTDZ SyntaxErrorで全停止)。
let currentAgentBadgeState = '';

// =============================================================================
// 🔐 同期サーバー認証トークン管理 (Zero-Trust Bearer Auth)
// =============================================================================
// PC側の .sync_token と一致するトークンを localStorage に保持し、
// 全APIリクエストに Authorization: Bearer ヘッダーで添付する。
const SYNC_TOKEN_KEY = 'neo_hisho_sync_token';
let syncToken = '';

function loadSyncToken() {
  const urlParams = new URLSearchParams(window.location.search);
  const paramToken = urlParams.get('token');
  if (paramToken) {
    syncToken = paramToken;
    localStorage.setItem(SYNC_TOKEN_KEY, syncToken);
    return;
  }
  syncToken = localStorage.getItem(SYNC_TOKEN_KEY) || '';
}
loadSyncToken();

/**
 * 認証済みfetchラッパー。全API呼び出しはこれを経由すること。
 * 401応答時はトークンを自動取得して1回だけ再試行する。
 */
async function authFetch(url, options = {}) {
  const headers = Object.assign({}, options.headers || {});
  if (syncToken) {
    headers['Authorization'] = `Bearer ${syncToken}`;
  }
  if (options.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
  let res = await fetch(url, Object.assign({}, options, { headers }));
  if (res.status === 401 && !options._retried) {
    // トークン未取得・失効の可能性 → /api/auth/token で再取得して1回だけ再試行
    try {
      const tokenRes = await fetch('/api/auth/token');
      if (tokenRes.ok) {
        const tokenData = await tokenRes.json();
        if (tokenData.token) {
          syncToken = tokenData.token;
          localStorage.setItem(SYNC_TOKEN_KEY, syncToken);
          return authFetch(url, Object.assign({}, options, { _retried: true }));
        }
      }
    } catch (e) {
      console.debug('Token refresh error:', e);
    }
  }
  return res;
}

// 5大背景テーマ定義
const ENV_THEMES = [
  { id: 'room', label: '書斎', class: 'theme-room' },
  { id: 'cafe', label: 'カフェ', class: 'theme-cafe' },
  { id: 'forest', label: '森', class: 'theme-forest' },
  { id: 'ocean', label: '海', class: 'theme-ocean' },
  { id: 'cyber', label: 'サイバー', class: 'theme-cyber' }
];
let currentEnvIndex = 0;

// パーティクル管理
let envParticles = [];
let touchParticles = [];
let envCanvas = null;
let envCtx = null;

// =============================================================================
// 1. 初期化 ＆ Canvas パーティクルループ
// =============================================================================
function initEnvCanvas() {
  envCanvas = document.getElementById('env-canvas');
  if (envCanvas) {
    envCanvas.width = window.innerWidth;
    envCanvas.height = window.innerHeight;
    envCtx = envCanvas.getContext('2d');
  }
}
window.addEventListener('resize', initEnvCanvas);
window.addEventListener('DOMContentLoaded', () => {
  initEnvCanvas();
  loadSyncToken();
  unlockAudio();
  setupMediaKeyApproval();
  setupBannerSwipe();
  updateBriefingBannerText();
  requestAnimationFrame(particleLoop);
  preloadSprites(currentCharacterId);
  // 🐛 バグ修正 (2026-08-31): 通知キーをsessionStorageに永続化。
  //   サーバー側TTL延長(10分)と組み合わせ、再読み込み時に既表示の通知が
  //   二重表示されるのを防止する（同一セッション内でのみ有効）。
  window._lastNotifKey = sessionStorage.getItem('lastNotifKey') || null;
  fetchStatus();
  (function pollingLoop() {
    fetchStatus();
    const nextInterval = getNextFetchInterval();
    setTimeout(pollingLoop, nextInterval);
  })();
});

// =============================================================================
// 1.5. テーマごとの背景シーン描画（本格的ピクセルアート書斎・生活空間）
// =============================================================================
function drawEnvScene() {
  if (!envCtx || !envCanvas) return;
  const w = envCanvas.width, h = envCanvas.height;
  const theme = ENV_THEMES[currentEnvIndex].id;
  const t = Date.now();
  envCtx.save();

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
  envCtx.restore();
}

// パーティクルアニメーションループ
// =============================================================================
// 天候エフェクト（雨・雪・雷・落ち葉）をパーティクルとして生成
// =============================================================================
function spawnWeatherParticles() {
  if (!envCanvas) return;
  const w = envCanvas.width;

  if (currentWeather === 'rainy') {
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
  } else if (currentWeather === 'snowy') {
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
  } else if (currentWeather === 'thunder') {
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
  } else if (currentWeather === 'cloudy' && Math.random() < 0.15) {
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

function particleLoop() {
  if (envCtx && envCanvas) {
    envCtx.clearRect(0, 0, envCanvas.width, envCanvas.height);

    // テーマごとの背景シーン（暖炉・窓・木々・波・ネオンビル等）を描画
    drawEnvScene();

    // 🌈 天候エフェクト（雨・雪・雷・落ち葉）を生成
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

    // 2. タップ・なでなでパーティクル（ハート・星）の描画
    for (let i = touchParticles.length - 1; i >= 0; i--) {
      const tp = touchParticles[i];
      tp.x += tp.vx;
      tp.y += tp.vy;
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
  requestAnimationFrame(particleLoop);
}

// =============================================================================
// 2. 背景環境の切り替え
// =============================================================================
function cycleEnvTheme() {
  currentEnvIndex = (currentEnvIndex + 1) % ENV_THEMES.length;
  const theme = ENV_THEMES[currentEnvIndex];
  
  const backdrop = document.getElementById('env-backdrop');
  if (backdrop) {
    backdrop.className = `env-backdrop ${theme.class}`;
  }
  const label = document.getElementById('env-label');
  if (label) {
    label.innerText = theme.label;
  }
  envParticles = [];
  if (navigator.vibrate) navigator.vibrate(25);

  // 切替を分かりやすくトースト通知
  showToast(`🏞️ ${theme.label}テーマに変わりました`);
}

/** 高視認性HUDトースト通知 */
let toastTimer = null;
function showToast(message, duration = 3500, isHighlight = false) {
  let toast = document.getElementById('global-hud-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'global-hud-toast';
    toast.style.cssText = `
      position: fixed;
      top: 42px;
      left: 50%;
      transform: translateX(-50%) translateY(-10px);
      background: linear-gradient(135deg, rgba(30, 20, 14, 0.97), rgba(46, 28, 20, 0.97));
      border: 2px solid var(--accent-amber);
      color: #F5F5DC;
      padding: 9px 18px;
      border-radius: 8px;
      font-family: 'DotGothic16', monospace;
      font-size: 13px;
      font-weight: bold;
      z-index: 999999;
      box-shadow: 0 8px 30px rgba(0,0,0,0.85), 0 0 15px rgba(255,184,0,0.5);
      opacity: 0;
      transition: all 0.3s cubic-bezier(0.18, 0.89, 0.32, 1.28);
      pointer-events: none;
      text-align: center;
      max-width: 90vw;
      word-break: break-word;
      line-height: 1.4;
    `;
    document.body.appendChild(toast);
  }

  if (isHighlight) {
    toast.style.borderColor = '#00E676';
    toast.style.boxShadow = '0 8px 30px rgba(0,0,0,0.85), 0 0 20px rgba(0,230,118,0.7)';
  } else {
    toast.style.borderColor = '#FFB800';
    toast.style.boxShadow = '0 8px 30px rgba(0,0,0,0.85), 0 0 15px rgba(255,184,0,0.5)';
  }

  toast.innerHTML = message;
  toast.style.opacity = '1';
  toast.style.transform = 'translateX(-50%) translateY(0)';

  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(-50%) translateY(-10px)';
  }, duration);
}

// =============================================================================
// 3. なでなでインタラクション (Spring & Haptics & Particles & Web Audio SE)
// =============================================================================
let audioCtx = null;

function getAudioContext() {
  if (!audioCtx) {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    audioCtx = new AudioContext();
  }
  if (audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  return audioCtx;
}

// =============================================================================
// 3.5. 通知チャイム ＆ オーディオアンロック（ブラウザの User Gesture Policy 対応）
// =============================================================================
let lastApprovalRequestId = null;
let lastActiveEventKey = null;
let lastReminderKey = null;
let chimeTimers = [];

/** 最初のユーザー操作で AudioContext を解錠する（モバイル自動再生制限の解除） */
function unlockAudio() {
  try {
    const ctx = getAudioContext();
    if (ctx.state === 'suspended') ctx.resume();
  } catch (e) {
    console.debug('Audio unlock error:', e);
  }
}
document.addEventListener('pointerdown', unlockAudio, { passive: true });
document.addEventListener('touchstart', unlockAudio, { passive: true });
document.addEventListener('visibilitychange', () => { if (!document.hidden) unlockAudio(); });

// 🛡 通知再表示 (2026-08-31): 画面OFF/バックグラウンド中に通知トーストが描画されると
//   音だけ鳴って表示は失われ、再読み込みするまで出ない障害の根本対策。
//   非表示中に通知を処理していた場合はキーをリセットし、復帰後の最初のポーリングで
//   サーバー (60秒TTL) から再取得・再表示させる。
document.addEventListener('visibilitychange', () => {
  if (!document.hidden && window._notifShownWhileHidden) {
    window._notifShownWhileHidden = false;
    window._lastNotifKey = null;
    if (typeof fetchStatus === 'function') fetchStatus();
  }
});

/** 2音チャイム（ピンポン）を合成する */
function playTwoTone(ctx, freqLow, freqHigh) {
  const now = ctx.currentTime;
  [[freqLow, 0.0], [freqHigh, 0.22]].forEach(([freq, offset]) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'triangle';
    osc.frequency.value = freq;
    osc.connect(gain);
    gain.connect(ctx.destination);
    gain.gain.setValueAtTime(0.0001, now + offset);
    gain.gain.exponentialRampToValueAtTime(0.4, now + offset + 0.03);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + offset + 0.55);
    osc.start(now + offset);
    osc.stop(now + offset + 0.6);
  });
}

/** 通知アラート: チャイム連打 ＆ 振動パターン（前回分タイマーを必ず解除してから鳴らす） */
function playAlertChime(repeat = 3) {
  stopAlertChime();
  unlockAudio();
  try {
    const ctx = getAudioContext();
    for (let i = 0; i < repeat; i++) {
      chimeTimers.push(setTimeout(() => {
        try { playTwoTone(ctx, 880, 1245); } catch (e) { console.debug('Chime error:', e); }
      }, i * 950));
    }
  } catch (e) {
    console.debug('AudioContext error:', e);
  }
  if (navigator.vibrate) navigator.vibrate([220, 120, 220, 120, 320]);
}

/** 通知チャイムの停止（承認済み・タイムアウト時） */
function stopAlertChime() {
  chimeTimers.forEach(t => clearTimeout(t));
  chimeTimers = [];
}

/** 承認/却下の結果を音で区別する（承認=上昇2音・却下=下降2音） */
function playDecisionSound(approved) {
  try {
    const ctx = getAudioContext();
    if (approved) {
      playTwoTone(ctx, 880, 1245);
    } else {
      playTwoTone(ctx, 660, 440);
    }
  } catch (e) {
    console.debug('Decision sound error:', e);
  }
}

function playCharacterSE(charId) {
  try {
    const ctx = getAudioContext();
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.connect(gain);
    gain.connect(ctx.destination);

    if (charId === 'hisho') {
      // 👔 秘書くん: シャキーン！高音サイン波
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, now);
      osc.frequency.exponentialRampToValueAtTime(1320, now + 0.12);
      gain.gain.setValueAtTime(0.2, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.18);
      osc.start(now);
      osc.stop(now + 0.18);
    } else if (charId === 'kinoko') {
      // 🍄 キノコ君: ポフッ！ピッチベンド
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(520, now);
      osc.frequency.exponentialRampToValueAtTime(260, now + 0.15);
      gain.gain.setValueAtTime(0.25, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.15);
      osc.start(now);
      osc.stop(now + 0.15);
    } else if (charId === 'seal') {
      // 🦭 アザラシ: モチッ！キュートな和音ピチピチ
      osc.type = 'sine';
      osc.frequency.setValueAtTime(660, now);
      osc.frequency.exponentialRampToValueAtTime(990, now + 0.1);
      gain.gain.setValueAtTime(0.22, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.14);
      osc.start(now);
      osc.stop(now + 0.14);
    } else if (charId === 'wombat') {
      // 🦫 ウォンバット: ズシッ！低音ずっしり
      osc.type = 'square';
      osc.frequency.setValueAtTime(180, now);
      osc.frequency.exponentialRampToValueAtTime(90, now + 0.18);
      gain.gain.setValueAtTime(0.18, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.18);
      osc.start(now);
      osc.stop(now + 0.18);
    } else if (charId === 'kyle') {
      // 🐚 カイル風精霊: カタッ！ピピッ！貝型PCを叩く8bit風2連音
      osc.type = 'square';
      osc.frequency.setValueAtTime(520, now);
      osc.frequency.setValueAtTime(780, now + 0.07);
      gain.gain.setValueAtTime(0.12, now);
      gain.gain.setValueAtTime(0.12, now + 0.07);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.16);
      osc.start(now);
      osc.stop(now + 0.16);
    }
  } catch (e) {
    console.debug('Audio playback error:', e);
  }
}

function onPetTap(event) {
  // 微細振動フィードバック
  if (navigator.vibrate) navigator.vibrate(30);

  // キャラ固有のSE再生
  playCharacterSE(currentCharacterId);

  // スプライトに弾力バウンスアニメーションを適用
  const sprite = document.getElementById('pet-sprite');
  if (sprite) {
    sprite.classList.remove('squashing');
    void sprite.offsetWidth; // リフロー強制
    sprite.classList.add('squashing');
    setTimeout(() => sprite.classList.remove('squashing'), 500);
  }

  // タッチ位置にハートや星をスポーン
  const rect = event.currentTarget.getBoundingClientRect();
  const clickX = (event.clientX || (event.touches && event.touches[0].clientX)) || (rect.left + rect.width / 2);
  const clickY = (event.clientY || (event.touches && event.touches[0].clientY)) || (rect.top + rect.height / 2);

  const emojis = ['💖', '✨', '🌸', '⭐', '🐾', '🥰'];
  for (let i = 0; i < 5; i++) {
    touchParticles.push({
      x: clickX + (Math.random() - 0.5) * 40,
      y: clickY + (Math.random() - 0.5) * 40,
      vx: (Math.random() - 0.5) * 3,
      vy: -Math.random() * 3 - 1.5,
      size: 18,
      scale: 1.0,
      alpha: 1.0,
      emoji: emojis[Math.floor(Math.random() * emojis.length)]
    });
  }

  // なでなでリアクション
  const bubble = document.getElementById('speech-bubble');
  if (bubble) {
    const happyReplies = [
      "えへへ〜、くすぐったいです！🥰",
      "ボスになでなでしてもらえて幸せです〜！✨",
      "もちもちパワー全開ですっ！パチパチ👏",
      "今日もボスのお仕事、全力で応援しますね！🔥"
    ];
    bubble.innerText = happyReplies[Math.floor(Math.random() * happyReplies.length)];
  }
}

// =============================================================================
// 4. キャラクター切り替え
// =============================================================================
const CHARACTERS = [
  { id: 'hisho', name: '秘書くん', emoji: '👔' },
  { id: 'kyle', name: 'カイル風精霊', emoji: '🐚' }
];

function cycleCharacter() {
  const curIdx = CHARACTERS.findIndex(c => c.id === currentCharacterId);
  const nextChar = CHARACTERS[(curIdx + 1) % CHARACTERS.length];
  currentCharacterId = nextChar.id;

  const emojiEl = document.getElementById('char-emoji');
  if (emojiEl) emojiEl.innerText = nextChar.emoji;

  preloadSprites(currentCharacterId);

  // サーバーへも切り替え通知（認証付き）
  authFetch('/api/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'switch_character', character_id: currentCharacterId })
  }).catch(err => console.debug('Action failed:', err));

  if (navigator.vibrate) navigator.vibrate(35);
}

// =============================================================================
// 5. スプライト画像プリローダー
// =============================================================================
function preloadSprites(charId) {
  const spriteEl = document.getElementById('pet-sprite');
  if (spriteEl) {
    spriteEl.onerror = null;
    spriteEl.src = `/assets/dot/${charId}/idle_1.png`;
  }
}

// 🌈 生活イベントに応じたスプライト候補（優先順）
const ACTIVITY_SPRITES = {
  waking:    ['stretch_1', 'stretch', 'happy', 'idle_1'],
  breakfast: ['tea_1', 'happy', 'idle_1'],
  lunch:     ['happy', 'care_1', 'idle_1'],
  dinner:    ['cheer', 'happy', 'idle_1'],
  bathing:   ['care_1', 'care', 'happy', 'idle_1'],
  working:   ['focus_1', 'focus', 'idle_1'],
  resting:   ['tea_1', 'tea', 'idle_1'],
  reading:   ['reading_1', 'reading', 'focus_1', 'idle_1'],
  sleeping:  ['sleepy_1', 'sleepy', 'idle_1'],
  playing:   ['celebrate_1', 'celebrate', 'cheer', 'idle_1']
};

// ※ currentActivity はファイル先頭で一度だけ宣言済み（旧ブロックとの重複宣言を統合して削除）

/**
 * 生活イベントに応じてペットのスプライトを差し替える。
 * dot/{char}/{name}.png を最優先し、無ければ自キャラの idle_1 で安定させる。
 */
function updateLifeSprite(activity) {
  const spriteEl = document.getElementById('pet-sprite');
  if (!spriteEl) return;
  const candidates = ACTIVITY_SPRITES[activity] || ['idle_1'];
  
  // 自キャラの dot 配下の候補URLのみを生成
  const urls = candidates.map(name => `/assets/dot/${currentCharacterId}/${name}.png`);
  urls.push(`/assets/dot/${currentCharacterId}/idle_1.png`);

  let idx = 0;
  spriteEl.onerror = () => {
    idx += 1;
    if (idx < urls.length) {
      spriteEl.src = urls[idx];
    } else {
      spriteEl.onerror = null; // 最終フォールバックで停止
      spriteEl.src = `/assets/dot/${currentCharacterId}/idle_1.png`;
    }
  };
  spriteEl.src = urls[0];

  // キャラ本来の鮮やかなドット絵を保つ（不自然な暗色フィルターは撤廃）
  spriteEl.style.filter = '';
}

/**
 * 時間帯およびランダム気まぐれ行動によるペットの生活サイクル自動更新
 */
function updatePetLifeActivity(forcedActivity = null) {
  const now = new Date();
  const hour = now.getHours();
  const min = now.getMinutes();

  let act = 'working';
  let dialog = 'カタカタ…集中してお手伝い中！';

  if (hour >= 23 || hour < 6) {
    act = 'sleeping';
    dialog = 'すやすや…ボス、良い夢を…💤';
  } else if (hour >= 6 && hour < 8) {
    act = 'breakfast';
    dialog = 'おはようございます！朝ごはん美味しいです🍞';
  } else if (hour >= 11 && hour < 13 && min >= 30 || hour === 12) {
    act = 'lunch';
    dialog = 'もぐもぐ…お昼ごはんの時間ですね🍱';
  } else if (hour === 15) {
    act = 'resting';
    dialog = 'ほっと一息、お茶とお菓子タイムです🍵';
  } else if (hour >= 16 && hour < 18) {
    act = 'reading';
    dialog = 'ふむふむ…新しい技術や本を読んで勉強中📖';
  } else if (hour >= 18 && hour < 20) {
    act = 'dinner';
    dialog = '今日もお疲れ様でした！美味しい晩ごはんです🍚';
  } else if (hour >= 20 && hour < 22) {
    act = 'bathing';
    dialog = 'いい湯だな〜♪さっぱりリフレッシュ🛁';
  } else {
    const randomActs = [
      { act: 'working', msg: 'カタカタ…集中してお手伝い中！' },
      { act: 'reading', msg: '仕様書やニュースをチェック中📖' },
      { act: 'resting', msg: '深呼吸してストレッチ〜✨' },
      { act: 'playing', msg: 'ボスと一緒にいられて嬉しいです♪' }
    ];
    const pick = randomActs[Math.floor(Math.random() * randomActs.length)];
    act = pick.act;
    dialog = pick.msg;
  }

  if (forcedActivity) act = forcedActivity;

  currentActivity = act;
  updateLifeSprite(act);

  const bubble = document.getElementById('speech-bubble');
  if (bubble && (!petStateNow || petStateNow === 'idle')) {
    bubble.innerText = dialog;
  }
}

// 45秒ごとに生活リズムを自律更新
setInterval(() => {
  if (!currentPomodoro || !currentPomodoro.active) {
    updatePetLifeActivity();
  }
}, 45000);

// =============================================================================
// 6. サジェスト表示 ＆ Glass Bottom Sheet ニュースリーダー ＆ 手動スワイプ
// =============================================================================
let currentSheetItem = null;

function renderSuggestionCard() {
  if (!suggestionsData || suggestionsData.length === 0) {
    const titleEl = document.getElementById('suggest-title');
    const descEl = document.getElementById('suggest-desc');
    const tagEl = document.getElementById('suggest-tag');
    const qBtn = document.getElementById('suggest-quick-complete-btn');
    if (titleEl) titleEl.innerText = "予定・タスクはありません";
    if (descEl) descEl.innerText = "ゆっくりお茶でも飲んで休みましょう🍵";
    if (tagEl) tagEl.innerText = "💡 サジェスト";
    if (qBtn) qBtn.style.display = 'none';
    return;
  }

  suggestIndex = (suggestIndex + suggestionsData.length) % suggestionsData.length;
  const s = suggestionsData[suggestIndex];
  const total = suggestionsData.length;
  const curr = suggestIndex + 1;
  const icon = s.icon || "💡";
  const tag = s.tag || "サジェスト";

  const tagEl = document.getElementById('suggest-tag');
  if (tagEl) tagEl.innerText = `${icon} ${tag} (${curr}/${total})`;
  
  const titleEl = document.getElementById('suggest-title');
  if (titleEl) titleEl.innerText = s.title || "";
  
  const descEl = document.getElementById('suggest-desc');
  if (descEl) descEl.innerText = s.description || "";

  // サジェストヘッダーの「✅ 完了」クイックボタン表示制御
  const qBtn = document.getElementById('suggest-quick-complete-btn');
  if (qBtn) {
    if (s && s.source === 'tasks' && s.id && s.id.startsWith('task_')) {
      qBtn.style.display = 'inline-flex';
    } else {
      qBtn.style.display = 'none';
    }
  }
}

function nextSuggest(e) {
  if (e) e.stopPropagation();
  if (!suggestionsData || suggestionsData.length === 0) return;
  suggestIndex = (suggestIndex + 1) % suggestionsData.length;
  renderSuggestionCard();
  if (navigator.vibrate) navigator.vibrate(15);
}

function prevSuggest(e) {
  if (e) e.stopPropagation();
  if (!suggestionsData || suggestionsData.length === 0) return;
  suggestIndex = (suggestIndex - 1 + suggestionsData.length) % suggestionsData.length;
  renderSuggestionCard();
  if (navigator.vibrate) navigator.vibrate(15);
}

function onSuggestCardClick() {
  if (!suggestionsData || suggestionsData.length === 0) return;
  const s = suggestionsData[suggestIndex];
  if (!s) return;

  openBottomSheet(s);
}

// サジェストカードから直接ワンタップでTODOを完了する (Bearer認証対応)
async function quickCompleteCurrentTask(e) {
  if (e) e.stopPropagation();
  if (!suggestionsData || suggestionsData.length === 0) return;
  const s = suggestionsData[suggestIndex];
  if (!s || !s.id || !s.id.startsWith('task_')) return;
  const taskId = s.id.replace('task_', '');

  try {
    const res = await authFetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'complete_task', task_id: taskId })
    });
    const result = await res.json();
    if (result.status === 'success') {
      showToast('✅ タスクを完了しました！', 2500, true);
      if (typeof addBondExp === 'function') addBondExp(15);
      updateLifeSprite('playing');
      setTimeout(fetchStatus, 300);
    } else {
      showToast('❌ 完了に失敗しました', 2000, false);
    }
  } catch (e) {
    console.error('Quick complete error:', e);
    showToast('❌ 通信エラーが発生しました', 2000, false);
  }
}

function openBottomSheet(item, bodyHtml) {
  const sheet = document.getElementById('bottom-sheet');
  const overlay = document.getElementById('bottom-sheet-overlay');
  if (!sheet || !overlay) return;

  currentSheetItem = item;

  document.getElementById('sheet-tag').innerText = `${item.icon || '💡'} ${item.tag || '詳細'}`;
  document.getElementById('sheet-title').innerText = item.title || "";

  const bodyEl = document.getElementById('sheet-body');
  if (typeof bodyHtml === 'string') {
    bodyEl.innerHTML = bodyHtml;
    bodyEl.style.maxHeight = '60vh';
  } else {
    bodyEl.innerText = item.description || "詳細情報はありません。";
  }

  // TODO完了ボタンの制御
  const completeBtn = document.getElementById('sheet-complete-btn');
  if (completeBtn) {
    if (item && item.source === 'tasks' && item.id && item.id.startsWith('task_')) {
      completeBtn.style.display = 'flex';
    } else {
      completeBtn.style.display = 'none';
    }
  }

  // URL抽出
  const matchUrl = item.description ? item.description.match(/https?:\/\/[^\s)\]"'>]+/)?.[0] : null;
  const targetUrl = typeof bodyHtml === 'string' ? null : (item.link || item.url || matchUrl);

  const linkBtn = document.getElementById('sheet-link-btn');
  if (linkBtn) {
    if (targetUrl) {
      linkBtn.style.display = 'flex';
      linkBtn.href = targetUrl;
    } else {
      linkBtn.style.display = 'none';
    }
  }

  overlay.classList.add('open');
  sheet.classList.add('open');
  if (navigator.vibrate) navigator.vibrate(20);
}

async function onSheetCompleteTask() {
  if (!currentSheetItem || !currentSheetItem.id) return;
  const taskId = currentSheetItem.id.replace('task_', '');
  if (!taskId) return;

  try {
    const res = await authFetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'complete_task', task_id: taskId })
    });
    const result = await res.json();
    if (result.status === 'success') {
      closeBottomSheet();
      showToast('✅ タスクを完了しました！', 2500, true);
      if (typeof addBondExp === 'function') addBondExp(15);
      updateLifeSprite('playing');
      fetchStatus();
    } else {
      showToast('❌ タスク完了に失敗しました', 2000, false);
    }
  } catch (e) {
    console.error('Task complete error:', e);
    showToast('❌ 通信エラーが発生しました', 2000, false);
  }
}

function closeBottomSheet() {
  const sheet = document.getElementById('bottom-sheet');
  const overlay = document.getElementById('bottom-sheet-overlay');
  if (sheet) sheet.classList.remove('open');
  if (overlay) overlay.classList.remove('open');
  currentSheetItem = null;
}

// 👾 秘密の部屋（サークル暗転トランジション）
// 旧マリオ風のアイリスアウト: タップ位置を中心に世界が一点へ吸い込まれ、
// ゲームがその点から展開される。.iris-hole（透明な穴＋巨大な黒い影）の
// width/height を縮小/拡大する方式。穴が 0 になった最終フレームで黒影
// (120vmax) が単体で画面を完全に覆うため「全面黒」が幾何学的に保証される。
// （transform: scale は黒影の外周まで縮めてしまい全面黒にならないため廃止）
function triggerSecretRoomIris(e) {
  if (e) e.stopPropagation();
  const overlay = document.getElementById('iris-transition-overlay');
  const hole = overlay ? overlay.querySelector('.iris-hole') : null;

  // オーバーレイが無い環境では演出をスキップして直接ゲームを起動
  if (!overlay || !hole) {
    if (window.PixelDefense) window.PixelDefense.show();
    return;
  }

  // 演出中の再入防止（連続タップでタイマーが多重化するのを防ぐ）
  if (overlay.style.display === 'block') return;

  // タップ位置（%指定。タップ座標が取れない場合は右上のバッジ位置を使用）
  let x = 85;
  let y = 15;
  if (e && typeof e.clientX === 'number' && typeof e.clientY === 'number') {
    x = (e.clientX / window.innerWidth) * 100;
    y = (e.clientY / window.innerHeight) * 100;
  }
  overlay.style.setProperty('--iris-x', `${x.toFixed(1)}%`);
  overlay.style.setProperty('--iris-y', `${y.toFixed(1)}%`);
  if (navigator.vibrate) navigator.vibrate(30);

  // 1) 「穴=全画面（透過）」の初期状態で一度描画を確定させてから
  // 2) closing クラスで穴を点まで縮小（吸い込み）。
  //    display:none → block とクラス変更を同フレームで行うと遷移が
  //    発火しないため、ダブル requestAnimationFrame で分離する。
  overlay.className = 'iris-transition-overlay';
  overlay.style.display = 'block';

  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      overlay.className = 'iris-transition-overlay closing';

      // 3) 400ms後: ゲーム起動 → opening クラスで穴を広げ（アイリスイン）、
      //    完了後にオーバーレイを必ず非表示へ戻す（残渣による画面封鎖防止）
      setTimeout(() => {
        try {
          if (window.PixelDefense) {
            window.PixelDefense.show();
          } else {
            showToast('👾 秘密の部屋を起動中...', 2000, true);
          }
        } finally {
          overlay.className = 'iris-transition-overlay opening';
          setTimeout(() => {
            overlay.className = 'iris-transition-overlay';
            overlay.style.display = 'none';
          }, 450);
        }
      }, 400);
    });
  });
}

// サジェストカードのタッチスワイプ（左右フリック）機能
function setupSuggestSwipe() {
  const card = document.getElementById('suggest-card');
  if (!card) return;

  let startX = 0;
  let startY = 0;
  let isSwiping = false;

  card.addEventListener('touchstart', (e) => {
    // 内部ボタンタップ時はスワイプ判定をスキップ
    if (e.target.closest('.btn-suggest-nav') || e.target.closest('.btn-suggest-quick-complete')) {
      return;
    }
    if (e.touches.length === 1) {
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
      isSwiping = true;
    }
  }, { passive: true });

  card.addEventListener('touchend', (e) => {
    if (!isSwiping) return;
    isSwiping = false;
    if (e.changedTouches.length === 1) {
      const diffX = e.changedTouches[0].clientX - startX;
      const diffY = e.changedTouches[0].clientY - startY;
      
      // 水平方向のスワイプ判定（縦スクロールと分離：|diffX| > |diffY| かつ 25px 以上）
      if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 25) {
        if (diffX < 0) {
          nextSuggest();
        } else {
          prevSuggest();
        }
      }
    }
  }, { passive: true });
}

// グローバルスコープへの関数エクスポート（HTML onclick からの完全呼び出し保証）
window.prevSuggest = prevSuggest;
window.nextSuggest = nextSuggest;
window.quickCompleteCurrentTask = quickCompleteCurrentTask;
window.onSheetCompleteTask = onSheetCompleteTask;
window.closeBottomSheet = closeBottomSheet;
window.onSuggestCardClick = onSuggestCardClick;
window.triggerSecretRoomIris = triggerSecretRoomIris;

// 初期化時にスワイプと生活リズムを起動
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    setupSuggestSwipe();
    updatePetLifeActivity();
  });
} else {
  setupSuggestSwipe();
  updatePetLifeActivity();
}

// 20秒ごとにサジェスト自動ローテーション
setInterval(() => {
  if (suggestionsData.length > 1) {
    suggestIndex++;
    renderSuggestionCard();
  }
}, 20000);

// =============================================================================
// 7. 時計 ＆ ポモドーロ
// =============================================================================
function updateClock() {
  const now = new Date();
  const h = String(now.getHours()).padStart(2, '0');
  const m = String(now.getMinutes()).padStart(2, '0');
  const s = String(now.getSeconds()).padStart(2, '0');
  const clockEl = document.getElementById('clock-display');
  if (clockEl) clockEl.innerText = `${h}:${m}:${s}`;
}
setInterval(updateClock, 1000);
updateClock();

function togglePomodoro() {
  // トグル動作: 実行中なら停止(stop_pomodoro)、停止中なら開始(start_pomodoro)
  const isActive = currentPomodoro && currentPomodoro.active;
  const payload = isActive
    ? { action: 'stop_pomodoro' }
    : { action: 'start_pomodoro', minutes: 25 };
  authFetch('/api/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).then(fetchStatus).catch(err => console.debug('Pomodoro action failed:', err));
  if (navigator.vibrate) navigator.vibrate(40);
}

// =============================================================================
// 8. サーバー状態フェッチ ＆ イベント監視
// =============================================================================
// 🤖 エージェント状態 ➔ ライブバッジ演出マッピング (Phase H)
const AGENT_BADGE_STYLES = {
  coding:           { cls: 'a-coding',   icon: '🟢', suffix: 'Coding... 🔥' },
  thinking:         { cls: 'a-thinking', icon: '🟡', suffix: 'Thinking... 🤔' },
  waiting_approval: { cls: 'a-waiting',  icon: '🟣', suffix: 'Waiting Approval 🚨' },
  success:          { cls: 'a-success',  icon: '✅', suffix: 'Done ✨' }
};

/**
 * /api/status の agent_activity を受けて、時計直下のライブバッジを更新する。
 * エージェントが非アクティブ (idle / TTL切れ) の場合はバッジを隠す。
 * @param {Object|null} activity - payload.agent_activity
 */
function updateAgentActivityBadge(activity) {
  const badge = document.getElementById('agent-live-badge');
  if (!badge) return;
  const isActive = !!(activity && activity.is_active);
  const state = isActive ? String(activity.state || '') : '';
  const conf = AGENT_BADGE_STYLES[state];
  if (!isActive || !conf) {
    if (badge.style.display !== 'none') {
      badge.style.display = 'none';
      currentAgentBadgeState = '';
    }
    return;
  }
  const agentName = String(activity.agent_name || 'AI Agent').trim() || 'AI Agent';
  const stateKey = state + ':' + agentName;
  if (currentAgentBadgeState === stateKey) return; // 同一状態の再描画は抑制
  currentAgentBadgeState = stateKey;
  const textEl = document.getElementById('agent-live-badge-text');
  if (textEl) textEl.innerText = conf.icon + ' [' + agentName + '] ' + conf.suffix;
  badge.className = 'agent-live-badge ' + conf.cls;
  badge.style.display = 'flex';
}

async function fetchStatus() {
  try {
    const res = await authFetch('/api/status');
    if (!res.ok) return;
    const data = await res.json();

    // 成功時はバックオフを即座に解除
    if (fetchBackoffActive || fetchFailCount > 0) {
      fetchFailCount = 0;
      fetchBackoffActive = false;
    }

    // 🔐 トークン自動同期（自己治癒）
    if (data.sync_token && data.sync_token !== syncToken) {
      syncToken = data.sync_token;
      localStorage.setItem(SYNC_TOKEN_KEY, syncToken);
    }

    // 0. ペット状態（歩行コントローラーのガード用）
    petStateNow = data.pet_state || 'idle';

    // 0.5 🤖 AIエージェント稼働ライブバッジ (Phase H: agent_activity 連動)
    updateAgentActivityBadge(data.agent_activity);

    // 1. メッセージ
    if (data.message) {
      const bubble = document.getElementById('speech-bubble');
      if (bubble && !bubble.matches(':hover')) {
        bubble.innerText = data.message;
      }
    }

    // 2. キャラクター
    if (data.character && data.character.id !== currentCharacterId) {
      currentCharacterId = data.character.id;
      const emojiEl = document.getElementById('char-emoji');
      if (emojiEl) emojiEl.innerText = data.character.emoji;
      preloadSprites(currentCharacterId);
    }

    // 3. サジェストデータ
    if (data.suggestions) {
      suggestionsData = data.suggestions;
      renderSuggestionCard();
    }

    // 3.5. 手帳データ（予定・TODO・習慣）→ 手帳モーダルで使用
    if (data.events) eventsData = data.events;
    if (data.tasks) tasksData = data.tasks;
    if (data.habits) habitsData = data.habits;

    // 4. ポモドーロ状態
    if (data.pomodoro) {
      const wasActive = currentPomodoro && currentPomodoro.active;
      currentPomodoro = data.pomodoro;
      const pomoBtn = document.getElementById('pomodoro-btn');
      const timerText = document.getElementById('pomodoro-timer-text');
      if (pomoBtn && timerText) {
        const iconEl = document.getElementById('pomodoro-icon');
        if (currentPomodoro.active) {
          pomoBtn.classList.add('active');
          const mins = Math.floor(currentPomodoro.remaining_seconds / 60);
          const secs = currentPomodoro.remaining_seconds % 60;
          timerText.innerText = `${mins}:${String(secs).padStart(2, '0')}`;
          // 実行中は「押すと止まる」ことを可視化
          if (iconEl) iconEl.innerText = '⏹';
          pomoBtn.title = '⏹ タップでポモドーロ停止';
        } else {
          pomoBtn.classList.remove('active');
          timerText.innerText = "25:00";
          if (iconEl) iconEl.innerText = '🍅';
          pomoBtn.title = '🍅 ポモドーロ開始（25分）';
        }
      }

      // ポモドーロ完了検知 (active -> inactive に遷移、または残り0秒)
      if (wasActive && (!currentPomodoro.active || currentPomodoro.remaining_seconds === 0)) {
        updateLifeSprite('playing');
        const bubble = document.getElementById('speech-bubble');
        if (bubble) bubble.innerText = '🎉 集中タイム完了！ボス、素晴らしい集中力でした！！🔥';
        showToast('🎉 ポモドーロ完了！お疲れ様でした！', 4000, true);
        if (typeof addBondExp === 'function') addBondExp(30);
      } else if (currentPomodoro.active && !currentPomodoro.is_break) {
        // ポモドーロ中はペットスプライトを集中モードに切替
        updateLifeSprite('working');
      } else if (currentPomodoro.active && currentPomodoro.is_break) {
        // 休憩中は rest スプライトへ切替（集中スプライトの引きずり防止）
        updateLifeSprite('resting');
      }
    }

    // 5. 承認・質問イベントバナー（新規着信時はチャイム＋振動で強調）
    const eventBanner = document.getElementById('active-event-banner');
    const bannerActions = document.getElementById('banner-actions');
    if (data.pending_approval) {
      const req = data.pending_approval;
      const isNew = (!currentApprovalRequest || currentApprovalRequest.request_id !== req.request_id);
      currentApprovalRequest = req;
      currentActiveEvent = req;
      eventBanner.style.display = 'block';
      const isQuestion = (req.type === 'question');
      if (isQuestion) {
        eventBanner.className = 'question';
        document.getElementById('event-type-badge').innerText = `❓ 【${req.agent_name}】質問`;
        document.getElementById('banner-hint').innerText = 'タップで回答';
        document.getElementById('event-title').innerText = req.title || req.question || '';
        document.getElementById('event-desc').innerText = (req.choices && req.choices.length > 0) ? `選択肢: ${req.choices.join(' / ')}` : 'タップして回答';
        if (bannerActions) bannerActions.style.display = 'none';
      } else {
        eventBanner.className = '';
        document.getElementById('event-type-badge').innerText = `⚠️ 【${req.agent_name}】承認要請`;
        document.getElementById('banner-hint').innerText = 'ボタンでワンタップ回答';
        document.getElementById('event-title').innerText = req.summary || req.command || '';
        document.getElementById('event-desc').innerText = req.command ? `⌨️ ${req.command}` : '';
        if (bannerActions) bannerActions.style.display = 'flex';
      }
      if (isNew) {
        lastApprovalRequestId = req.request_id;
        playAlertChime(4);
        showToast(`🔔 承認要請: ${req.summary || req.command || ''}`);
      }
    } else {
      currentApprovalRequest = null;
      if (bannerActions) bannerActions.style.display = 'none';
      if (data.active_event) {
        const ev = data.active_event;
        const eventKey = `${ev.type || ''}:${ev.timestamp || ''}:${ev.summary || ev.title || ''}`;
        const isNew = (lastActiveEventKey !== eventKey);
        lastActiveEventKey = eventKey;
        currentActiveEvent = ev;
        eventBanner.style.display = 'block';
        eventBanner.className = ev.type || 'completed';
        const typeLabel = ev.type === 'question' ? '質問' : '完了通知';
        document.getElementById('event-type-badge').innerText = `✨ 【${ev.agent_name || 'AI'}】${typeLabel}`;
        document.getElementById('banner-hint').innerText = 'タップで詳細';
        document.getElementById('event-title').innerText = ev.summary || ev.title || '';
        document.getElementById('event-desc').innerText = 'タップして確認';
        // ✖ dismiss button: completed 時にのみ表示
        const dismissBtn = document.getElementById('banner-dismiss-btn');
        if (dismissBtn) dismissBtn.style.display = ev.type === 'completed' ? '' : 'none';
        if (isNew) {
          playAlertChime(2);
          showToast(`🎉 【${ev.agent_name || 'AI'}】${ev.title || ev.summary || '作業完了！'}`);
          if (navigator.vibrate) navigator.vibrate([120, 80, 120, 80, 240]);
          petStateNow = 'celebrate';
          if (window.EasterEggEngine) EasterEggEngine.playSound('revive');
        }
      } else if (data.due_reminders && data.due_reminders.length > 0) {
        const rem = data.due_reminders[0];
        const remKey = `${rem.type || 'reminder'}:${rem.title || ''}:${rem.due_at || ''}`;
        const isNew = (lastReminderKey !== remKey);
        lastReminderKey = remKey;
        currentActiveEvent = rem;
        eventBanner.style.display = 'block';
        eventBanner.className = 'reminder';
        document.getElementById('event-type-badge').innerText = '⏰ 予定リマインダー';
        document.getElementById('banner-hint').innerText = '10分前のお知らせ';
        document.getElementById('event-title').innerText = rem.title || '予定の時間です';
        document.getElementById('event-desc').innerText = rem.message || rem.due_at || '';
        const dismissBtn = document.getElementById('banner-dismiss-btn');
        if (dismissBtn) dismissBtn.style.display = '';
        if (bannerActions) bannerActions.style.display = 'none';
        if (isNew) {
          playAlertChime(3);
          showToast(`⏰ 【リマインダー】${rem.title || '予定があります'}`);
          if (navigator.vibrate) navigator.vibrate([150, 100, 150, 100, 300]);
          petStateNow = 'alarm_ask';
          if (window.EasterEggEngine) EasterEggEngine.playSound('alarm');
        }
      } else {
        currentActiveEvent = null;
        lastActiveEventKey = null;
        lastReminderKey = null;
        eventBanner.style.display = 'none';
      }
    }

    // 5.4. 🌟 最新通知（latest_notification）の即座フィードバック
    if (data.latest_notification) {
      const notif = data.latest_notification;
      const notifKey = `${notif.id || ''}:${notif.timestamp || ''}`;
      if (window._lastNotifKey !== notifKey) {
        window._lastNotifKey = notifKey;
        try {
          sessionStorage.setItem('lastNotifKey', notifKey);
        } catch (e) { /* プライベートモード等では永続化を諦める */ }
        // 🛡 バグ修正 (2026-08-31): set_notification は必ず buzz 要求も発行するため、
        //   同一ポーリング周期内で後続の §5.6 buzz トーストが本通知トーストを
        //   上書きし「音は鳴るのに通知が表示されない」障害の原因になっていた。
        //   表示時刻を記録し、§5.6 側で上書きを抑制する。
        window._notifDisplayedAt = Date.now();
        // 🛡 追加修正 (2026-08-31): 画面OFF/バックグラウンド中に本ブロックが実行されると
        //   チャイム（音）だけ鳴り、トーストは不可視の画面に描画されて消える。
        //   復帰（visibilitychange）時に再表示させるため、非表示中実行フラグを記録。
        window._notifShownWhileHidden = document.hidden;
        petStateNow = notif.reaction || 'celebrate';
        const msgEl = document.getElementById('speech-bubble');
        if (msgEl) {
          msgEl.innerText = `🎉 【${notif.agent_name}】${notif.title}\n${notif.message}`;
        }
        const fullMsg = notif.message ? `🎉 【${notif.agent_name}】${notif.title}<br><span style="font-size:11px;opacity:0.9;font-weight:normal;">${escapeHtml(notif.message)}</span>` : `🎉 【${notif.agent_name}】${notif.title}`;
        showToast(fullMsg, 4000, true);
        if (navigator.vibrate) navigator.vibrate([120, 80, 120, 80, 240]);
        if (window.EasterEggEngine) {
          EasterEggEngine.playSound('revive');
        } else {
          playAlertChime(2);
        }
      }
    }

    // 5.5. ⬆ アップデート通知バナー（新バージョン検知時）
    const updateBanner = document.getElementById('update-banner');
    const updateText = document.getElementById('update-banner-text');
    const updateLink = document.getElementById('update-banner-link');
    if (data.update && data.update.update_available && updateBanner && updateText && updateLink) {
      const latest = data.update.latest_version || '';
      const current = data.update.current_version || '';
      updateText.innerText = `⬆ ${latest} が利用可能です（現在: v${current}）`;
      updateLink.href = data.update.release_url || '#';
      // dismissedフラグがなければ表示
      if (!sessionStorage.getItem('update_banner_dismissed')) {
        updateBanner.style.display = 'block';
      }
    } else if (updateBanner) {
      updateBanner.style.display = 'none';
    }

    // 5.6. PCからの呼び出し信号 (Buzz)
    if (data.buzz) {
      // 🛡 通知トースト表示直後 (1.5秒以内) の同一周期 buzz は上書き抑制。
      //   通知自体が既にチャイム＋バイブを鳴らしているため二重再生も防止する。
      const sinceNotif = Date.now() - (window._notifDisplayedAt || 0);
      if (sinceNotif > 1500) {
        playAlertChime(2);
        showToast('📲 ボスが呼んでいます！');
      }
    }

    // 5.7. ⚡ イースターエッグ演出同期
    if (window.EasterEggEngine && data.easter_egg) {
      EasterEggEngine.syncFromStatus(data);
    }

    // 5.8. 📍 地域設定の同期
    if (typeof data.weather_location === 'string') {
      currentSavedLocation = data.weather_location;
    }

    // 6. 🌈 自律生活ドリーマー状態（天候・生活イベント）
    if (data.life_state) {
      const ls = data.life_state;
      // 天候バッジの更新
      const wBadge = document.getElementById('weather-badge');
      const weatherKey = ls.weather || 'sunny';
      if (wBadge) {
        const temp = ls.temperature != null ? ` ${ls.temperature}°C` : '';
        const city = ls.city || '';
        wBadge.innerText = `${WEATHER_LABELS_JS[weatherKey] || '☀️ 晴れ'}${temp}${city ? '（' + city + '）' : ''}`;
        wBadge.className = `weather-badge w-${weatherKey}`;
      }
      currentWeather = weatherKey;
      currentActivity = ls.current_activity || 'resting';
      // 活動に応じたスプライトへ切替
      // ※ ポモドーロ実行中は §4 で設定した集中/休憩スプライトを維持する。
      //   ここで無条件に updateLifeSprite(currentActivity) を呼ぶと2秒毎に
      //   生活活動スプライトで上書きされ「ポモドーロなのにキャラが変わらない」
      //   障害の原因になっていた (2026-08-30 実機検証)。
      if (currentPomodoro && currentPomodoro.active) {
        updateLifeSprite(currentPomodoro.is_break ? 'resting' : 'working');
      } else {
        updateLifeSprite(currentActivity);
      }
      // 新しい生活イベントが届いたらトースト＋バイブ＋ペット状態を更新
      const msg = ls.message || '';
      if (msg && msg !== lastLifeMessage && ls.last_generated_at > 0) {
        lastLifeMessage = msg;
        showToast(`🌈 ${msg}`);
        if (navigator.vibrate) navigator.vibrate([40, 60, 40]);
      }
    }

  } catch (err) {
    console.debug("Status fetch error:", err);
    fetchFailCount++;
    if (fetchFailCount >= FETCH_BACKOFF_THRESHOLD && !fetchBackoffActive) {
      fetchBackoffActive = true;
      // 連続失敗 → 30秒バックオフ (バッテリー・発熱対策)
      showToast('📡 サーバーとの接続が不安定です。バックオフ中…');
    }
  }
}

// ポーリング間隔を返す（通常時は2秒、バックオフ中は30秒）
function getNextFetchInterval() {
  if (fetchBackoffActive) return FETCH_BACKOFF_INTERVAL;
  return FETCH_NORMAL_INTERVAL;
}

// =============================================================================
// 8.5. ワンタップ承認（バンボタン / シート / イヤホンメディアキー）
// =============================================================================
function handleActiveEventClick() {
  if (currentApprovalRequest) {
    if (currentApprovalRequest.type === 'question') {
      openQuestionSheet();
      return;
    }
    openApprovalSheet();
    return;
  }
  if (!currentActiveEvent) return;
  // 完了通知なら「閉じる」ボタン付きボトムシートを表示し、閉じる際に dismiss API を呼ぶ
  if (currentActiveEvent.type === 'completed') {
    const ev = currentActiveEvent;
    const html = `
      <div class="note-item">
        <div class="note-title">${escapeHtml(ev.summary || ev.title || '')}</div>
        <div class="note-desc">${escapeHtml(ev.details || ev.message || 'タップして閉じてください')}</div>
      </div>
      <div class="approval-sheet-actions">
        <button class="btn-approve" onclick="dismissCompleted()">✖ 閉じる</button>
      </div>`;
    openBottomSheet({ icon: '✨', tag: '完了通知', title: `${ev.agent_name || 'AI'} からの報告` }, html);
    return;
  }
  openBottomSheet(currentActiveEvent);
}

/** 完了通知を閉じ、サーバ側のイベントも永続的に削除する */
async function dismissCompleted() {
  stopAlertChime();
  if (navigator.vibrate) navigator.vibrate(20);
  closeBottomSheet();
  try {
    await authFetch('/api/agent/dismiss_completed', { method: 'POST' });
  } catch (e) { /* サーバ側エラーは無視（既に消えている場合もある） */ }
  _hideBanner();
  showToast('✅ 通知を閉じました');
  fetchStatus();
}

/** アップデートバナーを閉じる（sessionStorageで永続化：同一セッションでは再表示しない） */
function dismissUpdateBanner() {
  const banner = document.getElementById('update-banner');
  if (banner) banner.style.display = 'none';
  sessionStorage.setItem('update_banner_dismissed', 'true');
}

/** バナーを即座に非表示にする（内部ヘルパー） */
function _hideBanner() {
  currentActiveEvent = null;
  lastActiveEventKey = null;
  const banner = document.getElementById('active-event-banner');
  if (banner) {
    banner.style.display = 'none';
    banner.style.transform = ''; // スワイプ変形をリセット
  }
  const dismissBtn = document.getElementById('banner-dismiss-btn');
  if (dismissBtn) dismissBtn.style.display = 'none';
}

// =============================================================================
// 12. バナースワイプ dismiss (タッチでスワイプして閉じる)
// =============================================================================
let _bannerSwipeX = 0;
let _bannerSwipeStartX = 0;
let _bannerSwipeDelta = 0;

function setupBannerSwipe() {
  const banner = document.getElementById('active-event-banner');
  if (!banner) return;
  banner.addEventListener('touchstart', (e) => {
    _bannerSwipeStartX = e.touches[0].clientX;
    _bannerSwipeDelta = 0;
    banner.style.transition = 'none';
  }, { passive: true });
  banner.addEventListener('touchmove', (e) => {
    _bannerSwipeDelta = e.touches[0].clientX - _bannerSwipeStartX;
    if (_bannerSwipeDelta > 0) {
      banner.style.transform = `translateX(${_bannerSwipeDelta * 0.5}px)`;
      banner.style.opacity = Math.max(0, 1 - _bannerSwipeDelta / 200);
    }
  }, { passive: true });
  banner.addEventListener('touchend', () => {
    banner.style.transition = 'transform 0.25s ease, opacity 0.25s ease';
    if (_bannerSwipeDelta > 80) {
      // 右に80px以上スワイプ → dismiss
      banner.style.transform = 'translateX(120%)';
      banner.style.opacity = '0';
      setTimeout(() => {
        if (currentActiveEvent && currentActiveEvent.type === 'completed') {
          dismissCompleted();
        } else {
          _hideBanner();
        }
      }, 250);
    } else {
      // 戻す
      banner.style.transform = '';
      banner.style.opacity = '1';
    }
  }, { passive: true });
}

/** 承認シート（コマンド全文 ＆ 大ボタンで承認/却下） */
function openApprovalSheet() {
  const req = currentApprovalRequest;
  if (!req) return;
  const commandHtml = req.command
    ? `<div class="note-item"><div class="note-title">⌨️ 実行コマンド</div><div class="note-desc" style="white-space: pre-wrap;">${escapeHtml(req.command)}</div></div>`
    : '';
  const html = `${commandHtml}
    <div class="note-item"><div class="note-title">🛡️ このコマンドの実行を許可しますか？</div><div class="note-desc">イヤホンの再生ボタンでも承認できます</div></div>
    <div class="approval-sheet-actions">
      <button class="btn-approve" onclick="closeBottomSheet(); respondApproval('approve')">✅ 承認する</button>
      <button class="btn-deny" onclick="closeBottomSheet(); respondApproval('deny')">🛑 却下する</button>
    </div>`;
  openBottomSheet({ icon: '🛡️', tag: '承認要請', title: req.summary || 'コマンド実行の承認' }, html);
}

/** 質問シート（選択肢を大ボタンで表示） */
function openQuestionSheet() {
  const req = currentApprovalRequest;
  if (!req) return;
  const choices = req.choices || [];
  let choicesHtml = '';
  if (choices.length > 0) {
    // インデックス参照で選択肢テキストを渡す（JSON.stringifyの二重引用符競合を回避）
    choicesHtml = choices.map((c, i) =>
      `<button class="btn-approve" onclick="closeBottomSheet(); respondChoice(${i})">${i+1}. ${escapeHtml(c)}</button>`
    ).join('');
  } else {
    choicesHtml = `<div class="note-item"><div class="note-desc">自由回答はPC側でお願いします</div></div>`;
  }
  const html = `
    <div class="note-item"><div class="note-title">❓ ${escapeHtml(req.title || req.question || '')}</div></div>
    <div class="approval-sheet-actions" style="flex-direction:column;gap:6px;">
      ${choicesHtml}
    </div>`;
  openBottomSheet({ icon: '❓', tag: '質問', title: `${req.agent_name} からの質問` }, html);
}

/** 質問シートの選択肢ボタンから呼ばれるヘルパー（index参照で二重引用符競合を回避） */
function respondChoice(index) {
  const req = currentApprovalRequest;
  if (!req || !req.choices || !req.choices[index]) return;
  respondApproval('answered', null, req.choices[index]);
}

/** 承認/却下/回答をサーバーへ送信する（バナーボタン・シート・メディアキー共通） */
async function respondApproval(decision, ev, answerText) {
  if (ev && ev.stopPropagation) ev.stopPropagation();
  if (!currentApprovalRequest) return;
  stopAlertChime();
  if (navigator.vibrate) navigator.vibrate(60);
  const req = currentApprovalRequest;
  try {
    const res = await authFetch('/api/agent/respond', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ request_id: req.request_id, decision, message: answerText || '' })
    });
    if (res.ok) {
      const data = await res.json().catch(() => ({}));
      if (data.status === 'expired') {
        showToast('⏰ この質問は期限切れです');
        currentApprovalRequest = null;
        currentActiveEvent = null;
        const banner = document.getElementById('active-event-banner');
        if (banner) banner.style.display = 'none';
        fetchStatus();
        return;
      }
      currentApprovalRequest = null;
      currentActiveEvent = null;
      const banner = document.getElementById('active-event-banner');
      if (banner) banner.style.display = 'none';
      playDecisionSound(decision === 'approve');
      // PC側ペットにも結果をリアクションさせる（承認=大喜び・却下=心配）
      authFetch('/api/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'pet_reaction', state: decision === 'approve' ? 'celebrate' : 'care', duration_ms: 5000 })
      }).catch(err => console.debug('Pet reaction failed:', err));
      showToast(decision === 'approve' ? '✅ 承認を送信しました' : decision === 'answered' ? '✅ 回答を送信しました' : '🛑 却下を送信しました');
    } else {
      showToast('⚠️ 送信に失敗しました');
    }
  } catch (err) {
    console.debug('Respond error:', err);
    showToast('⚠️ 通信エラー');
  }
  fetchStatus();
}

/** イヤホンの再生/一時停止ボタンを「承認」として割り当てる（ノールック操作） */
function setupMediaKeyApproval() {
  if (!('mediaSession' in navigator)) return;
  const handleMediaKey = () => {
    if (currentApprovalRequest) respondApproval('approve');
  };
  try { navigator.mediaSession.setActionHandler('play', handleMediaKey); } catch (e) { /* 非対応ブラウザ */ }
  try { navigator.mediaSession.setActionHandler('pause', handleMediaKey); } catch (e) { /* 非対応ブラウザ */ }
  try { navigator.mediaSession.setActionHandler('nexttrack', handleMediaKey); } catch (e) { /* 非対応ブラウザ */ }
}

// =============================================================================
// 10. 手帳モーダル（予定・TODO・習慣・設定）本実装
// =============================================================================

/** HTML特殊文字のエスケープ（リスト表示のXSS対策） */
function escapeHtml(str) {
  return String(str || '').replace(/[&<>"']/g, m => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]
  ));
}

/** 📅 予定一覧モーダル */
function openEventsModal() {
  const count = eventsData ? eventsData.length : 0;
  let html = '';
  if (count === 0) {
    html = '<div class="note-empty">📅 登録された予定はありません。<br>PC側の手帳やAIチャットで追加できます。</div>' +
      '<div class="approval-sheet-actions" style="margin-top:8px;"><button class="btn-approve" onclick="closeBottomSheet();showToast(\'📱 PC側でGoogleカレンダー連携を設定してください\')">⚙ 設定から連携する</button></div>';
  } else {
    html = eventsData.map(e => {
      const dt = String(e.start_time || '').replace('T', ' ').slice(0, 16);
      return `<div class="note-item"><div class="note-title">📅 ${escapeHtml(e.title)}</div><div class="note-desc">🕐 ${escapeHtml(dt)}${e.source_name ? " ／ " + escapeHtml(e.source_name) : ""}</div></div>`;
    }).join('');
  }
  openBottomSheet({ icon: '📅', tag: '手帳', title: `予定一覧 (${count}件)` }, html);
}

// 🗂️ TODOビューの絞り込み状態 (Plan C: リスト/タグ/期間フィルタ)
let todoFilter = { listId: null, tag: null, range: 'all' };
let todoTasks = [];   // get_tasks_view で取得した拡充タスク (tags/due_date/list_id付き)
let todoLists = [];   // list_task_lists で取得したリスト一覧
let todoTagCandidates = []; // 描画ごとのタグ候補 (onclickはインデックス参照・XSS安全)
let todoViewMode = 'list';  // 🎯 ビュー切替 ('list': 通常一覧 / 'quad': 4象限)

/** 🗂️ TODOビュー用データ取得 (拡充タスク + リスト一覧) */
function fetchTodoView() {
  const post = (action) => authFetch('/api/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: action })
  }).then(res => res.json()).catch(err => {
    console.debug(`${action} failed:`, err);
    return null;
  });
  return Promise.all([post('get_tasks_view'), post('list_task_lists')]).then(([tasksRes, listsRes]) => {
    if (tasksRes && tasksRes.status === 'success') todoTasks = tasksRes.tasks || [];
    if (listsRes && listsRes.status === 'success') todoLists = listsRes.lists || [];
  });
}

/** 絞り込み条件を変更してTODOモーダルを再描画する (データ再取得なし) */
function setTodoFilter(patch) {
  if (navigator.vibrate) navigator.vibrate(15);
  Object.assign(todoFilter, patch);
  renderTodoModal();
}

/** タグ絞り込みのトグル (候補配列のインデックス指定・XSS安全) */
function toggleTodoTagIndex(idx) {
  const tag = todoTagCandidates[idx];
  if (tag === undefined) return;
  setTodoFilter({ tag: todoFilter.tag === tag ? null : tag });
}

/** タスクが期間フィルタに合致するか ('all' | 'today' | 'week') */
function todoMatchRange(t, range) {
  if (range === 'all') return true;
  if (!t.due_date) return false;
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const dayMs = 24 * 60 * 60 * 1000;
  if (range === 'today') return t.due_date < startOfToday + dayMs;   // 期限切れ含む今日中
  if (range === 'week') return t.due_date < startOfToday + 7 * dayMs;
  return true;
}

/** 現在の絞り込み状態をTODO一覧へ適用する */
function todoApplyFilter() {
  return todoTasks.filter(t => {
    if (todoFilter.listId !== null && t.list_id !== todoFilter.listId) return false;
    if (todoFilter.tag) {
      const tags = String(t.tags || '').split(',').map(s => s.trim()).filter(Boolean);
      if (!tags.includes(todoFilter.tag)) return false;
    }
    return todoMatchRange(t, todoFilter.range);
  });
}

/** 🎯 TODOビュー切替 (📋 リスト ⇔ 🎯 4象限) */
function setTodoView(mode) {
  if (navigator.vibrate) navigator.vibrate(15);
  todoViewMode = mode === 'quad' ? 'quad' : 'list';
  renderTodoModal();
}

/** 🎯 緊急判定: 明示属性 (※緊急/※非緊急) を最優先 → 未指定は期限3日以内で推定 */
function todoIsUrgent(t) {
  if (t.urgency_flag !== null && t.urgency_flag !== undefined) {
    return !!t.urgency_flag;
  }
  if (!t.due_date) return false;
  return t.due_date < Date.now() + 3 * 24 * 60 * 60 * 1000;
}

/** 🎯 重要判定: 明示属性 (※重要/※非重要) を最優先 → 未指定は優先度高で推定 */
function todoIsImportant(t) {
  if (t.importance_flag !== null && t.importance_flag !== undefined) {
    return !!t.importance_flag;
  }
  return t.priority >= 3;
}

/** 4象限セル内の1タスク行 (タップで完了) */
function todoQuadItem(t) {
  const pad = n => String(n).padStart(2, '0');
  let due = '';
  if (t.due_date) {
    const d = new Date(t.due_date);
    due = `📅 ${pad(d.getMonth() + 1)}/${pad(d.getDate())}`;
  }
  return `<div class="note-item" onclick="completeTask(${t.id}, this)"><div class="note-title">${escapeHtml(t.title)}</div><div class="note-desc">${due} <span class="task-edit-link" onclick="event.stopPropagation();openTaskEditSheet(${t.id})">✏️</span></div></div>`;
}

/** 📅 期限 (epochミリ秒) を datetime-local 入力値へ変換 (空なら '') */
function epochToDatetimeLocal(ms) {
  if (!ms) return '';
  const d = new Date(ms);
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** ✏️ タスク編集シート (タイトル・期限の編集＋削除。サーバー update_task / delete_task アクションと連携) */
function openTaskEditSheet(taskId) {
  const t = todoTasks.find(x => x.id === taskId);
  if (!t) return;
  if (navigator.vibrate) navigator.vibrate(15);
  const inputStyle = 'width:100%;box-sizing:border-box;padding:10px;border-radius:8px;border:1px solid rgba(255,255,255,0.3);background:rgba(0,0,0,0.2);color:inherit;font-size:14px;';
  const html = `
    <div style="display:flex;flex-direction:column;gap:10px;">
      <label style="font-size:12px;opacity:0.8;">タイトル</label>
      <input type="text" id="task-edit-title" value="${escapeHtml(t.title)}" maxlength="200" style="${inputStyle}">
      <label style="font-size:12px;opacity:0.8;">期限 (空で期日なし)</label>
      <input type="datetime-local" id="task-edit-due" value="${epochToDatetimeLocal(t.due_date)}" style="${inputStyle}">
      <div class="approval-sheet-actions">
        <button class="btn-approve" onclick="saveTaskEdit(${t.id})">💾 保存</button>
        <button class="btn-deny" onclick="deleteTaskFromEdit(${t.id})">🗑 削除</button>
      </div>
    </div>`;
  openBottomSheet({ icon: '✏️', tag: '編集', title: 'タスクを編集' }, html);
}

/** ✏️ 編集シートの保存 (update_task → 再取得 → モーダル再描画) */
function saveTaskEdit(taskId) {
  const titleEl = document.getElementById('task-edit-title');
  const dueEl = document.getElementById('task-edit-due');
  if (!titleEl) return;
  const newTitle = titleEl.value.trim();
  if (!newTitle) {
    showToast('⚠️ タイトルを入力してください');
    return;
  }
  authFetch('/api/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      action: 'update_task',
      task_id: taskId,
      title: newTitle,
      due_date: (dueEl && dueEl.value) ? new Date(dueEl.value).getTime() : null
    })
  }).then(res => res.json()).then(res => {
    if (res.status === 'success') {
      showToast('💾 保存しました');
      closeBottomSheet();
      fetchTodoView().then(renderTodoModal);
    } else {
      showToast('⚠️ 保存に失敗しました');
    }
  }).catch(err => {
    console.debug('update_task failed:', err);
    showToast('⚠️ 通信エラー');
  });
}

/** 🗑 編集シートからの削除 (確認ダイアログ → delete_task → 再取得) */
function deleteTaskFromEdit(taskId) {
  if (!window.confirm('このタスクを削除しますか？')) return;
  if (navigator.vibrate) navigator.vibrate([20, 40, 20]);
  authFetch('/api/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'delete_task', task_id: taskId })
  }).then(res => res.json()).then(res => {
    if (res.status === 'success') {
      showToast('🗑 削除しました');
      closeBottomSheet();
      fetchTodoView().then(renderTodoModal);
    } else {
      showToast('⚠️ 削除に失敗しました');
    }
  }).catch(err => {
    console.debug('delete_task failed:', err);
    showToast('⚠️ 通信エラー');
  });
}

/** 🎯 アイゼンハワー4象限グリッド描画 (Plan D) */
function renderQuadrant(tasks) {
  const q1 = tasks.filter(t => todoIsImportant(t) && todoIsUrgent(t));
  const q2 = tasks.filter(t => todoIsImportant(t) && !todoIsUrgent(t));
  const q3 = tasks.filter(t => !todoIsImportant(t) && todoIsUrgent(t));
  const q4 = tasks.filter(t => !todoIsImportant(t) && !todoIsUrgent(t));
  const cell = (cls, icon, label, arr, hint) =>
    `<div class="quad-cell ${cls}"><div class="quad-head">${icon} ${label}<span class="quad-count">${arr.length}</span></div>`
    + (arr.length ? arr.map(todoQuadItem).join('') : `<div class="quad-empty">${hint}</div>`)
    + `</div>`;
  return `<div class="quad-grid">`
    + cell('q1', '🔥', '今すぐやる', q1, '重要×緊急。最優先！')
    + cell('q2', '🎯', '計画する', q2, '重要×非緊急。予定を立てよう')
    + cell('q3', '⚡', '調整する', q3, '非重要×緊急。丸投げも一手')
    + cell('q4', '☕', '後回し', q4, '非重要×非緊急。余裕があれば')
    + `</div>`;
}

/** 📝 TODOリストモーダル (フィルタチップ付き) — キャッシュ即描画→取得後再描画 */
function openTodoModal() {
  renderTodoModal();
  fetchTodoView().then(renderTodoModal);
}

/** TODOモーダルの本体描画 (openTodoModal / setTodoFilter から呼ばれる) */
function renderTodoModal() {
  const filtered = todoApplyFilter();
  // 🚀 クイック追加バー (TickTick拡張): 「明日18時に〜 #仕事 !3」構文対応
  const quickBar = `
    <div class="quick-add-bar">
      <input type="text" id="quick-task-input" placeholder="例: 明日18時に資料 #仕事 !3" enterkeyhint="done">
      <button id="quick-task-btn" onclick="quickAddTask()">＋</button>
    </div>`;
  // 🌳 リスト階層順ソート (parent_id ツリー・Block 1.6-R): 親→子の深さ優先で並べ、
  // 子リストにはインデント接頭辞を付けて階層を可視化する
  const listChildren = {};
  todoLists.forEach(l => {
    const key = (l.parent_id == null) ? 0 : l.parent_id;
    (listChildren[key] = listChildren[key] || []).push(l);
  });
  const orderedLists = [];
  (function walkLists(pid, depth) {
    (listChildren[pid === null ? 0 : pid] || []).forEach(l => {
      orderedLists.push({ l, depth });
      walkLists(l.id, depth + 1);
    });
  })(null, 0);
  const listRow = todoLists.length > 0
    ? `<div class="todo-filter-bar"><span class="todo-filter-label">📋 リスト</span><div class="todo-filter-chips">`
      + ['<button class="todo-chip' + (todoFilter.listId === null ? ' active' : '') + '" onclick="setTodoFilter({listId: null})">📥 すべて</button>']
        .concat(orderedLists.map(({ l, depth }) => {
          const indent = depth > 0 ? '　'.repeat(depth) + '└ ' : '';
          return `<button class="todo-chip${todoFilter.listId === l.id ? ' active' : ''}" onclick="setTodoFilter({listId: ${l.id}})">${indent}${escapeHtml(l.emoji || '📋')} ${escapeHtml(l.name)}</button>`;
        })).join('')
      + `</div></div>`
    : '';
  // 🗓 期間フィルタ行 (セグメントコントロール化) ＋ 🎯 4象限ビュー切替を同列に集約
  const rangeRow = `<div class="todo-filter-bar"><span class="todo-filter-label">🗓 期間</span><div class="todo-filter-chips">`
    + [['all', '🗂 すべて'], ['today', '⏰ 今日'], ['week', '📅 今週']]
      .map(([k, label]) => `<button class="todo-chip${todoFilter.range === k ? ' active' : ''}" onclick="setTodoFilter({range: '${k}'})">${label}</button>`).join('')
    + `<button class="todo-chip todo-view-toggle${todoViewMode === 'quad' ? ' active' : ''}" onclick="setTodoView('${todoViewMode === 'quad' ? 'list' : 'quad'}')">${todoViewMode === 'quad' ? '📋 一覧に戻る' : '🎯 4象限'}</button>`
    + `</div></div>`;
  // 🏷 タグ行 (絞り込み中のみ表示・✕で解除)
  const tagRow = todoFilter.tag
    ? `<div class="todo-filter-bar"><span class="todo-filter-label">🏷 タグ</span><div class="todo-filter-chips"><button class="todo-chip active" onclick="setTodoFilter({tag: null})">#${escapeHtml(todoFilter.tag)} ✕ 解除</button></div></div>`
    : '';
  let html = quickBar + listRow + rangeRow + tagRow;
  // 🎯 4象限ビュー (Plan D): バケツ分けして2x2グリッド描画して終了
  if (todoViewMode === 'quad') {
    todoTagCandidates = [];
    html += renderQuadrant(filtered);
    openBottomSheet({ icon: '📝', tag: '手帳', title: `TODO 4象限 (${filtered.length}件)` }, html);
    const qinput = document.getElementById('quick-task-input');
    if (qinput) {
      qinput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          quickAddTask();
        }
      });
    }
    return;
  }
  const tagCandidates = [];
  if (filtered.length === 0) {
    html += '<div class="note-empty">📝 該当するTODOはありません。<br>フィルタを変更するか、上のバーから追加してください✨</div>';
  } else {
    const prioIcon = { 3: '🔥', 2: '⭐', 1: '🌱' };
    const pad = n => String(n).padStart(2, '0');
    html += filtered.map(t => {
      const icon = prioIcon[t.priority] || '📌';
      const recBadge = t.recurrence ? '<span class="todo-tag">🔄 繰り返し</span>' : '';
      const tags = String(t.tags || '').split(',').map(s => s.trim()).filter(Boolean);
      const tagHtml = tags.map(tag => {
        let idx = tagCandidates.indexOf(tag);
        if (idx === -1) { tagCandidates.push(tag); idx = tagCandidates.length - 1; }
        return `<span class="todo-tag" onclick="event.stopPropagation();toggleTodoTagIndex(${idx})">#${escapeHtml(tag)}</span>`;
      }).join('');
      let dueHtml = '';
      if (t.due_date) {
        const d = new Date(t.due_date);
        dueHtml = ` 📅 ${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
      }
      return `<div class="note-item" onclick="completeTask(${t.id}, this)"><div class="note-title">${icon} ${escapeHtml(t.title)}${recBadge}${tagHtml}</div><div class="note-desc">${dueHtml || '👆 タップで完了にする'} <span class="task-edit-link" onclick="event.stopPropagation();openTaskEditSheet(${t.id})">✏️</span></div></div>`;
    }).join('');
  }
  todoTagCandidates = tagCandidates;
  openBottomSheet({ icon: '📝', tag: '手帳', title: `TODOリスト (${filtered.length}件)` }, html);
  // Enterキーでも追加できるようにバインド
  const input = document.getElementById('quick-task-input');
  if (input) {
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        quickAddTask();
      }
    });
  }
}

/** 🚀 クイック追加（サーバー解析 → 楽観的更新 → 再取得） */
function quickAddTask() {
  const input = document.getElementById('quick-task-input');
  const btn = document.getElementById('quick-task-btn');
  if (!input) return;
  const text = input.value.trim();
  if (!text) return;
  if (btn) btn.disabled = true;
  if (navigator.vibrate) navigator.vibrate(20);
  authFetch('/api/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'quick_add_task', text: text })
  }).then(res => res.json()).then(data => {
    if (data.status === 'success') {
      if (navigator.vibrate) navigator.vibrate([20, 40, 20]);
      if (window.MinigameArcade) window.MinigameArcade.beep(880, 0.08, 0.05, 'triangle');
      openTodoModal(); // 再描画
    } else {
      alert(data.message || '追加に失敗しました');
      if (btn) btn.disabled = false;
    }
  }).catch(err => {
    console.debug('Quick add failed:', err);
    alert('サーバーとの通信に失敗しました');
    if (btn) btn.disabled = false;
  });
}

/** タスク完了（楽観的UI更新 → サーバー同期）。完了後、同一行タップで元に戻せる (誤タップ対策) */
function completeTask(taskId, el) {
  if (navigator.vibrate) navigator.vibrate(30);
  if (el) {
    el.classList.add('done');
    const desc = el.querySelector('.note-desc');
    if (desc) desc.innerHTML = '✅ 完了！お見事です！ <span class="task-undo-link">↩ 誤タップ？ここで元に戻す</span>';
    // 完了表示中の行タップ = 取り消し (再取得で行が消える前に復帰できるように)
    el.onclick = (ev) => {
      ev.stopPropagation();
      undoTask(taskId, el);
    };
  }
  authFetch('/api/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'complete_task', task_id: taskId })
  }).then(() => { fetchStatus(); fetchTodoView(); }).catch(err => console.debug('Task action failed:', err));
}

/** タスク完了取り消し（楽観的UI復元 → reopen_task 同期 → 再取得） */
function undoTask(taskId, el) {
  if (navigator.vibrate) navigator.vibrate(20);
  if (el) {
    el.classList.remove('done');
    const desc = el.querySelector('.note-desc');
    if (desc) desc.innerText = '👆 タップで完了にする';
    // 行タップで再度完了にできるようハンドラを差し戻す
    el.onclick = (ev) => {
      ev.stopPropagation();
      completeTask(taskId, el);
    };
  }
  authFetch('/api/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'reopen_task', task_id: taskId })
  }).then(() => { fetchStatus(); fetchTodoView(); }).catch(err => console.debug('Task action failed:', err));
}

/** 🌱 習慣トラッカーモーダル（項目タップで達成トグル） */
function openNotesModal() {
  const count = habitsData ? habitsData.length : 0;
  let html = '';
  if (count === 0) {
    html = '<div class="note-empty">🌱 登録された習慣はありません。<br>PC側の手帳で習慣を追加できます。</div>';
  } else {
    html = habitsData.map(h => {
      const done = !!h.completed_today;
      const streakBadge = h.streak > 0 ? `<span class="note-badge">🔥 ${h.streak}日連続</span>` : '';
      return `<div class="note-item ${done ? 'done' : ''}" onclick="toggleHabit(${h.id}, this)"><div class="note-title">${h.emoji || '🌱'} ${escapeHtml(h.title)}${streakBadge}</div><div class="note-desc">${done ? '今日は達成済み！素晴らしい！✨' : '👆 タップで今日の達成を記録'}</div></div>`;
    }).join('');
  }
  openBottomSheet({ icon: '🌱', tag: '手帳', title: '習慣トラッカー' }, html);
}

/** 習慣達成トグル（サーバー同期 → 再取得） */
function toggleHabit(habitId, el) {
  if (navigator.vibrate) navigator.vibrate(30);
  authFetch('/api/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'toggle_habit', habit_id: habitId })
  }).then(() => fetchStatus()).catch(err => console.debug('Habit toggle failed:', err));
}

// ※ CHARACTERS 一覧は本ファイル前半（キャラクター切り替えセクション）で単一宣言。
//    cycleCharacter / selectCharacter の両方がこの共有リストを参照する。

/** キャラクター直接選択（設定モーダルのチップ） */
function selectCharacter(charId) {
  if (navigator.vibrate) navigator.vibrate(25);
  // サーバー側の正規アクションは 'switch_character' (local_sync_server.py 実装)。
  // 旧 'set_character' はサーバーに実装がなく無応答 → 2秒後の fetchStatus が
  // サーバー側キャラ(未変更)を再同期するため「設定でキャラが変わらない」障害の原因だった。
  authFetch('/api/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'switch_character', character_id: charId })
  }).then(res => res.json().catch(() => ({}))).then(result => {
    if (result && result.status === 'success') {
      currentCharacterId = charId;
      preloadSprites(charId);
      showToast(`🎭 キャラクターを【${CHARACTERS.find(c => c.id === charId)?.name || charId}】に変更しました`);
    } else {
      showToast('⚠️ キャラクターの変更に失敗しました（サーバー拒否）');
    }
    fetchStatus();
    openSettingsModal();
  }).catch(err => {
    console.debug('Switch character failed:', err);
    showToast('⚠️ 通信エラーでキャラクターを変更できませんでした');
  });
}

/** 背景テーマ直接選択 */
function selectEnvTheme(themeId) {
  const idx = ENV_THEMES.findIndex(t => t.id === themeId);
  if (idx !== -1) {
    currentEnvIndex = idx;
    const theme = ENV_THEMES[currentEnvIndex];
    const backdrop = document.getElementById('env-backdrop');
    if (backdrop) backdrop.className = `env-backdrop ${theme.class}`;
    const label = document.getElementById('env-label');
    if (label) label.innerText = theme.label;
    envParticles = [];
    if (navigator.vibrate) navigator.vibrate(25);
    showToast(`🏞️ 【${theme.label}】テーマに変更しました`);
    openSettingsModal();
  }
}

let currentSavedLocation = '';

/** ⚙️ 設定モーダル（キャラ・テーマ・地域・演出モード・全画面・常時ON・PCペット呼び出し） */
function openSettingsModal() {
  const locLabel = currentSavedLocation ? currentSavedLocation : 'IP自動検出';

  // キャラクター選択チップ
  const charChipsHtml = CHARACTERS.map(c => `
    <button style="
      background: ${currentCharacterId === c.id ? 'var(--accent-amber)' : 'rgba(255,255,255,0.08)'};
      color: ${currentCharacterId === c.id ? '#1E140E' : 'var(--text-main)'};
      border: 1px solid var(--accent-amber);
      border-radius: 14px;
      padding: 5px 11px;
      font-size: 11px;
      font-weight: bold;
      cursor: pointer;
      margin: 3px;
    " onclick="selectCharacter('${c.id}')">${c.emoji} ${c.name}</button>
  `).join('');

  // 背景テーマ選択チップ
  const themeChipsHtml = ENV_THEMES.map(t => `
    <button style="
      background: ${ENV_THEMES[currentEnvIndex].id === t.id ? 'var(--accent-amber)' : 'rgba(255,255,255,0.08)'};
      color: ${ENV_THEMES[currentEnvIndex].id === t.id ? '#1E140E' : 'var(--text-main)'};
      border: 1px solid var(--accent-amber);
      border-radius: 14px;
      padding: 5px 11px;
      font-size: 11px;
      font-weight: bold;
      cursor: pointer;
      margin: 3px;
    " onclick="selectEnvTheme('${t.id}')">${t.label}</button>
  `).join('');

  const html = `
    <div style="margin-bottom:12px;">
      <div style="font-size:11px; font-weight:bold; color:var(--accent-amber); margin-bottom:5px;">🎭 キャラクター選択:</div>
      <div style="display:flex; flex-wrap:wrap;">
        ${charChipsHtml}
      </div>
    </div>

    <div style="margin-bottom:12px;">
      <div style="font-size:11px; font-weight:bold; color:var(--accent-amber); margin-bottom:5px;">🏞️ 背景テーマ選択:</div>
      <div style="display:flex; flex-wrap:wrap;">
        ${themeChipsHtml}
      </div>
    </div>

    <div class="note-item" onclick="openLocationSettingsModal();"><div class="note-title">📍 お住まいの地域（天気）</div><div class="note-desc">現在: <b>${escapeHtml(locLabel)}</b> → タップで変更</div></div>
    <div class="note-item" onclick="cycleEffectMode(); openSettingsModal();"><div class="note-title">✨ イースターエッグ演出モード</div><div class="note-desc">現在: <b>${effectModeLabel()}</b> → タップで切替（低スペ端末は自動で軽量）</div></div>
    <div class="note-item" onclick="toggleNoSleep(); closeBottomSheet();"><div class="note-title">💡 常時画面ON（自動消灯防止）</div><div class="note-desc">卓上スマートディスプレイとして常時点灯します</div></div>
    <div class="note-item" onclick="toggleFullscreen(); closeBottomSheet();"><div class="note-title">⛶ 全画面表示</div><div class="note-desc">ブラウザUIを隠して全画面表示にします</div></div>
    <div class="note-item" onclick="showPcPet()"><div class="note-title">🖥️ PCのペットを呼び出す</div><div class="note-desc">デスクトップのペットを再表示します</div></div>
    <div class="note-item" onclick="closeBottomSheet(); if (window.EasterEggEngine) EasterEggEngine.triggerFromPwa();"><div class="note-title">⚡ イースターエッグ演出テスト</div><div class="note-desc">「お前を消す方法」の演出を発火テストします</div></div>
    <div class="note-item" onclick="closeBottomSheet()"><div class="note-title">✖ 閉じる</div></div>`;
  openBottomSheet({ icon: '⚙️', tag: '設定', title: '設定' }, html);
}

/** ✨ 演出モードの現在値ラベル（easter_eggs.js 連携・low-end端末は自動で軽量化） */
function effectModeLabel() {
  const mode = window.EasterEggEngine ? window.EasterEggEngine.getEffectMode() : 'full';
  return { full: '標準', light: '軽量', off: 'OFF' }[mode] || '標準';
}

/** ✨ 演出モード循環切替（標準→軽量→OFF） */
function cycleEffectMode() {
  if (window.EasterEggEngine) {
    window.EasterEggEngine.cycleEffectMode();
  }
}

/** 📍 地域設定モーダル */
function openLocationSettingsModal() {
  const popularCities = ['東京都', '横浜市', '大阪市', '名古屋市', '京都市', '神戸市', '福岡市', '札幌市', '仙台市', '広島市', '自動検出(IP)'];
  const chipsHtml = popularCities.map(city => `
    <button style="
      background: ${currentSavedLocation === city || (city === '自動検出(IP)' && !currentSavedLocation) ? 'var(--accent-amber)' : 'rgba(255,255,255,0.08)'};
      color: ${currentSavedLocation === city || (city === '自動検出(IP)' && !currentSavedLocation) ? '#1E140E' : 'var(--text-main)'};
      border: 1px solid var(--accent-amber);
      border-radius: 14px;
      padding: 4px 10px;
      font-size: 11px;
      font-weight: bold;
      cursor: pointer;
      margin: 3px;
    " onclick="selectWeatherCity('${city}')">${city}</button>
  `).join('');

  const html = `
    <div style="margin-bottom:10px; font-size:12px; color:var(--text-main); line-height:1.4;">
      お住まいの地域（市区町村名や都道府県名）を設定すると、正確なリアルタイム天気と生活アドバイスをお届けします。
    </div>

    <div style="margin-bottom:12px;">
      <div style="font-size:11px; font-weight:bold; color:var(--accent-amber); margin-bottom:6px;">⚡ クイック選択:</div>
      <div style="display:flex; flex-wrap:wrap;">
        ${chipsHtml}
      </div>
    </div>

    <div style="margin-bottom:12px;">
      <div style="font-size:11px; font-weight:bold; color:var(--accent-amber); margin-bottom:4px;">✏️ 自由入力 (例: 渋谷区, 堺市, 35.68,139.69):</div>
      <input id="weather-location-input" type="text" value="${escapeHtml(currentSavedLocation)}" placeholder="市区町村名を入力" style="
        width: 100%;
        box-sizing: border-box;
        background: rgba(0,0,0,0.4);
        border: 1px solid var(--accent-amber);
        border-radius: 6px;
        color: #FFF;
        padding: 8px 10px;
        font-size: 13px;
        font-family: inherit;
        outline: none;
      " />
    </div>

    <div class="approval-sheet-actions" style="margin-top:14px; gap:8px;">
      <button class="btn-approve" onclick="saveCustomWeatherLocation()">💾 設定を保存</button>
      <button class="btn-deny" onclick="openSettingsModal()">⬅ 戻る</button>
    </div>
  `;

  openBottomSheet({ icon: '📍', tag: '地域設定', title: 'お住まいの地域設定' }, html);
}

function selectWeatherCity(city) {
  const input = document.getElementById('weather-location-input');
  if (input) {
    input.value = city === '自動検出(IP)' ? '' : city;
  }
}

async function saveCustomWeatherLocation() {
  const input = document.getElementById('weather-location-input');
  const loc = input ? input.value.trim() : '';
  showToast("📍 地域設定を保存中…", 1500);

  try {
    const res = await authFetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'set_weather_location', location: loc })
    });
    if (!res.ok) throw new Error("保存失敗");
    currentSavedLocation = loc;
    showToast(`✅ 地域を【${loc || '自動検出'}】に設定しました！`, 3000, true);
    fetchStatus();
    openSettingsModal();
  } catch (e) {
    showToast("⚠️ 地域設定の保存に失敗しました: " + e.message);
  }
}

/** PCペット再表示（スマホから遠隔呼び出し） */
function showPcPet() {
  if (navigator.vibrate) navigator.vibrate(25);
  authFetch('/api/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'show_pc_pet' })
  }).then(() => {
    closeBottomSheet();
  }).catch(err => console.debug('Show PC pet failed:', err));
}

// =============================================================================
// 11. 全画面表示 ＆ 常時画面ON (NoSleep captureStream 無限生配信)
// =============================================================================

/** 全画面表示トグル (Fullscreen API) */
function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(err => console.debug('Fullscreen request failed:', err));
  } else {
    document.exitFullscreen().catch(err => console.debug('Exit fullscreen failed:', err));
  }
  if (navigator.vibrate) navigator.vibrate(25);
}

let nosleepActive = false;

/**
 * 常時画面ON トグル (NoSleep captureStream 方式)
 *
 * HTTP環境 (http://192.168.x.x:8765) では navigator.wakeLock が
 * セキュリティ制限で動作しないため、Canvasの再描画フレームを
 * captureStream() で不可視videoへ流し込み「永遠に終わらない生配信」として
 * 再生し続けることで、OSのスリープタイマーをバイパスする（2026-08-16 第一原理の再実装）。
 */
function toggleNoSleep() {
  const video = document.getElementById('nosleep-video');
  if (!video) return;

  if (nosleepActive) {
    // --- 停止 ---
    if (video.srcObject) {
      video.srcObject.getTracks().forEach(t => t.stop());
      video.srcObject = null;
    }
    video.pause();
    nosleepActive = false;
    updateNoSleepUI();
    if (navigator.vibrate) navigator.vibrate(20);
    return;
  }

  try {
    // 描画が常時更新されている env-canvas をストリーム源にする
    // （requestAnimationFrame で描き続けられているため、配信が途切れない）
    const sourceCanvas = envCanvas || document.createElement('canvas');
    const stream = sourceCanvas.captureStream(10);
    video.srcObject = stream;
    video.play().then(() => {
      nosleepActive = true;
      updateNoSleepUI();
      if (navigator.vibrate) navigator.vibrate(30);
    }).catch((err) => {
      console.warn('NoSleep: video play failed:', err);
    });
  } catch (err) {
    console.warn('NoSleep: captureStream error:', err);
  }
}

/** 常時ON状態に応じてヘッダーアイコンとバナーを更新 */
function updateNoSleepUI() {
  const icon = document.getElementById('nosleep-icon');
  const banner = document.getElementById('wake-banner');
  if (icon) {
    icon.innerText = nosleepActive ? '🔆' : '💡';
    const btn = icon.closest('.btn-header');
    if (btn) btn.style.borderColor = nosleepActive ? 'var(--accent-amber)' : '';
  }
  if (banner) banner.style.display = nosleepActive ? 'none' : '';
}

// =============================================================================
// 12. 自律歩行コントローラー（テクテク歩き ＆ フレームアニメ）
//     - idle_1/idle_2 のフレーム切替で呼吸感を演出
//     - 地面ライン上をランダムに歩行（方向転換あり・進行方向へスプライト反転）
//     - 集中中・承認待ち等の特別状態では歩行を中断し既存描画に任せる
// =============================================================================
const WANDER = { mode: 'idle', dir: 1, x: 0.5, until: Date.now() + 5000, frame: 0, lastFrameAt: 0, lastTick: 0 };
const WALK_MIN = 0.18, WALK_MAX = 0.82, WALK_SPEED = 0.045;

function _setPetSprite(name) {
  const el = document.getElementById('pet-sprite');
  if (!el) return;
  const url = '/assets/dot/' + currentCharacterId + '/' + name + '.png';
  if (el.src.indexOf(url) !== -1) return;
  // 歩行フレーム未保有キャラ等で 404 になった場合は idle へフォールバック
  el.onerror = function () {
    el.onerror = null;
    el.src = '/assets/dot/' + currentCharacterId + '/idle_1.png';
  };
  el.src = url;
}

function petWanderTick() {
  if (typeof currentPomodoro !== 'undefined' && currentPomodoro && currentPomodoro.active) return;
  if (petStateNow && petStateNow !== 'idle') return;
  const wrap = document.querySelector('.pet-img-wrap');
  if (!wrap) return;
  const now = Date.now();
  const dt = Math.min(0.5, (now - (WANDER.lastTick || now)) / 1000);
  WANDER.lastTick = now;
  if (WANDER.mode === 'walk') {
    WANDER.x += WANDER.dir * WALK_SPEED * dt;
    if (WANDER.x < WALK_MIN) { WANDER.x = WALK_MIN; WANDER.dir = 1; }
    if (WANDER.x > WALK_MAX) { WANDER.x = WALK_MAX; WANDER.dir = -1; }
    wrap.style.left = (WANDER.x * 100) + '%';
    wrap.style.transform = WANDER.dir < 0 ? 'scaleX(-1)' : 'none';
    if (now - WANDER.lastFrameAt > 160) {
      WANDER.lastFrameAt = now;
      WANDER.frame = 1 - WANDER.frame;
      const hasWalk = WALK_CAPABLE_CHARS.indexOf(currentCharacterId) !== -1;
      _setPetSprite(WANDER.frame ? (hasWalk ? 'walk_1' : 'idle_2') : (hasWalk ? 'walk_2' : 'idle_1'));
    }
    if (now > WANDER.until) {
      WANDER.mode = 'idle';
      WANDER.until = now + 4000 + Math.random() * 6000;
    }
  } else {
    wrap.style.transform = 'none';
    if (now - WANDER.lastFrameAt > 700) {
      WANDER.lastFrameAt = now;
      WANDER.frame = 1 - WANDER.frame;
      _setPetSprite(WANDER.frame ? 'idle_2' : 'idle_1');
    }
    if (now > WANDER.until) {
      WANDER.mode = 'walk';
      WANDER.dir = Math.random() < 0.5 ? -1 : 1;
      WANDER.until = now + 2000 + Math.random() * 2500;
    }
  }
}
setInterval(petWanderTick, 120);

// =============================================================================
// 13. 朝会/終礼ブリーフィング (Phase L3) & Web Speech API (TTS)
// =============================================================================
function updateBriefingBannerText() {
  const btnText = document.getElementById('briefing-quick-text');
  if (!btnText) return;
  const hour = new Date().getHours();
  if (5 <= hour && hour < 12) {
    btnText.innerText = "☀️ 今日の朝会ブリーフィングを聞く";
  } else if (12 <= hour && hour < 18) {
    btnText.innerText = "⛅ 午後の進捗ブリーフィング";
  } else if (18 <= hour && hour < 24) {
    btnText.innerText = "🌙 本日の終礼日報をまとめる";
  } else {
    btnText.innerText = "🌌 夜間ブリーフィング";
  }
}

async function openBriefingModal(forceMode) {
  if (navigator.vibrate) navigator.vibrate(25);
  showToast("📖 ブリーフィングをまとめています…", 1500);
  try {
    const url = forceMode ? `/api/briefing?mode=${encodeURIComponent(forceMode)}` : '/api/briefing';
    const res = await authFetch(url);
    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status}: ${errText.slice(0, 50)}`);
    }
    const data = await res.json();
    if (data.status !== "ok" || !data.briefing) {
      throw new Error(data.message || "データが空です");
    }

    const b = data.briefing;
    
    // イベントリストHTML
    let eventsHtml = "";
    if (b.events_today && b.events_today.length > 0) {
      eventsHtml = b.events_today.map(ev => `
        <div class="note-item" style="padding:4px 0;">
          <div class="note-title" style="font-size:12px;">⏰ ${escapeHtml(ev.start_time || '')}〜${escapeHtml(ev.end_time || '')} <b>${escapeHtml(ev.title || '')}</b></div>
          ${ev.location ? `<div class="note-desc">📍 ${escapeHtml(ev.location)}</div>` : ''}
        </div>
      `).join('');
    } else {
      eventsHtml = `<div class="note-desc">大きな予定はありません（集中作業チャンス！🎯）</div>`;
    }

    // タスクリストHTML
    let tasksHtml = "";
    if (b.mode === 'morning' || b.mode === 'day') {
      if (b.active_tasks && b.active_tasks.length > 0) {
        tasksHtml = b.active_tasks.map(t => `
          <div class="note-item" style="padding:4px 0;">
            <div class="note-title" style="font-size:12px;">⏳ ${escapeHtml(t.title || '')}</div>
          </div>
        `).join('');
      } else {
        tasksHtml = `<div class="note-desc">残タスクなし！素晴らしいです✨</div>`;
      }
    } else {
      if (b.completed_tasks_today && b.completed_tasks_today.length > 0) {
        tasksHtml = b.completed_tasks_today.map(t => `
          <div class="note-item done" style="padding:4px 0;">
            <div class="note-title" style="font-size:12px;">✅ ${escapeHtml(t.title || '')}</div>
          </div>
        `).join('');
      } else {
        tasksHtml = `<div class="note-desc">本日もお疲れ様でした！</div>`;
      }
    }

    // 習慣サマリHTML
    let habitsHtml = "";
    if (b.habits_summary && b.habits_summary.total > 0) {
      const hs = b.habits_summary;
      habitsHtml = `
        <div class="briefing-card-section">
          <div class="briefing-section-title">🌱 習慣達成状況</div>
          <div class="note-desc" style="color:var(--text-main); font-weight:bold;">${hs.done || 0} / ${hs.total || 0} 件達成 (${hs.rate_percent || 0}%)</div>
        </div>
      `;
    }

    const tempVal = (b.weather_summary && typeof b.weather_summary.temperature === 'number') ? b.weather_summary.temperature.toFixed(1) : '20.0';
    const weatherCity = (b.weather_summary && b.weather_summary.city) || '現在地';
    const weatherDesc = (b.weather_summary && b.weather_summary.desc) || '晴れ ☀️';

    window._currentBriefingSpeechText = b.speech_text || "";

    const html = `
      <div style="margin-bottom:8px; font-size:12px; color:var(--text-main); line-height:1.5;">
        ${escapeHtml(b.greeting || '')}
      </div>

      <div class="briefing-card-section">
        <div class="briefing-section-title">🌡️ 現在の天気</div>
        <div class="note-desc" style="color:var(--text-main);">${escapeHtml(weatherCity)}: <b>${escapeHtml(weatherDesc)}</b> (${tempVal}°C)</div>
      </div>

      <div class="briefing-card-section">
        <div class="briefing-section-title">📅 ${b.mode === 'morning' || b.mode === 'day' ? '本日の予定' : '予定振り返り'} (${b.events_today ? b.events_today.length : 0}件)</div>
        ${eventsHtml}
      </div>

      <div class="briefing-card-section">
        <div class="briefing-section-title">📝 ${b.mode === 'morning' || b.mode === 'day' ? '重要TODO' : '本日完了したタスク'}</div>
        ${tasksHtml}
      </div>

      ${habitsHtml}

      <div style="margin-top:10px; padding:8px; background:rgba(255,184,0,0.1); border-left:3px solid var(--accent-amber); border-radius:4px; font-size:12px; font-weight:bold; color:var(--accent-amber);">
        ${escapeHtml(b.encouragement || '')}
      </div>

      <div class="approval-sheet-actions" style="margin-top:14px; gap:8px;">
        <button id="tts-speak-btn" class="btn-approve" onclick="toggleBriefingSpeech()">🔊 音声で聴く</button>
        <button class="btn-deny" onclick="stopBriefingSpeech(); closeBottomSheet();">✖ 閉じる</button>
      </div>
    `;

    openBottomSheet({
      icon: b.mode === 'morning' ? '☀️' : (b.mode === 'evening' ? '🌙' : '⛅'),
      tag: b.mode_label || 'ブリーフィング',
      title: `${b.date_str || ''}`
    }, html);

  } catch (err) {
    console.error("ブリーフィング読み込みエラー:", err);
    showToast(`⚠️ ブリーフィング取得失敗: ${err.message}`, 4500);
  }
}

/** Web Speech API による音声読み上げトグル */
function toggleBriefingSpeech(customText) {
  const text = customText || window._currentBriefingSpeechText || "";
  if (!text) return;
  if (!('speechSynthesis' in window)) {
    showToast("⚠️ お使いのブラウザは音声読み上げに対応していません");
    return;
  }
  const btn = document.getElementById('tts-speak-btn');

  if (window.speechSynthesis.speaking) {
    window.speechSynthesis.cancel();
    if (btn) btn.innerText = "🔊 音声で聴く";
    return;
  }

  window.speechSynthesis.cancel();
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = 'ja-JP';
  utter.rate = 1.05;
  utter.pitch = 1.0;

  const voices = window.speechSynthesis.getVoices();
  const jaVoice = voices.find(v => v.lang === 'ja-JP' || v.lang.startsWith('ja'));
  if (jaVoice) utter.voice = jaVoice;

  utter.onstart = () => {
    if (btn) btn.innerText = "⏹️ 読み上げ停止";
  };
  utter.onend = () => {
    if (btn) btn.innerText = "🔊 音声で聴く";
  };
  utter.onerror = () => {
    if (btn) btn.innerText = "🔊 音声で聴く";
  };

  window.speechSynthesis.speak(utter);
}

function stopBriefingSpeech() {
  if ('speechSynthesis' in window && window.speechSynthesis.speaking) {
    window.speechSynthesis.cancel();
  }
}

function escapeJsString(str) {
  return (str || "").replace(/'/g, "\\'").replace(/"/g, '&quot;').replace(/\n/g, ' ');
}

// =============================================================================
// 🎙️ PC Whisper 音声録音 ＆ タスク自動作成パイプライン (B20)
// =============================================================================
let _voiceMediaRecorder = null;
let _voiceAudioChunks = [];
let _voiceRecordTimeout = null;
let _isVoiceRecording = false;

/** スマホマイク録音の開始/停止トグル */
async function startVoiceInput() {
  // 🔒 フィーチャーフラグ: 品質検証合格まで機能を表に出さない (内部課題 B20)
  if (!VOICE_INPUT_ENABLED) {
    console.info("🎙️ 音声入力は内部品質検証中のため無効化されています (VOICE_INPUT_ENABLED=false)");
    return;
  }
  const micBtn = document.getElementById('mic-btn');

  // 既に録音中の場合はタップで停止して即時文字起こしへ
  if (_isVoiceRecording) {
    stopVoiceRecording();
    return;
  }

  // 🔒 セキュアコンテキスト判定: Chrome は HTTPS / localhost 以外のオリジンでは
  // マイクアクセスを仕様上ブロックする（LAN直結の http://192.168.x.x がこれに該当）。
  // getUserMedia が undefined になる前に分かりやすい日本語ガイダンスを出す。
  if (!window.isSecureContext) {
    showToast('🔒 マイク録音はHTTPS接続でのみ許可されます。<br>' +
      'LAN直結(HTTP)のためブラウザがブロックしています。<br>' +
      '<span style="font-weight:normal;font-size:11px;">テキスト入力は通常どおりご利用できます</span>', 6000);
    return;
  }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    showToast("⚠️ お使いの端末・ブラウザはマイク録音に対応していません");
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    _voiceAudioChunks = [];

    // 最適な mimeType の選択
    let mimeType = 'audio/webm;codecs=opus';
    if (!MediaRecorder.isTypeSupported(mimeType)) {
      if (MediaRecorder.isTypeSupported('audio/webm')) mimeType = 'audio/webm';
      else if (MediaRecorder.isTypeSupported('audio/mp4')) mimeType = 'audio/mp4';
      else mimeType = '';
    }

    // 🎧 音質最適化: audioBitsPerSecond を明示指定（既定約32kbpsだと子音が欠落するため128kbpsへ）
    const recorderOptions = mimeType ? { mimeType, audioBitsPerSecond: 128000 } : {};
    _voiceMediaRecorder = new MediaRecorder(stream, recorderOptions);

    _voiceMediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) {
        _voiceAudioChunks.push(e.data);
      }
    };

    _voiceMediaRecorder.onstop = async () => {
      _isVoiceRecording = false;
      if (micBtn) {
        micBtn.style.background = '';
        micBtn.style.animation = '';
        micBtn.innerHTML = '<span>🎤</span>';
      }
      stream.getTracks().forEach(track => track.stop());

      if (_voiceAudioChunks.length === 0) {
        showToast("⚠️ 録音データが空でした");
        return;
      }

      // 🎧 拡張子を実際の mimeType と一致させる（iPhoneは audio/mp4 で録音されるため、
      //    誤った拡張子だとサーバ側デコーダのフォーマット判定が崩れる）
      const isMp4 = (_voiceMediaRecorder.mimeType || '').indexOf('mp4') !== -1;
      const audioBlob = new Blob(_voiceAudioChunks, { type: _voiceMediaRecorder.mimeType || 'audio/webm' });
      await _sendVoiceToWhisper(audioBlob, isMp4 ? 'voice.mp4' : 'voice.webm');
    };

    _voiceMediaRecorder.start();
    _isVoiceRecording = true;

    // UI演出: ボタン点滅と吹き出し更新
    if (micBtn) {
      micBtn.style.background = 'var(--accent-red)';
      micBtn.style.animation = 'pulse 1s infinite alternate';
      micBtn.innerHTML = '<span>⏹️</span>';
    }
    const bubble = document.getElementById('speech-bubble');
    if (bubble) bubble.innerText = "🎤 音声TODOを録音中…（話しかけてください）";
    showToast("🎙️ 録音開始（最大15秒・タップで終了）");
    if (navigator.vibrate) navigator.vibrate(50);

    // 最大15秒で自動停止
    if (_voiceRecordTimeout) clearTimeout(_voiceRecordTimeout);
    _voiceRecordTimeout = setTimeout(() => {
      if (_isVoiceRecording) {
        stopVoiceRecording();
      }
    }, 15000);

  } catch (err) {
    console.error("マイクアクセスエラー:", err);
    showToast(`⚠️ マイク起動失敗: ${err.message}`);
    _isVoiceRecording = false;
  }
}

/** 録音を手動停止 */
function stopVoiceRecording() {
  if (_voiceRecordTimeout) {
    clearTimeout(_voiceRecordTimeout);
    _voiceRecordTimeout = null;
  }
  if (_voiceMediaRecorder && _voiceMediaRecorder.state !== 'inactive') {
    _voiceMediaRecorder.stop();
  }
}

/** 録音BlobをBase64化してPCの Whisper API へ送信 */
async function _sendVoiceToWhisper(audioBlob, filename) {
  showToast("🧠 PCのWhisperで文字起こし中…");
  const bubble = document.getElementById('speech-bubble');
  if (bubble) bubble.innerText = "🧠 PCで音声解析中…少々お待ちください…";

  try {
    // Blob ➔ Base64 変換
    const reader = new FileReader();
    const base64Promise = new Promise((resolve, reject) => {
      reader.onloadend = () => {
        const base64data = reader.result.split(',')[1];
        resolve(base64data);
      };
      reader.onerror = reject;
    });
    reader.readAsDataURL(audioBlob);
    const audioBase64 = await base64Promise;

    const res = await authFetch('/api/action', {
      method: 'POST',
      body: JSON.stringify({
        action: 'transcribe_voice',
        audio_base64: audioBase64,
        filename: filename || 'voice.webm',
        auto_add_task: true
      })
    });

    const data = await res.json();
    if (data.status === 'ok') {
      const transcript = data.transcript || '';
      if (data.task_created) {
        showToast(`✅ TODO追加: ${data.title || transcript}`, 4000);
        if (bubble) bubble.innerText = `📝 『${data.title || transcript}』をTODOに追加しました！✨`;
        if (navigator.vibrate) navigator.vibrate([60, 80, 60]);
      } else {
        showToast(`🗣️ 認識結果: ${transcript}`, 4000);
        if (bubble) bubble.innerText = `🗣️ 「${transcript}」`;
      }
      fetchStatus();
    } else if (data.status === 'empty_transcript') {
      showToast("⚠️ 音声を認識できませんでした");
      if (bubble) bubble.innerText = "うーん…うまく聞き取れませんでした💦 もう少しはっきり話しかけてください！";
    } else {
      showToast(`⚠️ ${data.message || '文字起こし失敗'}`);
      if (bubble) bubble.innerText = `⚠️ ${data.message || '文字起こしエラー'}`;
    }
  } catch (err) {
    console.error("音声送信エラー:", err);
    showToast(`⚠️ 送信失敗: ${err.message}`);
    if (bubble) bubble.innerText = "⚠️ PCとの通信に失敗しました。接続を確認してください。";
  }
}