export type FounderStage = {
  stage?: string;
  observed?: boolean | null;
  evidence_ref?: string | null;
  detail?: string | null;
};

export type FounderDashboard = {
  mode?: string;
  generated_at?: string;
  commercial_loop?: {
    available?: boolean;
    observed_at?: string | null;
    loop_complete?: boolean;
    blocker_state?: string | null;
    highest_priority_blocker?: string | null;
    operating_state?: {
      class?: string;
      next_event?: string | null;
      founder_action_required?: boolean;
    };
    stages?: FounderStage[];
  };
  astra?: {
    available?: boolean;
    mode?: string;
    fresh?: boolean | null;
    freshness_reason?: string | null;
    observed?: Record<string, unknown>;
    board?: Array<Record<string, unknown>>;
    calibration?: Record<string, unknown>;
  };
  source_health?: {
    available?: boolean;
    observed_at?: string | null;
    source?: string | null;
    metro?: string | null;
    endpoint_healthy?: boolean | null;
    end_to_end_healthy?: boolean | null;
    candidates_seen?: number | null;
    quality_accepted?: number | null;
    quality_rejected?: number | null;
    canonical_ingest_authorized?: boolean | null;
    canonical_ingest_scheduled?: boolean | null;
    blockers?: string[];
    errors?: string[];
  };
  acquisition?: {
    available?: boolean;
    started_at?: string | null;
    source?: string | null;
    metro?: string | null;
    real_data_only?: boolean | null;
    recorded_ok?: boolean | null;
    returncode?: number | null;
  };
  phases?: Array<{
    phase?: number;
    title?: string;
    state?: string;
    verified_markers?: number;
  }>;
};

export type FounderApiResult = {
  ok: boolean;
  status: number | null;
  data: FounderDashboard | null;
  reason: string | null;
};

function apiBase() {
  const value =
    process.env.EMPIRE_API_BASE_URL?.trim() ??
    process.env.EMPIRE_SEARCH_API_BASE_URL?.trim();
  return value ? value.replace(/\/$/, "") : null;
}

export async function getFounderDashboard(): Promise<FounderApiResult> {
  const base = apiBase();
  if (!base) {
    return {
      ok: false,
      status: null,
      data: null,
      reason: "api_base_not_configured",
    };
  }

  try {
    const response = await fetch(
      base + "/v1/founder-dashboard/overview",
      {
        cache: "no-store",
        headers: { Accept: "application/json" },
      },
    );

    if (!response.ok) {
      let reason = "http_" + response.status;
      try {
        const body = await response.json();
        if (body?.detail) reason = String(body.detail);
      } catch {}
      return {
        ok: false,
        status: response.status,
        data: null,
        reason,
      };
    }

    return {
      ok: true,
      status: response.status,
      data: (await response.json()) as FounderDashboard,
      reason: null,
    };
  } catch {
    return {
      ok: false,
      status: null,
      data: null,
      reason: "api_unreachable",
    };
  }
}


export type FounderIntelligenceNode = {
  key: string;
  name: string;
  market: string;
  sensors: string[];
  products: string[];
  opportunity_types: string[];
  execution_authority: string;
  runtime_evidence?: {
    observed_sources?: string[];
    current_source_match?: boolean;
    opportunity_count?: number | null;
    revenue_cents?: number | null;
    realized_gp_cents?: number | null;
    counts_unknown?: boolean;
  };
};

export type FounderIntelligenceNodes = {
  schema_version?: string;
  mode?: string;
  execution_authority?: string;
  node_count?: number;
  current_observed_sources?: string[];
  nodes?: FounderIntelligenceNode[];
};

export type FounderDataProduct = {
  key: string;
  name: string;
  category: string;
  source_nodes: string[];
  deliverables: string[];
  delivery_modes: string[];
  required_evidence: string[];
  compatible_usage_modes: string[];
  commercial_model: string;
  pricing_cents?: number | null;
  execution_authority: string;
};

export type FounderDataProducts = {
  schema_version?: string;
  mode?: string;
  execution_authority?: string;
  products?: FounderDataProduct[];
};

