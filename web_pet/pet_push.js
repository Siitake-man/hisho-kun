/**
 * ネオ秘書くん Desk Pet - Web Push 購読管理 (pet_push.js)
 *
 * Service Worker 登録・Push 購読 (/api/push/subscribe)・起動時の
 * 「取りこぼした通知のまとめ表示（未読バッジ）」を担当する。
 *
 * 設計:
 *   - 認証付き fetch は pet_auth.js の window.authFetch (Bearer 自動付与・
 *     401 自動リトライ) を利用する。
 *   - 通知許可は未許可の場合にユーザーの初回タップを待ってから要求する
 *     （ロード直後の驚きプロンプト防止・モバイルブラウザのジェスチャ要件対策）。
 *   - いかなる失敗でも PWA 本体 (pet.js ポーリング) を止めない (Fail-Safe)。
 */
(function () {
  'use strict';

  // 認証トークン解決 (pet_auth.js) が完了した後に初期化するための遅延
  const INIT_DELAY_MS = 3000;
  // まとめバナーの自動非表示時間 (ミリ秒)
  const BANNER_AUTO_HIDE_MS = 10000;
  // まとめ表示の最大件数
  const SUMMARY_MAX_COUNT = 10;

  /**
   * Service Worker を登録し、Push 購読をサーバーへ登録する。
   * @param {ServiceWorkerRegistration} registration 登録済み SW の registration。
   * @returns {Promise<void>}
   */
  async function subscribeWebPush(registration) {
    const keyRes = await window.authFetch('/api/push/vapid_key');
    if (!keyRes.ok) {
      console.warn('[pet_push] VAPID 公開鍵の取得に失敗しました:', keyRes.status);
      return;
    }
    const keyData = await keyRes.json();
    if (!keyData.public_key) {
      console.warn('[pet_push] VAPID 公開鍵が空のため購読をスキップします');
      return;
    }

    let subscription = await registration.pushManager.getSubscription();
    if (!subscription) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: self.NeoPush.urlBase64ToUint8Array(keyData.public_key)
      });
    }

    const subJson = subscription.toJSON();
    if (!subJson.endpoint || !subJson.keys) {
      console.warn('[pet_push] 購読情報が不完全のため登録をスキップします');
      return;
    }
    const res = await window.authFetch('/api/push/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify({ endpoint: subJson.endpoint, keys: subJson.keys })
    });
    if (res.ok) {
      console.info('[pet_push] Push 購読をサーバーへ登録しました');
    } else {
      console.warn('[pet_push] Push 購読の登録に失敗しました:', res.status);
    }
  }

  /**
   * 起動時の取りこぼし通知まとめバナー (未読バッジ) を表示する。
   * 表示後は全未読を既読化し、次回起動時に二重表示しない。
   * @returns {Promise<void>}
   */
  async function showUnreadSummary() {
    if (!self.NeoPush) return;
    const unread = await self.NeoPush.getUnreadPushes(SUMMARY_MAX_COUNT);
    if (unread.length === 0) return;

    const latest = unread[0];
    const banner = document.createElement('div');
    banner.id = 'push-summary-banner';
    banner.style.cssText =
      'position:fixed;top:8px;left:50%;transform:translateX(-50%);z-index:9999;' +
      'max-width:92%;box-sizing:border-box;padding:10px 14px;border-radius:10px;' +
      'background:#2b2320;color:#f5e9d8;font-family:inherit;font-size:13px;' +
      'box-shadow:0 4px 12px rgba(0,0,0,.5);cursor:pointer;' +
      'border:1px solid #d4a373;display:flex;flex-direction:column;gap:2px;';
    const heading = document.createElement('div');
    heading.textContent = '🔔 オフライン中の通知 ' + unread.length + ' 件';
    heading.style.fontWeight = 'bold';
    const body = document.createElement('div');
    body.textContent =
      (latest.title ? '【' + latest.title + '】' : '') +
      (latest.body || '');
    banner.appendChild(heading);
    banner.appendChild(body);
    document.body.appendChild(banner);

    const dismiss = () => {
      if (banner.parentNode) banner.parentNode.removeChild(banner);
    };
    banner.addEventListener('click', dismiss);
    setTimeout(dismiss, BANNER_AUTO_HIDE_MS);
    // 二重表示防止のため表示した時点で既読化する
    await self.NeoPush.markAllPushesRead();
  }

  /**
   * 通知許可を要求して購読する (未許可時は初回タップを待つ)。
   *
   * Android Chrome の Quiet UI では許可プロンプトが数秒で自動的に消える
   * (通知シェードへ退避) ため、未選択 (default) の間はユーザーのタップの
   * たびに許可要求を再提示する。
   *
   * @param {ServiceWorkerRegistration} registration 登録済み SW の registration。
   * @returns {Promise<void>}
   */
  async function requestPermissionAndSubscribe(registration) {
    let permission = Notification.permission;

    // 未選択 (default) の間: タップのたびに許可要求を出して結果を待つ
    while (permission === 'default') {
      showPermissionHint();
      permission = await new Promise((resolve) => {
        const handler = () => {
          document.removeEventListener('click', handler);
          Promise.resolve(Notification.requestPermission()).then(resolve);
        };
        document.addEventListener('click', handler, { once: true });
      });
      removePermissionHint();
    }

    if (permission !== 'granted') {
      console.info('[pet_push] 通知許可がないため Push 購読をスキップしました');
      return;
    }
    await subscribeWebPush(registration);
  }

  /**
   * 通知許可を促すヒントバナーを表示する (既に表示中なら何もしない)。
   */
  function showPermissionHint() {
    if (document.getElementById('push-permission-hint')) return;
    const hint = document.createElement('div');
    hint.id = 'push-permission-hint';
    hint.style.cssText =
      'position:fixed;top:8px;left:50%;transform:translateX(-50%);z-index:9999;' +
      'max-width:92%;box-sizing:border-box;padding:10px 14px;border-radius:10px;' +
      'background:#1d3a5f;color:#eaf3ff;font-family:inherit;font-size:13px;' +
      'box-shadow:0 4px 12px rgba(0,0,0,.5);border:1px solid #7fb3ff;';
    hint.textContent = '🔔 画面をタップすると通知の許可確認が出ます。「許可」を押してください';
    document.body.appendChild(hint);
  }

  /**
   * 通知許可のヒントバナーを取り除く。
   */
  function removePermissionHint() {
    const hint = document.getElementById('push-permission-hint');
    if (hint && hint.parentNode) hint.parentNode.removeChild(hint);
  }

  /**
   * Web Push 初期化の本体 (SW 登録 → まとめ表示 → 購読)。
   * @returns {Promise<void>}
   */
  async function initWebPush() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
      console.info('[pet_push] このブラウザは Web Push 非対応のためスキップします');
      return;
    }
    const registration = await navigator.serviceWorker.register('./sw.js');
    await navigator.serviceWorker.ready;
    // まとめ表示は許可状態と無関係に実施 (オフライン中の push 記録の復元)
    await showUnreadSummary();
    await requestPermissionAndSubscribe(registration);
  }

  /**
   * 遅延初期化 (pet_auth.js のトークン解決後を狙う)。
   */
  function scheduleInit() {
    setTimeout(() => {
      initWebPush().catch((err) => {
        console.warn('[pet_push] Web Push 初期化に失敗しました (Fail-Safe):', err);
      });
    }, INIT_DELAY_MS);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', scheduleInit);
  } else {
    scheduleInit();
  }
})();
