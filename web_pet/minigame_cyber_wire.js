/**
 * ネオ秘書くん ミニゲーム「⚡ 電脳イライラ棒」 (minigame_cyber_wire.js)
 *
 * ファミコン風 無限生成コース: 蛇行する配線コースが右から左へ流れ続けるので、
 * 指ドラッグ (デルタ追従) でプローブをコース内に留め続ける。
 * 壁接触で火花エフェクト + バチッ音で即終了、進行距離 (m) がスコア。
 */
(function () {
  'use strict';

  const GAME_ID = 'cyber_wire';
  const W = 320;
  const H = 420;
  const PROBE_R = 7;
  const SEG = 32;      // コース中心線の制御点間隔 (px)
  const PAD = 48;      // 上下の安全マージン (壁が侵入しない領域)
  const LEAD = 96;     // カメラ前方の生成バッファ (px)
  const TRAIL = 128;   // カメラ後方の保持バッファ (px)
  const BASE_HALF = 34; // コース初期半幅

  let api = null;
  let running = false;
  let rafId = null;
  let lastTime = 0;

  let pts = [];        // コース中心線の制御点 {x, y} (ワールド座標)
  let halfs = [];      // 各制御点でのコース半幅
  let cameraX = 0;
  let scrollSpeed = 70;
  let probe = { x: 90, y: H / 2 };
  let dragging = false;
  let lastPt = null; // ドラッグ基準点 (デルタ追従用)
  let scoreM = 0;
  let best = 0;
  let state = 'ready'; // ready | play | over
  let sparks = []; // {x, y, vx, vy, life}
  let shockCooldown = 0;
  let milestoneM = 0; // 進行加算音用の区切り

  /**
   * コース中心線の制御点を1つ生成する。
   * ランダムウォーク (傾き制限つき) で蛇行させ、直線区間も混ぜる。
   * @param {{x: number, y: number}} prev - 直前の制御点
   * @param {number} index - 制御点の通し番号 (直線区間の配置に使用)
   * @returns {{x: number, y: number, half: number}} 新しい制御点
   */
  function makePoint(prev, index) {
    const half = Math.max(23, BASE_HALF - scoreM * 0.05);
    let y;
    if (index < 4 || (index % 9 === 0)) {
      // 導入部と9ポイントごとに直線 (休憩区間)
      y = prev.y;
    } else {
      const maxStep = 34 + scoreM * 0.08;
      const step = (Math.random() * 2 - 1) * maxStep;
      const lo = PAD + half;
      const hi = H - PAD - half;
      y = Math.max(lo, Math.min(hi, prev.y + step));
      // 傾き制限: 前点から大幅に離れすぎないよう丸める
      y = prev.y + Math.max(-52, Math.min(52, y - prev.y));
    }
    return { x: prev.x + SEG, y: y, half: half };
  }

  /**
   * コース制御点をカメラ前方まで補充する。
   * @returns {void}
   */
  function ensureCourse() {
    while (pts[pts.length - 1].x < cameraX + W + LEAD) {
      const np = makePoint(pts[pts.length - 1], pts.length);
      pts.push({ x: np.x, y: np.y });
      halfs.push(np.half);
    }
    while (pts.length > 2 && pts[1].x < cameraX - TRAIL) {
      pts.shift();
      halfs.shift();
    }
  }

  /**
   * ワールド座標 x におけるコース中心Yを補間する。
   * @param {number} wx - ワールドX座標
   * @returns {number} 中心Y
   */
  function centerYAt(wx) {
    let i = 0;
    while (i < pts.length - 2 && pts[i + 1].x < wx) i++;
    const p0 = pts[i];
    const p1 = pts[i + 1];
    const t = Math.max(0, Math.min(1, (wx - p0.x) / (p1.x - p0.x)));
    const s = (1 - Math.cos(t * Math.PI)) / 2; // コサイン補間で滑らかに
    return p0.y + (p1.y - p0.y) * s;
  }

  /**
   * ワールド座標 x におけるコース半幅を補間する。
   * @param {number} wx - ワールドX座標
   * @returns {number} 半幅
   */
  function halfAt(wx) {
    let i = 0;
    while (i < halfs.length - 2 && pts[i + 1].x < wx) i++;
    const p0 = pts[i];
    const p1 = pts[i + 1];
    const t = Math.max(0, Math.min(1, (wx - p0.x) / (p1.x - p0.x)));
    return halfs[i] + (halfs[i + 1] - halfs[i]) * t;
  }

  /**
   * プローブが壁に接触しているか判定する。
   * @returns {boolean} 接触していれば true
   */
  function hitsWall() {
    const wx = cameraX + probe.x;
    const cy = centerYAt(wx);
    const hw = halfAt(wx);
    return Math.abs(probe.y - cy) > hw - PROBE_R;
  }

  /**
   * ゲーム状態を初期化して開始する。
   * @returns {void}
   */
  function startGame() {
    cameraX = 0;
    scrollSpeed = 70;
    scoreM = 0;
    milestoneM = 0;
    sparks = [];
    pts = [{ x: -SEG, y: H / 2 }];
    halfs = [BASE_HALF];
    ensureCourse();
    probe.x = 90;
    probe.y = centerYAt(cameraX + probe.x);
    state = 'play';
    api.setScore(0);
    api.beep(660, 0.08, 0.06);
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
    // 火花エフェクト更新 (over中も燃え続ける)
    for (let i = sparks.length - 1; i >= 0; i--) {
      const s = sparks[i];
      s.x += s.vx * dt;
      s.y += s.vy * dt;
      s.vy += 300 * dt;
      s.life -= dt;
      if (s.life <= 0) sparks.splice(i, 1);
    }
    if (state !== 'play') return;

    // コースが右から左へ流れ続ける (距離が伸びるほど加速)
    scrollSpeed = Math.min(165, 70 + scoreM * 0.9);
    cameraX += scrollSpeed * dt;
    ensureCourse();

    // 進行距離 (10px = 1m) をスコア化
    scoreM = cameraX / 10;
    api.setScore(Math.floor(scoreM));
    if (scoreM >= milestoneM + 50) {
      milestoneM = Math.floor(scoreM / 50) * 50;
      api.beep(1200, 0.08, 0.07); // 50m到達ごとの合図音
    }

    // 壁接触判定 (ファミコン仕様: 触れた瞬間にショート → 即終了)
    if (hitsWall()) {
      for (let i = 0; i < 14; i++) {
        sparks.push({
          x: probe.x,
          y: probe.y,
          vx: (Math.random() - 0.5) * 220,
          vy: (Math.random() - 0.5) * 220 - 60,
          life: 0.35 + Math.random() * 0.25
        });
      }
      gameOver();
    }
  }

  /**
   * 折れ線パスを現在の線設定でストロークする。
   * @param {Array<{x: number, y: number}>} edge - 折れ線の頂点列
   * @param {CanvasRenderingContext2D} ctx - 描画コンテキスト
   * @returns {void}
   */
  function strokeEdge(edge, ctx) {
    ctx.beginPath();
    ctx.moveTo(edge[0].x, edge[0].y);
    for (let i = 1; i < edge.length; i++) {
      ctx.lineTo(edge[i].x, edge[i].y);
    }
    ctx.stroke();
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

    // コース上端・下端の折れ線をサンプリング
    const topEdge = [];
    const botEdge = [];
    for (let sx = -6; sx <= W + 6; sx += 6) {
      const wx = cameraX + sx;
      const cy = centerYAt(wx);
      const hw = halfAt(wx);
      topEdge.push({ x: sx, y: cy - hw });
      botEdge.push({ x: sx, y: cy + hw });
    }

    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    // 壁バンド (通路の外側を暗色で塗る)
    ctx.fillStyle = '#38101d';
    ctx.beginPath();
    ctx.moveTo(-6, -10);
    for (const p of topEdge) ctx.lineTo(p.x, p.y);
    ctx.lineTo(W + 6, -10);
    ctx.closePath();
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(-6, H + 10);
    for (const p of botEdge) ctx.lineTo(p.x, p.y);
    ctx.lineTo(W + 6, H + 10);
    ctx.closePath();
    ctx.fill();

    // 配線の縁 (ネオンピンク + 発光)
    ctx.shadowColor = 'rgba(255, 90, 110, 0.75)';
    ctx.shadowBlur = 7;
    ctx.strokeStyle = '#e05555';
    ctx.lineWidth = 6;
    strokeEdge(topEdge, ctx);
    strokeEdge(botEdge, ctx);
    ctx.strokeStyle = '#ff8a8a';
    ctx.lineWidth = 2;
    strokeEdge(topEdge, ctx);
    strokeEdge(botEdge, ctx);
    ctx.shadowBlur = 0;

    // 火花
    for (const s of sparks) {
      ctx.fillStyle = 'rgba(255, 220, 80, ' + Math.max(0, s.life / 0.5) + ')';
      ctx.fillRect(s.x - 2, s.y - 2, 4, 4);
    }

    // プローブ
    ctx.fillStyle = '#7ff0ff';
    ctx.shadowColor = 'rgba(127, 240, 255, 0.9)';
    ctx.shadowBlur = 8;
    ctx.beginPath();
    ctx.arc(probe.x, probe.y, PROBE_R, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // 状態表示
    ctx.textAlign = 'center';
    if (state === 'ready') {
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 18px sans-serif';
      ctx.fillText('⚡ 電脳イライラ棒', W / 2, H / 2 - 40);
      ctx.font = '13px sans-serif';
      ctx.fillText('流れてくる配線コースに触れずに進め！', W / 2, H / 2 - 12);
      ctx.fillText('タップしたままドラッグで追従', W / 2, H / 2 + 8);
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
    // ready画面でもコースを描画できるよう初期生成しておく
    cameraX = 0;
    scrollSpeed = 70;
    scoreM = 0;
    milestoneM = 0;
    sparks = [];
    pts = [{ x: -SEG, y: H / 2 }];
    halfs = [BASE_HALF];
    ensureCourse();
    probe.x = 90;
    probe.y = centerYAt(cameraX + probe.x);
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

