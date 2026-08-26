/**
 * ネオ秘書くん Desk Pet ＆ Agent Bridge Cockpit ロジック (pet.js v7.1 - Backoff Edition)
 * 5大背景環境 ＆ Glass Bottom Sheetニュースリーダー ＆ なでなでパーティクル
 */

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
let wakeLock = null;
let currentCharacterId = 'seal';

// 🌈 自律生活ドリーマー状態（/api/status の life_state から更新）
const WEATHER_LABELS_JS = {
  sunny: '☀️ 晴れ', cloudy: '☁️ 曇り', rainy: '🌧️ 雨',
  snowy: '❄️ 雪', thunder: '⚡ 嵐'
};
let currentWeather = 'sunny';
let currentActivity = 'resting';
let lastLifeMessage = '';

// =============================================================================
// 🔐 同期サーバー認証トークン管理 (Zero-Trust Bearer Auth)
// =============================================================================
// PC側の .sync_token と一致するトークンを localStorage に保持し、
// 全APIリクエストに Authorization: Bearer ヘッダーで添付する。
const SYNC_TOKEN_KEY = 'neo_hisho_sync_token';
let syncToken = '';

function loadSyncToken() {
  syncToken = localStorage.getItem(SYNC_TOKEN_KEY) || '';
}

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
  requestAnimationFrame(particleLoop);
  preloadSprites(currentCharacterId);
  fetchStatus();
  (function pollingLoop() {
    fetchStatus();
    const nextInterval = getNextFetchInterval();
    setTimeout(pollingLoop, nextInterval);
  })();
});

