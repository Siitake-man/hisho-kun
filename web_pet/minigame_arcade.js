/**
 * ネオ秘書くん レトロミニゲームセンター マネージャー (minigame_arcade.js)
 *
 * カートリッジ型オムニバスフレームワーク:
 * - 各ミニゲームは window.MinigameArcade.register(cartridge) で自己登録する
 * - show() 時にランダム (ガチャ) で1つ選んで即起動する
 * - ◀[L] / ▶[R] ボタン (または ←/→ キー) でカートリッジ感覚に切替できる
 * - ハイスコアは GET /api/minigame/high で取得し、
 *   POST /api/action (record_minigame_score) で game_id ごとに独立永続化される
 *
 * 後方互換: 既存 window.PixelDefense.show()/hide() の呼び出し経路
 * (pet.js / easter_eggs.js / バッジ onclick) はarcadeへのエイリアスに迂回されるため、
 * 呼び出し側は一切変更不要。
 */
(function () {
  'use strict';

  // ==========================================================================
  // モジュール状態
  // ==========================================================================
  const registry = []; // 登録済みカートリッジ
  let overlay = null;
  let canvas = null;
  let ctx = null;
  let titleEl = null;
  let scoreEl = null;
  let highEl = null;
  let initialized = false;
  let active = false; // arcadeがオーバーレイを所有中か
  let current = null; // 稼働中カートリッジ
  let currentIndex = -1;
  let rafId = null;
  let lastTime = 0;
  let audioCtx = null;

  // ==========================================================================
  // サウンド (Web Audio 矩形波合成・完全オフライン)
  // ==========================================================================

  /**
   * AudioContextを取得する（未初期化なら生成）。
   * @returns {AudioContext|null} オーディオコンテキスト
   */
  function getAudioCtx() {
    try {
      if (!audioCtx) {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return null;
        audioCtx = new AC();
      }
      if (audioCtx.state === 'suspended') {
        audioCtx.resume();
      }
      return audioCtx;
    } catch (e) {
      console.debug('[MinigameArcade] AudioContext error:', e);
      return null;
    }
  }

  /**
   * 矩形波ビープ音を再生する。
   * @param {number} freq - 周波数 (Hz)
   * @param {number} duration - 長さ (秒)
   * @param {number} [volume=0.08] - 音量 (0〜1)
   * @param {string} [type='square'] - 波形
   */
  function beep(freq, duration, volume = 0.08, type = 'square') {
    const ac = getAudioCtx();
    if (!ac) return;
    try {
      const osc = ac.createOscillator();
      const gain = ac.createGain();
      osc.type = type;
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(volume, ac.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, ac.currentTime + duration);
      osc.connect(gain).connect(ac.destination);
      osc.start();
      osc.stop(ac.currentTime + duration);
    } catch (e) {
      console.debug('[MinigameArcade] beep error:', e);
    }
  }

  // ==========================================================================
  // カートリッジレジストリ
  // ==========================================================================

  /**
   * ミニゲームカートリッジを登録する (二重登録は無視)。
   * @param {Object} game - {id, title, usesArrowKeys?, start, stop, handleInput?, update?, draw?}
   */
  function register(game) {
    if (!game || typeof game.id !== 'string' || !game.id || typeof game.start !== 'function') {
      console.debug('[MinigameArcade] 不正なカートリッジ登録を無視しました');
      return;
    }
    if (registry.some((g) => g.id === game.id)) {
      return;
    }
    registry.push(game);
  }

  // ==========================================================================
  // HUD / サーバー連携
  // ==========================================================================

  function setHudScore(n) {
    if (scoreEl) scoreEl.textContent = String(n);
  }

  function setHudHigh(n) {
    if (highEl) highEl.textContent = String(n);
  }

  /**
   * サーバーからハイスコアを取得する。
   * @param {string} gameId - ゲームID
   * @returns {Promise<number>} ハイスコア (失敗時 0)
   */
  function fetchHigh(gameId) {
    const doFetch = window.authFetch || window.fetch.bind(window);
    return doFetch('/api/minigame/high?game_id=' + encodeURIComponent(gameId))
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error('HTTP ' + res.status))))
      .then((data) => (data && typeof data.high_score === 'number' ? data.high_score : 0))
      .catch((e) => {
        console.debug('[MinigameArcade] ハイスコア取得失敗:', e);
        return 0;
      });
  }

  /**
   * スコアを POST /api/action 経由で SQLite へ記録する。
   * @param {string} gameId - ゲームID
   * @param {number} score - 達成スコア
   * @returns {Promise<number|null>} 新ハイスコア (失敗時 null)
   */
  function submitScore(gameId, score) {
    const doFetch = window.authFetch || window.fetch.bind(window);
    return doFetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'record_minigame_score', game_id: gameId, score: score })
    })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error('HTTP ' + res.status))))
      .then((data) => (data && typeof data.high_score === 'number' ? data.high_score : null))
      .catch((e) => {
        console.debug('[MinigameArcade] スコア送信失敗:', e);
        return null;
      });
  }

  /**
   * カートリッジへ渡す共通APIを構築する。
   * @param {Object} game - 対象カートリッジ
   * @returns {Object} 共通API
   */
  function buildApi(game) {
    return {
      canvas: canvas,
      ctx: ctx,
      toCanvasX: function (clientX) {
        const rect = canvas.getBoundingClientRect();
        return (clientX - rect.left) * (canvas.width / rect.width);
      },
      toCanvasY: function (clientY) {
        const rect = canvas.getBoundingClientRect();
        return (clientY - rect.top) * (canvas.height / rect.height);
      },
      setScore: setHudScore,
      setHigh: setHudHigh,
      beep: beep,
      fetchHigh: fetchHigh,
      submitScore: submitScore
    };
  }


  // ==========================================================================
  // カートリッジ切替 / メインループ
  // ==========================================================================

  function stopCurrent() {
    if (current && typeof current.stop === 'function') {
      try {
        current.stop();
      } catch (e) {
        console.debug('[MinigameArcade] stop error:', e);
      }
    }
  }

  function startCurrent() {
    if (!current) return;
    if (titleEl) titleEl.textContent = current.title || current.id;
    setHudScore(0);
    setHudHigh(0);
    fetchHigh(current.id).then((h) => setHudHigh(h));
    try {
      current.start(buildApi(current));
    } catch (e) {
      console.debug('[MinigameArcade] start error:', e);
    }
  }

  /**
   * 前後のカートリッジへ切り替える。
   * @param {number} dir - -1 (前) / +1 (次)
   */
  function switchCartridge(dir) {
    if (!active || registry.length === 0) return;
    stopCurrent();
    currentIndex = (currentIndex + dir + registry.length) % registry.length;
    current = registry[currentIndex];
    startCurrent();
  }

  /**
   * arcade所有のメインループ (自己ループ型カートリッジは update/draw 未定義で素通し)。
   * @param {number} time - タイムスタンプ
   */
  function loop(time) {
    if (!active) return;
    const dt = Math.min(0.05, (time - lastTime) / 1000 || 0);
    lastTime = time;
    if (current) {
      if (typeof current.update === 'function') current.update(dt);
      if (typeof current.draw === 'function') {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        current.draw(ctx);
      }
    }
    rafId = requestAnimationFrame(loop);
  }

  // ==========================================================================
  // 入力ハンドラ (arcadeが一元受取しカートリッジへ転送)
  // ==========================================================================

  function onKeyDown(e) {
    if (!active || !current) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      hide();
      return;
    }
    const isArrow = e.key === 'ArrowLeft' || e.key === 'ArrowRight';
    if (isArrow && !current.usesArrowKeys) {
      e.preventDefault();
      switchCartridge(e.key === 'ArrowLeft' ? -1 : 1);
      return;
    }
    if (typeof current.handleInput === 'function') {
      current.handleInput('keydown', e);
    }
  }

  function onKeyUp(e) {
    if (!active || !current) return;
    if (typeof current.handleInput === 'function') {
      current.handleInput('keyup', e);
    }
  }

  function onCanvasInput(e) {
    if (!active || !current) return;
    if (typeof current.handleInput === 'function') {
      current.handleInput(e.type, e);
    }
  }

  function onOverlayClick(e) {
    if (e.target === overlay) {
      hide();
    }
  }

  // ==========================================================================
  // 公開API (show / hide)
  // ==========================================================================

  /**
   * DOM要素を取得し入力をバインドする (初回 show 時の一度のみ)。
   */
  function initDom() {
    if (initialized) return;
    overlay = document.getElementById('minigame-overlay');
    canvas = document.getElementById('pixel-defense-canvas');
    titleEl = document.getElementById('minigame-title');
    scoreEl = document.getElementById('pixel-defense-score');
    highEl = document.getElementById('pixel-defense-high');
    const prevBtn = document.getElementById('minigame-prev');
    const nextBtn = document.getElementById('minigame-next');
    if (!overlay || !canvas) {
      console.debug('[MinigameArcade] モーダル要素が見つかりません');
      return;
    }
    ctx = canvas.getContext('2d');
    if (prevBtn) prevBtn.addEventListener('click', () => switchCartridge(-1));
    if (nextBtn) nextBtn.addEventListener('click', () => switchCartridge(1));
    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('keyup', onKeyUp);
    canvas.addEventListener('touchstart', onCanvasInput, { passive: false });
    canvas.addEventListener('touchmove', onCanvasInput, { passive: false });
    canvas.addEventListener('touchend', onCanvasInput);
    canvas.addEventListener('mousedown', onCanvasInput);
    canvas.addEventListener('mousemove', onCanvasInput);
    canvas.addEventListener('mouseup', onCanvasInput);
    overlay.addEventListener('click', onOverlayClick);
    initialized = true;
  }

  /**
   * ミニゲームセンターを開く。ガチャでランダムに1つ起動する。
   */
  function show() {
    initDom();
    if (!initialized) return;
    overlay.classList.add('active');
    active = true;
    getAudioCtx(); // ユーザー操作起点でAudioContextを解錠

    if (registry.length === 0) {
      // ゲーム未登録の場合は従来の Pixel Defense 単体起動へフォールバック
      const legacy = window.PixelDefense && window.PixelDefense._legacy;
      if (legacy) {
        legacy.show();
      }
      return;
    }

    // ガチャ: ランダム選出
    currentIndex = Math.floor(Math.random() * registry.length);
    current = registry[currentIndex];
    startCurrent();

    lastTime = performance.now();
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
    }
    rafId = requestAnimationFrame(loop);
  }

  /**
   * ミニゲームセンターを閉じて稼働中ゲームを停止する。
   */
  function hide() {
    if (!active) {
      // arcade起動以外 (直接 pixel_defense.show した等) の後方互換
      const legacy = window.PixelDefense && window.PixelDefense._legacy;
      if (legacy) {
        legacy.hide();
      }
      if (overlay) overlay.classList.remove('active');
      return;
    }
    active = false;
    stopCurrent();
    current = null;
    currentIndex = -1;
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
    if (overlay) overlay.classList.remove('active');
  }

  // グローバル公開
  window.MinigameArcade = {
    register: register,
    show: show,
    hide: hide,
    next: () => switchCartridge(1),
    prev: () => switchCartridge(-1),
    isActive: () => active,
    beep: beep
  };

  // 後方互換エイリアス: 既存の window.PixelDefense.show()/hide() 呼び出しを
  // arcade へ迂回させる (元実装は _legacy に保持しフォールバックで使用)。
  if (window.PixelDefense && typeof window.PixelDefense.show === 'function') {
    window.PixelDefense._legacy = window.PixelDefense;
    window.PixelDefense.show = show;
    window.PixelDefense.hide = hide;
  }
})();
