/**
 * ネオ秘書くん Desk Pet ＆ Agent Bridge Cockpit ロジック (pet.js v5.0)
 * ポモドーロ双方向同期 ＆ 多彩な自律生活シーン ＆ 動画スリープ完全防止
 */

let currentTab = 'todo';
let petState = 'idle'; // 'idle', 'focus', 'happy', 'alarm_ask', 'pet_love', 'cheer', 'life_tea', 'life_study', 'life_workout', 'life_sleep', 'life_tv', 'life_clean'
let animTick = 0;
let tasksData = [];
let eventsData = [];
let currentApprovalRequest = null;
let currentPomodoro = { active: false, is_break: false, remaining_seconds: 0, mode_label: "" };
let wakeLock = null;
let lastPingMs = 0;
let isKeepAwakeActive = false;
let isFetching = false;
let audioWakeCtx = null;
let petStreamBound = false;

const canvas = document.getElementById('pet-canvas');
const ctx = canvas.getContext('2d');
ctx.imageSmoothingEnabled = false;

// =============================================================================
// 📺 全画面（フルスクリーン）モード
// =============================================================================
function toggleFullscreen() {
  if (!document.fullscreenElement && !document.webkitFullscreenElement) {
    const docEl = document.documentElement;
    if (docEl.requestFullscreen) {
      docEl.requestFullscreen().catch(() => {});
    } else if (docEl.webkitRequestFullscreen) {
      docEl.webkitRequestFullscreen();
    }
  } else {
    if (document.exitFullscreen) {
      document.exitFullscreen().catch(() => {});
    } else if (document.webkitExitFullscreen) {
      document.webkitExitFullscreen();
    }
  }
  activateKeepAwake();
}

// =============================================================================
// 🎨 PC側と100%完全同一のスプライト画像プリローダー
// =============================================================================
const spriteNames = [
  'idle_1', 'idle_2', 'look_left', 'look_right', 'look_up', 'look_down',
  'thinking_1', 'thinking_2', 'happy', 'focus_1', 'focus_2',
  'sleepy_1', 'sleepy_2', 'alarm_ask', 'pet_love', 'cheer'
];

const spriteCache = {};

function preloadSprites() {
  const baseUrl = getServerBaseUrl();
  spriteNames.forEach(name => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.src = `${baseUrl}/assets/${name}.png?v=5.0`;
    img.onload = () => {
      spriteCache[name] = img;
    };
  });
}
preloadSprites();

// =============================================================================
// 🎨 スプライト描画エンジン ＆ ペット動画ストリームバインド
// =============================================================================
function bindPetVideoStream() {
  if (petStreamBound) return;
  const video = document.getElementById('pet-video');
  if (video && canvas.captureStream) {
    try {
      const stream = canvas.captureStream(10); // 10 fps
      video.srcObject = stream;
      video.play().then(() => {
        petStreamBound = true;
      }).catch(() => {});
    } catch (e) {}
  }
}

function drawPixelPet(state, tick) {
  ctx.clearRect(0, 0, 32, 32);

  let targetSprite = 'idle_1';
  if (state === 'alarm_ask') {
    targetSprite = 'alarm_ask';
  } else if (state === 'pet_love') {
    targetSprite = 'pet_love';
  } else if (state === 'happy' || state === 'life_tv') {
    targetSprite = 'happy';
  } else if (state === 'cheer') {
    targetSprite = 'cheer';
  } else if (state === 'focus' || state === 'life_study' || state === 'life_workout' || state === 'life_clean') {
    targetSprite = (tick % 2 === 0) ? 'focus_1' : 'focus_2';
  } else if (state === 'life_sleep' || state.includes('sleep')) {
    targetSprite = (tick % 2 === 0) ? 'sleepy_1' : 'sleepy_2';
  } else if (state === 'life_tea') {
    targetSprite = (tick % 4 === 0) ? 'happy' : 'idle_1';
  } else if (state.includes('thinking')) {
    targetSprite = (tick % 2 === 0) ? 'thinking_1' : 'thinking_2';
  } else {
    targetSprite = (tick % 8 === 0) ? 'idle_2' : 'idle_1';
  }

  if (spriteCache[targetSprite]) {
    ctx.drawImage(spriteCache[targetSprite], 0, 0, 32, 32);
  } else {
    ctx.fillStyle = "#A67B5B";
    ctx.fillRect(8, 8, 16, 15);
    ctx.fillStyle = "#F5F5DC";
    ctx.fillRect(10, 11, 12, 10);
    ctx.fillStyle = "#4A3B32";
    ctx.fillRect(12, 13, 2, 2);
    ctx.fillRect(19, 13, 2, 2);
    ctx.fillStyle = "#E6D235";
    ctx.fillRect(15, 19, 2, 3);
  }

  if (!petStreamBound) {
    bindPetVideoStream();
  }
}

