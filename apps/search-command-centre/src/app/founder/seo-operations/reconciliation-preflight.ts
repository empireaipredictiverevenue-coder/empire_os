/** Read-only source/compiled-route preflight. Never authorizes release activation. */
import { createHash } from "node:crypto";
import { readFileSync, statSync } from "node:fs";
import { resolve } from "node:path";

export const PATCH_COMMIT = "19eb011ebf05d792bb7970414bd5f6f698c11634";
export const SEO_DIRECTORY = "src/app/founder/seo-operations/";
export const SEO_HASHES: Record<string, string> = {
  "gsc-daily.ts": "1852dc7d7af102fd4afec74c6599016ecdce1c091dcd1d85ab9e7eda0fc55bd9",
  "gsc-history.test.tsx": "14df4a81f001a4d484772cd48b81d2bbfb9bc9702580cf1b8b76628de98a2526",
  "gsc-history.tsx": "90bcb902f290aa9ad1856edd07e0e152cb629dba3b40eb1e04bee57751eccffe",
  "page.tsx": "5c53fbead1216e8f17d8514a8e93d84e7527ce658c671f12e63f33d4152adf48",
  "unified-assets-data.ts": "75add2acc78edaa55a04f9f543a4cdc653e14c2bb9ad4fc8c0220eceab796ae8",
  "unified-assets.test.tsx": "fcd01cb91b3d4a2a1a11ba2913b2d3eb1f4632022129f3899e3643c95bfa374d",
  "unified-assets.tsx": "536d71de1c6185130419cde3e940f361db44a045dc62cd47a0d25e8a3146e9b5",
};
export const SEO_ROUTE = "/founder/seo-operations";
export const PROTECTED_ROUTES = ["/founder", "/founder/browser-tasks", "/founder/mail", "/founder/results", "/founder/solar"];
const LIMIT = 2 * 1024 * 1024;
export type Reader = (relativePath: string) => Uint8Array;
export const digest = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex");
const routeValid = (route: string) => /^\/(?:[a-z0-9-]+\/?)*$/.test(route) && !route.endsWith("/");

/** Concrete routes only: dynamic patterns cannot prove a protected concrete page exists. */
export function manifestRoutes(bytes: Uint8Array): string[] {
  if (bytes.length > LIMIT) throw new Error("manifest_limit");
  const raw: unknown = JSON.parse(Buffer.from(bytes).toString("utf8"));
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new Error("manifest_shape");
  const routes = new Set<string>();
  for (const [key, value] of Object.entries(raw)) {
    if (!key.startsWith("/") || typeof value !== "string" || !value.startsWith("app/") || value.includes("..") || !value.endsWith(".js")) throw new Error("manifest_entry");
    if (!/\/(page|route)$/.test(key)) throw new Error("manifest_key");
    const parts = key.split("/").slice(1, -1).filter(p => !/^\([^()]+\)$/.test(p) && !p.startsWith("@"));
    const route = "/" + parts.join("/");
    if (route === "/" || routeValid(route)) routes.add(route);
  }
  return [...routes].sort();
}

