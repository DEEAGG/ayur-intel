/* AYUR-INTEL — Knowledge Engine Views (Phase 3)
   Research workspace for Traditional Knowledge and evidence-backed findings.
   This file is loaded after app.js and extends it with knowledge functions.
   Must be loaded within the same IIFE scope (concatenated before app.js closes). */

  // ----------------------------------------------------------------
  // Knowledge Engine — API calls
  // ----------------------------------------------------------------

  async function searchKnowledge(params) {
    state.loading = true;
    state.error = null;
    render();
    try {
      var data = await api("POST", "/knowledge/search", params);
      state.knowledgeResults = data;
    } catch (e) {
      state.error = e.message;
    }
    state.loading = false;
    render();
  }

  async function saveKnowledgeFinding(findingData, caseId) {
    var payload = Object.assign({}, findingData, { product_case_id: caseId });
    return await api("POST", "/knowledge/findings/save", payload);
  }

  async function loadKnowledgeSources() {
    try {
      var data = await api("GET", "/knowledge/sources");
      state.knowledgeSources = data.sources || [];
    } catch (e) {
      state.knowledgeSources = [];
    }
  }

  // ----------------------------------------------------------------
  // Knowledge Engine — Main view
  // ----------------------------------------------------------------

  function renderKnowledgeEngine() {
    var resultsHtml = "";
    if (state.knowledgeResults) {
      resultsHtml = renderKnowledgeResults();
    } else if (state.loading) {
      resultsHtml = '<div class="card" style="margin-top:20px"><div class="card-body" style="text-align:center;padding:40px">'
        + '<div class="skeleton" style="height:20px;width:200px;margin:0 auto 12px"></div>'
        + '<div class="skeleton" style="height:100px;width:100%;margin-bottom:12px"></div>'
        + '<p style="color:var(--text-secondary);margin-top:12px">Searching sources...</p>'
        + '</div></div>';
    }

    var sourcesHtml = "";
    if (state.knowledgeSources.length > 0) {
      sourcesHtml = '<div class="card" style="margin-top:20px"><div class="card-head"><h2>Registered Sources</h2></div><div class="card-body">';
      state.knowledgeSources.forEach(function (s) {
        var statusClass = s.is_configured ? "source-status-active" : "source-status-inactive";
        var statusText = s.is_configured ? "Active" : "Not Configured";
        sourcesHtml += '<div class="source-item">'
          + '<div class="source-item-header">'
          + '<strong>' + escapeHtml(s.name) + '</strong>'
          + '<span class="source-badge ' + statusClass + '">' + statusText + '</span>'
          + '</div>'
          + '<div class="source-item-meta">'
          + '<span class="case-badge case-badge-jurisdiction">' + escapeHtml(s.jurisdiction || "GLOBAL") + '</span>'
          + '<span class="case-badge case-badge-stage">' + escapeHtml(s.source_type || "") + '</span>'
          + '<span style="color:var(--text-secondary);font-size:12px">' + escapeHtml(s.authority || "") + '</span>'
          + '</div>'
          + '</div>';
      });
      sourcesHtml += '</div></div>';
    }

    return ''
      + '<div class="case-header">'
      + '<div><h1 class="case-title">Knowledge Engine</h1>'
      + '<div class="case-subtitle">Research Traditional Knowledge and evidence-backed findings for your plants and ingredients.</div></div>'
      + '</div>'
      + '<div class="card"><div class="card-body">'
      + '<form id="knowledge-search-form">'
      + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px">'
      + '<div class="form-group">'
      + '<label class="form-label">Search Query *</label>'
      + '<input class="form-input" type="text" id="kq-query" placeholder="e.g. traditional uses, preparations, safety" value="' + escapeHtml(state.knowledgeQuery) + '" required>'
      + '</div>'
      + '<div class="form-group">'
      + '<label class="form-label">Plant / Ingredient</label>'
      + '<input class="form-input" type="text" id="kq-plant" placeholder="e.g. Withania somnifera" value="' + escapeHtml(state.knowledgePlantName) + '">'
      + '</div>'
      + '</div>'
      + '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:12px">'
      + '<div class="form-group">'
      + '<label class="form-label">Botanical Name</label>'
      + '<input class="form-input" type="text" id="kq-botanical" placeholder="e.g. Bacopa monnieri" value="' + escapeHtml(state.knowledgeBotanicalName) + '">'
      + '</div>'
      + '<div class="form-group">'
      + '<label class="form-label">Category</label>'
      + '<select class="form-select" id="kq-category">'
      + '<option value="">All Categories</option>'
      + '<option value="TRADITIONAL_USE">Traditional Use</option>'
      + '<option value="PREPARATION">Preparation</option>'
      + '<option value="BOTANICAL">Botanical</option>'
      + '<option value="SAFETY">Safety</option>'
      + '<option value="DOSAGE">Dosage</option>'
      + '<option value="PHARMACOLOGY">Pharmacology</option>'
      + '<option value="HISTORY">History</option>'
      + '<option value="OTHER">Other</option>'
      + '</select>'
      + '</div>'
      + '<div class="form-group">'
      + '<label class="form-label">Jurisdiction</label>'
      + '<select class="form-select" id="kq-jurisdiction">'
      + '<option value="">All Jurisdictions</option>'
      + '<option value="IN">India</option>'
      + '<option value="US">United States</option>'
      + '<option value="EU">European Union</option>'
      + '<option value="GLOBAL">Global</option>'
      + '</select>'
      + '</div>'
      + '</div>'
      + '<button class="btn btn-primary" type="submit" id="kq-search-btn">' + icon("beaker", 15) + ' Search Sources</button>'
      + '</form>'
      + '</div></div>'
      + resultsHtml
      + sourcesHtml;
  }

  // ----------------------------------------------------------------
  // Knowledge Engine — Results view
  // ----------------------------------------------------------------

  function renderKnowledgeResults() {
    var data = state.knowledgeResults;
    if (!data) return "";

    var html = '<div class="card" style="margin-top:20px"><div class="card-head">'
      + '<h2>Search Results</h2>'
      + '<p>' + (data.total_results || 0) + ' result(s) from ' + (data.sources ? data.sources.length : 0) + ' source(s)</p>'
      + '</div><div class="card-body">';

    if (!data.has_configured_sources && (!data.sources || data.sources.length === 0)) {
      html += '<div class="empty-state">'
        + '<div class="empty-icon">' + icon("evidence", 28) + '</div>'
        + '<h3>No sources available</h3>'
        + '<p>No knowledge sources are currently configured. Configure source adapters in the environment to enable real data retrieval.</p>'
        + '</div>';
    } else if (!data.has_configured_sources) {
      // Sources exist but none are configured
      html += '<div class="source-status-banner source-status-warning">'
        + icon("alert", 18)
        + '<div><strong>Source adapters found but not configured.</strong>'
        + '<p style="margin-top:4px;font-size:13px;color:var(--text-secondary)">Configure the corresponding API keys and credentials in your .env file to enable real knowledge retrieval. No fabricated results are shown.</p></div>'
        + '</div>';

      // Show what sources are available
      data.sources.forEach(function (src) {
        if (src.message) {
          html += '<div class="source-result-card source-result-unconfigured">'
            + '<div class="source-result-header">'
            + '<strong>' + escapeHtml(src.source_name) + '</strong>'
            + '<span class="case-badge case-badge-jurisdiction">' + escapeHtml(src.jurisdiction || "GLOBAL") + '</span>'
            + '</div>'
            + '<p class="source-result-message">' + escapeHtml(src.message) + '</p>'
            + '</div>';
        }
      });
    } else {
      // Show actual results
      var hasResults = false;
      data.sources.forEach(function (src) {
        if (src.results && src.results.length > 0) {
          hasResults = true;
          src.results.forEach(function (r) {
            html += renderKnowledgeFindingCard(r, src);
          });
        } else if (!src.is_configured) {
          html += '<div class="source-result-card source-result-unconfigured">'
            + '<div class="source-result-header">'
            + '<strong>' + escapeHtml(src.source_name) + '</strong>'
            + '<span class="case-badge case-badge-jurisdiction">' + escapeHtml(src.jurisdiction || "GLOBAL") + '</span>'
            + '<span class="source-badge source-status-inactive">Not Configured</span>'
            + '</div>'
            + '<p class="source-result-message">' + escapeHtml(src.message || "Source not configured.") + '</p>'
            + '</div>';
        }
      });

      if (!hasResults) {
        html += '<div class="empty-state">'
          + '<h3>No findings for this query</h3>'
          + '<p>Try a different query or check that your source adapters are configured.</p>'
          + '</div>';
      }
    }

    html += '</div></div>';
    return html;
  }

  // ----------------------------------------------------------------
  // Knowledge Engine — Single finding card
  // ----------------------------------------------------------------

  function renderKnowledgeFindingCard(finding, source) {
    var confClass = "confidence-unknown";
    var confText = finding.confidence || "UNKNOWN";
    if (confText === "HIGH") confClass = "confidence-high";
    else if (confText === "MODERATE") confClass = "confidence-moderate";
    else if (confText === "LOW") confClass = "confidence-low";
    else if (confText === "CONFLICTING") confClass = "confidence-conflicting";

    var categoryLabel = (finding.category || "OTHER").replace(/_/g, " ");
    var findingDataJson = escapeHtml(JSON.stringify(finding).replace(/"/g, "&quot;"));

    return '<div class="knowledge-finding-card">'
      + '<div class="knowledge-finding-header">'
      + '<div><h3 class="knowledge-finding-title">' + escapeHtml(finding.title) + '</h3>'
      + (finding.plant_name ? '<span style="color:var(--text-secondary);font-size:13px;font-style:italic">' + escapeHtml(finding.botanical_name || finding.plant_name) + '</span>' : '')
      + '</div>'
      + '<span class="confidence-badge ' + confClass + '">' + confText + '</span>'
      + '</div>'
      + (finding.summary ? '<p class="knowledge-finding-summary">' + escapeHtml(finding.summary) + '</p>' : '')
      + '<div class="knowledge-finding-meta">'
      + '<span class="case-badge case-badge-stage">' + escapeHtml(categoryLabel) + '</span>'
      + '<span class="case-badge case-badge-jurisdiction">' + escapeHtml(source.jurisdiction || finding.jurisdiction || "—") + '</span>'
      + '<span class="source-label">' + escapeHtml(source.source_authority || source.source_name || "—") + '</span>'
      + '</div>'
      + (finding.evidence_locator ? '<div class="knowledge-finding-evidence"><strong>Evidence:</strong> ' + escapeHtml(finding.evidence_locator) + '</div>' : '')
      + (finding.excerpt ? '<div class="knowledge-finding-excerpt">"' + escapeHtml(finding.excerpt) + '"</div>' : '')
      + (finding.limitations ? '<div class="knowledge-finding-limitations">' + icon("alert", 14) + ' ' + escapeHtml(finding.limitations) + '</div>' : '')
      + '<div class="knowledge-finding-actions">'
      + '<button class="btn btn-primary btn-sm save-finding-btn" data-finding=\'' + findingDataJson + '\'>' + icon("plus", 14) + ' Save to Product Case</button>'
      + '</div>'
      + '</div>';
  }

  // ----------------------------------------------------------------
  // Knowledge Engine — Event handlers
  // ----------------------------------------------------------------

  function bindKnowledgeEvents() {
    // Search form
    var form = document.getElementById("knowledge-search-form");
    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var query = document.getElementById("kq-query").value.trim();
        if (!query) {
          toast("Search query is required", "error");
          return;
        }
        state.knowledgeQuery = query;
        state.knowledgePlantName = document.getElementById("kq-plant").value.trim();
        state.knowledgeBotanicalName = document.getElementById("kq-botanical").value.trim();
        state.knowledgeCategory = document.getElementById("kq-category").value;
        state.knowledgeJurisdiction = document.getElementById("kq-jurisdiction").value;

        searchKnowledge({
          query: query,
          plant_name: state.knowledgePlantName || null,
          botanical_name: state.knowledgeBotanicalName || null,
          category: state.knowledgeCategory || null,
          jurisdiction: state.knowledgeJurisdiction || null,
          limit: 20,
        });
      });
    }

    // Save finding buttons
    document.querySelectorAll(".save-finding-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var findingStr = btn.getAttribute("data-finding");
        if (!findingStr) return;
        var finding;
        try { finding = JSON.parse(findingStr); } catch (e) { return; }
        showSaveFindingModal(finding);
      });
    });
  }

  // ----------------------------------------------------------------
  // Knowledge Engine — Save to Product Case modal
  // ----------------------------------------------------------------

  function showSaveFindingModal(finding) {
    if (!state.cases || state.cases.length === 0) {
      toast("Create a Product Case first before saving findings", "error");
      return;
    }

    var existing = document.getElementById("knowledge-save-modal");
    if (existing) existing.remove();

    var optionsHtml = '<option value="">Select a Product Case...</option>';
    state.cases.forEach(function (c) {
      optionsHtml += '<option value="' + escapeHtml(c.id) + '">' + escapeHtml(c.name) + '</option>';
    });

    var html = '<div class="modal-overlay open" id="knowledge-save-modal">'
      + '<div class="modal" role="dialog">'
      + '<div class="modal-head">'
      + '<h2>Save Finding to Product Case</h2>'
      + '<button class="modal-close" id="ksm-close">' + icon("close", 18) + '</button>'
      + '</div>'
      + '<div class="modal-body">'
      + '<p style="margin-bottom:12px;color:var(--text-secondary)">Save this finding as part of your product research trail.</p>'
      + '<div class="form-group">'
      + '<label class="form-label">Finding</label>'
      + '<div style="padding:8px 12px;background:var(--gray-50);border-radius:6px;font-size:13px">'
      + '<strong>' + escapeHtml(finding.title) + '</strong>'
      + (finding.source_name ? '<br><span style="color:var(--text-secondary)">Source: ' + escapeHtml(finding.source_name) + '</span>' : '')
      + '</div>'
      + '</div>'
      + '<div class="form-group">'
      + '<label class="form-label">Product Case *</label>'
      + '<select class="form-select" id="ksm-case-select">' + optionsHtml + '</select>'
      + '</div>'
      + '</div>'
      + '<div class="modal-foot">'
      + '<button class="btn btn-secondary" id="ksm-cancel">Cancel</button>'
      + '<button class="btn btn-primary" id="ksm-save">' + icon("plus", 15) + ' Save Finding</button>'
      + '</div>'
      + '</div></div>';

    document.body.insertAdjacentHTML("beforeend", html);

    var overlay = document.getElementById("knowledge-save-modal");
    var closeBtn = document.getElementById("ksm-close");
    var cancelBtn = document.getElementById("ksm-cancel");
    var saveBtn = document.getElementById("ksm-save");

    function closeModal() { overlay.remove(); }
    if (closeBtn) closeBtn.addEventListener("click", closeModal);
    if (cancelBtn) cancelBtn.addEventListener("click", closeModal);
    if (overlay) overlay.addEventListener("click", function (e) { if (e.target === overlay) closeModal(); });

    if (saveBtn) {
      saveBtn.addEventListener("click", async function () {
        var caseId = document.getElementById("ksm-case-select").value;
        if (!caseId) {
          toast("Select a Product Case", "error");
          return;
        }
        saveBtn.disabled = true;
        saveBtn.textContent = "Saving...";
        try {
          await saveKnowledgeFinding(finding, caseId);
          closeModal();
          toast("Finding saved to Product Case", "success");
        } catch (e) {
          toast("Failed to save: " + e.message, "error");
          saveBtn.disabled = false;
          saveBtn.innerHTML = icon("plus", 15) + " Save Finding";
        }
      });
    }
  }
