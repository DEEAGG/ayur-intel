/**
 * AYUR-INTEL — Unified Authentication & Profile Management Handler
 *
 * Provides authentication (Sign In / Create Account), post-signup login redirect,
 * email validation, deterministic avatar styling, profile updating, password changes,
 * account switching, and account deletion.
 */

(function () {
  'use strict';

  var CURRENT_MODE = 'signin'; // 'signin' | 'signup'

  var AVATAR_COLORS = [
    '#7dba9a', '#4ecdc4', '#45b7d1', '#6c5ce7',
    '#fd79a8', '#fdcb6e', '#e17055', '#00b894'
  ];

  // ---------------------------------------------------------------------------
  // Local Storage & Token Helpers
  // ---------------------------------------------------------------------------
  function getToken() {
    return localStorage.getItem('ayur_auth_token') || '';
  }

  function setToken(token) {
    if (token) {
      localStorage.setItem('ayur_auth_token', token);
    } else {
      localStorage.removeItem('ayur_auth_token');
    }
  }

  function getUser() {
    try {
      var u = localStorage.getItem('ayur_user');
      return u ? JSON.parse(u) : null;
    } catch (e) {
      return null;
    }
  }

  function setUser(user) {
    if (user) {
      localStorage.setItem('ayur_user', JSON.stringify(user));
    } else {
      localStorage.removeItem('ayur_user');
    }
  }

  // ---------------------------------------------------------------------------
  // Validation & Formatting Helpers
  // ---------------------------------------------------------------------------
  function isValidEmail(email) {
    var re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(String(email).trim().toLowerCase());
  }

  function showToastMsg(msg, type) {
    if (typeof showToast === 'function') {
      showToast(msg, type || 'info');
    } else if (typeof toast === 'function') {
      toast(msg, type || 'info');
    } else {
      alert(msg);
    }
  }

  function getAvatarColor(nameOrEmail) {
    if (!nameOrEmail) return AVATAR_COLORS[0];
    var str = String(nameOrEmail).trim();
    var hash = 0;
    for (var i = 0; i < str.length; i++) {
      hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    var index = Math.abs(hash) % AVATAR_COLORS.length;
    return AVATAR_COLORS[index];
  }

  function getInitials(name, email) {
    var source = (name || email || 'User').trim();
    if (!source) return 'U';
    var parts = source.split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return source.substring(0, 2).toUpperCase();
  }

  // ---------------------------------------------------------------------------
  // Auth Modal & Card Renderer
  // ---------------------------------------------------------------------------
  function ensureAuthOverlay() {
    var overlay = document.getElementById('auth-overlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'auth-overlay';
      overlay.className = 'auth-overlay';
      document.body.appendChild(overlay);
    }
    return overlay;
  }

  function renderAuthCard(mode, defaultEmail) {
    CURRENT_MODE = mode || 'signin';
    var overlay = ensureAuthOverlay();
    overlay.style.display = 'flex';

    var isSignIn = CURRENT_MODE === 'signin';

    var html = ''
      + '<div class="auth-card">'
      // Brand Header
      + '<div class="auth-brand">'
      + '<div class="auth-brand-icon">'
      + '<span class="material-symbols-outlined">spa</span>'
      + '</div>'
      + '<h1 class="auth-brand-title">AYUR-INTEL</h1>'
      + '<p class="auth-brand-subtitle">Product Intelligence</p>'
      + '</div>'

      // Mode Navigation Tabs
      + '<div class="auth-tabs">'
      + '<button class="auth-tab ' + (isSignIn ? 'active' : '') + '" onclick="window.AYUR_AUTH.switchMode(\'signin\')">Sign In</button>'
      + '<button class="auth-tab ' + (!isSignIn ? 'active' : '') + '" onclick="window.AYUR_AUTH.switchMode(\'signup\')">Create Account</button>'
      + '</div>'

      // Auth Form
      + '<form class="auth-form" id="auth-form" onsubmit="window.AYUR_AUTH.handleSubmit(event)">';

    if (!isSignIn) {
      html += '<div class="auth-field">'
        + '<label for="auth-fullname">Full Name</label>'
        + '<input type="text" id="auth-fullname" placeholder="e.g. Deepansh Aggarwal" required autocomplete="name">'
        + '</div>';
    }

    html += '<div class="auth-field">'
      + '<label for="auth-email">Email Address</label>'
      + '<input type="email" id="auth-email" placeholder="name@company.com" value="' + (defaultEmail || '') + '" required autocomplete="email">'
      + '</div>'

      + '<div class="auth-field">'
      + '<label for="auth-password">Password</label>'
      + '<input type="password" id="auth-password" placeholder="••••••••" required minlength="8" autocomplete="' + (isSignIn ? 'current-password' : 'new-password') + '">'
      + '<small class="auth-hint">Must be at least 8 characters</small>'
      + '</div>';

    if (!isSignIn) {
      html += '<div class="auth-field">'
        + '<label for="auth-confirm-password">Confirm Password</label>'
        + '<input type="password" id="auth-confirm-password" placeholder="••••••••" required minlength="8" autocomplete="new-password">'
        + '</div>';
    }

    html += '<button type="submit" class="auth-submit-btn" id="auth-submit-btn">'
      + (isSignIn ? 'Sign In' : 'Create Account')
      + '</button>'
      + '</form>'

      // Toggle Link Footer
      + '<div class="auth-toggle-footer">'
      + (isSignIn
        ? 'Don\'t have an account? <a href="#" onclick="event.preventDefault(); window.AYUR_AUTH.switchMode(\'signup\')">Create one</a>'
        : 'Already have an account? <a href="#" onclick="event.preventDefault(); window.AYUR_AUTH.switchMode(\'signin\')">Sign in</a>'
      )
      + '</div>'

      + '</div>'; // End auth-card

    overlay.innerHTML = html;
  }

  function hideAuthOverlay() {
    var overlay = document.getElementById('auth-overlay');
    if (overlay) {
      overlay.style.display = 'none';
    }
  }

  // ---------------------------------------------------------------------------
  // Form Submission Handler
  // ---------------------------------------------------------------------------
  async function handleSubmit(event) {
    if (event) event.preventDefault();

    var email = (document.getElementById('auth-email')?.value || '').trim();
    var password = (document.getElementById('auth-password')?.value || '').trim();
    var submitBtn = document.getElementById('auth-submit-btn');

    if (!email || !password) {
      showToastMsg('⚠️ Please fill in all required fields', 'error');
      return;
    }

    if (!isValidEmail(email)) {
      showToastMsg('⚠️ Please enter a valid email address format', 'error');
      return;
    }

    if (password.length < 8) {
      showToastMsg('⚠️ Password must be at least 8 characters long', 'error');
      return;
    }

    if (CURRENT_MODE === 'signup') {
      var fullName = (document.getElementById('auth-fullname')?.value || '').trim();
      var confirmPassword = (document.getElementById('auth-confirm-password')?.value || '').trim();

      if (!fullName) {
        showToastMsg('⚠️ Please enter your full name', 'error');
        return;
      }

      if (password !== confirmPassword) {
        showToastMsg('⚠️ Passwords do not match', 'error');
        return;
      }
    }

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = '⏳ Processing...';
    }

    try {
      var endpoint = CURRENT_MODE === 'signup' ? '/api/auth/signup' : '/api/auth/login';
      var payload = CURRENT_MODE === 'signup'
        ? { full_name: fullName, email: email, password: password }
        : { email: email, password: password };

      var response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      var data = await response.json();

      if (response.ok && data.user) {
        if (CURRENT_MODE === 'signup') {
          // POST-SIGNUP REDIRECT TO LOGIN: Do NOT store token, redirect to Login form
          showToastMsg('✅ Account created! Please login to continue.', 'success');
          renderAuthCard('signin', email);
        } else {
          // LOGIN SUCCESS: Save token, update UI, hide overlay
          setToken(data.token);
          setUser(data.user);
          hideAuthOverlay();
          updateUIWithUser(data.user);
          showToastMsg('✅ Welcome back, ' + (data.user.display_name || data.user.username) + '!', 'success');

          if (window.AYUR && typeof window.AYUR.init === 'function') {
            window.AYUR.init();
          }
        }
      } else {
        var errorDetail = data.detail || (CURRENT_MODE === 'signup' ? 'Registration failed' : 'Invalid email or password');
        showToastMsg('❌ ' + errorDetail, 'error');
      }
    } catch (err) {
      console.error('Auth request exception:', err);
      showToastMsg('❌ Network error. Please try again.', 'error');
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = CURRENT_MODE === 'signup' ? 'Create Account' : 'Sign In';
      }
    }
  }

  // ---------------------------------------------------------------------------
  // Update Topbar / Sidebar UI with Logged In User Data
  // ---------------------------------------------------------------------------
  function updateUIWithUser(user) {
    if (!user) return;
    var name = user.display_name || user.username || 'User';
    var email = user.email || '';
    var initials = getInitials(name, email);
    var avatarUrl = user.avatar_url || '';
    var bgColor = avatarUrl && avatarUrl.startsWith('#') ? avatarUrl : getAvatarColor(name || email);

    // Sidebar footer
    var avatarElem = document.querySelector('.sidebar-footer .user-avatar');
    var nameElem = document.querySelector('.sidebar-footer .user-info strong');
    var roleElem = document.querySelector('.sidebar-footer .user-info small');
    var userPill = document.getElementById('sidebar-user-pill');

    if (avatarElem) {
      if (avatarUrl && avatarUrl.startsWith('data:image')) {
        avatarElem.innerHTML = '<img src="' + avatarUrl + '" alt="Avatar" style="width:100%;height:100%;aspect-ratio:1/1;object-fit:cover;border-radius:50%;display:block;">';
        avatarElem.style.background = 'transparent';
      } else {
        avatarElem.textContent = initials;
        avatarElem.style.backgroundColor = bgColor;
      }
    }
    if (nameElem) nameElem.textContent = name;
    if (roleElem) roleElem.textContent = email || 'Researcher';
    if (userPill) {
      userPill.onclick = function() {
        if (window.AYUR && typeof window.AYUR.navigateTo === 'function') {
          window.AYUR.navigateTo('profile');
        }
      };
      userPill.title = 'Click to view profile & settings';
    }

    // Topbar right avatar icon
    var topbarAvatar = document.getElementById('topbar-avatar-btn');
    if (topbarAvatar) {
      if (avatarUrl && avatarUrl.startsWith('data:image')) {
        topbarAvatar.innerHTML = '<img src="' + avatarUrl + '" alt="Avatar" style="width:100%;height:100%;aspect-ratio:1/1;object-fit:cover;border-radius:50%;display:block;">';
        topbarAvatar.style.backgroundColor = 'transparent';
      } else {
        topbarAvatar.textContent = initials[0] || 'U';
        topbarAvatar.style.backgroundColor = bgColor;
      }
      topbarAvatar.onclick = function() {
        if (window.AYUR && typeof window.AYUR.navigateTo === 'function') {
          window.AYUR.navigateTo('profile');
        }
      };
    }
  }

  // ---------------------------------------------------------------------------
  // Profile Management API Functions
  // ---------------------------------------------------------------------------
  async function updateProfile(fullName, email) {
    var token = getToken();
    if (!token) return { success: false, message: 'Not authenticated' };

    if (email && !isValidEmail(email)) {
      showToastMsg('⚠️ Invalid email format', 'error');
      return { success: false, message: 'Invalid email format' };
    }

    try {
      var res = await fetch('/api/auth/profile', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + token
        },
        body: JSON.stringify({ full_name: fullName, email: email })
      });
      var data = await res.json();
      if (res.ok && data.user) {
        setUser(data.user);
        updateUIWithUser(data.user);
        showToastMsg('✅ Personal information saved successfully!', 'success');
        return { success: true, user: data.user };
      } else {
        showToastMsg('❌ ' + (data.detail || 'Failed to update profile'), 'error');
        return { success: false, message: data.detail };
      }
    } catch (e) {
      console.error('Update profile error:', e);
      showToastMsg('❌ Network error while saving profile', 'error');
      return { success: false, message: 'Network error' };
    }
  }

  async function changePassword(oldPassword, newPassword) {
    var token = getToken();
    if (!token) return { success: false, message: 'Not authenticated' };

    if (!newPassword || newPassword.length < 8) {
      showToastMsg('⚠️ New password must be at least 8 characters', 'error');
      return { success: false, message: 'Password too short' };
    }

    try {
      var res = await fetch('/api/auth/password', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + token
        },
        body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
      });
      var data = await res.json();
      if (res.ok) {
        showToastMsg('🔒 Password updated successfully!', 'success');
        return { success: true };
      } else {
        showToastMsg('❌ ' + (data.detail || 'Failed to change password'), 'error');
        return { success: false, message: data.detail };
      }
    } catch (e) {
      console.error('Change password error:', e);
      showToastMsg('❌ Network error changing password', 'error');
      return { success: false, message: 'Network error' };
    }
  }

  async function updateAvatar(avatarUrl) {
    var token = getToken();
    if (!token) return { success: false, message: 'Not authenticated' };

    try {
      var res = await fetch('/api/auth/avatar', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + token
        },
        body: JSON.stringify({ avatar_url: avatarUrl || '' })
      });
      var data = await res.json();
      if (res.ok && data.user) {
        setUser(data.user);
        updateUIWithUser(data.user);
        showToastMsg('🖼️ Profile picture updated!', 'success');
        return { success: true, user: data.user };
      } else {
        showToastMsg('❌ ' + (data.detail || 'Failed to update avatar'), 'error');
        return { success: false, message: data.detail };
      }
    } catch (e) {
      console.error('Update avatar error:', e);
      showToastMsg('❌ Network error updating avatar', 'error');
      return { success: false, message: 'Network error' };
    }
  }

  function logout() {
    setToken('');
    setUser(null);
    showToastMsg('👋 Logged out successfully', 'info');
    renderAuthCard('signin');
  }

  function switchAccount() {
    if (confirm('Switch to a different account? You will be signed out of your current session.')) {
      logout();
    }
  }

  async function deleteAccount() {
    if (!confirm('⚠️ Are you sure you want to delete your account? This action is permanent and CANNOT be undone!')) {
      return;
    }

    var token = getToken();
    if (!token) {
      logout();
      return;
    }

    try {
      var res = await fetch('/api/auth/account', {
        method: 'DELETE',
        headers: { 'Authorization': 'Bearer ' + token }
      });
      var data = await res.json();
      if (res.ok) {
        setToken('');
        setUser(null);
        showToastMsg('🗑️ Account deleted successfully.', 'info');
        renderAuthCard('signin');
      } else {
        showToastMsg('❌ ' + (data.detail || 'Failed to delete account'), 'error');
      }
    } catch (e) {
      console.error('Delete account error:', e);
      showToastMsg('❌ Network error deleting account', 'error');
    }
  }

  // ---------------------------------------------------------------------------
  // Auto Authentication Check on Page Load
  // ---------------------------------------------------------------------------
  async function checkAuthOnLoad() {
    var token = getToken();
    if (!token) {
      renderAuthCard('signin');
      return;
    }

    try {
      var res = await fetch('/api/auth/me', {
        headers: { 'Authorization': 'Bearer ' + token }
      });
      var data = await res.json();
      if (res.ok && data.user) {
        setUser(data.user);
        updateUIWithUser(data.user);
        hideAuthOverlay();
      } else {
        setToken('');
        setUser(null);
        renderAuthCard('signin');
      }
    } catch (e) {
      console.error('Auth check error:', e);
      var cached = getUser();
      if (cached) {
        updateUIWithUser(cached);
        hideAuthOverlay();
      } else {
        renderAuthCard('signin');
      }
    }
  }

  // Global Export
  window.AYUR_AUTH = {
    init: checkAuthOnLoad,
    render: renderAuthCard,
    switchMode: renderAuthCard,
    handleSubmit: handleSubmit,
    updateProfile: updateProfile,
    changePassword: changePassword,
    updateAvatar: updateAvatar,
    logout: logout,
    switchAccount: switchAccount,
    deleteAccount: deleteAccount,
    getToken: getToken,
    getUser: getUser,
    getAvatarColor: getAvatarColor,
    getInitials: getInitials,
    AVATAR_COLORS: AVATAR_COLORS,
    updateUIWithUser: updateUIWithUser
  };

  document.addEventListener('DOMContentLoaded', function () {
    checkAuthOnLoad();
  });

})();
