/* Empire AI private read-only CRM console.
   The existing server verifies Bearer tokens and tenant authority.
   This page never writes CRM records, stores passwords/tokens or issues sends.
*/
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const state = { token: "", records: [], fetching: false, sourceFetching: false, generation: 0, expiresAt: 0, expiryTimer: null };
  const LIMIT = 40;
  const DETAIL_LIMIT = 20;
  const BATCH = 4;
  const PRIORITY = {
    0: "Contact hold",
    1: "Payment / fulfilment review",
    2: "Proposal / capacity review",
    3: "Conversation review",
    4: "Evidence gap",
  };
  const STATUS_LABELS = {
    REVIEW_CONTACT_HOLD: "Review contact hold — do not send",
    REVIEW_PAYMENT_EVIDENCE: "Check payment evidence",
    REVIEW_FULFILMENT_EVIDENCE: "Check fulfilment evidence",
    REVIEW_PROPOSAL_EVIDENCE: "Review proposal readiness",
    REVIEW_BUYER_CAPACITY_EVIDENCE: "Review verified buyer capacity",
    REVIEW_CONVERSATION_EVIDENCE: "Review engaged conversation",
    RECONCILE_ORIGINAL_INBOUND_AND_CONTACT: "Verify original inbound and identity",
    REVIEW_SOURCE_GAPS: "Resolve missing commercial evidence",
  };

  const text = (node, value) => { node.textContent = String(value ?? "Unknown"); return node; };
  const make = (tag, cls, value) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (value != null) text(node, value);
    return node;
  };
  function clearSession(message) {
    if (state.expiryTimer !== null) clearTimeout(state.expiryTimer);
    state.expiryTimer = null;
    state.expiresAt = 0;
    state.generation += 1;
    state.token = "";
    state.records = [];
    $("workspace-nav").hidden = true;
    $("kanban-results").replaceChildren();
    text($("kanban-status"), "Signed out. Tenant task records hidden.");
    text($("sales-actions-workspace-status"), "Signed out. Sales actions hidden.");
    text($("revenue-evidence-status"), "Verified tenant settlement reader not connected; no revenue amount claimed.");
    $("results").replaceChildren();
    $("buyer-results").replaceChildren();
    text($("buyer-review-status"), "Signed out. Buyer records hidden.");
    $("partner-source-results").replaceChildren();
    $("win-plan-results").replaceChildren();
    $("solar-preview-results").replaceChildren();
    $("inbound-source-results").replaceChildren();
    text($("partner-source-status"), "Signed out. Partner evidence hidden.");
    text($("partner-action-summary"), "Signed out. Founder tasks hidden.");
    text($("win-plan-status"), "Signed out. Win Plans hidden.");
    text($("win-plan-coverage"), "Full inbox coverage not established.");
    text($("solar-preview-status"), "Signed out. Solar prospect matches hidden.");
    text($("solar-preview-coverage"), "Tenant row-window coverage not established.");
    text($("inbound-source-status"), "Signed out. Incoming enquiries hidden.");
    $("login-panel").hidden = false;
    $("review-panel").hidden = true;
    $("password").value = "";
    text($("login-status"), message || "");
    $("sign-in").disabled = false;
    state.fetching = false;
  }

  async function request(path, init = {}) {
    if (state.token && Date.now() >= state.expiresAt) {
      clearSession("CRM session expired. Sign in again.");
      throw new Error("crm_session_expired");
    }
    const headers = { Accept: "application/json" };
    if (state.token) headers.Authorization = "Bearer " + state.token;
    if (init.body) headers["Content-Type"] = "application/json";
    const response = await fetch(path, {
      method: init.method || "GET",
      headers,
      body: init.body ? JSON.stringify(init.body) : undefined,
      credentials: "omit",
      cache: "no-store",
      redirect: "error",
    });
    if (response.status === 401 && state.token) {
      clearSession("Your CRM session expired or no longer has access. Sign in again.");
      throw new Error("crm_session_expired");
    }
    if (!response.ok) throw new Error("CRM returned HTTP " + response.status);
    const payload = await response.json();
    if (!payload || typeof payload !== "object") throw new Error("Invalid CRM response");
    return payload;
  }

  function detailRow(dl, key, value) {
    dl.append(make("dt", null, key), make("dd", null, value));
  }

  function card(item) {
    const { prospect, action, error } = item;
    const box = make("article", "card");
    const valid = action &&
      action.schema_version === "empire.revenue_crm_commercial_action_review.v1" &&
      action.mode === "OBSERVE" &&
      action.execution_authority === "none" &&
      action.send_authorized === false;
    const rank = valid && Number.isInteger(action.priority_rank) &&
      action.priority_rank >= 0 && action.priority_rank <= 4
      ? action.priority_rank : null;
    const held = valid && action.contact_hold === true;
    const pill = make("span", "tag" + (held ? " hold" : rank === null ? " gap" : ""),
      rank === null ? "Unavailable" : (PRIORITY[rank] || "Evidence review"));
    box.append(pill);
    box.append(make("h3", null,
      typeof prospect.business_name === "string" && prospect.business_name.trim()
      ? prospect.business_name : "CRM prospect"));
    box.append(make("div", "meta", prospect.prospect_id || "Missing prospect ID"));
    box.append(make("p", "tiny", "Sector: " + (prospect.niche || "Not recorded")));
    box.append(make("p", null, valid
      ? (STATUS_LABELS[action.recommended_internal_review] || "Manual evidence review")
      : (error || "Action evidence unavailable")));
    if (valid) {
      const details = make("details", "details");
      details.append(make("summary", null, "Evidence and limitations"));
      const dl = make("dl");
      detailRow(dl, "CRM stage", action.crm_stage_action || "Not observed");
      detailRow(dl, "Reply signals", (action.unverified_reply_signals || []).join(", ") || "None observed");
      detailRow(dl, "Provider/identity", action.source_proof_blockers_present ? "Original proof pending" : "Reader has no declared blockers");
      detailRow(dl, "Channel status", action.channel_evidence_status || "Unknown");
      detailRow(dl, "Contact hold", held ? "Yes — no messaging" : "No explicit hold; sending is still not authorised");
      detailRow(dl, "Closing probability", "Not validated");
      detailRow(dl, "Realised revenue", "Not verified");
      const evidence = Array.isArray(action.canonical_evidence_refs)
        ? action.canonical_evidence_refs.map((v) => (v.kind || "source") + ": " + (v.record_id || "unknown")).join("; ")
        : "";
      detailRow(dl, "Evidence refs", evidence || "None available");
      details.append(dl);
      box.append(details);
    }
    return box;
  }

  // These are deliberately SEPARATE from canonical tenant CRM prospects.
  // All records are loaded only through existing owner-gated API routes.
  const PARTNER_ACTIONS = new Map([
    ["1a0d9ce883c87d4a", "REVIEW_PILOT_READINESS"],
    ["1a0cfb65e0dd960e", "WAIT_BUYER_REQUIREMENTS"],
    ["1a0cfb667dca0957", "WAIT_BUYER_REQUIREMENTS"],
    ["1a0d9fa5b944630a", "REVIEW_EXISTING_ANSWERS"],
    ["1a0d9ef44c7f77d0", "DEFER_UNTIL_TRAFFIC"],
  ]);
  const PRIORITY_BANDS = new Map([["REVIEW_NEXT", 0], ["WAIT", 1], ["DEFER", 2]]);
  // Reviewed policies only. A source-backed *task to review* is not a
  // partner commitment, an automated follow-up or a CRM opportunity stage.
  const FOUNDER_LANES = new Map([
    ["REVIEW_PILOT_READINESS", {
      rank: 0, lane: "Founder review now",
      instruction: "Review the original pilot evidence and clarify outstanding proof before any activation decision."
    }],
    ["REVIEW_EXISTING_ANSWERS", {
      rank: 1, lane: "Founder review now",
      instruction: "Compare the original answers with unresolved buyer requirements; identify precise unanswered questions."
    }],
    ["WAIT_BUYER_REQUIREMENTS", {
      rank: 2, lane: "Buyer information outstanding",
      instruction: "Review the original thread for current buying requirements; do not treat unanswered questions as a purchasing commitment."
    }],
    ["DEFER_UNTIL_TRAFFIC", {
      rank: 3, lane: "Deferred · no outreach",
      instruction: "Revisit only after independently verified eligible traffic and a fresh partner review."
    }],
  ]);

  function founderTask(row) {
    const policy = FOUNDER_LANES.get(row.founder_review_action);
    if (!policy) throw new Error("Partner action requires renewed source review");
    const needed = row.missing_proofs.slice(0, 5)
      .map((proof) => String(proof).toLowerCase().replaceAll("_", " "));
    const brief = [
      "Empire AI · internal commercial review (NOT AN OUTBOUND EMAIL)",
      "Partner: " + row.partner,
      "Source: original reviewed Gmail conversation " + row.gmail_thread_id,
      "Lane: " + policy.lane,
      "Provider review action: " + row.founder_review_action,
      "Founder instruction: " + policy.instruction,
      "Original source next evidence: " + String(row.next_evidence).toLowerCase().replaceAll("_", " "),
      "Evidence to establish:",
      ...needed.map((item, idx) => String(idx + 1) + ". " + item),
      "Limits: no verified CRM prospect, signed deal, payable terms, calibrated forecast or contact permission.",
      "Next decision: review original correspondence; prepare a separate accurate draft for founder approval if justified.",
      "No email queued, sent or authorised by this review."
    ].join("\n");
    return { ...policy, needed, brief };
  }


  function strictPartnerSource(data) {
    if (data.schema_version !== "empire.crm.partner_conversation_review.v3" ||
        data.coverage !== "EXACT_FIVE_PREVIOUSLY_REVIEWED_THREADS_NOT_FULL_INBOX" ||
        data.commercial_sales_readiness_source !==
          "EXISTING_REVIEWED_PARTNER_REGISTRY_AND_CRM_EVIDENCE_GATES" ||
        data.mode !== "OBSERVE" || data.read_only !== true ||
        data.execution_authority !== "none" ||
        data.outbound_authorized !== false || data.payment_authorized !== false ||
        data.crm_mutation !== false || data.buyer_identity_verified !== false ||
        data.revenue_verified !== false || data.commercial_terms_accepted !== false ||
        data.calibrated_probability_available !== false ||
        data.portfolio_forecast_revenue_cents !== null ||
        data.portfolio_recognized_revenue_cents !== null ||
        data.verified_paid_deals_from_this_source !== null ||
        !Array.isArray(data.items) || data.items.length !== 5 ||
        data.count_in_page !== 5 || !Number.isFinite(Date.parse(data.provider_partial_refresh_at)))
      throw new Error("Partner source contract unavailable");
    const seen = new Set();
    for (const row of data.items) {
      if (seen.has(row.gmail_thread_id) ||
          PARTNER_ACTIONS.get(row.gmail_thread_id) !== row.founder_review_action ||
          !PRIORITY_BANDS.has(row.attention_band) ||
          typeof row.partner !== "string" || row.partner.length > 90 ||
          typeof row.founder_review_title !== "string" || row.founder_review_title.length > 120 ||
          typeof row.founder_review_description !== "string" ||
          row.founder_review_description.length > 400 ||
          !["SUPERVISED_PILOT_REVIEW", "WAITING_EXTERNAL_REQUIREMENTS",
            "REVIEW_EXISTING_REQUIREMENTS", "DEFERRED_UNTIL_REAL_TRAFFIC"].includes(row.readiness) ||
          row.crm_prospect_identity_verified !== false ||
          row.opportunity_in_canonical_crm !== false ||
          row.buying_intent_independently_verified !== false ||
          row.accepted_payable_terms_verified !== false ||
          row.expected_revenue_cents !== null ||
          row.recognized_revenue_cents !== null ||
          row.send_authorized !== false ||
          !Array.isArray(row.missing_proofs) ||
          row.missing_proofs.length < 4 || row.missing_proofs.length > 12 ||
          row.missing_proofs.some(item => typeof item !== "string" ||
            !/^[A-Z0-9_]{6,100}$/.test(item)) ||
          typeof row.next_evidence !== "string" ||
          !/^[A-Z0-9_]{6,120}$/.test(row.next_evidence))
        throw new Error("Partner evidence row not trusted");
      seen.add(row.gmail_thread_id);
    }
    if (seen.size !== PARTNER_ACTIONS.size)
      throw new Error("Partner source only partly refreshed");
  }

  async function loadOriginalPartners(generation) {
    const target = $("partner-source-results");
    const status = $("partner-source-status");
    const summary = $("partner-action-summary");
    target.replaceChildren();
    text(summary, "Checking original commercial task priorities…");
    text(status, "Checking approved provider-backed partner evidence…");
    try {
      const data = await request("/v1/revenue-crm/partner-conversations/review");
      if (generation !== state.generation || !state.token) return;
      strictPartnerSource(data);
      const ranked = [...data.items].sort((a, b) =>
        founderTask(a).rank - founderTask(b).rank ||
        PRIORITY_BANDS.get(a.attention_band) - PRIORITY_BANDS.get(b.attention_band));
      const reviewNow = ranked.filter(row => founderTask(row).rank < 2).length;
      const buyerWaiting = ranked.filter(row => founderTask(row).rank === 2).length;
      const deferred = ranked.filter(row => founderTask(row).rank === 3).length;
      text(summary, reviewNow + " founder review tasks · " + buyerWaiting +
        " awaiting buyer details · " + deferred +
        " deferred · no automatic sends or client stage changes.");
      const fragment = document.createDocumentFragment();
      for (const row of ranked) {
        const task = founderTask(row);
        const block = make("article", "card");
        block.append(make("span", "tag", row.attention_band === "DEFER" ?
            "Deferred partner" : row.attention_band === "REVIEW_NEXT" ?
            "Human review next" : "Waiting for partner"),
          make("h3", null, row.partner),
          make("p", "meta", "Founder queue: " + task.lane),
          make("p", null, row.founder_review_title),
          make("p", "tiny", task.instruction),
          make("p", "tiny", row.founder_review_description),
          make("p", "tiny", "Commercial readiness: " +
            row.readiness.replaceAll("_", " ").toLowerCase() +
            " · NOT A CRM CLIENT · NOT A VERIFIED PAID DEAL"),
          make("p", "tiny", "Required next proof: " +
            String(row.next_evidence || "Original buyer evidence").replaceAll("_", " ").toLowerCase()));
        const original = make("a", "source-link", "Open original Gmail thread");
        original.href = "https://mail.google.com/mail/u/?authuser=flavag83%40gmail.com#all/" +
          row.gmail_thread_id;
        original.target = "_blank";
        original.rel = "noopener noreferrer";
        original.referrerPolicy = "no-referrer";
        const details = make("details", "details");
        details.append(make("summary", null, "Original source evidence checklist"));
        const checklist = make("ol");
        for (const proof of task.needed) checklist.append(make("li", null, proof));
        details.append(checklist, make("p", "tiny",
          "Only verified original source and approved tenant authority can advance a CRM opportunity."));
        const copy = make("button", "secondary", "Copy internal review brief");
        copy.type = "button";
        copy.addEventListener("click", async () => {
          if (generation !== state.generation || !state.token ||
              Date.now() >= state.expiresAt) return;
          try {
            if (!navigator.clipboard || typeof navigator.clipboard.writeText !== "function")
              throw new Error("Clipboard is unavailable");
            await navigator.clipboard.writeText(task.brief);
            if (generation === state.generation && state.token) {
              copy.textContent = "Internal task copied — no email sent";
            }
          } catch (_) {
            if (generation === state.generation && state.token) {
              copy.textContent = "Copy unavailable — use the checklist above";
            }
          }
        });
        block.append(original, details, copy);
        fragment.append(block);
      }
      target.append(fragment);
      text(status, "5 previously reviewed partner threads · refreshed " +
        new Date(data.provider_partial_refresh_at).toLocaleString() +
        " · 0 of these are established as paying CRM clients.");
    } catch (_) {
      if (generation !== state.generation || !state.token) return;
      target.replaceChildren();
      text(summary, "Founder task queue unavailable — original source not trusted.");
      text(status, "Partner source unavailable or out of date. No old evidence substituted.");
    }
  }

  function strictInboundSource(data) {
    if (data.schema_version !== "empire.crm.first_party_inbound.v1" ||
        data.mode !== "OBSERVE" || data.read_only !== true ||
        data.execution_authority !== "none" ||
        data.trust_level !== "BUYER_STATED_UNAUTHENTICATED" ||
        data.response_consent_recorded_not_independently_verified !== true ||
        data.marketing_consent_verified !== false ||
        data.original_buyer_identity_authenticated !== false ||
        data.outbound_authorized !== false || data.payment_authorized !== false ||
        typeof data.tenant_id !== "string" || !Array.isArray(data.items) ||
        data.items.length > 20 || data.count_in_page !== data.items.length ||
        data.requested_limit !== 20)
      throw new Error("Private enquiry source contract unavailable");
    for (const row of data.items) {
      if (row.tenant_id !== data.tenant_id ||
          !/^[a-f0-9]{20}$/.test(row.enquiry_reference) ||
          !/^sha256:[a-f0-9]{64}$/.test(row.immutable_receipt_fingerprint) ||
          typeof row.business_name !== "string" || row.business_name.length > 200 ||
          typeof row.reply_email !== "string" || row.reply_email.length > 320 ||
          !/^[^\s@]+@[^\s@]+[.][^\s@]+$/.test(row.reply_email) ||
          typeof row.requested_product_code !== "string" || row.requested_product_code.length > 120 ||
          typeof row.desired_outcome !== "string" || row.desired_outcome.length > 1200 ||
          typeof row.received_at !== "string" || row.received_at.length > 64 ||
          typeof row.crm_binding_evidence_passes !== "boolean")
        throw new Error("Private enquiry data not trusted");
    }
  }

  async function loadOriginalEnquiries(generation) {
    const target = $("inbound-source-results");
    const status = $("inbound-source-status");
    target.replaceChildren();
    text(status, "Checking founder-only original sales enquiries…");
    try {
      const data = await request("/v1/revenue-crm/first-party-inbound?limit=20");
      if (generation !== state.generation || !state.token) return;
      strictInboundSource(data);
      if (!data.items.length) {
        target.append(make("p", "empty",
          "No recorded incoming first-party enquiries in this authorised page."));
      }
      const fragment = document.createDocumentFragment();
      for (const row of data.items) {
        const block = make("article", "card");
        block.append(make("span", "tag", "Buyer-stated enquiry · identity unverified"),
          make("h3", null, row.business_name || "Unnamed business"),
          make("p", "meta", "Receipt " + row.enquiry_reference + " · " + row.received_at),
          make("p", null, "Requested product: " + row.requested_product_code),
          make("p", "tiny", "Requested outcome: " + row.desired_outcome),
          make("p", "tiny", "Buyer-supplied reply address: " + row.reply_email),
          make("p", "tiny", row.crm_binding_evidence_passes ?
            "CRM binding evidence reported; verify tenant prospect separately." :
            "No verified tenant CRM prospect binding. Identity review still needed."));
        fragment.append(block);
      }
      target.append(fragment);
      text(status, data.count_in_page + " original website enquiries in this bounded page" +
        " · buyer identity unverified · not a mailing list.");
    } catch (_) {
      if (generation !== state.generation || !state.token) return;
      target.replaceChildren();
      text(status, "First-party inbox unavailable. No synthetic enquiries substituted.");
    }
  }

  function strictlyVerifiedWinPlans(data) {
    if (!data || data.schema_version !== "empire.sales_director.evidence_win_plan.v1" ||
        data.mode !== "OBSERVE" || data.execution_authority !== "NONE" ||
        data.source_coverage !== "EXACT_FIVE_REVIEWED_THREADS_NOT_COMPLETE_INBOX" ||
        data.outbound_authorized !== false || data.database_writes !== false ||
        data.crm_clients_verified !== 0 || data.calibrated_forecast_claimed !== false ||
        data.live_traffic_authorized !== false || data.buyer_capacity_verified !== false ||
        data.source_scan_incomplete !== true && data.source_scan_incomplete !== false ||
        !Array.isArray(data.plans) || data.plans.length !== 5 ||
        data.partner_win_plan_count !== 5 || !Number.isFinite(Date.parse(data.source_snapshot_at)) ||
        Date.now() - Date.parse(data.source_snapshot_at) > 86400000 ||
        Date.parse(data.source_snapshot_at) > Date.now() + 60000)
      throw new Error("Win Plan source contract untrusted");
    const seen = new Set();
    for (const row of data.plans) {
      if (!row || seen.has(row.source_thread_id) ||
          !PARTNER_ACTIONS.has(row.source_thread_id) ||
          typeof row.partner !== "string" || row.partner.length > 95 ||
          typeof row.next_internal_action !== "string" ||
          row.next_internal_action.length > 460 ||
          typeof row.buyer_win_hypothesis !== "string" ||
          row.buyer_win_hypothesis.length > 460 ||
          !["PROVIDER_PILOT_READINESS","VERIFY_ACTUAL_BUY_BOX",
            "AWAITING_EXTERNAL_SPECIFICATION","DEFER_NO_OUTREACH"].includes(row.human_review_lane) ||
          !["SOURCE_INBOUND_WAITING_FOR_FOUNDER_REVIEW",
            "LATEST_OBSERVED_MESSAGE_WAS_OUR_OUTBOUND",
            "DEFER_NO_REPLY_UNTIL_NEW_TRAFFIC_EVIDENCE"].includes(row.founder_reply_position) ||
          row.crm_client_verified !== false || row.revenue_recognised !== false ||
          row.outbound_authorized !== false || row.deal_probability !== null ||
          row.priced_deal_value !== null ||
          typeof row.next_original_evidence !== "string" ||
          !/^[A-Z0-9_]{5,120}$/.test(row.next_original_evidence) ||
          !Array.isArray(row.evidence_gap_codes) ||
          row.evidence_gap_codes.length < 4 || row.evidence_gap_codes.length > 12 ||
          row.evidence_gap_codes.some(item => !/^[A-Z0-9_]{5,120}$/.test(item)))
        throw new Error("Win Plan original evidence changed");
      seen.add(row.source_thread_id);
    }
    if (seen.size !== PARTNER_ACTIONS.size)
      throw new Error("Win Plan thread coverage incomplete");
  }

  async function loadWinPlans(generation) {
    const target = $("win-plan-results");
    target.replaceChildren();
    text($("win-plan-status"), "Checking original source-matched commercial Win Plans…");
    text($("win-plan-coverage"), "Checking original inbox evidence coverage…");
    try {
      const data = await request("/v1/revenue-crm/partner-conversations/win-plans");
      if (generation !== state.generation || !state.token) return;
      strictlyVerifiedWinPlans(data);
      const fragment = document.createDocumentFragment();
      for (const plan of data.plans) {
        const box = make("article", "card");
        box.append(make("h3", null, plan.partner),
          make("p", "meta", "Source-matched: " +
            plan.human_review_lane.replaceAll("_", " ").toLowerCase()),
          make("p", "tiny",
            plan.founder_reply_position === "DEFER_NO_REPLY_UNTIL_NEW_TRAFFIC_EVIDENCE" ?
            "On hold: no follow-up until verified traffic." :
            plan.founder_reply_position === "SOURCE_INBOUND_WAITING_FOR_FOUNDER_REVIEW" ?
            "Original inbound reply needs founder review." :
            "Latest verified direction is our outbound; await buyer response."),
          make("p", null, plan.next_internal_action),
          make("p", "tiny", "Buyer validation hypothesis: " +
            plan.buyer_win_hypothesis));
        const details = make("details");
        details.append(make("summary", null, "Evidence needed and limitations"));
        const list = make("ol");
        for (const code of plan.evidence_gap_codes)
          list.append(make("li", null, code.replaceAll("_", " ").toLowerCase()));
        details.append(list,
          make("p", "tiny", "Original source: " + plan.source_thread_id),
          make("p", "tiny", "No verified CRM client, accepted deal value, or sales probability."));
        box.append(details);
        fragment.append(box);
      }
      target.append(fragment);
      text($("win-plan-status"), data.partner_win_plan_count +
        " matched buyer Win Plans · " + data.founder_review_now_count +
        " founder reviews · " + data.awaiting_buyer_spec_count +
        " waiting on buyer details · " + data.deferred_count +
        " deferred · no sending.");
      text($("win-plan-coverage"), data.source_scan_incomplete ?
        "Only five original threads matched. Full Gmail inbox scan INCOMPLETE — new buyer replies may be missing." :
        "Full relationship snapshot marked complete; scope still limited to five verified partner threads.");
    } catch (_) {
      if (generation !== state.generation || !state.token) return;
      target.replaceChildren();
      text($("win-plan-status"), "Win Plans unavailable — original source or owner authority not verified.");
      text($("win-plan-coverage"), "No cached or synthetic Win Plans substituted.");
    }
  }

  const SOLAR_NAMES = new Set([
    "100% Renewables", "GB NRG", "Perfect Sense Energy",
    "SOL PV Group", "Solar4Good", "Sustain Commercial Solar",
  ]);
  const SOLAR_STATES = new Set([
    "POSSIBLE_MULTIPLE_NAME_MATCHES_REQUIRE_DEDUP_REVIEW",
    "POSSIBLE_NAME_MATCH_REQUIRES_IDENTITY_REVIEW",
    "NO_MATCH_IN_PARTIAL_TENANT_VIEW_NOT_EXHAUSTIVE",
    "NO_EXACT_NAME_MATCH_IN_VISIBLE_TENANT_VIEW",
  ]);

  function strictlyTenantScopedSolarPreview(data) {
    if (!data || data.schema_version !== "empire.workspace_solar_tenant_prospect_name_preview.v1" ||
        data.mode !== "OBSERVE" ||
        data.status !== "TENANT_AUTHENTICATED_PROSPECT_NAME_DUPLICATE_REVIEW_ONLY" ||
        data.execution_authority !== "none" ||
        data.tenant_scope_source !== "existing_signed_crm_principal_and_dedicated_db_reader" ||
        data.six_historical_companies_checked !== 6 ||
        data.canonical_contact_identity_verified !== false ||
        data.historical_outbound_intent_bound !== false ||
        data.tenant_contact_authority_verified !== false ||
        data.crm_mutation !== false || data.outbound_sent !== false ||
        data.payment_execution !== false ||
        typeof data.tenant_visible_window_exhaustive !== "boolean" ||
        !Number.isInteger(data.tenant_view_row_count) ||
        !Number.isInteger(data.requested_window_limit) ||
        data.requested_window_limit !== 500 ||
        data.tenant_view_row_count < 0 || data.tenant_view_row_count > 500 ||
        data.tenant_visible_window_exhaustive !== (data.tenant_view_row_count < 500) ||
        !Number.isInteger(data.possible_exact_company_name_matches) ||
        !Array.isArray(data.items) || data.items.length !== 6)
      throw new Error("Untrusted CRM solar preview contract");

    const found = new Set();
    let count = 0;
    for (const item of data.items) {
      if (!item || typeof item.company !== "string" ||
          !SOLAR_NAMES.has(item.company) || found.has(item.company) ||
          !SOLAR_STATES.has(item.status) ||
          !Number.isInteger(item.possible_name_match_count) ||
          item.possible_name_match_count < 0 ||
          !Array.isArray(item.candidate_prospect_ids) ||
          item.candidate_prospect_ids.length > 12 ||
          item.candidate_prospect_ids.length > item.possible_name_match_count ||
          item.candidate_ids_truncated !== (item.possible_name_match_count > 12) ||
          item.name_match_does_not_verify_original_contact !== true ||
          item.tenanted_prospect_row_is_not_email_sender_proof !== true ||
          item.crm_contact_binding_verified !== false ||
          item.crm_conversation_created !== false ||
          item.outbound_authorized !== false)
        throw new Error("Untrusted solar company match");
      for (const pid of item.candidate_prospect_ids) {
        if (typeof pid !== "string" ||
            !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(pid))
          throw new Error("Untrusted tenant prospect identifier");
      }
      if (item.possible_name_match_count > 1 &&
          item.status !== "POSSIBLE_MULTIPLE_NAME_MATCHES_REQUIRE_DEDUP_REVIEW")
        throw new Error("Untrusted ambiguous company status");
      if (item.possible_name_match_count === 1 &&
          item.status !== "POSSIBLE_NAME_MATCH_REQUIRES_IDENTITY_REVIEW")
        throw new Error("Untrusted singleton company status");
      if (item.possible_name_match_count === 0 &&
          item.status !== (data.tenant_visible_window_exhaustive
            ? "NO_EXACT_NAME_MATCH_IN_VISIBLE_TENANT_VIEW"
            : "NO_MATCH_IN_PARTIAL_TENANT_VIEW_NOT_EXHAUSTIVE"))
        throw new Error("Untrusted no-match status");
      found.add(item.company);
      count += item.possible_name_match_count;
    }
    if (found.size !== SOLAR_NAMES.size ||
        count !== data.possible_exact_company_name_matches)
      throw new Error("Incomplete CRM solar preview");
  }

  async function loadSolarProspectPreview(generation) {
    const target = $("solar-preview-results");
    target.replaceChildren();
    text($("solar-preview-status"), "Reading signed tenant-only company-name matches…");
    text($("solar-preview-coverage"), "Checking the 500-row CRM visibility limit…");
    try {
      const data = await request(
        "/v1/revenue-crm/workspace-solar/prospect-name-matches/preview");
      if (generation !== state.generation || !state.token) return;
      strictlyTenantScopedSolarPreview(data);
      const fragment = document.createDocumentFragment();
      for (const item of data.items) {
        const card = make("article", "card");
        card.append(make("h3", null, item.company));
        const status = item.possible_name_match_count > 1
          ? "Multiple possible name matches — manual deduplication required"
          : item.possible_name_match_count === 1
          ? "One possible company-name match — identity not verified"
          : data.tenant_visible_window_exhaustive
          ? "No exact name match in this visible tenant view"
          : "Not found in first 500 rows — further matches may exist";
        card.append(make("p", null, status));
        card.append(make("p", "tiny", "Possible name matches: " +
          item.possible_name_match_count + ". No verified contact, reply, consent or sales authority."));
        if (item.candidate_prospect_ids.length) {
          const detail = make("details");
          detail.append(make("summary", null, "Inspect internal candidate prospect IDs"));
          const list = make("ol");
          for (const pid of item.candidate_prospect_ids)
            list.append(make("li", null, pid));
          detail.append(list);
          if (item.candidate_ids_truncated)
            detail.append(make("p", "tiny", "Candidate ID list truncated."));
          card.append(detail);
        }
        fragment.append(card);
      }
      target.append(fragment);
      text($("solar-preview-status"), "Reviewed 6 solar company names · " +
        data.possible_exact_company_name_matches +
        " possible exact-name matches · read only.");
      text($("solar-preview-coverage"), data.tenant_visible_window_exhaustive
        ? "Tenant window exhaustive within the existing prospect reader: " +
          data.tenant_view_row_count + " rows."
        : "PARTIAL VIEW: first 500 tenant-visible prospect rows only. No-match results are not exhaustive.");
    } catch (_) {
      if (generation !== state.generation || !state.token) return;
      target.replaceChildren();
      text($("solar-preview-status"),
        "Solar duplicate preview unavailable — no synthetic matches shown.");
      text($("solar-preview-coverage"),
        "Signed tenant scope or private CRM source could not be verified.");
    }
  }

  async function refreshOriginalSources() {
    if (!state.token || state.sourceFetching) return;
    state.sourceFetching = true;
    const generation = state.generation;
    try {
      await Promise.all([loadOriginalPartners(generation), loadOriginalEnquiries(generation),
        loadWinPlans(generation), loadSolarProspectPreview(generation)]);
    } finally {
      state.sourceFetching = false;
    }
  }

  function trustedTenantKanban(data) {
    if (!data || data.schema_version !== "empire.departments.kanban.v1" ||
        data.source !== "canonical_department_work_queue" ||
        data.tenant_scope !== "explicit_tenant" || data.read_only !== true ||
        data.execution_authority !== "none" || !data.lanes ||
        typeof data.lanes !== "object" || Array.isArray(data.lanes)) return false;
    const names = ["ready", "running", "review", "blocked", "done", "failed"];
    if (Object.keys(data.lanes).length !== names.length) return false;
    const fields = ["work_id", "goal_key", "department_keys", "target_component",
      "priority", "status", "has_result_evidence", "has_active_lease"];
    for (const name of names) {
      const lane = data.lanes[name];
      if (!lane || !Number.isSafeInteger(lane.total) || lane.total < 0 ||
          !Array.isArray(lane.cards) || lane.cards.length > 10 ||
          typeof lane.truncated !== "boolean" ||
          (lane.total < lane.cards.length)) return false;
      for (const card of lane.cards) {
        if (!card || typeof card !== "object" ||
            Object.keys(card).some((k) => !fields.includes(k)) ||
            card.status !== name.toUpperCase() ||
            typeof card.work_id !== "string" || card.work_id.length > 150 ||
            typeof card.has_result_evidence !== "boolean" ||
            typeof card.has_active_lease !== "boolean")
          return false;
      }
    }
    return true;
  }

  async function refreshKanban() {
    if (!state.token) return;
    const generation = state.generation;
    text($("kanban-status"), "Reading authenticated, tenant-bound agent queue…");
    try {
      const data = await request("/v1/revenue-crm/department-kanban?max_cards_per_lane=10");
      if (generation !== state.generation || !state.token) return;
      if (!trustedTenantKanban(data)) throw new Error("invalid_tenant_board");
      const container = $("kanban-results");
      container.replaceChildren();
      let visible = 0;
      for (const [name, lane] of Object.entries(data.lanes)) {
        const board = make("article", "card");
        board.append(make("h3", null, name + " · " + lane.total));
        board.append(make("p", "tiny", "Tenant-bound queue · " +
          (lane.truncated ? "additional tasks held in the source" : "bounded evidence preview")));
        for (const card of lane.cards) {
          board.append(make("p", "tiny", (card.goal_key || card.work_id).slice(0, 140) +
            " · " + (card.has_result_evidence ? "has result evidence" : "unverified completion")));
          visible += 1;
        }
        container.append(board);
      }
      text($("kanban-status"), visible +
        " tenant-bound task previews; no execution authority and no unbound work exposed.");
    } catch {
      if (generation === state.generation && state.token) {
        $("kanban-results").replaceChildren();
        text($("kanban-status"), "Tenant-bound agent board unavailable; no agent work promoted.");
      }
    }
  }

  async function refreshAll() {
    await Promise.all([refresh(), refreshOriginalSources(), refreshBuyers(), refreshKanban()]);
  }

  function render() {
    const filter = $("filter").value.trim().toLowerCase();
    const visible = state.records.filter(({ prospect, action }) =>
      [prospect.prospect_id, prospect.business_name, prospect.niche,
       prospect.prospect_status, action?.recommended_internal_review]
        .some((value) => typeof value === "string" && value.toLowerCase().includes(filter)));
    const container = $("results");
    container.replaceChildren();
    if (!visible.length) {
      container.append(make("p", "empty", state.records.length
        ? "No matching loaded prospects."
        : "No CRM prospects returned by this authenticated tenant reader."));
      return;
    }
    const fragment = document.createDocumentFragment();
    for (const item of visible) fragment.append(card(item));
    container.append(fragment);
  }

  async function refreshBuyers() {
    if (!state.token) return;
    const generation = state.generation;
    text($("buyer-review-status"), "Reading tenant-scoped CRM buyers…");
    try {
      const listing = await request("/v1/revenue-crm/buyers?limit=40");
      if (generation !== state.generation || !state.token) return;
      if (listing.read_only !== true || !Array.isArray(listing.items) ||
          listing.source !== "canonical_revenue_crm_repository")
        throw new Error("untrusted_buyer_reader");
      const container = $("buyer-results");
      container.replaceChildren();
      const fragment = document.createDocumentFragment();
      for (const buyer of listing.items.slice(0, 20)) {
        if (!buyer || typeof buyer !== "object") continue;
        const card = make("article", "card");
        const name = buyer.business_name || buyer.company_name || buyer.name || "CRM buyer";
        card.append(make("h3", null, String(name).slice(0, 160)));
        card.append(make("p", "tiny", "Tenant CRM record · commercial capacity unverified"));
        fragment.append(card);
      }
      container.append(fragment);
      text($("buyer-review-status"),
        (listing.count ?? listing.items.length) + " tenant buyer rows returned; " +
        Math.min(listing.items.length, 20) + " shown. No contact approval inferred.");
    } catch {
      if (generation === state.generation && state.token) {
        $("buyer-results").replaceChildren();
        text($("buyer-review-status"), "Buyer read unavailable; no buyer status promoted.");
      }
    }
  }

  async function refresh() {
    if (state.fetching || !state.token) return;
    const generation = state.generation;
    state.fetching = true;
    $("refresh").disabled = true;
    text($("review-status"), "Reading authenticated CRM prospects and evidence reviews…");
    try {
      const listing = await request("/v1/revenue-crm/prospects?limit=" + LIMIT);
      if (generation !== state.generation) return;
      if (listing.read_only !== true || !Array.isArray(listing.items))
        throw new Error("CRM reader did not return a read-only prospect list");
      const prospects = listing.items.slice(0, DETAIL_LIMIT).filter((p) =>
        p && typeof p.prospect_id === "string" && p.prospect_id.length > 0);
      const rows = [];
      for (let i = 0; i < prospects.length; i += BATCH) {
        const group = await Promise.all(prospects.slice(i, i + BATCH).map(async (prospect) => {
          try {
            const action = await request(
              "/v1/revenue-crm/prospects/" + encodeURIComponent(prospect.prospect_id) +
              "/commercial-action-review"
            );
            return { prospect, action, error: null };
          } catch (err) {
            return { prospect, action: null, error: "Evidence endpoint not available" };
          }
        }));
        if (generation !== state.generation || !state.token) return;
        rows.push(...group);
      }
      rows.sort((a, b) => {
        const rank = (v) => Number.isInteger(v.action?.priority_rank)
          ? v.action.priority_rank : 9;
        return rank(a) - rank(b);
      });
      if (generation !== state.generation || !state.token) return;
      state.records = rows;
      $("total").textContent = String(listing.count ?? listing.items.length);
      $("held").textContent = String(rows.filter((r) => r.action?.contact_hold === true).length);
      $("reviews").textContent = String(rows.filter((r) =>
        r.action?.status === "INTERNAL_REVIEW_ONLY").length);
      $("missing").textContent = String(rows.filter((r) => !r.action).length);
      text($("review-status"), rows.length + " prospects reviewed (up to " + DETAIL_LIMIT +
        "); " + (listing.count ?? listing.items.length) +
        " currently visible in this tenant. Missing original source proof remains a review blocker.");
      const validActions = rows.filter((r) =>
        r.action?.schema_version === "empire.revenue_crm_commercial_action_review.v1" &&
        r.action?.mode === "OBSERVE" &&
        r.action?.execution_authority === "none" &&
        r.action?.send_authorized === false).length;
      text($("sales-actions-workspace-status"), validActions +
        " signed-tenant internal action reviews; " + (rows.length - validActions) +
        " held or unavailable. No sends, stage changes or payment authority.");
      render();
    } catch (err) {
      if (state.token) {
        text($("review-status"), "CRM read unavailable — no prospect or buyer evidence was promoted.");
        text($("sales-actions-workspace-status"), "Action source unavailable; no sales authority implied.");
      }
    } finally {
      state.fetching = false;
      $("refresh").disabled = false;
    }
  }

  $("login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    $("sign-in").disabled = true;
    text($("login-status"), "Verifying existing CRM credentials…");
    const email = $("account").value.trim();
    const password = $("password").value;
    const tenant_id = $("tenant").value.trim();
    $("password").value = "";
    try {
      if (location.protocol !== "https:" && !["localhost", "127.0.0.1"].includes(location.hostname))
        throw new Error("Secure CRM origin required");
      const result = await request("/v1/revenue-crm/auth/login", {
        method: "POST", body: { email, password, tenant_id },
      });
      if (result.token_type !== "Bearer" || typeof result.access_token !== "string" ||
          result.access_token.length < 100 || result.access_token.length > 6000 ||
          result.scope !== "crm:read" || !Number.isInteger(result.expires_in) ||
          result.expires_in < 1 || result.expires_in > 900)
        throw new Error("Invalid signed CRM session");
      state.token = result.access_token; // In-memory only. Never persistent browser storage.
      state.generation += 1;
      const generation = state.generation;
      state.expiresAt = Date.now() + result.expires_in * 1000;
      state.expiryTimer = setTimeout(() => {
        if (generation === state.generation) clearSession("CRM session expired. Sign in again.");
      }, result.expires_in * 1000);
      $("login-panel").hidden = true;
      $("review-panel").hidden = false;
      $("workspace-nav").hidden = false;
      text($("login-status"), "");
      await refreshAll();
    } catch {
      if (!state.token) text($("login-status"),
        "Sign-in unavailable or credentials were not accepted. Use your approved CRM account and tenant ID.");
    } finally {
      $("sign-in").disabled = false;
    }
  });
  $("sign-out").addEventListener("click", () => clearSession("Signed out of this browser session."));
  $("refresh").addEventListener("click", refreshAll);
  $("filter").addEventListener("input", render);
  window.addEventListener("pagehide", () => clearSession("CRM browser session closed."));
})();
