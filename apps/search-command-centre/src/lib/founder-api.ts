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