export type FounderOps = {
  available?: boolean;
  observed_at?: string;
  healthy?: boolean | null;
  business_blocker?: string | null;
  sentinel?: {
    findings?: Array<Record<string, unknown>>;
    repair_plan?: Array<Record<string, unknown>>;
  };
  healer?: {
    proposed?: number;
    executed?: number;
    results?: Array<Record<string, unknown>>;
  };
  incident_manager?: {
    incident_count?: number;
    requires_escalation?: boolean;
    diagnoses?: Array<Record<string, unknown>>;
  };
};

export type FounderReadResult<T> = {
  ok: boolean;
  status: number | null;
  data: T | null;
  reason: string | null;
};

async function getFounderRead<T>(
  path: string,
): Promise<FounderReadResult<T>> {
  const base = apiBase();
  if (!base) {
    return {
      ok: false,
      status: null,
      data: null,
      reason: "api_base_not_configured",
    };
  }

  try {
    const response = await fetch(base + path, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      return {
        ok: false,
        status: response.status,
        data: null,
        reason: "http_" + response.status,
      };
    }
    return {
      ok: true,
      status: response.status,
      data: (await response.json()) as T,
      reason: null,
    };
  } catch {
    return {
      ok: false,
      status: null,
      data: null,
      reason: "api_unreachable",
    };
  }
}

export function getFounderIntelligenceNodes() {
  return getFounderRead<FounderIntelligenceNodes>(
    "/v1/founder-intelligence-nodes",
  );
}

export function getFounderDataProducts() {
  return getFounderRead<FounderDataProducts>(
    "/v1/founder-data-products",
  );
}

export function getFounderOps() {
  return getFounderRead<FounderOps>("/v1/founder-ops/status");
}


export type FounderDailyResults = {
  schema_version?: string;
  date?: string;
  generated_at?: string;
  headline?: {
    technical_health?: boolean | null;
    commercial_blocker?: string | null;
    blocker_owner?: string | null;
    blocker_authority?: string | null;
    recognized_revenue_events?: number | null;
    realized_gp_events?: number | null;
  };
  commercial_funnel?: {
    omega_observations?: number | null;
    approved_buyers?: number | null;
    outbound_authorized?: number | null;
    outbound_sent?: number | null;
    commercial_buyer_replies?: number | null;
    verified_terms?: number | null;
    payment_requests?: number | null;
    verified_payments?: number | null;
    fulfilments?: number | null;
    recognized_revenue_events?: number | null;
    realized_gp_events?: number | null;
  };
  acquisition?: Record<string, unknown>;
  qualification?: Record<string, unknown>;
  buyer_review?: Record<string, unknown>;
  intent_and_pain?: {
    observations?: number | null;
    high_intent?: number | null;
    medium_intent?: number | null;
    by_source?: Record<string, number>;
    pain_points?: Record<string, number>;
    opportunity_routes?: number | null;
  };
  search_and_seo?: {
    aeo_asset_count?: number | null;
    aeo_status_counts?: Record<string, number>;
    aeo_risk_counts?: Record<string, number>;
    timesfm_shadow_enabled?: boolean;
    traffic_forecast_mode?: string;
  };
  coder?: {
    pending?: number;
    running?: number;
    completed?: number;
    failed?: number;
  };
  reliability?: {
    healthy?: boolean | null;
    incident_count?: number | null;
    safe_repairs_queued?: number | null;
    current_blocker?: string | null;
  };
  security?: {
    supabase_audit_available?: boolean;
    findings?: Record<string, number>;
    trust_snapshot_available?: boolean;
    trust_ready?: boolean | null;
  };
};

export type FounderDailyResultsHistory = {
  schema_version?: string;
  count?: number;
  items?: FounderDailyResults[];
};

export function getFounderDailyResults() {
  return getFounderRead<FounderDailyResults>(
    "/v1/founder-daily-results/latest",
  );
}

export function getFounderDailyResultsHistory(limit = 14) {
  return getFounderRead<FounderDailyResultsHistory>(
    `/v1/founder-daily-results/history?limit=${limit}`,
  );
}
