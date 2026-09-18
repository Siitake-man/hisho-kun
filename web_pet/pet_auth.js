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
var syncToken = '';

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
    try {
      const tokenRes = await fetch('/api/auth/token');
      if (tokenRes.ok) {
        const tokenData = await tokenRes.json();
        if (tokenData && tokenData.token) {
          setSyncToken(tokenData.token);
          return authFetch(url, Object.assign({}, options, { _retried: true }));
        }
      } else {
        // トークン取得に失敗（ペアリング未開放等）した場合は古い無効トークンをクリア
        setSyncToken('');
      }
    } catch (e) {
      console.debug('[pet_auth] Token refresh error:', e);
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
