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
