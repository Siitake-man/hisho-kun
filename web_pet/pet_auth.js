/**
 * @fileoverview ネオ秘書くん Desk Pet - 認証トークン管理 ＆ authFetch (pet_auth.js)
 * Zero-Trust Bearer Token 管理、URLパラメータ/localStorage 解決、および自動再試行 fetch ラッパー。
 * 
 * 責務:
 * 1. PC側同期サーバーとの Bearer トークン初期化 (URLクエリ `token=` または localStorage)
 * 2. 全APIリクエストへの Authorization ヘッダー自動付与
 * 3. 401 Unauthorized 受信時の /api/auth/token からのトークン再取得と自動リトライ (1回)
 * 4. グローバル後方互換 (window.authFetch, window.syncToken, var syncToken)
 */

// グローバル定数・変数定義
// ⚠️ 他のスクリプト (pet.js, minigame_*.js) から直接アクセス可能にするため var / window 併用
const SYNC_TOKEN_KEY = 'neo_hisho_sync_token';
// 🛡️ ID 50 (2026-09-23): 端末自己生成UUID（MACの代替）。ペアリング時の行再利用キー。
// IP・UA・経路（Serve/LAN）が変わっても同一端末が1行に集約される。
const DEVICE_UUID_KEY = 'neo_hisho_device_uuid';
var syncToken = '';

/**
 * 端末自己生成UUID（MACの代替）を取得する。初回は生成して localStorage に永続化する。
 * ブラウザからMACアドレスは取得不可のため、推測不能な UUIDv4 を端末の一意IDとして使う。
 * @returns {string} 端末UUID（生成・保存に失敗した場合は空文字＝従来動作へフォールバック）
 */
