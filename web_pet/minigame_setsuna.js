/**
 * ネオ秘書くん ミニゲーム「刹那の見斬り」 (minigame_setsuna.js)
 *
 * SFC風 反射神経勝負: 秘書くんと敵が対峙し、「！！」が出た瞬間に
 * 最速タップ (Space) する。5ラウンドの合計反応速度をスコア化する。
 * フライング (合図前のタップ) はそのラウンド0点。
 */
(function () {
  'use strict';

  const GAME_ID = 'setsuna';
  const GAME_TITLE = '⚔️ 刹那の見斬り';
  const W = 320;
  const H = 420;
  const TOTAL_ROUNDS = 5;
  const PENALTY_MS = 400; // この値以上は0点 (フライング含む)
  const BASE_MS = 120;    // 満点換算の基準速度

  let api = null;
  let state = 'ready'; // ready | standup | signal | result | done
  let round = 0;
  let score = 0;
  let signalTimer = 0;
  let signalDelay = 0;
  let reactionMs = 0;
  let flashAlpha = 0;
  let lastReactionText = '';
  let resultTimer = 0; // result状態の表示秒数カウンタ

  /** スコア換算: 速いほど高得点 (BASE_MS=300点, PENALTY_MS以上は0点)。 */
  function scoreFor(ms) {
    if (ms <= 0 || ms >= PENALTY_MS) return 0;
    return Math.max(0, Math.round(300 * (PENALTY_MS - ms) / (PENALTY_MS - BASE_MS)));
  }

  /**
   * ラウンドを開始する。
   */
  function beginRound() {
    state = 'standup';
    round += 1;
    reactionMs = 0;
    signalTimer = 0;
    lastReactionText = '';
    // 1.2〜3.5秒のランダム遅延後に「！！」を出す (暗記防止)
    signalDelay = 1.2 + Math.random() * 2.3;
  }

  /**
   * ゲームを初期化して開始する。
   * @param {Object} arcadeApi - arcade共通API
   */
  function start(arcadeApi) {
    api = arcadeApi;
    state = 'ready';
    round = 0;
    score = 0;
    signalTimer = 0;
    reactionMs = 0;
    lastReactionText = '';
    api.setScore(0);
    api.fetchHigh(GAME_ID).then((h) => api.setHigh(h));
  }

  /**
   * ゲームを停止する (タイマーはarcadeループ駆動のため状態リセットのみ)。
   */
  function stop() {
    api = null;
    state = 'ready';
  }


  /**
   * フレーム更新。
   * @param {number} dt - 前フレームからの経過秒
   */
  function update(dt) {
    if (!api) return;
    if (state === 'standup') {
      signalTimer += dt;
      if (signalTimer >= signalDelay) {
        state = 'signal';
        signalTimer = 0;
        api.beep(1760, 0.12, 0.1);
      }
    } else if (state === 'signal') {
      signalTimer += dt;
    } else if (state === 'result') {
      resultTimer += dt;
      if (resultTimer >= 0.9) {
        beginRound(); // 0.9秒表示後に次ラウンドへ
      }
    }
    if (flashAlpha > 0) {
      flashAlpha = Math.max(0, flashAlpha - dt * 3);
    }
  }

  /**
   * 入力処理 (タップ / Space)。
   * @param {string} type - イベント種別
   * @param {Event} e - イベント
   */
  function handleInput(type, e) {
    if (!api) return;
    const isTap = type === 'touchstart' || type === 'mousedown';
    const isSpace = type === 'keydown' && (e.key === ' ' || e.code === 'Space');
    if (!isTap && !isSpace) return;
    if (isSpace) e.preventDefault();

    if (state === 'ready') {
      beginRound();
      api.beep(660, 0.08, 0.06);
    } else if (state === 'standup') {
      // フライング: そのラウンドは0点
      reactionMs = PENALTY_MS;
      lastReactionText = 'フライング！';
      api.beep(180, 0.25, 0.1, 'sawtooth');
      finishRound();
    } else if (state === 'signal') {
      reactionMs = Math.round(signalTimer * 1000);
      lastReactionText = reactionMs + 'ms';
      api.beep(990, 0.08, 0.08);
      finishRound();
    } else if (state === 'done') {
      state = 'ready';
      round = 0;
      score = 0;
      api.setScore(0);
    }
  }

  /**
   * ラウンド結果を確定して次へ進む (全ラウンド終了でスコア送信)。
   */
  function finishRound() {
    flashAlpha = 1;
    score += scoreFor(reactionMs);
    api.setScore(score);
    if (round >= TOTAL_ROUNDS) {
      state = 'done';
      api.submitScore(GAME_ID, score).then((h) => {
        if (h !== null) api.setHigh(h);
      });
    } else {
      // 結果を0.9秒表示してから次ラウンドへ (update側でbeginRound)
      state = 'result';
      resultTimer = 0;
    }
  }

  /**
   * 描画。
   * @param {CanvasRenderingContext2D} ctx - 描画コンテキスト
   */
  function draw(ctx) {
    // 背景 (対峙の土俵)
    ctx.fillStyle = '#191d2e';
    ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    ctx.lineWidth = 1;
    for (let gy = 60; gy < H; gy += 40) {
      ctx.beginPath();
      ctx.moveTo(0, gy);
      ctx.lineTo(W, gy);
      ctx.stroke();
    }

    // 秘書くん (左) と敵 (右)
    const duelY = 190;
    ctx.font = '40px serif';
    ctx.textAlign = 'center';
    ctx.fillText('🤖', 70, duelY);
    ctx.fillText('🥷', W - 70, duelY);

    if (state === 'ready') {
      ctx.fillStyle = 'rgba(0,0,0,0.55)';
      ctx.fillRect(0, 60, W, H - 60);
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 20px sans-serif';
      ctx.fillText('刹那の見斬り', W / 2, 150);
      ctx.font = '13px sans-serif';
      ctx.fillText('「！！」が出た瞬間に画面をタップ！', W / 2, 185);
      ctx.fillText('(Spaceキーでも可)', W / 2, 210);
      if (round === 0) {
        ctx.fillStyle = '#7fd4ff';
        ctx.font = 'bold 16px sans-serif';
        ctx.fillText('タップして開始', W / 2, 260);
      }
    } else if (state === 'standup') {
      ctx.fillStyle = '#c8d3e8';
      ctx.font = 'bold 22px sans-serif';
      ctx.fillText('Round ' + round + ' / ' + TOTAL_ROUNDS, W / 2, 100);
      ctx.font = '16px sans-serif';
      ctx.fillText('構えて…', W / 2, 300);
    } else if (state === 'signal') {
      ctx.fillStyle = '#ffd54a';
      ctx.font = 'bold 56px sans-serif';
      ctx.fillText('！！', W / 2, 160);
      ctx.fillStyle = '#ffffff';
      ctx.font = '14px sans-serif';
      ctx.fillText('今だ！', W / 2, 300);
    } else if (state === 'result') {
      ctx.fillStyle = '#8ef2a2';
      ctx.font = 'bold 26px sans-serif';
      ctx.fillText(lastReactionText || '…', W / 2, 160);
    } else if (state === 'done') {
      ctx.fillStyle = 'rgba(0,0,0,0.6)';
      ctx.fillRect(0, 60, W, H - 60);
      ctx.fillStyle = '#ffd54a';
      ctx.font = 'bold 24px sans-serif';
      ctx.fillText('合計スコア ' + score, W / 2, 150);
      ctx.fillStyle = '#ffffff';
      ctx.font = '14px sans-serif';
      ctx.fillText('タップでもう一度挑戦', W / 2, 200);
    }

    if (flashAlpha > 0) {
      ctx.fillStyle = 'rgba(255,255,255,' + (flashAlpha * 0.5).toFixed(3) + ')';
      ctx.fillRect(0, 0, W, H);
    }
  }

  // arcade へカートリッジ登録 (usesArrowKeys=false: ←/→ は切替に使用)
  if (window.MinigameArcade) {
    window.MinigameArcade.register({
      id: GAME_ID,
      title: GAME_TITLE,
      usesArrowKeys: false,
      start: start,
      stop: stop,
      handleInput: handleInput,
      update: update,
      draw: draw
    });
  }
})();
