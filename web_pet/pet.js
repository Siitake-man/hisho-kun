/**
 * ネオ秘書くん Desk Pet ＆ Agent Bridge Cockpit ロジック (pet.js v6.0)
 * インテリジェント・サジェスト ＆ オンデマンド手帳 ＆ ポモドーロ双方向同期
 */

let petState = 'idle';
let animTick = 0;
let tasksData = [];
let eventsData = [];
let suggestionsData = [];
let suggestConfig = {};
let suggestIndex = 0;
let currentApprovalRequest = null;
let currentPomodoro = { active: false, is_break: false, remaining_seconds: 0, mode_label: "" };
let wakeLock = null;
let lastPingMs = 0;
let isKeepAwakeActive = false;
let isFetching = false;
let audioWakeCtx = null;
let canvas = null;
let ctx = null;

function initCanvas() {
  canvas = document.getElementById('pet-canvas');
  if (canvas) {
    ctx = canvas.getContext('2d');
    if (ctx) ctx.imageSmoothingEnabled = false;
  }
}
initCanvas();
window.addEventListener('DOMContentLoaded', initCanvas);

// =============================================================================
// ⏰ 大型デジタル時計の更新ループ (1秒ごと)
// =============================================================================
function updateClock() {
  const now = new Date();
  const h = String(now.getHours()).padStart(2, '0');
  const m = String(now.getMinutes()).padStart(2, '0');
  const s = String(now.getSeconds()).padStart(2, '0');
  const clockEl = document.getElementById('clock-display');
  if (clockEl) {
    clockEl.innerText = `${h}:${m}:${s}`;
  }
}
setInterval(updateClock, 1000);
updateClock();

// =============================================================================
// 📺 全画面（フルスクリーン）モード
// =============================================================================
async function toggleFullscreen() {
  const docEl = document.documentElement;
  try {
    if (!document.fullscreenElement && !document.webkitFullscreenElement) {
      if (docEl.requestFullscreen) {
        await docEl.requestFullscreen();
      } else if (docEl.webkitRequestFullscreen) {
        await docEl.webkitRequestFullscreen();
      } else if (docEl.msRequestFullscreen) {
        await docEl.msRequestFullscreen();
      }
    } else {
      if (document.exitFullscreen) {
        await document.exitFullscreen();
      } else if (document.webkitExitFullscreen) {
        await document.webkitExitFullscreen();
      }
    }
  } catch (err) {
    console.warn("全画面切り替えエラー:", err);
  }
  activateKeepAwake();
}

// =============================================================================
// 🎨 PC側と100%完全同一のスプライト画像プリローダー
// =============================================================================
const spriteNames = [
  'idle_1', 'idle_2', 'look_left', 'look_right', 'look_up', 'look_down',
  'thinking_1', 'thinking_2', 'happy', 'focus_1', 'focus_2',
  'sleepy_1', 'sleepy_2', 'alarm_ask', 'pet_love', 'cheer',
  'tea_1', 'tea_2', 'reading_1', 'reading_2', 'stretch_1', 'stretch_2',
  'celebrate_1', 'celebrate_2', 'celebrate_3', 'care_1', 'care_2', 'night_1', 'night_2'
];

const spriteCache = {};

function preloadSprites() {
  const baseUrl = (typeof getServerBaseUrl === 'function') ? getServerBaseUrl() : '';
  spriteNames.forEach(name => {
    const img = new Image();
    img.src = `${baseUrl}/assets/${name}.png?v=8.0`;
    img.onload = () => {
      spriteCache[name] = img;
      if (name === 'idle_1' && ctx) {
        drawPixelPet(petState, animTick);
      }
    };
    img.onerror = (e) => {
      console.warn(`スプライト読込失敗: ${name}`, e);
    };
  });
}
preloadSprites();

