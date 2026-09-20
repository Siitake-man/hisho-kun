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

  /**
   * 言語切り替え
   * @param {string} lang - 'ja' | 'en'
   */
  function setLang(lang) {
    var target = (lang === 'en') ? 'en' : 'ja';
    _currentLang = target;

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
    setLang(next);
    if (navigator.vibrate) {
      navigator.vibrate(25);
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
   * 初期化処理
   */
  function init() {
    _currentLang = getLang();
    if (document.documentElement) {
      document.documentElement.lang = _currentLang;
    }

    // DOM構築完了後にボタン表示を整える
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function () {
        updateToggleButtonUI();
      });
    } else {
      updateToggleButtonUI();
    }
  }

  // 初期化実行
  init();

  // グローバルモジュール公開
  var NeoLang = {
    t: t,
    getLang: function () { return _currentLang; },
    setLang: setLang,
    toggleLang: toggleLang,
    init: init,
    dictionaries: DICTIONARIES
  };

  window.NeoLang = NeoLang;

})(window);
