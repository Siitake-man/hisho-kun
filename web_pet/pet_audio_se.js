/**
 * ネオ秘書くん Web Audio SE 再生エンジン (pet_audio_se.js)
 *
 * 【役割】
 * - Web Audio API による完全ローカル・低遅延シンセサイザー効果音の生成・再生
 * - モバイルブラウザの User Gesture Policy (自動再生制限) 解錠ハンドラ
 * - 通知アラートチャイム、判定音（承認/却下）、キャラクター固有SE
 *
 * 【アーキテクチャ】
 * - 外部依存ゼロ（Vanilla JS）
 * - シングルトン AudioContext の遅延初期化 ＆ 復帰自己治癒
 * - 非モジュール/モジュール双方に対応するグローバル公開
 */

(function() {
  'use strict';

  let audioCtx = null;
  let chimeTimers = [];

  /**
   * AudioContextの取得（シングルトン・遅延生成）
   * @returns {AudioContext|null} オーディオコンテキスト
   */
  function getAudioContext() {
    try {
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
    } catch (e) {
      console.debug('[PetAudioSE] AudioContext error:', e);
      return null;
    }
  }

  /**
   * 最初のユーザー操作で AudioContext を解錠する（モバイル自動再生制限の解除）
   */
  function unlockAudio() {
    try {
      const ctx = getAudioContext();
      if (ctx && ctx.state === 'suspended') {
        ctx.resume().catch(() => {});
      }
    } catch (e) {
      console.debug('[PetAudioSE] Audio unlock error:', e);
    }
  }

  // 🛡️ モバイル自動再生制限（User Gesture Policy）の解錠リスナー
  // passive: true を指定してスクロール・タッチのパフォーマンス低下を防止
  document.addEventListener('pointerdown', unlockAudio, { passive: true });
  document.addEventListener('touchstart', unlockAudio, { passive: true });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) unlockAudio();
  });

  /**
   * 2音チャイム（ピンポン）を合成する
   * @param {AudioContext} ctx
   * @param {number} freqLow 低音周波数 (Hz)
   * @param {number} freqHigh 高音周波数 (Hz)
   */
  function playTwoTone(ctx, freqLow, freqHigh) {
    if (!ctx) return;
    try {
      const now = ctx.currentTime;
      [[freqLow, 0.0], [freqHigh, 0.22]].forEach(([freq, offset]) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'triangle';
        osc.frequency.value = freq;
        osc.connect(gain);
        gain.connect(ctx.destination);
        gain.gain.setValueAtTime(0.0001, now + offset);
        gain.gain.exponentialRampToValueAtTime(0.4, now + offset + 0.03);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + offset + 0.55);
        osc.start(now + offset);
        osc.stop(now + offset + 0.6);
      });
    } catch (e) {
      console.debug('[PetAudioSE] playTwoTone error:', e);
    }
  }

  /**
   * 通知アラート: チャイム連打 ＆ 振動パターン（前回分タイマーを必ず解除してから鳴らす）
   * @param {number} repeat 繰り返し回数（デフォルト 3回）
   */
  function playAlertChime(repeat = 3) {
    stopAlertChime();
    unlockAudio();
    try {
      const ctx = getAudioContext();
      if (ctx) {
        for (let i = 0; i < repeat; i++) {
          chimeTimers.push(setTimeout(() => {
            try {
              playTwoTone(ctx, 880, 1245);
            } catch (e) {
              console.debug('[PetAudioSE] Chime repeat error:', e);
            }
          }, i * 950));
        }
      }
    } catch (e) {
      console.debug('[PetAudioSE] playAlertChime error:', e);
    }
    if (navigator.vibrate) {
      try {
        navigator.vibrate([220, 120, 220, 120, 320]);
      } catch (e) {
        // Haptics 非対応環境を安全に無視
      }
    }
  }

  /**
   * 通知チャイムの停止（承認済み・タイムアウト時）
   */
  function stopAlertChime() {
    chimeTimers.forEach(t => clearTimeout(t));
    chimeTimers = [];
  }

  /**
   * 承認/却下の結果を音で区別する（承認=上昇2音・却下=下降2音）
   * @param {boolean} approved 承認時 true, 却下時 false
   */
  function playDecisionSound(approved) {
    try {
      const ctx = getAudioContext();
      if (ctx) {
        if (approved) {
          playTwoTone(ctx, 880, 1245);
        } else {
          playTwoTone(ctx, 660, 440);
        }
      }
    } catch (e) {
      console.debug('[PetAudioSE] playDecisionSound error:', e);
    }
  }

  /**
   * キャラクター固有のSE再生（タップ・なでなで時）
   * @param {string} charId キャラクター識別子 ('hisho' | 'kinoko' | 'seal' | 'wombat' | 'kyle')
   */
  function playCharacterSE(charId) {
    try {
      const validChars = ['hisho', 'kinoko', 'seal', 'wombat', 'kyle'];
      const targetChar = validChars.includes(charId) ? charId : 'hisho';

      const ctx = getAudioContext();
      if (!ctx) return;
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.connect(gain);
      gain.connect(ctx.destination);

      if (targetChar === 'hisho') {
        // 👔 秘書くん: シャキーン！高音サイン波
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, now);
        osc.frequency.exponentialRampToValueAtTime(1320, now + 0.12);
        gain.gain.setValueAtTime(0.2, now);
        gain.gain.exponentialRampToValueAtTime(0.01, now + 0.18);
        osc.start(now);
        osc.stop(now + 0.18);
      } else if (targetChar === 'kinoko') {
        // 🍄 キノコ君: ポフッ！ピッチベンド
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(520, now);
        osc.frequency.exponentialRampToValueAtTime(260, now + 0.15);
        gain.gain.setValueAtTime(0.25, now);
        gain.gain.exponentialRampToValueAtTime(0.01, now + 0.15);
        osc.start(now);
        osc.stop(now + 0.15);
      } else if (targetChar === 'seal') {
        // 🦭 アザラシ: モチッ！キュートな和音ピチピチ
        osc.type = 'sine';
        osc.frequency.setValueAtTime(660, now);
        osc.frequency.exponentialRampToValueAtTime(990, now + 0.1);
        gain.gain.setValueAtTime(0.22, now);
        gain.gain.exponentialRampToValueAtTime(0.01, now + 0.14);
        osc.start(now);
        osc.stop(now + 0.14);
      } else if (targetChar === 'wombat') {
        // 🦫 ウォンバット: ズシッ！低音ずっしり
        osc.type = 'square';
        osc.frequency.setValueAtTime(180, now);
        osc.frequency.exponentialRampToValueAtTime(90, now + 0.18);
        gain.gain.setValueAtTime(0.18, now);
        gain.gain.exponentialRampToValueAtTime(0.01, now + 0.18);
        osc.start(now);
        osc.stop(now + 0.18);
      } else if (targetChar === 'kyle') {
        // 🐚 カイル風精霊: カタッ！ピピッ！貝型PCを叩く8bit風2連音
        osc.type = 'square';
        osc.frequency.setValueAtTime(520, now);
        osc.frequency.setValueAtTime(780, now + 0.07);
        gain.gain.setValueAtTime(0.12, now);
        gain.gain.setValueAtTime(0.12, now + 0.07);
        gain.gain.exponentialRampToValueAtTime(0.01, now + 0.16);
        osc.start(now);
        osc.stop(now + 0.16);
      }
    } catch (e) {
      console.debug('[PetAudioSE] playCharacterSE error:', e);
    }
  }

  // グローバル公開 (window オブジェクトおよび標準グローバルスコープ)
  window.getAudioContext = getAudioContext;
  window.unlockAudio = unlockAudio;
  window.playTwoTone = playTwoTone;
  window.playAlertChime = playAlertChime;
  window.stopAlertChime = stopAlertChime;
  window.playDecisionSound = playDecisionSound;
  window.playCharacterSE = playCharacterSE;
})();

// 非モジュール環境での直接呼び出し互換用トップレベルバインド
var getAudioContext = window.getAudioContext;
var unlockAudio = window.unlockAudio;
var playTwoTone = window.playTwoTone;
var playAlertChime = window.playAlertChime;
var stopAlertChime = window.stopAlertChime;
var playDecisionSound = window.playDecisionSound;
var playCharacterSE = window.playCharacterSE;
