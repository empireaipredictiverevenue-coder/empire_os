import "server-only";

// This is a server-to-loopback bridge, not an identity authority. The API
// independently verifies the signed Cloudflare Access JWT and Founder subject.
// The only override is a fixed loopback port for ephemeral integration tests.
// Live configuration always uses the existing Founder API on port 8766.
const RESEARCH_API =
  process.env.EMPIRE_RESEARCH_ISOLATED_STAGE === "1"
    ? "http://127.0.0.1:3097/v1/founder-research-products"
    : "http://127.0.0.1:8766/v1/founder-research-products";

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


// The live Founder Console is SSH-forwarded and is NOT a Cloudflare Access app.
// Preserve verified Cloudflare JWT by default. This opt-in transport can only
// operate on the local-only Founder Console port after independently verified
// ingress isolation and an operator-provisioned secret. SSH is the human login.
export function isSshFounderResearchMode(): boolean {
  return process.env.EMPIRE_FOUNDER_RESEARCH_AUTH_MODE === "ssh_loopback";
}

function sshPrivateBridgeSecret(): string | null {
  const value = process.env.EMPIRE_RESEARCH_SSH_BRIDGE_SECRET ?? "";
  if (process.env.EMPIRE_RESEARCH_SSH_PRIVATE_ENABLED !== "1"
      || process.env.EMPIRE_PRIVATE_FOUNDER_INGRESS_REVIEWED !== "1"
      || !/^[A-Za-z0-9_-]{48,256}$/.test(value)) return null;
  return value;
}

export function sshFounderRequestIsLocal(headers: Pick<Headers, "get">): boolean {
  if (!isSshFounderResearchMode() || !sshPrivateBridgeSecret()) return false;
  const port = process.env.EMPIRE_RESEARCH_ISOLATED_STAGE === "1" ? "3098" : "3001";
  const host = (headers.get("host") ?? "").toLowerCase();
  const allowed = new Set([`localhost:${port}`, `127.0.0.1:${port}`]);
  if (!allowed.has(host)) return false;
  const forwardHost = headers.get("x-forwarded-host")?.toLowerCase();
  if (forwardHost && !allowed.has(forwardHost)) return false;
  const forwardedFor = headers.get("x-forwarded-for");
  if (forwardedFor !== null && !["127.0.0.1", "::1"].includes(forwardedFor.trim())) return false;
  if (["cf-connecting-ip", "cf-ray", "x-real-ip", "forwarded", "via"].some(
    key => headers.get(key) !== null
  )) return false;
  return true;
}

export function sshFounderServerCredential(headers: Pick<Headers, "get">): string | null {
  return sshFounderRequestIsLocal(headers) ? sshPrivateBridgeSecret() : null;
}
