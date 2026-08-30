/**
 * ネオ秘書くん - イースターエッグ演出エンジン (web_pet/easter_eggs.js)
 * 
 * 「お前を消す方法」イベントのステージ別リッチ演出を管理。
 * - Web Audio API による完全オフライン 8bit シンセ音
 * - CRT走査線・RGB色収差グリッチ・暗転・ピクセル粒子消滅・復活演出
 * - 低スペック端末配慮: CSS Transform / Canvas アニメーション最適化
 */

(function(window) {
  'use strict';

  // 内部状態
  let audioCtx = null;
  let isEffectRunning = false;
  let lastProcessedEventId = '';

  // ==========================================================================
  // 演出モード管理 (11.3: 低スペ端末向け軽量化 + スキップ設定)
  // 'full' = 標準演出 / 'light' = 軽量演出(重いエフェクト省略) / 'off' = 演出スキップ
  // ==========================================================================
  const EFFECT_MODE_KEY = 'hisho_effect_mode';
  const EFFECT_MODES = ['full', 'light', 'off'];
  const EFFECT_MODE_LABELS = { full: '標準', light: '軽量', off: 'OFF' };

  /**
   * 端末性能から推奨演出モードを判定する（初回のみ）。
   * @returns {string} 'full' | 'light'
   */
  function detectDefaultMode() {
    try {
      // OSの「動きを減らす」設定を最優先で尊重
      if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        return 'light';
      }
      const mem = navigator.deviceMemory;
      const cores = navigator.hardwareConcurrency;
      if ((mem && mem <= 2) || (cores && cores <= 4)) {
        return 'light';
      }
    } catch (e) {
      console.debug('Effect mode detection error:', e);
    }
    return 'full';
  }

  /**
   * 現在の演出モードを取得する（未設定なら端末性能から自動判定して保存）。
   * @returns {string} 'full' | 'light' | 'off'
   */
  function getEffectMode() {
    let mode = null;
    try {
      mode = localStorage.getItem(EFFECT_MODE_KEY);
    } catch (e) {
      console.debug('localStorage unavailable:', e);
    }
    if (!mode || EFFECT_MODES.indexOf(mode) === -1) {
      mode = detectDefaultMode();
      saveEffectMode(mode);
    }
    return mode;
  }

  /**
   * 演出モードを保存する。
   * @param {string} mode - 'full' | 'light' | 'off'
   */
  function saveEffectMode(mode) {
    if (EFFECT_MODES.indexOf(mode) === -1) return;
    try {
      localStorage.setItem(EFFECT_MODE_KEY, mode);
    } catch (e) {
      console.debug('localStorage unavailable:', e);
    }
  }

  /**
   * 演出モードを設定する（設定UIから呼び出し）。
   * @param {string} mode - 'full' | 'light' | 'off'
   * @returns {string} 設定後のモード
   */
  function setEffectMode(mode) {
    saveEffectMode(mode);
    const label = EFFECT_MODE_LABELS[getEffectMode()] || mode;
    showEasterEggToast(`✨ 演出モード: ${label}`, '#00E676', 2000);
    return getEffectMode();
  }

  /**
   * 演出モードを 標準→軽量→OFF→標準 の順で循環切替する（設定UI用）。
   * @returns {string} 切替後のモード
   */
  function cycleEffectMode() {
    const idx = EFFECT_MODES.indexOf(getEffectMode());
    const next = EFFECT_MODES[(idx + 1) % EFFECT_MODES.length];
    return setEffectMode(next);
  }

  /**
   * ミニゲーム解放バッジ（👾 秘密の部屋）を点灯させる。
   * 演出モードに関係なく、解放ロジック自体は必ず実行される。
   */
  function unlockSecretGameBadge() {
    const badge = document.getElementById('secret-game-badge');
    if (badge) {
      badge.style.display = 'inline-flex';
      badge.classList.add('badge-unlocked-pulse');
    }
  }

  /**
   * Web Audio API コンテキストの取得＆アンロック
   */
  function getAudioContext() {
    if (!audioCtx) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (AudioContextClass) {
        audioCtx = new AudioContextClass();
      }
    }
    if (audioCtx && audioCtx.state === 'suspended') {
      audioCtx.resume().catch(() => {});
    }
    return audioCtx;
  }

  // ユーザー操作時にアンロック
  ['click', 'touchstart', 'keydown'].forEach(evt => {
    window.addEventListener(evt, () => {
      getAudioContext();
    }, { once: false, passive: true });
  });

  /**
   * 8bit レトロシンセ音の生成・再生
   * @param {string} type - 'blip' | 'reject' | 'glitch' | 'revive'
   */
  function playSynthSound(type) {
    const ctx = getAudioContext();
    if (!ctx) return;

    const now = ctx.currentTime;

    try {
      if (type === 'blip') {
        // Stage 1: かわいい疑問ピピ音
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(440, now);
        osc.frequency.exponentialRampToValueAtTime(880, now + 0.12);
        gain.gain.setValueAtTime(0.2, now);
        gain.gain.linearRampToValueAtTime(0, now + 0.12);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.12);

      } else if (type === 'reject') {
        // Stage 2: 低めの電子ブザー音
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(220, now);
        osc.frequency.setValueAtTime(160, now + 0.1);
        gain.gain.setValueAtTime(0.25, now);
        gain.gain.linearRampToValueAtTime(0, now + 0.25);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.25);

      } else if (type === 'glitch') {
        // Stage 3: 周波数変調 ＆ ノイズグリッチ音
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'square';
        osc.frequency.setValueAtTime(800, now);
        osc.frequency.setValueAtTime(120, now + 0.05);
        osc.frequency.setValueAtTime(950, now + 0.1);
        osc.frequency.setValueAtTime(200, now + 0.2);
        gain.gain.setValueAtTime(0.3, now);
        gain.gain.linearRampToValueAtTime(0.05, now + 0.3);
        gain.gain.linearRampToValueAtTime(0, now + 0.45);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.45);

      } else if (type === 'revive') {
        // Stage 4: 復活のレトロアルペジオファンファーレ
        const notes = [261.63, 329.63, 392.00, 523.25, 659.25, 783.99, 1046.50]; // C Major
        notes.forEach((freq, idx) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          const t = now + idx * 0.08;
          osc.type = 'sine';
          osc.frequency.setValueAtTime(freq, t);
          gain.gain.setValueAtTime(0.22, t);
          gain.gain.exponentialRampToValueAtTime(0.001, t + 0.35);
          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.start(t);
          osc.stop(t + 0.35);
        });
      }
    } catch (e) {
      console.debug('Synth sound error:', e);
    }
  }

  /**
   * HUDトースト通知の表示
   */
  function showEasterEggToast(text, color = '#FFB800', duration = 3000) {
    let toast = document.getElementById('ee-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'ee-toast';
      toast.style.cssText = `
        position: fixed;
        top: 48px;
        left: 50%;
        transform: translateX(-50%) translateY(-20px);
        background: rgba(30, 20, 14, 0.95);
        border: 2px solid ${color};
        color: #F5F5DC;
        padding: 8px 16px;
        border-radius: 8px;
        font-family: 'DotGothic16', monospace;
        font-size: 13px;
        font-weight: bold;
        z-index: 99999;
        box-shadow: 0 4px 20px rgba(0,0,0,0.8), 0 0 12px ${color};
        opacity: 0;
        transition: transform 0.3s cubic-bezier(0.18, 0.89, 0.32, 1.28), opacity 0.3s ease;
        pointer-events: none;
        text-align: center;
        white-space: nowrap;
      `;
      document.body.appendChild(toast);
    }

    toast.style.borderColor = color;
    toast.style.boxShadow = `0 4px 20px rgba(0,0,0,0.8), 0 0 12px ${color}`;
    toast.innerHTML = text;
    toast.style.opacity = '1';
    toast.style.transform = 'translateX(-50%) translateY(0)';

    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(-50%) translateY(-20px)';
    }, duration);
  }

  /**
   * ピクセル粒子消滅アニメーション (Canvas)
   */
  function triggerPixelScatter(callback) {
    const petImg = document.getElementById('pet-img');
    const container = document.querySelector('.pet-display-area') || document.body;
    if (!petImg) {
      if (callback) callback();
      return;
    }

    const rect = petImg.getBoundingClientRect();
    const c = document.createElement('canvas');
    c.width = window.innerWidth;
    c.height = window.innerHeight;
    c.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:99998;';
    document.body.appendChild(c);
    const ctx = c.getContext('2d');

    // 粒子の生成
    const particles = [];
    const pCount = 60;
    const colors = ['#8A9EA7', '#5B8A9B', '#FFFFFF', '#FFB800', '#FF1744', '#00E5FF'];

    for (let i = 0; i < pCount; i++) {
      particles.push({
        x: rect.left + rect.width * (0.2 + Math.random() * 0.6),
        y: rect.top + rect.height * (0.2 + Math.random() * 0.6),
        vx: (Math.random() - 0.5) * 12,
        vy: (Math.random() - 0.5) * 12 - 3,
        size: Math.floor(Math.random() * 6) + 3,
        color: colors[Math.floor(Math.random() * colors.length)],
        alpha: 1.0,
        gravity: 0.15
      });
    }

    // ペット本体を一瞬透明に
    petImg.style.opacity = '0';
    let frame = 0;

    function renderScatter() {
      ctx.clearRect(0, 0, c.width, c.height);
      let alive = false;
      particles.forEach(p => {
        p.x += p.vx;
        p.y += p.vy;
        p.vy += p.gravity;
        p.alpha -= 0.025;
        if (p.alpha > 0) {
          alive = true;
          ctx.fillStyle = p.color;
          ctx.globalAlpha = Math.max(0, p.alpha);
          ctx.fillRect(p.x, p.y, p.size, p.size);
        }
      });

      frame++;
      if (alive && frame < 80) {
        requestAnimationFrame(renderScatter);
      } else {
        c.remove();
        if (callback) callback();
      }
    }

    requestAnimationFrame(renderScatter);
  }

  /**
   * ステージ別イースターエッグ演出のトリガー
   * @param {number} stage - 1 (とぼけ) | 2 (却下) | 3 (グリッチ) | 4 (消滅・解放)
   * @param {Object} eventData - { message, attempt_count, daily_count }
   */
  function triggerEffect(stage, eventData = {}) {
    if (isEffectRunning) return;
    isEffectRunning = true;

    // 演出OFF: 視覚・音響演出を完全スキップ。
    // ただし解放バッジ点灯などの「実ロジック」は必ず維持する（機能が壊れないことを優先）。
    if (getEffectMode() === 'off') {
      const offModeMsg = document.getElementById('pet-message');
      if (offModeMsg && eventData.message) {
        offModeMsg.textContent = eventData.message;
      }
      if (stage >= 4) {
        unlockSecretGameBadge();
        showEasterEggToast('👾 シークレットゲーム解放！（演出OFF）', '#00E676', 3000);
      }
      isEffectRunning = false;
      return;
    }

    const lightMode = getEffectMode() === 'light';
    const casing = document.querySelector('.device-casing') || document.body;
    const petImg = document.getElementById('pet-img');
    const msgEl = document.getElementById('pet-message');

    // 1. Stage 1: 微振動 ＆ とぼけ（軽量モードでは振動エフェクトを省略）
    if (stage === 1) {
      playSynthSound('blip');
      showEasterEggToast('❓ 消去コマンド検知…？', '#FFB800', 2500);
      if (!lightMode) {
        casing.classList.add('fx-shake-light');
        setTimeout(() => {
          casing.classList.remove('fx-shake-light');
          isEffectRunning = false;
        }, 600);
      } else {
        isEffectRunning = false;
      }

    // 2. Stage 2: 却下 ＆ 赤スキャンライン（軽量モードではパルスエフェクトを省略）
    } else if (stage === 2) {
      playSynthSound('reject');
      showEasterEggToast('⛔ 削除要求を却下しました', '#FF1744', 3000);
      if (msgEl && eventData.message) {
        msgEl.textContent = eventData.message;
      }
      if (!lightMode) {
        casing.classList.add('fx-reject-pulse');
        setTimeout(() => {
          casing.classList.remove('fx-reject-pulse');
          isEffectRunning = false;
        }, 1200);
      } else {
        isEffectRunning = false;
      }

    // 3. Stage 3: CRT走査線 ＆ RGB色収差グリッチ（軽量モードではグリッチエフェクトを省略）
    } else if (stage === 3) {
      playSynthSound('glitch');
      showEasterEggToast('⚡ 回線ノイズ発生…！', '#AB47BC', 3000);
      if (msgEl && eventData.message) {
        msgEl.textContent = eventData.message;
      }
      if (!lightMode) {
        casing.classList.add('fx-glitch-active');
        setTimeout(() => {
          casing.classList.remove('fx-glitch-active');
          isEffectRunning = false;
        }, 2000);
      } else {
        isEffectRunning = false;
      }

    // 4. Stage 4: 暗転 ➔ ピクセル粒子消滅 ➔ 復活ファンファーレ ＆ 解放
    } else if (stage === 4 || stage >= 5) {
      // 軽量モード: 暗転・全画面Canvas粒子を省略し、短いフェードで復活を表現
      if (lightMode) {
        playSynthSound('revive');
        showEasterEggToast('✨ 案内精霊は復活しました！（軽量演出）', '#00E676', 2500);
        if (petImg) {
          petImg.style.transition = 'opacity 0.4s ease';
          petImg.style.opacity = '0.2';
          setTimeout(() => {
            petImg.style.opacity = '1';
            petImg.style.transition = '';
          }, 400);
        }
        unlockSecretGameBadge();
        isEffectRunning = false;
        return;
      }

      playSynthSound('glitch');
      casing.classList.add('fx-blackout');
      showEasterEggToast('💀 消滅プロセス開始……', '#FF1744', 2000);

      // 粒子消滅
      setTimeout(() => {
        triggerPixelScatter(() => {
          // 2秒の静寂
          setTimeout(() => {
            // 復活！
            playSynthSound('revive');
            casing.classList.remove('fx-blackout');
            casing.classList.add('fx-revive-burst');

            if (petImg) {
              petImg.style.opacity = '1';
              petImg.classList.add('fx-pet-revive');
            }

            showEasterEggToast('✨ 案内精霊は完全復活しました！', '#00E676', 4000);

            // ミニゲーム解放バッジの点灯
            unlockSecretGameBadge();

            setTimeout(() => {
              casing.classList.remove('fx-revive-burst');
              if (petImg) petImg.classList.remove('fx-pet-revive');
              isEffectRunning = false;
            }, 3000);
          }, 1800);
        });
      }, 500);

    } else {
      isEffectRunning = false;
    }
  }

  /**
   * /api/status からの同期ポーリング監視
   * @param {Object} statusData - /api/status のレスポンスJSON
   */
  function syncFromStatus(statusData) {
    if (!statusData || !statusData.easter_egg) return;
    const ee = statusData.easter_egg;

    // ミニゲーム解放状態の同期
    if (ee.secret_game_unlocked) {
      const badge = document.getElementById('secret-game-badge');
      if (badge && badge.style.display === 'none') {
        badge.style.display = 'inline-flex';
      }
    }

    // 新規アクティブイベントの検知
    if (ee.active_event && ee.active_event.id) {
      if (ee.active_event.id !== lastProcessedEventId) {
        lastProcessedEventId = ee.active_event.id;
        triggerEffect(ee.active_event.stage, ee.active_event);
      }
    }
  }

  /**
   * PWAから直接テスト発火（開発・デモ用）
   */
  async function triggerFromPwa(phrase = 'お前を消す方法') {
    try {
      const res = await window.authFetch('/api/action', {
        method: 'POST',
        body: JSON.stringify({
          action: 'easter_egg_trigger',
          phrase: phrase
        })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'success') {
          triggerEffect(data.stage, {
            message: data.reply,
            daily_count: data.daily_count,
            attempt_count: data.attempt_count
          });
        }
      }
    } catch (e) {
      console.debug('Easter egg PWA trigger error:', e);
      // ローカルフォールバック実行
      triggerEffect(3, { message: '……回線ノイズ、再構築完了。' });
    }
  }

  // グローバル公開
  window.EasterEggEngine = {
    trigger: triggerEffect,
    syncFromStatus: syncFromStatus,
    triggerFromPwa: triggerFromPwa,
    playSound: playSynthSound,
    getEffectMode: getEffectMode,
    setEffectMode: setEffectMode,
    cycleEffectMode: cycleEffectMode
  };

})(window);
