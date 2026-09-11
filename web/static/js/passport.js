/* AYUR-INTEL — Conversational Product Passport & Guided Assistant
   Intelligent, conversational intake for Ayurvedic & Herbal products.
   Normalizes natural language inputs into structured Product Passports.
   Exclusively focused on the Indian Regulatory & Patent Ecosystem (CGPDTM / IPO). */

(function () {
  "use strict";

  var A = window.AYUR;
  if (!A) { console.error("passport.js requires app.js"); return; }

  var state = A.state;
  var api = A.api;
  var toast = A.toast;
  var esc = A.escapeHtml;
  var icon = A.icon;

  // ----------------------------------------------------------------
  // Step Definitions (EXACTLY 7 Questions + 1 Review Screen)
  // ----------------------------------------------------------------

  var CONV_STEPS = [
    {
      key: "category",
      tag: "Step 1 of 7",
      title: "Product Category",
      desc: "Select the category that best describes your product formulation.",
    },
    {
      key: "name",
      tag: "Step 2 of 7",
      title: "Product Name",
      desc: "Enter a working title or project identifier for this product.",
    },
    {
      key: "description",
      tag: "Step 3 of 7",
      title: "Product Description",
      desc: "Provide an overview of the product in your own words. English, Hindi, or Hinglish inputs are structured automatically.",
    },
    {
      key: "ingredients",
      tag: "Step 4 of 7",
      title: "Ingredients & Botanicals",
      desc: "Select common Ayurvedic botanicals or specify custom ingredients. Specify quantity/potency for each ingredient.",
    },
    {
      key: "intended_use",
      tag: "Step 5 of 7",
      title: "Intended Use & Indications",
      desc: "Select the primary health focus areas, indications, and traditional wellness uses.",
    },
    {
      key: "process",
      tag: "Step 6 of 7",
      title: "Preparation & Formulation",
      desc: "Specify the manufacturing or extraction method to support patent landscape and IP analysis.",
    },
    {
      key: "claims",
      tag: "Step 7 of 7",
      title: "Proposed Claims",
      desc: "Define the proposed benefit claims to be assessed in regulatory intelligence.",
    },
    {
      key: "review",
      tag: "Review",
      title: "Product Passport & Indian Patent Intelligence",
      desc: "Review the structured product identity — ingredients, formulation, intended use, claims, and Indian patent readiness.",
    }
  ];

  var POPULAR_BOTANICALS = [
    { name: "Ashwagandha", botanical: "Withania somnifera", emoji: "🌿" },
    { name: "Brahmi", botanical: "Bacopa monnieri", emoji: "🌿" },
    { name: "Tulsi", botanical: "Ocimum sanctum", emoji: "🍃" },
    { name: "Shankhpushpi", botanical: "Convolvulus pluricaulis", emoji: "🌸" },
    { name: "Jatamansi", botanical: "Nardostachys jatamansi", emoji: "🌱" },
    { name: "Turmeric (Haridra)", botanical: "Curcuma longa", emoji: "🌾" },
    { name: "Neem", botanical: "Azadirachta indica", emoji: "🍃" },
    { name: "Amla", botanical: "Phyllanthus emblica", emoji: "🍈" },
    { name: "Giloy (Guduchi)", botanical: "Tinospora cordifolia", emoji: "🌿" },
    { name: "Shatavari", botanical: "Asparagus racemosus", emoji: "🌱" },
    { name: "Triphala", botanical: "T. chebula + T. bellirica + P. emblica", emoji: "🌾" },
    { name: "Mulethi (Licorice)", botanical: "Glycyrrhiza glabra", emoji: "🪵" },
  ];

  var BOTANICAL_LOOKUP = {
    "ashwagandha": "Withania somnifera",
    "brahmi": "Bacopa monnieri",
    "tulsi": "Ocimum sanctum",
    "holy basil": "Ocimum sanctum",
    "shankhpushpi": "Convolvulus pluricaulis",
    "jatamansi": "Nardostachys jatamansi",
    "turmeric": "Curcuma longa",
    "haridra": "Curcuma longa",
    "haldi": "Curcuma longa",
    "neem": "Azadirachta indica",
    "amla": "Phyllanthus emblica",
    "amalaki": "Phyllanthus emblica",
    "giloy": "Tinospora cordifolia",
    "guduchi": "Tinospora cordifolia",
    "shatavari": "Asparagus racemosus",
    "triphala": "T. chebula + T. bellirica + P. emblica",
    "mulethi": "Glycyrrhiza glabra",
    "licorice": "Glycyrrhiza glabra",
    "yashtimadhu": "Glycyrrhiza glabra",
    "guggulu": "Commiphora mukul",
    "guggul": "Commiphora mukul",
    "ginger": "Zingiber officinale",
    "adrak": "Zingiber officinale",
    "sonth": "Zingiber officinale",
    "shunthi": "Zingiber officinale",
    "gotu kola": "Centella asiatica",
    "mandukaparni": "Centella asiatica",
    "arjuna": "Terminalia arjuna",
    "manjistha": "Rubia cordifolia",
    "vasa": "Adhatoda vasica"
  };

  // Quantity Input Validation helper
  function validateQuantityInput(input) {
    if (!input) return;
    var value = input.value;
    if (!value) return;
    // Only allow: numbers, space, 'mg', 'gm', 'ml', 'g', 'm', 'l'
    value = value.replace(/[^0-9\s.mgMG]/g, '');
    input.value = value;
  }
  window.validateQuantityInput = validateQuantityInput;
  if (window.AYUR) window.AYUR.validateQuantityInput = validateQuantityInput;

  // Helper to normalize custom ingredient name from Hindi/Hinglish/English
  function normalizeCustomIngredient(raw) {
    if (!raw) return { name: "", botanical: "" };
    var s = raw.trim();
    
    // Hinglish transformations
    s = s.replace(/\bka\s+extract\b/gi, "Extract");
    s = s.replace(/\bki\s+extract\b/gi, "Extract");
    s = s.replace(/\bka\s+churna\b/gi, "Churna");
    s = s.replace(/\bka\s+powder\b/gi, "Powder");
    s = s.replace(/\bka\s+tel\b/gi, "Oil");
    s = s.replace(/\bki\s+patti\b/gi, "Leaves");
    s = s.replace(/\bke\s+beej\b/gi, "Seeds");
    s = s.replace(/\bki\s+jad\b/gi, "Root");
    s = s.replace(/\bka\s+swaras\b/gi, "Swaras");

    // Title case words
    var words = s.split(/\s+/).map(function(w) {
      if (!w) return "";
      return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
    });
    var cleanName = words.join(" ");

    // Look up botanical Latin name
    var lower = cleanName.toLowerCase();
    var matchedLatin = "";
    Object.keys(BOTANICAL_LOOKUP).forEach(function(k) {
      if (lower.indexOf(k) !== -1 && !matchedLatin) {
        matchedLatin = BOTANICAL_LOOKUP[k];
      }
    });

    return {
      name: cleanName,
      botanical: matchedLatin
    };
  }

  // ----------------------------------------------------------------
  // Demo Product Data Definition (Ashwagandha & Brahmi Cognitive Capsules)
  // ----------------------------------------------------------------

  var DEMO_PASSPORT_DATA = {
    name: "AYUR-INTEL NeuroAdapt Botanical Complex",
    product_type: "Ayurvedic Proprietary Medicine",
    formulation: "Ayurvedic Proprietary Medicine",
    form: "Hard Gelatin Capsule",
    description: "A multi-botanical neuro-adaptogenic product showcase concept designed for cognitive wellness support, focus support, and adaptogenic stress management. It combines six standardized Indian botanical extracts in a defined oral dosage form with a piperine-containing bio-enhancement strategy under evaluation.",
    normalized_description: "A multi-botanical neuro-adaptogenic product showcase concept designed for cognitive wellness support, focus support, and adaptogenic stress management. It combines six standardized Indian botanical extracts in a defined oral dosage form with a piperine-containing bio-enhancement strategy under evaluation.",
    ingredients: [
      {
        name: "Ashwagandha",
        botanical: "Withania somnifera",
        quantity: "175 mg",
        standardization: "5% Withanolides (HPLC)",
        status: "VERIFIED",
        source: "Charaka Samhita Chikitsa Sthana Rasayana",
        verification_status: "VERIFIED",
        therapeutic_indication: "Adaptogenic stress & neuro-wellness support"
      },
      {
        name: "Brahmi",
        botanical: "Bacopa monnieri",
        quantity: "125 mg",
        standardization: "20% Bacosides (HPLC)",
        status: "VERIFIED",
        source: "Charaka Samhita Sutra Sthana Medhya",
        verification_status: "VERIFIED",
        therapeutic_indication: "Cognitive wellness & memory support"
      },
      {
        name: "Mandukaparni",
        botanical: "Centella asiatica",
        quantity: "100 mg",
        standardization: "10% Asiaticosides",
        status: "VERIFIED",
        source: "Sushruta Samhita Sutra Sthana",
        verification_status: "VERIFIED",
        therapeutic_indication: "Nootropic & focus support"
      },
      {
        name: "Tulsi",
        botanical: "Ocimum sanctum",
        quantity: "50 mg",
        standardization: "2.5% Ursolic Acid",
        status: "VERIFIED",
        source: "Sushruta Samhita Sutra Sthana",
        verification_status: "VERIFIED",
        therapeutic_indication: "Stress resilience & bio-wellness support"
      },
      {
        name: "Haridra",
        botanical: "Curcuma longa",
        quantity: "45 mg",
        standardization: "95% Curcuminoids",
        status: "VERIFIED",
        source: "Astanga Hridaya",
        verification_status: "VERIFIED",
        therapeutic_indication: "Cellular wellness & balance support"
      },
      {
        name: "Maricha",
        botanical: "Piper nigrum",
        quantity: "5 mg",
        standardization: "95% Piperine",
        status: "VERIFIED",
        source: "Charaka Samhita",
        verification_status: "VERIFIED",
        therapeutic_indication: "Bio-enhancer strategy under evaluation"
      }
    ],
    intended_use: [
      "Cognitive wellness & focus support",
      "Adaptogenic stress & vitality support",
      "Memory & mental clarity support"
    ],
    process: "Standardized botanical extract fractions prepared using controlled extraction and phytochemical standardization parameters, followed by staged blending and dry granulation into a defined oral capsule formulation. The formulation includes hydro-ethanolic extraction, HPLC phytochemical fingerprinting, staged blending, and dry granulation, incorporating a defined piperine-containing bio-enhancement strategy for intelligence evaluation.",
    claims: [
      "Cognitive wellness & focus support",
      "Adaptogenic stress & vitality support",
      "Memory & mental clarity support"
    ],
    brand: "AYUR-INTEL Showcase",
    packaging: "Blister pack in outer carton with moisture barrier (500 mg per capsule)",
    notes: "A quantitative multi-botanical formulation combining standardized extract fractions of adaptogenic and cognitive-support botanicals with a defined piperine-containing bio-enhancement strategy and controlled extraction / standardization characteristics for improved formulation consistency and delivery characteristics.",
    id: "demo-001",
    public_id: "demo-001",
    is_demo: true,
    ai_normalized: true
  };

  // ----------------------------------------------------------------
  // Initialize Passport Data — ZERO DEFAULT SELECTIONS
  // ----------------------------------------------------------------

  function initPassportData(existingCase) {
    var c = (existingCase && typeof existingCase === "object") ? existingCase : {};

    var ingredients = [];
    if (c.ingredients && Array.isArray(c.ingredients)) {
      ingredients = c.ingredients.map(function (ing) {
        if (typeof ing === "string") return { name: ing, botanical: "", quantity: null, status: "USER_PROVIDED" };
        return {
          name: ing.name || "",
          botanical: ing.botanical || ing.botanical_name || "",
          quantity: ing.quantity || null,
          status: ing.status || (ing.botanical ? "IDENTIFIED" : "USER_PROVIDED")
        };
      });
    }

    state.passportData = {
      id: c.id || c.public_id || null,
      name: c.name || "",
      product_type: c.product_type || null, // ZERO DEFAULT
      description: c.description || "",
      normalized_description: c.normalized_description || "",
      product_suggestions: c.product_suggestions || [],
      reference_context: c.reference_context || "", // Optional benchmark context
      ingredients: ingredients, // ZERO DEFAULT INGREDIENTS
      form: c.form || null, // ZERO DEFAULT
      intended_use: Array.isArray(c.intended_use) ? c.intended_use : (c.intended_use ? [c.intended_use] : []), // ZERO DEFAULT
      process: c.process || null, // ZERO DEFAULT
      claims: Array.isArray(c.claims) ? c.claims : (c.claims ? [c.claims] : []), // ZERO DEFAULT
      jurisdictions: ["IN"], // INDIA ONLY
      regulatory_pathway: c.regulatory_pathway || null,
      notes: c.notes || "",
      is_demo: Boolean(c.is_demo),
      is_normalizing: false,
      ai_normalized: Boolean(c.ai_normalized),
      activeBotanicalCard: null, // Holds botanical currently selected for quantity popup modal
      activeSuggestionModal: null // Holds suggestion currently displayed in detail popup modal
    };

    state.passportStep = 0;
  }

  function initDemoPassport(demoCase) {
    var data = demoCase || DEMO_PASSPORT_DATA;
    initPassportData(data);
    state.passportStep = CONV_STEPS.length - 1; // Direct jump to Review / Completed Passport screen
  }

  // Helper to generate dynamic formulation / product suggestions based on ingredients
  function getFormulationSuggestions(ingredients, existingSuggestions) {
    if (existingSuggestions && Array.isArray(existingSuggestions) && existingSuggestions.length > 0) {
      return existingSuggestions;
    }
    var list = ingredients || [];
    if (list.length === 0) {
      return [];
    }
    var names = list.map(function (i) { return (i.name || "").trim(); }).filter(Boolean);
    if (names.length === 0) {
      return [];
    }

    var herbCombo = names.slice(0, 2).join(" & ");
    var suggestions = [];
    var namesLower = names.map(function (n) { return n.toLowerCase(); });

    if (namesLower.some(function(n){ return n.includes("ashwagandha") || n.includes("brahmi") || n.includes("shankhpushpi") || n.includes("jatamansi"); })) {
      suggestions.push(herbCombo + " Stress Relief & Focus Capsules");
      suggestions.push(herbCombo + " Cognitive Support Formula");
    }
    if (namesLower.some(function(n){ return n.includes("tulsi") || n.includes("turmeric") || n.includes("haridra") || n.includes("haldi") || n.includes("giloy") || n.includes("amla"); })) {
      suggestions.push(herbCombo + " Immunity & Defense Elixir");
      suggestions.push(herbCombo + " Daily Defense Tablets");
    }
    if (namesLower.some(function(n){ return n.includes("shatavari") || n.includes("triphala") || n.includes("mulethi") || n.includes("neem"); })) {
      suggestions.push(herbCombo + " Digestive Wellness & Balance Churna");
      suggestions.push(herbCombo + " Rejuvenating Detox Formula");
    }

    if (suggestions.length === 0) {
      suggestions.push(herbCombo + " Vitality & Balance Capsules");
      suggestions.push("Standardized " + herbCombo + " Herbal Extract");
    }
    return suggestions.slice(0, 4);
  }

  function getFormulationSuggestionsDetailed(ingredients, existingSuggestions) {
    var raw = getFormulationSuggestions(ingredients, existingSuggestions);
    var list = ingredients || [];
    var herbNames = list.map(function (i) { return i.name || ""; }).filter(Boolean);
    var herbStr = herbNames.length > 0 ? herbNames.join(", ") : "Ayurvedic Botanicals";

    return raw.map(function (item) {
      if (typeof item === "object" && item && item.name) {
        return {
          name: item.name,
          ingredientsText: item.ingredientsText || herbStr,
          description: item.description || "Synergistic Ayurvedic formulation engineered for therapeutic efficacy and regulatory safety."
        };
      }
      var name = String(item);
      var desc = "A synergistic Ayurvedic formulation designed for holistic therapeutic balance, standardized active extracts, and regulatory compliance.";
      if (name.toLowerCase().indexOf("medhya") !== -1 || name.toLowerCase().indexOf("focus") !== -1) {
        desc = "A classical Ayurvedic Medhya Rasayana formulation supporting cognitive vitality, neurotransmitter balance, memory, and nervous system nourishment.";
      } else if (name.toLowerCase().indexOf("kwatha") !== -1 || name.toLowerCase().indexOf("immunity") !== -1) {
        desc = "A traditional immune-modulating Ayurvedic decoction / infusion supporting respiratory wellness, cellular defense, and natural vitality.";
      } else if (name.toLowerCase().indexOf("digestive") !== -1 || name.toLowerCase().indexOf("gut") !== -1) {
        desc = "A tri-doshic digestive balancing formulation supporting optimal Agni (digestive fire), bioavailability, and natural gut health.";
      }
      return {
        name: name,
        ingredientsText: herbStr,
        description: desc
      };
    });
  }

  // ----------------------------------------------------------------
  // Main Render: Conversational Wizard (7 Steps) & Review Screen
  // ----------------------------------------------------------------

  function renderPassportWizard() {
    var pd = state.passportData;
    if (!pd) {
      initPassportData();
      pd = state.passportData;
    }

    var stepIdx = state.passportStep || 0;
    var stepDef = CONV_STEPS[stepIdx] || CONV_STEPS[0];
    var isReview = stepDef.key === "review" || stepIdx === CONV_STEPS.length - 1;

    if (isReview) {
      return renderPassportReviewScreen(pd);
    }

    var totalQuestions = CONV_STEPS.length - 1; // Exactly 7 questions
    var currentNum = stepIdx + 1;
    var progressPct = Math.round((currentNum / totalQuestions) * 100);

    var stepContentHtml = "";
    if (stepDef.key === "category") stepContentHtml = renderStepCategory(pd);
    else if (stepDef.key === "name") stepContentHtml = renderStepName(pd);
    else if (stepDef.key === "description") stepContentHtml = renderStepDescription(pd);
    else if (stepDef.key === "ingredients") stepContentHtml = renderStepIngredients(pd);
    else if (stepDef.key === "intended_use") stepContentHtml = renderStepIntendedUse(pd);
    else if (stepDef.key === "process") stepContentHtml = renderStepProcess(pd);
    else if (stepDef.key === "claims") stepContentHtml = renderStepClaims(pd);

    var isFirst = stepIdx === 0;

    return ''
      + '<div class="conv-wizard-container">'
      + '<div class="conv-assistant-header">'
      + '<div class="conv-assistant-badge">' + icon("psychology", 16) + ' Product Passport Assistant</div>'
      + '<button class="btn btn-ghost btn-sm" id="conv-exit-btn">' + icon("close", 14) + ' Exit to Dashboard</button>'
      + '</div>'

      + '<div class="conv-progress-wrap">'
      + '<div class="conv-progress-meta">'
      + '<span>' + esc(stepDef.tag) + ': ' + esc(stepDef.title) + '</span>'
      + '<span>' + progressPct + '% Complete</span>'
      + '</div>'
      + '<div class="conv-progress-track"><div class="conv-progress-bar" style="width:' + progressPct + '%"></div></div>'
      + '</div>'

      + '<div class="conv-question-card">'
      + '<div class="conv-step-tag">' + icon("spa", 14) + ' ' + esc(stepDef.tag) + '</div>'
      + '<h1 class="conv-question-title">' + esc(stepDef.title) + '</h1>'
      + '<p class="conv-question-desc">' + esc(stepDef.desc) + '</p>'
      + stepContentHtml
      + '</div>'

      + '<div class="conv-nav-bar">'
      + (isFirst ? '<div></div>' : '<button class="conv-btn-back" id="conv-back-btn">' + icon("arrow_back", 16) + ' Back</button>')
      + '<div style="display:flex;gap:10px;align-items:center;">'
      + (pd.id ? '<button type="button" class="btn btn-secondary btn-sm" id="conv-jump-review-btn">📋 Return to Review</button>' : '')
      + '<button class="btn btn-ghost btn-sm" id="conv-skip-btn">Skip for now</button>'
      + '<button class="conv-btn-continue" id="conv-next-btn">Continue ' + icon("arrow_forward", 16) + '</button>'
      + '</div></div>'
      + '</div>'
      + renderSuggestionModalHtml(pd);
  }

  // Shared Helper for Suggestion Detail Modal
  function renderSuggestionModalHtml(pd) {
    if (!pd || !pd.activeSuggestionModal) return "";
    var sm = pd.activeSuggestionModal;
    return '<div class="ing-modal-overlay" id="sugg-modal-overlay">'
      + '<div class="ing-modal-card" style="max-width:500px;">'
      + '<div class="ing-modal-head">'
      + '<div class="ing-modal-title-wrap">'
      + '<span class="ing-modal-icon">💡</span>'
      + '<div>'
      + '<h3 class="ing-modal-name" style="font-size:16px;">Product Suggestion</h3>'
      + '<span class="ing-modal-latin" style="color:#a5b4fc;">Formulation Innovation & Line Extension</span>'
      + '</div>'
      + '</div>'
      + '<button class="ing-modal-close-btn" id="conv-cancel-sugg-modal" aria-label="Close">&times;</button>'
      + '</div>'
      + '<div class="ing-modal-body" style="padding:16px 0;">'
      + '<h2 id="sugg-modal-product-name" style="font-size:19px;font-weight:700;color:#ffffff;margin-bottom:12px;line-height:1.3;">'
      + esc(sm.name)
      + '</h2>'
      + '<div style="margin-bottom:12px;">'
      + '<div style="font-size:11px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px;">Ingredients Used</div>'
      + '<div id="sugg-modal-ingredients" style="font-size:13px;color:#34d399;font-weight:500;">🌿 ' + esc(sm.ingredientsText || "Active Ayurvedic Botanicals") + '</div>'
      + '</div>'
      + '<div>'
      + '<div style="font-size:11px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px;">Description</div>'
      + '<div id="sugg-modal-description" style="font-size:13px;color:#e2e8f0;line-height:1.5;">' + esc(sm.description || "Synergistic traditional formulation developed for therapeutic balance.") + '</div>'
      + '</div>'
      + '</div>'
      + '<div class="ing-modal-foot">'
      + '<button class="btn btn-ghost btn-sm" id="conv-close-sugg-btn">Close</button>'
      + '<button class="btn btn-primary btn-sm" id="conv-use-sugg-btn">'
      + icon("check", 16) + ' Use This Name'
      + '</button>'
      + '</div>'
      + '</div>'
      + '</div>';
  }

  // Step 1: Category (ZERO default selection)
  function renderStepCategory(pd) {
    var categories = [
      { id: "Ayurvedic Product", title: "Ayurvedic Product", sub: "Classical or proprietary Ayurvedic formulation", icon: "science" },
      { id: "Herbal Product", title: "Herbal Product", sub: "Plant-based herbal & botanical formulation", icon: "eco" },
      { id: "Herbal Supplement", title: "Herbal Supplement", sub: "Nutraceutical or dietary supplement", icon: "medication" },
      { id: "Functional Food / Beverage", title: "Food / Beverage", sub: "Herbal tea, health drink, wellness powder", icon: "local_cafe" },
      { id: "Cosmetic / Personal Care", title: "Cosmetic / Personal Care", sub: "Herbal skincare, haircare, topicals", icon: "spa" },
      { id: "Other", title: "Something Else", sub: "Custom traditional or hybrid formulation", icon: "category" }
    ];

    var html = '<div class="conv-options-grid">';
    categories.forEach(function (cat) {
      var isSelected = pd.product_type === cat.id;
      html += '<div class="conv-option-card ' + (isSelected ? "selected" : "") + '" data-val="' + esc(cat.id) + '">'
        + '<div class="conv-option-icon">' + icon(cat.icon, 24) + '</div>'
        + '<div>'
        + '<div class="conv-option-title">' + esc(cat.title) + '</div>'
        + '<div class="conv-option-sub">' + esc(cat.sub) + '</div>'
        + '</div></div>';
    });
    html += '</div>';

    var isOther = pd.product_type === "Other" || (pd.product_type && categories.every(function(c){ return c.id !== pd.product_type; }));
    html += '<div id="conv-category-custom" style="display:' + (isOther ? "block" : "none") + ';margin-top:16px;">'
      + '<label class="form-label" style="font-size:12px;margin-bottom:6px;display:block;">Specify your product category:</label>'
      + '<input class="form-input" type="text" id="conv-category-text" value="' + (isOther && pd.product_type !== "Other" ? esc(pd.product_type) : "") + '" placeholder="e.g. Traditional Ayurvedic Extract">'
      + '</div>';

    return html;
  }

  // Step 2: Name
  function renderStepName(pd) {
    return '<div class="conv-input-wrap">'
      + '<label class="form-label" style="font-weight:600;margin-bottom:8px;display:block;">Product Name</label>'
      + '<input class="form-input" type="text" id="conv-name-input" value="' + esc(pd.name) + '" placeholder="e.g. Ashwagandha Calm & Restore Capsules" style="font-size:16px;padding:14px 16px;" autofocus>'
      + '<div class="conv-lang-hint">'
      + '<span>Can be a brand name, project code, or descriptive working name. Press Enter to continue.</span>'
      + '</div>'
      + '</div>';
  }

  // Step 3: Description + Structure with AI + Optional Benchmark Reference
  function renderStepDescription(pd) {
    var isNormalizing = pd.is_normalizing;
    var normDesc = pd.normalized_description || "";
    return '<div class="conv-input-wrap">'
      + '<label class="form-label" style="font-weight:600;margin-bottom:8px;display:block;">Product Description (Original)</label>'
      + '<textarea class="conv-textarea" id="conv-desc-input" placeholder="Example: Yeh ek Ayurvedic herbal capsule formulation hai jisme Ashwagandha ko primary ingredient ke roop mein use kiya gaya hai for stress management and mental balance.">' + esc(pd.description) + '</textarea>'
      + '<div class="conv-lang-hint">'
      + '<span>Type in Hindi, English, Hinglish, or mixed language. Enter inside textarea creates normal newlines.</span>'
      + '<span class="conv-lang-pill">' + icon("translate", 12) + ' Multilingual AI Structuring</span>'
      + '</div>'
      + '</div>'
      + '<div class="conv-ai-banner">'
      + icon("psychology", 20)
      + '<div style="flex:1;">'
      + '<strong>Structure with AI:</strong> Translates & structures botanical ingredients, dosage form, intended use, and claims into professional English.'
      + '</div>'
      + '<button class="btn btn-secondary btn-sm" id="conv-normalize-btn" ' + (isNormalizing ? "disabled" : "") + '>'
      + (isNormalizing ? icon("hourglass_empty", 14) + " Structuring..." : icon("auto_awesome", 14) + " Structure with AI")
      + '</button>'
      + '</div>'
      + '<div id="conv-desc-normalized-wrap" class="conv-normalized-preview" style="display:' + (normDesc ? 'block' : 'none') + ';">'
      + '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">'
      + '<div style="display:flex;align-items:center;gap:6px;font-size:12px;font-weight:600;color:#34d399;">'
      + icon("auto_awesome", 15) + ' 📝 Structured English Description'
      + '</div>'
      + '<span class="chip" style="font-size:10px;background:rgba(52,211,153,0.15);color:#34d399;">AI Translation</span>'
      + '</div>'
      + '<div id="conv-desc-normalized-text" style="font-size:13px;color:#f1f5f9;line-height:1.5;">' + esc(normDesc) + '</div>'
      + '</div>'
      + '<div style="margin-top:16px;">'
      + '<label class="form-label" style="font-size:12px;margin-bottom:6px;display:block;color:#94a3b8;">Known Benchmark Product / Classical Reference (Optional):</label>'
      + '<input class="form-input" type="text" id="conv-reference-input" value="' + esc(pd.reference_context || '') + '" placeholder="e.g. Classical text reference, Charaka Samhita, or benchmark product (Optional)" style="font-size:13px;padding:10px 14px;">'
      + '</div>';
  }

  // Step 4: Ingredients & Botanicals (Zero Defaults, Floating Quantity Modal Popup)
  function renderStepIngredients(pd) {
    var ingredients = pd.ingredients || [];
    var activeBot = pd.activeBotanicalCard;

    var html = '<div style="margin-bottom:16px;">'
      + '<label class="form-label" style="font-weight:600;margin-bottom:8px;display:block;">Select Common Ayurvedic Botanicals (Click to specify quantity):</label>'
      + '<div class="conv-chips-wrap">';

    POPULAR_BOTANICALS.forEach(function (bot) {
      var isAdded = ingredients.some(function (ing) {
        return (ing.name || "").toLowerCase() === bot.name.toLowerCase() ||
               (ing.botanical || "").toLowerCase() === bot.botanical.toLowerCase();
      });

      html += '<div class="conv-chip ' + (isAdded ? "selected" : "") + '" data-bot-name="' + esc(bot.name) + '" data-bot-latin="' + esc(bot.botanical) + '">'
        + '<span>' + bot.emoji + '</span>'
        + '<strong>' + esc(bot.name) + '</strong>'
        + '<small style="opacity:0.8;font-style:italic;">(' + esc(bot.botanical) + ')</small>'
        + (isAdded ? icon("check", 14) : icon("add", 14))
        + '</div>';
    });
    html += '</div></div>';

    // Quantity Popup Floating Modal
    if (activeBot) {
      html += '<div class="ing-modal-overlay" id="ing-modal-overlay">'
        + '<div class="ing-modal-card">'
        + '<div class="ing-modal-head">'
        + '<div class="ing-modal-title-wrap">'
        + '<span class="ing-modal-icon">' + (activeBot.emoji || "🌿") + '</span>'
        + '<div>'
        + '<h3 class="ing-modal-name">' + esc(activeBot.name) + '</h3>'
        + '<span class="ing-modal-latin">' + esc(activeBot.botanical || "Ayurvedic Botanical") + '</span>'
        + '</div>'
        + '</div>'
        + '<button class="ing-modal-close-btn" id="conv-cancel-bot-card" aria-label="Close">&times;</button>'
        + '</div>'
        + '<div class="ing-modal-body">'
        + '<label class="form-label" for="conv-ing-card-qty" style="font-weight:600;font-size:13px;margin-bottom:6px;display:block;">Quantity / Dosage (Optional)</label>'
        + '<input type="text" class="form-input" id="conv-ing-card-qty" value="' + esc(activeBot.initialQty || '') + '" placeholder="e.g. 500 mg (Optional)" autocomplete="off" autofocus oninput="validateQuantityInput(this)" />'
        + '<div style="font-size:11px;color:#94a3b8;margin-top:6px;">Leave blank for \'Add Qty\', or enter dosage, then press Enter to confirm.</div>'
        + '</div>'
        + '<div class="ing-modal-foot">'
        + '<button class="btn btn-ghost btn-sm" id="conv-cancel-bot-btn">Cancel</button>'
        + '<button class="btn btn-primary btn-sm" id="conv-ing-card-confirm">'
        + icon("check_circle", 16) + ' Confirm (Enter)'
        + '</button>'
        + '</div>'
        + '</div>'
        + '</div>';
    }

    // Custom Ingredient Box
    html += '<div style="margin-bottom:20px;padding:16px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:14px;">'
      + '<label class="form-label" style="font-weight:600;font-size:13px;margin-bottom:8px;display:block;">Add Custom Ingredient (e.g. "tulsi ka extract", "50 mg"):</label>'
      + '<div style="display:flex;gap:8px;flex-wrap:wrap;">'
      + '<input class="form-input" type="text" id="conv-custom-ing-name" placeholder="Ingredient name (e.g. tulsi ka extract)" style="flex:2;min-width:180px;">'
      + '<input class="form-input" type="text" id="conv-custom-ing-qty" placeholder="Quantity optional (e.g. 50 mg)" style="flex:1;min-width:120px;" oninput="validateQuantityInput(this)">'
      + '<button class="btn btn-primary btn-sm" id="conv-add-ing-btn">' + icon("add", 16) + ' Add Custom (Enter)</button>'
      + '</div>'
      + '</div>';

    // Dynamic Formulation Suggestions ("What can you make with these ingredients")
    var suggestions = getFormulationSuggestionsDetailed(ingredients, pd.product_suggestions);
    if (suggestions && suggestions.length > 0) {
      html += '<div class="conv-suggestions-card" style="margin-bottom:20px;">'
        + '<div class="conv-suggestions-head">'
        + '<div class="conv-suggestions-title">' + icon("lightbulb", 16) + ' What can you make with these ingredients?</div>'
        + '<span style="font-size:11px;color:#94a3b8;">Click suggestion to view details & apply name</span>'
        + '</div>'
        + '<div class="conv-suggestions-grid">';
      suggestions.forEach(function (sugg, sIdx) {
        html += '<button type="button" class="conv-suggestion-card-btn" data-sugg-idx="' + sIdx + '">'
          + '<div style="font-weight:600;display:flex;align-items:center;gap:6px;">' + icon("auto_awesome", 14) + ' ' + esc(sugg.name) + '</div>'
          + '<div style="font-size:11.5px;color:#a5b4fc;opacity:0.9;">(' + esc(sugg.ingredientsText) + ')</div>'
          + '</button>';
      });
      html += '</div></div>';
    }

    // Formulation Ingredients List with DRAVYA Eligibility Badges
    var verifiedCount = 0;
    ingredients.forEach(function(ing) {
      if (ing.eligibility && ing.eligibility.verified) verifiedCount++;
    });

    html += '<div style="margin-top:16px;">'
      + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
      + '<label class="form-label" style="font-weight:600;margin:0;">Formulation Ingredients (' + ingredients.length + '):</label>'
      + (ingredients.length > 0 ? '<span class="chip" style="font-weight:700;font-size:11px;background:rgba(46,204,113,0.15);color:#2ecc71;border:1px solid rgba(46,204,113,0.3);">' + verifiedCount + '/' + ingredients.length + ' Verified ✅</span>' : '')
      + '</div>';

    if (ingredients.length === 0) {
      html += '<div style="padding:16px;text-align:center;color:var(--text-secondary);border:1.5px dashed rgba(255,255,255,0.1);border-radius:12px;">'
        + 'No ingredients selected yet. Click any botanical chip above to specify quantity, or add custom ingredients.'
        + '</div>';
    } else {
      ingredients.forEach(function (ing, idx) {
        var el = ing.eligibility;
        var badgeHTML = '';
        if (el) {
          var lvl = el.eligibility_level || 'NOT FOUND';
          var badgeClass = lvl.toLowerCase().replace(' ', '_');
          var badgeText = el.verified ? ('✅ ' + lvl) : (lvl === 'LOW' ? '⚠️ PARTIAL' : '❌ NOT FOUND');
          if (el.schedule_e1) badgeText = '⚠️ SCHEDULE E-1';
          badgeHTML = '<span class="eligibility-badge ' + badgeClass + '" style="cursor:pointer;" onclick="if(window.showIngredientPopup)window.showIngredientPopup(\'' + esc(ing.name).replace(/'/g, "\\'") + '\', \'' + esc(ing.botanical || '').replace(/'/g, "\\'") + '\', \'' + esc(ing.quantity || '').replace(/'/g, "\\'") + '\');">' + esc(badgeText) + '</span>';
        } else {
          // Asynchronously trigger eligibility check if not cached
          fetch('/api/ingredients/eligibility/' + encodeURIComponent(ing.name))
            .then(function(r){ return r.json(); })
            .then(function(data){ ing.eligibility = data; if(window.AYUR && typeof window.AYUR.render === 'function') window.AYUR.render(); })
            .catch(function(e){});
          badgeHTML = '<span class="eligibility-badge low" style="opacity:0.6;">Checking...</span>';
        }

        html += '<div class="conv-ing-item" style="cursor:pointer;" onclick="if(event.target.tagName!==\'BUTTON\' && window.showIngredientPopup)window.showIngredientPopup(\'' + esc(ing.name).replace(/'/g, "\\'") + '\', \'' + esc(ing.botanical || '').replace(/'/g, "\\'") + '\', \'' + esc(ing.quantity || '').replace(/'/g, "\\'") + '\');">'
          + '<div class="conv-ing-main" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">'
          + '<span class="conv-ing-name">🌿 ' + esc(ing.name) + '</span>'
          + (ing.botanical ? '<span class="conv-ing-botanical">(' + esc(ing.botanical) + ')</span>' : '')
          + badgeHTML
          + (ing.quantity ? (
              '<button type="button" class="conv-qty-badge" data-edit-ing-idx="' + idx + '" title="Click to edit quantity">' + esc(ing.quantity) + '</button>'
            ) : (
              '<button type="button" class="conv-qty-badge empty" data-edit-ing-idx="' + idx + '" title="Click to add quantity">+ Add Qty</button>'
            ))
          + '</div>'
          + '<button class="btn btn-ghost btn-sm conv-remove-ing" data-idx="' + idx + '" title="Remove ingredient" style="color:#f87171;">' + icon("delete", 16) + '</button>'
          + '</div>';
      });
    }
    html += '</div>';

    return html;
  }

  // Step 5: Intended Use & Indications (ZERO default selection)
  function renderStepIntendedUse(pd) {
    var selectedUses = pd.intended_use || [];
    var useOptions = [
      { id: "Stress Relief & Relaxation", title: "Stress & Relaxation", icon: "self_improvement" },
      { id: "Cognitive Health & Focus", title: "Brain & Focus", icon: "psychology" },
      { id: "Immunity & Defense", title: "Immunity & Defense", icon: "shield" },
      { id: "Digestive Health & Gut Support", title: "Digestion & Gut", icon: "nutrition" },
      { id: "Energy & Vitality", title: "Energy & Vitality", icon: "bolt" },
      { id: "Skin & Beauty Care", title: "Skin & Beauty", icon: "face" },
      { id: "Sleep & Calming Support", title: "Sleep & Rest", icon: "bedtime" },
      { id: "General Wellness & Longevity", title: "General Longevity (Rasayana)", icon: "spa" },
      { id: "Joint & Muscle Comfort", title: "Joint & Muscle", icon: "accessibility" }
    ];

    var html = '<div class="conv-options-grid">';
    useOptions.forEach(function (opt) {
      var isSelected = selectedUses.indexOf(opt.id) !== -1;
      html += '<div class="conv-option-card ' + (isSelected ? "selected" : "") + '" data-use-id="' + esc(opt.id) + '">'
        + '<div class="conv-option-icon">' + icon(opt.icon, 22) + '</div>'
        + '<div>'
        + '<div class="conv-option-title">' + esc(opt.title) + '</div>'
        + '</div></div>';
    });
    html += '</div>';

    html += '<div style="margin-top:16px;">'
      + '<label class="form-label" style="font-size:12px;margin-bottom:6px;display:block;">Add custom health indication (Supports Hindi/Hinglish e.g. "mental balance ke liye"):</label>'
      + '<input class="form-input" type="text" id="conv-custom-use" placeholder="e.g. Mental balance & daily stress management">'
      + '</div>';

    return html;
  }

  // Step 6: Process & Preparation (ZERO default selection)
  function renderStepProcess(pd) {
    var processes = [
      { id: "Simple mixing / blending", title: "Simple Mixing & Blending", sub: "Dry blending of powders and natural botanicals", icon: "blender" },
      { id: "Powdering / grinding", title: "Fine Powdering / Churna", sub: "Micronization, traditional fine milling", icon: "grain" },
      { id: "Standardized Extraction", title: "Standardized Extraction", sub: "HPLC-verified standardized active extract", icon: "science" },
      { id: "Classical Fermentation", title: "Classical Fermentation", sub: "Asava / Arishta natural bio-fermentation", icon: "liquor" },
      { id: "Heating / decoction", title: "Aqueous Decoction / Kwatha", sub: "Boiling, aqueous extraction, Snehapaka oil processing", icon: "local_fire_department" },
      { id: "Standard Ayurvedic preparation", title: "Standard Ayurvedic Process", sub: "Traditional classical method", icon: "help_outline" }
    ];

    var html = '<div class="conv-options-grid">';
    processes.forEach(function (proc) {
      var isSelected = pd.process === proc.id || pd.process === proc.title;
      html += '<div class="conv-option-card ' + (isSelected ? "selected" : "") + '" data-proc-id="' + esc(proc.id) + '">'
        + '<div class="conv-option-icon">' + icon(proc.icon, 22) + '</div>'
        + '<div>'
        + '<div class="conv-option-title">' + esc(proc.title) + '</div>'
        + '<div class="conv-option-sub">' + esc(proc.sub) + '</div>'
        + '</div></div>';
    });
    html += '</div>';

    html += '<div style="margin-top:16px;">'
      + '<label class="form-label" style="font-weight:600;font-size:13px;margin-bottom:6px;display:block;">Additional Process Details (Optional):</label>'
      + '<textarea class="conv-textarea" id="conv-process-details" style="min-height:80px;" placeholder="e.g. Standardized aqueous-alcoholic extract manufactured in a GMP-certified Ayurvedic unit.">' + esc(pd.process || "") + '</textarea>'
      + '</div>';

    return html;
  }

  // Step 7: Claims (ZERO default selection)
  function renderStepClaims(pd) {
    var claims = pd.claims || [];
    var claimSuggestions = [
      "Supports stress management & relaxation",
      "Enhances cognitive function & mental clarity",
      "Promotes digestive health & gut balance",
      "Supports natural immune defense",
      "Promotes restful & restorative sleep",
      "Helps maintain natural vitality & energy"
    ];

    var html = '<div style="margin-bottom:16px;">'
      + '<label class="form-label" style="font-weight:600;margin-bottom:8px;display:block;">Select Common Benefit Claims (NO defaults selected):</label>'
      + '<div class="conv-chips-wrap">';

    claimSuggestions.forEach(function (claim) {
      var isSelected = claims.indexOf(claim) !== -1;
      html += '<div class="conv-chip ' + (isSelected ? "selected" : "") + '" data-claim-text="' + esc(claim) + '">'
        + '<span>💬</span> ' + esc(claim)
        + (isSelected ? icon("check", 14) : icon("add", 14))
        + '</div>';
    });
    html += '</div></div>';

    html += '<div style="margin-bottom:20px;padding:16px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:14px;">'
      + '<label class="form-label" style="font-weight:600;font-size:13px;margin-bottom:6px;display:block;">Add Custom Benefit Claim:</label>'
      + '<div style="display:flex;gap:8px;">'
      + '<input class="form-input" type="text" id="conv-custom-claim" placeholder="e.g. Promotes calming focus and physical stamina" style="flex:1;">'
      + '<button class="btn btn-primary btn-sm" id="conv-add-claim-btn">' + icon("add", 16) + ' Add Claim</button>'
      + '</div>'
      + '</div>';

    html += '<div style="margin-top:16px;">'
      + '<label class="form-label" style="font-weight:600;margin-bottom:8px;display:block;">Proposed Claims to Analyze (' + claims.length + '):</label>';

    if (claims.length === 0) {
      html += '<div style="padding:14px;text-align:center;color:var(--text-secondary);border:1.5px dashed rgba(255,255,255,0.1);border-radius:12px;">No claims specified yet.</div>';
    } else {
      claims.forEach(function (clm, idx) {
        html += '<div class="conv-ing-item">'
          + '<div class="conv-ing-main">'
          + '<span class="conv-ing-name">💬 "' + esc(clm) + '"</span>'
          + '</div>'
          + '<button class="btn btn-ghost btn-sm conv-remove-claim" data-idx="' + idx + '" title="Remove claim" style="color:#f87171;">' + icon("delete", 16) + '</button>'
          + '</div>';
      });
    }
    html += '</div>';

    return html;
  }

  // ----------------------------------------------------------------
  // PRODUCT PASSPORT REVIEW & INDIAN PATENT INTELLIGENCE STAGE
  // ----------------------------------------------------------------

  function renderPassportReviewScreen(pd) {
    var name = pd.name || "Ashwagandha Calm & Restore Capsules";
    var productType = pd.product_type || "Ayurvedic Product";
    var ingredients = pd.ingredients || [];
    var claims = pd.claims || [];
    var uses = pd.intended_use || [];

    var html = ''
      + '<div class="conv-wizard-container" style="max-width:920px;">'
      + '<div class="conv-assistant-header">'
      + '<div class="conv-assistant-badge">' + icon("verified", 16) + ' Product Passport Generated • Indian Patent Ready</div>'
      + '<button class="btn btn-ghost btn-sm" id="passport-edit-all-btn">' + icon("edit", 14) + ' Edit Questionnaire</button>'
      + '</div>'

      + '<div class="passport-review-card">'
      + '<div class="passport-review-header">'
      + '<div>'
      + '<div class="passport-review-category">' + icon("spa", 14) + ' ' + esc(productType) + ' • 🇮🇳 India Scope</div>'
      + '<div style="display:flex;align-items:center;gap:10px;margin-top:8px;flex-wrap:wrap;">'
      + '<h1 class="passport-review-title" style="margin:0;">' + esc(name) + '</h1>'
      + '<button class="passport-edit-btn" data-jump-step="1" title="Edit Product Name">' + icon("edit", 12) + ' Edit Name</button>'
      + '</div>'
      + '<div style="font-size:13px;opacity:0.9;margin-top:6px;">Structured product identity & Indian patent landscape readiness baseline.</div>'
      + '</div>'
      + '<div style="text-align:right;">'
      + '<span class="confidence-badge confidence-high" style="font-size:13px;padding:6px 14px;">Passport Complete</span>'
      + '</div>'
      + '</div>'

      + '<div class="passport-review-grid">'

      // Product Form & Identity
      + '<div class="passport-section-card">'
      + '<div class="passport-section-head">'
      + '<div class="passport-section-title">' + icon("inventory_2", 16) + ' Product Identity & Category</div>'
      + '<button class="passport-edit-btn" data-jump-step="0">' + icon("edit", 12) + ' Edit Category</button>'
      + '</div>'
      + '<div class="passport-value-text">' + esc(productType) + '</div>'
      + '<div style="margin-top:8px;font-size:13px;color:var(--text-secondary);">'
      + '<strong>Dosage Form:</strong> ' + ((pd.form || pd.product_type) ? esc(pd.form || pd.product_type) : '<span style="color:var(--text-tertiary);font-style:italic;">Not specified</span>')
      + '</div>'
      + (pd.description ? '<div style="margin-top:8px;font-size:13px;color:var(--text-secondary);display:flex;justify-content:space-between;align-items:flex-start;gap:8px;"><div><strong>Description:</strong> ' + esc(pd.description) + '</div><button class="passport-edit-btn" data-jump-step="2" style="flex-shrink:0;">' + icon("edit", 12) + ' Edit</button></div>' : '<div style="margin-top:8px;"><button class="passport-edit-btn" data-jump-step="2">' + icon("edit", 12) + ' Add Description</button></div>')
      + (pd.normalized_description ? '<div style="margin-top:10px;padding:8px 10px;background:rgba(52,211,153,0.08);border-left:2px solid #34d399;border-radius:4px;font-size:12px;color:#e2e8f0;line-height:1.4;"><strong>AI Structured:</strong> ' + esc(pd.normalized_description) + '</div>' : '')
      + '</div>'

      // Target Market Scope (Fixed National Jurisdiction)
      + '<div class="passport-section-card">'
      + '<div class="passport-section-head">'
      + '<div class="passport-section-title">' + icon("flag", 16) + ' Market Scope</div>'
      + '</div>'
      + '<div>'
      + '<span class="passport-badge-tag">🇮🇳 India (AYUSH / FSSAI)</span>'
      + '</div>'
      + '<div style="margin-top:8px;font-size:12px;color:#94a3b8;">Focused exclusively on the Indian patent & regulatory ecosystem.</div>'
      + '</div>'

      // Ingredients Table
      + '<div class="passport-section-card full-width">'
      + '<div class="passport-section-head">'
      + '<div class="passport-section-title">' + icon("eco", 16) + ' Formulation Ingredients (' + ingredients.length + ')</div>'
      + '<button class="passport-edit-btn" data-jump-step="3">' + icon("edit", 12) + ' Edit</button>'
      + '</div>';

    if (ingredients.length === 0) {
      html += '<p style="color:var(--text-secondary);font-size:13px;padding:8px 0;font-style:italic;">No ingredients specified.</p>';
    } else {
      html += '<table class="passport-ing-table">'
        + '<thead><tr style="text-align:left;font-size:11px;color:var(--text-secondary);text-transform:uppercase;">'
        + '<th style="padding-bottom:8px;">Common Name</th>'
        + '<th style="padding-bottom:8px;">Botanical (Latin) Name</th>'
        + '<th style="padding-bottom:8px;">Dosage / Qty</th>'
        + '<th style="padding-bottom:8px;text-align:right;">Status</th>'
        + '</tr></thead><tbody>';

      ingredients.forEach(function (ing) {
        html += '<tr>'
          + '<td style="padding:8px 0;font-weight:600;">🌿 ' + esc(ing.name) + '</td>'
          + '<td style="padding:8px 0;font-style:italic;color:var(--text-secondary);">' + (ing.botanical ? esc(ing.botanical) : '<span style="color:var(--text-tertiary)">Matched via Rule Engine</span>') + '</td>'
          + '<td style="padding:8px 0;">' + (ing.quantity ? '<span class="chip" style="font-size:11px;background:rgba(52,211,153,0.15);color:#34d399;">' + esc(ing.quantity) + '</span>' : '<span style="color:var(--text-tertiary);font-style:italic;font-size:11px;">Unspecified</span>') + '</td>'
          + '<td style="padding:8px 0;text-align:right;"><span class="chip selected" style="font-size:10px;">' + esc(ing.status || "IDENTIFIED") + '</span></td>'
          + '</tr>';
      });
      html += '</tbody></table>';
    }
    html += '</div>';

    // Formulation Suggestions
    var reviewSuggestions = getFormulationSuggestionsDetailed(ingredients, pd.product_suggestions);
    if (reviewSuggestions && reviewSuggestions.length > 0) {
      html += '<div class="passport-section-card full-width" style="background:rgba(99,102,241,0.06);border:1px solid rgba(99,102,241,0.22);">'
        + '<div class="passport-section-head">'
        + '<div class="passport-section-title" style="color:#a5b4fc;">' + icon("lightbulb", 16) + ' Suggested Product Formulations & Line Extensions</div>'
        + '<span style="font-size:11px;color:#94a3b8;">Click suggestion to view details & apply name</span>'
        + '</div>'
        + '<div class="conv-suggestions-grid" style="margin-top:8px;">';
      reviewSuggestions.forEach(function(sugg, sIdx) {
        html += '<button type="button" class="conv-suggestion-card-btn" data-sugg-idx="' + sIdx + '">'
          + '<div style="font-weight:600;display:flex;align-items:center;gap:6px;">' + icon("auto_awesome", 14) + ' ' + esc(sugg.name) + '</div>'
          + '<div style="font-size:11.5px;color:#a5b4fc;opacity:0.9;">(' + esc(sugg.ingredientsText) + ')</div>'
          + '</button>';
      });
      html += '</div></div>';
    }

    html += ''
      // Intended Uses
      + '<div class="passport-section-card">'
      + '<div class="passport-section-head">'
      + '<div class="passport-section-title">' + icon("self_improvement", 16) + ' Intended Use & Indications</div>'
      + '<button class="passport-edit-btn" data-jump-step="4">' + icon("edit", 12) + ' Edit</button>'
      + '</div>'
      + '<div style="display:flex;flex-wrap:wrap;gap:6px;">';

    if (uses.length === 0) {
      html += '<span style="font-size:13px;color:var(--text-tertiary);font-style:italic;">No indications specified</span>';
    } else {
      uses.forEach(function (u) {
        html += '<span class="passport-badge-tag">🎯 ' + esc(u) + '</span>';
      });
    }
    html += '</div></div>'

      // Process
      + '<div class="passport-section-card">'
      + '<div class="passport-section-head">'
      + '<div class="passport-section-title">' + icon("precision_manufacturing", 16) + ' Preparation & Formulation</div>'
      + '<button class="passport-edit-btn" data-jump-step="5">' + icon("edit", 12) + ' Edit</button>'
      + '</div>'
      + '<div class="passport-value-text" style="font-size:14px;">' + (pd.process ? esc(pd.process) : '<span style="color:var(--text-tertiary);font-style:italic;">Not specified</span>') + '</div>'
      + '</div>'

      // Proposed Claims
      + '<div class="passport-section-card full-width">'
      + '<div class="passport-section-head">'
      + '<div class="passport-section-title">' + icon("chat_bubble", 16) + ' Proposed Claims (' + claims.length + ')</div>'
      + '<button class="passport-edit-btn" data-jump-step="6">' + icon("edit", 12) + ' Edit</button>'
      + '</div>';

    if (claims.length === 0) {
      html += '<p style="color:var(--text-secondary);font-size:13px;font-style:italic;">No claims specified.</p>';
    } else {
      html += '<div style="display:flex;flex-direction:column;gap:8px;">';
      claims.forEach(function (clm) {
        html += '<div style="background:rgba(255,255,255,0.03);border-left:3px solid #34d399;padding:8px 12px;border-radius:6px;font-size:13px;color:#ffffff;">"' + esc(clm) + '"</div>';
      });
      html += '</div>';
    }
    html += '</div>'

      // Final Stage — Indian Patent Intelligence Readiness Preview
      + '<div class="passport-section-card full-width" style="background:rgba(30,58,45,0.6);border:1px solid rgba(52,211,153,0.3);">'
      + '<div class="passport-section-head">'
      + '<div class="passport-section-title" style="color:#34d399;">' + icon("gavel", 16) + ' Final Stage — Indian Patent Intelligence (CGPDTM / IPO)</div>'
      + '<span class="chip" style="background:rgba(52,211,153,0.15);color:#34d399;font-size:11px;">Analytical Research Baseline</span>'
      + '</div>'
      + '<p style="font-size:13px;line-height:1.6;color:#e2e8f0;margin-bottom:12px;">'
      + 'Upon saving, AYUR-INTEL runs structured Indian patent intelligence indexing for formulation overlaps, active botanical claims, and Indian Patent Office (IPO) application records.'
      + '</p>'
      + '<div style="font-size:11px;color:#94a3b8;display:flex;align-items:center;gap:6px;">'
      + icon("info", 14) + ' <em>AYUR-INTEL presents patent intelligence as an analytical research & decision-support tool, not a legal infringement opinion.</em>'
      + '</div>'
      + '</div>';

    html += '</div>'

      // Action Footer
      + '<div class="passport-review-actions">'
      + '<button class="conv-btn-back" id="passport-back-to-questions">' + icon("arrow_back", 16) + ' Edit Questions</button>'
      + '<div style="display:flex;gap:12px;align-items:center;">'
      + '<button class="passport-btn-cta" id="passport-save-and-analyze">'
      + icon("analytics", 18) + (pd.is_demo ? ' Run Indian Patent Intelligence →' : ' Save & Run Indian Patent Intelligence →')
      + '</button>'
      + '</div>'
      + '</div>'

      + '</div></div>'
      + renderSuggestionModalHtml(pd);

    return html;
  }

  // ----------------------------------------------------------------
  // Event Binding for Conversational Wizard & Global Enter Behavior
  // ----------------------------------------------------------------

  function bindPassportEvents() {
    var pd = state.passportData;
    if (!pd) return;

    // Exit Button
    var exitBtn = document.getElementById("conv-exit-btn");
    if (exitBtn) {
      exitBtn.addEventListener("click", function () {
        state.passportData = null;
        state.passportStep = 0;
        state.currentCase = null;
        state.view = "dashboard";
        A.render();
      });
    }

    // Step 1: Category Option Cards
    document.querySelectorAll(".conv-option-card[data-val]").forEach(function (card) {
      card.addEventListener("click", function () {
        var val = this.getAttribute("data-val");
        pd.product_type = val;
        if (!pd.form || pd.form === "Not specified") pd.form = val;
        A.render();
      });
    });

    var catText = document.getElementById("conv-category-text");
    if (catText) {
      catText.addEventListener("input", function () {
        pd.product_type = this.value || "Other";
        if (!pd.form || pd.form === "Not specified" || pd.form === "Other") pd.form = this.value || "Other";
      });
    }

    // Step 2: Name Input
    var nameInput = document.getElementById("conv-name-input");
    if (nameInput) {
      nameInput.addEventListener("input", function () {
        pd.name = this.value;
        if (A.updateTopbarUI) A.updateTopbarUI();
      });
    }

    // Step 3: Description Input & Benchmark Reference Input
    var descInput = document.getElementById("conv-desc-input");
    if (descInput) {
      descInput.addEventListener("input", function () {
        pd.description = this.value;
      });
    }

    var refInput = document.getElementById("conv-reference-input");
    if (refInput) {
      refInput.addEventListener("input", function () {
        pd.reference_context = this.value;
      });
    }

    var normBtn = document.getElementById("conv-normalize-btn");
    if (normBtn) {
      normBtn.addEventListener("click", function () {
        triggerAiNormalize();
      });
    }

    // Step 4: Popular Botanical Chips (Opens Floating Quantity Modal)
    document.querySelectorAll(".conv-chip[data-bot-name]").forEach(function (chip) {
      chip.addEventListener("click", function () {
        var name = this.getAttribute("data-bot-name");
        var latin = this.getAttribute("data-bot-latin");
        
        var existsIdx = pd.ingredients.findIndex(function (ing) {
          return (ing.name || "").toLowerCase() === name.toLowerCase();
        });

        if (existsIdx >= 0) {
          // If already added, clicking toggles/removes it
          pd.ingredients.splice(existsIdx, 1);
          pd.activeBotanicalCard = null;
          A.render();
        } else {
          // Open Floating Quantity Modal for selected botanical
          pd.activeBotanicalCard = { name: name, botanical: latin, emoji: "🌿" };
          A.render();

          // Auto-focus quantity input
          setTimeout(function() {
            var qtyInput = document.getElementById("conv-ing-card-qty");
            if (qtyInput) {
              qtyInput.focus();
              qtyInput.select();
            }
          }, 30);
        }
      });
    });

    // Cancel botanical quantity modal
    var cancelBotCard = document.getElementById("conv-cancel-bot-card");
    if (cancelBotCard) {
      cancelBotCard.addEventListener("click", function () {
        pd.activeBotanicalCard = null;
        A.render();
      });
    }

    var cancelBotBtn = document.getElementById("conv-cancel-bot-btn");
    if (cancelBotBtn) {
      cancelBotBtn.addEventListener("click", function () {
        pd.activeBotanicalCard = null;
        A.render();
      });
    }

    var ingOverlay = document.getElementById("ing-modal-overlay");
    if (ingOverlay) {
      ingOverlay.addEventListener("click", function(e) {
        if (e.target === ingOverlay) {
          pd.activeBotanicalCard = null;
          A.render();
        }
      });
    }

    // Confirm & Add/Edit botanical with quantity
    function confirmBotanicalQuantity() {
      if (!pd.activeBotanicalCard) return;
      var qtyInput = document.getElementById("conv-ing-card-qty");
      var qty = qtyInput ? qtyInput.value.trim() : "";
      
      if (qty) {
        // If user typed only letters or symbols without numbers (e.g. "g" or "mg"), reject
        if (!/[0-9]/.test(qty)) {
          if (typeof toast === "function") {
            toast("⚠️ Please enter a valid quantity with numbers (e.g. 500 mg)", "warning");
          }
          return;
        }
        qty = qty.replace(/[^0-9\s.mgMGkKlL%]/g, "").trim();
      }

      // If left blank by user, do NOT auto-fill 500 mg! Leave as null / unspecified.
      var finalQty = qty || null;

      if (typeof pd.activeBotanicalCard.editingIdx === "number" && pd.activeBotanicalCard.editingIdx >= 0) {
        var editIdx = pd.activeBotanicalCard.editingIdx;
        if (pd.ingredients[editIdx]) {
          pd.ingredients[editIdx].quantity = finalQty;
        }
      } else {
        // Prevent duplicate
        var existsIdx = pd.ingredients.findIndex(function (ing) {
          return (ing.name || "").toLowerCase() === pd.activeBotanicalCard.name.toLowerCase();
        });

        if (existsIdx >= 0) {
          pd.ingredients[existsIdx].quantity = finalQty;
        } else {
          pd.ingredients.push({
            name: pd.activeBotanicalCard.name,
            botanical: pd.activeBotanicalCard.botanical || "",
            quantity: finalQty,
            status: "IDENTIFIED"
          });
        }
      }

      pd.activeBotanicalCard = null;
      A.render();
    }

    var confirmBotBtn = document.getElementById("conv-ing-card-confirm");
    if (confirmBotBtn) {
      confirmBotBtn.addEventListener("click", function () {
        confirmBotanicalQuantity();
      });
    }

    // Edit Ingredient Quantity Badge Click
    document.querySelectorAll(".conv-qty-badge[data-edit-ing-idx]").forEach(function (badge) {
      badge.addEventListener("click", function (e) {
        e.stopPropagation();
        var idx = parseInt(this.getAttribute("data-edit-ing-idx"), 10);
        if (!isNaN(idx) && idx >= 0 && idx < pd.ingredients.length) {
          var ing = pd.ingredients[idx];
          pd.activeBotanicalCard = {
            name: ing.name,
            botanical: ing.botanical || "",
            emoji: "🌿",
            editingIdx: idx,
            initialQty: ing.quantity || ""
          };
          A.render();
          setTimeout(function() {
            var qtyInput = document.getElementById("conv-ing-card-qty");
            if (qtyInput) {
              qtyInput.focus();
              qtyInput.select();
            }
          }, 30);
        }
      });
    });

    // Custom Ingredient Add
    function addCustomIngredient() {
      var nameEl = document.getElementById("conv-custom-ing-name");
      var qtyEl = document.getElementById("conv-custom-ing-qty");
      var rawName = (nameEl && nameEl.value) ? nameEl.value.trim() : "";
      var rawQty = (qtyEl && qtyEl.value) ? qtyEl.value.trim() : "";

      if (!rawName) {
        toast("Please enter a custom ingredient name", "error");
        return;
      }

      if (rawQty) {
        if (!/[0-9]/.test(rawQty)) {
          if (typeof toast === "function") {
            toast("⚠️ Please enter a valid quantity with numbers (e.g. 50 mg)", "warning");
          }
          return;
        }
        rawQty = rawQty.replace(/[^0-9\s.mgMGkKlL%]/g, "").trim();
      }

      var normalized = normalizeCustomIngredient(rawName);
      // If left blank, do NOT auto-fill 100 mg! Leave as null / unspecified.
      var finalQty = rawQty || null;

      pd.ingredients.push({
        name: normalized.name,
        botanical: normalized.botanical || "",
        quantity: finalQty,
        status: "USER_PROVIDED"
      });

      if (nameEl) nameEl.value = "";
      if (qtyEl) qtyEl.value = "";
      A.render();
    }

    var addIngBtn = document.getElementById("conv-add-ing-btn");
    if (addIngBtn) {
      addIngBtn.addEventListener("click", function () {
        addCustomIngredient();
      });
    }

    // Suggestion Cards Click (Opens Modal Popup)
    document.querySelectorAll(".conv-suggestion-card-btn[data-sugg-idx]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var sIdx = parseInt(this.getAttribute("data-sugg-idx"), 10);
        var suggList = getFormulationSuggestionsDetailed(pd.ingredients, pd.product_suggestions);
        if (suggList && suggList[sIdx]) {
          pd.activeSuggestionModal = suggList[sIdx];
          A.render();
        }
      });
    });

    // Suggestion Modal Actions
    var useSuggBtn = document.getElementById("conv-use-sugg-btn");
    if (useSuggBtn) {
      useSuggBtn.addEventListener("click", function () {
        if (pd.activeSuggestionModal && pd.activeSuggestionModal.name) {
          pd.name = pd.activeSuggestionModal.name;
          if (A.updateTopbarUI) A.updateTopbarUI();
          toast("Applied product name: " + pd.name, "success");
        }
        pd.activeSuggestionModal = null;
        A.render();
      });
    }

    var closeSuggBtn = document.getElementById("conv-close-sugg-btn");
    if (closeSuggBtn) {
      closeSuggBtn.addEventListener("click", function () {
        pd.activeSuggestionModal = null;
        A.render();
      });
    }

    var cancelSuggModal = document.getElementById("conv-cancel-sugg-modal");
    if (cancelSuggModal) {
      cancelSuggModal.addEventListener("click", function () {
        pd.activeSuggestionModal = null;
        A.render();
      });
    }

    var suggOverlay = document.getElementById("sugg-modal-overlay");
    if (suggOverlay) {
      suggOverlay.addEventListener("click", function (e) {
        if (e.target === suggOverlay) {
          pd.activeSuggestionModal = null;
          A.render();
        }
      });
    }

    // Formulation suggestion pills click (fallback legacy pills)
    document.querySelectorAll(".conv-suggestion-pill[data-sugg-name]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var name = this.getAttribute("data-sugg-name");
        pd.name = name;
        if (A.updateTopbarUI) A.updateTopbarUI();
        toast("Applied product name: " + name, "success");
      });
    });

    // Remove ingredient
    document.querySelectorAll(".conv-remove-ing").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var idx = parseInt(this.getAttribute("data-idx"), 10);
        if (!isNaN(idx) && idx >= 0 && idx < pd.ingredients.length) {
          pd.ingredients.splice(idx, 1);
          A.render();
        }
      });
    });

    // Step 5: Intended Use Cards
    document.querySelectorAll(".conv-option-card[data-use-id]").forEach(function (card) {
      card.addEventListener("click", function () {
        var useId = this.getAttribute("data-use-id");
        var idx = pd.intended_use.indexOf(useId);
        if (idx >= 0) {
          pd.intended_use.splice(idx, 1);
        } else {
          pd.intended_use.push(useId);
        }
        A.render();
      });
    });

    function addCustomUse() {
      var input = document.getElementById("conv-custom-use");
      if (input && input.value.trim()) {
        pd.intended_use.push(input.value.trim());
        input.value = "";
        A.render();
        return true;
      }
      return false;
    }

    // Step 6: Process Cards
    document.querySelectorAll(".conv-option-card[data-proc-id]").forEach(function (card) {
      card.addEventListener("click", function () {
        pd.process = this.getAttribute("data-proc-id");
        A.render();
      });
    });

    var procDetails = document.getElementById("conv-process-details");
    if (procDetails) {
      procDetails.addEventListener("input", function () {
        pd.process = this.value;
      });
    }

    // Step 7: Claims Chips
    document.querySelectorAll(".conv-chip[data-claim-text]").forEach(function (chip) {
      chip.addEventListener("click", function () {
        var text = this.getAttribute("data-claim-text");
        var idx = pd.claims.indexOf(text);
        if (idx >= 0) {
          pd.claims.splice(idx, 1);
        } else {
          pd.claims.push(text);
        }
        A.render();
      });
    });

    function addCustomClaim() {
      var customClaim = document.getElementById("conv-custom-claim");
      if (customClaim && customClaim.value.trim()) {
        pd.claims.push(customClaim.value.trim());
        customClaim.value = "";
        A.render();
        return true;
      }
      return false;
    }

    var addClaimBtn = document.getElementById("conv-add-claim-btn");
    if (addClaimBtn) {
      addClaimBtn.addEventListener("click", function () {
        addCustomClaim();
      });
    }

    document.querySelectorAll(".conv-remove-claim").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var idx = parseInt(this.getAttribute("data-idx"), 10);
        if (!isNaN(idx) && idx >= 0 && idx < pd.claims.length) {
          pd.claims.splice(idx, 1);
          A.render();
        }
      });
    });

    // Navigation: Back / Continue / Skip
    var backBtn = document.getElementById("conv-back-btn");
    if (backBtn) {
      backBtn.addEventListener("click", function () {
        if (state.passportStep > 0) {
          state.passportStep--;
          A.render();
        }
      });
    }

    // Unified Continue Handler (Runs identical validation and navigation)
    function handleContinue() {
      var curStep = state.passportStep || 0;
      if (curStep === 1 && (!pd.name || !pd.name.trim())) {
        pd.name = "Ashwagandha Calm & Restore Capsules";
      }
      if (curStep < CONV_STEPS.length - 1) {
        state.passportStep++;
        A.render();
      }
    }

    var nextBtn = document.getElementById("conv-next-btn");
    if (nextBtn) {
      nextBtn.addEventListener("click", handleContinue);
    }

    var skipBtn = document.getElementById("conv-skip-btn");
    if (skipBtn) {
      skipBtn.addEventListener("click", function () {
        if (state.passportStep < CONV_STEPS.length - 1) {
          state.passportStep++;
          A.render();
        }
      });
    }

    // Review Screen Actions
    var jumpReviewBtn = document.getElementById("conv-jump-review-btn");
    if (jumpReviewBtn) {
      jumpReviewBtn.addEventListener("click", function () {
        state.passportStep = CONV_STEPS.length - 1; // Jump directly to Review
        A.render();
      });
    }

    var editAllBtn = document.getElementById("passport-edit-all-btn");
    if (editAllBtn) {
      editAllBtn.addEventListener("click", function () {
        state.passportStep = 0;
        A.render();
      });
    }

    var backToQuestionsBtn = document.getElementById("passport-back-to-questions");
    if (backToQuestionsBtn) {
      backToQuestionsBtn.addEventListener("click", function () {
        state.passportStep = CONV_STEPS.length - 2; // Jump back to Step 7
        A.render();
      });
    }

    document.querySelectorAll(".passport-edit-btn[data-jump-step]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var stepNum = parseInt(this.getAttribute("data-jump-step"), 10);
        if (!isNaN(stepNum)) {
          state.passportStep = stepNum;
          A.render();
        }
      });
    });

    var saveAndAnalyzeBtn = document.getElementById("passport-save-and-analyze");
    if (saveAndAnalyzeBtn) {
      saveAndAnalyzeBtn.addEventListener("click", async function () {
        await saveProductPassportAndStartAnalysis();
      });
    }

    // ----------------------------------------------------------------
    // Global Keyboard & Enter-Key Handler for EVERY Step
    // ----------------------------------------------------------------
    window.onkeydown = function(e) {
      if (state.view !== "passport-wizard") return;
      if (e.key === "Enter" && !e.isComposing) {
        var target = e.target;
        
        // 1. Textarea Exception: Multiline textareas preserve natural newline
        if (target && target.tagName === "TEXTAREA") {
          return;
        }

        // 2. Ingredient Quantity Popup Exception: Enter confirms & adds quantity
        if (target && target.id === "conv-ing-card-qty") {
          e.preventDefault();
          e.stopPropagation();
          confirmBotanicalQuantity();
          return;
        }

        // 3. Custom Ingredient Exception: Enter adds custom ingredient
        if (target && (target.id === "conv-custom-ing-name" || target.id === "conv-custom-ing-qty")) {
          e.preventDefault();
          e.stopPropagation();
          addCustomIngredient();
          return;
        }

        // 4. Custom Claim Input: If text entered, add it; otherwise continue
        if (target && target.id === "conv-custom-claim") {
          e.preventDefault();
          e.stopPropagation();
          if (target.value.trim()) {
            addCustomClaim();
          } else {
            handleContinue();
          }
          return;
        }

        // 5. Custom Use Input: If text entered, add it; otherwise continue
        if (target && target.id === "conv-custom-use") {
          e.preventDefault();
          e.stopPropagation();
          if (target.value.trim()) {
            addCustomUse();
          } else {
            handleContinue();
          }
          return;
        }

        // 6. Review Screen Enter: Save & Start Analysis
        var stepIdx = state.passportStep || 0;
        if (stepIdx === CONV_STEPS.length - 1) {
          e.preventDefault();
          saveProductPassportAndStartAnalysis();
          return;
        }

        // 7. For EVERY remaining questionnaire step: Enter = Continue (reusing handleContinue)
        var nxt = document.getElementById("conv-next-btn");
        if (nxt) {
          e.preventDefault();
          handleContinue();
        }
      }
    };
  }

  // ----------------------------------------------------------------
  // AI Normalization Trigger
  // ----------------------------------------------------------------

  async function triggerAiNormalize() {
    var pd = state.passportData;
    if (!pd) return;

    var descInput = document.getElementById("conv-desc-input");
    var rawText = (descInput ? descInput.value : (pd.description || "")).trim();

    if (!rawText) {
      console.warn("⚠️ No description entered");
      toast("Please enter a product description first", "warning");
      return;
    }

    pd.description = rawText;
    var normBtn = document.getElementById("conv-normalize-btn");
    var originalText = normBtn ? normBtn.innerHTML : "Structure with AI";
    if (normBtn) {
      normBtn.innerHTML = '<span class="spinner"></span> Analyzing...';
      normBtn.disabled = true;
    }
    pd.is_normalizing = true;

    try {
      var payload = {
        description: rawText,
        name: pd.name || "",
        product_type: pd.product_type || "",
        ingredients: pd.ingredients || [],
        form: pd.form || "",
        intended_use_list: pd.intended_use || [],
        process: pd.process || "",
        claims: pd.claims || [],
        jurisdictions: ["IN"]
      };

      console.log("📤 Sending normalization payload:", payload);

      var res = await api("/api/cases/normalize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      console.log("✅ AI Normalization response:", res);

      if (res) {
        if (res.product_name && !pd.name) {
          pd.name = res.product_name;
        }
        if (res.form) pd.form = res.form;
        if (res.product_type && !pd.product_type) pd.product_type = res.product_type;
        if (res.process && !pd.process) {
          pd.process = res.process;
        }
        if (res.normalized_description) {
          pd.normalized_description = res.normalized_description;
        }
        if (res.product_suggestions && Array.isArray(res.product_suggestions)) {
          pd.product_suggestions = res.product_suggestions;
        }

        // Merge ingredients
        if (res.ingredients && Array.isArray(res.ingredients) && res.ingredients.length > 0) {
          res.ingredients.forEach(function (normIng) {
            var ingName = normIng.input_name || normIng.name || "";
            var ingBot = normIng.botanical_name || normIng.botanical || "";
            if (!ingName) return;
            var exists = pd.ingredients.some(function (existing) {
              return (existing.name || "").toLowerCase() === ingName.toLowerCase() ||
                     (ingBot && (existing.botanical || "").toLowerCase() === ingBot.toLowerCase());
            });
            if (!exists) {
              pd.ingredients.push({
                name: ingName.charAt(0).toUpperCase() + ingName.slice(1),
                botanical: ingBot,
                quantity: normIng.quantity || null,
                status: normIng.status || "AI_DETECTED"
              });
            }
          });
        }

        // Merge intended uses
        if (res.intended_use && Array.isArray(res.intended_use)) {
          res.intended_use.forEach(function (u) {
            if (pd.intended_use.indexOf(u) === -1) {
              pd.intended_use.push(u);
            }
          });
        }

        // Merge claims
        if (res.claims && Array.isArray(res.claims)) {
          res.claims.forEach(function (c) {
            if (pd.claims.indexOf(c) === -1) {
              pd.claims.push(c);
            }
          });
        }

        pd.ai_normalized = true;
        console.log("✅ Passport updated:", pd);

        // Show success toast with ingredients and confidence
        var ingNames = (pd.ingredients || []).map(function (i) { return i.name; }).filter(Boolean).join(", ") || "Properties updated";
        toast("✅ AI structured successfully! Ingredients: " + ingNames, "success");
      }
    } catch (e) {
      console.warn("⚠️ AI service error, running fallback:", e);
      toast("⚠️ AI service unavailable. Using local botanical engine.", "warning");
      fallbackNormalize(rawText);
    } finally {
      pd.is_normalizing = false;
      if (normBtn) {
        normBtn.innerHTML = originalText;
        normBtn.disabled = false;
      }
      A.render();
    }
  }

  // ----------------------------------------------------------------
  // Fallback Normalization
  // ----------------------------------------------------------------

  function fallbackNormalize(rawText) {
    var pd = state.passportData;
    if (!pd || !rawText) return;

    console.log("🔄 Using fallback normalization for:", rawText);
    var textLower = rawText.toLowerCase();
    var knownHerbs = {
      "ashwagandha": "Withania somnifera",
      "brahmi": "Bacopa monnieri",
      "tulsi": "Ocimum sanctum",
      "neem": "Azadirachta indica",
      "haldi": "Curcuma longa",
      "turmeric": "Curcuma longa",
      "amla": "Phyllanthus emblica",
      "giloy": "Tinospora cordifolia",
      "shatavari": "Asparagus racemosus",
      "shankhpushpi": "Convolvulus pluricaulis",
      "jatamansi": "Nardostachys jatamansi",
      "mulethi": "Glycyrrhiza glabra",
      "triphala": "Triphala",
      "haritaki": "Terminalia chebula",
      "bibhitaki": "Terminalia bellirica"
    };

    var detected = [];
    Object.keys(knownHerbs).forEach(function (herb) {
      if (textLower.indexOf(herb) !== -1) {
        detected.push({
          name: herb.charAt(0).toUpperCase() + herb.slice(1),
          botanical: knownHerbs[herb]
        });
      }
    });

    console.log("🔍 Detected ingredients (fallback):", detected);

    if (detected.length > 0) {
      detected.forEach(function (ing) {
        var exists = pd.ingredients.some(function (existing) {
          return (existing.name || "").toLowerCase() === ing.name.toLowerCase();
        });
        if (!exists) {
          pd.ingredients.push({
            name: ing.name,
            botanical: ing.botanical,
            quantity: null,
            status: "USER_PROVIDED"
          });
        }
      });
      var ingsStr = detected.map(function (d) { return d.name; }).join(", ");
      pd.normalized_description = "A classical Ayurvedic formulation containing active botanical extracts of " + ingsStr + " for holistic wellness.";
      pd.product_suggestions = getFormulationSuggestions(pd.ingredients, []);
      pd.ai_normalized = true;
      toast("✅ Found ingredients: " + ingsStr, "success");
    } else {
      // Symptom / condition detection & translation
      if (textLower.indexOf("sar dard") !== -1 || textLower.indexOf("sir dard") !== -1 || textLower.indexOf("headache") !== -1 || textLower.indexOf("migraine") !== -1) {
        pd.normalized_description = "This formulation helps relieve headaches and provides soothing head tension relief.";
        if (pd.intended_use.indexOf("Headache & Migraine Relief") === -1) {
          pd.intended_use.push("Headache & Migraine Relief");
        }
      } else if (textLower.indexOf("pet") !== -1 || textLower.indexOf("pachan") !== -1 || textLower.indexOf("gas") !== -1 || textLower.indexOf("kabz") !== -1) {
        pd.normalized_description = "This formulation promotes healthy digestion and relieves gastrointestinal discomfort.";
        if (pd.intended_use.indexOf("Digestive Health & Gut Support") === -1) {
          pd.intended_use.push("Digestive Health & Gut Support");
        }
      } else if (textLower.indexOf("stress") !== -1 || textLower.indexOf("tanaav") !== -1 || textLower.indexOf("calm") !== -1) {
        pd.normalized_description = "This formulation supports daily stress management, mental calmness, and relaxation.";
        if (pd.intended_use.indexOf("Stress Relief & Relaxation") === -1) {
          pd.intended_use.push("Stress Relief & Relaxation");
        }
      } else if (textLower.indexOf("neend") !== -1 || textLower.indexOf("sleep") !== -1) {
        pd.normalized_description = "This formulation promotes restful sleep, calming relaxation, and nightly rejuvenation.";
        if (pd.intended_use.indexOf("Sleep & Calming Support") === -1) {
          pd.intended_use.push("Sleep & Calming Support");
        }
      } else {
        pd.normalized_description = "A targeted Ayurvedic formulation crafted to support daily health and holistic balance.";
      }
      pd.product_suggestions = getFormulationSuggestions(pd.ingredients, []);
      pd.ai_normalized = true;
      toast("✅ Description structured and translated into English", "success");
    }
    A.render();
  }

  // ----------------------------------------------------------------
  // Save Passport & Transition to Case Intelligence
  // ----------------------------------------------------------------
  var _isSavingPassport = false;

  async function saveProductPassportAndStartAnalysis() {
    if (_isSavingPassport) {
      console.warn("⚠️ Save already in progress, ignoring duplicate click");
      return;
    }

    var pd = (window.AYUR && window.AYUR.state && window.AYUR.state.passportData) || state.passportData;
    if (!pd) return;

    // If this is an existing demo case, reuse directly without creating another case
    if (pd.is_demo && pd.id) {
      _isSavingPassport = true;
      var saveBtn = document.getElementById("passport-save-and-analyze");
      var origBtnText = "";
      if (saveBtn) {
        origBtnText = saveBtn.innerHTML;
        saveBtn.disabled = true;
        saveBtn.style.opacity = "0.7";
        saveBtn.style.pointerEvents = "none";
        saveBtn.innerHTML = '<span class="spinner-sm" style="display:inline-block;width:14px;height:14px;border:2px solid currentColor;border-top-color:transparent;border-radius:50%;animation:spin 0.6s linear infinite;margin-right:8px;vertical-align:middle;"></span> Loading Intelligence...';
      }
      try {
        var caseData = null;
        try {
          caseData = await api("/api/cases/" + pd.id);
        } catch (e) {
          caseData = pd;
        }
        window.AYUR.state.currentCase = caseData || pd;
        window.AYUR.state.passportData = null;
        if (typeof window.AYUR.saveStateToLocalStorage === 'function') {
          window.AYUR.saveStateToLocalStorage();
        }
        if (typeof window.AYUR.updateTopbarUI === 'function') {
          window.AYUR.updateTopbarUI();
        } else if (typeof updateTopbarUI === 'function') {
          updateTopbarUI();
        }
        if (typeof showToast === 'function') {
          showToast('🌿 Opening Case Intelligence for Demo Case...', 'success');
        } else if (typeof toast === 'function') {
          toast('🌿 Opening Case Intelligence for Demo Case...', 'success');
        }
        window.AYUR.state.view = 'case-detail';
        window.AYUR.render();
        return;
      } catch (err) {
        console.warn("Direct demo navigation fallback:", err);
      } finally {
        _isSavingPassport = false;
      }
    }

    _isSavingPassport = true;
    var saveBtn = document.getElementById("passport-save-and-analyze");
    var origBtnText = "";
    if (saveBtn) {
      origBtnText = saveBtn.innerHTML;
      saveBtn.disabled = true;
      saveBtn.style.opacity = "0.7";
      saveBtn.style.pointerEvents = "none";
      saveBtn.innerHTML = '<span class="spinner-sm" style="display:inline-block;width:14px;height:14px;border:2px solid currentColor;border-top-color:transparent;border-radius:50%;animation:spin 0.6s linear infinite;margin-right:8px;vertical-align:middle;"></span> Saving & Running Intelligence...';
    }

    // CRITICAL: Ensure ingredients are properly formatted
    var ingredients = pd.ingredients || [];
    var cleanIngredients = ingredients.map(function (ing) {
      return {
        name: ing.name || ing.input_name || '',
        botanical: ing.botanical || ing.botanical_name || '',
        quantity: ing.quantity || '',
        status: ing.status || 'USER_PROVIDED'
      };
    });

    var payload = {
      name: pd.name || 'Unnamed Product',
      stage: 'IDEA',
      jurisdictions: ['IN'],
      ingredients: cleanIngredients,
      form: pd.form || pd.product_type || null,
      intended_use: Array.isArray(pd.intended_use) ? pd.intended_use.join(', ') : (pd.intended_use || null),
      claims: pd.claims || [],
      formulation: pd.formulation || pd.form || pd.product_type || null,
      process: pd.process || null,
      brand: pd.brand || null,
      packaging: pd.packaging || null,
      notes: pd.reference_context || pd.notes || null,
      is_demo: Boolean(pd.is_demo)
    };

    console.log('💾 SAVING WITH PAYLOAD:', payload);

    try {
      var response = await fetch('/api/cases', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      var data = await response.json();

      if (response.ok) {
        console.log('✅ Case saved:', data);

        // Invalidate API cache and module cache for this case
        if (window.AYUR && typeof window.AYUR.invalidateClientApiCache === 'function') {
          window.AYUR.invalidateClientApiCache('/api/cases');
        }
        if (window.AYUR && typeof window.AYUR.invalidateCaseModuleCache === 'function' && data.id) {
          window.AYUR.invalidateCaseModuleCache(data.id);
        }
        if (window.AYUR && typeof window.AYUR.loadCases === 'function') {
          window.AYUR.loadCases();
        }

        // Update state
        window.AYUR.state.currentCase = data;
        window.AYUR.state.passportData = null;

        // Persist to localStorage
        if (typeof window.AYUR.saveStateToLocalStorage === 'function') {
          window.AYUR.saveStateToLocalStorage();
        }

        // Update topbar
        if (typeof window.AYUR.updateTopbarUI === 'function') {
          window.AYUR.updateTopbarUI();
        } else if (typeof updateTopbarUI === 'function') {
          updateTopbarUI();
        }

        // Show success
        if (typeof showToast === 'function') {
          showToast('✅ Product saved! Opening Case Intelligence...', 'success');
        } else if (typeof toast === 'function') {
          toast('✅ Product saved! Opening Case Intelligence...', 'success');
        }

        // Navigate to Case Intelligence
        window.AYUR.state.view = 'case-detail';
        window.AYUR.render();
      } else {
        var errMsg = '❌ Failed to save: ' + (data.detail || 'Unknown error');
        if (typeof showToast === 'function') showToast(errMsg, 'error');
        else if (typeof toast === 'function') toast(errMsg, 'error');
        if (saveBtn) {
          saveBtn.disabled = false;
          saveBtn.style.opacity = "";
          saveBtn.style.pointerEvents = "";
          saveBtn.innerHTML = origBtnText;
        }
      }
    } catch (error) {
      console.error('Save error:', error);
      if (typeof showToast === 'function') showToast('❌ Failed to save product', 'error');
      else if (typeof toast === 'function') toast('❌ Failed to save product', 'error');
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.style.opacity = "";
        saveBtn.style.pointerEvents = "";
        saveBtn.innerHTML = origBtnText;
      }
    } finally {
      _isSavingPassport = false;
    }
  }

  // Expose
  window.AYUR.renderPassportWizard = renderPassportWizard;
  window.AYUR.initPassportData = initPassportData;
  window.AYUR.initDemoPassport = initDemoPassport;
  window.AYUR.DEMO_PASSPORT_DATA = DEMO_PASSPORT_DATA;
  window.AYUR.bindPassportEvents = bindPassportEvents;
  window.AYUR.triggerAiNormalize = triggerAiNormalize;
  window.AYUR.fallbackNormalize = fallbackNormalize;

})();
