/**
 * ネオ秘書くん Desk Pet PWA - UI・バナー・承認・サジェストエンジン (pet_ui.js)
 * 
 * 【責務】
 * 1. 高視認性HUDトースト通知 (showToast, toastTimer)
 * 2. サジェストカード表示 ＆ Glass Bottom Sheet (renderSuggestionCard, nextSuggest, prevSuggest, openBottomSheet, closeBottomSheet)
 * 3. エージェント承認バナー ＆ イベント操作 (setupBannerSwipe, openApprovalSheet, openQuestionSheet, respondApproval, respondChoice)
 * 4. MediaSession API によるノールック承認 (setupMediaKeyApproval)
 * 5. 時計 ＆ ポモドーロUI制御 (updateClock, togglePomodoro)
 * 6. エージェント稼働ライブバッジ表示 (updateAgentActivityBadge)
 * 7. HTMLエスケープユーティリティ (escapeHtml)
 */

(function () {
  'use strict';

  // =============================================================================
  // 1. 高視認性HUDトースト通知
  // =============================================================================
  var toastTimer = null;

  /**
   * HUDトースト通知を表示
   * @param {string} message - 表示メッセージ (HTML可)
   * @param {number} duration - 表示時間 (ミリ秒)
   * @param {boolean} isHighlight - 成功・強調枠線
   */
  function showToast(message, duration, isHighlight) {
    if (typeof duration !== 'number') duration = 3500;
    try {
      var toast = document.getElementById('global-hud-toast');
      if (!toast) {
        toast = document.createElement('div');
        toast.id = 'global-hud-toast';
        toast.style.cssText = [
          'position: fixed',
          'top: 42px',
          'left: 50%',
          'transform: translateX(-50%) translateY(-10px)',
          'background: linear-gradient(135deg, rgba(30, 20, 14, 0.97), rgba(46, 28, 20, 0.97))',
          'border: 2px solid var(--accent-amber, #FFB800)',
          'color: #F5F5DC',
          'padding: 9px 18px',
          'border-radius: 8px',
          'font-family: \'DotGothic16\', monospace',
          'font-size: 13px',
          'font-weight: bold',
          'z-index: 999999',
          'box-shadow: 0 8px 30px rgba(0,0,0,0.85), 0 0 15px rgba(255,184,0,0.5)',
          'opacity: 0',
          'transition: all 0.3s cubic-bezier(0.18, 0.89, 0.32, 1.28)',
          'pointer-events: none',
          'text-align: center',
          'max-width: 90vw',
          'word-break: break-word',
          'line-height: 1.4'
        ].join(';');
        document.body.appendChild(toast);
      }

      if (isHighlight) {
        toast.style.borderColor = '#00E676';
        toast.style.boxShadow = '0 8px 30px rgba(0,0,0,0.85), 0 0 20px rgba(0,230,118,0.7)';
      } else {
        toast.style.borderColor = '#FFB800';
        toast.style.boxShadow = '0 8px 30px rgba(0,0,0,0.85), 0 0 15px rgba(255,184,0,0.5)';
      }

      toast.innerHTML = message;
      toast.style.opacity = '1';
      toast.style.transform = 'translateX(-50%) translateY(0)';

      if (toastTimer) clearTimeout(toastTimer);
      toastTimer = setTimeout(function () {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(-50%) translateY(-10px)';
      }, duration);
    } catch (e) {
      console.warn('[pet_ui] showToast failed:', e);
    }
  }

  // =============================================================================
  // 2. HTML特殊文字エスケープ (XSS防止)
  // =============================================================================
  function escapeHtml(str) {
    return String(str || '').replace(/[&<>"']/g, function (m) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
    });
  }

  // =============================================================================
  // 3. サジェスト表示 ＆ Glass Bottom Sheet ニュースリーダー
  // =============================================================================
  var currentSheetItem = null;

  function renderSuggestionCard() {
    try {
      var suggestions = window.suggestionsData || [];
      var suggestIdx = window.suggestIndex || 0;

      if (!suggestions || suggestions.length === 0) {
        var titleEl = document.getElementById('suggest-title');
        var descEl = document.getElementById('suggest-desc');
        var tagEl = document.getElementById('suggest-tag');
        var qBtn = document.getElementById('suggest-quick-complete-btn');
        if (titleEl) titleEl.innerText = "予定・タスクはありません";
        if (descEl) descEl.innerText = "ゆっくりお茶でも飲んで休みましょう🍵";
        if (tagEl) tagEl.innerText = "💡 サジェスト";
        if (qBtn) qBtn.style.display = 'none';
        return;
      }

      suggestIdx = (suggestIdx + suggestions.length) % suggestions.length;
      window.suggestIndex = suggestIdx;
      var s = suggestions[suggestIdx];
      var total = suggestions.length;
      var curr = suggestIdx + 1;
      var icon = s.icon || "💡";
      var tag = s.tag || "サジェスト";

      var tagEl2 = document.getElementById('suggest-tag');
      if (tagEl2) tagEl2.innerText = icon + ' ' + tag + ' (' + curr + '/' + total + ')';
      
      var titleEl2 = document.getElementById('suggest-title');
      if (titleEl2) titleEl2.innerText = s.title || "";
      
      var descEl2 = document.getElementById('suggest-desc');
      if (descEl2) descEl2.innerText = s.description || "";

      var qBtn2 = document.getElementById('suggest-quick-complete-btn');
      if (qBtn2) {
        if (s && s.source === 'tasks' && s.id && s.id.startsWith('task_')) {
          qBtn2.style.display = 'inline-flex';
        } else {
          qBtn2.style.display = 'none';
        }
      }
    } catch (e) {
      console.warn('[pet_ui] renderSuggestionCard failed:', e);
    }
  }

  function nextSuggest(e) {
    if (e && e.stopPropagation) e.stopPropagation();
    var suggestions = window.suggestionsData || [];
    if (!suggestions || suggestions.length === 0) return;
    window.suggestIndex = ((window.suggestIndex || 0) + 1) % suggestions.length;
    renderSuggestionCard();
    if (navigator.vibrate) navigator.vibrate(15);
  }

  function prevSuggest(e) {
    if (e && e.stopPropagation) e.stopPropagation();
    var suggestions = window.suggestionsData || [];
    if (!suggestions || suggestions.length === 0) return;
    window.suggestIndex = ((window.suggestIndex || 0) - 1 + suggestions.length) % suggestions.length;
    renderSuggestionCard();
    if (navigator.vibrate) navigator.vibrate(15);
  }

  function onSuggestCardClick() {
    var suggestions = window.suggestionsData || [];
    var suggestIdx = window.suggestIndex || 0;
    if (!suggestions || suggestions.length === 0) return;
    var s = suggestions[suggestIdx];
    if (!s) return;
    openBottomSheet(s);
  }

  // サジェストカードから直接ワンタップでTODOを完了する (Bearer認証対応)
  async function quickCompleteCurrentTask(e) {
    if (e && e.stopPropagation) e.stopPropagation();
    var suggestions = window.suggestionsData || [];
    var suggestIdx = window.suggestIndex || 0;
    if (!suggestions || suggestions.length === 0) return;
    var s = suggestions[suggestIdx];
    if (!s || !s.id || !s.id.startsWith('task_')) return;
    var taskId = s.id.replace('task_', '');

    try {
      var fetchFn = window.authFetch || authFetch;
      var res = await fetchFn('/api/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'complete_task', task_id: taskId })
      });
      var result = await res.json();
      if (result.status === 'success') {
        showToast('✅ タスクを完了しました！', 2500, true);
        if (typeof window.addBondExp === 'function') window.addBondExp(15);
        if (typeof window.updateLifeSprite === 'function') window.updateLifeSprite('playing');
        if (typeof window.fetchStatus === 'function') setTimeout(window.fetchStatus, 300);
      } else {
        showToast('❌ 完了に失敗しました', 2000, false);
      }
    } catch (err) {
      console.error('[pet_ui] Quick complete error:', err);
      showToast('❌ 通信エラーが発生しました', 2000, false);
    }
  }

  function openBottomSheet(item, bodyHtml) {
    try {
      var sheet = document.getElementById('bottom-sheet');
      var overlay = document.getElementById('bottom-sheet-overlay');
      if (!sheet || !overlay) return;

      currentSheetItem = item;
      window.currentSheetItem = item;

      var tagEl = document.getElementById('sheet-tag');
      if (tagEl) tagEl.innerText = (item.icon || '💡') + ' ' + (item.tag || '詳細');
      
      var titleEl = document.getElementById('sheet-title');
      if (titleEl) titleEl.innerText = item.title || "";

      var bodyEl = document.getElementById('sheet-body');
      if (bodyEl) {
        if (typeof bodyHtml === 'string') {
          bodyEl.innerHTML = bodyHtml;
          bodyEl.style.maxHeight = '60vh';
        } else {
          bodyEl.innerText = item.description || "詳細情報はありません。";
        }
      }

      var completeBtn = document.getElementById('sheet-complete-btn');
      if (completeBtn) {
        if (item && item.source === 'tasks' && item.id && item.id.startsWith('task_')) {
          completeBtn.style.display = 'flex';
        } else {
          completeBtn.style.display = 'none';
        }
      }

      var matchUrl = item.description ? item.description.match(/https?:\/\/[^\s)\]"'>]+/)?.[0] : null;
      var targetUrl = typeof bodyHtml === 'string' ? null : (item.link || item.url || matchUrl);

      var linkBtn = document.getElementById('sheet-link-btn');
      if (linkBtn) {
        if (targetUrl) {
          linkBtn.style.display = 'flex';
          linkBtn.href = targetUrl;
        } else {
          linkBtn.style.display = 'none';
        }
      }

      overlay.classList.add('open');
      sheet.classList.add('open');
      if (navigator.vibrate) navigator.vibrate(20);
    } catch (e) {
      console.warn('[pet_ui] openBottomSheet failed:', e);
    }
  }

  async function onSheetCompleteTask() {
    var item = window.currentSheetItem || currentSheetItem;
    if (!item || !item.id) return;
    var taskId = item.id.replace('task_', '');
    if (!taskId) return;

    try {
      var fetchFn = window.authFetch || authFetch;
      var res = await fetchFn('/api/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'complete_task', task_id: taskId })
      });
      var result = await res.json();
      if (result.status === 'success') {
        closeBottomSheet();
        showToast('✅ タスクを完了しました！', 2500, true);
        if (typeof window.addBondExp === 'function') window.addBondExp(15);
        if (typeof window.updateLifeSprite === 'function') window.updateLifeSprite('playing');
        if (typeof window.fetchStatus === 'function') window.fetchStatus();
      } else {
        showToast('❌ タスク完了に失敗しました', 2000, false);
      }
    } catch (e) {
      console.error('[pet_ui] Task complete error:', e);
      showToast('❌ 通信エラーが発生しました', 2000, false);
    }
  }

  function closeBottomSheet() {
    var sheet = document.getElementById('bottom-sheet');
    var overlay = document.getElementById('bottom-sheet-overlay');
    if (sheet) sheet.classList.remove('open');
    if (overlay) overlay.classList.remove('open');
    currentSheetItem = null;
    window.currentSheetItem = null;
  }

  // 👾 秘密の部屋（サークル暗転トランジション）
  function triggerSecretRoomIris(e) {
    if (e && e.stopPropagation) e.stopPropagation();
    try {
      var overlay = document.getElementById('iris-transition-overlay');
      var hole = overlay ? overlay.querySelector('.iris-hole') : null;

      if (!overlay || !hole) {
        if (window.PixelDefense) window.PixelDefense.show();
        return;
      }

      if (overlay.style.display === 'block') return;

      var x = 85;
      var y = 15;
      if (e && typeof e.clientX === 'number' && typeof e.clientY === 'number') {
        x = (e.clientX / window.innerWidth) * 100;
        y = (e.clientY / window.innerHeight) * 100;
      }
      overlay.style.setProperty('--iris-x', x.toFixed(1) + '%');
      overlay.style.setProperty('--iris-y', y.toFixed(1) + '%');
      if (navigator.vibrate) navigator.vibrate(30);

      overlay.className = 'iris-transition-overlay';
      overlay.style.display = 'block';

      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          overlay.className = 'iris-transition-overlay closing';
          setTimeout(function () {
            try {
              if (window.PixelDefense) {
                window.PixelDefense.show();
              } else {
                showToast('👾 秘密の部屋を起動中...', 2000, true);
              }
            } finally {
              overlay.className = 'iris-transition-overlay opening';
              setTimeout(function () {
                overlay.className = 'iris-transition-overlay';
                overlay.style.display = 'none';
              }, 450);
            }
          }, 400);
        });
      });
    } catch (err) {
      console.warn('[pet_ui] triggerSecretRoomIris failed:', err);
    }
  }

  // サジェストカードのタッチスワイプ（左右フリック）機能
  function setupSuggestSwipe() {
    var card = document.getElementById('suggest-card');
    if (!card) return;

    var startX = 0;
    var startY = 0;
    var isSwiping = false;

    card.addEventListener('touchstart', function (e) {
      if (e.target.closest('.btn-suggest-nav') || e.target.closest('.btn-suggest-quick-complete')) {
        return;
      }
      if (e.touches.length === 1) {
        startX = e.touches[0].clientX;
        startY = e.touches[0].clientY;
        isSwiping = true;
      }
    }, { passive: true });

    card.addEventListener('touchend', function (e) {
      if (!isSwiping) return;
      isSwiping = false;
      if (e.changedTouches.length === 1) {
        var diffX = e.changedTouches[0].clientX - startX;
        var diffY = e.changedTouches[0].clientY - startY;
        if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 25) {
          if (diffX < 0) {
            nextSuggest();
          } else {
            prevSuggest();
          }
        }
      }
    }, { passive: true });
  }

  // =============================================================================
  // 4. イベントバナー ＆ 承認操作
  // =============================================================================
  var _bannerSwipeStartX = 0;
  var _bannerSwipeDelta = 0;

  function setupBannerSwipe() {
    var banner = document.getElementById('active-event-banner');
    if (!banner) return;
    banner.addEventListener('touchstart', function (e) {
      _bannerSwipeStartX = e.touches[0].clientX;
      _bannerSwipeDelta = 0;
      banner.style.transition = 'none';
    }, { passive: true });

    banner.addEventListener('touchmove', function (e) {
      _bannerSwipeDelta = e.touches[0].clientX - _bannerSwipeStartX;
      if (_bannerSwipeDelta > 0) {
        banner.style.transform = 'translateX(' + (_bannerSwipeDelta * 0.5) + 'px)';
        banner.style.opacity = Math.max(0, 1 - _bannerSwipeDelta / 200);
      }
    }, { passive: true });

    banner.addEventListener('touchend', function () {
      banner.style.transition = 'transform 0.25s ease, opacity 0.25s ease';
      if (_bannerSwipeDelta > 80) {
        banner.style.transform = 'translateX(120%)';
        banner.style.opacity = '0';
        setTimeout(function () {
          if (window.currentActiveEvent && window.currentActiveEvent.type === 'completed') {
            dismissCompleted();
          } else {
            _hideBanner();
          }
        }, 250);
      } else {
        banner.style.transform = '';
        banner.style.opacity = '1';
      }
    }, { passive: true });
  }

  function dismissCompleted(e) {
    if (e && e.stopPropagation) e.stopPropagation();
    try {
      if (window.currentActiveEvent && window.currentActiveEvent.timestamp) {
        sessionStorage.setItem('dismissed_completed_' + window.currentActiveEvent.timestamp, '1');
      }
      _hideBanner();
      if (typeof window.fetchStatus === 'function') window.fetchStatus();
    } catch (err) {
      console.warn('[pet_ui] dismissCompleted failed:', err);
    }
  }

  function _hideBanner() {
    window.currentActiveEvent = null;
    window.currentApprovalRequest = null;
    var banner = document.getElementById('active-event-banner');
    if (banner) {
      banner.style.display = 'none';
      banner.style.opacity = '1';
      banner.style.transform = '';
      banner.style.transition = '';
    }
    var actions = document.getElementById('banner-actions');
    if (actions) actions.style.display = 'none';
    var dismissBtn = document.getElementById('banner-dismiss-btn');
    if (dismissBtn) dismissBtn.style.display = 'none';
  }

  /** 承認シート（コマンド全文 ＆ 大ボタンで承認/却下） */
  function openApprovalSheet() {
    var req = window.currentApprovalRequest;
    if (!req) return;
    var isStrict = (req.risk_level === 'strict');
    var warningHtml = isStrict
      ? '<div class="note-item" style="border-left: 3px solid #FF5252; background: rgba(255, 82, 82, 0.15);"><div class="note-title" style="color:#FF5252;">🚨 破壊的変更の警告</div><div class="note-desc">git reset / rm / drop table などの重大操作が含まれる可能性があります。コマンド内容を必ず確認してください。</div></div>'
      : '';
    var commandHtml = req.command
      ? '<div class="note-item"><div class="note-title">⌨️ 実行コマンド</div><div class="note-desc" style="white-space: pre-wrap;">' + escapeHtml(req.command) + '</div></div>'
      : '';
    var html = warningHtml + commandHtml +
      '<div class="note-item"><div class="note-title">🛡️ このコマンドの実行を許可しますか？</div><div class="note-desc">イヤホンの再生ボタンでも承認できます</div></div>' +
      '<div class="approval-sheet-actions">' +
      '<button class="btn-approve" onclick="closeBottomSheet(); respondApproval(\'approve\')">✅ 承認する</button>' +
      '<button class="btn-deny" onclick="closeBottomSheet(); respondApproval(\'deny\')">🛑 却下する</button>' +
      '</div>';
    var sheetIcon = isStrict ? '🚨' : '🛡️';
    var sheetTag = isStrict ? '高リスク承認' : '承認要請';
    openBottomSheet({ icon: sheetIcon, tag: sheetTag, title: req.summary || 'コマンド実行の承認' }, html);
  }

  /** 質問シート（選択肢を大ボタンで表示） */
  function openQuestionSheet() {
    var req = window.currentApprovalRequest;
    if (!req) return;
    var choices = req.choices || [];
    var choicesHtml = '';
    if (choices.length > 0) {
      choicesHtml = choices.map(function (c, i) {
        return '<button class="btn-approve" onclick="closeBottomSheet(); respondChoice(' + i + ')">' + (i+1) + '. ' + escapeHtml(c) + '</button>';
      }).join('');
    } else {
      choicesHtml = '<div class="note-item"><div class="note-desc">自由回答はPC側でお願いします</div></div>';
    }
    var html = '<div class="note-item"><div class="note-title">❓ ' + escapeHtml(req.title || req.question || '') + '</div></div>' +
      '<div class="approval-sheet-actions" style="flex-direction:column;gap:6px;">' +
      choicesHtml +
      '</div>';
    openBottomSheet({ icon: '❓', tag: '質問', title: (req.agent_name || 'AI Agent') + ' からの質問' }, html);
  }

  /** 質問シートの選択肢ボタンから呼ばれるヘルパー */
  function respondChoice(index) {
    var req = window.currentApprovalRequest;
    if (!req || !req.choices || !req.choices[index]) return;
    respondApproval('answered', null, req.choices[index]);
  }

  /** 承認/却下/回答をサーバーへ送信する */
  async function respondApproval(decision, ev, answerText) {
    if (ev && ev.stopPropagation) ev.stopPropagation();
    var req = window.currentApprovalRequest;
    if (!req) return;
    if (typeof window.stopAlertChime === 'function') window.stopAlertChime();
    if (navigator.vibrate) navigator.vibrate(60);

    if (req && req.request_id && window._resolvedRequestIds) {
      window._resolvedRequestIds.add(req.request_id);
      if (window._resolvedRequestIds.size > 100) {
        var oldest = window._resolvedRequestIds.values().next().value;
        window._resolvedRequestIds.delete(oldest);
      }
    }

    try {
      var fetchFn = window.authFetch || authFetch;
      var res = await fetchFn('/api/agent/respond', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request_id: req.request_id, decision: decision, message: answerText || '' })
      });

      if (res.ok) {
        var data = await res.json().catch(function () { return {}; });
        if (data.status === 'expired') {
          showToast('⏰ この質問・要請は期限切れです');
          window.currentApprovalRequest = null;
          window.currentActiveEvent = null;
          _hideBanner();
          if (typeof window.fetchStatus === 'function') window.fetchStatus();
          return;
        }
        if (data.status === 'error') {
          showToast('🛑 ' + (data.message || '自己承認等のエラーで拒否されました'));
          if (typeof window.fetchStatus === 'function') window.fetchStatus();
          return;
        }
        if (data.status === 'not_found') {
          showToast('⚠️ 対象の要請が見つかりません（既に処理されたか取消されました）');
          window.currentApprovalRequest = null;
          window.currentActiveEvent = null;
          _hideBanner();
          if (typeof window.fetchStatus === 'function') window.fetchStatus();
          return;
        }
        window.currentApprovalRequest = null;
        window.currentActiveEvent = null;
        _hideBanner();

        if (typeof window.playDecisionSound === 'function') {
          window.playDecisionSound(decision === 'approve');
        }

        var bubble = document.getElementById('speech-bubble');
        if (decision === 'approve') {
          if (bubble) bubble.innerText = '承知いたしました！作業を続行します(｀・ω・´)ゞ';
        } else if (decision === 'answered') {
          if (bubble) bubble.innerText = '了解です！回答を反映して進めます✨';
        } else {
          if (bubble) bubble.innerText = '🛑 却下を確認しました。軌道修正します！';
        }

        // PC側ペットにもリアクション通知
        fetchFn('/api/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'pet_reaction', state: decision === 'approve' ? 'focus' : 'care', duration_ms: 3000 })
        }).catch(function (err) { console.debug('Pet reaction failed:', err); });
      } else {
        showToast('⚠️ 送信に失敗しました');
      }
    } catch (err) {
      console.debug('Respond error:', err);
      showToast('⚠️ 通信エラー');
    }
    if (typeof window.fetchStatus === 'function') window.fetchStatus();
  }

  /** イヤホンの再生/一時停止ボタンを「承認」として割り当てる */
  function setupMediaKeyApproval() {
    if (!('mediaSession' in navigator)) return;
    var handleMediaKey = function () {
      if (window.currentApprovalRequest) respondApproval('approve');
    };
    try { navigator.mediaSession.setActionHandler('play', handleMediaKey); } catch (e) { /* pass */ }
    try { navigator.mediaSession.setActionHandler('pause', handleMediaKey); } catch (e) { /* pass */ }
    try { navigator.mediaSession.setActionHandler('nexttrack', handleMediaKey); } catch (e) { /* pass */ }
  }

  // =============================================================================
  // 5. 時計 ＆ ポモドーロ
  // =============================================================================
  function updateClock() {
    try {
      var now = new Date();
      var h = String(now.getHours()).padStart(2, '0');
      var m = String(now.getMinutes()).padStart(2, '0');
      var s = String(now.getSeconds()).padStart(2, '0');
      var clockEl = document.getElementById('clock-display');
      if (clockEl) clockEl.innerText = h + ':' + m + ':' + s;
    } catch (e) {
      console.warn('[pet_ui] updateClock failed:', e);
    }
  }
  setInterval(updateClock, 1000);
  updateClock();

  function togglePomodoro() {
    var pomo = window.currentPomodoro;
    var isActive = pomo && pomo.active;
    var payload = isActive
      ? { action: 'stop_pomodoro' }
      : { action: 'start_pomodoro', minutes: 25 };
    var fetchFn = window.authFetch || authFetch;
    fetchFn('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(function () {
      if (typeof window.fetchStatus === 'function') window.fetchStatus();
    }).catch(function (err) { console.debug('Pomodoro action failed:', err); });
    if (navigator.vibrate) navigator.vibrate(40);
  }

  // =============================================================================
  // 6. 🤖 エージェント状態ライブバッジ (Phase H)
  // =============================================================================
  var AGENT_BADGE_STYLES = {
    coding:           { cls: 'a-coding',   icon: '🟢', suffix: 'Coding... 🔥' },
    thinking:         { cls: 'a-thinking', icon: '🟡', suffix: 'Thinking... 🤔' },
    waiting_approval: { cls: 'a-waiting',  icon: '🟣', suffix: 'Waiting Approval 🚨' },
    success:          { cls: 'a-success',  icon: '✅', suffix: 'Done ✨' }
  };

  var currentAgentBadgeState = '';

  function updateAgentActivityBadge(activity) {
    var badge = document.getElementById('agent-live-badge');
    if (!badge) return;
    var isActive = !!(activity && activity.is_active);
    var state = isActive ? String(activity.state || '') : '';
    var conf = AGENT_BADGE_STYLES[state];
    if (!isActive || !conf) {
      if (badge.style.display !== 'none') {
        badge.style.display = 'none';
        currentAgentBadgeState = '';
      }
      return;
    }
    var agentName = String(activity.agent_name || 'AI Agent').trim() || 'AI Agent';
    var stateKey = state + ':' + agentName;
    if (currentAgentBadgeState === stateKey) return;
    currentAgentBadgeState = stateKey;
    var textEl = document.getElementById('agent-live-badge-text');
    if (textEl) textEl.innerText = conf.icon + ' [' + agentName + '] ' + conf.suffix;
    badge.className = 'agent-live-badge ' + conf.cls;
    badge.style.display = 'flex';
  }

  // =============================================================================
  // 7. 朝会／終礼ブリーフィングバナーテキスト更新
  // =============================================================================
  function updateBriefingBannerText() {
    try {
      var hour = new Date().getHours();
      var isMorning = (hour < 15);
      var textEl = document.getElementById('briefing-banner-text');
      var iconEl = document.getElementById('briefing-banner-icon');
      if (textEl) textEl.innerText = isMorning ? "☀️ 今日の予定を確認する（朝会）" : "🌙 今日の振り返りをする（終礼）";
      if (iconEl) iconEl.innerText = isMorning ? "☀️" : "🌙";

      var quickTextEl = document.getElementById('briefing-quick-text');
      if (quickTextEl) {
        if (5 <= hour && hour < 12) {
          quickTextEl.innerText = "☀️ 今日の朝会ブリーフィングを聞く";
        } else if (12 <= hour && hour < 18) {
          quickTextEl.innerText = "⛅ 午後の進捗ブリーフィング";
        } else if (18 <= hour && hour < 24) {
          quickTextEl.innerText = "🌙 本日の終礼日報をまとめる";
        } else {
          quickTextEl.innerText = "🌙 深夜の振り返り・明日の準備";
        }
      }
    } catch (e) {
      console.warn('[pet_ui] updateBriefingBannerText failed:', e);
    }
  }

  // =============================================================================
  // 8. グローバル公開
  // =============================================================================
  window.showToast = showToast;
  window.escapeHtml = escapeHtml;
  window.renderSuggestionCard = renderSuggestionCard;
  window.nextSuggest = nextSuggest;
  window.prevSuggest = prevSuggest;
  window.onSuggestCardClick = onSuggestCardClick;
  window.quickCompleteCurrentTask = quickCompleteCurrentTask;
  window.openBottomSheet = openBottomSheet;
  window.onSheetCompleteTask = onSheetCompleteTask;
  window.closeBottomSheet = closeBottomSheet;
  window.triggerSecretRoomIris = triggerSecretRoomIris;
  window.setupSuggestSwipe = setupSuggestSwipe;
  window.setupBannerSwipe = setupBannerSwipe;
  window.dismissCompleted = dismissCompleted;
  window._hideBanner = _hideBanner;
  window.openApprovalSheet = openApprovalSheet;
  window.openQuestionSheet = openQuestionSheet;
  window.respondChoice = respondChoice;
  window.respondApproval = respondApproval;
  window.setupMediaKeyApproval = setupMediaKeyApproval;
  window.updateClock = updateClock;
  window.togglePomodoro = togglePomodoro;
  window.AGENT_BADGE_STYLES = AGENT_BADGE_STYLES;
  window.updateAgentActivityBadge = updateAgentActivityBadge;
  window.updateBriefingBannerText = updateBriefingBannerText;

})();

