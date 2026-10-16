/**
 * AYUR-INTEL — Private Admin Console UI Module (Phase 5 Overhaul)
 *
 * Dark Botanical Intelligence SaaS System
 * Implements Institutional Oversight:
 * - Persistent, isolated Admin Console password lock
 * - Full-screen background blur when locked with center-screen lock card
 * - First-time console password setup, unlock, and recovery flows
 * - 15-minute inactivity auto-lock and explicit lock controls
 * - In-console change console password flow
 * - 8-KPI responsive overview grid
 * - 4 Management Sections / Tabs:
 *     1. User Directory & Sessions (horizontal cards without avatar circles)
 *     2. Device-Level Access Approval Queue
 *     3. System-Wide Active Session Management (global concurrent sessions)
 *     4. Immutable System Audit Log Inspection
 * - User detail sliding side drawer with complete session history & danger zone
 */

(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Module State
  // ---------------------------------------------------------------------------
  var state = {
    activeTab: 'users', // 'users' | 'requests' | 'sessions' | 'audit'

    // Users Directory
    users: [],
    totalUsers: 0,
    metrics: null,
    userPage: 1,
    userLimit: 12,
    userQuery: '',
    statusFilter: 'all', // 'all' | 'online' | 'offline' | 'active' | 'inactive' | 'pending'
    userSort: 'presence', // 'presence' | 'recent' | 'newest' | 'name'

    // User Detail Side Drawer
    selectedUser: null,
    selectedUserSubtab: 'overview', // 'overview' | 'sessions' | 'requests' | 'controls'
    loadingUserDetail: false,

    // Access Requests Queue
    accessRequests: [],
    requestsTotal: 0,
    requestsPage: 1,
    requestsLimit: 10,
    requestsFilter: 'all', // 'all' | 'pending' | 'approved' | 'rejected'
    isRequestsLoading: false,

    // Global Active Sessions Tab
    allSessions: [],
    sessionsTotal: 0,
    sessionsPage: 1,
    sessionsLimit: 25,
    sessionsQuery: '',
    isSessionsLoading: false,

    // System Audit Logs
    auditLogs: [],
    auditTotal: 0,
    auditPage: 1,
    auditLimit: 25,
    auditUserQuery: '',
    auditActionFilter: '',
    auditStatusFilter: '',
    isAuditLoading: false,

    // Persistent Admin Console Password & Lock State
    isConfigured: true,
    isUnlocked: false,
    unlockExpiresAt: null,
    remainingSeconds: 0,
    lockMode: 'unlock', // 'unlock' | 'setup' | 'recover'
    lockError: null,
    lockSuccess: null,
    showChangePasswordModal: false,
    changePasswordError: null,

    // Inactivity & Activity Tracking
    lastActivityTime: Date.now(),
    inactivityTimerId: null,
    durationTimerId: null,

    // Global View State
    isLoading: false,
    error: null,
    isUnauthorized: false,

    // Generic Confirmation Dialog State
    confirmation: null // { title, message, warning, confirmText, isDanger, onConfirm }
  };

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function formatDate(isoStr) {
    if (!isoStr) return '—';
    try {
      var d = new Date(isoStr);
      if (isNaN(d.getTime())) return isoStr;
      return d.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (_) {
      return isoStr;
    }
  }

  function formatRelativeTime(isoStr) {
    if (!isoStr) return '—';
    try {
      var d = new Date(isoStr);
      if (isNaN(d.getTime())) return isoStr;
      var now = Date.now();
      var diffSec = Math.max(0, Math.floor((now - d.getTime()) / 1000));
      if (diffSec < 45) return 'just now';
      var min = Math.floor(diffSec / 60);
      if (min < 60) return min + (min === 1 ? ' min ago' : ' mins ago');
      var hr = Math.floor(min / 60);
      if (hr < 24) return hr + (hr === 1 ? ' hr ago' : ' hrs ago');
      var days = Math.floor(hr / 24);
      if (days < 7) return days + (days === 1 ? ' day ago' : ' days ago');
      return formatDate(isoStr);
    } catch (_) {
      return isoStr;
    }
  }

  function formatDuration(sec) {
    if (sec === null || sec === undefined || isNaN(sec)) return '0 min';
    var totalSeconds = Math.max(0, Math.floor(sec));
    var m = Math.floor(totalSeconds / 60);
    var h = Math.floor(m / 60);
    m = m % 60;
    var d = Math.floor(h / 24);
    h = h % 24;
    if (d > 0) return d + 'd ' + h + 'h';
    if (h > 0) return h + 'h ' + (m > 0 ? m + 'm' : '');
    if (m > 0) return m + ' min';
    return '< 1 min';
  }

  function calculatePasswordStrength(pwd) {
    if (!pwd || pwd.length === 0) return { score: 0, label: 'empty', class: '' };
    var score = 0;
    if (pwd.length >= 12) score += 2;
    else if (pwd.length >= 8) score += 1;
    if (/[A-Z]/.test(pwd)) score += 1;
    if (/[a-z]/.test(pwd)) score += 1;
    if (/[0-9]/.test(pwd)) score += 1;
    if (/[^A-Za-z0-9]/.test(pwd)) score += 1;

    if (score <= 2) return { score: 1, label: 'Weak (min 12 chars required)', class: 'weak' };
    if (score <= 4) return { score: 2, label: 'Fair (add symbols/numbers)', class: 'fair' };
    if (score <= 5) return { score: 3, label: 'Good', class: 'good' };
    return { score: 4, label: 'Strong Botanical Hash', class: 'strong' };
  }

  function showToast(msg, type) {
    if (typeof window.showToast === 'function') {
      window.showToast(msg, type || 'info');
    } else if (window.AYUR_AUTH && typeof window.AYUR_AUTH.showToastMsg === 'function') {
      window.AYUR_AUTH.showToastMsg(msg, type || 'info');
    } else {
      console.log('[' + (type || 'info').toUpperCase() + '] ' + msg);
    }
  }

  // ---------------------------------------------------------------------------
  // API Calls & Inactivity Enforcement
  // ---------------------------------------------------------------------------

  async function callApi(url, opts) {
    var options = Object.assign({}, opts || {});
    var headers = Object.assign({}, options.headers || {});

    // Bearer Token
    var token = (window.AYUR_AUTH && typeof window.AYUR_AUTH.getToken === 'function')
      ? window.AYUR_AUTH.getToken()
      : '';
    if (token && !headers['Authorization']) {
      headers['Authorization'] = 'Bearer ' + token;
    }

    // Admin Unlock Token
    var unlockToken = localStorage.getItem('ayur_admin_unlock_token');
    if (unlockToken && !headers['X-Admin-Unlock-Token']) {
      headers['X-Admin-Unlock-Token'] = unlockToken;
    }

    options.headers = headers;

    var resp = await fetch(url, options);
    if (!resp.ok) {
      var errText = await resp.text();
      var errObj = null;
      try { errObj = JSON.parse(errText); } catch (_) {}
      var msg = (errObj && (errObj.detail || errObj.message || errObj.error)) || errText || ('HTTP ' + resp.status);

      // Handle HTTP 423 Locked (Elevated Admin Password Required)
      if (resp.status === 423) {
        state.isUnlocked = false;
        var isCfg = resp.headers.get('X-Admin-Configured');
        if (isCfg !== null) {
          state.isConfigured = (isCfg === 'true');
        }
        state.lockMode = state.isConfigured ? 'unlock' : 'setup';
        refreshView();
        showToast('Elevated Admin Console access locked. Authentication required.', 'warning');
      }

      var err = new Error(msg);
      err.status = resp.status;
      err.data = errObj;

      if (resp.status === 401 && window.AYUR_AUTH && typeof window.AYUR_AUTH.handleSessionExpired === 'function') {
        window.AYUR_AUTH.handleSessionExpired(msg);
      }
      throw err;
    }
    return await resp.json();
  }

  function recordUserActivity() {
    state.lastActivityTime = Date.now();
  }

  function setupInactivityWatcher() {
    if (state.inactivityTimerId) {
      clearInterval(state.inactivityTimerId);
      state.inactivityTimerId = null;
    }

    // Listen to user interactions across the page
    var events = ['mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart'];
    events.forEach(function (evt) {
      window.addEventListener(evt, recordUserActivity, { passive: true });
    });

    // Check inactivity every 10 seconds
    state.inactivityTimerId = setInterval(function () {
      if (!state.isUnlocked) return;
      var idleMs = Date.now() - state.lastActivityTime;
      var maxIdleMs = 15 * 60 * 1000; // 15 minutes
      if (idleMs >= maxIdleMs) {
        executeLock(true);
      }
    }, 10000);
  }

  // ---------------------------------------------------------------------------
  // Data Fetching & State Synchronization
  // ---------------------------------------------------------------------------

  async function checkUnlockStatus() {
    try {
      var status = await callApi('/api/admin/unlock-status');
      state.isConfigured = !!(status && status.is_configured);
      state.isUnlocked = !!(status && status.is_unlocked);
      state.unlockExpiresAt = status && status.unlocked_until;
      state.remainingSeconds = (status && status.remaining_seconds) || 0;
      if (!state.isUnlocked) {
        state.lockMode = state.isConfigured ? 'unlock' : 'setup';
      }
    } catch (_) {
      state.isUnlocked = false;
    }
  }

  async function loadUsers(page) {
    if (page !== undefined) state.userPage = page;
    state.isLoading = true;
    state.error = null;
    state.isUnauthorized = false;
    refreshView();

    try {
      var offset = (state.userPage - 1) * state.userLimit;
      var params = '?limit=' + state.userLimit + '&offset=' + offset;

      if (state.userQuery && state.userQuery.trim()) {
        params += '&query=' + encodeURIComponent(state.userQuery.trim());
      }

      if (state.statusFilter === 'active' || state.statusFilter === 'inactive' || state.statusFilter === 'pending') {
        params += '&status=' + encodeURIComponent(state.statusFilter);
      }

      var [data, metrics] = await Promise.all([
        callApi('/api/admin/users' + params),
        callApi('/api/admin/metrics').catch(function () { return null; }),
        checkUnlockStatus().catch(function () {})
      ]);

      state.users = data.users || [];
      state.totalUsers = data.total || 0;
      if (metrics) state.metrics = metrics;
      state.isLoading = false;
      refreshView();
    } catch (e) {
      state.isLoading = false;
      if (e.status === 401 || e.status === 403) {
        clearData();
        state.isUnauthorized = true;
        showToast('Access denied: Administrator privileges required.', 'error');
      } else if (e.status !== 423) {
        state.error = e.message || 'Failed to load user directory.';
        showToast('Failed to load users: ' + state.error, 'error');
      }
      refreshView();
    }
  }

  async function loadUserDetail(userId) {
    state.loadingUserDetail = true;
    state.selectedUser = { id: userId, loading: true };
    refreshView();

    try {
      var data = await callApi('/api/admin/users/' + encodeURIComponent(userId));
      state.selectedUser = data;
      state.loadingUserDetail = false;
      refreshView();
    } catch (e) {
      state.loadingUserDetail = false;
      state.selectedUser = null;
      if (e.status !== 423) {
        showToast('Failed to load user details: ' + (e.message || 'Unknown error'), 'error');
      }
      refreshView();
    }
  }

  async function executeStatusChange(user, makeActive) {
    try {
      var res = await callApi('/api/admin/users/' + encodeURIComponent(user.id) + '/status', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: makeActive })
      });
      showToast(res.message || ('User successfully ' + (makeActive ? 'activated' : 'deactivated')), 'success');
      await loadUsers();
      if (state.selectedUser && state.selectedUser.id === user.id) {
        await loadUserDetail(user.id);
      }
    } catch (e) {
      if (e.status !== 423) {
        showToast('Status update failed: ' + (e.message || 'Server error'), 'error');
      }
    }
  }

  async function executeRevokeSession(userId, sessionId) {
    try {
      var res = await callApi('/api/admin/users/' + encodeURIComponent(userId) + '/sessions/' + encodeURIComponent(sessionId) + '/revoke', {
        method: 'POST'
      });
      showToast(res.message || 'Session revoked successfully.', 'success');
      if (state.selectedUser && state.selectedUser.id === userId) {
        await loadUserDetail(userId);
      }
      if (state.activeTab === 'sessions') {
        await loadAllSessions();
      }
      await loadUsers();
    } catch (e) {
      if (e.status !== 423) {
        showToast('Failed to revoke session: ' + (e.message || 'Server error'), 'error');
      }
    }
  }

  async function executeRevokeAllSessions(userId, userName) {
    try {
      var res = await callApi('/api/admin/users/' + encodeURIComponent(userId) + '/logout-all', {
        method: 'POST'
      });
      showToast(res.message || ('Revoked all active sessions for ' + userName), 'success');
      if (state.selectedUser && state.selectedUser.id === userId) {
        await loadUserDetail(userId);
      }
      if (state.activeTab === 'sessions') {
        await loadAllSessions();
      }
      await loadUsers();
    } catch (e) {
      if (e.status !== 423) {
        showToast('Failed to revoke all sessions: ' + (e.message || 'Server error'), 'error');
      }
    }
  }

  async function loadAccessRequests(page) {
    if (page !== undefined) state.requestsPage = page;
    state.isRequestsLoading = true;
    refreshView();

    try {
      var offset = (state.requestsPage - 1) * state.requestsLimit;
      var params = '?limit=' + state.requestsLimit + '&offset=' + offset;
      if (state.requestsFilter && state.requestsFilter !== 'all') {
        params += '&status=' + encodeURIComponent(state.requestsFilter);
      }

      var data = await callApi('/api/admin/requests' + params);
      state.accessRequests = data.requests || [];
      state.requestsTotal = data.total || 0;
      state.isRequestsLoading = false;
      refreshView();
    } catch (e) {
      state.isRequestsLoading = false;
      if (e.status !== 423) {
        showToast('Failed to load access requests: ' + (e.message || 'Server error'), 'error');
      }
      refreshView();
    }
  }

  async function executeApproveRequest(reqId, notes) {
    try {
      var res = await callApi('/api/admin/requests/' + encodeURIComponent(reqId) + '/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ review_notes: notes || 'Access request approved by administrator.' })
      });
      showToast(res.message || 'Access request approved. Account reactivated and device bound.', 'success');
      await loadAccessRequests();
      await loadUsers();
    } catch (e) {
      if (e.status !== 423) {
        showToast('Failed to approve request: ' + (e.message || 'Server error'), 'error');
      }
    }
  }

  async function executeRejectRequest(reqId, notes) {
    try {
      var res = await callApi('/api/admin/requests/' + encodeURIComponent(reqId) + '/reject', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ review_notes: notes || 'Access request rejected by administrator.' })
      });
      showToast(res.message || 'Access request rejected.', 'info');
      await loadAccessRequests();
      await loadUsers();
    } catch (e) {
      if (e.status !== 423) {
        showToast('Failed to reject request: ' + (e.message || 'Server error'), 'error');
      }
    }
  }

  async function loadAllSessions(page) {
    if (page !== undefined) state.sessionsPage = page;
    state.isSessionsLoading = true;
    refreshView();

    try {
      var offset = (state.sessionsPage - 1) * state.sessionsLimit;
      var params = '?limit=' + state.sessionsLimit + '&offset=' + offset;
      var data = await callApi('/api/admin/all-sessions' + params);
      state.allSessions = data.sessions || [];
      state.sessionsTotal = data.total || 0;
      state.isSessionsLoading = false;
      refreshView();
    } catch (e) {
      state.isSessionsLoading = false;
      if (e.status !== 423) {
        showToast('Failed to load global active sessions: ' + (e.message || 'Server error'), 'error');
      }
      refreshView();
    }
  }

  async function loadAuditLogs(page) {
    if (page !== undefined) state.auditPage = page;
    state.isAuditLoading = true;
    state.error = null;
    refreshView();

    try {
      var offset = (state.auditPage - 1) * state.auditLimit;
      var params = '?limit=' + state.auditLimit + '&offset=' + offset;
      if (state.auditUserQuery && state.auditUserQuery.trim()) {
        params += '&user_query=' + encodeURIComponent(state.auditUserQuery.trim());
      }
      if (state.auditActionFilter && state.auditActionFilter.trim()) {
        params += '&action=' + encodeURIComponent(state.auditActionFilter.trim());
      }
      if (state.auditStatusFilter && state.auditStatusFilter.trim()) {
        params += '&status=' + encodeURIComponent(state.auditStatusFilter.trim());
      }

      var data = await callApi('/api/admin/audit-logs' + params);
      state.auditLogs = data.logs || [];
      state.auditTotal = data.total || 0;
      state.isAuditLoading = false;
      refreshView();
    } catch (e) {
      state.isAuditLoading = false;
      if (e.status === 401 || e.status === 403) {
        state.isUnauthorized = true;
        state.auditLogs = [];
        showToast('Access denied: Administrator privileges required.', 'error');
      } else if (e.status !== 423) {
        showToast('Failed to load audit logs: ' + (e.message || 'Server error'), 'error');
      }
      refreshView();
    }
  }

  // ---------------------------------------------------------------------------
  // Console Password Lifecycle: Setup, Unlock, Change, Recover, Lock
  // ---------------------------------------------------------------------------

  async function executeSetupConsolePassword(accountPwd, consolePwd, confirmPwd) {
    state.lockError = null;
    if (!accountPwd) {
      state.lockError = 'Current account password is required to verify identity.';
      refreshView();
      return;
    }
    if (!consolePwd || consolePwd.length < 12) {
      state.lockError = 'New console password must be at least 12 characters long.';
      refreshView();
      return;
    }
    if (consolePwd !== confirmPwd) {
      state.lockError = 'Console passwords do not match.';
      refreshView();
      return;
    }

    try {
      var res = await callApi('/api/admin/setup-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_password: accountPwd,
          console_password: consolePwd,
          confirm_password: confirmPwd
        })
      });
      if (res && res.token) {
        localStorage.setItem('ayur_admin_unlock_token', res.token);
      }
      state.isConfigured = true;
      state.isUnlocked = true;
      state.unlockExpiresAt = res.unlocked_until;
      state.lockError = null;
      state.lastActivityTime = Date.now();
      showToast('Admin Console password set and elevated access active (15 minutes).', 'success');
      refreshView();
      loadUsers();
    } catch (e) {
      state.lockError = e.message || 'Failed to setup Admin Console password.';
      refreshView();
    }
  }

  async function executeUnlock(password) {
    state.lockError = null;
    if (!password) {
      state.lockError = 'Please enter your Admin Console password.';
      refreshView();
      return;
    }

    try {
      var res = await callApi('/api/admin/unlock', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: password })
      });
      if (res && res.token) {
        localStorage.setItem('ayur_admin_unlock_token', res.token);
      }
      state.isUnlocked = true;
      state.unlockExpiresAt = res.unlocked_until;
      state.lockError = null;
      state.lastActivityTime = Date.now();
      showToast('Administrator elevated access enabled (15 minutes).', 'success');
      refreshView();
      loadUsers();
    } catch (e) {
      state.lockError = e.message || 'Invalid administrator console password.';
      refreshView();
    }
  }

  async function executeRecoverConsolePassword(accountPwd, newConsolePwd, confirmPwd) {
    state.lockError = null;
    if (!accountPwd) {
      state.lockError = 'Account password is required for recovery.';
      refreshView();
      return;
    }
    if (!newConsolePwd || newConsolePwd.length < 12) {
      state.lockError = 'New console password must be at least 12 characters long.';
      refreshView();
      return;
    }
    if (newConsolePwd !== confirmPwd) {
      state.lockError = 'Console passwords do not match.';
      refreshView();
      return;
    }

    try {
      var res = await callApi('/api/admin/recover-console-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_password: accountPwd,
          new_console_password: newConsolePwd,
          confirm_console_password: confirmPwd
        })
      });
      if (res && res.token) {
        localStorage.setItem('ayur_admin_unlock_token', res.token);
      }
      state.isConfigured = true;
      state.isUnlocked = true;
      state.unlockExpiresAt = res.unlocked_until;
      state.lockMode = 'unlock';
      state.lockError = null;
      state.lastActivityTime = Date.now();
      showToast('Admin Console password recovered and access elevated (15 minutes).', 'success');
      refreshView();
      loadUsers();
    } catch (e) {
      state.lockError = e.message || 'Password recovery failed. Please verify your account password.';
      refreshView();
    }
  }

  async function executeChangeConsolePassword(currPwd, newPwd, confirmPwd) {
    state.changePasswordError = null;
    if (!currPwd) {
      state.changePasswordError = 'Current console password is required.';
      refreshView();
      return;
    }
    if (!newPwd || newPwd.length < 12) {
      state.changePasswordError = 'New console password must be at least 12 characters long.';
      refreshView();
      return;
    }
    if (newPwd !== confirmPwd) {
      state.changePasswordError = 'New passwords do not match.';
      refreshView();
      return;
    }

    try {
      var res = await callApi('/api/admin/change-console-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          current_password: currPwd,
          new_password: newPwd,
          confirm_password: confirmPwd
        })
      });
      if (res && res.token) {
        localStorage.setItem('ayur_admin_unlock_token', res.token);
      }
      state.showChangePasswordModal = false;
      state.changePasswordError = null;
      state.lastActivityTime = Date.now();
      showToast('Admin Console password changed successfully.', 'success');
      refreshView();
    } catch (e) {
      state.changePasswordError = e.message || 'Failed to change console password.';
      refreshView();
    }
  }

  async function executeLock(isAutoLock) {
    try {
      await callApi('/api/admin/lock', { method: 'POST' }).catch(function () {});
    } catch (_) {}
    localStorage.removeItem('ayur_admin_unlock_token');
    state.isUnlocked = false;
    state.unlockExpiresAt = null;
    state.lockMode = state.isConfigured ? 'unlock' : 'setup';
    if (isAutoLock) {
      showToast('Console auto-locked after 15 minutes of inactivity.', 'info');
    } else {
      showToast('Admin Console locked.', 'info');
    }
    refreshView();
  }

  function refreshView() {
    var content = document.getElementById('content');
    if (content && window.AYUR && window.AYUR.state && window.AYUR.state.view === 'admin-console') {
      content.innerHTML = renderAdminConsole();
      bindEvents();
    }
  }

  // ---------------------------------------------------------------------------
  // HTML Rendering
  // ---------------------------------------------------------------------------

  function renderAdminConsole() {
    // 1. Unauthorized Access
    if (state.isUnauthorized) {
      return ''
        + '<div class="admin-console-wrapper">'
        + '  <div class="admin-unauthorized-card">'
        + '    <div class="admin-unauthorized-icon"><span class="material-symbols-outlined">gpp_maybe</span></div>'
        + '    <h2>Access Restricted</h2>'
        + '    <p>Administrative privileges are strictly required to view this area. Your request was rejected by the server authorization engine.</p>'
        + '    <button class="btn btn-primary" onclick="if(window.AYUR) window.AYUR.navigateTo(\'dashboard\');">'
        + '      <span class="material-symbols-outlined">arrow_back</span> Return to Dashboard'
        + '    </button>'
        + '  </div>'
        + '</div>';
    }

    var currentUser = (window.AYUR_AUTH && typeof window.AYUR_AUTH.getUser === 'function')
      ? window.AYUR_AUTH.getUser()
      : null;

    // Filter users client-side for presence
    var displayUsers = state.users.slice();
    if (state.statusFilter === 'online') {
      displayUsers = displayUsers.filter(function (u) { return u.is_online; });
    } else if (state.statusFilter === 'offline') {
      displayUsers = displayUsers.filter(function (u) { return !u.is_online; });
    }

    // Deterministic sorting (Online users first by default)
    displayUsers.sort(function (a, b) {
      if (state.userSort === 'presence') {
        if (a.is_online && !b.is_online) return -1;
        if (!a.is_online && b.is_online) return 1;
        var timeA = new Date(a.last_active_at || a.last_opened_at || a.created_at).getTime() || 0;
        var timeB = new Date(b.last_active_at || b.last_opened_at || b.created_at).getTime() || 0;
        return timeB - timeA;
      } else if (state.userSort === 'recent') {
        var tA = new Date(a.last_active_at || a.last_opened_at || a.created_at).getTime() || 0;
        var tB = new Date(b.last_active_at || b.last_opened_at || b.created_at).getTime() || 0;
        return tB - tA;
      } else if (state.userSort === 'newest') {
        var cA = new Date(a.created_at).getTime() || 0;
        var cB = new Date(b.created_at).getTime() || 0;
        return cB - cA;
      } else if (state.userSort === 'name') {
        var nameA = (a.display_name || a.username || '').toLowerCase();
        var nameB = (b.display_name || b.username || '').toLowerCase();
        return nameA.localeCompare(nameB);
      }
      return 0;
    });

    // 8 Overview Metrics
    var m = state.metrics || {};
    var totalUsersCount = m.total_users !== undefined ? m.total_users : state.totalUsers;
    var onlineUsersCount = m.online_users !== undefined ? m.online_users : state.users.filter(function (u) { return u.is_online; }).length;
    var offlineUsersCount = m.offline_users !== undefined ? m.offline_users : Math.max(0, totalUsersCount - onlineUsersCount);
    var activeAccountsCount = m.active_accounts !== undefined ? m.active_accounts : state.users.filter(function (u) { return u.is_active; }).length;
    var deactivatedAccountsCount = m.deactivated_accounts !== undefined ? m.deactivated_accounts : state.users.filter(function (u) { return !u.is_active; }).length;
    var pendingRequestsCount = m.pending_access_requests !== undefined ? m.pending_access_requests : 0;
    var totalActiveSessions = m.total_active_sessions !== undefined ? m.total_active_sessions : state.sessionsTotal;
    var auditEvents24h = m.recent_audit_events_24h !== undefined ? m.recent_audit_events_24h : state.auditTotal;

    var isLocked = !state.isUnlocked;

    var html = ''
      // The wrapper: gets .admin-blurred-content when locked
      + '<div class="admin-console-wrapper ' + (isLocked ? 'admin-blurred-content' : '') + '">'
      // Institutional Oversight Header
      + '  <div class="admin-header">'
      + '    <div class="admin-header-titles">'
      + '      <div class="admin-header-badge">'
      + '        <span class="material-symbols-outlined">shield</span> Security Administration'
      + '      </div>'
      + '      <h1>Institutional Oversight</h1>'
      + '      <p>Manage verified accounts, review device sessions, control access, and investigate security activity.</p>'
      + '    </div>'
      + '    <div class="admin-header-actions-group">'
      + (state.isUnlocked
          ? '<span class="admin-elevated-pill" title="Protected operations elevated for 15 minutes"><span class="material-symbols-outlined">lock_open</span> Elevated Active</span>'
            + '<button class="btn btn-secondary btn-sm" id="admin-change-pwd-btn" title="Update console password"><span class="material-symbols-outlined">password</span> Change Password</button>'
            + '<button class="btn btn-secondary btn-sm" id="admin-lock-btn" title="Lock console immediately"><span class="material-symbols-outlined">lock</span> Lock Console</button>'
          : '<span class="admin-locked-pill" title="Protected Mode: Password required to view and modify"><span class="material-symbols-outlined">lock</span> Protected Mode</span>'
            + '<button class="btn btn-primary btn-sm" id="admin-unlock-trigger-btn" title="Authenticate to elevate access"><span class="material-symbols-outlined">lock_open</span> Elevate Access</button>'
        )
      + '      <button class="btn btn-secondary btn-sm" id="admin-refresh-btn" title="Refresh backend data">'
      + '        <span class="material-symbols-outlined">sync</span> Refresh Data'
      + '      </button>'
      + '    </div>'
      + '  </div>'

      // Overview 8-KPI Responsive Grid
      + '  <div class="admin-kpi-grid admin-kpi-grid-8">'
      // 1. Total Registered Accounts
      + '    <div class="admin-kpi-card">'
      + '      <div class="admin-kpi-icon kpi-icon-total"><span class="material-symbols-outlined">people</span></div>'
      + '      <div class="admin-kpi-data">'
      + '        <div class="admin-kpi-val">' + totalUsersCount + '</div>'
      + '        <div class="admin-kpi-lbl">Total Registered Accounts</div>'
      + '        <div class="admin-kpi-sub">Institutional directory</div>'
      + '      </div>'
      + '    </div>'

      // 2. Currently Online
      + '    <div class="admin-kpi-card kpi-card-online">'
      + '      <div class="admin-kpi-icon kpi-icon-online"><span class="material-symbols-outlined">sensors</span></div>'
      + '      <div class="admin-kpi-data">'
      + '        <div class="admin-kpi-val"><span class="presence-pulse-dot inline"></span>' + onlineUsersCount + '</div>'
      + '        <div class="admin-kpi-lbl">Currently Online</div>'
      + '        <div class="admin-kpi-sub">Active in idle window</div>'
      + '      </div>'
      + '    </div>'

      // 3. Offline Accounts
      + '    <div class="admin-kpi-card">'
      + '      <div class="admin-kpi-icon kpi-icon-offline"><span class="material-symbols-outlined">nightlight</span></div>'
      + '      <div class="admin-kpi-data">'
      + '        <div class="admin-kpi-val">' + offlineUsersCount + '</div>'
      + '        <div class="admin-kpi-lbl">Offline Accounts</div>'
      + '        <div class="admin-kpi-sub">Signed out or idle</div>'
      + '      </div>'
      + '    </div>'

      // 4. Active Accounts
      + '    <div class="admin-kpi-card">'
      + '      <div class="admin-kpi-icon kpi-icon-active"><span class="material-symbols-outlined">verified_user</span></div>'
      + '      <div class="admin-kpi-data">'
      + '        <div class="admin-kpi-val">' + activeAccountsCount + '</div>'
      + '        <div class="admin-kpi-lbl">Active Accounts</div>'
      + '        <div class="admin-kpi-sub">Authorized system access</div>'
      + '      </div>'
      + '    </div>'

      // 5. Deactivated Accounts
      + '    <div class="admin-kpi-card">'
      + '      <div class="admin-kpi-icon kpi-icon-deactivated"><span class="material-symbols-outlined">block</span></div>'
      + '      <div class="admin-kpi-data">'
      + '        <div class="admin-kpi-val">' + deactivatedAccountsCount + '</div>'
      + '        <div class="admin-kpi-lbl">Deactivated Accounts</div>'
      + '        <div class="admin-kpi-sub">Access blocked</div>'
      + '      </div>'
      + '    </div>'

      // 6. Pending Access Requests
      + '    <div class="admin-kpi-card ' + (pendingRequestsCount > 0 ? 'kpi-card-pending-alert' : '') + '">'
      + '      <div class="admin-kpi-icon kpi-icon-pending"><span class="material-symbols-outlined">pending_actions</span></div>'
      + '      <div class="admin-kpi-data">'
      + '        <div class="admin-kpi-val">' + pendingRequestsCount + '</div>'
      + '        <div class="admin-kpi-lbl">Pending Access Requests</div>'
      + '        <div class="admin-kpi-sub">' + (pendingRequestsCount > 0 ? 'Requires administrator review' : 'Queue clear') + '</div>'
      + '      </div>'
      + '    </div>'

      // 7. Active Sessions
      + '    <div class="admin-kpi-card">'
      + '      <div class="admin-kpi-icon kpi-icon-sessions"><span class="material-symbols-outlined">devices</span></div>'
      + '      <div class="admin-kpi-data">'
      + '        <div class="admin-kpi-val">' + totalActiveSessions + '</div>'
      + '        <div class="admin-kpi-lbl">Active Sessions</div>'
      + '        <div class="admin-kpi-sub">Concurrent client tokens</div>'
      + '      </div>'
      + '    </div>'

      // 8. Security Events (Last 24 Hours)
      + '    <div class="admin-kpi-card">'
      + '      <div class="admin-kpi-icon kpi-icon-audit"><span class="material-symbols-outlined">policy</span></div>'
      + '      <div class="admin-kpi-data">'
      + '        <div class="admin-kpi-val">' + auditEvents24h + '</div>'
      + '        <div class="admin-kpi-lbl">Security Events (24h)</div>'
      + '        <div class="admin-kpi-sub">Privilege &amp; auth audits</div>'
      + '      </div>'
      + '    </div>'
      + '  </div>'

      // 4 Main Navigation Tabs
      + '  <div class="admin-tabs">'
      + '    <button class="admin-tab-btn ' + (state.activeTab === 'users' ? 'active' : '') + '" data-admin-tab="users">'
      + '      <span class="material-symbols-outlined">group</span> User Directory (' + state.totalUsers + ')'
      + '    </button>'
      + '    <button class="admin-tab-btn ' + (state.activeTab === 'requests' ? 'active' : '') + '" data-admin-tab="requests">'
      + '      <span class="material-symbols-outlined">assignment_late</span> Access Requests'
      + (pendingRequestsCount > 0 ? ' <span class="admin-tab-pill">' + pendingRequestsCount + '</span>' : '')
      + '    </button>'
      + '    <button class="admin-tab-btn ' + (state.activeTab === 'sessions' ? 'active' : '') + '" data-admin-tab="sessions">'
      + '      <span class="material-symbols-outlined">devices</span> Session Management (' + state.sessionsTotal + ')'
      + '    </button>'
      + '    <button class="admin-tab-btn ' + (state.activeTab === 'audit' ? 'active' : '') + '" data-admin-tab="audit">'
      + '      <span class="material-symbols-outlined">history</span> Security Audit Logs'
      + '    </button>'
      + '  </div>';

    // -------------------------------------------------------------------------
    // TAB 1: USER DIRECTORY (Horizontal User Cards without Initial Circles)
    // -------------------------------------------------------------------------
    if (state.activeTab === 'users') {
      var totalUserPages = Math.ceil(state.totalUsers / state.userLimit) || 1;
      var startIdx = (state.userPage - 1) * state.userLimit + 1;
      var endIdx = Math.min(state.userPage * state.userLimit, state.totalUsers);

      html += ''
        + '  <div class="admin-card">'
        + '    <div class="admin-filter-bar">'
        + '      <div class="admin-toolbar-row">'
        + '        <div class="admin-search-wrap">'
        + '          <span class="material-symbols-outlined">search</span>'
        + '          <input type="text" id="admin-user-search" class="admin-search-input" placeholder="Search by name, email, or username..." value="' + escapeHtml(state.userQuery) + '">'
        + '          ' + (state.userQuery ? '<button class="admin-clear-search-btn" id="admin-clear-search-btn" title="Clear search">×</button>' : '')
        + '        </div>'
        + '        <div class="admin-toolbar-controls">'
        + '          <select id="admin-status-filter" class="admin-select" title="Filter by status">'
        + '            <option value="all" ' + (state.statusFilter === 'all' ? 'selected' : '') + '>All Statuses</option>'
        + '            <option value="online" ' + (state.statusFilter === 'online' ? 'selected' : '') + '>Online Only</option>'
        + '            <option value="offline" ' + (state.statusFilter === 'offline' ? 'selected' : '') + '>Offline Only</option>'
        + '            <option value="active" ' + (state.statusFilter === 'active' ? 'selected' : '') + '>Active Accounts</option>'
        + '            <option value="inactive" ' + (state.statusFilter === 'inactive' ? 'selected' : '') + '>Deactivated Accounts</option>'
        + '            <option value="pending" ' + (state.statusFilter === 'pending' ? 'selected' : '') + '>Pending Approval</option>'
        + '          </select>'
        + '          <select id="admin-user-sort" class="admin-select" title="Sort order">'
        + '            <option value="presence" ' + (state.userSort === 'presence' ? 'selected' : '') + '>Online First &amp; Recent (Default)</option>'
        + '            <option value="recent" ' + (state.userSort === 'recent' ? 'selected' : '') + '>Most Recent Activity</option>'
        + '            <option value="newest" ' + (state.userSort === 'newest' ? 'selected' : '') + '>Newest Accounts</option>'
        + '            <option value="name" ' + (state.userSort === 'name' ? 'selected' : '') + '>Account Name (A–Z)</option>'
        + '          </select>'
        + '          <button class="btn btn-primary btn-sm" id="admin-search-submit-btn">'
        + '            <span class="material-symbols-outlined">filter_list</span> Apply'
        + '          </button>'
        + '        </div>'
        + '      </div>'
        + '    </div>'

        // Horizontal User Cards
        + '    <div class="admin-user-cards-list">';

      if (state.isLoading) {
        html += '<div class="admin-empty-cell"><div class="admin-spinner"></div> Loading user directory...</div>';
      } else if (displayUsers.length === 0) {
        html += '<div class="admin-empty-cell"><div class="admin-empty-icon"><span class="material-symbols-outlined">person_search</span></div><p>No user accounts match current criteria.</p></div>';
      } else {
        displayUsers.forEach(function (u) {
          var isSelf = currentUser && (currentUser.id === u.id || currentUser.public_id === u.id);
          var fullName = u.display_name || u.username;

          var statusBadge = '';
          if (u.has_pending_request) {
            statusBadge = '<span class="admin-badge badge-pending"><span class="admin-badge-dot"></span> Approval Pending</span>';
          } else if (u.is_active) {
            statusBadge = '<span class="admin-badge badge-active"><span class="admin-badge-dot"></span> Active</span>';
          } else {
            statusBadge = '<span class="admin-badge badge-inactive"><span class="admin-badge-dot"></span> Deactivated</span>';
          }

          var roleBadgeClass = u.role === 'admin' ? 'badge-admin' : 'badge-user';

          var presenceHtml = '';
          if (u.is_online) {
            presenceHtml = ''
              + '<div class="admin-presence-line online">'
              + '  <span class="presence-pulse-dot"></span>'
              + '  <span class="presence-status-text">Online · Last active ' + escapeHtml(formatRelativeTime(u.last_active_at)) + '</span>'
              + '  <span class="presence-duration-line live-duration" data-session-start="' + escapeHtml(u.session_started_at || '') + '">(Current: ' + escapeHtml(formatDuration(u.current_session_duration_seconds)) + ')</span>'
              + '</div>';
          } else {
            var openedText = u.last_opened_at ? ('Last opened ' + formatRelativeTime(u.last_opened_at)) : 'Last opened: Not available';
            var lastDurationText = (u.last_session_duration_seconds !== null && u.last_session_duration_seconds !== undefined)
              ? ('Last session: ' + formatDuration(u.last_session_duration_seconds))
              : 'Duration: Not recorded';
            presenceHtml = ''
              + '<div class="admin-presence-line offline">'
              + '  <span class="presence-static-dot"></span>'
              + '  <span class="presence-status-text">Offline · ' + escapeHtml(openedText) + '</span>'
              + '  <span class="presence-duration-line">(' + escapeHtml(lastDurationText) + ')</span>'
              + '</div>';
          }

          var cardClass = 'admin-user-card';
          if (u.has_pending_request) cardClass += ' user-card-pending';
          else if (u.is_online) cardClass += ' user-card-online';
          else if (!u.is_active) cardClass += ' user-card-deactivated';

          html += ''
            + '<div class="' + cardClass + '" data-user-id="' + escapeHtml(u.id) + '">'
            // Primary Identity (NO avatar initials circle)
            + '  <div class="admin-card-primary">'
            + '    <div class="admin-card-name-row">'
            + '      <span class="admin-card-name">' + escapeHtml(fullName) + '</span>'
            + (isSelf ? ' <span class="self-tag">(You)</span>' : '')
            + '      <span class="admin-badge ' + roleBadgeClass + '">' + escapeHtml(u.role) + '</span>'
            + '      ' + statusBadge
            + '    </div>'
            + '    <div class="admin-card-meta-row">'
            + '      <span class="admin-card-email">' + escapeHtml(u.email || '—') + '</span>'
            + '      <span class="admin-card-handle">@' + escapeHtml(u.username) + '</span>'
            + '    </div>'
            + '    ' + presenceHtml
            + '  </div>'

            // Secondary Metrics
            + '  <div class="admin-card-stats">'
            + '    <div class="admin-stat-item">'
            + '      <span class="admin-stat-value">' + (u.login_count || 0) + '</span>'
            + '      <span class="admin-stat-label">Logins Recorded</span>'
            + '    </div>'
            + '    <div class="admin-stat-item">'
            + '      <span class="admin-stat-value">' + (u.active_sessions_count || 0) + '</span>'
            + '      <span class="admin-stat-label">Active Sessions</span>'
            + '    </div>'
            + '    <div class="admin-stat-item">'
            + '      <span class="admin-stat-value">' + formatDate(u.created_at).split(',')[0] + '</span>'
            + '      <span class="admin-stat-label">Member Since</span>'
            + '    </div>'
            + '  </div>'

            // Right Affordance
            + '  <div class="admin-card-actions">'
            + '    <button class="btn btn-secondary btn-sm btn-view-details" data-user-id="' + escapeHtml(u.id) + '">'
            + '      View Details <span class="material-symbols-outlined">chevron_right</span>'
            + '    </button>'
            + '  </div>'
            + '</div>';
        });
      }

      html += ''
        + '    </div>'
        + '    <div class="admin-pagination">'
        + '      <div class="admin-pagination-info">'
        + '        Showing <strong>' + (state.totalUsers > 0 ? startIdx : 0) + '–' + endIdx + '</strong> of <strong>' + state.totalUsers + '</strong> user accounts'
        + '      </div>'
        + '      <div class="admin-pagination-btns">'
        + '        <button class="btn btn-secondary btn-sm" id="admin-user-prev" ' + (state.userPage <= 1 ? 'disabled' : '') + '>'
        + '          <span class="material-symbols-outlined">chevron_left</span> Previous'
        + '        </button>'
        + '        <span class="admin-page-indicator">Page ' + state.userPage + ' of ' + totalUserPages + '</span>'
        + '        <button class="btn btn-secondary btn-sm" id="admin-user-next" ' + (state.userPage >= totalUserPages ? 'disabled' : '') + '>'
        + '          Next <span class="material-symbols-outlined">chevron_right</span>'
        + '        </button>'
        + '      </div>'
        + '    </div>'
        + '  </div>';
    }

    // -------------------------------------------------------------------------
    // TAB 2: ACCESS REQUESTS QUEUE
    // -------------------------------------------------------------------------
    if (state.activeTab === 'requests') {
      var totalReqPages = Math.ceil(state.requestsTotal / state.requestsLimit) || 1;
      var reqStart = (state.requestsPage - 1) * state.requestsLimit + 1;
      var reqEnd = Math.min(state.requestsPage * state.requestsLimit, state.requestsTotal);

      html += ''
        + '  <div class="admin-card">'
        + '    <div class="admin-filter-bar">'
        + '      <div class="admin-toolbar-row">'
        + '        <div>'
        + '          <h3 style="font-size: 15px; font-weight: 700; color: #f2f7f4; margin-bottom: 2px;">Device-Level Access Approval Queue</h3>'
        + '          <p style="font-size: 12px; color: #94a39b;">Review sign-in requests from deactivated users and authorized cryptographic hardware fingerprints.</p>'
        + '        </div>'
        + '        <div class="admin-toolbar-controls">'
        + '          <select id="admin-requests-filter" class="admin-select">'
        + '            <option value="all" ' + (state.requestsFilter === 'all' ? 'selected' : '') + '>All Requests</option>'
        + '            <option value="pending" ' + (state.requestsFilter === 'pending' ? 'selected' : '') + '>Pending Review Only</option>'
        + '            <option value="approved" ' + (state.requestsFilter === 'approved' ? 'selected' : '') + '>Approved</option>'
        + '            <option value="rejected" ' + (state.requestsFilter === 'rejected' ? 'selected' : '') + '>Rejected</option>'
        + '          </select>'
        + '          <button class="btn btn-secondary btn-sm" id="admin-requests-refresh-btn">'
        + '            <span class="material-symbols-outlined">sync</span> Refresh'
        + '          </button>'
        + '        </div>'
        + '      </div>'
        + '    </div>'
        + '    <div class="admin-requests-list">';

      if (state.isRequestsLoading) {
        html += '<div class="admin-empty-cell"><div class="admin-spinner"></div> Loading access requests...</div>';
      } else if (state.accessRequests.length === 0) {
        html += '<div class="admin-empty-cell"><div class="admin-empty-icon"><span class="material-symbols-outlined">task_alt</span></div><p>No access requests matching current filter.</p></div>';
      } else {
        state.accessRequests.forEach(function (req) {
          var isPending = req.status === 'pending';
          var statusBadge = '';
          if (req.status === 'pending') {
            statusBadge = '<span class="admin-badge badge-pending"><span class="admin-badge-dot"></span> Pending Review</span>';
          } else if (req.status === 'approved') {
            statusBadge = '<span class="admin-badge badge-approved"><span class="admin-badge-dot"></span> Approved</span>';
          } else {
            statusBadge = '<span class="admin-badge badge-rejected"><span class="admin-badge-dot"></span> Rejected</span>';
          }

          html += ''
            + '<div class="admin-request-card ' + (isPending ? 'pending' : '') + '">'
            + '  <div class="admin-request-head">'
            + '    <div class="admin-request-user">'
            + '      <h4>' + escapeHtml(req.user_display_name || req.user_email) + '</h4>'
            + '      <div class="admin-request-meta">'
            + '        <span><span class="material-symbols-outlined" style="font-size:14px; vertical-align:middle;">mail</span> ' + escapeHtml(req.user_email) + '</span>'
            + '        <span><span class="material-symbols-outlined" style="font-size:14px; vertical-align:middle;">schedule</span> ' + formatRelativeTime(req.created_at) + ' (' + formatDate(req.created_at) + ')</span>'
            + '        <span><span class="material-symbols-outlined" style="font-size:14px; vertical-align:middle;">devices</span> ' + escapeHtml(req.device_info || 'Unknown Device') + '</span>'
            + '      </div>'
            + '    </div>'
            + '    <div>' + statusBadge + '</div>'
            + '  </div>'
            + '  <div class="admin-request-body">'
            + '    <strong>Reason:</strong> ' + escapeHtml(req.reason || 'Deactivated user sign-in attempt') + '<br>'
            + '    <small class="mono-text">Device Cryptographic Fingerprint: ' + escapeHtml(req.device_hash ? ('sha256:' + req.device_hash.substring(0, 24) + '...') : 'None') + '</small>'
            + '  </div>';

          if (isPending) {
            html += ''
              + '  <div class="admin-request-foot">'
              + '    <span class="text-muted" style="font-size:12px;">Action requires elevated administrator authorization.</span>'
              + '    <div class="admin-action-btn-group">'
              + '      <button class="btn btn-danger-outline btn-sm btn-reject-request" data-req-id="' + escapeHtml(req.id) + '" data-user-email="' + escapeHtml(req.user_email) + '">'
              + '        <span class="material-symbols-outlined">cancel</span> Reject Request'
              + '      </button>'
              + '      <button class="btn btn-success-outline btn-sm btn-approve-request" data-req-id="' + escapeHtml(req.id) + '" data-user-email="' + escapeHtml(req.user_email) + '">'
              + '        <span class="material-symbols-outlined">check_circle</span> Approve &amp; Reactivate'
              + '      </button>'
              + '    </div>'
              + '  </div>';
          } else {
            html += ''
              + '  <div class="admin-request-foot">'
              + '    <span class="mono-text" style="font-size:11.5px;">Reviewed by @' + escapeHtml(req.reviewer_username || 'admin') + ' on ' + formatDate(req.reviewed_at) + ' · Notes: ' + escapeHtml(req.review_notes || 'None') + '</span>'
              + '  </div>';
          }

          html += '</div>';
        });
      }

      html += ''
        + '    </div>'
        + '    <div class="admin-pagination">'
        + '      <div class="admin-pagination-info">'
        + '        Showing <strong>' + (state.requestsTotal > 0 ? reqStart : 0) + '–' + reqEnd + '</strong> of <strong>' + state.requestsTotal + '</strong> access requests'
        + '      </div>'
        + '      <div class="admin-pagination-btns">'
        + '        <button class="btn btn-secondary btn-sm" id="admin-req-prev" ' + (state.requestsPage <= 1 ? 'disabled' : '') + '>'
        + '          <span class="material-symbols-outlined">chevron_left</span> Previous'
        + '        </button>'
        + '        <span class="admin-page-indicator">Page ' + state.requestsPage + ' of ' + totalReqPages + '</span>'
        + '        <button class="btn btn-secondary btn-sm" id="admin-req-next" ' + (state.requestsPage >= totalReqPages ? 'disabled' : '') + '>'
        + '          Next <span class="material-symbols-outlined">chevron_right</span>'
        + '        </button>'
        + '      </div>'
        + '    </div>'
        + '  </div>';
    }

    // -------------------------------------------------------------------------
    // TAB 3: SYSTEM-WIDE SESSION MANAGEMENT (Global Active Concurrent Sessions)
    // -------------------------------------------------------------------------
    if (state.activeTab === 'sessions') {
      var totalSessPages = Math.ceil(state.sessionsTotal / state.sessionsLimit) || 1;
      var sessStart = (state.sessionsPage - 1) * state.sessionsLimit + 1;
      var sessEnd = Math.min(state.sessionsPage * state.sessionsLimit, state.sessionsTotal);

      html += ''
        + '  <div class="admin-card">'
        + '    <div class="admin-filter-bar">'
        + '      <div class="admin-toolbar-row">'
        + '        <div>'
        + '          <h3 style="font-size: 15px; font-weight: 700; color: #f2f7f4; margin-bottom: 2px;">Global Active Device Sessions</h3>'
        + '          <p style="font-size: 12px; color: #94a39b;">Live concurrent browser and client sessions across the entire Ayur-Intel platform.</p>'
        + '        </div>'
        + '        <div class="admin-toolbar-controls">'
        + '          <button class="btn btn-secondary btn-sm" id="admin-sessions-refresh-btn">'
        + '            <span class="material-symbols-outlined">sync</span> Refresh Sessions'
        + '          </button>'
        + '        </div>'
        + '      </div>'
        + '    </div>'
        + '    <div class="admin-table-container">'
        + '      <table class="admin-table">'
        + '        <thead>'
        + '          <tr>'
        + '            <th>User Identity</th>'
        + '            <th>Device &amp; Client</th>'
        + '            <th>IP Address</th>'
        + '            <th>Logged In (Local)</th>'
        + '            <th>Session Duration</th>'
        + '            <th>State</th>'
        + '            <th style="text-align: right;">Action</th>'
        + '          </tr>'
        + '        </thead>'
        + '        <tbody>';

      if (state.isSessionsLoading) {
        html += '<tr><td colspan="7" class="admin-empty-cell"><div class="admin-spinner"></div> Loading active sessions...</td></tr>';
      } else if (state.allSessions.length === 0) {
        html += '<tr><td colspan="7" class="admin-empty-cell"><div class="admin-empty-icon"><span class="material-symbols-outlined">devices</span></div><p>No active sessions found across the system.</p></td></tr>';
      } else {
        state.allSessions.forEach(function (sess) {
          var isSelf = currentUser && (currentUser.id === sess.user_id || currentUser.public_id === sess.user_id);
          var durationText = formatDuration(sess.duration_seconds);

          html += ''
            + '      <tr>'
            + '        <td>'
            + '          <div class="admin-actor-cell">'
            + '            <strong>' + escapeHtml(sess.display_name || sess.username) + (isSelf ? ' <span class="self-tag">(You)</span>' : '') + '</strong>'
            + '            <small class="mono-text">' + escapeHtml(sess.email || ('@' + sess.username)) + '</small>'
            + '          </div>'
            + '        </td>'
            + '        <td>'
            + '          <div class="admin-device-info">'
            + '            <span class="material-symbols-outlined admin-device-icon" style="font-size: 18px;">computer</span>'
            + '            <div>'
            + '              <strong>' + escapeHtml(sess.device_info || 'Browser Client') + '</strong>'
            + '              ' + (sess.user_agent ? '<small class="text-muted" title="' + escapeHtml(sess.user_agent) + '">' + escapeHtml(sess.user_agent.substring(0, 36)) + '...</small>' : '')
            + '            </div>'
            + '          </div>'
            + '        </td>'
            + '        <td><span class="mono-ip">' + escapeHtml(sess.ip_address || '—') + '</span></td>'
            + '        <td><span class="mono-date">' + formatDate(sess.created_at) + '</span></td>'
            + '        <td><span class="mono-text" style="color:#6ee7b7;">' + escapeHtml(durationText) + '</span></td>'
            + '        <td><span class="admin-badge badge-active"><span class="presence-pulse-dot inline"></span> Live</span></td>'
            + '        <td style="text-align: right;">'
            + '          <button class="btn btn-danger-outline btn-xs btn-terminate-global-session" data-user-id="' + escapeHtml(sess.user_id) + '" data-session-id="' + escapeHtml(sess.id) + '" data-user-name="' + escapeHtml(sess.display_name || sess.username) + '" data-device="' + escapeHtml(sess.device_info || 'device') + '">'
            + '            <span class="material-symbols-outlined">logout</span> Terminate'
            + '          </button>'
            + '        </td>'
            + '      </tr>';
        });
      }

      html += ''
        + '        </tbody>'
        + '      </table>'
        + '    </div>'
        + '    <div class="admin-pagination">'
        + '      <div class="admin-pagination-info">'
        + '        Showing <strong>' + (state.sessionsTotal > 0 ? sessStart : 0) + '–' + sessEnd + '</strong> of <strong>' + state.sessionsTotal + '</strong> active device sessions'
        + '      </div>'
        + '      <div class="admin-pagination-btns">'
        + '        <button class="btn btn-secondary btn-sm" id="admin-sess-prev" ' + (state.sessionsPage <= 1 ? 'disabled' : '') + '>'
        + '          <span class="material-symbols-outlined">chevron_left</span> Previous'
        + '        </button>'
        + '        <span class="admin-page-indicator">Page ' + state.sessionsPage + ' of ' + totalSessPages + '</span>'
        + '        <button class="btn btn-secondary btn-sm" id="admin-sess-next" ' + (state.sessionsPage >= totalSessPages ? 'disabled' : '') + '>'
        + '          Next <span class="material-symbols-outlined">chevron_right</span>'
        + '        </button>'
        + '      </div>'
        + '    </div>'
        + '  </div>';
    }

    // -------------------------------------------------------------------------
    // TAB 4: IMMUTABLE AUDIT TRAIL
    // -------------------------------------------------------------------------
    if (state.activeTab === 'audit') {
      var totalAuditPages = Math.ceil(state.auditTotal / state.auditLimit) || 1;
      var auditStartIdx = (state.auditPage - 1) * state.auditLimit + 1;
      var auditEndIdx = Math.min(state.auditPage * state.auditLimit, state.auditTotal);

      html += ''
        + '  <div class="admin-card">'
        + '    <div class="admin-filter-bar">'
        + '      <div class="admin-search-wrap">'
        + '        <span class="material-symbols-outlined">person_search</span>'
        + '        <input type="text" id="admin-audit-user-search" class="admin-search-input" placeholder="Filter by username or public ID..." value="' + escapeHtml(state.auditUserQuery) + '">'
        + '      </div>'
        + '      <div class="admin-filter-actions">'
        + '        <select id="admin-audit-action-filter" class="admin-select">'
        + '          <option value="" ' + (!state.auditActionFilter ? 'selected' : '') + '>All Actions</option>'
        + '          <option value="LOGIN" ' + (state.auditActionFilter === 'LOGIN' ? 'selected' : '') + '>LOGIN</option>'
        + '          <option value="SIGNUP" ' + (state.auditActionFilter === 'SIGNUP' ? 'selected' : '') + '>SIGNUP</option>'
        + '          <option value="LOGOUT" ' + (state.auditActionFilter === 'LOGOUT' ? 'selected' : '') + '>LOGOUT</option>'
        + '          <option value="LOGOUT_ALL" ' + (state.auditActionFilter === 'LOGOUT_ALL' ? 'selected' : '') + '>LOGOUT_ALL</option>'
        + '          <option value="STATUS_CHANGE" ' + (state.auditActionFilter === 'STATUS_CHANGE' ? 'selected' : '') + '>STATUS_CHANGE</option>'
        + '          <option value="SESSION_REVOKE" ' + (state.auditActionFilter === 'SESSION_REVOKE' ? 'selected' : '') + '>SESSION_REVOKE</option>'
        + '          <option value="ADMIN_UNLOCK" ' + (state.auditActionFilter === 'ADMIN_UNLOCK' ? 'selected' : '') + '>ADMIN_UNLOCK</option>'
        + '          <option value="ADMIN_CONSOLE_PASSWORD_SETUP" ' + (state.auditActionFilter === 'ADMIN_CONSOLE_PASSWORD_SETUP' ? 'selected' : '') + '>PASSWORD_SETUP</option>'
        + '          <option value="ADMIN_CONSOLE_PASSWORD_CHANGE" ' + (state.auditActionFilter === 'ADMIN_CONSOLE_PASSWORD_CHANGE' ? 'selected' : '') + '>PASSWORD_CHANGE</option>'
        + '          <option value="ADMIN_CONSOLE_PASSWORD_RECOVERED" ' + (state.auditActionFilter === 'ADMIN_CONSOLE_PASSWORD_RECOVERED' ? 'selected' : '') + '>PASSWORD_RECOVERED</option>'
        + '          <option value="ACCESS_REQUEST_SUBMIT" ' + (state.auditActionFilter === 'ACCESS_REQUEST_SUBMIT' ? 'selected' : '') + '>ACCESS_REQUEST_SUBMIT</option>'
        + '          <option value="ACCESS_REQUEST_APPROVE" ' + (state.auditActionFilter === 'ACCESS_REQUEST_APPROVE' ? 'selected' : '') + '>ACCESS_REQUEST_APPROVE</option>'
        + '        </select>'
        + '        <select id="admin-audit-status-filter" class="admin-select">'
        + '          <option value="" ' + (!state.auditStatusFilter ? 'selected' : '') + '>All Statuses</option>'
        + '          <option value="SUCCESS" ' + (state.auditStatusFilter === 'SUCCESS' ? 'selected' : '') + '>SUCCESS</option>'
        + '          <option value="FAILED" ' + (state.auditStatusFilter === 'FAILED' ? 'selected' : '') + '>FAILED</option>'
        + '          <option value="DENIED" ' + (state.auditStatusFilter === 'DENIED' ? 'selected' : '') + '>DENIED</option>'
        + '        </select>'
        + '        <button class="btn btn-primary btn-sm" id="admin-audit-search-submit">'
        + '          <span class="material-symbols-outlined">filter_alt</span> Apply'
        + '        </button>'
        + '        <button class="btn btn-secondary btn-sm" id="admin-audit-reset-btn" title="Reset audit filters">'
        + '          <span class="material-symbols-outlined">restart_alt</span> Reset'
        + '        </button>'
        + '      </div>'
        + '    </div>'
        + '    <div class="admin-table-container">'
        + '      <table class="admin-table">'
        + '        <thead>'
        + '          <tr>'
        + '            <th>Timestamp (Local)</th>'
        + '            <th>Action</th>'
        + '            <th>Resource</th>'
        + '            <th>Actor / Target</th>'
        + '            <th>Client IP</th>'
        + '            <th>Status</th>'
        + '            <th>Operation Details</th>'
        + '          </tr>'
        + '        </thead>'
        + '        <tbody>';

      if (state.isAuditLoading) {
        html += '<tr><td colspan="7" class="admin-empty-cell"><div class="admin-spinner"></div> Loading audit events...</td></tr>';
      } else if (state.auditLogs.length === 0) {
        html += '<tr><td colspan="7" class="admin-empty-cell"><div class="admin-empty-icon"><span class="material-symbols-outlined">policy</span></div><p>No audit trail records found matching your query.</p></td></tr>';
      } else {
        state.auditLogs.forEach(function (log) {
          var statusClass = log.status === 'SUCCESS' ? 'badge-success' : 'badge-danger';
          var actionClass = 'badge-action-' + (log.action || '').toLowerCase();

          html += ''
            + '      <tr>'
            + '        <td><span class="mono-date">' + formatDate(log.created_at) + '</span></td>'
            + '        <td><span class="admin-badge ' + actionClass + '">' + escapeHtml(log.action) + '</span></td>'
            + '        <td><span class="mono-text">' + escapeHtml(log.resource_type || '—') + (log.resource_id ? ' <small class="text-muted">#' + escapeHtml(log.resource_id.substring(0, 8)) + '</small>' : '') + '</span></td>'
            + '        <td>'
            + '          <div class="admin-actor-cell">'
            + '            <strong>' + escapeHtml(log.username || 'System/Anonymous') + '</strong>'
            + '            ' + (log.user_public_id ? '<small class="mono-text">id:' + escapeHtml(log.user_public_id.substring(0, 8)) + '</small>' : '')
            + '          </div>'
            + '        </td>'
            + '        <td><span class="mono-ip">' + escapeHtml(log.ip_address || '—') + '</span></td>'
            + '        <td><span class="admin-badge ' + statusClass + '">' + escapeHtml(log.status) + '</span></td>'
            + '        <td>'
            + '          <div class="admin-audit-detail">'
            + '            <span>' + escapeHtml(log.detail || '—') + '</span>'
            + '            ' + (log.metadata ? '<small class="mono-text audit-meta">' + escapeHtml(log.metadata) + '</small>' : '')
            + '          </div>'
            + '        </td>'
            + '      </tr>';
        });
      }

      html += ''
        + '        </tbody>'
        + '      </table>'
        + '    </div>'
        + '    <div class="admin-pagination">'
        + '      <div class="admin-pagination-info">'
        + '        Showing <strong>' + (state.auditTotal > 0 ? auditStartIdx : 0) + '–' + auditEndIdx + '</strong> of <strong>' + state.auditTotal + '</strong> events'
        + '      </div>'
        + '      <div class="admin-pagination-btns">'
        + '        <button class="btn btn-secondary btn-sm" id="admin-audit-prev" ' + (state.auditPage <= 1 ? 'disabled' : '') + '>'
        + '          <span class="material-symbols-outlined">chevron_left</span> Previous'
        + '        </button>'
        + '        <span class="admin-page-indicator">Page ' + state.auditPage + ' of ' + totalAuditPages + '</span>'
        + '        <button class="btn btn-secondary btn-sm" id="admin-audit-next" ' + (state.auditPage >= totalAuditPages ? 'disabled' : '') + '>'
        + '          Next <span class="material-symbols-outlined">chevron_right</span>'
        + '        </button>'
        + '      </div>'
        + '    </div>'
        + '  </div>';
    }

    // -------------------------------------------------------------------------
    // USER DETAIL SLIDING SIDE DRAWER
    // -------------------------------------------------------------------------
    if (state.selectedUser) {
      var sel = state.selectedUser;
      var isSelfModal = currentUser && (currentUser.id === sel.id || currentUser.public_id === sel.id);
      var sessions = sel.recent_sessions || [];
      var requests = sel.access_requests || [];

      html += ''
        + '<div class="admin-drawer-backdrop" id="admin-drawer-backdrop"></div>'
        + '<div class="admin-detail-drawer" id="admin-detail-drawer">'
        + '  <div class="admin-drawer-head">'
        + '    <div class="admin-drawer-title-wrap">'
        + '      <h2>' + escapeHtml(sel.display_name || sel.username) + (isSelfModal ? ' <span class="self-tag">(You)</span>' : '') + '</h2>'
        + '      <p>' + escapeHtml(sel.email || '—') + ' · @' + escapeHtml(sel.username) + '</p>'
        + '    </div>'
        + '    <button class="admin-modal-close" id="admin-drawer-close-btn" title="Close details">×</button>'
        + '  </div>'
        + '  <div class="admin-drawer-subtabs">'
        + '    <button class="admin-drawer-subtab ' + (state.selectedUserSubtab === 'overview' ? 'active' : '') + '" data-subtab="overview">'
        + '      <span class="material-symbols-outlined">badge</span> Overview'
        + '    </button>'
        + '    <button class="admin-drawer-subtab ' + (state.selectedUserSubtab === 'sessions' ? 'active' : '') + '" data-subtab="sessions">'
        + '      <span class="material-symbols-outlined">devices</span> Sessions (' + sessions.length + ')'
        + '    </button>'
        + '    <button class="admin-drawer-subtab ' + (state.selectedUserSubtab === 'requests' ? 'active' : '') + '" data-subtab="requests">'
        + '      <span class="material-symbols-outlined">assignment_turned_in</span> Requests (' + requests.length + ')'
        + '    </button>'
        + '    <button class="admin-drawer-subtab ' + (state.selectedUserSubtab === 'controls' ? 'active' : '') + '" data-subtab="controls">'
        + '      <span class="material-symbols-outlined">security</span> Access Controls'
        + '    </button>'
        + '  </div>'
        + '  <div class="admin-drawer-body">';

      if (state.loadingUserDetail) {
        html += '<div class="admin-empty-cell"><div class="admin-spinner"></div> Fetching user records...</div>';
      } else {
        if (state.selectedUserSubtab === 'overview') {
          var liveDurationText = sel.is_online
            ? formatDuration(sel.current_session_duration_seconds)
            : (sel.last_session_duration_seconds !== null && sel.last_session_duration_seconds !== undefined
                ? formatDuration(sel.last_session_duration_seconds)
                : 'Not recorded');

          html += ''
            + '<div class="admin-detail-section">'
            + '  <div class="admin-detail-section-title"><span class="material-symbols-outlined">fingerprint</span> Account Identity</div>'
            + '  <div class="admin-detail-kv-grid">'
            + '    <div class="admin-detail-kv-item"><small>Full Name</small><strong>' + escapeHtml(sel.display_name || sel.username) + '</strong></div>'
            + '    <div class="admin-detail-kv-item"><small>Email Address</small><strong>' + escapeHtml(sel.email || '—') + '</strong></div>'
            + '    <div class="admin-detail-kv-item"><small>Username Handle</small><strong>@' + escapeHtml(sel.username) + '</strong></div>'
            + '    <div class="admin-detail-kv-item"><small>System Role</small><strong><span class="admin-badge ' + (sel.role === 'admin' ? 'badge-admin' : 'badge-user') + '">' + escapeHtml(sel.role) + '</span></strong></div>'
            + '    <div class="admin-detail-kv-item"><small>Account Standing</small><strong>' + (sel.is_active ? '<span class="admin-badge badge-active">Active</span>' : '<span class="admin-badge badge-inactive">Deactivated</span>') + '</strong></div>'
            + '    <div class="admin-detail-kv-item"><small>Member Since</small><strong class="mono-date">' + formatDate(sel.created_at) + '</strong></div>'
            + '  </div>'
            + '</div>'
            + '<div class="admin-detail-section">'
            + '  <div class="admin-detail-section-title"><span class="material-symbols-outlined">insights</span> Presence &amp; Activity</div>'
            + '  <div class="admin-detail-kv-grid">'
            + '    <div class="admin-detail-kv-item"><small>Presence State</small><strong>' + (sel.is_online ? '<span class="presence-pulse-dot inline"></span> Online' : '<span class="presence-static-dot inline"></span> Offline') + '</strong></div>'
            + '    <div class="admin-detail-kv-item"><small>Total Logins Recorded</small><strong>' + (sel.login_count || 0) + ' logins</strong></div>'
            + '    <div class="admin-detail-kv-item"><small>Last Activity</small><strong>' + formatRelativeTime(sel.last_active_at) + '</strong></div>'
            + '    <div class="admin-detail-kv-item"><small>Last Opened</small><strong>' + (sel.last_opened_at ? formatRelativeTime(sel.last_opened_at) : 'Not available') + '</strong></div>'
            + '    <div class="admin-detail-kv-item"><small>' + (sel.is_online ? 'Current Session Duration' : 'Last Session Duration') + '</small><strong>' + escapeHtml(liveDurationText) + '</strong></div>'
            + '    <div class="admin-detail-kv-item"><small>Active Sessions</small><strong>' + (sel.active_sessions_count || sessions.length || 0) + ' concurrent</strong></div>'
            + '    <div class="admin-detail-kv-item" style="grid-column: 1 / -1;"><small>Approved Device Cryptographic Hash</small><span class="mono-text">' + (sel.approved_device_hash ? ('sha256:' + sel.approved_device_hash) : 'None (No specific device binding enforced)') + '</span></div>'
            + '  </div>'
            + '</div>';
        }

        if (state.selectedUserSubtab === 'sessions') {
          html += ''
            + '<div class="admin-session-header">'
            + '  <div>'
            + '    <h4>Active &amp; Historic Device Sessions</h4>'
            + '    <p>View client sessions with exact local timestamps and remote revocation control.</p>'
            + '  </div>'
            + '  <button class="btn btn-danger-outline btn-sm" id="admin-drawer-revoke-all-btn" data-user-id="' + escapeHtml(sel.id) + '" data-user-name="' + escapeHtml(sel.display_name || sel.username) + '" ' + (sessions.length === 0 ? 'disabled' : '') + '>'
            + '    <span class="material-symbols-outlined">power_settings_new</span> Logout from All Devices'
            + '  </button>'
            + '</div>'
            + '<div class="admin-table-container">'
            + '  <table class="admin-table">'
            + '    <thead>'
            + '      <tr>'
            + '        <th>Device &amp; Browser</th>'
            + '        <th>Client IP</th>'
            + '        <th>Started (Local)</th>'
            + '        <th>Last Active</th>'
            + '        <th>State</th>'
            + '        <th style="text-align: right;">Action</th>'
            + '      </tr>'
            + '    </thead>'
            + '    <tbody>';

          if (sessions.length === 0) {
            html += '<tr><td colspan="6" class="admin-empty-cell"><p>No session activity recorded for this user.</p></td></tr>';
          } else {
            sessions.forEach(function (s) {
              var isRevoked = s.is_revoked;
              var statusBadge = isRevoked
                ? '<span class="admin-badge badge-inactive">Revoked</span>'
                : '<span class="admin-badge badge-active">Active</span>';

              html += ''
                + '<tr class="' + (isRevoked ? 'tr-revoked' : '') + '">'
                + '  <td>'
                + '    <div class="admin-device-info">'
                + '      <span class="material-symbols-outlined admin-device-icon">computer</span>'
                + '      <div>'
                + '        <strong>' + escapeHtml(s.device_info || 'Browser Client') + '</strong>'
                + '        ' + (s.user_agent ? '<small class="text-muted" title="' + escapeHtml(s.user_agent) + '">' + escapeHtml(s.user_agent.substring(0, 42)) + '...</small>' : '')
                + '      </div>'
                + '    </div>'
                + '  </td>'
                + '  <td><span class="mono-ip">' + escapeHtml(s.ip_address || '—') + '</span></td>'
                + '  <td><span class="mono-date">' + formatDate(s.created_at) + '</span></td>'
                + '  <td><span class="mono-date">' + formatRelativeTime(s.last_active_at) + '</span></td>'
                + '  <td>' + statusBadge + '</td>'
                + '  <td style="text-align: right;">';

              if (!isRevoked) {
                html += ''
                  + '    <button class="btn btn-danger-outline btn-xs btn-revoke-session" data-user-id="' + escapeHtml(sel.id) + '" data-session-id="' + escapeHtml(s.id) + '" data-device="' + escapeHtml(s.device_info || 'this device') + '">'
                  + '      <span class="material-symbols-outlined">logout</span> Revoke'
                  + '    </button>';
              } else {
                html += '<span class="text-muted" style="font-size:11.5px;">Terminated</span>';
              }

              html += '  </td></tr>';
            });
          }

          html += '    </tbody></table></div>';
        }

        if (state.selectedUserSubtab === 'requests') {
          html += ''
            + '<div class="admin-session-header">'
            + '  <div>'
            + '    <h4>Access Approval History</h4>'
            + '    <p>Review past and pending device verification requests for this account.</p>'
            + '  </div>'
            + '</div>';

          if (requests.length === 0) {
            html += '<div class="admin-empty-cell"><p>No access approval requests submitted by this user.</p></div>';
          } else {
            requests.forEach(function (r) {
              var statusBadge = '';
              if (r.status === 'pending') statusBadge = '<span class="admin-badge badge-pending">Pending Review</span>';
              else if (r.status === 'approved') statusBadge = '<span class="admin-badge badge-approved">Approved</span>';
              else statusBadge = '<span class="admin-badge badge-rejected">Rejected</span>';

              html += ''
                + '<div class="admin-detail-section" style="margin-bottom: 12px;">'
                + '  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">'
                + '    <strong style="color:#f2f7f4; font-size:13.5px;">' + formatDate(r.created_at) + '</strong>'
                + '    ' + statusBadge
                + '  </div>'
                + '  <div class="admin-detail-kv-grid">'
                + '    <div><small>Device Information</small><span>' + escapeHtml(r.device_info || 'Unknown') + '</span></div>'
                + '    <div><small>Client IP</small><span class="mono-ip">' + escapeHtml(r.ip_address || '—') + '</span></div>'
                + '    <div><small>Device Hash</small><span class="mono-text">' + escapeHtml(r.device_hash ? ('sha256:' + r.device_hash.substring(0, 16) + '...') : 'None') + '</span></div>'
                + '    <div><small>Reviewer Notes</small><span>' + escapeHtml(r.review_notes || 'None') + '</span></div>'
                + '  </div>'
                + '</div>';
            });
          }
        }

        if (state.selectedUserSubtab === 'controls') {
          html += ''
            + '<div class="admin-danger-zone">'
            + '  <div class="admin-danger-title">'
            + '    <span class="material-symbols-outlined">warning</span> Access &amp; Account Controls'
            + '  </div>'
            + '  <p style="font-size:12.5px; color:#cbd5e1; margin-bottom:14px;">Destructive administrative operations require elevated permissions and prompt for confirmation.</p>'
            + '  <div class="admin-danger-row">'
            + '    <div class="admin-danger-info">'
            + '      <h5>' + (sel.is_active ? 'Deactivate Account' : 'Reactivate Account') + '</h5>'
            + '      <p>' + (sel.is_active ? 'Immediately revoke all active sessions and block further authentication.' : 'Restore system login access for this account.') + '</p>'
            + '    </div>'
            + (sel.is_active
                ? '<button class="btn btn-danger-outline btn-sm btn-drawer-toggle-status" data-user-id="' + escapeHtml(sel.id) + '" data-user-name="' + escapeHtml(sel.display_name || sel.username) + '" data-active="false" ' + (isSelfModal ? 'disabled title="You cannot deactivate your own account"' : '') + '><span class="material-symbols-outlined">block</span> Deactivate</button>'
                : '<button class="btn btn-success-outline btn-sm btn-drawer-toggle-status" data-user-id="' + escapeHtml(sel.id) + '" data-user-name="' + escapeHtml(sel.display_name || sel.username) + '" data-active="true"><span class="material-symbols-outlined">check_circle</span> Reactivate</button>'
              )
            + '  </div>'
            + '  <div class="admin-danger-row">'
            + '    <div class="admin-danger-info">'
            + '      <h5>Invalidate Active Sessions</h5>'
            + '      <p>Terminate all active browser and device sessions across all platforms.</p>'
            + '    </div>'
            + '    <button class="btn btn-danger-outline btn-sm btn-drawer-logout-all" data-user-id="' + escapeHtml(sel.id) + '" data-user-name="' + escapeHtml(sel.display_name || sel.username) + '" ' + (sessions.length === 0 ? 'disabled' : '') + '>'
            + '      <span class="material-symbols-outlined">logout</span> Revoke All Sessions'
            + '    </button>'
            + '  </div>'
            + '</div>';
        }
      }

      html += ''
        + '  </div>'
        + '  <div class="admin-drawer-foot">'
        + '    <button class="btn btn-secondary" id="admin-drawer-foot-close">Close Drawer</button>'
        + '  </div>'
        + '</div>';
    }

    html += '</div>'; // End .admin-console-wrapper

    // -------------------------------------------------------------------------
    // PERSISTENT LOCK SCREEN OVERLAY (When Console is Locked)
    // -------------------------------------------------------------------------
    if (isLocked) {
      html += '<div class="admin-centre-lock-overlay" id="admin-lock-overlay">';

      // Mode A: First-Time Setup
      if (state.lockMode === 'setup') {
        html += ''
          + '<div class="admin-centre-lock-card">'
          + '  <div class="admin-unlock-icon"><span class="material-symbols-outlined">lock_person</span></div>'
          + '  <h2>Setup Admin Console Password</h2>'
          + '  <p class="lock-sub">Set a dedicated, persistent password to protect Institutional Oversight. This password is isolated from your standard account credentials (minimum 12 characters).</p>'
          + (state.lockError ? '<div class="admin-confirm-warning" style="margin-bottom:16px;">' + escapeHtml(state.lockError) + '</div>' : '')
          + '  <form id="admin-setup-form" onsubmit="return false;">'
          + '    <div class="admin-lock-form-group">'
          + '      <label for="admin-setup-account-pwd">Current Account Password</label>'
          + '      <div class="admin-lock-input-wrap">'
          + '        <input type="password" id="admin-setup-account-pwd" placeholder="Enter your current login password..." autocomplete="current-password" required>'
          + '        <button type="button" class="admin-lock-toggle-pwd" data-target="admin-setup-account-pwd"><span class="material-symbols-outlined" style="font-size:18px;">visibility</span></button>'
          + '      </div>'
          + '      <small class="admin-pwd-hint">Required to verify administrative authority.</small>'
          + '    </div>'
          + '    <div class="admin-lock-form-group">'
          + '      <label for="admin-setup-new-pwd">Create Admin Console Password</label>'
          + '      <div class="admin-lock-input-wrap">'
          + '        <input type="password" id="admin-setup-new-pwd" placeholder="Min. 12 characters..." autocomplete="new-password" required>'
          + '        <button type="button" class="admin-lock-toggle-pwd" data-target="admin-setup-new-pwd"><span class="material-symbols-outlined" style="font-size:18px;">visibility</span></button>'
          + '      </div>'
          + '      <div class="admin-pwd-meter"><div class="admin-pwd-meter-fill" id="admin-setup-meter"></div></div>'
          + '      <small class="admin-pwd-hint" id="admin-setup-meter-lbl">Minimum 12 characters required.</small>'
          + '    </div>'
          + '    <div class="admin-lock-form-group">'
          + '      <label for="admin-setup-confirm-pwd">Confirm Console Password</label>'
          + '      <div class="admin-lock-input-wrap">'
          + '        <input type="password" id="admin-setup-confirm-pwd" placeholder="Repeat console password..." autocomplete="new-password" required>'
          + '        <button type="button" class="admin-lock-toggle-pwd" data-target="admin-setup-confirm-pwd"><span class="material-symbols-outlined" style="font-size:18px;">visibility</span></button>'
          + '      </div>'
          + '    </div>'
          + '    <div class="admin-lock-actions">'
          + '      <button type="button" class="btn btn-primary" id="admin-setup-submit-btn" style="width:100%; justify-content:center;">'
          + '        <span class="material-symbols-outlined">lock_open</span> Save Password &amp; Unlock Console'
          + '      </button>'
          + '    </div>'
          + '  </form>'
          + '</div>';
      }

      // Mode B: Standard Persistent Password Unlock
      else if (state.lockMode === 'unlock') {
        html += ''
          + '<div class="admin-centre-lock-card">'
          + '  <div class="admin-unlock-icon"><span class="material-symbols-outlined">lock</span></div>'
          + '  <h2>Institutional Oversight Locked</h2>'
          + '  <p class="lock-sub">Enter your persistent Admin Console password to elevate permissions and inspect administrative intelligence.</p>'
          + (state.lockError ? '<div class="admin-confirm-warning" style="margin-bottom:16px;">' + escapeHtml(state.lockError) + '</div>' : '')
          + '  <form id="admin-unlock-form" onsubmit="return false;">'
          + '    <div class="admin-lock-form-group">'
          + '      <label for="admin-centre-unlock-pwd">Admin Console Password</label>'
          + '      <div class="admin-lock-input-wrap">'
          + '        <input type="password" id="admin-centre-unlock-pwd" placeholder="Enter console password..." autocomplete="current-password" autofocus required>'
          + '        <button type="button" class="admin-lock-toggle-pwd" data-target="admin-centre-unlock-pwd"><span class="material-symbols-outlined" style="font-size:18px;">visibility</span></button>'
          + '      </div>'
          + '    </div>'
          + '    <div class="admin-lock-actions">'
          + '      <button type="button" class="btn btn-primary" id="admin-centre-unlock-submit-btn" style="width:100%; justify-content:center;">'
          + '        <span class="material-symbols-outlined">lock_open</span> Unlock Console'
          + '      </button>'
          + '      <button type="button" class="admin-lock-secondary-link" id="admin-trigger-recover-btn">'
          + '        Forgot console password? Recover with account credentials'
          + '      </button>'
          + '    </div>'
          + '  </form>'
          + '</div>';
      }

      // Mode C: Recovery Flow (Using Account Password)
      else if (state.lockMode === 'recover') {
        html += ''
          + '<div class="admin-centre-lock-card">'
          + '  <div class="admin-unlock-icon"><span class="material-symbols-outlined">lock_reset</span></div>'
          + '  <h2>Recover Admin Console Access</h2>'
          + '  <p class="lock-sub">Verify your main account password to set a new persistent console password.</p>'
          + (state.lockError ? '<div class="admin-confirm-warning" style="margin-bottom:16px;">' + escapeHtml(state.lockError) + '</div>' : '')
          + '  <form id="admin-recover-form" onsubmit="return false;">'
          + '    <div class="admin-lock-form-group">'
          + '      <label for="admin-recover-account-pwd">Current Account Password</label>'
          + '      <div class="admin-lock-input-wrap">'
          + '        <input type="password" id="admin-recover-account-pwd" placeholder="Enter login password..." autocomplete="current-password" required>'
          + '        <button type="button" class="admin-lock-toggle-pwd" data-target="admin-recover-account-pwd"><span class="material-symbols-outlined" style="font-size:18px;">visibility</span></button>'
          + '      </div>'
          + '    </div>'
          + '    <div class="admin-lock-form-group">'
          + '      <label for="admin-recover-new-pwd">New Admin Console Password</label>'
          + '      <div class="admin-lock-input-wrap">'
          + '        <input type="password" id="admin-recover-new-pwd" placeholder="Min. 12 characters..." autocomplete="new-password" required>'
          + '        <button type="button" class="admin-lock-toggle-pwd" data-target="admin-recover-new-pwd"><span class="material-symbols-outlined" style="font-size:18px;">visibility</span></button>'
          + '      </div>'
          + '      <div class="admin-pwd-meter"><div class="admin-pwd-meter-fill" id="admin-recover-meter"></div></div>'
          + '      <small class="admin-pwd-hint" id="admin-recover-meter-lbl">Minimum 12 characters required.</small>'
          + '    </div>'
          + '    <div class="admin-lock-form-group">'
          + '      <label for="admin-recover-confirm-pwd">Confirm New Password</label>'
          + '      <div class="admin-lock-input-wrap">'
          + '        <input type="password" id="admin-recover-confirm-pwd" placeholder="Repeat new console password..." autocomplete="new-password" required>'
          + '        <button type="button" class="admin-lock-toggle-pwd" data-target="admin-recover-confirm-pwd"><span class="material-symbols-outlined" style="font-size:18px;">visibility</span></button>'
          + '      </div>'
          + '    </div>'
          + '    <div class="admin-lock-actions">'
          + '      <button type="button" class="btn btn-primary" id="admin-recover-submit-btn" style="width:100%; justify-content:center;">'
          + '        <span class="material-symbols-outlined">lock_open</span> Reset Password &amp; Unlock'
          + '      </button>'
          + '      <button type="button" class="admin-lock-secondary-link" id="admin-back-to-unlock-btn">'
          + '        ← Return to Unlock Screen'
          + '      </button>'
          + '    </div>'
          + '  </form>'
          + '</div>';
      }

      html += '</div>'; // End .admin-centre-lock-overlay
    }

    // -------------------------------------------------------------------------
    // CHANGE PASSWORD MODAL (When Console is Unlocked)
    // -------------------------------------------------------------------------
    if (state.showChangePasswordModal) {
      html += ''
        + '<div class="admin-modal-backdrop" id="admin-change-pwd-modal">'
        + '  <div class="admin-modal admin-modal-sm">'
        + '    <div class="admin-modal-head">'
        + '      <div class="admin-modal-title">'
        + '        <span class="material-symbols-outlined" style="color: #10b981;">password</span>'
        + '        <h2>Change Console Password</h2>'
        + '      </div>'
        + '      <button class="admin-modal-close" id="admin-change-pwd-close-btn" title="Cancel">×</button>'
        + '    </div>'
        + '    <div class="admin-modal-body">'
        + '      <p style="font-size:12.5px; color:#94a39b; margin-bottom:16px;">Update your persistent Admin Console password. Requires your current console password.</p>'
        + (state.changePasswordError ? '<div class="admin-confirm-warning" style="margin-bottom:14px;">' + escapeHtml(state.changePasswordError) + '</div>' : '')
        + '      <div class="admin-lock-form-group">'
        + '        <label for="admin-change-current-pwd">Current Console Password</label>'
        + '        <div class="admin-lock-input-wrap">'
        + '          <input type="password" id="admin-change-current-pwd" placeholder="Enter current console password..." required>'
        + '          <button type="button" class="admin-lock-toggle-pwd" data-target="admin-change-current-pwd"><span class="material-symbols-outlined" style="font-size:18px;">visibility</span></button>'
        + '        </div>'
        + '      </div>'
        + '      <div class="admin-lock-form-group">'
        + '        <label for="admin-change-new-pwd">New Console Password</label>'
        + '        <div class="admin-lock-input-wrap">'
        + '          <input type="password" id="admin-change-new-pwd" placeholder="Min. 12 characters..." required>'
        + '          <button type="button" class="admin-lock-toggle-pwd" data-target="admin-change-new-pwd"><span class="material-symbols-outlined" style="font-size:18px;">visibility</span></button>'
        + '        </div>'
        + '        <div class="admin-pwd-meter"><div class="admin-pwd-meter-fill" id="admin-change-meter"></div></div>'
        + '        <small class="admin-pwd-hint" id="admin-change-meter-lbl">Minimum 12 characters required.</small>'
        + '      </div>'
        + '      <div class="admin-lock-form-group">'
        + '        <label for="admin-change-confirm-pwd">Confirm New Password</label>'
        + '        <div class="admin-lock-input-wrap">'
        + '          <input type="password" id="admin-change-confirm-pwd" placeholder="Repeat new password..." required>'
        + '          <button type="button" class="admin-lock-toggle-pwd" data-target="admin-change-confirm-pwd"><span class="material-symbols-outlined" style="font-size:18px;">visibility</span></button>'
        + '        </div>'
        + '      </div>'
        + '    </div>'
        + '    <div class="admin-modal-foot">'
        + '      <button class="btn btn-secondary" id="admin-change-pwd-cancel-btn">Cancel</button>'
        + '      <button class="btn btn-primary" id="admin-change-pwd-submit-btn">'
        + '        <span class="material-symbols-outlined">check_circle</span> Update Password'
        + '      </button>'
        + '    </div>'
        + '  </div>'
        + '</div>';
    }

    // -------------------------------------------------------------------------
    // GENERIC CONFIRMATION DIALOG MODAL
    // -------------------------------------------------------------------------
    if (state.confirmation) {
      var c = state.confirmation;
      html += ''
        + '<div class="admin-modal-backdrop" id="admin-confirm-modal">'
        + '  <div class="admin-modal admin-modal-sm">'
        + '    <div class="admin-modal-head">'
        + '      <div class="admin-modal-title">'
        + '        <span class="material-symbols-outlined" style="color: ' + (c.isDanger ? '#ef4444' : '#10b981') + ';">' + (c.isDanger ? 'warning' : 'help') + '</span>'
        + '        <h2>' + escapeHtml(c.title) + '</h2>'
        + '      </div>'
        + '    </div>'
        + '    <div class="admin-modal-body">'
        + '      <p class="admin-confirm-msg">' + escapeHtml(c.message) + '</p>'
        + '      ' + (c.warning ? '<div class="admin-confirm-warning">' + escapeHtml(c.warning) + '</div>' : '')
        + '    </div>'
        + '    <div class="admin-modal-foot">'
        + '      <button class="btn btn-secondary" id="admin-confirm-cancel-btn">Cancel</button>'
        + '      <button class="btn ' + (c.isDanger ? 'btn-danger' : 'btn-primary') + '" id="admin-confirm-action-btn">'
        + '        ' + escapeHtml(c.confirmText || 'Confirm')
        + '      </button>'
        + '    </div>'
        + '  </div>'
        + '</div>';
    }

    return html;
  }

  // ---------------------------------------------------------------------------
  // Event Binding
  // ---------------------------------------------------------------------------

  function bindEvents() {
    // 1. Password Visibility Toggles across all inputs
    var toggleBtns = document.querySelectorAll('.admin-lock-toggle-pwd[data-target]');
    toggleBtns.forEach(function (btn) {
      btn.onclick = function () {
        var targetId = btn.getAttribute('data-target');
        var input = document.getElementById(targetId);
        if (input) {
          if (input.type === 'password') {
            input.type = 'text';
            btn.innerHTML = '<span class="material-symbols-outlined" style="font-size:18px;">visibility_off</span>';
          } else {
            input.type = 'password';
            btn.innerHTML = '<span class="material-symbols-outlined" style="font-size:18px;">visibility</span>';
          }
        }
      };
    });

    // 2. Real-time Password Strength Meters
    function bindMeter(inputId, meterFillId, meterLblId) {
      var input = document.getElementById(inputId);
      var fill = document.getElementById(meterFillId);
      var lbl = document.getElementById(meterLblId);
      if (input && fill) {
        input.oninput = function () {
          var res = calculatePasswordStrength(input.value);
          fill.className = 'admin-pwd-meter-fill ' + res.class;
          if (lbl) lbl.textContent = res.label;
        };
      }
    }
    bindMeter('admin-setup-new-pwd', 'admin-setup-meter', 'admin-setup-meter-lbl');
    bindMeter('admin-recover-new-pwd', 'admin-recover-meter', 'admin-recover-meter-lbl');
    bindMeter('admin-change-new-pwd', 'admin-change-meter', 'admin-change-meter-lbl');

    // 3. Lock Screen Setup Submit
    var setupSubmit = document.getElementById('admin-setup-submit-btn');
    if (setupSubmit) {
      setupSubmit.onclick = function () {
        var aPwd = (document.getElementById('admin-setup-account-pwd') || {}).value;
        var cPwd = (document.getElementById('admin-setup-new-pwd') || {}).value;
        var cfPwd = (document.getElementById('admin-setup-confirm-pwd') || {}).value;
        executeSetupConsolePassword(aPwd, cPwd, cfPwd);
      };
    }

    // 4. Lock Screen Unlock Submit
    var unlockSubmit = document.getElementById('admin-centre-unlock-submit-btn');
    var unlockInput = document.getElementById('admin-centre-unlock-pwd');
    if (unlockSubmit && unlockInput) {
      unlockSubmit.onclick = function () {
        executeUnlock(unlockInput.value);
      };
      unlockInput.onkeydown = function (e) {
        if (e.key === 'Enter') executeUnlock(unlockInput.value);
      };
    }

    // 5. Recovery Link & Return Link
    var triggerRecover = document.getElementById('admin-trigger-recover-btn');
    if (triggerRecover) {
      triggerRecover.onclick = function () {
        state.lockMode = 'recover';
        state.lockError = null;
        refreshView();
      };
    }
    var backToUnlock = document.getElementById('admin-back-to-unlock-btn');
    if (backToUnlock) {
      backToUnlock.onclick = function () {
        state.lockMode = 'unlock';
        state.lockError = null;
        refreshView();
      };
    }

    // 6. Recover Submit
    var recoverSubmit = document.getElementById('admin-recover-submit-btn');
    if (recoverSubmit) {
      recoverSubmit.onclick = function () {
        var aPwd = (document.getElementById('admin-recover-account-pwd') || {}).value;
        var nPwd = (document.getElementById('admin-recover-new-pwd') || {}).value;
        var cfPwd = (document.getElementById('admin-recover-confirm-pwd') || {}).value;
        executeRecoverConsolePassword(aPwd, nPwd, cfPwd);
      };
    }

    // 7. Change Password Modal Triggers & Submit
    var changePwdBtn = document.getElementById('admin-change-pwd-btn');
    if (changePwdBtn) {
      changePwdBtn.onclick = function () {
        state.showChangePasswordModal = true;
        state.changePasswordError = null;
        refreshView();
      };
    }
    var changePwdClose = document.getElementById('admin-change-pwd-close-btn');
    var changePwdCancel = document.getElementById('admin-change-pwd-cancel-btn');
    if (changePwdClose) changePwdClose.onclick = function () { state.showChangePasswordModal = false; refreshView(); };
    if (changePwdCancel) changePwdCancel.onclick = function () { state.showChangePasswordModal = false; refreshView(); };

    var changePwdSubmit = document.getElementById('admin-change-pwd-submit-btn');
    if (changePwdSubmit) {
      changePwdSubmit.onclick = function () {
        var curr = (document.getElementById('admin-change-current-pwd') || {}).value;
        var nPwd = (document.getElementById('admin-change-new-pwd') || {}).value;
        var cfPwd = (document.getElementById('admin-change-confirm-pwd') || {}).value;
        executeChangeConsolePassword(curr, nPwd, cfPwd);
      };
    }

    // 8. Explicit Lock & Unlock Trigger in Header
    var lockBtn = document.getElementById('admin-lock-btn');
    if (lockBtn) {
      lockBtn.onclick = function () {
        executeLock(false);
      };
    }
    var unlockTriggerBtn = document.getElementById('admin-unlock-trigger-btn');
    if (unlockTriggerBtn) {
      unlockTriggerBtn.onclick = function () {
        state.lockMode = state.isConfigured ? 'unlock' : 'setup';
        state.lockError = null;
        refreshView();
      };
    }

    // 9. Header Refresh
    var refreshBtn = document.getElementById('admin-refresh-btn');
    if (refreshBtn) {
      refreshBtn.onclick = function () {
        if (state.activeTab === 'users') loadUsers();
        else if (state.activeTab === 'requests') loadAccessRequests();
        else if (state.activeTab === 'sessions') loadAllSessions();
        else loadAuditLogs();
      };
    }

    // 10. Navigation Tabs (4 Sections)
    var tabBtns = document.querySelectorAll('.admin-tab-btn[data-admin-tab]');
    tabBtns.forEach(function (btn) {
      btn.onclick = function () {
        var tab = btn.getAttribute('data-admin-tab');
        if (tab && state.activeTab !== tab) {
          state.activeTab = tab;
          if (tab === 'users' && state.users.length === 0) loadUsers(1);
          if (tab === 'requests') loadAccessRequests(1);
          if (tab === 'sessions') loadAllSessions(1);
          if (tab === 'audit' && state.auditLogs.length === 0) loadAuditLogs(1);
          refreshView();
        }
      };
    });

    // 11. User Directory Controls: Search, Filter, Sort
    var searchInput = document.getElementById('admin-user-search');
    var statusSelect = document.getElementById('admin-status-filter');
    var sortSelect = document.getElementById('admin-user-sort');
    var searchSubmit = document.getElementById('admin-search-submit-btn');
    var clearSearch = document.getElementById('admin-clear-search-btn');

    if (searchSubmit) {
      searchSubmit.onclick = function () {
        if (searchInput) state.userQuery = searchInput.value;
        if (statusSelect) state.statusFilter = statusSelect.value;
        if (sortSelect) state.userSort = sortSelect.value;
        loadUsers(1);
      };
    }
    if (searchInput) {
      searchInput.onkeydown = function (e) {
        if (e.key === 'Enter') {
          state.userQuery = searchInput.value;
          if (statusSelect) state.statusFilter = statusSelect.value;
          if (sortSelect) state.userSort = sortSelect.value;
          loadUsers(1);
        }
      };
    }
    if (clearSearch) {
      clearSearch.onclick = function () {
        state.userQuery = '';
        if (searchInput) searchInput.value = '';
        loadUsers(1);
      };
    }
    if (statusSelect) {
      statusSelect.onchange = function () {
        state.statusFilter = statusSelect.value;
        loadUsers(1);
      };
    }
    if (sortSelect) {
      sortSelect.onchange = function () {
        state.userSort = sortSelect.value;
        refreshView();
      };
    }

    var userPrev = document.getElementById('admin-user-prev');
    var userNext = document.getElementById('admin-user-next');
    if (userPrev) userPrev.onclick = function () { if (state.userPage > 1) loadUsers(state.userPage - 1); };
    if (userNext) userNext.onclick = function () {
      var totalUserPages = Math.ceil(state.totalUsers / state.userLimit) || 1;
      if (state.userPage < totalUserPages) loadUsers(state.userPage + 1);
    };

    // 12. Open User Detail (Drawer)
    var userCards = document.querySelectorAll('.admin-user-card[data-user-id]');
    userCards.forEach(function (card) {
      card.onclick = function (e) {
        if (e.target.closest('button')) return;
        var uid = card.getAttribute('data-user-id');
        if (uid) loadUserDetail(uid);
      };
    });

    var viewDetailBtns = document.querySelectorAll('.btn-view-details');
    viewDetailBtns.forEach(function (btn) {
      btn.onclick = function (e) {
        e.stopPropagation();
        var uid = btn.getAttribute('data-user-id');
        if (uid) loadUserDetail(uid);
      };
    });

    // 13. User Drawer Controls
    var drawerSubtabs = document.querySelectorAll('.admin-drawer-subtab');
    drawerSubtabs.forEach(function (tab) {
      tab.onclick = function () {
        var sub = tab.getAttribute('data-subtab');
        if (sub) {
          state.selectedUserSubtab = sub;
          refreshView();
        }
      };
    });

    function closeDrawer() {
      state.selectedUser = null;
      state.selectedUserSubtab = 'overview';
      refreshView();
    }
    var drawerBackdrop = document.getElementById('admin-drawer-backdrop');
    var drawerCloseBtn = document.getElementById('admin-drawer-close-btn');
    var drawerFootClose = document.getElementById('admin-drawer-foot-close');
    if (drawerBackdrop) drawerBackdrop.onclick = closeDrawer;
    if (drawerCloseBtn) drawerCloseBtn.onclick = closeDrawer;
    if (drawerFootClose) drawerFootClose.onclick = closeDrawer;

    // 14. Drawer Status Toggle & Session Revoke
    var drawerToggleStatus = document.querySelector('.btn-drawer-toggle-status');
    if (drawerToggleStatus) {
      drawerToggleStatus.onclick = function () {
        var uid = drawerToggleStatus.getAttribute('data-user-id');
        var uname = drawerToggleStatus.getAttribute('data-user-name');
        var makeActive = drawerToggleStatus.getAttribute('data-active') === 'true';

        if (!makeActive) {
          state.confirmation = {
            title: 'Deactivate User Account',
            message: 'Are you sure you want to deactivate ' + uname + '?',
            warning: 'All active sessions will be revoked immediately and subsequent logins will require administrator approval.',
            confirmText: 'Deactivate Account',
            isDanger: true,
            onConfirm: function () {
              executeStatusChange({ id: uid, username: uname }, false);
            }
          };
        } else {
          state.confirmation = {
            title: 'Reactivate User Account',
            message: 'Restore login access for ' + uname + '?',
            warning: null,
            confirmText: 'Reactivate Account',
            isDanger: false,
            onConfirm: function () {
              executeStatusChange({ id: uid, username: uname }, true);
            }
          };
        }
        refreshView();
      };
    }

    var drawerRevokeAll = document.querySelector('.btn-drawer-logout-all') || document.getElementById('admin-drawer-revoke-all-btn');
    if (drawerRevokeAll) {
      drawerRevokeAll.onclick = function () {
        var uid = drawerRevokeAll.getAttribute('data-user-id');
        var uname = drawerRevokeAll.getAttribute('data-user-name');

        state.confirmation = {
          title: 'Revoke All User Sessions',
          message: 'Terminate all active sessions across all devices for ' + uname + '?',
          warning: 'The user will be required to re-authenticate on all devices.',
          confirmText: 'Terminate All Sessions',
          isDanger: true,
          onConfirm: function () {
            executeRevokeAllSessions(uid, uname);
          }
        };
        refreshView();
      };
    }

    var revokeSessBtns = document.querySelectorAll('.btn-revoke-session');
    revokeSessBtns.forEach(function (btn) {
      btn.onclick = function () {
        var uid = btn.getAttribute('data-user-id');
        var sid = btn.getAttribute('data-session-id');
        var dev = btn.getAttribute('data-device');

        state.confirmation = {
          title: 'Revoke Device Session',
          message: 'Revoke active session for ' + dev + '?',
          warning: 'The user will be logged out of this device immediately.',
          confirmText: 'Revoke Session',
          isDanger: true,
          onConfirm: function () {
            executeRevokeSession(uid, sid);
          }
        };
        refreshView();
      };
    });

    // 15. Global Sessions Tab Terminate Button
    var globalTerminateBtns = document.querySelectorAll('.btn-terminate-global-session');
    globalTerminateBtns.forEach(function (btn) {
      btn.onclick = function () {
        var uid = btn.getAttribute('data-user-id');
        var sid = btn.getAttribute('data-session-id');
        var uname = btn.getAttribute('data-user-name');
        var dev = btn.getAttribute('data-device');

        state.confirmation = {
          title: 'Terminate Device Session',
          message: 'Terminate session for ' + uname + ' on ' + dev + '?',
          warning: 'The client token will be immediately invalidated.',
          confirmText: 'Terminate Session',
          isDanger: true,
          onConfirm: function () {
            executeRevokeSession(uid, sid);
          }
        };
        refreshView();
      };
    });

    var sessRefreshBtn = document.getElementById('admin-sessions-refresh-btn');
    if (sessRefreshBtn) sessRefreshBtn.onclick = function () { loadAllSessions(); };
    var sessPrev = document.getElementById('admin-sess-prev');
    var sessNext = document.getElementById('admin-sess-next');
    if (sessPrev) sessPrev.onclick = function () { if (state.sessionsPage > 1) loadAllSessions(state.sessionsPage - 1); };
    if (sessNext) sessNext.onclick = function () {
      var totalSessPages = Math.ceil(state.sessionsTotal / state.sessionsLimit) || 1;
      if (state.sessionsPage < totalSessPages) loadAllSessions(state.sessionsPage + 1);
    };

    // 16. Access Requests Tab Actions
    var reqFilter = document.getElementById('admin-requests-filter');
    if (reqFilter) {
      reqFilter.onchange = function () {
        state.requestsFilter = reqFilter.value;
        loadAccessRequests(1);
      };
    }
    var reqRefresh = document.getElementById('admin-requests-refresh-btn');
    if (reqRefresh) {
      reqRefresh.onclick = function () { loadAccessRequests(state.requestsPage); };
    }

    var approveBtns = document.querySelectorAll('.btn-approve-request');
    approveBtns.forEach(function (btn) {
      btn.onclick = function () {
        var reqId = btn.getAttribute('data-req-id');
        var email = btn.getAttribute('data-user-email');

        state.confirmation = {
          title: 'Approve Access & Reactivate',
          message: 'Approve access request for ' + email + '? The account will be reactivated and bound to this device.',
          warning: null,
          confirmText: 'Approve & Reactivate',
          isDanger: false,
          onConfirm: function () {
            executeApproveRequest(reqId, 'Approved by administrator via Institutional Oversight.');
          }
        };
        refreshView();
      };
    });

    var rejectBtns = document.querySelectorAll('.btn-reject-request');
    rejectBtns.forEach(function (btn) {
      btn.onclick = function () {
        var reqId = btn.getAttribute('data-req-id');
        var email = btn.getAttribute('data-user-email');

        state.confirmation = {
          title: 'Reject Access Request',
          message: 'Reject access request for ' + email + '?',
          warning: 'The account will remain deactivated and this request will be marked as rejected.',
          confirmText: 'Reject Request',
          isDanger: true,
          onConfirm: function () {
            executeRejectRequest(reqId, 'Rejected by administrator.');
          }
        };
        refreshView();
      };
    });

    var reqPrev = document.getElementById('admin-req-prev');
    var reqNext = document.getElementById('admin-req-next');
    if (reqPrev) reqPrev.onclick = function () { if (state.requestsPage > 1) loadAccessRequests(state.requestsPage - 1); };
    if (reqNext) reqNext.onclick = function () {
      var totalReqPages = Math.ceil(state.requestsTotal / state.requestsLimit) || 1;
      if (state.requestsPage < totalReqPages) loadAccessRequests(state.requestsPage + 1);
    };

    // 17. Generic Confirmation Modal Controls
    var confirmCancel = document.getElementById('admin-confirm-cancel-btn');
    var confirmAction = document.getElementById('admin-confirm-action-btn');
    if (confirmCancel) {
      confirmCancel.onclick = function () {
        state.confirmation = null;
        refreshView();
      };
    }
    if (confirmAction && state.confirmation && state.confirmation.onConfirm) {
      var actionFn = state.confirmation.onConfirm;
      confirmAction.onclick = function () {
        state.confirmation = null;
        actionFn();
      };
    }

    // 18. Audit Log Filters & Pagination
    var auditSearchInput = document.getElementById('admin-audit-user-search');
    var auditActionSelect = document.getElementById('admin-audit-action-filter');
    var auditStatusSelect = document.getElementById('admin-audit-status-filter');
    var auditSearchBtn = document.getElementById('admin-audit-search-submit');
    var auditResetBtn = document.getElementById('admin-audit-reset-btn');

    if (auditSearchBtn) {
      auditSearchBtn.onclick = function () {
        if (auditSearchInput) state.auditUserQuery = auditSearchInput.value;
        if (auditActionSelect) state.auditActionFilter = auditActionSelect.value;
        if (auditStatusSelect) state.auditStatusFilter = auditStatusSelect.value;
        loadAuditLogs(1);
      };
    }
    if (auditSearchInput) {
      auditSearchInput.onkeydown = function (e) {
        if (e.key === 'Enter') {
          state.auditUserQuery = auditSearchInput.value;
          if (auditActionSelect) state.auditActionFilter = auditActionSelect.value;
          if (auditStatusSelect) state.auditStatusFilter = auditStatusSelect.value;
          loadAuditLogs(1);
        }
      };
    }
    if (auditResetBtn) {
      auditResetBtn.onclick = function () {
        state.auditUserQuery = '';
        state.auditActionFilter = '';
        state.auditStatusFilter = '';
        if (auditSearchInput) auditSearchInput.value = '';
        if (auditActionSelect) auditActionSelect.value = '';
        if (auditStatusSelect) auditStatusSelect.value = '';
        loadAuditLogs(1);
      };
    }
    var auditPrev = document.getElementById('admin-audit-prev');
    var auditNext = document.getElementById('admin-audit-next');
    if (auditPrev) auditPrev.onclick = function () { if (state.auditPage > 1) loadAuditLogs(state.auditPage - 1); };
    if (auditNext) auditNext.onclick = function () {
      var totalAuditPages = Math.ceil(state.auditTotal / state.auditLimit) || 1;
      if (state.auditPage < totalAuditPages) loadAuditLogs(state.auditPage + 1);
    };

    // 19. Client-Side Live Duration Updates (15s interval)
    if (state.durationTimerId) {
      clearInterval(state.durationTimerId);
      state.durationTimerId = null;
    }
    state.durationTimerId = setInterval(function () {
      var liveEls = document.querySelectorAll('.live-duration[data-session-start]');
      var now = Date.now();
      liveEls.forEach(function (el) {
        var startIso = el.getAttribute('data-session-start');
        if (!startIso) return;
        var startTime = new Date(startIso).getTime();
        if (isNaN(startTime)) return;
        var elapsedSec = Math.max(0, Math.floor((now - startTime) / 1000));
        el.textContent = '(Current: ' + formatDuration(elapsedSec) + ')';
      });
    }, 15000);
  }

  function clearData() {
    if (state.durationTimerId) {
      clearInterval(state.durationTimerId);
      state.durationTimerId = null;
    }
    if (state.inactivityTimerId) {
      clearInterval(state.inactivityTimerId);
      state.inactivityTimerId = null;
    }
    state.users = [];
    state.totalUsers = 0;
    state.metrics = null;
    state.selectedUser = null;
    state.accessRequests = [];
    state.requestsTotal = 0;
    state.allSessions = [];
    state.sessionsTotal = 0;
    state.auditLogs = [];
    state.auditTotal = 0;
    state.confirmation = null;
    state.isUnlocked = false;
    state.isUnauthorized = false;
    state.error = null;
    state.showChangePasswordModal = false;
  }

  // ---------------------------------------------------------------------------
  // Global Export
  // ---------------------------------------------------------------------------
  window.AYUR_ADMIN = {
    render: function () {
      setupInactivityWatcher();
      if (state.users.length === 0 && !state.isLoading && !state.isUnauthorized) {
        loadUsers(1);
      }
      return renderAdminConsole();
    },
    bindEvents: bindEvents,
    loadUsers: loadUsers,
    loadAccessRequests: loadAccessRequests,
    loadAllSessions: loadAllSessions,
    loadAuditLogs: loadAuditLogs,
    clearData: clearData,
    getState: function () { return state; }
  };

})();
