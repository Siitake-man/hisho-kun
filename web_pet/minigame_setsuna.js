/**
 * ネオ秘書くん ミニゲーム「⚔️ 刹那の見斬り」 (minigame_setsuna.js)
 *
 * SFC風 反射神経勝負: 秘書くんと敵が対峙し、「！！」が出た瞬間に
 * 最速タップ (または Space)。5ラウンドの合計反応速度を競う。
 * フライングはそのラウンド 0 点。合計スコアが高ほど鋭い。
 */
(function () {
  'use strict';

  const GAME_ID = 'setsuna';
  const W = 320;
  const H = 420;
  const ROUNDS = 5;
  const SLOW_MS = 400; // これ以上遅いと 0 点

  let api = null;
  let running = false;
  let rafId = null;
  let lastTime = 0;

  let state = 'ready'; // ready | wait | go | result | done
  let round = 0;
  let scores = []; // 各ラウンドの加点
  let reactionMs = 0;
  let signalAt = 0;
  let waitTimer = 0;
  let flashAlpha = 0;
  let best = 0;
  let fakeout = false; // ダミー合図 (「…」) 中か

  function startGame() {
    round = 0;
    scores = [];
    state = 'wait';
    waitTimer = 0.8 + Math.random() * 1.6;
    fakeout = false;
    api.setScore(0);
  }

  function totalScore() {
    return scores.reduce((a, b) => a + b, 0);
  }

  function finish() {
    state = 'done';
    const total = totalScore();
    api.setScore(total);
    api.beep(660, 0.15, 0.1);
    api.submitScore(GAME_ID, total).then((hi) => {
      if (hi !== null) best = Math.max(best, hi);
      api.setHigh(best);
    });
  }

  /**
   * プレイヤーの斬撃入力を処理する。
   */
  function strike() {
    if (state === 'ready' || state === 'done') {
      startGame();
      return;
    }
    if (state === 'wait') {
      // フライング
      scores.push(0);
      flashAlpha = 0.5;
      api.beep(60, 0.3, 0.12, 'sawtooth');
      nextRoundOrFinish();
      return;
    }
    if (state === 'go') {
      reactionMs = (performance.now() - signalAt);
      const pts = reactionMs >= SLOW_MS ? 0 : Math.max(1, Math.round((SLOW_MS - reactionMs) / 4));
      scores.push(pts);
      flashAlpha = 1;
      api.beep(reactionMs < 200 ? 1200 : 900, 0.1, 0.1);
      nextRoundOrFinish();
    }
  }

  function nextRoundOrFinish() {
    round += 1;
    if (round >= ROUNDS) {
      finish();
      return;
    }
    state = 'wait';
    waitTimer = 0.8 + Math.random() * 1.8;
    fakeout = Math.random() < 0.3; // 30% でダミー合図を混ぜる
  }

  function update(dt) {
    flashAlpha = Math.max(0, flashAlpha - dt * 2);
    if (state !== 'wait') return;
    waitTimer -= dt;
    if (waitTimer <= 0) {
      if (fakeout) {
        // ダミー: 少し遅れて本番へ
        fakeout = false;
        waitTimer = 0.25 + Math.random() * 0.4;
        api.beep(500, 0.05, 0.04);
        return;
      }
      state = 'go';
      signalAt = performance.now();
      api.beep(1400, 0.08, 0.1);
    }
  }


  function draw() {
    const ctx = api.ctx;
    // 背景 (夕暮れの対峙)
    const grad = ctx.createLinearGradient(0, 0, 0, H);
    grad.addColorStop(0, '#2b1a3a');
    grad.addColorStop(1, '#5c2e3e');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = 'rgba(255, 200, 120, 0.25)';
    ctx.beginPath();
    ctx.arc(W / 2, 140, 46, 0, Math.PI * 2);
    ctx.fill();
    // 地面
    ctx.fillStyle = '#241420';
    ctx.fillRect(0, 330, W, H - 330);

    // 秘書くん (左) と敵 (右)
    ctx.font = '34px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('🐦', 80, 322);
    ctx.fillText('🥷', 240, 322);
    // 刀を構える線
    ctx.strokeStyle = state === 'go' ? '#ffe66e' : '#c9b8d4';
    ctx.lineWidth = state === 'go' ? 3 : 2;
    ctx.beginPath();
    ctx.moveTo(96, 300);
    ctx.lineTo(224, 300);
    ctx.stroke();

    // 中央メッセージ
    if (state === 'go') {
      ctx.fillStyle = '#ffe66e';
      ctx.font = 'bold 52px sans-serif';
      ctx.fillText('！！', W / 2, 170);
    } else if (state === 'wait' && fakeout) {
      ctx.fillStyle = 'rgba(255,255,255,0.75)';
      ctx.font = 'bold 30px sans-serif';
      ctx.fillText('…', W / 2, 170);
    }

    // ラウンド表示
    ctx.fillStyle = '#fff';
    ctx.font = '13px sans-serif';
    ctx.fillText('Round ' + Math.min(round + 1, ROUNDS) + ' / ' + ROUNDS, W / 2, 372);

    if (state === 'ready') {
      ctx.fillStyle = 'rgba(0,0,0,0.55)';

      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = '#ffe66e';
      ctx.font = 'bold 20px sans-serif';
      ctx.fillText('⚔️ 刹那の見斬り', W / 2, H / 2 - 46);
      ctx.fillStyle = '#fff';
      ctx.font = '13px sans-serif';
      ctx.fillText('「！！」が出たら最速タップ！', W / 2, H / 2 - 16);
      ctx.fillText('フライング厳禁・5回戦勝負', W / 2, H / 2 + 6);
      ctx.fillText('タップまたは Space で開始', W / 2, H / 2 + 32);
    } else if (state === 'done') {
      ctx.fillStyle = 'rgba(0,0,0,0.6)';
      ctx.fillRect(0, 0, W, H);
      const total = totalScore();
      ctx.fillStyle = '#ffe66e';
      ctx.font = 'bold 24px sans-serif';
      ctx.fillText('見事！', W / 2, H / 2 - 40);
      ctx.fillStyle = '#fff';
      ctx.font = '14px sans-serif';
      scores.forEach((s, i) => {
        ctx.fillText((i + 1) + '戦目: ' + s + ' pt', W / 2, H / 2 - 8 + i * 18);
      });
      ctx.fillText('合計 ' + total + ' pt', W / 2, H / 2 + 108);
      ctx.fillText('タップで再戦', W / 2, H - 20);
    }

    // 斬撃フラッシュ
    if (flashAlpha > 0) {
      ctx.fillStyle = 'rgba(255,255,255,' + flashAlpha * 0.5 + ')';
      ctx.fillRect(0, 0, W, H);
    }
  }

  function handleInput(type, e) {
    if (type === 'keydown') {
      if (e.code === 'Space' || e.key === ' ') {
        e.preventDefault();
        if (!e.repeat) strike();
      }
      return;
    }
    if (type === 'touchstart' || type === 'mousedown') {
      e.preventDefault();
      strike();
    }
  }

  function start(a) {
    api = a;
    running = true;
    state = 'ready';
    round = 0;
    scores = [];
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
    title: '⚔️ 刹那の見斬り',
    start: start,
    stop: stop,
    handleInput: handleInput
  });
})();
