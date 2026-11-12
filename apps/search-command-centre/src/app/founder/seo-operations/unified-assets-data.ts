import { dailyWindow } from "./gsc-daily";

export const ASSETS = [
  ["Revenue leak check", "https://empire-ai.co.uk/tools/revenue-leak-check"],
  ["Replacement vs repair", "https://empire-ai.co.uk/roofing/replacement-vs-repair"],
  ["Installation checklist", "https://empire-ai.co.uk/roofing/installation-checklist"],
  ["Roofing AEO · DFW", "https://empire-ai.co.uk/aeo/roofing/DFW"],
] as const;
type RecordValue = Record<string, unknown>;
function record(value: unknown): RecordValue {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Invalid evidence");
  return value as RecordValue;
}
function requireEvidence(ok: boolean): asserts ok { if (!ok) throw new Error("Invalid evidence"); }
const count = (n: unknown): n is number => typeof n === "number" && Number.isSafeInteger(n) && n >= 0;
export type PageMetric = { clicks: number; impressions: number; ctr: number; position: number };
export function validatePages(raw: unknown, start: string, end: string) {
  const d = record(raw);
  requireEvidence(d.schema_version === "empire.search.gsc_page_observations.v1" && d.mode === "OBSERVE" &&
    d.available === true && d.source === "google_search_console" && d.site_url === "sc-domain:empire-ai.co.uk" &&
    d.data_state === "final" && d.execution_authority === "none" &&
    Array.isArray(d.dimensions) && d.dimensions.length === 1 && d.dimensions[0] === "page" &&
    Array.isArray(d.window) && d.window.length === 2 && d.window[0] === start && d.window[1] === end &&
    Array.isArray(d.items) && d.items.length <= 250 && d.count === d.items.length && d.limit === 250);
  for (const flag of ["indexation_verified", "attributed_buyer_verified", "actual_revenue_verified"]) {
    requireEvidence(d[flag] === undefined || d[flag] === false);
  }
  const seen = new Set<string>();
  const matched = new Map<string, PageMetric>();
  for (const item of d.items) {
    const r = record(item);
    requireEvidence(Array.isArray(r.keys) && r.keys.length === 1 && typeof r.keys[0] === "string");
    const url = r.keys[0];
    const parsed = new URL(url);
    // Domain-property GSC can legitimately include www, HTTP and query/encoded
    // variants. Validate those records but match ONLY exact pinned HTTPS assets.
    requireEvidence(url.length <= 2048 &&
      (parsed.protocol === "https:" || parsed.protocol === "http:") &&
      (parsed.hostname === "empire-ai.co.uk" || parsed.hostname.endsWith(".empire-ai.co.uk")) &&
      !parsed.username && !parsed.password && !parsed.hash && !parsed.port &&
      parsed.href === url && !/[\s\\]/.test(url) && !seen.has(url));
    seen.add(url);
    requireEvidence(count(r.clicks) && count(r.impressions) && r.clicks <= r.impressions &&
      typeof r.ctr === "number" && Number.isFinite(r.ctr) && r.ctr >= 0 && r.ctr <= 1 &&
      typeof r.position === "number" && Number.isFinite(r.position) && r.position >= 0);
    if (ASSETS.some(([, allowed]) => allowed === url)) {
      matched.set(url, { clicks: r.clicks, impressions: r.impressions, ctr: r.ctr, position: r.position });
    }
  }
  return { returned: d.items.length, assets: ASSETS.map(([name, url]) => ({ name, url, metrics: matched.get(url) ?? null })) };
}
export function validateJev(raw: unknown) {
  const d = record(raw);
  requireEvidence(d.schema_version === "empire.search.jev_department_portfolio.v1" && d.mode === "OBSERVE" &&
    d.execution_authority === "NONE" && count(d.task_count) && d.jev_inference_calls === 0 && d.jev_scores_generated === 0);
  return { tasks: d.task_count, inferenceCalls: 0, scores: 0 };
}
export function validateBrowser(raw: unknown) {
  const d = record(raw);
  requireEvidence(d.schema === "empire.task.founder_status_feed.v1" && d.status === "READONLY_EVIDENCE_FEED" &&
    d.read_only === true && d.mode === "OBSERVE" && d.execution_authority === "none" && count(d.task_count) && d.task_count <= 25);
  return { tasks: d.task_count };
}
// Fixed loopback targets only. Never forward cookies, credentials, task text or source errors.
export async function boundedJSON(url: string, reader: typeof fetch): Promise<unknown> {
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const work = async () => {
    const response = await reader(url, { method: "GET", cache: "no-store", redirect: "error",
      signal: controller.signal, headers: { Accept: "application/json" } });
    if (!response.ok || !response.body) throw new Error("Unavailable");
    const stream = response.body.getReader();
    const chunks: Uint8Array[] = [];
    let size = 0;
    try {
      while (true) {
        const { done, value } = await stream.read();
        if (done) break;
        size += value.byteLength;
        if (size > 262144) { controller.abort(); await stream.cancel(); throw new Error("Oversized"); }
        chunks.push(value);
      }
    } finally { stream.releaseLock(); }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  };
  try {
    return await Promise.race([work(), new Promise<never>((_, reject) => {
      timer = setTimeout(() => { controller.abort(); reject(new Error("Timeout")); }, 4000);
    })]);
  } finally { clearTimeout(timer); }
}
export async function loadUnifiedAssets(now = new Date(), reader: typeof fetch = fetch) {
  const { start, end } = dailyWindow(now);
  const safe = async <T,>(url: string, validate: (raw: unknown) => T): Promise<T | null> => {
    try { return validate(await boundedJSON(url, reader)); } catch { return null; }
  };
  const [pages, jev, browser] = await Promise.all([
    safe(`http://127.0.0.1:8771/v1/search/search-console/pages?start_date=${start}&end_date=${end}&limit=250`, raw => validatePages(raw, start, end)),
    safe("http://127.0.0.1:8771/v1/search/jev/department/review", validateJev),
    safe("http://127.0.0.1:8766/v1/founder-execution-plane/browser-tasks/recent?limit=25", validateBrowser),
  ]);
  return { start, end, checkedAt: now.toISOString(), pages, jev, browser };
}
