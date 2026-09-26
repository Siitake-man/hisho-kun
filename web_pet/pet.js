/**
 * ネオ秘書くん Desk Pet ＆ Agent Bridge Cockpit ロジック (pet.js v7.4)
 * 5大背景環境 ＆ Glass Bottom Sheetニュースリーダー ＆ なでなでパーティクル
 */

// 🧹 古いPWA/ブラウザキャッシュを安全に自動パージ (version.js の WEB_PET_CACHE_NAME を参照)
if ('caches' in window) {
  caches.keys().then(keys => {
    const activeCache = window.WEB_PET_CACHE_NAME || ('neo-pet-v' + (window.APP_VERSION || '1.0.0'));
    keys.forEach(key => {
      if (key !== activeCache) caches.delete(key);
    });
  });
}

let fetchFailCount = 0;
const FETCH_BACKOFF_THRESHOLD = 3;  // 連続3回失敗でバックオフ
const FETCH_NORMAL_INTERVAL = 2000;
const FETCH_BACKOFF_INTERVAL = 30000;
const FETCH_HIDDEN_INTERVAL = 30000;  // 画面非表示時（バックグラウンド/スリープ）は30秒間隔で省電力化
let pollingTimerId = null;  // ポーリングタイマー多重発火防止用ハンドル
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
const _resolvedRequestIds = new Set();
let currentPomodoro = { active: false, is_break: false, remaining_seconds: 0, mode_label: "" };
let petStateNow = 'idle';
// 歩行フレーム(walk_1/2)を持つキャラ（未保有キャラは歩行中も idle フレームで代用）
// ※ pet_motion.js で先行定義された変数を安全に参照
if (typeof WALK_CAPABLE_CHARS === 'undefined') {
  var WALK_CAPABLE_CHARS = window.WALK_CAPABLE_CHARS || ['kyle'];
}
let wakeLock = null;
if (typeof currentCharacterId === 'undefined') {
  var currentCharacterId = window.currentCharacterId || 'hisho';
}
// 🐛 S3 (2026-09-26): 初回 status 同期時に sprite を必ず再確定するフラグ。
// index.html 静的初期 src（誤キャラの可能性）を、最初の /api/status 応答で正規キャラへ自己修復させる。
// キャラ ID 一致でも初回だけは preloadSprites を発火させるために存在する。
let spriteSynced = false;
// 📱 案α (ID 63・2026-09-26): 質問シート自動オープンの重複防止ガード。
// ※ 宣言はファイル先頭に置くこと (fetchStatus はページ初期化直後に走るため、
//   末尾での let 宣言は TDZ ReferenceError で初回発火が必ず失敗する — 2026-09-26 実測)。
let _autoOpenedQuestionId = null;

// 🌈 自律生活ドリーマー状態（/api/status の life_state から更新）
const WEATHER_LABELS_JS = {
  sunny: '☀️ 晴れ', cloudy: '☁️ 曇り', rainy: '🌧️ 雨',
  snowy: '❄️ 雪', thunder: '⚡ 嵐'
};
let currentWeather = 'sunny';
if (typeof currentActivity === 'undefined') {
  var currentActivity = window.currentActivity || 'resting';
}
let lastLifeMessage = '';

let currentAgentBadgeState = '';

// 🌐 各Seamモジュール (pet_motion.js, pet_ui.js) とのグローバル状態共有
window.suggestionsData = suggestionsData;
window.currentApprovalRequest = currentApprovalRequest;
window.currentActiveEvent = currentActiveEvent;
window._resolvedRequestIds = _resolvedRequestIds;
window.currentPomodoro = currentPomodoro;
window.petStateNow = petStateNow;
window.currentCharacterId = currentCharacterId;
window.currentActivity = currentActivity;

// =============================================================================
// 🔐 認証トークン管理 ＆ authFetch (pet_auth.js にSeam分離済み)
// =============================================================================
// ※ SYNC_TOKEN_KEY, syncToken, loadSyncToken, setSyncToken, authFetch は
//    先行読み込みされる pet_auth.js で定義および window に公開されています。
if (typeof authFetch === 'undefined' && typeof window.authFetch !== 'undefined') {
  var authFetch = window.authFetch;
}
if (typeof syncToken === 'undefined' && typeof window.syncToken !== 'undefined') {
  var syncToken = window.syncToken;
}

// =============================================================================
// 1. 背景環境シーン ＆ パーティクル描画エンジン (pet_particles.js に委譲)
// =============================================================================
function initDeskPetApp() {
  try { if (typeof initEnvCanvas === 'function') initEnvCanvas(); } catch (e) { console.warn('initEnvCanvas error:', e); }
  try { if (typeof loadSyncToken === 'function') loadSyncToken(); } catch (e) { console.warn('loadSyncToken error:', e); }
  try { if (typeof unlockAudio === 'function') unlockAudio(); } catch (e) { console.warn('unlockAudio error:', e); }
  try { if (typeof setupMediaKeyApproval === 'function') setupMediaKeyApproval(); } catch (e) { console.warn('setupMediaKeyApproval error:', e); }
  try { if (typeof setupBannerSwipe === 'function') setupBannerSwipe(); } catch (e) { console.warn('setupBannerSwipe error:', e); }
  try { if (typeof setupSuggestSwipe === 'function') setupSuggestSwipe(); } catch (e) { console.warn('setupSuggestSwipe error:', e); }
  try {
    if (typeof wakeParticleLoop === 'function') {
      wakeParticleLoop();
    } else if (typeof particleLoop === 'function') {
      requestAnimationFrame(particleLoop);
    }
  } catch (e) { console.warn('particleLoop error:', e); }
  try { if (typeof preloadSprites === 'function') preloadSprites(window.currentCharacterId || currentCharacterId); } catch (e) { console.warn('preloadSprites error:', e); }
  // 📡 S3.5 (2026-09-26): 初回 status 到達前から「接続中」を明示し、既定表示を見せかけの正常状態にさせない
  try { markConnectionState('connecting'); } catch (e) { console.warn('conn badge init error:', e); }
  
  // 🐛 バグ修正 (2026-08-31): 通知キーをsessionStorageに永続化
  try {
    window._lastNotifKey = sessionStorage.getItem('lastNotifKey') || null;
  } catch (e) {}

  window.triggerPollingStep = function triggerPollingStep() {
    if (pollingTimerId !== null) {
      clearTimeout(pollingTimerId);
      pollingTimerId = null;
    }
    fetchStatus();
    const nextInterval = getNextFetchInterval();
    pollingTimerId = setTimeout(triggerPollingStep, nextInterval);
  };
  window.triggerPollingStep();
}

