// Preserve the original CRM login URL and backend. No account creation,
// password verification, token signing or session persistence happens here.
export async function POST(request: Request) {
  const headers = {"Cache-Control": "no-store", "Pragma": "no-cache", "Referrer-Policy": "no-referrer"};
  const fail = (status: number) => Response.json({detail: "crm_login_unavailable_or_denied"}, {status, headers});
  const origin = process.env.EMPIRE_CONSOLE_ORIGIN?.trim() || new URL(request.url).origin;
  if (request.headers.get("origin") !== origin) return fail(403);
  if (request.headers.get("sec-fetch-site") && request.headers.get("sec-fetch-site") !== "same-origin") return fail(403);
  if (!request.headers.get("content-type")?.startsWith("application/json")) return fail(415);
  // Cap streamed input, not only caller-controlled Content-Length.
  const reader = request.body?.getReader();
  if (!reader) return fail(400);
  const parts: Uint8Array[] = []; let length = 0;
  try {
    while (true) {
      const {done, value} = await reader.read(); if (done) break;
      length += value.length; if (length > 8192) { await reader.cancel(); return fail(413); }
      parts.push(value);
    }
    const bytes = new Uint8Array(length); let offset = 0;
    for (const part of parts) { bytes.set(part, offset); offset += part.length; }
    const body = JSON.parse(new TextDecoder().decode(bytes));
    if (!body || Array.isArray(body) || Object.keys(body).sort().join(",") !== "email,password,tenant_id" ||
        typeof body.email !== "string" || body.email.length < 3 || body.email.length > 254 ||
        typeof body.password !== "string" || body.password.length < 1 || body.password.length > 256 ||
        typeof body.tenant_id !== "string" || !/^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(body.tenant_id)) return fail(400);
    const base = process.env.EMPIRE_CRM_API_BASE_URL?.trim();
    if (!base) return fail(503);
    const target = new URL(base.replace(/\/$/, "") + "/v1/revenue-crm/auth/login");
    if (target.username || target.password || target.search || target.hash ||
        (target.protocol !== "https:" && !(target.protocol === "http:" && ["localhost", "127.0.0.1", "[::1]"].includes(target.hostname)))) return fail(503);
    const upstream = await fetch(target, {method: "POST", body: JSON.stringify(body),
      headers: {"Content-Type": "application/json", Accept: "application/json"},
      credentials: "omit", cache: "no-store", redirect: "error", signal: AbortSignal.timeout(10000)});
    if (!upstream.ok) return fail([401, 403, 429].includes(upstream.status) ? upstream.status : 503);
    const session = await upstream.json();
    if (session.token_type !== "Bearer" || session.scope !== "crm:read" ||
        typeof session.access_token !== "string" || session.access_token.length < 100 || session.access_token.length > 6000 ||
        !/^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(session.access_token) ||
        !Number.isInteger(session.expires_in) || session.expires_in < 1 || session.expires_in > 900) return fail(503);
    return Response.json({access_token: session.access_token, token_type: "Bearer", scope: "crm:read", expires_in: session.expires_in}, {headers});
  } catch { return fail(503); }
}
