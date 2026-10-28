import { getPredictiveCompanyReview } from "@/lib/founder-api";

export const dynamic = "force-dynamic";

// The original signed bearer is forwarded for this request only. The backend
// verifies membership and company/source permission; cookies grant no access.
export async function GET(request: Request) {
  const headers = {
    "Cache-Control": "no-store",
    "Vary": "Authorization, Cookie",
    "X-Content-Type-Options": "nosniff",
  };
  const fail = (detail: string, status: number) => Response.json({ detail }, { status, headers });
  const url = new URL(request.url);
  const expectedOrigin = process.env.EMPIRE_CONSOLE_ORIGIN?.trim();
  try {
    const configured = new URL(expectedOrigin ?? "");
    if (configured.origin !== expectedOrigin || configured.username || configured.password ||
        (configured.protocol !== "https:" && !(configured.protocol === "http:" &&
          ["localhost", "127.0.0.1", "[::1]"].includes(configured.hostname))))
      return fail("company_review_configuration_required", 503);
  } catch { return fail("company_review_configuration_required", 503); }
  const origin = request.headers.get("origin");
  const site = request.headers.get("sec-fetch-site");
  if ((origin && origin !== expectedOrigin) || (site && site !== "same-origin" && site !== "none"))
    return fail("company_review_access_denied", 403);
  const authorization = request.headers.get("authorization") ?? "";
  const bearer = /^Bearer ([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)$/.exec(authorization);
  if (!bearer || bearer[1].length < 100 || bearer[1].length > 6000)
    return fail("crm_session_required", 401);
  const params = url.searchParams;
  if (params.size !== 2 || params.getAll("company_scope").length !== 1 ||
      params.getAll("source_id").length !== 1)
    return fail("company_source_scope_required", 400);
  const company = params.get("company_scope")!;
  const source = params.get("source_id")!;
  if (![company, source].every(value => /^[A-Za-z0-9:@._/-]{1,128}$/.test(value)))
    return fail("company_source_scope_required", 400);
  const result = await getPredictiveCompanyReview(bearer[1], company, source);
  if (!result.ok) {
    if (result.status === 401) return fail("crm_session_required", 401);
    if (result.status === 403) return fail("company_review_access_denied", 403);
    return fail("company_review_evidence_unavailable", 503);
  }
  return Response.json(result.data, { status: 200, headers });
}
