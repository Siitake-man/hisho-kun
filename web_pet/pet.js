/**
 * ネオ秘書くん Desk Pet - PWA ロジック (pet.js)
 * 32x32 ピクセルアートアニメーション ＆ PC側ローカル同期
 */

let currentTab = 'todo';
let petState = 'idle'; // 'idle', 'thinking', 'happy'
let animTick = 0;
let tasksData = [];
let eventsData = [];

const canvas = document.getElementById('pet-canvas');
const ctx = canvas.getContext('2d');
ctx.imageSmoothingEnabled = false;

// 32x32 ドット絵描画ルーチン
function drawPixelPet(state, tick) {
  ctx.clearRect(0, 0, 32, 32);

  // 1. ロボット本体（角丸風長方形）
  ctx.fillStyle = "#5B8A72"; // セージグリーン
  ctx.fillRect(8, 10, 16, 14);

  // 2. お腹のスクリーン
  ctx.fillStyle = "#FDFBF7";
  ctx.fillRect(11, 14, 10, 8);

  // 3. アンテナ
  ctx.fillStyle = "#4A3B32";
  ctx.fillRect(15, 6, 2, 4);
  
  // アンテナ先端（思考中はピコピコ点滅）
  if (state === 'thinking') {
    ctx.fillStyle = (tick % 2 === 0) ? "#E63946" : "#CCD5AE";
  } else {
    ctx.fillStyle = "#E63946";
  }
  ctx.fillRect(14, 4, 4, 3);

  // 4. 目・表情
  if (state === 'happy') {
    // 笑顔 (^ ^)
    ctx.fillStyle = "#4A3B32";
    ctx.fillRect(12, 16, 2, 2);
    ctx.fillRect(14, 15, 1, 1);
    ctx.fillRect(17, 15, 1, 1);
    ctx.fillRect(18, 16, 2, 2);
    
    // ほっぺ（ピンク）
    ctx.fillStyle = "#F28482";
    ctx.fillRect(11, 18, 2, 1);
    ctx.fillRect(19, 18, 2, 1);
  } else if (state === 'thinking') {
    // 思考中の目 (o o)
    ctx.fillStyle = "#4A3B32";
    ctx.fillRect(13, 16, 2, 2);
    ctx.fillRect(17, 16, 2, 2);
  } else {
    // 通常待機 (瞬き)
    if (tick % 10 === 0) {
      // 瞬き (- -)
      ctx.fillStyle = "#4A3B32";
      ctx.fillRect(12, 17, 3, 1);
      ctx.fillRect(17, 17, 3, 1);
    } else {
      // パッチリ (● ●)
      ctx.fillStyle = "#4A3B32";
      ctx.fillRect(13, 16, 2, 3);
      ctx.fillRect(17, 16, 2, 3);
    }
  }

  // 5. 手足
  ctx.fillStyle = "#4A3B32";
  // 手
  if (state === 'happy') {
    // バンザイ
    ctx.fillRect(5, 10, 3, 3);
    ctx.fillRect(24, 10, 3, 3);
  } else {
    ctx.fillRect(5, 15, 3, 4);
    ctx.fillRect(24, 15, 3, 4);
  }
  // 足
  ctx.fillRect(11, 24, 4, 3);
  ctx.fillRect(17, 24, 4, 3);
}

// アニメーションループ (500msごと)
setInterval(() => {
  animTick++;
  drawPixelPet(petState, animTick);
}, 400);

// ペットをつついたときのリアクション
function pokePet() {
  petState = 'happy';
  const phrases = [
    "えへへ！ボス、つつきましたね！",
    "ボス！応援してますよ！エイエイオー！",
    "今日も絶好調！いつでも指示してくださいね！",
    "何かお手伝いできることはありますか？"
  ];
  document.getElementById('pet-message').innerHTML = phrases[Math.floor(Math.random() * phrases.length)];
  setTimeout(() => {
    petState = 'idle';
  }, 3500);
}

// タブ切り替え
function switchTab(tab) {
  currentTab = tab;
  document.getElementById('tab-todo').classList.toggle('active', tab === 'todo');
  document.getElementById('tab-calendar').classList.toggle('active', tab === 'calendar');
  renderList();
}

// リスト描画
function renderList() {
  const container = document.getElementById('content-list');
  container.innerHTML = '';

  if (currentTab === 'todo') {
    if (tasksData.length === 0) {
      container.innerHTML = '<div class="item-card">📋 未完了タスクはありません ✨</div>';
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
      container.innerHTML = '<div class="item-card">📅 本日の予定はありません</div>';
      return;
    }
    eventsData.forEach(ev => {
      const card = document.createElement('div');
      card.className = 'item-card';
      card.innerHTML = `
        <span>⏰ ${ev.start_time || '終日'}: ${ev.title}</span>
      `;
      container.appendChild(card);
    });
  }
}

// PC側ローカル同期APIからのデータ取得
async function fetchSyncData() {
  try {
    const res = await fetch('/api/status');
    if (!res.ok) throw new Error('Offline');
    const data = await res.json();

    document.getElementById('status-badge').innerText = 'ONLINE';
    document.getElementById('status-badge').style.backgroundColor = '#5B8A72';

    if (data.message) {
      document.getElementById('pet-message').innerText = data.message;
    }
    if (data.pet_state) {
      petState = data.pet_state;
    }

    tasksData = data.tasks || [];
    eventsData = data.events || [];
    document.getElementById('todo-count').innerText = tasksData.length;
    renderList();
  } catch (err) {
    document.getElementById('status-badge').innerText = 'STANDALONE';
    document.getElementById('status-badge').style.backgroundColor = '#E76F51';
  }
}

// タスク完了API呼び出し
async function completeTask(taskId) {
  try {
    await fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'complete_task', task_id: taskId })
    });
    pokePet();
    fetchSyncData();
  } catch (err) {
    // スタンドアロン動作時
    tasksData = tasksData.filter(t => t.id !== taskId);
    document.getElementById('todo-count').innerText = tasksData.length;
    renderList();
    pokePet();
  }
}

function quickCompleteTopTask() {
  if (tasksData.length > 0) {
    completeTask(tasksData[0].id);
  } else {
    pokePet();
  }
}

function refreshData() {
  fetchSyncData();
  pokePet();
}

// 初回同期と定期ポーリング (5秒ごと)
fetchSyncData();
setInterval(fetchSyncData, 5000);
