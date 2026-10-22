export type ApiResult<T> = {
  ok: boolean;
  status: number | null;
  data: T | null;
  reason?: string;
};

export type Health = {
  execution_mode?: string;
  mutations_enabled?: boolean;
  repository_available?: boolean;
  api_contract_version?: string;
};

export type Summary = Health & {
  stored_metrics?: string | {
    pages?: number;
    opportunities?: number;
    indexed_pages?: number;
    open_alerts?: number;
    revenue_cents?: number;
  };
};

export type SearchConsoleStatus = {
  enabled: boolean;
  configured: boolean;
  available: boolean;
  reason: string;
  site_url?: string | null;
};

export type GscDailyChart = {
  schema_version: "empire.search.gsc_daily_chart_evidence.v1";
  status: "DATE_DIMENSION_ROWS_OBSERVED" | "HELD_GSC_DAILY_SOURCE_UNAVAILABLE";
  source: "google_search_console_date_dimension";
  mode: "READ_ONLY";
  date_window: [string, string];
  days_observed: number | null;
  days_missing_unreported: string[] | null;
  rows: Array<{
    date: string;
    clicks: number;
    impressions: number;
    gsc_reported_ctr: number;
    gsc_reported_average_position: number;
  }>;
  reported_date_dimension_clicks: number | null;
  reported_date_dimension_impressions: number | null;
  missing_days_treated_as_zero: false;
  gsc_average_position_is_independent_serp_rank: false;
  independent_google_rank_positions_verified: false;
  buyer_enquiries_verified: false;
  realised_revenue_verified: false;
  execution_authority: "NONE";
};

export type SeoDepartmentReview = {
  schema_version: "empire.search_growth.department_integration.v1";
  status: "DEPARTMENT_CONNECTED_EVIDENCE_GAPS_OPEN";
  mode: "OBSERVE";
  gsc_final_page_window: [string, string];
  gsc_daily_chart?: GscDailyChart;
  gsc_returned_page_rows: number;
  gsc_returned_page_sample_clicks: number;
  gsc_returned_page_sample_impressions: number;
  legacy_missing_404_count_in_returned_page_sample: number;
  legacy_missing_404_impressions_in_returned_page_sample: number;
  legacy_missing_404_clicks_in_returned_page_sample: number;
  legacy_404_editorial_category_counts: Record<string, number>;
  legacy_404_core_topic_editorial_review_count: number;
  legacy_404_off_core_retain_404_count: number;
  semantic_live_priority_pages_checked: number;
  semantic_editorial_review_candidates: number;
  semantic_owned_pages_commercial_route_verified: boolean;
  search_fabric_cache_files_observed: number;
  search_fabric_cache_fresh_candidates_24h: number;
  search_fabric_cache_stale_candidates: number;
  search_fabric_cache_invalid_envelopes: number;
  search_rankings_verified: false;
  independent_google_rank_positions_verified: false;
  external_ai_answer_citation_verified: boolean;
  external_geo_mentions_verified: boolean;
  buyer_enquiries_verified: false;
  realised_revenue_verified: false;
  growth_specialist_desks: number;
  research_campaigns: number;
  open_gates: string[];
  customer_identifiers_disclosed: false;
  publisher_mutation_authorized: false;
  execution_authority: "NONE";
};

export type CollectionEnvelope = {
  available: boolean;
  source: string;
  count: number;
  limit: number;
  items: Array<Record<string, unknown>>;
};

function apiBase(): string | null {
  const value = process.env.EMPIRE_SEARCH_API_BASE_URL?.trim();
  return value ? value.replace(/\/$/, "") : null;
}

async function request<T>(path: string): Promise<ApiResult<T>> {
  const base = apiBase();
  if (!base) {
    return { ok: false, status: null, data: null, reason: "api_base_not_configured" };
  }

  try {
    const response = await fetch(base + path, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      let reason = "http_" + response.status;
      try {
        const body = (await response.json()) as { detail?: string };
        if (body.detail) reason = body.detail;
      } catch {
        // Keep the status-based reason.
      }
      return { ok: false, status: response.status, data: null, reason };
    }
    return { ok: true, status: response.status, data: (await response.json()) as T };
  } catch {
    return { ok: false, status: null, data: null, reason: "api_unreachable" };
  }
}