setInterval(() => {
  animTick++;
  drawPixelPet(petState, animTick);
}, 300);

// =============================================================================
// 🔋 スリープ完全防止エンジン (Active Video ＋ Audio Stream ＋ WakeLock)
// =============================================================================
async function activateKeepAwake() {
  isKeepAwakeActive = true;
  bindPetVideoStream();

  if ('wakeLock' in navigator) {
    try {
      wakeLock = await navigator.wakeLock.request('screen');
    } catch (err) {}
  }
  
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (AudioContext && !audioWakeCtx) {
      audioWakeCtx = new AudioContext();
      const osc = audioWakeCtx.createOscillator();
      const gain = audioWakeCtx.createGain();
      gain.gain.value = 0.00001;
      osc.connect(gain);
      gain.connect(audioWakeCtx.destination);
      osc.start();
    }
    if (audioWakeCtx && audioWakeCtx.state === 'suspended') {
      audioWakeCtx.resume();
    }
  } catch (e) {}

  const banner = document.getElementById('wake-banner');
  if (banner) {
    banner.innerText = "🟢 常時画面ON アクティブ（スリープ防止中）";
    banner.style.background = "#E8F5E9";
    banner.style.borderColor = "#4CAF50";
    banner.style.color = "#2E7D32";
  }
}

function handleGlobalInteraction() {
  if (!isKeepAwakeActive) {
    activateKeepAwake();
  }
}

document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    activateKeepAwake();
    fetchSyncData();
  }
});

// =============================================================================
// ⏰ 時計 ＆ 多彩な自律生活シーンエンジン
// =============================================================================
function updateClock() {
  const now = new Date();
  const h = String(now.getHours()).padStart(2, '0');
  const m = String(now.getMinutes()).padStart(2, '0');
  const s = String(now.getSeconds()).padStart(2, '0');
  document.getElementById('clock-display').innerText = `${h}:${m}:${s}`;
}
setInterval(updateClock, 1000);
updateClock();

function updateSceneBadge(name) {
  const badge = document.getElementById('scene-badge');
  if (badge) badge.innerText = name;
}

// 6大生活シーン定義
const lifeScenes = [
  { state: 'life_tea', badge: '☕ お茶ブレイク中', msg: 'ボス、温かいお茶で一息入れましょう🍵' },
  { state: 'life_study', badge: '📖 読書・勉強中', msg: '新しい技術書を読んでいます！知識の筋トレです📚' },
  { state: 'life_workout', badge: '🏋️ 筋トレ中', msg: 'ふんぬっ！ダンベル10回！ボスも肩を回しましょ💪' },
  { state: 'life_sleep', badge: '🛏️ お昼寝中', msg: 'Zzz...ボス...いつもありがとう...Zzz💤' },
  { state: 'life_tv', badge: '📺 テレビ鑑賞中', msg: 'お笑い番組見てます！リラックス大事ですね📺' },
  { state: 'life_clean', badge: '🧹 お掃除中', msg: '机の上をホウキでパタパタ...ピカピカにします！✨' }
];

let lastLifeSceneChange = Date.now();

function scheduleLifeScenes() {
  // 承認要請中、またはポモドーロ中は生活シーンを上書きしない
  if (currentApprovalRequest || currentPomodoro.active || petState === 'pet_love') {
    return;
  }

  const now = Date.now();
  // 90秒ごとにランダムで生活シーンを切り替え
  if (now - lastLifeSceneChange > 90000) {
    lastLifeSceneChange = now;
    const isSpecialScene = Math.random() < 0.7; // 70%の確率で生活シーン
    if (isSpecialScene) {
      const scene = lifeScenes[Math.floor(Math.random() * lifeScenes.length)];
      petState = scene.state;
      updateSceneBadge(scene.badge);
      document.getElementById('pet-message').innerHTML = scene.msg;
    } else {
      petState = 'idle';
      updateSceneBadge('✨ 待機中');
      document.getElementById('pet-message').innerHTML = 'ボス、見守っています！いつでも声をかけてくださいね✨';
    }
  }
}

setInterval(scheduleLifeScenes, 5000);

function pokePet() {
  petState = 'pet_love';
  updateSceneBadge('💖 なでなで中');
  if (navigator.vibrate) navigator.vibrate([50, 40, 50]);
  handleGlobalInteraction();
  
  const phrases = [
    "えへへ、くすぐったいです！🥰",
    "ボス、いつもお疲れさまです！🔥",
    "机の上から見守ってますよ！✨",
    "いつでも指示してくださいね！👍"
  ];
  document.getElementById('pet-message').innerHTML = phrases[Math.floor(Math.random() * phrases.length)];
  setTimeout(() => {
    if (currentApprovalRequest) {
      petState = 'alarm_ask';
      updateSceneBadge('⚠️ 承認待ち');
    } else if (currentPomodoro.active) {
      petState = currentPomodoro.is_break ? 'happy' : 'focus';
      updateSceneBadge(currentPomodoro.is_break ? '☕ お茶休憩中' : '🔥 集中作業中');
    } else {
      petState = 'idle';
      updateSceneBadge('✨ 待機中');
    }
  }, 2500);
}

