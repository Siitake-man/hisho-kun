/**
 * ネオ秘書くん Service Worker (sw.js)
 * PWAスタンドアロンインストール ＆ オフラインキャッシュ
 */
try {
  importScripts('./version.js');
} catch (e) {
  // フォールバック
}
const CACHE_NAME = self.WEB_PET_CACHE_NAME || 'neo-pet-v1.0.0';
const ASSETS_TO_CACHE = [
  './index.html',
  './version.js',
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
