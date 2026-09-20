/**
 * ネオ秘書くん Desk Pet PWA - 多言語化（i18n）＆ Microcopy管理エンジン (lang.js)
 * 
 * 【設計思想 - DESIGN_SPEC 20.14節 引き算のMicrocopy規約】
 * 1. 直訳の禁止: 英語化に伴うテキスト長膨張（1.3〜1.8倍）に対し、UI領域ごとの文字数予算（Character Budget）を死守する。
 *    - ボトムドック (Budget: 最大7文字): Tasks, Cal, Daily, Settings
 *    - 承認ボタン (Budget: 最大8文字): Approve, Deny
 *    - Jev安全審査バッジ (Budget: 最大14文字): 🟢 JEV: ALLOW
 * 2. 状態の永続化: localStorage ('neo_hisho_lang') に保存し、即座にカスタムイベント 'neolang:changed' をディスパッチ。
 * 3. ゼロ依存・完全自己完結: PWAオフライン環境でも確実に動作。
 */

(function (window) {
  'use strict';

  var STORAGE_KEY = 'neo_hisho_lang';

  // 多言語辞書定義
  var DICTIONARIES = {
    ja: {
      // ボトムドック (Character Budget: 最大7文字)
      'dock.tasks': 'タスク',
      'dock.cal': 'カレンダー',
      'dock.daily': '日報',
      'dock.settings': '設定',

      // 承認アクションボタン (Character Budget: 各単語最大8文字)
      'btn.approve': '承認する',
      'btn.deny': '却下する',
      'btn.complete': '完了',
      'btn.close': '閉じる',

      // Jev安全審査バッジ (Character Budget: 最大14文字)
      'badge.jev_prefix': '🟢 Jev安全審査: ',

      // エージェント・ペット状態
      'status.working': 'お仕事中',
      'status.sleeping': '睡眠中',
      'status.break': '休憩中',
      'status.idle': '待機中',

      // 最優先イベントバナー
      'banner.approval_wait': '⚠️ 外部AI 承認待ち',
      'banner.tap_details': 'タップで詳細',
      'banner.question': '❓ AIからの質問',
      'banner.completed': '🎉 タスク完了通知',
      'banner.reminder': '⏰ リマインダー',

      // ヘッダー・常時ONバナー
      'header.wake_banner': '💡 常時画面ON（自動消灯防止）はここをタップ',
      'header.nosleep_title': '💡 常時画面ON（自動消灯防止）',
      'header.theme_title': '🏞️ 背景テーマ切替',
      'header.fullscreen_title': '⛶ 全画面表示',
      'header.pomodoro_title': '🍅 ポモドーロ開始（25分）',

      // ブリーフィングバナー
      'briefing.quick_morning': '☀️ 朝会ブリーフィングを聞く',
      'briefing.quick_night': '🌙 夜間ブリーフィングを聞く',
      'briefing.quick_tap': 'タップ 📖',

      // サジェスト
      'suggest.tag': '💡 サジェスト',
      'suggest.ai_news': '💡 AIニュース',
      'suggest.loading': '読み込み中...',
      'suggest.default_title': '最新のAIトレンドをチェック',
      'suggest.complete_task': 'このタスクを完了にする',

      // TODOモーダル
      'todo.title': '📝 タスク管理',
      'todo.placeholder': '例: 明日18時に資料 #仕事 !3',
      'todo.filter_list': '📋 リスト',
      'todo.filter_all': '📥 すべて',
      'todo.filter_range': '🗓 期間',
      'todo.range_all': '🗂 すべて',
      'todo.range_today': '⏰ 今日',
      'todo.range_week': '📅 今週',
      'todo.quad_toggle': '🎯 4象限',
      'todo.quad_back': '📋 一覧に戻る',
      'todo.empty': '🎉 未完了のタスクはありません！',

      // カレンダーモーダル
      'cal.title': '📅 統合手帳・カレンダー',
      'cal.empty': '📅 直近3日間の予定はありません',

      // 日報モーダル
      'daily.title': '🌱 日報・生活記録',

      // 設定モーダル
      'settings.title': '⚙️ 設定',

      // トグルボタン表示（相手言語アフォーダンス）
      'lang.toggle_label': 'EN'
    },
    en: {
      // Bottom Dock (Character Budget: max 7 chars)
      'dock.tasks': 'Tasks',
      'dock.cal': 'Cal',
      'dock.daily': 'Daily',
      'dock.settings': 'Config',

      // Approval Action Buttons (Character Budget: max 8 chars)
      'btn.approve': 'Approve',
      'btn.deny': 'Deny',
      'btn.complete': 'Done',
      'btn.close': 'Close',

      // JEV Safety Badge (Character Budget: max 14 chars)
      'badge.jev_prefix': '🟢 JEV: ',

      // Agent / Pet Status
      'status.working': 'Working',
      'status.sleeping': 'Sleeping',
      'status.break': 'Break',
      'status.idle': 'Idle',

      // Active Event Banners
      'banner.approval_wait': '⚠️ Approval Needed',
      'banner.tap_details': 'Tap for details',
      'banner.question': '❓ AI Question',
      'banner.completed': '🎉 Task Completed',
      'banner.reminder': '⏰ Reminder',

      // Header & Wake Banner
      'header.wake_banner': '💡 Tap here to keep screen ON',
      'header.nosleep_title': '💡 Keep Screen ON',
      'header.theme_title': '🏞️ Switch Background Theme',
      'header.fullscreen_title': '⛶ Fullscreen',
      'header.pomodoro_title': '🍅 Start Pomodoro (25m)',

      // Briefing Banner
      'briefing.quick_morning': '☀️ Morning Briefing',
      'briefing.quick_night': '🌙 Evening Report Summary',
      'briefing.quick_tap': 'Tap 📖',

      // Suggestion
      'suggest.tag': '💡 Suggestion',
      'suggest.ai_news': '💡 AI News',
      'suggest.loading': 'Loading...',
      'suggest.default_title': 'Check latest AI trends',
      'suggest.complete_task': 'Mark task complete',

      // TODO Modal
      'todo.title': '📝 Task Manager',
      'todo.placeholder': 'e.g. Tomorrow 6pm docs #work !3',
      'todo.filter_list': '📋 Lists',
      'todo.filter_all': '📥 All',
      'todo.filter_range': '🗓 Range',
      'todo.range_all': '🗂 All',
      'todo.range_today': '⏰ Today',
      'todo.range_week': '📅 Week',
      'todo.quad_toggle': '🎯 Eisenhower',
      'todo.quad_back': '📋 Back to List',
      'todo.empty': '🎉 No pending tasks right now!',

      // Calendar Modal
      'cal.title': '📅 Schedule / Calendar',
      'cal.empty': '📅 No upcoming events in next 3 days',

      // Daily Modal
      'daily.title': '🌱 Daily Log & Habits',

      // Settings Modal
      'settings.title': '⚙️ Settings',

      // Toggle Button Label
      'lang.toggle_label': 'JA'
    }
  };

  var _currentLang = 'ja';

  /**
   * 現在言語を判定・取得
   * 1. localStorage優先
   * 2. ブラウザ言語 (navigator.language)
   * 3. フォールバック ('ja')
   */
  function getLang() {
    try {
      var saved = localStorage.getItem(STORAGE_KEY);
      if (saved === 'ja' || saved === 'en') {
        return saved;
      }
    } catch (e) {
      console.warn('[NeoLang] localStorage read error:', e);
    }

    try {
      var browserLang = (navigator.language || navigator.userLanguage || '').toLowerCase();
      if (browserLang.startsWith('en')) {
        return 'en';
      }
    } catch (e) {
      console.warn('[NeoLang] navigator.language detection error:', e);
    }

    return 'ja';
  }

  /**
   * 辞書引き
   * @param {string} key 
   * @param {string} [fallback] 
   * @returns {string}
   */
  function t(key, fallback) {
    var dict = DICTIONARIES[_currentLang] || DICTIONARIES.ja;
    if (dict && Object.prototype.hasOwnProperty.call(dict, key)) {
      return dict[key];
    }
    return fallback !== undefined ? fallback : key;
  }

  var _lastUserSwitchTime = 0;

  /**
   * 直近（5秒以内）にユーザー自身が手動で言語を切り替えたかどうかを判定
   * サーバーからの古いステータスポーリングによる巻き戻しを防止する。
   * @returns {boolean}
   */
  function isUserOverrideActive() {
    return (Date.now() - _lastUserSwitchTime) < 5000;
  }

  /**
   * 言語切り替え
   * @param {string} lang - 'ja' | 'en'
   * @param {boolean} [fromUser=false] - ユーザーの手動操作かどうか
   */
  function setLang(lang, fromUser) {
    if (fromUser === undefined) fromUser = false;
    var target = (lang === 'en') ? 'en' : 'ja';
    _currentLang = target;

    if (fromUser) {
      _lastUserSwitchTime = Date.now();
    }

    try {
      localStorage.setItem(STORAGE_KEY, target);
    } catch (e) {
      console.warn('[NeoLang] localStorage write error:', e);
    }

    // HTML lang 属性更新
    if (document.documentElement) {
      document.documentElement.lang = target;
    }

    // トグルボタンの表示更新
    updateToggleButtonUI();

    // 🌐 ユーザー自身による手動切替時は、PCサーバー側にも即座に同期通知 & トースト視覚フィードバック
    if (fromUser) {
      try {
        if (typeof window.showToast === 'function') {
          var msg = (target === 'en') ? '🌐 Switched to English' : '🌐 言語を日本語に切り替えました';
          window.showToast(msg, 1800, true);
        }
      } catch (e) {
        console.debug('[NeoLang] showToast error (ignored):', e);
      }

      try {
        var fetchFn = window.authFetch || window.fetch;
        if (fetchFn) {
          fetchFn('/api/action', {
            method: 'POST',
            body: JSON.stringify({ action: 'set_language', language: target })
          }).catch(function (e) {
            console.debug('[NeoLang] Server sync error (ignored):', e);
          });
        }
      } catch (e) {
        console.debug('[NeoLang] Server sync dispatch error:', e);
      }
    }

    // カスタムイベント発火（各UIコンポーネントが自律更新）
    try {
      var event;
      if (typeof CustomEvent === 'function') {
        event = new CustomEvent('neolang:changed', { detail: { lang: target } });
      } else {
        event = document.createEvent('CustomEvent');
        event.initCustomEvent('neolang:changed', true, true, { lang: target });
      }
      window.dispatchEvent(event);
    } catch (e) {
      console.warn('[NeoLang] Event dispatch error:', e);
    }
  }

  /**
   * 言語トグル（ja <-> en）
   */
  function toggleLang() {
    var next = (_currentLang === 'ja') ? 'en' : 'ja';
    setLang(next, true);
    if (navigator.vibrate) {
      try { navigator.vibrate(25); } catch (e) {}
    }
    return next;
  }

  /**
   * トグルボタンのUI更新
   */
  function updateToggleButtonUI() {
    var btn = document.getElementById('lang-toggle-btn');
    if (btn) {
      // 日本語時は次の切替先 'EN'、英語時は 'JA'
      btn.textContent = (_currentLang === 'ja') ? 'EN' : 'JA';
      btn.setAttribute('aria-label', (_currentLang === 'ja') ? 'Switch to English' : '日本語に切り替え');
      btn.setAttribute('data-lang', _currentLang);
    }
  }

  /**
   * トグルボタンへの確実なイベントバインド（スマホのタップ・タッチ対応）
   */
  function bindToggleButton() {
    var btn = document.getElementById('lang-toggle-btn');
    if (!btn) return;
    if (btn._neolangBound) return;
    btn._neolangBound = true;

    var handleToggle = function (ev) {
      if (ev) {
        if (ev.preventDefault) ev.preventDefault();
        if (ev.stopPropagation) ev.stopPropagation();
      }
      toggleLang();
    };

    // click と touchend の両方で即時反応（二重発火抑止付き）
    var lastTrigger = 0;
    var safeHandler = function (ev) {
      var now = Date.now();
      if (now - lastTrigger < 300) return; // 300ms以内の連続発火を防止
      lastTrigger = now;
      handleToggle(ev);
    };

    btn.addEventListener('click', safeHandler, { passive: false });
    btn.addEventListener('touchend', safeHandler, { passive: false });
  }

  /**
   * 初期化処理
   */
  function init() {
    _currentLang = getLang();
    if (document.documentElement) {
      document.documentElement.lang = _currentLang;
    }

    // DOM構築完了後にボタン表示とイベントバインドを整える
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function () {
        updateToggleButtonUI();
        bindToggleButton();
      });
    } else {
      updateToggleButtonUI();
      bindToggleButton();
    }
  }

  // 初期化実行
  init();

  var DICTIONARY = DICTIONARIES;

  // グローバルモジュール公開
  var NeoLang = {
    t: t,
    getLang: getLang,
    setLang: setLang,
    toggleLang: toggleLang,
    isUserOverrideActive: isUserOverrideActive,
    updateToggleButtonUI: updateToggleButtonUI,
    bindToggleButton: bindToggleButton,
    DICTIONARY: DICTIONARY,
    dictionaries: DICTIONARIES,
    init: init
  };

  window.NeoLang = NeoLang;

})(window);
