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

  function field(label, value) {
    var v = value || "";
    var cls = v ? "value" : "value empty";
    return '<div class="detail-field"><label>' + escapeHtml(label) + '</label><div class="' + cls + '">' + (escapeHtml(v) || "Not specified") + '</div></div>';
  }

  // ----------------------------------------------------------------
  // API helpers
  // ----------------------------------------------------------------
  async function api(url, opts) {
    try {
      var resp = await fetch(url, opts || {});
      if (!resp.ok) { var err = await resp.text(); throw new Error(err); }
      return await resp.json();
    } catch (e) {
      console.error("API error:", url, e);
      throw e;
    }
  }

  // ----------------------------------------------------------------
  // Render dispatcher
  // ----------------------------------------------------------------
  function render() {
    var content = document.getElementById("content");
    if (!content) return;

    if (state.loading) {
      content.innerHTML = '<div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div>';
      return;
    }

    if (state.error) {
      content.innerHTML = '<div class="error-panel">' + icon("error", 20) + '<div><h4>Error</h4><p>' + escapeHtml(state.error) + '</p></div></div>';
      return;
    }

    if (state.view === "dashboard") {
      content.innerHTML = renderDashboard();
    } else if (state.view === "product-cases") {
      content.innerHTML = renderProductCases();
    } else if (state.view === "case-detail") {
      if (state.currentCase) {
        if (window.AYUR && window.AYUR.renderCaseDetail) {
          content.innerHTML = window.AYUR.renderCaseDetail();
        } else {
          content.innerHTML = renderCaseDetail();
        }
      } else {
        content.innerHTML = renderNoCaseSelectedForIntel();
      }
    } else if (state.view === "knowledge-hub") {
      content.innerHTML = renderKnowledgeHub();
    } else if (state.view === "passport-wizard" && state.passportData) {
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
    } else if (state.view === "innovation-analysis" && state.innovationAnalysis) {
      content.innerHTML = renderInnovationAnalysis();
    } else if (state.view === "patent-intelligence") {
      content.innerHTML = renderPatentIntelligence();
    } else if (state.view === "patent-deep-analysis" && state.patentDeepAnalysis) {
      content.innerHTML = renderPatentDeepAnalysis();
    } else if (state.view === "ip-strategy" && state.ipStrategy) {
      content.innerHTML = renderIPStrategy();
    } else if (state.view === "regulatory-select") {
      content.innerHTML = renderRegulatorySelect();
    } else if (state.view === "regulatory-intelligence" && state.regulatoryProfile) {
      content.innerHTML = renderRegulatoryIntelligence();
    } else if (state.view === "jurisdiction-comparison" && state.jurisdictionComparison) {
      content.innerHTML = renderJurisdictionComparison();
    } else if (state.view === "evidence") {
      content.innerHTML = renderEvidenceView();
    } else if (state.view === "risk" && state.riskData) {
      content.innerHTML = renderRiskView();
    } else if (state.view === "dashboard-detail" && state.dashboardData) {
      content.innerHTML = renderDecisionDashboard();
    } else if (state.view === "monitoring-center" && state.monitoringData) {
      content.innerHTML = renderMonitoringCenter();
    } else if (state.view === "knowledge-graph" && state.knowledgeGraphData) {
      content.innerHTML = renderKnowledgeGraph();
    } else if (state.view === "source-router" && state.sourceRouterData) {
      content.innerHTML = renderSourceRouter();
    } else if (state.view === "source-router") {
      // Sidebar nav to source-router without case data
      content.innerHTML = renderSourceRouter();
    } else if (state.view === "review-queue") {
      content.innerHTML = renderReviewQueue();
    } else if (state.view === "settings") {
      content.innerHTML = renderSettings();
    } else if (state.view === "monitoring-center") {
      content.innerHTML = renderMonitoringCenter();
    } else {
      content.innerHTML = renderDashboard();
    }

    updateTopBarAndActiveNav(state.view);
    bindEvents();
    if (state.view === 'passport-wizard' && window.AYUR && window.AYUR.bindPassportEvents) { window.AYUR.bindPassportEvents(); }

    // Initialize graph visualization if on knowledge-graph view
    if (state.view === 'knowledge-graph' && state.knowledgeGraphData) {
      setTimeout(function () { initGraphVisualization(); }, 100);
    }
  }

  // ----------------------------------------------------------------
  // Dashboard View
  // ----------------------------------------------------------------
  function renderDashboard() {
    var cases = state.cases || [];
    var pillars = [
      { icon: "verified", title: "Evidence-Backed", desc: "Ground product claims in scientific research and classical Ayurvedic literature." },
      { icon: "language", title: "Jurisdiction-Aware", desc: "Evaluate regulatory pathways across India, United States, and European Union markets." },
      { icon: "lightbulb", title: "IP & Innovation", desc: "Identify formulation whitespace and evaluate patent landscape overlaps proactively." }
    ];
    var pipeline = [
      { icon: "psychology", label: "Idea" }, { icon: "eco", label: "Plant Eval" },
      { icon: "menu_book", label: "Lit Review" }, { icon: "science", label: "Formulation" },
      { icon: "gavel", label: "Patent Check" }, { icon: "policy", label: "Regs Check" },
      { icon: "verified", label: "Evidence" }, { icon: "warning", label: "Risk Assmt" },
      { icon: "rocket_launch", label: "Go-to-Market" }, { icon: "visibility", label: "Monitoring" }
    ];

    var html = ''
      + '<div class="hero-section hero-pattern">'
      + '<div class="hero-content">'
      + '<h1>Ayurvedic Product Intelligence & Decision Support</h1>'
      + '<p>Connect Traditional Knowledge, patent landscapes, regulatory pathways, and global markets through evidence-backed intelligence.</p>'
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
    pipeline.forEach(function (n, i) {
      var cls = i <= 1 ? "active" : "inactive";
      html += '<div class="pipeline-node">'
        + '<div class="pipeline-node-circle ' + cls + '">' + icon(n.icon, 18) + '</div>'
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
        var jurisdictions = parseJson(c.jurisdictions);
        var ingredients = parseJson(c.ingredients);
        html += '<div class="case-card" data-case-id="' + c.id + '">'
          + '<div class="case-card-header">'
          + '<div class="case-card-name">' + escapeHtml(c.name) + '</div>'
          + '</div>'
          + '<div class="case-card-meta">'
          + '<span class="case-badge case-badge-stage">' + escapeHtml(stageLabel(c.stage)) + '</span>'
          + '<span class="case-badge case-badge-status">' + escapeHtml(statusLabel(c.status)) + '</span>'
          + '</div>'
          + '<div class="case-card-stats">'
          + '<div class="case-stat"><div class="case-stat-label">JURISDICTIONS</div><div class="case-stat-value">' + (jurisdictions.join(", ") || "None") + '</div></div>'
          + '<div class="case-stat"><div class="case-stat-label">INGREDIENTS</div><div class="case-stat-value">' + ingredients.length + '</div></div>'
          + '<div class="case-stat"><div class="case-stat-label">CREATED</div><div class="case-stat-value">' + new Date(c.created_at).toLocaleDateString() + '</div></div>'
          + '<div class="case-stat"><div class="case-stat-label">UPDATED</div><div class="case-stat-value">' + new Date(c.updated_at).toLocaleDateString() + '</div></div>'
          + '</div>'
          + '<div class="case-card-footer">'
          + '<button class="btn btn-ghost btn-sm" data-open-case="' + c.id + '">Open Case ' + icon("chevron_right", 16) + '</button>'
          + '</div></div>';
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
      + '<div class="section-header"><div><h2>Products</h2><p style="font-size:13px;color:var(--text-secondary);margin-top:2px;">Review and manage all active product cases and research profiles.</p></div>'
      + '<button class="btn btn-primary btn-sm" id="create-case-btn-3">' + icon("add", 14) + ' New Case</button></div>';
    if (cases.length === 0) {
      html += '<div class="empty-state"><div class="empty-icon">' + icon("inventory_2", 28) + '</div>'
        + '<h3>No Products Found</h3><p>Create your first product case to initiate intelligence analysis.</p></div>';
    } else {
      html += '<div class="case-grid">';
      cases.forEach(function (c) {
        html += '<div class="case-card" data-case-id="' + c.id + '">'
          + '<div class="case-card-header"><div class="case-card-name">' + escapeHtml(c.name) + '</div></div>'
          + '<div class="case-card-meta">'
          + '<span class="case-badge case-badge-stage">' + escapeHtml(stageLabel(c.stage)) + '</span>'
          + '<span class="case-badge case-badge-status">' + escapeHtml(statusLabel(c.status)) + '</span>'
          + '</div>'
          + '<div class="case-card-footer">'
          + '<button class="btn btn-ghost btn-sm" data-open-case="' + c.id + '">Open ' + icon("chevron_right", 16) + '</button>'
          + '</div></div>';
      });
      html += '</div>';
    }
    return html;
  }

  // ----------------------------------------------------------------
  // Case Detail View
  // ----------------------------------------------------------------
  // ----------------------------------------------------------------
  // Case Intelligence Workspace (Phase 2)
  // ----------------------------------------------------------------
  function renderCaseDetail() {
    var c = state.currentCase;
    if (!c) return renderNoCaseSelectedForIntel();

    var jurisdictions = parseJson(c.jurisdictions);
    var ingredients = parseJson(c.ingredients);
    var claims = parseJson(c.claims);

    var html = ''
      + '<div class="case-header" style="margin-bottom:24px;">'
      + '<div>'
      + '<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">'
      + '<span class="passport-badge-tag" style="background:rgba(52,211,153,0.15);color:#34d399;font-weight:600;">' + icon("verified", 14) + ' Active Product Case</span>'
      + '<span class="case-badge case-badge-stage">' + escapeHtml(stageLabel(c.stage)) + '</span>'
      + '</div>'
      + '<h1 class="case-title" style="font-size:26px;color:#ffffff;">' + escapeHtml(c.name) + '</h1>'
      + '<div class="case-subtitle" style="color:var(--text-secondary);">' + escapeHtml(c.form || "Ayurvedic Product") + ' • Target Markets: ' + (jurisdictions.join(", ") || "Global") + '</div>'
      + '</div>'
      + '<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">'
      + '<button class="btn btn-secondary btn-sm" id="case-switch-btn">' + icon("swap_horiz", 16) + ' Switch Case</button>'
      + '<button class="btn btn-primary btn-sm" id="open-passport-btn">' + icon("edit_note", 16) + ' Edit Passport</button>'
      + '</div></div>'

      // Product Passport Summary Banner
      + '<div class="passport-review-card" style="margin-bottom:28px;">'
      + '<div class="passport-review-header" style="padding:20px 24px;display:flex;align-items:center;justify-content:space-between;">'
      + '<div>'
      + '<div class="passport-review-category" style="color:#34d399;">' + icon("spa", 14) + ' Product Passport Baseline</div>'
      + '<h3 style="font-size:18px;margin-top:4px;color:#ffffff;">' + escapeHtml(c.name) + '</h3>'
      + '</div>'
      + '<button class="btn btn-secondary btn-sm" id="passport-reopen-btn" style="background:rgba(255,255,255,0.08);color:#fff;border-color:rgba(255,255,255,0.2);">' + icon("visibility", 14) + ' Review Full Passport</button>'
      + '</div>'
      + '<div style="padding:20px 24px;display:grid;grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));gap:16px;">'
      + '<div><span class="label-caps" style="color:var(--text-secondary);font-size:11px;">FORMULATION & FORM</span><div style="font-size:14px;font-weight:600;color:#ffffff;margin-top:2px;">' + escapeHtml(c.form || "Powder / Churna") + '</div></div>'
      + '<div><span class="label-caps" style="color:var(--text-secondary);font-size:11px;">VERIFIED BOTANICALS</span><div style="font-size:14px;font-weight:600;color:#ffffff;margin-top:2px;">' + ingredients.length + ' Ingredients Identified</div></div>'
      + '<div><span class="label-caps" style="color:var(--text-secondary);font-size:11px;">INTENDED INDICATION</span><div style="font-size:14px;font-weight:600;color:#ffffff;margin-top:2px;">' + escapeHtml(c.intended_use || "General Wellness") + '</div></div>'
      + '<div><span class="label-caps" style="color:var(--text-secondary);font-size:11px;">PREPARATION PROCESS</span><div style="font-size:14px;font-weight:600;color:#ffffff;margin-top:2px;">' + escapeHtml(c.process || "Standard Ayurvedic preparation") + '</div></div>'
      + '</div>'
      + '</div>'

      // Section Header: Intelligence Modules
      + '<div class="section-header" style="margin-bottom:16px;">'
      + '<div><h2 style="font-size:20px;color:#ffffff;">Intelligence Workspace</h2>'
      + '<p style="font-size:13px;color:var(--text-secondary);margin-top:2px;">Comprehensive analysis across innovation, patent landscapes, regulatory pathways, and risk.</p></div>'
      + '</div>'

      // 10 Interactive Intelligence Module Cards Grid
      + '<div class="intel-workspace-grid">'

      // 1. Innovation Analysis
      + '<div class="intel-module-card" id="card-intel-innovation">'
      + '<div class="intel-module-head">'
      + '<div class="intel-module-icon">' + icon("hub", 22) + '</div>'
      + '<div class="intel-module-title">Innovation Analysis</div>'
      + '</div>'
      + '<p class="intel-module-desc">Decompose formulation into ingredients, process, claims, and areas of potential differentiation.</p>'
      + '<div class="intel-module-action"><span>Analyze Innovation</span> ' + icon("arrow_forward", 16) + '</div>'
      + '</div>'

      // 2. Patents & IP
      + '<div class="intel-module-card" id="card-intel-patent">'
      + '<div class="intel-module-head">'
      + '<div class="intel-module-icon">' + icon("gavel", 22) + '</div>'
      + '<div class="intel-module-title">Patents & IP</div>'
      + '</div>'
      + '<p class="intel-module-desc">Search patent databases across India, USA, and EU to assess prior art and claim similarity.</p>'
      + '<div class="intel-module-action"><span>Explore Patent Landscape</span> ' + icon("arrow_forward", 16) + '</div>'
      + '</div>'

      // 3. IP Strategy Roadmap
      + '<div class="intel-module-card" id="card-intel-ip">'
      + '<div class="intel-module-head">'
      + '<div class="intel-module-icon">' + icon("analytics", 22) + '</div>'
      + '<div class="intel-module-title">IP Strategy</div>'
      + '</div>'
      + '<p class="intel-module-desc">Prioritized IP investigation roadmap and potential protection routes for key components.</p>'
      + '<div class="intel-module-action"><span>View IP Strategy</span> ' + icon("arrow_forward", 16) + '</div>'
      + '</div>'

      // 4. Regulatory Pathways
      + '<div class="intel-module-card" id="card-intel-regulatory">'
      + '<div class="intel-module-head">'
      + '<div class="intel-module-icon">' + icon("policy", 22) + '</div>'
      + '<div class="intel-module-title">Regulatory Pathways</div>'
      + '</div>'
      + '<p class="intel-module-desc">Assess product classification, allowable claims, and compliance across target markets.</p>'
      + '<div class="intel-module-action"><span>Evaluate Pathways</span> ' + icon("arrow_forward", 16) + '</div>'
      + '</div>'

      // 5. Risk Assessment
      + '<div class="intel-module-card" id="card-intel-risk">'
      + '<div class="intel-module-head">'
      + '<div class="intel-module-icon">' + icon("warning", 22) + '</div>'
      + '<div class="intel-module-title">Risk Assessment</div>'
      + '</div>'
      + '<p class="intel-module-desc">Identify areas requiring attention across IP, traditional knowledge, regulation, and evidence completeness.</p>'
      + '<div class="intel-module-action"><span>Review Risks</span> ' + icon("arrow_forward", 16) + '</div>'
      + '</div>'

      // 6. Evidence Review
      + '<div class="intel-module-card" id="card-intel-evidence">'
      + '<div class="intel-module-head">'
      + '<div class="intel-module-icon">' + icon("verified", 22) + '</div>'
      + '<div class="intel-module-title">Evidence Review</div>'
      + '</div>'
      + '<p class="intel-module-desc">Review verified scientific citations, clinical trials, and classical Ayurvedic references.</p>'
      + '<div class="intel-module-action"><span>View Evidence</span> ' + icon("arrow_forward", 16) + '</div>'
      + '</div>'

      // 7. Decision Support
      + '<div class="intel-module-card" id="card-intel-decision">'
      + '<div class="intel-module-head">'
      + '<div class="intel-module-icon">' + icon("leaderboard", 22) + '</div>'
      + '<div class="intel-module-title">Decision Support</div>'
      + '</div>'
      + '<p class="intel-module-desc">Consolidated decision context, risk-weighted readiness score, and recommended next steps.</p>'
      + '<div class="intel-module-action"><span>Open Decision Support</span> ' + icon("arrow_forward", 16) + '</div>'
      + '</div>'

      // 8. Interactive Knowledge Graph
      + '<div class="intel-module-card" id="card-intel-graph">'
      + '<div class="intel-module-head">'
      + '<div class="intel-module-icon">' + icon("account_tree", 22) + '</div>'
      + '<div class="intel-module-title">Knowledge Graph</div>'
      + '</div>'
      + '<p class="intel-module-desc">Interactive force-directed graph exploring entity connections between plants, targets, and patents.</p>'
      + '<div class="intel-module-action"><span>Explore Graph</span> ' + icon("arrow_forward", 16) + '</div>'
      + '</div>'

      // 9. Continuous Monitoring
      + '<div class="intel-module-card" id="card-intel-monitoring">'
      + '<div class="intel-module-head">'
      + '<div class="intel-module-icon">' + icon("visibility", 22) + '</div>'
      + '<div class="intel-module-title">Continuous Monitoring</div>'
      + '</div>'
      + '<p class="intel-module-desc">Configure automated alerts for newly published patents, regulatory updates, and literature.</p>'
      + '<div class="intel-module-action"><span>Manage Monitoring</span> ' + icon("arrow_forward", 16) + '</div>'
      + '</div>'

      // 10. AI Source Router
      + '<div class="intel-module-card" id="card-intel-router">'
      + '<div class="intel-module-head">'
      + '<div class="intel-module-icon">' + icon("database", 22) + '</div>'
      + '<div class="intel-module-title">AI Source Router</div>'
      + '</div>'
      + '<p class="intel-module-desc">Route specific pharmacological questions directly to connected institutional knowledge sources.</p>'
      + '<div class="intel-module-action"><span>Route Query</span> ' + icon("arrow_forward", 16) + '</div>'
      + '</div>'

      + '</div>'; // End intel-workspace-grid

    return html;
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
  function renderPatentIntelligence() {
    var results = state.patentSavedResults || state.patentSearchResults;
    var html = ''
      + '<div class="view-header"><button class="btn btn-ghost btn-sm" id="back-from-patent">' + icon("arrow_back", 15) + ' Back to Case</button></div>'
      + '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>Indian Patent Intelligence</h2>'
      + '<p>Search Indian Patent Office (IPO / CGPDTM) application records, formulation overlaps, and botanical composition claims</p></div>'
      + '<div class="card-body">'
      + '<div style="margin-bottom:14px;display:flex;align-items:center;gap:10px;">'
      + '<span class="chip selected" style="background:rgba(52,211,153,0.15);color:#34d399;font-size:12px;padding:6px 12px;">🇮🇳 Indian Patent Office (IPO / CGPDTM)</span>'
      + '</div>'
      + '<button class="btn btn-primary btn-sm" id="run-patent-search">' + icon("search", 14) + ' Run Indian Patent Intelligence Search</button>'
      + '</div></div>';

    if (results && results.results && results.results.length > 0) {
      results.results.forEach(function (r) {
        html += '<div class="patent-result-card">'
          + '<div class="patent-result-header"><div>'
          + '<div class="patent-result-type">' + escapeHtml(r.jurisdiction) + '</div>'
          + '<div class="patent-result-title">' + escapeHtml(r.title || "Untitled Patent Record") + '</div>'
          + '</div></div>'
          + '<div class="patent-result-details">'
          + '<div><strong>Publication:</strong> ' + escapeHtml(r.publication_number || "N/A") + '</div>'
          + '<div><strong>Applicant:</strong> ' + escapeHtml(r.applicant || "N/A") + '</div>'
          + '<div><strong>Priority Date:</strong> ' + escapeHtml(r.priority_date || "N/A") + '</div>'
          + '<div><strong>Status:</strong> ' + escapeHtml(r.status || "N/A") + '</div>'
          + '</div>';
        if (r.abstract) html += '<div class="patent-result-abstract">' + escapeHtml(r.abstract.substring(0, 300)) + '</div>';
        html += '<div class="patent-result-actions">'
          + '<button class="btn btn-secondary btn-sm patent-analyze-btn" data-patent-id="' + escapeHtml(r.id) + '">' + icon("analytics", 14) + ' Deep Analysis</button>'
          + '<button class="btn btn-ghost btn-sm patent-save-btn" data-patent-id="' + escapeHtml(r.id) + '">' + icon("bookmark", 14) + ' Save to Case</button>'
          + '</div></div>';
      });
    } else if (results) {
      html += '<div class="source-status-banner source-status-warning">' + icon("info", 18)
        + '<div>No patent records found for the selected query and target markets.</div></div>';
    }
    return html;
  }

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
  // IP Strategy Map View
  // ----------------------------------------------------------------
  function renderIPStrategy() {
    var s = state.ipStrategy;
    if (!s) return '';
    var html = ''
      + '<div class="view-header"><button class="btn btn-ghost btn-sm" id="back-from-ip-strategy">' + icon("arrow_back", 15) + ' Back to Case</button></div>'
      + '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>IP Strategy Map</h2>'
      + '<p>Visual IP investigation roadmap derived from your product analysis</p></div><div class="card-body">';

    html += '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px">'
      + '<div><span class="label-caps" style="color:var(--color-on-surface-variant)">HIGH PRIORITY</span><div style="font-size:24px;font-weight:600;color:var(--color-on-surface)">' + (s.high_priority_count || 0) + '</div></div>'
      + '<div><span class="label-caps" style="color:var(--color-on-surface-variant)">MEDIUM</span><div style="font-size:24px;font-weight:600;color:var(--color-on-surface)">' + (s.medium_priority_count || 0) + '</div></div>'
      + '<div><span class="label-caps" style="color:var(--color-on-surface-variant)">LOW</span><div style="font-size:24px;font-weight:600;color:var(--color-on-surface)">' + (s.low_priority_count || 0) + '</div></div>'
      + '<div><span class="label-caps" style="color:var(--color-on-surface-variant)">INFO NEEDED</span><div style="font-size:24px;font-weight:600;color:var(--color-on-surface)">' + (s.info_needed_count || 0) + '</div></div>'
      + '</div></div></div>';

    if (s.items && s.items.length > 0) {
      s.items.forEach(function (item) {
        var priColor = "var(--color-outline)";
        if (item.priority === "HIGH") priColor = "var(--color-error)";
        else if (item.priority === "MEDIUM") priColor = "#d97706";
        else if (item.priority === "LOW") priColor = "var(--color-secondary)";

        html += '<div class="innovation-component-card">'
          + '<div class="innovation-component-header"><div>'
          + '<div class="innovation-component-type">' + escapeHtml(item.component_type) + '</div>'
          + '<div class="innovation-component-label">' + escapeHtml(item.component_label) + '</div></div>'
          + '<span class="innovation-classification-badge" style="background:' + priColor + '20;color:' + priColor + '">' + escapeHtml(item.priority) + '</span></div>'
          + '<div style="margin:8px 0"><span class="label-caps" style="color:var(--color-on-surface-variant)">IP CATEGORY</span> '
          + '<span class="chip selected">' + escapeHtml(item.ip_category.replace(/_/g, " ")) + '</span></div>';
        if (item.reason) html += '<div class="innovation-component-explanation">' + escapeHtml(item.reason) + '</div>';
        if (item.next_action) html += '<div class="innovation-component-ip"><span class="label-caps" style="color:var(--color-on-surface-variant)">Next Action</span> ' + escapeHtml(item.next_action) + '</div>';
        html += '</div>';
      });
    }

    html += '<div class="innovation-disclaimer">' + icon("warning", 18) + '<div><strong>Research & Decision Support Only.</strong> This strategy map is not legal advice and does not guarantee registration, patentability, or protection.</div></div>';
    return html;
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
    html += '<div class="card" style="border-left:4px solid ' + ipColor + '"><div class="card-body">'
      + '<div class="label-caps" style="color:var(--color-on-surface-variant);margin-bottom:4px">IP INTELLIGENCE</div>'
      + '<div style="font-size:16px;font-weight:700;color:' + ipColor + ';margin-bottom:4px">' + (statusLabels[summary.ip_status] || summary.ip_status) + '</div>'
      + '<div style="font-size:12px;color:var(--color-on-surface-variant)">' + escapeHtml(summary.ip_reason || '') + '</div>'
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
  // Risk + Self-Extension View (Phase 12)
  // ----------------------------------------------------------------

  function renderRiskView() {
    var rd = state.riskData;
    if (!rd) return '<div class="card"><div class="card-body"><p>No risk data available.</p></div></div>';

    var levelColors = { HIGH: 'var(--color-error)', MEDIUM: '#d97706', LOW: 'var(--color-secondary)', UNKNOWN: 'var(--color-outline)' };
    var levelLabels = { HIGH: 'High', MEDIUM: 'Medium', LOW: 'Low', UNKNOWN: 'Unknown' };
    var categoryLabels = {
      PATENT_IP: 'Patent / IP', REGULATORY: 'Regulatory',
      INGREDIENT_PRODUCT_INFO: 'Product Information', CLAIMS: 'Claims',
      TK_PRIOR_ART: 'TK / Prior Art', DATA_EVIDENCE_GAP: 'Evidence Gap',
      JURISDICTION_UNCERTAINTY: 'Jurisdiction Uncertainty'
    };
    var categoryIcons = {
      PATENT_IP: 'gavel', REGULATORY: 'policy', INGREDIENT_PRODUCT_INFO: 'eco',
      CLAIMS: 'verified', TK_PRIOR_ART: 'menu_book', DATA_EVIDENCE_GAP: 'warning',
      JURISDICTION_UNCERTAINTY: 'language'
    };
    var healthColors = { GOOD: 'var(--color-secondary)', PARTIAL: '#d97706', LIMITED: 'var(--color-error)' };
    var phaseLabels = {
      PHASE_5_INNOVATION: 'Innovation Map', PHASE_6_PATENT: 'Patent Intelligence',
      PHASE_7_PATENT_DEEP: 'Patent Deep Analysis', PHASE_8_IP_STRATEGY: 'IP Strategy',
      PHASE_9_REGULATORY: 'Regulatory Intel', PHASE_10_JURISDICTION: 'Jurisdiction Compare',
      USER_INPUT: 'User Input'
    };

    var html = ''
      + '<div class="view-header"><button class="btn btn-ghost btn-sm" id="back-from-risk">' + icon('arrow_back', 15) + ' Back to Case</button></div>'

      // Header card
      + '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>Risk &amp; Analysis Health</h2>'
      + '<p>Potential issues and missing information for ' + escapeHtml(rd.product_name || '') + '</p></div><div class="card-body">'

      // Risk summary stats
      + '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:20px">'
      + '<div class="patent-stat-card"><div class="patent-stat-label">TOTAL RISKS</div><div class="patent-stat-value">' + rd.total_risks + '</div></div>'
      + '<div class="patent-stat-card" style="border-left:4px solid ' + levelColors.HIGH + '"><div class="patent-stat-label">HIGH</div><div class="patent-stat-value">' + rd.high_count + '</div></div>'
      + '<div class="patent-stat-card" style="border-left:4px solid ' + levelColors.MEDIUM + '"><div class="patent-stat-label">MEDIUM</div><div class="patent-stat-value">' + rd.medium_count + '</div></div>'
      + '<div class="patent-stat-card" style="border-left:4px solid ' + levelColors.LOW + '"><div class="patent-stat-label">LOW</div><div class="patent-stat-value">' + rd.low_count + '</div></div>'
      + '</div>';

    // Analysis Health
    var h = rd.analysis_health || {};
    html += '<div style="margin-bottom:16px"><span class="label-caps" style="color:var(--color-on-surface-variant)">ANALYSIS HEALTH</span></div>'
      + '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px">';
    var healthItems = [
      { label: 'Product Completeness', value: h.product_completeness || 'LIMITED' },
      { label: 'Evidence Coverage', value: (h.evidence_coverage || 0) + '%' },
      { label: 'Patent Analysis', value: h.patent_analysis || 'LIMITED' },
      { label: 'Regulatory', value: h.regulatory_coverage || 'LIMITED' },
      { label: 'Jurisdictions', value: h.jurisdiction_coverage || 'LIMITED' }
    ];
    healthItems.forEach(function (item) {
      var color = healthColors[item.value] || 'var(--color-outline)';
      html += '<div style="padding:8px 14px;border:1px solid var(--color-outline-variant);border-radius:var(--radius-md);display:flex;align-items:center;gap:8px">'
        + '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + color + '"></span>'
        + '<span style="font-size:13px;color:var(--color-on-surface-variant)">' + item.label + '</span>'
        + '<span style="font-size:13px;font-weight:600;color:var(--color-on-surface)">' + item.value + '</span>'
        + '</div>';
    });
    html += '</div></div></div>';

    // Risk cards grouped by category
    if (rd.risks && rd.risks.length > 0) {
      var grouped = {};
      rd.risks.forEach(function (r) {
        if (!grouped[r.category]) grouped[r.category] = [];
        grouped[r.category].push(r);
      });

      Object.keys(grouped).forEach(function (cat) {
        var risks = grouped[cat];
        html += '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>' + icon(categoryIcons[cat] || 'warning', 18) + ' ' + (categoryLabels[cat] || cat) + '</h2>'
          + '<p>' + risks.length + ' risk' + (risks.length > 1 ? 's' : '') + '</p></div><div class="card-body">';

        risks.forEach(function (r) {
          var color = levelColors[r.level] || 'var(--color-outline)';
          html += '<div class="innovation-component-card" style="margin-bottom:12px;border-left:4px solid ' + color + '">'
            + '<div class="innovation-component-header"><div>'
            + '<div style="font-size:15px;font-weight:600;color:var(--color-on-surface)">' + escapeHtml(r.title) + '</div>'
            + '</div>'
            + '<span class="innovation-classification-badge" style="background:' + color + '15;color:' + color + '">' + (levelLabels[r.level] || r.level) + '</span>'
            + '</div>';
          if (r.description) html += '<div style="font-size:13px;color:var(--color-on-surface-variant);line-height:1.6;margin-bottom:8px">' + escapeHtml(r.description) + '</div>';
          if (r.affected_component_label) html += '<div style="margin-bottom:8px"><span class="label-caps" style="color:var(--color-on-surface-variant)">AFFECTED</span> ' + escapeHtml(r.affected_component_label) + '</div>';
          if (r.missing_information) html += '<div style="margin-bottom:8px;padding:8px 12px;background:var(--color-surface-container);border-radius:var(--radius-md);font-size:12px"><span class="label-caps" style="color:var(--color-on-surface-variant)">MISSING</span> ' + escapeHtml(r.missing_information) + '</div>';
          if (r.next_action) html += '<div style="margin-bottom:8px"><span class="label-caps" style="color:var(--color-on-surface-variant)">NEXT ACTION</span> ' + escapeHtml(r.next_action) + '</div>';
          if (r.source_phase) html += '<div style="font-size:12px;color:var(--color-on-surface-variant)">Source: ' + (phaseLabels[r.source_phase] || r.source_phase) + '</div>';

          // Evidence
          if (r.evidence && r.evidence.length > 0) {
            html += '<div style="margin-top:8px">';
            r.evidence.forEach(function (e, ci) {
              html += '<div class="knowledge-finding-evidence" style="cursor:pointer" onclick="window.AYUR.openEvidenceDrawer(\'' + (e.evidence_id || 'N/A') + '\')">'
                + '<div style="font-weight:600;color:var(--color-on-surface)"[' + (ci + 1) + '] ' + escapeHtml(e.evidence_source_name || e.evidence_authority || 'Source') + '</div>';
              if (e.evidence_jurisdiction) html += '<div style="font-size:12px;color:var(--color-on-surface-variant)">Jurisdiction: ' + escapeHtml(e.evidence_jurisdiction) + '</div>';
              if (e.evidence_reference) html += '<div style="font-size:12px;color:var(--color-on-surface-variant);font-family:JetBrains Mono,monospace">Ref: ' + escapeHtml(e.evidence_reference) + '</div>';
              html += '</div>';
            });
            html += '</div>';
          }

          html += '</div>';
        });
        html += '</div></div>';
      });
    }

    // Self-Extension panel
    if (rd.self_extensions && rd.self_extensions.length > 0) {
      html += '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>' + icon('extension', 18) + ' Self-Extension: Missing Information</h2>'
        + '<p>' + rd.self_extensions.length + ' item' + (rd.self_extensions.length > 1 ? 's' : '') + ' need attention</p></div><div class="card-body">';

      rd.self_extensions.forEach(function (ext) {
        var priColor = ext.priority === 'HIGH' ? 'var(--color-error)' : ext.priority === 'MEDIUM' ? '#d97706' : 'var(--color-secondary)';
        html += '<div class="innovation-component-card" style="margin-bottom:12px;border-left:4px solid ' + priColor + '>'
          + '<div class="innovation-component-header"><div>'
          + '<div style="font-size:14px;font-weight:600;color:var(--color-on-surface)">' + icon('warning', 16) + ' ' + escapeHtml(ext.title) + '</div>'
          + '</div>'
          + '<span class="innovation-classification-badge" style="background:' + priColor + '15;color:' + priColor + '">' + escapeHtml(ext.priority) + '</span>'
          + '</div>';
        if (ext.description) html += '<div style="font-size:13px;color:var(--color-on-surface-variant);line-height:1.6;margin-bottom:4px">' + escapeHtml(ext.description) + '</div>';
        if (ext.why_needed) html += '<div style="font-size:12px;color:var(--color-on-surface-variant);font-style:italic;margin-bottom:8px">Why: ' + escapeHtml(ext.why_needed) + '</div>';
        if (ext.suggested_action) html += '<div style="font-size:13px;color:var(--color-on-surface)">Action: ' + escapeHtml(ext.suggested_action) + '</div>';
        html += '</div>';
      });
      html += '</div></div>';
    }

    // Disclaimer
    html += '<div class="innovation-disclaimer">' + icon('warning', 18) + '<div><strong>Risk &amp; Self-Extension Engine.</strong> Risks are decision-support indicators only. They are NOT legal, medical, regulatory, or patentability conclusions.</div></div>';

    return html;
  }

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
  // Knowledge Graph View (Phase 15)
  // ----------------------------------------------------------------
  function renderKnowledgeGraph() {
    var g = state.knowledgeGraphData;
    if (!g) return '<div class="card"><div class="card-body"><p>No graph data available.</p></div></div>';

    var nodeTypes = g.summary ? g.summary.node_types : {};
    var totalNodes = g.summary ? g.summary.total_nodes : 0;
    var totalEdges = g.summary ? g.summary.total_edges : 0;

    var html = ''
      + '<div class="view-header"><button class="btn btn-ghost btn-sm" id="back-from-knowledge-graph">' + icon('arrow_back', 15) + ' Back to Case</button>'
      + '<div style="display:flex;gap:8px;margin-left:auto;align-items:center">'
      + '<input type="text" class="form-input" id="graph-search-input" placeholder="Search entities..." style="width:200px;padding:6px 10px;font-size:13px">'
      + '<button class="btn btn-primary btn-sm" id="graph-search-btn">' + icon('search', 14) + '</button>'
      + '<button class="btn btn-secondary btn-sm" id="graph-reset-btn">' + icon('restart_alt', 14) + ' Reset</button>'
      + '</div></div>'

      // Header
      + '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>' + icon('account_tree', 20) + ' Knowledge Graph</h2>'
      + '<p>Interactive visualization of ' + escapeHtml(g.product_name || '') + ' entity relationships</p></div><div class="card-body">'

      // Stats
      + '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px">'
      + '<div class="patent-stat-card"><div class="patent-stat-label">ENTITIES</div><div class="patent-stat-value">' + totalNodes + '</div></div>'
      + '<div class="patent-stat-card"><div class="patent-stat-label">RELATIONSHIPS</div><div class="patent-stat-value">' + totalEdges + '</div></div>';

    // Node type counts
    var typeLabels = {
      PRODUCT: 'Products', INGREDIENT: 'Ingredients', PLANT: 'Plants',
      FORMULATION: 'Formulations', PROCESS: 'Processes',
      TRADITIONAL_KNOWLEDGE: 'TK', PATENT: 'Patents',
      INNOVATION_COMPONENT: 'Innovation', IP_STRATEGY: 'IP Strategy',
      REGULATION: 'Regulations', JURISDICTION: 'Jurisdictions',
      EVIDENCE: 'Evidence', SOURCE: 'Sources', RISK: 'Risks',
      ALERT: 'Alerts', CASE_FINDING: 'Findings'
    };
    Object.keys(nodeTypes).forEach(function (t) {
      if (nodeTypes[t] > 0) {
        html += '<div class="patent-stat-card"><div class="patent-stat-label">' + (typeLabels[t] || t).toUpperCase() + '</div><div class="patent-stat-value">' + nodeTypes[t] + '</div></div>';
      }
    });
    html += '</div>';

    // Filters
    html += '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px">'
      + '<button class="btn btn-ghost btn-xs graph-filter-btn active" data-filter="ALL">All</button>';
    var filterTypes = ['PRODUCT', 'INGREDIENT', 'PLANT', 'PATENT', 'REGULATION', 'JURISDICTION', 'TRADITIONAL_KNOWLEDGE', 'INNOVATION_COMPONENT', 'IP_STRATEGY', 'EVIDENCE', 'RISK', 'ALERT', 'SOURCE', 'CASE_FINDING'];
    filterTypes.forEach(function (t) {
      if (nodeTypes[t] && nodeTypes[t] > 0) {
        html += '<button class="btn btn-ghost btn-xs graph-filter-btn" data-filter="' + t + '">' + (typeLabels[t] || t) + '</button>';
      }
    });
    html += '</div>';

    // Graph container
    html += '<div id="knowledge-graph-container" style="width:100%;height:500px;border:1px solid var(--color-outline-variant);border-radius:var(--radius-md);overflow:hidden;background:var(--color-surface-container-low);position:relative"></div>';

    // Node detail panel
    html += '<div id="graph-node-detail" style="display:none;margin-top:16px;padding:16px;border:1px solid var(--color-outline-variant);border-radius:var(--radius-md);background:var(--color-surface)"></div>';

    html += '</div></div>';

    // Legend
    html += '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>' + icon('palette', 18) + ' Legend</h2></div><div class="card-body">'
      + '<div style="display:flex;gap:12px;flex-wrap:wrap">';
    var legendItems = [
      { type: 'PRODUCT', color: '#2d4a3e', label: 'Product' },
      { type: 'INGREDIENT', color: '#4caf50', label: 'Ingredient' },
      { type: 'PLANT', color: '#66bb6a', label: 'Plant' },
      { type: 'PATENT', color: '#f44336', label: 'Patent' },
      { type: 'REGULATION', color: '#2196f3', label: 'Regulation' },
      { type: 'JURISDICTION', color: '#1565c0', label: 'Jurisdiction' },
      { type: 'TRADITIONAL_KNOWLEDGE', color: '#ff9800', label: 'Traditional Knowledge' },
      { type: 'INNOVATION_COMPONENT', color: '#9c27b0', label: 'Innovation' },
      { type: 'IP_STRATEGY', color: '#7b1fa2', label: 'IP Strategy' },
      { type: 'EVIDENCE', color: '#607d8b', label: 'Evidence' },
      { type: 'SOURCE', color: '#455a64', label: 'Source' },
      { type: 'RISK', color: '#ff5722', label: 'Risk' },
      { type: 'ALERT', color: '#ff9800', label: 'Alert' },
      { type: 'CASE_FINDING', color: '#795548', label: 'Finding' },
    ];
    legendItems.forEach(function (item) {
      if (nodeTypes[item.type] && nodeTypes[item.type] > 0) {
        html += '<div style="display:flex;align-items:center;gap:6px;font-size:12px">'
          + '<span style="width:12px;height:12px;border-radius:50%;background:' + item.color + '"></span>'
          + '<span>' + item.label + ' (' + nodeTypes[item.type] + ')</span></div>';
      }
    });
    html += '</div></div></div>';

    // Disclaimer
    html += '<div class="innovation-disclaimer">' + icon('warning', 18) + '<div><strong>Knowledge Graph.</strong> Relationships are derived from stored database records. No fabricated relationships are shown.</div></div>';

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
  // Graph visualization helpers (called after render)
  // ----------------------------------------------------------------
  function initGraphVisualization() {
    var container = document.getElementById('knowledge-graph-container');
    if (!container || !state.knowledgeGraphData) return;
    if (typeof d3 === 'undefined') { container.innerHTML = '<div style="padding:20px;text-align:center;color:var(--color-on-surface-variant)">D3.js not loaded</div>'; return; }

    var g = state.knowledgeGraphData;
    var width = container.clientWidth;
    var height = container.clientHeight;

    var svg = d3.select(container).append('svg')
      .attr('width', width).attr('height', height)
      .attr('viewBox', [0, 0, width, height]);

    // Add zoom
    var g_group = svg.append('g');
    var zoom = d3.zoom()
      .scaleExtent([0.2, 5])
      .on('zoom', function (event) { g_group.attr('transform', event.transform); });
    svg.call(zoom);

    // Arrow markers
    svg.append('defs').selectAll('marker')
      .data(['arrow']).enter().append('marker')
      .attr('id', 'arrow').attr('viewBox', '0 -5 10 10')
      .attr('refX', 20).attr('refY', 0)
      .attr('markerWidth', 6).attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path').attr('d', 'M0,-5L10,0L0,5').attr('fill', '#999');

    // Prepare data
    var nodeMap = {};
    g.nodes.forEach(function (n) { nodeMap[n.id] = n; });
    var links = g.edges.map(function (e) {
      return {
        source: nodeMap[e.source] || e.source,
        target: nodeMap[e.target] || e.target,
        relationship: e.relationship,
        metadata: e.metadata,
      };
    }).filter(function (l) { return l.source && l.target && typeof l.source === 'object' && typeof l.target === 'object'; });

    // Force simulation
    var simulation = d3.forceSimulation(g.nodes)
      .force('link', d3.forceLink(links).id(function (d) { return d.id; }).distance(120))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(30));

    window._graphSimulation = simulation;
    window._graphSvg = svg;
    window._graphNodes = g.nodes;
    window._graphLinks = links;

    // Links
    var link = g_group.append('g').selectAll('line')
      .data(links).enter().append('line')
      .attr('stroke', '#999').attr('stroke-opacity', 0.4).attr('stroke-width', 1)
      .attr('marker-end', 'url(#arrow)');

    // Link labels
    var linkLabel = g_group.append('g').selectAll('text')
      .data(links).enter().append('text')
      .attr('font-size', '8px').attr('fill', '#666').attr('text-anchor', 'middle')
      .text(function (d) { return d.relationship.replace(/_/g, ' '); });

    // Nodes
    var node = g_group.append('g').selectAll('g')
      .data(g.nodes).enter().append('g')
      .attr('class', 'graph-node')
      .style('cursor', 'pointer')
      .call(d3.drag()
        .on('start', function (event, d) {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x; d.fy = d.y;
        })
        .on('drag', function (event, d) { d.fx = event.x; d.fy = event.y; })
        .on('end', function (event, d) {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null; d.fy = null;
        })
      );

    // Node circles
    node.append('circle')
      .attr('r', function (d) { return d.type === 'PRODUCT' ? 18 : 10; })
      .attr('fill', function (d) { return d.color || '#757575'; })
      .attr('stroke', '#fff').attr('stroke-width', 2);

    // Node labels
    node.append('text')
      .attr('dy', function (d) { return d.type === 'PRODUCT' ? -24 : -16; })
      .attr('text-anchor', 'middle')
      .attr('font-size', function (d) { return d.type === 'PRODUCT' ? '11px' : '9px'; })
      .attr('font-weight', function (d) { return d.type === 'PRODUCT' ? '700' : '500'; })
      .attr('fill', '#333')
      .text(function (d) { var lbl = d.label || ''; return lbl.length > 25 ? lbl.substring(0, 22) + '...' : lbl; });

    // Node click
    node.on('click', function (event, d) {
      event.stopPropagation();
      showNodeDetail(d);
    });

    // Tick
    simulation.on('tick', function () {
      link
        .attr('x1', function (d) { return d.source.x; })
        .attr('y1', function (d) { return d.source.y; })
        .attr('x2', function (d) { return d.target.x; })
        .attr('y2', function (d) { return d.target.y; });
      linkLabel
        .attr('x', function (d) { return (d.source.x + d.target.x) / 2; })
        .attr('y', function (d) { return (d.source.y + d.target.y) / 2; });
      node.attr('transform', function (d) { return 'translate(' + d.x + ',' + d.y + ')'; });
    });

    // Click on background to deselect
    svg.on('click', function () {
      document.getElementById('graph-node-detail').style.display = 'none';
    });
  }

  function showNodeDetail(d) {
    var panel = document.getElementById('graph-node-detail');
    if (!panel) return;

    var meta = d.metadata || {};
    var html = '<div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">'
      + '<span style="width:16px;height:16px;border-radius:50%;background:' + (d.color || '#757575') + '"></span>'
      + '<div><div style="font-size:16px;font-weight:600">' + escapeHtml(d.label) + '</div>'
      + '<div style="font-size:12px;color:var(--color-on-surface-variant)">' + escapeHtml(d.type) + '</div></div></div>';

    // Metadata
    var metaKeys = Object.keys(meta).filter(function (k) { return meta[k] !== null && meta[k] !== undefined && meta[k] !== ''; });
    if (metaKeys.length > 0) {
      html += '<div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(200px, 1fr));gap:8px">';
      metaKeys.forEach(function (k) {
        var val = meta[k];
        if (typeof val === 'object') val = JSON.stringify(val);
        html += '<div><span class="label-caps" style="color:var(--color-on-surface-variant);font-size:10px">' + escapeHtml(k.replace(/_/g, ' ')) + '</span>'
          + '<div style="font-size:13px;margin-top:2px">' + escapeHtml(String(val).substring(0, 100)) + '</div></div>';
      });
      html += '</div>';
    }

    // Find connected edges
    if (window._graphLinks) {
      var connected = window._graphLinks.filter(function (l) {
        return (l.source && l.source.id === d.id) || (l.target && l.target.id === d.id);
      });
      if (connected.length > 0) {
        html += '<div style="margin-top:12px"><span class="label-caps" style="color:var(--color-on-surface-variant);font-size:10px">CONNECTIONS (' + connected.length + ')</span></div>';
        connected.slice(0, 10).forEach(function (l) {
          var other = (l.source.id === d.id) ? l.target : l.source;
          var direction = (l.source.id === d.id) ? '->' : '<-';
          html += '<div style="font-size:12px;padding:4px 0;border-bottom:1px solid var(--color-outline-variant)">'
            + escapeHtml(l.relationship.replace(/_/g, ' ')) + ' ' + direction + ' '
            + '<strong>' + escapeHtml(other.label || other.id) + '</strong>'
            + ' <span style="color:var(--color-on-surface-variant)">(' + escapeHtml(other.type) + ')</span></div>';
        });
      }
    }

    panel.innerHTML = html;
    panel.style.display = 'block';
  }

  // Graph filter
  function filterGraphNodes(type) {
    if (!window._graphSvg) return;
    window._graphSvg.selectAll('.graph-node').style('opacity', function (d) {
      if (type === 'ALL') return 1;
      return d.type === type ? 1 : 0.15;
    });
    window._graphSvg.selectAll('line').style('opacity', function (d) {
      if (type === 'ALL') return 0.4;
      var srcType = d.source ? d.source.type : '';
      var tgtType = d.target ? d.target.type : '';
      return (srcType === type || tgtType === type) ? 0.6 : 0.05;
    });
  }

  // Graph highlight (for search)
  function highlightGraphNodes(nodeIds) {
    if (!window._graphSvg) return;
    var idSet = {};
    nodeIds.forEach(function (id) { idSet[id] = true; });
    window._graphSvg.selectAll('.graph-node').style('opacity', function (d) {
      return idSet[d.id] ? 1 : 0.15;
    });
  }

  function resetGraphHighlight() {
    if (!window._graphSvg) return;
    window._graphSvg.selectAll('.graph-node').style('opacity', 1);
    window._graphSvg.selectAll('line').style('opacity', 0.4);
  }


  // ----------------------------------------------------------------
  // Knowledge Hub View (Unified Traditional Knowledge, Plants, Graph, Router)
  // ----------------------------------------------------------------
  function renderKnowledgeHub() {
    var activeTab = state.knowledgeTab || "literature";

    var tabs = [
      { id: "literature", label: "Literature & Traditional Texts", icon: "menu_book" },
      { id: "plants", label: "Plant Discovery & ID", icon: "eco" },
      { id: "graph", label: "Interactive Knowledge Graph", icon: "account_tree" },
      { id: "router", label: "AI Source Router", icon: "database" }
    ];

    var tabNavHtml = '<div class="knowledge-segmented-nav">';
    tabs.forEach(function (t) {
      var isAct = activeTab === t.id;
      tabNavHtml += '<button class="knowledge-tab-btn ' + (isAct ? "active" : "") + '" data-ktab="' + t.id + '">'
        + icon(t.icon, 18) + ' ' + escapeHtml(t.label)
        + '</button>';
    });
    tabNavHtml += '</div>';

    var tabContent = "";
    if (activeTab === "literature") {
      tabContent = renderKnowledgeEngine();
    } else if (activeTab === "plants") {
      tabContent = renderPlantDiscovery();
    } else if (activeTab === "graph") {
      if (!state.currentCase && (!state.knowledgeGraphData || !state.knowledgeGraphData.nodes)) {
        tabContent = '<div class="card"><div class="card-body" style="text-align:center;padding:40px;">'
          + '<div class="empty-icon" style="font-size:36px;color:#2D4A3E;margin-bottom:12px;">' + icon("account_tree", 36) + '</div>'
          + '<h3>Interactive Knowledge Graph</h3>'
          + '<p style="color:var(--text-secondary);max-width:500px;margin:8px auto 16px;">The Knowledge Graph visualizes all interconnected entities for your product case. Select a product case to explore its entity network.</p>'
          + '<button class="btn btn-primary" id="kg-select-case-btn">' + icon("folder_open", 16) + ' Select Product Case</button>'
          + '</div></div>';
      } else {
        tabContent = renderKnowledgeGraph();
      }
    } else if (activeTab === "router") {
      tabContent = renderSourceRouter();
    }

    return '<div class="knowledge-hub-container">'
      + '<div class="knowledge-hub-head">'
      + '<h1 class="knowledge-hub-title">Knowledge Discovery Hub</h1>'
      + '<p class="knowledge-hub-sub">Explore classical Ayurvedic texts, identify unknown botanicals, investigate relationship graphs, and route intelligence queries.</p>'
      + '</div>'
      + tabNavHtml
      + '<div id="knowledge-hub-tab-content">' + tabContent + '</div>'
      + '</div>';
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
    var topCasePretitle = document.getElementById("topbar-case-pretitle");
    var topCaseName = document.getElementById("topbar-case-name");
    var topCaseStage = document.getElementById("topbar-case-stage");

    var activeName = (state.view === "passport-wizard" && state.passportData && state.passportData.name && state.passportData.name.trim()) 
      ? state.passportData.name.trim() 
      : (state.currentCase && state.currentCase.name && state.currentCase.name.trim() 
        ? state.currentCase.name.trim() 
        : "");

    if (topCaseName && topCaseStage) {
      if (activeName) {
        if (topCasePretitle) {
          topCasePretitle.textContent = "PRODUCT";
          topCasePretitle.style.display = "block";
        }
        topCaseName.textContent = activeName;
        topCaseStage.textContent = "Ongoing";
        topCaseStage.style.color = "#34d399";
      } else {
        if (topCasePretitle) {
          topCasePretitle.style.display = "none";
        }
        topCaseName.textContent = "No Active Case";
        topCaseStage.textContent = "Click to select";
        topCaseStage.style.color = "var(--text-secondary)";
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

        if (view === "dashboard" || view === "product-cases") {
          loadCases();
        }
        if (view === "knowledge-hub" && !state.knowledgeSources.length) {
          loadKnowledgeSources();
        }
        render();
      });
    });

    // Topbar & Sidebar New Product Buttons
    var sbNewBtn = document.getElementById("sidebar-new-case-btn");
    if (sbNewBtn) sbNewBtn.addEventListener("click", createCase);

    var tbNewBtn = document.getElementById("topbar-new-case-btn");
    if (tbNewBtn) tbNewBtn.addEventListener("click", createCase);

    var tbSettingsBtn = document.getElementById("topbar-settings-btn");
    if (tbSettingsBtn) tbSettingsBtn.addEventListener("click", function () { state.view = "settings"; render(); });

    // Topbar Case Context Switcher
    var tbContext = document.getElementById("topbar-case-context");
    if (tbContext) tbContext.addEventListener("click", openCaseSwitcherModal);

    // Topbar Search
    var tbSearch = document.getElementById("topbar-search-input");
    if (tbSearch) {
      tbSearch.addEventListener("input", function () {
        var q = this.value.toLowerCase().trim();
        var cards = document.querySelectorAll(".case-card");
        cards.forEach(function (c) {
          var text = c.textContent.toLowerCase();
          c.style.display = (q === "" || text.indexOf(q) !== -1) ? "" : "none";
        });
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
  function renderSettings() {
    var html = '<div class="card" style="margin-bottom:20px"><div class="card-head"><h2>' + icon('settings', 20) + ' Settings</h2>'
      + '<p>System configuration and security status</p></div><div class="card-body">'

      // Security status
      + '<div id="settings-security"><div style="text-align:center;padding:16px;color:var(--color-on-surface-variant)">Loading security status...</div></div>'

      // App info
      + '<div style="margin-top:24px;padding:16px;border:1px solid var(--color-outline-variant);border-radius:var(--radius-md)">'
      + '<div style="font-weight:600;margin-bottom:12px">' + icon('info', 16) + ' Application Info</div>'
      + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:13px">'
      + '<div><span class="label-caps" style="color:var(--color-on-surface-variant)">Version</span><div>0.1.0</div></div>'
      + '<div><span class="label-caps" style="color:var(--color-on-surface-variant)">Phases</span><div>21 Complete</div></div>'
      + '<div><span class="label-caps" style="color:var(--color-on-surface-variant)">Architecture</span><div>FastAPI + SQLite</div></div>'
      + '<div><span class="label-caps" style="color:var(--color-on-surface-variant)">Frontend</span><div>Vanilla JS SPA</div></div>'
      + '</div></div>'

      // Legal disclaimer
      + '<div style="margin-top:16px;padding:12px 16px;border:1px solid var(--color-error);border-radius:var(--radius-md);background:rgba(255,87,34,0.03);font-size:12px;color:var(--color-on-surface-variant);line-height:1.6">'
      + icon('warning', 14) + ' <strong>Disclaimer:</strong> AYUR-INTEL is a decision-support tool. AI analysis is advisory only. Always consult qualified legal, regulatory, and medical professionals for product decisions.'
      + '</div>'

      + '</div></div>';

    // Load security status async
    setTimeout(async function () {
      try {
        var data = await api('/api/security/status');
        var el = document.getElementById('settings-security');
        if (!el) return;
        var sf = data.security_features || {};
        var auth = data.authentication || {};
        var html2 = '<div style="padding:16px;border:1px solid var(--color-outline-variant);border-radius:var(--radius-md);margin-bottom:16px">'
          + '<div style="font-weight:600;margin-bottom:12px">' + icon('shield', 16) + ' Security Status</div>'
          + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:13px">'
          + '<div><span class="label-caps" style="color:var(--color-on-surface-variant)">Authentication</span><div>' + escapeHtml(auth.mode || 'demo') + '</div></div>'
          + '<div><span class="label-caps" style="color:var(--color-on-surface-variant)">Session TTL</span><div>' + (auth.session_ttl_seconds || 86400) + 's</div></div>'
          + '</div>'
          + '<div style="margin-top:12px;display:flex;flex-wrap:wrap;gap:6px">';
        Object.keys(sf).forEach(function (key) {
          var color = sf[key] ? 'var(--color-secondary)' : 'var(--color-error)';
          var label = key.replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
          html2 += '<span style="font-size:11px;padding:3px 8px;border:1px solid ' + color + '30;border-radius:var(--radius-full);color:' + color + '">' + (sf[key] ? icon('check', 10) : icon('close', 10)) + ' ' + label + '</span>';
        });
        html2 += '</div></div>';
        el.innerHTML = html2;
      } catch (e) {
        var el2 = document.getElementById('settings-security');
        if (el2) el2.innerHTML = '';
      }
    }, 100);

    return html;
  }

  // ----------------------------------------------------------------
  // Event Bindings
  // ----------------------------------------------------------------
  function bindEvents() {
    // Case Switch Button in Case Header
    var caseSwitchBtn = document.getElementById("case-switch-btn");
    if (caseSwitchBtn) caseSwitchBtn.addEventListener("click", openCaseSwitcherModal);

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
      cardInnovation.addEventListener("click", async function () {
        if (!state.currentCase) return;
        state.loading = true; render();
        try {
          var data = await api("/api/cases/" + state.currentCase.id + "/innovation-analysis", { method: "POST" });
          state.innovationAnalysis = data;
          state.view = "innovation-analysis";
        } catch (e) { state.error = "Failed to generate innovation analysis."; }
        state.loading = false; render();
      });
    }

    var cardPatent = document.getElementById("card-intel-patent");
    if (cardPatent) {
      cardPatent.addEventListener("click", function () {
        state.view = "patent-intelligence";
        render();
      });
    }

    var cardIp = document.getElementById("card-intel-ip");
    if (cardIp) {
      cardIp.addEventListener("click", async function () {
        if (!state.currentCase) return;
        state.loading = true; render();
        try {
          var data = await api("/api/cases/" + state.currentCase.id + "/ip-strategy", { method: "POST" });
          state.ipStrategy = data;
          state.view = "ip-strategy";
        } catch (e) { state.error = "Failed to generate IP strategy."; }
        state.loading = false; render();
      });
    }

    var cardRegulatory = document.getElementById("card-intel-regulatory");
    if (cardRegulatory) {
      cardRegulatory.addEventListener("click", function () {
        state.view = "regulatory-select";
        render();
      });
    }

    var cardRisk = document.getElementById("card-intel-risk");
    if (cardRisk) {
      cardRisk.addEventListener("click", async function () {
        if (!state.currentCase) return;
        state.loading = true; render();
        try {
          var data = await api("/api/cases/" + state.currentCase.id + "/risk-analysis", { method: "POST" });
          state.riskData = data;
          state.view = "risk";
        } catch (e) { state.error = "Failed to generate risk analysis."; }
        state.loading = false; render();
      });
    }

    var cardEvidence = document.getElementById("card-intel-evidence");
    if (cardEvidence) {
      cardEvidence.addEventListener("click", async function () {
        if (!state.currentCase) return;
        state.loading = true; render();
        try {
          var data = await api("/api/cases/" + state.currentCase.id + "/evidence");
          state.evidenceData = data;
          state.view = "evidence";
        } catch (e) { state.error = "Failed to load evidence data."; }
        state.loading = false; render();
      });
    }

    var cardDecision = document.getElementById("card-intel-decision");
    if (cardDecision) {
      cardDecision.addEventListener("click", async function () {
        if (!state.currentCase) return;
        state.loading = true; render();
        try {
          var data = await api("/api/cases/" + state.currentCase.id + "/decision-dashboard");
          state.dashboardData = data;
          state.view = "dashboard-detail";
        } catch (e) { state.error = "Failed to load decision dashboard."; }
        state.loading = false; render();
      });
    }

    var cardGraph = document.getElementById("card-intel-graph");
    if (cardGraph) {
      cardGraph.addEventListener("click", async function () {
        if (!state.currentCase) return;
        state.loading = true; render();
        try {
          var data = await api("/api/cases/" + state.currentCase.id + "/knowledge-graph");
          state.knowledgeGraphData = data;
          state.view = "knowledge-graph";
        } catch (e) { state.error = "Failed to load knowledge graph."; }
        state.loading = false; render();
      });
    }

    var cardMonitoring = document.getElementById("card-intel-monitoring");
    if (cardMonitoring) {
      cardMonitoring.addEventListener("click", async function () {
        if (!state.currentCase) return;
        state.loading = true; render();
        try {
          var data = await api("/api/cases/" + state.currentCase.id + "/monitoring");
          state.monitoringData = data;
          state.view = "monitoring-center";
        } catch (e) { state.error = "Failed to load monitoring data."; }
        state.loading = false; render();
      });
    }

    var cardRouter = document.getElementById("card-intel-router");
    if (cardRouter) {
      cardRouter.addEventListener("click", async function () {
        state.loading = true; render();
        try {
          var data = await api("/api/source-router/sources");
          state.sourceRouterData = { sources: data, routingResult: null, question: '' };
          state.view = "source-router";
        } catch (e) { state.error = "Failed to load source router."; }
        state.loading = false; render();
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

    // Explore demo
    var demoBtn = document.getElementById("explore-demo-btn");
    if (demoBtn) demoBtn.addEventListener("click", function () { loadCases(); state.view = "product-cases"; render(); });

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
      innovationBtn.addEventListener("click", async function () {
        if (!state.currentCase) return;
        state.loading = true; render();
        try {
          var data = await api("/api/cases/" + state.currentCase.id + "/innovation-analysis", { method: "POST" });
          state.innovationAnalysis = data;
          state.view = "innovation-analysis";
        } catch (e) { state.error = "Failed to generate innovation analysis."; }
        state.loading = false; render();
      });
    }

    var patentBtn = document.getElementById("open-patent-btn");
    if (patentBtn) {
      patentBtn.addEventListener("click", function () { state.view = "patent-intelligence"; render(); });
    }

    var ipStrategyBtn = document.getElementById("open-ip-strategy-btn");
    if (ipStrategyBtn) {
      ipStrategyBtn.addEventListener("click", async function () {
        if (!state.currentCase) return;
        state.loading = true; render();
        try {
          var data = await api("/api/cases/" + state.currentCase.id + "/ip-strategy", { method: "POST" });
          state.ipStrategy = data;
          state.view = "ip-strategy";
        } catch (e) { state.error = "Failed to generate IP strategy."; }
        state.loading = false; render();
      });
    }

    var regulatoryBtn = document.getElementById("open-regulatory-btn");
    if (regulatoryBtn) {
      regulatoryBtn.addEventListener("click", function () { state.view = "regulatory-select"; render(); });
    }

    // --- Evidence & Citation (Phase 11) ---
    var evidenceBtn = document.getElementById("open-evidence-btn");
    if (evidenceBtn) {
      evidenceBtn.addEventListener("click", async function () {
        if (!state.currentCase) return;
        state.loading = true; render();
        try {
          var data = await api("/api/cases/" + state.currentCase.id + "/evidence");
          state.evidenceData = data;
          state.view = "evidence";
        } catch (e) { state.error = "Failed to load evidence data."; }
        state.loading = false; render();
      });
    }

    var backFromEvidence = document.getElementById("back-from-evidence");
    if (backFromEvidence) {
      backFromEvidence.addEventListener("click", function () {
        state.view = "case-detail";
        state.evidenceData = null;
        render();
      });
    }

    // --- Risk + Self-Extension (Phase 12) ---
    var riskBtn = document.getElementById("open-risk-btn");
    if (riskBtn) {
      riskBtn.addEventListener("click", async function () {
        if (!state.currentCase) return;
        state.loading = true; render();
        try {
          var data = await api("/api/cases/" + state.currentCase.id + "/risk-analysis", { method: "POST" });
          state.riskData = data;
          state.view = "risk";
        } catch (e) { state.error = "Failed to generate risk analysis."; }
        state.loading = false; render();
      });
    }

    var backFromRisk = document.getElementById("back-from-risk");
    if (backFromRisk) {
      backFromRisk.addEventListener("click", function () {
        state.view = "case-detail";
        state.riskData = null;
        render();
      });
    }

    // --- Decision Dashboard (Phase 13) ---
    var dashboardBtn = document.getElementById("open-dashboard-btn");
    if (dashboardBtn) {
      dashboardBtn.addEventListener("click", async function () {
        if (!state.currentCase) return;
        state.loading = true; render();
        try {
          var data = await api("/api/cases/" + state.currentCase.id + "/decision-dashboard");
          state.dashboardData = data;
          state.view = "dashboard-detail";
        } catch (e) { state.error = "Failed to load decision dashboard."; }
        state.loading = false; render();
      });
    }

    var backFromDashboard = document.getElementById("back-from-dashboard");
    if (backFromDashboard) {
      backFromDashboard.addEventListener("click", function () {
        state.view = "case-detail";
        state.dashboardData = null;
        render();
      });
    }

    // --- Continuous Monitoring (Phase 14) ---
    var monitoringBtn = document.getElementById("open-monitoring-btn");
    if (monitoringBtn) {
      monitoringBtn.addEventListener("click", async function () {
        if (!state.currentCase) return;
        state.loading = true; render();
        try {
          var data = await api("/api/cases/" + state.currentCase.id + "/monitoring");
          state.monitoringData = data;
          state.view = "monitoring-center";
        } catch (e) { state.error = "Failed to load monitoring data."; }
        state.loading = false; render();
      });
    }

    var backFromMonitoring = document.getElementById("back-from-monitoring");
    if (backFromMonitoring) {
      backFromMonitoring.addEventListener("click", function () {
        state.view = "case-detail";
        state.monitoringData = null;
        render();
      });
    }

    var checkNowBtn = document.getElementById("monitoring-check-now");
    if (checkNowBtn) {
      checkNowBtn.addEventListener("click", async function () {
        if (!state.currentCase) return;
        state.loading = true; render();
        try {
          var runResult = await api("/api/cases/" + state.currentCase.id + "/monitoring/run", { method: "POST" });
          toast('Monitoring check complete. ' + (runResult.alerts_created || 0) + ' alerts created.', 'success');
          var data = await api("/api/cases/" + state.currentCase.id + "/monitoring");
          state.monitoringData = data;
        } catch (e) { state.error = "Monitoring check failed."; }
        state.loading = false; render();
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
        state.loading = false; render();
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
          render();
        } catch (e) { state.error = "Failed to update alert."; }
      });
    });

    // --- Knowledge Graph (Phase 15) ---
    var knowledgeGraphBtn = document.getElementById("open-knowledge-graph-btn");
    if (knowledgeGraphBtn) {
      knowledgeGraphBtn.addEventListener("click", async function () {
        if (!state.currentCase) return;
        state.loading = true; render();
        try {
          var data = await api("/api/cases/" + state.currentCase.id + "/knowledge-graph");
          state.knowledgeGraphData = data;
          state.view = "knowledge-graph";
        } catch (e) { state.error = "Failed to load knowledge graph."; }
        state.loading = false; render();
      });
    }

    var backFromKnowledgeGraph = document.getElementById("back-from-knowledge-graph");
    if (backFromKnowledgeGraph) {
      backFromKnowledgeGraph.addEventListener("click", function () {
        state.view = "case-detail";
        state.knowledgeGraphData = null;
        render();
      });
    }

    // Graph search
    var graphSearchBtn = document.getElementById("graph-search-btn");
    if (graphSearchBtn) {
      graphSearchBtn.addEventListener("click", async function () {
        var q = document.getElementById("graph-search-input");
        if (!q || !q.value.trim() || !state.currentCase) return;
        state.loading = true; render();
        try {
          var data = await api("/api/cases/" + state.currentCase.id + "/knowledge-graph/search?q=" + encodeURIComponent(q.value.trim()));
          if (data.matching_nodes && data.matching_nodes.length > 0) {
            toast('Found ' + data.total_matches + ' matching node(s)', 'success');
            // Highlight matching nodes
            highlightGraphNodes(data.matching_nodes.map(function(n) { return n.id; }));
          } else {
            toast('No matches found', 'info');
          }
        } catch (e) { state.error = "Search failed."; }
        state.loading = false; render();
      });
    }

    // Graph filter buttons
    document.querySelectorAll(".graph-filter-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var filterType = btn.getAttribute("data-filter");
        filterGraphNodes(filterType);
        // Toggle active state
        document.querySelectorAll(".graph-filter-btn").forEach(function(b) { b.classList.remove("active"); });
        btn.classList.add("active");
      });
    });

    // Graph reset
    var graphResetBtn = document.getElementById("graph-reset-btn");
    if (graphResetBtn) {
      graphResetBtn.addEventListener("click", function () {
        if (window._graphSimulation) {
          window._graphSimulation.alpha(0.3).restart();
        }
        document.querySelectorAll(".graph-filter-btn").forEach(function(b) { b.classList.remove("active"); });
        var allBtn = document.querySelector(".graph-filter-btn[data-filter='ALL']");
        if (allBtn) allBtn.classList.add("active");
        resetGraphHighlight();
      });
    }

    // --- Source Router (Phase 16) ---
    var sourceRouterBtn = document.getElementById("open-source-router-btn");
    if (sourceRouterBtn) {
      sourceRouterBtn.addEventListener("click", async function () {
        if (!state.currentCase) return;
        state.loading = true; render();
        try {
          var data = await api("/api/source-router/sources");
          state.sourceRouterData = { sources: data, routingResult: null, question: '' };
          state.view = "source-router";
        } catch (e) { state.error = "Failed to load source router."; }
        state.loading = false; render();
      });
    }

    var backFromSourceRouter = document.getElementById("back-from-source-router");
    if (backFromSourceRouter) {
      backFromSourceRouter.addEventListener("click", function () {
        state.view = "case-detail";
        state.sourceRouterData = null;
        render();
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
    if (backInnovation) backInnovation.addEventListener("click", function () { state.view = "case-detail"; state.innovationAnalysis = null; render(); });

    var backPatent = document.getElementById("back-from-patent");
    if (backPatent) backPatent.addEventListener("click", function () { state.view = "case-detail"; state.patentSearchResults = null; state.patentSavedResults = null; render(); });

    var backDeepAnalysis = document.getElementById("back-from-deep-analysis");
    if (backDeepAnalysis) backDeepAnalysis.addEventListener("click", function () { state.view = "patent-intelligence"; state.patentDeepAnalysis = null; render(); });

    var backIP = document.getElementById("back-from-ip-strategy");
    if (backIP) backIP.addEventListener("click", function () { state.view = "case-detail"; state.ipStrategy = null; render(); });

    var backFromRegSelect = document.getElementById("back-from-regulatory-select");
    if (backFromRegSelect) backFromRegSelect.addEventListener("click", function () { state.view = "case-detail"; render(); });

    var backFromReg = document.getElementById("back-from-regulatory");
    if (backFromReg) backFromReg.addEventListener("click", function () { state.view = "case-detail"; state.regulatoryProfile = null; render(); });

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
  // Data Loaders
  // ----------------------------------------------------------------
  async function loadCases() {
    try {
      var data = await api("/api/cases");
      state.cases = data.cases || [];
    } catch (e) { state.error = "Failed to load cases."; }
  }

  async function loadCase(id) {
    try {
      var data = await api("/api/cases/" + id);
      state.currentCase = data;
      state.view = "case-detail";
      state.error = null;
    } catch (e) { state.error = "Failed to load case."; }
    render();
  }

  function createCase() {
    if (window.AYUR && window.AYUR.initPassportData) {
      window.AYUR.initPassportData(null);
    }
    state.currentCase = null;
    state.view = "passport-wizard";
    render();
  }

  // ----------------------------------------------------------------
  // Init
  // ----------------------------------------------------------------
  async function init() {
    bindNavigation();
    await loadCases();
    render();
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
    updateTopbarUI: updateTopbarUI,
    openEvidenceDrawer: window.AYUR.openEvidenceDrawer
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
    var modals = document.querySelectorAll(".modal-overlay.open, .modal-backdrop.open, #case-switcher-modal");
    modals.forEach(function(m) {
      m.classList.remove("open");
      if (m.style.display !== "none") m.style.display = "none";
    });
  }
});
