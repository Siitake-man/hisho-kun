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
let lastProcessedNotificationId = null;
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
let currentCharacterId = 'hisho';

function preloadSprites(charId = 'hisho') {
  currentCharacterId = charId;
  const baseUrl = (typeof getServerBaseUrl === 'function') ? getServerBaseUrl() : '';
  const cacheBuster = Date.now();
  
  // ボタンのアクティブ装飾
  ['hisho', 'kinoko', 'seal', 'wombat'].forEach(cid => {
    const btn = document.getElementById(`char-btn-${cid}`);
    if (btn) {
      if (cid === charId) {
        btn.style.borderColor = '#A67B5B';
        btn.style.borderWidth = '2px';
        btn.style.fontWeight = 'bold';
        btn.style.background = '#FFF8E7';
      } else {
        btn.style.borderColor = '#CCC';
        btn.style.borderWidth = '1px';
        btn.style.fontWeight = 'normal';
        btn.style.background = '#FFF';
      }
    }
  });

  // 古いキャッシュをクリア
  for (const k of Object.keys(spriteCache)) {
    delete spriteCache[k];
  }

  spriteNames.forEach(name => {
    const img = new Image();
    // キャラ固有プレフィックス付き画像を優先読み込み
    img.src = `${baseUrl}/assets/${charId}_${name}.png?t=${cacheBuster}`;
    img.onload = () => {
      spriteCache[name] = img;
      if (name === 'idle_1' && ctx) {
        drawPixelPet(petState, animTick);
      }
    };
    img.onerror = () => {
      // フォールバック: デフォルト画像
      const fallbackImg = new Image();
      fallbackImg.src = `${baseUrl}/assets/${name}.png?t=${cacheBuster}`;
      fallbackImg.onload = () => {
        spriteCache[name] = fallbackImg;
        if (name === 'idle_1' && ctx) {
          drawPixelPet(petState, animTick);
        }
      };
    };
  });
}
preloadSprites('hisho');

