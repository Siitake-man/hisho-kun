/**
 * ネオ秘書くん ミニゲーム「🪡 糸通し」 (minigame_itotooshi.js)
 *
 * 1ボタン浮遊アクション: 長押し (タッチ/Space) で上昇、離すと下降。
 * 右から流れてくる針の穴 (ギャップ) を連続でくぐり抜ける。
 * 10本ごとに加速し、くぐり抜けた本数がスコア。
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

  const needle = { x: 90, y: 210, vy: 0, r: 10 };
  const GRAVITY = 900; // px/s^2
  const THRUST = -420; // 長押し中の上昇加速度
  let scrollSpeed = 90;
  let needles = []; // {x, gapY, gapH, passed}
  let score = 0;
  let best = 0;
  let state = 'ready'; // ready | play | over
  let spawnTimer = 0;
  let wobble = 0;

  function reset() {
    needle.x = 90;
    needle.y = H / 2;
    needle.vy = 0;
    scrollSpeed = 90;
    needles = [];
    score = 0;
    spawnTimer = 0;
  }

  function spawnNeedle() {
    const gapH = Math.max(64, 110 - score * 2);
    const gapY = 70 + Math.random() * (H - 140 - gapH);
    needles.push({ x: W + 30, gapY: gapY, gapH: gapH, passed: false });
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

    // 物理
    needle.vy += (pressing ? THRUST : GRAVITY) * dt;
    needle.y += needle.vy * dt;
    if (needle.y < needle.r) {
      needle.y = needle.r;
      needle.vy = 0;
    }
    if (needle.y > H - needle.r) {
      gameOver();
      return;
    }

    // 針の生成・移動
    spawnTimer -= dt;
    if (spawnTimer <= 0) {
      spawnNeedle();
      spawnTimer = Math.max(0.9, 1.5 - score * 0.02);
    }
    for (let i = needles.length - 1; i >= 0; i--) {
      const n = needles[i];
      n.x -= scrollSpeed * dt;
      if (!n.passed && n.x + 14 < needle.x - needle.r) {
        n.passed = true;
        score += 1;
        api.setScore(score);
        api.beep(880 + (score % 10) * 40, 0.07, 0.06); // ピロリン
        if (score % 10 === 0) {
          scrollSpeed += 22; // 10本ごとに加速
          api.beep(1320, 0.15, 0.08);
        }
      }
      if (n.x < -40) {
        needles.splice(i, 1);
        continue;
      }
      // 針本体 (穴の上下の板) との当たり判定
      const hitPlate = needle.x + needle.r > n.x - 14 && needle.x - needle.r < n.x + 14;
      const inGap = needle.y - needle.r > n.gapY && needle.y + needle.r < n.gapY + n.gapH;
      if (hitPlate && !inGap) {
        gameOver();
        return;
      }
    }
  }

  function drawThread() {
    // 針から手前へ波打つ糸を描く
    const ctx = api.ctx;
    ctx.strokeStyle = '#ffd27f';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(needle.x, needle.y);
    for (let x = needle.x - 8; x > 0; x -= 8) {
      const y = needle.y + Math.sin(wobble * 6 + x * 0.08) * 5;
      ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  function draw() {
    const ctx = api.ctx;
    // 背景 (縫い布風)
    ctx.fillStyle = '#1d2333';
    ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = 'rgba(255,255,255,0.06)';
    ctx.lineWidth = 1;
    for (let gy = 0; gy < H; gy += 28) {
      ctx.beginPath();
      ctx.moveTo(0, gy);
      ctx.lineTo(W, gy);
      ctx.stroke();
    }

    // 針の穴 (上下の板)
    for (const n of needles) {
      ctx.fillStyle = '#8a93b8';
      ctx.fillRect(n.x - 14, 0, 28, n.gapY);
      ctx.fillStyle = '#b9c2e8';
      ctx.fillRect(n.x - 14, n.gapY - 6, 28, 6);
      ctx.fillStyle = '#8a93b8';
      ctx.fillRect(n.x - 14, n.gapY + n.gapH, 28, H - n.gapY - n.gapH);
      ctx.fillStyle = '#b9c2e8';
      ctx.fillRect(n.x - 14, n.gapY + n.gapH, 28, 6);
    }

    drawThread();

    // 針 (プレイヤー)
    ctx.fillStyle = '#e8ecff';
    ctx.beginPath();
    ctx.moveTo(needle.x + 14, needle.y);
    ctx.lineTo(needle.x - 10, needle.y - 7);
    ctx.lineTo(needle.x - 10, needle.y + 7);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = '#ff8fa3';
    ctx.fillRect(needle.x - 13, needle.y - 2, 4, 4); // 糸結び

    // 状態表示
    ctx.textAlign = 'center';
    if (state === 'ready') {
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 18px sans-serif';
      ctx.fillText('🪡 糸通し', W / 2, H / 2 - 40);
      ctx.font = '13px sans-serif';
      ctx.fillText('長押しで上昇・離して下降', W / 2, H / 2 - 12);
      ctx.fillText('針の穴をくぐり抜けろ！', W / 2, H / 2 + 8);
      ctx.fillText('タップまたは Space でスタート', W / 2, H / 2 + 34);
    } else if (state === 'over') {
      ctx.fillStyle = 'rgba(0,0,0,0.6)';
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = '#ff8fa3';
      ctx.font = 'bold 22px sans-serif';
      ctx.fillText('糸が切れた…', W / 2, H / 2 - 20);
      ctx.fillStyle = '#fff';
      ctx.font = '15px sans-serif';
      ctx.fillText(score + ' 本くぐり抜けた', W / 2, H / 2 + 10);
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