// =============================================================================
// 🍅 ポモドーロ双方向同期 ＆ スマホ側起動
// =============================================================================

function updatePomodoroUI(pomodoro) {
  if (!pomodoro) return;
  currentPomodoro = pomodoro;
  const badge = document.getElementById('pomodoro-badge');
  if (!badge) return;

  if (pomodoro.active) {
    const mins = String(Math.floor(pomodoro.remaining_seconds / 60)).padStart(2, '0');
    const secs = String(pomodoro.remaining_seconds % 60).padStart(2, '0');
    const modeStr = pomodoro.is_break ? "☕ 休憩" : "🍅 集中";
    
    badge.innerText = `${modeStr} ${mins}:${secs}`;
    badge.className = `pomodoro-badge ${pomodoro.is_break ? 'break' : ''}`;
    
    if (!currentApprovalRequest && petState !== 'pet_love') {
      if (pomodoro.is_break) {
        petState = 'happy';
        updateSceneBadge('☕ お茶休憩中');
      } else {
        petState = 'focus';
        updateSceneBadge('🔥 集中作業中');
      }
    }
  } else {
    badge.innerText = "🍅 集中開始 (25分)";
    badge.className = "pomodoro-badge idle";
  }
}

async function togglePomodoro() {
  const baseUrl = getServerBaseUrl();
  handleGlobalInteraction();
  if (navigator.vibrate) navigator.vibrate(60);

  const action = currentPomodoro.active ? "stop_pomodoro" : "start_pomodoro";
  try {
    await fetch(`${baseUrl}/api/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: action,
        minutes: 25
      })
    });
    
    if (action === "start_pomodoro") {
      petState = 'focus';
      updateSceneBadge('🔥 集中作業中');
      document.getElementById('pet-message').innerHTML = "🍅 <b>ポモドーロ開始！</b><br>25分間、集中していきましょう！ボス！🔥";
      if (navigator.vibrate) navigator.vibrate([100, 50, 100]);
    } else {
      petState = 'idle';
      updateSceneBadge('✨ 待機中');
      document.getElementById('pet-message').innerHTML = "⏹ <b>ポモドーロを停止しました。</b>";
    }
    
    setTimeout(fetchSyncData, 300);
  } catch (err) {
    alert("通信エラー: " + err);
  }
}

// =============================================================================
// 🤖 Agent Bridge 承認コクピット (Codex / Claude Code / Antigravity)
// =============================================================================

function updateApprovalUI(req) {
  const card = document.getElementById('approval-card');
  if (!card) return;

  if (!req || req.status !== 'pending') {
    currentApprovalRequest = null;
    card.style.display = 'none';
    if (petState === 'alarm_ask') {
      petState = currentPomodoro.active ? (currentPomodoro.is_break ? 'happy' : 'focus') : 'idle';
      updateSceneBadge(currentPomodoro.active ? (currentPomodoro.is_break ? '☕ お茶休憩中' : '🔥 集中作業中') : '✨ 待機中');
    }
    return;
  }

  // 新しい承認要請が届いた場合
  if (!currentApprovalRequest || currentApprovalRequest.request_id !== req.request_id) {
    currentApprovalRequest = req;
    card.style.display = 'block';
    document.getElementById('approval-agent').innerText = `🤖 ${req.agent_name}`;
    document.getElementById('approval-summary').innerText = req.summary || 'コマンド実行の許可要請';
    document.getElementById('approval-cmd').innerText = req.command || '';
    
    petState = 'alarm_ask';
    updateSceneBadge('⚠️ 承認待ち');
    document.getElementById('pet-message').innerHTML = `⚠️ <b>${req.agent_name}</b> からコマンド実行許可！`;
    
    handleGlobalInteraction();
    if (navigator.vibrate) navigator.vibrate([300, 150, 300, 150, 300]);
  }
}

async function respondApproval(decision) {
  if (!currentApprovalRequest) return;
  const baseUrl = getServerBaseUrl();
  const reqId = currentApprovalRequest.request_id;
  
  if (navigator.vibrate) navigator.vibrate(80);
  handleGlobalInteraction();

  try {
    await fetch(`${baseUrl}/api/agent/respond`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        request_id: reqId,
        decision: decision
      })
    });

    if (decision === 'approve') {
      petState = 'happy';
      updateSceneBadge('🎉 承認完了');
      document.getElementById('pet-message').innerHTML = "🎉 <b>承認完了！</b><br>エージェントが作業を再開しました！";
    } else if (decision === 'reject') {
      petState = 'idle';
      updateSceneBadge('🛑 実行拒否');
      document.getElementById('pet-message').innerHTML = "🛑 <b>実行を拒否しました。</b>";
    } else {
      petState = 'focus';
      updateSceneBadge('💬 説明要求');
      document.getElementById('pet-message').innerHTML = "💬 <b>説明を要求しました。</b>";
    }

    document.getElementById('approval-card').style.display = 'none';
    currentApprovalRequest = null;
    setTimeout(fetchSyncData, 300);
  } catch (err) {
    alert("通信エラー: " + err);
  }
}

// =============================================================================
// 📶 リンク死活監視 ＆ 疎通テスト
// =============================================================================

async function testPing() {
  const baseUrl = getServerBaseUrl();
  const t0 = performance.now();
  try {
    const res = await fetch(`${baseUrl}/api/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'ping_test' })
    });
    const t1 = performance.now();
    const rtt = Math.round(t1 - t0);
    if (navigator.vibrate) navigator.vibrate([50, 50, 50]);
    handleGlobalInteraction();
    
    petState = 'happy';
    document.getElementById('pet-message').innerHTML = `📶 <b>疎通成功！</b> (${rtt} ms) ✨`;
    setTimeout(() => { petState = 'idle'; updateSceneBadge('✨ 待機中'); }, 3000);
  } catch (err) {
    document.getElementById('pet-message').innerHTML = "🔴 <b>PC通信エラー</b>";
  }
}

