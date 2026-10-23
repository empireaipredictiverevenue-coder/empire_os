"use client";
import CommercialBuyerExplanation from "@/components/CommercialBuyerExplanation";
import BrokeragePremiumDiscovery from "@/components/BrokeragePremiumDiscovery";
import TamBuyingIntentEvidenceGuide from "@/components/TamBuyingIntentEvidenceGuide";
import { ArrowLeft, ArrowRight, LoaderCircle, CheckCircle2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  reuseCommercialInterestAttempt,
  type CommercialInterestAttempt,
  type CommercialInterestDetails,
} from "@/lib/commercial-interest-attempt";
import { selectApprovedProposalOffer } from "@/lib/buyer-proposal-handoff";
import { claimedEntryForReview } from "@/lib/commercial-entry-review";

type Offer = { product_code: string; name: string; offer_family: string; currency: string; approved_price_cents: number; price_interval: string; implementation_fee_cents?: number };
type Catalog = { status: string; offers: Offer[] };
type Receipt = { decision?: string; reference?: string; detail?: string; error?: string };
const inputStyle = "mt-2 w-full rounded-xl border border-white/15 bg-[#07152f] px-4 py-3 text-sm text-white placeholder:text-slate-500 focus:border-cyan-300";
function price(offer: Offer) {
  return (offer.currency === "GBP" ? "£" : "$") +
    (offer.approved_price_cents / 100).toLocaleString("en-GB") +
    (offer.price_interval === "monthly" ? "/month" : "");
}