export async function getTechnicalData() {
  const [health, indexation, decay, cannibalisation] = await Promise.all([
    request<Health>("/v1/search/health"),
    request<CollectionEnvelope>("/v1/search/indexation?limit=20"),
    request<CollectionEnvelope>("/v1/search/decay?limit=20"),
    request<CollectionEnvelope>("/v1/search/cannibalisation?limit=20"),
  ]);
  return { health, indexation, decay, cannibalisation };
}

export async function getCompetitorData() {
  const [health, opportunities] = await Promise.all([
    request<Health>("/v1/search/health"),
    request<CollectionEnvelope>("/v1/search/opportunities?limit=50"),
  ]);
  return { health, opportunities };
}

export async function getOpportunityData() {
  const [health, opportunities] = await Promise.all([
    request<Health>("/v1/search/health"),
    request<CollectionEnvelope>("/v1/search/opportunities?limit=100"),
  ]);
  return { health, opportunities };
}

export async function getEvidenceTimelineData() {
  const [health, opportunities, indexation, alerts, revenue] = await Promise.all([
    request<Health>("/v1/search/health"),
    request<CollectionEnvelope>("/v1/search/opportunities?limit=50"),
    request<CollectionEnvelope>("/v1/search/indexation?limit=50"),
    request<CollectionEnvelope>("/v1/search/alerts?limit=50"),
    request<CollectionEnvelope>("/v1/search/revenue?limit=50"),
  ]);
  return { health, opportunities, indexation, alerts, revenue };
}

export async function getInternalLinkData() {
  const [health, pages, links] = await Promise.all([
    request<Health>("/v1/search/health"),
    request<CollectionEnvelope>("/v1/search/pages?limit=200"),
    request<CollectionEnvelope>("/v1/search/internal-links?limit=500"),
  ]);
  return { health, pages, links };
}

export async function getAuthorityData() {
  const [health, backlinks, aiVisibility] = await Promise.all([
    request<Health>("/v1/search/health"),
    request<CollectionEnvelope>("/v1/search/backlinks?limit=200"),
    request<CollectionEnvelope>("/v1/search/ai-visibility?limit=200"),
  ]);
  return { health, backlinks, aiVisibility };
}

export async function getDashboardData() {
  const [health, summary, searchConsole, pages, opportunities, alerts, revenue] =
    await Promise.all([
      request<Health>("/v1/search/health"),
      request<Summary>("/v1/search/summary"),
      request<SearchConsoleStatus>("/v1/search/search-console/status"),
      request<CollectionEnvelope>("/v1/search/pages?limit=6"),
      request<CollectionEnvelope>("/v1/search/opportunities?limit=6"),
      request<CollectionEnvelope>("/v1/search/alerts?limit=6"),
      request<CollectionEnvelope>("/v1/search/revenue?limit=6"),
    ]);
  return { health, summary, searchConsole, pages, opportunities, alerts, revenue };
}

export async function getRevenueAttributionData() {
  const [health, revenue] = await Promise.all([
    request<Health>("/v1/search/health"),
    request<CollectionEnvelope>("/v1/search/revenue?limit=200"),
  ]);
  return { health, revenue };
}

/** Read-only search-department totals; no client credentials or side effects. */
export function getSeoDepartmentReview() {
  return request<SeoDepartmentReview>("/v1/search/department/review");
}


// Existing private Search Intelligence Quora editorial review: research only.
export type QuoraReviewTopic = {
  item_id: string;
  vertical: "roofing" | "hvac" | "solar" | "dental" | "legal" | "b2b";
  specialist_editorial_review_required: boolean;
  question_theme: string;
  topic: string;
  proposed_owned_page: string;
  source_query_plan: string;
  broader_discovery_query_plan: string;
  proposed_page_public_verified: false;
  editorial_review_required: true;
  intent_hypothesis: string;
  sector_hypothesis: string;
  answer_publication_state: "RESEARCH_ONLY";
};

export type QuoraResearchReview = {
  schema_version: "empire.search_intelligence.quora_research.v1";
  mode: "OBSERVE";
  existing_search_fabric: "SOURCE_CANDIDATES_ONLY";
  topic_count: number;
  vertical_topic_counts: Record<string, number>;
  topics: QuoraReviewTopic[];
  source_candidates_count: number;
  fresh_source_candidate_count: number;
  verified_quora_questions: number;
  published_answers_verified: number;
  owned_seo_sessions_verified: number;
  third_party_visits_first_party: false;
  affiliate_links_authorized: false;
  automated_posting_authorized: false;
  owner_editorial_signoff_verified: false;
  organic_buyer_enquiries_verified: false;
  buyer_accepted_calls_verified: false;
  realized_revenue_verified: false;
  external_requests_performed: false;
  production_writes: false;
  execution_authority: "NONE";
};