function getOrCreateDeviceUuid() {
  try {
    const stored = localStorage.getItem(DEVICE_UUID_KEY);
    if (stored && /^[0-9a-fA-F-]{36}$/.test(stored)) {
      return stored;
    }
    let uuid = '';
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
      uuid = window.crypto.randomUUID();
    } else if (window.crypto && typeof window.crypto.getRandomValues === 'function') {
      // 🛡️ P1-2 (2026-09-23 査読): randomUUID はセキュアコンテキスト専用のため、LAN (http) でも
      // 動作する getRandomValues ベースの RFC 4122 v4 生成へフォールバックする（推測不能性は維持）。
      // 生成不能時のみ空文字＝従来動作へ後方互換。
      const bytes = new Uint8Array(16);
      window.crypto.getRandomValues(bytes);
      bytes[6] = (bytes[6] & 0x0f) | 0x40;
      bytes[8] = (bytes[8] & 0x3f) | 0x80;
      const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
      uuid = `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
    }
    if (uuid) {
      localStorage.setItem(DEVICE_UUID_KEY, uuid);
    }
    return uuid;
  } catch (e) {
    console.warn('[pet_auth] Failed to access device uuid:', e);
    return '';
  }
}

/**
 * 同期トークンを取得
 * @returns {string} 現在の同期トークン
 */
function getSyncToken() {
  return syncToken || '';
}

/**
 * 同期トークンをロード（URLクエリパラメータ最優先、次点で localStorage）
 * URLから取得した場合は、リファラ漏洩や画面共有での露出を防ぐためアドレスバーをサニタイズする。
 * @returns {string} ロードされた同期トークン
 */
function loadSyncToken() {
  try {
    const urlParams = new URLSearchParams(window.location.search);
    const paramToken = urlParams.get('token');
    if (paramToken) {
      syncToken = paramToken;
      localStorage.setItem(SYNC_TOKEN_KEY, syncToken);
      window.syncToken = syncToken;
      
      // 🛡️ Zero-Trust強化: URLからトークンを除去してアドレスバーをサニタイズ
      if (window.history && window.history.replaceState) {
        urlParams.delete('token');
        const remainingQuery = urlParams.toString();
        const cleanUrl = window.location.pathname + (remainingQuery ? '?' + remainingQuery : '') + window.location.hash;
        window.history.replaceState(null, '', cleanUrl);
      }
      return syncToken;
    }
    syncToken = localStorage.getItem(SYNC_TOKEN_KEY) || '';
    window.syncToken = syncToken;
  } catch (e) {
    console.warn('[pet_auth] Failed to access URLSearchParams or localStorage:', e);
    syncToken = syncToken || '';
    window.syncToken = syncToken;
  }
  return syncToken;
}

/**
 * 同期トークンを明示的に更新・保存
 * @param {string} newToken 新しいBearerトークン
 */
function setSyncToken(newToken) {
  syncToken = newToken || '';
  window.syncToken = syncToken;
  try {
    if (syncToken) {
      localStorage.setItem(SYNC_TOKEN_KEY, syncToken);
    } else {
      localStorage.removeItem(SYNC_TOKEN_KEY);
    }
  } catch (e) {
    console.warn('[pet_auth] Failed to save sync token to localStorage:', e);
  }
}

let activeTokenRefreshPromise = null;
let lastTokenRefreshAttempt = 0;
const TOKEN_REFRESH_COOLDOWN_MS = 3000; // 連続要求を抑制するクールダウン(3秒)

/**
 * サーバーから新しい同期トークンを取得する（In-Flight重複リクエスト合流 ＆ クールダウン制御）。
 * 
 * @returns {Promise<string|null>} 取得できたトークン文字列、または失敗時 null
 */
async function requestSyncToken() {
  if (activeTokenRefreshPromise) {
    return activeTokenRefreshPromise;
  }
  const now = Date.now();
  if (now - lastTokenRefreshAttempt < TOKEN_REFRESH_COOLDOWN_MS) {
    console.debug('[pet_auth] Token refresh throttled by cooldown');
    return syncToken || null;
  }
  lastTokenRefreshAttempt = now;

  activeTokenRefreshPromise = (async () => {
    try {
      // 🛡️ ID 50: 端末自己生成UUIDを申告（台帳の行再利用キー。認証の根拠にはならない）
      const deviceUuid = getOrCreateDeviceUuid();
      const tokenHeaders = deviceUuid ? { 'X-Device-UUID': deviceUuid } : {};
      const tokenRes = await fetch('/api/auth/token', { headers: tokenHeaders });
      if (tokenRes.ok) {
        const tokenData = await tokenRes.json();
        if (tokenData && tokenData.token) {
          setSyncToken(tokenData.token);
          return tokenData.token;
        }
      } else {
        // 403 (明示的拒絶・失効) の場合のみトークンをクリア
        if (tokenRes.status === 403) {
          setSyncToken('');
        }
        if (typeof window.showToast === 'function') {
          window.showToast('⚠️ PC側で「📱スマホDesk Pet接続」を開いて承認してください');
        }
      }
    } catch (e) {
      console.debug('[pet_auth] Token refresh error:', e);
    } finally {
      activeTokenRefreshPromise = null;
    }
    return null;
  })();
  return activeTokenRefreshPromise;
}

/**
 * 認証済み fetch ラッパー。全 API 呼び出しはこの関数を経由する。
 * 401応答時は /api/auth/token でトークン再取得を試み、1回だけ再試行する。
 * 
 * @param {string} url リクエスト先URL
 * @param {RequestInit & { _retried?: boolean }} [options={}] fetchオプション
 * @returns {Promise<Response>} fetchレスポンス
 */
async function authFetch(url, options = {}) {
  const headers = Object.assign({}, options.headers || {});
  
  // 🛡️ Zero-Trust強化: 相対パスまたは同一オリジン宛てのみ Bearer トークンを付与 (外部流出防止)
  const isSameOrigin = !url.includes('://') || (typeof window !== 'undefined' && url.startsWith(window.location.origin));
  if (syncToken && isSameOrigin) {
    headers['Authorization'] = `Bearer ${syncToken}`;
  }
  
  // FormData や Blob 以外の通常の body で Content-Type 未指定なら application/json を設定
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
  if (options.body && !isFormData && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
  
  let res;
  try {
    res = await fetch(url, Object.assign({}, options, { headers }));
  } catch (err) {
    throw err;
  }

  // 401 Unauthorized または 403 Forbidden（失効済み・不整合）かつ未再試行の場合、トークン再取得を試行
  if ((res.status === 401 || res.status === 403) && !options._retried) {
    const newToken = await requestSyncToken();
    if (newToken) {
      return authFetch(url, Object.assign({}, options, { _retried: true }));
    }
  }
  return res;
}

// 初期化実行
loadSyncToken();

// グローバルスコープ (window) への明示的公開（後方互換 ＆ 他モジュールからの安全な参照）
window.SYNC_TOKEN_KEY = SYNC_TOKEN_KEY;
window.syncToken = syncToken;
window.getSyncToken = getSyncToken;
window.loadSyncToken = loadSyncToken;
window.setSyncToken = setSyncToken;
window.authFetch = authFetch;
