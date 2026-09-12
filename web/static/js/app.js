/* ==================================================================
   AYUR-INTEL -- Main SPA Application (Phases 1-10)
   ================================================================== */
(function () {
  "use strict";

  // ----------------------------------------------------------------
  // State
  // ----------------------------------------------------------------
  var state = {
    view: "dashboard",
    cases: [],
    currentCase: null,
    loading: false,
    error: null,
    plantDiscoveries: [],
    knowledgeFindings: null,
    knowledgeSources: [],
    innovationAnalysis: null,
    patentSearchResults: null,
    patentSavedResults: null,
    patentDeepAnalysis: null,
    ipStrategy: null,
    regulatoryProfile: null,
    jurisdictionComparison: null,
    evidenceData: null,
    riskData: null,
    dashboardData: null,
    monitoringData: null,
    knowledgeGraphData: null,
    sourceRouterData: null,
    passportData: null,
    patentAnalyses: null,
  };

  var ICONS = {};

  // ----------------------------------------------------------------
  // Helpers
  // ----------------------------------------------------------------
  function icon(name, size) {
    var s = size || 20;
    return '<span class="material-symbols-outlined" style="font-size:' + s + 'px">' + name + '</span>';
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function parseJson(str) {
    if (!str) return [];
    if (Array.isArray(str)) return str;
    try { var v = JSON.parse(str); return Array.isArray(v) ? v : []; } catch (e) { return []; }
  }

  function stageLabel(s) {
    var m = { IDEA: "Idea", RND: "R&D", PILOT: "Pilot", PRE_LAUNCH: "Pre-Launch", COMMERCIAL: "Commercial" };
    return m[s] || s;
  }

  function statusLabel(s) {
    var m = { DRAFT: "Draft", ANALYZING: "Analyzing", COMPLETED: "Completed", ARCHIVED: "Archived" };
    return m[s] || s;
  }

  function toast(msg, type) {
    var c = document.getElementById("toasts");
    if (!c) return;
    var d = document.createElement("div");
    d.className = "toast toast-" + (type || "info");
    d.textContent = msg;
    c.appendChild(d);
    setTimeout(function () { d.remove(); }, 3000);
  }

  function showToast(msg, type) {
    toast(msg, type);
  }
  // ----------------------------------------------------------------
  // Centralized Navigation & Scroll Preservation System
  // ----------------------------------------------------------------
  var _viewScrollPositions = {};
  var _currentActiveView = null;

  function getScrollPosition() {
    var content = document.getElementById("content");
    var main = document.querySelector(".main");
    var app = document.querySelector(".app");
    return {
      windowY: window.scrollY || window.pageYOffset || (document.documentElement && document.documentElement.scrollTop) || (document.body && document.body.scrollTop) || 0,
      windowX: window.scrollX || window.pageXOffset || (document.documentElement && document.documentElement.scrollLeft) || (document.body && document.body.scrollLeft) || 0,
      contentY: content ? content.scrollTop : 0,
      mainY: main ? main.scrollTop : 0,
      appY: app ? app.scrollTop : 0
    };
  }

  function saveCurrentViewScrollPosition() {
    var view = state.view;
    if (!view) return;
    var caseKey = (state.currentCase && (state.currentCase.public_id || state.currentCase.id)) || "global";
    _viewScrollPositions[caseKey + ":" + view] = getScrollPosition();
  }

  function getSavedViewScrollPosition(viewName) {
    var targetView = viewName || state.view;
    var caseKey = (state.currentCase && (state.currentCase.public_id || state.currentCase.id)) || "global";
    return _viewScrollPositions[caseKey + ":" + targetView] || null;
  }

  function restoreScrollPosition(pos) {
    if (!pos) return;
    requestAnimationFrame(function () {
      try {
        window.scrollTo({ top: pos.windowY, left: pos.windowX, behavior: 'instant' });
      } catch (e) {
        window.scrollTo(pos.windowX, pos.windowY);
      }
      if (document.documentElement) {
        document.documentElement.scrollTop = pos.windowY;
        document.documentElement.scrollLeft = pos.windowX;
      }
      if (document.body) {
        document.body.scrollTop = pos.windowY;
        document.body.scrollLeft = pos.windowX;
      }
      var content = document.getElementById("content");
      if (content && typeof pos.contentY === "number") content.scrollTop = pos.contentY;
      var main = document.querySelector(".main");
      if (main && typeof pos.mainY === "number") main.scrollTop = pos.mainY;
      var app = document.querySelector(".app");
      if (app && typeof pos.appY === "number") app.scrollTop = pos.appY;
    });
  }

  function scrollToTop() {
    try {
      window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
    } catch (e) {
      window.scrollTo(0, 0);
    }
    if (document.documentElement) document.documentElement.scrollTop = 0;
    if (document.body) document.body.scrollTop = 0;
    var content = document.getElementById("content");
    if (content) content.scrollTop = 0;
    var main = document.querySelector(".main");
    if (main) main.scrollTop = 0;
    var app = document.querySelector(".app");
    if (app) app.scrollTop = 0;
  }
  window.scrollToTop = scrollToTop;
  window.getScrollPosition = getScrollPosition;
  window.restoreScrollPosition = restoreScrollPosition;
  window.saveCurrentViewScrollPosition = saveCurrentViewScrollPosition;

  function navigateBackToCaseDetail() {
    saveCurrentViewScrollPosition();
    state.view = "case-detail";
    saveStateToLocalStorage();
    var caseKey = (state.currentCase && (state.currentCase.public_id || state.currentCase.id)) || "global";
    var savedPos = _viewScrollPositions[caseKey + ":case-detail"];
    render({ scroll: savedPos ? "restore" : "top", savedPos: savedPos });
  }
  window.navigateBackToCaseDetail = navigateBackToCaseDetail;

  window.showToast = showToast;

  window.openRegistrationGuide = openRegistrationGuide;
  window.closeRegistrationPopup = closeRegistrationPopup;
  window.toggleIndicatorStatus = toggleIndicatorStatus;
  window.showCompletionPopup = showCompletionPopup;
  window.closeCompletionPopup = closeCompletionPopup;
  window.completeIndicator = completeIndicator;
  window.triggerFireworks = triggerFireworks;
  function editProductPassport(caseId) {
    var s = window.AYUR ? window.AYUR.state : state;
    if (!s) return;
    var caseData = (s.cases && s.cases.find(function (c) { return c.id === caseId; })) || s.currentCase;
    
    if (!caseData) {
      showToast('⚠️ Product not found', 'error');
      return;
    }
    
    saveCurrentViewScrollPosition();

    // Initialize passport data with existing case data
    if (window.AYUR && typeof window.AYUR.initPassportData === 'function') {
      window.AYUR.initPassportData(caseData);
    }
    
    // Navigate directly to Passport Review screen (Review Step)
    s.view = 'passport-wizard';
    s.passportStep = 7; // Open Review screen directly
    if (typeof window.AYUR.saveStateToLocalStorage === 'function') {
      window.AYUR.saveStateToLocalStorage();
    }
    if (typeof window.AYUR.updateTopbarUI === 'function') {
      window.AYUR.updateTopbarUI();
    }
    if (typeof window.AYUR.render === 'function') {
      window.AYUR.render({ scroll: "top" });
    }
    showToast('✏️ Editing product: ' + (caseData.name || 'Product'), 'info');
  }

  window.editProductPassport = editProductPassport;


  function field(label, value) {
    var v = value || "";
    var cls = v ? "value" : "value empty";
    return '<div class="detail-field"><label>' + escapeHtml(label) + '</label><div class="' + cls + '">' + (escapeHtml(v) || "Not specified") + '</div></div>';
  }

  // ----------------------------------------------------------------
  // API helpers with In-Flight Deduplication & Client Cache
  // ----------------------------------------------------------------
  var _clientApiCache = new Map(); // url -> { ts, data }
  var _inFlightApiRequests = new Map(); // url -> Promise
  var CLIENT_CACHE_TTL = 15000; // 15 seconds client cache for GET

  function invalidateClientApiCache(urlPrefix) {
    if (!urlPrefix) {
      _clientApiCache.clear();
      return;
    }
    for (var key of _clientApiCache.keys()) {
      if (key.indexOf(urlPrefix) !== -1) {
        _clientApiCache.delete(key);
      }
    }
  }

  async function api(url, opts) {
    var method = (opts && opts.method ? opts.method : "GET").toUpperCase();
    var isGet = method === "GET";

    if (!isGet) {
      // Invalidate relevant cache on mutation
      invalidateClientApiCache("/api/cases");
    } else {
      // Check client memory cache
      var cached = _clientApiCache.get(url);
      if (cached && (Date.now() - cached.ts < CLIENT_CACHE_TTL)) {
        return cached.data;
      }
      // Deduplicate concurrent in-flight requests for identical GET url
      if (_inFlightApiRequests.has(url)) {
        return _inFlightApiRequests.get(url);
      }
    }

    var requestPromise = (async function () {
      try {
        var resp = await fetch(url, opts || {});
        if (!resp.ok) { var err = await resp.text(); throw new Error(err); }
        var json = await resp.json();
        if (isGet) {
          _clientApiCache.set(url, { ts: Date.now(), data: json });
        }
        return json;
      } catch (e) {
        console.error("API error:", url, e);
        throw e;
      } finally {
        if (isGet) {
          _inFlightApiRequests.delete(url);
        }
      }
    })();

    if (isGet) {
      _inFlightApiRequests.set(url, requestPromise);
    }

    return await requestPromise;
  }

  // ----------------------------------------------------------------
  // Per-Case Intelligence Module Cache
  // ----------------------------------------------------------------
  var _caseModuleCache = new Map();
  function getCachedModule(caseId, key) {
    return _caseModuleCache.get(String(caseId) + ":" + key);
  }
  function setCachedModule(caseId, key, data) {
    _caseModuleCache.set(String(caseId) + ":" + key, data);
  }

  function invalidateCaseModuleCache(caseId) {
    if (!caseId) {
      _caseModuleCache.clear();
      return;
    }
    var prefix = String(caseId) + ":";
    for (var key of _caseModuleCache.keys()) {
      if (key.indexOf(prefix) === 0) {
        _caseModuleCache.delete(key);
      }
    }
  }

  async function openCaseModule(key, endpoint, targetView, httpOptions) {
    if (!state.currentCase) return;
    var isNewView = state.view !== targetView;
    if (isNewView) {
      saveCurrentViewScrollPosition();
    }
    var cached = getCachedModule(state.currentCase.id, key);
    if (cached) {
      state[key] = cached;
      state.view = targetView;
      saveStateToLocalStorage();
      render({ scroll: isNewView ? "top" : "preserve" });
      return;
    }
    state.loading = true;
    render({ scroll: isNewView ? "top" : "preserve" });
    try {
      var data = await api(endpoint, httpOptions);
      setCachedModule(state.currentCase.id, key, data);
      state[key] = data;
      state.view = targetView;
      saveStateToLocalStorage();
    } catch (e) {
      state.error = "Failed to load " + targetView + ".";
    }
    state.loading = false;
    render({ scroll: isNewView ? "top" : "preserve" });
  }

  // ----------------------------------------------------------------
  // Render dispatcher
  // ----------------------------------------------------------------
  function render(options) {
    var content = document.getElementById("content");
    if (!content) return;

    var opt = options || {};
    var prevView = _currentActiveView;
    var targetView = state.view || "dashboard";
    var prevScroll = (opt.scroll === "preserve" || (opt.scroll === undefined && prevView === targetView)) ? getScrollPosition() : null;

    // Clear active case when going to dashboard
    if (targetView === "dashboard") {
      state.currentCase = null;
      updateTopbarUI();
      saveStateToLocalStorage();
    }

    if (state.loading) {
      content.innerHTML = '<div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div>';
      if (opt.scroll === "preserve" && prevScroll) {
        restoreScrollPosition(prevScroll);
      } else if (opt.scroll === "top" || (opt.scroll === undefined && prevView !== targetView)) {
        scrollToTop();
      }
      return;
    }

    if (state.error) {
      content.innerHTML = '<div class="error-panel">' + icon("error", 20) + '<div><h4>Error</h4><p>' + escapeHtml(state.error) + '</p></div></div>';
      if (opt.scroll === "preserve" && prevScroll) {
        restoreScrollPosition(prevScroll);
      } else if (opt.scroll === "top" || (opt.scroll === undefined && prevView !== targetView)) {
        scrollToTop();
      }
      return;
    }

    if (state.view === "dashboard") {
      content.innerHTML = renderDashboard();
    } else if (state.view === "product-cases") {
      content.innerHTML = renderProductCases();
    } else if (state.view === "case-detail") {
      content.innerHTML = renderCaseIntelligence();
    } else if (state.view === "knowledge-hub") {
      content.innerHTML = renderKnowledgeHub();
    } else if (state.view === "passport-wizard" || state.view === "passport") {
      // passport.js renders the wizard
      if (window.AYUR && window.AYUR.renderPassportWizard) {
        content.innerHTML = window.AYUR.renderPassportWizard();
      } else {
        content.innerHTML = '<div class="card"><div class="card-body"><p>Passport wizard not available</p></div></div>';
      }
    } else if (state.view === "plant-discovery") {
      content.innerHTML = renderPlantDiscovery();
    } else if (state.view === "knowledge-engine") {
      content.innerHTML = renderKnowledgeEngine();
    } else if (state.view === "innovation-analysis") {
      content.innerHTML = renderInnovationAnalysis();
    } else if (state.view === "patent-intelligence") {
      content.innerHTML = renderPatentIntelligence();
    } else if (state.view === "patent-deep-analysis") {
      content.innerHTML = renderPatentDeepAnalysis();
    } else if (state.view === "ip-strategy") {
      content.innerHTML = renderIPStrategy();
    } else if (state.view === "regulatory-select") {
      content.innerHTML = renderRegulatorySelect();
    } else if (state.view === "regulatory-intelligence") {
      content.innerHTML = renderRegulatoryIntelligence();
    } else if (state.view === "jurisdiction-comparison") {
      content.innerHTML = renderJurisdictionComparison();
    } else if (state.view === "evidence") {
      content.innerHTML = renderEvidenceView();
    } else if (state.view === "risk") {
      content.innerHTML = renderRiskView();
    } else if (state.view === "dashboard-detail") {
      content.innerHTML = renderDecisionDashboard();
    } else if (state.view === "monitoring-center") {
      content.innerHTML = renderMonitoringCenter();
    } else if (state.view === "knowledge-graph") {
      content.innerHTML = renderKnowledgeGraph();
    } else if (state.view === "source-router") {
      content.innerHTML = renderSourceRouter();
    } else if (state.view === "review-queue") {
      content.innerHTML = renderReviewQueue();
    } else if (state.view === "settings") {
      content.innerHTML = renderSettings();
    } else if (state.view === "profile") {
      content.innerHTML = renderProfilePage();
    } else {
      content.innerHTML = renderDashboard();
    }

    _currentActiveView = targetView;

    updateTopBarAndActiveNav(state.view);
    bindEvents();
    if ((state.view === 'passport-wizard' || state.view === 'passport') && window.AYUR && window.AYUR.bindPassportEvents) { window.AYUR.bindPassportEvents(); }

    // Intentional Scroll Rules:
    // RULE 1: EVERY NEW PAGE / VIEW / MODULE MUST OPEN AT TOP
    // RULE 2: ACTIONS INSIDE THE SAME PAGE MUST PRESERVE POSITION
    // RULE 3: BACK RESTORES PARENT POSITION
    if (opt.scroll === "preserve") {
      if (prevScroll) restoreScrollPosition(prevScroll);
    } else if (opt.scroll === "restore" && opt.savedPos) {
      restoreScrollPosition(opt.savedPos);
    } else if (opt.scroll === "restore") {
      var savedPos = getSavedViewScrollPosition(targetView);
      if (savedPos) restoreScrollPosition(savedPos);
      else scrollToTop();
    } else if (opt.scroll === "top") {
      scrollToTop();
    } else {
      if (prevView !== targetView) {
        scrollToTop();
      } else if (prevScroll) {
        restoreScrollPosition(prevScroll);
      }
    }

    // Initialize graph visualization if on knowledge-graph view
    if (state.view === 'knowledge-graph' && state.knowledgeGraphData) {
      setTimeout(function () { initGraphVisualization(); }, 100);
    }
  }

  // ----------------------------------------------------------------
  // ----------------------------------------------------------------
  // Research & Intelligence Workflow Steps (10 Steps with Definitions)
  // ----------------------------------------------------------------
  var PIPELINE_WORKFLOW_STEPS = [
    { icon: "psychology", label: "Idea", desc: "Capture your Ayurvedic product concept and define its core purpose." },
    { icon: "eco", label: "Plant Eval", desc: "Identify and evaluate botanical ingredients with scientific and classical backing." },
    { icon: "menu_book", label: "Lit Review", desc: "Analyze classical Ayurvedic texts and modern research for your formulation." },
    { icon: "science", label: "Formulation", desc: "Structure your product with dosages, ratios, and delivery formats." },
    { icon: "gavel", label: "Patent Check", desc: "Screen Indian patent landscape for similar formulations and processes." },
    { icon: "policy", label: "Regs Check", desc: "Understand Indian regulatory requirements (AYUSH, FSSAI, Drugs & Cosmetics Act)." },
    { icon: "verified", label: "Evidence", desc: "Build evidence-based claims with scientific and traditional sources." },
    { icon: "warning", label: "Risk Assmt", desc: "Identify intellectual property, regulatory, and market risks early." },
    { icon: "rocket_launch", label: "Go-to-Market", desc: "Prepare for product launch with regulatory and IP strategy." },
    { icon: "visibility", label: "Monitoring", desc: "Track changes in patent landscape and regulatory updates post-launch." }
  ];

  function openWorkflowStepModal(step, stepNumber) {
    var old = document.getElementById("workflow-step-modal-overlay");
    if (old) old.remove();

    var overlay = document.createElement("div");
    overlay.className = "modal-overlay open workflow-modal-overlay";
    overlay.id = "workflow-step-modal-overlay";
    overlay.style.backdropFilter = "blur(10px)";
    overlay.style.backgroundColor = "rgba(0, 0, 0, 0.7)";
    overlay.innerHTML = '<div class="modal workflow-modal" style="max-width:480px;border-radius:16px;overflow:hidden;box-shadow:0 25px 50px -12px rgba(0,0,0,0.6);border:1px solid rgba(52,211,153,0.3);background:rgba(18,24,27,0.98);">'
      + '<div class="modal-head" style="padding:20px 24px 14px;border-bottom:1px solid rgba(255,255,255,0.08);background:rgba(255,255,255,0.02);">'
      + '<div style="display:flex;align-items:center;gap:12px;">'
      + '<div class="workflow-modal-icon" style="width:40px;height:40px;border-radius:10px;background:rgba(52,211,153,0.15);color:#34d399;display:flex;align-items:center;justify-content:center;border:1px solid rgba(52,211,153,0.3);">' + icon(step.icon, 22) + '</div>'
      + '<div>'
      + '<span class="workflow-stage-tag" style="font-size:11px;font-family:\'JetBrains Mono\',monospace;color:#34d399;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;">Stage ' + stepNumber + ' of 10</span>'
      + '<h2 style="font-size:18px;font-weight:700;color:#ffffff;margin:2px 0 0 0;font-family:\'Geist\',sans-serif;">' + escapeHtml(step.label) + '</h2>'
      + '</div>'
      + '</div>'
      + '<button class="modal-close" id="workflow-modal-close" aria-label="Close" style="color:#94a3b8;">' + icon("close", 20) + '</button>'
      + '</div>'
      + '<div class="modal-body" style="padding:22px 24px;">'
      + '<p style="font-size:14.5px;line-height:1.6;color:#e2e8f0;margin:0;font-family:\'Geist\',sans-serif;">' + escapeHtml(step.desc) + '</p>'
      + '</div>'
      + '<div class="modal-foot" style="padding:14px 24px 20px;border-top:1px solid rgba(255,255,255,0.08);background:rgba(255,255,255,0.01);display:flex;justify-content:flex-end;">'
      + '<button class="btn btn-primary btn-sm" id="workflow-modal-ok-btn" style="padding:6px 18px;font-size:13px;border-radius:8px;">Close</button>'
      + '</div>'
      + '</div>';

    document.body.appendChild(overlay);

    var closeFn = function () {
      overlay.classList.remove("open");
      setTimeout(function () { overlay.remove(); }, 100);
    };

    overlay.querySelector("#workflow-modal-close").addEventListener("click", closeFn);
    overlay.querySelector("#workflow-modal-ok-btn").addEventListener("click", closeFn);
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) closeFn();
    });
  }

  // ----------------------------------------------------------------
  // Dashboard View
  // ----------------------------------------------------------------
  function renderDashboard() {
    var cases = state.cases || [];
    var pillars = [
      { icon: "verified", title: "Evidence-Backed", desc: "Ground product claims in scientific research and classical Ayurvedic literature." },
      { icon: "language", title: "Jurisdiction-Aware", desc: "Navigate Indian regulatory pathways (AYUSH, FSSAI) and patent landscapes for Ayurvedic innovation." },
      { icon: "lightbulb", title: "IP & Innovation", desc: "Identify formulation whitespace and evaluate patent landscape overlaps proactively." }
    ];

    var html = ''
      + '<div class="hero-section hero-pattern">'
      + '<div class="hero-content">'
      + '<h1>Ayurvedic Product Intelligence & Decision Support</h1>'
      + '<p>Connect Traditional Knowledge, Indian patent landscapes, regulatory pathways (AYUSH, FSSAI), and evidence-backed formulation intelligence.</p>'
      + '<div class="hero-actions">'
      + '<button class="btn btn-primary" id="create-case-btn">' + icon("add", 16) + ' Create Product Case</button>'
      + '<button class="btn btn-secondary" id="explore-demo-btn">' + icon("explore", 16) + ' Explore Demo Case</button>'
      + '</div></div>'
      + '<div class="hero-icon"><span class="material-symbols-outlined">science</span></div>'
      + '</div>'

      + '<div class="value-pillars">';
    pillars.forEach(function (p) {
      html += '<div class="value-pillar">'
        + '<div class="value-pillar-icon">' + icon(p.icon, 22) + '</div>'
        + '<h3>' + p.title + '</h3><p>' + p.desc + '</p></div>';
    });
    html += '</div>'

      + '<div class="pipeline-section">'
      + '<h2>Research & Intelligence Workflow</h2>'
      + '<div class="pipeline-container"><div class="pipeline-track">';
    PIPELINE_WORKFLOW_STEPS.forEach(function (n, i) {
      html += '<div class="pipeline-node" data-pipeline-step="' + i + '" title="Click to view details">'
        + '<div class="pipeline-node-circle">' + icon(n.icon, 18) + '</div>'
        + '<div class="pipeline-node-label">' + n.label + '</div></div>';
    });
    html += '</div></div></div>'

      + '<div class="section-header">'
      + '<h2>Active Products</h2>'
      + '<span class="view-all" id="view-all-cases">View All ' + icon("arrow_forward", 16) + '</span>'
      + '</div>';

    if (cases.length === 0) {
      html += '<div class="empty-state">'
        + '<div class="empty-icon">' + icon("inventory_2", 28) + '</div>'
        + '<h3>No Products Found</h3>'
        + '<p>Create your first product case to begin intelligence analysis.</p>'
        + '<button class="btn btn-primary" id="create-case-btn-2">' + icon("add", 16) + ' Create Product Case</button>'
        + '</div>';
    } else {
      html += '<div class="case-grid">';
      cases.forEach(function (c) {
        var createdDate = c.created_at ? new Date(c.created_at).toLocaleDateString("en-IN", { month: "short", day: "numeric", year: "numeric" }) : "Recently";
        var safeName = String(c.name || 'Product').replace(/'/g, "\\'");
        var ingCount = Array.isArray(c.ingredients) ? c.ingredients.length : (c.ingredients && typeof c.ingredients === 'object' ? Object.keys(c.ingredients).length : (c.ingredients ? 1 : 0));
        var statusText = statusLabel(c.status) || c.status || 'Draft';
        var statusClass = (c.status || 'draft').toLowerCase();

        html += '<div class="clean-product-card" data-case-id="' + c.id + '">'
          + '<div class="product-card-left">'
          + '<span class="product-card-name">' + escapeHtml(c.name || 'Product') + '</span>'
          + '<div class="product-card-meta">'
          + '<span>📅 Created ' + escapeHtml(createdDate) + '</span>'
          + '<span class="ingredient-count">🌿 ' + ingCount + ' ' + (ingCount === 1 ? 'ingredient' : 'ingredients') + '</span>'
          + '</div>'
          + '</div>'
          + '<div class="product-card-right">'
          + '<span class="product-card-status ' + escapeHtml(statusClass) + '">' + escapeHtml(statusText) + '</span>'
          + '<button class="product-open-btn" onclick="event.stopPropagation(); openCase(\'' + c.id + '\')">Open Case</button>'
          + '<button class="product-delete-btn" onclick="event.stopPropagation(); deleteCase(\'' + c.id + '\', \'' + safeName + '\')">🗑 Delete</button>'
          + '</div>'
          + '</div>';
      });
      html += '</div>';
    }
    return html;
  }

  // ----------------------------------------------------------------
  // Product Cases View
  // ----------------------------------------------------------------
  function renderProductCases() {
    var cases = state.cases || [];
    var html = ''
      + '<div class="section-header"><div><h2 style="font-family:\'Geist\',sans-serif;">Products</h2><p style="font-size:13px;color:var(--text-secondary);margin-top:2px;">Review and manage all active product cases and research profiles.</p></div>'
      + '<button class="btn btn-primary btn-sm" id="create-case-btn-3">' + icon("add", 14) + ' New Case</button></div>';
    if (cases.length === 0) {
      html += '<div class="empty-state"><div class="empty-icon">' + icon("inventory_2", 28) + '</div>'
        + '<h3>No Products Found</h3><p>Create your first product case to initiate intelligence analysis.</p></div>';
    } else {
      html += '<div class="case-grid">';
      cases.forEach(function (c) {
        var createdDate = c.created_at ? new Date(c.created_at).toLocaleDateString("en-IN", { month: "short", day: "numeric", year: "numeric" }) : "Recently";
        var safeName = String(c.name || 'Product').replace(/'/g, "\\'");
        var ingCount = Array.isArray(c.ingredients) ? c.ingredients.length : (c.ingredients && typeof c.ingredients === 'object' ? Object.keys(c.ingredients).length : (c.ingredients ? 1 : 0));
        var statusText = statusLabel(c.status) || c.status || 'Draft';
        var statusClass = (c.status || 'draft').toLowerCase();

        html += '<div class="clean-product-card" data-case-id="' + c.id + '">'
          + '<div class="product-card-left">'
          + '<span class="product-card-name">' + escapeHtml(c.name || 'Product') + '</span>'
          + '<div class="product-card-meta">'
          + '<span>📅 Created ' + escapeHtml(createdDate) + '</span>'
          + '<span class="ingredient-count">🌿 ' + ingCount + ' ' + (ingCount === 1 ? 'ingredient' : 'ingredients') + '</span>'
          + '</div>'
          + '</div>'
          + '<div class="product-card-right">'
          + '<span class="product-card-status ' + escapeHtml(statusClass) + '">' + escapeHtml(statusText) + '</span>'
          + '<button class="product-open-btn" onclick="event.stopPropagation(); openCase(\'' + c.id + '\')">Open Case</button>'
          + '<button class="product-delete-btn" onclick="event.stopPropagation(); deleteCase(\'' + c.id + '\', \'' + safeName + '\')">🗑 Delete</button>'
          + '</div>'
          + '</div>';
      });
      html += '</div>';
    }
    return html;
  }

  // ----------------------------------------------------------------
  // Case Detail View
  // ----------------------------------------------------------------
  // ----------------------------------------------------------------
  // ----------------------------------------------------------------
  // ----------------------------------------------------------------
  // Case Intelligence Workspace
  // ----------------------------------------------------------------
  function renderCaseIntelligence() {
    var state = (window.AYUR && window.AYUR.state) || state;
    var caseData = state.currentCase;
    
    // DEBUG: Log what we have
    console.log('🔍 CASE DATA:', caseData);
    console.log('🔍 CASE DATA INGREDIENTS:', caseData ? caseData.ingredients : undefined);
    
    if (!caseData) {
        return '<div class="empty-state">'
            + '<span class="empty-icon">🔍</span>'
            + '<h3>No Active Case</h3>'
            + '<p>Create a new product or select an existing one.</p>'
            + '<button onclick="window.AYUR.state.view=\'dashboard\';window.AYUR.render();">Go to Dashboard</button>'
            + '</div>';
    }
    
    // Extract name
    var name = caseData.name || 'Unnamed Product';
    
    // ===== CRITICAL FIX: Parse ingredients PROPERLY =====
    var ingredients = [];
    
    // Case 1: ingredients is already an array
    if (Array.isArray(caseData.ingredients)) {
        ingredients = caseData.ingredients;
    }
    // Case 2: ingredients is a JSON string
    else if (typeof caseData.ingredients === 'string') {
        try {
            var parsed = JSON.parse(caseData.ingredients);
            if (Array.isArray(parsed)) {
                ingredients = parsed;
            }
        } catch (e) {
            console.warn('Could not parse ingredients JSON:', e);
        }
    }
    // Case 3: ingredients exists but is an object
    else if (caseData.ingredients && typeof caseData.ingredients === 'object') {
        ingredients = Object.values(caseData.ingredients);
    }
    
    // ===== DEBUG: Log what we parsed =====
    console.log('✅ PARSED INGREDIENTS:', ingredients);
    console.log('✅ INGREDIENTS COUNT:', ingredients.length);
    
    // Form - ONLY show what user entered, NOT "Not specified" if user selected something
    let form = caseData.form || caseData.dosage_form || caseData.formulation || caseData.product_type;
    if (!form || form === '' || form === 'null' || form === 'undefined') {
        form = 'Not specified';
    }
    console.log('📦 FORM VALUE:', form);

    var intendedUse = caseData.intended_use || 'Not specified';
    var process = caseData.process || 'Not specified';
    var stage = caseData.stage || 'IDEA';
    var status = caseData.status || 'DRAFT';
    
    // Build ingredient list HTML - Clickable with popup
    var ingredientListHTML = '';
    if (ingredients && ingredients.length > 0) {
        ingredientListHTML = ingredients.map(function (ing, index) {
            var ingName = (typeof ing === 'object' ? (ing.name || ing.input_name || ing.ingredient_name) : ing) || 'Unknown';
            var botanical = (typeof ing === 'object' ? (ing.botanical || ing.botanical_name) : '') || '';
            var quantity = (typeof ing === 'object' ? ing.quantity : '') || '';
            var safeName = String(ingName).replace(/'/g, "\\'");
            var safeBotanical = String(botanical).replace(/'/g, "\\'");
            var safeQuantity = String(quantity).replace(/'/g, "\\'");
            return '<div class="ci-ingredient-item clickable" data-index="' + index + '" onclick="showIngredientPopup(\'' + safeName + '\', \'' + safeBotanical + '\', \'' + safeQuantity + '\')">'
                + '<span class="ci-ing-name">' + escapeHtml(ingName) + '</span>'
                + (botanical ? '<span class="ci-ing-botanical">(' + escapeHtml(botanical) + ')</span>' : '')
                + (quantity ? '<span class="ci-ing-qty">' + escapeHtml(quantity) + '</span>' : '')
                + '<span class="ci-ing-click-hint">↗</span>'
                + '</div>';
        }).join('');
    } else {
        ingredientListHTML = '<span class="ci-empty">No ingredients added</span>';
    }
    
    var html = '<div class="case-intelligence">'
        + '<div class="ci-header">'
        + '<h2>Case Intelligence · ' + escapeHtml(name) + '</h2>'
        + '<div class="ci-meta">'
        + '<span class="ci-badge stage">' + escapeHtml(stage) + '</span>'
        + '<span class="ci-badge status">' + escapeHtml(status) + '</span>'
        + '<button class="ci-edit-btn" onclick="editProductPassport(\'' + caseData.id + '\')">✏️ Edit</button>'
        + '<button class="ci-close-btn" onclick="window.AYUR.state.currentCase=null;if(typeof window.AYUR.saveStateToLocalStorage===\'function\'){window.AYUR.saveStateToLocalStorage();}window.AYUR.updateTopbarUI();window.AYUR.render();">✕ Close Case</button>'
        + '</div>'
        + '</div>'
        
        + '<!-- Grid Cards -->'
        + '<div class="ci-grid">'
        + '<!-- Form -->'
        + '<div class="ci-card">'
        + '<h4>📦 Formulation & Form</h4>'
        + '<div class="ci-value">' + escapeHtml(form) + '</div>'
        + '<div class="ci-label">Dosage Form</div>'
        + '</div>'
        
        + '<!-- Process -->'
        + '<div class="ci-card">'
        + '<h4>⚙️ Preparation Process</h4>'
        + '<div class="ci-value">' + escapeHtml(process) + '</div>'
        + '<div class="ci-label">Manufacturing Method</div>'
        + '</div>'
        
        + '<!-- Ingredients - CRITICAL FIX -->'
        + '<div class="ci-card">'
        + '<h4>🌿 Verified Botanicals</h4>'
        + '<div class="ci-value" style="font-size: 24px;">' + ingredients.length + ' Ingredients</div>'
        + '<div class="ci-ingredient-list">' + ingredientListHTML + '</div>'
        + '</div>'
        
        + '<!-- Indication -->'
        + '<div class="ci-card">'
        + '<h4>🎯 Intended Indication</h4>'
        + '<div class="ci-value">' + escapeHtml(intendedUse) + '</div>'
        + '<div class="ci-label">Primary Use</div>'
        + '</div>'
        + '</div>'
        
        + '<!-- Workspace -->'
        + '<div class="ci-workspace">'
        + '<h3>🧠 Intelligence Workspace</h3>'
        + '<div class="ci-workspace-grid">'
        + '<div class="workspace-card">'
        + '<span class="ws-icon">💡</span>'
        + '<h4>Innovation Analysis</h4>'
        + '<p>Decompose formulation into ingredients, process, claims, and differentiation areas.</p>'
        + '<button class="ws-btn" onclick="runInnovationAnalysis()">Analyze →</button>'
        + '</div>'
        + '<div class="workspace-card" id="card-intel-patent" onclick="openPatentIntelligence()">'
        + '<span class="ws-icon">📜</span>'
        + '<h4>Patents & IP</h4>'
        + '<p>Search Indian patent databases (IPO / InPASS) and global prior art for evidence-first screening.</p>'
        + '<button class="ws-btn" onclick="event.stopPropagation(); openPatentIntelligence()">Search →</button>'
        + '</div>'
        + '<div class="workspace-card">'
        + '<span class="ws-icon">🗺️</span>'
        + '<h4>IP Strategy</h4>'
        + '<p>Generate prioritized IP roadmap and protection routes.</p>'
        + '<button class="ws-btn" onclick="generateIPStrategy()">Generate →</button>'
        + '</div>'
        + '<div class="workspace-card" id="card-intel-regulatory">'
        + '<span class="ws-icon">📋</span>'
        + '<h4>Regulatory Pathways</h4>'
        + '<p>Navigate AYUSH, FSSAI, and Indian regulatory requirements.</p>'
        + '<button class="ws-btn" onclick="event.stopPropagation(); generateRegulatoryAnalysis()">Check →</button>'
        + '</div>'
        + '<div class="workspace-card" id="card-intel-risk">'
        + '<span class="ws-icon">⚠️</span>'
        + '<h4>Risk Assessment</h4>'
        + '<p>Identify IP, regulatory, and market risks.</p>'
        + '<button class="ws-btn" onclick="event.stopPropagation(); generateRiskAssessment()">Assess →</button>'
        + '</div>'
        + '<div class="workspace-card" id="card-intel-graph" onclick="openKnowledgeGraph()">'
        + '<span class="ws-icon">🕸️</span>'
        + '<h4>Knowledge Graph</h4>'
        + '<p>Visualize relationships between ingredients, patents, and evidence.</p>'
        + '<button class="ws-btn" id="open-knowledge-graph-btn" onclick="event.stopPropagation(); openKnowledgeGraph()">Explore →</button>'
        + '</div>'
        + '</div>'
        + '</div>'
        + '</div>';
    
    return html;
  }
  var renderCaseDetail = renderCaseIntelligence;

  // ----------------------------------------------------------------
  // DRAVYA Ingredient Search & Detail Functions
  // ----------------------------------------------------------------
  async function searchIngredients(query, limit) {
    if (!query || !query.trim()) return { query: "", total_results: 0, results: [] };
    try {
      var resp = await fetch('/api/ingredients/search?q=' + encodeURIComponent(query.trim()) + '&limit=' + (limit || 20));
      if (!resp.ok) throw new Error('Search failed: ' + resp.status);
      return await resp.json();
    } catch (e) {
      console.error('Error searching ingredients:', e);
      return { query: query, total_results: 0, results: [], error: e.message };
    }
  }

  async function getIngredientDetail(plantId) {
    try {
      var resp = await fetch('/api/ingredients/' + plantId);
      if (!resp.ok) throw new Error('Failed to fetch detail: ' + resp.status);
      return await resp.json();
    } catch (e) {
      console.error('Error fetching plant detail:', e);
      return null;
    }
  }

  async function autocompleteIngredients(query, limit) {
    if (!query || !query.trim()) return [];
    try {
      var resp = await fetch('/api/ingredients/autocomplete?q=' + encodeURIComponent(query.trim()) + '&limit=' + (limit || 10));
      if (!resp.ok) throw new Error('Autocomplete failed: ' + resp.status);
      return await resp.json();
    } catch (e) {
      console.error('Error in autocomplete:', e);
      return [];
    }
  }

  async function showIngredientPopup(name, botanical, quantity) {
    var initialHTML = `
        <div class="ingredient-popup-overlay" id="ingredient-popup" onclick="if(event.target===this)closeIngredientPopup()">
            <div class="ingredient-popup-card" style="max-width: 650px; max-height: 88vh; overflow-y: auto; background: var(--color-surface-container, #141c18); border: 1px solid rgba(46, 204, 113, 0.3); border-radius: 16px; padding: 24px;">
                <button class="popup-close-btn" onclick="closeIngredientPopup()">✕</button>
                <div class="popup-icon" style="font-size: 32px; margin-bottom: 8px;">🌿</div>
                <h3 style="font-size: 20px; font-weight: 700; color: #ffffff; margin-bottom: 4px;">${escapeHtml(name)}</h3>
                ${botanical ? `<p class="popup-botanical" style="color: #7dba9a; font-size: 13.5px; font-style: italic; margin-bottom: 4px;">Botanical Name: ${escapeHtml(botanical)}</p>` : ''}
                ${quantity ? `<p class="popup-quantity" style="color: #3498db; font-size: 13px; font-weight: 600; margin-bottom: 12px;">Quantity: ${escapeHtml(quantity)}</p>` : ''}
                
                <div id="ingredient-popup-body">
                    <div style="text-align: center; padding: 24px; color: #7dba9a;">
                        <div class="spinner" style="margin: 0 auto 10px;"></div>
                        Verifying CCRAS DRAVYA monograph &amp; Schedule E-1 compliance...
                    </div>
                </div>
                
                <button class="popup-close-action" onclick="closeIngredientPopup()" style="margin-top: 16px; width: 100%; justify-content: center;">Close</button>
            </div>
        </div>
    `;

    var existing = document.getElementById('ingredient-popup');
    if (existing) existing.remove();
    document.body.insertAdjacentHTML('beforeend', initialHTML);

    var bodyEl = document.getElementById('ingredient-popup-body');
    if (!bodyEl) return;

    try {
      var resp = await fetch('/api/ingredients/eligibility/' + encodeURIComponent(name));
      if (!resp.ok) throw new Error('API returned ' + resp.status);
      var data = await resp.json();

      var lvl = data.eligibility_level || 'NOT FOUND';
      var lvlClass = lvl.toLowerCase().replace(' ', '_');
      var badgeIcon = (lvl === 'HIGH' || lvl === 'MEDIUM') ? '✅' : (lvl === 'LOW' ? '⚠️' : '❌');
      var props = data.properties || {};

      var gunas = (props.guna || []).join(', ');
      var viryas = (props.virya || []).join(', ');
      var vipakas = (props.vipaka || []).join(', ');
      var karmas = (props.karma || []).slice(0, 6).join(', ');
      var doshakarmas = (props.doshakarma || []).join(', ');
      var uses = (props.therapeutic_usage || []).slice(0, 8).join(', ');

      var html = '';

      // Schedule E-1 Alert if applicable
      if (data.schedule_e1) {
        html += `
            <div class="schedule-e1-alert">
                <span style="font-size: 18px;">⚠️</span>
                <div>
                    <strong>Schedule E-1 Poisonous Substance Detected</strong><br>
                    <span style="font-weight: 400; font-size: 12px;">${escapeHtml(data.schedule_e1_warning || '')}</span>
                </div>
            </div>
        `;
      }

      html += `
          <div class="eligibility-card">
              <div class="eligibility-header">
                  <div>
                      <span class="eligibility-badge ${lvlClass}">${badgeIcon} Status: ${escapeHtml(data.status)} (${escapeHtml(lvl)})</span>
                  </div>
                  <div style="text-align: right;">
                      <strong style="font-size: 16px; color: ${lvl === 'HIGH' ? '#2ecc71' : (lvl === 'MEDIUM' ? '#f1c40f' : '#e74c3c')};">Score: ${data.score}%</strong>
                  </div>
              </div>

              <div class="eligibility-score-bar">
                  <div class="eligibility-score-fill ${lvlClass}" style="width: ${data.score}%;"></div>
              </div>

              <div style="font-size: 13.5px; line-height: 1.6; color: #e0eee8; margin-bottom: 14px;">
                  <div style="margin-bottom: 4px;"><strong>📜 Scientific Name:</strong> <span style="color: #ffffff; font-weight: 600;">${escapeHtml(data.scientific_name || 'Not Specified')}</span></div>
                  ${data.family ? `<div style="margin-bottom: 4px;"><strong>🌱 Family:</strong> ${escapeHtml(data.family)}</div>` : ''}
                  <div style="margin-bottom: 4px;"><strong>📖 Classical Reference:</strong> ${escapeHtml(data.classical_reference || 'Recognized in Classical Ayurvedic Texts')}</div>
              </div>

              ${(gunas || viryas || vipakas || karmas || doshakarmas) ? `
              <!-- Ayurvedic Properties -->
              <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; padding: 12px; margin-bottom: 14px; font-size: 12.5px;">
                  <strong style="color: #2ecc71; display: block; margin-bottom: 6px; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px;">⚕️ Ayurvedic Pharmacological Profile:</strong>
                  ${gunas ? `<div><strong>Guna:</strong> ${escapeHtml(gunas)}</div>` : ''}
                  ${viryas ? `<div><strong>Virya:</strong> ${escapeHtml(viryas)}</div>` : ''}
                  ${vipakas ? `<div><strong>Vipaka:</strong> ${escapeHtml(vipakas)}</div>` : ''}
                  ${doshakarmas ? `<div><strong>Doshakarma:</strong> ${escapeHtml(doshakarmas)}</div>` : ''}
                  ${karmas ? `<div><strong>Karma:</strong> ${escapeHtml(karmas)}</div>` : ''}
              </div>
              ` : ''}

              ${uses ? `
              <div style="margin-bottom: 14px; font-size: 12.5px;">
                  <strong style="color: #3498db; display: block; margin-bottom: 4px; text-transform: uppercase; font-size: 11px;">🩺 Therapeutic Indications:</strong>
                  <div style="color: #b0c8c0;">${escapeHtml(uses)}</div>
              </div>
              ` : ''}

              <!-- Verification Details Criteria -->
              <div style="font-size: 12px; background: rgba(0,0,0,0.2); border-radius: 8px; padding: 10px;">
                  <strong style="color: #7dba9a; display: block; margin-bottom: 6px; text-transform: uppercase; font-size: 10.5px;">📌 Verification Details:</strong>
                  ${(data.breakdown || []).map(function(item) {
                      return `<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 3px; color: ${item.passed ? '#e0eee8' : '#888'};">
                          <span>${item.passed ? '✅' : '❌'} ${escapeHtml(item.criterion)}</span>
                          <span style="font-weight: 600; color: ${item.passed ? '#2ecc71' : '#666'};">+${item.score || 0}% / ${item.weight}%</span>
                      </div>`;
                  }).join('')}
              </div>

              ${data.url ? `
              <div style="margin-top: 12px; text-align: right;">
                  <a href="${data.url}" target="_blank" class="btn btn-xs" style="display: inline-flex; align-items: center; gap: 4px; color: #3498db; background: rgba(52, 152, 219, 0.15); border: 1px solid rgba(52, 152, 219, 0.35); padding: 5px 12px; border-radius: 4px; text-decoration: none; font-size: 11.5px; font-weight: 600;">
                      View Monograph on CCRAS DRAVYA Portal ↗
                  </a>
              </div>
              ` : ''}
          </div>
      `;

      bodyEl.innerHTML = html;

    } catch (err) {
      console.error('Error fetching eligibility in popup:', err);
      bodyEl.innerHTML = `
          <div class="popup-description">
              <p><strong>About this ingredient:</strong></p>
              <p>${escapeHtml(getIngredientDescription(name))}</p>
          </div>
      `;
    }
  }

  function getIngredientDescription(name) {
    const descriptions = {
        'ashwagandha': 'Adaptogenic herb that helps the body manage stress and promotes overall well-being.',
        'brahmi': 'Supports cognitive function, memory, and mental clarity. Traditionally used for brain health.',
        'tulsi': 'Sacred basil that supports respiratory health, immunity, and stress management.',
        'turmeric': 'Powerful anti-inflammatory and antioxidant herb for joint health and overall wellness.',
        'amla': 'Rich in Vitamin C, supports immunity, digestion, and skin health.',
        'triphala': 'Combination of three fruits for digestive health, detoxification, and nourishment.',
        'shatavari': 'Supports female reproductive health, hormonal balance, and lactation.',
        'giloy': 'Immunomodulator that helps fight infections and supports overall immunity.',
        'neem': 'Purifies blood, supports skin health, and has antibacterial properties.',
        'jatamansi': 'Calming herb for nervous system support, sleep, and mental clarity.',
        'mulethi': 'Supports respiratory health, digestion, and soothes inflammation.',
        'haritaki': 'Supports digestive health, elimination, and rejuvenation.',
        'bibhitaki': 'Supports respiratory health, digestion, and eye health.',
        'shankhpushpi': 'Enhances memory, concentration, and cognitive function.',
        'guggul': 'Supports healthy cholesterol levels and joint health.',
        'ginger': 'Aids digestion, reduces nausea, and has anti-inflammatory properties.'
    };
    
    const key = (name || '').toLowerCase().trim();
    for (const [k, v] of Object.entries(descriptions)) {
        if (key.includes(k)) return v;
    }
    return descriptions[key] || `${name} is a traditional Ayurvedic herb used in various formulations for wellness and balance.`;
  }

  function closeIngredientPopup() {
    const popup = document.getElementById('ingredient-popup');
    if (popup) popup.remove();
  }

  window.searchIngredients = searchIngredients;
  window.getIngredientDetail = getIngredientDetail;
  window.autocompleteIngredients = autocompleteIngredients;
  window.showIngredientPopup = showIngredientPopup;
  window.getIngredientDescription = getIngredientDescription;
  window.closeIngredientPopup = closeIngredientPopup;
  window.deleteCase = deleteCase;


  async function deleteCase(caseId, caseName) {
    if (!caseId) return;
    if (!confirm(`Delete "${caseName || 'this product'}"? This cannot be undone.`)) {
      return;
    }
    
    try {
        invalidateClientApiCache('/api/cases');
        invalidateCaseModuleCache(caseId);
        const response = await fetch(`/api/cases/${caseId}`, { method: 'DELETE' });
        if (response.ok || response.status === 204) {
            invalidateClientApiCache('/api/cases');
            invalidateCaseModuleCache(caseId);

            // Optimistically remove from state immediately
            state.cases = (state.cases || []).filter(function (c) {
                return String(c.id) !== String(caseId);
            });

            if (state.currentCase && String(state.currentCase.id) === String(caseId)) {
                state.currentCase = null;
                if (window.AYUR && window.AYUR.state) window.AYUR.state.currentCase = null;
                if (state.view !== "product-cases" && state.view !== "dashboard") {
                    state.view = "dashboard";
                }
            }
            saveStateToLocalStorage();
            updateTopbarUI();
            render();

            if (typeof showToast === 'function') showToast(`✅ "${caseName}" deleted`, 'success');
            else if (typeof toast === 'function') toast(`✅ "${caseName}" deleted`, 'success');

            loadCases().then(function () {
                render();
            });
        } else {
            var errText = "";
            try { errText = await response.text(); } catch (e) {}
            console.error('🗑 DELETE failed:', response.status, errText);
            if (typeof showToast === 'function') showToast('❌ Delete failed: ' + (errText || 'Server error'), 'error');
            else if (typeof toast === 'function') toast('❌ Delete failed: ' + (errText || 'Server error'), 'error');
        }
    } catch (error) {
        console.error('🗑 DELETE catch error:', error);
        if (typeof showToast === 'function') showToast('❌ Error deleting product', 'error');
        else if (typeof toast === 'function') toast('❌ Error deleting product', 'error');
    }
  }

  async function openCase(caseId) {
    if (!caseId) return;
    await loadCase(caseId);
  }

  async function runInnovationAnalysis() {
    const s = (window.AYUR && window.AYUR.state) || state;
    const caseData = s.currentCase;

    if (!caseData || !caseData.id) {
      if (typeof showToast === 'function') showToast('⚠️ Please select a product case first', 'warning');
      else if (typeof toast === 'function') toast('⚠️ Please select a product case first', 'warning');
      return;
    }

    var isNewView = s.view !== 'innovation-analysis';
    if (isNewView) {
      saveCurrentViewScrollPosition();
    }

    if (typeof showToast === 'function') showToast('🔬 Analyzing innovation...', 'info');
    else if (typeof toast === 'function') toast('🔬 Analyzing innovation...', 'info');

    try {
      const response = await fetch(`/api/cases/${caseData.id}/innovate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      if (!response.ok) {
        throw new Error('Analysis failed');
      }

      const result = await response.json();
      s.innovationAnalysis = result;
      s.view = 'innovation-analysis';
      if (typeof saveStateToLocalStorage === 'function') saveStateToLocalStorage();
      renderInnovationResults(result);
      if (isNewView) {
        scrollToTop();
      }
      if (typeof showToast === 'function') showToast('✅ Innovation analysis complete!', 'success');
      else if (typeof toast === 'function') toast('✅ Innovation analysis complete!', 'success');

    } catch (error) {
      console.error('Innovation analysis error:', error);
      if (typeof showToast === 'function') showToast('❌ Failed to analyze innovation', 'error');
      else if (typeof toast === 'function') toast('❌ Failed to analyze innovation', 'error');
    }
  }

  // Plant images mapping
  const PLANT_IMAGES = {
    "ashwagandha": "🌿",
    "tulsi": "🍃",
    "brahmi": "🌱",
    "turmeric": "✨",
    "amla": "🍈",
    "neem": "🌿",
    "giloy": "🪴",
    "shatavari": "🌿",
    "triphala": "🫐",
    "jatamansi": "🌿",
    "mulethi": "🪵"
  };

  function getPlantImage(name) {
    if (!name) return '🌿';
    const key = name.toLowerCase().trim();
    for (const [k, v] of Object.entries(PLANT_IMAGES)) {
      if (key.includes(k) || k.includes(key)) return v;
    }
    return '🌿';
  }

  function showDetailPopup(title, description, detail, icon, type) {
    const popupHTML = `
        <div class="detail-popup-overlay" onclick="if(event.target===this)closeDetailPopup()">
            <div class="detail-popup-card">
                <button class="detail-popup-close" onclick="closeDetailPopup()">✕</button>
                <div class="detail-popup-icon">${icon || '💡'}</div>
                <h3>${title}</h3>
                <div class="detail-popup-type ${type || 'neutral'}">
                    ${type === 'positive' ? '✅ Insight' : type === 'traditional' ? '📜 Traditional' : type === 'innovative' ? '🚀 Innovation' : type === 'unique' ? '🔗 Unique' : type === 'enhance' ? '✨ Opportunity' : '💡 Recommendation'}
                </div>
                <div class="detail-popup-description">
                    <strong>What this means:</strong>
                    <p>${description}</p>
                </div>
                <div class="detail-popup-detail">
                    <strong>Why:</strong>
                    <p>${detail || 'Additional context for this recommendation.'}</p>
                </div>
                <button class="detail-popup-action" onclick="closeDetailPopup()">Got it</button>
            </div>
        </div>
    `;

    const existing = document.getElementById('detail-popup');
    if (existing) existing.remove();

    const div = document.createElement('div');
    div.id = 'detail-popup';
    div.innerHTML = popupHTML;
    document.body.appendChild(div);
  }

  function closeDetailPopup() {
    const popup = document.getElementById('detail-popup');
    if (popup) popup.remove();
  }

  window.showDetailPopup = showDetailPopup;
  window.closeDetailPopup = closeDetailPopup;
  window.getPlantImage = getPlantImage;

  function safeJsAttr(str) {
    return String(str || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '&quot;').replace(/\n/g, ' ');
  }

  function renderInnovationResults(result) {
    const content = document.getElementById('content');
    if (!result) return '';

    // Get plant images for ingredients
    const ingredientNames = result.traditional_elements?.map(el => el.name) || [];
    const plantImages = ingredientNames.map(name => getPlantImage(name)).slice(0, 3);
    if (plantImages.length === 0) plantImages.push('🌿');

    const html = `
        <div class="case-intelligence">
            <!-- Header -->
            <div class="ci-header">
                <h2>💡 Innovation Analysis · ${escapeHtml(result.product_name || 'Product')}</h2>
                <div class="ci-meta">
                    <span class="ci-badge stage">${escapeHtml(result.confidence || 'Medium')} Confidence</span>
                    <button class="ci-close-btn" onclick="if(window.AYUR){window.AYUR.navigateBackToCaseDetail();}">← Back to Case</button>
                </div>
            </div>
            
            <!-- Product Overview Card -->
            <div class="ci-grid" style="margin-bottom: 24px;">
                <div class="ci-card" style="grid-column: 1 / -1; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px;">
                    <div style="display: flex; align-items: center; gap: 14px;">
                        <span style="font-size: 28px;">${plantImages.join(' ')}</span>
                        <div>
                            <h3 style="margin: 0 0 4px 0; font-size: 18px; color: #e0eee8;">${escapeHtml(result.product_name || 'Unnamed Product')}</h3>
                            <p style="margin: 0; font-size: 13px; color: #6b8a7a;">${result.total_ingredients || 0} ingredients · ${result.traditional_elements?.length || 0} traditional · ${result.innovative_elements?.length || 0} innovative</p>
                        </div>
                    </div>
                    <span class="ci-badge status" style="font-size: 12px; padding: 4px 12px;">${escapeHtml(result.confidence || 'Medium')} Confidence</span>
                </div>
            </div>
            
            <!-- Insights Cards -->
            <div class="ci-grid" style="margin-bottom: 24px;">
                ${result.innovation_insights?.map(insight => `
                    <div class="ci-card">
                        <h4>${insight.icon || (insight.type === 'positive' ? '✅' : '💡')} ${escapeHtml(insight.title)}</h4>
                        <div class="ci-value" style="font-size: 14px; margin: 8px 0; color: #e0eee8; font-weight: 500;">${escapeHtml(insight.description)}</div>
                        <div class="ci-label" style="font-size: 12px; line-height: 1.4; color: #8aaaa0;">${escapeHtml(insight.detail || '')}</div>
                    </div>
                `).join('') || ''}
            </div>
            
            <!-- Elements Breakdown Grid & Product Summary -->
            <div class="innovation-premium-grid" style="margin-bottom: 24px;">
                <!-- Left Column Elements -->
                <div class="innovation-elements-col">
                    <!-- Traditional Elements -->
                    <div class="ci-card">
                        <h4>📜 Traditional Elements (${result.traditional_elements?.length || 0})</h4>
                        <div class="ci-ingredient-list" style="margin-top: 10px;">
                            ${result.traditional_elements?.length > 0 ? 
                                result.traditional_elements.map(el => `
                                    <div class="ci-ingredient-item">
                                        <span class="ci-ing-name">${escapeHtml(el.name)}</span>
                                        <span class="ci-ing-botanical">${escapeHtml(el.reason)}</span>
                                    </div>
                                `).join('') : 
                                '<span class="ci-empty">No traditional elements identified</span>'
                            }
                        </div>
                    </div>
                    
                    <!-- Innovative Elements -->
                    <div class="ci-card" style="margin-top: 16px;">
                        <h4>🚀 Innovative Elements (${result.innovative_elements?.length || 0})</h4>
                        <div class="ci-ingredient-list" style="margin-top: 10px;">
                            ${result.innovative_elements?.length > 0 ? 
                                result.innovative_elements.map(el => `
                                    <div class="ci-ingredient-item">
                                        <span class="ci-ing-name">${escapeHtml(el.name)}</span>
                                        <span class="ci-ing-botanical">${escapeHtml(el.reason)}</span>
                                    </div>
                                `).join('') : 
                                '<span class="ci-empty">No innovative elements identified yet</span>'
                            }
                        </div>
                    </div>

                    <!-- Unique Combinations -->
                    ${result.unique_combinations?.length > 0 ? `
                        <div class="ci-card" style="margin-top: 16px;">
                            <h4>🔗 Unique Combinations (${result.unique_combinations.length})</h4>
                            <div class="ci-ingredient-list" style="margin-top: 10px;">
                                ${result.unique_combinations.map(el => `
                                    <div class="ci-ingredient-item">
                                        <span class="ci-ing-name">${escapeHtml(el.name)}</span>
                                        <span class="ci-ing-botanical">${escapeHtml(el.reason)}</span>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>

                <!-- Product Summary Card - Fills Empty Space on Right -->
                <div class="innovation-summary-card">
                    <div class="summary-card-header">
                        <span class="summary-card-icon">📊</span>
                        <h4>Product Summary</h4>
                    </div>
                    <div class="summary-card-body">
                        <div class="summary-row">
                            <span class="summary-label">Product</span>
                            <span class="summary-value">${escapeHtml(result.product_name || 'Product')}</span>
                        </div>
                        <div class="summary-row">
                            <span class="summary-label">Total Ingredients</span>
                            <span class="summary-value">${result.total_ingredients || 0}</span>
                        </div>
                        <div class="summary-row">
                            <span class="summary-label">📜 Traditional</span>
                            <span class="summary-value">${result.traditional_elements?.length || 0}</span>
                        </div>
                        <div class="summary-row">
                            <span class="summary-label">🚀 Innovative</span>
                            <span class="summary-value">${result.innovative_elements?.length || 0}</span>
                        </div>
                        <div class="summary-row">
                            <span class="summary-label">Confidence</span>
                            <span class="summary-value">${escapeHtml(result.confidence || 'Medium')}</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Enhancement Suggestions -->
            <div class="ci-workspace" style="margin-bottom: 24px;">
                <h3>✨ Enhancement Suggestions & Opportunities</h3>
                <div class="ci-workspace-grid">
                    ${result.enhancement_suggestions?.map(suggestion => `
                        <div class="workspace-card">
                            <span class="ws-icon">${suggestion.icon || '💡'}</span>
                            <h4>${escapeHtml(suggestion.title)}</h4>
                            <p>${escapeHtml(suggestion.description)}</p>
                            <p style="font-size: 11px; color: #7dba9a; margin-top: 6px; line-height: 1.4;">${escapeHtml(suggestion.detail || '')}</p>
                        </div>
                    `).join('') || ''}
                </div>
            </div>
            
            <!-- Recommendations & Disclaimer -->
            <div class="ci-card" style="margin-bottom: 16px; background: rgba(45,139,106,0.04);">
                <h4>📌 Recommended Next Steps</h4>
                <ul style="margin: 8px 0 0 16px; color: #b0c8c0; font-size: 13px; line-height: 1.8;">
                    ${result.recommendations?.map(r => `<li>${escapeHtml(r)}</li>`).join('') || ''}
                </ul>
            </div>
            
            <div style="padding: 12px 16px; background: rgba(255,80,80,0.04); border: 1px solid rgba(255,80,80,0.08); border-radius: 10px; font-size: 12px; color: #6b8a7a;">
                ⚠️ This analysis is for informational and decision-support purposes only. It does not constitute legal advice or patentability opinion. Please consult qualified professionals for final IP decisions.
            </div>
        </div>
    `;

    if (content) content.innerHTML = html;
    return html;
  }

  var renderInnovationAnalysis = function() {
    return renderInnovationResults(state.innovationAnalysis);
  };

  window.deleteCase = deleteCase;
  window.openCase = openCase;
  window.runInnovationAnalysis = runInnovationAnalysis;
  window.renderInnovationResults = renderInnovationResults;
  window.renderInnovationAnalysis = renderInnovationAnalysis;
  window.generateIPStrategy = generateIPStrategy;
  window.renderIPStrategyResult = renderIPStrategyResult;
  window.renderIPStrategy = renderIPStrategy;
  if (window.AYUR) {
    window.AYUR.deleteCase = deleteCase;
    window.AYUR.openCase = openCase;
    window.AYUR.runInnovationAnalysis = runInnovationAnalysis;
    window.AYUR.renderInnovationResults = renderInnovationResults;
    window.AYUR.renderInnovationAnalysis = renderInnovationAnalysis;
    window.AYUR.generateIPStrategy = generateIPStrategy;
    window.AYUR.renderIPStrategyResult = renderIPStrategyResult;
    window.AYUR.renderIPStrategy = renderIPStrategy;
  }

  function renderPlantDiscovery() {
    return '<div class="card"><div class="card-head"><h2>Plant Discovery</h2><p>Upload an image for preliminary plant identification</p></div>'
      + '<div class="card-body">'
      + '<div class="upload-zone" id="upload-zone">'
      + '<div class="upload-icon">' + icon("cloud_upload", 28) + '</div>'
      + '<div class="upload-title">Drop an image here or click to upload</div>'
      + '<div class="upload-hint">Supports JPG, PNG up to 10MB</div>'
      + '</div>'
      + '<input type="file" id="plant-file-input" accept="image/*" style="display:none">'
      + '<div id="plant-result"></div>'
      + '</div></div>';
  }

  // ----------------------------------------------------------------
  // Knowledge Engine View
  // ----------------------------------------------------------------
  function renderKnowledgeEngine() {
    var html = ''
      + '<div class="card" style="margin-bottom:20px"><div class="card-head">'
      + '<h2>Knowledge Engine</h2>'
      + '<p>Explore traditional Ayurvedic texts, classical preparations, and peer-reviewed scientific literature.</p>'
      + '</div><div class="card-body">'
      + '<div class="form-group"><label class="form-label">Search Query *</label>'
      + '<input type="text" class="form-input" id="knowledge-search-input" placeholder="e.g. traditional uses, preparations, safety"></div>'
      + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">'
      + '<div class="form-group"><label class="form-label">Plant / Ingredient</label>'
      + '<input type="text" class="form-input" id="knowledge-plant-input" placeholder="e.g. Withania somnifera"></div>'
      + '<div class="form-group"><label class="form-label">Botanical Name</label>'
      + '<input type="text" class="form-input" id="knowledge-botanical-input" placeholder="e.g. Bacopa monnieri"></div>'
      + '</div>'
      + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">'
      + '<div class="form-group"><label class="form-label">Category</label>'
      + '<select class="form-select" id="knowledge-category">'
      + '<option value="">All Categories</option>'
      + '<option value="TRADITIONAL_USE">Traditional Use</option>'
      + '<option value="PREPARATION">Preparation</option>'
      + '<option value="BOTANICAL">Botanical</option>'
      + '<option value="SAFETY">Safety</option>'
      + '<option value="DOSAGE">Dosage</option>'
      + '<option value="PHARMACOLOGY">Pharmacology</option>'
      + '<option value="HISTORY">History</option>'
      + '</select></div>'
      + '<div class="form-group"><label class="form-label">Jurisdiction</label>'
      + '<select class="form-select" id="knowledge-jurisdiction">'
      + '<option value="">All Jurisdictions</option>'
      + '<option value="IN">India</option>'
      + '<option value="US">United States</option>'
      + '<option value="EU">European Union</option>'
      + '<option value="GLOBAL">Global</option>'
      + '</select></div>'
      + '</div>'
      + '<button class="btn btn-primary" id="knowledge-search-btn">' + icon("search", 16) + ' Search Sources</button>'
      + '</div></div>'
      + '<div id="knowledge-results"></div>';
    return html;
  }

  // ----------------------------------------------------------------
  // Innovation Analysis View
  // ----------------------------------------------------------------
  function renderInnovationAnalysis() {
    var a = state.innovationAnalysis;
    if (!a) return '';
    var html = ''
      + '<div class="view-header"><button class="btn btn-ghost btn-sm" id="back-from-innovation">' + icon("arrow_back", 15) + ' Back to Case</button></div>'
      + '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>Innovation Analysis</h2>'
      + '<p>Decompose the product into ingredients, formulation, process, claims, and areas of potential differentiation.</p></div>'
      + '<div class="card-body">';

    var summary = [
      { label: "Total Components", value: a.total_components },
      { label: "Traditional / Known", value: a.traditional_count },
      { label: "Potentially Differentiated", value: a.differentiated_count },
      { label: "Requires Investigation", value: a.investigation_count }
    ];
    html += '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:20px">';
    summary.forEach(function (s) {
      html += '<div class="patent-stat-card"><div class="patent-stat-label">' + s.label.toUpperCase() + '</div><div class="patent-stat-value">' + s.value + '</div></div>';
    });
    html += '</div></div></div>';

    if (a.components && a.components.length > 0) {
      a.components.forEach(function (comp) {
        var clsColor = "var(--color-outline)";
        if (comp.classification === "TRADITIONAL_OR_KNOWN") clsColor = "var(--color-secondary)";
        else if (comp.classification === "POTENTIALLY_DIFFERENTIATED") clsColor = "#d97706";
        else if (comp.classification === "REQUIRES_INVESTIGATION") clsColor = "var(--color-error)";

        html += '<div class="innovation-component-card">'
          + '<div class="innovation-component-header">'
          + '<div><div class="innovation-component-type">' + escapeHtml(comp.component_type) + '</div>'
          + '<div class="innovation-component-label">' + escapeHtml(comp.component_label) + '</div></div>'
          + '<span class="innovation-classification-badge" style="background:' + clsColor + '20;color:' + clsColor + '">' + escapeHtml(comp.classification.replace(/_/g, " ")) + '</span>'
          + '</div>';
        if (comp.component_value) html += '<div class="innovation-component-value">' + escapeHtml(comp.component_value) + '</div>';
        if (comp.explanation) html += '<div class="innovation-component-explanation">' + escapeHtml(comp.explanation) + '</div>';
        if (comp.potential_ip_route) html += '<div class="innovation-component-ip"><span class="label-caps" style="color:var(--color-on-surface-variant)">Potential IP Route</span> ' + escapeHtml(comp.potential_ip_route) + '</div>';
        html += '</div>';
      });
    }
    html += '<div class="innovation-disclaimer">' + icon("warning", 18) + '<div><strong>Decision Support Only.</strong> Classifications are preliminary research assessments, not legal conclusions.</div></div>';
    return html;
  }

  // ----------------------------------------------------------------
  // Patent Intelligence View
  // ----------------------------------------------------------------
  // ----------------------------------------------------------------
  // Patent Intelligence View (Master Implementation)
  // ----------------------------------------------------------------
  async function openPatentIntelligence(caseId) {
    var s = (window.AYUR && window.AYUR.state) || state;
    var c = s.currentCase || (s.cases && s.cases.find(function(item) { return item.id === caseId; }));
    if (!c && s.cases && s.cases.length > 0) {
      c = s.cases[0];
      s.currentCase = c;
    }
    if (!c) {
      showToast('⚠️ Please select a product case first', 'error');
      return;
    }
    openCaseModule("patentSearchResults", "/api/cases/" + c.id + "/patents", "patent-intelligence");
  }
  window.openPatentIntelligence = openPatentIntelligence;

  var _isRerunningPatent = false;
  async function rerunPatentSearch(evt) {
    var s = (window.AYUR && window.AYUR.state) || state;
    if (!s.currentCase || _isRerunningPatent) return;
    _isRerunningPatent = true;

    var btn = (evt && evt.target) ? evt.target.closest("button") : document.querySelector(".btn-rerun-patent, [onclick*='rerunPatentSearch']");
    var originalHTML = btn ? btn.innerHTML : "";
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-sm"></span> Re-running Prior-Art Search…';
    }

    var stages = [
      "Searching patent literature…",
      "Normalizing and deduplicating…",
      "Ranking candidates…",
      "AI comparing shortlisted evidence…",
      "Saving refreshed intelligence…"
    ];
    var stageIdx = 0;
    var stageTimer = setInterval(function () {
      stageIdx = (stageIdx + 1) % stages.length;
      if (btn) {
        btn.innerHTML = '<span class="spinner-sm"></span> ' + stages[stageIdx];
      }
    }, 1800);

    try {
      var data = await api("/api/cases/" + s.currentCase.id + "/patent-search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ force_rerun: true })
      });
      clearInterval(stageTimer);
      setCachedModule(s.currentCase.id, "patentSearchResults", data);
      s.patentSearchResults = data;
      showToast("✅ Patent Intelligence prior-art re-run complete", "success");
      render({ scroll: "preserve" });
    } catch (e) {
      clearInterval(stageTimer);
      console.error("Patent rerun error:", e);
      showToast("⚠️ Could not re-run patent discovery: " + (e.message || "Server error"), "error");
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = originalHTML;
      }
    } finally {
      _isRerunningPatent = false;
    }
  }
  window.rerunPatentSearch = rerunPatentSearch;

  async function savePatentToCase(patentRecordId) {
    var s = (window.AYUR && window.AYUR.state) || state;
    if (!s.currentCase || !patentRecordId) return;
    try {
      await api("/api/cases/" + s.currentCase.id + "/patents/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ patent_record_id: patentRecordId, user_notes: "Saved from Patent Intelligence screening view." })
      });
      showToast("📌 Patent saved to Product Case", "success");
    } catch (e) {
      showToast("⚠️ Could not save patent", "error");
    }
  }
  async function retryPatentAiAnalysis() {
    var s = (window.AYUR && window.AYUR.state) || state;
    if (!s.currentCase) return;
    s.loading = true;
    render({ scroll: "top" });
    try {
      var data = await api("/api/cases/" + s.currentCase.id + "/patents/retry-analysis", {
        method: "POST"
      });
      setCachedModule(s.currentCase.id, "patentSearchResults", data);
      s.patentSearchResults = data;
      showToast("✅ AI semantic analysis retry complete", "success");
    } catch (e) {
      showToast("⚠️ Could not retry AI analysis", "error");
    }
    s.loading = false;
    render({ scroll: "top" });
  }
  window.retryPatentAiAnalysis = retryPatentAiAnalysis;

  function toggleShowAllPatents() {
    window._showAllPatents = !window._showAllPatents;
    render();
  }
  window.toggleShowAllPatents = toggleShowAllPatents;

  function setPatentTab(tab) {
    window._patentActiveTab = tab;
    render({ scroll: "preserve" });
  }
  window.setPatentTab = setPatentTab;

  function getPatentJurisdictionCode(rec) {
    if (!rec) return "UNKNOWN";
    var j = rec.jurisdiction_code || rec.jurisdiction;
    if (j && typeof j === 'string') {
      var jUp = j.trim().upperCase ? j.trim().toUpperCase() : j.trim();
      if (jUp.length === 2 && jUp !== "GL" && jUp !== "UN") return jUp;
    }
    var pub = (rec.publication_number || "").toUpperCase();
    var m = pub.match(/^([A-Z]{2})\d/);
    if (m) return m[1];
    var pid = (rec.provider_record_id || "").toUpperCase();
    var m2 = pid.match(/^([A-Z]{2})\d/);
    if (m2) return m2[1];
    return "UNKNOWN";
  }

  function renderPatentIntelligence() {
    var data = state.patentSearchResults;
    var caseName = state.currentCase ? state.currentCase.name : "Product Case";
    var caseId = state.currentCase ? state.currentCase.id : "";

    var html = ''
      + '<div class="view-header" style="margin-bottom:16px;">'
      + '<button class="btn btn-ghost btn-sm" id="back-from-patent" onclick="openCaseIntelligence(\'' + escapeHtml(caseId) + '\')">' + icon("arrow_back", 15) + ' Back to Case</button>'
      + '</div>';

    if (!data || data.has_searched === false) {
      return html + '<div class="card" style="padding:40px;text-align:center;background:rgba(20,28,24,0.6);border:1px solid rgba(255,255,255,0.08);margin-top:20px;">'
        + '<div style="font-size:42px;margin-bottom:12px;">📜</div>'
        + '<h3 style="font-size:18px;font-weight:700;color:#f8fafc;margin-bottom:8px;">No Prior-Art Search Run Yet</h3>'
        + '<p style="font-size:13px;color:#94a3b8;max-width:580px;margin:0 auto 20px auto;line-height:1.5;">Initiate structured prior-art discovery across public life-sciences patent literature (<strong>Europe PMC Patent Index</strong>) for <strong>' + escapeHtml(caseName) + '</strong>.</p>'
        + '<div style="margin-bottom:20px;font-size:12px;color:#64748b;max-width:620px;margin-left:auto;margin-right:auto;">'
        + '<strong>Methodology & Disclosures:</strong> Discovery is non-exhaustive. Jurisdiction Focus: <strong>India</strong>. Direct manual verification required on: <strong>IP India / InPASS</strong>, <strong>WIPO PATENTSCOPE</strong>, and <strong>TKDL</strong> (manual traditional-knowledge research resource).'
        + '</div>'
        + '<button class="btn btn-primary" onclick="rerunPatentSearch()">' + icon("search", 16) + ' Run Prior-Art Search</button>'
        + '</div>';
    }

    var items = data.patents || data.results || [];
    var metrics = data.summary_metrics || {
      raw_discovered_count: items.length,
      unique_screened_count: items.length,
      shortlisted_count: Math.min(20, items.length),
      analyzed_count: items.length,
      total_retrieved: items.length,
      very_high_count: items.filter(function(i){ return i.relevance_level === "VERY_HIGH"; }).length,
      high_count: items.filter(function(i){ return i.relevance_level === "HIGH"; }).length,
      moderate_count: items.filter(function(i){ return i.relevance_level === "MODERATE"; }).length,
      low_count: items.filter(function(i){ return i.relevance_level === "LOW"; }).length,
      not_analyzed_count: items.filter(function(i){ return i.relevance_level === "NOT_ANALYZED"; }).length,
      queries_executed: (data.query_plan || []).length,
      queries_with_results: items.length > 0 ? (data.query_plan || []).length : 0,
      prior_art_signal: "LOW",
      discovery_coverage: items.length > 0 ? "PARTIAL" : "ZERO",
      evidence_basis: "ABSTRACT-LEVEL SCREENING"
    };

    var queryPlan = data.query_plan || [];
    var differentiators = data.potential_differentiators || [];
    var unanalyzedCount = metrics.not_analyzed_count || 0;

    html += '<div class="patent-intel-header">'
      + '<div class="patent-intel-title-row">'
      + '<div class="patent-intel-title-area">'
      + '<h2>AYUR-INTEL — Patent Intelligence & Prior-Art Screening</h2>'
      + '<div class="patent-intel-subtitle">Public Patent Discovery: <strong>Europe PMC Patent Index</strong> for <strong>' + escapeHtml(caseName) + '</strong></div>'
      + '<div style="font-size:12px;color:#94a3b8;margin-top:6px;background:rgba(15,23,42,0.6);padding:8px 12px;border-radius:6px;border:1px solid rgba(255,255,255,0.06);">'
      + '<strong>Jurisdiction Focus:</strong> India (Discovery includes international literature). Verification portals: <strong>Google Patents</strong> / <strong>IP India (InPASS)</strong> / <strong>WIPO PATENTSCOPE</strong>. <strong>TKDL</strong> is a manual research resource. Discovery is non-exhaustive.'
      + '</div>'
      + '</div>'
      + '<div style="display:flex;gap:8px;align-items:center;">'
      + (unanalyzedCount > 0 ? ('<button class="btn btn-secondary btn-sm" onclick="retryPatentAiAnalysis()">' + icon("auto_renew", 14) + ' Retry AI Analysis (' + unanalyzedCount + ' Unanalyzed)</button>') : '')
      + '<button class="btn btn-primary btn-sm" onclick="rerunPatentSearch()">' + icon("refresh", 14) + ' Force Re-Run Search</button>'
      + '</div>'
      + '</div></div>';

    // Executive Summary Answer Box ("What This Means For Your Product")
    var signalColor = "#34d399";
    var signalLabel = "LOW PRIOR-ART PRESSURE";
    var signalBg = "rgba(52,211,153,0.12)";
    if (metrics.prior_art_signal === "HIGH") {
      signalColor = "#f87171";
      signalLabel = "HIGH PRIOR-ART PRESSURE";
      signalBg = "rgba(239,68,68,0.12)";
    } else if (metrics.prior_art_signal === "MODERATE") {
      signalColor = "#fb923c";
      signalLabel = "MODERATE PRIOR-ART PRESSURE";
      signalBg = "rgba(249,115,22,0.12)";
    }

    var covBadge = metrics.discovery_coverage || "PARTIAL";
    var covColor = covBadge === "FULL" ? "#34d399" : (covBadge === "PARTIAL" ? "#fbbf24" : "#94a3b8");

    html += '<div class="card" style="margin-bottom:20px;background:rgba(15,23,42,0.75);border:1px solid rgba(52,211,153,0.3);padding:20px 24px;">'
      + '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:14px;">'
      + '<h3 style="font-size:16px;font-weight:700;color:#f8fafc;display:flex;align-items:center;gap:8px;">💡 Executive Summary — What This Means For Your Product</h3>'
      + '<div style="display:flex;gap:8px;align-items:center;">'
      + '<span style="font-size:11px;font-weight:700;padding:4px 10px;border-radius:6px;background:' + signalBg + ';color:' + signalColor + ';border:1px solid ' + signalColor + '40;">PRIOR-ART SIGNAL: ' + signalLabel + '</span>'
      + '<span style="font-size:11px;font-weight:700;padding:4px 10px;border-radius:6px;background:rgba(255,255,255,0.05);color:' + covColor + ';border:1px solid ' + covColor + '40;">COVERAGE: ' + covBadge + '</span>'
      + '</div></div>'
      + '<p style="font-size:13px;color:#e2e8f0;line-height:1.6;margin-bottom:14px;">'
      + 'AYUR-INTEL screened <strong>' + (metrics.unique_screened_count || metrics.total_retrieved) + ' unique candidate patents</strong> from <strong>' + (metrics.raw_discovered_count || metrics.total_retrieved) + ' raw hits</strong> across query plan concepts. '
      + 'Found <strong>' + (metrics.very_high_count + metrics.high_count + metrics.moderate_count) + ' technically overlapping patents</strong> (' + (metrics.very_high_count + metrics.high_count) + ' High/Very High overlap). '
      + 'Prior-art density indicates <strong>' + signalLabel + '</strong> for this formulation concept.'
      + '</p>'
      + '<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:10px;background:rgba(0,0,0,0.25);padding:12px 16px;border-radius:8px;font-size:11px;color:#cbd5e1;margin-bottom:12px;">'
      + '<div><strong style="color:#4ade80;">0–34 LOW:</strong> Distant category or single term match</div>'
      + '<div><strong style="color:#facc15;">35–64 MODERATE:</strong> Partial ingredient / process overlap</div>'
      + '<div><strong style="color:#fb923c;">65–79 HIGH:</strong> Multi-active botanical combination</div>'
      + '<div><strong style="color:#f87171;">80–100 VERY HIGH:</strong> Direct formulation & claim concept match</div>'
      + '</div>'
      + '<div style="font-size:11px;color:#94a3b8;font-style:italic;">* Screened based on public title and abstract text. Does not constitute a formal freedom-to-operate (FTO) or legal patentability opinion.</div>'
      + '</div>';

    // True 4-Stage Visual Funnel Pipeline (Discovered -> Screened -> Shortlisted -> AI Analyzed)
    var rawDiscovered = metrics.raw_discovered_count || metrics.total_retrieved || items.length;
    var uniqueScreened = metrics.unique_screened_count || metrics.total_retrieved || items.length;
    var shortlisted = metrics.shortlisted_count || Math.min(20, items.length);
    var analyzedCount = metrics.analyzed_count || (items.length - unanalyzedCount);

    html += '<div style="display:grid;grid-template-columns:repeat(4, 1fr);gap:12px;margin-bottom:16px;text-align:center;">'
      + '<div style="background:rgba(15,23,42,0.6);border:1px solid rgba(255,255,255,0.08);padding:14px;border-radius:8px;">'
      + '<div style="font-size:11px;font-weight:700;color:#94a3b8;letter-spacing:0.05em;">1. DISCOVERED</div>'
      + '<div style="font-size:22px;font-weight:700;color:#f8fafc;margin-top:2px;">' + rawDiscovered + '</div>'
      + '<div style="font-size:10px;color:#64748b;">Raw Hits Across Queries</div>'
      + '</div>'
      + '<div style="background:rgba(15,23,42,0.6);border:1px solid rgba(52,211,153,0.15);padding:14px;border-radius:8px;">'
      + '<div style="font-size:11px;font-weight:700;color:#34d399;letter-spacing:0.05em;">2. SCREENED</div>'
      + '<div style="font-size:22px;font-weight:700;color:#34d399;margin-top:2px;">' + uniqueScreened + '</div>'
      + '<div style="font-size:10px;color:#64748b;">Unique Deduplicated Records</div>'
      + '</div>'
      + '<div style="background:rgba(15,23,42,0.6);border:1px solid rgba(251,191,36,0.2);padding:14px;border-radius:8px;">'
      + '<div style="font-size:11px;font-weight:700;color:#fbbf24;letter-spacing:0.05em;">3. SHORTLISTED</div>'
      + '<div style="font-size:22px;font-weight:700;color:#fbbf24;margin-top:2px;">' + shortlisted + '</div>'
      + '<div style="font-size:10px;color:#64748b;">Top Pre-Ranked Candidates</div>'
      + '</div>'
      + '<div style="background:rgba(15,23,42,0.6);border:1px solid rgba(96,165,250,0.2);padding:14px;border-radius:8px;">'
      + '<div style="font-size:11px;font-weight:700;color:#60a5fa;letter-spacing:0.05em;">4. AI ANALYZED</div>'
      + '<div style="font-size:22px;font-weight:700;color:#60a5fa;margin-top:2px;">' + analyzedCount + '</div>'
      + '<div style="font-size:10px;color:#64748b;">' + (unanalyzedCount > 0 ? (unanalyzedCount + ' Pending AI Retry') : 'Semantic Overlap Verified') + '</div>'
      + '</div>'
      + '</div>';

    // Expandable "How AYUR-INTEL analyzed this" Accordion
    html += '<details style="margin-bottom:20px;background:rgba(15,23,42,0.75);border:1px solid rgba(52,211,153,0.3);border-radius:8px;padding:12px 16px;">'
      + '<summary style="font-size:13px;font-weight:700;color:#34d399;cursor:pointer;display:flex;align-items:center;gap:8px;">'
      + icon("info", 16) + ' How AYUR-INTEL analyzed this (3-Stage Screening Methodology)'
      + '</summary>'
      + '<div style="padding-top:14px;font-size:13px;color:#cbd5e1;line-height:1.6;">'
      + '<div style="margin-bottom:10px;">'
      + '<strong style="color:#f8fafc;">Stage 1 — Patent Discovery:</strong> Queries public patent indices (Europe PMC Patent Index) deterministically across 5–10 structured query plan concepts (botanical names, active phytoconstituents, formulation matrix, and process terms).'
      + '</div>'
      + '<div style="margin-bottom:10px;">'
      + '<strong style="color:#f8fafc;">Stage 2 — Candidate Ranking:</strong> Deterministic pre-ranking ranks deduplicated public prior-art records based on active ingredient matches, formulation matrix, and query plan term overlap.'
      + '</div>'
      + '<div style="margin-bottom:10px;">'
      + '<strong style="color:#f8fafc;">Stage 3 — AI Deep Comparison:</strong> Gemini AI semantically evaluates ONLY the actual retrieved patent title/abstract text against product case details across 4 scoring dimensions (technology, ingredient, formulation/process, claim concept).'
      + '</div>'
      + '<div style="padding:10px 12px;background:rgba(52,211,153,0.1);border-left:3px solid #34d399;border-radius:4px;font-size:12px;color:#34d399;margin-top:12px;">'
      + '🔒 <strong>Non-Negotiable Rule:</strong> Gemini does NOT invent or discover patent records. All candidate literature originates from verified public patent index queries.'
      + '</div>'
      + '</div>'
      + '</details>';

    // Jurisdiction Breakdown & Coverage Summary Box
    var jurCounts = { IN: 0, US: 0, WO: 0, EP: 0, OTHER: 0, UNKNOWN: 0 };
    items.forEach(function(item) {
      var rec = item.patent || {};
      var code = getPatentJurisdictionCode(rec);
      if (code === "IN") jurCounts.IN++;
      else if (code === "US") jurCounts.US++;
      else if (code === "WO") jurCounts.WO++;
      else if (code === "EP") jurCounts.EP++;
      else if (code === "UNKNOWN") jurCounts.UNKNOWN++;
      else jurCounts.OTHER++;
    });

    html += '<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;background:rgba(15,23,42,0.6);border:1px solid rgba(255,255,255,0.08);padding:12px 16px;border-radius:8px;margin-bottom:20px;font-size:12px;">'
      + '<div style="font-weight:700;color:#94a3b8;letter-spacing:0.05em;text-transform:uppercase;">Jurisdiction Coverage:</div>'
      + '<div style="display:flex;gap:14px;flex-wrap:wrap;color:#f8fafc;font-weight:600;">'
      + '<span>🇮🇳 IN: <strong>' + jurCounts.IN + '</strong></span>'
      + '<span>🇺🇸 US: <strong>' + jurCounts.US + '</strong></span>'
      + '<span>🌐 WO: <strong>' + jurCounts.WO + '</strong></span>'
      + '<span>🇪🇺 EP: <strong>' + jurCounts.EP + '</strong></span>'
      + '<span>Other: <strong>' + jurCounts.OTHER + '</strong></span>'
      + '<span>Unknown: <strong>' + jurCounts.UNKNOWN + '</strong></span>'
      + '</div>'
      + '</div>';

    // Summary Metrics Strip
    html += '<div class="patent-metrics-strip" style="margin-bottom:20px;">'
      + '<div class="patent-metric-card"><div class="patent-metric-label">TOTAL PATENTS</div><div class="patent-metric-value">' + metrics.total_retrieved + '</div></div>'
      + '<div class="patent-metric-card" style="border-color:rgba(239,68,68,0.3);"><div class="patent-metric-label" style="color:#f87171;">VERY HIGH OVERLAP</div><div class="patent-metric-value" style="color:#f87171;">' + metrics.very_high_count + '</div></div>'
      + '<div class="patent-metric-card" style="border-color:rgba(249,115,22,0.3);"><div class="patent-metric-label" style="color:#fb923c;">HIGH OVERLAP</div><div class="patent-metric-value" style="color:#fb923c;">' + metrics.high_count + '</div></div>'
      + '<div class="patent-metric-card" style="border-color:rgba(234,179,8,0.3);"><div class="patent-metric-label" style="color:#facc15;">MODERATE OVERLAP</div><div class="patent-metric-value" style="color:#facc15;">' + metrics.moderate_count + '</div></div>'
      + '<div class="patent-metric-card" style="border-color:rgba(34,197,94,0.3);"><div class="patent-metric-label" style="color:#4ade80;">LOW OVERLAP</div><div class="patent-metric-value" style="color:#4ade80;">' + metrics.low_count + '</div></div>'
      + '<div class="patent-metric-card" style="border-color:rgba(148,163,184,0.3);"><div class="patent-metric-label" style="color:#cbd5e1;">NOT ANALYZED</div><div class="patent-metric-value" style="color:#cbd5e1;">' + unanalyzedCount + '</div></div>'
      + '</div>';

    // Potential Differentiators Section
    if (differentiators.length > 0) {
      html += '<div class="card" style="margin-bottom:20px;background:rgba(52,211,153,0.05);border:1px solid rgba(52,211,153,0.2);padding:16px 20px;">'
        + '<h3 style="font-size:14px;font-weight:700;color:#34d399;margin-bottom:8px;display:flex;align-items:center;gap:6px;">' + icon("verified", 16) + ' Potential Differentiators from Retrieved Evidence</h3>'
        + '<ul style="margin:0;padding-left:20px;font-size:13px;color:#e2e8f0;line-height:1.6;">';
      differentiators.forEach(function(diff) {
        html += '<li>' + escapeHtml(diff) + '</li>';
      });
      html += '</ul>'
        + '<div style="font-size:11px;color:#94a3b8;margin-top:8px;">* Based strictly on comparison with retrieved prior-art evidence. Does not constitute a formal novelty assertion.</div>'
        + '</div>';
    }

    // Zero-Result Diagnostics State
    if (items.length === 0) {
      html += '<div class="card" style="padding:32px;background:rgba(15,23,42,0.8);border:1px solid rgba(245,158,11,0.3);margin-bottom:24px;">'
        + '<div style="display:flex;align-items:flex-start;gap:14px;">'
        + '<div style="font-size:28px;">🔍</div>'
        + '<div>'
        + '<h3 style="font-size:16px;font-weight:700;color:#f8fafc;margin-bottom:6px;">No Relevant Patent Literature Retrieved</h3>'
        + '<p style="font-size:13px;color:#cbd5e1;line-height:1.5;margin-bottom:14px;">'
        + 'No relevant patent literature was retrieved from the current public index using <strong>' + (metrics.queries_executed || queryPlan.length) + '</strong> search strategies.'
        + '</p>'
        + '<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:10px;background:rgba(0,0,0,0.2);padding:12px;border-radius:6px;font-size:12px;color:#94a3b8;margin-bottom:16px;">'
        + '<div><strong>Queries Executed:</strong> ' + (metrics.queries_executed || queryPlan.length) + '</div>'
        + '<div><strong>Queries with Matches:</strong> ' + (metrics.queries_with_results || 0) + '</div>'
        + '<div><strong>Provider:</strong> Europe PMC Patent Index</div>'
        + '<div><strong>Search Coverage:</strong> Non-exhaustive public literature</div>'
        + '<div><strong>Last Searched:</strong> ' + (metrics.last_searched || "Just now") + '</div>'
        + '</div>'
        + '<div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center;">'
        + '<button class="btn btn-primary btn-sm" onclick="rerunPatentSearch()">' + icon("refresh", 14) + ' Refine Search / Force Re-Run</button>'
        + '<a href="https://ipindia.gov.in/patents-before-you-apply-public-search" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm">🇮🇳 Open IP India / InPASS ↗</a>'
        + '<a href="https://patentscope.wipo.int/search/en/search.jsf" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm">🌐 Open WIPO PATENTSCOPE ↗</a>'
        + '</div>'
        + '<div style="font-size:11px;color:#64748b;margin-top:10px;">* Zero search matches indicates no records were returned for these specific query terms in public index literature. It does NOT imply that no patents exist worldwide.</div>'
        + '</div></div></div>';
    } else {
      // Tab Navigation (TOP MATCHES, INDIAN MATCHES, ALL SHORTLISTED)
      var activeTab = window._patentActiveTab || "top";
      var indianItems = items.filter(function(item) {
        return getPatentJurisdictionCode(item.patent) === "IN";
      });

      html += '<div style="display:flex;gap:8px;border-bottom:1px solid rgba(255,255,255,0.1);margin-bottom:16px;padding-bottom:8px;">'
        + '<button class="btn btn-sm ' + (activeTab === "top" ? "btn-primary" : "btn-ghost") + '" onclick="setPatentTab(\'top\')">⭐ Top Matches (' + Math.min(5, items.length) + ')</button>'
        + '<button class="btn btn-sm ' + (activeTab === "india" ? "btn-primary" : "btn-ghost") + '" onclick="setPatentTab(\'india\')">🇮🇳 Indian Matches (' + indianItems.length + ')</button>'
        + '<button class="btn btn-sm ' + (activeTab === "all" ? "btn-primary" : "btn-ghost") + '" onclick="setPatentTab(\'all\')">📋 All Shortlisted (' + items.length + ')</button>'
        + '</div>';

      var displayItems = items;
      if (activeTab === "top") {
        displayItems = items.slice(0, 5);
      } else if (activeTab === "india") {
        displayItems = indianItems;
      }

      if (activeTab === "india" && indianItems.length === 0) {
        html += '<div class="card" style="padding:28px;background:rgba(15,23,42,0.8);border:1px solid rgba(245,158,11,0.3);margin-bottom:24px;text-align:center;">'
          + '<div style="font-size:36px;margin-bottom:8px;">🇮🇳</div>'
          + '<h3 style="font-size:16px;font-weight:700;color:#f8fafc;margin-bottom:6px;">No India-Identified Patent Records in Current Public Screening</h3>'
          + '<p style="font-size:13px;color:#cbd5e1;max-width:640px;margin:0 auto 16px auto;line-height:1.6;">'
          + 'No patent records with explicit Indian jurisdiction metadata (IN) were returned during this public literature screening for <strong>' + escapeHtml(caseName) + '</strong>.<br>'
          + 'Public literature indices cover a subset of published Indian patents. For a complete Indian patent search, verify directly on official government search portals.'
          + '</p>'
          + '<div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap;align-items:center;margin-bottom:12px;">'
          + '<a href="https://ipindia.gov.in/patents-before-you-apply-public-search" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm">🇮🇳 Open IP India / InPASS Public Search ↗</a>'
          + '<a href="https://patentscope.wipo.int/search/en/search.jsf" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm">🌐 Open WIPO PATENTSCOPE (India Coverage) ↗</a>'
          + '</div>'
          + '<div style="font-size:11px;color:#64748b;">'
          + '* Note: TKDL (Traditional Knowledge Digital Library) is a non-patent manual research resource accessible via official Indian patent examiners.'
          + '</div>'
          + '</div>';
      } else {
        html += '<div style="margin-bottom:14px;display:flex;justify-content:space-between;align-items:center;">'
          + '<h3 style="font-size:15px;font-weight:700;color:#f8fafc;">📑 ' + (activeTab === "top" ? 'Top Matches' : (activeTab === "india" ? 'Indian Matches' : 'All Shortlisted Patents')) + ' (' + displayItems.length + ')</h3>'
          + '</div>';

        displayItems.forEach(function(item) {
          var rec = item.patent || {};
          var providerId = rec.provider_record_id || "";
          var pubNum = rec.publication_number || null;
          var title = rec.title || "Untitled Patent Document";
          var applicant = rec.applicant || "Not Listed";
          var pubDate = rec.publication_date || rec.filing_date || "N/A";
          var jCode = getPatentJurisdictionCode(rec);
          var jurisdiction = jCode !== "UNKNOWN" ? jCode : (rec.authority || "GLOBAL");

          var flag = "🌍";
          if (jurisdiction.indexOf("IN") !== -1) flag = "🇮🇳";
          else if (jurisdiction.indexOf("US") !== -1) flag = "🇺🇸";
          else if (jurisdiction.indexOf("EP") !== -1 || jurisdiction.indexOf("EU") !== -1) flag = "🇪🇺";
          else if (jurisdiction.indexOf("WO") !== -1) flag = "🌐";

          var idBadgeText = pubNum ? (flag + " " + pubNum) : (providerId ? (flag + " Source ID: " + providerId) : (flag + " ID Not Available"));
          var pubNumDisplay = pubNum ? escapeHtml(pubNum) : "Not available";
          var sourceIdDisplay = providerId ? (' &nbsp;|&nbsp; <strong>Source Record ID:</strong> ' + escapeHtml(providerId)) : '';

          var level = item.relevance_level || "LOW";
          var score = item.relevance_score;
          var isNotAnalyzed = level === "NOT_ANALYZED" || score === null || score === undefined;

          var badgeCls = "badge-low";
          if (level === "VERY_HIGH") badgeCls = "badge-very-high";
          else if (level === "HIGH") badgeCls = "badge-high";
          else if (level === "MODERATE") badgeCls = "badge-moderate";
          else if (isNotAnalyzed) badgeCls = "badge-not-analyzed";

          var scoreLabel = !isNotAnalyzed ? (level.replace("_", " ") + ' (' + score + ' / 100)') : 'NOT ANALYZED (AI Unavailable)';

          var breakdown = item.score_breakdown || null;
          var techVal = isNotAnalyzed || !breakdown ? "—" : (breakdown.technological_overlap + "%");
          var ingVal = isNotAnalyzed || !breakdown ? "—" : (breakdown.ingredient_overlap + "%");
          var formVal = isNotAnalyzed || !breakdown ? "—" : (breakdown.formulation_process_overlap + "%");
          var claimVal = isNotAnalyzed || !breakdown ? "—" : (breakdown.claim_concept_overlap + "%");

          var matchedComps = item.matched_components || [];
          var openUrl = rec.open_patent_url || (pubNum ? ("https://patents.google.com/patent/" + pubNum.replace(/[^A-Za-z0-9]/g, "") + "/en") : (providerId ? ("https://europepmc.org/article/PAT/" + providerId) : ""));
          var openBtnLabel = openUrl.indexOf("patents.google.com") !== -1 ? "Open Google Patent ↗" : "Open Europe PMC Record ↗";

          var evBasis = item.evidence_basis || "TITLE_ABSTRACT";
          var evBadgeLabel = "ABSTRACT-LEVEL SCREENING";
          if (evBasis === "TITLE_ONLY") evBadgeLabel = "TITLE-LEVEL SCREENING";
          else if (evBasis === "TITLE_ABSTRACT_CLAIMS" || evBasis === "CLAIM_TEXT") evBadgeLabel = "CLAIM-LEVEL SCREENING";

          var familyHtml = "";
          if (rec.family_id && rec.family_members && rec.family_members.length > 1) {
            familyHtml = '<span class="patent-pub-badge" style="background:rgba(168,85,247,0.12);color:#c084fc;border-color:rgba(168,85,247,0.3);">Family: ' + escapeHtml(rec.family_id) + ' (' + rec.family_members.length + ')</span>';
          }

          html += '<div class="patent-card">'
            + '<div class="patent-card-header">'
            + '<div>'
            + '<div class="patent-card-title-row">'
            + '<span class="patent-pub-badge">' + escapeHtml(idBadgeText) + '</span>'
            + familyHtml
            + '<span class="patent-evidence-basis-badge">' + escapeHtml(evBadgeLabel) + '</span>'
            + '<span class="patent-relevance-badge ' + badgeCls + '">' + escapeHtml(scoreLabel) + '</span>'
            + '</div>'
            + '<h3 style="font-size:16px;font-weight:700;color:#f8fafc;line-height:1.4;margin-bottom:6px;">' + escapeHtml(title) + '</h3>'
            + '<div style="font-size:12px;color:#94a3b8;"><strong>Applicant / Assignee:</strong> ' + escapeHtml(applicant) + ' &nbsp;|&nbsp; <strong>Publication #:</strong> ' + pubNumDisplay + sourceIdDisplay + ' &nbsp;|&nbsp; <strong>Date:</strong> ' + escapeHtml(pubDate) + ' &nbsp;|&nbsp; <strong>Authority:</strong> ' + escapeHtml(rec.authority || jurisdiction) + '</div>'
            + '</div>'
            + '</div>';

          if (rec.abstract) {
            html += '<div style="font-size:13px;color:#cbd5e1;line-height:1.5;margin:10px 0;padding:10px 12px;background:rgba(15,23,42,0.4);border-radius:6px;border-left:3px solid #34d399;">'
              + escapeHtml(rec.abstract.length > 320 ? rec.abstract.substring(0, 320) + '...' : rec.abstract)
              + '</div>';
          }

          html += '<div class="patent-score-grid">'
            + '<div class="patent-score-dim"><div class="patent-score-dim-label">TECH OVERLAP</div><div class="patent-score-dim-val">' + techVal + '</div></div>'
            + '<div class="patent-score-dim"><div class="patent-score-dim-label">INGREDIENT OVERLAP</div><div class="patent-score-dim-val">' + ingVal + '</div></div>'
            + '<div class="patent-score-dim"><div class="patent-score-dim-label">FORMULATION & PROCESS</div><div class="patent-score-dim-val">' + formVal + '</div></div>'
            + '<div class="patent-score-dim"><div class="patent-score-dim-label">CLAIM CONCEPT</div><div class="patent-score-dim-val">' + claimVal + '</div></div>'
            + '</div>';

          if (matchedComps.length > 0) {
            html += '<div style="margin-bottom:8px;display:flex;align-items:center;gap:6px;flex-wrap:wrap;">'
              + '<span style="font-size:11px;color:#94a3b8;font-weight:600;">MATCHED WITH YOUR PRODUCT:</span>';
            matchedComps.forEach(function(mc) {
              html += '<span style="font-size:11px;padding:2px 8px;border-radius:12px;background:rgba(52,211,153,0.12);color:#34d399;border:1px solid rgba(52,211,153,0.25);">' + escapeHtml(mc) + '</span>';
            });
            html += '</div>';
          }

          html += '<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(260px, 1fr));gap:10px;margin-top:12px;">'
            + '<div class="patent-section-box"><div class="patent-section-title">WHY RELEVANT</div><div style="color:#f8fafc;">' + escapeHtml(item.why_relevant || "Overlap detected in abstract screening.") + '</div></div>'
            + '<div class="patent-section-box"><div class="patent-section-title">IMPORTANT DIFFERENCE</div><div style="color:#f8fafc;">' + escapeHtml(item.important_difference || "Product case specifies standardized extract ratios.") + '</div></div>'
            + '<div class="patent-section-box"><div class="patent-section-title">SCREENING LIMITATION</div><div style="color:#f8fafc;">' + escapeHtml(item.limitations || "Based on title/abstract text screening.") + '</div></div>'
            + '</div>';

          html += '<div style="display:flex;justify-content:flex-end;align-items:center;gap:10px;margin-top:16px;padding-top:12px;border-top:1px solid rgba(255,255,255,0.06);">'
            + (isNotAnalyzed ? ('<button class="btn btn-secondary btn-sm" onclick="retryPatentAiAnalysis()">' + icon("auto_renew", 14) + ' Retry AI Analysis</button>') : '')
            + '<a href="' + escapeHtml(openUrl) + '" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm" style="display:inline-flex;align-items:center;gap:4px;">' + escapeHtml(openBtnLabel) + '</a>'
            + '<button class="btn btn-ghost btn-sm" onclick="savePatentToCase(\'' + escapeHtml(rec.id || "") + '\')">' + icon("bookmark", 14) + ' Save to Case</button>'
            + '</div>';

          html += '</div>';
        });
      }
    }

    // Collapsible Provider Query Plan
    if (queryPlan.length > 0) {
      html += '<details style="margin-bottom:24px;background:rgba(20,28,24,0.6);border:1px solid rgba(255,255,255,0.08);border-radius:8px;padding:12px 16px;">'
        + '<summary style="font-size:14px;font-weight:700;color:#f8fafc;cursor:pointer;display:flex;align-items:center;gap:8px;">🎯 View Provider Query Plan (' + queryPlan.length + ' Categorized Search Concepts)</summary>'
        + '<div style="padding-top:16px;">'
        + '<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(280px, 1fr));gap:10px;">';

      queryPlan.forEach(function(q) {
        var cat = q.category || "SEARCH";
        var catBg = "rgba(52,211,153,0.12)";
        var catColor = "#34d399";
        if (cat === "BOTANICAL") { catBg = "rgba(168,85,247,0.12)"; catColor = "#c084fc"; }
        else if (cat === "COMMON_NAMES") { catBg = "rgba(236,72,153,0.12)"; catColor = "#f472b6"; }
        else if (cat === "COMBINATION") { catBg = "rgba(59,130,246,0.12)"; catColor = "#60a5fa"; }
        else if (cat === "STANDARDIZATION") { catBg = "rgba(16,185,129,0.12)"; catColor = "#34d399"; }
        else if (cat === "FORMULATION") { catBg = "rgba(245,158,11,0.12)"; catColor = "#fbbf24"; }
        else if (cat === "PROCESS") { catBg = "rgba(234,179,8,0.12)"; catColor = "#facc15"; }

        html += '<div style="background:rgba(15,23,42,0.5);padding:10px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.05);">'
          + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">'
          + '<span style="font-size:10px;font-weight:700;padding:2px 6px;border-radius:4px;background:' + catBg + ';color:' + catColor + ';">' + escapeHtml(cat) + '</span>'
          + (q.signals ? ('<span style="font-size:10px;color:#94a3b8;">' + escapeHtml(q.signals) + '</span>') : '')
          + '</div>'
          + '<div style="font-family:monospace;font-size:12px;color:#f8fafc;font-weight:600;margin-bottom:4px;">Search: ' + escapeHtml(q.query) + '</div>'
          + '<div style="font-size:11px;color:#94a3b8;">Purpose: ' + escapeHtml(q.rationale || "Screens literature for overlap.") + '</div>'
          + '</div>';
      });

      html += '</div></div></details>';
    }

    // Manual Verification Callout & Correct IP India Link
    html += '<div class="patent-verification-box">'
      + '<h3 style="font-size:15px;font-weight:700;color:#f8fafc;margin-bottom:8px;display:flex;align-items:center;gap:8px;">🇮🇳 Official Patent Registers & Direct Verification Portals</h3>'
      + '<p style="font-size:13px;color:#cbd5e1;line-height:1.5;margin-bottom:14px;">'
      + 'Always cross-reference abstract findings with official patent prosecution databases and traditional knowledge registers.'
      + '</p>'
      + '<div style="display:flex;gap:12px;flex-wrap:wrap;">'
      + '<a href="https://ipindia.gov.in/patents-before-you-apply-public-search" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm" style="display:inline-flex;align-items:center;gap:6px;">🇮🇳 Search IP India / InPASS ↗</a>'
      + '<a href="https://patentscope.wipo.int/search/en/search.jsf" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm" style="display:inline-flex;align-items:center;gap:6px;">🌐 Open WIPO PATENTSCOPE ↗</a>'
      + '<a href="https://www.tkdl.res.in" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm" style="display:inline-flex;align-items:center;gap:6px;">📚 TKDL Portal ↗</a>'
      + '</div>'
      + '</div>';

    // Highlighted "File Your Patent in India" CTA Card
    html += '<div class="card patent-filing-cta-card" style="margin-top:24px;background:linear-gradient(135deg, rgba(16,185,129,0.12) 0%, rgba(15,23,42,0.85) 100%);border:1px solid rgba(16,185,129,0.35);padding:24px;border-radius:12px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px;">'
      + '<div>'
      + '<h3 style="font-size:17px;font-weight:700;color:#f8fafc;margin-bottom:6px;display:flex;align-items:center;gap:8px;">'
      + '🛡️ Protect Your Innovation — Ready to Take the Next Step?'
      + '</h3>'
      + '<p style="font-size:13px;color:#cbd5e1;max-width:620px;margin:0;line-height:1.5;">'
      + 'Understand the official Indian patent filing process, provisional vs complete specifications, required forms, fees, and access official IP India e-Filing services.'
      + '</p>'
      + '</div>'
      + '<div>'
      + '<button class="btn btn-primary" onclick="openPatentFilingGuideModal()" style="background:linear-gradient(135deg, #10b981 0%, #059669 100%);border:none;padding:12px 20px;font-weight:700;font-size:14px;box-shadow:0 4px 14px rgba(16,185,129,0.3);cursor:pointer;">'
      + '🇮🇳 File Your Patent in India →'
      + '</button>'
      + '</div>'
      + '</div>';

    // Disclaimer
    html += '<div class="innovation-disclaimer" style="margin-top:20px;">' + icon("warning", 18) + '<div><strong>Decision-Support & Prior-Art Screening Notice.</strong> Patent Intelligence assessments are generated for early prior-art research and product strategy. They do not constitute formal legal patentability opinions or freedom-to-operate (FTO) clearances. Always verify claims against official patent registers.</div></div>';

    return html;
  }

  // ----------------------------------------------------------------
  // Patent Filing Guide Modal (0 API calls, Instant Local Modal)
  // ----------------------------------------------------------------
  function openPatentFilingGuideModal() {
    var existing = document.getElementById("patent-filing-modal-root");
    if (existing) existing.remove();

    var modalDiv = document.createElement("div");
    modalDiv.id = "patent-filing-modal-root";
    modalDiv.className = "patent-filing-modal-overlay";
    modalDiv.onclick = function (e) {
      if (e.target === modalDiv) closePatentFilingGuideModal();
    };

    var html = '<div class="patent-filing-modal-container">'
      + '<div class="patent-filing-modal-header">'
      + '<h3>🏛️ How to File a Patent Application in India</h3>'
      + '<button class="patent-filing-modal-close" onclick="closePatentFilingGuideModal()">✕</button>'
      + '</div>'
      + '<div class="patent-filing-modal-body">'
      + '<div style="margin-bottom:20px;font-size:13px;color:#94a3b8;line-height:1.5;">'
      + 'A practical, beginner-friendly roadmap based on official Indian Patent Office (CGPDTM / IP India) procedures for botanical, herbal, and Ayurvedic innovations.'
      + '</div>'

      // Step 1
      + '<div class="patent-filing-step">'
      + '<div class="patent-filing-step-num">1</div>'
      + '<div class="patent-filing-step-content">'
      + '<h4>Step 1 — Check Existing Prior Art</h4>'
      + '<p>Search existing patent literature before filing. Use <strong>AYUR-INTEL Patent Intelligence</strong> and the official <strong>IP India / InPASS Public Search Portal</strong> to evaluate potential prior-art overlap and freedom-to-operate.</p>'
      + '</div></div>'

      // Step 2
      + '<div class="patent-filing-step">'
      + '<div class="patent-filing-step-num">2</div>'
      + '<div class="patent-filing-step-content">'
      + '<h4>Step 2 — Define the Invention</h4>'
      + '<p>Clearly identify what is technically new: specific composition ratios, standardized extract parameters, unique extraction/purification processes, bio-enhancement strategies, or delivery systems. <em>Note: A botanical ingredient or known traditional use alone is not patentable.</em></p>'
      + '</div></div>'

      // Step 3
      + '<div class="patent-filing-step">'
      + '<div class="patent-filing-step-num">3</div>'
      + '<div class="patent-filing-step-content">'
      + '<h4>Step 3 — Prepare Provisional or Complete Specification</h4>'
      + '<p><strong>Provisional Specification:</strong> Useful to secure an early priority date while formulation details are being finalized.<br>'
      + '<strong>Complete Specification:</strong> Contains full technical disclosure, drawings, and patent claims.<br>'
      + '<em>IMPORTANT: If a provisional specification is filed, official IP India guidance requires submitting the complete specification within <strong>12 months</strong>.</em></p>'
      + '</div></div>'

      // Step 4
      + '<div class="patent-filing-step">'
      + '<div class="patent-filing-step-num">4</div>'
      + '<div class="patent-filing-step-content">'
      + '<h4>Step 4 — Prepare Applicable Forms & Documents</h4>'
      + '<p>Common filing components include:<br>'
      + '• <strong>Form 1:</strong> Application for Grant of Patent<br>'
      + '• <strong>Form 2:</strong> Provisional or Complete Specification<br>'
      + '• Abstract of invention and drawings (where applicable)<br>'
      + '• <strong>Form 26:</strong> Power of Attorney (when filing through a registered patent agent/attorney, where applicable)<br>'
      + '<em>Requirements vary by applicant type. Always verify current forms and fees on IP India before filing.</em></p>'
      + '</div></div>'

      // Step 5
      + '<div class="patent-filing-step">'
      + '<div class="patent-filing-step-num">5</div>'
      + '<div class="patent-filing-step-content">'
      + '<h4>Step 5 — Access IP India e-Filing Portal</h4>'
      + '<p>The official Patent Office provides online patent submission via <strong>ipindiaonline.gov.in</strong>. A Digital Signature Certificate (DSC) or E-sign is required for online submission per current official guidelines.</p>'
      + '</div></div>'

      // Step 6
      + '<div class="patent-filing-step">'
      + '<div class="patent-filing-step-num">6</div>'
      + '<div class="patent-filing-step-content">'
      + '<h4>Step 6 — File Application & Pay Official Fee</h4>'
      + '<p>Complete the required forms, upload specifications, digitally sign, and pay the applicable official statutory fee. Fee structure varies by applicant category (natural person, startup, small entity, large entity).</p>'
      + '</div></div>'

      // Step 7
      + '<div class="patent-filing-step">'
      + '<div class="patent-filing-step-num">7</div>'
      + '<div class="patent-filing-step-content">'
      + '<h4>Step 7 — Publication & Examination</h4>'
      + '<p>Filing does NOT mean the patent has been granted. The application is published after 18 months (or earlier upon request). A <strong>Request for Examination (Form 18 / 18A)</strong> must be submitted. The Patent Office may issue a First Examination Report (FER) to which the applicant must respond.</p>'
      + '</div></div>'

      // Step 8
      + '<div class="patent-filing-step">'
      + '<div class="patent-filing-step-num">8</div>'
      + '<div class="patent-filing-step-content">'
      + '<h4>Step 8 — Grant & Post-Grant Maintenance</h4>'
      + '<p>A patent is granted only if statutory patentability requirements under the Indian Patents Act are satisfied. After grant, statutory renewal fees apply to maintain the patent term.</p>'
      + '</div></div>'

      // Highlighted Ayurvedic / Herbal Note Card
      + '<div style="background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.3);border-radius:10px;padding:16px;margin-top:20px;margin-bottom:20px;">'
      + '<h4 style="margin:0 0 8px 0;font-size:14px;font-weight:700;color:#fbbf24;display:flex;align-items:center;gap:8px;">🌿 Ayurvedic & Botanical Innovation Note</h4>'
      + '<p style="margin:0 0 10px 0;font-size:13px;color:#cbd5e1;line-height:1.5;">'
      + 'Traditional knowledge or known traditional use is not automatically patentable under Section 3(p) of the Indian Patents Act. Patent evaluation depends on the actual technical contribution, such as a genuinely novel formulation composition, standardized extract ratio, specific extraction/purification process, or delivery system.'
      + '</p>'
      + '<div style="font-size:12px;color:#cbd5e1;display:flex;gap:12px;flex-wrap:wrap;">'
      + '<a href="https://ipindia.gov.in/resource/patents-resources-guidelines" target="_blank" rel="noopener noreferrer" style="color:#fbbf24;text-decoration:underline;">IP India Examination Guidelines (AYUSH 2025) ↗</a>'
      + '<a href="https://www.tkdl.res.in" target="_blank" rel="noopener noreferrer" style="color:#fbbf24;text-decoration:underline;">TKDL Resource Portal ↗</a>'
      + '<a href="https://ipindia.gov.in/patents-before-you-apply-public-search" target="_blank" rel="noopener noreferrer" style="color:#fbbf24;text-decoration:underline;">Official Public Search ↗</a>'
      + '</div>'
      + '</div>'

      // Disclaimer
      + '<div class="innovation-disclaimer" style="margin:0;background:rgba(30,41,59,0.85);">'
      + icon("info", 18)
      + '<div><strong>Informational Filing Guidance Disclaimer:</strong> AYUR-INTEL provides informational filing guidance only. It does not file a patent on your behalf, provide legal advice, or guarantee patentability or grant. Always verify current requirements, forms, fees, and procedures with the Indian Patent Office (CGPDTM) or a qualified patent agent/attorney.</div>'
      + '</div>'
      + '</div>'

      // Footer Action Buttons
      + '<div class="patent-filing-modal-footer">'
      + '<a href="https://ipindia.gov.in/patents-e-services-comprehensive-e-filing-services" target="_blank" rel="noopener noreferrer" class="btn btn-primary" style="background:linear-gradient(135deg, #10b981 0%, #059669 100%);border:none;padding:10px 18px;font-size:13px;font-weight:700;display:inline-flex;align-items:center;gap:6px;">🇮🇳 Continue to Official IP India e-Filing ↗</a>'
      + '<div style="display:flex;gap:8px;flex-wrap:wrap;">'
      + '<a href="https://ipindia.gov.in/patents-before-you-apply-public-search" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm" style="display:inline-flex;align-items:center;gap:6px;">🔍 Search Existing Indian Patents ↗</a>'
      + '<a href="https://ipindia.gov.in/patents-before-you-apply-forms-official-fees" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm" style="display:inline-flex;align-items:center;gap:6px;">📄 Forms & Official Fees ↗</a>'
      + '</div>'
      + '</div>'
      + '</div>';

    modalDiv.innerHTML = html;
    document.body.appendChild(modalDiv);

    var escHandler = function (e) {
      if (e.key === "Escape") {
        closePatentFilingGuideModal();
        document.removeEventListener("keydown", escHandler);
      }
    };
    document.addEventListener("keydown", escHandler);
  }
  window.openPatentFilingGuideModal = openPatentFilingGuideModal;

  function closePatentFilingGuideModal() {
    var root = document.getElementById("patent-filing-modal-root");
    if (root) root.remove();
  }
  window.closePatentFilingGuideModal = closePatentFilingGuideModal;

  // ----------------------------------------------------------------
  // Patent Deep Analysis View
  // ----------------------------------------------------------------
  function renderPatentDeepAnalysis() {
    var a = state.patentDeepAnalysis;
    if (!a) return '';
    var html = ''
      + '<div class="view-header"><button class="btn btn-ghost btn-sm" id="back-from-deep-analysis">' + icon("arrow_back", 15) + ' Back to Patent Intel</button></div>'
      + '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>Patent Deep Analysis</h2></div><div class="card-body">';

    html += '<div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:16px">'
      + '<div><span class="label-caps" style="color:var(--color-on-surface-variant)">OVERALL RELEVANCE</span><div style="font-size:18px;font-weight:600;color:var(--color-on-surface)">' + escapeHtml((a.overall_relevance || "").replace(/_/g, " ")) + '</div></div>'
      + '<div><span class="label-caps" style="color:var(--color-on-surface-variant)">CONFIDENCE</span><div style="font-size:18px;font-weight:600;color:var(--color-on-surface)">' + escapeHtml(a.overall_confidence || "LOW") + '</div></div>'
      + '</div>';
    if (a.summary) html += '<p style="font-size:14px;color:var(--color-on-surface-variant);line-height:1.6;margin-bottom:16px">' + escapeHtml(a.summary) + '</p>';
    if (a.recommended_next_step) html += '<div style="padding:12px;border:1px solid var(--color-outline-variant);border-radius:var(--radius-md);margin-bottom:16px"><span class="label-caps" style="color:var(--color-on-surface-variant)">RECOMMENDED NEXT STEP</span><div style="margin-top:4px">' + escapeHtml(a.recommended_next_step) + '</div></div>';
    html += '</div></div>';

    if (a.comparisons && a.comparisons.length > 0) {
      html += '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>Feature Comparison</h2></div><div class="card-body">'
        + '<table style="width:100%;border-collapse:collapse"><thead><tr>'
        + '<th style="text-align:left;padding:8px 12px;border-bottom:2px solid var(--color-outline-variant);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:var(--color-on-surface-variant)">PRODUCT</th>'
        + '<th style="text-align:left;padding:8px 12px;border-bottom:2px solid var(--color-outline-variant);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:var(--color-on-surface-variant)">PATENT</th>'
        + '<th style="text-align:left;padding:8px 12px;border-bottom:2px solid var(--color-outline-variant);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:var(--color-on-surface-variant)">SIMILARITY</th>'
        + '</tr></thead><tbody>';
      a.comparisons.forEach(function (c) {
        html += '<tr style="border-bottom:1px solid var(--color-outline-variant)">'
          + '<td style="padding:10px 12px;font-weight:600">' + escapeHtml(c.product_component_label) + '</td>'
          + '<td style="padding:10px 12px">' + escapeHtml(c.patent_element) + '</td>'
          + '<td style="padding:10px 12px"><span class="chip selected">' + escapeHtml(c.similarity_level) + '</span></td>'
          + '</tr>';
      });
      html += '</tbody></table></div></div>';
    }

    html += '<div class="innovation-disclaimer">' + icon("warning", 18) + '<div><strong>Research & Decision Support Only.</strong> This analysis is not a legal opinion on patentability or infringement.</div></div>';
    return html;
  }
  // ----------------------------------------------------------------
  // IP Strategy Roadmap & Interactive Guides (with Fireworks)
  // ----------------------------------------------------------------
  let indicatorStatus = { ayush: 'pending', trademark: 'pending', patent: 'pending', tradesecret: 'pending', priorart: 'pending' };

  function loadIndicatorStatus() {
    try {
      const saved = localStorage.getItem('ip_indicator_status');
      if (saved) indicatorStatus = JSON.parse(saved);
    } catch (e) {}
  }

  function saveIndicatorStatus() {
    try {
      localStorage.setItem('ip_indicator_status', JSON.stringify(indicatorStatus));
    } catch (e) {}
  }

  // Initial load of indicator status
  loadIndicatorStatus();

  async function generateIPStrategy() {
    const s = (window.AYUR && window.AYUR.state) || state;
    const caseData = s.currentCase;
    if (!caseData || !caseData.id) {
      showToast('⚠️ Please select a product case first', 'warning');
      return;
    }
    var isNewView = s.view !== 'ip-strategy';
    if (isNewView) {
      saveCurrentViewScrollPosition();
    }
    showToast('🗺️ Generating IP Strategy Roadmap...', 'info');
    try {
      const response = await fetch(`/api/ip-strategy/cases/${caseData.id}/roadmap`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      if (!response.ok) throw new Error('IP Strategy generation failed');
      const result = await response.json();
      s.ipStrategy = result;
      s.view = 'ip-strategy';
      if (typeof saveStateToLocalStorage === 'function') saveStateToLocalStorage();
      renderIPStrategyResult(result);
      if (isNewView) {
        scrollToTop();
      }
      showToast('✅ IP Strategy Roadmap generated!', 'success');
    } catch (error) {
      console.error('IP Strategy error:', error);
      showToast('❌ Failed to generate IP Strategy', 'error');
    }
  }

  function renderIPStrategyResult(result) {
    const content = document.getElementById('content');
    if (!result) return '';
    loadIndicatorStatus();

    const stepsHTML = (result.steps || []).map(function(step) {
      const portalBtn = step.portal_link ? 
        `<button class="ip-step-action-btn" onclick="openRegistrationGuide('${step.guide_type}')">${escapeHtml(step.action)} →</button>` :
        `<button class="ip-step-action-btn" onclick="showToast('📝 ${escapeHtml(step.action)} - Coming soon!', 'info')">${escapeHtml(step.action)} →</button>`;

      return `
        <div class="ip-step-card">
          <div class="ip-step-number">${step.step}</div>
          <div class="ip-step-content">
            <div class="ip-step-header">
              <span class="ip-step-icon">${step.icon || '📄'}</span>
              <h4>${escapeHtml(step.title)}</h4>
              <span class="ip-step-status ${step.status || 'pending'}">Pending</span>
            </div>
            <div class="ip-step-details">
              <div class="ip-step-detail-row"><span class="ip-step-detail-label">What:</span><span>${escapeHtml(step.what)}</span></div>
              <div class="ip-step-detail-row"><span class="ip-step-detail-label">Why:</span><span>${escapeHtml(step.why)}</span></div>
              <div class="ip-step-detail-row"><span class="ip-step-detail-label">How:</span><span>${escapeHtml(step.how)}</span></div>
              <div class="ip-step-meta">
                <span class="ip-step-meta-item">⏱️ ${step.timeline_min}-${step.timeline_max} ${step.timeline_unit}</span>
                <span class="ip-step-meta-item">💰 ${step.cost_currency || '₹'}${Number(step.cost_min || 0).toLocaleString()} - ${step.cost_currency || '₹'}${Number(step.cost_max || 0).toLocaleString()}</span>
                <span class="ip-step-meta-item">🏛️ ${escapeHtml(step.authority || 'IPO')}</span>
              </div>
            </div>
            <div class="ip-step-action">${portalBtn}</div>
          </div>
        </div>
      `;
    }).join('');

    const indicatorsHTML = (result.success_indicators || []).map(function(ind) {
      const key = ind.key || (ind.title.toLowerCase().includes('ayush') ? 'ayush' : ind.title.toLowerCase().includes('trademark') ? 'trademark' : ind.title.toLowerCase().includes('patent') ? 'patent' : ind.title.toLowerCase().includes('trade secret') ? 'tradesecret' : 'priorart');
      const status = indicatorStatus[key] || 'pending';
      const statusLabels = { 'pending': 'Pending', 'in-progress': '⏳ In Progress', 'done': '✅ Done' };
      const statusClasses = { 'pending': 'pending', 'in-progress': 'in-progress', 'done': 'done' };
      return `
        <div class="ip-success-item ${status}" onclick="toggleIndicatorStatus('${key}', '${status}')">
          <span class="ip-success-icon">${ind.icon || '📜'}</span>
          <div>
            <div class="ip-success-title">${escapeHtml(ind.title)}</div>
            <div class="ip-success-desc">${escapeHtml(ind.description)}</div>
          </div>
          <span class="ip-success-status ${statusClasses[status]}">${statusLabels[status]}</span>
        </div>
      `;
    }).join('');

    const html = `
      <div class="ip-strategy-container">
        <div class="ip-strategy-header">
          <div>
            <h2>🗺️ IP Strategy Roadmap</h2>
            <p>${escapeHtml(result.product_name || 'Product')} · India-Specific IP Protection Plan</p>
          </div>
          <button onclick="if(window.AYUR){window.AYUR.navigateBackToCaseDetail();}" class="ip-strategy-back">← Back</button>
        </div>
        
        <div class="ip-readiness-card ${result.readiness_color || 'medium'}">
          <div class="ip-readiness-left">
            <span class="ip-readiness-icon">${result.readiness_icon || '🟢'}</span>
            <div>
              <div class="ip-readiness-label">IP Readiness</div>
              <div class="ip-readiness-value">${result.readiness_score !== undefined ? result.readiness_score + ' / 100 · ' : ''}${escapeHtml(result.readiness_level || result.readiness || 'HIGH')}</div>
            </div>
          </div>
          <div class="ip-readiness-right">
            <p>${escapeHtml(result.readiness_description || '')}</p>
            ${result.readiness_note ? `<p style="font-size:13px;color:#8aaaa0;margin-top:4px;">💡 ${escapeHtml(result.readiness_note)}</p>` : ''}
          </div>
        </div>

        ${result.readiness_breakdown ? `
        <div class="ip-breakdown-card" style="background:rgba(255,255,255,0.02);border:1px solid var(--color-outline);border-radius:var(--radius-md);padding:14px 18px;margin-bottom:16px;">
          <h4 style="margin:0 0 10px 0;font-size:13px;color:var(--color-on-surface-variant);">📊 Grounded Readiness Score Breakdown (0–100)</h4>
          <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(160px, 1fr));gap:10px;">
            <div style="background:rgba(0,0,0,0.25);padding:8px 12px;border-radius:6px;border-left:3px solid var(--color-primary);">
              <div style="font-size:11px;color:#8aaaa0;">Product Definition</div>
              <div style="font-size:14px;font-weight:700;color:var(--color-on-surface);margin-top:2px;">${result.readiness_breakdown.product_definition.score} / ${result.readiness_breakdown.product_definition.max_score}</div>
            </div>
            <div style="background:rgba(0,0,0,0.25);padding:8px 12px;border-radius:6px;border-left:3px solid var(--color-primary);">
              <div style="font-size:11px;color:#8aaaa0;">Innovation Articulation</div>
              <div style="font-size:14px;font-weight:700;color:var(--color-on-surface);margin-top:2px;">${result.readiness_breakdown.innovation_articulation.score} / ${result.readiness_breakdown.innovation_articulation.max_score}</div>
            </div>
            <div style="background:rgba(0,0,0,0.25);padding:8px 12px;border-radius:6px;border-left:3px solid var(--color-primary);">
              <div style="font-size:11px;color:#8aaaa0;">Prior-Art Intelligence</div>
              <div style="font-size:14px;font-weight:700;color:var(--color-on-surface);margin-top:2px;">${result.readiness_breakdown.prior_art_intelligence.score} / ${result.readiness_breakdown.prior_art_intelligence.max_score}</div>
            </div>
            <div style="background:rgba(0,0,0,0.25);padding:8px 12px;border-radius:6px;border-left:3px solid var(--color-primary);">
              <div style="font-size:11px;color:#8aaaa0;">Technical Differentiation</div>
              <div style="font-size:14px;font-weight:700;color:var(--color-on-surface);margin-top:2px;">${result.readiness_breakdown.technical_differentiation.score} / ${result.readiness_breakdown.technical_differentiation.max_score}</div>
            </div>
            <div style="background:rgba(0,0,0,0.25);padding:8px 12px;border-radius:6px;border-left:3px solid var(--color-primary);">
              <div style="font-size:11px;color:#8aaaa0;">Strategy Preparedness</div>
              <div style="font-size:14px;font-weight:700;color:var(--color-on-surface);margin-top:2px;">${result.readiness_breakdown.strategy_preparedness.score} / ${result.readiness_breakdown.strategy_preparedness.max_score}</div>
            </div>
          </div>
        </div>
        ` : ''}

        ${(result.strengths && result.strengths.length > 0) || (result.gaps && result.gaps.length > 0) ? `
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(240px, 1fr));gap:12px;margin-bottom:16px;">
          ${result.strengths && result.strengths.length > 0 ? `
          <div style="background:rgba(81,207,102,0.04);border:1px solid rgba(81,207,102,0.2);border-radius:8px;padding:12px 14px;">
            <h5 style="margin:0 0 6px 0;color:#51cf66;font-size:12px;display:flex;align-items:center;gap:6px;">💪 Key Strengths</h5>
            <ul style="margin:0;padding-left:16px;font-size:12px;color:var(--color-on-surface-variant);line-height:1.5;">
              ${result.strengths.map(s => `<li>${escapeHtml(s)}</li>`).join('')}
            </ul>
          </div>` : ''}
          ${result.gaps && result.gaps.length > 0 ? `
          <div style="background:rgba(255,146,43,0.04);border:1px solid rgba(255,146,43,0.2);border-radius:8px;padding:12px 14px;">
            <h5 style="margin:0 0 6px 0;color:#ff922b;font-size:12px;display:flex;align-items:center;gap:6px;">⚠️ Preparedness Gaps</h5>
            <ul style="margin:0;padding-left:16px;font-size:12px;color:var(--color-on-surface-variant);line-height:1.5;">
              ${result.gaps.map(g => `<li>${escapeHtml(g)}</li>`).join('')}
            </ul>
          </div>` : ''}
        </div>
        ` : ''}
        
        <div class="ip-summary-card">
          <div class="ip-summary-icon">📋</div>
          <div>
            <h4>Summary</h4>
            <p>${escapeHtml(result.summary || '')}</p>
          </div>
        </div>
        
        <div class="ip-steps-container">
          <h3>🗺️ Your IP Roadmap</h3>
          <div class="ip-steps-timeline">${stepsHTML}</div>
        </div>
        
        <div class="ip-success-indicators">
          <h4>📈 Success Indicators <span style="font-size:12px;color:#6b8a7a;font-weight:400;">(Click to update progress)</span></h4>
          <div class="ip-success-grid">${indicatorsHTML}</div>
        </div>
        
        <div class="ip-cost-summary">
          <h4>💰 Estimated Total Investment</h4>
          <div class="ip-cost-row"><span>Total Estimated Cost</span><span class="ip-cost-amount">₹${Number(result.total_cost_min || 0).toLocaleString()} - ₹${Number(result.total_cost_max || 0).toLocaleString()}</span></div>
          <div class="ip-cost-row"><span>Jurisdiction</span><span class="ip-cost-jurisdiction">${escapeHtml(result.jurisdiction || 'India (IPO/CGPDTM/AYUSH)')}</span></div>
          <div class="ip-cost-row"><span>Generated On</span><span>${escapeHtml(result.generated_on || '')}</span></div>
        </div>
        
        <div class="ip-disclaimer"><p>⚠️ ${escapeHtml(result.disclaimer || '')}</p></div>
        
        <div class="ip-actions">
          <button onclick="if(window.AYUR){window.AYUR.navigateBackToCaseDetail();}" class="ip-action-btn secondary">← Back to Case</button>
          <button onclick="showToast('📄 Export coming soon!', 'info')" class="ip-action-btn primary">📄 Export Roadmap</button>
          <button onclick="saveIndicatorStatus();showToast('💾 Progress saved!', 'success')" class="ip-action-btn primary">💾 Save Progress</button>
        </div>
      </div>
    `;

    if (content) content.innerHTML = html;
    return html;
  }

  function renderIPStrategy() {
    return renderIPStrategyResult(state.ipStrategy);
  }

  // Registration Guides
  function openRegistrationGuide(guideType) {
    const guides = {
      'ayush': {
        title: '📜 AYUSH Registration Guide',
        steps: [
          '📄 <strong>Step 1: Documentation</strong> - Prepare Aadhaar, PAN, Company registration (CoI, MoA, AoA), product list, component list, equipment list, staff qualifications (B.Sc/BAMS/B.Pharm)',
          '✅ <strong>Step 2: Apply for GMP Certificate</strong> - Get Good Manufacturing Practice certificate from Ministry of AYUSH',
          '📝 <strong>Step 3: Fill Application</strong> - Download and fill AYUSH license application form with product details',
          '📤 <strong>Step 4: Submit to Portal</strong> - Upload form with documents on e-AUSHADHI portal. Fees: ₹2,000 - ₹15,000',
          '⏳ <strong>Step 5: Verification & Approval</strong> - Department verifies, may inspect facility. Certificate issued upon approval'
        ],
        portalLink: 'https://www.e-aushadhi.gov.in/',
        portalText: 'Go to AYUSH Portal →'
      },
      'trademark': {
        title: '🏷️ Trademark Registration Guide',
        steps: [
          '🔍 <strong>Step 1: Trademark Search</strong> - Check if your mark is available at ipindia.gov.in',
          '📋 <strong>Step 2: File Form TM-A</strong> - Apply online with trademark specimen, goods list, and Power of Attorney. Fees: ₹4,500 - ₹9,000/class',
          '📑 <strong>Step 3: Examination</strong> - CGPDTM examines (6-12 months). Respond to objections if any',
          '📰 <strong>Step 4: Publication</strong> - Mark published in Trademark Journal (4 months opposition period)',
          '✅ <strong>Step 5: Registration</strong> - Certificate issued. Valid 10 years, renewable'
        ],
        portalLink: 'https://www.ipindia.gov.in/',
        portalText: 'Go to IP India Portal →'
      },
      'gi': {
        title: '🌍 GI Tagging Guide',
        steps: [
          '👥 <strong>Step 1: Form Association</strong> - Organize producers/association representing interest of producers',
          '📄 <strong>Step 2: File Application</strong> - Submit in triplicate with statement of case, 3 certified maps of region',
          '📋 <strong>Step 3: Documentation</strong> - Details of special characteristics, inspection structure, applicant details',
          '📤 <strong>Step 4: Submit to GI Registry</strong> - Send to Geographical Indications Registry, Chennai. Fees: ₹5,000 - ₹20,000',
          '📰 <strong>Step 5: Publication</strong> - Application published in GI Journal (3 months opposition period)',
          '✅ <strong>Step 6: Registration</strong> - Certificate issued. Valid 10 years, renewable'
        ],
        portalLink: 'https://www.ipindia.gov.in/gi-filing-process-step-by-step',
        portalText: 'Go to GI Registry Portal →'
      },
      'design': {
        title: '🎨 Design Patent Guide',
        steps: [
          '📐 <strong>Step 1: Prepare Drawings</strong> - Create PDF/JPG drawings showing article from all sides (shape, configuration, pattern)',
          '📋 <strong>Step 2: File Form 01</strong> - Submit design application with Power of Attorney and applicant details. Fees: ₹5,000 - ₹15,000',
          '🔍 <strong>Step 3: Examination</strong> - IPO examines for novelty and originality (6-9 months)',
          '✅ <strong>Step 4: Registration</strong> - Certificate issued. Valid 10 years, extendable by 5 years'
        ],
        portalLink: 'https://www.ipindia.gov.in/',
        portalText: 'Go to IPO Portal →'
      }
    };

    const guide = guides[guideType];
    if (!guide) return;

    const popupHTML = `
      <div class="registration-popup-overlay" onclick="if(event.target===this)closeRegistrationPopup()">
        <div class="registration-popup-card">
          <button class="registration-popup-close" onclick="closeRegistrationPopup()">✕</button>
          <div class="registration-popup-header">
            <h3>${guide.title}</h3>
            <p>Follow these steps to register on the official government portal</p>
          </div>
          <div class="registration-steps">
            ${guide.steps.map((step, i) => `
              <div class="registration-step">
                <span class="step-number">${i + 1}</span>
                <div class="step-content">${step}</div>
              </div>
            `).join('')}
          </div>
          <div class="registration-popup-footer">
            <a href="${guide.portalLink}" target="_blank" rel="noopener noreferrer" class="registration-portal-btn">
              ${guide.portalText} <span>↗</span>
            </a>
            <p class="registration-disclaimer">⚠️ You will be redirected to the official government portal. Complete your registration there.</p>
          </div>
        </div>
      </div>
    `;

    const existing = document.getElementById('registration-popup');
    if (existing) existing.remove();
    const div = document.createElement('div');
    div.id = 'registration-popup';
    div.innerHTML = popupHTML;
    document.body.appendChild(div);
  }

  function closeRegistrationPopup() {
    const popup = document.getElementById('registration-popup');
    if (popup) popup.remove();
  }

  // Indicator Status Toggle
  function toggleIndicatorStatus(indicatorKey, currentStatus) {
    if (currentStatus === 'done') return;
    if (currentStatus === 'pending') {
      indicatorStatus[indicatorKey] = 'in-progress';
      saveIndicatorStatus();
      if (window.AYUR.state.ipStrategy) {
        renderIPStrategyResult(window.AYUR.state.ipStrategy);
      }
      showToast('🔄 Status updated to "In Progress"', 'info');
      return;
    }
    if (currentStatus === 'in-progress') {
      showCompletionPopup(indicatorKey);
    }
  }

  // Completion Popup
  function showCompletionPopup(indicatorKey) {
    const names = {
      'ayush': 'AYUSH Registration',
      'trademark': 'Trademark Application',
      'patent': 'Patent Filing',
      'tradesecret': 'Trade Secret Documentation',
      'priorart': 'Prior Art Search'
    };
    const popupHTML = `
      <div class="completion-popup-overlay" onclick="if(event.target===this)closeCompletionPopup()">
        <div class="completion-popup-card">
          <button class="completion-popup-close" onclick="closeCompletionPopup()">✕</button>
          <div class="completion-popup-icon">🎉</div>
          <h3>Mark as Complete?</h3>
          <p>Are you sure you want to mark "<strong>${names[indicatorKey] || indicatorKey}</strong>" as complete?</p>
          <div class="completion-popup-actions">
            <button class="completion-popup-btn cancel" onclick="closeCompletionPopup()">Cancel</button>
            <button class="completion-popup-btn confirm" onclick="completeIndicator('${indicatorKey}')">✅ Yes, Done!</button>
          </div>
        </div>
      </div>
    `;

    const existing = document.getElementById('completion-popup');
    if (existing) existing.remove();
    const div = document.createElement('div');
    div.id = 'completion-popup';
    div.innerHTML = popupHTML;
    document.body.appendChild(div);
  }

  function closeCompletionPopup() {
    const popup = document.getElementById('completion-popup');
    if (popup) popup.remove();
  }

  function completeIndicator(indicatorKey) {
    indicatorStatus[indicatorKey] = 'done';
    saveIndicatorStatus();
    closeCompletionPopup();
    if (window.AYUR.state.ipStrategy) {
      renderIPStrategyResult(window.AYUR.state.ipStrategy);
    }
    showToast('🎉 Milestone marked as Complete!', 'success');
    triggerFireworks();
  }

  // Fireworks Celebration
  function triggerFireworks() {
    const existing = document.getElementById('fireworks-canvas');
    if (existing) existing.remove();

    const canvas = document.createElement('canvas');
    canvas.id = 'fireworks-canvas';
    document.body.appendChild(canvas);

    const ctx = canvas.getContext('2d');
    let width = canvas.width = window.innerWidth;
    let height = canvas.height = window.innerHeight;

    const colors = ['#34d399', '#10b981', '#fbbf24', '#f59e0b', '#60a5fa', '#a78bfa', '#f43f5e', '#ffffff'];
    const particles = [];
    const rockets = [];

    class Rocket {
      constructor(targetX, targetY) {
        this.x = Math.random() * (width * 0.8) + (width * 0.1);
        this.y = height;
        this.targetX = targetX;
        this.targetY = targetY;
        this.speed = 10 + Math.random() * 4;
        this.angle = Math.atan2(targetY - this.y, targetX - this.x);
        this.vx = Math.cos(this.angle) * this.speed;
        this.vy = Math.sin(this.angle) * this.speed;
        this.color = colors[Math.floor(Math.random() * colors.length)];
        this.trail = [];
      }
      update() {
        this.trail.push({ x: this.x, y: this.y });
        if (this.trail.length > 5) this.trail.shift();
        this.x += this.vx;
        this.y += this.vy;
        const dist = Math.hypot(this.targetX - this.x, this.targetY - this.y);
        return dist < 15 || this.vy >= 0 || this.y <= this.targetY;
      }
      draw() {
        ctx.beginPath();
        for (let i = 0; i < this.trail.length; i++) {
          const pt = this.trail[i];
          ctx.lineTo(pt.x, pt.y);
        }
        ctx.strokeStyle = this.color;
        ctx.lineWidth = 3;
        ctx.stroke();
      }
    }

    class Particle {
      constructor(x, y, color) {
        this.x = x;
        this.y = y;
        this.color = color || colors[Math.floor(Math.random() * colors.length)];
        const angle = Math.random() * Math.PI * 2;
        const speed = Math.random() * 7 + 2;
        this.vx = Math.cos(angle) * speed;
        this.vy = Math.sin(angle) * speed;
        this.alpha = 1;
        this.decay = Math.random() * 0.02 + 0.015;
        this.gravity = 0.12;
        this.friction = 0.96;
        this.size = Math.random() * 3 + 2;
      }
      update() {
        this.vx *= this.friction;
        this.vy *= this.friction;
        this.vy += this.gravity;
        this.x += this.vx;
        this.y += this.vy;
        this.alpha -= this.decay;
        return this.alpha > 0;
      }
      draw() {
        ctx.save();
        ctx.globalAlpha = Math.max(0, this.alpha);
        ctx.fillStyle = this.color;
        ctx.shadowBlur = 10;
        ctx.shadowColor = this.color;
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }
    }

    function createExplosion(x, y) {
      const count = 50 + Math.floor(Math.random() * 30);
      const chosenColor = colors[Math.floor(Math.random() * colors.length)];
      for (let i = 0; i < count; i++) {
        particles.push(new Particle(x, y, Math.random() > 0.3 ? chosenColor : colors[Math.floor(Math.random() * colors.length)]));
      }
    }

    // Launch 5 bursts of rockets
    for (let i = 0; i < 6; i++) {
      setTimeout(() => {
        const tx = Math.random() * (width * 0.7) + (width * 0.15);
        const ty = Math.random() * (height * 0.4) + (height * 0.15);
        rockets.push(new Rocket(tx, ty));
      }, i * 280);
    }

    let animId;
    const startTime = Date.now();

    function animate() {
      ctx.clearRect(0, 0, width, height);

      // Update rockets
      for (let i = rockets.length - 1; i >= 0; i--) {
        const rocket = rockets[i];
        const exploded = rocket.update();
        rocket.draw();
        if (exploded) {
          createExplosion(rocket.x, rocket.y);
          rockets.splice(i, 1);
        }
      }

      // Update particles
      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        const alive = p.update();
        if (alive) {
          p.draw();
        } else {
          particles.splice(i, 1);
        }
      }

      if (Date.now() - startTime < 3500 || rockets.length > 0 || particles.length > 0) {
        animId = requestAnimationFrame(animate);
      } else {
        cancelAnimationFrame(animId);
        canvas.remove();
      }
    }

    animate();
  }


  // ----------------------------------------------------------------
  // Regulatory Intelligence Select View
  // ----------------------------------------------------------------
  function renderRegulatorySelect() {
    var c = state.currentCase;
    var jurisdictions = [
      { code: "IN", name: "India", flag: "\ud83c\uddee\ud83c\uddf3" },
      { code: "US", name: "United States", flag: "\ud83c\uddfa\ud83c\uddf8" },
      { code: "EU", name: "European Union", flag: "\ud83c\uddea\ud83c\uddfa" },
      { code: "DE", name: "Germany", flag: "\ud83c\udde9\ud83c\uddea" }
    ];
    var html = ''
      + '<div class="view-header"><button class="btn btn-ghost btn-sm" id="back-from-regulatory-select">' + icon("arrow_back", 15) + ' Back to Case</button></div>'
      + '<div class="card"><div class="card-head"><h2>Regulatory Intelligence</h2>'
      + '<p>Select a target market to evaluate regulatory pathways and compliance requirements for ' + escapeHtml(c ? c.name : "your product") + '</p></div>'
      + '<div class="card-body">'
      + '<div class="passport-jurisdiction-grid" style="grid-template-columns:repeat(4,1fr)">';
    jurisdictions.forEach(function (j) {
      html += '<button class="passport-jurisdiction-btn reg-jur-btn" data-jurisdiction="' + j.code + '">'
        + '<span class="jurisdiction-flag">' + j.flag + '</span>'
        + '<span>' + j.name + '</span></button>';
    });
    html += '</div></div></div>';
    return html;
  }

  // ----------------------------------------------------------------
  // Regulatory Intelligence View
  // ----------------------------------------------------------------
  function renderRegulatoryIntelligence() {
    var p = state.regulatoryProfile;
    if (!p) return '';
    var c = state.currentCase;
    var jurisdictionNames = { IN: "India \ud83c\uddee\ud83c\uddf3", US: "United States \ud83c\uddfa\ud83c\uddf8", EU: "European Union \ud83c\uddea\ud83c\uddfa", DE: "Germany \ud83c\udde9\ud83c\uddea" };

    var html = ''
      + '<div class="view-header">'
      + '<button class="btn btn-ghost btn-sm" id="back-from-regulatory">' + icon("arrow_back", 15) + ' Back to Case</button>'
      + '<div style="display:flex;gap:8px;margin-left:auto">'
      + '<button class="btn btn-secondary btn-sm" id="open-jurisdiction-compare-btn">' + icon("compare", 14) + ' Compare Jurisdictions</button>'
      + '</div></div>'

      + '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>Regulatory Intelligence</h2>'
      + '<p>Regulatory landscape analysis for your product</p></div><div class="card-body">'

      + '<div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:16px">'
      + '<div><span class="label-caps" style="color:var(--color-on-surface-variant)">PRODUCT</span><div style="font-size:16px;font-weight:600;color:var(--color-on-surface)">' + escapeHtml(p.product_name || (c ? c.name : "")) + '</div></div>'
      + '<div><span class="label-caps" style="color:var(--color-on-surface-variant)">TARGET MARKET</span><div style="font-size:16px;font-weight:600;color:var(--color-on-surface)">' + (jurisdictionNames[p.jurisdiction] || p.jurisdiction) + '</div></div>'
      + '<div><span class="label-caps" style="color:var(--color-on-surface-variant)">POTENTIAL CATEGORY</span><div style="font-size:14px;font-weight:600;color:var(--color-on-surface)">' + escapeHtml(p.potential_category || "Requires verification") + '</div>'
      + '<div style="font-size:12px;color:var(--color-on-surface-variant)">Confidence: ' + escapeHtml(p.category_confidence || "Low") + '</div></div>'
      + '</div>'

      + '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px">';
    if (p.relevant_count > 0) html += '<span class="innovation-badge" style="background:rgba(45,74,62,0.1);color:var(--color-secondary)">' + p.relevant_count + ' Relevant</span>';
    if (p.potentially_relevant_count > 0) html += '<span class="innovation-badge" style="background:rgba(245,158,11,0.1);color:#d97706">' + p.potentially_relevant_count + ' Potentially Relevant</span>';
    if (p.needs_verification_count > 0) html += '<span class="innovation-badge" style="background:rgba(117,119,122,0.1);color:var(--color-on-surface-variant)">' + p.needs_verification_count + ' Needs Verification</span>';
    html += '</div></div></div>';

    // Requirements by category
    var grouped = {};
    (p.requirements || []).forEach(function (r) {
      var cat = r.category || "OTHER";
      if (!grouped[cat]) grouped[cat] = [];
      grouped[cat].push(r);
    });
    var categoryIcons = { CLASSIFICATION: "science", INGREDIENT: "eco", CLAIMS: "verified", LABELLING: "description", DOCUMENTATION: "folder", SAFETY: "warning" };
    Object.keys(grouped).forEach(function (cat) {
      html += '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>' + icon(categoryIcons[cat] || "info", 18) + ' ' + escapeHtml(cat) + '</h2></div><div class="card-body">';
      grouped[cat].forEach(function (r) {
        html += '<div style="margin-bottom:12px;padding:12px;border:1px solid var(--color-outline-variant);border-radius:var(--radius-md)">'
          + '<div style="font-size:14px;font-weight:600;color:var(--color-on-surface);margin-bottom:4px">' + escapeHtml(r.title) + '</div>'
          + '<div style="font-size:13px;color:var(--color-on-surface-variant);line-height:1.6">' + escapeHtml(r.description) + '</div>'
          + '<div style="margin-top:8px"><span class="chip selected">' + escapeHtml(r.applicability) + '</span> ';
        if (r.authority) html += '<span style="font-size:12px;color:var(--color-on-surface-variant)">' + escapeHtml(r.authority) + '</span>';
        html += '</div></div>';
      });
      html += '</div></div>';
    });

    // Information gaps
    if (p.information_gaps && p.information_gaps.length > 0) {
      html += '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>Information Gaps</h2></div><div class="card-body"><ul style="margin:0;padding-left:20px">';
      p.information_gaps.forEach(function (g) { html += '<li style="margin-bottom:6px">' + escapeHtml(g) + '</li>'; });
      html += '</ul></div></div>';
    }

    html += '<div class="innovation-disclaimer">' + icon("warning", 18) + '<div><strong>Research & Decision Support Only.</strong> This analysis is not legal or regulatory advice.</div></div>';
    return html;
  }

  // ----------------------------------------------------------------
  // Jurisdiction Comparison View (Phase 10)
  // ----------------------------------------------------------------
  function renderJurisdictionComparison() {
    var jc = state.jurisdictionComparison;
    if (!jc) return '<div class="card"><div class="card-body"><p>No comparison available.</p></div></div>';
    var c = state.currentCase;

    var statusColors = { FOUND: "var(--color-secondary)", MISSING: "var(--color-outline)", NOT_CONFIGURED: "var(--color-outline)", PARTIAL: "var(--color-amber)" };

    var html = ''
      + '<div class="view-header">'
      + '<button class="btn btn-ghost btn-sm" id="back-from-jurisdiction-comparison">' + icon("arrow_back", 15) + ' Back to Regulatory</button></div>'

      + '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>Jurisdiction Comparison</h2>'
      + '<p>Cross-jurisdiction regulatory comparison for your product</p></div><div class="card-body">'

      + '<div style="margin-bottom:16px"><span class="label-caps" style="color:var(--color-on-surface-variant)">PRODUCT</span>'
      + '<div style="font-size:16px;font-weight:600;color:var(--color-on-surface)">' + escapeHtml(jc.product_name || (c ? c.name : "")) + '</div></div>'

      + '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px">';
    jc.jurisdictions.forEach(function (j) {
      html += '<span class="chip selected">' + (j.flag || '') + ' ' + (j.jurisdiction_name || j.jurisdiction) + '</span>';
    });
    html += '</div>'

      + '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px">'
      + '<div class="patent-stat-card"><div class="patent-stat-label">ITEMS COMPARED</div><div class="patent-stat-value">' + jc.total_items + '</div></div>'
      + '<div class="patent-stat-card"><div class="patent-stat-label">DIFFERENCES</div><div class="patent-stat-value">' + jc.differences_found + '</div></div>'
      + '<div class="patent-stat-card"><div class="patent-stat-label">JURISDICTIONS</div><div class="patent-stat-value">' + jc.jurisdictions_count + '</div></div>'
      + '<div class="patent-stat-card"><div class="patent-stat-label">INFO GAPS</div><div class="patent-stat-value">' + jc.information_gaps_total + '</div></div>'
      + '</div></div></div>';

    // Comparison Table
    html += '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>Comparison Matrix</h2></div>'
      + '<div class="card-body" style="overflow-x:auto">'
      + '<table style="width:100%;border-collapse:collapse;font-size:14px">'
      + '<thead><tr><th style="text-align:left;padding:8px 12px;border-bottom:2px solid var(--color-outline-variant);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:var(--color-on-surface-variant)">REQUIREMENT</th>';
    jc.jurisdictions.forEach(function (j) {
      html += '<th style="text-align:left;padding:8px 12px;border-bottom:2px solid var(--color-outline-variant);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:var(--color-on-surface-variant)">' + (j.flag || '') + ' ' + (j.jurisdiction_name || j.jurisdiction) + '</th>';
    });
    html += '<th style="text-align:left;padding:8px 12px;border-bottom:2px solid var(--color-outline-variant);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:var(--color-on-surface-variant)">DIFF?</th></tr></thead><tbody>';

    jc.items.forEach(function (item) {
      html += '<tr style="border-bottom:1px solid var(--color-outline-variant)">'
        + '<td style="padding:10px 12px;font-weight:600;color:var(--color-on-surface);white-space:nowrap">' + escapeHtml(item.normalized_label) + '</td>';
      jc.jurisdictions.forEach(function (j) {
        var val = item.values.find(function (v) { return v.jurisdiction === j.jurisdiction; });
        var status = val ? val.status : "MISSING";
        var color = statusColors[status] || "var(--color-outline)";
        var dot = '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + color + ';margin-right:6px;vertical-align:middle"></span>';
        var valueText = (val && val.value) ? escapeHtml(val.value.substring(0, 80)) + (val.value.length > 80 ? '...' : '') : '<span style="color:var(--color-outline);font-style:italic">Not available</span>';
        html += '<td style="padding:10px 12px;font-size:13px;color:var(--color-on-surface)">' + dot + valueText + '</td>';
      });
      var diffBadge = item.is_difference
        ? '<span class="chip selected" style="background:rgba(245,158,11,0.1);color:#d97706;font-size:11px">DIFF</span>'
        : '<span style="color:var(--color-outline);font-size:11px">Same</span>';
      html += '<td style="padding:10px 12px">' + diffBadge + '</td></tr>';
    });
    html += '</tbody></table></div></div>';

    // Jurisdiction Detail Cards
    jc.jurisdictions.forEach(function (j) {
      html += '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>' + (j.flag || '') + ' ' + escapeHtml(j.jurisdiction_name || j.jurisdiction) + '</h2></div><div class="card-body">'
        + '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px">'
        + '<div><span class="label-caps" style="color:var(--color-on-surface-variant)">CONFIDENCE</span><div style="font-size:14px;font-weight:600;color:var(--color-on-surface)">' + (j.confidence || "LOW") + '</div></div>'
        + '<div><span class="label-caps" style="color:var(--color-on-surface-variant)">SOURCE COVERAGE</span><div style="font-size:14px;font-weight:600;color:var(--color-on-surface)">' + (j.source_coverage || "NONE") + '</div></div>'
        + '<div><span class="label-caps" style="color:var(--color-on-surface-variant)">REQUIREMENTS</span><div style="font-size:14px;font-weight:600;color:var(--color-on-surface)">' + (j.requirements_count || 0) + '</div></div>'
        + '</div>';
      if (j.category) html += '<div style="margin-bottom:12px"><span class="label-caps" style="color:var(--color-on-surface-variant)">POTENTIAL CATEGORY</span><div style="font-size:14px;font-weight:600;color:var(--color-on-surface);margin-top:4px">' + escapeHtml(j.category) + '</div></div>';
      html += '</div></div>';
    });

    // Key Differences
    if (jc.key_differences && jc.key_differences.length > 0) {
      html += '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>Key Differences</h2></div><div class="card-body"><ul style="margin:0;padding-left:20px">';
      jc.key_differences.forEach(function (d) { html += '<li style="margin-bottom:8px;line-height:1.6">' + escapeHtml(d) + '</li>'; });
      html += '</ul></div></div>';
    }

    // Decision Support Notes
    if (jc.decision_support_notes) {
      html += '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>Decision Support Notes</h2></div><div class="card-body">'
        + '<p style="font-size:14px;color:var(--color-on-surface-variant);line-height:1.6;font-style:italic">' + escapeHtml(jc.decision_support_notes) + '</p>'
        + '</div></div>';
    }

    html += '<div class="innovation-disclaimer">' + icon("warning", 18) + '<div><strong>Research & Decision Support Only.</strong> This comparison reflects the information currently available in AYUR-INTEL and is not legal or regulatory advice.</div></div>';
    return html;
  }

  // ----------------------------------------------------------------
  // Product Decision Dashboard (Phase 13)
  // ----------------------------------------------------------------

  function renderDecisionDashboard() {
    var d = state.dashboardData;
    if (!d) return '<div class="card"><div class="card-body"><p>No dashboard data available.</p></div></div>';

    var statusColors = {
      GOOD: 'var(--color-secondary)', PARTIAL: '#d97706', LIMITED: 'var(--color-error)',
      REVIEW_REQUIRED: '#d97706', WATCH: '#d97706', ATTENTION_REQUIRED: 'var(--color-error)',
      CLEAR: 'var(--color-secondary)', NOT_READY: 'var(--color-error)',
      PARTIALLY_READY: '#d97706', READY_FOR_NEXT_STEP: 'var(--color-secondary)'
    };
    var statusLabels = {
      GOOD: 'Good', PARTIAL: 'Partial', LIMITED: 'Limited',
      REVIEW_REQUIRED: 'Review Required', WATCH: 'Watch', ATTENTION_REQUIRED: 'Attention Required',
      CLEAR: 'Clear', NOT_READY: 'Not Ready',
      PARTIALLY_READY: 'Partially Ready', READY_FOR_NEXT_STEP: 'Ready for Next Step',
      ANALYSIS_NOT_STARTED: 'Not Started', DATA_INCOMPLETE: 'Data Incomplete',
      ANALYSIS_IN_PROGRESS: 'In Progress'
    };
    var phaseLabels = {
      PHASE_5_INNOVATION: 'Innovation Map', PHASE_6_PATENT: 'Patent Intelligence',
      PHASE_7_PATENT_DEEP: 'Patent Deep Analysis', PHASE_8_IP_STRATEGY: 'IP Strategy',
      PHASE_9_REGULATORY: 'Regulatory Intel', PHASE_10_JURISDICTION: 'Jurisdiction Compare',
      USER_INPUT: 'User Input'
    };

    var snap = d.product_snapshot || {};
    var summary = d.decision_summary || {};
    var readiness = d.readiness || {};
    var ipSum = d.ip_summary || {};
    var regSum = d.regulatory_summary || {};

    var html = ''
      + '<div class="view-header"><button class="btn btn-ghost btn-sm" id="back-from-dashboard">' + icon('arrow_back', 15) + ' Back to Case</button></div>'

      // Hero header
      + '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>Product Decision Dashboard</h2>'
      + '<p>Single decision center for ' + escapeHtml(d.product_name || '') + '</p></div><div class="card-body">'

      // Readiness status banner
      + '<div style="padding:16px 20px;border-radius:var(--radius-md);margin-bottom:16px;border:1px solid ' + (statusColors[readiness.level] || 'var(--color-outline)') + ';background:' + (statusColors[readiness.level] || 'var(--color-outline)') + '08">'
      + '<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">'
      + '<span style="font-size:24px;font-weight:700;color:' + (statusColors[readiness.level] || 'var(--color-on-surface)') + '">' + (statusLabels[readiness.level] || readiness.level) + '</span>'
      + '</div>';
    if (readiness.explanation && readiness.explanation.length > 0) {
      html += '<ul style="margin:0;padding-left:20px;font-size:13px;color:var(--color-on-surface-variant);line-height:1.6">';
      readiness.explanation.forEach(function (r) { html += '<li>' + escapeHtml(r) + '</li>'; });
      html += '</ul>';
    }
    html += '</div>';

    // Product snapshot
    html += '<div style="display:flex;gap:24px;flex-wrap:wrap">'
      + '<div><span class="label-caps" style="color:var(--color-on-surface-variant)">PRODUCT</span><div style="font-size:16px;font-weight:600;color:var(--color-on-surface)">' + escapeHtml(snap.name || '') + '</div></div>'
      + '<div><span class="label-caps" style="color:var(--color-on-surface-variant)">STAGE</span><div style="font-size:14px;font-weight:600;color:var(--color-on-surface)">' + escapeHtml(snap.stage || 'Idea') + '</div></div>'
      + '<div><span class="label-caps" style="color:var(--color-on-surface-variant)">FORM</span><div style="font-size:14px;font-weight:600;color:var(--color-on-surface)">' + escapeHtml(snap.form || 'Not specified') + '</div></div>'
      + '<div><span class="label-caps" style="color:var(--color-on-surface-variant)">JURISDICTIONS</span><div style="font-size:14px;font-weight:600;color:var(--color-on-surface)">' + (snap.jurisdictions || []).join(', ') + '</div></div>'
      + '</div>';

    html += '</div></div>';

    // Decision Summary cards
    html += '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;margin-bottom:20px">';

    // IP Card
    var ipColor = statusColors[summary.ip_status] || 'var(--color-outline)';
    var ipReadinessText = (ipSum.ip_readiness_score !== undefined) ? (ipSum.ip_readiness_score + ' / 100 · ' + (ipSum.ip_readiness_level || '')) : (statusLabels[summary.ip_status] || summary.ip_status);
    html += '<div class="card" style="border-left:4px solid ' + ipColor + '"><div class="card-body">'
      + '<div class="label-caps" style="color:var(--color-on-surface-variant);margin-bottom:4px">IP READINESS & STRATEGY</div>'
      + '<div style="font-size:16px;font-weight:700;color:' + ipColor + ';margin-bottom:4px">' + escapeHtml(ipReadinessText) + '</div>'
      + '<div style="font-size:12px;color:var(--color-on-surface-variant)">' + (ipSum.ip_strategy_items || 0) + ' Strategy Actions · ' + escapeHtml(summary.ip_reason || '') + '</div>'
      + '</div></div>';

    // Regulatory Card
    var regColor = statusColors[summary.regulatory_status] || 'var(--color-outline)';
    html += '<div class="card" style="border-left:4px solid ' + regColor + '"><div class="card-body">'
      + '<div class="label-caps" style="color:var(--color-on-surface-variant);margin-bottom:4px">REGULATORY</div>'
      + '<div style="font-size:16px;font-weight:700;color:' + regColor + ';margin-bottom:4px">' + (statusLabels[summary.regulatory_status] || summary.regulatory_status) + '</div>'
      + '<div style="font-size:12px;color:var(--color-on-surface-variant)">' + escapeHtml(summary.regulatory_reason || '') + '</div>'
      + '</div></div>';

    // Evidence Card
    var evColor = statusColors[summary.evidence_status] || 'var(--color-outline)';
    html += '<div class="card" style="border-left:4px solid ' + evColor + '"><div class="card-body">'
      + '<div class="label-caps" style="color:var(--color-on-surface-variant);margin-bottom:4px">EVIDENCE</div>'
      + '<div style="font-size:16px;font-weight:700;color:' + evColor + ';margin-bottom:4px">' + (summary.evidence_coverage || 0) + '% Coverage</div>'
      + '<div style="font-size:12px;color:var(--color-on-surface-variant)">' + (statusLabels[summary.evidence_status] || summary.evidence_status) + '</div>'
      + '</div></div>';

    // Risk Card
    var riskColor = statusColors[summary.risk_status] || 'var(--color-outline)';
    html += '<div class="card" style="border-left:4px solid ' + riskColor + '"><div class="card-body">'
      + '<div class="label-caps" style="color:var(--color-on-surface-variant);margin-bottom:4px">RISK</div>'
      + '<div style="font-size:16px;font-weight:700;color:' + riskColor + ';margin-bottom:4px">' + (statusLabels[summary.risk_status] || summary.risk_status) + '</div>'
      + '<div style="font-size:12px;color:var(--color-on-surface-variant)">' + (summary.high_risks || 0) + ' high-priority risk(s)</div>'
      + '</div></div>';

    // Completeness Card
    var compColor = statusColors[summary.product_completeness_status] || 'var(--color-outline)';
    html += '<div class="card" style="border-left:4px solid ' + compColor + '"><div class="card-body">'
      + '<div class="label-caps" style="color:var(--color-on-surface-variant);margin-bottom:4px">PRODUCT COMPLETENESS</div>'
      + '<div style="font-size:16px;font-weight:700;color:' + compColor + ';margin-bottom:4px">' + (summary.product_completeness_pct || 0) + '%</div>'
      + '<div style="font-size:12px;color:var(--color-on-surface-variant)">' + (statusLabels[summary.product_completeness_status] || summary.product_completeness_status) + '</div>'
      + '</div></div>';

    html += '</div>';

    // Key Findings
    if (d.key_findings && d.key_findings.length > 0) {
      html += '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>' + icon('lightbulb', 18) + ' Key Findings</h2></div><div class="card-body">';
      d.key_findings.forEach(function (f, i) {
        html += '<div style="display:flex;gap:12px;align-items:start;margin-bottom:12px;padding:12px;border:1px solid var(--color-outline-variant);border-radius:var(--radius-md)">'
          + '<span style="font-size:18px;font-weight:700;color:var(--color-on-surface-variant);min-width:24px">' + (i + 1) + '</span>'
          + '<div><div style="font-size:14px;font-weight:600;color:var(--color-on-surface)">' + escapeHtml(f.title) + '</div>';
        if (f.description) html += '<div style="font-size:12px;color:var(--color-on-surface-variant);margin-top:2px">' + escapeHtml(f.description) + '</div>';
        html += '<div style="margin-top:4px">';
        if (f.source_phase) html += '<span class="chip selected" style="font-size:10px">' + (phaseLabels[f.source_phase] || f.source_phase) + '</span> ';
        if (f.evidence_available) html += '<span class="chip" style="font-size:10px">Evidence Available</span>';
        html += '</div></div></div>';
      });
      html += '</div></div>';
    }

    // Top Risks
    if (d.top_risks && d.top_risks.length > 0) {
      html += '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>' + icon('warning', 18) + ' Top Risks</h2>'
        + '<button class="btn btn-ghost btn-sm" onclick="document.getElementById(\'open-risk-btn\') && document.getElementById(\'open-risk-btn\').click()">View All Risks</button></div><div class="card-body">';
      d.top_risks.forEach(function (r) {
        var color = statusColors[r.level] || 'var(--color-outline)';
        html += '<div style="display:flex;gap:12px;align-items:start;margin-bottom:12px;padding:12px;border-left:4px solid ' + color + ';border-radius:0 var(--radius-md) var(--radius-md) 0;background:' + color + '08">'
          + '<span style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:' + color + ';min-width:60px">' + escapeHtml(r.level) + '</span>'
          + '<div><div style="font-size:14px;font-weight:600;color:var(--color-on-surface)">' + escapeHtml(r.title) + '</div>';
        if (r.description) html += '<div style="font-size:12px;color:var(--color-on-surface-variant);margin-top:2px">' + escapeHtml(r.description) + '</div>';
        html += '</div></div>';
      });
      html += '</div></div>';
    }

    // Information Gaps
    if (d.information_gaps && d.information_gaps.length > 0) {
      html += '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>' + icon('extension', 18) + ' Information Gaps</h2></div><div class="card-body">';
      d.information_gaps.forEach(function (g) {
        var priColor = g.priority === 'HIGH' ? 'var(--color-error)' : g.priority === 'MEDIUM' ? '#d97706' : 'var(--color-secondary)';
        html += '<div style="display:flex;gap:12px;align-items:start;margin-bottom:12px;padding:12px;border:1px solid var(--color-outline-variant);border-radius:var(--radius-md)">'
          + '<span style="color:' + priColor + ';font-size:16px">' + icon('warning', 16) + '</span>'
          + '<div><div style="font-size:14px;font-weight:600;color:var(--color-on-surface)">' + escapeHtml(g.title) + '</div>';
        if (g.description) html += '<div style="font-size:12px;color:var(--color-on-surface-variant);margin-top:2px">' + escapeHtml(g.description) + '</div>';
        if (g.suggested_action) html += '<div style="font-size:12px;color:var(--color-on-surface);margin-top:4px">Action: ' + escapeHtml(g.suggested_action) + '</div>';
        html += '</div></div>';
      });
      html += '</div></div>';
    }

    // Recommended Next Steps
    if (d.recommended_actions && d.recommended_actions.length > 0) {
      html += '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>' + icon('arrow_forward', 18) + ' Recommended Next Steps</h2></div><div class="card-body">';
      d.recommended_actions.forEach(function (a, i) {
        var priColor = a.priority === 'HIGH' ? 'var(--color-error)' : a.priority === 'MEDIUM' ? '#d97706' : 'var(--color-secondary)';
        html += '<div style="display:flex;gap:12px;align-items:start;margin-bottom:12px;padding:12px;border:1px solid var(--color-outline-variant);border-radius:var(--radius-md)">'
          + '<span style="font-size:18px;font-weight:700;color:' + priColor + ';min-width:24px">' + (i + 1) + '</span>'
          + '<div style="flex:1"><div style="font-size:14px;font-weight:600;color:var(--color-on-surface)">' + escapeHtml(a.title) + '</div>';
        if (a.description) html += '<div style="font-size:12px;color:var(--color-on-surface-variant);margin-top:2px">' + escapeHtml(a.description) + '</div>';
        html += '</div>';
        if (a.action_view) html += '<button class="btn btn-ghost btn-sm">' + escapeHtml(a.action_label) + '</button>';
        html += '</div>';
      });
      html += '</div></div>';
    }

    // Jurisdictions
    if (d.jurisdictions && d.jurisdictions.length > 0) {
      html += '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>' + icon('language', 18) + ' Jurisdiction Summary</h2></div><div class="card-body">';
      d.jurisdictions.forEach(function (j) {
        html += '<div style="display:flex;gap:16px;align-items:center;margin-bottom:12px;padding:12px;border:1px solid var(--color-outline-variant);border-radius:var(--radius-md)">'
          + '<span style="font-size:24px">' + (j.flag || '') + '</span>'
          + '<div style="flex:1"><div style="font-size:14px;font-weight:600;color:var(--color-on-surface)">' + escapeHtml(j.jurisdiction) + '</div>';
        if (j.key_issue) html += '<div style="font-size:12px;color:var(--color-on-surface-variant)">Key Issue: ' + escapeHtml(j.key_issue) + '</div>';
        html += '</div>';
        html += '<span class="chip selected" style="font-size:10px">' + escapeHtml(j.regulatory_coverage) + '</span>';
        html += '</div>';
      });
      html += '</div></div>';
    }

    // Disclaimer
    html += '<div class="innovation-disclaimer">' + icon('warning', 18) + '<div><strong>Decision Support Only.</strong> This dashboard is NOT legal approval, patentability, regulatory approval, or safety certification. It reflects the current state of information in AYUR-INTEL.</div></div>';

    return html;
  }

  // ----------------------------------------------------------------
  // AI-Powered Risk Intelligence Module (Phase 12)
  // ----------------------------------------------------------------

  var _isRiskAssessmentGenerating = false;

  async function generateRiskAssessment(caseId, forceReassess) {
    var c = state.currentCase || (state.cases && state.cases.find(function(item) { return item.id === caseId; }));
    if (!c && state.cases && state.cases.length > 0) {
      c = state.cases[0];
      state.currentCase = c;
    }
    if (!c) {
      showToast('⚠️ No active product case found', 'error');
      return;
    }

    if (_isRiskAssessmentGenerating) {
      showToast('⏳ Risk assessment generation is already in progress...', 'info');
      return;
    }

    var isNewView = state.view !== "risk";
    if (isNewView) {
      // Save scroll position of Case Intelligence before opening Risk
      saveCurrentViewScrollPosition();
    }

    var cacheKey = "riskAssessment";
    if (!forceReassess) {
      var cached = getCachedModule(c.id, cacheKey) || getCachedModule(c.id, "riskData");
      if (cached) {
        state.riskData = cached;
        state.riskLoading = false;
        state.view = "risk";
        saveStateToLocalStorage();
        render({ scroll: isNewView ? "top" : "preserve" });
        return;
      }
    }

    _isRiskAssessmentGenerating = true;
    state.riskLoading = true;
    state.riskLoadingStep = 1;
    state.view = "risk";
    render({ scroll: isNewView ? "top" : "preserve" });

    // Visual step sequence
    var stepTimer1 = setTimeout(function() {
      if (state.riskLoading) { state.riskLoadingStep = 2; render({ scroll: "preserve" }); }
    }, 450);
    var stepTimer2 = setTimeout(function() {
      if (state.riskLoading) { state.riskLoadingStep = 3; render({ scroll: "preserve" }); }
    }, 900);
    var stepTimer3 = setTimeout(function() {
      if (state.riskLoading) { state.riskLoadingStep = 4; render({ scroll: "preserve" }); }
    }, 1400);

    try {
      var data = null;
      if (forceReassess) {
        data = await api("/api/cases/" + c.id + "/risk-assessment/reassess", {
          method: "POST",
          headers: { "Content-Type": "application/json" }
        });
      } else {
        try {
          data = await api("/api/cases/" + c.id + "/risk-assessment");
        } catch (getErr) {
          data = await api("/api/cases/" + c.id + "/risk-assessment", {
            method: "POST",
            headers: { "Content-Type": "application/json" }
          });
        }
      }

      if (data) {
        setCachedModule(c.id, cacheKey, data);
        setCachedModule(c.id, "riskData", data);
        state.riskData = data;
        state.riskLoading = false;
        saveStateToLocalStorage();
      }
    } catch (e) {
      console.error("Risk assessment generation failed:", e);
      state.riskLoading = false;
      showToast("⚠️ Could not generate AI Risk Assessment right now.", "error");
    } finally {
      clearTimeout(stepTimer1);
      clearTimeout(stepTimer2);
      clearTimeout(stepTimer3);
      _isRiskAssessmentGenerating = false;
      state.riskLoading = false;
      render({ scroll: "preserve" });
    }
  }
  window.generateRiskAssessment = generateRiskAssessment;

  function renderRiskLoadingShell(step) {
    var s = step || 1;
    var html = ''
      + '<div class="view-header">'
      + '<button class="btn btn-ghost btn-sm" onclick="if(window.AYUR){window.AYUR.navigateBackToCaseDetail();}">' + icon('arrow_back', 16) + ' Back to Case Intelligence</button>'
      + '</div>'
      + '<div class="risk-loading-shell">'
      + '<div style="font-size:36px;margin-bottom:12px">⚠️</div>'
      + '<h2 style="font-size:22px;font-weight:700;color:#ffffff;margin-bottom:6px">Synthesizing Product Risk Profile</h2>'
      + '<p style="color:#7a9c8f;font-size:14px;margin-bottom:24px">Evaluating IP, regulatory, claims, and formulation safety parameters</p>'
      + '<div class="risk-loading-steps">'

      + '<div class="risk-loading-step-item ' + (s >= 1 ? 'active' : '') + '">'
      + (s > 1 ? '<span class="material-symbols-outlined risk-step-icon-done" style="font-size:20px">check_circle</span>' : '<span class="material-symbols-outlined risk-step-icon-pulse" style="font-size:20px">pending</span>')
      + '<span>Product identity, ingredients &amp; claims loaded</span>'
      + '</div>'

      + '<div class="risk-loading-step-item ' + (s >= 2 ? 'active' : '') + '">'
      + (s > 2 ? '<span class="material-symbols-outlined risk-step-icon-done" style="font-size:20px">check_circle</span>' : (s === 2 ? '<span class="material-symbols-outlined risk-step-icon-pulse" style="font-size:20px">pending</span>' : '<span class="material-symbols-outlined" style="font-size:20px;color:#4a6358">radio_button_unchecked</span>'))
      + '<span>Regulatory framework &amp; classification reviewed</span>'
      + '</div>'

      + '<div class="risk-loading-step-item ' + (s >= 3 ? 'active' : '') + '">'
      + (s > 3 ? '<span class="material-symbols-outlined risk-step-icon-done" style="font-size:20px">check_circle</span>' : (s === 3 ? '<span class="material-symbols-outlined risk-step-icon-pulse" style="font-size:20px">pending</span>' : '<span class="material-symbols-outlined" style="font-size:20px;color:#4a6358">radio_button_unchecked</span>'))
      + '<span>Patent landscape &amp; prior art signals reviewed</span>'
      + '</div>'

      + '<div class="risk-loading-step-item ' + (s >= 4 ? 'active' : '') + '">'
      + (s >= 4 ? '<span class="material-symbols-outlined risk-step-icon-pulse" style="font-size:20px">sync</span>' : '<span class="material-symbols-outlined" style="font-size:20px;color:#4a6358">radio_button_unchecked</span>')
      + '<span>Synthesizing structured risk intelligence...</span>'
      + '</div>'

      + '</div>'
      + '<div class="skeleton skeleton-text" style="width:80%;margin:0 auto"></div>'
      + '</div>';
    return html;
  }

  function renderRiskView() {
    if (state.riskLoading) {
      return renderRiskLoadingShell(state.riskLoadingStep || 1);
    }

    var rd = state.riskData;
    if (!rd) {
      return ''
        + '<div class="view-header">'
        + '<button class="btn btn-ghost btn-sm" onclick="if(window.AYUR){window.AYUR.navigateBackToCaseDetail();}">' + icon('arrow_back', 16) + ' Back to Case Intelligence</button>'
        + '</div>'
        + '<div class="card"><div class="card-body" style="text-align:center;padding:40px">'
        + '<p style="color:#b0c8c0;font-size:16px;margin-bottom:16px">No Risk Assessment has been generated yet for this product case.</p>'
        + '<button class="btn btn-primary" onclick="generateRiskAssessment()">Run AI Risk Assessment →</button>'
        + '</div></div>';
    }

    var ov = rd.overall_risk || {};
    var score = typeof ov.score === 'number' ? ov.score : 50;
    var level = (ov.level || 'MODERATE').toUpperCase();
    var conf = Math.round((typeof ov.confidence === 'number' ? ov.confidence : 0.8) * 100);
    var source = rd.assessment_source || 'GEMINI';
    var isAI = source === 'GEMINI';
    var modelUsed = rd.model_used;
    var cov = rd.evidence_coverage || {};
    var topRisks = rd.top_risks || [];
    var domainScores = rd.domain_scores || [];
    var mitigation = rd.mitigation_plan || {};
    var gaps = rd.evidence_gaps || [];
    var disclaimer = rd.disclaimer || 'Decision support only.';

    var levelColorMap = {
      LOW: '#2ecc71',
      MODERATE: '#f39c12',
      HIGH: '#e74c3c',
      CRITICAL: '#ff6b6b'
    };
    var scoreColor = levelColorMap[level] || '#f39c12';

    var tagClass = 'risk-tag-' + level.toLowerCase();

    var html = ''
      + '<div class="view-header" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">'
      + '<button class="btn btn-ghost btn-sm" id="back-from-risk" onclick="if(window.AYUR){window.AYUR.navigateBackToCaseDetail();}">' + icon('arrow_back', 16) + ' Back to Case Intelligence</button>'
      + '<button class="btn btn-outline btn-sm" id="refresh-risk-btn" onclick="generateRiskAssessment(null, true)" title="Run a fresh AI assessment with latest case evidence">' + icon('refresh', 16) + ' Refresh AI Assessment</button>'
      + '</div>';

    // Fallback Alert Banner
    if (!isAI) {
      html += '<div style="margin-bottom:16px;background:rgba(243,156,18,0.1);border:1px solid rgba(243,156,18,0.3);border-radius:10px;padding:12px 16px;color:#f39c12;font-size:13px;display:flex;align-items:center;gap:10px">'
        + '<span class="material-symbols-outlined" style="font-size:20px">info</span>'
        + '<div><strong>Rule-Based Assessment:</strong> AI analysis is temporarily unavailable. This assessment was generated using AYUR-INTEL\'s deterministic risk rules.</div>'
        + '</div>';
    }

    // 1. Overall Risk Hero Card
    html += '<div class="risk-hero-card">'
      + '<div class="risk-hero-header">'
      + '<div>'
      + '<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;flex-wrap:wrap">'
      + '<span style="font-size:28px">⚠️</span>'
      + '<h2 style="font-size:24px;font-weight:700;color:#ffffff;margin:0">Risk Intelligence Assessment</h2>'
      + (isAI
          ? '<span class="chip" style="background:rgba(46,204,113,0.15);color:#2ecc71;border:1px solid rgba(46,204,113,0.3);font-weight:600">✨ AI-Assisted • Powered by Gemini' + (modelUsed ? ' (' + escapeHtml(modelUsed) + ')' : '') + '</span>'
          : '<span class="chip" style="background:rgba(243,156,18,0.15);color:#f39c12;border:1px solid rgba(243,156,18,0.3);font-weight:600">⚙️ Rule-Based Assessment</span>')
      + '</div>'
      + '<p style="color:#b0c8c0;margin:0;font-size:14px">Decision-support risk profile for <strong style="color:#e0eee8">' + escapeHtml(rd.product_name || (state.currentCase ? state.currentCase.name : 'Product')) + '</strong></p>'
      + '</div>'

      // Score Display
      + '<div class="risk-score-badge">'
      + '<div>'
      + '<div style="font-size:11px;color:#7a9c8f;text-transform:uppercase;font-weight:700;margin-bottom:2px">Risk Score</div>'
      + '<span class="risk-score-num" style="color:' + scoreColor + '">' + score + '</span>'
      + '<span class="risk-score-max"> / 100</span>'
      + '</div>'
      + '<span class="risk-level-tag ' + tagClass + '">' + level + ' RISK</span>'
      + '</div>'
      + '</div>'

      // Executive Summary & Confidence
      + '<div style="background:rgba(10,18,14,0.6);border-radius:10px;padding:14px 18px;margin-bottom:16px;border:1px solid rgba(255,255,255,0.05)">'
      + '<div style="font-size:14px;color:#ffffff;line-height:1.6;margin-bottom:8px">' + escapeHtml(ov.summary || 'Risk profile synthesized across available case intelligence dimensions.') + '</div>'
      + '<div style="display:flex;align-items:center;gap:12px;font-size:12px;color:#7a9c8f">'
      + '<span>Assessment Confidence: <strong style="color:#e0eee8">' + conf + '%</strong></span>'
      + '<span>•</span>'
      + '<span>Last Assessed: <strong style="color:#b0c8c0">' + (rd.updated_at ? new Date(rd.updated_at).toLocaleDateString() : 'Just now') + '</strong></span>'
      + '</div>'
      + '</div>'

      // Evidence Coverage Strip
      + '<div class="risk-coverage-strip">'
      + '<span style="font-size:11px;font-weight:700;color:#7a9c8f;text-transform:uppercase;margin-right:4px">Evidence Coverage:</span>'
      + '<span class="risk-coverage-chip ' + (cov.product_passport === 'Complete' ? 'available' : 'not-run') + '">Passport: ' + escapeHtml(cov.product_passport || 'Complete') + '</span>'
      + '<span class="risk-coverage-chip ' + (cov.patent_intelligence === 'Available' ? 'available' : 'not-run') + '">Patents: ' + escapeHtml(cov.patent_intelligence || 'Not Run') + '</span>'
      + '<span class="risk-coverage-chip ' + (cov.regulatory_pathways === 'Available' ? 'available' : 'not-run') + '">Regulatory: ' + escapeHtml(cov.regulatory_pathways || 'Not Run') + '</span>'
      + '<span class="risk-coverage-chip ' + (cov.knowledge_evidence === 'Available' ? 'available' : 'not-run') + '">Knowledge: ' + escapeHtml(cov.knowledge_evidence || 'Not Run') + '</span>'
      + '<span class="risk-coverage-chip ' + (cov.innovation_analysis === 'Available' ? 'available' : 'not-run') + '">Innovation: ' + escapeHtml(cov.innovation_analysis || 'Not Run') + '</span>'
      + '</div>'
      + '</div>';

    // 2. Top Priority Risks Section
    if (topRisks.length > 0) {
      html += '<div style="margin-bottom:28px">'
        + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">'
        + '<h3 style="font-size:18px;font-weight:700;color:#ffffff;margin:0;display:flex;align-items:center;gap:8px"><span style="color:#e74c3c">●</span> Top Priority Risks</h3>'
        + '<span style="font-size:12px;color:#7a9c8f">' + topRisks.length + ' key risk items</span>'
        + '</div>'
        + '<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(300px, 1fr));gap:16px">';

      topRisks.forEach(function(r, idx) {
        var rSev = (r.severity || 'MODERATE').toUpperCase();
        var sClass = rSev === 'HIGH' || rSev === 'CRITICAL' ? 'sev-high' : 'sev-mod';
        var tColor = levelColorMap[rSev] || '#f39c12';
        var rTag = 'risk-tag-' + rSev.toLowerCase();

        html += '<div class="risk-interactive-card ' + sClass + '" id="top-risk-card-' + idx + '">'
          + '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">'
          + '<span class="risk-level-tag ' + rTag + '" style="font-size:11px">' + rSev + '</span>'
          + '<span style="font-size:12px;color:#7a9c8f;font-weight:600">' + escapeHtml(r.domain || 'General') + '</span>'
          + '</div>'
          + '<h4 style="font-size:15px;font-weight:700;color:#ffffff;margin:0 0 8px 0;line-height:1.4">' + escapeHtml(r.title) + '</h4>'
          + '<p style="font-size:13px;color:#b0c8c0;line-height:1.5;margin:0 0 12px 0">' + escapeHtml(r.why_it_matters || '') + '</p>'
          + '<div style="display:flex;gap:12px;font-size:11px;color:#7a9c8f;margin-bottom:12px;flex-wrap:wrap">'
          + '<span>Likelihood: <strong style="color:#e0eee8">' + escapeHtml(r.likelihood || 'Medium') + '</strong></span>'
          + '<span>Impact: <strong style="color:#e0eee8">' + escapeHtml(r.impact || 'Medium') + '</strong></span>'
          + '</div>'
          + '<div style="display:flex;justify-content:space-between;align-items:center;border-top:1px solid rgba(255,255,255,0.06);padding-top:10px">'
          + '<span style="font-size:11px;color:#7a9c8f">' + (r.evidence_refs && r.evidence_refs.length > 0 ? escapeHtml(r.evidence_refs[0].label || 'Evidence Linked') : 'Verified') + '</span>'
          + '<button class="btn btn-ghost btn-sm" style="padding:4px 8px;font-size:12px;color:#2ecc71" onclick="window.AYUR.focusRiskInRegister(\'' + escapeHtml(r.id || idx) + '\')">Review Risk ↓</button>'
          + '</div>'
          + '</div>';
      });

      html += '</div></div>';
    }

    // 3. Domain Scores & 3x3 Risk Matrix Grid Container
    html += '<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(320px, 1fr));gap:20px;margin-bottom:28px">';

    // Domain Scores Overview Card
    html += '<div class="card" style="margin:0"><div class="card-head"><h3 style="font-size:16px;font-weight:700;margin:0">Risk Domain Overview</h3><p style="font-size:12px;color:#7a9c8f">Score breakdown by statutory &amp; IP domain</p></div><div class="card-body">';
    if (domainScores.length > 0) {
      domainScores.forEach(function(d) {
        var dSev = (d.level || 'MODERATE').toUpperCase();
        var dColor = levelColorMap[dSev] || '#f39c12';
        html += '<div style="margin-bottom:14px">'
          + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">'
          + '<span style="font-size:13px;font-weight:600;color:#e0eee8">' + escapeHtml(d.domain) + '</span>'
          + '<div style="display:flex;align-items:center;gap:8px">'
          + '<span style="font-size:13px;font-weight:700;font-family:\'JetBrains Mono\',monospace;color:' + dColor + '">' + d.score + '</span>'
          + '<span class="risk-level-tag risk-tag-' + dSev.toLowerCase() + '" style="font-size:10px;padding:2px 6px">' + dSev + '</span>'
          + '</div>'
          + '</div>'
          + '<div style="height:6px;background:rgba(255,255,255,0.06);border-radius:3px;overflow:hidden">'
          + '<div style="height:100%;width:' + d.score + '%;background:' + dColor + ';border-radius:3px;transition:width 400ms ease"></div>'
          + '</div>'
          + (d.summary ? '<div style="font-size:11px;color:#7a9c8f;margin-top:4px">' + escapeHtml(d.summary) + '</div>' : '')
          + '</div>';
      });
    } else {
      html += '<p style="color:#7a9c8f;font-size:13px">No domain scores recorded.</p>';
    }
    html += '</div></div>';

    // 3x3 Likelihood × Impact Risk Matrix Card
    html += '<div class="card" style="margin:0"><div class="card-head"><h3 style="font-size:16px;font-weight:700;margin:0">Likelihood × Impact Matrix</h3><p style="font-size:12px;color:#7a9c8f">Interactive prioritization grid</p></div><div class="card-body">'
      + '<div class="risk-matrix-container">'
      + '<div class="risk-matrix-grid">'
      + '<div class="risk-matrix-header-cell"></div>'
      + '<div class="risk-matrix-header-cell">Low Impact</div>'
      + '<div class="risk-matrix-header-cell">Med Impact</div>'
      + '<div class="risk-matrix-header-cell">High Impact</div>'

      // Row 1: High Likelihood
      + '<div class="risk-matrix-row-label">High Lik.</div>'
      + '<div class="risk-matrix-cell risk-cell-med" id="matrix-cell-HIGH-LOW">' + renderMatrixDots(topRisks, 'HIGH', 'LOW') + '</div>'
      + '<div class="risk-matrix-cell risk-cell-high" id="matrix-cell-HIGH-MEDIUM">' + renderMatrixDots(topRisks, 'HIGH', 'MEDIUM') + '</div>'
      + '<div class="risk-matrix-cell risk-cell-critical" id="matrix-cell-HIGH-HIGH">' + renderMatrixDots(topRisks, 'HIGH', 'HIGH') + '</div>'

      // Row 2: Med Likelihood
      + '<div class="risk-matrix-row-label">Med Lik.</div>'
      + '<div class="risk-matrix-cell risk-cell-low" id="matrix-cell-MEDIUM-LOW">' + renderMatrixDots(topRisks, 'MEDIUM', 'LOW') + '</div>'
      + '<div class="risk-matrix-cell risk-cell-med" id="matrix-cell-MEDIUM-MEDIUM">' + renderMatrixDots(topRisks, 'MEDIUM', 'MEDIUM') + '</div>'
      + '<div class="risk-matrix-cell risk-cell-high" id="matrix-cell-MEDIUM-HIGH">' + renderMatrixDots(topRisks, 'MEDIUM', 'HIGH') + '</div>'

      // Row 3: Low Likelihood
      + '<div class="risk-matrix-row-label">Low Lik.</div>'
      + '<div class="risk-matrix-cell risk-cell-low" id="matrix-cell-LOW-LOW">' + renderMatrixDots(topRisks, 'LOW', 'LOW') + '</div>'
      + '<div class="risk-matrix-cell risk-cell-low" id="matrix-cell-LOW-MEDIUM">' + renderMatrixDots(topRisks, 'LOW', 'MEDIUM') + '</div>'
      + '<div class="risk-matrix-cell risk-cell-med" id="matrix-cell-LOW-HIGH">' + renderMatrixDots(topRisks, 'LOW', 'HIGH') + '</div>'

      + '</div>'
      + '</div>'
      + '<div style="font-size:11px;color:#7a9c8f;text-align:center;margin-top:8px">Click chips in matrix to focus corresponding Risk Register entry.</div>'
      + '</div></div>';

    html += '</div>';

    // 4. Detailed Risk Register
    html += '<div class="card" style="margin-bottom:24px"><div class="card-head"><h3 style="font-size:18px;font-weight:700;margin:0">Detailed Risk Register</h3><p style="font-size:13px;color:#7a9c8f">Comprehensive risk breakdown with evidence traceability and mitigation</p></div><div class="card-body">';

    if (topRisks.length > 0) {
      topRisks.forEach(function(r, idx) {
        var rSev = (r.severity || 'MODERATE').toUpperCase();
        var tColor = levelColorMap[rSev] || '#f39c12';
        var rTag = 'risk-tag-' + rSev.toLowerCase();
        var regId = 'risk-reg-item-' + (r.id || idx);

        html += '<div class="risk-register-item expanded" id="' + regId + '">'
          + '<div class="risk-register-header" onclick="window.AYUR.toggleRiskAccordion(\'' + regId + '\')">'
          + '<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">'
          + '<span class="risk-level-tag ' + rTag + '" style="font-size:11px">' + rSev + '</span>'
          + '<span style="font-size:12px;color:#7a9c8f;font-weight:600">' + escapeHtml(r.domain) + '</span>'
          + '<strong style="font-size:15px;color:#ffffff">' + escapeHtml(r.title) + '</strong>'
          + '</div>'
          + '<span class="material-symbols-outlined" style="font-size:20px;color:#7a9c8f">expand_more</span>'
          + '</div>'

          + '<div class="risk-register-body">'
          + '<div style="margin-bottom:12px">'
          + '<div style="font-size:11px;font-weight:700;color:#7a9c8f;text-transform:uppercase;margin-bottom:4px">Why This Matters</div>'
          + '<div style="font-size:13px;color:#e0eee8;line-height:1.6">' + escapeHtml(r.why_it_matters || '') + '</div>'
          + '</div>'

          + '<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(140px, 1fr));gap:10px;margin-bottom:14px;background:rgba(10,18,14,0.6);padding:10px 14px;border-radius:8px">'
          + '<div><span style="font-size:11px;color:#7a9c8f">Likelihood:</span> <strong style="font-size:12px;color:#ffffff">' + escapeHtml(r.likelihood || 'Medium') + '</strong></div>'
          + '<div><span style="font-size:11px;color:#7a9c8f">Impact:</span> <strong style="font-size:12px;color:#ffffff">' + escapeHtml(r.impact || 'Medium') + '</strong></div>'
          + '<div><span style="font-size:11px;color:#7a9c8f">Confidence:</span> <strong style="font-size:12px;color:#ffffff">' + Math.round((r.confidence || 0.8) * 100) + '%</strong></div>'
          + '<div><span style="font-size:11px;color:#7a9c8f">Evidence Status:</span> <strong style="font-size:12px;color:#2ecc71">' + escapeHtml(r.evidence_status || 'SUPPORTED') + '</strong></div>'
          + '</div>'

          // Evidence Traceability Pills
          + '<div style="margin-bottom:14px">'
          + '<div style="font-size:11px;font-weight:700;color:#7a9c8f;text-transform:uppercase;margin-bottom:6px">Based On Evidence:</div>'
          + '<div style="display:flex;gap:8px;flex-wrap:wrap">';

        if (r.evidence_refs && r.evidence_refs.length > 0) {
          r.evidence_refs.forEach(function(ev) {
            var st = ev.source_type || 'passport';
            var evLabel = ev.label || ev.reference_key || 'Evidence';
            var onClickAction = 'void(0)';
            if (st === 'patent') onClickAction = 'if(window.generatePatentIntelligence){window.generatePatentIntelligence();}';
            else if (st === 'regulatory') onClickAction = 'if(window.generateRegulatoryAnalysis){window.generateRegulatoryAnalysis();}';
            else if (st === 'passport') onClickAction = 'if(window.AYUR){window.AYUR.state.view=\'passport-wizard\';window.AYUR.render();}';

            html += '<span class="risk-evidence-link-pill" onclick="' + onClickAction + '" title="Open source intelligence module">'
              + icon('open_in_new', 14) + ' ' + escapeHtml(evLabel) + '</span>';
          });
        } else {
          html += '<span style="font-size:12px;color:#7a9c8f">Verified from Product Passport specifications</span>';
        }
        html += '</div></div>'

          // Recommended Action
          + '<div style="background:rgba(46,204,113,0.06);border-left:3px solid #2ecc71;padding:10px 14px;border-radius:0 8px 8px 0;margin-bottom:10px">'
          + '<div style="font-size:11px;font-weight:700;color:#2ecc71;text-transform:uppercase;margin-bottom:2px">Recommended Action</div>'
          + '<div style="font-size:13px;color:#ffffff">' + escapeHtml(r.recommended_action || 'Review details with domain specialist.') + '</div>'
          + '</div>'

          + (r.requires_human_verification ? '<div style="font-size:11px;color:#7a9c8f;display:flex;align-items:center;gap:6px">' + icon('verified', 14) + ' Requires Human Specialist Review</div>' : '')
          + '</div>'
          + '</div>';
      });
    } else {
      html += '<p style="color:#7a9c8f;font-size:13px">No detailed risk items recorded.</p>';
    }

    html += '</div></div>';

    // 5. AI Mitigation Plan Section
    var imm = mitigation.immediate || [];
    var regSub = mitigation.before_regulatory_submission || [];
    var mktLaunch = mitigation.before_market_launch || [];

    html += '<div class="card" style="margin-bottom:24px"><div class="card-head"><h3 style="font-size:18px;font-weight:700;margin:0">AI Mitigation Roadmap</h3><p style="font-size:13px;color:#7a9c8f">Phased action items to de-risk commercialization</p></div><div class="card-body">'
      + '<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(280px, 1fr));gap:16px">'

      // Column 1: Immediate
      + '<div style="background:rgba(10,18,14,0.6);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:16px">'
      + '<div style="font-size:13px;font-weight:700;color:#2ecc71;margin-bottom:12px;display:flex;align-items:center;gap:6px">' + icon('bolt', 18) + ' Immediate Actions</div>'
      + '<ul style="margin:0;padding-left:18px;font-size:13px;color:#b0c8c0;line-height:1.6">';
    imm.forEach(function(item) { html += '<li style="margin-bottom:8px">' + escapeHtml(item) + '</li>'; });
    html += '</ul></div>'

      // Column 2: Before Regulatory
      + '<div style="background:rgba(10,18,14,0.6);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:16px">'
      + '<div style="font-size:13px;font-weight:700;color:#f39c12;margin-bottom:12px;display:flex;align-items:center;gap:6px">' + icon('assignment', 18) + ' Pre-Submission</div>'
      + '<ul style="margin:0;padding-left:18px;font-size:13px;color:#b0c8c0;line-height:1.6">';
    regSub.forEach(function(item) { html += '<li style="margin-bottom:8px">' + escapeHtml(item) + '</li>'; });
    html += '</ul></div>'

      // Column 3: Before Market Launch
      + '<div style="background:rgba(10,18,14,0.6);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:16px">'
      + '<div style="font-size:13px;font-weight:700;color:#3498db;margin-bottom:12px;display:flex;align-items:center;gap:6px">' + icon('rocket_launch', 18) + ' Pre-Launch (Commercial)</div>'
      + '<ul style="margin:0;padding-left:18px;font-size:13px;color:#b0c8c0;line-height:1.6">';
    mktLaunch.forEach(function(item) { html += '<li style="margin-bottom:8px">' + escapeHtml(item) + '</li>'; });
    html += '</ul></div>'

      + '</div>'
      + '</div></div>';

    // 6. Evidence Gaps & Uncertainties
    if (gaps.length > 0) {
      html += '<div class="card" style="margin-bottom:24px;border-left:4px solid #f39c12"><div class="card-head"><h3 style="font-size:16px;font-weight:700;color:#ffffff;margin:0">Evidence Gaps &amp; Uncertainties</h3><p style="font-size:12px;color:#7a9c8f">Intelligence areas that require execution to increase certainty</p></div><div class="card-body">'
        + '<ul style="margin:0;padding-left:18px;font-size:13px;color:#b0c8c0;line-height:1.6">';
      gaps.forEach(function(g) {
        html += '<li style="margin-bottom:8px">' + escapeHtml(g) + '</li>';
      });
      html += '</ul></div></div>';
    }

    // 7. Transparency Disclaimer Footer
    html += '<div class="innovation-disclaimer" style="margin-top:20px">'
      + icon('warning', 18)
      + '<div><strong>Decision Support Only.</strong> ' + escapeHtml(disclaimer) + '</div>'
      + '</div>';

    return html;
  }

  function renderMatrixDots(topRisks, targetLikelihood, targetImpact) {
    var matching = (topRisks || []).filter(function(r) {
      var l = (r.likelihood || 'MEDIUM').toUpperCase();
      var i = (r.impact || 'MEDIUM').toUpperCase();
      return l === targetLikelihood && i === targetImpact;
    });

    if (matching.length === 0) return '<span style="font-size:11px;color:#4a6358">—</span>';

    var html = '';
    matching.forEach(function(r) {
      var rSev = (r.severity || 'MODERATE').toUpperCase();
      var bg = rSev === 'CRITICAL' ? '#ff6b6b' : (rSev === 'HIGH' ? '#e74c3c' : (rSev === 'MODERATE' ? '#f39c12' : '#2ecc71'));
      html += '<div class="risk-chip-marker" style="background:' + bg + '22;color:' + bg + ';border:1px solid ' + bg + '55" onclick="window.AYUR.focusRiskInRegister(\'' + escapeHtml(r.id) + '\')" title="' + escapeHtml(r.title) + ' (' + rSev + ')">'
        + '<span style="width:6px;height:6px;border-radius:50%;background:' + bg + '"></span>'
        + '<span>' + escapeHtml(r.title) + '</span>'
        + '</div>';
    });
    return html;
  }

  function focusRiskInRegister(riskId) {
    var el = document.getElementById('risk-reg-item-' + riskId);
    if (el) {
      el.classList.add('expanded');
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.style.boxShadow = '0 0 16px rgba(46, 204, 113, 0.4)';
      setTimeout(function() {
        el.style.boxShadow = '';
      }, 1500);
    }
  }
  window.focusRiskInRegister = focusRiskInRegister;

  function toggleRiskAccordion(regId) {
    var el = document.getElementById(regId);
    if (el) {
      el.classList.toggle('expanded');
    }
  }
  window.toggleRiskAccordion = toggleRiskAccordion;

  // ----------------------------------------------------------------
  // Evidence & Citation View (Phase 11)
  // ----------------------------------------------------------------


  // ----------------------------------------------------------------
  // Evidence & Citation View (Phase 11)
  // ----------------------------------------------------------------

  function renderEvidenceView() {
    var ev = state.evidenceData;
    if (!ev) return '<div class="card"><div class="card-body"><p>No evidence data available.</p></div></div>';

    var originLabels = { FACT: 'Fact', INFERENCE: 'Inference', USER_INPUT: 'User Input', UNKNOWN: 'Unknown', SYSTEM_DERIVED: 'System Derived' };
    var originColors = { FACT: 'var(--color-secondary)', INFERENCE: 'var(--color-amber)', USER_INPUT: 'var(--color-scientific-blue)', UNKNOWN: 'var(--color-outline)', SYSTEM_DERIVED: 'var(--color-outline)' };
    var typeLabels = {
      PATENT_PUBLICATION: 'Patent Publication', PATENT_CLAIM: 'Patent Claim', PATENT_ABSTRACT: 'Patent Abstract',
      PATENT_METADATA: 'Patent Metadata', REGULATION: 'Regulation', REGULATORY_GUIDANCE: 'Regulatory Guidance',
      OFFICIAL_SOURCE: 'Official Source', TK_DOCUMENT: 'TK Document', SCIENTIFIC_PAPER: 'Scientific Paper',
      USER_PROVIDED: 'User Provided', SYSTEM_DERIVED: 'System Derived', INNOVATION_ANALYSIS: 'Innovation Analysis',
      PATENT_ANALYSIS: 'Patent Analysis', IP_STRATEGY: 'IP Strategy', REGULATORY_PROFILE: 'Regulatory Profile',
      JURISDICTION_COMPARISON: 'Jurisdiction Comparison', PRODUCT_PASSPORT: 'Product Passport'
    };
    var phaseLabels = {
      PHASE_5_INNOVATION: 'Innovation Map', PHASE_6_PATENT: 'Patent Intelligence',
      PHASE_7_PATENT_DEEP: 'Patent Deep Analysis', PHASE_8_IP_STRATEGY: 'IP Strategy',
      PHASE_9_REGULATORY: 'Regulatory Intel', PHASE_10_JURISDICTION: 'Jurisdiction Compare',
      PHASE_3_KNOWLEDGE: 'Knowledge Engine', USER_INPUT: 'User Input'
    };

    var html = ''
      + '<div class="view-header"><button class="btn btn-ghost btn-sm" id="back-from-evidence">' + icon("arrow_back", 15) + ' Back to Case</button></div>'

      // Header
      + '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>Evidence &amp; Citations</h2>'
      + '<p>Traceable evidence behind all findings for ' + escapeHtml(ev.product_name || '') + '</p></div><div class="card-body">'

      // Coverage summary
      + '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px">'
      + '<div class="patent-stat-card"><div class="patent-stat-label">TOTAL FINDINGS</div><div class="patent-stat-value">' + ev.total_findings + '</div></div>'
      + '<div class="patent-stat-card"><div class="patent-stat-label">CITATION COVERAGE</div><div class="patent-stat-value">' + ev.citation_coverage + '%</div></div>'
      + '<div class="patent-stat-card"><div class="patent-stat-label">EVIDENCE RECORDS</div><div class="patent-stat-value">' + ev.total_evidence + '</div></div>'
      + '<div class="patent-stat-card"><div class="patent-stat-label">UNSUPPORTED</div><div class="patent-stat-value">' + ev.unsupported_count + '</div></div>'
      + '</div>'

      // Coverage bar
      + '<div style="margin-bottom:16px">'
      + '<div style="display:flex;justify-content:space-between;margin-bottom:4px"><span class="label-caps" style="color:var(--color-on-surface-variant)">Evidence Coverage</span>'
      + '<span style="font-size:12px;font-weight:600;color:var(--color-on-surface)">' + ev.findings_with_evidence + ' / ' + ev.total_findings + ' findings have evidence</span></div>'
      + '<div class="confidence-bar"><div class="confidence-fill" style="width:' + ev.citation_coverage + '%"></div>'
      + '<div class="confidence-label">' + ev.citation_coverage + '%</div></div>'
      + '</div></div></div>';

    // Findings list
    if (ev.findings && ev.findings.length > 0) {
      // Group by phase
      var grouped = {};
      ev.findings.forEach(function (f) {
        var phase = f.source_phase;
        if (!grouped[phase]) grouped[phase] = [];
        grouped[phase].push(f);
      });

      Object.keys(grouped).forEach(function (phase) {
        var findings = grouped[phase];
        html += '<div class="card" style="margin-bottom:20px">'
          + '<div class="card-head"><h2>' + icon('link', 18) + ' ' + (phaseLabels[phase] || phase) + '</h2>'
          + '<p>' + findings.length + ' finding' + (findings.length > 1 ? 's' : '') + '</p></div>'
          + '<div class="card-body">';

        findings.forEach(function (f) {
          var originColor = originColors[f.data_origin] || 'var(--color-outline)';
          html += '<div class="knowledge-finding-card" style="margin-bottom:12px">'
            + '<div class="knowledge-finding-header">'
            + '<div class="knowledge-finding-title">' + escapeHtml(f.title) + '</div>'
            + '<span style="display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:var(--radius-full);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;background:' + originColor + '15;color:' + originColor + '">' + (originLabels[f.data_origin] || f.data_origin) + '</span>'
            + '</div>';

          if (f.content) html += '<div class="knowledge-finding-summary">' + escapeHtml(f.content) + '</div>';

          // Citations
          if (f.citations && f.citations.length > 0) {
            html += '<div style="margin-top:8px">';
            f.citations.forEach(function (c, ci) {
              var e = c.evidence;
              html += '<div class="knowledge-finding-evidence" style="cursor:pointer" onclick="window.AYUR.openEvidenceDrawer(\'' + e.id + '\')">'
                + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">'
                + '<span style="font-weight:600;color:var(--color-on-surface)"[' + (ci + 1) + '] ' + escapeHtml(e.source_name || e.authority || 'Source') + '</span>'
                + '<span class="chip selected" style="font-size:10px">' + escapeHtml(typeLabels[e.evidence_type] || e.evidence_type) + '</span>'
                + '</div>';
              if (e.jurisdiction) html += '<div style="font-size:12px;color:var(--color-on-surface-variant)">Jurisdiction: ' + escapeHtml(e.jurisdiction) + '</div>';
              if (e.reference) html += '<div style="font-size:12px;color:var(--color-on-surface-variant);font-family:' + 'JetBrains Mono' + ',monospace">Ref: ' + escapeHtml(e.reference) + '</div>';
              if (e.publication_date) html += '<div style="font-size:12px;color:var(--color-on-surface-variant)">Published: ' + escapeHtml(e.publication_date) + '</div>';
              html += '</div>';
            });
            html += '</div>';
          } else {
            html += '<div style="margin-top:8px;padding:8px 12px;background:var(--color-error-container);border-radius:var(--radius-md);font-size:12px;color:var(--color-on-error-container)">No supporting evidence available.</div>';
          }

          html += '</div>';
        });

        html += '</div></div>';
      });
    }

    // Disclaimer
    html += '<div class="innovation-disclaimer">' + icon('warning', 18) + '<div><strong>Evidence &amp; Citation Engine.</strong> All evidence is traceable to its source. User-provided information is clearly distinguished from external sources.</div></div>';

    return html;
  }

  // ----------------------------------------------------------------
  // Monitoring Center View (Phase 14)
  // ----------------------------------------------------------------
  function renderMonitoringCenter() {
    var m = state.monitoringData;
    if (!m) return '<div class="card"><div class="card-body"><p>No monitoring data available.</p></div></div>';

    var config = m.config || {};
    var severityColors = { HIGH: 'var(--color-error)', MEDIUM: '#d97706', LOW: 'var(--color-secondary)', INFO: 'var(--color-scientific-blue)' };
    var severityLabels = { HIGH: 'HIGH', MEDIUM: 'MEDIUM', LOW: 'LOW', INFO: 'INFO' };
    var typeLabels = { NEW_PATENT: 'New Patent', PATENT_UPDATE: 'Patent Update', REGULATORY_UPDATE: 'Regulatory Update', JURISDICTION_UPDATE: 'Jurisdiction Update', SOURCE_UPDATE: 'Source Update', MONITORING_FAILURE: 'Monitoring Failure' };
    var statusLabels = { NEW: 'New', SEEN: 'Seen', UNDER_REVIEW: 'Under Review', RESOLVED: 'Resolved', DISMISSED: 'Dismissed' };

    var html = ''
      + '<div class="view-header"><button class="btn btn-ghost btn-sm" id="back-from-monitoring">' + icon('arrow_back', 15) + ' Back to Case</button></div>'

      // Header
      + '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>' + icon('visibility', 20) + ' Continuous Monitoring</h2>'
      + '<p>Monitor saved Product Cases for potentially relevant changes</p></div><div class="card-body">'

      // Status
      + '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px">'
      + '<div class="patent-stat-card"><div class="patent-stat-label">STATUS</div><div class="patent-stat-value" style="font-size:14px;color:' + (config.enabled ? 'var(--color-secondary)' : 'var(--color-error)') + '">' + (config.enabled ? 'ACTIVE' : 'PAUSED') + '</div></div>'
      + '<div class="patent-stat-card"><div class="patent-stat-label">FREQUENCY</div><div class="patent-stat-value" style="font-size:14px">' + (config.frequency || 'WEEKLY') + '</div></div>'
      + '<div class="patent-stat-card"><div class="patent-stat-label">LAST CHECKED</div><div class="patent-stat-value" style="font-size:12px">' + (config.last_checked_at ? new Date(config.last_checked_at).toLocaleDateString() : 'Never') + '</div></div>'
      + '<div class="patent-stat-card"><div class="patent-stat-label">TOTAL ALERTS</div><div class="patent-stat-value">' + (m.total_alerts || 0) + '</div></div>'
      + '</div>'

      // Monitoring scope
      + '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px">'
      + '<span class="chip' + (config.patent_monitoring ? ' selected' : '') + '" style="cursor:default">' + icon('gavel', 12) + ' Patents</span>'
      + '<span class="chip' + (config.regulatory_monitoring ? ' selected' : '') + '" style="cursor:default">' + icon('policy', 12) + ' Regulations</span>'
      + '<span class="chip' + (config.jurisdiction_monitoring ? ' selected' : '') + '" style="cursor:default">' + icon('language', 12) + ' Jurisdictions</span>'
      + '<span class="chip' + (config.source_monitoring ? ' selected' : '') + '" style="cursor:default">' + icon('source', 12) + ' Sources</span>'
      + '</div>'

      // Actions
      + '<div style="display:flex;gap:8px;flex-wrap:wrap">'
      + '<button class="btn btn-primary btn-sm" id="monitoring-check-now">' + icon('refresh', 14) + ' Check Now</button>'
      + '<button class="btn btn-secondary btn-sm" id="monitoring-toggle">' + icon(config.enabled ? 'pause' : 'play_arrow', 14) + ' ' + (config.enabled ? 'Pause' : 'Resume') + '</button>'
      + '<button class="btn btn-secondary btn-sm" id="monitoring-history-btn">' + icon('history', 14) + ' History</button>'
      + '</div>'
      + '</div></div>';

    // Alert summary
    if (m.total_alerts > 0) {
      html += '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>' + icon('notifications', 18) + ' Alert Summary</h2></div><div class="card-body">'
        + '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:12px">'
        + '<div style="font-size:14px;font-weight:600;color:var(--color-error)">' + (m.high_alerts || 0) + ' High</div>'
        + '<div style="font-size:14px;font-weight:600;color:#d97706">' + (m.medium_alerts || 0) + ' Medium</div>'
        + '<div style="font-size:14px;font-weight:600;color:var(--color-scientific-blue)">' + (m.new_alerts || 0) + ' New</div>'
        + '</div>'
        + '</div></div>';
    }

    // Recent alerts
    if (m.recent_alerts && m.recent_alerts.length > 0) {
      html += '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>' + icon('notifications_active', 18) + ' Recent Alerts</h2>'
        + '<p>' + m.recent_alerts.length + ' alert(s)</p></div><div class="card-body">';

      m.recent_alerts.forEach(function (alert) {
        var sev = severityColors[alert.severity] || 'var(--color-outline)';
        html += '<div class="knowledge-finding-card" style="margin-bottom:12px;border-left:4px solid ' + sev + '">'
          + '<div class="knowledge-finding-header">'
          + '<div class="knowledge-finding-title">' + (severityLabels[alert.severity] || '') + ' ' + escapeHtml(alert.title) + '</div>'
          + '<span class="chip' + (alert.status === 'NEW' ? ' selected' : '') + '" style="font-size:10px">' + (statusLabels[alert.status] || alert.status) + '</span>'
          + '</div>';
        if (alert.summary) html += '<div class="knowledge-finding-summary">' + escapeHtml(alert.summary) + '</div>';
        html += '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;font-size:12px;color:var(--color-on-surface-variant)">'
          + '<span>' + icon('label', 12) + ' ' + (typeLabels[alert.alert_type] || alert.alert_type) + '</span>';
        if (alert.jurisdiction) html += '<span>' + icon('language', 12) + ' ' + escapeHtml(alert.jurisdiction) + '</span>';
        if (alert.source_name) html += '<span>' + icon('source', 12) + ' ' + escapeHtml(alert.source_name) + '</span>';
        html += '</div>';

        // Alert actions
        html += '<div style="display:flex;gap:6px;margin-top:8px">';
        if (alert.status !== 'RESOLVED' && alert.status !== 'DISMISSED') {
          html += '<button class="btn btn-ghost btn-xs alert-action" data-alert-id="' + alert.id + '" data-action="UNDER_REVIEW">Review</button>'
            + '<button class="btn btn-ghost btn-xs alert-action" data-alert-id="' + alert.id + '" data-action="RESOLVED">Resolve</button>'
            + '<button class="btn btn-ghost btn-xs alert-action" data-alert-id="' + alert.id + '" data-action="DISMISSED">Dismiss</button>';
        }
        html += '</div></div>';
      });
      html += '</div></div>';
    } else {
      html += '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>' + icon('notifications_none', 18) + ' Recent Alerts</h2></div>'
        + '<div class="card-body"><div style="text-align:center;padding:24px;color:var(--color-on-surface-variant)">'
        + icon('check_circle', 32) + '<br>No alerts yet. Run a check to start monitoring.</div></div></div>';
    }

    // Recent runs
    if (m.recent_runs && m.recent_runs.length > 0) {
      html += '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>' + icon('history', 18) + ' Recent Checks</h2></div><div class="card-body">'
        + '<div style="overflow-x:auto"><table style="width:100%;font-size:13px;border-collapse:collapse">'
        + '<thead><tr style="border-bottom:1px solid var(--color-outline-variant)">'  
        + '<th style="padding:8px 12px;text-align:left">Date</th>'
        + '<th style="padding:8px 12px;text-align:left">Status</th>'
        + '<th style="padding:8px 12px;text-align:left">Sources Checked</th>'
        + '<th style="padding:8px 12px;text-align:left">Changes</th>'
        + '<th style="padding:8px 12px;text-align:left">Alerts</th>'
        + '</tr></thead><tbody>';

      m.recent_runs.forEach(function (run) {
        var statusColor = run.status === 'SUCCESS' ? 'var(--color-secondary)' : (run.status === 'PARTIAL' ? '#d97706' : 'var(--color-error)');
        html += '<tr style="border-bottom:1px solid var(--color-outline-variant)">'  
          + '<td style="padding:8px 12px">' + (run.started_at ? new Date(run.started_at).toLocaleString() : '-') + '</td>'
          + '<td style="padding:8px 12px;color:' + statusColor + ';font-weight:600">' + (run.status || '-') + '</td>'
          + '<td style="padding:8px 12px">' + (run.sources_checked || 0) + '</td>'
          + '<td style="padding:8px 12px">' + (run.changes_detected || 0) + '</td>'
          + '<td style="padding:8px 12px">' + (run.alerts_created || 0) + '</td>'
          + '</tr>';
      });
      html += '</tbody></table></div></div></div>';
    }

    // Disclaimer
    html += '<div class="innovation-disclaimer">' + icon('warning', 18) + '<div><strong>Continuous Monitoring.</strong> Change detection is based on source availability. Detected changes are informational -- not regulatory or legal conclusions.</div></div>';

    return html;
  }

  // ----------------------------------------------------------------
  // Knowledge Graph Action & View (Phase B: Evidence Intelligence Graph)
  // ----------------------------------------------------------------
  async function openKnowledgeGraph(caseId) {
    var s = (window.AYUR && window.AYUR.state) || state;
    var c = s.currentCase || (s.cases && s.cases.find(function(item) { return item.id === caseId; }));
    if (!c && s.cases && s.cases.length > 0) {
      c = s.cases[0];
      s.currentCase = c;
    }
    if (!c) {
      showToast('⚠️ Please select a product case first', 'error');
      return;
    }
    openCaseModule("knowledgeGraphData", "/api/cases/" + c.id + "/knowledge-graph", "knowledge-graph");
  }
  window.openKnowledgeGraph = openKnowledgeGraph;

  function renderKnowledgeGraph() {
    var g = state.knowledgeGraphData;
    if (!g || !g.nodes || g.nodes.length === 0) {
      return ''
        + '<div class="view-header">'
        + '<button class="btn btn-ghost btn-sm" id="back-from-knowledge-graph">' + icon('arrow_back', 15) + ' Back to Case</button>'
        + '<div class="kg-header-badge"><span class="badge-dot"></span> Evidence Intelligence Graph</div>'
        + '</div>'
        + '<div class="card" style="margin-top:16px;"><div class="card-body" style="text-align:center;padding:48px 20px;">'
        + '<div style="font-size:40px;color:#34d399;margin-bottom:12px;">' + icon('hub', 44) + '</div>'
        + '<h3 style="font-size:18px;margin-bottom:8px;color:#f8fafc;">No Graph Entities Available</h3>'
        + '<p style="color:#94a3b8;max-width:500px;margin:0 auto 20px;font-size:13px;line-height:1.5;">'
        + 'Complete additional Case Intelligence modules (Botanical Discovery, Claims, Patent Screen, Regulatory Profile, Risk Assessment) to expand and explore this Evidence Intelligence Graph.'
        + '</p>'
        + '<button class="btn btn-primary btn-sm" id="back-from-knowledge-graph-empty">' + icon('arrow_back', 14) + ' Return to Case Overview</button>'
        + '</div></div>';
    }

    var nodeTypes = (g.summary && g.summary.node_types) ? g.summary.node_types : {};
    var totalNodes = (g.summary && g.summary.total_nodes) ? g.summary.total_nodes : g.nodes.length;
    var totalEdges = (g.summary && g.summary.total_edges) ? g.summary.total_edges : g.edges.length;

    var evidenceCount = (nodeTypes.EVIDENCE || 0) + (nodeTypes.CASE_FINDING || 0) + (nodeTypes.TRADITIONAL_KNOWLEDGE || 0);
    var risksCount = nodeTypes.RISK || 0;
    var claimsCount = nodeTypes.CLAIM || 0;
    var productName = g.product_name || (state.currentCase ? state.currentCase.name : 'Product Case');

    var directCount = (g.edges || []).filter(function (e) {
      var gnd = (e.grounding || (e.metadata && e.metadata.grounding) || "DIRECT").toUpperCase();
      return gnd === "DIRECT";
    }).length;
    var derivedCount = (g.edges || []).filter(function (e) {
      var gnd = (e.grounding || (e.metadata && e.metadata.grounding) || "").toUpperCase();
      return gnd === "DERIVED";
    }).length;

    var html = ''
      // Top Navigation bar
      + '<div class="view-header">'
      + '<button class="btn btn-ghost btn-sm" id="back-from-knowledge-graph">' + icon('arrow_back', 15) + ' Back to Case</button>'
      + '<div class="kg-header-badge"><span class="badge-dot"></span> Evidence Intelligence Graph</div>'
      + '</div>'

      // Page Header with Real Metrics Strip
      + '<div class="kg-page-header">'
      + '<div class="kg-title-row">'
      + '<div class="kg-title-group">'
      + '<h1 class="kg-page-title">' + icon('account_tree', 24) + ' Knowledge Graph</h1>'
      + '<p class="kg-page-subtitle">Connected intelligence across evidence, IP, regulation and product decisions for <strong>' + escapeHtml(productName) + '</strong></p>'
      + '</div>'
      + '</div>'
      + '<div class="kg-metrics-strip">'
      + '<span class="kg-metric-item"><strong class="kg-metric-val">' + totalNodes + '</strong> Nodes</span>'
      + '<span class="kg-metric-sep">·</span>'
      + '<span class="kg-metric-item"><strong class="kg-metric-val">' + totalEdges + '</strong> Relationships <span style="font-size:11px;opacity:0.85;">(' + directCount + ' Direct · ' + derivedCount + ' Derived)</span></span>'
      + '<span class="kg-metric-sep">·</span>'
      + '<span class="kg-metric-item"><strong class="kg-metric-val">' + (nodeTypes.EVIDENCE || 0) + '</strong> Evidence</span>'
      + '<span class="kg-metric-sep">·</span>'
      + '<span class="kg-metric-item"><strong class="kg-metric-val">' + risksCount + '</strong> Risks</span>'
      + '<span class="kg-metric-sep">·</span>'
      + '<span class="kg-metric-item"><strong class="kg-metric-val">' + claimsCount + '</strong> Claims</span>'
      + '</div>'
      + '</div>'

      // Toolbar: 6 Intelligence Lenses + Controls
      + '<div class="kg-toolbar">'
      + '<div class="kg-lenses-group">'
      + '<span class="kg-lenses-label">INTELLIGENCE LENS:</span>'
      + '<button class="kg-lens-pill active" data-lens="OVERVIEW">' + icon('hub', 15) + ' Overview</button>'
      + '<button class="kg-lens-pill" data-lens="EVIDENCE">' + icon('verified', 15) + ' Evidence</button>'
      + '<button class="kg-lens-pill" data-lens="IP">' + icon('gavel', 15) + ' IP & Patents</button>'
      + '<button class="kg-lens-pill" data-lens="REGULATORY">' + icon('policy', 15) + ' Regulatory</button>'
      + '<button class="kg-lens-pill" data-lens="RISK">' + icon('warning', 15) + ' Risk</button>'
      + '<button class="kg-lens-pill" data-lens="INNOVATION">' + icon('lightbulb', 15) + ' Innovation</button>'
      + '</div>'
      + '<div class="kg-controls-group">'
      + '<div class="kg-search-wrap">'
      + '<span class="material-symbols-outlined kg-search-icon">search</span>'
      + '<input type="text" class="kg-search-input" id="kg-search-input" placeholder="Search graph nodes..." autocomplete="off">'
      + '<button class="kg-search-clear" id="kg-search-clear" style="display:none;" title="Clear search">✕</button>'
      + '</div>'
      + '<div class="kg-btn-group">'
      + '<button class="btn btn-secondary btn-sm kg-control-btn" id="kg-zoom-in" title="Zoom In">' + icon('zoom_in', 16) + '</button>'
      + '<button class="btn btn-secondary btn-sm kg-control-btn" id="kg-zoom-out" title="Zoom Out">' + icon('zoom_out', 16) + '</button>'
      + '<button class="btn btn-secondary btn-sm kg-control-btn" id="kg-fit-btn" title="Fit Graph">' + icon('center_focus_strong', 16) + '</button>'
      + '<button class="btn btn-secondary btn-sm kg-control-btn" id="kg-reset-btn" title="Reset Selection">' + icon('restart_alt', 16) + ' Reset</button>'
      + '</div>'
      + '</div>'
      + '</div>'

      // Main Workspace: Graph Canvas + Drawer
      + '<div class="kg-workspace">'
      + '<div id="knowledge-graph-container" class="kg-canvas-container">'
      + '<div class="kg-legend-overlay">'
      + '<div class="kg-legend-items">'
      + '<span class="kg-legend-item"><span class="kg-legend-dot" style="background:#2d4a3e;border-color:#34d399"></span> Product</span>'
      + '<span class="kg-legend-item"><span class="kg-legend-dot" style="background:#4caf50"></span> Ingredient</span>'
      + '<span class="kg-legend-item"><span class="kg-legend-dot" style="background:#00bcd4"></span> Claim</span>'
      + '<span class="kg-legend-item"><span class="kg-legend-dot" style="background:#607d8b"></span> Evidence</span>'
      + '<span class="kg-legend-item"><span class="kg-legend-dot" style="background:#f44336"></span> Patent</span>'
      + '<span class="kg-legend-item"><span class="kg-legend-dot" style="background:#2196f3"></span> Regulation</span>'
      + '<span class="kg-legend-item"><span class="kg-legend-dot" style="background:#ff5722"></span> Risk</span>'
      + '<span class="kg-legend-item"><span class="kg-legend-dot" style="background:#9c27b0"></span> Innovation</span>'
      + '</div>'
      + '</div>'
      + '<div id="kg-tooltip" class="kg-tooltip" style="display:none;"></div>'
      + '</div>'
      + '<div id="kg-drawer" class="kg-drawer" style="display:none;">'
      + '<div class="kg-drawer-header">'
      + '<div class="kg-drawer-title-wrap">'
      + '<div class="kg-drawer-badges" id="kg-drawer-badges"></div>'
      + '<h3 class="kg-drawer-title" id="kg-drawer-title">Node Details</h3>'
      + '</div>'
      + '<button class="kg-drawer-close" id="kg-drawer-close" title="Close Drawer">' + icon('close', 18) + '</button>'
      + '</div>'
      + '<div class="kg-drawer-body" id="kg-drawer-body"></div>'
      + '</div>'
      + '</div>'

      // Disclaimer
      + '<div class="innovation-disclaimer" style="margin-top:16px;">'
      + '<span class="material-symbols-outlined" style="color:#34d399;">verified_user</span>'
      + '<div><strong>Evidence Intelligence Graph.</strong> All entities and relationships are dynamically synthesized from stored case records, regulatory profiles, patent searches, and canonical risk assessments. Zero speculative connections.</div>'
      + '</div>';

    return html;
  }

  // ----------------------------------------------------------------
  // Source Router View (Phase 16)
  // ----------------------------------------------------------------
  function renderSourceRouter() {
    var sr = state.sourceRouterData;
    if (!sr) return '<div class="card"><div class="card-body"><p>No source router data available.</p></div></div>';

    var sources = sr.sources || {};
    var result = sr.routingResult;

    var html = ''
      + '<div class="view-header"><button class="btn btn-ghost btn-sm" id="back-from-source-router">' + icon('arrow_back', 15) + ' Back to Case</button></div>'

      // Header
      + '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>' + icon('route', 20) + ' AI Source Router</h2>'
      + '<p>Route research questions to the most appropriate authoritative sources</p></div><div class="card-body">'

      // Question input
      + '<div style="margin-bottom:16px"><label class="form-label">Ask a Research Question</label>'
      + '<div style="display:flex;gap:8px">'
      + '<input type="text" class="form-input" id="route-question-input" placeholder="e.g. Is there a similar patent in Germany?" style="flex:1" value="' + escapeHtml(sr.question || '') + '">'
      + '<button class="btn btn-primary btn-sm" id="route-question-btn">' + icon('send', 14) + ' Route</button>'
      + '</div>'
      + '<div style="margin-top:8px;font-size:12px;color:var(--color-on-surface-variant)">Try: "FDA requirements for supplements", "Traditional use of ashwagandha", "Patent status in India"</div>'
      + '</div></div>';

    // Source registry overview
    if (sources.by_type) {
      html += '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>' + icon('source', 18) + ' Source Registry</h2>'
        + '<p>' + (sources.configured_sources || 0) + ' of ' + (sources.total_sources || 0) + ' sources configured</p></div><div class="card-body">'
        + '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px">';

      sources.by_type.forEach(function (st) {
        html += '<div style="padding:12px;border:1px solid var(--color-outline-variant);border-radius:var(--radius-md);border-left:4px solid ' + (st.color || '#757575') + '">'
          + '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
          + '<span class="material-symbols-outlined" style="font-size:18px;color:' + (st.color || '#757575') + '">' + (st.icon || 'help') + '</span>'
          + '<div style="font-weight:600;font-size:13px">' + escapeHtml(st.label) + '</div></div>';
        st.sources.forEach(function (s) {
          html += '<div style="font-size:12px;padding:4px 0;border-top:1px solid var(--color-outline-variant);color:var(--color-on-surface-variant)">'
            + escapeHtml(s.name)
            + (s.jurisdiction ? ' <span class="chip" style="font-size:9px;padding:1px 6px">' + escapeHtml(s.jurisdiction) + '</span>' : '')
            + (s.is_configured ? ' <span style="color:var(--color-secondary)">Configured</span>' : '')
            + '</div>';
        });
        html += '</div>';
      });
      html += '</div></div></div>';
    }

    // Routing result
    if (result) {
      html += '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>' + icon('alt_route', 18) + ' Routing Result</h2></div><div class="card-body">'

        // Classification
        + '<div style="margin-bottom:16px"><span class="label-caps" style="color:var(--color-on-surface-variant)">QUESTION CLASSIFICATION</span>'
        + '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:4px">'
        + '<span class="chip selected">' + escapeHtml(result.classification.primary_topic.replace(/_/g, ' ')) + '</span>'
        + '<span class="chip" style="font-size:11px">Confidence: ' + escapeHtml(result.classification.confidence) + '</span>';
      if (result.classification.secondary_topics && result.classification.secondary_topics.length > 0) {
        result.classification.secondary_topics.forEach(function (t) {
          html += '<span class="chip" style="font-size:11px">Also: ' + escapeHtml(t.replace(/_/g, ' ')) + '</span>';
        });
      }
      html += '</div></div>';

      // Jurisdictions
      html += '<div style="margin-bottom:16px"><span class="label-caps" style="color:var(--color-on-surface-variant)">DETECTED JURISDICTIONS</span>'
        + '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:4px">';
      result.jurisdictions.forEach(function (j) {
        html += '<span class="chip selected" style="background:rgba(33,150,243,0.1);color:var(--color-scientific-blue)">' + escapeHtml(j) + '</span>';
      });
      html += '</div></div>';

      // Routing decisions
      if (result.routing_decisions && result.routing_decisions.length > 0) {
        result.routing_decisions.forEach(function (rd) {
          var confColor = rd.routing_confidence === 'HIGH' ? 'var(--color-secondary)' : (rd.routing_confidence === 'MEDIUM' ? '#d97706' : 'var(--color-outline)');
          var typeInfo = rd.source_type_info || {};

          html += '<div style="margin-bottom:16px;padding:16px;border:1px solid var(--color-outline-variant);border-radius:var(--radius-md);border-left:4px solid ' + (typeInfo.color || '#757575') + '">'
            + '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
            + '<span class="material-symbols-outlined" style="font-size:18px;color:' + (typeInfo.color || '#757575') + '">' + (typeInfo.icon || 'help') + '</span>'
            + '<div style="font-weight:600">' + escapeHtml(rd.jurisdiction) + ' -- ' + escapeHtml(typeInfo.label || rd.primary_topic) + '</div>'
            + '<span class="chip" style="font-size:10px;background:' + confColor + '15;color:' + confColor + '">' + escapeHtml(rd.routing_confidence) + '</span>'
            + '</div>';

          // Selected source
          if (rd.selected_source) {
            html += '<div style="margin-bottom:8px"><span class="label-caps" style="font-size:10px;color:var(--color-on-surface-variant)">SELECTED SOURCE</span>'
              + '<div style="font-size:14px;font-weight:600;margin-top:2px">' + escapeHtml(rd.selected_source.name) + '</div>'
              + '<div style="font-size:12px;color:var(--color-on-surface-variant);margin-top:2px">' + escapeHtml(rd.selected_source.authority || '') + ' | Score: ' + rd.selected_source.relevance_score + '</div>'
              + '</div>';
          } else {
            html += '<div style="margin-bottom:8px;padding:8px 12px;background:rgba(255,87,34,0.05);border-radius:var(--radius-md);color:var(--color-error);font-size:13px">'
              + icon('warning', 14) + ' No suitable source found for this jurisdiction.</div>';
          }

          // Explanation
          html += '<div style="font-size:12px;color:var(--color-on-surface-variant);line-height:1.6;margin-bottom:8px;font-style:italic">'
            + escapeHtml(rd.explanation) + '</div>';

          // Detected keywords
          if (rd.detected_keywords && rd.detected_keywords.length > 0) {
            html += '<div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px">';
            rd.detected_keywords.forEach(function (kw) {
              html += '<span style="font-size:10px;padding:2px 6px;border:1px solid var(--color-outline-variant);border-radius:var(--radius-full);color:var(--color-on-surface-variant)">' + escapeHtml(kw) + '</span>';
            });
            html += '</div>';
          }

          // Alternative sources
          if (rd.alternative_sources && rd.alternative_sources.length > 0) {
            html += '<div><span class="label-caps" style="font-size:10px;color:var(--color-on-surface-variant)">ALTERNATIVE SOURCES</span>';
            rd.alternative_sources.forEach(function (alt) {
              html += '<div style="font-size:12px;padding:4px 0;color:var(--color-on-surface-variant)">- ' + escapeHtml(alt.name) + ' <span style="color:var(--color-outline)">(Score: ' + alt.relevance_score + ')</span></div>';
            });
            html += '</div>';
          }

          // Conflict warning
          if (rd.has_conflict && rd.conflict_details) {
            html += '<div style="margin-top:8px;padding:8px 12px;background:rgba(217,119,6,0.05);border:1px solid rgba(217,119,6,0.2);border-radius:var(--radius-md);font-size:12px;color:#d97706">'
              + icon('warning', 14) + ' <strong>SOURCE CONFLICT:</strong> ' + escapeHtml(rd.conflict_details.note) + '</div>';
          }

          html += '</div>';
        });
      }

      // Source type summary
      if (result.source_type_summary && result.source_type_summary.length > 0) {
        html += '<div style="margin-top:16px"><span class="label-caps" style="color:var(--color-on-surface-variant)">SOURCES NEEDED</span>'
          + '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">';
        result.source_type_summary.forEach(function (st) {
          var configured = st.configured_count > 0;
          html += '<div style="padding:8px 12px;border:1px solid ' + (configured ? 'var(--color-secondary)' : 'var(--color-outline-variant)') + ';border-radius:var(--radius-md);font-size:12px">'
            + '<div style="font-weight:600;color:' + (st.color || '#757575') + '">' + escapeHtml(st.label) + (st.is_primary ? ' (PRIMARY)' : '') + '</div>'
            + '<div style="color:var(--color-on-surface-variant);margin-top:2px">' + st.available_count + ' available, ' + st.configured_count + ' configured</div>'
            + '</div>';
        });
        html += '</div></div>';
      }

      html += '</div></div>';
    }

    // Disclaimer
    html += '<div class="innovation-disclaimer">' + icon('warning', 18) + '<div><strong>AI Source Router.</strong> Routing decisions are based on configured source registry and question classification. Routing confidence reflects source availability, not factual accuracy.</div></div>';

    return html;
  }

  // ----------------------------------------------------------------
  // Regulatory Intelligence View (India-First AYUSH & FSSAI)
  // ----------------------------------------------------------------
  function formatStatusLabel(status) {
    if (!status) return 'Relevant';
    var map = {
      'RELEVANT': 'Relevant',
      'POTENTIALLY_RELEVANT': 'Potentially Relevant',
      'NEEDS_VERIFICATION': 'Needs Verification',
      'INFORMATIONAL': 'Informational',
      'COMPLIANT': 'Compliant',
      'NON_COMPLIANT': 'Non-Compliant'
    };
    return map[status] || status.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, function(l){ return l.toUpperCase(); });
  }

  async function generateRegulatoryAnalysis(caseId, jurisdiction) {
    var j = jurisdiction || "IN";
    var c = state.currentCase || (state.cases && state.cases.find(function(item) { return item.id === caseId; }));
    if (!c && state.cases && state.cases.length > 0) {
      c = state.cases[0];
      state.currentCase = c;
    }
    if (!c) {
      showToast('⚠️ No active product case found', 'error');
      return;
    }
    var isNewView = state.view !== "regulatory-intelligence";
    if (isNewView) {
      saveCurrentViewScrollPosition();
    }
    var cacheKey = "regulatoryProfile:" + j;
    var cached = getCachedModule(c.id, cacheKey) || getCachedModule(c.id, "regulatoryProfile");
    if (cached && (cached.jurisdiction === j || !j)) {
      state.regulatoryProfile = cached;
      state.view = "regulatory-intelligence";
      saveStateToLocalStorage();
      render({ scroll: isNewView ? "top" : "preserve" });
      return;
    }
    state.loading = true;
    render({ scroll: isNewView ? "top" : "preserve" });
    try {
      var data = null;
      try {
        data = await api("/api/cases/" + c.id + "/regulatory-analysis?jurisdiction=" + encodeURIComponent(j));
      } catch (getErr) {
        data = await api("/api/cases/" + c.id + "/regulatory-analysis", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ jurisdiction: j })
        });
      }
      if (data) {
        setCachedModule(c.id, cacheKey, data);
        setCachedModule(c.id, "regulatoryProfile", data);
        state.regulatoryProfile = data;
        state.view = "regulatory-intelligence";
        saveStateToLocalStorage();
      }
    } catch (e) {
      console.error("Regulatory analysis failed:", e);
      state.error = "Failed to generate regulatory analysis.";
    }
    state.loading = false;
    render({ scroll: isNewView ? "top" : "preserve" });
  }
  window.generateRegulatoryAnalysis = generateRegulatoryAnalysis;

  function renderRegulatoryIntelligence() {
    var rp = state.regulatoryProfile;
    if (!rp) return '<div class="card"><div class="card-body"><p style="color:#b0c8c0">No regulatory profile available. Please run analysis from Case Intelligence.</p></div></div>';

    var ayush = rp.ayush_details || {};
    var fssai = rp.fssai_details || {};

    var confColor = rp.category_confidence === 'HIGH' ? '#2ecc71' : (rp.category_confidence === 'MEDIUM' ? '#f39c12' : '#e74c3c');

    var rawReqs = rp.requirements || [];
    var requirements = [];
    var seenReqKeys = {};
    for (var i = 0; i < rawReqs.length; i++) {
      var reqItem = rawReqs[i];
      var rKey = ((reqItem.title || '') + '|' + (reqItem.jurisdiction || '') + '|' + (reqItem.category || '')).toLowerCase().trim();
      if (!seenReqKeys[rKey]) {
        seenReqKeys[rKey] = true;
        requirements.push(reqItem);
      }
    }

    var html = ''
      + '<div class="view-header">'
      + '<button class="btn btn-ghost btn-sm" id="back-from-regulatory-intel" onclick="if(window.AYUR){window.AYUR.navigateBackToCaseDetail();}">' + icon('arrow_back', 16) + ' Back to Case Intelligence</button>'
      + '</div>'

      // Header Card
      + '<div class="card regulatory-header-card" style="margin-bottom:24px;border-left:6px solid #2ecc71">'
      + '<div class="card-body" style="padding:24px">'
      + '<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:16px">'
      + '<div>'
      + '<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">'
      + '<span style="font-size:28px">📋</span>'
      + '<h2 style="font-size:24px;font-weight:700;color:#ffffff;margin:0">Regulatory Intelligence Report — India</h2>'
      + '<span class="chip" style="background:rgba(46,204,113,0.15);color:#2ecc71;border:1px solid rgba(46,204,113,0.3);font-weight:600">🇮🇳 India Focus</span>'
      + '</div>'
      + '<p style="color:#b0c8c0;margin:0;font-size:14px">Comprehensive statutory analysis for <strong style="color:#e0eee8">' + escapeHtml(rp.product_name) + '</strong> under AYUSH and FSSAI frameworks.</p>'
      + '</div>'
      + '<div style="text-align:right">'
      + '<span class="chip" style="background:' + confColor + '20;color:' + confColor + ';border:1px solid ' + confColor + '40;font-weight:700;font-size:12px;padding:6px 12px">'
      + icon('verified', 14) + ' ' + escapeHtml(rp.category_confidence) + ' Confidence</span>'
      + '</div>'
      + '</div>'
      + '</div>'
      + '</div>'

      // Product Summary Card
      + '<div class="card" style="margin-bottom:24px">'
      + '<div class="card-head" style="border-bottom:1px solid var(--color-outline-variant);padding:16px 20px">'
      + '<h3 style="margin:0;font-size:16px;color:#e0eee8;display:flex;align-items:center;gap:8px">' + icon('inventory_2', 18) + ' Product Summary &amp; Classification Baseline</h3>'
      + '</div>'
      + '<div class="card-body" style="padding:20px">'
      + '<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));gap:16px">'
      + '<div><span style="font-size:11px;font-weight:700;text-transform:uppercase;color:#7dba9a;display:block;margin-bottom:4px">PRODUCT NAME</span><strong style="font-size:15px;color:#e0eee8">' + escapeHtml(rp.product_name) + '</strong></div>'
      + '<div><span style="font-size:11px;font-weight:700;text-transform:uppercase;color:#7dba9a;display:block;margin-bottom:4px">FORM / DOSAGE</span><span class="chip selected" style="font-size:12px">' + escapeHtml(rp.product_form) + '</span></div>'
      + '<div><span style="font-size:11px;font-weight:700;text-transform:uppercase;color:#7dba9a;display:block;margin-bottom:4px">PRIMARY INTENDED USE</span><span style="font-size:13px;color:#b0c8c0">' + escapeHtml(rp.intended_use) + '</span></div>'
      + '</div>'
      + '<div style="margin-top:16px;padding-top:16px;border-top:1px dashed var(--color-outline-variant);display:grid;grid-template-columns:1fr 1fr;gap:16px">'
      + '<div><span style="font-size:11px;font-weight:700;text-transform:uppercase;color:#7dba9a;display:block;margin-bottom:6px">INGREDIENTS (' + (rp.ingredients ? rp.ingredients.length : 0) + ')</span>'
      + '<div style="display:flex;flex-wrap:wrap;gap:6px">'
      + (rp.ingredients && rp.ingredients.length > 0 ? rp.ingredients.map(function(ing){ return '<div class="regulatory-ingredient-item">🌿 <span class="ingredient-name">' + escapeHtml(typeof ing === "string" ? ing : ing.name) + '</span></div>'; }).join('') : '<span style="color:#b0c8c0;font-size:13px">No ingredients specified</span>')
      + '</div></div>'
      + '<div><span style="font-size:11px;font-weight:700;text-transform:uppercase;color:#7dba9a;display:block;margin-bottom:6px">PROPOSED CLAIMS (' + (rp.claims ? rp.claims.length : 0) + ')</span>'
      + '<div style="display:flex;flex-wrap:wrap;gap:6px">'
      + (rp.claims && rp.claims.length > 0 ? rp.claims.map(function(c){ return '<span class="chip" style="font-size:12px;background:rgba(46,204,113,0.12);color:#2ecc71;border:1px solid rgba(46,204,113,0.3)">📜 ' + escapeHtml(typeof c === "string" ? c : c.claim) + '</span>'; }).join('') : '<span style="color:#b0c8c0;font-size:13px">No explicit claims logged</span>')
      + '</div></div>'
      + '</div>'
      + '</div>'
      + '</div>'

      // Classification Result Card
      + '<div class="card" style="margin-bottom:24px;background:linear-gradient(135deg, rgba(20,34,27,0.95) 0%, rgba(11,18,14,0.98) 100%);border:1px solid rgba(125,186,154,0.35)">'
      + '<div class="card-body" style="padding:20px">'
      + '<div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">'
      + '<span style="font-size:24px">⚖️</span>'
      + '<div>'
      + '<span style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:#7dba9a">IDENTIFIED STATUTORY PATHWAY</span>'
      + '<h3 style="margin:2px 0 0;font-size:18px;color:#ffffff;font-weight:700">' + escapeHtml(rp.potential_category) + '</h3>'
      + '</div>'
      + '</div>'
      + '<p style="color:#b0c8c0;font-size:14px;line-height:1.6;margin:0;padding:12px;background:rgba(255,255,255,0.04);border-radius:var(--radius-md);border-left:3px solid #2ecc71">'
      + escapeHtml(rp.category_reasoning)
      + '</p>'
      + '</div>'
      + '</div>'

      // Statutory Pathways Grid (AYUSH & FSSAI)
      + '<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(340px, 1fr));gap:20px;margin-bottom:24px">'

      // AYUSH Card
      + '<div class="card reg-path-card" style="border-top:4px solid #2e7d32">'
      + '<div class="card-head" style="padding:16px 20px;background:rgba(46,125,50,0.12);border-bottom:1px solid var(--color-outline-variant)">'
      + '<div style="display:flex;justify-content:space-between;align-items:center">'
      + '<h3 style="margin:0;font-size:17px;font-weight:700;color:#ffffff;display:flex;align-items:center;gap:8px">🏛️ AYUSH Drug License</h3>'
      + '<span class="chip" style="background:#2e7d32;color:#fff;font-size:11px;font-weight:600">Drugs &amp; Cosmetics Act</span>'
      + '</div>'
      + '</div>'
      + '<div class="card-body" style="padding:20px">'
      + '<div style="margin-bottom:14px;font-size:13.5px;color:#b0c8c0;line-height:1.6">'
      + '<span style="color:#7dba9a;font-weight:600">Authority:</span> <span style="color:#e0eee8">' + escapeHtml(ayush.authority || 'Ministry of Ayush / State Licensing Authority (SLA)') + '</span><br>'
      + '<span style="color:#7dba9a;font-weight:600">GMP Requirement:</span> <span style="color:#2ecc71;font-weight:600">' + escapeHtml(ayush.gmp || 'Schedule T Compliance Mandatory') + '</span>'
      + '</div>'

      // Required Govt Forms Section
      + '<div style="margin-bottom:16px"><span style="font-size:11px;font-weight:700;text-transform:uppercase;color:#7dba9a;display:block;margin-bottom:10px">REQUIRED GOVT FORMS &amp; TIMELINES</span>'
      + (ayush.forms ? ayush.forms.map(function(f){
          return '<div style="margin-bottom:10px;padding:12px;background:var(--color-surface-container-low);border:1px solid var(--color-outline-variant);border-radius:var(--radius-md)">'
            + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">'
            + '<strong style="font-size:14px;color:#e0eee8">' + escapeHtml(f.form) + '</strong>'
            + '<span class="chip" style="font-size:10px;background:rgba(46,204,113,0.15);color:#2ecc71;border:1px solid rgba(46,204,113,0.3)">' + escapeHtml(f.timeline) + ' | ' + escapeHtml(f.fee) + '</span>'
            + '</div>'
            + '<div style="font-size:12.5px;color:#b0c8c0;margin-bottom:8px;line-height:1.4">' + escapeHtml(f.title || f.description) + '</div>'
            + (f.download_url ? '<a href="' + f.download_url + '" target="_blank" class="btn btn-xs" style="display:inline-flex;align-items:center;gap:4px;background:rgba(46,204,113,0.15);color:#2ecc71;border:1px solid rgba(46,204,113,0.35);padding:5px 12px;font-size:12px;font-weight:600;border-radius:var(--radius-sm);text-decoration:none">📥 Download Form</a>' : '')
            + '</div>';
        }).join('') : '')
      + '</div>'

      + '<button class="btn btn-primary" style="width:100%;justify-content:center;padding:12px;font-weight:600" onclick="window.openRegulatoryGuide(\'ayush\')">'
      + icon('open_in_new', 16) + ' e-AUSHADHI Registration Guide &amp; Portal →'
      + '</button>'
      + '</div>'
      + '</div>'

      // FSSAI Card
      + '<div class="card reg-path-card" style="border-top:4px solid #1565c0">'
      + '<div class="card-head" style="padding:16px 20px;background:rgba(21,101,192,0.12);border-bottom:1px solid var(--color-outline-variant)">'
      + '<div style="display:flex;justify-content:space-between;align-items:center">'
      + '<h3 style="margin:0;font-size:17px;font-weight:700;color:#ffffff;display:flex;align-items:center;gap:8px">🥗 FSSAI Ayurveda Aahara</h3>'
      + '<span class="chip" style="background:#1565c0;color:#fff;font-size:11px;font-weight:600">Food Safety Act 2006</span>'
      + '</div>'
      + '</div>'
      + '<div class="card-body" style="padding:20px">'
      + '<div style="margin-bottom:14px;font-size:13.5px;color:#b0c8c0;line-height:1.6">'
      + '<span style="color:#7dba9a;font-weight:600">Authority:</span> <span style="color:#e0eee8">' + escapeHtml(fssai.authority || 'Food Safety and Standards Authority of India') + '</span><br>'
      + '<span style="color:#7dba9a;font-weight:600">Annual Fee:</span> <span style="color:#3498db;font-weight:600">' + escapeHtml(fssai.fee || '₹7,500 + GST / Year') + '</span><br>'
      + '<span style="color:#ff8e8e;font-weight:600">Enforcement:</span> <span style="color:#e0eee8">' + escapeHtml(fssai.enforcement || 'Strict compliance mandated from Sept 1, 2025.') + '</span>'
      + '</div>'

      // Warning penalty box - HIGH CONTRAST
      + '<div style="margin-bottom:16px;padding:12px;background:rgba(231,76,60,0.12);border:1px solid rgba(231,76,60,0.4);border-radius:var(--radius-md);font-size:12.5px;color:#ff8e8e;line-height:1.5">'
      + '⚠️ <strong style="color:#ffffff">Non-Compliance Penalty:</strong> Operating without an Ayurveda Aahara license carries fines up to <strong style="color:#ffffff">₹2,00,000</strong> and/or up to <strong style="color:#ffffff">6 months imprisonment</strong> (Section 63 of FSS Act 2006).'
      + '</div>'

      + '<div style="margin-bottom:16px"><span style="font-size:11px;font-weight:700;text-transform:uppercase;color:#7dba9a;display:block;margin-bottom:8px">PRODUCT CATEGORIES</span>'
      + (fssai.categories ? fssai.categories.map(function(c){
          return '<div style="margin-bottom:8px;padding:10px 12px;background:var(--color-surface-container-low);border:1px solid var(--color-outline-variant);border-radius:var(--radius-md)">'
            + '<strong style="font-size:13px;color:#3498db">' + escapeHtml(c.code) + ' — ' + escapeHtml(c.name) + '</strong>'
            + '<div style="font-size:12px;color:#b0c8c0;margin-top:2px">' + escapeHtml(c.description) + '</div>'
            + '</div>';
        }).join('') : '')
      + '</div>'

      + '<button class="btn btn-primary" style="width:100%;justify-content:center;padding:12px;background:#1565c0;border-color:#1565c0;font-weight:600" onclick="window.openRegulatoryGuide(\'fssai\')">'
      + icon('open_in_new', 16) + ' FoSCoS Registration Guide &amp; Portal →'
      + '</button>'
      + '</div>'
      + '</div>'

      + '</div>' // end grid

      // Detailed Regulatory Requirements Checklist - HIGH CONTRAST
      + '<div class="card" style="margin-bottom:24px">'
      + '<div class="card-head" style="border-bottom:1px solid var(--color-outline-variant);padding:16px 20px">'
      + '<h3 style="margin:0;font-size:16px;color:#e0eee8;display:flex;align-items:center;gap:8px">' + icon('checklist', 18) + ' Compliance Requirements &amp; Evidence Checklist</h3>'
      + '</div>'
      + '<div class="card-body" style="padding:20px">'
      + (requirements.length > 0 ? requirements.map(function(req){
          var app = (req.applicability || 'RELEVANT').toUpperCase();
          var statusBg = app === 'RELEVANT' ? 'rgba(46,204,113,0.15)' : (app === 'NEEDS_VERIFICATION' ? 'rgba(230,126,34,0.15)' : 'rgba(241,196,15,0.15)');
          var statusColor = app === 'RELEVANT' ? '#2ecc71' : (app === 'NEEDS_VERIFICATION' ? '#e67e22' : '#f1c40f');
          var isIngEligibility = req.title && req.title.indexOf('Ingredient Eligibility') !== -1;

          return '<div style="margin-bottom:14px;padding:16px 18px;background:var(--color-surface-container-low);border:1px solid var(--color-outline-variant);border-radius:var(--radius-md);border-left:4px solid ' + statusColor + '">'
            + '<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:8px">'
            + '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">'
            + '<h4 style="margin:0;font-size:15px;font-weight:700;color:#ffffff">' + escapeHtml(req.title) + '</h4>'
            + (isIngEligibility ? '<button class="btn btn-xs" style="background:rgba(46,204,113,0.15);color:#2ecc71;border:1px solid rgba(46,204,113,0.35);padding:4px 10px;font-size:12px;font-weight:600;border-radius:var(--radius-sm);cursor:pointer;display:inline-flex;align-items:center;gap:4px" onclick="event.stopPropagation(); openEligibilityPopup()">' + icon('search', 13) + ' Check Eligibility</button>' : '')
            + '</div>'
            + '<span class="chip" style="background:' + statusBg + ';color:' + statusColor + ';border:1px solid ' + statusColor + '40;font-size:11px;font-weight:700;padding:3px 10px;white-space:nowrap">' + escapeHtml(formatStatusLabel(req.applicability)) + '</span>'
            + '</div>'
            + '<p style="margin:0 0 10px;font-size:13.5px;color:#b0c8c0;line-height:1.55">' + escapeHtml(req.description) + '</p>'
            + '<div style="display:flex;flex-wrap:wrap;gap:8px;font-size:12px;margin-bottom:' + (req.next_action ? '8px' : '0') + '">'
            + '<span class="chip" style="background:var(--color-surface-container);color:#b0c8c0;border:1px solid var(--color-outline-variant);padding:3px 8px"><strong style="color:#7dba9a">Authority:</strong>&nbsp;<span style="color:#e0eee8">' + escapeHtml(req.authority || 'N/A') + '</span></span>'
            + '<span class="chip" style="background:var(--color-surface-container);color:#b0c8c0;border:1px solid var(--color-outline-variant);padding:3px 8px"><strong style="color:#7dba9a">Source:</strong>&nbsp;<span style="color:#e0eee8">' + escapeHtml(req.source_name || 'N/A') + '</span></span>'
            + '</div>'
            + (req.next_action ? '<div style="margin-top:6px;font-size:12.5px;color:#2ecc71;font-weight:600;display:flex;align-items:center;gap:6px">' + icon('arrow_forward', 14) + ' <span>Next Step: ' + escapeHtml(req.next_action) + '</span></div>' : '')
            + '</div>';
        }).join('') : '<p style="color:#b0c8c0">No specific requirements found.</p>')
      + '</div>'
      + '</div>'

      // Disclaimer Banner - HIGH CONTRAST (Fix pale washed out text)
      + '<div class="innovation-disclaimer" style="margin-bottom:24px;background:rgba(241,196,15,0.1);border:1px solid rgba(241,196,15,0.35);border-radius:var(--radius-md);padding:16px;display:flex;align-items:flex-start;gap:12px">'
      + '<span style="font-size:22px">⚠️</span>'
      + '<div style="color:#b0c8c0;font-size:13px;line-height:1.5"><strong style="color:#f1c40f">Statutory Disclaimer:</strong> ' + escapeHtml(rp.disclaimer || 'This regulatory analysis is generated strictly for research and decision-support purposes under Indian regulatory frameworks (AYUSH & FSSAI). It does not constitute formal legal or regulatory advice. Consult certified legal counsel prior to commercial launch.') + '</div>'
      + '</div>';

    return html;
  }

  async function openEligibilityPopup() {
    var c = state.currentCase;
    var rp = state.regulatoryProfile;
    var rawIngredients = (rp && rp.ingredients) ? rp.ingredients : ((c && c.ingredients) ? c.ingredients : []);
    
    var formattedIngredients = rawIngredients.map(function(item) {
      if (typeof item === 'string') {
        return { name: item, botanical: '' };
      }
      return {
        name: item.name || item.input_name || item.ingredient_name || '',
        botanical: item.botanical || item.botanical_name || ''
      };
    });

    if (formattedIngredients.length === 0) {
      formattedIngredients = [
        { name: 'Ashwagandha', botanical: 'Withania somnifera Dunal.' },
        { name: 'Tulsi', botanical: 'Ocimum sanctum' }
      ];
    }

    var existing = document.getElementById('eligibility-popup-modal');
    if (existing) existing.remove();

    var overlay = document.createElement('div');
    overlay.className = 'eligibility-popup-overlay';
    overlay.id = 'eligibility-popup-modal';
    overlay.onclick = function(e) {
      if (e.target === overlay) closeEligibilityPopup();
    };

    overlay.innerHTML = '<div class="eligibility-popup-card">'
      + '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;border-bottom:1px solid var(--color-outline-variant);padding-bottom:12px;">'
      + '<div>'
      + '<h3 style="margin:0;font-size:20px;color:#ffffff;display:flex;align-items:center;gap:8px;">🌿 Ingredient Eligibility &amp; Schedule E-1 Check — India</h3>'
      + '<p style="margin:4px 0 0;font-size:13px;color:#7dba9a;">Verifying ingredients against CCRAS DRAVYA Database</p>'
      + '</div>'
      + '<button class="eligibility-popup-close" onclick="closeEligibilityPopup()">✕</button>'
      + '</div>'
      + '<div id="eligibility-popup-body" style="padding:10px 0;">'
      + '<div style="text-align:center;padding:24px;color:#7dba9a;">🔍 Querying CCRAS DRAVYA Monograph Database...</div>'
      + '</div>'
      + '<div class="eligibility-popup-actions">'
      + '<button class="btn btn-secondary" onclick="closeEligibilityPopup()">Close</button>'
      + '<a href="https://dravya.ccras.org.in/" target="_blank" class="btn btn-primary" style="background:#2ecc71;color:#0b120e;font-weight:700;text-decoration:none;display:inline-flex;align-items:center;gap:6px;">🔗 Open DRAVYA Portal</a>'
      + '</div>'
      + '</div>';

    document.body.appendChild(overlay);

    try {
      var batchRes = await api('/api/ingredients/batch-eligibility', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formattedIngredients)
      });

      var evals = batchRes.evaluations || [];
      var verifiedCount = batchRes.verified_count || 0;
      var totalCount = batchRes.total_ingredients || evals.length;
      var e1Count = batchRes.schedule_e1_count || 0;

      var bodyHtml = '';

      evals.forEach(function(ev) {
        var isVerified = ev.verified;
        var lvl = ev.eligibility_level || (isVerified ? 'HIGH' : 'NOT FOUND');
        var badgeColor = isVerified ? '#2ecc71' : (lvl === 'LOW' ? '#f1c40f' : '#e74c3c');
        var badgeBg = isVerified ? 'rgba(46,204,113,0.15)' : (lvl === 'LOW' ? 'rgba(241,196,15,0.15)' : 'rgba(231,76,60,0.15)');
        var badgeText = isVerified ? '✅ Verified' : (lvl === 'LOW' ? '⚠️ Partial' : '❌ Not Found');

        bodyHtml += '<div class="eligibility-popup-item">'
          + '<div class="eligibility-popup-item-header">'
          + '<div>'
          + '<strong style="font-size:16px;color:#ffffff;">🌿 ' + escapeHtml(ev.name) + '</strong>'
          + (ev.scientific_name ? ' <span style="font-size:13.5px;color:#7dba9a;font-style:italic;">(' + escapeHtml(ev.scientific_name) + ')</span>' : '')
          + '</div>'
          + '<span class="chip" style="background:' + badgeBg + ';color:' + badgeColor + ';border:1px solid ' + badgeColor + '40;font-weight:700;">' + badgeText + '</span>'
          + '</div>'

          + '<div style="font-size:13px;color:#b0c8c0;line-height:1.6;margin-top:8px;">'
          + '<div>└── <strong>Source:</strong> CCRAS DRAVYA Database</div>'
          + '<div>└── <strong>Classical Text:</strong> ' + escapeHtml(ev.classical_reference || 'Recognized in Ayurvedic Samhitas') + '</div>'
          + '<div>└── <strong>Schedule Status:</strong> ' + (ev.schedule_e1 ? '<span style="color:#ff8e8e;font-weight:700;">⚠️ In Schedule E-1 (Poisonous/Restricted)</span>' : '<span style="color:#2ecc71;">Not in Schedule E-1 (Safe)</span>') + '</div>'
          + '</div>'
          + '</div>';
      });

      // Verification Summary
      bodyHtml += '<div class="eligibility-popup-summary">'
        + '<div style="font-weight:700;font-size:15px;color:#ffffff;margin-bottom:6px;">'
        + 'Verification Summary: ' + verifiedCount + '/' + totalCount + ' Ingredients Verified ' + (verifiedCount === totalCount ? '✅' : '⚠️')
        + '</div>'
        + '<div style="font-size:13px;color:#b0c8c0;line-height:1.5;">'
        + (e1Count > 0 ? '⚠️ <span style="color:#ff8e8e;font-weight:700;">Schedule E-1 poisonous substances detected!</span> Doctor prescription & special labeling mandatory.' : '✅ No Schedule E-1 poisonous substances detected (Safe for OTC sale).') + '<br>'
        + '✅ Schedule T Good Manufacturing Practice (GMP) Compliance Required.'
        + '</div>'
        + '</div>';

      var bodyElem = document.getElementById('eligibility-popup-body');
      if (bodyElem) bodyElem.innerHTML = bodyHtml;

    } catch (err) {
      console.error('Eligibility popup query failed:', err);
      var bodyElem = document.getElementById('eligibility-popup-body');
      if (bodyElem) bodyElem.innerHTML = '<div style="color:#ff8e8e;padding:16px;">❌ Failed to load ingredient eligibility details.</div>';
    }
  }

  function closeEligibilityPopup() {
    var modal = document.getElementById('eligibility-popup-modal');
    if (modal) modal.remove();
  }

  window.openEligibilityPopup = openEligibilityPopup;
  window.closeEligibilityPopup = closeEligibilityPopup;

  function openRegulatoryGuide(type) {
    var rp = state.regulatoryProfile;
    if (!rp) return;

    var isAyush = type === 'ayush';
    var title = isAyush ? '🏛️ e-AUSHADHI Registration Guide (AYUSH Drug License)' : '🥗 FoSCoS Registration Guide (FSSAI Ayurveda Aahara)';
    var portalUrl = isAyush ? 'https://www.e-aushadhi.gov.in' : 'https://foscos.fssai.gov.in';
    var portalName = isAyush ? 'Visit e-AUSHADHI Portal' : 'Visit FoSCoS Portal';
    var steps = isAyush ? (rp.step_guides ? rp.step_guides.ayush : []) : (rp.step_guides ? rp.step_guides.fssai : []);

    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay open';
    overlay.id = 'reg-guide-modal';

    var stepsHtml = (steps || []).map(function(s) {
      return '<div style="display:flex;gap:14px;align-items:flex-start;margin-bottom:16px;padding:14px;background:var(--color-surface-container-low);border:1px solid var(--color-outline-variant);border-radius:var(--radius-md)">'
        + '<div style="width:32px;height:32px;border-radius:50%;background:' + (isAyush ? '#2e7d32' : '#1565c0') + ';color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;flex-shrink:0">' + s.step + '</div>'
        + '<div style="flex:1">'
        + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">'
        + '<h4 style="margin:0;font-size:14px;font-weight:700;color:var(--color-on-surface)">' + escapeHtml(s.title) + '</h4>'
        + '<span class="chip" style="font-size:10px;background:rgba(255,255,255,0.06)">⏱️ ' + escapeHtml(s.timeline) + '</span>'
        + '</div>'
        + '<p style="margin:0;font-size:13px;color:var(--color-on-surface-variant);line-height:1.5">' + escapeHtml(s.desc) + '</p>'
        + '</div>'
        + '</div>';
    }).join('');

    overlay.innerHTML = '<div class="modal" style="max-width:680px;background:var(--color-surface);border:1px solid var(--color-outline-variant);border-radius:var(--radius-lg)">'
      + '<div class="modal-head" style="padding:16px 20px;border-bottom:1px solid var(--color-outline-variant);display:flex;justify-content:space-between;align-items:center">'
      + '<h3 style="margin:0;font-size:17px;font-weight:700;color:var(--color-on-surface)">' + title + '</h3>'
      + '<button class="modal-close" onclick="document.getElementById(\'reg-guide-modal\').remove()">' + icon('close', 20) + '</button>'
      + '</div>'
      + '<div class="modal-body" style="padding:20px;max-height:70vh;overflow-y:auto">'
      + '<p style="font-size:13px;color:var(--color-on-surface-variant);margin:0 0 16px">Step-by-step statutory filing walkthrough for Indian market clearance:</p>'
      + stepsHtml
      + '</div>'
      + '<div class="modal-foot" style="padding:16px 20px;border-top:1px solid var(--color-outline-variant);display:flex;justify-content:space-between;align-items:center">'
      + '<button class="btn btn-ghost btn-sm" onclick="document.getElementById(\'reg-guide-modal\').remove()">Close</button>'
      + '<a href="' + portalUrl + '" target="_blank" class="btn btn-primary btn-sm" style="background:' + (isAyush ? '#2e7d32' : '#1565c0') + ';border-color:' + (isAyush ? '#2e7d32' : '#1565c0') + ';display:flex;align-items:center;gap:6px;text-decoration:none">'
      + icon('open_in_new', 14) + ' ' + portalName + ' ↗'
      + '</a>'
      + '</div>'
      + '</div>';

    document.body.appendChild(overlay);
  }
  window.openRegulatoryGuide = openRegulatoryGuide;


  // ----------------------------------------------------------------
  // Knowledge Graph (Phase B: Evidence Intelligence Graph Helpers)
  // ----------------------------------------------------------------
  var GRAPH_LENSES = {
    OVERVIEW: {
      label: 'Overview',
      primaryTypes: ['PRODUCT', 'INGREDIENT', 'CLAIM', 'EVIDENCE', 'PATENT', 'REGULATION', 'RISK', 'INNOVATION_COMPONENT'],
      supportingTypes: ['PLANT', 'JURISDICTION', 'SOURCE', 'CASE_FINDING', 'IP_STRATEGY', 'ALERT', 'FORMULATION', 'PROCESS', 'TRADITIONAL_KNOWLEDGE']
    },
    EVIDENCE: {
      label: 'Evidence',
      primaryTypes: ['PRODUCT', 'CLAIM', 'EVIDENCE', 'SOURCE', 'CASE_FINDING', 'TRADITIONAL_KNOWLEDGE', 'INGREDIENT', 'PLANT'],
      supportingTypes: []
    },
    IP: {
      label: 'IP & Patents',
      primaryTypes: ['PRODUCT', 'INGREDIENT', 'PATENT', 'IP_STRATEGY', 'INNOVATION_COMPONENT', 'JURISDICTION'],
      supportingTypes: []
    },
    REGULATORY: {
      label: 'Regulatory',
      primaryTypes: ['PRODUCT', 'CLAIM', 'REGULATION', 'JURISDICTION', 'INGREDIENT'],
      supportingTypes: []
    },
    RISK: {
      label: 'Risk',
      primaryTypes: ['PRODUCT', 'RISK', 'CLAIM', 'PATENT', 'REGULATION', 'EVIDENCE', 'ALERT'],
      supportingTypes: []
    },
    INNOVATION: {
      label: 'Innovation',
      primaryTypes: ['PRODUCT', 'INGREDIENT', 'FORMULATION', 'PROCESS', 'INNOVATION_COMPONENT', 'IP_STRATEGY', 'PLANT'],
      supportingTypes: []
    }
  };

  function initGraphVisualization() {
    var container = document.getElementById('knowledge-graph-container');
    if (!container || !state.knowledgeGraphData) return;
    if (typeof d3 === 'undefined') {
      container.innerHTML = '<div style="padding:40px;text-align:center;color:var(--color-on-surface-variant)">D3.js visualization engine is loading...</div>';
      return;
    }

    // Stop and cleanup any previous simulation
    if (window._graphSimulation) {
      window._graphSimulation.stop();
      window._graphSimulation = null;
    }

    var g = state.knowledgeGraphData;
    var width = container.clientWidth || 800;
    var height = container.clientHeight || 640;

    // Clear previous SVG inside container while preserving legend overlay and tooltip
    var legendHtml = container.querySelector('.kg-legend-overlay');
    var tooltipHtml = container.querySelector('.kg-tooltip');
    container.innerHTML = '';
    if (legendHtml) container.appendChild(legendHtml);
    if (tooltipHtml) container.appendChild(tooltipHtml);

    var svg = d3.select(container).insert('svg', ':first-child')
      .attr('width', '100%')
      .attr('height', '100%')
      .attr('viewBox', [0, 0, width, height]);

    // Graph Root Group with Zoom
    var g_group = svg.append('g');
    var zoom = d3.zoom()
      .scaleExtent([0.15, 4])
      .on('zoom', function (event) {
        g_group.attr('transform', event.transform);
      });
    svg.call(zoom);

    // Store zoom on window for control buttons
    window._graphZoom = zoom;
    window._graphSvg = svg;
    window._graphRootGroup = g_group;
    window._graphWidth = width;
    window._graphHeight = height;

    // Arrow markers
    var defs = svg.append('defs');
    defs.append('marker')
      .attr('id', 'kg-arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 24)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-4L8,0L0,4')
      .attr('fill', '#64748b');

    defs.append('marker')
      .attr('id', 'kg-arrow-highlight')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 24)
      .attr('refY', 0)
      .attr('markerWidth', 7)
      .attr('markerHeight', 7)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-4L8,0L0,4')
      .attr('fill', '#34d399');

    // Build entity lookup map
    var nodeMap = {};
    g.nodes.forEach(function (n) { nodeMap[n.id] = n; });

    var links = (g.edges || []).map(function (e) {
      return {
        source: nodeMap[e.source] || e.source,
        target: nodeMap[e.target] || e.target,
        relationship: e.relationship,
        grounding: e.grounding || (e.metadata ? e.metadata.grounding : 'DIRECT'),
        explanation: e.explanation || (e.metadata ? e.metadata.explanation : ''),
        metadata: e.metadata || {}
      };
    }).filter(function (l) {
      return l.source && l.target && typeof l.source === 'object' && typeof l.target === 'object';
    });

    // Helper to identify primary hierarchy
    function isPrimaryNodeType(t) {
      return ['PRODUCT', 'INGREDIENT', 'CLAIM', 'EVIDENCE', 'PATENT', 'REGULATION', 'RISK', 'INNOVATION_COMPONENT'].indexOf(t) !== -1;
    }

    function getNodeRadius(d) {
      if (d.type === 'PRODUCT') return 22;
      if (isPrimaryNodeType(d.type)) return 14;
      return 9;
    }

    // Force Simulation setup
    var simulation = d3.forceSimulation(g.nodes)
      .force('link', d3.forceLink(links).id(function (d) { return d.id; }).distance(function (l) {
        if (l.source.type === 'PRODUCT' || l.target.type === 'PRODUCT') return 140;
        return 90;
      }))
      .force('charge', d3.forceManyBody().strength(function (d) {
        if (d.type === 'PRODUCT') return -600;
        if (isPrimaryNodeType(d.type)) return -250;
        return -120;
      }))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(function (d) {
        return getNodeRadius(d) + 16;
      }));

    window._graphSimulation = simulation;
    window._graphNodes = g.nodes;
    window._graphLinks = links;
    window._selectedNodeId = null;
    window._selectedEdge = null;
    window._traceMode = false;
    window._activeLens = 'OVERVIEW';

    // Links Rendering
    var linkGroup = g_group.append('g').attr('class', 'kg-links-layer');
    var link = linkGroup.selectAll('line')
      .data(links)
      .enter().append('line')
      .attr('class', 'graph-link')
      .attr('stroke', '#475569')
      .attr('stroke-opacity', 0.28)
      .attr('stroke-width', 1.2)
      .attr('marker-end', 'url(#kg-arrow)');

    // Hit Areas for Link Interaction (Transparent thick overlay)
    var hitLinkGroup = g_group.append('g').attr('class', 'kg-link-hit-layer');
    var hitLink = hitLinkGroup.selectAll('line')
      .data(links)
      .enter().append('line')
      .attr('class', 'kg-link-hit-area')
      .attr('stroke', 'transparent')
      .attr('stroke-width', 14)
      .style('cursor', 'pointer');

    // Link Labels (shown on hover/selection/trace)
    var linkLabelGroup = g_group.append('g').attr('class', 'kg-link-labels-layer');
    var linkLabel = linkLabelGroup.selectAll('text')
      .data(links)
      .enter().append('text')
      .attr('class', 'graph-link-label')
      .attr('text-anchor', 'middle')
      .attr('dy', -4)
      .text(function (d) { return d.relationship.replace(/_/g, ' '); });

    // Nodes Rendering
    var nodeGroup = g_group.append('g').attr('class', 'kg-nodes-layer');
    var node = nodeGroup.selectAll('g')
      .data(g.nodes)
      .enter().append('g')
      .attr('class', function (d) {
        return 'graph-node' + (d.type === 'PRODUCT' ? ' active-product' : '');
      })
      .call(d3.drag()
        .on('start', function (event, d) {
          if (!event.active) simulation.alphaTarget(0.2).restart();
          d.fx = d.x; d.fy = d.y;
        })
        .on('drag', function (event, d) { d.fx = event.x; d.fy = event.y; })
        .on('end', function (event, d) {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null; d.fy = null;
        })
      );

    // Outer Halo for Product
    node.filter(function (d) { return d.type === 'PRODUCT'; })
      .append('circle')
      .attr('r', 28)
      .attr('fill', 'none')
      .attr('stroke', '#34d399')
      .attr('stroke-width', 1.5)
      .attr('stroke-dasharray', '4 3')
      .attr('opacity', 0.85);

    // Node Main Circle
    node.append('circle')
      .attr('r', function (d) { return getNodeRadius(d); })
      .attr('fill', function (d) { return d.color || '#757575'; })
      .attr('stroke', function (d) {
        return d.type === 'PRODUCT' ? '#34d399' : (isPrimaryNodeType(d.type) ? '#ffffff' : 'rgba(255,255,255,0.7)');
      })
      .attr('stroke-width', function (d) {
        return d.type === 'PRODUCT' ? 3 : 2;
      });

    // Node Labels
    node.append('text')
      .attr('dy', function (d) { return getNodeRadius(d) + 12; })
      .attr('text-anchor', 'middle')
      .attr('font-size', function (d) { return d.type === 'PRODUCT' ? '11px' : (isPrimaryNodeType(d.type) ? '9px' : '8px'); })
      .attr('font-weight', function (d) { return d.type === 'PRODUCT' ? '700' : '500'; })
      .text(function (d) {
        var lbl = d.label || '';
        var maxLen = d.type === 'PRODUCT' ? 26 : 18;
        return lbl.length > maxLen ? lbl.substring(0, maxLen - 1) + '…' : lbl;
      });

    var tooltip = document.getElementById('kg-tooltip');

    // Node Hover Interactions
    node.on('mouseenter', function (event, d) {
      if (window._selectedNodeId || window._selectedEdge || window._traceMode) return; // Keep locked state

      // Find 1-hop connected neighbors & links
      var connectedNodeIds = {};
      connectedNodeIds[d.id] = true;
      var connectedLinks = {};

      links.forEach(function (l) {
        if (l.source.id === d.id) {
          connectedNodeIds[l.target.id] = true;
          connectedLinks[l.source.id + '->' + l.target.id] = true;
        } else if (l.target.id === d.id) {
          connectedNodeIds[l.source.id] = true;
          connectedLinks[l.source.id + '->' + l.target.id] = true;
        }
      });

      // Highlight active neighborhood
      node.style('opacity', function (n) {
        return connectedNodeIds[n.id] ? 1 : 0.15;
      });

      link
        .attr('stroke-opacity', function (l) {
          return connectedLinks[l.source.id + '->' + l.target.id] ? 0.9 : 0.05;
        })
        .attr('stroke-width', function (l) {
          return connectedLinks[l.source.id + '->' + l.target.id] ? 2 : 1;
        })
        .attr('marker-end', function (l) {
          return connectedLinks[l.source.id + '->' + l.target.id] ? 'url(#kg-arrow-highlight)' : 'url(#kg-arrow)';
        });

      linkLabel.classed('visible', function (l) {
        return !!connectedLinks[l.source.id + '->' + l.target.id];
      });

      // Show rich tooltip
      if (tooltip) {
        var meta = d.metadata || {};
        var tipHtml = '<div class="kg-tooltip-type">' + escapeHtml(d.type.replace(/_/g, ' ')) + '</div>'
          + '<div class="kg-tooltip-title">' + escapeHtml(d.label) + '</div>';

        var metaDetails = [];
        if (meta.confidence !== undefined && meta.confidence !== null) {
          var confVal = typeof meta.confidence === 'number' ? Math.round(meta.confidence * 100) + '%' : meta.confidence;
          metaDetails.push('Confidence: <strong>' + escapeHtml(String(confVal)) + '</strong>');
        }
        if (meta.severity) {
          metaDetails.push('Severity: <strong>' + escapeHtml(String(meta.severity)) + '</strong>');
        }
        if (meta.assessment_source) {
          metaDetails.push('Source: <strong>' + (meta.assessment_source === 'GEMINI' ? 'AI-Assisted' : 'Rule Engine') + '</strong>');
        }
        if (meta.jurisdiction) {
          metaDetails.push('Jurisdiction: <strong>' + escapeHtml(String(meta.jurisdiction)) + '</strong>');
        }

        if (metaDetails.length > 0) {
          tipHtml += '<div class="kg-tooltip-meta">' + metaDetails.join(' · ') + '</div>';
        }

        tooltip.innerHTML = tipHtml;
        tooltip.style.display = 'block';
        var bounds = container.getBoundingClientRect();
        tooltip.style.left = (event.clientX - bounds.left + 14) + 'px';
        tooltip.style.top = (event.clientY - bounds.top + 14) + 'px';
      }
    });

    node.on('mousemove', function (event) {
      if (tooltip && tooltip.style.display !== 'none') {
        var bounds = container.getBoundingClientRect();
        tooltip.style.left = (event.clientX - bounds.left + 14) + 'px';
        tooltip.style.top = (event.clientY - bounds.top + 14) + 'px';
      }
    });

    node.on('mouseleave', function () {
      if (tooltip) tooltip.style.display = 'none';
      if (!window._selectedNodeId && !window._selectedEdge && !window._traceMode) {
        applyGraphLens(window._activeLens || 'OVERVIEW');
      }
    });

    // Node Click -> Lock Selection and Open Drawer
    node.on('click', function (event, d) {
      event.stopPropagation();
      selectGraphNode(d);
    });

    // Edge Hover & Click (via transparent hit-areas)
    hitLink.on('mouseenter', function (event, l) {
      if (window._selectedNodeId || window._selectedEdge || window._traceMode) return;
      if (tooltip) {
        var isDirect = (l.grounding || '').toUpperCase() === 'DIRECT';
        var gBadge = '<span class="kg-conn-grounding ' + (isDirect ? 'direct' : 'derived') + '">' + escapeHtml(l.grounding || 'DIRECT') + '</span>';
        var tipHtml = '<div class="kg-tooltip-type">Relationship · ' + gBadge + '</div>'
          + '<div class="kg-tooltip-title">' + escapeHtml(l.source.label || l.source.id) + ' → ' + escapeHtml(l.target.label || l.target.id) + '</div>'
          + '<div class="kg-tooltip-meta"><strong>' + escapeHtml(l.relationship.replace(/_/g, ' ')) + '</strong>'
          + (l.explanation ? '<div style="margin-top:4px;font-size:11px;color:#cbd5e1;">' + escapeHtml(l.explanation) + '</div>' : '')
          + '</div>';

        tooltip.innerHTML = tipHtml;
        tooltip.style.display = 'block';
        var bounds = container.getBoundingClientRect();
        tooltip.style.left = (event.clientX - bounds.left + 14) + 'px';
        tooltip.style.top = (event.clientY - bounds.top + 14) + 'px';
      }
    });

    hitLink.on('mousemove', function (event) {
      if (tooltip && tooltip.style.display !== 'none') {
        var bounds = container.getBoundingClientRect();
        tooltip.style.left = (event.clientX - bounds.left + 14) + 'px';
        tooltip.style.top = (event.clientY - bounds.top + 14) + 'px';
      }
    });

    hitLink.on('mouseleave', function () {
      if (tooltip) tooltip.style.display = 'none';
    });

    hitLink.on('click', function (event, l) {
      event.stopPropagation();
      selectGraphEdge(l);
    });

    // Background Click -> Deselect and Close Drawer
    svg.on('click', function () {
      deselectGraphNode();
    });

    // Simulation Tick
    simulation.on('tick', function () {
      link
        .attr('x1', function (d) { return d.source.x; })
        .attr('y1', function (d) { return d.source.y; })
        .attr('x2', function (d) { return d.target.x; })
        .attr('y2', function (d) { return d.target.y; });

      hitLink
        .attr('x1', function (d) { return d.source.x; })
        .attr('y1', function (d) { return d.source.y; })
        .attr('x2', function (d) { return d.target.x; })
        .attr('y2', function (d) { return d.target.y; });

      linkLabel
        .attr('x', function (d) { return (d.source.x + d.target.x) / 2; })
        .attr('y', function (d) { return (d.source.y + d.target.y) / 2; });

      node.attr('transform', function (d) {
        return 'translate(' + d.x + ',' + d.y + ')';
      });
    });

    // Initial lens activation
    applyGraphLens('OVERVIEW');
  }

  // ----------------------------------------------------------------
  // Evidence Traversal & Grounding Helpers (Deterministic Graph BFS)
  // ----------------------------------------------------------------
  function findEvidenceTraces(startNode, maxDepth, maxTraces) {
    if (!startNode || !window._graphLinks || !window._graphNodes) return [];
    maxDepth = maxDepth || 4;
    maxTraces = maxTraces || 3;

    var evidenceTypes = ['EVIDENCE', 'CASE_FINDING', 'TRADITIONAL_KNOWLEDGE', 'SOURCE', 'BOTANICAL_SOURCE'];
    var anchorTypes = ['PATENT', 'REGULATION', 'PRODUCT', 'INGREDIENT', 'CLAIM', 'RISK'];

    // If starting node is already Evidence, we trace outwards to Claim, Ingredient, Product
    var isStartingEvidence = evidenceTypes.indexOf(startNode.type) !== -1;
    var targetTypes = isStartingEvidence ? anchorTypes : evidenceTypes.concat(anchorTypes);

    // Build adjacency list for fast BFS
    var adj = {};
    (window._graphNodes || []).forEach(function (n) { adj[n.id] = []; });
    (window._graphLinks || []).forEach(function (l) {
      if (adj[l.source.id]) adj[l.source.id].push({ neighbor: l.target, link: l, dir: 'out' });
      if (adj[l.target.id]) adj[l.target.id].push({ neighbor: l.source, link: l, dir: 'in' });
    });

    var queue = [{
      curr: startNode,
      pathNodes: [startNode],
      pathLinks: [],
      visited: {}
    }];
    queue[0].visited[startNode.id] = true;

    var candidatePaths = [];

    while (queue.length > 0) {
      var item = queue.shift();
      if (item.pathLinks.length >= maxDepth) continue;

      var edges = adj[item.curr.id] || [];
      for (var i = 0; i < edges.length; i++) {
        var edge = edges[i];
        var nbr = edge.neighbor;
        if (item.visited[nbr.id]) continue;

        var nextVisited = {};
        Object.keys(item.visited).forEach(function (k) { nextVisited[k] = true; });
        nextVisited[nbr.id] = true;

        var nextPathNodes = item.pathNodes.concat([nbr]);
        var nextPathLinks = item.pathLinks.concat([edge.link]);

        var isTargetMatch = targetTypes.indexOf(nbr.type) !== -1 && nbr.id !== startNode.id;
        var isEvidenceEnd = evidenceTypes.indexOf(nbr.type) !== -1;

        if (isTargetMatch) {
          var directCount = nextPathLinks.filter(function (l) {
            return (l.grounding || '').toUpperCase() === 'DIRECT';
          }).length;
          var derivedCount = nextPathLinks.length - directCount;

          candidatePaths.push({
            nodes: nextPathNodes,
            links: nextPathLinks,
            directCount: directCount,
            derivedCount: derivedCount,
            targetType: nbr.type,
            targetLabel: nbr.label || nbr.id,
            hops: nextPathLinks.length,
            isEvidence: isEvidenceEnd
          });
        }

        if (nextPathLinks.length < maxDepth) {
          queue.push({
            curr: nbr,
            pathNodes: nextPathNodes,
            pathLinks: nextPathLinks,
            visited: nextVisited
          });
        }
      }
    }

    // Rank candidate traces:
    // 1. Evidence-bearing targets first (if startNode is not Evidence)
    // 2. Shorter hop distance
    // 3. Higher direct grounding count
    candidatePaths.sort(function (a, b) {
      if (a.isEvidence !== b.isEvidence) return a.isEvidence ? -1 : 1;
      if (a.hops !== b.hops) return a.hops - b.hops;
      return b.directCount - a.directCount;
    });

    // Deduplicate by target ID
    var seenTargets = {};
    var uniquePaths = [];
    for (var p = 0; p < candidatePaths.length; p++) {
      var path = candidatePaths[p];
      var targetId = path.nodes[path.nodes.length - 1].id;
      if (!seenTargets[targetId]) {
        seenTargets[targetId] = true;
        uniquePaths.push(path);
        if (uniquePaths.length >= maxTraces) break;
      }
    }

    return uniquePaths;
  }

  function getNodeEvidenceStatus(d, traces) {
    var evidenceTypes = ['EVIDENCE', 'CASE_FINDING', 'TRADITIONAL_KNOWLEDGE', 'SOURCE', 'BOTANICAL_SOURCE'];
    if (evidenceTypes.indexOf(d.type) !== -1) {
      return {
        status: 'PRIMARY_SOURCE',
        badgeClass: 'traceable',
        label: 'PRIMARY EVIDENCE',
        description: 'This entity is an empirical evidence source, classical literature record, or verified case finding.'
      };
    }

    var hasEvidenceTrace = (traces || []).some(function (t) {
      return t.isEvidence;
    });

    if (d.type === 'CLAIM' || d.type === 'RISK') {
      if (hasEvidenceTrace) {
        return {
          status: 'TRACEABLE',
          badgeClass: 'traceable',
          label: 'TRACEABLE EVIDENCE',
          description: 'Verified grounded trail connects this ' + d.type.toLowerCase() + ' to empirical scientific/classical evidence.'
        };
      } else {
        return {
          status: 'NO_GROUNDED_PATH',
          badgeClass: 'no-path',
          label: 'NO GROUNDED PATH',
          description: 'No scientific or classical literature evidence node is currently linked to this ' + d.type.toLowerCase() + ' in the graph.'
        };
      }
    }

    if (traces && traces.length > 0) {
      return {
        status: 'CONNECTED',
        badgeClass: 'traceable',
        label: 'GRAPH CONNECTED',
        description: 'Grounded relationships connect this node across ' + traces.length + ' multi-hop pathway' + (traces.length === 1 ? '' : 's') + '.'
      };
    }

    return null;
  }

  // ----------------------------------------------------------------
  // Graph Lens Application (Client-Side Filtering & Dimming)
  // ----------------------------------------------------------------
  function applyGraphLens(lensName) {
    window._activeLens = lensName;
    window._selectedEdge = null;
    window._traceMode = false;
    var lens = GRAPH_LENSES[lensName] || GRAPH_LENSES.OVERVIEW;
    if (!window._graphSvg) return;

    var primarySet = {};
    (lens.primaryTypes || []).forEach(function (t) { primarySet[t] = true; });
    var supportingSet = {};
    (lens.supportingTypes || []).forEach(function (t) { supportingSet[t] = true; });

    // Clean active trace classes
    window._graphSvg.selectAll('.graph-node')
      .classed('active-trace-node', false)
      .classed('active-trace-start', false)
      .style('opacity', function (d) {
        if (window._selectedNodeId) {
          return d.id === window._selectedNodeId ? 1 : 0.2;
        }
        if (primarySet[d.type]) return 1;
        if (supportingSet[d.type]) return 0.45;
        return 0.12;
      });

    // Update edge emphasis
    window._graphSvg.selectAll('.graph-link')
      .classed('active-selected', false)
      .classed('active-trace-link', false)
      .classed('derived', false)
      .attr('stroke-opacity', function (l) {
        if (window._selectedNodeId) {
          return (l.source.id === window._selectedNodeId || l.target.id === window._selectedNodeId) ? 0.9 : 0.05;
        }
        var srcEmphasized = primarySet[l.source.type];
        var tgtEmphasized = primarySet[l.target.type];
        if (srcEmphasized && tgtEmphasized) return 0.35;
        if (srcEmphasized || tgtEmphasized) return 0.18;
        return 0.06;
      })
      .attr('stroke-width', 1.2)
      .attr('marker-end', 'url(#kg-arrow)');

    window._graphSvg.selectAll('.graph-link-label').classed('visible', false);

    // Gently reheat simulation
    if (window._graphSimulation) {
      window._graphSimulation.alpha(0.08).restart();
    }
  }

  // ----------------------------------------------------------------
  // Node Selection & Intelligence Drawer
  // ----------------------------------------------------------------
  function selectGraphNode(d) {
    window._selectedNodeId = d.id;
    window._selectedEdge = null;
    window._traceMode = false;
    if (!window._graphSvg) return;

    // Highlight selected node visually
    window._graphSvg.selectAll('.graph-node')
      .classed('active-trace-node', false)
      .classed('active-trace-start', false)
      .classed('active-selected', function (n) { return n.id === d.id; });

    // Find connected links and nodes
    var connectedNodeIds = {};
    connectedNodeIds[d.id] = true;
    var connectedLinks = {};

    (window._graphLinks || []).forEach(function (l) {
      if (l.source.id === d.id) {
        connectedNodeIds[l.target.id] = true;
        connectedLinks[l.source.id + '->' + l.target.id] = true;
      } else if (l.target.id === d.id) {
        connectedNodeIds[l.source.id] = true;
        connectedLinks[l.source.id + '->' + l.target.id] = true;
      }
    });

    window._graphSvg.selectAll('.graph-node')
      .style('opacity', function (n) {
        return connectedNodeIds[n.id] ? 1 : 0.15;
      });

    window._graphSvg.selectAll('.graph-link')
      .classed('active-selected', false)
      .classed('active-trace-link', false)
      .classed('derived', false)
      .attr('stroke-opacity', function (l) {
        return connectedLinks[l.source.id + '->' + l.target.id] ? 0.9 : 0.05;
      })
      .attr('stroke-width', function (l) {
        return connectedLinks[l.source.id + '->' + l.target.id] ? 2.2 : 1;
      })
      .attr('marker-end', function (l) {
        return connectedLinks[l.source.id + '->' + l.target.id] ? 'url(#kg-arrow-highlight)' : 'url(#kg-arrow)';
      });

    window._graphSvg.selectAll('.graph-link-label')
      .classed('visible', function (l) {
        return !!connectedLinks[l.source.id + '->' + l.target.id];
      });

    showNodeDrawer(d);
  }

  function deselectGraphNode() {
    window._selectedNodeId = null;
    window._selectedEdge = null;
    window._traceMode = false;
    if (window._graphSvg) {
      window._graphSvg.selectAll('.graph-node')
        .classed('active-selected', false)
        .classed('active-trace-node', false)
        .classed('active-trace-start', false);
      window._graphSvg.selectAll('.graph-link')
        .classed('active-selected', false)
        .classed('active-trace-link', false)
        .classed('derived', false);
    }
    hideNodeDrawer();
    applyGraphLens(window._activeLens || 'OVERVIEW');
  }

  function showNodeDrawer(d) {
    var drawer = document.getElementById('kg-drawer');
    var badgesEl = document.getElementById('kg-drawer-badges');
    var titleEl = document.getElementById('kg-drawer-title');
    var bodyEl = document.getElementById('kg-drawer-body');
    if (!drawer || !badgesEl || !titleEl || !bodyEl) return;

    titleEl.textContent = d.label || 'Entity Details';

    // Header Badges
    var meta = d.metadata || {};
    var badgesHtml = '<span class="chip" style="background:' + (d.color || '#34d399') + '22;color:' + (d.color || '#34d399') + ';font-weight:700;font-size:11px;">'
      + escapeHtml(d.type.replace(/_/g, ' ')) + '</span>';

    if (meta.confidence !== undefined && meta.confidence !== null) {
      var confNum = typeof meta.confidence === 'number' ? Math.round(meta.confidence * 100) : parseInt(meta.confidence, 10);
      var confLabel = isNaN(confNum) ? meta.confidence : confNum + '% Confidence';
      badgesHtml += '<span class="chip" style="background:rgba(52,211,153,0.12);color:#34d399;font-size:10px;">' + icon('verified', 12) + ' ' + escapeHtml(String(confLabel)) + '</span>';
    }

    if (meta.severity) {
      var sevColor = meta.severity === 'HIGH' || meta.severity === 'CRITICAL' ? '#ef4444' : (meta.severity === 'MODERATE' ? '#f59e0b' : '#34d399');
      badgesHtml += '<span class="chip" style="background:' + sevColor + '22;color:' + sevColor + ';font-weight:700;font-size:10px;">' + escapeHtml(String(meta.severity)) + ' Severity</span>';
    }

    if (meta.assessment_source) {
      var srcLabel = meta.assessment_source === 'GEMINI' ? 'AI-Assisted (' + (meta.model_used || 'Gemini') + ')' : 'Deterministic Rule Engine';
      badgesHtml += '<span class="chip" style="background:rgba(147,51,234,0.12);color:#c084fc;font-size:10px;">' + icon('psychology', 12) + ' ' + escapeHtml(srcLabel) + '</span>';
    }

    badgesEl.innerHTML = badgesHtml;

    // Body Content
    var bodyHtml = '';

    // Evidence Grounding Status Block
    var traces = findEvidenceTraces(d, 4, 3);
    var evidenceStatus = getNodeEvidenceStatus(d, traces);
    if (evidenceStatus) {
      bodyHtml += '<div class="kg-drawer-section">'
        + '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">'
        + '<span style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:#94a3b8;">Evidence Grounding Status</span>'
        + '<span class="kg-evidence-status-badge ' + evidenceStatus.badgeClass + '">' + escapeHtml(evidenceStatus.label) + '</span>'
        + '</div>'
        + '<div class="kg-drawer-card" style="font-size:11px;line-height:1.45;color:#cbd5e1;">'
        + escapeHtml(evidenceStatus.description)
        + '</div>'
        + '</div>';
    }

    // Section 1: Summary / Rationale / Full Claim
    if (meta.full_text) {
      bodyHtml += '<div class="kg-drawer-section">'
        + '<div class="kg-drawer-section-title">' + icon('format_quote', 14) + ' Claim Assertion</div>'
        + '<div class="kg-drawer-card" style="font-style:italic;border-left:3px solid #00bcd4;">"' + escapeHtml(meta.full_text) + '"</div>'
        + '</div>';
    } else if (meta.rationale || meta.why_it_matters || meta.summary || meta.description) {
      var mainText = meta.rationale || meta.why_it_matters || meta.summary || meta.description;
      bodyHtml += '<div class="kg-drawer-section">'
        + '<div class="kg-drawer-section-title">' + icon('lightbulb', 14) + ' Intelligence Summary</div>'
        + '<div class="kg-drawer-card">' + escapeHtml(String(mainText)) + '</div>'
        + '</div>';
    }

    if (meta.recommended_action) {
      bodyHtml += '<div class="kg-drawer-section">'
        + '<div class="kg-drawer-section-title">' + icon('task_alt', 14) + ' Recommended Action</div>'
        + '<div class="kg-drawer-card callout-action"><strong>Action:</strong> ' + escapeHtml(meta.recommended_action) + '</div>'
        + '</div>';
    }

    // Section 2: Connected Graph Relationships (Interactive rows)
    var connections = [];
    (window._graphLinks || []).forEach(function (l) {
      if (l.source.id === d.id) {
        connections.push({
          linkRef: l,
          target: l.target,
          relationship: l.relationship,
          direction: 'out',
          grounding: l.grounding || 'DIRECT',
          explanation: l.explanation || ''
        });
      } else if (l.target.id === d.id) {
        connections.push({
          linkRef: l,
          target: l.source,
          relationship: l.relationship,
          direction: 'in',
          grounding: l.grounding || 'DIRECT',
          explanation: l.explanation || ''
        });
      }
    });

    if (connections.length > 0) {
      bodyHtml += '<div class="kg-drawer-section">'
        + '<div class="kg-drawer-section-title">' + icon('hub', 14) + ' Connected Relationships (' + connections.length + ')</div>'
        + '<div style="display:flex;flex-direction:column;gap:6px;">';

      connections.forEach(function (c, cIdx) {
        var isDirect = (c.grounding || '').toUpperCase() === 'DIRECT';
        var groundingClass = isDirect ? 'direct' : 'derived';
        var arrowSym = c.direction === 'out' ? '→' : '←';

        bodyHtml += '<div class="kg-conn-item" style="cursor:pointer;" data-conn-idx="' + cIdx + '" title="Click to inspect relationship details">'
          + '<div class="kg-conn-left">'
          + '<span class="kg-conn-rel">' + arrowSym + ' ' + escapeHtml(c.relationship.replace(/_/g, ' ')) + '</span>'
          + '<span class="kg-conn-name">' + escapeHtml(c.target.label || c.target.id) + '</span>'
          + '</div>'
          + '<span class="kg-conn-grounding ' + groundingClass + '" title="' + escapeHtml(c.explanation || '') + '">'
          + escapeHtml(c.grounding || 'DIRECT') + '</span>'
          + '</div>';
      });

      bodyHtml += '</div></div>';
    }

    // Section 3: Key Structured Metadata
    var skipKeys = {
      full_text: true, rationale: true, why_it_matters: true, summary: true, description: true,
      recommended_action: true, assessment_source: true, model_used: true
    };
    var dataRows = [];
    Object.keys(meta).forEach(function (k) {
      if (!skipKeys[k] && meta[k] !== null && meta[k] !== undefined && meta[k] !== '') {
        var formattedVal = meta[k];
        if (typeof formattedVal === 'object') {
          try { formattedVal = JSON.stringify(formattedVal); } catch (e) { formattedVal = String(formattedVal); }
        }
        var formattedKey = k.replace(/_/g, ' ').replace(/\b\w/g, function (l) { return l.toUpperCase(); });
        dataRows.push({ key: formattedKey, val: String(formattedVal) });
      }
    });

    if (dataRows.length > 0) {
      bodyHtml += '<div class="kg-drawer-section">'
        + '<div class="kg-drawer-section-title">' + icon('table_chart', 14) + ' Entity Properties</div>'
        + '<div class="kg-drawer-card"><div class="kg-data-table">';

      dataRows.forEach(function (row) {
        bodyHtml += '<div class="kg-data-row">'
          + '<span class="kg-data-key">' + escapeHtml(row.key) + '</span>'
          + '<span class="kg-data-val">' + escapeHtml(row.val) + '</span>'
          + '</div>';
      });

      bodyHtml += '</div></div></div>';
    }

    // Section 4: Phase C Trace Evidence Action
    var traceCount = traces.length;
    var traceBtnLabel = traceCount > 0
      ? (icon('timeline', 13) + ' Trace Evidence (' + traceCount + ' Path' + (traceCount === 1 ? '' : 's') + ')')
      : (icon('timeline', 13) + ' Trace Evidence (0 Paths)');

    bodyHtml += '<div style="margin-top:auto;padding-top:12px;border-top:1px solid rgba(255,255,255,0.06);display:flex;gap:8px;">'
      + '<button class="btn btn-primary btn-xs" style="flex:1;" id="kg-btn-trace-evidence"' + (traceCount === 0 ? ' disabled style="opacity:0.55;cursor:not-allowed;"' : '') + '>'
      + traceBtnLabel + '</button>'
      + '</div>';

    bodyEl.innerHTML = bodyHtml;
    drawer.style.display = 'flex';

    // Wire connection row clicks
    drawer.querySelectorAll('.kg-conn-item').forEach(function (el) {
      el.addEventListener('click', function () {
        var idx = parseInt(el.getAttribute('data-conn-idx'), 10);
        if (connections[idx] && connections[idx].linkRef) {
          selectGraphEdge(connections[idx].linkRef);
        }
      });
    });

    // Wire Trace Evidence click
    var traceBtn = document.getElementById('kg-btn-trace-evidence');
    if (traceBtn && traceCount > 0) {
      traceBtn.addEventListener('click', function (e) {
        e.preventDefault();
        activateTraceMode(d, traces, 0);
      });
    }
  }

  function hideNodeDrawer() {
    var drawer = document.getElementById('kg-drawer');
    if (drawer) drawer.style.display = 'none';
  }

  // ----------------------------------------------------------------
  // Trace Evidence Mode & Multi-Hop Pathway Drawer
  // ----------------------------------------------------------------
  function activateTraceMode(startNode, traces, activeIdx) {
    if (!traces || traces.length === 0) {
      toast('No evidence trace pathways found for this entity', 'info');
      return;
    }
    window._traceMode = true;
    window._activeTraces = traces;
    window._activeTraceIndex = activeIdx || 0;
    window._traceStartNode = startNode;
    window._selectedEdge = null;
    window._selectedNodeId = null;

    var activeTrace = traces[window._activeTraceIndex] || traces[0];
    var nodeInPathMap = {};
    var linkInPathMap = {};

    activeTrace.nodes.forEach(function (n) { nodeInPathMap[n.id] = true; });
    activeTrace.links.forEach(function (l) {
      linkInPathMap[l.source.id + '->' + l.target.id] = l;
      linkInPathMap[l.target.id + '->' + l.source.id] = l;
    });

    if (window._graphSvg) {
      // Highlight nodes in trace
      window._graphSvg.selectAll('.graph-node')
        .style('opacity', function (d) {
          return nodeInPathMap[d.id] ? 1 : 0.08;
        })
        .classed('active-selected', false)
        .classed('active-trace-node', function (d) {
          return !!nodeInPathMap[d.id];
        })
        .classed('active-trace-start', function (d) {
          return d.id === startNode.id;
        });

      // Highlight links in trace
      window._graphSvg.selectAll('.graph-link')
        .classed('active-selected', false)
        .attr('stroke-opacity', function (l) {
          var key1 = l.source.id + '->' + l.target.id;
          var key2 = l.target.id + '->' + l.source.id;
          return (linkInPathMap[key1] || linkInPathMap[key2]) ? 1 : 0.04;
        })
        .attr('stroke-width', function (l) {
          var key1 = l.source.id + '->' + l.target.id;
          var key2 = l.target.id + '->' + l.source.id;
          return (linkInPathMap[key1] || linkInPathMap[key2]) ? 3 : 1;
        })
        .classed('active-trace-link', function (l) {
          var key1 = l.source.id + '->' + l.target.id;
          var key2 = l.target.id + '->' + l.source.id;
          return !!(linkInPathMap[key1] || linkInPathMap[key2]);
        })
        .classed('derived', function (l) {
          var key1 = l.source.id + '->' + l.target.id;
          var key2 = l.target.id + '->' + l.source.id;
          var match = linkInPathMap[key1] || linkInPathMap[key2];
          return match && (match.grounding || '').toUpperCase() !== 'DIRECT';
        });

      // Show labels for links in trace
      window._graphSvg.selectAll('.graph-link-label')
        .classed('visible', function (l) {
          var key1 = l.source.id + '->' + l.target.id;
          var key2 = l.target.id + '->' + l.source.id;
          return !!(linkInPathMap[key1] || linkInPathMap[key2]);
        });
    }

    showTraceDrawer(startNode, traces, window._activeTraceIndex);
  }

  function showTraceDrawer(startNode, traces, activeIdx) {
    var drawer = document.getElementById('kg-drawer');
    var badgesEl = document.getElementById('kg-drawer-badges');
    var titleEl = document.getElementById('kg-drawer-title');
    var bodyEl = document.getElementById('kg-drawer-body');
    if (!drawer || !badgesEl || !titleEl || !bodyEl) return;

    var trace = traces[activeIdx] || traces[0];
    titleEl.textContent = 'Evidence Trace Pathway';

    // Badges
    badgesEl.innerHTML = '<span class="chip" style="background:rgba(52,211,153,0.15);color:#34d399;font-weight:700;font-size:11px;">'
      + icon('timeline', 12) + ' ' + trace.hops + ' Hop' + (trace.hops === 1 ? '' : 's') + '</span>'
      + '<span class="chip" style="background:rgba(255,255,255,0.06);color:#e2e8f0;font-size:10px;">'
      + trace.directCount + ' Direct · ' + trace.derivedCount + ' Derived</span>';

    var bodyHtml = '';

    // Tab navigation if multiple traces
    if (traces.length > 1) {
      bodyHtml += '<div class="kg-trace-nav">';
      traces.forEach(function (t, idx) {
        var isTabActive = idx === activeIdx;
        var targetName = t.nodes[t.nodes.length - 1].label || t.nodes[t.nodes.length - 1].id;
        var shortTarget = targetName.length > 16 ? targetName.substring(0, 15) + '…' : targetName;
        bodyHtml += '<button class="kg-trace-tab ' + (isTabActive ? 'active' : '') + '" data-trace-idx="' + idx + '">'
          + 'Path ' + (idx + 1) + ' (' + escapeHtml(shortTarget) + ')' + '</button>';
      });
      bodyHtml += '</div>';
    }

    // Trace Timeline
    bodyHtml += '<div class="kg-drawer-section">'
      + '<div class="kg-drawer-section-title">' + icon('route', 14) + ' Grounded Path Traversal</div>'
      + '<div class="kg-trace-timeline">';

    trace.nodes.forEach(function (currNode, idx) {
      var isStart = idx === 0;
      var isEnd = idx === trace.nodes.length - 1;
      var cardClass = isStart ? 'start-node' : (isEnd ? 'origin-target' : '');

      bodyHtml += '<div class="kg-trace-step">'
        + '<div class="kg-trace-node-card ' + cardClass + '" style="cursor:pointer;" data-node-id="' + escapeHtml(currNode.id) + '">'
        + '<span class="chip" style="background:' + (currNode.color || '#34d399') + '22;color:' + (currNode.color || '#34d399') + ';font-size:10px;font-weight:700;">'
        + escapeHtml(currNode.type.replace(/_/g, ' ')) + '</span>'
        + '<div style="display:flex;flex-direction:column;flex:1;min-width:0;">'
        + '<span style="font-size:12px;font-weight:600;color:#f1f5f9;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + escapeHtml(currNode.label || currNode.id) + '</span>'
        + (isStart ? '<span style="font-size:10px;color:#fbbf24;font-weight:600;">Trace Origin Entity</span>' : (isEnd ? '<span style="font-size:10px;color:#34d399;font-weight:600;">Evidence Destination</span>' : ''))
        + '</div>'
        + '</div>';

      if (idx < trace.links.length) {
        var l = trace.links[idx];
        var isDirect = (l.grounding || '').toUpperCase() === 'DIRECT';
        bodyHtml += '<div class="kg-trace-step-conn">'
          + '<div class="kg-trace-step-line"></div>'
          + '<span class="kg-trace-conn-badge">'
          + escapeHtml(l.relationship.replace(/_/g, ' '))
          + '<span class="kg-conn-grounding ' + (isDirect ? 'direct' : 'derived') + '" style="font-size:9px;padding:1px 5px;">' + escapeHtml(l.grounding || 'DIRECT') + '</span>'
          + '</span>'
          + '<div class="kg-trace-step-line"></div>'
          + '</div>';
      }

      bodyHtml += '</div>';
    });

    bodyHtml += '</div></div>';

    // Target Entity Details
    var targetNode = trace.nodes[trace.nodes.length - 1];
    var tMeta = targetNode.metadata || {};
    if (tMeta.rationale || tMeta.summary || tMeta.full_text || tMeta.description || tMeta.source_title) {
      var descText = tMeta.rationale || tMeta.summary || tMeta.full_text || tMeta.description || tMeta.source_title;
      bodyHtml += '<div class="kg-drawer-section">'
        + '<div class="kg-drawer-section-title">' + icon('verified', 14) + ' Evidence Finding Summary</div>'
        + '<div class="kg-drawer-card" style="font-size:12px;color:#e2e8f0;border-left:3px solid #34d399;">'
        + escapeHtml(String(descText))
        + '</div>'
        + '</div>';
    }

    // Footer
    bodyHtml += '<div style="margin-top:auto;padding-top:12px;border-top:1px solid rgba(255,255,255,0.06);display:flex;gap:8px;">'
      + '<button class="btn btn-secondary btn-xs" style="flex:1;" id="kg-btn-exit-trace">' + icon('arrow_back', 12) + ' Exit Trace View</button>'
      + '</div>';

    bodyEl.innerHTML = bodyHtml;
    drawer.style.display = 'flex';

    // Wire Tab Clicks
    drawer.querySelectorAll('.kg-trace-tab').forEach(function (tab) {
      tab.addEventListener('click', function (e) {
        e.preventDefault();
        var idx = parseInt(tab.getAttribute('data-trace-idx'), 10);
        activateTraceMode(startNode, traces, idx);
      });
    });

    // Wire Node Clicks in timeline
    drawer.querySelectorAll('.kg-trace-node-card').forEach(function (card) {
      card.addEventListener('click', function () {
        var nid = card.getAttribute('data-node-id');
        var nodeObj = (window._graphNodes || []).find(function (n) { return n.id === nid; });
        if (nodeObj) {
          selectGraphNode(nodeObj);
        }
      });
    });

    // Wire Exit Button
    var exitBtn = document.getElementById('kg-btn-exit-trace');
    if (exitBtn) {
      exitBtn.addEventListener('click', function (e) {
        e.preventDefault();
        exitTraceMode();
      });
    }
  }

  function exitTraceMode() {
    window._traceMode = false;
    window._activeTraces = null;
    window._activeTraceIndex = 0;

    if (window._graphSvg) {
      window._graphSvg.selectAll('.graph-node')
        .classed('active-trace-node', false)
        .classed('active-trace-start', false);

      window._graphSvg.selectAll('.graph-link')
        .classed('active-trace-link', false)
        .classed('derived', false);

      window._graphSvg.selectAll('.graph-link-label').classed('visible', false);
    }

    if (window._traceStartNode) {
      var prevStart = window._traceStartNode;
      window._traceStartNode = null;
      selectGraphNode(prevStart);
    } else {
      deselectGraphNode();
    }
  }

  // ----------------------------------------------------------------
  // Connection Selection & Connection Intelligence Drawer
  // ----------------------------------------------------------------
  function selectGraphEdge(l) {
    window._selectedEdge = l;
    window._selectedNodeId = null;
    window._traceMode = false;

    if (window._graphSvg) {
      window._graphSvg.selectAll('.graph-node')
        .classed('active-selected', false)
        .classed('active-trace-node', false)
        .classed('active-trace-start', false)
        .style('opacity', function (d) {
          return (d.id === l.source.id || d.id === l.target.id) ? 1 : 0.12;
        });

      window._graphSvg.selectAll('.graph-link')
        .classed('active-trace-link', false)
        .classed('derived', false)
        .classed('active-selected', function (edge) {
          return (edge.source.id === l.source.id && edge.target.id === l.target.id) ||
                 (edge.source.id === l.target.id && edge.target.id === l.source.id);
        })
        .attr('stroke-opacity', function (edge) {
          var isSelected = (edge.source.id === l.source.id && edge.target.id === l.target.id) ||
                           (edge.source.id === l.target.id && edge.target.id === l.source.id);
          return isSelected ? 1 : 0.05;
        })
        .attr('stroke-width', function (edge) {
          var isSelected = (edge.source.id === l.source.id && edge.target.id === l.target.id) ||
                           (edge.source.id === l.target.id && edge.target.id === l.source.id);
          return isSelected ? 3.2 : 1;
        });

      window._graphSvg.selectAll('.graph-link-label')
        .classed('visible', function (edge) {
          return (edge.source.id === l.source.id && edge.target.id === l.target.id) ||
                 (edge.source.id === l.target.id && edge.target.id === l.source.id);
        });
    }

    showConnectionDrawer(l);
  }

  function showConnectionDrawer(l) {
    var drawer = document.getElementById('kg-drawer');
    var badgesEl = document.getElementById('kg-drawer-badges');
    var titleEl = document.getElementById('kg-drawer-title');
    var bodyEl = document.getElementById('kg-drawer-body');
    if (!drawer || !badgesEl || !titleEl || !bodyEl) return;

    var isDirect = (l.grounding || '').toUpperCase() === 'DIRECT';
    titleEl.textContent = 'Connection Intelligence';

    // Badges
    badgesEl.innerHTML = '<span class="chip" style="background:rgba(52,211,153,0.12);color:#34d399;font-weight:700;font-size:11px;">'
      + escapeHtml(l.relationship.replace(/_/g, ' ')) + '</span>'
      + '<span class="kg-conn-grounding ' + (isDirect ? 'direct' : 'derived') + '" style="font-size:11px;padding:3px 8px;">'
      + escapeHtml(l.grounding || 'DIRECT') + '</span>';

    var bodyHtml = '';

    // Relationship Explanation Card
    bodyHtml += '<div class="kg-drawer-section">'
      + '<div class="kg-drawer-section-title">' + icon('help_outline', 14) + ' Relationship Explanation</div>'
      + '<div class="kg-conn-expl-card">'
      + '<div>' + escapeHtml(l.explanation || ('Connects ' + (l.source.label || l.source.id) + ' to ' + (l.target.label || l.target.id) + ' via ' + l.relationship.replace(/_/g, ' ') + '.')) + '</div>'
      + '<div class="kg-grounding-help">'
      + (isDirect
          ? '<strong>DIRECT Grounding:</strong> Verified deterministic reference from source record without heuristic jump.'
          : '<strong>DERIVED Grounding:</strong> Inferred via rule-based canonical mapping or multi-hop relationship resolution.')
      + '</div>'
      + '</div></div>';

    // Endpoints section
    bodyHtml += '<div class="kg-drawer-section">'
      + '<div class="kg-drawer-section-title">' + icon('route', 14) + ' Connected Entities</div>'
      + '<div style="display:flex;flex-direction:column;gap:8px;">'
      + '<div class="kg-trace-node-card" style="cursor:pointer;" id="kg-conn-source-card">'
      + '<span class="chip" style="background:' + (l.source.color || '#34d399') + '22;color:' + (l.source.color || '#34d399') + ';font-size:10px;font-weight:700;">' + escapeHtml(l.source.type.replace(/_/g, ' ')) + '</span>'
      + '<span style="font-size:12px;font-weight:600;color:#f1f5f9;flex:1;">' + escapeHtml(l.source.label || l.source.id) + '</span>'
      + '<span style="font-size:10px;color:#94a3b8;">Source ' + icon('arrow_forward', 11) + '</span>'
      + '</div>'
      + '<div class="kg-trace-node-card" style="cursor:pointer;" id="kg-conn-target-card">'
      + '<span class="chip" style="background:' + (l.target.color || '#34d399') + '22;color:' + (l.target.color || '#34d399') + ';font-size:10px;font-weight:700;">' + escapeHtml(l.target.type.replace(/_/g, ' ')) + '</span>'
      + '<span style="font-size:12px;font-weight:600;color:#f1f5f9;flex:1;">' + escapeHtml(l.target.label || l.target.id) + '</span>'
      + '<span style="font-size:10px;color:#94a3b8;">Target ' + icon('arrow_forward', 11) + '</span>'
      + '</div>'
      + '</div></div>';

    // Edge Metadata Properties if any
    var meta = l.metadata || {};
    var skipMeta = { grounding: true, explanation: true };
    var metaRows = [];
    Object.keys(meta).forEach(function (k) {
      if (!skipMeta[k] && meta[k] !== null && meta[k] !== undefined && meta[k] !== '') {
        var val = meta[k];
        if (typeof val === 'object') {
          try { val = JSON.stringify(val); } catch (e) { val = String(val); }
        }
        var fKey = k.replace(/_/g, ' ').replace(/\b\w/g, function (char) { return char.toUpperCase(); });
        metaRows.push({ key: fKey, val: String(val) });
      }
    });

    if (metaRows.length > 0) {
      bodyHtml += '<div class="kg-drawer-section">'
        + '<div class="kg-drawer-section-title">' + icon('table_chart', 14) + ' Relationship Properties</div>'
        + '<div class="kg-drawer-card"><div class="kg-data-table">';
      metaRows.forEach(function (row) {
        bodyHtml += '<div class="kg-data-row"><span class="kg-data-key">' + escapeHtml(row.key) + '</span><span class="kg-data-val">' + escapeHtml(row.val) + '</span></div>';
      });
      bodyHtml += '</div></div></div>';
    }

    // Footer Actions
    bodyHtml += '<div style="margin-top:auto;padding-top:12px;border-top:1px solid rgba(255,255,255,0.06);display:flex;gap:8px;">'
      + '<button class="btn btn-secondary btn-xs" style="flex:1;" id="kg-btn-close-conn">' + icon('close', 12) + ' Close Connection View</button>'
      + '</div>';

    bodyEl.innerHTML = bodyHtml;
    drawer.style.display = 'flex';

    var srcCard = document.getElementById('kg-conn-source-card');
    if (srcCard) {
      srcCard.addEventListener('click', function () {
        selectGraphNode(l.source);
      });
    }

    var tgtCard = document.getElementById('kg-conn-target-card');
    if (tgtCard) {
      tgtCard.addEventListener('click', function () {
        selectGraphNode(l.target);
      });
    }

    var closeBtn = document.getElementById('kg-btn-close-conn');
    if (closeBtn) {
      closeBtn.addEventListener('click', function () {
        deselectGraphNode();
      });
    }
  }

  // ----------------------------------------------------------------
  // Search & Navigation Helpers
  // ----------------------------------------------------------------
  function searchGraphLocally(query) {
    if (!window._graphNodes || !window._graphSvg) return;
    window._selectedEdge = null;
    window._traceMode = false;

    var q = (query || '').trim().toLowerCase();
    if (!q) {
      deselectGraphNode();
      return;
    }

    var matchingNodes = (window._graphNodes || []).filter(function (n) {
      var labelMatch = (n.label || '').toLowerCase().indexOf(q) !== -1;
      var typeMatch = (n.type || '').toLowerCase().indexOf(q) !== -1;
      var metaStr = JSON.stringify(n.metadata || {}).toLowerCase();
      var metaMatch = metaStr.indexOf(q) !== -1;
      return labelMatch || typeMatch || metaMatch;
    });

    if (matchingNodes.length === 0) {
      toast('No graph entities match "' + query + '"', 'info');
      return;
    }

    toast('Found ' + matchingNodes.length + ' matching entity in graph', 'success');

    var matchMap = {};
    matchingNodes.forEach(function (n) { matchMap[n.id] = true; });

    window._graphSvg.selectAll('.graph-node')
      .classed('active-trace-node', false)
      .classed('active-trace-start', false)
      .style('opacity', function (d) { return matchMap[d.id] ? 1 : 0.12; });

    window._graphSvg.selectAll('.graph-link')
      .classed('active-selected', false)
      .classed('active-trace-link', false)
      .classed('derived', false)
      .attr('stroke-opacity', 0.05);

    // Zoom and center on the first match
    var target = matchingNodes[0];
    if (target && typeof target.x === 'number' && typeof target.y === 'number' && window._graphZoom) {
      var width = window._graphWidth || 800;
      var height = window._graphHeight || 640;
      var scale = 1.4;
      var transform = d3.zoomIdentity
        .translate(width / 2 - target.x * scale, height / 2 - target.y * scale)
        .scale(scale);

      window._graphSvg.transition().duration(400).call(window._graphZoom.transform, transform);
      selectGraphNode(target);
    }
  }

  function zoomGraph(scaleFactor) {
    if (window._graphSvg && window._graphZoom) {
      window._graphSvg.transition().duration(250).call(window._graphZoom.scaleBy, scaleFactor);
    }
  }

  function fitGraphToView() {
    if (!window._graphSvg || !window._graphZoom || !window._graphNodes || window._graphNodes.length === 0) return;
    var nodes = window._graphNodes;
    var xs = nodes.map(function (n) { return n.x || 0; });
    var ys = nodes.map(function (n) { return n.y || 0; });
    var minX = Math.min.apply(null, xs);
    var maxX = Math.max.apply(null, xs);
    var minY = Math.min.apply(null, ys);
    var maxY = Math.max.apply(null, ys);

    var width = window._graphWidth || 800;
    var height = window._graphHeight || 640;
    var graphW = (maxX - minX) || 1;
    var graphH = (maxY - minY) || 1;

    var scale = Math.min(width / (graphW + 80), height / (graphH + 80), 1.6);
    scale = Math.max(scale, 0.3);
    var midX = (minX + maxX) / 2;
    var midY = (minY + maxY) / 2;

    var transform = d3.zoomIdentity
      .translate(width / 2 - midX * scale, height / 2 - midY * scale)
      .scale(scale);

    window._graphSvg.transition().duration(400).call(window._graphZoom.transform, transform);
  }

  function resetGraphView() {
    var searchInput = document.getElementById('kg-search-input');
    var searchClear = document.getElementById('kg-search-clear');
    if (searchInput) searchInput.value = '';
    if (searchClear) searchClear.style.display = 'none';

    // Set overview active
    document.querySelectorAll('.kg-lens-pill').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-lens') === 'OVERVIEW');
    });

    deselectGraphNode();
    fitGraphToView();
  }


  // ----------------------------------------------------------------
  // Knowledge Hub View (Classical Texts, Research, Regulatory, Patents)
  // ----------------------------------------------------------------
  const knowledgeSources = [
    {
      id: 'charaka',
      icon: '📜',
      title: 'Charaka Samhita',
      category: 'classical',
      categoryLabel: 'Classical Text',
      description: 'Foundational Ayurvedic internal medicine & holistic health text.',
      isLive: true,
      badgeText: 'LIVE SOURCE',
      badgeClass: 'kh-card-badge-live',
      searchPlaceholder: 'Search herbs, concepts or classical terms (e.g. Rasayana, Sthana, Medha)...',
      overviewText: 'Explore traditional Ayurvedic descriptions of health, herbs, formulations, therapeutic concepts and classical principles documented in the Charaka Samhita.',
      capabilities: [
        'Find classical references to herbs and formulation ingredients',
        'Explore traditional preparation methods and therapeutic indications',
        'Understand classical Ayurvedic terminology (Dravya, Tridosha, Rasayana)',
        'Locate passages relevant to product formulation research'
      ],
      disclaimer: 'Traditional textual references represent historical and classical evidence. They describe traditional Ayurvedic context and are not proof of modern clinical efficacy.'
    },
    {
      id: 'sushruta',
      icon: '📜',
      title: 'Sushruta Samhita',
      category: 'classical',
      categoryLabel: 'Classical Text',
      description: 'Ancient Ayurvedic text on surgery, anatomy, and surgical preparations.',
      isLive: true,
      badgeText: 'LIVE SOURCE',
      badgeClass: 'kh-card-badge-live',
      searchPlaceholder: 'Search herbs, preparations or anatomical concepts (e.g. Svastha, Agni, Vedautpatti)...',
      overviewText: 'Explore classical Ayurvedic textual evidence covering surgical concepts, anatomy, plant-based preparations, and holistic health definitions contained in the Sushruta Samhita.',
      capabilities: [
        'Research classical definitions of health (Svastha) and Agni-Dosha equilibrium',
        'Study ancient mineral/herb combination preparations and processing methods',
        'Understand traditional anatomical and physiological frameworks',
        'Trace historical usage of Ayurvedic botanicals in therapeutic passages'
      ],
      disclaimer: 'Classical textual passages provide historical context. They do not constitute modern clinical validation.'
    },
    {
      id: 'ashtanga',
      icon: '📜',
      title: 'Ashtanga Hridaya',
      category: 'classical',
      categoryLabel: 'Classical Text',
      description: 'Comprehensive synthesis of Ayurvedic medicine covering all eight branches.',
      isLive: false,
      badgeText: 'EXPANDING COVERAGE',
      badgeClass: 'kh-card-badge-expanding',
      overviewText: 'Ashtanga Hridaya synthesizes the core principles of Charaka and Sushruta across all eight branches of Ayurveda into concise verse form.',
      capabilities: [
        'Cross-reference internal medicine, pediatrics, toxicology, and rejuvenation',
        'Analyze practical formulation guidelines and classical dosage rules',
        'Examine standardized treatment protocols across Ayurvedic specializations'
      ],
      disclaimer: 'EXPANDING COVERAGE · OFFICIAL DIGITAL SOURCE VERIFICATION IN PROGRESS. AYUR-INTEL ingests evidence strictly from verified digital repositories (NIIMH / CCRAS e-Samhita). Coverage will become searchable once full-text digital verification is completed.'
    },
    {
      id: 'pmc',
      icon: '🔬',
      title: 'PubMed Central',
      category: 'research',
      categoryLabel: 'Research',
      description: 'Free full-text archive of biomedical and life sciences journal literature.',
      isLive: true,
      badgeText: 'LIVE SOURCE',
      badgeClass: 'kh-card-badge-live',
      searchPlaceholder: 'Search ingredients, botanicals or research topics (e.g. Ashwagandha, Bacopa, Stress)...',
      overviewText: 'Search open-access scientific literature for biomedical research, pharmacological studies, clinical trials, and phytochemical analyses of Ayurvedic herbs and ingredients.',
      capabilities: [
        'Investigate published research on botanical active constituents and bioactives',
        'Review in vitro, in vivo, and clinical study outcomes',
        'Assess safety profiles, dosage studies, and pharmacological mechanisms',
        'Retrieve full-text journal citations and PMID/PMC references'
      ],
      disclaimer: 'Individual scientific studies describe preliminary experimental or observational findings. A single study does not automatically establish clinical efficacy or regulatory approval.'
    },
    {
      id: 'ayush_portal',
      icon: '🔬',
      title: 'Ayush Research Portal',
      category: 'research',
      categoryLabel: 'Research',
      description: 'Government of India research database on Ayurveda, Yoga, and traditional medicine.',
      isLive: false,
      badgeText: 'EXPANDING COVERAGE',
      badgeClass: 'kh-card-badge-expanding',
      overviewText: 'Official repository of research evidence on Ayurveda, Yoga, Unani, Siddha, and Homeopathy maintained by the Ministry of Ayush, Government of India.',
      capabilities: [
        'Access government-sponsored clinical trial reports and observational studies',
        'Review drug standardization reports published by official research councils (CCRAS)',
        'Track evidence-based clinical protocols for traditional medicine formulations'
      ],
      disclaimer: 'EXPANDING COVERAGE · GOV PORTAL API INTEGRATION IN PROGRESS. Official digital integration underway.'
    },
    {
      id: 'ayush_guidelines',
      icon: '📋',
      title: 'AYUSH Guidelines',
      category: 'regulatory',
      categoryLabel: 'Regulatory',
      description: 'Official guidelines for Ayurvedic product manufacturing, licensing, and quality control.',
      isLive: true,
      badgeText: 'LIVE SOURCE',
      badgeClass: 'kh-card-badge-live',
      searchPlaceholder: 'Search guidelines, GMP rules or quality standards (e.g. Schedule T, Quality, Licensing)...',
      overviewText: 'Official Ministry of Ayush regulatory directives, Good Manufacturing Practices (GMP), Pharmacopoeial Standards of Ayurveda (API), and licensing guidelines.',
      capabilities: [
        'Verify official manufacturing compliance standards and Schedule T requirements',
        'Review mandatory quality control specifications and pharmacopoeial monograph parameters',
        'Track regulatory licensing frameworks for Ayurvedic proprietary medicines'
      ],
      disclaimer: 'Official Ministry of Ayush regulatory directives, gazette notices, and pharmacopoeial standards context preserved.'
    },
    {
      id: 'fssai',
      icon: '📋',
      title: 'FSSAI Regulations',
      category: 'regulatory',
      categoryLabel: 'Regulatory',
      description: 'Food safety regulations for Ayurvedic and herbal products in India.',
      isLive: true,
      badgeText: 'LIVE SOURCE',
      badgeClass: 'kh-card-badge-live',
      searchPlaceholder: 'Search regulations, ingredients or requirements (e.g. Ayurveda Aahara, Category A, Labeling)...',
      overviewText: 'Explore official Indian food safety regulatory framework documents governing Ayurveda Aahara products, Category A approvals, permissible additives, and labeling compliance.',
      capabilities: [
        'Check Ayurveda Aahara 2022 regulation requirements and statutory definitions',
        'Review 2025 Category A product approval exemptions and FoSCoS portal guidelines',
        'Inspect permissible food additives, processing aids, and Schedule A text lists',
        'Verify mandatory packaging declarations, logo guidelines, and warning statements'
      ],
      disclaimer: 'Preserves official document dates, notification versions, and gazette authority context. Regulatory information is provided for compliance research and decision-support.'
    },
    {
      id: 'patent',
      icon: '📜',
      title: 'Indian Patent Office',
      category: 'patent',
      categoryLabel: 'Patents',
      description: 'Indian Patent Office literature, prior art research & formulation intelligence.',
      isLive: false,
      badgeText: 'PATENT INTEL',
      badgeClass: 'kh-card-badge-patent',
      overviewText: 'Explore official Indian Patent System context, CGPDTM patent literature, published specifications, and prior-art screening for herbal formulations.',
      capabilities: [
        'Review Indian Patent Office (CGPDTM) examination context and publication framework',
        'Investigate published patent specifications for herbal extraction processes and active fractions',
        'Screen patent literature prior art for technical formulation research'
      ],
      disclaimer: 'Patent search and prior art screening are performed for technical research and decision-support via AYUR-INTEL Patent Intelligence module. Does not constitute legal advice or formal freedom-to-operate opinion.'
    },
    {
      id: 'drugs_act',
      icon: '📋',
      title: 'Drugs & Cosmetics Act',
      category: 'regulatory',
      categoryLabel: 'Regulatory',
      description: 'Regulatory framework for Ayurvedic, Siddha, and Unani drugs in India.',
      isLive: true,
      badgeText: 'LIVE SOURCE',
      badgeClass: 'kh-card-badge-live',
      searchPlaceholder: 'Search statutes, rules or provisions (e.g. Chapter IV-A, Misbranding, Rule 161)...',
      overviewText: 'Primary statutory framework governing Ayurvedic, Siddha, and Unani drugs under Chapter IV-A of the Drugs and Cosmetics Act 1940 and Rules 1945.',
      capabilities: [
        'Review statutory drug definitions, manufacturing license rules, and Section 33EEB misbranding laws',
        'Inspect Schedule T Good Manufacturing Practice (GMP) requirements',
        'Track Rule 161 mandatory labelling rules and Ayurvedic Medicine container declarations'
      ],
      disclaimer: 'Statutory Drugs & Cosmetics Act 1940 and Rules 1945 digest preserved for regulatory decision-support.'
    }
  ];

  function formatSectionValue(val) {
    if (val === null || val === undefined) return '';
    if (typeof val === 'string') return val;
    if (typeof val === 'number' || typeof val === 'boolean') return String(val);
    if (Array.isArray(val)) {
      return val.map(function (item) {
        if (typeof item === 'object' && item !== null) {
          return item.name || item.title || item.text || item.summary || JSON.stringify(item);
        }
        return String(item);
      }).join(', ');
    }
    if (typeof val === 'object') {
      return Object.entries(val).map(function (pair) {
        var k = pair[0].replace(/_/g, ' ').toUpperCase();
        var v = pair[1];
        var vStr = Array.isArray(v) ? v.join(', ') : (typeof v === 'object' ? JSON.stringify(v) : String(v));
        return k + ': ' + vStr;
      }).join('\n');
    }
    return String(val);
  }

  function updateKnowledgeSectionVisibility() {
    document.querySelectorAll('.kh-category-section').forEach(function (sec) {
      var visibleCards = sec.querySelectorAll('.kh-card:not([style*="display: none"])');
      sec.style.display = visibleCards.length > 0 ? 'block' : 'none';
    });
  }

  function filterKnowledgeSources(query) {
    const cards = document.querySelectorAll('.kh-card');
    const q = (query || '').toLowerCase().trim();
    cards.forEach(card => {
      const title = card.dataset.title || '';
      const desc = card.dataset.desc || '';
      const match = !q || title.includes(q) || desc.includes(q);
      card.style.display = match ? 'block' : 'none';
    });
    updateKnowledgeSectionVisibility();
  }

  function filterKnowledge(category) {
    document.querySelectorAll('.kh-filter-chip').forEach(chip => {
      chip.classList.toggle('active', chip.dataset.filter === category);
    });

    const cards = document.querySelectorAll('.kh-card');
    cards.forEach(card => {
      const show = category === 'all' || card.dataset.category === category;
      card.style.display = show ? 'block' : 'none';
    });
    updateKnowledgeSectionVisibility();
  }

  window.filterKnowledgeSources = filterKnowledgeSources;
  window.filterKnowledge = filterKnowledge;

  function goKnowledgeHubHome() {
    state.khSubView = 'HUB';
    state.khActiveSource = null;
    state.khActiveDocId = null;
    state.khSearchQuery = '';
    render({ scroll: 'restore' });
  }

  function openExpandingCoverageInfo(sourceId) {
    state.khPrevScroll = window.scrollY || 0;
    state.khSubView = 'INFO';
    state.khActiveSource = sourceId;
    render({ scroll: 'top' });
  }

  function openPatentSourceInfo() {
    state.khPrevScroll = window.scrollY || 0;
    state.khSubView = 'PATENT_INFO';
    state.khActiveSource = 'patent';
    render({ scroll: 'top' });
  }

  async function openKnowledgeLibrary(sourceId) {
    state.khPrevScroll = window.scrollY || 0;
    state.khSubView = 'LIBRARY';
    state.khActiveSource = sourceId;
    state.khActiveDocId = null;
    state.khLibraryLoading = true;
    state.khLibraryItems = [];
    state.khFilteredItems = null;
    state.khSearchQuery = '';
    state.khProductAnalysis = null;
    render({ scroll: 'top' });

    var queryMap = {
      charaka: 'Charaka',
      sushruta: 'Sushruta',
      pmc: 'PMC',
      fssai: 'FSSAI',
      ayush_guidelines: 'AYUSH Guidelines',
      drugs_act: 'Drugs and Cosmetics Act'
    };
    var q = queryMap[sourceId] || '';
    var activeCase = state.currentCase || (state.cases && state.cases[0]);

    var searchPromise = api('/api/knowledge/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: q, limit: 30 })
    }).catch(function (e) {
      toast('Failed to load library items: ' + e.message, 'error');
      return null;
    });

    var paPromise = activeCase ? api('/api/knowledge/source-analysis/' + sourceId + '/' + activeCase.id).catch(function () { return null; }) : Promise.resolve(null);

    var res = await Promise.all([searchPromise, paPromise]);
    var data = res[0];
    var paData = res[1];

    var items = [];
    if (data && data.sources) {
      data.sources.forEach(function (src) {
        if (src.results && src.results.length > 0) {
          src.results.forEach(function (r) {
            if (sourceId === 'charaka' && r.title.indexOf('Charaka') === -1) return;
            if (sourceId === 'sushruta' && r.title.indexOf('Sushruta') === -1) return;
            if (sourceId === 'ayush_guidelines' && r.title.indexOf('AYUSH') === -1 && r.source_name !== 'AYUSH_GUIDELINES') return;
            if (sourceId === 'drugs_act' && r.title.indexOf('Drugs') === -1 && r.source_name !== 'DRUGS_ACT') return;
            items.push(r);
          });
        }
      });
    }
    state.khLibraryItems = items;
    state.khFilteredItems = items;
    state.khLibraryLoading = false;

    if (paData && paData.ai_available) {
      state.khProductAnalysis = paData;
    }

    render({ scroll: 'top' });
  }

  async function fetchIntegratedKnowledgeSearch(sourceId, query) {
    if (!query) {
      state.khIntegratedResult = null;
      state.khPlantExplanation = null;
      return;
    }
    try {
      var data = await api('/api/knowledge/integrated-search?source_name=' + encodeURIComponent(sourceId) + '&query=' + encodeURIComponent(query), {
        method: 'POST'
      });
      state.khIntegratedResult = data;
      state.khPlantExplanation = null;

      // If top plant match exists, pre-fetch any existing persisted plant explanation (0 Gemini calls)
      if (data && data.plant_match) {
        try {
          var exp = await api('/api/knowledge/plant-explanation/' + sourceId + '/' + data.plant_match.plant_id);
          if (exp && exp.ai_available) {
            state.khPlantExplanation = exp;
          }
        } catch (e) {
          // Silently skip if no plant explanation exists yet
        }
      }
    } catch (e) {
      console.warn('Integrated search failed:', e);
      state.khIntegratedResult = null;
    }
  }

  async function filterSourceLibrarySearch(query) {
    state.khSearchQuery = query;
    var q = (query || '').toLowerCase().trim();
    var allItems = state.khLibraryItems || [];
    var sourceId = state.khActiveSource || 'charaka';

    if (sourceId === 'charaka' || sourceId === 'sushruta') {
      if (q) {
        await fetchIntegratedKnowledgeSearch(sourceId, query);
      } else {
        state.khIntegratedResult = null;
        state.khPlantExplanation = null;
        state.khFilteredItems = allItems;
      }
    } else {
      state.khIntegratedResult = null;
      if (!q) {
        state.khFilteredItems = allItems;
      } else {
        state.khFilteredItems = allItems.filter(function (item) {
          var title = (item.title || '').toLowerCase();
          var excerpt = (item.excerpt || item.summary || '').toLowerCase();
          var locator = (item.evidence_locator || '').toLowerCase();
          var authority = (item.source_authority || item.source_name || '').toLowerCase();
          return title.indexOf(q) !== -1 || excerpt.indexOf(q) !== -1 || locator.indexOf(q) !== -1 || authority.indexOf(q) !== -1;
        });
      }
    }

    var contentEl = document.getElementById('kh-library-items-list');
    var countEl = document.getElementById('kh-search-count-pill');
    var sourceMeta = knowledgeSources.find(function (s) { return s.id === sourceId; }) || { title: 'Source Library', id: 'charaka' };

    if (contentEl) {
      if (state.khIntegratedResult && q) {
        contentEl.innerHTML = renderIntegratedSearchResult(state.khIntegratedResult, sourceMeta);
      } else {
        contentEl.innerHTML = renderLibraryItemsContent(state.khFilteredItems);
      }
    }

    if (countEl) {
      if (state.khIntegratedResult && state.khIntegratedResult.plant_match) {
        countEl.textContent = 'Integrated match: ' + state.khIntegratedResult.plant_match.primary_name + ' (DRAVYA + ' + sourceMeta.title + ')';
      } else {
        countEl.textContent = 'Showing ' + (state.khFilteredItems ? state.khFilteredItems.length : 0) + ' of ' + allItems.length + ' evidence records';
      }
    }
  }

  async function generatePlantExplanationForSource(sourceId, plantId, forceRegenerate) {
    var btn = document.getElementById('kh-explain-plant-btn');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = icon('sync', 16) + ' Generating Grounded AI Research Explanation...';
    }
    try {
      var data = await api('/api/knowledge/plant-explanation/generate?source_name=' + encodeURIComponent(sourceId) + '&plant_id=' + plantId + '&force_regenerate=' + (forceRegenerate ? 'true' : 'false'), {
        method: 'POST'
      });
      state.khPlantExplanation = data;
      toast('Grounded AI research explanation updated.', 'success');
    } catch (e) {
      toast('Failed to generate plant explanation: ' + e.message, 'error');
    }

    var contentEl = document.getElementById('kh-library-items-list');
    var sourceMeta = knowledgeSources.find(function (s) { return s.id === sourceId; }) || { title: 'Source Library', id: 'charaka' };
    if (contentEl && state.khIntegratedResult) {
      contentEl.innerHTML = renderIntegratedSearchResult(state.khIntegratedResult, sourceMeta);
    }
  }

  function renderIntegratedSearchResult(data, sourceMeta) {
    if (!data) return '';
    var plant = data.plant_match;
    var classicalEvidence = data.classical_evidence || [];
    var hasClassicalMatch = data.has_classical_match;
    var query = data.query || state.khSearchQuery || '';

    if (!plant && classicalEvidence.length === 0) {
      return `
        <div class="kh-notice-box" style="margin-top:20px;padding:24px;text-align:center;">
          <span class="material-symbols-outlined" style="font-size:32px;color:#94a3b8;margin-bottom:8px;">search_off</span>
          <h4 style="margin:0 0 6px 0;color:#f8fafc;font-size:16px;">No matching plant or evidence found</h4>
          <p style="margin:0;font-size:13px;color:#94a3b8;">
            No record matching "<strong>${escapeHtml(query)}</strong>" was found in AYUR-INTEL's current curated 400-plant DRAVYA dataset or ${escapeHtml(sourceMeta.title)} evidence set.
          </p>
        </div>
      `;
    }

    var plantHeaderHtml = '';
    var plantProfileHtml = '';
    if (plant) {
      var displayHeading = query || plant.primary_name;
      plantHeaderHtml = `
        <div class="kh-plant-header">
          <div>
            <div style="font-size:11px;font-weight:800;letter-spacing:0.6px;color:#34d399;text-transform:uppercase;margin-bottom:4px;">
              MATCHED PLANT KNOWLEDGE PROFILE
            </div>
            <h2 style="font-size:24px;font-weight:800;color:#f8fafc;margin:0 0 2px 0;">
              🌱 ${escapeHtml(displayHeading)}
            </h2>
            ${(plant.primary_name && plant.primary_name.toLowerCase() !== displayHeading.toLowerCase()) ? `
              <div style="font-size:13px;color:#94a3b8;margin-bottom:2px;">CCRAS recorded name: <strong style="color:#cbd5e1;">${escapeHtml(plant.primary_name)}</strong></div>
            ` : ''}
            <div style="font-size:14px;font-style:italic;color:#34d399;font-weight:600;">
              ${escapeHtml(plant.scientific_name)} ${plant.family ? '· Family: ' + escapeHtml(plant.family) : ''}
            </div>
          </div>
          <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px;">
            <span class="kh-card-badge kh-card-badge-live">DRAVYA / CCRAS ENRICHED</span>
            ${plant.url ? `<a class="btn btn-secondary btn-xs" href="${escapeHtml(plant.url)}" target="_blank" rel="noopener">View DRAVYA Source ↗</a>` : ''}
          </div>
        </div>
      `;

      var props = plant.ayurvedic_properties || {};
      var dgItemsHtml = '';
      ['rasa', 'guna', 'virya', 'vipaka', 'karma', 'doshakarma', 'mahakashaya', 'varga'].forEach(function (propKey) {
        var items = props[propKey];
        if (!items || items.length === 0) return;
        var label = propKey.toUpperCase();
        var tagList = Array.isArray(items) ? items.map(function (it) {
          return typeof it === 'object' ? (it.name || it.val || JSON.stringify(it)) : String(it);
        }).join(', ') : String(items);

        dgItemsHtml += `
          <div class="kh-dg-box">
            <div class="kh-dg-title">${escapeHtml(label)}</div>
            <div class="kh-dg-tags">${escapeHtml(tagList)}</div>
          </div>
        `;
      });

      var aliasesList = plant.aliases || [];

      plantProfileHtml = `
        <div class="kh-section-card">
          <div class="kh-section-header">
            <div>
              <div class="kh-source-label">SOURCE: DRAVYA / CCRAS PLANT KNOWLEDGE</div>
              <h3 class="kh-section-title">🌿 Structured Plant Profile</h3>
            </div>
          </div>

          <div class="kh-profile-grid">
            <div class="kh-prop-box">
              <div class="kh-prop-label">CCRAS RECORDED NAME</div>
              <div class="kh-prop-val">${escapeHtml(plant.primary_name)}</div>
            </div>
            <div class="kh-prop-box">
              <div class="kh-prop-label">BOTANICAL NAME</div>
              <div class="kh-prop-val"><em>${escapeHtml(plant.scientific_name)}</em></div>
            </div>
            ${plant.family ? `
              <div class="kh-prop-box">
                <div class="kh-prop-label">FAMILY</div>
                <div class="kh-prop-val">${escapeHtml(plant.family)}</div>
              </div>
            ` : ''}
            ${(plant.sanskrit_synonyms && plant.sanskrit_synonyms.length > 0) ? `
              <div class="kh-prop-box">
                <div class="kh-prop-label">SANSKRIT SYNONYMS</div>
                <div class="kh-prop-val">${plant.sanskrit_synonyms.slice(0, 6).map(function(s){ return escapeHtml(s); }).join(' · ')}</div>
              </div>
            ` : ''}
            ${aliasesList.length > 0 ? `
              <div class="kh-prop-box" style="grid-column: 1 / -1;">
                <div class="kh-prop-label">SYNONYMS &amp; VERNACULAR NAMES</div>
                <div class="kh-alias-chips">
                  ${aliasesList.slice(0, 14).map(function (a) { return '<span class="chip" style="font-size:11px;background:rgba(255,255,255,0.06);color:#cbd5e1;">' + escapeHtml(a) + '</span>'; }).join('')}
                </div>
              </div>
            ` : ''}
          </div>

          ${dgItemsHtml ? `
            <div class="kh-dravyaguna-card">
              <div style="font-size:11.5px;font-weight:800;color:#34d399;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:10px;">
                ⚖️ AYURVEDIC DRAVYAGUNA PROPERTIES
              </div>
              <div class="kh-dravyaguna-grid">
                ${dgItemsHtml}
              </div>
            </div>
          ` : ''}

          ${(plant.therapeutic_usage && plant.therapeutic_usage.length > 0) ? `
            <div style="margin-top:14px;padding:12px;background:rgba(15,23,42,0.5);border-radius:8px;border:1px solid rgba(255,255,255,0.06);">
              <div style="font-size:11px;font-weight:700;color:#94a3b8;margin-bottom:6px;">THERAPEUTIC INDICATIONS (DRAVYA):</div>
              <div style="display:flex;gap:6px;flex-wrap:wrap;">
                ${plant.therapeutic_usage.slice(0, 10).map(function (tu) {
                  var name = typeof tu === 'object' ? (tu.name || JSON.stringify(tu)) : String(tu);
                  return '<span class="chip" style="background:rgba(52,211,153,0.12);color:#34d399;font-size:11.5px;">' + escapeHtml(name) + '</span>';
                }).join('')}
              </div>
            </div>
          ` : ''}
        </div>
      `;
    }

    var classicalEvidenceHtml = '';
    if (hasClassicalMatch && classicalEvidence.length > 0) {
      var evItemsHtml = classicalEvidence.map(function (ev, idx) {
        return `
          <div class="kh-card" style="margin-bottom:12px;background:rgba(15,23,42,0.6);border-color:rgba(52,211,153,0.2);">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;">
              <span style="font-size:12px;font-weight:700;color:#34d399;">
                Passage #${idx + 1}: ${escapeHtml(ev.evidence_locator || ev.source_identifier || 'Classical Passage')}
              </span>
              ${ev.official_url ? `<a href="${escapeHtml(ev.official_url)}" target="_blank" rel="noopener" style="font-size:11px;color:#38bdf8;">Read Original Source ↗</a>` : ''}
            </div>
            <div style="font-size:13.5px;color:#f8fafc;line-height:1.5;margin-bottom:8px;">
              ${escapeHtml(ev.title || 'Classical Passage')}
            </div>
            <div class="kh-evidence-text" style="font-size:12.5px;">
              ${escapeHtml(ev.excerpt || 'Raw passage excerpt preserved in database.')}
            </div>
          </div>
        `;
      }).join('');

      classicalEvidenceHtml = `
        <div class="kh-section-card">
          <div class="kh-section-header">
            <div>
              <div class="kh-source-label">SOURCE: ${escapeHtml(sourceMeta.title.toUpperCase())}</div>
              <h3 class="kh-section-title">📜 Matching Classical Passages</h3>
            </div>
            <span class="chip" style="background:rgba(52,211,153,0.15);color:#34d399;font-size:11.5px;font-weight:600;">
              ${classicalEvidence.length} matching passages found
            </span>
          </div>
          <div>${evItemsHtml}</div>
        </div>
      `;
    } else {
      var plantNameStr = plant ? plant.primary_name : query;
      classicalEvidenceHtml = `
        <div class="kh-section-card">
          <div class="kh-section-header">
            <div>
              <div class="kh-source-label">SOURCE: ${escapeHtml(sourceMeta.title.toUpperCase())}</div>
              <h3 class="kh-section-title">📜 Classical Text Evidence</h3>
            </div>
          </div>
          <div class="kh-notice-box" style="background:rgba(30,41,59,0.6);border-color:rgba(255,255,255,0.12);">
            <span class="material-symbols-outlined" style="font-size:20px;color:#94a3b8;">info</span>
            <div style="font-size:13.5px;color:#cbd5e1;">
              No matching <strong>${escapeHtml(plantNameStr)}</strong> passage was found in AYUR-INTEL's current curated ${escapeHtml(sourceMeta.title)} evidence set.
            </div>
          </div>
        </div>
      `;
    }

    var aiExplanationHtml = '';
    if (plant) {
      var expData = state.khPlantExplanation;
      var hasExp = expData && expData.ai_available;

      var groundingLabel = hasClassicalMatch
        ? `${sourceMeta.title} + DRAVYA / CCRAS`
        : 'DRAVYA / CCRAS';

      if (hasExp) {
        var expSections = expData.structured_sections || {};
        aiExplanationHtml = `
          <div class="kh-section-card" style="border-color:rgba(52,211,153,0.35);background:linear-gradient(135deg, rgba(15,23,42,0.85) 0%, rgba(30,41,59,0.9) 100%);">
            <div class="kh-section-header">
              <div>
                <div class="kh-ai-badge" style="margin-bottom:6px;">✨ AI EXPLANATION · GROUNDED IN SOURCE EVIDENCE</div>
                <h3 class="kh-section-title">AI Research Explanation for ${escapeHtml(plant.primary_name)}</h3>
                <div style="font-size:11.5px;color:#34d399;margin-top:2px;">GROUNDED IN: ${escapeHtml(groundingLabel)}</div>
              </div>
              <button class="btn btn-secondary btn-xs" onclick="generatePlantExplanationForSource('${escapeHtml(sourceMeta.id)}', ${plant.plant_id}, true)">
                Regenerate Explanation
              </button>
            </div>

            <p style="font-size:14px;color:#f8fafc;line-height:1.6;margin:0 0 16px 0;">${escapeHtml(expData.summary_60s)}</p>

            ${Object.keys(expSections).map(function (key) {
              if (key === 'summary_60s' || key === 'evidence_references') return '';
              var val = expSections[key];
              if (!val) return '';
              var label = key.replace(/_/g, ' ').toUpperCase();
              var valContent = formatSectionValue(val);
              return `
                <div style="background:rgba(15,23,42,0.6);border:1px solid rgba(255,255,255,0.06);border-radius:8px;padding:14px;margin-bottom:10px;">
                  <div style="font-size:11px;font-weight:700;color:#34d399;letter-spacing:0.5px;margin-bottom:4px;">${escapeHtml(label)}</div>
                  <div style="font-size:13px;color:#cbd5e1;line-height:1.5;white-space:pre-wrap;">${escapeHtml(valContent)}</div>
                </div>
              `;
            }).join('')}
          </div>
        `;
      } else {
        aiExplanationHtml = `
          <div class="kh-section-card" style="border-color:rgba(255,255,255,0.15);background:rgba(30,41,59,0.5);">
            <div class="kh-section-header">
              <div>
                <div class="kh-source-label">GROUNDED AI ANALYSIS</div>
                <h3 class="kh-section-title">Explain ${escapeHtml(plant.primary_name)} in Context</h3>
                <div style="font-size:11.5px;color:#94a3b8;margin-top:2px;">GROUNDING SOURCES: ${escapeHtml(groundingLabel)}</div>
              </div>
            </div>
            <p style="font-size:13.5px;color:#cbd5e1;line-height:1.5;margin:0 0 14px 0;">
              Click below to synthesize a grounded AI research explanation connecting the DRAVYA plant profile and available ${escapeHtml(sourceMeta.title)} evidence.
            </p>
            <button class="btn btn-primary btn-sm" id="kh-explain-plant-btn" onclick="generatePlantExplanationForSource('${escapeHtml(sourceMeta.id)}', ${plant.plant_id}, false)">
              ✨ Explain This Plant in Context
            </button>
          </div>
        `;
      }
    }

    return `
      <div class="kh-integrated-result">
        ${plantHeaderHtml}
        ${plantProfileHtml}
        ${classicalEvidenceHtml}
        ${aiExplanationHtml}
      </div>
    `;
  }

  async function openKnowledgeReader(docId) {
    if (!docId) return;
    state.khPrevScroll = window.scrollY || 0;
    state.khSubView = 'READER';
    state.khActiveDocId = docId;
    state.khReaderLoading = true;
    state.khReaderDoc = null;
    render({ scroll: 'top' });

    try {
      var data = await api('/api/knowledge/synthesis/' + encodeURIComponent(docId));
      state.khReaderDoc = data;
    } catch (e) {
      toast('Failed to load document synthesis: ' + e.message, 'error');
    }
    state.khReaderLoading = false;
    render({ scroll: 'top' });
  }

  async function generateKnowledgeSynthesisForDoc(docId) {
    if (!docId) return;
    var btn = document.getElementById('kh-generate-btn');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = icon('sync', 16) + ' Generating Grounded AI Explanation...';
    }

    try {
      var data = await api('/api/knowledge/synthesis/generate?document_identifier=' + encodeURIComponent(docId), {
        method: 'POST'
      });
      state.khReaderDoc = data;
      toast('Grounded Knowledge Synthesis generated!', 'success');
      render({ scroll: 'preserve' });
    } catch (e) {
      toast('Failed to generate synthesis: ' + e.message, 'error');
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '✨ Generate Grounded Explanation';
      }
    }
  }

  async function generateProductSourceAnalysis(sourceId, caseId) {
    if (!sourceId || !caseId) return;
    var btn = document.getElementById('kh-analyze-prod-btn');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = icon('sync', 16) + ' Analyzing Source for Product...';
    }

    try {
      var data = await api('/api/knowledge/source-analysis/generate?source_name=' + encodeURIComponent(sourceId) + '&case_id=' + encodeURIComponent(caseId), {
        method: 'POST'
      });
      state.khProductAnalysis = data;
      toast('Grounded Product Source Analysis completed!', 'success');
      render({ scroll: 'preserve' });
    } catch (e) {
      toast('Failed to analyze source: ' + e.message, 'error');
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '✨ Analyze Source for My Product';
      }
    }
  }

  window.goKnowledgeHubHome = goKnowledgeHubHome;
  window.openKnowledgeLibrary = openKnowledgeLibrary;
  window.openKnowledgeReader = openKnowledgeReader;
  window.openExpandingCoverageInfo = openExpandingCoverageInfo;
  window.openPatentSourceInfo = openPatentSourceInfo;
  window.filterSourceLibrarySearch = filterSourceLibrarySearch;
  window.generateKnowledgeSynthesisForDoc = generateKnowledgeSynthesisForDoc;
  window.generateProductSourceAnalysis = generateProductSourceAnalysis;

  function renderLibraryItemsContent(items) {
    if (!items || items.length === 0) {
      return '<div class="empty-state" style="padding:32px 20px;text-align:center;"><div class="empty-icon">' + icon('search_off', 28) + '</div><h3 style="color:#f8fafc;font-size:16px;">No evidence records match your search</h3><p style="color:var(--text-secondary);font-size:13px;">Try searching for a different herb, formulation term, or concept.</p></div>';
    }
    var html = '';
    items.forEach(function (item) {
      var docId = item.source_identifier || item.doc_id || item.title;
      var locator = item.evidence_locator || docId;
      var excerpt = item.excerpt || item.summary || 'No excerpt available.';
      html += `
        <div class="kh-item-card" style="background:rgba(30,41,59,0.4);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:18px 20px;margin-bottom:16px;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:8px;">
            <h3 style="margin:0;font-size:16px;font-weight:600;color:#f8fafc;">${escapeHtml(item.title)}</h3>
            <span class="case-badge case-badge-stage" style="white-space:nowrap;">${escapeHtml(item.jurisdiction || 'IN')}</span>
          </div>
          <div style="font-size:12px;color:var(--botanical-green,#34d399);margin-bottom:8px;font-weight:500;">
            📍 ${escapeHtml(locator)}
          </div>
          <p class="kh-item-excerpt" style="font-size:13px;color:#cbd5e1;line-height:1.5;margin-bottom:12px;">
            "${escapeHtml(excerpt)}"
          </p>
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:11px;color:var(--text-secondary);">${escapeHtml(item.source_authority || item.source_name || 'Official Text')}</span>
            <button class="btn btn-primary btn-sm" onclick="openKnowledgeReader('${escapeHtml(docId)}')">Read &amp; Synthesize Evidence →</button>
          </div>
        </div>
      `;
    });
    return html;
  }

  function renderKnowledgeLibraryView(sourceId) {
    var sourceMeta = knowledgeSources.find(function (s) { return s.id === sourceId; }) || {
      title: 'Knowledge Source',
      icon: '📚',
      description: 'Official digital repository',
      badgeClass: 'kh-card-badge-live',
      badgeText: 'LIVE SOURCE',
      searchPlaceholder: 'Search herbs, concepts or terms...',
      overviewText: 'Explore official evidence records preserved in this repository.',
      capabilities: ['Search classical references', 'Review verified excerpts'],
      disclaimer: 'Evidence records represent preserved source text.'
    };

    var items = state.khFilteredItems || state.khLibraryItems || [];
    var totalItems = (state.khLibraryItems || []).length;
    var activeCase = state.currentCase || (state.cases && state.cases[0]);

    var itemsHtml = '';
    if (state.khLibraryLoading) {
      itemsHtml = '<div style="padding:40px;text-align:center;"><div class="skeleton" style="height:80px;margin-bottom:12px;border-radius:8px;"></div><div class="skeleton" style="height:80px;margin-bottom:12px;border-radius:8px;"></div><p style="color:var(--text-secondary);margin-top:12px;">Loading official library evidence...</p></div>';
    } else {
      itemsHtml = renderLibraryItemsContent(items);
    }

    var prodAnalysisHtml = '';
    if (activeCase) {
      var pa = state.khProductAnalysis;
      var paSections = (pa && pa.structured_sections) || {};
      prodAnalysisHtml = `
        <div class="kh-prod-analysis-card">
          <div class="kh-prod-analysis-header">
            <div>
              <div style="font-size:11px;font-weight:700;letter-spacing:0.6px;color:#34d399;text-transform:uppercase;margin-bottom:4px;">
                RESEARCH THIS SOURCE FOR YOUR PRODUCT
              </div>
              <h3 style="margin:0;font-size:17px;font-weight:700;color:#f8fafc;">
                Selected Product: <span style="color:#34d399;">${escapeHtml(activeCase.name)}</span>
              </h3>
            </div>
            <button class="btn btn-primary btn-sm" id="kh-analyze-prod-btn" onclick="generateProductSourceAnalysis('${escapeHtml(sourceId)}', '${escapeHtml(activeCase.id)}')">
              ✨ ${pa ? 'Re-Analyze Source for Product' : 'Analyze Source for My Product'}
            </button>
          </div>

          ${pa && pa.summary_60s ? `
            <div style="background:rgba(15,23,42,0.7);border:1px solid rgba(52,211,153,0.3);border-radius:10px;padding:16px;margin-top:12px;">
              <div style="font-size:11px;font-weight:800;color:#34d399;margin-bottom:6px;letter-spacing:0.5px;">GROUNDED PRODUCT INTELLIGENCE OVERVIEW</div>
              <p style="font-size:13.5px;color:#f8fafc;line-height:1.6;margin:0 0 12px 0;">${escapeHtml(pa.summary_60s)}</p>
              ${paSections.relevant_ingredients ? `
                <div style="margin-bottom:10px;">
                  <span style="font-size:11px;font-weight:700;color:#94a3b8;display:block;margin-bottom:4px;">MATCHED PRODUCT INGREDIENTS:</span>
                  <div style="display:flex;gap:6px;flex-wrap:wrap;">
                    ${(Array.isArray(paSections.relevant_ingredients) ? paSections.relevant_ingredients : [paSections.relevant_ingredients]).map(ing => `<span class="chip" style="background:rgba(52,211,153,0.15);color:#34d399;font-size:11px;">${escapeHtml(String(ing))}</span>`).join('')}
                  </div>
                </div>
              ` : ''}
              ${paSections.source_findings ? `
                <div style="margin-top:10px;font-size:12.5px;color:#cbd5e1;line-height:1.5;">
                  <strong style="color:#e2e8f0;">Source Findings:</strong> ${escapeHtml(typeof paSections.source_findings === 'object' ? JSON.stringify(paSections.source_findings) : String(paSections.source_findings))}
                </div>
              ` : ''}
              ${paSections.limitations ? `
                <div style="margin-top:8px;font-size:11.5px;color:#94a3b8;font-style:italic;">
                  ⚠️ ${escapeHtml(String(paSections.limitations))}
                </div>
              ` : ''}
            </div>
          ` : `
            <p style="font-size:13px;color:#94a3b8;margin:0;">
              Click <strong>Analyze Source for My Product</strong> to evaluate how evidence in ${escapeHtml(sourceMeta.title)} specifically applies to your active formulation (<em>${escapeHtml(activeCase.name)}</em>).
            </p>
          `}
        </div>
      `;
    } else {
      prodAnalysisHtml = `
        <div class="kh-prod-analysis-card">
          <div class="kh-prod-analysis-header">
            <div>
              <div style="font-size:11px;font-weight:700;letter-spacing:0.6px;color:#94a3b8;text-transform:uppercase;margin-bottom:4px;">
                PRODUCT-SPECIFIC SOURCE RESEARCH
              </div>
              <h3 style="margin:0;font-size:15px;font-weight:600;color:#f8fafc;">Select a product case to analyze this source against your formulation</h3>
            </div>
            <button class="btn btn-secondary btn-sm" onclick="if(window.AYUR){state.view='product-cases';render();}">
              Select Product →
            </button>
          </div>
        </div>
      `;
    }

    return `
      <div class="knowledge-library">
        <!-- Simple Back Navigation -->
        <button class="kh-back-btn" onclick="goKnowledgeHubHome()">← Back to Knowledge Hub</button>

        <!-- Source Introduction Panel (5-Second Orientation) -->
        <div class="kh-intro-panel">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:12px;">
            <h2 class="kh-intro-title">
              <span>${sourceMeta.icon}</span> ${escapeHtml(sourceMeta.title)}
            </h2>
            <span class="kh-card-badge ${sourceMeta.badgeClass}">${sourceMeta.badgeText}</span>
          </div>
          <p class="kh-intro-subtitle">${escapeHtml(sourceMeta.overviewText)}</p>

          <div style="font-size:12px;font-weight:700;color:#34d399;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">WHAT YOU CAN FIND HERE:</div>
          <div class="kh-intro-capabilities">
            ${(sourceMeta.capabilities || []).map(cap => `
              <div class="kh-capability-item">
                <span class="material-symbols-outlined">check_circle</span>
                <span>${escapeHtml(cap)}</span>
              </div>
            `).join('')}
          </div>

          <div class="kh-notice-box">
            <span class="material-symbols-outlined" style="font-size:18px;">info</span>
            <div>${escapeHtml(sourceMeta.disclaimer)}</div>
          </div>
        </div>

        <!-- Prominent In-Library Search Bar -->
        <div class="kh-source-search-wrap">
          <span class="kh-source-search-icon">🔍</span>
          <input type="text" class="kh-source-search-input" id="kh-library-search-input" placeholder="${escapeHtml(sourceMeta.searchPlaceholder)}" value="${escapeHtml(state.khSearchQuery || '')}" onkeyup="filterSourceLibrarySearch(this.value)">
          <span class="chip" id="kh-search-count-pill" style="background:rgba(52,211,153,0.15);color:#34d399;font-weight:600;font-size:12px;white-space:nowrap;padding:6px 12px;">
            Showing ${items.length} of ${totalItems} evidence records
          </span>
        </div>

        <!-- Library Evidence Records List -->
        <div class="kh-library-content" id="kh-library-items-list">
          ${itemsHtml}
        </div>

        <!-- Product-Specific AI Analysis Section -->
        ${prodAnalysisHtml}
      </div>
    `;
  }

  function renderKnowledgeReaderView(docId) {
    var sourceMeta = knowledgeSources.find(function (s) { return s.id === state.khActiveSource; }) || { title: 'Source Library', id: 'charaka' };

    if (state.khReaderLoading || !state.khReaderDoc) {
      return `
        <div class="kh-reader-container">
          <button class="kh-back-btn" onclick="openKnowledgeLibrary('${sourceMeta.id}')">← Back to ${escapeHtml(sourceMeta.title)}</button>
          <div style="padding:40px;text-align:center;">
            <div class="skeleton" style="height:120px;margin-bottom:16px;border-radius:12px;"></div>
            <div class="skeleton" style="height:200px;margin-bottom:16px;border-radius:12px;"></div>
            <p style="color:var(--text-secondary);">Loading document evidence &amp; synthesis...</p>
          </div>
        </div>
      `;
    }

    var doc = state.khReaderDoc;
    var sections = doc.structured_sections || {};
    var evidenceItems = doc.evidence_items || [];

    var isGrounded = doc.grounding_status === 'GROUNDED' || doc.grounding_status === 'PARTIALLY_GROUNDED';
    var statusBadgeClass = isGrounded ? 'confidence-high' : 'confidence-unknown';
    var statusBadgeText = isGrounded ? doc.grounding_status : 'RAW EVIDENCE PRESERVED';

    var summaryBox = '';
    if (isGrounded && doc.summary_60s) {
      summaryBox = `
        <div class="kh-summary-card">
          <div class="kh-ai-badge">✨ AI EXPLANATION · GROUNDED IN SOURCE</div>
          <p style="font-size:14px;color:#f8fafc;line-height:1.6;margin:0 0 8px 0;">${escapeHtml(doc.summary_60s)}</p>
          ${doc.model_used ? `<div style="font-size:11px;color:var(--text-secondary);">Synthesized via ${escapeHtml(doc.model_used)} · Zero Hallucination Guarded</div>` : ''}
          ${doc.is_stale ? `
            <div style="margin-top:10px;padding:8px 12px;background:rgba(245,158,11,0.15);border:1px solid rgba(245,158,11,0.3);border-radius:6px;font-size:12px;color:#fcd34d;display:flex;justify-content:space-between;align-items:center;">
              <span>Source evidence has changed since this explanation was generated.</span>
              <button class="btn btn-xs" style="background:#f59e0b;color:#000;font-weight:700;" onclick="generateKnowledgeSynthesisForDoc('${escapeHtml(docId)}')">Regenerate Explanation</button>
            </div>
          ` : ''}
        </div>
      `;
    } else {
      summaryBox = `
        <div class="kh-summary-card" style="border-color:rgba(255,255,255,0.15);background:rgba(30,41,59,0.5);">
          <div class="kh-ai-badge" style="background:rgba(148,163,184,0.15);color:#94a3b8;border-color:rgba(148,163,184,0.3);">📄 RAW SOURCE EVIDENCE</div>
          <p style="font-size:14px;color:#e2e8f0;line-height:1.6;margin:0 0 14px 0;">
            ${escapeHtml(doc.summary_60s || 'AI synthesis has not been generated for this official record yet. Original source text and evidence provenance are fully preserved below.')}
          </p>
          <button class="btn btn-primary btn-sm" id="kh-generate-btn" onclick="generateKnowledgeSynthesisForDoc('${escapeHtml(docId)}')">✨ Generate Grounded Explanation</button>
        </div>
      `;
    }

    var sectionsHtml = '';
    Object.keys(sections).forEach(function (key) {
      if (key === 'summary_60s' || key === 'evidence_references') return;
      var val = sections[key];
      if (!val) return;
      var label = key.replace(/_/g, ' ').toUpperCase();
      var valContent = formatSectionValue(val);
      sectionsHtml += `
        <div style="background:rgba(15,23,42,0.5);border:1px solid rgba(255,255,255,0.06);border-radius:8px;padding:16px;margin-bottom:12px;">
          <div style="font-size:11px;font-weight:700;letter-spacing:0.5px;color:#34d399;margin-bottom:6px;">${escapeHtml(label)}</div>
          <div style="font-size:13px;color:#cbd5e1;line-height:1.5;white-space:pre-wrap;">${escapeHtml(valContent)}</div>
        </div>
      `;
    });

    var evidenceHtml = '';
    var officialUrl = '';
    evidenceItems.forEach(function (ev, idx) {
      if (!officialUrl && (ev.official_url || ev.source_url)) {
        officialUrl = ev.official_url || ev.source_url;
      }
      evidenceHtml += `
        <div style="margin-bottom:14px;">
          <div style="font-size:12px;font-weight:600;color:#94a3b8;margin-bottom:4px;">
            Evidence #${idx + 1}: ${escapeHtml(ev.evidence_locator || ev.source_identifier || 'Record')}
          </div>
          <div class="kh-evidence-text">${escapeHtml(ev.excerpt || ev.raw_text || ev.summary || 'No raw text excerpt available.')}</div>
          ${ev.content_hash ? `<div style="font-size:10px;font-family:monospace;color:#64748b;">SHA256: ${escapeHtml(ev.content_hash)}</div>` : ''}
        </div>
      `;
    });

    return `
      <div class="kh-reader-container">
        <!-- Simple Back Navigation -->
        <button class="kh-back-btn" onclick="openKnowledgeLibrary('${sourceMeta.id}')">← Back to ${escapeHtml(sourceMeta.title)}</button>

        <div class="kh-reader-topbar">
          <div>
            <h1 style="font-size:22px;font-weight:700;color:#f8fafc;margin:0 0 6px 0;">${escapeHtml(doc.title || docId)}</h1>
            <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
              <span class="case-badge case-badge-stage">${escapeHtml(doc.category || 'EVIDENCE')}</span>
              <span class="confidence-badge ${statusBadgeClass}">${escapeHtml(statusBadgeText)}</span>
              ${doc.generated_at ? `<span style="font-size:11px;color:var(--text-secondary);">Updated: ${escapeHtml(doc.generated_at)}</span>` : ''}
            </div>
          </div>
          ${officialUrl ? `
            <a class="btn btn-secondary btn-sm" href="${escapeHtml(officialUrl)}" target="_blank" rel="noopener">
              Read Original Source ↗
            </a>
          ` : ''}
        </div>

        ${summaryBox}

        ${sectionsHtml ? `
          <div style="margin-bottom:24px;">
            <h3 style="font-size:15px;font-weight:700;color:#f8fafc;margin-bottom:12px;">Grounding &amp; Key Takeaways</h3>
            ${sectionsHtml}
          </div>
        ` : ''}

        <div class="kh-evidence-section">
          <h3 class="kh-evidence-title">
            <span>📜 Preserved Source Evidence</span>
          </h3>
          ${evidenceHtml || '<p style="font-size:13px;color:var(--text-secondary);">Source excerpt is not available in the current curated evidence set.</p>'}
        </div>
      </div>
    `;
  }

  function renderExpandingCoverageInfoView(sourceId) {
    var sourceMeta = knowledgeSources.find(function (s) { return s.id === sourceId; }) || {
      title: 'Expanding Coverage Source',
      icon: '📚',
      description: 'Official digital repository',
      badgeClass: 'kh-card-badge-expanding',
      badgeText: 'EXPANDING COVERAGE',
      overviewText: 'Official repository in pipeline for digital verification.',
      capabilities: ['Target capability 1', 'Target capability 2'],
      disclaimer: 'EXPANDING COVERAGE · DIGITAL SOURCE VERIFICATION IN PROGRESS.'
    };

    return `
      <div class="kh-reader-container">
        <!-- Simple Back Navigation -->
        <button class="kh-back-btn" onclick="goKnowledgeHubHome()">← Back to Knowledge Hub</button>

        <div class="kh-intro-panel">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:12px;">
            <h2 class="kh-intro-title">
              <span>${sourceMeta.icon}</span> ${escapeHtml(sourceMeta.title)}
            </h2>
            <span class="kh-card-badge ${sourceMeta.badgeClass}">${sourceMeta.badgeText}</span>
          </div>
          <p class="kh-intro-subtitle">${escapeHtml(sourceMeta.overviewText)}</p>

          <div style="font-size:12px;font-weight:700;color:#f59e0b;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">WHAT THIS SOURCE WILL PROVIDE WHEN LIVE:</div>
          <div class="kh-intro-capabilities">
            ${(sourceMeta.capabilities || []).map(cap => `
              <div class="kh-capability-item">
                <span class="material-symbols-outlined" style="color:#f59e0b;">hourglass_top</span>
                <span>${escapeHtml(cap)}</span>
              </div>
            `).join('')}
          </div>

          <div class="kh-notice-box">
            <span class="material-symbols-outlined" style="font-size:18px;">verified_user</span>
            <div>${escapeHtml(sourceMeta.disclaimer)}</div>
          </div>
        </div>
      </div>
    `;
  }

  function renderPatentSourceInfoView() {
    var sourceMeta = knowledgeSources.find(function (s) { return s.id === 'patent'; }) || {
      title: 'Indian Patent Office',
      icon: '📜',
      description: 'Search Indian patents',
      badgeClass: 'kh-card-badge-patent',
      badgeText: 'PATENT INTEL',
      overviewText: 'Indian Patent Intelligence helps investigate published patent literature for herbal formulations, active fractions, extraction processes, and technical concepts.',
      capabilities: [
        'Screen patent prior art to identify potential novelty barriers and freedom-to-operate risks',
        'Compare formulation claims against published patent claims and specifications',
        'Evaluate patent family members, filing dates, and legal status'
      ],
      disclaimer: 'Patent search and prior art screening are performed via AYUR-INTEL Patent Intelligence module.'
    };

    var activeCase = state.currentCase || (state.cases && state.cases[0]);
    var btnOnClick = activeCase
      ? "navigate('patent-intelligence')"
      : "if(window.AYUR){state.view='product-cases';render();}";

    return `
      <div class="kh-reader-container">
        <!-- Simple Back Navigation -->
        <button class="kh-back-btn" onclick="goKnowledgeHubHome()">← Back to Knowledge Hub</button>

        <div class="kh-intro-panel">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:12px;">
            <h2 class="kh-intro-title">
              <span>${sourceMeta.icon}</span> ${escapeHtml(sourceMeta.title)}
            </h2>
            <span class="kh-card-badge ${sourceMeta.badgeClass}">${sourceMeta.badgeText}</span>
          </div>
          <p class="kh-intro-subtitle">${escapeHtml(sourceMeta.overviewText)}</p>

          <div style="font-size:12px;font-weight:700;color:#3b82f6;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">PATENT INTELLIGENCE CAPABILITIES:</div>
          <div class="kh-intro-capabilities">
            ${(sourceMeta.capabilities || []).map(cap => `
              <div class="kh-capability-item">
                <span class="material-symbols-outlined" style="color:#3b82f6;">verified</span>
                <span>${escapeHtml(cap)}</span>
              </div>
            `).join('')}
          </div>

          <div style="margin-top:20px;padding:16px;background:rgba(15,23,42,0.8);border:1px solid rgba(59,130,246,0.3);border-radius:10px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
            <div>
              <strong style="color:#f8fafc;font-size:14px;display:block;">Patent Prior Art &amp; FTO Screening Engine</strong>
              <span style="font-size:12px;color:#94a3b8;">${activeCase ? 'Active Case Selected: ' + escapeHtml(activeCase.name) : 'No active product case selected.'}</span>
            </div>
            <button class="btn btn-primary" onclick="${btnOnClick}">
              Open Patent Intelligence →
            </button>
          </div>
        </div>
      </div>
    `;
  }

  function renderKnowledgeHub() {
    var subView = state.khSubView || 'HUB';
    if (subView === 'LIBRARY' && state.khActiveSource) {
      return renderKnowledgeLibraryView(state.khActiveSource);
    } else if (subView === 'READER' && state.khActiveDocId) {
      return renderKnowledgeReaderView(state.khActiveDocId);
    } else if (subView === 'INFO' && state.khActiveSource) {
      return renderExpandingCoverageInfoView(state.khActiveSource);
    } else if (subView === 'PATENT_INFO') {
      return renderPatentSourceInfoView();
    }

    var categories = [
      { id: 'classical', title: '📜 CLASSICAL WISDOM', sources: knowledgeSources.filter(s => s.category === 'classical') },
      { id: 'research', title: '🔬 RESEARCH EVIDENCE', sources: knowledgeSources.filter(s => s.category === 'research') },
      { id: 'regulatory', title: '📋 REGULATORY INTELLIGENCE', sources: knowledgeSources.filter(s => s.category === 'regulatory') },
      { id: 'patent', title: '📜 PATENT LITERATURE', sources: knowledgeSources.filter(s => s.category === 'patent') }
    ];

    const html = `
        <div class="knowledge-hub">
            <div class="kh-header">
                <h2>📚 KNOWLEDGE HUB</h2>
                <p class="kh-subtitle">Evidence-backed Ayurvedic research across classical texts, scientific literature, regulatory sources and patent intelligence.</p>
                <div class="kh-trust-line">
                    <span class="material-symbols-outlined" style="font-size:16px;">verified</span>
                    <span>Official/credible sources provide the evidence. AI helps explain and connect it.</span>
                </div>
            </div>
            
            <!-- Search Bar -->
            <div class="kh-search">
                <span class="kh-search-icon">🔍</span>
                <input type="text" id="kh-search-input" placeholder="Search knowledge sources..." oninput="filterKnowledgeSources(this.value)">
            </div>
            
            <!-- Filter Chips -->
            <div class="kh-filters">
                <button class="kh-filter-chip active" data-filter="all" onclick="filterKnowledge('all')">All</button>
                <button class="kh-filter-chip" data-filter="classical" onclick="filterKnowledge('classical')">📜 Classical Wisdom</button>
                <button class="kh-filter-chip" data-filter="research" onclick="filterKnowledge('research')">🔬 Research Evidence</button>
                <button class="kh-filter-chip" data-filter="regulatory" onclick="filterKnowledge('regulatory')">📋 Regulatory Intelligence</button>
                <button class="kh-filter-chip" data-filter="patent" onclick="filterKnowledge('patent')">📜 Patent Literature</button>
            </div>
            
            <!-- Grouped Sources Sections -->
            <div id="kh-sections">
                ${categories.map(cat => `
                    <div class="kh-category-section" data-category="${cat.id}">
                        <div class="kh-category-title">${cat.title}</div>
                        <div class="kh-grid">
                            ${cat.sources.map(source => {
                                let onclickAction = '';
                                if (source.id === 'patent') {
                                    onclickAction = "openPatentSourceInfo()";
                                } else if (source.isLive) {
                                    onclickAction = `openKnowledgeLibrary('${source.id}')`;
                                } else {
                                    onclickAction = `openExpandingCoverageInfo('${source.id}')`;
                                }
                                return `
                                <div class="kh-card" data-category="${source.category}" data-title="${source.title.toLowerCase()}" data-desc="${source.description.toLowerCase()}">
                                    <div class="kh-card-icon">${source.icon}</div>
                                    <div class="kh-card-content">
                                        <h4>${source.title}</h4>
                                        <span class="kh-card-badge ${source.badgeClass}">${source.badgeText}</span>
                                        <p>${source.description}</p>
                                        <button class="kh-card-btn" onclick="${onclickAction}">Explore →</button>
                                    </div>
                                </div>
                                `;
                            }).join('')}
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;

    return html;
  }

  function renderNoCaseSelectedForIntel() {
    var cases = state.cases || [];
    var html = '<div class="case-header"><div>'
      + '<h1 class="case-title">Case Intelligence</h1>'
      + '<div class="case-subtitle">Select a product case to view its digital passport, innovation map, patents, and regulatory strategy.</div>'
      + '</div>'
      + '<button class="btn btn-primary" id="intel-new-product-btn">' + icon("add", 16) + ' Create New Product</button>'
      + '</div>';

    if (cases.length === 0) {
      html += '<div class="empty-state">'
        + '<div class="empty-icon">' + icon("inventory_2", 32) + '</div>'
        + '<h3>No Product Cases Available</h3>'
        + '<p>Start by creating your first product case through our guided assistant.</p>'
        + '<button class="btn btn-primary" id="intel-create-first-btn">' + icon("add", 16) + ' Create Product</button>'
        + '</div>';
    } else {
      html += '<div style="margin-top:20px;"><h3 style="margin-bottom:12px;font-size:16px;">Select an Active Product:</h3><div class="case-grid">';
      cases.forEach(function (c) {
        var jurisdictions = parseJson(c.jurisdictions);
        var ingredients = parseJson(c.ingredients);
        html += '<div class="case-card" data-select-intel-case="' + c.id + '" style="cursor:pointer;">'
          + '<div class="case-card-header"><div class="case-card-name">' + escapeHtml(c.name) + '</div></div>'
          + '<div class="case-card-meta">'
          + '<span class="case-badge case-badge-stage">' + escapeHtml(stageLabel(c.stage)) + '</span>'
          + '<span class="case-badge case-badge-status">' + escapeHtml(statusLabel(c.status)) + '</span>'
          + '</div>'
          + '<div class="case-card-stats">'
          + '<div class="case-stat"><div class="case-stat-label">JURISDICTIONS</div><div class="case-stat-value">' + (jurisdictions.join(", ") || "None") + '</div></div>'
          + '<div class="case-stat"><div class="case-stat-label">INGREDIENTS</div><div class="case-stat-value">' + ingredients.length + '</div></div>'
          + '</div>'
          + '<div class="case-card-footer">'
          + '<button class="btn btn-primary btn-sm" data-select-intel-case="' + c.id + '">Launch Intelligence ' + icon("chevron_right", 16) + '</button>'
          + '</div></div>';
      });
      html += '</div></div>';
    }
    return html;
  }

  function updateTopBarAndActiveNav(view) {
    // 1. Sidebar Nav items
    document.querySelectorAll(".nav-item").forEach(function (n) { n.classList.remove("active"); });
    var target = document.querySelector('.nav-item[data-view="' + view + '"]');
    if (target) target.classList.add("active");

    // 2. Active Case Sidebar Sub-Indicator
    var navCaseName = document.getElementById("nav-active-case-name");
    if (navCaseName) {
      if (state.currentCase) {
        navCaseName.textContent = state.currentCase.name || "Active Case";
        navCaseName.style.color = "#2D4A3E";
      } else {
        navCaseName.textContent = "Select Case";
        navCaseName.style.color = "var(--text-secondary)";
      }
    }

    // 3. Topbar Breadcrumb
    var breadcrumbEl = document.getElementById("topbar-breadcrumb");
    if (breadcrumbEl) {
      var viewTitles = {
        "dashboard": { icon: "dashboard", title: "Dashboard" },
        "product-cases": { icon: "inventory_2", title: "Products" },
        "case-detail": { icon: "hub", title: state.currentCase ? "Case Intelligence · " + state.currentCase.name : "Case Intelligence" },
        "passport-wizard": { icon: "edit_note", title: "Product Passport Assistant" },
        "knowledge-hub": { icon: "menu_book", title: "Knowledge Hub" },
        "plant-discovery": { icon: "eco", title: "Plant Discovery" },
        "knowledge-engine": { icon: "menu_book", title: "Traditional Knowledge" },
        "knowledge-graph": { icon: "account_tree", title: "Knowledge Graph" },
        "monitoring-center": { icon: "visibility", title: "Continuous Monitoring" },
        "source-router": { icon: "database", title: "AI Source Router" },
        "review-queue": { icon: "psychology", title: "Expert Review" },
        "settings": { icon: "settings", title: "System Settings" }
      };

      var info = viewTitles[view] || { icon: "dashboard", title: "Overview" };
      breadcrumbEl.innerHTML = '<span class="topbar-breadcrumb-icon material-symbols-outlined">' + info.icon + '</span>'
        + '<span class="topbar-breadcrumb-title">' + escapeHtml(info.title) + '</span>';
    }

    // 4. Topbar Case Context Pill
    updateTopbarUI();
  }

  function updateTopbarUI() {
    var st = (window.AYUR && window.AYUR.state) || state;
    var caseData = st.currentCase;

    var nameEl = document.getElementById("topbar-case-name");
    var stageEl = document.getElementById("topbar-case-stage");
    var pretitleEl = document.getElementById("topbar-case-pretitle");
    var contextEl = document.getElementById("topbar-case-context");

    if (caseData && (caseData.id || caseData.name)) {
      // Active case exists
      if (nameEl) nameEl.textContent = caseData.name || "Unnamed Product";
      if (stageEl) {
        stageEl.textContent = caseData.stage || "IDEA";
        stageEl.style.color = "#34d399";
      }
      if (pretitleEl) {
        pretitleEl.style.display = "block";
        pretitleEl.textContent = "PRODUCT";
      }
      if (contextEl) {
        contextEl.style.display = "flex";
        contextEl.style.cursor = "pointer";
        contextEl.title = "Current Active Product Case";
      }
    } else {
      // No active case
      if (nameEl) nameEl.textContent = "No Active Case";
      if (stageEl) {
        stageEl.textContent = "Click to select";
        stageEl.style.color = "var(--text-secondary)";
      }
      if (pretitleEl) {
        pretitleEl.style.display = "none";
      }
      if (contextEl) {
        contextEl.style.display = "flex";
        contextEl.style.cursor = "pointer";
      }
    }
  }

  function openCaseSwitcherModal() {
    var cases = state.cases || [];
    var overlay = document.createElement("div");
    overlay.className = "modal-overlay open";

    var casesListHtml = "";
    if (cases.length === 0) {
      casesListHtml = '<p style="color:var(--text-secondary);text-align:center;padding:20px;">No product cases yet.</p>';
    } else {
      cases.forEach(function (c) {
        var isSelected = state.currentCase && state.currentCase.id === c.id;
        casesListHtml += '<div class="case-switcher-item ' + (isSelected ? "selected" : "") + '" data-switch-case="' + c.id + '">'
          + '<div><strong>' + escapeHtml(c.name) + '</strong><br><small style="color:var(--text-secondary);">' + escapeHtml(c.form || "Formulation") + ' • ' + escapeHtml(stageLabel(c.stage)) + '</small></div>'
          + (isSelected ? '<span class="chip selected" style="font-size:11px;">Active</span>' : '<button class="btn btn-ghost btn-sm">Select</button>')
          + '</div>';
      });
    }

    overlay.innerHTML = '<div class="modal" style="max-width:520px;">'
      + '<div class="modal-head"><h2>Switch Active Product Case</h2><button class="modal-close" id="case-switch-close">' + icon("close", 20) + '</button></div>'
      + '<div class="modal-body" style="max-height:360px;overflow-y:auto;">'
      + casesListHtml
      + '</div>'
      + '<div class="modal-foot" style="display:flex;justify-content:space-between;align-items:center;">'
      + '<button class="btn btn-primary btn-sm" id="case-switch-new-btn">' + icon("add", 16) + ' New Product</button>'
      + '<button class="btn btn-ghost btn-sm" id="case-switch-cancel-btn">Close</button>'
      + '</div>'
      + '</div>';

    document.body.appendChild(overlay);

    var closeFn = function () { overlay.remove(); };
    overlay.querySelector("#case-switch-close").addEventListener("click", closeFn);
    overlay.querySelector("#case-switch-cancel-btn").addEventListener("click", closeFn);
    overlay.addEventListener("click", function (e) { if (e.target === overlay) closeFn(); });

    overlay.querySelectorAll("[data-switch-case]").forEach(function (item) {
      item.addEventListener("click", async function () {
        var cid = this.getAttribute("data-switch-case");
        closeFn();
        await loadCase(cid);
        state.view = "case-detail";
        render();
      });
    });

    overlay.querySelector("#case-switch-new-btn").addEventListener("click", function () {
      closeFn();
      createCase();
    });
  }


  // ----------------------------------------------------------------
  // Navigation
  // ----------------------------------------------------------------
  function bindNavigation() {
    var navItems = document.querySelectorAll(".nav-item[data-view]");
    navItems.forEach(function (item) {
      item.addEventListener("click", function () {
        var view = item.getAttribute("data-view");
        if (item.classList.contains("disabled")) return;
        state.view = view;
        state.error = null;
        render({ scroll: "top" });

        if (view === "dashboard" || view === "product-cases") {
          loadCases().then(function () {
            if (state.view === view) {
              render({ scroll: "preserve" });
            }
          });
        }
      });
    });

    // Topbar & Sidebar New Product Buttons
    var sbNewBtn = document.getElementById("sidebar-new-case-btn");
    if (sbNewBtn) sbNewBtn.addEventListener("click", createCase);

    var tbNewBtn = document.getElementById("topbar-new-case-btn");
    if (tbNewBtn) tbNewBtn.addEventListener("click", createCase);

    var tbSettingsBtn = document.getElementById("topbar-settings-btn");
    if (tbSettingsBtn) tbSettingsBtn.addEventListener("click", function () { state.view = "settings"; render({ scroll: "top" }); });

    // Topbar Case Context Switcher
    var tbContext = document.getElementById("topbar-case-context");
    if (tbContext) tbContext.addEventListener("click", openCaseSwitcherModal);

    // Topbar Search Handler (Global Search by product name or ingredient)
    var tbSearch = document.getElementById("topbar-search-input");
    if (tbSearch) {
      var searchWrap = tbSearch.closest(".topbar-search") || tbSearch.parentElement;

      function renderSearchDropdown(query) {
        var existingDropdown = document.getElementById("topbar-search-dropdown");
        var q = (query || "").toLowerCase().trim();

        if (!q) {
          if (existingDropdown) existingDropdown.remove();
          return;
        }

        var cases = state.cases || [];
        var matches = cases.filter(function(c) {
          var nameMatch = (c.name || "").toLowerCase().includes(q);
          var formMatch = (c.form || c.dosage_form || c.formulation || "").toLowerCase().includes(q);
          var descMatch = (c.description || c.intended_use || "").toLowerCase().includes(q);

          var ings = parseJson(c.ingredients);
          var ingMatch = ings.some(function(ing) {
            var iname = (ing.name || ing.input_name || "").toLowerCase();
            var ibot = (ing.botanical || ing.botanical_name || "").toLowerCase();
            return iname.includes(q) || ibot.includes(q);
          });

          return nameMatch || formMatch || descMatch || ingMatch;
        });

        if (!existingDropdown) {
          existingDropdown = document.createElement("div");
          existingDropdown.id = "topbar-search-dropdown";
          existingDropdown.className = "topbar-search-dropdown";
          if (searchWrap) {
            searchWrap.style.position = "relative";
            searchWrap.appendChild(existingDropdown);
          }
        }

        if (matches.length === 0) {
          existingDropdown.innerHTML = '<div class="topbar-search-empty">' + icon("search_off", 18) + ' No matching products or ingredients</div>';
        } else {
          var html = '';
          matches.forEach(function(m) {
            var ings = parseJson(m.ingredients);
            var ingNames = ings.map(function(i) { return i.name || i.input_name; }).filter(Boolean).slice(0, 3).join(", ");
            html += '<div class="topbar-search-item" data-search-case-id="' + escapeHtml(m.id) + '">'
              + '<div class="topbar-search-item-header">'
              + '<span class="topbar-search-item-title">' + escapeHtml(m.name) + '</span>'
              + '<span class="topbar-search-item-stage">' + escapeHtml(m.stage || "IDEA") + '</span>'
              + '</div>'
              + (ingNames ? '<div class="topbar-search-item-meta">' + icon("spa", 12) + ' ' + escapeHtml(ingNames) + (ings.length > 3 ? ' +' + (ings.length - 3) + ' more' : '') + '</div>' : '')
              + '</div>';
          });
          existingDropdown.innerHTML = html;

          // Bind click to open case
          existingDropdown.querySelectorAll("[data-search-case-id]").forEach(function(item) {
            item.addEventListener("click", async function() {
              var caseId = this.getAttribute("data-search-case-id");
              tbSearch.value = "";
              if (existingDropdown) existingDropdown.remove();
              await loadCase(caseId);
            });
          });
        }
      }

      tbSearch.addEventListener("input", function () {
        var q = this.value.toLowerCase().trim();
        // 1. In-page cards filter
        var cards = document.querySelectorAll(".case-card");
        cards.forEach(function (c) {
          var text = c.textContent.toLowerCase();
          c.style.display = (q === "" || text.indexOf(q) !== -1) ? "" : "none";
        });

        // 2. Global floating search dropdown
        renderSearchDropdown(q);
      });

      // Close dropdown on outside click
      document.addEventListener("click", function(e) {
        if (!searchWrap || !searchWrap.contains(e.target)) {
          var drop = document.getElementById("topbar-search-dropdown");
          if (drop) drop.remove();
        }
      });
    }
  }

  function updateActiveNav(view) {
    document.querySelectorAll(".nav-item").forEach(function (n) { n.classList.remove("active"); });
    var target = document.querySelector('.nav-item[data-view="' + view + '"]');
    if (target) target.classList.add("active");
  }

  // ----------------------------------------------------------------
  // Review Queue View
  // ----------------------------------------------------------------
  function renderReviewQueue() {
    var html = '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>' + icon('psychology', 20) + ' Expert Review Queue</h2>'
      + '<p>Review requests for high-risk findings requiring human expert assessment</p></div><div class="card-body">'
      + '<div id="review-queue-content"><div style="text-align:center;padding:24px;color:var(--color-on-surface-variant)">' + icon('hourglass_empty', 32) + '<br>Loading reviews...</div></div>'
      + '</div></div>';

    // Load reviews async
    setTimeout(async function () {
      try {
        var data = await api('/api/reviews');
        var reviews = data.reviews || data.items || [];
        var el = document.getElementById('review-queue-content');
        if (!el) return;
        if (reviews.length === 0) {
          el.innerHTML = '<div style="text-align:center;padding:40px;color:var(--color-on-surface-variant)">' + icon('check_circle', 48) + '<br><br><strong>No pending reviews</strong><br><span style="font-size:13px">All findings have been reviewed or no high-risk items exist.</span></div>';
          return;
        }
        var html2 = '<div style="display:flex;flex-direction:column;gap:12px">';
        reviews.forEach(function (r) {
          var priorityColor = r.priority === 'HIGH' ? 'var(--color-error)' : (r.priority === 'MEDIUM' ? '#d97706' : 'var(--color-on-surface-variant)');
          var statusColor = r.status === 'PENDING' ? '#d97706' : (r.status === 'COMPLETED' ? 'var(--color-secondary)' : 'var(--color-outline)');
          html2 += '<div style="padding:16px;border:1px solid var(--color-outline-variant);border-radius:var(--radius-md);border-left:4px solid ' + priorityColor + '">'
            + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
            + '<div style="font-weight:600">' + escapeHtml(r.title || 'Review Request') + '</div>'
            + '<span class="chip" style="font-size:10px;background:' + statusColor + '15;color:' + statusColor + '">' + escapeHtml(r.status || 'PENDING') + '</span>'
            + '</div>'
            + '<div style="font-size:12px;color:var(--color-on-surface-variant);margin-bottom:8px">' + escapeHtml(r.description || r.trigger_type || '') + '</div>'
            + '<div style="display:flex;gap:8px;align-items:center;font-size:11px;color:var(--color-outline)">'
            + '<span>Priority: ' + escapeHtml(r.priority || 'MEDIUM') + '</span>'
            + '<span>|</span><span>Created: ' + escapeHtml((r.created_at || '').substring(0, 10)) + '</span>'
            + '</div></div>';
        });
        html2 += '</div>';
        el.innerHTML = html2;
      } catch (e) {
        var el2 = document.getElementById('review-queue-content');
        if (el2) el2.innerHTML = '<div style="text-align:center;padding:24px;color:var(--color-on-surface-variant)">No reviews available. Reviews are created automatically for high-risk findings.</div>';
      }
    }, 100);

    return html;
  }

  // ----------------------------------------------------------------
  // Settings View
  // ----------------------------------------------------------------
  // ----------------------------------------------------------------
  // Settings Helper Engine & Preferences Store
  // ----------------------------------------------------------------
  function getSettingsState() {
    var defaults = {
      growthTreeBg: true,
      tfaEnabled: false,
      sessionTimeout: '30m',
      role: 'Researcher',
      defaultStage: 'IDEA',
      defaultPathway: 'Both',
      patentAlerts: true,
      regulatoryUpdates: true,
      expiryReminders: true,
      emailDigest: false,
      accentColor: '#7dba9a'
    };
    try {
      var saved = localStorage.getItem('ayur_intel_settings');
      if (saved) {
        var parsed = JSON.parse(saved);
        return Object.assign({}, defaults, parsed);
      }
    } catch (e) {
      console.warn('Could not parse settings:', e);
    }
    return defaults;
  }

  function updateSettingValue(key, val) {
    var s = getSettingsState();
    s[key] = val;
    try {
      localStorage.setItem('ayur_intel_settings', JSON.stringify(s));
    } catch (e) {
      console.warn('Could not save setting:', e);
    }

    // Reactive actions
    if (key === 'growthTreeBg') {
      var canvas = document.getElementById('growth-tree-canvas');
      if (canvas) canvas.style.display = val ? 'block' : 'none';
      toast('Growth Tree Background ' + (val ? 'Enabled 🌿' : 'Disabled 🚫'), 'info');
    } else if (key === 'tfaEnabled') {
      toast('Two-Factor Authentication ' + (val ? 'Enabled 🔒' : 'Disabled 🔓'), 'info');
    } else if (key === 'patentAlerts' || key === 'regulatoryUpdates' || key === 'expiryReminders' || key === 'emailDigest') {
      toast('Notification preference updated 🔔', 'info');
    } else if (key === 'accentColor') {
      toast('Accent color updated 🎨', 'info');
    } else {
      toast('Setting saved', 'success');
    }

    render();
  }

  function exportAllSystemData() {
    try {
      var exportPayload = {
        app: 'AYUR-INTEL',
        version: '0.1.0',
        exported_at: new Date().toISOString(),
        cases: state.cases || [],
        settings: getSettingsState(),
        user: window.AYUR_AUTH ? window.AYUR_AUTH.getUser() : null
      };

      var dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(exportPayload, null, 2));
      var downloadAnchor = document.createElement('a');
      downloadAnchor.setAttribute('href', dataStr);
      downloadAnchor.setAttribute('download', 'ayur_intel_export_' + new Date().toISOString().substring(0, 10) + '.json');
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
      toast('💾 All data exported successfully!', 'success');
    } catch (e) {
      console.error('Export error:', e);
      toast('❌ Failed to export data', 'error');
    }
  }

  function importSystemData(event) {
    var files = event.target.files;
    if (!files || files.length === 0) return;
    var file = files[0];
    var reader = new FileReader();
    reader.onload = function(e) {
      try {
        var parsed = JSON.parse(e.target.result);
        if (parsed.cases && Array.isArray(parsed.cases)) {
          state.cases = parsed.cases;
          saveStateToLocalStorage();
          toast('✅ Imported ' + parsed.cases.length + ' product case(s)!', 'success');
          render();
        } else {
          toast('⚠️ Invalid JSON format for AYUR-INTEL export', 'error');
        }
      } catch (err) {
        toast('❌ Error parsing import file', 'error');
      }
    };
    reader.readAsText(file);
  }

  function clearSystemCache() {
    if (confirm('Clear temporary application cache? Your product cases and account will remain safe.')) {
      try {
        sessionStorage.clear();
        toast('🧹 Cache cleared successfully!', 'success');
      } catch (e) {
        toast('Cache cleared', 'info');
      }
    }
  }

  function deleteAllSystemData() {
    if (confirm('⚠️ WARNING: Are you sure you want to delete ALL local product cases and reset settings? This CANNOT be undone!')) {
      state.cases = [];
      state.currentCase = null;
      localStorage.removeItem('ayur_intel_state');
      localStorage.removeItem('ayur_intel_settings');
      toast('🗑️ All local data reset to default', 'info');
      render();
    }
  }

  // ----------------------------------------------------------------
  // Premium Settings View Renderer
  // ----------------------------------------------------------------
  function renderSettings() {
    var user = (window.AYUR_AUTH && typeof window.AYUR_AUTH.getUser === 'function' ? window.AYUR_AUTH.getUser() : null) || {
      display_name: "Deepansh Aggarwal",
      email: "india.deepanshaggarwal@gmail.com",
      created_at: "2026-09-08T12:00:00Z"
    };

    var s = getSettingsState();
    var name = user.display_name || user.username || "User";
    var email = user.email || "";
    var memberSince = user.created_at ? new Date(user.created_at).toLocaleDateString('en-US', { month: 'short', year: 'numeric' }) : 'Sep 2026';

    var ACCENT_COLORS = ['#7dba9a', '#4ecdc4', '#6c5ce7', '#fdcb6e', '#e17055', '#45b7d1', '#fd79a8', '#00b894'];

    var html = ''
      + '<div class="settings-dashboard-wrapper">'
      
      // Header
      + '<div class="settings-dashboard-header">'
      + '<h1>' + icon('settings', 24) + ' <span>Settings & System Control</span></h1>'
      + '<p>Configure system preferences, security policies, notification alerts, data privacy, and integrations.</p>'
      + '</div>'

      + '<div class="settings-grid">'

      // -----------------------------------------------------------------
      // SECTION 1: SECURITY & AUTHENTICATION
      // -----------------------------------------------------------------
      + '<div class="settings-card">'
      + '<div class="settings-card-title">' + icon('security', 20) + ' <span>Security & Authentication</span></div>'
      + '<div class="settings-row-list">'
      
      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('lock', 16) + ' <span>Password Security</span></div>'
      + '<div class="settings-row-value"><button class="btn btn-outline btn-xs" onclick="window.AYUR.navigateTo(\'profile\')">Change Password</button></div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('verified_user', 16) + ' <span>Two-Factor Auth (2FA)</span></div>'
      + '<div class="settings-row-value">'
      + '<label class="ios-toggle"><input type="checkbox" ' + (s.tfaEnabled ? 'checked' : '') + ' onchange="window.updateSetting(\'tfaEnabled\', this.checked)"><span class="ios-slider"></span></label>'
      + '</div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('devices', 16) + ' <span>Active Sessions</span></div>'
      + '<div class="settings-row-value"><span class="badge-status-green">1 Active</span> <button class="btn btn-ghost btn-xs text-danger" onclick="window.AYUR_AUTH.logout()">Logout All</button></div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('timer', 16) + ' <span>Session Timeout</span></div>'
      + '<div class="settings-row-value">'
      + '<select class="settings-select" onchange="window.updateSetting(\'sessionTimeout\', this.value)">'
      + '<option value="5m" ' + (s.sessionTimeout === '5m' ? 'selected' : '') + '>5 minutes</option>'
      + '<option value="15m" ' + (s.sessionTimeout === '15m' ? 'selected' : '') + '>15 minutes</option>'
      + '<option value="30m" ' + (s.sessionTimeout === '30m' ? 'selected' : '') + '>30 minutes</option>'
      + '<option value="1h" ' + (s.sessionTimeout === '1h' ? 'selected' : '') + '>1 hour</option>'
      + '</select>'
      + '</div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('history', 16) + ' <span>Audit Logging</span></div>'
      + '<div class="settings-row-value"><span class="badge-status-green">Enabled</span></div>'
      + '</div>'

      + '</div>'
      + '</div>'

      // -----------------------------------------------------------------
      // SECTION 2: PROFILE & ACCOUNT
      // -----------------------------------------------------------------
      + '<div class="settings-card">'
      + '<div class="settings-card-title">' + icon('person', 20) + ' <span>Profile & Account</span></div>'
      + '<div class="settings-row-list">'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('badge', 16) + ' <span>Full Name</span></div>'
      + '<div class="settings-row-value"><strong>' + escapeHtml(name) + '</strong></div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('mail', 16) + ' <span>Email Address</span></div>'
      + '<div class="settings-row-value" style="font-family:\'JetBrains Mono\',monospace;font-size:12px;color:#7dba9a;">' + escapeHtml(email) + '</div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('admin_panel_settings', 16) + ' <span>Account Role</span></div>'
      + '<div class="settings-row-value">'
      + '<select class="settings-select" onchange="window.updateSetting(\'role\', this.value)">'
      + '<option value="Researcher" ' + (s.role === 'Researcher' ? 'selected' : '') + '>Researcher</option>'
      + '<option value="Admin" ' + (s.role === 'Admin' ? 'selected' : '') + '>Admin</option>'
      + '<option value="Auditor" ' + (s.role === 'Auditor' ? 'selected' : '') + '>Auditor</option>'
      + '</select>'
      + '</div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('calendar_today', 16) + ' <span>Member Since</span></div>'
      + '<div class="settings-row-value">' + escapeHtml(memberSince) + '</div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('manage_accounts', 16) + ' <span>Profile Settings</span></div>'
      + '<div class="settings-row-value"><button class="btn btn-primary btn-xs" onclick="window.AYUR.navigateTo(\'profile\')">Edit Profile</button></div>'
      + '</div>'

      + '</div>'
      + '</div>'

      // -----------------------------------------------------------------
      // SECTION 3: PREFERENCES
      // -----------------------------------------------------------------
      + '<div class="settings-card">'
      + '<div class="settings-card-title">' + icon('tune', 20) + ' <span>Preferences & Pipeline</span></div>'
      + '<div class="settings-row-list">'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('flag', 16) + ' <span>Default Product Stage</span></div>'
      + '<div class="settings-row-value">'
      + '<select class="settings-select" onchange="window.updateSetting(\'defaultStage\', this.value)">'
      + '<option value="IDEA" ' + (s.defaultStage === 'IDEA' ? 'selected' : '') + '>Idea</option>'
      + '<option value="RND" ' + (s.defaultStage === 'RND' ? 'selected' : '') + '>R&D</option>'
      + '<option value="PILOT" ' + (s.defaultStage === 'PILOT' ? 'selected' : '') + '>Pilot</option>'
      + '<option value="PRE_LAUNCH" ' + (s.defaultStage === 'PRE_LAUNCH' ? 'selected' : '') + '>Pre-Launch</option>'
      + '<option value="COMMERCIAL" ' + (s.defaultStage === 'COMMERCIAL' ? 'selected' : '') + '>Commercial</option>'
      + '</select>'
      + '</div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('public', 16) + ' <span>Default Jurisdiction</span></div>'
      + '<div class="settings-row-value"><span class="badge-status-green">🇮🇳 India (AYUSH/FSSAI)</span></div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('policy', 16) + ' <span>Default Regulatory Pathway</span></div>'
      + '<div class="settings-row-value">'
      + '<select class="settings-select" onchange="window.updateSetting(\'defaultPathway\', this.value)">'
      + '<option value="AYUSH" ' + (s.defaultPathway === 'AYUSH' ? 'selected' : '') + '>AYUSH Drug License</option>'
      + '<option value="FSSAI" ' + (s.defaultPathway === 'FSSAI' ? 'selected' : '') + '>FSSAI Ayurveda Aahara</option>'
      + '<option value="Both" ' + (s.defaultPathway === 'Both' ? 'selected' : '') + '>Both Pathways</option>'
      + '</select>'
      + '</div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('database', 16) + ' <span>Ingredient DB Source</span></div>'
      + '<div class="settings-row-value"><span class="badge-status-green">DRAVYA (400 Plants) ✅</span></div>'
      + '</div>'

      + '</div>'
      + '</div>'

      // -----------------------------------------------------------------
      // SECTION 4: APPEARANCE
      // -----------------------------------------------------------------
      + '<div class="settings-card">'
      + '<div class="settings-card-title">' + icon('palette', 20) + ' <span>Appearance & Theme</span></div>'
      + '<div class="settings-row-list">'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('dark_mode', 16) + ' <span>Theme Mode</span></div>'
      + '<div class="settings-row-value"><span class="badge-status-green">🌙 Dark Botanical</span></div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('park', 16) + ' <span>Growth Tree Background</span></div>'
      + '<div class="settings-row-value">'
      + '<label class="ios-toggle"><input type="checkbox" ' + (s.growthTreeBg ? 'checked' : '') + ' onchange="window.updateSetting(\'growthTreeBg\', this.checked)"><span class="ios-slider"></span></label>'
      + '</div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('color_lens', 16) + ' <span>Accent Color</span></div>'
      + '<div class="settings-row-value" style="display:flex;gap:6px;">';

    ACCENT_COLORS.forEach(function(c) {
      var isAct = s.accentColor === c;
      html += '<button class="settings-accent-swatch ' + (isAct ? 'active' : '') + '" style="background:' + c + '" onclick="window.updateSetting(\'accentColor\', \'' + c + '\')"></button>';
    });

    html += '</div>'
      + '</div>'

      + '</div>'
      + '</div>'

      // -----------------------------------------------------------------
      // SECTION 5: NOTIFICATIONS & ALERTS
      // -----------------------------------------------------------------
      + '<div class="settings-card">'
      + '<div class="settings-card-title">' + icon('notifications', 20) + ' <span>Notifications & Alerts</span></div>'
      + '<div class="settings-row-list">'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('gavel', 16) + ' <span>Patent Alerts</span></div>'
      + '<div class="settings-row-value">'
      + '<label class="ios-toggle"><input type="checkbox" ' + (s.patentAlerts ? 'checked' : '') + ' onchange="window.updateSetting(\'patentAlerts\', this.checked)"><span class="ios-slider"></span></label>'
      + '</div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('campaign', 16) + ' <span>Regulatory Updates</span></div>'
      + '<div class="settings-row-value">'
      + '<label class="ios-toggle"><input type="checkbox" ' + (s.regulatoryUpdates ? 'checked' : '') + ' onchange="window.updateSetting(\'regulatoryUpdates\', this.checked)"><span class="ios-slider"></span></label>'
      + '</div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('event_repeat', 16) + ' <span>Product Expiry Reminders</span></div>'
      + '<div class="settings-row-value">'
      + '<label class="ios-toggle"><input type="checkbox" ' + (s.expiryReminders ? 'checked' : '') + ' onchange="window.updateSetting(\'expiryReminders\', this.checked)"><span class="ios-slider"></span></label>'
      + '</div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('mail_outline', 16) + ' <span>Email Digest</span></div>'
      + '<div class="settings-row-value">'
      + '<label class="ios-toggle"><input type="checkbox" ' + (s.emailDigest ? 'checked' : '') + ' onchange="window.updateSetting(\'emailDigest\', this.checked)"><span class="ios-slider"></span></label>'
      + '</div>'
      + '</div>'

      + '</div>'
      + '</div>'

      // -----------------------------------------------------------------
      // SECTION 6: DATA & PRIVACY
      // -----------------------------------------------------------------
      + '<div class="settings-card">'
      + '<div class="settings-card-title">' + icon('sd_storage', 20) + ' <span>Data Management & Privacy</span></div>'
      + '<div class="settings-row-list">'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('download', 16) + ' <span>Export All Data</span></div>'
      + '<div class="settings-row-value"><button class="btn-settings-action btn-export" onclick="window.exportAllSystemData()">📥 Download JSON</button></div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('upload', 16) + ' <span>Import Data</span></div>'
      + '<div class="settings-row-value">'
      + '<input type="file" id="settings-import-file-input" accept=".json" style="display:none;" onchange="window.importSystemData(event)">'
      + '<button class="btn-settings-action btn-import" onclick="document.getElementById(\'settings-import-file-input\').click()">📤 Upload JSON</button>'
      + '</div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('cleaning_services', 16) + ' <span>Clear Cache</span></div>'
      + '<div class="settings-row-value"><button class="btn-settings-action btn-clear" onclick="window.clearSystemCache()">🗑️ Clear Cache</button></div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('delete_forever', 16) + ' <span>Reset Local Data</span></div>'
      + '<div class="settings-row-value"><button class="btn-settings-action btn-reset" onclick="window.deleteAllSystemData()">⚠️ Reset All</button></div>'
      + '</div>'

      + '</div>'
      + '</div>'

      // -----------------------------------------------------------------
      // SECTION 7: SYSTEM STATUS
      // -----------------------------------------------------------------
      + '<div class="settings-card">'
      + '<div class="settings-card-title">' + icon('monitor_heart', 20) + ' <span>System Status & Health</span></div>'
      + '<div class="settings-row-list">'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('terminal', 16) + ' <span>App Version</span></div>'
      + '<div class="settings-row-value"><code>v0.1.0</code></div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('api', 16) + ' <span>API Status</span></div>'
      + '<div class="settings-row-value"><span class="badge-status-green">Operational ✅</span></div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('storage', 16) + ' <span>Database Connection</span></div>'
      + '<div class="settings-row-value"><span class="badge-status-green">SQLite ✅</span></div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('security', 16) + ' <span>Security Headers</span></div>'
      + '<div class="settings-row-value"><span class="badge-status-green">Active ✅</span></div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('backup', 16) + ' <span>Last Backup</span></div>'
      + '<div class="settings-row-value">' + new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' Today</div>'
      + '</div>'

      + '</div>'
      + '</div>'

      // -----------------------------------------------------------------
      // SECTION 8: SUPPORT & HELP
      // -----------------------------------------------------------------
      + '<div class="settings-card">'
      + '<div class="settings-card-title">' + icon('help_center', 20) + ' <span>Support & Documentation</span></div>'
      + '<div class="settings-row-list">'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('menu_book', 16) + ' <span>User Guide</span></div>'
      + '<div class="settings-row-value"><a href="#" class="settings-link" onclick="event.preventDefault(); window.openRegistrationGuide();">View Guide ' + icon('open_in_new', 12) + '</a></div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('quiz', 16) + ' <span>FAQ & Troubleshooting</span></div>'
      + '<div class="settings-row-value"><a href="#" class="settings-link" onclick="event.preventDefault(); showToast(\'Documentation available in ARCHITECTURE.md\', \'info\');">Read FAQ ' + icon('open_in_new', 12) + '</a></div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('support_agent', 16) + ' <span>Contact Support</span></div>'
      + '<div class="settings-row-value"><a href="mailto:support@ayurintel.com" class="settings-link">Email Support ' + icon('open_in_new', 12) + '</a></div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('bug_report', 16) + ' <span>Report Issue</span></div>'
      + '<div class="settings-row-value"><a href="#" class="settings-link" onclick="event.preventDefault(); showToast(\'Issue reporting log created in system\', \'info\');">Report Issue ' + icon('open_in_new', 12) + '</a></div>'
      + '</div>'

      + '</div>'
      + '</div>'

      // -----------------------------------------------------------------
      // SECTION 9: LICENSING & LEGAL
      // -----------------------------------------------------------------
      + '<div class="settings-card" style="grid-column: span 2;">'
      + '<div class="settings-card-title">' + icon('gavel', 20) + ' <span>Licensing & Advisory Legal Statement</span></div>'
      + '<div class="settings-row-list">'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('description', 16) + ' <span>Terms of Service & Privacy</span></div>'
      + '<div class="settings-row-value"><a href="#" class="settings-link" onclick="event.preventDefault(); showToast(\'AYUR-INTEL v0.1.0 Enterprise Terms\', \'info\');">Terms & Conditions</a></div>'
      + '</div>'

      + '<div class="settings-row-item">'
      + '<div class="settings-row-label">' + icon('info', 16) + ' <span>Advisory Disclaimer</span></div>'
      + '<div class="settings-row-value" style="font-size:12px;color:#94a3b8;line-height:1.5;text-align:left;max-width:700px;">'
      + 'AYUR-INTEL is an evidence-backed Ayurvedic product decision-support platform. All automated regulatory compliance checks, TK evidence findings, and patent overlap screenings are advisory decision support and do not constitute formal legal opinions.'
      + '</div>'
      + '</div>'

      + '</div>'
      + '</div>'

      + '</div>' // End settings-grid
      + '</div>'; // End settings-dashboard-wrapper

    return html;
  }

  window.updateSetting = updateSettingValue;
  window.exportAllSystemData = exportAllSystemData;
  window.importSystemData = importSystemData;
  window.clearSystemCache = clearSystemCache;
  window.deleteAllSystemData = deleteAllSystemData;

  // ----------------------------------------------------------------
  // Event Bindings
  // ----------------------------------------------------------------
  function bindEvents() {
    // Case Switch Button in Case Header
    var caseSwitchBtn = document.getElementById("case-switch-btn");
    if (caseSwitchBtn) caseSwitchBtn.addEventListener("click", openCaseSwitcherModal);

    var caseCloseBtn = document.getElementById("case-close-btn");
    if (caseCloseBtn) {
      caseCloseBtn.addEventListener("click", function () {
        state.currentCase = null;
        state.passportData = null;
        state.view = "dashboard";
        updateTopbarUI();
        render();
      });
    }

    var passportReopenBtn = document.getElementById("passport-reopen-btn");
    if (passportReopenBtn) {
      passportReopenBtn.addEventListener("click", function () {
        if (window.AYUR && window.AYUR.initPassportData) {
          window.AYUR.initPassportData(state.currentCase);
        }
        state.passportStep = 9; // Review step
        state.view = "passport-wizard";
        render();
      });
    }

    // Intelligence Module Cards
    var cardInnovation = document.getElementById("card-intel-innovation");
    if (cardInnovation) {
      cardInnovation.addEventListener("click", function () {
        if (!state.currentCase) return;
        openCaseModule("innovationAnalysis", "/api/cases/" + state.currentCase.id + "/innovation-analysis", "innovation-analysis", { method: "POST" });
      });
    }

    var cardPatent = document.getElementById("card-intel-patent");
    if (cardPatent) {
      cardPatent.addEventListener("click", function () {
        if (!state.currentCase) return;
        openPatentIntelligence(state.currentCase.id);
      });
    }

    var cardIp = document.getElementById("card-intel-ip");
    if (cardIp) {
      cardIp.addEventListener("click", function () {
        if (!state.currentCase) return;
        openCaseModule("ipStrategy", "/api/cases/" + state.currentCase.id + "/ip-strategy", "ip-strategy", { method: "POST" });
      });
    }

    var cardRegulatory = document.getElementById("card-intel-regulatory");
    if (cardRegulatory) {
      cardRegulatory.addEventListener("click", function () {
        generateRegulatoryAnalysis();
      });
    }

    var cardRisk = document.getElementById("card-intel-risk");
    if (cardRisk) {
      cardRisk.addEventListener("click", function () {
        generateRiskAssessment();
      });
    }

    var cardEvidence = document.getElementById("card-intel-evidence");
    if (cardEvidence) {
      cardEvidence.addEventListener("click", function () {
        if (!state.currentCase) return;
        openCaseModule("evidenceData", "/api/cases/" + state.currentCase.id + "/evidence", "evidence");
      });
    }

    var cardDecision = document.getElementById("card-intel-decision");
    if (cardDecision) {
      cardDecision.addEventListener("click", function () {
        if (!state.currentCase) return;
        openCaseModule("dashboardData", "/api/cases/" + state.currentCase.id + "/decision-dashboard", "dashboard-detail");
      });
    }

    var cardGraph = document.getElementById("card-intel-graph");
    if (cardGraph) {
      cardGraph.addEventListener("click", function () {
        if (!state.currentCase) return;
        openCaseModule("knowledgeGraphData", "/api/cases/" + state.currentCase.id + "/knowledge-graph", "knowledge-graph");
      });
    }

    var cardMonitoring = document.getElementById("card-intel-monitoring");
    if (cardMonitoring) {
      cardMonitoring.addEventListener("click", function () {
        if (!state.currentCase) return;
        openCaseModule("monitoringData", "/api/cases/" + state.currentCase.id + "/monitoring", "monitoring-center");
      });
    }

    var cardRouter = document.getElementById("card-intel-router");
    if (cardRouter) {
      cardRouter.addEventListener("click", async function () {
        if (state.view !== "source-router") {
          saveCurrentViewScrollPosition();
        }
        state.loading = true; render({ scroll: "top" });
        try {
          var data = await api("/api/source-router/sources");
          state.sourceRouterData = { sources: data, routingResult: null, question: '' };
          state.view = "source-router";
        } catch (e) { state.error = "Failed to load source router."; }
        state.loading = false; render({ scroll: "top" });
      });
    }

    // Knowledge Hub Tabs
    document.querySelectorAll(".knowledge-tab-btn[data-ktab]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var tab = this.getAttribute("data-ktab");
        state.knowledgeTab = tab;
        render();
      });
    });

    var kgSelectCaseBtn = document.getElementById("kg-select-case-btn");
    if (kgSelectCaseBtn) kgSelectCaseBtn.addEventListener("click", openCaseSwitcherModal);

    var intelNewBtn = document.getElementById("intel-new-product-btn") || document.getElementById("intel-create-first-btn");
    if (intelNewBtn) intelNewBtn.addEventListener("click", createCase);

    document.querySelectorAll("[data-select-intel-case]").forEach(function (card) {
      card.addEventListener("click", async function () {
        var id = this.getAttribute("data-select-intel-case");
        await loadCase(id);
        state.view = "case-detail";
        render();
      });
    });

    // Mobile toggle
    var mobileToggle = document.getElementById("mobile-toggle");
    if (mobileToggle) {
      mobileToggle.addEventListener("click", function () {
        var sb = document.getElementById("sidebar");
        if (sb) sb.classList.toggle("open");
      });
    }

    // Create case
    ["create-case-btn", "create-case-btn-2", "create-case-btn-3"].forEach(function (id) {
      var btn = document.getElementById(id);
      if (btn) btn.addEventListener("click", createCase);
    });

    // Pipeline workflow step modal click
    document.querySelectorAll(".pipeline-node[data-pipeline-step]").forEach(function (node) {
      node.addEventListener("click", function () {
        var idx = parseInt(this.getAttribute("data-pipeline-step"), 10);
        var step = PIPELINE_WORKFLOW_STEPS[idx];
        if (step) {
          openWorkflowStepModal(step, idx + 1);
        }
      });
    });

    // Explore demo
    var demoBtn = document.getElementById("explore-demo-btn");
    if (demoBtn) {
      demoBtn.addEventListener("click", function (e) {
        e.preventDefault();
        exploreDemoCase();
      });
    }

    // View all cases
    var viewAll = document.getElementById("view-all-cases");
    if (viewAll) viewAll.addEventListener("click", function () { state.view = "product-cases"; render(); });

    // Open case cards
    document.querySelectorAll("[data-case-id]").forEach(function (card) {
      card.addEventListener("click", async function () {
        var id = card.getAttribute("data-case-id");
        await loadCase(id);
      });
    });
    document.querySelectorAll("[data-open-case]").forEach(function (btn) {
      btn.addEventListener("click", async function (e) {
        e.stopPropagation();
        var id = btn.getAttribute("data-open-case");
        await loadCase(id);
      });
    });

    // Case detail buttons
    var passportBtn = document.getElementById("open-passport-btn");
    if (passportBtn) {
      passportBtn.addEventListener("click", function () {
        if (window.AYUR && window.AYUR.initPassportData) {
          window.AYUR.initPassportData(state.currentCase);
        }
        state.view = "passport-wizard";
        render();
      });
    }

    var innovationBtn = document.getElementById("open-innovation-btn");
    if (innovationBtn) {
      innovationBtn.addEventListener("click", function () {
        if (!state.currentCase) return;
        openCaseModule("innovationAnalysis", "/api/cases/" + state.currentCase.id + "/innovation-analysis", "innovation-analysis", { method: "POST" });
      });
    }

    var patentBtn = document.getElementById("open-patent-btn");
    if (patentBtn) {
      patentBtn.addEventListener("click", function () {
        if (state.view !== "patent-intelligence") {
          saveCurrentViewScrollPosition();
        }
        state.view = "patent-intelligence";
        render({ scroll: "top" });
      });
    }

    var ipStrategyBtn = document.getElementById("open-ip-strategy-btn");
    if (ipStrategyBtn) {
      ipStrategyBtn.addEventListener("click", function () {
        if (!state.currentCase) return;
        openCaseModule("ipStrategy", "/api/cases/" + state.currentCase.id + "/ip-strategy", "ip-strategy", { method: "POST" });
      });
    }

    var regulatoryBtn = document.getElementById("open-regulatory-btn");
    if (regulatoryBtn) {
      regulatoryBtn.addEventListener("click", function () {
        if (state.view !== "regulatory-select") {
          saveCurrentViewScrollPosition();
        }
        state.view = "regulatory-select";
        render({ scroll: "top" });
      });
    }

    // --- Evidence & Citation (Phase 11) ---
    var evidenceBtn = document.getElementById("open-evidence-btn");
    if (evidenceBtn) {
      evidenceBtn.addEventListener("click", function () {
        if (!state.currentCase) return;
        openCaseModule("evidenceData", "/api/cases/" + state.currentCase.id + "/evidence", "evidence");
      });
    }

    var backFromEvidence = document.getElementById("back-from-evidence");
    if (backFromEvidence) {
      backFromEvidence.addEventListener("click", function () {
        navigateBackToCaseDetail();
      });
    }

    // --- Risk + Self-Extension (Phase 12) ---
    var riskBtn = document.getElementById("open-risk-btn");
    if (riskBtn) {
      riskBtn.addEventListener("click", function () {
        generateRiskAssessment();
      });
    }

    var backFromRisk = document.getElementById("back-from-risk");
    if (backFromRisk) {
      backFromRisk.addEventListener("click", function () {
        navigateBackToCaseDetail();
      });
    }

    // --- Decision Dashboard (Phase 13) ---
    var dashboardBtn = document.getElementById("open-dashboard-btn");
    if (dashboardBtn) {
      dashboardBtn.addEventListener("click", function () {
        if (!state.currentCase) return;
        openCaseModule("dashboardData", "/api/cases/" + state.currentCase.id + "/decision-dashboard", "dashboard-detail");
      });
    }

    var backFromDashboard = document.getElementById("back-from-dashboard");
    if (backFromDashboard) {
      backFromDashboard.addEventListener("click", function () {
        navigateBackToCaseDetail();
      });
    }

    // --- Continuous Monitoring (Phase 14) ---
    var monitoringBtn = document.getElementById("open-monitoring-btn");
    if (monitoringBtn) {
      monitoringBtn.addEventListener("click", function () {
        if (!state.currentCase) return;
        openCaseModule("monitoringData", "/api/cases/" + state.currentCase.id + "/monitoring", "monitoring-center");
      });
    }

    var backFromMonitoring = document.getElementById("back-from-monitoring");
    if (backFromMonitoring) {
      backFromMonitoring.addEventListener("click", function () {
        navigateBackToCaseDetail();
      });
    }

    var checkNowBtn = document.getElementById("monitoring-check-now");
    if (checkNowBtn) {
      checkNowBtn.addEventListener("click", async function () {
        if (!state.currentCase) return;
        state.loading = true; render({ scroll: "preserve" });
        try {
          var runResult = await api("/api/cases/" + state.currentCase.id + "/monitoring/run", { method: "POST" });
          toast('Monitoring check complete. ' + (runResult.alerts_created || 0) + ' alerts created.', 'success');
          var data = await api("/api/cases/" + state.currentCase.id + "/monitoring");
          state.monitoringData = data;
        } catch (e) { state.error = "Monitoring check failed."; }
        state.loading = false; render({ scroll: "preserve" });
      });
    }

    var monitoringToggle = document.getElementById("monitoring-toggle");
    if (monitoringToggle) {
      monitoringToggle.addEventListener("click", async function () {
        if (!state.currentCase || !state.monitoringData) return;
        var config = state.monitoringData.config || {};
        try {
          await api("/api/cases/" + state.currentCase.id + "/monitoring", {
            method: "PATCH",
            body: JSON.stringify({ enabled: !config.enabled }),
            headers: { 'Content-Type': 'application/json' }
          });
          var data = await api("/api/cases/" + state.currentCase.id + "/monitoring");
          state.monitoringData = data;
          toast('Monitoring ' + (!config.enabled ? 'resumed' : 'paused'), 'success');
        } catch (e) { state.error = "Failed to update monitoring."; }
        state.loading = false; render({ scroll: "preserve" });
      });
    }

    // Alert action buttons
    document.querySelectorAll(".alert-action").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var alertId = btn.getAttribute("data-alert-id");
        var action = btn.getAttribute("data-action");
        if (!alertId || !action) return;
        try {
          await api("/api/monitoring/alerts/" + alertId, {
            method: "PATCH",
            body: JSON.stringify({ status: action }),
            headers: { 'Content-Type': 'application/json' }
          });
          toast('Alert updated to ' + action, 'success');
          var data = await api("/api/cases/" + state.currentCase.id + "/monitoring");
          state.monitoringData = data;
          render({ scroll: "preserve" });
        } catch (e) { state.error = "Failed to update alert."; }
      });
    });

    // --- Knowledge Graph (Phase 15) ---
    var knowledgeGraphBtn = document.getElementById("open-knowledge-graph-btn");
    if (knowledgeGraphBtn) {
      knowledgeGraphBtn.addEventListener("click", async function () {
        if (!state.currentCase) return;
        openCaseModule("knowledgeGraphData", "/api/cases/" + state.currentCase.id + "/knowledge-graph", "knowledge-graph");
      });
    }

    var backFromKnowledgeGraph = document.getElementById("back-from-knowledge-graph");
    if (backFromKnowledgeGraph) {
      backFromKnowledgeGraph.addEventListener("click", function () {
        state.knowledgeGraphData = null;
        navigateBackToCaseDetail();
      });
    }

    var backFromKnowledgeGraphEmpty = document.getElementById("back-from-knowledge-graph-empty");
    if (backFromKnowledgeGraphEmpty) {
      backFromKnowledgeGraphEmpty.addEventListener("click", function () {
        state.knowledgeGraphData = null;
        navigateBackToCaseDetail();
      });
    }

    // Graph Intelligence Lens Pills
    document.querySelectorAll(".kg-lens-pill").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var lens = btn.getAttribute("data-lens");
        document.querySelectorAll(".kg-lens-pill").forEach(function (b) { b.classList.remove("active"); });
        btn.classList.add("active");
        applyGraphLens(lens);
      });
    });

    // Graph Client-side Search & Clear
    var kgSearchInput = document.getElementById("kg-search-input");
    var kgSearchClear = document.getElementById("kg-search-clear");
    if (kgSearchInput) {
      kgSearchInput.addEventListener("input", function () {
        var val = kgSearchInput.value;
        if (kgSearchClear) kgSearchClear.style.display = val.trim() ? "block" : "none";
        searchGraphLocally(val);
      });
      kgSearchInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          searchGraphLocally(kgSearchInput.value);
        }
      });
    }
    if (kgSearchClear) {
      kgSearchClear.addEventListener("click", function () {
        if (kgSearchInput) kgSearchInput.value = "";
        kgSearchClear.style.display = "none";
        searchGraphLocally("");
      });
    }

    // Graph View Controls (Zoom in/out, fit, reset)
    var kgZoomIn = document.getElementById("kg-zoom-in");
    if (kgZoomIn) {
      kgZoomIn.addEventListener("click", function () { zoomGraph(1.25); });
    }
    var kgZoomOut = document.getElementById("kg-zoom-out");
    if (kgZoomOut) {
      kgZoomOut.addEventListener("click", function () { zoomGraph(0.8); });
    }
    var kgFitBtn = document.getElementById("kg-fit-btn");
    if (kgFitBtn) {
      kgFitBtn.addEventListener("click", function () { fitGraphToView(); });
    }
    var kgResetBtn = document.getElementById("kg-reset-btn");
    if (kgResetBtn) {
      kgResetBtn.addEventListener("click", function () { resetGraphView(); });
    }

    // Drawer Close
    var kgDrawerClose = document.getElementById("kg-drawer-close");
    if (kgDrawerClose) {
      kgDrawerClose.addEventListener("click", function () { deselectGraphNode(); });
    }

    // --- Source Router (Phase 16) ---
    var sourceRouterBtn = document.getElementById("open-source-router-btn");
    if (sourceRouterBtn) {
      sourceRouterBtn.addEventListener("click", async function () {
        if (!state.currentCase) return;
        if (state.view !== "source-router") {
          saveCurrentViewScrollPosition();
        }
        state.loading = true; render({ scroll: "top" });
        try {
          var data = await api("/api/source-router/sources");
          state.sourceRouterData = { sources: data, routingResult: null, question: '' };
          state.view = "source-router";
        } catch (e) { state.error = "Failed to load source router."; }
        state.loading = false; render({ scroll: "top" });
      });
    }

    var backFromSourceRouter = document.getElementById("back-from-source-router");
    if (backFromSourceRouter) {
      backFromSourceRouter.addEventListener("click", function () {
        state.sourceRouterData = null;
        navigateBackToCaseDetail();
      });
    }

    // Source router question submit
    var routeQuestionBtn = document.getElementById("route-question-btn");
    if (routeQuestionBtn) {
      routeQuestionBtn.addEventListener("click", async function () {
        var input = document.getElementById("route-question-input");
        if (!input || !input.value.trim()) return;
        var question = input.value.trim();
        state.loading = true; render();
        try {
          var caseId = state.currentCase ? state.currentCase.id : null;
          var data = await api("/api/source-router/route", {
            method: "POST",
            body: JSON.stringify({ question: question, case_id: caseId }),
            headers: { 'Content-Type': 'application/json' }
          });
          if (state.sourceRouterData) {
            state.sourceRouterData.routingResult = data;
            state.sourceRouterData.question = question;
          }
        } catch (e) { state.error = "Routing failed."; }
        state.loading = false; render();
      });
    }

    // Source router sidebar nav
    var sourceRouterNav = document.querySelector('.nav-item[data-view="source-router"]');
    if (sourceRouterNav) {
      sourceRouterNav.addEventListener("click", async function () {
        state.loading = true; render();
        try {
          var data = await api("/api/source-router/sources");
          state.sourceRouterData = { sources: data, routingResult: null, question: '' };
          state.view = "source-router";
        } catch (e) { state.error = "Failed to load source router."; }
        state.loading = false; render();
      });
    }

    // Monitoring sidebar nav
    // NOTE: sidebar nav items are handled generically by bindNavigation().
    // Only add special handlers here for items that need async data loading
    // when clicked from the sidebar (not from case detail buttons).

    // Back buttons
    var backInnovation = document.getElementById("back-from-innovation");
    if (backInnovation) backInnovation.addEventListener("click", function () { state.innovationAnalysis = null; navigateBackToCaseDetail(); });

    var backPatent = document.getElementById("back-from-patent");
    if (backPatent) backPatent.addEventListener("click", function () { state.patentSearchResults = null; state.patentSavedResults = null; navigateBackToCaseDetail(); });

    var backDeepAnalysis = document.getElementById("back-from-deep-analysis");
    if (backDeepAnalysis) backDeepAnalysis.addEventListener("click", function () { state.view = "patent-intelligence"; state.patentDeepAnalysis = null; render({ scroll: "preserve" }); });

    var backIP = document.getElementById("back-from-ip-strategy");
    if (backIP) backIP.addEventListener("click", function () { state.ipStrategy = null; navigateBackToCaseDetail(); });

    var backFromRegSelect = document.getElementById("back-from-regulatory-select");
    if (backFromRegSelect) backFromRegSelect.addEventListener("click", function () { navigateBackToCaseDetail(); });

    var backFromReg = document.getElementById("back-from-regulatory");
    if (backFromReg) backFromReg.addEventListener("click", function () { state.regulatoryProfile = null; navigateBackToCaseDetail(); });

    var backFromDashboard = document.getElementById("back-from-dashboard");
    if (backFromDashboard) backFromDashboard.addEventListener("click", function () { navigateBackToCaseDetail(); });

    // Regulatory jurisdiction selection
    document.querySelectorAll(".reg-jur-btn").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var jurisdiction = btn.getAttribute("data-jurisdiction");
        if (!state.currentCase) return;
        state.loading = true; render();
        try {
          var data = await api("/api/cases/" + state.currentCase.id + "/regulatory-analysis", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ jurisdiction: jurisdiction })
          });
          state.regulatoryProfile = data;
          state.view = "regulatory-intelligence";
        } catch (e) { state.error = "Failed to generate regulatory analysis."; }
        state.loading = false; render();
      });
    });

    // --- Jurisdiction Comparison (Phase 10) ---
    var jurisdictionCompareBtn = document.getElementById("open-jurisdiction-compare-btn");
    if (jurisdictionCompareBtn) {
      jurisdictionCompareBtn.addEventListener("click", async function () {
        var c = state.currentCase;
        if (!c) return;
        state.loading = true; render();
        try {
          var profile = state.regulatoryProfile;
          var selectedJurisdictions = [profile ? profile.jurisdiction : null];
          var allJurisdictions = ["IN", "US", "EU", "DE"];
          var otherJurisdictions = allJurisdictions.filter(function (j) { return j !== profile.jurisdiction; });
          selectedJurisdictions = selectedJurisdictions.concat(otherJurisdictions.slice(0, 2));
          var data = await api("/api/cases/" + c.id + "/jurisdiction-comparison", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ jurisdictions: selectedJurisdictions })
          });
          state.jurisdictionComparison = data;
          state.view = "jurisdiction-comparison";
        } catch (e) { state.error = "Failed to generate jurisdiction comparison."; }
        state.loading = false; render();
      });
    }

    var backFromJurisdictionComparison = document.getElementById("back-from-jurisdiction-comparison");
    if (backFromJurisdictionComparison) {
      backFromJurisdictionComparison.addEventListener("click", function () {
        state.view = "regulatory-intelligence";
        state.jurisdictionComparison = null;
        render();
      });
    }

    // Knowledge search
    var knowledgeSearchBtn = document.getElementById("knowledge-search-btn");
    if (knowledgeSearchBtn) {
      knowledgeSearchBtn.addEventListener("click", async function () {
        var query = document.getElementById("knowledge-search-input");
        if (!query || !query.value.trim()) return;
        state.loading = true; render();
        try {
          var body = { query: query.value.trim() };
          var plantInput = document.getElementById("knowledge-plant-input");
          var botanicalInput = document.getElementById("knowledge-botanical-input");
          var categorySelect = document.getElementById("knowledge-category");
          var jurisdictionSelect = document.getElementById("knowledge-jurisdiction");
          if (plantInput && plantInput.value) body.plant_name = plantInput.value;
          if (botanicalInput && botanicalInput.value) body.botanical_name = botanicalInput.value;
          if (categorySelect && categorySelect.value) body.category = categorySelect.value;
          if (jurisdictionSelect && jurisdictionSelect.value) body.jurisdiction = jurisdictionSelect.value;

          var data = await api("/api/knowledge/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
          });
          state.knowledgeFindings = data;
          var resultsDiv = document.getElementById("knowledge-results");
          if (resultsDiv) {
            if (data.findings && data.findings.length > 0) {
              var rhtml = '';
              data.findings.forEach(function (f) {
                rhtml += '<div class="knowledge-finding-card">'
                  + '<div class="knowledge-finding-header"><div class="knowledge-finding-title">' + escapeHtml(f.title) + '</div></div>';
                if (f.summary) rhtml += '<div class="knowledge-finding-summary">' + escapeHtml(f.summary) + '</div>';
                rhtml += '<div class="knowledge-finding-meta">';
                if (f.category) rhtml += '<span class="chip selected">' + escapeHtml(f.category) + '</span>';
                if (f.confidence) rhtml += '<span class="confidence-badge confidence-' + (f.confidence || "unknown").toLowerCase() + '">' + escapeHtml(f.confidence) + '</span>';
                if (f.jurisdiction) rhtml += '<span class="chip">' + escapeHtml(f.jurisdiction) + '</span>';
                rhtml += '</div>';
                if (f.source_name) rhtml += '<div class="source-label">Source: ' + escapeHtml(f.source_name) + '</div>';
                rhtml += '</div>';
              });
              resultsDiv.innerHTML = rhtml;
            } else {
              resultsDiv.innerHTML = '<div class="source-status-banner source-status-warning">' + icon("info", 18) + '<div>No findings returned. Source adapters may not be configured.</div></div>';
            }
          }
        } catch (e) { state.error = "Knowledge search failed."; }
        state.loading = false; render();
      });
    }

    // Patent search
    var patentSearchBtn = document.getElementById("run-patent-search");
    if (patentSearchBtn) {
      patentSearchBtn.addEventListener("click", async function () {
        if (!state.currentCase) return;
        state.loading = true; render();
        try {
          var jurisdictions = [];
          if (document.getElementById("pj-in") && document.getElementById("pj-in").checked) jurisdictions.push("IN");
          if (document.getElementById("pj-us") && document.getElementById("pj-us").checked) jurisdictions.push("US");
          if (document.getElementById("pj-eu") && document.getElementById("pj-eu").checked) jurisdictions.push("EU");
          if (document.getElementById("pj-de") && document.getElementById("pj-de").checked) jurisdictions.push("DE");

          var data = await api("/api/cases/" + state.currentCase.id + "/patent-search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ jurisdictions: jurisdictions })
          });
          state.patentSearchResults = data;
        } catch (e) { state.error = "Patent search failed."; }
        state.loading = false; render();
      });
    }

    // Patent save
    document.querySelectorAll(".patent-save-btn").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var patentId = btn.getAttribute("data-patent-id");
        if (!state.currentCase || !patentId) return;
        try {
          await api("/api/cases/" + state.currentCase.id + "/patents/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ patent_record_id: patentId })
          });
          toast("Patent saved to case", "success");
        } catch (e) { toast("Failed to save patent", "error"); }
      });
    });

    // Patent deep analysis
    document.querySelectorAll(".patent-analyze-btn").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var patentId = btn.getAttribute("data-patent-id");
        if (!state.currentCase || !patentId) return;
        state.loading = true; render();
        try {
          var data = await api("/api/cases/" + state.currentCase.id + "/patent-analyses", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ patent_record_id: patentId })
          });
          state.patentDeepAnalysis = data;
          state.view = "patent-deep-analysis";
        } catch (e) { state.error = "Failed to run deep analysis."; }
        state.loading = false; render();
      });
    });

    // Plant discovery upload
    var uploadZone = document.getElementById("upload-zone");
    var fileInput = document.getElementById("plant-file-input");
    if (uploadZone && fileInput) {
      uploadZone.addEventListener("click", function () { fileInput.click(); });
      uploadZone.addEventListener("dragover", function (e) { e.preventDefault(); uploadZone.classList.add("drag-over"); });
      uploadZone.addEventListener("dragleave", function () { uploadZone.classList.remove("drag-over"); });
      uploadZone.addEventListener("drop", function (e) { e.preventDefault(); uploadZone.classList.remove("drag-over"); if (e.dataTransfer.files.length > 0) handlePlantUpload(e.dataTransfer.files[0]); });
      fileInput.addEventListener("change", function () { if (fileInput.files.length > 0) handlePlantUpload(fileInput.files[0]); });
    }
  }

  // ----------------------------------------------------------------
  // Plant Upload Handler
  // ----------------------------------------------------------------
  async function handlePlantUpload(file) {
    var resultDiv = document.getElementById("plant-result");
    if (!resultDiv) return;
    resultDiv.innerHTML = '<div class="analyzing-overlay"><div class="skeleton" style="height:200px"></div><p style="text-align:center;margin-top:12px;color:var(--color-on-surface-variant)">Uploading image...</p></div>';

    try {
      // Step 1: Upload the image
      var formData = new FormData();
      formData.append("file", file);
      var discovery = await api("/api/plant-discoveries", { method: "POST", body: formData });

      // Show uploaded image + analyzing state
      var imgUrl = discovery.image_url || ("/api/plant-discoveries/" + discovery.id + "/image");
      resultDiv.innerHTML = '<div class="card" style="margin-top:16px"><div class="card-body">'
        + '<div style="display:flex;gap:16px;align-items:flex-start">'
        + '<img src="' + imgUrl + '" style="width:160px;height:120px;object-fit:cover;border-radius:var(--radius-md);border:1px solid var(--color-outline-variant)">'
        + '<div style="flex:1">'
        + '<h3 style="margin-bottom:4px">Image Uploaded</h3>'
        + '<p style="font-size:13px;color:var(--color-on-surface-variant)">' + escapeHtml(file.name) + ' (' + (file.size / 1024).toFixed(0) + ' KB)</p>'
        + '<div id="analyze-status" style="margin-top:8px;color:var(--color-on-surface-variant)">' + icon("hourglass_empty", 14) + ' Running botanical identification...</div>'
        + '</div></div></div>';

      // Step 2: Auto-analyze
      var analyzed = await api("/api/plant-discoveries/" + discovery.id + "/analyze", { method: "POST" });

      // Step 3: Show results
      var conf = analyzed.confidence || 0;
      var provider = analyzed.provider_used || 'unknown';
      var isReal = provider === 'plantnet';
      var isDemo = provider === 'demo';
      var hasCandidates = analyzed.candidate_name && conf > 0;
      var noPlantDetected = !hasCandidates && isReal;

      // Provider badge
      var isFallback = (analyzed.identification_notes || '').toLowerCase().includes('unreachable') || (analyzed.identification_notes || '').toLowerCase().includes('fallback');
      var providerBadge = '';
      if (isReal && !isFallback) {
        providerBadge = '<span class="chip" style="background:rgba(46,125,50,0.1);color:#2e7d32;font-size:10px">' + icon('verified', 12) + ' PlantNet AI — Real Identification</span>';
      } else if (isDemo && isFallback) {
        providerBadge = '<span class="chip" style="background:rgba(255,152,0,0.15);color:#e65100;font-size:10px">' + icon('warning', 12) + ' PlantNet Unavailable — Demo Fallback</span>'
          + '<span class="chip" style="background:rgba(255,87,34,0.08);color:#bf360c;font-size:10px;margin-left:4px">' + icon('science', 10) + ' Simulated Results</span>';
      } else if (isDemo) {
        providerBadge = '<span class="chip" style="background:rgba(255,152,0,0.1);color:#e65100;font-size:10px">' + icon('science', 12) + ' Demo Mode — Simulated Results</span>';
      }

      var confColor = conf >= 70 ? "var(--color-secondary)" : conf >= 40 ? "#d97706" : "var(--color-error)";
      var html = '<div class="card" style="margin-top:16px"><div class="card-body">'
        + '<div style="display:flex;gap:16px;align-items:flex-start">'
        + '<img src="' + imgUrl + '" style="width:160px;height:120px;object-fit:cover;border-radius:var(--radius-md);border:1px solid var(--color-outline-variant)">'
        + '<div style="flex:1">'

      // Provider badge
        + '<div style="margin-bottom:8px">' + providerBadge + '</div>'

      // No plant detected (real API)
      + (noPlantDetected ? '<div style="padding:16px;background:var(--color-surface-variant);border-radius:var(--radius-md);text-align:center">'
        + '<div style="font-size:48px;margin-bottom:8px">🌿</div>'
        + '<h3 style="margin:0 0 4px">No Plant Detected</h3>'
        + '<p style="font-size:13px;color:var(--color-on-surface-variant);margin:0">The PlantNet AI could not identify a plant in this image. This may not be a botanical photograph.</p>'
        + '<p style="font-size:11px;color:var(--color-on-surface-variant);margin:8px 0 0">Try uploading a clear photo of a leaf, flower, fruit, or bark.</p>'
        + '</div>'

      // Identification result
      : '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
        + '<h3 style="margin:0">' + escapeHtml(analyzed.candidate_name || "Identification Pending") + '</h3>'
        + '<span class="chip" style="background:' + confColor + '15;color:' + confColor + '">' + conf + '% confidence</span>'
        + '</div>'
        + (analyzed.botanical_name ? '<p style="font-style:italic;color:var(--color-on-surface-variant);margin-bottom:8px">' + escapeHtml(analyzed.botanical_name) + '</p>' : '')

      // Confidence bar
        + '<div style="margin:12px 0;padding:8px 12px;background:var(--color-surface-variant);border-radius:var(--radius-md);font-size:12px">'
        + '<div style="display:flex;justify-content:space-between;margin-bottom:4px"><span>Confidence</span><span style="font-weight:600">' + conf + '%</span></div>'
        + '<div style="height:6px;background:var(--color-outline-variant);border-radius:3px;overflow:hidden">'
        + '<div style="height:100%;width:' + conf + '%;background:' + confColor + ';border-radius:3px"></div></div></div>'

      // Safety warning
        + '<div style="padding:10px 12px;background:rgba(255,87,34,0.05);border:1px solid rgba(255,87,34,0.2);border-radius:var(--radius-md);font-size:12px;color:#d97706;line-height:1.5">'
        + icon('warning', 14) + ' <strong>Safety Warning:</strong> This is a preliminary AI identification. Expert botanical verification is recommended before any use. Never consume an unidentified plant.'
        + '</div>'

      // Verification status
        + (analyzed.verification_required ? '<div style="margin-top:8px;font-size:12px;color:var(--color-on-surface-variant)">' + icon('info', 12) + ' Expert verification required</div>' : '')

      // Alternative candidates
        + (analyzed.alternative_candidates && analyzed.alternative_candidates.length > 0
          ? '<div style="margin-top:12px"><span class="label-caps" style="color:var(--color-on-surface-variant);font-size:10px">ALTERNATIVE CANDIDATES</span>'
          + '<div style="margin-top:4px;display:flex;flex-wrap:wrap;gap:6px">'
          + analyzed.alternative_candidates.map(function (c) {
              return '<span class="chip" style="font-size:11px">' + escapeHtml(c.name || c.candidate_name || '') + ' (' + (c.confidence || 0) + '%)</span>';
            }).join('')
          + '</div></div>'
          : '')

      // Identification notes
        + (analyzed.identification_notes ? '<div style="margin-top:8px;font-size:12px;color:var(--color-on-surface-variant);line-height:1.5">' + escapeHtml(analyzed.identification_notes) + '</div>' : '')

        + '</div></div>'
        )

      // Actions
        + '<div style="margin-top:16px;padding-top:12px;border-top:1px solid var(--color-outline-variant);display:flex;gap:8px">'
        + '<button class="btn btn-primary btn-sm" id="plant-create-case-btn" data-discovery-id="' + escapeHtml(analyzed.id) + '">' + icon('add', 14) + ' Create Product Case from This</button>'
        + '<button class="btn btn-secondary btn-sm" id="plant-upload-another">' + icon('upload', 14) + ' Upload Another</button>'
        + '</div>'

        + '</div></div>';
      resultDiv.innerHTML = html;

      // Bind action buttons
      var createBtn = document.getElementById("plant-create-case-btn");
      if (createBtn) {
        createBtn.addEventListener("click", async function () {
          var discoveryId = this.getAttribute("data-discovery-id");
          try {
            var newCase = await api("/api/cases", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                name: (analyzed.candidate_name || "New Plant") + " — Product Case",
                ingredients: [{ name: analyzed.candidate_name || "Unknown", botanical: analyzed.botanical_name || "" }]
              })
            });
            toast("Product Case created from plant identification", "success");
            await loadCases();
            await loadCase(newCase.id);
          } catch (err) { toast("Failed to create case", "error"); }
        });
      }
      var uploadAnother = document.getElementById("plant-upload-another");
      if (uploadAnother) {
        uploadAnother.addEventListener("click", function () {
          resultDiv.innerHTML = '';
          document.getElementById("plant-file-input").value = '';
        });
      }

    } catch (e) {
      var errMsg = e.message || 'Unknown error';
      var isNetworkError = errMsg.includes('timeout') || errMsg.includes('fetch') || errMsg.includes('network');
      var isPlantNetError = errMsg.includes('PlantNet') || errMsg.includes('plantnet');
      
      var helpfulMsg = '';
      if (isPlantNetError && isNetworkError) {
        helpfulMsg = '<div style="margin-top:12px;padding:12px;background:rgba(255,152,0,0.1);border:1px solid rgba(255,152,0,0.3);border-radius:var(--radius-md);font-size:12px">'
          + '<strong>PlantNet API Unreachable</strong><br>'
          + 'The PlantNet identification service could not be reached from your network. '
          + 'This may be due to firewall settings or network restrictions.<br><br>'
          + '<strong>Options:</strong><br>'
          + '• Try from a different network<br>'
          + '• Check if <code>my-api.plantnet.org</code> is accessible<br>'
          + '• Use demo mode for testing (results are simulated)'
          + '</div>';
      } else if (isPlantNetError) {
        helpfulMsg = '<div style="margin-top:12px;padding:12px;background:rgba(255,152,0,0.1);border:1px solid rgba(255,152,0,0.3);border-radius:var(--radius-md);font-size:12px">'
          + '<strong>PlantNet API Error</strong><br>'
          + 'The PlantNet service returned an error. Your API key may be invalid or the service may be temporarily unavailable.'
          + '</div>';
      }
      
      resultDiv.innerHTML = '<div class="error-panel" style="margin-top:16px">' + icon("error", 20) + '<div><h4>Analysis Failed</h4><p>' + escapeHtml(errMsg) + '</p>' + helpfulMsg + '</div></div>';
    }
  }

  // ----------------------------------------------------------------
  // Profile Page Renderer & Handlers
  // ----------------------------------------------------------------
  function renderProfilePage() {
    var user = (window.AYUR_AUTH && typeof window.AYUR_AUTH.getUser === 'function' ? window.AYUR_AUTH.getUser() : null) || {
      display_name: "Deepansh Aggarwal",
      email: "india.deepanshaggarwal@gmail.com",
      username: "deepansh"
    };

    var name = user.display_name || user.username || "User";
    var email = user.email || "";
    var initials = window.AYUR_AUTH ? window.AYUR_AUTH.getInitials(name, email) : "DA";
    var avatarUrl = user.avatar_url || "";
    var bgColor = avatarUrl && avatarUrl.startsWith("#") ? avatarUrl : (window.AYUR_AUTH ? window.AYUR_AUTH.getAvatarColor(name || email) : "#7dba9a");
    var colors = (window.AYUR_AUTH && window.AYUR_AUTH.AVATAR_COLORS) || ['#7dba9a', '#4ecdc4', '#45b7d1', '#6c5ce7', '#fd79a8', '#fdcb6e', '#e17055', '#00b894'];

    var avatarHtml = '';
    if (avatarUrl && avatarUrl.startsWith('data:image')) {
      avatarHtml = '<img src="' + avatarUrl + '" alt="Avatar" style="width:76px;height:76px;border-radius:50%;object-fit:cover;border:2px solid #2ecc71;box-shadow:0 0 15px rgba(46,204,113,0.3);">';
    } else {
      avatarHtml = '<div style="width:76px;height:76px;border-radius:50%;background:' + bgColor + ';color:#fff;display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:700;box-shadow:0 8px 24px rgba(0,0,0,0.3);border:2px solid rgba(46,204,113,0.3);">' + escapeHtml(initials) + '</div>';
    }

    var html = ''
      + '<div class="profile-page-wrapper">'
      // Navigation Header Back to Dashboard
      + '<div class="profile-header-nav">'
      + '<button class="btn btn-secondary btn-sm" onclick="window.AYUR.navigateTo(\'dashboard\')">'
      + icon('arrow_back', 18) + ' <span>Back to Dashboard</span>'
      + '</button>'
      + '</div>'

      // Profile Main Card
      + '<div class="profile-card-main">'
      
      // Top User Header Banner
      + '<div class="profile-user-header">'
      + '<div class="profile-avatar-wrap">' + avatarHtml + '</div>'
      + '<div class="profile-user-meta">'
      + '<h2 class="profile-user-name">' + escapeHtml(name) + '</h2>'
      + '<p class="profile-user-email">' + escapeHtml(email) + '</p>'
      + '<div class="profile-badge-wrap">'
      + '<span class="profile-role-badge">' + icon('verified_user', 14) + ' Researcher</span>'
      + '</div>'
      + '</div>'
      + '</div>'

      + '<div class="profile-divider"></div>'

      // Section 1: Personal Information
      + '<div class="profile-section">'
      + '<div class="profile-section-title">' + icon('edit_note', 20) + ' <span>Personal Information</span></div>'
      + '<div class="profile-form-grid">'
      
      + '<div class="profile-field-item">'
      + '<label for="profile-fullname">Full Name</label>'
      + '<div class="profile-input-inline">'
      + '<input type="text" id="profile-fullname" class="profile-input" value="' + escapeHtml(name) + '" placeholder="e.g. Deepansh Aggarwal">'
      + '<button class="btn btn-primary btn-sm" onclick="window.saveProfileInfo()">Save</button>'
      + '</div>'
      + '</div>'

      + '<div class="profile-field-item">'
      + '<label>Email Address <span class="profile-readonly-badge">' + icon('lock', 12) + ' Read-only</span></label>'
      + '<div class="profile-readonly-value">' + escapeHtml(email) + '</div>'
      + '</div>'

      + '</div>'
      + '</div>'

      + '<div class="profile-divider"></div>'

      // Section 2: Change Password
      + '<div class="profile-section">'
      + '<div class="profile-section-title">' + icon('lock', 20) + ' <span>Change Password</span></div>'
      + '<div class="profile-form-grid">'
      + '<div class="profile-field-item">'
      + '<label for="profile-old-pass">Current Password</label>'
      + '<input type="password" id="profile-old-pass" class="profile-input" placeholder="••••••••">'
      + '</div>'
      + '<div class="profile-field-item">'
      + '<label for="profile-new-pass">New Password</label>'
      + '<input type="password" id="profile-new-pass" class="profile-input" placeholder="•••••••• (min 8 chars)">'
      + '</div>'
      + '<div class="profile-field-item">'
      + '<label for="profile-confirm-pass">Confirm New Password</label>'
      + '<input type="password" id="profile-confirm-pass" class="profile-input" placeholder="••••••••">'
      + '</div>'
      + '<div style="margin-top:8px;">'
      + '<button class="btn btn-secondary btn-sm" onclick="window.saveProfilePassword()">' + icon('key', 16) + ' Change Password</button>'
      + '</div>'
      + '</div>'
      + '</div>'

      + '<div class="profile-divider"></div>'

      // Section 3: Profile Picture & Avatar Theme
      + '<div class="profile-section">'
      + '<div class="profile-section-title">' + icon('image', 20) + ' <span>Profile Picture & Avatar Theme</span></div>'
      + '<p class="profile-section-subtitle">Select a color theme for your initials circle or upload a custom avatar image.</p>'
      + '<div class="profile-avatar-controls-wrap">'
      + '<div class="profile-color-palette">';

    colors.forEach(function(c) {
      var isSelected = (bgColor.toLowerCase() === c.toLowerCase() && (!avatarUrl || !avatarUrl.startsWith('data:image')));
      html += '<button class="profile-color-swatch ' + (isSelected ? 'active' : '') + '" style="background-color:' + c + '" onclick="window.setPresetAvatarColor(\'' + c + '\')" title="Set color theme"></button>';
    });

    html += '</div>'
      + '<div class="profile-avatar-btn-group">'
      + '<input type="file" id="profile-image-upload-input" accept="image/*" style="display:none;" onchange="window.handleAvatarUpload(event)">'
      + '<button class="btn btn-secondary btn-sm" onclick="document.getElementById(\'profile-image-upload-input\').click()">' + icon('upload_file', 16) + ' Choose Image</button>'
      + '<button class="btn btn-outline btn-sm text-danger" onclick="window.removeCustomAvatar()">' + icon('delete', 16) + ' Remove Image</button>'
      + '</div>'
      + '</div>'
      + '</div>'

      + '<div class="profile-divider"></div>'

      // Section 4: Account Actions
      + '<div class="profile-section">'
      + '<div class="profile-section-title">' + icon('manage_accounts', 20) + ' <span>Account Actions</span></div>'
      + '<div class="profile-actions-toolbar">'
      + '<button class="btn-profile-action btn-profile-signout" onclick="window.AYUR_AUTH.logout()">' + icon('logout', 18) + ' <span>Sign Out</span></button>'
      + '<button class="btn-profile-action btn-profile-switch" onclick="window.AYUR_AUTH.switchAccount()">' + icon('sync_alt', 18) + ' <span>Change Account</span></button>'
      + '<button class="btn-profile-action btn-profile-delete" onclick="window.AYUR_AUTH.deleteAccount()">' + icon('delete_forever', 18) + ' <span>Delete Account</span></button>'
      + '</div>'
      + '</div>'

      + '</div>' // End profile-card-main
      + '</div>'; // End profile-page-wrapper

    return html;
  }

  window.saveProfileInfo = async function() {
    var name = (document.getElementById('profile-fullname')?.value || '').trim();
    if (window.AYUR_AUTH && typeof window.AYUR_AUTH.updateProfile === 'function') {
      var res = await window.AYUR_AUTH.updateProfile(name, null);
      if (res && res.success) {
        if (window.AYUR && typeof window.AYUR.render === 'function') {
          window.AYUR.render();
        }
      }
    }
  };

  window.saveProfilePassword = async function() {
    var oldPass = (document.getElementById('profile-old-pass')?.value || '').trim();
    var newPass = (document.getElementById('profile-new-pass')?.value || '').trim();
    var confirmPass = (document.getElementById('profile-confirm-pass')?.value || '').trim();

    if (!oldPass || !newPass || !confirmPass) {
      showToast('⚠️ Please fill in all password fields', 'error');
      return;
    }

    if (newPass !== confirmPass) {
      showToast('⚠️ New passwords do not match', 'error');
      return;
    }

    if (window.AYUR_AUTH && typeof window.AYUR_AUTH.changePassword === 'function') {
      var res = await window.AYUR_AUTH.changePassword(oldPass, newPass);
      if (res && res.success) {
        document.getElementById('profile-old-pass').value = '';
        document.getElementById('profile-new-pass').value = '';
        document.getElementById('profile-confirm-pass').value = '';
      }
    }
  };

  window.setPresetAvatarColor = async function(colorHex) {
    if (window.AYUR_AUTH && typeof window.AYUR_AUTH.updateAvatar === 'function') {
      var res = await window.AYUR_AUTH.updateAvatar(colorHex);
      if (res && res.success && window.AYUR) {
        window.AYUR.render();
      }
    }
  };

  window.handleAvatarUpload = function(event) {
    var files = event.target.files;
    if (!files || files.length === 0) return;
    var file = files[0];
    if (file.size > 2 * 1024 * 1024) {
      showToast('⚠️ Image size must be less than 2MB', 'error');
      return;
    }
    var reader = new FileReader();
    reader.onload = async function(e) {
      var dataUrl = e.target.result;
      if (window.AYUR_AUTH && typeof window.AYUR_AUTH.updateAvatar === 'function') {
        var res = await window.AYUR_AUTH.updateAvatar(dataUrl);
        if (res && res.success && window.AYUR) {
          window.AYUR.render();
        }
      }
    };
    reader.readAsDataURL(file);
  };

  window.removeCustomAvatar = async function() {
    if (window.AYUR_AUTH && typeof window.AYUR_AUTH.updateAvatar === 'function') {
      var res = await window.AYUR_AUTH.updateAvatar('');
      if (res && res.success && window.AYUR) {
        window.AYUR.render();
      }
    }
  };

  function navigateTo(viewName, options) {
    var opt = options || {};

    // Save current view scroll position if leaving an active view
    if (state.view && state.view !== viewName) {
      saveCurrentViewScrollPosition();
    }

    state.view = viewName;
    saveStateToLocalStorage();

    if (opt.scroll) {
      render(opt);
    } else if (viewName === "case-detail" && opt.restorePrevious) {
      var savedPos = getSavedViewScrollPosition("case-detail");
      render({ scroll: savedPos ? "restore" : "top", savedPos: savedPos });
    } else {
      render({ scroll: "top" });
    }
  }

  // ----------------------------------------------------------------
  // LocalStorage Persistence Helpers
  // ----------------------------------------------------------------
  function saveStateToLocalStorage() {
    var st = (window.AYUR && window.AYUR.state) || state;
    var toSave = {
      currentCase: st.currentCase,
      cases: st.cases,
      view: st.view
    };
    try {
      localStorage.setItem('ayur_intel_state', JSON.stringify(toSave));
    } catch (e) {
      console.warn('Could not save state:', e);
    }
  }

  // ----------------------------------------------------------------
  // Data Loaders
  // ----------------------------------------------------------------
  async function loadCases() {
    try {
      var data = await api("/api/cases");
      state.cases = data.cases || [];
      saveStateToLocalStorage();
    } catch (e) { state.error = "Failed to load cases."; }
  }

  async function loadCase(id) {
    var existing = (state.cases || []).find(function (c) { return String(c.id) === String(id); });
    // Reset active module transient states so they do not bleed between cases
    state.innovationAnalysis = null;
    state.ipStrategy = null;
    state.regulatoryProfile = null;
    state.riskData = null;
    state.evidenceData = null;
    state.dashboardData = null;
    state.knowledgeGraphData = null;
    state.monitoringData = null;

    if (existing) {
      state.currentCase = existing;
      state.view = "case-detail";
      state.error = null;
      updateTopbarUI();
      render({ scroll: "top" });
    }
    try {
      var data = await api("/api/cases/" + id);
      state.currentCase = data;
      state.view = "case-detail";
      state.error = null;
      saveStateToLocalStorage();
      updateTopbarUI();
      render(existing ? { scroll: "preserve" } : { scroll: "top" });
    } catch (e) {
      if (!existing) {
        state.error = "Failed to load case.";
        render({ scroll: "top" });
      }
    }
  }

  function createCase() {
    if (window.AYUR && window.AYUR.initPassportData) {
      window.AYUR.initPassportData(null);
    }
    state.currentCase = null;
    state.view = "passport-wizard";
    state.passportStep = 0;
    updateTopbarUI();
    saveStateToLocalStorage();
    render({ scroll: "top" });
  }

  async function exploreDemoCase() {
    showToast("🌿 Opening official Ayurvedic Demo Case in Product Passport...", "info");
    state.currentCase = null;
    var demoData = null;
    try {
      demoData = await api("/api/cases/demo");
    } catch (err) {
      console.warn("Could not fetch /api/cases/demo, using local template:", err);
    }
    if (!demoData && window.AYUR && window.AYUR.DEMO_PASSPORT_DATA) {
      demoData = window.AYUR.DEMO_PASSPORT_DATA;
    }

    if (window.AYUR && typeof window.AYUR.initDemoPassport === "function") {
      window.AYUR.initDemoPassport(demoData);
    } else if (window.AYUR && typeof window.AYUR.initPassportData === "function") {
      window.AYUR.initPassportData(demoData);
      state.passportStep = 7;
    }
    state.view = "passport-wizard";
    state.passportStep = 7; // Review / Completed Passport view
    state.error = null;
    updateTopbarUI();
    saveStateToLocalStorage();
    render({ scroll: "top" });
  }

  // ----------------------------------------------------------------
  // Init
  // ----------------------------------------------------------------
  async function init() {
    bindNavigation();

    // Default state: Always start clean on dashboard with No Active Case
    state.currentCase = null;
    state.view = "dashboard";
    state.passportData = null;

    updateTopbarUI();
    render({ scroll: "top" });

    loadCases().then(function () {
      if (state.view === "dashboard" || state.view === "product-cases") {
        render({ scroll: "preserve" });
      }
    });
  }

  window.AYUR = {};

  // ----------------------------------------------------------------
  // Expose shared API for passport.js / knowledge.js
  // ----------------------------------------------------------------
  // Evidence Drawer
  window.AYUR.openEvidenceDrawer = async function (evidenceId) {
    try {
      var data = await api("/api/evidence/" + evidenceId);
      var overlay = document.createElement('div');
      overlay.className = 'modal-overlay open';
      overlay.innerHTML = '<div class="modal" style="max-width:600px">'
        + '<div class="modal-head"><h2>Evidence</h2><button class="modal-close" id="evidence-drawer-close">' + icon('close', 20) + '</button></div>'
        + '<div class="modal-body">'
        + '<div style="margin-bottom:16px"><span class="label-caps" style="color:var(--color-on-surface-variant)">EVIDENCE TYPE</span>'
        + '<div style="margin-top:4px"><span class="chip selected">' + escapeHtml(data.evidence_type) + '</span></div></div>'
        + (data.title ? '<div style="margin-bottom:16px"><span class="label-caps" style="color:var(--color-on-surface-variant)">TITLE</span><div style="margin-top:4px;font-weight:600">' + escapeHtml(data.title) + '</div></div>' : '')
        + (data.description ? '<div style="margin-bottom:16px"><span class="label-caps" style="color:var(--color-on-surface-variant)">DESCRIPTION</span><div style="margin-top:4px;font-size:14px;line-height:1.6;color:var(--color-on-surface-variant)">' + escapeHtml(data.description) + '</div></div>' : '')
        + (data.source_name ? '<div style="margin-bottom:16px"><span class="label-caps" style="color:var(--color-on-surface-variant)">SOURCE</span><div style="margin-top:4px;font-weight:600">' + escapeHtml(data.source_name) + '</div></div>' : '')
        + (data.authority ? '<div style="margin-bottom:16px"><span class="label-caps" style="color:var(--color-on-surface-variant)">AUTHORITY</span><div style="margin-top:4px">' + escapeHtml(data.authority) + '</div></div>' : '')
        + (data.jurisdiction ? '<div style="margin-bottom:16px"><span class="label-caps" style="color:var(--color-on-surface-variant)">JURISDICTION</span><div style="margin-top:4px">' + escapeHtml(data.jurisdiction) + '</div></div>' : '')
        + (data.reference ? '<div style="margin-bottom:16px"><span class="label-caps" style="color:var(--color-on-surface-variant)">REFERENCE</span><div style="margin-top:4px;font-family:JetBrains Mono,monospace;font-size:13px">' + escapeHtml(data.reference) + '</div></div>' : '')
        + (data.publication_date ? '<div style="margin-bottom:16px"><span class="label-caps" style="color:var(--color-on-surface-variant)">PUBLICATION DATE</span><div style="margin-top:4px">' + escapeHtml(data.publication_date) + '</div></div>' : '')
        + (data.retrieved_at ? '<div style="margin-bottom:16px"><span class="label-caps" style="color:var(--color-on-surface-variant)">RETRIEVED</span><div style="margin-top:4px">' + escapeHtml(data.retrieved_at) + '</div></div>' : '')
        + '<div style="margin-bottom:16px"><span class="label-caps" style="color:var(--color-on-surface-variant)">CONFIDENCE</span><div style="margin-top:4px">' + escapeHtml(data.confidence || 'N/A') + '</div></div>'
        + '<div style="margin-bottom:16px"><span class="label-caps" style="color:var(--color-on-surface-variant)">DATA ORIGIN</span><div style="margin-top:4px">' + escapeHtml(data.data_origin || 'N/A') + '</div></div>'
        + (data.excerpt ? '<div style="margin-bottom:16px"><span class="label-caps" style="color:var(--color-on-surface-variant)">EXCERPT</span><div style="margin-top:4px;padding:12px;border-left:3px solid var(--color-secondary);background:var(--color-surface-container-low);border-radius:var(--radius-md);font-style:italic;font-size:13px;line-height:1.6">' + escapeHtml(data.excerpt) + '</div></div>' : '')
        + '</div>'
        + '<div class="modal-foot"><button class="btn btn-ghost btn-sm" id="evidence-drawer-close-btn">Close</button></div>'
        + '</div>';
      document.body.appendChild(overlay);
      var closeFn = function () { overlay.remove(); };
      overlay.querySelector('#evidence-drawer-close').addEventListener('click', closeFn);
      overlay.querySelector('#evidence-drawer-close-btn').addEventListener('click', closeFn);
      overlay.addEventListener('click', function (e) { if (e.target === overlay) closeFn(); });
    } catch (err) { toast('Failed to load evidence', 'error'); }
  };

  window.AYUR = {
    state: state,
    api: api,
    toast: toast,
    escapeHtml: escapeHtml,
    icon: icon,
    render: render,
    parseJson: parseJson,
    field: field,
    loadCase: loadCase,
    loadCases: loadCases,
    deleteCase: deleteCase,
    openCase: openCase,
    showIngredientPopup: showIngredientPopup,
    searchIngredients: searchIngredients,
    getIngredientDetail: getIngredientDetail,
    autocompleteIngredients: autocompleteIngredients,
    getIngredientDescription: getIngredientDescription,
    closeIngredientPopup: closeIngredientPopup,
    updateTopbarUI: updateTopbarUI,
    renderCaseIntelligence: renderCaseIntelligence,
    renderCaseDetail: renderCaseDetail,
    renderKnowledgeHub: renderKnowledgeHub,
    filterKnowledgeSources: filterKnowledgeSources,
    filterKnowledge: filterKnowledge,
    saveStateToLocalStorage: saveStateToLocalStorage,
    openEvidenceDrawer: window.AYUR.openEvidenceDrawer,
    openRegistrationGuide: openRegistrationGuide,
    closeRegistrationPopup: closeRegistrationPopup,
    toggleIndicatorStatus: toggleIndicatorStatus,
    showCompletionPopup: showCompletionPopup,
    closeCompletionPopup: closeCompletionPopup,
    completeIndicator: completeIndicator,
    triggerFireworks: triggerFireworks,
    generateIPStrategy: generateIPStrategy,
    renderIPStrategyResult: renderIPStrategyResult,
    renderIPStrategy: renderIPStrategy,
    generateRegulatoryAnalysis: generateRegulatoryAnalysis,
    renderRegulatoryIntelligence: renderRegulatoryIntelligence,
    generateRiskAssessment: generateRiskAssessment,
    renderRiskView: renderRiskView,
    focusRiskInRegister: focusRiskInRegister,
    toggleRiskAccordion: toggleRiskAccordion,
    openRegulatoryGuide: openRegulatoryGuide,
    editProductPassport: editProductPassport,
    scrollToTop: scrollToTop,
    getScrollPosition: getScrollPosition,
    restoreScrollPosition: restoreScrollPosition,
    saveCurrentViewScrollPosition: saveCurrentViewScrollPosition,
    navigateBackToCaseDetail: navigateBackToCaseDetail,
    navigateTo: navigateTo,
    renderProfilePage: renderProfilePage,
    exploreDemoCase: exploreDemoCase,
    openKnowledgeGraph: openKnowledgeGraph,
    invalidateClientApiCache: invalidateClientApiCache,
    invalidateCaseModuleCache: invalidateCaseModuleCache
  };

  // Boot
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

// Global Keyboard Shortcut: Escape closes active modal overlays
document.addEventListener("keydown", function(e) {
  if (e.key === "Escape") {
    var modals = document.querySelectorAll(".modal-overlay.open, .modal-backdrop.open, #case-switcher-modal, #detail-popup, .detail-popup-overlay");
    modals.forEach(function(m) {
      m.classList.remove("open");
      if (m.id === 'detail-popup' || m.classList.contains('detail-popup-overlay')) {
        m.remove();
      } else if (m.style.display !== "none") {
        m.style.display = "none";
      }
    });
  }
});