export function getQuoraResearchReview() {
  return request<QuoraResearchReview>("/v1/search/quora/review");
}


/** SEO Jev typed-decision readiness; this API never invokes a model. */
export type QuoraJevShadowReview = {
  schema_version: "empire.search.quora_jev_shadow_readiness.v1";
  mode: "OBSERVE";
  provider_key: "disabled";
  provider_invoked: false;
  external_requests_performed: false;
  external_tokens_billed: 0;
  jev_model_predictions_count: 0;
  real_labeled_case_count: 0;
  reviewed_topics_count: number;
  vertical_topic_counts: Record<string, number>;
  cases_ready_for_model_evaluation: 0;
  typed_decision_task_readiness: {
    promotion_review_ready: false;
    shadow_eval_ready: false;
    blockers: string[];
  };
  jev_use_case_readiness: {
    provider_activation: false;
    review_ready: false;
    warnings: string[];
  };
  publishing_authorized: false;
  buyer_routing_authorized: false;
  production_writes: false;
  execution_authority: "NONE";
};

export function getQuoraJevShadowReview() {
  return request<QuoraJevShadowReview>("/v1/search/quora/jev-shadow/review");
}


/** High-level Jev SEO task portfolio: observable evidence, no model execution. */
export type SeoJevDepartmentReview = {
  schema_version: "empire.search.jev_department_portfolio.v1";
  mode: "OBSERVE";
  scope: "EXISTING_SEO_DEPARTMENT";
  task_count: number;
  aggregate_observed_lane_count: number;
  independent_case_evaluation_ready_count: 0;
  origin_quora_questions_verified: 0;
  jev_provider: "disabled";
  jev_inference_calls: 0;
  jev_scores_generated: 0;
  provider_keys_accessed: false;
  external_requests_performed_by_review: false;
  typed_decision_plan_only: true;
  database_writes: false;
  publication_authority: false;
  buyer_outreach_authority: false;
  payment_authority: false;
  execution_authority: "NONE";
  task_board: Array<{
    task_id: string;
    title: string;
    existing_owner: string;
    risk_class: "medium" | "high";
    evidence_state: "AGGREGATE_REVIEW_AVAILABLE" | "ORIGINAL_EVIDENCE_REQUIRED";
    next_evidence_action: string;
    jev_decision_goal: string;
    aggregate_scalar_evidence: Record<string, number>;
    labeled_real_cases: 0;
    jev_prediction: null;
    jev_score: null;
    jev_confidence: null;
    model_evaluation_authorized: false;
    automatic_execution_authorized: false;
    publishing_authorized: false;
  }>;
};

export function getSeoJevDepartmentReview() {
  return request<SeoJevDepartmentReview>("/v1/search/jev/department/review");
}


/** One verified Jev pilot receipt. Fetch never invokes a model or bills. */
export type JevRealPilotReceipt = {
  schema_version: "empire.search.jev_one_shot_private_receipt_review.v1";
  mode: "ONE_SHOT_SHADOW_ONLY";
  provider_key: "openrouter_typesafe_jev";
  model: string;
  actual_jev_inference_calls_observed: 1;
  decision_label: string;
  decision_confidence: number;
  human_review_yes_probability: number;
  investigation_priority_score: number;
  usage_input_tokens: number;
  usage_cost_usd: number;
  source_scope: "FIRST_PARTY_GSC_PAGE_SAMPLE_AGGREGATES_ONLY";
  accuracy_or_ground_truth_verified: false;
  independent_eval_cases_ready: 0;
  provider_enabled_for_unattended_runs: false;
  new_provider_calls_triggered: 0;
  replay_billing_authorized: false;
  publication_authorized: false;
  outreach_or_payment_authorized: false;
  external_requests_performed_by_review: false;
  database_writes: false;
  execution_authority: "NONE";
};

export function getJevRealPilotReceipt() {
  return request<JevRealPilotReceipt>("/v1/search/jev/pilot/receipt");
}