if (document.readyState === 'loading') {
  window.addEventListener('DOMContentLoaded', initDeskPetApp);
} else {
  initDeskPetApp();
}

// =============================================================================
// =============================================================================
// 1.5. 高視認性HUDトースト通知 (pet_ui.js に委譲)
// =============================================================================
// ※ showToast は先行読み込みされる pet_ui.js で定義および window に公開されています。
if (typeof showToast === 'undefined' && typeof window.showToast !== 'undefined') {
  var showToast = window.showToast;
}

// =============================================================================
// 3. なでなでインタラクション (Spring & Haptics & Particles & Web Audio SE)
//    ※ 音声・効果音合成エンジンは pet_audio_se.js に委譲
// =============================================================================

// =============================================================================
// 3.5. 通知チャイム ＆ ポーリング状態管理
// =============================================================================
let lastApprovalRequestId = null;
let lastActiveEventKey = null;
let lastReminderKey = null;

// 🛡 通知再表示 (2026-08-31): 画面OFF/バックグラウンド中に通知トーストが描画されると
//   音だけ鳴って表示は失われ、再読み込みするまで出ない障害の根本対策。
//   非表示中に通知を処理していた場合はキーをリセットし、復帰後の最初のポーリングで
//   サーバー (60秒TTL) から再取得・再表示させる。
// 🛡 画面表示状態に応じた適応型ポーリング ＆ 通知再表示
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) {
    // 画面復帰時: 即時同期とタイマーリセット（遅延ゼロ化）
    if (window._notifShownWhileHidden) {
      window._notifShownWhileHidden = false;
      window._lastNotifKey = null;
    }
    if (typeof window.triggerPollingStep === 'function') {
      window.triggerPollingStep();
    } else if (typeof fetchStatus === 'function') {
      fetchStatus();
    }
  } else {
    // 画面非表示時: 次のインターバルを低頻度(30秒)に切り替え
    if (pollingTimerId !== null) {
      clearTimeout(pollingTimerId);
      const nextInterval = getNextFetchInterval();
      pollingTimerId = setTimeout(window.triggerPollingStep, nextInterval);
    }
  }
});

// =============================================================================
// 2. なでなで・キャラクター・生活・歓喜演出 (pet_motion.js に委譲)
// =============================================================================
// ※ onPetTap, cycleCharacter, preloadSprites, updateLifeSprite,
//    updatePetLifeActivity, triggerCelebrateReaction, petWanderTick
//    は先行読み込みされる pet_motion.js で定義および window に公開されています。

// =============================================================================
// 3. サジェスト・ボトムシート・時計・ポモドーロ・バッジUI (pet_ui.js に委譲)
// =============================================================================
// ※ renderSuggestionCard, nextSuggest, prevSuggest, onSuggestCardClick,
//    quickCompleteCurrentTask, openBottomSheet, closeBottomSheet, onSheetCompleteTask,
//    setupSuggestSwipe, triggerSecretRoomIris, updateClock, togglePomodoro,
//    updateAgentActivityBadge, AGENT_BADGE_STYLES
//    は先行読み込みされる pet_ui.js で定義および window に公開されています。


// =============================================================================
// 1.2 接続状態バッジ (S3.5・2026-09-26): status 取得失敗を沈黙させない
// =============================================================================
let connBadgeEl = null;

/** 接続状態バッジの DOM 要素を遅延生成して取得する。 */
function ensureConnStateBadge() {
  if (connBadgeEl) return connBadgeEl;
  connBadgeEl = document.createElement('div');
  connBadgeEl.id = 'conn-state-badge';
  connBadgeEl.style.cssText = 'position:fixed;top:8px;left:50%;transform:translateX(-50%);z-index:9999;padding:3px 10px;border-radius:10px;font-size:11px;font-weight:bold;background:rgba(255,184,0,0.85);color:#1E140E;display:none;box-shadow:0 2px 6px rgba(0,0,0,0.4);pointer-events:none;';
  document.body.appendChild(connBadgeEl);
  return connBadgeEl;
}

/**
 * 接続状態を画面上部バッジへ反映する (S3.5)。
 * 従来は /api/status 失敗時に既定表示のまま沈黙し、「壊れた画面」と「読み込み中」の区別が付かなかった。
 *
 * @param {string} state 'connecting' | 'ok' | 'error'
 * @param {string} [detail] エラー時の補足情報 (HTTP ステータス等)
 * @returns {void}
 */
