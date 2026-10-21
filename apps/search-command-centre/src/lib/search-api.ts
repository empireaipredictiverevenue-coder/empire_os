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