function drawPixelPet(state, tick) {
  if (!ctx) initCanvas();
  if (!ctx) return;
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, 64, 64);

  let targetSprite = 'idle_1';
  if (state === 'alarm_ask') {
    targetSprite = 'alarm_ask';
  } else if (state === 'pet_love') {
    targetSprite = 'pet_love';
  } else if (state === 'celebrate') {
    const celFrames = ['celebrate_1', 'celebrate_2', 'celebrate_3', 'celebrate_2'];
    targetSprite = celFrames[tick % celFrames.length];
  } else if (state === 'care') {
    targetSprite = (tick % 2 === 0) ? 'care_1' : 'care_2';
  } else if (state === 'night') {
    targetSprite = (tick % 2 === 0) ? 'night_1' : 'night_2';
  } else if (state === 'focus') {
    targetSprite = (tick % 2 === 0) ? 'focus_1' : 'focus_2';
  } else if (state === 'happy') {
    targetSprite = 'happy';
  } else if (state === 'thinking') {
    targetSprite = (tick % 2 === 0) ? 'thinking_1' : 'thinking_2';
  } else if (state === 'sleepy') {
    targetSprite = (tick % 2 === 0) ? 'sleepy_1' : 'sleepy_2';
  } else if (state === 'cheer') {
    targetSprite = 'cheer';
  } else if (state === 'life_tea') {
    targetSprite = (tick % 2 === 0) ? 'tea_1' : 'tea_2';
  } else if (state === 'life_study') {
    targetSprite = (tick % 2 === 0) ? 'reading_1' : 'reading_2';
  } else if (state === 'life_workout') {
    targetSprite = (tick % 2 === 0) ? 'stretch_1' : 'stretch_2';
  } else if (state === 'life_sleep') {
    targetSprite = (tick % 2 === 0) ? 'night_1' : 'night_2';
  } else {
    targetSprite = (tick % 2 === 0) ? 'idle_1' : 'idle_2';
  }

  const img = spriteCache[targetSprite];
  if (img && img.complete && img.naturalWidth > 0) {
    ctx.drawImage(img, 0, 0, 64, 64);
  } else {
    // フォールバックドット絵描画
    ctx.fillStyle = '#A67B5B';
    ctx.beginPath();
    ctx.arc(32, 32, 24, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#4A3B32';
    ctx.fillRect(24, 26, 4, 4);
    ctx.fillRect(36, 26, 4, 4);
  }
}

// 350msごとにアニメーション進行
setInterval(() => {
  animTick++;
  drawPixelPet(petState, animTick);
}, 350);