// 非モジュール環境での直接参照用トップレベル宣言
var showToast = window.showToast;
var escapeHtml = window.escapeHtml;
var renderSuggestionCard = window.renderSuggestionCard;
var nextSuggest = window.nextSuggest;
var prevSuggest = window.prevSuggest;
var onSuggestCardClick = window.onSuggestCardClick;
var quickCompleteCurrentTask = window.quickCompleteCurrentTask;
var openBottomSheet = window.openBottomSheet;
var onSheetCompleteTask = window.onSheetCompleteTask;
var closeBottomSheet = window.closeBottomSheet;
var triggerSecretRoomIris = window.triggerSecretRoomIris;
var setupSuggestSwipe = window.setupSuggestSwipe;
var setupBannerSwipe = window.setupBannerSwipe;
var dismissCompleted = window.dismissCompleted;
var _hideBanner = window._hideBanner;
var openApprovalSheet = window.openApprovalSheet;
var openQuestionSheet = window.openQuestionSheet;
var respondChoice = window.respondChoice;
var respondApproval = window.respondApproval;
var setupMediaKeyApproval = window.setupMediaKeyApproval;
var updateClock = window.updateClock;
var togglePomodoro = window.togglePomodoro;
var AGENT_BADGE_STYLES = window.AGENT_BADGE_STYLES;
var updateAgentActivityBadge = window.updateAgentActivityBadge;
var updateBriefingBannerText = window.updateBriefingBannerText;
