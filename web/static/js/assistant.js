/* ==================================================================
   AYUR-INTEL — In-App RAG Assistant Frontend Component
   Floating botanical assistant panel with grounded Q&A and safe navigation.
   ================================================================== */
(function () {
  "use strict";

  // Assistant State
  var state = {
    isOpen: false,
    loading: false,
    requestId: 0,
    messages: [
      {
        sender: "assistant",
        text: "Namaste! I am your **AYUR-INTEL Assistant**. I can help you navigate the platform, understand how to create products, explore Patent & Regulatory Intelligence, and guide your Ayurvedic formulations.\n\nWhat would you like to know?",
        sources: ["AYUR-INTEL Platform & Mission"],
        actions: [
          { id: "OPEN_PRODUCTS", label: "View Products →", target: "product-cases" },
          { id: "CREATE_PRODUCT", label: "Create Product →", target: "passport-wizard" }
        ]
      }
    ],
    suggestedQuestions: [
      "What can AYUR-INTEL do?",
      "How do I create a product?",
      "What is Product Passport?",
      "How does Patent Intelligence work?",
      "Where are my products?"
    ]
  };

  // Helper: get current application view and active product safely
  function getAppContext() {
    var ayur = window.AYUR || {};
    var ayurState = ayur.state || {};
    var view = ayurState.view || "dashboard";

    var activeId = null;
    var activeName = null;

    if (typeof ayur.getActiveProductId === "function") {
      activeId = ayur.getActiveProductId();
    } else if (ayurState.currentCase) {
      activeId = String(ayurState.currentCase.public_id || ayurState.currentCase.id || "");
    }

    if (ayurState.currentCase && ayurState.currentCase.name) {
      activeName = ayurState.currentCase.name;
    }

    return {
      current_view: view,
      active_product_id: activeId || null,
      active_product_name: activeName || null
    };
  }

  // Helper: sanitize and format text (safe markdown subset)
  function renderMarkdown(raw) {
    if (!raw) return "";
    var escaped = String(raw)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Bold **text**
    escaped = escaped.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

    // Italics *text*
    escaped = escaped.replace(/\*(.*?)\*/g, "<em>$1</em>");

    // Inline code `text`
    escaped = escaped.replace(/`([^`]+)`/g, "<code>$1</code>");

    // Bullet lists lines starting with • or -
    var lines = escaped.split("\n");
    var inList = false;
    var result = [];

    for (var i = 0; i < lines.length; i++) {
      var line = lines[i].trim();
      if (line.startsWith("• ") || line.startsWith("- ")) {
        if (!inList) {
          result.push("<ul class='assistant-list'>");
          inList = true;
        }
        result.push("<li>" + line.substring(2) + "</li>");
      } else if (line.match(/^\d+\.\s/)) {
        if (!inList) {
          result.push("<ol class='assistant-list'>");
          inList = true;
        }
        result.push("<li>" + line.replace(/^\d+\.\s/, "") + "</li>");
      } else {
        if (inList) {
          result.push("</ul>");
          inList = false;
        }
        if (line.length > 0) {
          result.push("<p>" + line + "</p>");
        }
      }
    }
    if (inList) {
      result.push("</ul>");
    }

    return result.join("");
  }

  // Safe Navigation Action Handler
  function handleAssistantAction(actionId, target, productId) {
    var ayur = window.AYUR || {};
    var s = ayur.state || {};

    try {
      switch (actionId) {
        case "OPEN_DASHBOARD":
          if (typeof ayur.navigateTo === "function") {
            ayur.navigateTo("dashboard");
          } else {
            s.view = "dashboard";
            if (ayur.render) ayur.render({ scroll: "top" });
          }
          break;

        case "OPEN_PRODUCTS":
          if (typeof ayur.navigateTo === "function") {
            ayur.navigateTo("product-cases");
          } else {
            s.view = "product-cases";
            if (ayur.render) ayur.render({ scroll: "top" });
          }
          break;

        case "CREATE_PRODUCT":
          var createFn = ayur.createCase || window.createCase;
          if (typeof createFn === "function") {
            createFn();
          } else if (typeof ayur.navigateTo === "function") {
            ayur.navigateTo("passport-wizard");
          } else {
            s.view = "passport-wizard";
            s.passportStep = 0;
            if (ayur.render) ayur.render({ scroll: "top" });
          }
          break;

        case "OPEN_PRODUCT_PASSPORT":
          var pId = productId || (ayur.getActiveProductId ? ayur.getActiveProductId() : null);
          var editFn = ayur.editProductPassport || window.editProductPassport;
          var createFn2 = ayur.createCase || window.createCase;
          if (pId && typeof editFn === "function") {
            editFn(pId);
          } else if (typeof createFn2 === "function") {
            createFn2();
          } else {
            s.view = "passport-wizard";
            if (ayur.render) ayur.render({ scroll: "top" });
          }
          break;

        case "OPEN_MONITORING":
          var mId = productId || (ayur.getActiveProductId ? ayur.getActiveProductId() : null);
          if (typeof ayur.navigateTo === "function") {
            ayur.navigateTo("monitoring-center");
          } else {
            s.view = "monitoring-center";
            if (ayur.render) ayur.render({ scroll: "top" });
          }
          if (mId && typeof window.switchMonitoringProduct === "function") {
            window.switchMonitoringProduct(mId);
          }
          break;

        case "OPEN_PATENT":
          var patId = productId || (ayur.getActiveProductId ? ayur.getActiveProductId() : null);
          var patFn = ayur.openPatentIntelligence || window.openPatentIntelligence;
          if (patId && typeof patFn === "function") {
            patFn(patId);
          } else if (typeof ayur.navigateTo === "function") {
            ayur.navigateTo("product-cases");
          }
          break;

        case "OPEN_REGULATORY":
          var regId = productId || (ayur.getActiveProductId ? ayur.getActiveProductId() : null);
          var regFn = ayur.generateRegulatoryAnalysis || window.generateRegulatoryAnalysis;
          if (regId && typeof regFn === "function") {
            regFn(regId, "IN");
          } else if (typeof ayur.navigateTo === "function") {
            ayur.navigateTo("product-cases");
          }
          break;

        case "OPEN_RISK":
          var riskId = productId || (ayur.getActiveProductId ? ayur.getActiveProductId() : null);
          var riskFn = ayur.generateRiskAssessment || window.generateRiskAssessment;
          if (typeof riskFn === "function") {
            riskFn(riskId);
          } else if (typeof ayur.navigateTo === "function") {
            ayur.navigateTo("product-cases");
          }
          break;

        case "OPEN_EVIDENCE":
          var evId = productId || (ayur.getActiveProductId ? ayur.getActiveProductId() : null);
          var evFn = ayur.openCaseModule || window.openCaseModule;
          if (evId && typeof evFn === "function") {
            evFn("evidenceData", "/api/cases/" + evId + "/evidence", "evidence");
          } else if (typeof ayur.navigateTo === "function") {
            ayur.navigateTo("product-cases");
          }
          break;

        case "OPEN_DECISION_DASHBOARD":
          var decId = productId || (ayur.getActiveProductId ? ayur.getActiveProductId() : null);
          var decFn = ayur.openCaseModule || window.openCaseModule;
          if (decId && typeof decFn === "function") {
            decFn("dashboardData", "/api/cases/" + decId + "/decision-dashboard", "dashboard-detail");
          } else if (typeof ayur.navigateTo === "function") {
            ayur.navigateTo("product-cases");
          }
          break;

        default:
          if (target && typeof ayur.navigateTo === "function") {
            ayur.navigateTo(target);
          }
          break;
      }

      if (ayur.toast) {
        ayur.toast("Navigating to " + (target || "feature"), "info");
      }
    } catch (err) {
      console.warn("Navigation action error:", err);
    }
  }
  window.handleAssistantAction = handleAssistantAction;

  // Render DOM: Trigger Button & Panel
  function injectAssistantDOM() {
    if (document.getElementById("ayur-assistant-trigger")) return;

    // 1. Floating trigger button
    var trigger = document.createElement("button");
    trigger.id = "ayur-assistant-trigger";
    trigger.className = "ayur-assistant-trigger";
    trigger.setAttribute("aria-label", "Ask AYUR-INTEL Assistant");
    trigger.setAttribute("type", "button");
    trigger.innerHTML = '<span class="assistant-trigger-leaf">🌿</span>'
      + '<span class="assistant-trigger-text">Ask AYUR-INTEL</span>';

    // 2. Main assistant panel
    var panel = document.createElement("div");
    panel.id = "ayur-assistant-panel";
    panel.className = "ayur-assistant-panel";
    panel.style.display = "none";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-labelledby", "ayur-assistant-title");

    panel.innerHTML = ''
      // Header
      + '<div class="assistant-header">'
      + '  <div class="assistant-header-info">'
      + '    <div class="assistant-title-row">'
      + '      <span class="assistant-header-leaf">🌿</span>'
      + '      <h3 id="ayur-assistant-title">AYUR-INTEL Assistant</h3>'
      + '    </div>'
      + '    <div class="assistant-subtitle">Product & Platform Guide</div>'
      + '  </div>'
      + '  <div class="assistant-header-actions">'
      + '    <button type="button" class="assistant-btn-icon" id="assistant-btn-minimize" title="Minimize">'
      + '      <span class="material-symbols-outlined">remove</span>'
      + '    </button>'
      + '    <button type="button" class="assistant-btn-icon" id="assistant-btn-close" title="Close">'
      + '      <span class="material-symbols-outlined">close</span>'
      + '    </button>'
      + '  </div>'
      + '</div>'

      // Context Banner (Active Product Indicator)
      + '<div class="assistant-context-bar" id="assistant-context-bar" style="display:none;">'
      + '  <span class="material-symbols-outlined" style="font-size:14px;">spa</span>'
      + '  <span id="assistant-context-name">No active product</span>'
      + '</div>'

      // Messages Area
      + '<div class="assistant-conversation" id="assistant-conversation">'
      + '  <div id="assistant-messages-list"></div>'
      + '  <div class="assistant-loading-indicator" id="assistant-loading-indicator" style="display:none;">'
      + '    <div class="assistant-typing-dots"><span></span><span></span><span></span></div>'
      + '    <span class="assistant-typing-text">Grounded retrieval in progress...</span>'
      + '  </div>'
      + '</div>'

      // Suggested Prompts
      + '<div class="assistant-suggestions" id="assistant-suggestions">'
      + '  <div class="assistant-suggestions-label">Suggested:</div>'
      + '  <div class="assistant-chips-scroll" id="assistant-chips-container"></div>'
      + '</div>'

      // Input Footer
      + '<div class="assistant-footer">'
      + '  <form id="assistant-form" class="assistant-input-form" onsubmit="return false;">'
      + '    <input type="text" id="assistant-input" class="assistant-input" placeholder="Ask about AYUR-INTEL, features, navigation..." autocomplete="off">'
      + '    <button type="submit" id="assistant-send-btn" class="assistant-send-btn" title="Send Question" aria-label="Send">'
      + '      <span class="material-symbols-outlined">send</span>'
      + '    </button>'
      + '  </form>'
      + '</div>';

    document.body.appendChild(trigger);
    document.body.appendChild(panel);

    // Bind UI Events
    trigger.addEventListener("click", toggleAssistant);
    document.getElementById("assistant-btn-close").addEventListener("click", closeAssistant);
    document.getElementById("assistant-btn-minimize").addEventListener("click", closeAssistant);

    var form = document.getElementById("assistant-form");
    var input = document.getElementById("assistant-input");

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      e.stopPropagation();
      handleSend();
    });

    input.addEventListener("keydown", function (e) {
      // Prevent interfering with global page enter or escape shortcuts
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        handleSend();
      }
    });

    renderSuggestedChips();
    renderMessages();
  }

  // Toggle Assistant Panel
  function toggleAssistant() {
    if (state.isOpen) {
      closeAssistant();
    } else {
      openAssistant();
    }
  }

  function openAssistant() {
    state.isOpen = true;
    var panel = document.getElementById("ayur-assistant-panel");
    var trigger = document.getElementById("ayur-assistant-trigger");
    if (panel) {
      panel.style.display = "flex";
      updateContextBar();
      scrollToBottom();
      var input = document.getElementById("assistant-input");
      if (input) input.focus();
    }
    if (trigger) trigger.classList.add("active");
  }

  function closeAssistant() {
    state.isOpen = false;
    var panel = document.getElementById("ayur-assistant-panel");
    var trigger = document.getElementById("ayur-assistant-trigger");
    if (panel) panel.style.display = "none";
    if (trigger) trigger.classList.remove("active");
  }

  // Update Active Product Context Bar
  function updateContextBar() {
    var bar = document.getElementById("assistant-context-bar");
    var nameEl = document.getElementById("assistant-context-name");
    if (!bar || !nameEl) return;

    var ctx = getAppContext();
    if (ctx.active_product_name) {
      bar.style.display = "flex";
      nameEl.innerHTML = "Active Case: <strong>" + escapeHtml(ctx.active_product_name) + "</strong>";
    } else {
      bar.style.display = "none";
    }
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // Render Suggested Question Chips
  function renderSuggestedChips() {
    var container = document.getElementById("assistant-chips-container");
    if (!container) return;

    var html = "";
    state.suggestedQuestions.forEach(function (q) {
      html += '<button type="button" class="assistant-chip" onclick="window.sendAssistantSuggestedPrompt(this)">'
        + escapeHtml(q)
        + '</button>';
    });
    container.innerHTML = html;
  }

  window.sendAssistantSuggestedPrompt = function (btn) {
    if (!btn) return;
    var text = btn.innerText || btn.textContent;
    var input = document.getElementById("assistant-input");
    if (input) {
      input.value = text;
      handleSend();
    }
  };

  // Render Conversation Messages
  function renderMessages() {
    var list = document.getElementById("assistant-messages-list");
    if (!list) return;

    var html = "";
    state.messages.forEach(function (msg, idx) {
      var isUser = msg.sender === "user";
      html += '<div class="assistant-message-row ' + (isUser ? "user" : "assistant") + '">'
        + '  <div class="assistant-avatar">' + (isUser ? "👤" : "🌿") + '</div>'
        + '  <div class="assistant-bubble">'
        + '    <div class="assistant-message-content">' + renderMarkdown(msg.text) + '</div>';

      // Action buttons
      if (!isUser && msg.actions && msg.actions.length > 0) {
        html += '<div class="assistant-actions-row">';
        msg.actions.forEach(function (act) {
          var actId = act.id || "";
          var target = act.target || "";
          var pId = act.product_id || "";
          var safeLabel = escapeHtml(act.label || "Open");
          html += '<button type="button" class="assistant-action-btn" '
            + 'onclick="window.handleAssistantAction(\'' + actId + '\', \'' + target + '\', \'' + pId + '\')">'
            + safeLabel
            + '</button>';
        });
        html += '</div>';
      }

      // Source Labels
      if (!isUser && msg.sources && msg.sources.length > 0) {
        html += '<div class="assistant-sources-row">'
          + '<span class="assistant-source-icon material-symbols-outlined">menu_book</span>'
          + '<span>Knowledge: ' + escapeHtml(msg.sources.join(" • ")) + '</span>'
          + '</div>';
      }

      html += '  </div>'
        + '</div>';
    });

    list.innerHTML = html;
    scrollToBottom();
  }

  function scrollToBottom() {
    var conv = document.getElementById("assistant-conversation");
    if (conv) {
      setTimeout(function () {
        conv.scrollTop = conv.scrollHeight;
      }, 50);
    }
  }

  // Handle User Message Submission
  async function handleSend() {
    var input = document.getElementById("assistant-input");
    if (!input || state.loading) return;

    var text = (input.value || "").trim();
    if (!text) return;

    // Append user message immediately
    state.messages.push({
      sender: "user",
      text: text
    });
    input.value = "";
    state.loading = true;

    renderMessages();

    var loadingIndicator = document.getElementById("assistant-loading-indicator");
    if (loadingIndicator) loadingIndicator.style.display = "flex";
    scrollToBottom();

    var currentSeq = ++state.requestId;
    var ctx = getAppContext();

    try {
      var payload = {
        message: text,
        current_view: ctx.current_view,
        active_product_id: ctx.active_product_id,
        active_product_name: ctx.active_product_name
      };

      var response = await fetch("/api/assistant/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error("Server returned status " + response.status);
      }

      var data = await response.json();

      // Guard against stale response if user sent another query rapidly
      if (currentSeq === state.requestId) {
        state.messages.push({
          sender: "assistant",
          text: data.answer || "I received your request.",
          sources: data.sources || [],
          actions: data.actions || [],
          source_type: data.source_type || "GEMINI"
        });
      }
    } catch (err) {
      console.warn("Assistant request failed, using local resilient response:", err);
      if (currentSeq === state.requestId) {
        state.messages.push({
          sender: "assistant",
          text: "I am currently running in offline resilience mode. You can view your saved formulations, create a new Product Passport, or check monitoring directly using the quick links below.",
          sources: ["AYUR-INTEL Platform & Mission"],
          actions: [
            { id: "OPEN_PRODUCTS", label: "View Products →", target: "product-cases" },
            { id: "CREATE_PRODUCT", label: "Create Product →", target: "passport-wizard" }
          ],
          source_type: "FALLBACK"
        });
      }
    } finally {
      if (currentSeq === state.requestId) {
        state.loading = false;
        if (loadingIndicator) loadingIndicator.style.display = "none";
        renderMessages();
      }
    }
  }

  // Boot assistant on DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", injectAssistantDOM);
  } else {
    injectAssistantDOM();
  }

  // Expose API for external integration & debugging
  window.AYUR_ASSISTANT = {
    open: openAssistant,
    close: closeAssistant,
    toggle: toggleAssistant,
    updateContext: updateContextBar,
    state: state,
    send: function (text) {
      var input = document.getElementById("assistant-input");
      if (input) {
        input.value = text;
        handleSend();
      }
    }
  };
})();