export type Observation = { route: string; status: number | null; http: "ok" | "not_ok" | "unavailable"; markers: "present" | "absent" | "unknown"; data: "unverified"; error: "probe_failed" | null };
/** Only rendered heading tags count; scripts/comments and escaped Flight payloads do not. */
export function seoMarkers(html: string): boolean {
  const rendered = html.replace(/<!--[\s\S]*?-->|<(script|style|template|textarea|title|xmp|iframe|noembed|noframes)\b[^>]*>[\s\S]*?<\/\1\s*>/gi, "");
  const ids = new Set<string>();
  // Consume quoted attribute values atomically so embedded fake headings/IDs fail.
  const tags = rendered.match(/<[a-z][a-z0-9-]*(?=[\s/>])(?:"[^"]*"|'[^']*'|[^'">])*>/gi) ?? [];
  for (const tag of tags) {
    if (!/^<h2(?=[\s>])/i.test(tag)) continue;
    const attrs = tag.slice(3, -1).matchAll(/\s+([^\s=/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g);
    const found = [...attrs].filter(a => a[1].toLowerCase() === "id");
    if (found.length === 1) ids.add(found[0][2] ?? found[0][3] ?? found[0][4]);
  }
  return ["gsc-history-heading", "unified-assets-heading"].every(id => ids.has(id));
}
export async function probe(route: string, reader: typeof fetch = fetch): Promise<Observation> {
  if (![...PROTECTED_ROUTES, SEO_ROUTE].includes(route)) throw new Error("route_not_allowlisted");
  let status: number | null = null;
  try {
    const response = await reader(`http://127.0.0.1:3001${route}`, { method: "GET", redirect: "error", credentials: "omit", cache: "no-store", headers: { Accept: "text/html" }, signal: AbortSignal.timeout(5000) });
    status = response.status;
    if (status !== 200) { await response.body?.cancel(); return { route, status, http: "not_ok", markers: "unknown", data: "unverified", error: null }; }
    if (!/^text\/html(?:;|$)/i.test(response.headers.get("content-type") ?? "")) { await response.body?.cancel(); throw new Error("content_type"); }
    if (Number(response.headers.get("content-length")) > LIMIT) { await response.body?.cancel(); throw new Error("body_limit"); }
    if (!response.body) throw new Error("empty_body");
    const stream = response.body.getReader();
    let size = 0;
    const chunks: Uint8Array[] = [];
    try {
      for (;;) {
        const { done, value } = await stream.read();
        if (done) break;
        size += value.length;
        if (size > LIMIT) throw new Error("body_limit");
        chunks.push(value);
      }
    } finally { await stream.cancel(); }
    return { route, status, http: "ok", markers: route === SEO_ROUTE ? (seoMarkers(Buffer.concat(chunks).toString("utf8")) ? "present" : "absent") : "unknown", data: "unverified", error: null };
  } catch { return { route, status, http: "unavailable", markers: "unknown", data: "unverified", error: "probe_failed" }; }
}

export function reconcile(read: Reader, observations: Observation[] = [], additionalProtected: string[] = [], proposedChanges: string[] = [SEO_ROUTE]) {
  if (observations.length > 100 || !observations.every(o => routeValid(o.route)) || additionalProtected.length > 100 || !additionalProtected.every(routeValid) || proposedChanges.length > 100 || !proposedChanges.every(routeValid)) throw new Error("invalid_route_input");
  const files = Object.entries(SEO_HASHES).map(([file, hash]) => {
    try { return { file, parity: digest(read(SEO_DIRECTORY + file)) === hash ? "exact" : "mismatch" }; }
    catch { return { file, parity: "unreadable" }; }
  });
  let routes: string[] = [], manifest = "valid", manifestSha256: string | null = null;
  try { const bytes = read(".next/server/app-paths-manifest.json"); manifestSha256 = digest(bytes); routes = manifestRoutes(bytes); }
  catch { manifest = "invalid_or_unreadable"; }
  const protectedRoutes = [...new Set([...PROTECTED_ROUTES, ...additionalProtected, ...observations.map(o => o.route).filter(r => r !== SEO_ROUTE)])].sort();
  const requirements = [...new Set([...protectedRoutes, SEO_ROUTE])].sort().map(route => ({
    route, candidatePresent: routes.includes(route), protected: protectedRoutes.includes(route), proposedChange: proposedChanges.includes(route),
    // Reconstruct the safe fields; never forward arbitrary input or error bodies.
    live: observations.filter(o => o.route === route).map(o => ({ status: Number.isInteger(o.status) && o.status! >= 100 && o.status! <= 599 ? o.status : null, http200: o.status === 200 && o.http === "ok", seoMarkers: o.markers === "present" ? "present" : o.markers === "absent" ? "absent" : "unknown", data: "unverified" })),
  }));
  const reasons: string[] = [];
  if (files.some(f => f.parity !== "exact")) reasons.push("seo_patch_parity_failed");
  if (manifest !== "valid") reasons.push("candidate_manifest_unverified");
  if (requirements.some(r => !r.candidatePresent)) reasons.push("required_route_missing_needs_original_release_owner");
  if (proposedChanges.some(r => r !== SEO_ROUTE)) reasons.push("proposed_change_outside_seo_scope_needs_original_release_owner");
  if (requirements.some(r => r.live.length !== 1 || !r.live[0].http200)) reasons.push("live_http_parity_unverified");
  if (!requirements.find(r => r.route === SEO_ROUTE)?.live.some(o => o.seoMarkers === "present")) reasons.push("live_seo_markers_unverified");
  return { schema: "empire.seo.reconciliation-preflight.v1", mode: "OBSERVE", writes: false, seoPatchCommit: PATCH_COMMIT,
    candidateVerification: reasons.length ? "HOLD" : "PASS", reasons, files, manifest: { status: manifest, sha256: manifestSha256 }, requirements,
    productionRelease: "HOLD", needsOriginalReleaseOwner: true,
    handoff: { owner: "original Founder Console protected release owner", patchCommit: PATCH_COMMIT, preserveRoutes: protectedRoutes,
      required: ["Reconcile with actual v2r3 source; v2r2 is historical only", "Confirm complete protected route inventory and behavior", "Bind clean candidate source to fresh build manifest; source hashes alone do not prove compiled bundle parity", "Verify SEO data against canonical read-only APIs; headings and HTTP 200 are not data verification", "Obtain existing protected deployment approval before activation"], activationPerformed: false } };
}

/** Root is a candidate Next app directory, never a release destination. No writes. */
export function filesystemReader(root: string): Reader {
  return relative => {
    if (relative !== ".next/server/app-paths-manifest.json" && !Object.keys(SEO_HASHES).some(file => relative === SEO_DIRECTORY + file)) throw new Error("input_not_allowlisted");
    const path = resolve(root, relative);
    const stat = statSync(path);
    if (!stat.isFile() || stat.size > LIMIT) throw new Error("input_limit");
    const bytes = readFileSync(path);
    if (bytes.length > LIMIT) throw new Error("input_limit");
    return bytes;
  };
}
