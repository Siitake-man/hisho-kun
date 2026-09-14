/**
 * ネオ秘書くん Desk Pet PWA - キャラクター・モーション・生活サイクルエンジン (pet_motion.js)
 * 
 * 【責務】
 * 1. キャラクター管理 & スプライトプリローダー (CHARACTERS, preloadSprites, _setPetSprite)
 * 2. 生活リズム & 睡眠・行動サイクル (ACTIVITY_SPRITES, updateLifeSprite, updatePetLifeActivity)
 * 3. 大歓喜セレブレーション・エフェクト (triggerCelebrateReaction: CSS物理バウンス・足元シャドウ・パラパラアニメ)
 * 4. 自律歩行コントローラー (WANDER, petWanderTick: 地面ランダム歩行・反転・吹き出し頭上リアルタイム追従)
 * 5. なでなでインタラクション (onPetTap: 弾力バウンス・Haptics・SE・パーティクル・セリフ)
 */

(function () {
  'use strict';

  // =============================================================================
  // 1. キャラクター定義 ＆ スプライト設定
  // =============================================================================
  var CHARACTERS = [
    { id: 'hisho', name: '秘書くん', emoji: '👔' },
    { id: 'kyle', name: 'カイル風精霊', emoji: '🐚' }
  ];

  // 歩行フレーム(walk_1/2)を持つキャラ（未保有キャラは歩行中も idle フレームで代用）
  var WALK_CAPABLE_CHARS = ['kyle'];

  // 現在選択中のキャラクターID
  var currentCharacterId = 'hisho';

  /**
   * スプライト画像プリローダー
   * @param {string} charId - キャラクターID
   */
  function preloadSprites(charId) {
    try {
      var spriteEl = document.getElementById('pet-sprite');
      if (spriteEl) {
        spriteEl.onerror = null;
        spriteEl.src = '/assets/dot/' + charId + '/idle_1.png';
      }
    } catch (e) {
      console.warn('[pet_motion] preloadSprites failed:', e);
    }
  }

  /**
   * スプライト安全差し替え（歩行未保有キャラ等で 404 になった場合は idle へフォールバック）
   * @param {string} name - スプライト名
   */
  function _setPetSprite(name) {
    try {
      var el = document.getElementById('pet-sprite');
      if (!el) return;
      var activeChar = window.currentCharacterId || currentCharacterId;
      var url = '/assets/dot/' + activeChar + '/' + name + '.png';
      if (el.src && el.src.indexOf(url) !== -1) return;
      el.onerror = function () {
        el.onerror = null;
        el.src = '/assets/dot/' + activeChar + '/idle_1.png';
      };
      el.src = url;
    } catch (e) {
      console.warn('[pet_motion] _setPetSprite failed:', e);
    }
  }

  /**
   * キャラクター切り替え（循環）
   */
  function cycleCharacter() {
    try {
      var activeChar = window.currentCharacterId || currentCharacterId;
      var curIdx = CHARACTERS.findIndex(function (c) { return c.id === activeChar; });
      var nextChar = CHARACTERS[(curIdx + 1) % CHARACTERS.length];
      currentCharacterId = nextChar.id;
      window.currentCharacterId = nextChar.id;

      var emojiEl = document.getElementById('char-emoji');
      if (emojiEl) emojiEl.innerText = nextChar.emoji;

      preloadSprites(currentCharacterId);

      // サーバーへも切り替え通知（認証付き）
      if (typeof authFetch === 'function') {
        authFetch('/api/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'switch_character', character_id: currentCharacterId })
        }).catch(function (err) { console.debug('Action failed:', err); });
      }

      if (navigator.vibrate) navigator.vibrate(35);
    } catch (e) {
      console.error('[pet_motion] cycleCharacter failed:', e);
    }
  }

  // =============================================================================
  // 2. 生活イベント ＆ 睡眠リズム
  // =============================================================================
  var ACTIVITY_SPRITES = {
    waking:    ['stretch_1', 'stretch', 'happy', 'idle_1'],
    breakfast: ['tea_1', 'happy', 'idle_1'],
    lunch:     ['happy', 'care_1', 'idle_1'],
    dinner:    ['cheer', 'happy', 'idle_1'],
    bathing:   ['care_1', 'care', 'happy', 'idle_1'],
    working:   ['focus_1', 'focus', 'idle_1'],
    resting:   ['tea_1', 'tea', 'idle_1'],
    reading:   ['reading_1', 'reading', 'focus_1', 'idle_1'],
    sleeping:  ['sleepy_1', 'sleepy', 'idle_1'],
    playing:   ['celebrate_1', 'celebrate', 'cheer', 'idle_1']
  };

  var currentActivity = 'resting';

  /**
   * 生活イベントに応じてペットのスプライトを差し替える。
   * dot/{char}/{name}.png を最優先し、無ければ自キャラの idle_1 で安定させる。
   * @param {string} activity - アクティビティ種別
   */
  function updateLifeSprite(activity) {
    try {
      var spriteEl = document.getElementById('pet-sprite');
      if (!spriteEl) return;
      var candidates = ACTIVITY_SPRITES[activity] || ['idle_1'];
      var activeChar = window.currentCharacterId || currentCharacterId;
      
      var urls = candidates.map(function (name) { return '/assets/dot/' + activeChar + '/' + name + '.png'; });
      urls.push('/assets/dot/' + activeChar + '/idle_1.png');

      var idx = 0;
      spriteEl.onerror = function () {
        idx += 1;
        if (idx < urls.length) {
          spriteEl.src = urls[idx];
        } else {
          spriteEl.onerror = null; // 最終フォールバック
          spriteEl.src = '/assets/dot/' + activeChar + '/idle_1.png';
        }
      };
      spriteEl.src = urls[0];
      spriteEl.style.filter = '';
    } catch (e) {
      console.warn('[pet_motion] updateLifeSprite failed:', e);
    }
  }

  /**
   * 時間帯およびランダム気まぐれ行動によるペットの生活サイクル自動更新
   * @param {string|null} forcedActivity - 強制指定アクティビティ
   */
  function updatePetLifeActivity(forcedActivity) {
    try {
      var now = new Date();
      var hour = now.getHours();
      var min = now.getMinutes();

      var act = 'working';
      var dialog = 'カタカタ…集中してお手伝い中！';

      if (hour >= 23 || hour < 6) {
        act = 'sleeping';
        dialog = 'すやすや…ボス、良い夢を…💤';
      } else if (hour >= 6 && hour < 8) {
        act = 'breakfast';
        dialog = 'おはようございます！朝ごはん美味しいです🍞';
      } else if (hour >= 11 && hour < 13 && min >= 30 || hour === 12) {
        act = 'lunch';
        dialog = 'もぐもぐ…お昼ごはんの時間ですね🍱';
      } else if (hour === 15) {
        act = 'resting';
        dialog = 'ほっと一息、お茶とお菓子タイムです🍵';
      } else if (hour >= 16 && hour < 18) {
        act = 'reading';
        dialog = 'ふむふむ…新しい技術や本を読んで勉強中📖';
      } else if (hour >= 18 && hour < 20) {
        act = 'dinner';
        dialog = '今日もお疲れ様でした！美味しい晩ごはんです🍚';
      } else if (hour >= 20 && hour < 22) {
        act = 'bathing';
        dialog = 'いい湯だな〜♪さっぱりリフレッシュ🛁';
      } else {
        var randomActs = [
          { act: 'working', msg: 'カタカタ…集中してお手伝い中！' },
          { act: 'reading', msg: '仕様書やニュースをチェック中📖' },
          { act: 'resting', msg: '深呼吸してストレッチ〜✨' },
          { act: 'playing', msg: 'ボスと一緒にいられて嬉しいです♪' }
        ];
        var pick = randomActs[Math.floor(Math.random() * randomActs.length)];
        act = pick.act;
        dialog = pick.msg;
      }

      if (forcedActivity) act = forcedActivity;

      currentActivity = act;
      window.currentActivity = act;
      updateLifeSprite(act);

      var bubble = document.getElementById('speech-bubble');
      var petState = window.petStateNow || 'idle';
      if (bubble && (!petState || petState === 'idle')) {
        bubble.innerText = dialog;
      }
    } catch (e) {
      console.warn('[pet_motion] updatePetLifeActivity failed:', e);
    }
  }

  // 45秒ごとに生活リズムを自律更新
  setInterval(function () {
    if (typeof window.currentPomodoro === 'undefined' || !window.currentPomodoro || !window.currentPomodoro.active) {
      updatePetLifeActivity(null);
    }
  }, 45000);

  // =============================================================================
  // 3. 🎉 歓喜ジャンプ＆セレブレーション・エフェクト（Phase H）
  // =============================================================================
  var _celebrateTimer = null;
  var _celebrateFrameInterval = null;

  /**
   * タスク完了や承認時にペットが大歓喜でピョンピョン跳ね、紙吹雪を舞わせる
   * @param {number} durationMs - 歓喜演出持続時間 (ミリ秒)
   */
  function triggerCelebrateReaction(durationMs) {
    if (typeof durationMs !== 'number') durationMs = 3500;
    try {
      var sprite = document.getElementById('pet-sprite');
      var shadow = document.querySelector('.pet-shadow');
      var bubble = document.getElementById('speech-bubble');
      if (!sprite) return;

      // 既存タイマーのクリア
      if (_celebrateTimer) clearTimeout(_celebrateTimer);
      if (_celebrateFrameInterval) clearInterval(_celebrateFrameInterval);

      window.petStateNow = 'celebrate';
      window._celebratingUntil = Date.now() + durationMs;

      // 1. CSSジャンプアニメーション＆足元シャドウ連動の適用
      sprite.classList.remove('squashing');
      void sprite.offsetWidth; // リフロー強制
      sprite.classList.add('celebrating');
      if (shadow) shadow.classList.add('celebrating');

      // 2. スプライトのパラパラアニメ（celebrate_1 ⇄ celebrate_2 ⇄ celebrate_3 ⇄ happy）
      var celebrateFrames = ['celebrate_1', 'celebrate_2', 'celebrate_3', 'happy'];
      var frameIdx = 0;
      _setPetSprite(celebrateFrames[frameIdx]);

      _celebrateFrameInterval = setInterval(function () {
        frameIdx = (frameIdx + 1) % celebrateFrames.length;
        _setPetSprite(celebrateFrames[frameIdx]);
      }, 220);

      // 3. 紙吹雪・お祝いパーティクル大噴射（放物線重力シミュレーション）
      if (typeof spawnCelebrationConfetti === 'function') {
        var wrap = document.querySelector('.pet-img-wrap');
        var rect = wrap ? wrap.getBoundingClientRect() : sprite.getBoundingClientRect();
        var cx = rect.left + rect.width / 2;
        var cy = rect.top + rect.height / 3;
        spawnCelebrationConfetti(cx, cy, 18);
      }

      // 4. 歓喜のセリフ（吹き出しが承認要請等でない場合）
      if (bubble && !bubble.innerText.includes('⚠️') && !bubble.innerText.includes('【要承認】')) {
        var happyQuotes = [
          "わーい！ボス、ありがとうございますっ！🎉✨",
          "やったーー！大成功ですっ！ぴょんぴょん！😆🌟",
          "ボス最高ーー！感激ですっ！🙌💖",
          "タスク完了！ボスのお役に立てて嬉しいですっ！🌸"
        ];
        if (!bubble.innerText.startsWith('🎉')) {
          bubble.innerText = happyQuotes[Math.floor(Math.random() * happyQuotes.length)];
        }
      }

      // 5. 終了後の通常状態への自動復帰
      _celebrateTimer = setTimeout(function () {
        if (_celebrateFrameInterval) clearInterval(_celebrateFrameInterval);
        _celebrateFrameInterval = null;
        _celebrateTimer = null;
        window._celebratingUntil = 0;

        sprite.classList.remove('celebrating');
        if (shadow) shadow.classList.remove('celebrating');

        window.petStateNow = 'idle';
        var act = window.currentActivity || currentActivity;
        if (typeof updateLifeSprite === 'function' && act) {
          updateLifeSprite(act);
        } else {
          _setPetSprite('idle_1');
        }
      }, durationMs);
    } catch (e) {
      console.error('[pet_motion] triggerCelebrateReaction failed:', e);
    }
  }

  // =============================================================================
  // 4. 自律歩行コントローラー（テクテク歩き ＆ フレームアニメ）
  // =============================================================================
  var WANDER = { mode: 'idle', dir: 1, x: 0.5, until: Date.now() + 5000, frame: 0, lastFrameAt: 0, lastTick: 0 };
  var WALK_MIN = 0.18, WALK_MAX = 0.82, WALK_SPEED = 0.045;

  /**
   * 自律歩行ティックハンドラ（120ms間隔）
   */
  function petWanderTick() {
    try {
      if (typeof window.currentPomodoro !== 'undefined' && window.currentPomodoro && window.currentPomodoro.active) return;
      var petState = window.petStateNow || 'idle';
      if (petState && petState !== 'idle') return;
      var wrap = document.querySelector('.pet-img-wrap');
      if (!wrap) return;
      var now = Date.now();
      var dt = Math.min(0.5, (now - (WANDER.lastTick || now)) / 1000);
      WANDER.lastTick = now;
      var activeChar = window.currentCharacterId || currentCharacterId;

      if (WANDER.mode === 'walk') {
        WANDER.x += WANDER.dir * WALK_SPEED * dt;
        if (WANDER.x < WALK_MIN) { WANDER.x = WALK_MIN; WANDER.dir = 1; }
        if (WANDER.x > WALK_MAX) { WANDER.x = WALK_MAX; WANDER.dir = -1; }
        wrap.style.left = (WANDER.x * 100) + '%';
        wrap.style.transform = WANDER.dir < 0 ? 'scaleX(-1)' : 'none';
        if (now - WANDER.lastFrameAt > 160) {
          WANDER.lastFrameAt = now;
          WANDER.frame = 1 - WANDER.frame;
          var hasWalk = WALK_CAPABLE_CHARS.indexOf(activeChar) !== -1;
          _setPetSprite(WANDER.frame ? (hasWalk ? 'walk_1' : 'idle_2') : (hasWalk ? 'walk_2' : 'idle_1'));
        }
        if (now > WANDER.until) {
          WANDER.mode = 'idle';
          WANDER.until = now + 4000 + Math.random() * 6000;
        }
      } else {
        wrap.style.transform = 'none';
        if (now - WANDER.lastFrameAt > 700) {
          WANDER.lastFrameAt = now;
          WANDER.frame = 1 - WANDER.frame;
          _setPetSprite(WANDER.frame ? 'idle_2' : 'idle_1');
        }
        if (now > WANDER.until) {
          WANDER.mode = 'walk';
          WANDER.dir = Math.random() < 0.5 ? -1 : 1;
          WANDER.until = now + 2000 + Math.random() * 2500;
        }
      }
      // 🐾 吹き出しをペットの頭上にリアルタイム追従（画面端のはみ出し防止クランプ付き）
      var bubble = document.getElementById('speech-bubble');
      if (bubble) {
        var bubbleX = Math.max(22, Math.min(78, WANDER.x * 100));
        bubble.style.left = bubbleX + '%';
      }
    } catch (e) {
      console.warn('[pet_motion] petWanderTick failed:', e);
    }
  }

  setInterval(petWanderTick, 120);

  // =============================================================================
  // 5. なでなでインタラクション (Spring & Haptics & Particles & SE)
  // =============================================================================
  /**
   * ペットタップ／クリック時のなでなでリアクション
   * @param {Event} event - タッチまたはクリックイベント
   */
  function onPetTap(event) {
    try {
      if (navigator.vibrate) navigator.vibrate(30);

      var activeChar = window.currentCharacterId || currentCharacterId;
      if (typeof playCharacterSE === 'function') {
        playCharacterSE(activeChar);
      }

      var sprite = document.getElementById('pet-sprite');
      if (sprite) {
        sprite.classList.remove('squashing');
        void sprite.offsetWidth; // リフロー強制
        sprite.classList.add('squashing');
        setTimeout(function () { sprite.classList.remove('squashing'); }, 500);
      }

      var rect = event.currentTarget ? event.currentTarget.getBoundingClientRect() : { left: 0, top: 0, width: 100, height: 100 };
      var clickX = (event.clientX || (event.touches && event.touches[0].clientX)) || (rect.left + rect.width / 2);
      var clickY = (event.clientY || (event.touches && event.touches[0].clientY)) || (rect.top + rect.height / 2);

      if (typeof spawnTouchParticles === 'function') {
        spawnTouchParticles(clickX, clickY, 5);
      }

      var bubble = document.getElementById('speech-bubble');
      if (bubble) {
        var happyReplies = [
          "えへへ〜、くすぐったいです！🥰",
          "ボスになでなでしてもらえて幸せです〜！✨",
          "もちもちパワー全開ですっ！パチパチ👏",
          "今日もボスのお仕事、全力で応援しますね！🔥"
        ];
        bubble.innerText = happyReplies[Math.floor(Math.random() * happyReplies.length)];
      }
    } catch (e) {
      console.warn('[pet_motion] onPetTap failed:', e);
    }
  }

  // =============================================================================
  // 6. グローバル公開 (window & var)
  // =============================================================================
  window.CHARACTERS = CHARACTERS;
  window.WALK_CAPABLE_CHARS = WALK_CAPABLE_CHARS;
  window.currentCharacterId = currentCharacterId;
  window.cycleCharacter = cycleCharacter;
  window.preloadSprites = preloadSprites;
  window._setPetSprite = _setPetSprite;
  window.setPetSprite = _setPetSprite;
  window.ACTIVITY_SPRITES = ACTIVITY_SPRITES;
  window.currentActivity = currentActivity;
  window.updateLifeSprite = updateLifeSprite;
  window.updatePetLifeActivity = updatePetLifeActivity;
  window.triggerCelebrateReaction = triggerCelebrateReaction;
  window.WANDER = WANDER;
  window.petWanderTick = petWanderTick;
  window.onPetTap = onPetTap;

})();

// 非モジュール環境での直接参照用トップレベル宣言
var CHARACTERS = window.CHARACTERS;
var WALK_CAPABLE_CHARS = window.WALK_CAPABLE_CHARS;
var currentCharacterId = window.currentCharacterId;
var cycleCharacter = window.cycleCharacter;
var preloadSprites = window.preloadSprites;
var _setPetSprite = window._setPetSprite;
var setPetSprite = window.setPetSprite;
var ACTIVITY_SPRITES = window.ACTIVITY_SPRITES;
var currentActivity = window.currentActivity;
var updateLifeSprite = window.updateLifeSprite;
var updatePetLifeActivity = window.updatePetLifeActivity;
var triggerCelebrateReaction = window.triggerCelebrateReaction;
var WANDER = window.WANDER;
var petWanderTick = window.petWanderTick;
var onPetTap = window.onPetTap;