// =============================================================================
// 💡 インテリジェント・サジェストの表示とローテーション
// =============================================================================
function renderSuggestionCard() {
  if (!suggestionsData || suggestionsData.length === 0) {
    document.getElementById('suggest-tag').innerText = "💡 サジェスト";
    document.getElementById('suggest-title').innerText = "ボス、今日も素晴らしい一日に！✨";
    document.getElementById('suggest-desc').innerText = "下のメニューからTODOや予定を確認できます。";
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

function nextSuggest() {
  suggestIndex++;
  renderSuggestionCard();
}

function prevSuggest() {
  suggestIndex--;
  renderSuggestionCard();
}

function onSuggestCardClick() {
  if (!suggestionsData || suggestionsData.length === 0) return;
  const s = suggestionsData[suggestIndex];
  if (s && s.source === 'calendar') {
    openEventsModal();
  } else if (s && s.source === 'tasks') {
    openTodoModal();
  }
}

// 15秒ごとに自動ローテーション
setInterval(() => {
  if (suggestionsData.length > 1) {
    nextSuggest();
  }
}, 15000);

// =============================================================================
// 📋 モーダル管理 (TODO手帳 / 予定一覧 / 設定)
// =============================================================================
function openTodoModal(event) {
  if (event) event.stopPropagation();
  const listEl = document.getElementById('todo-modal-list');
  if (!tasksData || tasksData.length === 0) {
    listEl.innerHTML = '<div class="modal-item-card" style="justify-content:center; color:#8D6E63; padding:12px;">未完了のTODOはありません 🎉</div>';
  } else {
    listEl.innerHTML = tasksData.map(t => {
      const pColor = t.priority === 'high' ? '#C62828' : '#4A3B32';
      const badge = t.priority === 'high' ? '🔥 高' : '📋';
      return `
        <div class="modal-item-card">
          <div style="flex:1;">
            <div style="font-weight:bold; color:${pColor};">${badge} ${t.title}</div>
          </div>
          <button class="btn-complete" onclick="completeTask(${t.id})">✓ 完了</button>
        </div>
      `;
    }).join('');
  }
  document.getElementById('todo-modal').style.display = 'flex';
}

function closeTodoModal() {
  document.getElementById('todo-modal').style.display = 'none';
}

function openEventsModal(event) {
  if (event) event.stopPropagation();
  const listEl = document.getElementById('events-modal-list');
  if (!eventsData || eventsData.length === 0) {
    listEl.innerHTML = '<div class="modal-item-card" style="justify-content:center; color:#8D6E63; padding:12px;">直近の予定はありません ☕</div>';
  } else {
    listEl.innerHTML = eventsData.map(e => {
      const d = new Date(e.start_time);
      const timeStr = `${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
      return `
        <div class="modal-item-card" style="flex-direction:column; align-items:flex-start; gap:2px;">
          <div style="font-weight:bold; color:#A67B5B;">📅 ${timeStr}〜</div>
          <div style="color:#4A3B32; font-weight:bold;">${e.title}</div>
          ${e.description ? `<div style="font-size:8.5px; color:#7A6B62;">${e.description}</div>` : ''}
        </div>
      `;
    }).join('');
  }
  document.getElementById('events-modal').style.display = 'flex';
}

function closeEventsModal() {
  document.getElementById('events-modal').style.display = 'none';
}

function openSettingsModal() {
  const container = document.getElementById('suggest-source-checkboxes');
  const sources = suggestConfig.sources || {};
  
  container.innerHTML = Object.keys(sources).map(k => {
    const s = sources[k];
    const checked = s.enabled ? 'checked' : '';
    return `
      <label style="display:flex; align-items:center; gap:6px; font-size:9.5px; color:#4A3B32; cursor:pointer;">
        <input type="checkbox" ${checked} onchange="toggleSuggestSource('${k}', this.checked)">
        <span><b>${s.name}</b></span>
      </label>
    `;
  }).join('');

  document.getElementById('server-url-input').value = getServerBaseUrl();
  document.getElementById('settings-modal').style.display = 'flex';
}

function closeSettingsModal() {
  document.getElementById('settings-modal').style.display = 'none';
}

async function toggleSuggestSource(key, enabled) {
  const baseUrl = getServerBaseUrl();
  try {
    await fetch(`${baseUrl}/api/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'toggle_suggest_source', source_key: key, enabled: enabled })
    });
    fetchSyncData();
  } catch (e) {
    console.error("サジェスト設定変更エラー:", e);
  }
}