function markConnectionState(state, detail) {
  try {
    const el = ensureConnStateBadge();
    if (state === 'ok') {
      el.style.display = 'none';
      return;
    }
    if (state === 'connecting') {
      el.textContent = '📡 接続中…';
      el.style.background = 'rgba(255,184,0,0.85)';
      el.style.color = '#1E140E';
      el.style.display = 'block';
      return;
    }
    el.textContent = `🔴 接続できません (${detail || 'error'})・自動再試行中…`;
    el.style.background = 'rgba(200,50,50,0.9)';
    el.style.color = '#FFF';
    el.style.display = 'block';
  } catch (e) {
    console.warn('conn badge error:', e);
  }
}

/** 連続失敗の計上とバックオフ移行（fetchStatus の !res.ok と catch から共通利用）。 */
function handleFetchFailure() {
  fetchFailCount++;
  if (fetchFailCount >= FETCH_BACKOFF_THRESHOLD && !fetchBackoffActive) {
    fetchBackoffActive = true;
    // 連続失敗 → 30秒バックオフ (バッテリー・発熱対策)
    showToast('📡 サーバーとの接続が不安定です。バックオフ中…');
  }
}

async function fetchStatus() {
  try {
    const res = await authFetch('/api/status');
    if (!res.ok) {
      // 🐛 S3.5 (2026-09-26): サイレント撤退 (`if (!res.ok) return;`) を廃止。
      // 失敗を接続バッジへ可視化し、失敗回数にも数える（429 はレートリミット案内を追加）。
      if (res.status === 429 && !fetchBackoffActive) {
        showToast('⏳ 認証の試行制限中です。まもなく自動再試行します');
      }
      markConnectionState('error', `HTTP ${res.status}`);
      handleFetchFailure();
      return;
    }
    const data = await res.json();
    markConnectionState('ok');

    // 成功時はバックオフを即座に解除
    if (fetchBackoffActive || fetchFailCount > 0) {
      fetchFailCount = 0;
      fetchBackoffActive = false;
    }

    // 🛡️ P0-1 (2026-09-22): ステータス応答で Bearer トークンを上書きしない。
    // /api/status はマスターキーを配布しなくなったため、トークン更新の唯一の経路は
    // pet_auth.js の requestSyncToken() (401/403 時の /api/auth/token = ペアリング開放 + 人間承認) のみ。
    // 旧実装はここでステータス応答内のトークンを保存し、端末個別トークンをマスターキーへ
    // 昇格させていた (「個別失効させても通信が通り続ける」権限昇格の真因)。

    // 0. ペット状態（歩行コントローラーのガード用 ＆ 歓喜アニメーション連動）
    if (!window._celebratingUntil || Date.now() > window._celebratingUntil) {
      if (data.pet_state === 'celebrate' && petStateNow !== 'celebrate') {
        triggerCelebrateReaction(4000);
      } else {
        petStateNow = data.pet_state || 'idle';
        window.petStateNow = petStateNow;
      }
    }

    // 🌐 デスクトップ側言語設定との自動同期（直近ユーザー手動切替時は巻き戻しを抑止）
    if (data.language && window.NeoLang) {
      const isOverride = typeof window.NeoLang.isUserOverrideActive === 'function' && window.NeoLang.isUserOverrideActive();
      if (!isOverride && window.NeoLang.getLang() !== data.language) {
        window.NeoLang.setLang(data.language, false);
      }
    }

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
    if (data.character) {
      // 🐛 S3 (2026-09-26): 初回同期時はキャラ ID 一致でも sprite を再確定する。
      // HTML 静的初期 src が誤キャラ (ロースター除外中の seal 等) のまま残る事故の恒久修理。
      const needsSpriteResync = !spriteSynced || data.character.id !== currentCharacterId;
      spriteSynced = true;
      if (needsSpriteResync) {
        currentCharacterId = data.character.id;
        window.currentCharacterId = currentCharacterId;
        const emojiEl = document.getElementById('char-emoji');
        if (emojiEl) emojiEl.innerText = data.character.emoji;
        preloadSprites(currentCharacterId);
      }
    }

    // 3. サジェストデータ
    if (data.suggestions) {
      suggestionsData = data.suggestions;
      window.suggestionsData = suggestionsData;
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
      window.currentPomodoro = currentPomodoro;
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
    if (data.pending_approval && !_resolvedRequestIds.has(data.pending_approval.request_id)) {
      const req = data.pending_approval;
      const isNew = (!currentApprovalRequest || currentApprovalRequest.request_id !== req.request_id);
      currentApprovalRequest = req;
      currentActiveEvent = req;
      window.currentApprovalRequest = req;
      window.currentActiveEvent = req;
      eventBanner.style.display = 'block';
      eventBanner.style.opacity = '1';
      eventBanner.style.transform = '';
      eventBanner.style.transition = '';
      const isQuestion = (req.type === 'question');
      if (isQuestion) {
        eventBanner.className = 'question';
        document.getElementById('event-type-badge').innerText = `❓ 【${req.agent_name}】質問`;
        document.getElementById('banner-hint').innerText = 'タップで回答';
        document.getElementById('event-title').innerText = req.title || req.question || '';
        document.getElementById('event-desc').innerText = (req.choices && req.choices.length > 0) ? `選択肢: ${req.choices.join(' / ')}` : 'タップして回答';
        if (bannerActions) bannerActions.style.display = 'none';
      } else {
        const isStrict = (req.risk_level === 'strict');
        eventBanner.className = isStrict ? 'strict' : 'prompt';
        const badgeIcon = isStrict ? '🚨' : '🛡️';
        const badgeLabel = isStrict ? '高リスク承認要請' : '承認要請';
        document.getElementById('event-type-badge').innerText = `${badgeIcon} 【${req.agent_name}】${badgeLabel}`;
        document.getElementById('banner-hint').innerText = isStrict ? '破壊的変更の可能性' : 'ボタンでワンタップ回答';
        document.getElementById('event-title').innerText = req.summary || req.command || '';
        document.getElementById('event-desc').innerText = req.command ? `⌨️ ${req.command}` : '';
        if (bannerActions) bannerActions.style.display = 'flex';
      }
      if (isNew) {
        lastApprovalRequestId = req.request_id;
        window._notifDisplayedAt = Date.now(); // 🛡 buzzによる上書きトースト防止
        const isStrict = (req.risk_level === 'strict');
        if (isStrict) {
          playAlertChime(5);
          if (navigator.vibrate) navigator.vibrate([200, 100, 200, 100, 400]);
        } else {
          playAlertChime(4);
          if (navigator.vibrate) navigator.vibrate([100, 60, 100]);
        }
        // 重複防止: 中央バナー（active-event-banner）に操作面を一本化しトーストは出さない
      }
      // 📱 案α (ID 63・2026-09-26): 質問着信時にシートを自動オープン
      // (PWA 既定表示のまま「タップで回答」を見失くさない。ガードは関数内・同一 request_id 1回のみ)
      if (isQuestion) {
        maybeAutoOpenQuestionSheet();
      }
    } else {
      currentApprovalRequest = null;
      window.currentApprovalRequest = null;
      if (bannerActions) bannerActions.style.display = 'none';
      if (data.active_event) {
        const ev = data.active_event;
        // 🛡️ 完了通知かつユーザーが消去（dismiss）済みなら即座に非表示を維持
        const isDismissed = (ev.type === 'completed') && (
          (typeof isCompletedDismissed === 'function' && isCompletedDismissed(ev)) ||
          (ev.id && sessionStorage.getItem('dismissed_completed_' + ev.id) === '1') ||
          (ev.timestamp && sessionStorage.getItem('dismissed_completed_' + ev.timestamp) === '1')
        );
        if (isDismissed) {
          eventBanner.style.display = 'none';
          currentActiveEvent = null;
          window.currentActiveEvent = null;
        } else {
          const eventKey = `${ev.type || ''}:${ev.timestamp || ''}:${ev.summary || ev.title || ''}`;
          const isNew = (lastActiveEventKey !== eventKey);
          lastActiveEventKey = eventKey;
          currentActiveEvent = ev;
          window.currentActiveEvent = ev;
          eventBanner.style.display = 'block';
          eventBanner.style.opacity = '1';
          eventBanner.style.transform = '';
          eventBanner.style.transition = '';
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
            window._notifDisplayedAt = Date.now();
            playAlertChime(2);
            // 🛡️ 重複排除: バナーが表示されるため上部HUDトーストは出さない
            if (navigator.vibrate) navigator.vibrate([120, 80, 120, 80, 240]);
            triggerCelebrateReaction(4000);
            if (window.EasterEggEngine) EasterEggEngine.playSound('revive');
          }
        }
      } else if (data.due_reminders && data.due_reminders.length > 0) {
        const rem = data.due_reminders[0];
        const remKey = `${rem.type || 'reminder'}:${rem.title || ''}:${rem.due_at || ''}`;
        const isNew = (lastReminderKey !== remKey);
        lastReminderKey = remKey;
        currentActiveEvent = rem;
        window.currentActiveEvent = rem;
        eventBanner.style.display = 'block';
        eventBanner.style.opacity = '1';
        eventBanner.style.transform = '';
        eventBanner.style.transition = '';
        eventBanner.className = 'reminder';
        document.getElementById('event-type-badge').innerText = '⏰ 予定リマインダー';
        document.getElementById('banner-hint').innerText = '10分前のお知らせ';
        document.getElementById('event-title').innerText = rem.title || '予定の時間です';
        document.getElementById('event-desc').innerText = rem.message || rem.due_at || '';
        const dismissBtn = document.getElementById('banner-dismiss-btn');
        if (dismissBtn) dismissBtn.style.display = '';
        if (bannerActions) bannerActions.style.display = 'none';
        if (isNew) {
          window._notifDisplayedAt = Date.now();
          playAlertChime(3);
          // 🛡️ 重複排除: リマインダーバナーが表示されるため上部HUDトーストは出さない
          if (navigator.vibrate) navigator.vibrate([150, 100, 150, 100, 300]);
          petStateNow = 'alarm_ask';
          if (window.EasterEggEngine) EasterEggEngine.playSound('alarm');
        }
      } else {
        currentActiveEvent = null;
        window.currentActiveEvent = null;
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
        window._notifDisplayedAt = Date.now();
        window._notifShownWhileHidden = document.hidden;
        triggerCelebrateReaction(4000);
        const msgEl = document.getElementById('speech-bubble');
        if (msgEl) {
          msgEl.innerText = `🎉 【${notif.agent_name}】${notif.title}\n${notif.message}`;
        }
        // 🛡️ 重複排除: ペットの頭上コミック吹き出しで愛らしく伝えるため上部トーストは出さない
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
    if (data.buzz && !data.pending_approval && !data.active_event) {
      // 🛡️ バナー（承認・完了）表示中はバナーに集中させるためトーストを出さない
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
    markConnectionState('error', (err && err.name === 'AbortError') ? 'timeout' : 'network');
    handleFetchFailure();
  }
}

// ポーリング間隔を返す（非表示時は30秒、バックオフ中は30秒、通常表示中は2秒）
function getNextFetchInterval() {
  if (fetchBackoffActive) return FETCH_BACKOFF_INTERVAL;
  if (typeof document !== 'undefined' && document.hidden) return FETCH_HIDDEN_INTERVAL;
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

// ※ dismissCompleted, isCompletedDismissed は先行読み込みされる pet_ui.js で定義および window に公開されています。
if (typeof dismissCompleted === 'undefined' && typeof window.dismissCompleted !== 'undefined') {
  var dismissCompleted = window.dismissCompleted;
}
if (typeof isCompletedDismissed === 'undefined' && typeof window.isCompletedDismissed !== 'undefined') {
  var isCompletedDismissed = window.isCompletedDismissed;
}

/** アップデートバナーを閉じる（sessionStorageで永続化：同一セッションでは再表示しない） */
function dismissUpdateBanner() {
  const banner = document.getElementById('update-banner');
  if (banner) banner.style.display = 'none';
  sessionStorage.setItem('update_banner_dismissed', 'true');
}

// =============================================================================
// 12. バナースワイプ・承認・質問・MediaSession (pet_ui.js に委譲)
// =============================================================================
// ※ setupBannerSwipe, openApprovalSheet, openQuestionSheet, respondChoice,
//    respondApproval, setupMediaKeyApproval
//    は先行読み込みされる pet_ui.js で定義および window に公開されています。


// =============================================================================
// 10. 手帳モーダル（予定・TODO・習慣・設定）本実装
// =============================================================================

// ※ escapeHtml は先行読み込みされる pet_ui.js で定義および window に公開されています。
if (typeof escapeHtml === 'undefined' && typeof window.escapeHtml !== 'undefined') {
  var escapeHtml = window.escapeHtml;
}

/** 📅 予定一覧モーダル */
function openEventsModal() {
  window._currentOpenModalName = 'events';
  const t = window.NeoLang ? window.NeoLang.t.bind(window.NeoLang) : (k, f) => f;
  const isEn = window.NeoLang && window.NeoLang.getLang() === 'en';
  const count = eventsData ? eventsData.length : 0;
  let html = '';
  if (count === 0) {
    const emptyMsg = isEn
      ? '📅 No upcoming events.<br>Add events via desktop notebook or AI chat.'
      : '📅 登録された予定はありません。<br>PC側の手帳やAIチャットで追加できます。';
    const btnLabel = isEn ? '⚙ Google Calendar Sync' : '⚙ 設定から連携する';
    const toastMsg = isEn ? '📱 Please set up Google Calendar on PC' : '📱 PC側でGoogleカレンダー連携を設定してください';
    html = `<div class="note-empty">${emptyMsg}</div>` +
      `<div class="approval-sheet-actions" style="margin-top:8px;"><button class="btn-approve" onclick="closeBottomSheet();showToast('${toastMsg}')">${btnLabel}</button></div>`;
  } else {
    html = eventsData.map(e => {
      const dt = String(e.start_time || '').replace('T', ' ').slice(0, 16);
      return `<div class="note-item"><div class="note-title">📅 ${escapeHtml(e.title)}</div><div class="note-desc">🕐 ${escapeHtml(dt)}${e.source_name ? " ／ " + escapeHtml(e.source_name) : ""}</div></div>`;
    }).join('');
  }
  const title = isEn ? `Schedule (${count})` : `予定一覧 (${count}件)`;
  openBottomSheet({ icon: '📅', tag: t('dock.cal', 'カレンダー'), title: title }, html);
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
  window._currentOpenModalName = 'todo';
  const t = window.NeoLang ? window.NeoLang.t.bind(window.NeoLang) : (k, f) => f;
  const isEn = window.NeoLang && window.NeoLang.getLang() === 'en';
  const filtered = todoApplyFilter();
  // 🚀 クイック追加バー (TickTick拡張): 「明日18時に〜 #仕事 !3」構文対応
  const quickBar = `
    <div class="quick-add-bar">
      <input type="text" id="quick-task-input" placeholder="${escapeHtml(t('todo.placeholder', '例: 明日18時に資料 #仕事 !3'))}" enterkeyhint="done">
      <button id="quick-task-btn" onclick="quickAddTask()">＋</button>
    </div>`;
  // 🌳 リスト階層順ソート (parent_id ツリー・Block 1.6-R)
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
  const allListLabel = t('todo.filter_all', '📥 すべて');
  const listRow = todoLists.length > 0
    ? `<div class="todo-filter-bar"><span class="todo-filter-label">${t('todo.filter_list', '📋 リスト')}</span><div class="todo-filter-chips">`
      + [`<button class="todo-chip${todoFilter.listId === null ? ' active' : ''}" onclick="setTodoFilter({listId: null})">${allListLabel}</button>`]
        .concat(orderedLists.map(({ l, depth }) => {
          const indent = depth > 0 ? '　'.repeat(depth) + '└ ' : '';
          return `<button class="todo-chip${todoFilter.listId === l.id ? ' active' : ''}" onclick="setTodoFilter({listId: ${l.id}})">${indent}${escapeHtml(l.emoji || '📋')} ${escapeHtml(l.name)}</button>`;
        })).join('')
      + `</div></div>`
    : '';
  // 🗓 期間フィルタ行 (セグメントコントロール化) ＋ 🎯 4象限ビュー切替
  const rangeRow = `<div class="todo-filter-bar"><span class="todo-filter-label">${t('todo.filter_range', '🗓 期間')}</span><div class="todo-filter-chips">`
    + [['all', t('todo.range_all', '🗂 すべて')], ['today', t('todo.range_today', '⏰ 今日')], ['week', t('todo.range_week', '📅 今週')]]
      .map(([k, label]) => `<button class="todo-chip${todoFilter.range === k ? ' active' : ''}" onclick="setTodoFilter({range: '${k}'})">${label}</button>`).join('')
    + `<button class="todo-chip todo-view-toggle${todoViewMode === 'quad' ? ' active' : ''}" onclick="setTodoView('${todoViewMode === 'quad' ? 'list' : 'quad'}')">${todoViewMode === 'quad' ? t('todo.quad_back', '📋 一覧に戻る') : t('todo.quad_toggle', '🎯 4象限')}</button>`
    + `</div></div>`;
  // 🏷 タグ行
  const tagRow = todoFilter.tag
    ? `<div class="todo-filter-bar"><span class="todo-filter-label">🏷 ${isEn ? 'Tag' : 'タグ'}</span><div class="todo-filter-chips"><button class="todo-chip active" onclick="setTodoFilter({tag: null})">#${escapeHtml(todoFilter.tag)} ✕</button></div></div>`
    : '';
  let html = quickBar + listRow + rangeRow + tagRow;
  // 🎯 4象限ビュー (Plan D)
  if (todoViewMode === 'quad') {
    todoTagCandidates = [];
    html += renderQuadrant(filtered);
    const quadTitle = isEn ? `Eisenhower Matrix (${filtered.length})` : `TODO 4象限 (${filtered.length}件)`;
    openBottomSheet({ icon: '📝', tag: t('dock.tasks', 'タスク'), title: quadTitle }, html);
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
    const emptyMsg = isEn
      ? '📝 No tasks match the criteria.<br>Change filters or add a task using the bar above ✨'
      : '📝 該当するTODOはありません。<br>フィルタを変更するか、上のバーから追加してください✨';
    html += `<div class="note-empty">${emptyMsg}</div>`;
  } else {
    const prioIcon = { 3: '🔥', 2: '⭐', 1: '🌱' };
    const pad = n => String(n).padStart(2, '0');
    html += filtered.map(tItem => {
      const icon = prioIcon[tItem.priority] || '📌';
      const recBadge = tItem.recurrence ? `<span class="todo-tag">🔄 ${isEn ? 'Recurring' : '繰り返し'}</span>` : '';
      const tags = String(tItem.tags || '').split(',').map(s => s.trim()).filter(Boolean);
      const tagHtml = tags.map(tag => {
        let idx = tagCandidates.indexOf(tag);
        if (idx === -1) { tagCandidates.push(tag); idx = tagCandidates.length - 1; }
        return `<span class="todo-tag" onclick="event.stopPropagation();toggleTodoTagIndex(${idx})">#${escapeHtml(tag)}</span>`;
      }).join('');
      let dueHtml = '';
      if (tItem.due_date) {
        const d = new Date(tItem.due_date);
        dueHtml = ` 📅 ${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
      }
      const tapToComplete = isEn ? '👆 Tap to complete' : '👆 タップで完了にする';
      return `<div class="note-item" onclick="completeTask(${tItem.id}, this)"><div class="note-title">${icon} ${escapeHtml(tItem.title)}${recBadge}${tagHtml}</div><div class="note-desc">${dueHtml || tapToComplete} <span class="task-edit-link" onclick="event.stopPropagation();openTaskEditSheet(${tItem.id})">✏️</span></div></div>`;
    }).join('');
  }
  todoTagCandidates = tagCandidates;
  const sheetTitle = isEn ? `Tasks (${filtered.length})` : `TODOリスト (${filtered.length}件)`;
  openBottomSheet({ icon: '📝', tag: t('dock.tasks', 'タスク'), title: sheetTitle }, html);
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
  window._currentOpenModalName = 'notes';
  const t = window.NeoLang ? window.NeoLang.t.bind(window.NeoLang) : (k, f) => f;
  const isEn = window.NeoLang && window.NeoLang.getLang() === 'en';
  const count = habitsData ? habitsData.length : 0;
  let html = '';
  if (count === 0) {
    const emptyMsg = isEn
      ? '🌱 No habits tracked yet.<br>Add habits via desktop notebook.'
      : '🌱 登録された習慣はありません。<br>PC側の手帳で習慣を追加できます。';
    html = `<div class="note-empty">${emptyMsg}</div>`;
  } else {
    html = habitsData.map(h => {
      const done = !!h.completed_today;
      const streakBadge = h.streak > 0 ? `<span class="note-badge">🔥 ${h.streak}${isEn ? 'd streak' : '日連続'}</span>` : '';
      const descText = done
        ? (isEn ? 'Completed today! Great job! ✨' : '今日は達成済み！素晴らしい！✨')
        : (isEn ? '👆 Tap to mark completed today' : '👆 タップで今日の達成を記録');
      return `<div class="note-item ${done ? 'done' : ''}" onclick="toggleHabit(${h.id}, this)"><div class="note-title">${h.emoji || '🌱'} ${escapeHtml(h.title)}${streakBadge}</div><div class="note-desc">${descText}</div></div>`;
    }).join('');
  }
  const title = isEn ? 'Habit Tracker' : '習慣トラッカー';
  openBottomSheet({ icon: '🌱', tag: t('dock.daily', '日報'), title: title }, html);
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
      const charList = (typeof CHARACTERS !== 'undefined') ? CHARACTERS : (window.CHARACTERS || []);
      const foundChar = charList.find ? charList.find(c => c.id === charId) : null;
      const charDisplayName = foundChar ? foundChar.name : charId;
      showToast(`🎭 キャラクターを【${charDisplayName}】に変更しました`);
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
  let theme = null;
  if (typeof setEnvTheme === 'function') {
    theme = setEnvTheme(themeId);
  } else if (typeof ENV_THEMES !== 'undefined') {
    const idx = ENV_THEMES.findIndex(t => t.id === themeId);
    if (idx !== -1) {
      currentEnvIndex = idx;
      theme = ENV_THEMES[currentEnvIndex];
    }
  }
  if (theme) {
    if (navigator.vibrate) {
      try { navigator.vibrate(25); } catch (e) {}
    }
    showToast(`🏞️ 【${theme.label}】テーマに変更しました`);
    openSettingsModal();
  }
}

let currentSavedLocation = '';

/** ⚙️ 設定モーダル（キャラ・テーマ・地域・演出モード・全画面・常時ON・PCペット呼び出し・言語切り替え） */
function openSettingsModal() {
  window._currentOpenModalName = 'settings';
  const t = window.NeoLang ? window.NeoLang.t.bind(window.NeoLang) : (k, f) => f;
  const isEn = window.NeoLang && window.NeoLang.getLang() === 'en';
  const locLabel = currentSavedLocation ? currentSavedLocation : (isEn ? 'Auto IP Detection' : 'IP自動検出');

  // 言語選択チップ
  const langChipsHtml = `
    <button style="
      background: ${!isEn ? 'var(--accent-amber)' : 'rgba(255,255,255,0.08)'};
      color: ${!isEn ? '#1E140E' : 'var(--text-main)'};
      border: 1px solid var(--accent-amber);
      border-radius: 14px;
      padding: 5px 11px;
      font-size: 11px;
      font-weight: bold;
      cursor: pointer;
      margin: 3px;
    " onclick="if(window.NeoLang){window.NeoLang.setLang('ja', true);openSettingsModal();}">🇯🇵 日本語</button>
    <button style="
      background: ${isEn ? 'var(--accent-amber)' : 'rgba(255,255,255,0.08)'};
      color: ${isEn ? '#1E140E' : 'var(--text-main)'};
      border: 1px solid var(--accent-amber);
      border-radius: 14px;
      padding: 5px 11px;
      font-size: 11px;
      font-weight: bold;
      cursor: pointer;
      margin: 3px;
    " onclick="if(window.NeoLang){window.NeoLang.setLang('en', true);openSettingsModal();}">🇺🇸 English</button>
  `;

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
  const themeChipsHtml = ENV_THEMES.map(tTheme => `
    <button style="
      background: ${ENV_THEMES[currentEnvIndex].id === tTheme.id ? 'var(--accent-amber)' : 'rgba(255,255,255,0.08)'};
      color: ${ENV_THEMES[currentEnvIndex].id === tTheme.id ? '#1E140E' : 'var(--text-main)'};
      border: 1px solid var(--accent-amber);
      border-radius: 14px;
      padding: 5px 11px;
      font-size: 11px;
      font-weight: bold;
      cursor: pointer;
      margin: 3px;
    " onclick="selectEnvTheme('${tTheme.id}')">${tTheme.label}</button>
  `).join('');

  const sectionChar = isEn ? '🎭 Character Select:' : '🎭 キャラクター選択:';
  const sectionTheme = isEn ? '🏞️ Background Theme:' : '🏞️ 背景テーマ選択:';
  const sectionLang = isEn ? '🌐 Display Language:' : '🌐 表示言語 / Language:';
  const locTitle = isEn ? '📍 Weather Location' : '📍 お住まいの地域（天気）';
  const locDesc = isEn ? `Current: <b>${escapeHtml(locLabel)}</b> → Tap to change` : `現在: <b>${escapeHtml(locLabel)}</b> → タップで変更`;
  const easterTitle = isEn ? '✨ Special Effects Mode' : '✨ イースターエッグ演出モード';
  const easterDesc = isEn ? `Current: <b>${effectModeLabel()}</b> → Tap to toggle` : `現在: <b>${effectModeLabel()}</b> → タップで切替（低スペ端末は自動で軽量）`;
  const nosleepTitle = isEn ? '💡 Keep Screen Always ON' : '💡 常時画面ON（自動消灯防止）';
  const nosleepDesc = isEn ? 'Stays lit as a smart desk display' : '卓上スマートディスプレイとして常時点灯します';
  const fullTitle = isEn ? '⛶ Fullscreen' : '⛶ 全画面表示';
  const fullDesc = isEn ? 'Hide browser UI for full screen' : 'ブラウザUIを隠して全画面表示にします';
  const pcPetTitle = isEn ? '🖥️ Summon PC Mascot' : '🖥️ PCのペットを呼び出す';
  const pcPetDesc = isEn ? 'Re-display the desktop mascot' : 'デスクトップのペットを再表示します';
  const closeTitle = isEn ? '✖ Close' : '✖ 閉じる';

  const html = `
    <div style="margin-bottom:12px;">
      <div style="font-size:11px; font-weight:bold; color:var(--accent-amber); margin-bottom:5px;">${sectionLang}</div>
      <div style="display:flex; flex-wrap:wrap;">
        ${langChipsHtml}
      </div>
    </div>

    <div style="margin-bottom:12px;">
      <div style="font-size:11px; font-weight:bold; color:var(--accent-amber); margin-bottom:5px;">${sectionChar}</div>
      <div style="display:flex; flex-wrap:wrap;">
        ${charChipsHtml}
      </div>
    </div>

    <div style="margin-bottom:12px;">
      <div style="font-size:11px; font-weight:bold; color:var(--accent-amber); margin-bottom:5px;">${sectionTheme}</div>
      <div style="display:flex; flex-wrap:wrap;">
        ${themeChipsHtml}
      </div>
    </div>

    <div class="note-item" onclick="openLocationSettingsModal();"><div class="note-title">${locTitle}</div><div class="note-desc">${locDesc}</div></div>
    <div class="note-item" onclick="cycleEffectMode(); openSettingsModal();"><div class="note-title">${easterTitle}</div><div class="note-desc">${easterDesc}</div></div>
    <div class="note-item" onclick="toggleNoSleep(); closeBottomSheet();"><div class="note-title">${nosleepTitle}</div><div class="note-desc">${nosleepDesc}</div></div>
    <div class="note-item" onclick="toggleFullscreen(); closeBottomSheet();"><div class="note-title">${fullTitle}</div><div class="note-desc">${fullDesc}</div></div>
    <div class="note-item" onclick="showPcPet()"><div class="note-title">${pcPetTitle}</div><div class="note-desc">${pcPetDesc}</div></div>
    <div class="note-item" onclick="closeBottomSheet()"><div class="note-title">${closeTitle}</div></div>`;
  const sheetTitle = isEn ? 'Settings' : '設定';
  openBottomSheet({ icon: '⚙️', tag: t('dock.settings', '設定'), title: sheetTitle }, html);
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
 * HTTP環境 (http://<PC-IP>:<PORT>) では navigator.wakeLock が
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
// 12. 自律歩行コントローラー (pet_motion.js に委譲)
// =============================================================================
// ※ WANDER, _setPetSprite, petWanderTick
//    は先行読み込みされる pet_motion.js で定義および window に公開されています。


// =============================================================================
// 13. 朝会/終礼ブリーフィング (Phase L3) & Web Speech API (TTS)
// ※ updateBriefingBannerText は先行読み込みされる pet_ui.js で定義および window に公開されています。


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

// 🌐 言語切り替え時のモーダル自動再描画
// 注: 承認/質問シート（pet_ui.js 管轄・window.currentApprovalRequest 使用）の表示中は
//     上書き破壊を避けるため何もしない（2026-09-24 V2 査読 P2-4 の最小修正）
window.addEventListener('neolang:changed', function () {
  if (window.currentApprovalRequest) return;
  const sheet = document.getElementById('bottom-sheet');
  if (sheet && sheet.classList.contains('open')) {
    if (window._currentOpenModalName === 'todo') {
      renderTodoModal();
    } else if (window._currentOpenModalName === 'events') {
      openEventsModal();
    } else if (window._currentOpenModalName === 'notes') {
      openNotesModal();
    } else if (window._currentOpenModalName === 'settings') {
      openSettingsModal();
    }
  }
});

// =============================================================================
// 14. 未回答質問シートの自動オープン (案α・ID 63 / 2026-09-26)
// =============================================================================
// OS 通知タップ等で PWA が前面復帰した瞬間に、未回答の質問 (type: 'question')
// が残っていればシートを自動で開き「通知 → タップ → 選択肢が見える」を1段に削減する。
// ガード: ①質問型のみ (承認要請はバナーのボタンで回答するため割り込ませない)
//        ②選択肢付きのみ (choices=[] の通知型質問はスマホから回答不能なため除外)
//        ③同一 request_id で1回のみ ④シートが未オープンのときのみ。
// ※ _autoOpenedQuestionId の宣言はファイル先頭 (TDZ 対策・v1.1.14)。
function maybeAutoOpenQuestionSheet() {
  try {
    const req = window.currentApprovalRequest;
    if (!req || req.type !== 'question' || !req.request_id) return;
    // 📵 選択肢なし質問（通知型）はスマホから回答できないため自動オープンしない:
    //    Antigravity tool_guard_hook / OpenCode plugin の「承認待ち heads-up」は
    //    choices=[] で届く。これを開くと「自由回答はPC側で」の回答不能カードが
    //    強制展開される割り込みになるため、選択肢付き質問のみ自動オープンする
    //    （バナー表示は従来どおり・2026-09-26 ボス実感を契機としたガード）。
    if (!(req.choices && req.choices.length > 0)) return;
    if (_autoOpenedQuestionId === req.request_id) return;
    const sheet = document.getElementById('bottom-sheet');
    if (sheet && sheet.classList.contains('open')) return;
    if (typeof window.openQuestionSheet !== 'function') return;
    _autoOpenedQuestionId = req.request_id;
    window.openQuestionSheet();
    // 📡 観測可能性: 自動オープンが発火したことを可視化 (動作検証・将来のトラブルシュート用)
    if (typeof showToast === 'function') showToast('📱 質問シートを自動で開きました', 2500);
  } catch (e) {
    console.warn('auto open question sheet failed:', e);
  }
}

// PWA 前面復帰 (通知タップ・アプリ切り替え) 時に発火
document.addEventListener('visibilitychange', function () {
  if (document.visibilityState === 'visible') {
    maybeAutoOpenQuestionSheet();
  }
});
