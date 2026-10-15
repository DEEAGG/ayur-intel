/**
 * AYUR-INTEL — Private Admin Console UI Module (Phase 3B)
 *
 * Implements administrative interface for user management, device session tracking,
 * remote session revocation, and immutable system audit log inspection.
 *
 * Security & Architecture Policies:
 * - Rendered only when the authenticated user's server-verified role is 'admin'.
 * - 401/403 responses trigger immediate data purging and access-denied state.
 * - All actions (activate/deactivate, session revocation) require explicit confirmation.
 * - Never renders secrets, tokens, or password hashes.
 */

(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Module State
  // ---------------------------------------------------------------------------
  var state = {
    activeTab: 'users', // 'users' | 'audit'

    // Users & Session Tracking
    users: [],
    totalUsers: 0,
    userPage: 1,
    userLimit: 15,
    userQuery: '',
    statusFilter: 'all', // 'all' | 'active' | 'inactive'

    // User Detail & Sessions Modal
    selectedUser: null,
    loadingUserDetail: false,

    // System Audit Logs
    auditLogs: [],
    auditTotal: 0,
    auditPage: 1,
    auditLimit: 25,
    auditUserQuery: '',
    auditActionFilter: '',
    auditStatusFilter: '',

    // Global View State
    isLoading: false,
    isAuditLoading: false,
    error: null,
    isUnauthorized: false,

    // Confirmation Dialog State
    confirmation: null // { title, message, warning, confirmText, isDanger, onConfirm }
  };

  // Helper: HTML Escaping
  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Helper: Format ISO Dates
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

  // Helper: Call Backend API with Authorization
  async function callApi(url, opts) {
    if (window.AYUR && typeof window.AYUR.api === 'function') {
      return await window.AYUR.api(url, opts);
    }
    var options = Object.assign({}, opts || {});
    var headers = Object.assign({}, options.headers || {});
    var token = (window.AYUR_AUTH && typeof window.AYUR_AUTH.getToken === 'function')
      ? window.AYUR_AUTH.getToken()
      : '';
    if (token && !headers['Authorization']) {
      headers['Authorization'] = 'Bearer ' + token;
    }
    options.headers = headers;

    var resp = await fetch(url, options);
    if (!resp.ok) {
      var errText = await resp.text();
      var errObj = null;
      try { errObj = JSON.parse(errText); } catch (_) {}
      var msg = (errObj && (errObj.detail || errObj.message || errObj.error)) || errText || ('HTTP ' + resp.status);
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
  // Data Fetching
  // ---------------------------------------------------------------------------

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
      var data = await callApi('/api/admin/users' + params);
      state.users = data.users || [];
      state.totalUsers = data.total || 0;
      state.isLoading = false;
      refreshView();
    } catch (e) {
      state.isLoading = false;
      if (e.status === 401 || e.status === 403) {
        clearData();
        state.isUnauthorized = true;
        showToast('Access denied: Administrator privileges required.', 'error');
      } else {
        state.error = e.message || 'Failed to load user directory.';
        showToast('Failed to load users: ' + state.error, 'error');
      }
      refreshView();
    }
  }

  async function loadUserDetail(userId) {
    state.loadingUserDetail = true;
    refreshView();

    try {
      var data = await callApi('/api/admin/users/' + encodeURIComponent(userId));
      state.selectedUser = data;
      state.loadingUserDetail = false;
      refreshView();
    } catch (e) {
      state.loadingUserDetail = false;
      showToast('Failed to load user details: ' + (e.message || 'Unknown error'), 'error');
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

      // Refresh current user list
      await loadUsers();

      // If modal for this user is open, refresh detail
      if (state.selectedUser && state.selectedUser.id === user.id) {
        await loadUserDetail(user.id);
      }
    } catch (e) {
      showToast('Status update failed: ' + (e.message || 'Server error'), 'error');
    }
  }

  async function executeRevokeSession(userId, sessionId) {
    try {
      var res = await callApi('/api/admin/users/' + encodeURIComponent(userId) + '/sessions/' + encodeURIComponent(sessionId) + '/revoke', {
        method: 'POST'
      });
      showToast(res.message || 'Session revoked successfully.', 'success');

      // Refresh detail and users
      if (state.selectedUser && state.selectedUser.id === userId) {
        await loadUserDetail(userId);
      }
      await loadUsers();
    } catch (e) {
      showToast('Failed to revoke session: ' + (e.message || 'Server error'), 'error');
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
      await loadUsers();
    } catch (e) {
      showToast('Failed to revoke all sessions: ' + (e.message || 'Server error'), 'error');
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
      } else {
        showToast('Failed to load audit logs: ' + (e.message || 'Server error'), 'error');
      }
      refreshView();
    }
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
    // 1. Unauthorized State
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

    // Filter users by client-side status filter if specified
    var filteredUsers = state.users;
    if (state.statusFilter === 'active') {
      filteredUsers = state.users.filter(function (u) { return u.is_active; });
    } else if (state.statusFilter === 'inactive') {
      filteredUsers = state.users.filter(function (u) { return !u.is_active; });
    }

    // Dynamic Overview KPIs (Computed from real backend data)
    var totalUsersCount = state.totalUsers;
    var activeUsersCount = state.users.filter(function (u) { return u.is_active; }).length;
    var inactiveUsersCount = state.users.filter(function (u) { return !u.is_active; }).length;
    var totalActiveSessions = state.users.reduce(function (acc, u) { return acc + (u.active_sessions_count || 0); }, 0);

    var html = ''
      + '<div class="admin-console-wrapper">'
      // Header & Title
      + '  <div class="admin-header">'
      + '    <div class="admin-header-titles">'
      + '      <div class="admin-header-badge">'
      + '        <span class="material-symbols-outlined">admin_panel_settings</span> Security Administration'
      + '      </div>'
      + '      <h1>Ayur-Intel Admin Console</h1>'
      + '      <p>Institutional oversight: manage verified accounts, inspect device sessions, remotely revoke access, and query immutable audit logs.</p>'
      + '    </div>'
      + '    <div class="admin-header-actions">'
      + '      <button class="btn btn-secondary btn-sm" id="admin-refresh-btn" title="Refresh backend data">'
      + '        <span class="material-symbols-outlined">sync</span> Refresh Data'
      + '      </button>'
      + '    </div>'
      + '  </div>'

      // Overview KPI Cards
      + '  <div class="admin-kpi-grid">'
      + '    <div class="admin-kpi-card">'
      + '      <div class="admin-kpi-icon" style="color: #2D4A3E; background: #e8f5e9;">'
      + '        <span class="material-symbols-outlined">people</span>'
      + '      </div>'
      + '      <div class="admin-kpi-data">'
      + '        <div class="admin-kpi-val">' + totalUsersCount + '</div>'
      + '        <div class="admin-kpi-lbl">Total Registered Accounts</div>'
      + '      </div>'
      + '    </div>'

      + '    <div class="admin-kpi-card">'
      + '      <div class="admin-kpi-icon" style="color: #15803d; background: #dcfce7;">'
      + '        <span class="material-symbols-outlined">verified</span>'
      + '      </div>'
      + '      <div class="admin-kpi-data">'
      + '        <div class="admin-kpi-val">' + activeUsersCount + '</div>'
      + '        <div class="admin-kpi-lbl">Active Users (Page)</div>'
      + '      </div>'
      + '    </div>'

      + '    <div class="admin-kpi-card">'
      + '      <div class="admin-kpi-icon" style="color: #0284c7; background: #e0f2fe;">'
      + '        <span class="material-symbols-outlined">devices</span>'
      + '      </div>'
      + '      <div class="admin-kpi-data">'
      + '        <div class="admin-kpi-val">' + totalActiveSessions + '</div>'
      + '        <div class="admin-kpi-lbl">Active Device Sessions (Page)</div>'
      + '      </div>'
      + '    </div>'

      + '    <div class="admin-kpi-card">'
      + '      <div class="admin-kpi-icon" style="color: #b91c1c; background: #fee2e2;">'
      + '        <span class="material-symbols-outlined">block</span>'
      + '      </div>'
      + '      <div class="admin-kpi-data">'
      + '        <div class="admin-kpi-val">' + inactiveUsersCount + '</div>'
      + '        <div class="admin-kpi-lbl">Deactivated / Blocked (Page)</div>'
      + '      </div>'
      + '    </div>'
      + '  </div>'

      // Navigation Tabs
      + '  <div class="admin-tabs">'
      + '    <button class="admin-tab-btn ' + (state.activeTab === 'users' ? 'active' : '') + '" data-admin-tab="users">'
      + '      <span class="material-symbols-outlined">manage_accounts</span> User Directory &amp; Sessions'
      + '    </button>'
      + '    <button class="admin-tab-btn ' + (state.activeTab === 'audit' ? 'active' : '') + '" data-admin-tab="audit">'
      + '      <span class="material-symbols-outlined">history</span> Immutable Audit Trail'
      + '    </button>'
      + '  </div>';

    // -------------------------------------------------------------------------
    // TAB 1: USERS & SESSIONS
    // -------------------------------------------------------------------------
    if (state.activeTab === 'users') {
      var totalUserPages = Math.ceil(state.totalUsers / state.userLimit) || 1;
      var startIdx = (state.userPage - 1) * state.userLimit + 1;
      var endIdx = Math.min(state.userPage * state.userLimit, state.totalUsers);

      html += ''
        + '  <div class="admin-card">'
        // Filter & Search Controls
        + '    <div class="admin-filter-bar">'
        + '      <div class="admin-search-wrap">'
        + '        <span class="material-symbols-outlined">search</span>'
        + '        <input type="text" id="admin-user-search" class="admin-search-input" placeholder="Search by name, email, or username..." value="' + escapeHtml(state.userQuery) + '">'
        + '        ' + (state.userQuery ? '<button class="admin-clear-search-btn" id="admin-clear-search-btn" title="Clear search">×</button>' : '')
        + '      </div>'
        + '      <div class="admin-filter-actions">'
        + '        <select id="admin-status-filter" class="admin-select">'
        + '          <option value="all" ' + (state.statusFilter === 'all' ? 'selected' : '') + '>All Statuses</option>'
        + '          <option value="active" ' + (state.statusFilter === 'active' ? 'selected' : '') + '>Active Only</option>'
        + '          <option value="inactive" ' + (state.statusFilter === 'inactive' ? 'selected' : '') + '>Deactivated Only</option>'
        + '        </select>'
        + '        <button class="btn btn-primary btn-sm" id="admin-search-submit-btn">'
        + '          <span class="material-symbols-outlined">filter_list</span> Search'
        + '        </button>'
        + '      </div>'
        + '    </div>'

        // User Directory Table
        + '    <div class="admin-table-container">'
        + '      <table class="admin-table">'
        + '        <thead>'
        + '          <tr>'
        + '            <th>User Account</th>'
        + '            <th>Email Address</th>'
        + '            <th>Role</th>'
        + '            <th>Status</th>'
        + '            <th>Active Sessions</th>'
        + '            <th>Joined Date</th>'
        + '            <th style="text-align: right;">Administrative Actions</th>'
        + '          </tr>'
        + '        </thead>'
        + '        <tbody>';

      if (state.isLoading) {
        html += '<tr><td colspan="7" class="admin-empty-cell"><div class="admin-spinner"></div> Loading user directory...</td></tr>';
      } else if (filteredUsers.length === 0) {
        html += '<tr><td colspan="7" class="admin-empty-cell"><div class="admin-empty-icon"><span class="material-symbols-outlined">person_search</span></div><p>No user accounts match the current filter or search criteria.</p></td></tr>';
      } else {
        filteredUsers.forEach(function (u) {
          var isSelf = currentUser && (currentUser.id === u.id || currentUser.public_id === u.id);
          var roleBadgeClass = u.role === 'admin' ? 'badge-admin' : 'badge-user';
          var statusBadge = u.is_active
            ? '<span class="admin-badge badge-active"><span class="admin-badge-dot"></span> Active</span>'
            : '<span class="admin-badge badge-inactive"><span class="admin-badge-dot"></span> Deactivated</span>';

          var sessionBadge = u.active_sessions_count > 0
            ? '<span class="admin-badge badge-sessions"><span class="material-symbols-outlined" style="font-size:12px;">devices</span> ' + u.active_sessions_count + ' active</span>'
            : '<span class="admin-badge badge-idle">None</span>';

          html += ''
            + '      <tr class="' + (!u.is_active ? 'tr-deactivated' : '') + '">'
            + '        <td>'
            + '          <div class="admin-user-cell">'
            + '            <div class="admin-user-avatar" style="background-color: ' + (window.AYUR_AUTH ? window.AYUR_AUTH.getAvatarColor(u.display_name || u.email) : '#476558') + ';">'
            + '              ' + (window.AYUR_AUTH ? window.AYUR_AUTH.getInitials(u.display_name, u.email) : 'U')
            + '            </div>'
            + '            <div class="admin-user-info">'
            + '              <strong>' + escapeHtml(u.display_name || u.username) + (isSelf ? ' <span class="self-tag">(You)</span>' : '') + '</strong>'
            + '              <small>@' + escapeHtml(u.username) + '</small>'
            + '            </div>'
            + '          </div>'
            + '        </td>'
            + '        <td><span class="mono-text">' + escapeHtml(u.email || '—') + '</span></td>'
            + '        <td><span class="admin-badge ' + roleBadgeClass + '">' + escapeHtml(u.role) + '</span></td>'
            + '        <td>' + statusBadge + '</td>'
            + '        <td>' + sessionBadge + '</td>'
            + '        <td><span class="mono-date">' + formatDate(u.created_at) + '</span></td>'
            + '        <td style="text-align: right;">'
            + '          <div class="admin-action-btn-group">'
            + '            <button class="btn btn-secondary btn-xs btn-inspect-user" data-user-id="' + escapeHtml(u.id) + '" title="View complete details and device sessions">'
            + '              <span class="material-symbols-outlined">visibility</span> Inspect'
            + '            </button>';

          if (u.is_active) {
            html += ''
              + '            <button class="btn btn-danger-outline btn-xs btn-toggle-status" data-user-id="' + escapeHtml(u.id) + '" data-user-name="' + escapeHtml(u.display_name || u.username) + '" data-active="false" ' + (isSelf ? 'disabled title="You cannot deactivate your own administrator account"' : 'title="Deactivate account and revoke all sessions"') + '>'
              + '              <span class="material-symbols-outlined">block</span> Deactivate'
              + '            </button>';
          } else {
            html += ''
              + '            <button class="btn btn-success-outline btn-xs btn-toggle-status" data-user-id="' + escapeHtml(u.id) + '" data-user-name="' + escapeHtml(u.display_name || u.username) + '" data-active="true" title="Restore account login access">'
              + '              <span class="material-symbols-outlined">check_circle</span> Activate'
              + '            </button>';
          }

          html += ''
            + '          </div>'
            + '        </td>'
            + '      </tr>';
        });
      }

      html += ''
        + '        </tbody>'
        + '      </table>'
        + '    </div>'

        // User Pagination
        + '    <div class="admin-pagination">'
        + '      <div class="admin-pagination-info">'
        + '        Showing <strong>' + (state.totalUsers > 0 ? startIdx : 0) + '–' + endIdx + '</strong> of <strong>' + state.totalUsers + '</strong> users'
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
    // TAB 2: SYSTEM AUDIT TRAIL
    // -------------------------------------------------------------------------
    if (state.activeTab === 'audit') {
      var totalAuditPages = Math.ceil(state.auditTotal / state.auditLimit) || 1;
      var auditStartIdx = (state.auditPage - 1) * state.auditLimit + 1;
      var auditEndIdx = Math.min(state.auditPage * state.auditLimit, state.auditTotal);

      html += ''
        + '  <div class="admin-card">'
        // Filter Controls
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

        // Audit Log Table
        + '    <div class="admin-table-container">'
        + '      <table class="admin-table">'
        + '        <thead>'
        + '          <tr>'
        + '            <th>Timestamp (UTC)</th>'
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

        // Audit Pagination
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
    // User Inspection & Session Modal
    // -------------------------------------------------------------------------
    if (state.selectedUser) {
      var sel = state.selectedUser;
      var isSelfModal = currentUser && (currentUser.id === sel.id || currentUser.public_id === sel.id);
      var sessions = sel.recent_sessions || [];

      html += ''
        + '<div class="admin-modal-backdrop" id="admin-user-modal">'
        + '  <div class="admin-modal admin-modal-lg">'
        + '    <div class="admin-modal-head">'
        + '      <div class="admin-modal-title">'
        + '        <span class="material-symbols-outlined">shield_person</span>'
        + '        <h2>User Profile &amp; Device Sessions</h2>'
        + '      </div>'
        + '      <button class="admin-modal-close" id="admin-modal-close-btn" title="Close modal">×</button>'
        + '    </div>'
        + '    <div class="admin-modal-body">'
        // User Profile Summary Card
        + '      <div class="admin-user-modal-summary">'
        + '        <div class="admin-user-avatar lg" style="background-color: ' + (window.AYUR_AUTH ? window.AYUR_AUTH.getAvatarColor(sel.display_name || sel.email) : '#476558') + ';">'
        + '          ' + (window.AYUR_AUTH ? window.AYUR_AUTH.getInitials(sel.display_name, sel.email) : 'U')
        + '        </div>'
        + '        <div class="admin-user-modal-meta">'
        + '          <div class="admin-user-modal-name-row">'
        + '            <h3>' + escapeHtml(sel.display_name || sel.username) + '</h3>'
        + '            <span class="admin-badge ' + (sel.role === 'admin' ? 'badge-admin' : 'badge-user') + '">' + escapeHtml(sel.role) + '</span>'
        + '            ' + (sel.is_active ? '<span class="admin-badge badge-active">Active</span>' : '<span class="admin-badge badge-inactive">Deactivated</span>')
        + '          </div>'
        + '          <div class="admin-meta-grid">'
        + '            <div><small>Email:</small> <strong>' + escapeHtml(sel.email || '—') + '</strong></div>'
        + '            <div><small>Username:</small> <strong>@' + escapeHtml(sel.username) + '</strong></div>'
        + '            <div><small>Public ID:</small> <span class="mono-text">' + escapeHtml(sel.id) + '</span></div>'
        + '            <div><small>Registered:</small> <span class="mono-date">' + formatDate(sel.created_at) + '</span></div>'
        + '          </div>'
        + '        </div>'
        + '      </div>'

        // Actions Header
        + '      <div class="admin-session-header">'
        + '        <div>'
        + '          <h4>Active Sessions &amp; Login History</h4>'
        + '          <p>Review logged-in devices and remotely revoke individual sessions or force logout across all platforms.</p>'
        + '        </div>'
        + '        <div>'
        + '          <button class="btn btn-danger-outline btn-sm" id="admin-revoke-all-btn" data-user-id="' + escapeHtml(sel.id) + '" data-user-name="' + escapeHtml(sel.display_name || sel.username) + '" ' + (sessions.length === 0 ? 'disabled' : '') + '>'
        + '            <span class="material-symbols-outlined">power_settings_new</span> Logout from All Devices'
        + '          </button>'
        + '        </div>'
        + '      </div>'

        // Sessions Table
        + '      <div class="admin-table-container">'
        + '        <table class="admin-table">'
        + '          <thead>'
        + '            <tr>'
        + '              <th>Client Device &amp; Browser</th>'
        + '              <th>IP Address</th>'
        + '              <th>Created (UTC)</th>'
        + '              <th>Last Active</th>'
        + '              <th>Status</th>'
        + '              <th style="text-align: right;">Action</th>'
        + '            </tr>'
        + '          </thead>'
        + '          <tbody>';

      if (sessions.length === 0) {
        html += '<tr><td colspan="6" class="admin-empty-cell"><p>No session activity recorded for this user.</p></td></tr>';
      } else {
        sessions.forEach(function (s) {
          var isRevoked = s.is_revoked;
          var statusBadge = isRevoked
            ? '<span class="admin-badge badge-inactive">Revoked</span>'
            : '<span class="admin-badge badge-active">Active</span>';

          html += ''
            + '      <tr class="' + (isRevoked ? 'tr-revoked' : '') + '">'
            + '        <td>'
            + '          <div class="admin-device-info">'
            + '            <span class="material-symbols-outlined admin-device-icon">computer</span>'
            + '            <div>'
            + '              <strong>' + escapeHtml(s.device_info || 'Unknown Device') + '</strong>'
            + '              ' + (s.user_agent ? '<small class="text-muted" title="' + escapeHtml(s.user_agent) + '">' + escapeHtml(s.user_agent.substring(0, 50)) + '...</small>' : '')
            + '            </div>'
            + '          </div>'
            + '        </td>'
            + '        <td><span class="mono-ip">' + escapeHtml(s.ip_address || '—') + '</span></td>'
            + '        <td><span class="mono-date">' + formatDate(s.created_at) + '</span></td>'
            + '        <td><span class="mono-date">' + formatDate(s.last_active_at) + '</span></td>'
            + '        <td>' + statusBadge + '</td>'
            + '        <td style="text-align: right;">';

          if (!isRevoked) {
            html += ''
              + '          <button class="btn btn-danger-outline btn-xs btn-revoke-session" data-user-id="' + escapeHtml(sel.id) + '" data-session-id="' + escapeHtml(s.id) + '" data-device="' + escapeHtml(s.device_info || s.ip_address || 'this device') + '">'
              + '            <span class="material-symbols-outlined">logout</span> Revoke Session'
              + '          </button>';
          } else {
            html += '<span class="text-muted" style="font-size:12px;">Terminated</span>';
          }

          html += ''
            + '        </td>'
            + '      </tr>';
        });
      }

      html += ''
        + '          </tbody>'
        + '        </table>'
        + '      </div>'
        + '    </div>'
        + '    <div class="admin-modal-foot">'
        + '      <button class="btn btn-secondary" id="admin-modal-foot-close-btn">Close</button>'
        + '    </div>'
        + '  </div>'
        + '</div>';
    }

    // -------------------------------------------------------------------------
    // Generic Confirmation Dialog Modal
    // -------------------------------------------------------------------------
    if (state.confirmation) {
      var c = state.confirmation;
      html += ''
        + '<div class="admin-modal-backdrop" id="admin-confirm-modal">'
        + '  <div class="admin-modal admin-modal-sm">'
        + '    <div class="admin-modal-head">'
        + '      <div class="admin-modal-title">'
        + '        <span class="material-symbols-outlined" style="color: ' + (c.isDanger ? '#b91c1c' : '#2D4A3E') + ';">' + (c.isDanger ? 'warning' : 'help') + '</span>'
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

    html += '</div>'; // End admin-console-wrapper
    return html;
  }

  // ---------------------------------------------------------------------------
  // Event Binding
  // ---------------------------------------------------------------------------

  function bindEvents() {
    // 1. Refresh Button
    var refreshBtn = document.getElementById('admin-refresh-btn');
    if (refreshBtn) {
      refreshBtn.onclick = function () {
        if (state.activeTab === 'users') loadUsers();
        else loadAuditLogs();
      };
    }

    // 2. Navigation Tabs
    var tabBtns = document.querySelectorAll('.admin-tab-btn[data-admin-tab]');
    tabBtns.forEach(function (btn) {
      btn.onclick = function () {
        var tab = btn.getAttribute('data-admin-tab');
        if (tab && state.activeTab !== tab) {
          state.activeTab = tab;
          if (tab === 'users' && state.users.length === 0) loadUsers(1);
          if (tab === 'audit' && state.auditLogs.length === 0) loadAuditLogs(1);
          refreshView();
        }
      };
    });

    // 3. User Search & Filter
    var searchInput = document.getElementById('admin-user-search');
    var statusSelect = document.getElementById('admin-status-filter');
    var searchSubmit = document.getElementById('admin-search-submit-btn');
    var clearSearch = document.getElementById('admin-clear-search-btn');

    if (searchSubmit) {
      searchSubmit.onclick = function () {
        if (searchInput) state.userQuery = searchInput.value;
        if (statusSelect) state.statusFilter = statusSelect.value;
        loadUsers(1);
      };
    }
    if (searchInput) {
      searchInput.onkeydown = function (e) {
        if (e.key === 'Enter') {
          state.userQuery = searchInput.value;
          if (statusSelect) state.statusFilter = statusSelect.value;
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
        refreshView();
      };
    }

    // 4. User Pagination
    var userPrev = document.getElementById('admin-user-prev');
    var userNext = document.getElementById('admin-user-next');
    if (userPrev) {
      userPrev.onclick = function () {
        if (state.userPage > 1) loadUsers(state.userPage - 1);
      };
    }
    if (userNext) {
      userNext.onclick = function () {
        var totalUserPages = Math.ceil(state.totalUsers / state.userLimit) || 1;
        if (state.userPage < totalUserPages) loadUsers(state.userPage + 1);
      };
    }

    // 5. Inspect User & Detail
    var inspectBtns = document.querySelectorAll('.btn-inspect-user');
    inspectBtns.forEach(function (b) {
      b.onclick = function () {
        var uid = b.getAttribute('data-user-id');
        if (uid) loadUserDetail(uid);
      };
    });

    // 6. Toggle Status (Activate / Deactivate) with Confirmation
    var toggleStatusBtns = document.querySelectorAll('.btn-toggle-status');
    toggleStatusBtns.forEach(function (b) {
      b.onclick = function () {
        var uid = b.getAttribute('data-user-id');
        var uname = b.getAttribute('data-user-name');
        var makeActive = b.getAttribute('data-active') === 'true';

        if (!makeActive) {
          state.confirmation = {
            title: 'Deactivate Account',
            message: 'Are you sure you want to deactivate the user account for ' + uname + '?',
            warning: 'Immediate Security Effect: All active device sessions will be invalidated immediately, and any subsequent authenticated requests will be blocked.',
            confirmText: 'Deactivate User',
            isDanger: true,
            onConfirm: function () {
              executeStatusChange({ id: uid, username: uname }, false);
            }
          };
        } else {
          state.confirmation = {
            title: 'Activate Account',
            message: 'Restore system access for ' + uname + '? The user will be permitted to authenticate and create new sessions.',
            warning: null,
            confirmText: 'Activate User',
            isDanger: false,
            onConfirm: function () {
              executeStatusChange({ id: uid, username: uname }, true);
            }
          };
        }
        refreshView();
      };
    });

    // 7. Modal Close Buttons
    var modalCloseBtn = document.getElementById('admin-modal-close-btn');
    var modalFootClose = document.getElementById('admin-modal-foot-close-btn');
    if (modalCloseBtn) {
      modalCloseBtn.onclick = function () {
        state.selectedUser = null;
        refreshView();
      };
    }
    if (modalFootClose) {
      modalFootClose.onclick = function () {
        state.selectedUser = null;
        refreshView();
      };
    }

    // 8. Revoke Individual Session with Confirmation
    var revokeSessBtns = document.querySelectorAll('.btn-revoke-session');
    revokeSessBtns.forEach(function (b) {
      b.onclick = function () {
        var uid = b.getAttribute('data-user-id');
        var sid = b.getAttribute('data-session-id');
        var dev = b.getAttribute('data-device');

        state.confirmation = {
          title: 'Revoke Device Session',
          message: 'Revoke active session for ' + dev + '?',
          warning: 'The user will be immediately logged out of this device upon their next request.',
          confirmText: 'Revoke Session',
          isDanger: true,
          onConfirm: function () {
            executeRevokeSession(uid, sid);
          }
        };
        refreshView();
      };
    });

    // 9. Revoke All Sessions with Confirmation
    var revokeAllBtn = document.getElementById('admin-revoke-all-btn');
    if (revokeAllBtn) {
      revokeAllBtn.onclick = function () {
        var uid = revokeAllBtn.getAttribute('data-user-id');
        var uname = revokeAllBtn.getAttribute('data-user-name');

        state.confirmation = {
          title: 'Revoke All Device Sessions',
          message: 'Terminate all active sessions across all devices for ' + uname + '?',
          warning: 'This will invalidate every active access token for this user. The user will be required to re-authenticate on all devices.',
          confirmText: 'Logout All Devices',
          isDanger: true,
          onConfirm: function () {
            executeRevokeAllSessions(uid, uname);
          }
        };
        refreshView();
      };
    }

    // 10. Confirmation Modal Buttons
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

    // 11. Audit Log Filter & Pagination
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
    if (auditPrev) {
      auditPrev.onclick = function () {
        if (state.auditPage > 1) loadAuditLogs(state.auditPage - 1);
      };
    }
    if (auditNext) {
      auditNext.onclick = function () {
        var totalAuditPages = Math.ceil(state.auditTotal / state.auditLimit) || 1;
        if (state.auditPage < totalAuditPages) loadAuditLogs(state.auditPage + 1);
      };
    }
  }

  function clearData() {
    state.users = [];
    state.totalUsers = 0;
    state.selectedUser = null;
    state.auditLogs = [];
    state.auditTotal = 0;
    state.confirmation = null;
    state.isUnauthorized = false;
    state.error = null;
  }

  // ---------------------------------------------------------------------------
  // Global Export
  // ---------------------------------------------------------------------------
  window.AYUR_ADMIN = {
    render: function () {
      // If users list is empty and not currently loading, trigger initial load
      if (state.users.length === 0 && !state.isLoading && !state.isUnauthorized) {
        loadUsers(1);
      }
      return renderAdminConsole();
    },
    bindEvents: bindEvents,
    loadUsers: loadUsers,
    loadAuditLogs: loadAuditLogs,
    clearData: clearData,
    getState: function () { return state; }
  };

})();
