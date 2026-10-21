"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowRight, CheckCircle2, LoaderCircle } from "lucide-react";
import {
  reuseCommercialInterestAttempt,
  type CommercialInterestAttempt,
  type CommercialInterestDetails,
} from "@/lib/commercial-interest-attempt";
import {
  PREMIUM_DISCOVERY_ENDPOINT,
  parsePremiumDiscoveryCatalog,
  parsePremiumDiscoveryReceipt,
  type PremiumDiscoveryCatalog,
  type PremiumDiscoveryCode,
  type PremiumDiscoveryReceipt,
} from "@/lib/brokerage-premium-interest";

const field = "mt-2 w-full rounded-xl border border-white/15 bg-[#07152f] px-4 py-3 text-sm text-white placeholder:text-slate-500 focus:border-cyan-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400";
const consentText = "I agree to Empire AI contacting me about this specific intelligence enquiry. This does not subscribe me to marketing.";

type State = { mode: "idle" } | { mode: "error"; message: string } |
  { mode: "recorded"; receipt: PremiumDiscoveryReceipt };

/**
 * ASTRA-ready, unpriced premium discovery. Feature-only: not imported by page.tsx.
 * If the reviewed public route has not been released (404/HOLD), render nothing;
 * preserve the original commercial page, its $199 SKU and current visuals.
 */