async function switchCharacter(charId) {
  preloadSprites(charId);
  const baseUrl = getServerBaseUrl();
  try {
    await fetch(`${baseUrl}/api/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'switch_character', character_id: charId })
    });
    fetchSyncData();
  } catch (e) {
    console.error("キャラクタースキン切り替えエラー:", e);
  }
}

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

// =============================================================================
// 📅 カレンダー手帳 (週間カレンダー ＆ 24hタイムグラフ ＆ リスト)
// =============================================================================
let currentEventView = 'week';
let selectedCalDate = new Date();

function openEventsModal(event) {
  if (event) event.stopPropagation();
  playRetroSound('click');
  document.getElementById('events-modal').style.display = 'flex';
  renderCurrentEventView();
}

function closeEventsModal() {
  document.getElementById('events-modal').style.display = 'none';
}

function switchEventView(viewName) {
  currentEventView = viewName;
  playRetroSound('click');
  
  ['week', 'timeline', 'list'].forEach(v => {
    const btn = document.getElementById(`tab-btn-${v}`);
    const sec = document.getElementById(`events-${v}-view`);
    if (btn) {
      if (v === viewName) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    }
    if (sec) {
      sec.style.display = (v === viewName) ? 'block' : 'none';
    }
  });
  
  renderCurrentEventView();
}

function renderCurrentEventView() {
  if (currentEventView === 'week') {
    renderWeekCalendar();
  } else if (currentEventView === 'timeline') {
    render24hTimeline(selectedCalDate);
  } else {
    renderEventsList();
  }
}

function renderWeekCalendar() {
  const gridEl = document.getElementById('cal-week-grid');
  if (!gridEl) return;
  
  const now = new Date();
  const dayNames = ['日', '月', '火', '水', '木', '金', '土'];
  
  // 今週の日曜日を取得
  const currDay = now.getDay();
  const startOfWeek = new Date(now);
  startOfWeek.setDate(now.getDate() - currDay);
  
  gridEl.innerHTML = '';
  
  for (let i = 0; i < 7; i++) {
    const d = new Date(startOfWeek);
    d.setDate(startOfWeek.getDate() + i);
    
    const isToday = (d.toDateString() === now.toDateString());
    const isSelected = (d.toDateString() === selectedCalDate.toDateString());
    
    // この日の予定をカウント
    const dayStart = new Date(d.getFullYear(), d.getMonth(), d.getDate(), 0, 0, 0).getTime();
    const dayEnd = new Date(d.getFullYear(), d.getMonth(), d.getDate(), 23, 59, 59).getTime();
    const hasEvents = (eventsData || []).filter(e => e.start_time >= dayStart && e.start_time <= dayEnd);
    
    const cell = document.createElement('div');
    cell.className = `cal-day-cell ${isToday ? 'today' : ''} ${isSelected ? 'selected' : ''}`;
    cell.innerHTML = `
      <span class="cal-day-name">${dayNames[d.getDay()]}</span>
      <span class="cal-day-num">${d.getDate()}</span>
      ${hasEvents.length > 0 ? `<span class="cal-dot"></span>` : ''}
    `;
    cell.onclick = () => {
      selectedCalDate = new Date(d);
      playRetroSound('click');
      renderWeekCalendar();
      renderSelectedDayEvents(d, hasEvents);
    };
    gridEl.appendChild(cell);
  }
  
  // 選択日の予定一覧を描画
  const dayStart = new Date(selectedCalDate.getFullYear(), selectedCalDate.getMonth(), selectedCalDate.getDate(), 0, 0, 0).getTime();
  const dayEnd = new Date(selectedCalDate.getFullYear(), selectedCalDate.getMonth(), selectedCalDate.getDate(), 23, 59, 59).getTime();
  const selectedDayEvents = (eventsData || []).filter(e => e.start_time >= dayStart && e.start_time <= dayEnd);
  renderSelectedDayEvents(selectedCalDate, selectedDayEvents);
}

function renderSelectedDayEvents(dateObj, evList) {
  const titleEl = document.getElementById('selected-day-title');
  const listEl = document.getElementById('selected-day-events');
  if (!titleEl || !listEl) return;
  
  const m = dateObj.getMonth() + 1;
  const d = dateObj.getDate();
  const dayNames = ['日', '月', '火', '水', '木', '金', '土'];
  titleEl.innerText = `📅 ${m}/${d} (${dayNames[dateObj.getDay()]}) の予定 (${evList.length}件):`;
  
  if (evList.length === 0) {
    listEl.innerHTML = '<div class="modal-item-card" style="color:#8D6E63; justify-content:center;">予定はありません ☕</div>';
  } else {
    listEl.innerHTML = evList.map(e => {
      const st = new Date(e.start_time);
      const timeStr = `${String(st.getHours()).padStart(2,'0')}:${String(st.getMinutes()).padStart(2,'0')}`;
      return `
        <div class="modal-item-card" style="flex-direction:column; align-items:flex-start; gap:2px;">
          <div style="font-weight:bold; color:#A67B5B;">⏰ ${timeStr}〜</div>
          <div style="font-weight:bold; color:#3E2723;">${e.title}</div>
          ${e.description ? `<div style="font-size:8.5px; color:#6D4C41;">${e.description}</div>` : ''}
        </div>
      `;
    }).join('');
  }
}

function render24hTimeline(dateObj) {
  const container = document.getElementById('timeline-container');
  const dateLabel = document.getElementById('timeline-date-label');
  if (!container) return;
  
  const m = dateObj.getMonth() + 1;
  const d = dateObj.getDate();
  if (dateLabel) dateLabel.innerText = `📅 ${m}/${d} (24時間タイムライン)`;
  
  container.innerHTML = '';
  
  // 24時間スロット生成
  for (let h = 0; h < 24; h++) {
    const slot = document.createElement('div');
    slot.className = 'timeline-hour-slot';
    slot.innerHTML = `<span class="timeline-hour-label">${String(h).padStart(2,'0')}:00</span>`;
    container.appendChild(slot);
  }
  
  // 現在時刻の赤線（今日の場合のみ）
  const now = new Date();
  if (dateObj.toDateString() === now.toDateString()) {
    const nowMins = now.getHours() * 60 + now.getMinutes();
    const nowTop = (nowMins / 60) * 20; // 1時間 = 20px
    const line = document.createElement('div');
    line.className = 'timeline-now-line';
    line.style.top = `${nowTop}px`;
    container.appendChild(line);
  }
  
  // この日の予定をブロック配置
  const dayStart = new Date(dateObj.getFullYear(), dateObj.getMonth(), dateObj.getDate(), 0, 0, 0).getTime();
  const dayEnd = new Date(dateObj.getFullYear(), dateObj.getMonth(), dateObj.getDate(), 23, 59, 59).getTime();
  const dayEvents = (eventsData || []).filter(e => e.start_time >= dayStart && e.start_time <= dayEnd);
  
  dayEvents.forEach(e => {
    const st = new Date(e.start_time);
    const startMins = st.getHours() * 60 + st.getMinutes();
    const topPx = (startMins / 60) * 20;
    const durMins = e.end_time ? Math.max(30, (e.end_time - e.start_time) / 60000) : 60;
    const heightPx = Math.max(16, (durMins / 60) * 20);
    
    const block = document.createElement('div');
    block.className = 'timeline-event-bar';
    block.style.top = `${topPx}px`;
    block.style.height = `${heightPx}px`;
    block.innerHTML = `<b>${String(st.getHours()).padStart(2,'0')}:${String(st.getMinutes()).padStart(2,'0')}</b> ${e.title}`;
    container.appendChild(block);
  });
}

function renderEventsList() {
  const listEl = document.getElementById('events-modal-list');
  if (!listEl) return;
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
}

// =============================================================================
// 🔊 8-bit レトロ効果音シンセサイザー (Web Audio API)
// =============================================================================
let audioCtx = null;

function getAudioContext() {
  if (!audioCtx) {
    const Audio = window.AudioContext || window.webkitAudioContext;
    if (Audio) audioCtx = new Audio();
  }
  if (audioCtx && audioCtx.state === 'suspended') {
    audioCtx.resume().catch(() => {});
  }
  return audioCtx;
}

function playRetroSound(type) {
  const ctx = getAudioContext();
  if (!ctx) return;
  
  // 状態が suspended なら復帰を試みる
  if (ctx.state === 'suspended') {
    ctx.resume();
  }
  
  const now = ctx.currentTime;
  
  if (type === 'alert' || type === 'alarm') {
    // 🔔 承認・質問アラート: 透き通る明るい2和音チャイム（ピンポンパンポーン♪ × 2連打）
    // スマホスピーカーでもはっきり聞こえる高音域 (E5, G5, B5, E6)
    const melody = [
      { f: 659.25, t: 0.00, d: 0.12 }, // E5
      { f: 783.99, t: 0.10, d: 0.12 }, // G5
      { f: 987.77, t: 0.20, d: 0.15 }, // B5
      { f: 1318.51, t: 0.32, d: 0.35 }, // E6
      // 2連打目
      { f: 659.25, t: 0.60, d: 0.12 },
      { f: 783.99, t: 0.70, d: 0.12 },
      { f: 987.77, t: 0.80, d: 0.15 },
      { f: 1318.51, t: 0.92, d: 0.45 }
    ];
    
    melody.forEach(note => {
      // 基音 (Sine)
      const osc1 = ctx.createOscillator();
      const gain1 = ctx.createGain();
      osc1.type = 'sine';
      osc1.frequency.setValueAtTime(note.f, now + note.t);
      gain1.gain.setValueAtTime(0.50, now + note.t);
      gain1.gain.exponentialRampToValueAtTime(0.001, now + note.t + note.d);
      osc1.connect(gain1);
      gain1.connect(ctx.destination);
      osc1.start(now + note.t);
      osc1.stop(now + note.t + note.d + 0.05);

      // 倍音 (Triangle) でチャイムの響き・厚みを付与
      const osc2 = ctx.createOscillator();
      const gain2 = ctx.createGain();
      osc2.type = 'triangle';
      osc2.frequency.setValueAtTime(note.f * 2, now + note.t);
      gain2.gain.setValueAtTime(0.25, now + note.t);
      gain2.gain.exponentialRampToValueAtTime(0.001, now + note.t + note.d * 0.8);
      osc2.connect(gain2);
      gain2.connect(ctx.destination);
      osc2.start(now + note.t);
      osc2.stop(now + note.t + note.d + 0.05);
    });

    // 📳 スマホバイブレーション（2連パルス）
    if (navigator.vibrate) {
      try {
        navigator.vibrate([150, 80, 150, 80, 300]);
      } catch(e) {}
    }
  } else if (type === 'celebrate') {
    // 🎉 作業完了ファンファーレ（明るいメロディ）
    const melody = [
      { f: 523.25, t: 0.00, d: 0.10 }, // C5
      { f: 659.25, t: 0.10, d: 0.10 }, // E5
      { f: 783.99, t: 0.20, d: 0.10 }, // G5
      { f: 1046.50, t: 0.30, d: 0.40 } // C6
    ];
    melody.forEach(note => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(note.f, now + note.t);
      gain.gain.setValueAtTime(0.45, now + note.t);
      gain.gain.exponentialRampToValueAtTime(0.001, now + note.t + note.d);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now + note.t);
      osc.stop(now + note.t + note.d + 0.02);
    });
    if (navigator.vibrate) {
      try {
        navigator.vibrate([200, 100, 200]);
      } catch(e) {}
    }
  } else if (type === 'click') {
    // ピッ（心地よい軽快なタップ音）
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(987.77, now); // B5
    gain.gain.setValueAtTime(0.35, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.06);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.07);
  }
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
// 🤖 外部AI統合コックピット (3大リッチカード: 承認 / 質問回答 / 作業完了)
// =============================================================================
let currentActiveEvent = null;
let lastNotifiedEventKey = null;

function updateActiveEventUI(event) {
  const approvalCard = document.getElementById('approval-card');
  const questionCard = document.getElementById('question-card');
  const completedCard = document.getElementById('completed-card');
  const suggestCard = document.getElementById('suggest-card-container');
  
  if (!approvalCard || !questionCard || !completedCard || !suggestCard) return;

  // すべて一旦リセット
  approvalCard.style.display = 'none';
  questionCard.style.display = 'none';
  completedCard.style.display = 'none';
  suggestCard.style.display = 'none';

  if (!event) {
    // 平常時: サジェストカードを表示
    currentApprovalRequest = null;
    currentActiveEvent = null;
    lastNotifiedEventKey = null;
    suggestCard.style.display = 'flex';
    return;
  }

  const eventKey = `${event.type}_${event.request_id || event.id || event.title}`;
  const isNew = (lastNotifiedEventKey !== eventKey);
  if (isNew) {
    lastNotifiedEventKey = eventKey;
  }

  // 1️⃣ 承認要請
  if (event.type === 'approval') {
    currentApprovalRequest = event;
    currentActiveEvent = event;
    document.getElementById('approval-agent').innerText = `🤖 ${event.agent_name}`;
    document.getElementById('approval-summary').innerText = event.title;
    document.getElementById('approval-cmd').innerText = event.command;
    approvalCard.style.display = 'flex';
    
    petState = 'alarm_ask';
    updateSceneBadge('⚠️ 承認要請');
    document.getElementById('pet-message').innerHTML = `<b>【${event.agent_name}から承認要請】</b><br>${event.title}`;
    
    if (isNew) {
      playRetroSound('alert');
      try { if (navigator.vibrate) navigator.vibrate([200, 100, 200, 100, 300]); } catch (e) {}
    }
  }
  // 2️⃣ 質問・選択肢回答待ち
  else if (event.type === 'question') {
    currentApprovalRequest = null;
    currentActiveEvent = event;
    document.getElementById('question-agent').innerText = `🤖 ${event.agent_name}`;
    document.getElementById('question-title').innerText = event.title;
    
    // 背景・詳細説明の表示
    const detailsElem = document.getElementById('question-details');
    const detailText = event.content || event.details || "";
    if (detailsElem) {
      if (detailText) {
        detailsElem.innerText = detailText;
        detailsElem.style.display = 'block';
      } else {
        detailsElem.style.display = 'none';
      }
    }
    
    // 選択肢ボタンの動的生成
    const choicesGrid = document.getElementById('choices-grid');
    choicesGrid.innerHTML = '';
    
    const choices = event.choices || [];
    if (choices.length > 0) {
      choices.forEach(ch => {
        const btn = document.createElement('button');
        btn.className = 'btn-choice';
        btn.innerHTML = `<span>👉</span> <b>${ch}</b>`;
        btn.onclick = () => sendChoiceAnswer(ch);
        choicesGrid.appendChild(btn);
      });
    }
    
    questionCard.style.display = 'flex';
    petState = 'alarm_ask';
    updateSceneBadge('🔔 確認待ち');
    document.getElementById('pet-message').innerHTML = `<b>【${event.agent_name}からの確認】</b><br>${event.title}`;
    
    if (isNew) {
      playRetroSound('alert');
      try { if (navigator.vibrate) navigator.vibrate([200, 100, 200, 100, 300]); } catch (e) {}
    }
  }
  // 3️⃣ 作業完了通知
  else if (event.type === 'completed') {
    currentApprovalRequest = null;
    currentActiveEvent = event;
    document.getElementById('completed-agent').innerText = `🤖 ${event.agent_name}`;
    document.getElementById('completed-title').innerText = event.title;
    
    const fullSummary = event.details ? `${event.summary}\n\n【詳細】\n${event.details}` : event.summary;
    document.getElementById('completed-summary').innerText = fullSummary || "作業が正常に完了しました！";
    
    completedCard.style.display = 'flex';
    petState = 'celebrate';
    updateSceneBadge('🎉 作業完了');
    document.getElementById('pet-message').innerHTML = `<b>【${event.agent_name}】${event.title}</b><br>${event.summary}`;
    
    if (isNew) {
      playRetroSound('celebrate');
      try { if (navigator.vibrate) navigator.vibrate([150, 80, 150, 80, 300]); } catch (e) {}
    }
  }
  else {
    currentActiveEvent = null;
    suggestCard.style.display = 'flex';
  }
}

async function respondApproval(decision) {
  if (!currentActiveEvent || currentActiveEvent.type !== 'approval') return;
  const baseUrl = getServerBaseUrl();
  try {
    await fetch(`${baseUrl}/api/agent/respond`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        request_id: currentActiveEvent.request_id,
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
    
    currentActiveEvent = null;
    updateActiveEventUI(null);
  } catch (err) {
    console.error("承認送信エラー:", err);
  }
}

async function sendChoiceAnswer(choiceText) {
  if (!currentActiveEvent || currentActiveEvent.type !== 'question') return;
  const baseUrl = getServerBaseUrl();
  try {
    await fetch(`${baseUrl}/api/agent/respond`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        request_id: currentActiveEvent.request_id,
        decision: 'answered',
        message: choiceText
      })
    });
    
    petState = 'happy';
    updateSceneBadge('✓ 回答送信');
    document.getElementById('pet-message').innerText = `✓ 『${choiceText}』と回答しました！`;
    setTimeout(() => { petState = 'idle'; updateSceneBadge('✨ 待機中'); }, 3000);
    
    currentActiveEvent = null;
    updateActiveEventUI(null);
  } catch (err) {
    console.error("回答送信エラー:", err);
  }
}

function sendQuickAnswer(text) {
  sendChoiceAnswer(text);
}

function sendCustomAnswer() {
  const input = document.getElementById('custom-answer-input');
  if (input && input.value.trim()) {
    sendChoiceAnswer(input.value.trim());
    input.value = '';
  }
}

async function dismissCompletedCard() {
  const baseUrl = getServerBaseUrl();
  try {
    await fetch(`${baseUrl}/api/agent/dismiss_completed`, { method: 'POST' });
  } catch (e) {}
  currentActiveEvent = null;
  updateActiveEventUI(null);
  petState = 'idle';
  updateSceneBadge('✨ 待機中');
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

  // 3. WebAudio 無音オシレーター & サウンド初期化
  try {
    const actx = getAudioContext();
    if (actx) {
      if (actx.state === 'suspended') actx.resume().catch(() => {});
      audioWakeCtx = actx;
    }
  } catch (e) {}

  // ユーザーのタップ確認音＆振動
  playRetroSound('click');
  if (navigator.vibrate) navigator.vibrate(100);

  const banner = document.getElementById('wake-banner');
  if (banner) {
    banner.style.background = '#E8F5E9';
    banner.style.borderColor = '#4CAF50';
    banner.style.color = '#2E7D32';
    banner.innerText = '⚡ 通知音・振動・画面ON 稼働中！';
  }
}

function handleGlobalInteraction() {
  activateKeepAwake();
  const actx = getAudioContext();
  if (actx && actx.state === 'suspended') {
    actx.resume().catch(() => {});
  }
}

// 画面復帰時のWakeLock自動再取得
document.addEventListener('visibilitychange', async () => {
  if (document.visibilityState === 'visible' && isKeepAwakeActive) {
    if ('wakeLock' in navigator) {
      try {
        wakeLock = await navigator.wakeLock.request('screen');
      } catch (e) {}
    }
    const video = document.getElementById('nosleep-video');
    if (video) video.play().catch(() => {});
  }
});

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

    // 📲 外部AI（Codex / Antigravity / Claude Code）からの通知処理
    if (data.latest_notification && data.latest_notification.id !== lastProcessedNotificationId) {
      lastProcessedNotificationId = data.latest_notification.id;
      const notif = data.latest_notification;
      
      if (navigator.vibrate) navigator.vibrate([200, 100, 200, 100, 200]);
      
      const reaction = notif.reaction || 'celebrate';
      petState = reaction;
      
      const badgeText = (reaction === 'celebrate') ? '🎉 タスク完了' : ((reaction === 'alarm_ask') ? '⚠️ 確認要請' : '🔔 お知らせ');
      updateSceneBadge(badgeText);
      
      const formattedMsg = `<b>【${notif.agent_name}】${notif.title}</b><br>${notif.message}`;
      document.getElementById('pet-message').innerHTML = formattedMsg;
      
      setTimeout(() => {
        if (petState === reaction) {
          petState = 'idle';
          updateSceneBadge('✨ 待機中');
        }
      }, 6000);
    } else if (data.buzz && !data.latest_notification) {
      if (navigator.vibrate) navigator.vibrate([200, 100, 200, 100, 200]);
      petState = 'cheer';
      updateSceneBadge('📲 PC呼出');
      document.getElementById('pet-message').innerHTML = "📲 <b>PCから呼び出し！</b>";
      setTimeout(() => { petState = 'idle'; updateSceneBadge('✨ 待機中'); }, 4000);
    }

    updatePomodoroUI(data.pomodoro);
    updateActiveEventUI(data.active_event);

    if (data.character && data.character.id && data.character.id !== currentCharacterId) {
      preloadSprites(data.character.id);
    }

    if (!data.active_event && !data.latest_notification && !data.buzz && !data.pomodoro?.active && data.message && petState === 'idle') {
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
