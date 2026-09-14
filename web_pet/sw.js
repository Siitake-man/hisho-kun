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
  './pet.js',
  './manifest.json'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE);
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