export default function BrokeragePremiumDiscovery() {
  const [catalog, setCatalog] = useState<PremiumDiscoveryCatalog | null>(null);
  const [code, setCode] = useState<PremiumDiscoveryCode>("brokerage_agency_discovery");
  const [business, setBusiness] = useState("");
  const [email, setEmail] = useState("");
  const [domain, setDomain] = useState("");
  const [industry, setIndustry] = useState("");
  const [geography, setGeography] = useState("");
  const [desiredOutcome, setDesiredOutcome] = useState("");
  const [contactConsent, setContactConsent] = useState(false);
  const [website, setWebsite] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [state, setState] = useState<State>({mode: "idle"});
  const attempts = useRef<CommercialInterestAttempt | null>(null);

  useEffect(() => {
    const abort = new AbortController();
    fetch(PREMIUM_DISCOVERY_ENDPOINT, {
      method: "GET", cache: "no-store", credentials: "same-origin",
      signal: abort.signal,
      headers: {"Accept": "application/json"},
    }).then(async response => {
      if (!response.ok) return null;
      return parsePremiumDiscoveryCatalog(await response.json() as unknown);
    }).then(offers => {
      if (abort.signal.aborted || offers === null) return;
      setCatalog(offers);
      setCode(offers.offers[0].product_code);
    }).catch(() => {
      // Feature not available yet, or transport failed: don't expose it.
    });
    return () => abort.abort();
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!catalog || submitting || state.mode === "recorded" ||
        !contactConsent || website !== "") return;
    setSubmitting(true);
    setState({mode: "idle"});
    try {
      const details: CommercialInterestDetails = {
        product_code: code,
        business_name: business,
        email,
        domain,
        industry,
        geography,
        desired_outcome: desiredOutcome,
        contact_consent: contactConsent,
        website,
      };
      const attempt = reuseCommercialInterestAttempt(
        attempts.current, details, () => {
          const uuid = globalThis.crypto?.randomUUID?.();
          if (!uuid) throw new Error("secure_key_unavailable");
          return uuid;
        },
      );
      attempts.current = attempt;
      const response = await fetch(PREMIUM_DISCOVERY_ENDPOINT, {
        method: "POST",
        cache: "no-store",
        credentials: "same-origin",
        headers: {"Content-Type": "application/json", "Accept": "application/json"},
        body: JSON.stringify({...details, idempotency_key: attempt.idempotencyKey}),
      });
      if (!response.ok) {
        setState({mode: "error", message:
          "We couldn't confirm this enquiry. Please retry; no payment or contract was created."});
        return;
      }
      const receipt = parsePremiumDiscoveryReceipt(
        await response.json() as unknown, code,
      );
      if (!receipt) {
        setState({mode: "error", message:
          "The response couldn't be verified. You may retry this same enquiry."});
        return;
      }
      setState({mode: "recorded", receipt});
    } catch {
      setState({mode: "error", message:
        "This enquiry couldn't be confirmed. Please retry; no order was placed."});
    } finally {
      setSubmitting(false);
    }
  }

  // Keep discoverability and the two genuine *unpriced* service names in
  // first-paint HTML. This is a static informational preview, NOT a usable
  // enquiry form. Submission is added only after the reviewed live GET passes.
  if (!catalog) return <section id="premium-brokerage" aria-label="Premium Data Brokerage enquiries"
    className="relative mx-auto max-w-7xl px-5 py-10 text-white md:px-10">
    <div className="rounded-[2rem] border border-cyan-300/20 bg-[#061127] p-6 md:p-9">
      <p className="text-xs font-semibold uppercase tracking-[.2em] text-cyan-300">Empire AI · Intelligence services</p>
      <h2 className="mt-3 text-3xl font-semibold tracking-tight md:text-4xl">Agency & enterprise market intelligence</h2>
      <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">Research tailored to real commercial decisions. Scope and pricing are discussed individually; no subscription or payment is created by an enquiry.</p>
      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <article className="rounded-xl border border-white/15 bg-white/[.035] p-5">
          <h3 className="text-lg font-semibold text-cyan-100">Agency Intelligence</h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">Evidence-linked local market research for B2B agencies.</p>
          <p className="mt-3 text-xs text-cyan-200">Discuss a custom scope</p>
        </article>
        <article className="rounded-xl border border-white/15 bg-white/[.035] p-5">
          <h3 className="text-lg font-semibold text-cyan-100">Enterprise Territory Intelligence</h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">Evidence-linked market selection for multi-territory operators.</p>
          <p className="mt-3 text-xs text-cyan-200">Discuss a custom scope</p>
        </article>
      </div>
      <p className="mt-5 text-xs leading-5 text-slate-400" aria-live="polite">The enquiry form becomes available when the live service is verified in your browser.</p>
    </div>
  </section>;

  return <section id="premium-brokerage" aria-label="Premium Data Brokerage enquiries"
    className="relative mx-auto max-w-7xl px-5 py-14 text-white md:px-10">
    <div className="rounded-[2rem] border border-cyan-300/15 bg-[radial-gradient(ellipse_at_top_right,rgba(13,112,191,.16),transparent_52%),linear-gradient(145deg,#061127,#020817)] p-6 shadow-[0_20px_100px_rgba(0,0,0,.25)] md:p-10">
      <p className="text-xs font-semibold uppercase tracking-[.2em] text-cyan-300">
        Empire AI · Source-verified intelligence
      </p>
      <h2 className="mt-4 max-w-3xl text-3xl font-semibold tracking-tight md:text-5xl">
        Intelligence tailored to your next decision.
      </h2>
      <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-300">
        Request a discovery scope for original market research. These are
        nonbinding enquiries—not subscriptions, rankings guarantees, or
        automatic data access. Scope, delivery and price are agreed separately.
      </p>
      <div className="mt-8 grid gap-6 lg:grid-cols-[.9fr_1.1fr]">
        <div className="grid content-start gap-3" role="group" aria-label="Intelligence type">
          {catalog.offers.map(item =>
            <button key={item.product_code} type="button"
              aria-pressed={code === item.product_code}
              disabled={state.mode === "recorded"}
              onClick={() => {setCode(item.product_code);setState({mode: "idle"});}}
              className={"rounded-2xl border p-5 text-left transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-300 " +
                (code === item.product_code ?
                  "border-cyan-300/70 bg-cyan-300/[.08]" :
                  "border-white/10 bg-white/[.025] hover:border-white/30")}>
              <span className="block text-lg font-semibold">{item.title}</span>
              <span className="mt-2 block text-sm leading-6 text-slate-300">{item.buyer_problem}</span>
              <span className="mt-3 block text-xs font-semibold uppercase tracking-wide text-cyan-200">
                Discuss a custom scope <ArrowRight className="ml-1 inline size-3" />
              </span>
            </button>,
          )}
          <p className="mt-3 text-xs leading-6 text-slate-400">
            We propose the scope after reviewing your requirements.
            No offer, recurring fee or licence is agreed by submitting this form.
          </p>
        </div>
        <form onSubmit={submit} className="space-y-4 rounded-2xl border border-white/10 bg-[#061024]/90 p-5 md:p-7">
          <h3 className="text-xl font-semibold">Request an intelligence scope</h3>
          <p className="text-xs leading-6 text-slate-400">Enquiries go to private founder review. No automated follow-up or payment.</p>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-xs text-slate-300">Company
              <input required maxLength={200} value={business} onChange={e=>setBusiness(e.target.value)}
                autoComplete="organization" className={field} placeholder="Company Ltd" />
            </label>
            <label className="text-xs text-slate-300">Work email
              <input required type="email" maxLength={320} value={email} onChange={e=>setEmail(e.target.value)}
                autoComplete="email" className={field} placeholder="you@company.com" />
            </label>
            <label className="text-xs text-slate-300">Company domain
              <input required maxLength={253} value={domain} onChange={e=>setDomain(e.target.value)}
                className={field} placeholder="company.com" />
            </label>
            <label className="text-xs text-slate-300">Industry
              <input required maxLength={120} value={industry} onChange={e=>setIndustry(e.target.value)}
                className={field} placeholder="Solar, roofing, agency…" />
            </label>
          </div>
          <label className="block text-xs text-slate-300">Markets or territories
            <input required maxLength={160} value={geography} onChange={e=>setGeography(e.target.value)}
              className={field} placeholder="North West England · Texas · US" />
          </label>
          <label className="block text-xs text-slate-300">What commercial decision are you researching?
            <textarea required minLength={12} maxLength={1200} rows={4} value={desiredOutcome}
              onChange={e=>setDesiredOutcome(e.target.value)} className={field}
              placeholder="Tell us which market, customer type or competitor question matters." />
          </label>
          <div aria-hidden="true" className="hidden">
            <label>Website<input tabIndex={-1} autoComplete="off" value={website}
              onChange={e=>setWebsite(e.target.value)} /></label>
          </div>
          <label className="flex items-start gap-3 text-xs leading-6 text-slate-300">
            <input type="checkbox" required checked={contactConsent}
              onChange={e=>setContactConsent(e.target.checked)}
              className="mt-1 size-4 accent-cyan-400" />
            {consentText}
          </label>
          <p className="text-xs leading-5 text-slate-400">
            <a href="/privacy" className="text-cyan-200 underline underline-offset-4">
              How Empire AI handles enquiry details
            </a>
          </p>
          <button type="submit"
            disabled={!contactConsent || submitting || state.mode === "recorded"}
            className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 px-5 py-4 text-sm font-semibold transition hover:brightness-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-300 disabled:opacity-40">
            {submitting ? <LoaderCircle className="size-4 animate-spin" /> :
              <ArrowRight className="size-4" />}
            {submitting ? "Confirming…" : "Request scope review"}
          </button>
          {state.mode === "recorded" ?
            <p role="status" className="rounded-xl border border-emerald-300/30 p-4 text-sm text-emerald-200">
              <CheckCircle2 className="mr-2 inline size-4" />
              Enquiry recorded, reference {state.receipt.reference}. This is not an order or a payment.
            </p>
            : state.mode === "error" ?
            <p role="alert" className="rounded-xl border border-amber-300/30 p-4 text-sm text-amber-200">
              {state.message}
            </p> : null}
        </form>
      </div>
    </div>
  </section>;
}
