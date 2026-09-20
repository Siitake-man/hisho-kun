// ネオ秘書くん - バージョン定数一元管理 (web_pet/version.js)
// Python 側の version.py (__version__) を Single Source of Truth とし、
// local_sync_server.py から動的配信されます。
// 本ファイルはオフライン時・開発環境・フォールバック用の静的実体です。

self.APP_VERSION = "1.1.0";
self.WEB_PET_CACHE_NAME = "neo-pet-v1.1.0";

if (typeof window !== "undefined") {
    window.APP_VERSION = self.APP_VERSION;
    window.WEB_PET_CACHE_NAME = self.WEB_PET_CACHE_NAME;
}