// =============================================================================
// 🖥️ PCペット呼出
// =============================================================================
async function callPCPet() {
  const baseUrl = getServerBaseUrl();
  try {
    await fetch(`${baseUrl}/api/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'show_pc_pet' })
    });
    const msg = document.getElementById('pet-message');
    if (msg) msg.innerText = "🖥️ PC画面にペットを呼び出しました！✨";
    pokePet();
  } catch (err) {
    console.error("PCペット呼出エラー:", err);
  }
}

// =============================================================================
// 🍅 ポモドーロタイマー操作 ＆ 同期
// =============================================================================
function togglePomodoro() {
  const baseUrl = getServerBaseUrl();
  if (currentPomodoro.active) {
    fetch(`${baseUrl}/api/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'stop_pomodoro' })
    }).then(() => fetchSyncData());
  } else {
    fetch(`${baseUrl}/api/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'start_pomodoro', minutes: 25 })
    }).then(() => fetchSyncData());
  }
}

function updatePomodoroUI(pomodoro) {
  const badge = document.getElementById('pomodoro-badge');
  if (!badge) return;

  if (pomodoro && pomodoro.active) {
    currentPomodoro = pomodoro;
    const mins = Math.floor(pomodoro.remaining_seconds / 60);
    const secs = pomodoro.remaining_seconds % 60;
    const timeStr = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    
    if (pomodoro.is_break) {
      badge.className = "pomodoro-badge break";
      badge.innerText = `☕ 休憩中 [ ${timeStr} ]`;
    } else {
      badge.className = "pomodoro-badge";
      badge.innerText = `🍅 集中中 [ ${timeStr} ]`;
    }
  } else {
    currentPomodoro = { active: false, is_break: false, remaining_seconds: 0, mode_label: "" };
    badge.className = "pomodoro-badge idle";
    badge.innerText = "🍅 25分集中";
  }
}

// =============================================================================
// ⚠️ Agent Bridge 承認要請 UI
// =============================================================================
function updateApprovalUI(req) {
  const card = document.getElementById('approval-card');
  const suggestCard = document.getElementById('suggest-card-container');
  if (!card) return;

  if (req && req.status === 'pending') {
    currentApprovalRequest = req;
    document.getElementById('approval-agent').innerText = `🤖 ${req.agent_name}`;
    document.getElementById('approval-summary').innerText = req.summary;
    document.getElementById('approval-cmd').innerText = req.command;
    card.style.display = 'block';
    if (suggestCard) suggestCard.style.display = 'none'; // 承認時はサジェストを隠す
    
    petState = 'alarm_ask';
    updateSceneBadge('⚠️ 承認要請');
    document.getElementById('pet-message').innerHTML = `<b>【${req.agent_name}から承認要請】</b><br>${req.summary}`;
  } else {
    currentApprovalRequest = null;
    card.style.display = 'none';
    if (suggestCard) suggestCard.style.display = 'flex';
  }
}

async function respondApproval(decision) {
  if (!currentApprovalRequest) return;
  const baseUrl = getServerBaseUrl();
  try {
    await fetch(`${baseUrl}/api/agent/respond`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        request_id: currentApprovalRequest.request_id,
        decision: decision,
        message: decision === 'approve' ? 'スマホから承認されました' : 'スマホから拒否されました'
      })
    });
    
    if (decision === 'approve') {
      petState = 'celebrate';
      updateSceneBadge('🎉 実行許可');
      document.getElementById('pet-message').innerText = "✓ 承認しました！エージェントが実行します！";
      setTimeout(() => { petState = 'idle'; updateSceneBadge('✨ 待機中'); }, 3000);
    } else {
      petState = 'thinking';
      document.getElementById('pet-message').innerText = "✕ コマンドを拒否しました。";
      setTimeout(() => { petState = 'idle'; }, 2500);
    }
    
    currentApprovalRequest = null;
    updateApprovalUI(null);
  } catch (err) {
    console.error("承認送信エラー:", err);
  }
}

// =============================================================================
// 🎧 Bluetoothイヤホン ＆ 物理音量キーでの遠隔承認 (Agent Bridge Earphone Interface)
// =============================================================================
function setupMediaSessionApproval() {
  if ('mediaSession' in navigator) {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: "🤖 ネオ秘書くん 承認中継",
      artist: "Bluetoothイヤホン遠隔操作",
      album: "＋/次/再生: 承認 | －/前/停止: 拒否"
    });

    const approveHandler = () => {
      if (currentApprovalRequest) {
        respondApproval('approve');
        if (navigator.vibrate) navigator.vibrate([100, 50, 100]);
      }
    };
    const rejectHandler = () => {
      if (currentApprovalRequest) {
        respondApproval('reject');
        if (navigator.vibrate) navigator.vibrate([200]);
      }
    };

    try {
      navigator.mediaSession.setActionHandler('nexttrack', approveHandler);
      navigator.mediaSession.setActionHandler('previoustrack', rejectHandler);
      navigator.mediaSession.setActionHandler('play', approveHandler);
      navigator.mediaSession.setActionHandler('pause', rejectHandler);
    } catch (e) {}
  }
}

// 物理キー・音量キー・キーボードフック
window.addEventListener('keydown', (e) => {
  if (!currentApprovalRequest) return;
  const k = e.key.toLowerCase();
  if (k === 'y' || k === 'enter' || k === 'arrowup' || k === 'volumeup' || k === 'audiovolumeup') {
    respondApproval('approve');
  } else if (k === 'n' || k === 'escape' || k === 'arrowdown' || k === 'volumedown' || k === 'audiovolumedown') {
    respondApproval('reject');
  }
});

// =============================================================================
// 🔋 スリープ完全防止 (NoSleep MP4 Video & Wake Lock & WebAudio)
// =============================================================================
const NO_SLEEP_VIDEO_SRC = "data:video/mp4;base64,AAAAHGZ0eXBtcDQyAAAAAG1wNDJpc29tYXZjMQAAAAhmcmVlAAAAm21kYXQAAAF2AAAABwAAAAAAAAB9AAAABwAAAAAAAAB9AAAABwAAAAAAAAB9AAAABwAAAAAAAAB9AAAABwAAAAAAAAB9AAAABwAAAAAAAAB9AAAABwAAAAAAAAB9AAAABwAAAAAAAAB9AAAABwAAAAAAAAB9AAAAAQAAAAAAAAB9AAAABwAAAAAAAAB9AAAABwAAAAAAAAB9AAAA";

function activateKeepAwake() {
  if (isKeepAwakeActive) return;
  isKeepAwakeActive = true;
  setupMediaSessionApproval();
  
  // 1. 永遠に途切れない生配信動画ストリーム再生（Canvas captureStream ➔ Video）
  const video = document.getElementById('nosleep-video');
  const canvasEl = document.getElementById('pet-canvas');
  if (video) {
    if (canvasEl && canvasEl.captureStream) {
      try {
        const stream = canvasEl.captureStream(10);
        video.srcObject = stream;
        video.play().catch(() => {
          video.src = NO_SLEEP_VIDEO_SRC;
          video.play().catch(() => {});
        });
      } catch (e) {
        video.src = NO_SLEEP_VIDEO_SRC;
        video.play().catch(() => {});
      }
    } else {
      video.src = NO_SLEEP_VIDEO_SRC;
      video.play().catch(() => {});
    }
  }

  // 2. Wake Lock API (HTTPS / localhost 対応)
  if ('wakeLock' in navigator) {
    navigator.wakeLock.request('screen').then(lock => {
      wakeLock = lock;
    }).catch(() => {});
  }

  // 3. WebAudio 無音オシレーター
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (AudioCtx && !audioWakeCtx) {
      audioWakeCtx = new AudioCtx();
      const osc = audioWakeCtx.createOscillator();
      const gain = audioWakeCtx.createGain();
      gain.gain.value = 0.001;
      osc.connect(gain);
      gain.connect(audioWakeCtx.destination);
      osc.start();
    }
  } catch (e) {}

  if (navigator.vibrate) navigator.vibrate(80);

  const banner = document.getElementById('wake-banner');
  if (banner) {
    banner.style.background = '#E8F5E9';
    banner.style.borderColor = '#4CAF50';
    banner.style.color = '#2E7D32';
    banner.innerText = '⚡ 常時画面ON ＆ 🎧イヤホン承認 稼働中';
  }
}

function handleGlobalInteraction() {
  activateKeepAwake();
}

window.addEventListener('pointerdown', handleGlobalInteraction, { passive: true });
window.addEventListener('touchstart', handleGlobalInteraction, { passive: true });
window.addEventListener('click', handleGlobalInteraction, { passive: true });

function updateSceneBadge(text) {
  const b = document.getElementById('scene-badge');
  if (b) b.innerText = text;
}

function pokePet() {
  if (currentApprovalRequest) return;
  petState = 'pet_love';
  updateSceneBadge('💖 なでなで');
  document.getElementById('pet-message').innerText = "えへへ、くすぐったいです！🥰 スマホからも応援してます！";
  setTimeout(() => {
    petState = 'idle';
    updateSceneBadge('✨ 待機中');
  }, 2500);
}

// =============================================================================
// 📡 PC同期ポーリングループ (1.5秒ごと)
// =============================================================================
function getServerBaseUrl() {
  const stored = localStorage.getItem('neo_server_url');
  if (stored) return stored.replace(/\/$/, '');
  const loc = window.location;
  return `${loc.protocol}//${loc.hostname}:${loc.port || '8765'}`;
}

function saveServerUrl() {
  const input = document.getElementById('server-url-input');
  if (input && input.value.trim()) {
    localStorage.setItem('neo_server_url', input.value.trim());
  }
  closeSettingsModal();
  fetchSyncData();
}

async function testPing() {
  const baseUrl = getServerBaseUrl();
  const startTime = Date.now();
  try {
    const res = await fetch(`${baseUrl}/api/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'ping_test' })
    });
    const data = await res.json();
    const latency = Date.now() - startTime;
    alert(`📶 疎通成功！ Ping: ${latency}ms\nサーバー: ${data.status}`);
  } catch (err) {
    alert(`❌ 接続失敗: ${err.message}`);
  }
}

async function fetchSyncData() {
  if (isFetching) return;
  isFetching = true;
  const baseUrl = getServerBaseUrl();
  const startPing = Date.now();

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 3500);

  try {
    const res = await fetch(`${baseUrl}/api/status`, {
      signal: controller.signal,
      cache: 'no-store'
    });
    lastPingMs = Date.now() - startPing;
    const data = await res.json();

    const badge = document.getElementById('status-badge');
    badge.innerText = `LINKED (${lastPingMs}ms)`;
    badge.style.backgroundColor = '#2E7D32';

    if (data.buzz) {
      if (navigator.vibrate) navigator.vibrate([200, 100, 200, 100, 200]);
      petState = 'cheer';
      updateSceneBadge('📲 PC呼出');
      document.getElementById('pet-message').innerHTML = "📲 <b>PCから呼び出し！</b>";
      setTimeout(() => { petState = 'idle'; updateSceneBadge('✨ 待機中'); }, 4000);
    }

    updatePomodoroUI(data.pomodoro);
    updateApprovalUI(data.pending_approval);

    if (!currentApprovalRequest && !data.buzz && !data.pomodoro?.active && data.message && petState === 'idle') {
      document.getElementById('pet-message').innerHTML = data.message;
    }

    tasksData = data.tasks || [];
    eventsData = data.events || [];
    suggestionsData = data.suggestions || [];
    suggestConfig = data.suggest_config || {};

    document.getElementById('todo-count').innerText = tasksData.length;
    renderSuggestionCard();
  } catch (err) {
    const badge = document.getElementById('status-badge');
    badge.innerText = 'OFFLINE';
    badge.style.backgroundColor = '#E53935';
  } finally {
    clearTimeout(timeoutId);
    isFetching = false;
  }
}

async function completeTask(taskId) {
  const baseUrl = getServerBaseUrl();
  try {
    await fetch(`${baseUrl}/api/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'complete_task', task_id: taskId })
    });
    pokePet();
    tasksData = tasksData.filter(t => t.id !== taskId);
    document.getElementById('todo-count').innerText = tasksData.length;
    openTodoModal(); // モーダル再描画
    fetchSyncData();
  } catch (err) {
    console.error("タスク完了エラー:", err);
  }
}

// 1.5秒ごとの高速同期
setInterval(fetchSyncData, 1500);
fetchSyncData();