/** A pinned private receipt: real source observations, zero human labels. */
export type JevOriginalPageEvidenceSummary = {
  schema_version: "empire.search.jev_original_page_review_summary.v1";
  mode: "OBSERVE";
  observed_url_case_count: number;
  observed_impressions_from_sample: number;
  reviewed_human_labels: 0;
  benchmark_ready_cases: 0;
  original_page_evidence_required: true;
  authenticated_human_review_required: true;
  training_rights_verified: false;
  automatic_model_calls: false;
  publication_authority: false;
  private_receipt_sha256: string;
  case_details_exposed: false;
  proposed_jev_model_outputs: 0;
  current_review_state: "PENDING_ORIGINAL_PAGE_AND_AUTHENTICATED_HUMAN_REVIEW";
  provider_inference_from_status_read: false;
  automatic_model_evaluation_enabled: false;
  external_requests_performed: false;
  database_writes: false;
  execution_authority: "NONE";
};

export function getJevOriginalPageEvidenceSummary() {
  return request<JevOriginalPageEvidenceSummary>("/v1/search/jev/evidence/summary");
}


/** Bounded local-model SEO investigation; no source URLs or autonomous actions. */
export type SeoAiFirstSummary = {
  schema_version: "empire.search.ai_first_seo_summary.v1";
  mode: "OBSERVE";
  observed_cases_reviewed: 30;
  local_model_inference_attempts: 30;
  model_candidates_returned: number;
  deep_ai_research_queue_count: number;
  human_labels_created: 0;
  benchmark_accuracy_measured: false;
  original_content_verified: false;
  automatic_jev_inference_enabled: false;
  external_paid_jev_calls: 0;
  source_paths_exposed: false;
  publication_authority: false;
  execution_authority: "NONE";
  shadow_model: "convaiinnovations/laya:onnx";
  provider: "existing_local_laya_http";
  model_output_status: "UNVERIFIED_RESEARCH_CANDIDATES";
  receipt_read_calls_to_model: 0;
  original_404_content_recovery_required: true;
  review_recommended_to_ai_research_desk: true;
};

export function getSeoAiFirstSummary() {
  return request<SeoAiFirstSummary>("/v1/search/jev/ai-first/summary");
}


/** Six pinned TypeSafe Jev batches; 30 public-owned URL paths, never exposed. */
export type JevCaseModelSummary = {
  schema_version: "empire.search.jev_original_page_case_summary.v1";
  mode: "REAL_PROVIDER_EVALUATION_SHADOW";
  provider_key: "openrouter_typesafe_jev";
  verified_provider_batches: 6;
  original_page_cases_assessed: 30;
  validated_model_responses: 30;
  model_choice_counts: Record<string, number>;
  model_confidence_at_least_0_80: number;
  model_confidence_below_0_80: number;
  reported_cost_usd: number;
  model_prediction_accuracy_verified: false;
  original_page_copy_verified: false;
  model_outputs_are_human_labels: false;
  model_research_recommendations_are_authorised_fixes: false;
  unattended_provider_calls_enabled: false;
  new_inference_requests_during_status: 0;
  external_buyer_or_personal_data_sent: false;
  case_url_paths_exposed: false;
  manual_publication_or_redirect_authority: false;
  execution_authority: "NONE";
};

export function getJevCaseModelSummary() {
  return request<JevCaseModelSummary>("/v1/search/jev/cases/summary");
}


/** Deployment shortlist derived from actual GSC + six pinned Jev receipts. */
export type JevSeoDeploymentSummary = {
  schema_version: "empire.search.jev_organic_deployment_summary.v1";
  mode: "RESEARCH_TO_RELEASE_READY";
  original_url_observations: 30;
  jev_predictions_observed: 30;
  core_topic_research_observations: 15;
  off_core_urls_retained_404: 15;
  sample_page_impressions: 44;
  sample_page_clicks: 0;
  research_workstreams: Array<{
    workstream: string;
    case_count: number;
    sample_impressions: number;
    status: "RESEARCH_ONLY" | "RETAIN_404_MONITOR";
  }>;
  website_changes_live: false;
  first_party_source_content_verified: false;
  seo_traffic_lift_verified: false;
  qualified_leads_verified: false;
  realised_revenue_verified: false;
  model_calls_during_summary: 0;
  personal_data_or_paths_disclosed: false;
  automatic_publishing_or_redirects_authorised: false;
  execution_authority: "NONE";
  validated_private_receipt_sha256: string;
  per_case_urls_exposed: false;
  proposed_deployment_scope: "ORIGINAL_EDUCATIONAL_CONTENT_ONLY";
  publication_approval_required: true;
  redirect_approval_required: true;
  new_calls_or_billing_triggered: 0;
};

export function getJevSeoDeploymentSummary() {
  return request<JevSeoDeploymentSummary>("/v1/search/jev/deployment/summary");
}
