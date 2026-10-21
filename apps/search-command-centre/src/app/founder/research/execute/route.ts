import { forwardedAccessAssertion, requestPrivateResearch } from "@/lib/founder-research-internal";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const PRIVATE_HEADERS = {
  "Cache-Control": "no-store, private",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
};

function json(body: object, status: number) {
  return Response.json(body, { status, headers: PRIVATE_HEADERS });
}

export async function POST(request: Request) {
  const canonicalOrigin = process.env.EMPIRE_FOUNDER_RESEARCH_ORIGIN;
  if (!canonicalOrigin || !/^https:\/\/[-.a-z0-9]+$/.test(canonicalOrigin)) {
    return json({ detail: "Research origin not configured" }, 503);
  }
  if (request.headers.get("origin") !== canonicalOrigin ||
      request.headers.get("sec-fetch-site") !== "same-origin") {
    return json({ detail: "Cross-origin execution refused" }, 403);
  }
  const bearer = forwardedAccessAssertion(request.headers.get("cf-access-jwt-assertion"));
  if (!bearer) return json({ detail: "Verified Founder session required" }, 401);
  if (request.headers.get("content-type")?.split(";")[0]?.trim() !== "application/json") {
    return json({ detail: "JSON request required" }, 415);
  }
  if (Number(request.headers.get("content-length") || 0) > 1024) {
    return json({ detail: "Research request too large" }, 413);
  }
  let parsed: unknown;
  try {
    const raw = await request.text();
    if (raw.length > 1024) return json({ detail: "Research request too large" }, 413);
    parsed = JSON.parse(raw);
  } catch {
    return json({ detail: "Invalid research request" }, 400);
  }
  const result = await requestPrivateResearch("preview", bearer, parsed);
  if (!result.ok) {
    const error = result.data as { detail?: string } | null;
    const message = typeof error?.detail === "string" ? error.detail : "Research unavailable";
    return json({ detail: message }, result.status);
  }
  return json(result.data as object, 200);
}
