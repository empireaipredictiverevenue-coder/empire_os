import "server-only";

// This is a server-to-loopback bridge, not an identity authority. The API
// independently verifies the signed Cloudflare Access JWT and Founder subject.
const RESEARCH_API = "http://127.0.0.1:8766/v1/founder-research-products";

export function forwardedAccessAssertion(value: string | null): string | null {
  if (!value || value.length > 8192 || value.split(".").length !== 3) return null;
  return value;
}

export async function requestPrivateResearch(
  endpoint: "catalog" | "preview",
  assertion: string,
  data?: unknown,
): Promise<{ ok: boolean; status: number; data: unknown }> {
  try {
    const response = await fetch(`${RESEARCH_API}/${endpoint}`, {
      method: endpoint === "catalog" ? "GET" : "POST",
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${assertion}`,
        Accept: "application/json",
        ...(endpoint === "preview" ? { "Content-Type": "application/json" } : {}),
      },
      ...(endpoint === "preview" ? { body: JSON.stringify(data) } : {}),
      signal: AbortSignal.timeout(endpoint === "catalog" ? 12000 : 90000),
    });
    const body = await response.json();
    return { ok: response.ok, status: response.status, data: body };
  } catch {
    return { ok: false, status: 503, data: { detail: "Research API unavailable" } };
  }
}
