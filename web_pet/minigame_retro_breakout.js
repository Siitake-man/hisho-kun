/**
 * ネオ秘書くん ミニゲーム「🧱 ブロックラリー」 (minigame_retro_breakout.js)
 *
 * パドル崩し: ボールを打ち返してバグブロックを破壊する癒やし系リラックスゲーム。
 * 跳ね返り角度はパドルの当たった位置で変化。全破壊で次レベル (加速)。
 */
(function () {
  'use strict';

  const GAME_ID = 'retro_breakout';
  const W = 320;
  const H = 420;
  const PADDLE_W = 56;
  const PADDLE_H = 10;
  const BALL_R = 5;
  const ROWS = 5;
  const COLS = 8;
  const ROW_COLORS = ['#ff8fa3', '#ffb35e', '#ffe66e', '#7fe0a8', '#7fb8ff'];
  const ROW_POINTS = [50, 40, 30, 20, 10];

  let api = null;
  let running = false;
  let rafId = null;
  let lastTime = 0;

  let paddle = { x: W / 2 - PADDLE_W / 2, y: H - 34 };
  let ball = { x: W / 2, y: H - 60, vx: 130, vy: -190, stuck: true };
  let blocks = []; // {col, row, alive}
  let score = 0;
  let best = 0;
  let level = 1;
  let speedMul = 1;
  let state = 'ready'; // ready | play | over
  let lives = 3;
  let pointerX = null;

  function buildBlocks() {
    blocks = [];
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        blocks.push({ col: c, row: r, alive: true });
      }
    }
  }

  function startGame() {
    score = 0;
    level = 1;
    speedMul = 1;
    lives = 3;
    buildBlocks();
    resetBall();
    state = 'play';
    api.setScore(0);
  }

  function resetBall() {
    ball.x = paddle.x + PADDLE_W / 2;
    ball.y = paddle.y - BALL_R - 1;
    const angle = -Math.PI / 2 + (Math.random() * 0.6 - 0.3);
    const speed = 220 * speedMul;
    ball.vx = Math.cos(angle) * speed;
    ball.vy = Math.sin(angle) * speed;
    ball.stuck = false;
  }

  function gameOver() {
    state = 'over';
    api.beep(90, 0.4, 0.12, 'sawtooth');
    api.submitScore(GAME_ID, score).then((hi) => {
      if (hi !== null) best = Math.max(best, hi);
      api.setHigh(best);
    });
  }

  function blockRect(b) {
    const bx = 16 + b.col * 36;
    const by = 56 + b.row * 20;
    return { x: bx, y: by, w: 32, h: 16 };
  }

  function update(dt) {
    if (state !== 'play') return;

    // パドル追従 (ポインタ優先、なければ自動中央)
    if (pointerX !== null) {
      paddle.x = Math.max(4, Math.min(W - PADDLE_W - 4, pointerX - PADDLE_W / 2));
    }

    // ボール移動
    ball.x += ball.vx * dt;
    ball.y += ball.vy * dt;

    // 壁反射
    if (ball.x < BALL_R) {
      ball.x = BALL_R;
      ball.vx = Math.abs(ball.vx);
      api.beep(320, 0.05, 0.05);
    }
    if (ball.x > W - BALL_R) {
      ball.x = W - BALL_R;
      ball.vx = -Math.abs(ball.vx);
      api.beep(320, 0.05, 0.05);
    }
    if (ball.y < BALL_R + 40) {
      ball.y = BALL_R + 40;
      ball.vy = Math.abs(ball.vy);
      api.beep(320, 0.05, 0.05);
    }

    // パドル反射 (当たった位置で角度変化)
    if (ball.vy > 0 && ball.y + BALL_R >= paddle.y && ball.y + BALL_R <= paddle.y + PADDLE_H &&
        ball.x >= paddle.x - BALL_R && ball.x <= paddle.x + PADDLE_W + BALL_R) {
      const hit = (ball.x - (paddle.x + PADDLE_W / 2)) / (PADDLE_W / 2); // -1..1
      const angle = -Math.PI / 2 + hit * 1.05;
      const speed = Math.min(420, 220 * speedMul + level * 14);
      ball.vx = Math.cos(angle) * speed;
      ball.vy = Math.sin(angle) * speed;
      ball.y = paddle.y - BALL_R;
      api.beep(520, 0.06, 0.06); // ポコッ
    }

    // 落下
    if (ball.y > H + BALL_R * 2) {
      lives -= 1;
      if (lives <= 0) {
        gameOver();
        return;
      }
      api.beep(180, 0.2, 0.1);
      resetBall();
    }

    // ブロック衝突
    for (const b of blocks) {
      if (!b.alive) continue;
      const r = blockRect(b);
      if (ball.x + BALL_R > r.x && ball.x - BALL_R < r.x + r.w &&
          ball.y + BALL_R > r.y && ball.y - BALL_R < r.y + r.h) {
        b.alive = false;
        // 簡易反射: 侵入方向で軸を決める
        const px = Math.min(Math.abs(ball.x - r.x), Math.abs(ball.x - (r.x + r.w)));
        const py = Math.min(Math.abs(ball.y - r.y), Math.abs(ball.y - (r.y + r.h)));
        if (px < py) {
          ball.vx = -ball.vx;
        } else {
          ball.vy = -ball.vy;
        }
        score += ROW_POINTS[b.row] * (level > 1 ? 2 : 1);
        api.setScore(score);
        api.beep(660 + (ROWS - b.row) * 60, 0.07, 0.07); // ポコポコ
        break;
      }
    }

    // 全破壊 → 次レベル
    if (blocks.every((b) => !b.alive)) {
      level += 1;
      speedMul = Math.min(2.2, speedMul + 0.18);
      api.beep(880, 0.12, 0.1);
      setTimeout(() => api.beep(1320, 0.18, 0.1), 130);
      buildBlocks();
      resetBall();
    }
  }

  function draw() {
    const ctx = api.ctx;
    // 背景
    ctx.fillStyle = '#141a2e';
    ctx.fillRect(0, 0, W, H);
    // 上部情報バー
    ctx.fillStyle = '#0d1120';
    ctx.fillRect(0, 0, W, 40);
    ctx.fillStyle = '#9aa7d0';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('🧱 Lv.' + level, 10, 16);
    ctx.fillText('♥ ' + lives, 70, 16);

    // ブロック (バグ風 🐛 付き)
    for (const b of blocks) {
      if (!b.alive) continue;
      const r = blockRect(b);
      ctx.fillStyle = ROW_COLORS[b.row];
      ctx.fillRect(r.x, r.y, r.w, r.h);
      ctx.fillStyle = 'rgba(0,0,0,0.35)';
      ctx.fillRect(r.x, r.y + r.h - 4, r.w, 4);
    }

    // パドル
    ctx.fillStyle = '#e8ecff';
    ctx.fillRect(paddle.x, paddle.y, PADDLE_W, PADDLE_H);
    ctx.fillStyle = '#7fb8ff';
    ctx.fillRect(paddle.x + 4, paddle.y + 3, PADDLE_W - 8, 3);

    // ボール
    ctx.fillStyle = '#ffe66e';
    ctx.beginPath();
    ctx.arc(ball.x, ball.y, BALL_R, 0, Math.PI * 2);
    ctx.fill();

    // 状態表示
    ctx.textAlign = 'center';
    if (state === 'ready') {
      ctx.fillStyle = 'rgba(0,0,0,0.55)';
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = '#ffe66e';
      ctx.font = 'bold 20px sans-serif';
      ctx.fillText('🧱 ブロックラリー', W / 2, H / 2 - 46);
      ctx.fillStyle = '#fff';
      ctx.font = '13px sans-serif';
      ctx.fillText('バグブロックを全部壊せ！', W / 2, H / 2 - 16);
      ctx.fillText('左右ドラッグ / 矢印キーでパドル', W / 2, H / 2 + 6);
      ctx.fillText('タップまたは Space で開始', W / 2, H / 2 + 32);
    } else if (state === 'over') {
      ctx.fillStyle = 'rgba(0,0,0,0.6)';
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = '#ff8fa3';
      ctx.font = 'bold 22px sans-serif';
      ctx.fillText('ボールが逃げた…', W / 2, H / 2 - 20);
      ctx.fillStyle = '#fff';
      ctx.font = '15px sans-serif';
      ctx.fillText(score + ' pt (Lv.' + level + ')', W / 2, H / 2 + 10);
      ctx.fillText('タップでリトライ', W / 2, H / 2 + 36);
    } else if (ball.stuck === false && state === 'play') {
      // プレイ中ガイド (開始直後のみ)
      if (ball.y > H - 90 && Math.abs(ball.vx) < 40) {
        ctx.fillStyle = 'rgba(255,255,255,0.4)';
        ctx.font = '11px sans-serif';
        ctx.fillText('← → で動かそう', W / 2, H - 60);
      }
    }
  }

  function handleInput(type, e) {
    const rect = api.canvas.getBoundingClientRect();
    const sx = api.canvas.width / rect.width;
    if (type === 'keydown') {
      if (e.code === 'Space' || e.key === ' ') {
        e.preventDefault();
        if (state === 'ready' || state === 'over') {
          startGame();
        } else if (ball.stuck) {
          resetBall();
        }
        return;
      }
      if (e.code === 'ArrowLeft' || e.code === 'ArrowRight') {
        const dir = e.code === 'ArrowLeft' ? -1 : 1;
        paddle.x = Math.max(4, Math.min(W - PADDLE_W - 4, paddle.x + dir * 26));
        pointerX = paddle.x + PADDLE_W / 2; // キー操作をポインタに反映
      }
      return;
    }
    if (type === 'keyup' && (e.code === 'ArrowLeft' || e.code === 'ArrowRight')) {
      return; // キーは押下ごとにステップ移動
    }
    if (type === 'touchstart' || type === 'mousedown') {
      e.preventDefault();
      if (state === 'ready' || state === 'over') {
        startGame();
        return;
      }
      if (ball.stuck) {
        resetBall();
        return;
      }
      pointerX = (e.clientX - rect.left) * sx;
      return;
    }
    if (type === 'touchmove' || type === 'mousemove') {
      if (state !== 'play') return;
      if (type === 'mousemove' && e.buttons === 0) {
        pointerX = (e.clientX - rect.left) * sx; // PCはホバー追従
      } else {
        pointerX = (e.clientX - rect.left) * sx;
      }
      return;
    }
    if (type === 'touchend' || type === 'mouseup') {
      // 追従は継続 (パドルは最後のXを保持)
    }
  }

  function start(a) {
    api = a;
    running = true;
    state = 'ready';
    score = 0;
    level = 1;
    lives = 3;
    pointerX = null;
    buildBlocks();
    ball.stuck = true;
    ball.x = W / 2;
    ball.y = H - 60;
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
    title: '🧱 ブロックラリー',
    usesArrowKeys: true,
    start: start,
    stop: stop,
    handleInput: handleInput
  });
})();

