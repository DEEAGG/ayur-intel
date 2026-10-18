/**
 * AYUR-INTEL — Unified Authentication & Profile Management Handler
 *
 * Provides premium botanical SaaS authentication (Sign In / Create Account / Reset Request),
 * session vs local storage token persistence, password show/hide micro-interactions,
 * email validation, deterministic avatar styling, profile updating, password changes,
 * account switching, and account deletion.
 */

(function () {
  'use strict';

  var CURRENT_MODE = 'signin'; // 'signin' | 'signup' | 'forgot'
  var isSubmitting = false;

  var AVATAR_COLORS = [
    '#7dba9a', '#4ecdc4', '#45b7d1', '#6c5ce7',
    '#fd79a8', '#fdcb6e', '#e17055', '#00b894'
  ];

  // ---------------------------------------------------------------------------
  // Local & Session Storage Token Helpers
  // ---------------------------------------------------------------------------
  function isRememberMePreferred() {
    try {
      return localStorage.getItem('ayur_remember_me') === 'true';
    } catch (e) {
      return false;
    }
  }

  function getRememberedEmail() {
    try {
      return localStorage.getItem('ayur_remembered_email') || '';
    } catch (e) {
      return '';
    }
  }

  function getToken() {
    try {
      // Prioritize sessionStorage for tab-bounded sessions, fall back to localStorage
      return sessionStorage.getItem('ayur_auth_token') || localStorage.getItem('ayur_auth_token') || '';
    } catch (e) {
      return '';
    }
  }

  function getDeviceId() {
    try {
      var devId = localStorage.getItem('ayur_device_id');
      if (!devId) {
        var arr = new Uint8Array(16);
        if (window.crypto && window.crypto.getRandomValues) {
          window.crypto.getRandomValues(arr);
        } else {
          for (var i = 0; i < 16; i++) arr[i] = Math.floor(Math.random() * 256);
        }
        devId = Array.from(arr, function (b) { return ('0' + b.toString(16)).slice(-2); }).join('');
        localStorage.setItem('ayur_device_id', devId);
      }
      return devId;
    } catch (_) {
      return 'dev_' + Math.random().toString(36).substring(2, 15);
    }
  }


  function setToken(token, rememberMe) {
    try {
      if (token) {
        if (rememberMe) {
          localStorage.setItem('ayur_auth_token', token);
          sessionStorage.removeItem('ayur_auth_token');
        } else {
          sessionStorage.setItem('ayur_auth_token', token);
          localStorage.removeItem('ayur_auth_token');
        }
      } else {
        localStorage.removeItem('ayur_auth_token');
        sessionStorage.removeItem('ayur_auth_token');
      }
    } catch (e) {
      console.warn('Storage setToken error:', e);
    }
  }

  function getUser() {
    try {
      var u = sessionStorage.getItem('ayur_user') || localStorage.getItem('ayur_user');
      return u ? JSON.parse(u) : null;
    } catch (e) {
      return null;
    }
  }

  function setUser(user, rememberMe) {
    try {
      if (user) {
        var str = JSON.stringify(user);
        if (rememberMe === true) {
          localStorage.setItem('ayur_user', str);
          sessionStorage.removeItem('ayur_user');
        } else if (rememberMe === false) {
          sessionStorage.setItem('ayur_user', str);
          localStorage.removeItem('ayur_user');
        } else {
          if (sessionStorage.getItem('ayur_auth_token')) {
            sessionStorage.setItem('ayur_user', str);
          } else {
            localStorage.setItem('ayur_user', str);
          }
        }
      } else {
        localStorage.removeItem('ayur_user');
        sessionStorage.removeItem('ayur_user');
      }
    } catch (e) {
      console.warn('Storage setUser error:', e);
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

  function setAlert(message, type) {
    var alertEl = document.getElementById('auth-alert');
    if (!alertEl) return;
    if (!message) {
      alertEl.style.display = 'none';
      alertEl.textContent = '';
      alertEl.className = 'auth-alert';
      return;
    }
    var iconName = type === 'success' ? 'check_circle' : (type === 'info' ? 'info' : 'error');
    alertEl.className = 'auth-alert auth-alert--' + (type || 'error');
    alertEl.innerHTML = '<span class="material-symbols-outlined auth-alert-icon" aria-hidden="true">' + iconName + '</span>'
      + '<span class="auth-alert-text">' + message + '</span>';
    alertEl.style.display = 'flex';
  }

  // ---------------------------------------------------------------------------
  // Password Visibility Toggle Handler
  // ---------------------------------------------------------------------------
  function togglePassword(inputId, btnElem) {
    var input = document.getElementById(inputId);
    if (!input) return;

    var isPassword = input.type === 'password';
    input.type = isPassword ? 'text' : 'password';

    if (btnElem) {
      btnElem.setAttribute('aria-pressed', isPassword ? 'true' : 'false');
      btnElem.setAttribute('aria-label', isPassword ? 'Hide password' : 'Show password');
      var icon = btnElem.querySelector('.material-symbols-outlined');
      if (icon) {
        icon.textContent = isPassword ? 'visibility_off' : 'visibility';
      }
    }
  }

  // ---------------------------------------------------------------------------
  // Auth Modal & Shell Renderer
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
    var isSignUp = CURRENT_MODE === 'signup';
    var isForgot = CURRENT_MODE === 'forgot';

    var emailVal = defaultEmail || (isRememberMePreferred() ? getRememberedEmail() : '');
    var rememberChecked = isRememberMePreferred();

    var html = ''
      + '<div class="auth-forest-scene" aria-hidden="true">'
      + '  <div class="auth-forest-glow"></div>'
      + '  <div class="auth-forest-layer auth-forest-far"><svg viewBox="0 0 1600 900" preserveAspectRatio="xMidYMax slice"><g fill="#153d2b"><path d="M0 900V450l55 95 30-130 40 80 42-190 55 180 42-100 35 140 48-230 55 250 43-130 38 160 40-90 42 150 48-250 55 240 40-130 50 180 38-100 48 160 52-220 48 230 42-140 45 170 55-270 50 250 45-130 45 170 55-200 48 230 48-110 55 180 42-240 58 250 50-130 48 170 52-200 58 220 40-110 45 150 0 300Z"/></g></svg></div>'
      + '  <div class="auth-forest-layer auth-forest-mid"><svg viewBox="0 0 1600 900" preserveAspectRatio="xMidYMax slice"><g fill="#0b281c"><path d="M0 900V600l45-90 42 90 20-160 48 160 38-115 43 115 25-205 55 205 40-125 45 125 20-170 55 170 38-95 45 95 32-220 58 220 42-135 48 135 30-190 55 190 42-110 50 110 25-230 60 230 42-145 48 145 30-170 52 170 44-120 48 120 34-205 60 205 45-130 50 130 32-180 55 180 40-100 50 100 0 300Z"/></g></svg></div>'
      + '  <div class="auth-forest-layer auth-forest-near"><svg viewBox="0 0 1600 900" preserveAspectRatio="xMidYMax slice"><g fill="#06170f"><path d="M0 900V720l35-70 38 70 25-150 48 150 32-85 38 85 25-125 45 125 28-90 45 90 25-165 50 165 30-85 45 85 32-130 48 130 30-75 45 75 25-155 50 155 38-90 45 90 25-125 50 125 32-85 48 85 30-155 50 155 35-80 48 80 25-140 50 140 30-85 50 85 0 180Z"/></g></svg></div>'
      + '  <div class="auth-forest-haze"></div>'
      + '</div>'
      + '<div class="auth-shell">'
      // Brand Pane (Left)
      + '  <div class="auth-brand-pane">'
      + '    <div>'
      + '      <div class="auth-brand-header">'
      + '        <div class="auth-brand-badge">'
      + '          <span class="material-symbols-outlined" aria-hidden="true">spa</span>'
      + '        </div>'
      + '        <div class="auth-brand-titles">'
      + '          <h1 class="auth-brand-title">AYUR-INTEL</h1>'
      + '          <div class="auth-brand-tagline">Evidence · Intelligence · Innovation</div>'
      + '        </div>'
      + '      </div>'
      + '      <p class="auth-brand-desc">'
      + '        Evidence-led Ayurvedic research, botanical intelligence, and IP insights — in one workspace.'
      + '      </p>'
      + '      <div class="auth-brand-pillars">'
      + '        <div class="auth-pillar-item">'
      + '          <span class="material-symbols-outlined auth-pillar-icon" aria-hidden="true">auto_stories</span>'
      + '          <div class="auth-pillar-content">'
      + '            <strong>Classical Knowledge</strong>'
      + '            <small>Sanskrit sources and Dravya profiles</small>'
      + '          </div>'
      + '        </div>'
      + '        <div class="auth-pillar-item">'
      + '          <span class="material-symbols-outlined auth-pillar-icon" aria-hidden="true">biotech</span>'
      + '          <div class="auth-pillar-content">'
      + '            <strong>Evidence &amp; Phytochemistry</strong>'
      + '            <small>Bioactive compounds and research findings</small>'
      + '          </div>'
      + '        </div>'
      + '        <div class="auth-pillar-item">'
      + '          <span class="material-symbols-outlined auth-pillar-icon" aria-hidden="true">verified_user</span>'
      + '          <div class="auth-pillar-content">'
      + '            <strong>Safety &amp; IP Intelligence</strong>'
      + '            <small>Regulatory signals and patent readiness</small>'
      + '          </div>'
      + '        </div>'
      + '      </div>'
      + '    </div>'
      + '    <div class="auth-brand-footer">'
      + '      <span class="auth-live-mark"><span></span> EVIDENCE-LED INTELLIGENCE</span>'
      + '    </div>'
      + '  </div>'

      // Authentication Card Pane (Right)
      + '  <div class="auth-card-pane">';

    if (!isForgot) {
      // Mode Navigation Tabs
      html += '    <div class="auth-tabs" role="tablist" aria-label="Authentication Type">'
        + '      <button type="button" role="tab" aria-selected="' + (isSignIn ? 'true' : 'false') + '" class="auth-tab ' + (isSignIn ? 'active' : '') + '" onclick="window.AYUR_AUTH.switchMode(\'signin\')">Sign In</button>'
        + '      <button type="button" role="tab" aria-selected="' + (isSignUp ? 'true' : 'false') + '" class="auth-tab ' + (isSignUp ? 'active' : '') + '" onclick="window.AYUR_AUTH.switchMode(\'signup\')">Create Account</button>'
        + '    </div>';
    }

    // Header title & subtitle
    html += '    <div class="auth-form-head">';
    if (isSignIn) {
      html += '      <h2 class="auth-form-title">Welcome back</h2>'
        + '      <p class="auth-form-subtitle">Sign in to your research workspace.</p>';
    } else if (isSignUp) {
      html += '      <h2 class="auth-form-title">Create your account</h2>'
        + '      <p class="auth-form-subtitle">Join the evidence-backed Ayurvedic product intelligence network.</p>';
    } else {
      html += '      <h2 class="auth-form-title">Reset your password</h2>'
        + '      <p class="auth-form-subtitle">Enter your registered email address to request account recovery.</p>';
    }
    html += '    </div>'

      // Alert container
      + '    <div class="auth-alert" id="auth-alert" role="alert" style="display:none;"></div>';

    if (isForgot) {
      // Forgot Password UI (Ready for subsequent email verification backend implementation)
      html += '    <div class="auth-notice-box">'
        + '      <span class="material-symbols-outlined auth-notice-icon" aria-hidden="true">info</span>'
        + '      <div class="auth-notice-content">'
        + '        <strong>Password Self-Service Notice</strong>'
        + '        <p>Automated password reset email delivery requires the pending SMTP/email verification backend service. Please contact your organization administrator or return to Sign In.</p>'
        + '      </div>'
        + '    </div>'
        + '    <form class="auth-form" id="auth-form" onsubmit="window.AYUR_AUTH.handleForgotSubmit(event)" novalidate>'
        + '      <div class="auth-field">'
        + '        <label for="auth-email">Email address</label>'
        + '        <div class="auth-input-wrap">'
        + '          <span class="material-symbols-outlined auth-input-icon" aria-hidden="true">mail</span>'
        + '          <input type="email" id="auth-email" placeholder="name@institution.org" value="' + (emailVal || '') + '" required autocomplete="email" spellcheck="false">'
        + '        </div>'
        + '      </div>'
        + '      <button type="submit" class="auth-submit-btn" id="auth-submit-btn">'
        + '        <span class="auth-submit-text">Request Reset Link</span>'
        + '      </button>'
        + '      <button type="button" class="auth-back-btn" onclick="window.AYUR_AUTH.switchMode(\'signin\', document.getElementById(\'auth-email\')?.value)">'
        + '        <span class="material-symbols-outlined" aria-hidden="true">arrow_back</span> Return to Sign In'
        + '      </button>'
        + '    </form>';
    } else {
      // Sign In / Sign Up Form
      html += '    <form class="auth-form" id="auth-form" onsubmit="window.AYUR_AUTH.handleSubmit(event)" novalidate>';

      if (isSignUp) {
        html += '      <div class="auth-field">'
          + '        <label for="auth-fullname">Full Name</label>'
          + '        <div class="auth-input-wrap">'
          + '          <span class="material-symbols-outlined auth-input-icon" aria-hidden="true">person</span>'
          + '          <input type="text" id="auth-fullname" placeholder="Dr. Deepansh Aggarwal" required autocomplete="name">'
          + '        </div>'
          + '      </div>';
      }

      html += '      <div class="auth-field">'
        + '        <label for="auth-email">Institutional Email</label>'
        + '        <div class="auth-input-wrap">'
        + '          <span class="material-symbols-outlined auth-input-icon" aria-hidden="true">mail</span>'
        + '          <input type="email" id="auth-email" placeholder="name@institution.org" value="' + (emailVal || '') + '" required autocomplete="email" spellcheck="false">'
        + '        </div>'
        + '      </div>'

        + '      <div class="auth-field">'
        + '        <label for="auth-password">Password</label>'
        + '        <div class="auth-input-wrap">'
        + '          <span class="material-symbols-outlined auth-input-icon" aria-hidden="true">lock</span>'
        + '          <input type="password" id="auth-password" placeholder="••••••••" required minlength="8" autocomplete="' + (isSignIn ? 'current-password' : 'new-password') + '">'
        + '          <button type="button" class="auth-pw-toggle" id="auth-pw-toggle-main" aria-label="Show password" aria-pressed="false" onclick="window.AYUR_AUTH.togglePassword(\'auth-password\', this)">'
        + '            <span class="material-symbols-outlined" aria-hidden="true">visibility</span>'
        + '          </button>'
        + '        </div>'
        + (isSignUp ? '        <small class="auth-hint">At least 8 characters</small>' : '')
        + '      </div>';

      if (isSignUp) {
        html += '      <div class="auth-field">'
          + '        <label for="auth-confirm-password">Confirm Password</label>'
          + '        <div class="auth-input-wrap">'
          + '          <span class="material-symbols-outlined auth-input-icon" aria-hidden="true">lock_reset</span>'
          + '          <input type="password" id="auth-confirm-password" placeholder="••••••••" required minlength="8" autocomplete="new-password">'
          + '          <button type="button" class="auth-pw-toggle" id="auth-pw-toggle-confirm" aria-label="Show password" aria-pressed="false" onclick="window.AYUR_AUTH.togglePassword(\'auth-confirm-password\', this)">'
          + '            <span class="material-symbols-outlined" aria-hidden="true">visibility</span>'
          + '          </button>'
        + '        </div>'
        + '      </div>';
      } else {
        // Aux Row for Sign In: Remember Me & Forgot Password
        html += '      <div class="auth-aux-row">'
          + '        <label class="auth-remember-wrap" for="auth-remember-me">'
          + '          <input type="checkbox" id="auth-remember-me" ' + (rememberChecked ? 'checked' : '') + '>'
          + '          <span class="auth-checkbox-custom" aria-hidden="true"></span>'
          + '          <span class="auth-remember-label">Remember me</span>'
          + '        </label>'
          + '        <button type="button" class="auth-forgot-link" onclick="window.AYUR_AUTH.switchMode(\'forgot\', document.getElementById(\'auth-email\')?.value)">Forgot password?</button>'
          + '      </div>';
      }

      html += '      <button type="submit" class="auth-submit-btn" id="auth-submit-btn">'
        + '        <span class="auth-submit-text">' + (isSignIn ? 'Sign In' : 'Create Account') + '</span>'
        + '      </button>'
        + '    </form>'

        // Mode Toggle Footer
        + '    <div class="auth-toggle-footer">'
        + (isSignIn
          ? 'Don\'t have an account? <a href="#" onclick="event.preventDefault(); window.AYUR_AUTH.switchMode(\'signup\', document.getElementById(\'auth-email\')?.value)">Create an account</a>'
          : 'Already have an account? <a href="#" onclick="event.preventDefault(); window.AYUR_AUTH.switchMode(\'signin\', document.getElementById(\'auth-email\')?.value)">Sign in</a>'
        )
        + '    </div>';
    }

    html += '  </div>' // End auth-card-pane
      + '</div>'; // End auth-shell

    overlay.innerHTML = html;
  }

  function hideAuthOverlay() {
    var overlay = document.getElementById('auth-overlay');
    if (overlay) {
      overlay.style.display = 'none';
    }
  }

  // ---------------------------------------------------------------------------
  // Forgot Password Interaction Handler
  // ---------------------------------------------------------------------------
  function handleForgotSubmit(event) {
    if (event) event.preventDefault();
    var email = (document.getElementById('auth-email')?.value || '').trim();

    if (!email) {
      setAlert('Please enter your email address.', 'error');
      return;
    }
    if (!isValidEmail(email)) {
      setAlert('Please enter a valid email format.', 'error');
      return;
    }

    // Do NOT invent endpoints, simulate fake email delivery, or display false success message
    setAlert(
      'Password reset endpoint is not configured in this deployment environment. Direct self-service email recovery will be activated upon SMTP service integration. Please contact admin@ayur-intel.local or return to Sign In.',
      'info'
    );
  }

  // ---------------------------------------------------------------------------
  // Form Submission Handler (Login & Signup)
  // ---------------------------------------------------------------------------
  async function handleSubmit(event) {
    if (event) event.preventDefault();
    if (isSubmitting) return;

    setAlert('');

    var email = (document.getElementById('auth-email')?.value || '').trim();
    var password = (document.getElementById('auth-password')?.value || '').trim();
    var submitBtn = document.getElementById('auth-submit-btn');

    if (!email || !password) {
      setAlert('Please fill in all required fields.', 'error');
      showToastMsg('⚠️ Please fill in all required fields', 'error');
      return;
    }

    if (!isValidEmail(email)) {
      setAlert('Please enter a valid institutional email address.', 'error');
      showToastMsg('⚠️ Please enter a valid email address format', 'error');
      return;
    }

    if (password.length < 8) {
      setAlert('Password must be at least 8 characters long.', 'error');
      showToastMsg('⚠️ Password must be at least 8 characters long', 'error');
      return;
    }

    var fullName = '';
    if (CURRENT_MODE === 'signup') {
      fullName = (document.getElementById('auth-fullname')?.value || '').trim();
      var confirmPassword = (document.getElementById('auth-confirm-password')?.value || '').trim();

      if (!fullName) {
        setAlert('Please enter your full name.', 'error');
        showToastMsg('⚠️ Please enter your full name', 'error');
        return;
      }

      if (password !== confirmPassword) {
        setAlert('Passwords do not match. Please verify.', 'error');
        showToastMsg('⚠️ Passwords do not match', 'error');
        return;
      }
    }

    var rememberMe = false;
    var rememberMeCheckbox = document.getElementById('auth-remember-me');
    if (rememberMeCheckbox) {
      rememberMe = rememberMeCheckbox.checked;
    }

    isSubmitting = true;
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="auth-btn-spinner" aria-hidden="true"></span> '
        + (CURRENT_MODE === 'signup' ? 'Creating Account...' : 'Authenticating...');
    }

    try {
      var endpoint = CURRENT_MODE === 'signup' ? '/api/auth/signup' : '/api/auth/login';
      var settingsState = {};
      try {
        var s = localStorage.getItem('ayur_intel_settings');
        if (s) settingsState = JSON.parse(s);
      } catch (_) {}

      var sessTimeout = settingsState.sessionTimeout || '30m';
      var maxLifetime = settingsState.maxSessionLifetime || '12h';
      var devId = getDeviceId();

      var payload = CURRENT_MODE === 'signup'
        ? { full_name: fullName, email: email, password: password }
        : { email: email, password: password, session_timeout: sessTimeout, max_lifetime: maxLifetime, device_id: devId };

      var response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      var data = await response.json();

      if (response.ok && data.user) {
        if (CURRENT_MODE === 'signup') {
          // POST-SIGNUP REDIRECT TO LOGIN: Do NOT store token, redirect to Login form
          showToastMsg('⏳ Registration submitted! Pending administrator approval.', 'info');
          renderAuthCard('signin', email);
          setAlert('<strong>Registration Submitted</strong><br>Your account has been registered and is pending administrator review. You will be able to sign in once access is approved.', 'info');
        } else {
          // LOGIN SUCCESS: Apply Remember Me strategy, save token, update UI, hide overlay
          sessionStartTimestamp = Date.now();
          lastUserActivityTimestamp = Date.now();

          if (rememberMe) {
            try {
              localStorage.setItem('ayur_remember_me', 'true');
              localStorage.setItem('ayur_remembered_email', email);
            } catch (e) {}
            setToken(data.token, true);
            setUser(data.user, true);
          } else {
            try {
              localStorage.removeItem('ayur_remember_me');
              localStorage.removeItem('ayur_remembered_email');
            } catch (e) {}
            setToken(data.token, false);
            setUser(data.user, false);
          }

          hideAuthOverlay();
          updateUIWithUser(data.user);
          startSessionInactivityMonitor();
          showToastMsg('✅ Welcome back, ' + (data.user.display_name || data.user.username) + '!', 'success');

          if (window.AYUR && typeof window.AYUR.init === 'function') {
            window.AYUR.init();
          }
        }
      } else {
        var errorDetail = data.detail || (CURRENT_MODE === 'signup' ? 'Registration failed. Please check your information.' : 'Invalid email or password.');
        if (response.status === 403) {
          if (errorDetail.indexOf('Approval pending by Admin') !== -1) {
            var isNewUserPending = errorDetail.indexOf('pending administrator approval') !== -1;
            var alertSubtext = isNewUserPending
              ? 'Your account is pending administrator approval. You will be able to sign in once access is approved.'
              : 'Your account is currently deactivated. Your access request has been submitted for administrator review. You will be able to sign in once access is approved.';
            setAlert(
              '<strong>Approval Pending by Admin</strong><br>' + alertSubtext,
              'warning'
            );
            showToastMsg('⏳ Approval pending by Admin for this account', 'warning');
          } else if (errorDetail.indexOf('Access not approved') !== -1) {
            setAlert(
              '<strong>Access Not Approved</strong><br>' + escapeHtml(errorDetail),
              'error'
            );
            showToastMsg('❌ Access not approved by administrator', 'error');
          } else {
            setAlert(errorDetail, 'error');
            showToastMsg('❌ ' + errorDetail, 'error');
          }
        } else {
          setAlert(errorDetail, 'error');
          showToastMsg('❌ ' + errorDetail, 'error');
        }
      }

    } catch (err) {
      console.error('Auth request exception:', err);
      setAlert('Network error occurred. Please check your connection and try again.', 'error');
      showToastMsg('❌ Network error. Please try again.', 'error');
    } finally {
      isSubmitting = false;
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span class="auth-submit-text">' + (CURRENT_MODE === 'signup' ? 'Create Account' : 'Sign In') + '</span>';
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
      if (avatarUrl && avatarUrl.startsWith('data:image/')) {
        avatarElem.textContent = '';
        var img = document.createElement('img');
        img.src = avatarUrl;
        img.alt = 'Avatar';
        img.style.cssText = 'width:100%;height:100%;aspect-ratio:1/1;object-fit:cover;border-radius:50%;display:block;';
        avatarElem.appendChild(img);
        avatarElem.style.background = 'transparent';
      } else {
        avatarElem.textContent = initials;
        avatarElem.style.backgroundColor = bgColor;
      }
    }
    if (nameElem) nameElem.textContent = name;
    if (roleElem) roleElem.textContent = (user && user.role === 'admin') ? 'Admin' : 'Researcher';

    // Private Admin Console entry — revealed only when server-verified role is 'admin'
    var adminNav = document.getElementById('nav-item-admin');
    if (adminNav) {
      if (user && user.role === 'admin') {
        adminNav.style.display = 'flex';
      } else {
        adminNav.style.display = 'none';
      }
    }

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
      if (avatarUrl && avatarUrl.startsWith('data:image/')) {
        topbarAvatar.textContent = '';
        var img2 = document.createElement('img');
        img2.src = avatarUrl;
        img2.alt = 'Avatar';
        img2.style.cssText = 'width:100%;height:100%;aspect-ratio:1/1;object-fit:cover;border-radius:50%;display:block;';
        topbarAvatar.appendChild(img2);
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

  async function logout() {
    var token = getToken();
    if (token) {
      try {
        await fetch('/api/auth/logout', {
          method: 'POST',
          headers: {
            'Authorization': 'Bearer ' + token,
            'Content-Type': 'application/json'
          }
        });
      } catch (e) {
        console.warn('Backend logout notification note:', e);
      }
    }
    setToken('');
    setUser(null);
    var adminNav = document.getElementById('nav-item-admin');
    if (adminNav) adminNav.style.display = 'none';
    if (window.AYUR && window.AYUR.state && window.AYUR.state.view === 'admin-console') {
      window.AYUR.state.view = 'dashboard';
    }
    if (window.AYUR_ADMIN && typeof window.AYUR_ADMIN.clearData === 'function') {
      window.AYUR_ADMIN.clearData();
    }
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
  // Inactivity & Session Lifetime Tracking
  // ---------------------------------------------------------------------------
  var lastUserActivityTimestamp = Date.now();
  var sessionStartTimestamp = Date.now();
  var _sessionCheckInterval = null;
  var _isHandlingExpiry = false;

  function recordUserActivity() {
    lastUserActivityTimestamp = Date.now();
  }

  ['pointerdown', 'keydown', 'scroll', 'touchstart'].forEach(function (evt) {
    window.addEventListener(evt, recordUserActivity, { passive: true });
  });

  function parseDurationToMs(durStr, defaultSec) {
    if (!durStr) return (defaultSec || 1800) * 1000;
    var str = String(durStr).trim().toLowerCase();
    if (str.endsWith('m')) return parseInt(str, 10) * 60 * 1000;
    if (str.endsWith('h')) return parseInt(str, 10) * 3600 * 1000;
    var num = parseInt(str, 10);
    return isNaN(num) ? (defaultSec || 1800) * 1000 : num * 1000;
  }

  function handleSessionExpired(reason) {
    if (_isHandlingExpiry) return;
    _isHandlingExpiry = true;

    var tok = getToken();
    setToken('');
    setUser(null);

    var adminNav = document.getElementById('nav-item-admin');
    if (adminNav) adminNav.style.display = 'none';

    if (window.AYUR && window.AYUR.state && window.AYUR.state.view === 'admin-console') {
      window.AYUR.state.view = 'dashboard';
    }
    if (window.AYUR_ADMIN && typeof window.AYUR_ADMIN.clearData === 'function') {
      window.AYUR_ADMIN.clearData();
    }

    if (tok) {
      fetch('/api/auth/logout', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer ' + tok,
          'Content-Type': 'application/json'
        }
      }).catch(function () {});
    }

    showToastMsg('⚠️ ' + (reason || 'Session expired. Please sign in again.'), 'info');
    renderAuthCard('signin');
    setAlert(reason || 'Session expired. Please sign in again.', 'info');

    setTimeout(function () {
      _isHandlingExpiry = false;
    }, 1500);
  }

  function startSessionInactivityMonitor() {
    if (_sessionCheckInterval) clearInterval(_sessionCheckInterval);
    _sessionCheckInterval = setInterval(function () {
      var token = getToken();
      if (!token) return;

      var s = {};
      try {
        var saved = localStorage.getItem('ayur_intel_settings');
        if (saved) s = JSON.parse(saved);
      } catch (_) {}

      var idleTimeoutMs = parseDurationToMs(s.sessionTimeout || '30m', 1800);
      var maxLifetimeMs = parseDurationToMs(s.maxSessionLifetime || '12h', 43200);

      var now = Date.now();

      // Check Inactivity Expiry
      if (now - lastUserActivityTimestamp >= idleTimeoutMs) {
        handleSessionExpired('Session expired due to inactivity. Please sign in again.');
        return;
      }

      // Check Maximum Session Lifetime Expiry
      if (now - sessionStartTimestamp >= maxLifetimeMs) {
        handleSessionExpired('Maximum session lifetime reached. Please sign in again.');
        return;
      }
    }, 10000);
  }

  // ---------------------------------------------------------------------------
  // Auto Authentication Check on Page Load
  // ---------------------------------------------------------------------------
  async function checkAuthOnLoad() {
    var token = getToken();
    if (!token) {
      var adminNav = document.getElementById('nav-item-admin');
      if (adminNav) adminNav.style.display = 'none';
      renderAuthCard('signin');
      return;
    }

    try {
      var res = await fetch('/api/auth/me', {
        headers: {
          'Authorization': 'Bearer ' + token,
          'X-Background-Request': 'true'
        }
      });
      var data = await res.json();
      if (res.ok && data.user) {
        if (data.session && data.session.created_at) {
          sessionStartTimestamp = new Date(data.session.created_at).getTime();
        }
        lastUserActivityTimestamp = Date.now();
        setUser(data.user);
        updateUIWithUser(data.user);
        hideAuthOverlay();
        startSessionInactivityMonitor();
      } else {
        handleSessionExpired(data.detail || 'Session expired. Please sign in again.');
      }
    } catch (e) {
      console.error('Auth check error:', e);
      var cached = getUser();
      if (cached) {
        updateUIWithUser(cached);
        hideAuthOverlay();
        startSessionInactivityMonitor();
      } else {
        var adminNav3 = document.getElementById('nav-item-admin');
        if (adminNav3) adminNav3.style.display = 'none';
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
    handleForgotSubmit: handleForgotSubmit,
    togglePassword: togglePassword,
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
    updateUIWithUser: updateUIWithUser,
    recordUserActivity: recordUserActivity,
    handleSessionExpired: handleSessionExpired,
    startSessionInactivityMonitor: startSessionInactivityMonitor
  };

  document.addEventListener('DOMContentLoaded', function () {
    checkAuthOnLoad();
  });

})();
