/**
 * ネオ秘書くん Web Push 共通ユーティリティ (push_common.js)
 *
 * Service Worker (importScripts) とページ (script タグ) の両方から読み込まれる。
 * 「取りこぼした通知のまとめ表示 (未読バッジ)」の中核として、Push 受信を
 * IndexedDB に記録し、PWA 起動時に未読一覧を取り出す API を提供する。
 *
 * ポーリングは PWA が開いている間しか動かないため、画面オフ・ブラウザ閉じ中に
 * 届いた Push の内容は本モジュールの IndexedDB 記録から復元する。
 */
(function (root) {
  'use strict';

  const PUSH_DB_NAME = 'neo-hisho-push';
  const PUSH_DB_STORE = 'unread';
  // 未読記録の保持期間 (7日)。それより古い記録は書き込み時に掃除する。
  const UNREAD_TTL_MS = 7 * 24 * 60 * 60 * 1000;

  /**
   * IndexedDB (neo-hisho-push / unread ストア) を開く。
   * @returns {Promise<IDBDatabase>} 開いた DB 接続。
   */
  function openPushDb() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(PUSH_DB_NAME, 1);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(PUSH_DB_STORE)) {
          const store = db.createObjectStore(PUSH_DB_STORE, { keyPath: 'id' });
          store.createIndex('timestamp', 'timestamp');
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  /**
   * Push 受信内容を未読として IndexedDB に記録する (7日より古い記録は掃除)。
   * @param {Object} data push ペイロード {title, body, event_type, timestamp, tag}。
   * @returns {Promise<void>}
   */
  async function recordUnreadPush(data) {
    const db = await openPushDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(PUSH_DB_STORE, 'readwrite');
      const store = tx.objectStore(PUSH_DB_STORE);
      const timestamp = Number(data.timestamp) || Date.now();
      const tag = data.tag || 'hisho-' + (data.event_type || 'generic');
      store.put({
        id: `${tag}:${timestamp}`,
        title: data.title || '',
        body: data.body || '',
        event_type: data.event_type || 'generic',
        timestamp: timestamp,
        read: 0
      });
      // 7日より古い記録の掃除 (TTL 運用)
      const cursorReq = store.openCursor();
      cursorReq.onsuccess = (event) => {
        const cursor = event.target.result;
        if (cursor && cursor.value.timestamp < Date.now() - UNREAD_TTL_MS) {
          cursor.delete();
          cursor.continue();
        }
      };
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  /**
   * 未読 push を新しい順に最大 limit 件取り出す。
   * @param {number} limit 最大取得件数。
   * @returns {Promise<Array<Object>>} 未読記録の配列。
   */
  async function getUnreadPushes(limit) {
    const db = await openPushDb();
    return new Promise((resolve, reject) => {
      const results = [];
      const tx = db.transaction(PUSH_DB_STORE, 'readonly');
      const index = tx.objectStore(PUSH_DB_STORE).index('timestamp');
      const req = index.openCursor(null, 'prev'); // 新しい順
      req.onsuccess = (event) => {
        const cursor = event.target.result;
        if (cursor && results.length < limit) {
          if (!cursor.value.read) results.push(cursor.value);
          cursor.continue();
        }
      };
      tx.oncomplete = () => resolve(results);
      tx.onerror = () => reject(tx.error);
    });
  }

  /**
   * 全未読を既読化する (まとめ表示の再表示防止)。
   * @returns {Promise<void>}
   */
  async function markAllPushesRead() {
    const db = await openPushDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(PUSH_DB_STORE, 'readwrite');
      const store = tx.objectStore(PUSH_DB_STORE);
      const req = store.openCursor();
      req.onsuccess = (event) => {
        const cursor = event.target.result;
        if (cursor) {
          if (!cursor.value.read) {
            const updated = Object.assign({}, cursor.value, { read: 1 });
            cursor.update(updated);
          }
          cursor.continue();
        }
      };
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  /**
   * VAPID 公開鍵 (Base64URL) を pushManager.subscribe 用の Uint8Array へ変換する。
   * @param {string} base64String Base64URL エンコードされた公開鍵。
   * @returns {Uint8Array} デコード済みバイト列。
   */
  function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = root.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; i += 1) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  root.NeoPush = {
    openPushDb: openPushDb,
    recordUnreadPush: recordUnreadPush,
    getUnreadPushes: getUnreadPushes,
    markAllPushesRead: markAllPushesRead,
    urlBase64ToUint8Array: urlBase64ToUint8Array
  };
})(typeof self !== 'undefined' ? self : this);