export default function CommercialPage() {
  const [offers, setOffers] = useState<Offer[]>([]);
  const [error, setError] = useState("");
  const [code, setCode] = useState("");
  const [business, setBusiness] = useState("");
  const [email, setEmail] = useState("");
  const [domain, setDomain] = useState("");
  const [industry, setIndustry] = useState("");
  const [region, setRegion] = useState("");
  const [outcome, setOutcome] = useState("");
  const [consent, setConsent] = useState(false);
  const [website, setWebsite] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<Receipt | null>(null);
  const enquiryAttemptRef = useRef<CommercialInterestAttempt | null>(null);
  useEffect(() => {
    let mounted = true;
    fetch("/v1/checkout/commercial/offers", { cache: "no-store" })
      .then(async res => { if (!res.ok) throw Error("unavailable"); return await res.json() as Catalog; })
      .then(data => {
        if (!mounted) return;
        if (data.status !== "FOUNDER_LED_ENQUIRY_AVAILABLE" || !Array.isArray(data.offers)) throw Error("unverified");
        setOffers(data.offers);
        // A /buy proposal link carries an UNTRUSTED suggested product.
        // Never treat the query as an approved offer or consent. The
        // first-party offers GET is the only selection allowlist.
        const requested = new URLSearchParams(window.location.search).get("product");
        const selection = selectApprovedProposalOffer(requested, data.offers);
        setCode(selection.code);
        if (selection.rejected) {
          setError("The requested product is not available for a proposal. Please choose an approved offer below.");
        }
      })
      .catch(() => { if (mounted) setError("Commercial enquiries are temporarily unavailable."); });
    return () => { mounted = false; };
  }, []);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!code || !consent || submitting ||
        result?.decision === "commercial_enquiry_recorded") return;
    setSubmitting(true);
    setResult(null);
    try {
      const details: CommercialInterestDetails = {
        product_code: code, business_name: business, email, domain,
        industry, geography: region, desired_outcome: outcome,
        contact_consent: consent, website,
        claimed_entry_page: claimedEntryForReview(window.location.search),
      };
      const attempt = reuseCommercialInterestAttempt(
        enquiryAttemptRef.current,
        details,
        () => {
          const key = globalThis.crypto?.randomUUID?.();
          if (!key) throw new Error("secure_commercial_key_unavailable");
          return key;
        },
      );
      enquiryAttemptRef.current = attempt;
      const response = await fetch("/v1/checkout/commercial/interests", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({...details, idempotency_key: attempt.idempotencyKey}),
      });
      const body = await response.json() as Receipt;
      setResult(response.ok && body.decision === "commercial_enquiry_recorded" ? body :
        { detail: body.detail || body.error || "Enquiry could not be recorded." });
    } catch (error) {
      setResult({detail:
        error instanceof Error && error.message === "secure_commercial_key_unavailable"
          ? "Secure request identity unavailable. Please reload before retrying."
          : "We could not confirm receipt. You can retry this same enquiry safely. No order was placed.",
      });
    }
    finally { setSubmitting(false); }
  }

  return <main className="min-h-screen bg-[#020817] text-white">
    <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_60%_0%,rgba(14,165,233,.17),transparent_45%)]" />
    <div className="relative mx-auto max-w-7xl px-5 py-8 md:px-10">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <a href="/" className="inline-flex items-center gap-2 text-xs font-semibold tracking-[.15em] text-slate-200"><ArrowLeft className="size-4" /> EMPIRE AI</a>
        <nav className="flex gap-5 text-xs text-slate-400">
          <a href="/buy" className="hover:text-white">Intelligence products</a>
          <a href="/predictive-revenue" className="hover:text-white">Predictive Revenue</a>
          <a href="/trust" className="hover:text-white">Trust</a>
        </nav>
      </header>
      <section className="pb-9 pt-16">
        <p className="text-xs font-semibold tracking-[.2em] text-cyan-300">FOUNDER-LED COMMERCIAL ENQUIRIES</p>
        <h1 className="mt-5 max-w-5xl text-5xl font-semibold tracking-[-.055em] md:text-7xl">Turn the opportunity into a <span className="text-cyan-300">real proposal.</span></h1>
        <p className="mt-5 max-w-3xl text-base leading-7 text-slate-400">Empire AI consultancy and Digital Avatar solutions. Discuss outcomes with our founder before agreeing scope, terms, delivery or payment.</p>
      </section>
      <BrokeragePremiumDiscovery />
      <div className="grid gap-10 pb-20 lg:grid-cols-[1fr_1fr]">
        <section aria-label="Approved pricing">
          <h2 className="mb-4 text-xl font-semibold">Founder-approved starting prices</h2>
          {error && <p role="alert" className="rounded-xl border border-amber-300/30 p-4 text-sm text-amber-200">{error}</p>}
          {!offers.length && !error && <p className="text-sm text-slate-400">Loading offer options…</p>}
          <div className="grid gap-3">
            {offers.map(offer => <button key={offer.product_code} type="button"
              aria-pressed={code === offer.product_code}
              onClick={() => { setCode(offer.product_code); setResult(null); }}
              className={"rounded-2xl border p-5 text-left transition " +
                (code === offer.product_code ? "border-cyan-300/70 bg-cyan-300/[.07]" : "border-white/10 bg-white/[.025] hover:border-white/30")}>
              <span className="flex flex-wrap items-start justify-between gap-3">
                <strong>{offer.name}</strong><strong className="text-cyan-200">{price(offer)}</strong>
              </span>
              <span className="mt-2 block text-xs text-slate-400">
                {offer.offer_family === "consultancy" ? "Consultancy and advisory" : "Digital Avatar — scoped deployment"}
                {offer.implementation_fee_cents ? " · Setup $" + (offer.implementation_fee_cents / 100).toLocaleString("en-GB") : ""}
              </span>
              <span className="mt-2 block text-xs text-slate-500">Nonbinding proposal enquiry · Delivery verified before contracting</span>
            </button>)}
          </div>
          <p className="mt-5 text-xs leading-6 text-slate-500">Prices are approved policy, not evidence of verified runtime costs or capacity. This page cannot place an order or accept payment.</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <a href="/buy" className="inline-flex items-center gap-2 rounded-full border border-emerald-300/30 px-5 py-3 text-xs text-emerald-200">Intelligence products <ArrowRight className="size-4" /></a>
            <a href="/predictive-revenue" className="inline-flex items-center gap-2 rounded-full border border-blue-300/30 px-5 py-3 text-xs text-blue-200">Enterprise platform <ArrowRight className="size-4" /></a>
          </div>
        </section>
        <section id="commercial-enquiry" className="h-fit scroll-mt-8 rounded-3xl border border-white/10 bg-[#07142b] p-6 md:p-8">
          <h2 className="text-2xl font-semibold">Request a commercial proposal</h2>
          <p className="mt-2 text-sm leading-6 text-slate-400">Buyer-initiated enquiries go to our first-party commercial workflow for founder review. No automated follow-up, checkout or payment.</p>
          <form onSubmit={submit} className="mt-7 space-y-4">
            <label className="block text-xs text-slate-300">Solution
              <select required value={code} onChange={e => { setCode(e.target.value); setError(""); }} className={inputStyle}>
                <option value="" disabled>Choose an approved offer</option>
                {offers.map(offer => <option value={offer.product_code} key={offer.product_code}>{offer.name}</option>)}
              </select>
            </label>
            <label className="block text-xs text-slate-300">Company
              <input required maxLength={200} value={business} onChange={e => setBusiness(e.target.value)} className={inputStyle} placeholder="Company Ltd" />
            </label>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="block text-xs text-slate-300">Work email
                <input required type="email" maxLength={320} value={email} onChange={e => setEmail(e.target.value)} className={inputStyle} placeholder="name@company.com" />
              </label>
              <label className="block text-xs text-slate-300">Company domain
                <input required maxLength={253} value={domain} onChange={e => setDomain(e.target.value)} className={inputStyle} placeholder="company.com" />
              </label>
              <label className="block text-xs text-slate-300">Industry
                <input required maxLength={120} value={industry} onChange={e => setIndustry(e.target.value)} className={inputStyle} placeholder="Professional services" />
              </label>
              <label className="block text-xs text-slate-300">Geography
                <input required maxLength={160} value={region} onChange={e => setRegion(e.target.value)} className={inputStyle} placeholder="United Kingdom" />
              </label>
            </div>
            <label className="block text-xs text-slate-300">Outcome you want
              <textarea required minLength={12} maxLength={1200} rows={4} value={outcome}
                onChange={e => setOutcome(e.target.value)} className={inputStyle}
                placeholder="Describe your business goal and timeframe." />
            </label>
            <div className="hidden" aria-hidden="true"><label>Website
              <input tabIndex={-1} autoComplete="off" value={website} onChange={e => setWebsite(e.target.value)} />
            </label></div>
            <label className="flex items-start gap-3 text-xs leading-6 text-slate-300">
              <input required type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} className="mt-1 size-4 accent-cyan-400" />
              <span>I consent to Empire AI emailing me about this specific enquiry. I am not signing up for unrelated marketing.</span>
            </label>
            <p className="text-xs leading-6 text-slate-400">
              How we use enquiry details: <a href="/privacy" className="font-semibold text-cyan-200 underline underline-offset-4 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-cyan-300">Read the Empire AI privacy notice</a>.
            </p>
            <button disabled={!code || !consent || submitting ||
              result?.decision === "commercial_enquiry_recorded"} type="submit"
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-600 px-5 py-4 text-sm font-semibold disabled:opacity-40">
              {submitting ? <LoaderCircle className="size-4 animate-spin" /> : <ArrowRight className="size-4" />}
              {submitting ? "Recording…" : "Request founder proposal"}
            </button>
            {result?.decision === "commercial_enquiry_recorded" ?
              <p role="status" className="flex items-center gap-2 rounded-xl border border-emerald-300/20 p-4 text-sm text-emerald-200"><CheckCircle2 className="size-4" /> Enquiry recorded, reference {result.reference}. No order or payment created. To start a separate enquiry, reload this page.</p>
              : result?.detail ? <p role="alert" className="rounded-xl border border-amber-300/30 p-4 text-sm text-amber-200">{result.detail}</p> : null}
          </form>
        </section>
      </div>
      <CommercialBuyerExplanation />
      <TamBuyingIntentEvidenceGuide />
    </div>
  </main>;
}