// =============================================================================
// 1.5. テーマごとの背景シーン描画（ペットの生活空間）
// =============================================================================
function drawEnvScene() {
  if (!envCtx || !envCanvas) return;
  const w = envCanvas.width, h = envCanvas.height;
  const theme = ENV_THEMES[currentEnvIndex].id;
  const t = Date.now();
  envCtx.save();

  if (theme === 'room') {
    // 暖炉（左下）＋ゆらぐ炎
    const fx = w * 0.12, fy = h * 0.72;
    envCtx.fillStyle = 'rgba(60, 35, 20, 0.9)';
    envCtx.fillRect(fx - 52, fy - 44, 104, 96);
    envCtx.fillStyle = 'rgba(25, 14, 8, 0.95)';
    envCtx.fillRect(fx - 38, fy - 26, 76, 66);
    const flameH = 20 + Math.sin(t / 120) * 5;
    envCtx.fillStyle = 'rgba(255, 140, 0, 0.85)';
    envCtx.beginPath();
    envCtx.moveTo(fx - 14, fy + 22);
    envCtx.quadraticCurveTo(fx - 10, fy + 22 - flameH, fx, fy + 22 - flameH * 1.4);
    envCtx.quadraticCurveTo(fx + 10, fy + 22 - flameH, fx + 14, fy + 22);
    envCtx.fill();
    envCtx.fillStyle = 'rgba(255, 220, 0, 0.9)';
    envCtx.beginPath();
    envCtx.moveTo(fx - 7, fy + 22);
    envCtx.quadraticCurveTo(fx - 4, fy + 22 - flameH * 0.6, fx, fy + 22 - flameH * 0.9);
    envCtx.quadraticCurveTo(fx + 4, fy + 22 - flameH * 0.6, fx + 7, fy + 22);
    envCtx.fill();
    // 本棚（右）
    envCtx.fillStyle = 'rgba(50, 30, 18, 0.9)';
    envCtx.fillRect(w * 0.82, h * 0.52, 74, h * 0.4);
    envCtx.fillStyle = 'rgba(90, 55, 30, 0.95)';
    for (let i = 0; i < 3; i++) envCtx.fillRect(w * 0.82 + 7, h * 0.52 + 12 + i * (h * 0.4 - 22) / 3, 60, 5);
  } else if (theme === 'cafe') {
    // テーブル＋カップ（右下）
    const tx = w * 0.78, ty = h * 0.75;
    envCtx.fillStyle = 'rgba(70, 45, 28, 0.92)';
    envCtx.beginPath();
    envCtx.ellipse(tx, ty, 95, 24, 0, 0, Math.PI * 2);
    envCtx.fill();
    envCtx.fillStyle = 'rgba(45, 28, 16, 0.95)';
    envCtx.fillRect(tx - 8, ty, 16, h - ty);
    envCtx.fillStyle = 'rgba(245, 245, 220, 0.92)';
    envCtx.fillRect(tx - 32, ty - 24, 26, 20);
    envCtx.beginPath();
    envCtx.arc(tx - 19, ty - 24, 9, Math.PI, 0);
    envCtx.fill();
    // 窓（左上）
    envCtx.strokeStyle = 'rgba(190, 155, 120, 0.55)';
    envCtx.lineWidth = 3;
    envCtx.strokeRect(w * 0.07, h * 0.12, w * 0.2, h * 0.28);
    envCtx.beginPath();
    envCtx.moveTo(w * 0.17, h * 0.12); envCtx.lineTo(w * 0.17, h * 0.4);
    envCtx.moveTo(w * 0.07, h * 0.26); envCtx.lineTo(w * 0.27, h * 0.26);
    envCtx.stroke();
  } else if (theme === 'forest') {
    // 木々のシルエット
    const trees = [[0.08, 0.92, 1.0], [0.2, 0.97, 0.65], [0.86, 0.94, 1.1], [0.95, 0.98, 0.55]];
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
    envCtx.fillStyle = 'rgba(22, 58, 30, 0.85)';
    envCtx.fillRect(0, h * 0.9, w, h * 0.1);
  } else if (theme === 'ocean') {
    // 水面の波線
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
    envCtx.fillRect(0, h * 0.92, w, h * 0.08);
  } else if (theme === 'cyber') {
    // ネオンビル群（窓は時間ベースで点滅）
    const buildings = [[0.04, 0.38], [0.14, 0.58], [0.27, 0.46], [0.71, 0.52], [0.83, 0.4], [0.93, 0.62]];
    for (const [px, ph] of buildings) {
      const bx = w * px, bw = w * 0.07, bh = h * ph;
      envCtx.fillStyle = 'rgba(18, 8, 34, 0.95)';
      envCtx.fillRect(bx, h - bh, bw, bh);
      for (let wy = h - bh + 10; wy < h - 12; wy += 16) {
        for (let wx = bx + 5; wx < bx + bw - 8; wx += 12) {
          if ((Math.floor(t / 500) + wx + wy) % 3 !== 0) {
            envCtx.fillStyle = (wx + wy) % 2 === 0 ? 'rgba(0, 229, 255, 0.75)' : 'rgba(255, 23, 68, 0.75)';
            envCtx.fillRect(wx, wy, 5, 7);
          }
        }
      }
    }
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

/** 短時間表示されるトースト通知 */
let toastTimer = null;
function showToast(message) {
  const toast = document.getElementById('theme-toast');
  if (!toast) return;
  toast.innerText = message;
  toast.classList.add('show');
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 1600);
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
  { id: 'seal', name: 'アザラシ', emoji: '🦭' },
  { id: 'hisho', name: '秘書くん', emoji: '👔' },
  { id: 'kinoko', name: 'キノコ君', emoji: '🍄' }
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
  }).catch(() => {});

  if (navigator.vibrate) navigator.vibrate(35);
}

// =============================================================================
// 5. スプライト画像プリローダー
// =============================================================================
function preloadSprites(charId) {
  const spriteEl = document.getElementById('pet-sprite');
  if (spriteEl) {
    // 最優先: 8/15レトロドット絵 (assets/dot/{char}/) → 既存アセットへフォールバック
    spriteEl.src = `/assets/dot/${charId}/idle_1.png`;
    spriteEl.onerror = () => {
      spriteEl.src = `/assets/mascot_${charId}_idle.png`;
      spriteEl.onerror = () => {
        spriteEl.src = `/assets/${charId}_idle.png`;
        spriteEl.onerror = () => {
          spriteEl.src = `/assets/mascot_idle_1.png`;
        };
      };
    };
  }
}

// 🌈 生活イベントに応じたスプライト候補（優先順）
const ACTIVITY_SPRITES = {
  waking:   ['stretch_1', 'stretch', 'idle_1'],
  breakfast: ['happy'],
  lunch:    ['happy'],
  dinner:   ['cheer'],
  bathing:  ['care_1', 'care', 'happy'],
  working:  ['focus_1', 'focus'],
  resting:  ['tea_1', 'tea', 'idle_1'],
  reading:  ['reading_1', 'reading', 'idle_1'],
  sleeping: ['sleepy_1', 'sleepy'],
  playing:  ['celebrate_1', 'celebrate', 'cheer']
};

