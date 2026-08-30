/**
 * ネオ秘書くん - シークレットミニゲーム「Pixel Defense」 (web_pet/pixel_defense.js)
 *
 * Phase L5: 8bitインベーダー風の防衛シューティング。
 * イースターエッグ（「お前を消す方法」5回発火）で解放される 👾 バッジから起動する。
 *
 * 設計方針:
 * - 疎結合: メインのペットAI・ブリーフィング機能に一切依存しない独立Canvasモーダル。
 * - 完全オフライン: 効果音は Web Audio API の矩形波合成のみで生成（外部アセット不要）。
 * - モバイル対応: タップ/ドラッグでの自機移動・発射に対応（User Gesture Policy 準拠）。
 * - スコア永続化: ゲームオーバー時に POST /api/action (record_minigame_score) で SQLite に記録。
 *
 * 公開API:
 *   window.PixelDefense.show()  - ミニゲームモーダルを開いてゲームを開始
 *   window.PixelDefense.hide()  - モーダルを閉じてゲームを停止
 */
(function () {
  'use strict';

  // ==========================================================================
  // 定数
  // ==========================================================================
  const GAME_ID = 'pixel_defense';
  const CANVAS_WIDTH = 320;
  const CANVAS_HEIGHT = 420;
  const PLAYER_WIDTH = 26;
  const PLAYER_HEIGHT = 14;
  const PLAYER_SPEED = 220; // px/sec
  const BULLET_SPEED = 420; // px/sec
  const BOMB_SPEED = 170; // px/sec
  const INVADER_COLS = 8;
  const INVADER_ROWS = 4;
  const INVADER_CELL_W = 30;
  const INVADER_CELL_H = 26;
  const INVADER_BASE_SPEED = 18; // px/sec（レベルで加速）
  const INVADER_DESCENT = 14; // 壁反射時の降下量 px
  const MAX_LIVES = 3;
  const SCORE_PER_INVADER = 100;
  // ゲームオーバー直後の入力無視時間（誤タップ連打で GAME OVER 画面を飛ばされるのを防ぐ）
  const GAMEOVER_COOLDOWN_MS = 1000;
  const PIXEL_COLORS = {
    player: '#00E676',
    bullet: '#FFFFFF',
    invader: '#FFB800',
    invaderAlt: '#FF5252',
    bomb: '#FF5252',
    particle: '#00E676',
    text: '#00E676',
    dim: '#546E7A'
  };

  // ==========================================================================
  // モジュール状態
  // ==========================================================================
  let canvas = null;
  let ctx = null;
  let overlay = null;
  let scoreEl = null;
  let highEl = null;
  let isInitialized = false;
  let isRunning = false;
  let rafId = null;
  let lastTime = 0;
  let audioCtx = null;

  /** ゲーム内エンティティ */
  const game = {
    state: 'idle', // idle | playing | gameover
    score: 0,
    highScore: 0,
    lives: MAX_LIVES,
    level: 1,
    player: { x: CANVAS_WIDTH / 2, y: CANVAS_HEIGHT - 34, cool: 0 },
    bullets: [], // {x, y}
    bombs: [], // {x, y}
    invaders: [], // {x, y, alive, type}
    invaderDir: 1,
    invaderSpeed: INVADER_BASE_SPEED,
    particles: [], // {x, y, vx, vy, life}
    fireCooldown: 0,
    invaderFireTimer: 0,
    gameoverAt: 0 // ゲームオーバー時刻（リトライクールダウン判定用）
  };

  /** 入力状態 */
  const input = { left: false, right: false, fire: false, pointerX: null };

  // ==========================================================================
  // 初期化
  // ==========================================================================

  /**
   * DOM要素を取得して初期化する（初回show時に一度だけ実行）。
   */
  function initialize() {
    if (isInitialized) return;
    overlay = document.getElementById('minigame-overlay');
    canvas = document.getElementById('pixel-defense-canvas');
    scoreEl = document.getElementById('pixel-defense-score');
    highEl = document.getElementById('pixel-defense-high');
    if (!overlay || !canvas) {
      console.debug('[PixelDefense] モーダル要素が見つかりません');
      return;
    }
    ctx = canvas.getContext('2d');
    bindInput();
    isInitialized = true;
  }

  /**
   * キーボード・タッチ入力のイベントリスナーを登録する。
   */
  function bindInput() {
    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('keyup', onKeyUp);
    canvas.addEventListener('touchstart', onTouch, { passive: false });
    canvas.addEventListener('touchmove', onTouch, { passive: false });
    canvas.addEventListener('touchend', onTouchEnd);
    canvas.addEventListener('mousedown', onCanvasPointer);
    canvas.addEventListener('mousemove', onCanvasPointer);
    canvas.addEventListener('mouseup', onTouchEnd);
    overlay.addEventListener('click', onOverlayClick);
  }

  // ==========================================================================
  // 入力ハンドラ
  // ==========================================================================

  /**
   * キー押下で入力状態を更新する。
   * @param {KeyboardEvent} e - キーボードイベント
   */
  function onKeyDown(e) {
    if (!isRunning) return;
    switch (e.key) {
      case 'ArrowLeft':
      case 'a':
      case 'A':
        input.left = true;
        e.preventDefault();
        break;
      case 'ArrowRight':
      case 'd':
      case 'D':
        input.right = true;
        e.preventDefault();
        break;
      case ' ':
      case 'Enter':
        input.fire = true;
        e.preventDefault();
        break;
      case 'Escape':
        hide();
        break;
      default:
        break;
    }
  }

  /**
   * キー解放で入力状態を解除する。
   * @param {KeyboardEvent} e - キーボードイベント
   */
  function onKeyUp(e) {
    switch (e.key) {
      case 'ArrowLeft':
      case 'a':
      case 'A':
        input.left = false;
        break;
      case 'ArrowRight':
      case 'd':
      case 'D':
        input.right = false;
        break;
      case ' ':
      case 'Enter':
        input.fire = false;
        break;
      default:
        break;
    }
  }

  /**
   * タッチ位置をキャンバス座標へ変換して自機を追従させる。
   * @param {TouchEvent} e - タッチイベント
   */
  function onTouch(e) {
    if (!isRunning) return;
    e.preventDefault();
    const touch = e.touches[0];
    if (touch) {
      applyPointerPosition(touch.clientX);
      input.fire = true;
    }
  }

  /**
   * タッチ解放で発射入力を解除する。
   */
  function onTouchEnd() {
    input.fire = false;
  }

  /**
   * マウス操作で自機を追従させる（PCデバッグ用）。
   * @param {MouseEvent} e - マウスイベント
   */
  function onCanvasPointer(e) {
    if (!isRunning) return;
    if (e.buttons > 0 || e.type === 'mousemove') {
      applyPointerPosition(e.clientX);
    }
  }

  /**
   * クライアントX座標をキャンバス内部座標へ変換して記録する。
   * @param {number} clientX - クライアントX座標
   */
  function applyPointerPosition(clientX) {
    const rect = canvas.getBoundingClientRect();
    const scale = CANVAS_WIDTH / rect.width;
    input.pointerX = (clientX - rect.left) * scale;
  }

  /**
   * オーバーレイ背景クリック（パネル外）でモーダルを閉じる。
   * @param {MouseEvent} e - クリックイベント
   */
  function onOverlayClick(e) {
    if (e.target === overlay) {
      hide();
    }
  }

  // ==========================================================================
  // サウンド (Web Audio API 矩形波合成 - 完全オフライン)
  // ==========================================================================

  /**
   * AudioContextを取得する（未初期化なら生成）。
   * @returns {AudioContext|null} オーディオコンテキスト
   */
  function getCtx() {
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
      console.debug('[PixelDefense] AudioContext error:', e);
      return null;
    }
  }

  /**
   * 矩形波のビープ音を再生する（ピコピコ音の素）。
   * @param {number} freq - 周波数 (Hz)
   * @param {number} duration - 長さ (秒)
   * @param {number} [volume=0.08] - 音量 (0〜1)
   */
  function beep(freq, duration, volume = 0.08) {
    const ac = getCtx();
    if (!ac) return;
    try {
      const osc = ac.createOscillator();
      const gain = ac.createGain();
      osc.type = 'square';
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(volume, ac.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, ac.currentTime + duration);
      osc.connect(gain).connect(ac.destination);
      osc.start();
      osc.stop(ac.currentTime + duration);
    } catch (e) {
      console.debug('[PixelDefense] beep error:', e);
    }
  }

  const sounds = {
    shoot: () => beep(880, 0.06),
    hit: () => { beep(220, 0.08); setTimeout(() => beep(110, 0.1), 60); },
    playerHit: () => { beep(160, 0.15); setTimeout(() => beep(80, 0.3), 120); },
    gameOver: () => { beep(392, 0.2); setTimeout(() => beep(262, 0.2), 200); setTimeout(() => beep(131, 0.5), 400); },
    levelUp: () => { beep(523, 0.08); setTimeout(() => beep(784, 0.12), 90); }
  };

  // ==========================================================================
  // ゲームロジック
  // ==========================================================================

  /**
   * ゲーム状態を初期化してプレイを開始する。
   */
  function startGame() {
    game.state = 'playing';
    game.score = 0;
    game.lives = MAX_LIVES;
    game.level = 1;
    game.bullets = [];
    game.bombs = [];
    game.particles = [];
    game.player.x = CANVAS_WIDTH / 2;
    game.player.cool = 0;
    game.invaderDir = 1;
    game.invaderSpeed = INVADER_BASE_SPEED;
    game.fireCooldown = 0;
    game.invaderFireTimer = 0;
    spawnInvaders();
    updateHud();
  }

  /**
   * インベーダー編隊を初期配置する。
   */
  function spawnInvaders() {
    game.invaders = [];
    const gridWidth = (INVADER_COLS - 1) * INVADER_CELL_W;
    const offsetX = (CANVAS_WIDTH - gridWidth) / 2;
    for (let row = 0; row < INVADER_ROWS; row++) {
      for (let col = 0; col < INVADER_COLS; col++) {
        game.invaders.push({
          x: offsetX + col * INVADER_CELL_W,
          y: 46 + row * INVADER_CELL_H,
          alive: true,
          type: row === 0 ? 1 : 0 // 最上段は高得点（赤）
        });
      }
    }
  }

  /**
   * 1フレーム分の状態更新を行う。
   * @param {number} dt - 前フレームからの経過秒
   */
  function update(dt) {
    updatePlayer(dt);
    updateBullets(dt);
    updateInvaders(dt);
    if (game.state !== 'playing') return; // updateInvaders内でゲームオーバーになり得る
    updateBombs(dt);
    handleCollisions();
    updateParticles(dt);

    // レベルクリア判定（全滅で再編成・加速）
    if (game.state === 'playing' && game.invaders.every((inv) => !inv.alive)) {
      game.level += 1;
      game.invaderSpeed = INVADER_BASE_SPEED + (game.level - 1) * 8;
      sounds.levelUp();
      spawnInvaders();
    }
  }

  /**
   * 自機の移動・発射を更新する。
   * @param {number} dt - 経過秒
   */
  function updatePlayer(dt) {
    const p = game.player;
    if (input.pointerX !== null) {
      // タッチ/マウス追従（キー入力が優先）
      if (!input.left && !input.right) {
        p.x += (input.pointerX - p.x) * Math.min(1, dt * 12);
      }
      input.pointerX = null;
    }
    if (input.left) p.x -= PLAYER_SPEED * dt;
    if (input.right) p.x += PLAYER_SPEED * dt;
    p.x = Math.max(PLAYER_WIDTH / 2, Math.min(CANVAS_WIDTH - PLAYER_WIDTH / 2, p.x));

    p.cool = Math.max(0, p.cool - dt);
    if (input.fire && p.cool <= 0 && game.state === 'playing') {
      game.bullets.push({ x: p.x, y: p.y - 10 });
      p.cool = 0.3;
      sounds.shoot();
    }
  }

  /**
   * 自機弾の移動と画面外除去を更新する。
   * @param {number} dt - 経過秒
   */
  function updateBullets(dt) {
    for (const b of game.bullets) {
      b.y -= BULLET_SPEED * dt;
    }
    game.bullets = game.bullets.filter((b) => b.y > -8);
  }

  /**
   * インベーダー編隊の横移動・降下・時々爆撃を更新する。
   * @param {number} dt - 経過秒
   */
  function updateInvaders(dt) {
    if (game.state !== 'playing') return;
    const alive = game.invaders.filter((inv) => inv.alive);
    if (alive.length === 0) return;

    let minX = CANVAS_WIDTH;
    let maxX = 0;
    let maxY = 0;
    for (const inv of alive) {
      minX = Math.min(minX, inv.x);
      maxX = Math.max(maxX, inv.x);
      maxY = Math.max(maxY, inv.y);
    }

    const step = game.invaderSpeed * dt;
    for (const inv of alive) {
      inv.x += step * game.invaderDir;
    }

    // 画面端で方向転換＋一段降下
    if ((game.invaderDir > 0 && maxX + 10 >= CANVAS_WIDTH) || (game.invaderDir < 0 && minX - 10 <= 0)) {
      game.invaderDir *= -1;
      for (const inv of alive) {
        inv.y += INVADER_DESCENT;
      }
      maxY += INVADER_DESCENT;
      beep(140, 0.05, 0.04);
    }

    // 防衛ライン到達でゲームオーバー
    if (maxY >= game.player.y - 12) {
      endGame();
      return;
    }

    // インベーダーの間欠爆撃（レベルが上がるほど激化）
    game.invaderFireTimer -= dt;
    if (game.invaderFireTimer <= 0 && alive.length > 0) {
      const shooter = alive[Math.floor(Math.random() * alive.length)];
      game.bombs.push({ x: shooter.x, y: shooter.y + 10 });
      game.invaderFireTimer = Math.max(0.35, 1.6 - game.level * 0.15);
    }
  }

  /**
   * 敵弾の移動と画面外除去を更新する。
   * @param {number} dt - 経過秒
   */
  function updateBombs(dt) {
    for (const bomb of game.bombs) {
      bomb.y += BOMB_SPEED * dt;
    }
    game.bombs = game.bombs.filter((bomb) => bomb.y < CANVAS_HEIGHT + 8);
  }

  /**
   * 爆発パーティクルを更新する。
   * @param {number} dt - 経過秒
   */
  function updateParticles(dt) {
    for (const pt of game.particles) {
      pt.x += pt.vx * dt;
      pt.y += pt.vy * dt;
      pt.life -= dt;
    }
    game.particles = game.particles.filter((pt) => pt.life > 0);
  }

  /**
   * 弾・敵・自機の当たり判定とスコア加算を処理する。
   */
  function handleCollisions() {
    // 自機弾 → インベーダー
    for (const b of game.bullets) {
      for (const inv of game.invaders) {
        if (!inv.alive) continue;
        if (Math.abs(b.x - inv.x) <= 12 && Math.abs(b.y - inv.y) <= 10) {
          inv.alive = false;
          b.y = -100; // 弾を消滅させる
          game.score += inv.type === 1 ? SCORE_PER_INVADER * 2 : SCORE_PER_INVADER;
          spawnExplosion(inv.x, inv.y, inv.type === 1 ? PIXEL_COLORS.invaderAlt : PIXEL_COLORS.invader);
          sounds.hit();
          updateHud();
          break;
        }
      }
    }
    game.bullets = game.bullets.filter((b) => b.y > -8);

    if (game.state !== 'playing') return;

    // 敵弾 → 自機
    for (const bomb of game.bombs) {
      if (Math.abs(bomb.x - game.player.x) <= PLAYER_WIDTH / 2 + 3 && Math.abs(bomb.y - game.player.y) <= PLAYER_HEIGHT / 2 + 3) {
        bomb.y = CANVAS_HEIGHT + 100;
        game.lives -= 1;
        spawnExplosion(game.player.x, game.player.y, PIXEL_COLORS.player);
        sounds.playerHit();
        updateHud();
        if (game.lives <= 0) {
          endGame();
          return;
        }
      }
    }
    game.bombs = game.bombs.filter((bomb) => bomb.y < CANVAS_HEIGHT + 8);
  }

  /**
   * 爆発パーティクルを生成する。
   * @param {number} x - 爆発中心X
   * @param {number} y - 爆発中心Y
   * @param {string} color - パーティクル色
   */
  function spawnExplosion(x, y, color) {
    for (let i = 0; i < 10; i++) {
      const angle = (Math.PI * 2 * i) / 10;
      const speed = 40 + Math.random() * 60;
      game.particles.push({
        x: x,
        y: y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        life: 0.4 + Math.random() * 0.2,
        color: color
      });
    }
  }

  /**
   * ゲームオーバー処理。スコアをサーバーへ送信して永続化する。
   */
  function endGame() {
    if (game.state !== 'playing') return;
    game.state = 'gameover';
    game.gameoverAt = performance.now();
    sounds.gameOver();
    updateHud();
    submitScore(game.score);
  }

  /**
   * スコアを POST /api/action 経由で SQLite へ記録する。
   * @param {number} score - 達成スコア
   */
  function submitScore(score) {
    const doFetch = window.authFetch || window.fetch.bind(window);
    doFetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'record_minigame_score', game_id: GAME_ID, score: score })
    })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
      .then((data) => {
        if (data && typeof data.high_score === 'number') {
          game.highScore = Math.max(game.highScore, data.high_score);
          updateHud();
          console.debug(`[PixelDefense] スコア記録完了: score=${score}, high=${game.highScore}`);
        }
      })
      .catch((err) => console.debug('[PixelDefense] スコア送信に失敗（オフライン?）:', err));
  }

  // ==========================================================================
  // 描画
  // ==========================================================================

  /**
   * 1フレーム分を描画する。
   */
  function render() {
    ctx.fillStyle = '#050510';
    ctx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);

    // 星空ドット（固定パターンの簡易配置）
    ctx.fillStyle = '#1e2a3a';
    for (let i = 0; i < 24; i++) {
      const sx = (i * 37 + 13) % CANVAS_WIDTH;
      const sy = (i * 53 + 29) % (CANVAS_HEIGHT - 80);
      ctx.fillRect(sx, sy, 2, 2);
    }

    drawInvaders();
    drawPlayer();
    drawBulletsAndBombs();
    drawParticles();
    drawHudText();
  }

  /**
   * 自機（レトロ砲台）を描画する。
   */
  function drawPlayer() {
    if (game.state === 'gameover') return;
    const p = game.player;
    ctx.fillStyle = PIXEL_COLORS.player;
    // 砲台シルエット（中央砲身＋台形ベース）
    ctx.fillRect(p.x - 2, p.y - 8, 4, 8);
    ctx.fillRect(p.x - 10, p.y - 2, 20, 6);
    ctx.fillRect(p.x - 13, p.y + 4, 26, 4);

    // 残機表示（ミニ自機）
    for (let i = 0; i < game.lives; i++) {
      ctx.fillRect(8 + i * 16, 8, 10, 4);
      ctx.fillRect(11 + i * 16, 4, 4, 4);
    }
  }

  /**
   * インベーダー編隊を描画する。
   */
  function drawInvaders() {
    for (const inv of game.invaders) {
      if (!inv.alive) continue;
      const isFrame = Math.floor(performance.now() / 300) % 2 === 0;
      ctx.fillStyle = inv.type === 1 ? PIXEL_COLORS.invaderAlt : PIXEL_COLORS.invader;
      // 8bit風インベーダー（2フレームアニメ）
      ctx.fillRect(inv.x - 8, inv.y - 6, 16, 6);
      ctx.fillRect(inv.x - 10, inv.y, 20, 4);
      if (isFrame) {
        ctx.fillRect(inv.x - 10, inv.y + 4, 4, 4);
        ctx.fillRect(inv.x + 6, inv.y + 4, 4, 4);
      } else {
        ctx.fillRect(inv.x - 6, inv.y + 4, 4, 4);
        ctx.fillRect(inv.x + 2, inv.y + 4, 4, 4);
      }
      ctx.fillStyle = '#050510';
      ctx.fillRect(inv.x - 4, inv.y - 3, 3, 3); // 目
      ctx.fillRect(inv.x + 1, inv.y - 3, 3, 3); // 目
    }
  }

  /**
   * 自機弾と敵弾を描画する。
   */
  function drawBulletsAndBombs() {
    ctx.fillStyle = PIXEL_COLORS.bullet;
    for (const b of game.bullets) {
      ctx.fillRect(b.x - 1, b.y - 6, 2, 8);
    }
    ctx.fillStyle = PIXEL_COLORS.bomb;
    for (const bomb of game.bombs) {
      ctx.fillRect(bomb.x - 1, bomb.y, 2, 6);
    }
  }

  /**
   * 爆発パーティクルを描画する。
   */
  function drawParticles() {
    for (const pt of game.particles) {
      ctx.globalAlpha = Math.max(0, pt.life / 0.6);
      ctx.fillStyle = pt.color;
      ctx.fillRect(pt.x - 2, pt.y - 2, 4, 4);
    }
    ctx.globalAlpha = 1.0;
  }

  /**
   * スコア・状態メッセージを描画する。
   */
  function drawHudText() {
    ctx.fillStyle = PIXEL_COLORS.text;
    ctx.font = 'bold 12px "Courier New", monospace';
    ctx.textAlign = 'right';
    ctx.fillText(`SCORE ${String(game.score).padStart(6, '0')}`, CANVAS_WIDTH - 10, 14);
    ctx.textAlign = 'center';

    if (game.state === 'idle') {
      ctx.font = 'bold 18px "Courier New", monospace';
      ctx.fillText('PIXEL DEFENSE', CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2 - 30);
      ctx.font = '12px "Courier New", monospace';
      ctx.fillStyle = PIXEL_COLORS.dim;
      ctx.fillText('タップ / SPACE で開始', CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2 + 6);
    } else if (game.state === 'gameover') {
      ctx.font = 'bold 20px "Courier New", monospace';
      ctx.fillStyle = PIXEL_COLORS.invaderAlt;
      ctx.fillText('GAME OVER', CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2 - 20);
      ctx.font = '12px "Courier New", monospace';
      ctx.fillStyle = PIXEL_COLORS.dim;
      ctx.fillText(`SCORE ${game.score} / HI ${game.highScore}`, CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2 + 10);
      ctx.fillStyle = PIXEL_COLORS.text;
      ctx.fillText('タップ / SPACE でリトライ', CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2 + 34);
    }
  }

  // ==========================================================================
  // メインループ / 公開API
  // ==========================================================================

  /**
   * requestAnimationFrame ループ。
   * @param {number} time - タイムスタンプ
   */
  function loop(time) {
    if (!isRunning) return;
    const dt = Math.min(0.05, (time - lastTime) / 1000 || 0);
    lastTime = time;

    // idle/gameover 状態でも入力で開始/リトライできるようにする。
    // ただしゲームオーバー直後 GAMEOVER_COOLDOWN_MS は入力を無視し、
    // GAME OVER 表示（スコア確認）が誤タップで飛ばされるのを防ぐ。
    if (game.state !== 'playing' && (input.fire || input.pointerX !== null)) {
      const inCooldown = game.state === 'gameover' &&
        (performance.now() - game.gameoverAt) < GAMEOVER_COOLDOWN_MS;
      input.fire = false;
      input.pointerX = null;
      if (!inCooldown) {
        startGame();
      }
    }

    if (game.state === 'playing') {
      update(dt);
    }
    updateParticles(dt);
    render();
    rafId = requestAnimationFrame(loop);
  }

  /**
   * HUD（DOM側スコア表示）を更新する。
   */
  function updateHud() {
    if (scoreEl) scoreEl.textContent = String(game.score);
    if (highEl) highEl.textContent = String(game.highScore);
  }

  /**
   * ミニゲームモーダルを開いてゲームを開始する。
   */
  function show() {
    initialize();
    if (!isInitialized) return;
    overlay.classList.add('active');
    isRunning = true;
    lastTime = performance.now();
    getCtx(); // ユーザー操作起点でAudioContextを解錠
    rafId = requestAnimationFrame(loop);
  }

  /**
   * ミニゲームモーダルを閉じてゲームを停止する。
   */
  function hide() {
    isRunning = false;
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
    if (overlay) overlay.classList.remove('active');
    input.left = false;
    input.right = false;
    input.fire = false;
    input.pointerX = null;
    game.state = 'idle';
  }

  // グローバル公開（疎結合API）
  window.PixelDefense = { show: show, hide: hide };
})();