// =============================================================================
// 📋 タスク / 予定 / 設定
// =============================================================================

function switchTab(tab) {
  currentTab = tab;
  document.getElementById('tab-todo').classList.toggle('active', tab === 'todo');
  document.getElementById('tab-calendar').classList.toggle('active', tab === 'calendar');
  renderList();
}

function renderList() {
  const container = document.getElementById('content-list');
  container.innerHTML = '';

  if (currentTab === 'todo') {
    if (tasksData.length === 0) {
      container.innerHTML = '<div class="item-card">📋 すべてのタスク完了 ✨</div>';
      return;
    }
    tasksData.forEach(task => {
      const card = document.createElement('div');
      card.className = 'item-card';
      card.innerHTML = `
        <span>📌 ${task.title}</span>
        <button class="btn-action" onclick="completeTask(${task.id})">完了 ✓</button>
      `;
      container.appendChild(card);
    });
  } else {
    if (eventsData.length === 0) {
      container.innerHTML = '<div class="item-card">📅 直近の予定はありません</div>';
      return;
    }
    eventsData.forEach(ev => {
      const card = document.createElement('div');
      card.className = 'item-card';
      const dtStr = ev.start_time ? new Date(ev.start_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : '終日';
      card.innerHTML = `
        <span>⏰ ${dtStr}: ${ev.title}</span>
      `;
      container.appendChild(card);
    });
  }
}

function getServerBaseUrl() {
  const customUrl = localStorage.getItem('neo_secretary_server_url');
  if (customUrl) return customUrl.replace(/\/$/, '');
  return '';
}

function openSettingsModal() {
  document.getElementById('server-url-input').value = localStorage.getItem('neo_secretary_server_url') || window.location.origin;
  document.getElementById('settings-modal').style.display = 'flex';
}

function closeSettingsModal() {
  document.getElementById('settings-modal').style.display = 'none';
}

function saveServerUrl() {
  const inputVal = document.getElementById('server-url-input').value.trim();
  if (inputVal) {
    localStorage.setItem('neo_secretary_server_url', inputVal);
  } else {
    localStorage.removeItem('neo_secretary_server_url');
  }
  closeSettingsModal();
  preloadSprites();
  fetchSyncData();
}

// リアルタイムデータ同期 (1.5秒間隔・タイムアウト保護付き)
async function fetchSyncData() {
  if (isFetching) return;
  isFetching = true;
  const baseUrl = getServerBaseUrl();
  const t0 = performance.now();
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 3500);

  try {
    const res = await fetch(`${baseUrl}/api/status`, { signal: controller.signal });
    clearTimeout(timeoutId);
    if (!res.ok) throw new Error('Offline');
    const t1 = performance.now();
    lastPingMs = Math.round(t1 - t0);

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
    document.getElementById('todo-count').innerText = tasksData.length;
    renderList();
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
    fetchSyncData();
  } catch (err) {
    tasksData = tasksData.filter(t => t.id !== taskId);
    document.getElementById('todo-count').innerText = tasksData.length;
    renderList();
    pokePet();
  }
}

fetchSyncData();
setInterval(fetchSyncData, 1500);
