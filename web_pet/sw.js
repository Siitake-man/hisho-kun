/**
 * ネオ秘書くん Service Worker (sw.js)
 * PWAスタンドアロンインストール ＆ オフラインキャッシュ
 */
try {
  importScripts('./version.js');
  importScripts('./push_common.js');
} catch (e) {
  // フォールバック (push_common.js が無くても SW 本体は動作させる)
}
const CACHE_NAME = self.WEB_PET_CACHE_NAME || 'neo-pet-v1.0.0';
const ASSETS_TO_CACHE = [
  './index.html',
  './version.js',
  './lang.js',
  './push_common.js',
  './pet_auth.js',
  './pet_audio_se.js',
  './pet_particles.js',
  './pet_motion.js',
  './pet_ui.js',
  './pet.js',
  './manifest.json',
  // ホーム画面アイコン (タスク3): オフライン起動時もアイコンが欠けないよう事前キャッシュ
  './assets/pwa/icon_192.png',
  './assets/pwa/icon_512.png',
  './assets/pwa/icon_maskable_512.png',
  './assets/pwa/apple_touch_icon_180.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      // P2-1 (2026-09-16): addAll は1件でも404でinstallが全滅するため、
      // 個別 add + 失敗ログで1件ずつ耐性を持たせる。
      return Promise.all(
        ASSETS_TO_CACHE.map((url) =>
          cache.add(url).catch((err) =>
            console.warn('[SW] pre-cache failed (non-fatal):', url, err)
          )
        )
      );
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // APIリクエストは常にネットワーク優先
  if (event.request.url.includes('/api/')) {
    event.respondWith(fetch(event.request));
    return;
  }
  
  event.respondWith(
    fetch(event.request).catch(() => {
      return caches.match(event.request);
    })
  );
});

// =============================================================================
// Web Push (Service Worker + VAPID): PWA を閉じていても OS 標準通知として届ける
// =============================================================================

/**
 * push イベント受信: OS 標準通知を表示し、未読記録 (IndexedDB) に蓄積する。
 * 取りこぼした通知は PWA 起動時に pet_push.js がまとめ表示する。
 */
self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    // JSON 以外のペイロードはテキストとして表示する (Fail-Safe)
    data = { title: 'ネオ秘書くん', body: event.data ? event.data.text() : '' };
  }
  const title = data.title || 'ネオ秘書くん';
  const timestamp = data.timestamp || Date.now();
  const options = {
    body: data.body || '',
    tag: data.tag || 'hisho-' + (data.event_type || 'generic'),
    icon: './assets/pwa/icon_192.png',
    badge: './assets/pwa/icon_192.png',
    data: { event_type: data.event_type || 'generic', timestamp: timestamp }
  };

  event.waitUntil(
    (async () => {
      // 取りこぼし対策: 未読として IndexedDB に記録してから通知表示する
      if (self.NeoPush) {
        try {
          await self.NeoPush.recordUnreadPush({
            title: title,
            body: data.body || '',
            event_type: data.event_type || 'generic',
            timestamp: timestamp,
            tag: options.tag
          });
        } catch (e) {
          console.warn('[SW] 未読記録に失敗 (通知表示は継続):', e);
        }
      }
      await self.registration.showNotification(title, options);
    })()
  );
});

/**
 * 通知タップ: PWA を前面に復帰させる (既に開いていればフォーカス)。
 */
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    (async () => {
      const clientList = await self.clients.matchAll({
        type: 'window',
        includeUncontrolled: true
      });
      for (const client of clientList) {
        if ('focus' in client) {
          return client.focus();
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow('./index.html');
      }
      return undefined;
    })()
  );
});
