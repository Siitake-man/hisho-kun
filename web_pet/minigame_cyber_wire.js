/**
 * ネオ秘書くん ミニゲーム「⚡ 電脳イライラ棒」 (minigame_cyber_wire.js)
 *
 * 集中スリル迷路: 指ドラッグ / マウス移動でプローブを操作し、
 * マザーボード配線風の狭いコースを壁に触れずにゴールへ進む。
 * 壁接触で火花エフェクト + バチッ音、進行距離 (m) がスコア。
 */
(function () {
  'use strict';

  const GAME_ID = 'cyber_wire';
  const W = 320;
  const H = 420;
  const PROBE_R = 7;

  let api = null;
  let running = false;
  let rafId = null;
  let lastTime = 0;

  let walls = []; // {x1, y1, x2, y2}
  let goal = { x: W - 40, y: H - 50 };
  let probe = { x: 30, y: 30 };
  let dragging = false;
  let lastPt = null; // ドラッグ基準点 (デルタ追従用)
  let scoreM = 0;
  let best = 0;
  let state = 'ready'; // ready | play | over | clear
  let sparks = []; // {x, y, life}
  let shockCooldown = 0;
  let reachedX = 30; // 進行度の基準

  // コース生成: ジグザグの通路を壁ペアで構成する
  function buildCourse() {
    walls = [];
    let y = 60;
    let dir = 1;
    let x = 0;
    const margin = 24;
    while (y < H - 80) {
      const corridor = 52 + Math.random() * 18;
      const nextY = y + corridor;
      if (dir > 0) {
        // 下壁が下からせり出す
        walls.push({ x1: x, y1: nextY + 34, x2: x + W * 0.62, y2: nextY + 34 });
        walls.push({ x1: x + W * 0.62, y1: nextY + 34, x2: x + W * 0.62, y2: H });
      } else {
        // 上壁が上からせり出す
        walls.push({ x1: x, y1: nextY - 34, x2: x + W * 0.62, y2: nextY - 34 });
        walls.push({ x1: x + W * 0.62, y1: 0, x2: x + W * 0.62, y2: nextY - 34 });
      }
      x = 0;
      y = nextY;
      dir = -dir;
    }
    // 外周 (上下)
    walls.push({ x1: 0, y1: margin - 18, x2: W, y2: margin - 18 });
    walls.push({ x1: 0, y1: H - margin + 18, x2: W, y2: H - margin + 18 });
    // 左壁 (スタート後方)
    walls.push({ x1: 8, y1: 0, x2: 8, y2: H });
    goal = { x: W - 34, y: y - 20 };
  }

  function distToSegment(px, py, x1, y1, x2, y2) {
    const dx = x2 - x1;
    const dy = y2 - y1;
    const lenSq = dx * dx + dy * dy;
    let t = lenSq === 0 ? 0 : ((px - x1) * dx + (py - y1) * dy) / lenSq;
    t = Math.max(0, Math.min(1, t));
    const cx = x1 + t * dx;
    const cy = y1 + t * dy;
    return Math.hypot(px - cx, py - cy);
  }

  function hitsWall(px, py) {
    for (const w of walls) {
      if (distToSegment(px, py, w.x1, w.y1, w.x2, w.y2) < PROBE_R + 2) {
        return true;
      }
    }
    return false;
  }

  function startGame() {
    buildCourse();
    probe.x = 30;
    probe.y = 40;
    reachedX = 30;
    scoreM = 0;
    sparks = [];
    state = 'play';
    api.setScore(0);
  }

  function gameOver() {
    state = 'over';
    api.beep(90, 0.35, 0.14, 'sawtooth');
    api.submitScore(GAME_ID, Math.floor(scoreM)).then((hi) => {
      if (hi !== null) best = Math.max(best, hi);
      api.setHigh(best);
    });
  }

  function update(dt) {
    shockCooldown = Math.max(0, shockCooldown - dt);
    if (state !== 'play') return;

    // 進行度スコア (右へ進むほど加算)
    if (probe.x > reachedX) {
      scoreM += (probe.x - reachedX) / 10;
      reachedX = probe.x;
      api.setScore(Math.floor(scoreM));
    }

    // ゴール判定
    if (Math.hypot(probe.x - goal.x, probe.y - goal.y) < 18) {
      state = 'clear';
      scoreM += 500;
      api.setScore(Math.floor(scoreM));
      api.beep(880, 0.12, 0.1);
      setTimeout(() => api.beep(1320, 0.2, 0.1), 120);
      api.submitScore(GAME_ID, Math.floor(scoreM)).then((hi) => {
        if (hi !== null) best = Math.max(best, hi);
        api.setHigh(best);
      });
      return;
    }

    // 壁接触判定
    if (shockCooldown <= 0 && hitsWall(probe.x, probe.y)) {
      shockCooldown = 0.6;
      for (let i = 0; i < 8; i++) {
        sparks.push({
          x: probe.x,
          y: probe.y,
          vx: (Math.random() - 0.5) * 160,
          vy: (Math.random() - 0.5) * 160,
          life: 0.4
        });
      }
      api.beep(70 + Math.random() * 40, 0.1, 0.12, 'sawtooth');
      // ペナルティ: スタート地点付近へ後退
      probe.x = Math.max(30, probe.x - 46);
      scoreM = Math.max(0, scoreM - 5);
      api.setScore(Math.floor(scoreM));
      if (probe.x <= 30.01 && hitsWall(30, probe.y)) {
        gameOver();
      }
    }

    // 火花エフェクト更新
    for (let i = sparks.length - 1; i >= 0; i--) {
      const s = sparks[i];
      s.x += s.vx * dt;
      s.y += s.vy * dt;
      s.life -= dt;
      if (s.life <= 0) sparks.splice(i, 1);
    }
  }

  function draw() {
    const ctx = api.ctx;
    // 背景 (マザーボード風)
    ctx.fillStyle = '#0d2b1e';
    ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = 'rgba(80, 220, 140, 0.12)';
    ctx.lineWidth = 1;
    for (let gx = 0; gx < W; gx += 24) {
      ctx.beginPath();
      ctx.moveTo(gx, 0);
      ctx.lineTo(gx, H);
      ctx.stroke();
    }
    for (let gy = 0; gy < H; gy += 24) {
      ctx.beginPath();
      ctx.moveTo(0, gy);
      ctx.lineTo(W, gy);
      ctx.stroke();
    }

    // 壁 (配線基板)
    ctx.strokeStyle = '#e05555';
    ctx.lineWidth = 6;
    ctx.lineCap = 'round';
    ctx.beginPath();
    for (const w of walls) {
      ctx.moveTo(w.x1, w.y1);
      ctx.lineTo(w.x2, w.y2);
    }
    ctx.stroke();
    ctx.strokeStyle = '#ff8a8a';
    ctx.lineWidth = 2;
    ctx.stroke();

    // ゴール (コネクタ)
    ctx.fillStyle = '#ffd75e';
    ctx.beginPath();
    ctx.arc(goal.x, goal.y, 14, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#0d2b1e';
    ctx.font = 'bold 13px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('GOAL', goal.x, goal.y + 4);

    // 火花
    for (const s of sparks) {
      ctx.fillStyle = 'rgba(255, 220, 80, ' + Math.max(0, s.life / 0.4) + ')';
      ctx.fillRect(s.x - 2, s.y - 2, 4, 4);
    }

    // プローブ
    ctx.fillStyle = state === 'play' && shockCooldown > 0.4 ? '#ff5f5f' : '#7ff0ff';
    ctx.beginPath();
    ctx.arc(probe.x, probe.y, PROBE_R, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // 状態表示
    if (state === 'ready') {
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 18px sans-serif';
      ctx.fillText('⚡ 電脳イライラ棒', W / 2, H / 2 - 40);
      ctx.font = '13px sans-serif';
      ctx.fillText('配線に触れずGOALへ導け', W / 2, H / 2 - 12);
      ctx.fillText('ドラッグ / マウスで操作', W / 2, H / 2 + 8);
      ctx.fillText('画面タップでスタート', W / 2, H / 2 + 34);
    } else if (state === 'over') {
      ctx.fillStyle = 'rgba(0,0,0,0.6)';
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = '#ff8a8a';
      ctx.font = 'bold 22px sans-serif';
      ctx.fillText('ショートした！💥', W / 2, H / 2 - 20);
      ctx.fillStyle = '#fff';
      ctx.font = '15px sans-serif';
      ctx.fillText(Math.floor(scoreM) + ' m 到達', W / 2, H / 2 + 10);
      ctx.fillText('タップでリトライ', W / 2, H / 2 + 36);
    } else if (state === 'clear') {
      ctx.fillStyle = 'rgba(0,0,0,0.55)';
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = '#7ff0ff';
      ctx.font = 'bold 22px sans-serif';
      ctx.fillText('導通成功！✨', W / 2, H / 2 - 20);
      ctx.fillStyle = '#fff';
      ctx.font = '15px sans-serif';
      ctx.fillText(Math.floor(scoreM) + ' pt', W / 2, H / 2 + 10);
      ctx.fillText('タップでもう一周', W / 2, H / 2 + 36);
    }
  }

  /**
   * マウス/タッチイベントを座標ソースに正規化する。
   * タッチイベントの実体は e.touches[0] (move中) / e.changedTouches[0] (end時) で、
   * e.clientX は存在しないため必ずこの関数を経由する。
   * @param {Event} e - マウスまたはタッチイベント
   * @returns {{clientX: number, clientY: number}} 座標を持つオブジェクト
   */
  function pointOf(e) {
    if (e.touches && e.touches.length > 0) {
      return e.touches[0];
    }
    if (e.changedTouches && e.changedTouches.length > 0) {
      return e.changedTouches[0];
    }
    return e;
  }

  function handleInput(type, e) {
    const rect = api.canvas.getBoundingClientRect();
    const sx = api.canvas.width / rect.width;
    const sy = api.canvas.height / rect.height;
    const pt = pointOf(e);
    if (type === 'keydown') {
      if (e.code === 'Space' || e.key === ' ') {
        e.preventDefault();
        if (state !== 'play') startGame();
      }
      return;
    }
    if (type === 'touchstart' || type === 'mousedown') {
      e.preventDefault();
      const cx = (pt.clientX - rect.left) * sx;
      const cy = (pt.clientY - rect.top) * sy;
      if (state !== 'play') {
        startGame();
        // スマホでは「タップで開始 → そのままドラッグ」が自然な操作なので
        // 開始と同時にドラッグ状態へ入る (旧実装は dragging が立たず固まって見えた)
        dragging = true;
        lastPt = { x: cx, y: cy };
        return;
      }
      // プローブはタップ位置へテレポートさせない (即ショート防止)。
      // 基準点だけ更新し、以降の移動でデルタ追従する。
      dragging = true;
      lastPt = { x: cx, y: cy };
      return;
    }
    if (type === 'touchmove' || type === 'mousemove') {
      if (!dragging || state !== 'play') return;
      e.preventDefault();
      const cx = (pt.clientX - rect.left) * sx;
      const cy = (pt.clientY - rect.top) * sy;
      if (lastPt) {
        // 指の移動量 (デルタ) だけプローブを動かす。
        // 絶対座標追従だと画面を触った瞬間にワープ→即ショートになり操作不能。
        probe.x = Math.max(0, Math.min(W, probe.x + (cx - lastPt.x)));
        probe.y = Math.max(0, Math.min(H, probe.y + (cy - lastPt.y)));
      }
      lastPt = { x: cx, y: cy };
      return;
    }
    if (type === 'touchend' || type === 'mouseup') {
      dragging = false;
      lastPt = null;
    }
  }

  function start(a) {
    api = a;
    running = true;
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
    title: '⚡ 電脳イライラ棒',
    start: start,
    stop: stop,
    handleInput: handleInput
  });
})();

