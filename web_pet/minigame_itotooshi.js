/**
 * ネオ秘書くん ミニゲーム「🪡 糸通し」 (minigame_itotooshi.js)
 *
 * ガラケー風 糸通し: 白い糸が右へ進み続けるので、長押し (タッチ/Space) で
 * 上昇・離して下降させ、下から立つ縫い針の「穴 (メ)」に糸先端を通す。
 * 穴を通せば1本カウント、針の軸に触れると糸が切れる。10本ごとに加速。
 */
(function () {
  'use strict';

  const GAME_ID = 'itotooshi';
  const W = 320;
  const H = 420;

  let api = null;
  let running = false;
  let pressing = false;
  let rafId = null;
  let lastTime = 0;

  const thread = { x: 70, y: 210, vy: 0, r: 5 };
  const GRAVITY = 900;  // px/s^2
  const THRUST = -420;  // 長押し中の上昇加速度
  const SHAFT_W = 5;    // 針の軸の半幅 (当たり判定・描画共用)
  let scrollSpeed = 90;
  let needles = []; // {x, eyeY, eyeH, passed, wasInEye}
  let score = 0;
  let best = 0;
  let state = 'ready'; // ready | play | over
  let spawnTimer = 0;
  let wobble = 0;
  let lastEyeY = H / 2; // 連続性確保用 (前の針の穴の高さ)

  function reset() {
    thread.x = 70;
    thread.y = H / 2;
    thread.vy = 0;
    scrollSpeed = 90;
    needles = [];
    score = 0;
    spawnTimer = 0;
    lastEyeY = H / 2;
  }

  /**
   * 下から立つ縫い針を1本生成する。
   * 穴 (メ) は針の最上部にあり、前の針の穴から大きく乖離しすぎない範囲で
   * 高さを決める (到達不可能な配置の防止)。
   * @returns {void}
   */
  function spawnNeedle() {
    const eyeH = Math.max(44, 70 - score * 1.2);
    const lo = 90;
    const hi = H - 90;
    let eyeY = lo + Math.random() * (hi - lo);
    // 前の針の穴から ±150px 以内に収める (届かない距離の排除)
    eyeY = Math.max(lo, Math.min(hi, lastEyeY + Math.max(-150, Math.min(150, eyeY - lastEyeY))));
    lastEyeY = eyeY;
    needles.push({ x: W + 20, eyeY: eyeY, eyeH: eyeH, passed: false, wasInEye: false });
  }

  function startGame() {
    reset();
    state = 'play';
    api.setScore(0);
  }

  function gameOver() {
    state = 'over';
    api.beep(110, 0.4, 0.12, 'sawtooth');
    api.submitScore(GAME_ID, score).then((hi) => {
      if (hi !== null) best = Math.max(best, hi);
      api.setHigh(best);
    });
  }

  function flap() {
    if (state !== 'play') {
      startGame();
      return;
    }
    pressing = true;
  }

  function update(dt) {
    wobble += dt;
    if (state !== 'play') return;

    // 糸の物理 (長押しで上昇 / 離すと下降)
    thread.vy += (pressing ? THRUST : GRAVITY) * dt;
    thread.y += thread.vy * dt;
    if (thread.y < thread.r) {
      thread.y = thread.r;
      thread.vy = 0;
    }
    if (thread.y > H - thread.r) {
      gameOver();
      return;
    }

    // 針の生成・移動
    spawnTimer -= dt;
    if (spawnTimer <= 0) {
      spawnNeedle();
      spawnTimer = Math.max(1.1, 1.7 - score * 0.02);
    }
    for (let i = needles.length - 1; i >= 0; i--) {
      const n = needles[i];
      n.x -= scrollSpeed * dt;
      if (n.x < -30) {
        needles.splice(i, 1);
        continue;
      }

      // 糸の先端が針の幅に差しかかっている間、穴の中にいるか記録する
      const overlapping = thread.x + thread.r > n.x - SHAFT_W && thread.x - thread.r < n.x + SHAFT_W;
      if (overlapping) {
        n.wasInEye = thread.y > n.eyeY && thread.y < n.eyeY + n.eyeH;
        // 軸 (穴より下) に触れたら糸切れ
        if (thread.y + thread.r * 0.6 > n.eyeY + n.eyeH) {
          gameOver();
          return;
        }
      } else if (!n.passed && n.x + SHAFT_W < thread.x - thread.r) {
        // 針を完全に通過: 穴を通れていれば本数カウント (上を飛び越えは無得点)
        n.passed = true;
        if (n.wasInEye) {
          score += 1;
          api.setScore(score);
          api.beep(880 + (score % 10) * 40, 0.07, 0.06); // ピロリン
          if (score % 10 === 0) {
            scrollSpeed += 22; // 10本ごとに加速
            api.beep(1320, 0.15, 0.08);
          }
        }
      }
    }
  }

  /**
   * 糸を描く: 先端から波打ちながら画面左へ延びる白い糸。
   * @returns {void}
   */
  function drawThread() {
    const ctx = api.ctx;
    ctx.strokeStyle = '#f2f4ff';
    ctx.lineWidth = 2;
    ctx.shadowColor = 'rgba(255,255,255,0.7)';
    ctx.shadowBlur = 3;
    ctx.beginPath();
    ctx.moveTo(thread.x, thread.y);
    for (let x = thread.x - 8; x > -10; x -= 8) {
      const y = thread.y + Math.sin(wobble * 6 + x * 0.08) * 6;
      ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.shadowBlur = 0;
    // 糸の先端 (針穴へ向かう糸玉)
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.arc(thread.x, thread.y, thread.r + 1, 0, Math.PI * 2);
    ctx.fill();
  }

  /**
   * 縫い針1本を描く: 下から立つ銀色の軸 + 先端の穴 (リング)。
   * @param {CanvasRenderingContext2D} ctx - 描画コンテキスト
   * @param {{x: number, eyeY: number, eyeH: number}} n - 針
   * @returns {void}
   */
  function drawNeedle(ctx, n) {
    const shaftTop = n.eyeY + n.eyeH;
    const grad = ctx.createLinearGradient(n.x - SHAFT_W, 0, n.x + SHAFT_W, 0);
    grad.addColorStop(0, '#6e7690');
    grad.addColorStop(0.5, '#dfe6ff');
    grad.addColorStop(1, '#6e7690');
    // 軸
    ctx.fillStyle = grad;
    ctx.fillRect(n.x - SHAFT_W, shaftTop, SHAFT_W * 2, H - shaftTop);
    // 穴 (リング): 先端の楕円リング
    ctx.strokeStyle = grad;
    ctx.lineWidth = 5;
    ctx.beginPath();
    ctx.ellipse(n.x, n.eyeY + n.eyeH / 2, SHAFT_W + 2, n.eyeH / 2, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.lineWidth = 1;
  }

  function draw() {
    const ctx = api.ctx;
    // 背景 (縫い作業台風の黒)
    ctx.fillStyle = '#101014';
    ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth = 1;
    for (let gy = 0; gy < H; gy += 28) {
      ctx.beginPath();
      ctx.moveTo(0, gy);
      ctx.lineTo(W, gy);
      ctx.stroke();
    }

    for (const n of needles) {
      drawNeedle(ctx, n);
    }

    drawThread();

    // 状態表示
    ctx.textAlign = 'center';
    if (state === 'ready') {
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 18px sans-serif';
      ctx.fillText('🪡 糸通し', W / 2, H / 2 - 40);
      ctx.font = '13px sans-serif';
      ctx.fillText('針の「穴」に糸を通せ！', W / 2, H / 2 - 12);
      ctx.fillText('長押しで上昇・離して下降', W / 2, H / 2 + 8);
      ctx.fillText('タップまたは Space でスタート', W / 2, H / 2 + 34);
    } else if (state === 'over') {
      ctx.fillStyle = 'rgba(0,0,0,0.6)';
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = '#ff8fa3';
      ctx.font = 'bold 22px sans-serif';
      ctx.fillText('糸が切れた…', W / 2, H / 2 - 20);
      ctx.fillStyle = '#fff';
      ctx.font = '15px sans-serif';
      ctx.fillText(score + ' 本 通した', W / 2, H / 2 + 10);
      ctx.fillText('タップでリトライ', W / 2, H / 2 + 36);
    }
  }

  function handleInput(type, e) {
    if (type === 'keydown') {
      if (e.code === 'Space' || e.key === ' ') {
        e.preventDefault();
        if (!e.repeat) flap();
      }
      return;
    }
    if (type === 'keyup') {
      if (e.code === 'Space' || e.key === ' ') {
        pressing = false;
      }
      return;
    }
    if (type === 'touchstart' || type === 'mousedown') {
      e.preventDefault();
      flap();
      return;
    }
    if (type === 'touchend' || type === 'mouseup') {
      pressing = false;
    }
  }

  function start(a) {
    api = a;
    running = true;
    reset();
    state = 'ready';
    api.setScore(0);
    api.fetchHigh(GAME_ID).then((h) => {
      best = h;
      api.setHigh(best);
    });
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
    const step = (t) => {
      if (!running) return;
      const dt = Math.min(0.05, (t - lastTime) / 1000 || 0);
      lastTime = t;
      update(dt);
      draw();
      rafId = requestAnimationFrame(step);
    };
    lastTime = performance.now();
    rafId = requestAnimationFrame(step);
  }

  function stop() {
    running = false;
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  }

  window.MinigameArcade.register({
    id: GAME_ID,
    title: '🪡 糸通し',
    start: start,
    stop: stop,
    handleInput: handleInput
  });
})();

