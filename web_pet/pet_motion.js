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
    { id: 'hisho', name: '秘書くん', emoji: '👔', mode: 'classic' },
    { id: 'kyle', name: 'カイル風精霊', emoji: '🐚', mode: 'classic' },
    { id: 'hisho_hd2d', name: '秘書くん (HD-2D)', emoji: '✨👔', mode: 'hd2d' }
  ];

  // 歩行フレーム(walk_1/2)を持つキャラ（未保有キャラは歩行中も idle フレームで代用）
  var WALK_CAPABLE_CHARS = ['kyle'];

  // 現在選択中のキャラクターID
  var currentCharacterId = 'hisho';

  /**
   * キャラクターIDからベースキャラクター (hisho または kyle) を解決
   * @param {string} charId
   * @returns {string} 'hisho' | 'kyle'
   */
  function getBaseCharacter(charId) {
    if (!charId) return 'hisho';
    if (charId === 'hisho_hd2d') return 'hisho';
    return charId.replace('_hd2d', '');
  }

  /**
   * HD-2D スキンに応じた .pet-stage のクラス同期
   * @param {string} charId
   */
  function _syncStageHd2dClasses(charId) {
    try {
      var stage = document.querySelector('.pet-stage');
      if (!stage) return;
      var isHd2d = charId && charId.indexOf('_hd2d') !== -1;
      if (isHd2d) {
        stage.classList.add('is-hd2d');
        stage.classList.add('char-hisho_hd2d');
      } else {
        stage.classList.remove('is-hd2d', 'char-hisho_hd2d');
      }
    } catch (e) {
      console.warn('[pet_motion] _syncStageHd2dClasses failed:', e);
    }
  }

  /**
   * スプライト画像プリローダー
   * @param {string} charId - キャラクターID
   */
  function preloadSprites(charId) {
    try {
      var spriteEl = document.getElementById('pet-sprite');
      var baseChar = getBaseCharacter(charId);
      _syncStageHd2dClasses(charId);
      if (spriteEl) {
        spriteEl.onerror = null;
        spriteEl.src = '/assets/dot/' + baseChar + '/idle_1.png';
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
      var baseChar = getBaseCharacter(activeChar);
      _syncStageHd2dClasses(activeChar);
      var url = '/assets/dot/' + baseChar + '/' + name + '.png';
      if (el.src && el.src.indexOf(url) !== -1) return;
      el.onerror = function () {
        el.onerror = null;
        el.src = '/assets/dot/' + baseChar + '/idle_1.png';
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
      var baseChar = getBaseCharacter(activeChar);
      _syncStageHd2dClasses(activeChar);
      
      var urls = candidates.map(function (name) { return '/assets/dot/' + baseChar + '/' + name + '.png'; });
      urls.push('/assets/dot/' + baseChar + '/idle_1.png');

      var idx = 0;
      spriteEl.onerror = function () {
        idx += 1;
        if (idx < urls.length) {
          spriteEl.src = urls[idx];
        } else {
          spriteEl.onerror = null; // 最終フォールバック
          spriteEl.src = '/assets/dot/' + baseChar + '/idle_1.png';
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
      var activeChar = window.currentCharacterId || currentCharacterId;
      var baseChar = getBaseCharacter(activeChar);
      var isKyle = (baseChar === 'kyle');

      var act = 'working';
      var dialog = isKyle ? 'カタカタ…貝型PCで集中業務支援中でございます🐚' : 'カタカタ…集中してお手伝い中！';

      if (hour >= 23 || hour < 6) {
        act = 'sleeping';
        dialog = isKyle ? 'カタカタ…深夜帯でございますね。貝型PCをナイトモードに移行いたします💤' : 'すやすや…ボス、良い夢を…💤 温かいお茶をどうぞ🍵';
      } else if (hour >= 6 && hour < 8) {
        act = 'breakfast';
        dialog = isKyle ? 'カタカタ…おはようございます、ボス！貝型PCが本日の予定を最適ソートいたしました🐚' : 'おはようございます！朝ごはん美味しいです🍞 お茶も淹れました🍵';
      } else if ((hour >= 11 && hour < 13 && min >= 30) || hour === 12) {
        act = 'lunch';
        dialog = isKyle ? 'カタカタ…お昼の業務インターバル。貝型PCの冷却ファンを回しております！' : 'もぐもぐ…お昼ごはんの時間ですね🍱 お茶のおかわりはいかがですか？';
      } else if (hour === 15) {
        act = 'resting';
        dialog = isKyle ? 'カタカタ…15時の一息でございます。貝型PCもリフレッシュ！🐚' : 'ほっと一息、お茶とお菓子タイムです🍵 ボス、深呼吸をどうぞ✨';
      } else if (hour >= 16 && hour < 18) {
        act = 'reading';
        dialog = isKyle ? 'カタカタ…貝型PCで最新技術ナレッジを高速クロール中でございます📖' : 'ふむふむ…新しい技術や手帳を読んで勉強中📖';
      } else if (hour >= 18 && hour < 20) {
        act = 'dinner';
        dialog = isKyle ? 'カタカタ…本日もお見事な采配でございました。業務ログの保存は貝型PCにお任せを✨' : '今日もお疲れ様でした！美味しい晩ごはんです🍚 残りのタスクはお任せください！';
      } else if (hour >= 20 && hour < 22) {
        act = 'bathing';
        dialog = isKyle ? 'カタカタ…夜のメンテナンスタイム。貝型PCもクリーンアップ中です🛁' : 'いい湯だな〜♪さっぱりリフレッシュ🛁 温かいほうじ茶をどうぞ🍵';
      } else {
        if (isKyle) {
          var kyleRandom = [
            { act: 'working', msg: 'カタカタ…貝型PC、フルスペック稼働中でございます🐚' },
            { act: 'reading', msg: 'カタカタ…手帳と知見ノートを索引中📖' },
            { act: 'resting', msg: 'ふっ、案内業務は継続しております！' },
            { act: 'playing', msg: '貝型PCのクロックが加速中…カタカタカタッ！⚡' }
          ];
          var pickK = kyleRandom[Math.floor(Math.random() * kyleRandom.length)];
          act = pickK.act;
          dialog = pickK.msg;
        } else {
          var hishoRandom = [
            { act: 'working', msg: 'カタカタ…集中してお手伝い中！' },
            { act: 'reading', msg: '仕様書や手帳の予定をチェック中📖' },
            { act: 'resting', msg: '深呼吸してストレッチ〜✨ お茶をどうぞ🍵' },
            { act: 'playing', msg: 'ボスと一緒にいられて嬉しいです♪🌸' }
          ];
          var pickH = hishoRandom[Math.floor(Math.random() * hishoRandom.length)];
          act = pickH.act;
          dialog = pickH.msg;
        }
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

      var now = Date.now();
      // 🛡️ 多重発火ガード: すでに歓喜ジャンプ中の場合はタイマー延長のみ行い、リフローやパーティクルの二重生成を抑止
      if (window._celebratingUntil && now < window._celebratingUntil) {
        window._celebratingUntil = Math.max(window._celebratingUntil, now + durationMs);
        return;
      }

      // 既存タイマーのクリア
      if (_celebrateTimer) clearTimeout(_celebrateTimer);
      if (_celebrateFrameInterval) clearInterval(_celebrateFrameInterval);

      window.petStateNow = 'celebrate';
      window._celebratingUntil = now + durationMs;

      // 1. CSSジャンプアニメーション＆足元シャドウ連動の適用
      if (!sprite.classList.contains('celebrating')) {
        sprite.classList.remove('squashing');
        // チラつき防止: 既にアニメーション中でない場合のみリフロー安全適用
        void sprite.offsetWidth;
        sprite.classList.add('celebrating');
      }
      if (shadow && !shadow.classList.contains('celebrating')) {
        shadow.classList.add('celebrating');
      }

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
          var baseChar = getBaseCharacter(activeChar);
          var hasWalk = WALK_CAPABLE_CHARS.indexOf(baseChar) !== -1;
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
  // 5. なでなでインタラクション ＆ HD-2Dリッチモーション
  // =============================================================================

  /**
   * タップ時のピクセル波紋リングを生成
   * @param {number} x - 画面X座標
   * @param {number} y - 画面Y座標
   */
  function spawnPixelRing(x, y) {
    try {
      var stage = document.querySelector('.pet-stage');
      if (!stage) return;
      var ring = document.createElement('div');
      ring.className = 'pixel-ring';
      var rect = stage.getBoundingClientRect();
      var relX = x - rect.left;
      var relY = y - rect.top;
      ring.style.left = relX + 'px';
      ring.style.top = relY + 'px';
      stage.appendChild(ring);
      setTimeout(function () {
        if (ring.parentNode) ring.parentNode.removeChild(ring);
      }, 650);
    } catch (e) {
      console.warn('[pet_motion] spawnPixelRing failed:', e);
    }
  }

  /**
   * キャラクター固有モーションを発火
   * @param {string} motionName - 'hop' | 'jiggle' | 'bow' | 'tea' | 'typing'
   */
  function triggerPetMotion(motionName) {
    try {
      var sprite = document.getElementById('pet-sprite');
      if (!sprite) return;
      var activeChar = window.currentCharacterId || currentCharacterId;
      var baseChar = getBaseCharacter(activeChar);

      var motionClass = 'motion-' + motionName;
      sprite.classList.remove('squashing', 'motion-hop', 'motion-jiggle', 'motion-bow', 'motion-tea', 'motion-typing');
      void sprite.offsetWidth; // リフロー強制
      sprite.classList.add(motionClass);

      // モーション中の特定フレーム差し替え
      if (motionName === 'tea') {
        _setPetSprite('tea_1');
        setTimeout(function () { _setPetSprite('tea_2'); }, 300);
      } else if (motionName === 'typing') {
        _setPetSprite('focus_1');
        setTimeout(function () { _setPetSprite('focus_2'); }, 250);
      } else if (motionName === 'hop') {
        _setPetSprite('happy');
      } else if (motionName === 'bow') {
        _setPetSprite('stretch_1');
      } else if (motionName === 'jiggle') {
        _setPetSprite('care_1');
      }

      setTimeout(function () {
        sprite.classList.remove(motionClass);
        var act = window.currentActivity || currentActivity || 'resting';
        updateLifeSprite(act);
      }, 750);
    } catch (e) {
      console.warn('[pet_motion] triggerPetMotion failed:', e);
    }
  }

  /**
   * ペットタップ／クリック時のなでなでリアクション（HD-2Dピクセル波紋 ＆ モーション ＆ 個性セリフ）
   * @param {Event} event - タッチまたはクリックイベント
   */
  function onPetTap(event) {
    try {
      if (navigator.vibrate) navigator.vibrate(30);

      var activeChar = window.currentCharacterId || currentCharacterId;
      var baseChar = getBaseCharacter(activeChar);
      if (typeof playCharacterSE === 'function') {
        playCharacterSE(baseChar);
      }

      var rect = event.currentTarget ? event.currentTarget.getBoundingClientRect() : { left: 0, top: 0, width: 100, height: 100 };
      var clickX = (event.clientX || (event.touches && event.touches[0].clientX)) || (rect.left + rect.width / 2);
      var clickY = (event.clientY || (event.touches && event.touches[0].clientY)) || (rect.top + rect.height / 2);

      // 🌟 ピクセル波紋 (Pixel Ring Ripple)
      spawnPixelRing(clickX, clickY);

      // 🎭 キャラ別モーション発火 (hisho: tea/bow/hop/jiggle, kyle: typing/hop/jiggle/bow)
      var motions = (baseChar === 'kyle') ? ['typing', 'hop', 'jiggle', 'bow'] : ['tea', 'bow', 'hop', 'jiggle'];
      var chosenMotion = motions[Math.floor(Math.random() * motions.length)];
      triggerPetMotion(chosenMotion);

      if (typeof spawnTouchParticles === 'function') {
        spawnTouchParticles(clickX, clickY, 6);
      }

      var bubble = document.getElementById('speech-bubble');
      if (bubble) {
        var replies = [];
        if (baseChar === 'kyle') {
          replies = [
            "カタカタ…！貝型PCのキーボードが絶好調でございます🐚",
            "ふっ、ボスの指先タッチ…！貝型PCのクロックが加速いたしました！⚡",
            "カタカタッ…！ご案内業務の準備はいつでも万端でございます！",
            "お呼びでしょうか！この貝型PC、ボスの相棒としてフル稼働いたします🐚"
          ];
        } else {
          replies = [
            "淹れたての温かいお茶をどうぞ🍵 ボス、深呼吸してくださいね！",
            "ボスにお仕えできて光栄です！本日も全力でサポートいたします✨",
            "えへへ、くすぐったいです！🥰 ボス、何でもお申し付けくださいね。",
            "ボスのご活躍を一番近くで応援しております！🌸"
          ];
        }
        bubble.innerText = replies[Math.floor(Math.random() * replies.length)];
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
  window.getBaseCharacter = getBaseCharacter;
  window.cycleCharacter = cycleCharacter;
  window.preloadSprites = preloadSprites;
  window._setPetSprite = _setPetSprite;
  window.setPetSprite = _setPetSprite;
  window.ACTIVITY_SPRITES = ACTIVITY_SPRITES;
  window.currentActivity = currentActivity;
  window.updateLifeSprite = updateLifeSprite;
  window.updatePetLifeActivity = updatePetLifeActivity;
  window.triggerCelebrateReaction = triggerCelebrateReaction;
  window.triggerPetMotion = triggerPetMotion;
  window.spawnPixelRing = spawnPixelRing;
  window.WANDER = WANDER;
  window.petWanderTick = petWanderTick;
  window.onPetTap = onPetTap;

})();

// 非モジュール環境での直接参照用トップレベル宣言
var CHARACTERS = window.CHARACTERS;
var WALK_CAPABLE_CHARS = window.WALK_CAPABLE_CHARS;
var currentCharacterId = window.currentCharacterId;
var getBaseCharacter = window.getBaseCharacter;
var cycleCharacter = window.cycleCharacter;
var preloadSprites = window.preloadSprites;
var _setPetSprite = window._setPetSprite;
var setPetSprite = window.setPetSprite;
var ACTIVITY_SPRITES = window.ACTIVITY_SPRITES;
var currentActivity = window.currentActivity;
var updateLifeSprite = window.updateLifeSprite;
var updatePetLifeActivity = window.updatePetLifeActivity;
var triggerCelebrateReaction = window.triggerCelebrateReaction;
var triggerPetMotion = window.triggerPetMotion;
var spawnPixelRing = window.spawnPixelRing;
var WANDER = window.WANDER;
var petWanderTick = window.petWanderTick;
var onPetTap = window.onPetTap;
