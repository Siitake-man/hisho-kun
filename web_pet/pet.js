/**
 * ネオ秘書くん Desk Pet ＆ Agent Bridge Cockpit ロジック (pet.js v7.0 - Stitch Edition)
 * 5大背景環境 ＆ Glass Bottom Sheetニュースリーダー ＆ なでなでパーティクル
 */

let petState = 'idle';
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
  requestAnimationFrame(particleLoop);
  preloadSprites(currentCharacterId);
  fetchStatus();
  setInterval(fetchStatus, 2000);
});

// パーティクルアニメーションループ
function particleLoop() {
  if (envCtx && envCanvas) {
    envCtx.clearRect(0, 0, envCanvas.width, envCanvas.height);

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
  { id: 'kinoko', name: 'キノコ君', emoji: '🍄' },
  { id: 'wombat', name: 'ウォンバット', emoji: '🦫' }
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
    spriteEl.src = `/assets/mascot_${charId}_idle.png`;
    spriteEl.onerror = () => {
      spriteEl.src = `/assets/${charId}_idle.png`;
      spriteEl.onerror = () => {
        spriteEl.src = `/assets/mascot_idle_1.png`;
      };
    };
  }
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
    }

    // 5. 承認・質問イベントバナー
    const eventBanner = document.getElementById('active-event-banner');
    if (data.pending_approval) {
      currentActiveEvent = data.pending_approval;
      eventBanner.style.display = 'block';
      eventBanner.className = '';
      document.getElementById('event-type-badge').innerText = `⚠️ 【${data.pending_approval.agent_name}】承認要請`;
      document.getElementById('event-title').innerText = data.pending_approval.summary || data.pending_approval.command;
      document.getElementById('event-desc').innerText = "タップしてワンタップ承認/却下";
    } else if (data.active_event) {
      currentActiveEvent = data.active_event;
      eventBanner.style.display = 'block';
      eventBanner.className = data.active_event.type || 'completed';
      document.getElementById('event-type-badge').innerText = `✨ 【${data.active_event.agent_name || 'AI'}】`;
      document.getElementById('event-title').innerText = data.active_event.summary || data.active_event.title;
      document.getElementById('event-desc').innerText = "タップして確認";
    } else {
      eventBanner.style.display = 'none';
    }

  } catch (err) {
    console.debug("Status fetch error:", err);
  }
}

function handleActiveEventClick() {
  if (!currentActiveEvent) return;
  if (currentActiveEvent.command) {
    // 承認ダイアログ
    if (confirm(`【承認リクエスト】\n${currentActiveEvent.summary}\nコマンド: ${currentActiveEvent.command}\n\n実行を許可しますか？`)) {
      authFetch('/api/agent/respond', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request_id: currentActiveEvent.request_id, decision: 'approve' })
      }).then(fetchStatus);
    }
  } else {
    openBottomSheet(currentActiveEvent);
  }
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
      return `<div class="note-item"><div class="note-title">📅 ${escapeHtml(e.title)}</div><div class="note-desc">🕐 ${escapeHtml(dt)}</div></div>`;
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