/**
 * 生活イベントに応じてペットのスプライトを差し替える。
 * dot/{char}/{name}.png を最優先し、無ければ旧形式へフォールバック、
 * 最終的に idle_1 で安定させる。
 */
function updateLifeSprite(activity) {
  const spriteEl = document.getElementById('pet-sprite');
  if (!spriteEl) return;
  const candidates = ACTIVITY_SPRITES[activity] || ['idle_1'];
  // 候補をURL列に展開（dot最優先 → mascot_ → プレーン → idleで安定）
  const urls = [];
  for (const name of candidates) {
    urls.push(`/assets/dot/${currentCharacterId}/${name}.png`);
    urls.push(`/assets/mascot_${currentCharacterId}_${name}.png`);
    urls.push(`/assets/${currentCharacterId}_${name}.png`);
  }
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
}

// =============================================================================
// 6. サジェスト表示 ＆ Glass Bottom Sheet ニュースリーダー
// =============================================================================
function renderSuggestionCard() {
  if (!suggestionsData || suggestionsData.length === 0) {
    document.getElementById('suggest-title').innerText = "予定・タスクはありません";
    document.getElementById('suggest-desc').innerText = "ゆっくりお茶でも飲んで休みましょう🍵";
    return;
  }

  suggestIndex = (suggestIndex + suggestionsData.length) % suggestionsData.length;
  const s = suggestionsData[suggestIndex];
  const total = suggestionsData.length;
  const curr = suggestIndex + 1;
  const icon = s.icon || "💡";
  const tag = s.tag || "サジェスト";

  document.getElementById('suggest-tag').innerText = `${icon} ${tag} (${curr}/${total})`;
  document.getElementById('suggest-title').innerText = s.title || "";
  document.getElementById('suggest-desc').innerText = s.description || "";
}

function onSuggestCardClick() {
  if (!suggestionsData || suggestionsData.length === 0) return;
  const s = suggestionsData[suggestIndex];
  if (!s) return;

  openBottomSheet(s);
}

function openBottomSheet(item, bodyHtml) {
  const sheet = document.getElementById('bottom-sheet');
  const overlay = document.getElementById('bottom-sheet-overlay');
  if (!sheet || !overlay) return;

  document.getElementById('sheet-tag').innerText = `${item.icon || '💡'} ${item.tag || '詳細'}`;
  document.getElementById('sheet-title').innerText = item.title || "";

  const bodyEl = document.getElementById('sheet-body');
  if (typeof bodyHtml === 'string') {
    // 手帳モーダル等のリストHTML表示
    bodyEl.innerHTML = bodyHtml;
    bodyEl.style.maxHeight = '60vh';
  } else {
    bodyEl.innerText = item.description || "詳細情報はありません。";
  }

  // URL抽出（リスト表示時はリンクボタンを隠す）
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

function closeBottomSheet() {
  const sheet = document.getElementById('bottom-sheet');
  const overlay = document.getElementById('bottom-sheet-overlay');
  if (sheet) sheet.classList.remove('open');
  if (overlay) overlay.classList.remove('open');
}

// 15秒ごとにサジェスト自動ローテーション
setInterval(() => {
  if (suggestionsData.length > 1) {
    suggestIndex++;
    renderSuggestionCard();
  }
}, 15000);

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
  authFetch('/api/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'start_pomodoro', minutes: 25 })
  }).then(fetchStatus).catch(() => {});
  if (navigator.vibrate) navigator.vibrate(40);
}

