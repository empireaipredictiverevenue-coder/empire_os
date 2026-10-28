"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

type Packet = Record<string, unknown>;
const obj = (value: unknown): Packet => value && typeof value === "object" && !Array.isArray(value) ? value as Packet : {};
const text = (value: unknown) => typeof value === "string" || typeof value === "number" ? String(value) : "UNKNOWN";

export function CompanyReview() {
  const token = useRef("");
  const generation = useRef(0);
  const pending = useRef<AbortController | null>(null);
  const expiry = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [signedIn, setSignedIn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Sign in with your existing CRM account to review permitted company evidence.");
  const [packet, setPacket] = useState<Packet | null>(null);

  function clear(message: string) {
    generation.current++; pending.current?.abort(); pending.current = null;
    token.current = "";
    if (expiry.current) clearTimeout(expiry.current);
    expiry.current = null;
    setPacket(null); setSignedIn(false); setBusy(false); setStatus(message);
  }
  useEffect(() => () => {
    generation.current++; pending.current?.abort(); token.current = "";
    if (expiry.current) clearTimeout(expiry.current);
  }, []);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const body = JSON.stringify({email: values.get("email"), password: values.get("password"), tenant_id: values.get("tenant_id")});
    (form.elements.namedItem("password") as HTMLInputElement).value = "";
    clear("Verifying your existing CRM account…");
    const current = generation.current;
    if (location.protocol !== "https:" && !["localhost", "127.0.0.1", "[::1]"].includes(location.hostname)) {
      setStatus("Secure CRM origin required."); return;
    }
    setBusy(true);
    const controller = new AbortController(); pending.current = controller;
    try {
      const response = await fetch("/v1/revenue-crm/auth/login", {
        method: "POST", body, credentials: "omit", cache: "no-store", redirect: "error",
        headers: {"Content-Type": "application/json", Accept: "application/json"}, signal: controller.signal,
      });
      if (!response.ok) throw Error("login_denied");
      const session = await response.json();
      if (current !== generation.current) return;
      if (session.token_type !== "Bearer" || session.scope !== "crm:read" ||
          typeof session.access_token !== "string" || session.access_token.length < 100 || session.access_token.length > 6000 ||
          !/^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(session.access_token) ||
          !Number.isInteger(session.expires_in) || session.expires_in < 1 || session.expires_in > 900)
        throw Error("invalid_session");
      token.current = session.access_token;
      expiry.current = setTimeout(() => clear("CRM session expired. Sign in again."), session.expires_in * 1000);
      setSignedIn(true); setStatus("Signed in. Company and source permissions are checked for every review.");
    } catch {
      if (current === generation.current) clear("CRM sign-in unavailable or denied. No company evidence loaded.");
    } finally { if (current === generation.current) setBusy(false); }
  }

  async function review(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token.current || busy) return;
    const values = new FormData(event.currentTarget);
    const company = String(values.get("company_scope") ?? "");
    const source = String(values.get("source_id") ?? "");
    const query = new URLSearchParams({company_scope: company, source_id: source});
    const current = generation.current;
    pending.current?.abort(); const controller = new AbortController(); pending.current = controller;
    setPacket(null); setBusy(true); setStatus("Reviewing permitted evidence…");
    try {
      const response = await fetch("/api/predictive-revenue/company-review?" + query, {
        credentials: "omit", cache: "no-store", redirect: "error",
        headers: {Accept: "application/json", Authorization: "Bearer " + token.current}, signal: controller.signal,
      });
      if (current !== generation.current) return;
      if (response.status === 401) { clear("CRM session expired or revoked. Sign in again."); return; }
      if (!response.ok) { setStatus(response.status === 403 ? "HOLD — this account is not authorised for that company/source." : "HOLD — company evidence is unavailable or not configured."); return; }
      const data = await response.json();
      if (current !== generation.current) return;
      if (data.schema_version !== "empire.predictive-revenue-company-export-review.v4.21" ||
          data.company_scope !== company || data.source_id !== source || data.execution_authority !== "none" ||
          data.eligible_for_training_or_live_prediction !== false || data.model_promotion_or_payment_authorized !== false)
        throw Error("invalid_review");
      setPacket(data); setStatus("Research review received. This is not verified revenue or authority to act.");
    } catch { if (current === generation.current) setStatus("HOLD — company evidence could not be verified."); }
    finally { if (current === generation.current) setBusy(false); }
  }
  const v5 = obj(packet?.v5_predictive_cloud_staging_read_only);
  const forecasts = Array.isArray(v5.issued_forecast_risk_screens_unverified) ? v5.issued_forecast_risk_screens_unverified.map(obj) : [];
  return <section className="panel mt-7" aria-labelledby="private-company-title">
    <h2 id="private-company-title" className="text-2xl font-semibold">Private company research</h2>
    <p role="status" className="mt-3 text-sm text-slate-300">{status}</p>
    {!signedIn ? <form onSubmit={login} className="mt-4 grid gap-3 md:grid-cols-2">
      <label>CRM email<input name="email" type="email" autoComplete="username" required maxLength={254} className="block w-full rounded bg-slate-900 p-2" /></label>
      <label>Existing password<input name="password" type="password" autoComplete="current-password" required maxLength={256} className="block w-full rounded bg-slate-900 p-2" /></label>
      <label>CRM tenant ID<input name="tenant_id" required minLength={36} maxLength={36} className="block w-full rounded bg-slate-900 p-2" /></label>
      <button disabled={busy} className="rounded border border-cyan-400 p-2">Sign in to existing CRM</button>
    </form> : <><button onClick={() => clear("Signed out. Private evidence cleared.")} className="mt-3 rounded border p-2">Sign out</button>
      <form onSubmit={review} className="mt-4 grid gap-3 md:grid-cols-3">
        <label>Company reference<input name="company_scope" required maxLength={128} className="block w-full rounded bg-slate-900 p-2" /></label>
        <label>Source reference<input name="source_id" required maxLength={128} className="block w-full rounded bg-slate-900 p-2" /></label>
        <button disabled={busy} className="rounded border border-cyan-400 p-2">Review permitted evidence</button>
      </form></>}
    {packet && <div className="mt-5 space-y-3" data-testid="private-company-result">
      <p>Company: {text(packet.company_scope)} · Source: {text(packet.source_id)}</p>
      <p>As of: {text(packet.as_of_utc)}</p><p>Decision: {text(packet.decision)}</p>
      <p>Evidence digest: <span className="break-all">{text(packet.payload_sha256)}</span></p>
      <p>Verified realised revenue: UNKNOWN · Model promotion: HOLD</p>
      {[30, 60, 90].map(horizon => <div key={horizon} className="rounded border border-white/10 p-3">
        <h3>{horizon}-day research horizon</h3>
        {forecasts.filter(row => row.horizon_days === horizon).length ? forecasts.filter(row => row.horizon_days === horizon).map((row, i) => <p key={i}>Forecast reference: {text(row.forecast_id)} · independently verified issuance: UNKNOWN · Risk: {text(obj(row.research_risk_band).decision)}</p>) : <p>HOLD — no issued forecast supplied for this horizon.</p>}
      </div>)}
    </div>}
  </section>;
}