// =============================================================================
// 8. サーバー状態フェッチ ＆ イベント監視
// =============================================================================
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
      currentPomodoro = data.pomodoro;
      const pomoBtn = document.getElementById('pomodoro-btn');
      const timerText = document.getElementById('pomodoro-timer-text');
      if (pomoBtn && timerText) {
        if (currentPomodoro.active) {
          pomoBtn.classList.add('active');
          const mins = Math.floor(currentPomodoro.remaining_seconds / 60);
          const secs = currentPomodoro.remaining_seconds % 60;
          timerText.innerText = `${mins}:${String(secs).padStart(2, '0')}`;
        } else {
          pomoBtn.classList.remove('active');
          timerText.innerText = "25:00";
        }
      }
      // ポモドーロ中はペットスプライトを集中モードに切替
      const spriteEl = document.getElementById('pet-sprite');
      if (spriteEl && currentPomodoro.active && !currentPomodoro.is_break) {
        const focusUrl = `/assets/dot/${currentCharacterId}/focus_1.png`;
        if (spriteEl.src !== focusUrl) spriteEl.src = focusUrl;
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
        }
      } else {
        currentActiveEvent = null;
        lastActiveEventKey = null;
        eventBanner.style.display = 'none';
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
      playAlertChime(2);
      showToast('📲 ボスが呼んでいます！');
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
      updateLifeSprite(currentActivity);
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
      }).catch(() => {});
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
    html = '<div class="note-empty">📅 登録された予定はありません。<br>PC側の手帳やAIチャットで追加できます。</div>';
  } else {
    html = eventsData.map(e => {
      const dt = String(e.start_time || '').replace('T', ' ').slice(0, 16);
      return `<div class="note-item"><div class="note-title">📅 ${escapeHtml(e.title)}</div><div class="note-desc">🕐 ${escapeHtml(dt)}${e.source_name ? " ／ " + escapeHtml(e.source_name) : ""}</div></div>`;
    }).join('');
  }
  openBottomSheet({ icon: '📅', tag: '手帳', title: `予定一覧 (${count}件)` }, html);
}

/** 📝 TODOリストモーダル（項目タップで完了） */
function openTodoModal() {
  const count = tasksData ? tasksData.length : 0;
  let html = '';
  if (count === 0) {
    html = '<div class="note-empty">📝 未完了のTODOはありません。<br>お見事です、ボス！✨</div>';
  } else {
    const prioIcon = { high: '🔥', medium: '⭐', low: '🌱' };
    html = tasksData.map(t => {
      const icon = prioIcon[t.priority] || '⭐';
      return `<div class="note-item" onclick="completeTask(${t.id}, this)"><div class="note-title">${icon} ${escapeHtml(t.title)}</div><div class="note-desc">👆 タップで完了にする</div></div>`;
    }).join('');
  }
  openBottomSheet({ icon: '📝', tag: '手帳', title: `TODOリスト (${count}件)` }, html);
}

/** TODO完了（楽観的UI更新 → サーバー同期 → 再取得） */
function completeTask(taskId, el) {
  if (navigator.vibrate) navigator.vibrate(30);
  if (el) {
    el.classList.add('done');
    const desc = el.querySelector('.note-desc');
    if (desc) desc.innerText = '✅ 完了！お見事です！';
    el.onclick = null;
  }
  authFetch('/api/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'complete_task', task_id: taskId })
  }).then(() => fetchStatus()).catch(() => {});
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
  }).then(() => fetchStatus()).catch(() => {});
}

/** ⚙️ 設定モーダル（キャラ・テーマ・全画面・常時ON・PCペット呼び出し） */
function openSettingsModal() {
  const curChar = CHARACTERS.find(c => c.id === currentCharacterId);
  const html = `
    <div class="note-item" onclick="cycleCharacter(); openSettingsModal();"><div class="note-title">🎭 キャラクター切り替え</div><div class="note-desc">現在: ${curChar ? curChar.emoji + ' ' + curChar.name : ''} → タップで次のキャラへ</div></div>
    <div class="note-item" onclick="cycleEnvTheme(); openSettingsModal();"><div class="note-title">🏞️ 背景テーマ切り替え</div><div class="note-desc">現在: ${ENV_THEMES[currentEnvIndex].label} → タップで次のテーマへ</div></div>
    <div class="note-item" onclick="toggleNoSleep(); closeBottomSheet();"><div class="note-title">💡 常時画面ON</div><div class="note-desc">画面の自動消灯を防ぎます（卓上スマートディスプレイ用）</div></div>
    <div class="note-item" onclick="toggleFullscreen(); closeBottomSheet();"><div class="note-title">⛶ 全画面表示</div><div class="note-desc">ブラウザUIを隠して全画面表示にします</div></div>
    <div class="note-item" onclick="showPcPet()"><div class="note-title">🖥️ PCのペットを呼び出す</div><div class="note-desc">デスクトップのペットを再表示します</div></div>
    <div class="note-item" onclick="closeBottomSheet()"><div class="note-title">✖ 閉じる</div></div>`;
  openBottomSheet({ icon: '⚙️', tag: '設定', title: '設定' }, html);
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
  }).catch(() => {});
}

// =============================================================================
// 11. 全画面表示 ＆ 常時画面ON (NoSleep captureStream 無限生配信)
// =============================================================================

/** 全画面表示トグル (Fullscreen API) */
function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(() => {});
  } else {
    document.exitFullscreen().catch(() => {});
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
