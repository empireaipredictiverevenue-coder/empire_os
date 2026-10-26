"use client";
import CommercialBuyerExplanation from "@/components/CommercialBuyerExplanation";
import BrokeragePremiumDiscovery from "@/components/BrokeragePremiumDiscovery";
import TamBuyingIntentEvidenceGuide from "@/components/TamBuyingIntentEvidenceGuide";
import { ArrowLeft, ArrowRight, ArrowUpRight, LoaderCircle, CheckCircle2, Radar, ShieldCheck, Layers3 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  reuseCommercialInterestAttempt,
  type CommercialInterestAttempt,
  type CommercialInterestDetails,
} from "@/lib/commercial-interest-attempt";
import { selectApprovedProposalOffer } from "@/lib/buyer-proposal-handoff";
import { claimedEntryForReview } from "@/lib/commercial-entry-review";
import { commercialOfferCategory } from "@/lib/commercial-offer-category";

type Offer = { product_code: string; name: string; offer_family: string; currency: string; approved_price_cents: number; price_interval: string; implementation_fee_cents?: number };
type Catalog = { status: string; offers: Offer[] };
type Receipt = { decision?: string; reference?: string; detail?: string; error?: string };
const inputStyle = "mt-2 w-full rounded-xl border border-[#b1c9f3]/20 bg-[#061327] px-4 py-3.5 text-sm text-white placeholder:text-slate-500 outline-none transition focus:border-[#e5bc76] focus:ring-1 focus:ring-[#e5bc76]/40";
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

  return <main className="min-h-screen overflow-hidden bg-[#030916] text-[#eef5ff] selection:bg-[#dfb875] selection:text-[#111a2a]">
    <section className="relative isolate overflow-hidden border-b border-[#b0c5e6]/15">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-[url('/art/empire-atrium.webp')] bg-cover bg-[position:70%_center] opacity-40" />
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-[linear-gradient(90deg,#030916_0%,rgba(3,9,22,.97)_45%,rgba(3,9,22,.36)_100%),linear-gradient(0deg,#030916_0%,transparent_50%)]" />
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_84%_32%,rgba(222,176,107,.18),transparent_37%)]" />
      <div className="relative z-10 mx-auto w-[min(1440px,calc(100%-40px))]">
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-[#b4c7e8]/15 py-6">
          <a href="/" className="inline-flex items-center gap-3 text-xs font-bold tracking-[.2em] text-white"><span className="grid size-10 place-items-center rounded-xl border border-[#dfb875]/35 bg-[#dfb875]/10 text-[#f1d39e]"><Layers3 className="size-5" aria-hidden="true" /></span> EMPIRE AI</a>
          <nav aria-label="Commercial navigation" className="flex flex-wrap gap-5 text-xs font-semibold text-[#dce7f8]/70">
            <a href="/buy" className="hover:text-white">Intelligence products</a>
            <a href="/predictive-revenue" className="hover:text-white">Predictive Revenue</a>
            <a href="/trust" className="hover:text-white">Trust</a>
          </nav>
        </header>
        <div className="grid items-end gap-10 pb-24 pt-20 lg:grid-cols-[1.3fr_.7fr] lg:pb-28 lg:pt-28">
          <div className="max-w-4xl">
            <p className="flex items-center gap-3 text-[11px] font-bold tracking-[.22em] text-[#f1d39e]"><span className="h-px w-9 bg-[#f1d39e]" /> EMPIRE AI / COMMERCIAL INTELLIGENCE</p>
            <h1 className="mt-8 text-[clamp(3.4rem,7vw,7rem)] font-semibold leading-[.94] tracking-[-.066em]">Turn intelligence into <span className="text-[#f1d39e]">a real commercial decision.</span></h1>
            <p className="mt-8 max-w-2xl text-base leading-8 text-[#d7e3f6]/80 sm:text-lg">
              Predictive Revenue, industry intelligence and bespoke research for businesses making consequential growth decisions.
              Tell us the outcome. We'll establish the evidence, delivery scope and commercial fit with you.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <a href="#commercial-enquiry" className="inline-flex min-h-14 items-center justify-center gap-3 rounded-full bg-[#dfb875] px-7 py-4 text-sm font-bold text-[#111a2a] transition hover:bg-[#f3d59f]">Request a scoped proposal <ArrowUpRight className="size-4" aria-hidden="true" /></a>
              <a href="#commercial-options" className="inline-flex min-h-14 items-center justify-center gap-3 rounded-full border border-[#b4c7e8]/30 bg-[#10203a]/50 px-7 py-4 text-sm font-semibold backdrop-blur-lg transition hover:border-white/60">Explore options <ArrowRight className="size-4" aria-hidden="true" /></a>
            </div>
            <p className="mt-5 text-xs leading-6 text-[#d5e2f3]/60">Founder-reviewed. No automatic order, payment or guarantee of available buyer capacity.</p>
          </div>
          <aside aria-label="From enquiry to verified scope" className="rounded-[26px] border border-[#d7e5ff]/20 bg-[#07182e]/75 p-6 shadow-[0_25px_75px_rgba(0,0,0,.35)] backdrop-blur-2xl sm:p-8">
            <div className="flex items-center justify-between gap-4 border-b border-white/10 pb-5">
              <p className="text-[10px] font-bold tracking-[.2em] text-[#f1d39e]">HOW WORK BEGINS</p>
              <Radar className="size-6 text-[#f1d39e]" strokeWidth={1.5} aria-hidden="true" />
            </div>
            {[
              ["01", "Define the problem", "Describe the market, decision and intended result."],
              ["02", "Validate the scope", "Check relevant evidence, delivery assumptions and capacity."],
              ["03", "Agree the terms", "Review the proposed work before any commitment."],
            ].map(([step,title,body])=><div key={step} className="grid grid-cols-[36px_1fr] gap-3 border-b border-white/10 py-5 last:border-0">
              <span className="text-xs font-bold text-[#f1d39e]">{step}</span>
              <div><p className="text-sm font-bold text-white">{title}</p><p className="mt-2 text-xs leading-6 text-[#d7e3f6]/65">{body}</p></div>
            </div>)}
            <div className="mt-2 flex gap-3 text-xs leading-6 text-[#cbdcf1]/65">
              <ShieldCheck className="mt-1 size-4 shrink-0 text-[#f1d39e]" aria-hidden="true" />
              <span>Decisions stay tied to documented evidence and explicit commercial acceptance.</span>
            </div>
          </aside>
        </div>
      </div>
    </section>
    <div className="mx-auto w-[min(1380px,calc(100%-40px))]">
      <section id="commercial-options" className="scroll-mt-8 pb-4 pt-20 sm:pt-28">
        <p className="text-[11px] font-bold tracking-[.2em] text-[#f1d39e]">FROM EXPLORATION TO PROPOSAL</p>
        <h2 className="mt-4 max-w-4xl text-[clamp(2.5rem,4.5vw,4.4rem)] font-semibold leading-[1.04] tracking-[-.054em]">Choose a starting point.<span className="block text-[#f1d39e]">Build around the real business problem.</span></h2>
        <p className="mt-6 max-w-3xl text-base leading-8 text-[#cfdef2]/65">No generic lead package, speculative return promise or instant purchase. Every enquiry goes through the existing first-party founder review.</p>
      </section>
      <div className="grid items-start gap-8 pb-20 lg:grid-cols-[.95fr_1.05fr] xl:gap-12">
        <section aria-label="Approved pricing" className="rounded-[28px] border border-[#a9c2f0]/15 bg-[#09172d]/75 p-5 shadow-[0_26px_70px_rgba(0,0,0,.24)] sm:p-8">
          <p className="text-[11px] font-bold tracking-[.2em] text-[#e9c487]">SOLUTION PATHWAYS</p>
          <h2 className="mb-4 mt-4 text-[clamp(1.75rem,3vw,2.35rem)] font-semibold tracking-[-.045em]">Choose the conversation, not a checkout.</h2>
          <p className="mb-7 max-w-xl text-sm leading-7 text-[#d2dff3]/70">Explore founder-approved starting offers. We review the actual business problem, source coverage and delivery requirements before agreeing any scope.</p>
          {error && <p role="alert" className="rounded-xl border border-amber-300/30 p-4 text-sm text-amber-200">{error}</p>}
          {!offers.length && !error && <p className="text-sm text-slate-400">Loading offer options…</p>}
          <div className="grid gap-3">
            {offers.map(offer => <button key={offer.product_code} type="button"
              aria-pressed={code === offer.product_code}
              onClick={() => { setCode(offer.product_code); setResult(null); }}
              className={"rounded-2xl border p-5 text-left transition " +
                (code === offer.product_code ? "border-[#e3bc79]/65 bg-[#d7b276]/[.08] ring-1 ring-[#e3bc79]/15" : "border-[#bbcff1]/15 bg-[#0d213d]/45 hover:border-[#a2c9f4]/45")}>
              <span className="flex flex-wrap items-start justify-between gap-3">
                <strong>{offer.name}</strong><strong className="text-[#f3d5a0]">{price(offer)}</strong>
              </span>
              <span className="mt-2 block text-xs text-slate-400">
                {commercialOfferCategory(offer.offer_family)}
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
        <section id="commercial-enquiry" className="h-fit scroll-mt-8 rounded-[28px] border border-[#ddba78]/25 bg-[linear-gradient(160deg,#0f2442,#071428_65%)] p-6 shadow-[0_28px_90px_rgba(0,0,0,.25)] md:p-9">
          <p className="text-[11px] font-bold tracking-[.2em] text-[#e9c487]">CONFIDENTIAL SCOPING ENQUIRY</p>
          <h2 className="mt-3 text-3xl font-semibold tracking-[-.045em]">Tell us what you need to achieve.</h2>
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
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#dfb875] px-5 py-4 text-sm font-bold text-[#111a2a] transition hover:bg-[#f1d39e] disabled:opacity-40">
              {submitting ? <LoaderCircle className="size-4 animate-spin" /> : <ArrowRight className="size-4" />}
              {submitting ? "Recording…" : "Request founder proposal"}
            </button>
            {result?.decision === "commercial_enquiry_recorded" ?
              <p role="status" className="flex items-center gap-2 rounded-xl border border-emerald-300/20 p-4 text-sm text-emerald-200"><CheckCircle2 className="size-4" /> Enquiry recorded, reference {result.reference}. No order or payment created. To start a separate enquiry, reload this page.</p>
              : result?.detail ? <p role="alert" className="rounded-xl border border-amber-300/30 p-4 text-sm text-amber-200">{result.detail}</p> : null}
          </form>
        </section>
      </div>
      <section aria-label="Premium brokerage discovery" className="border-y border-[#b7c9ec]/15 py-16">
        <div className="mb-8 max-w-3xl">
          <p className="text-[11px] font-bold tracking-[.2em] text-[#f1d39e]">BESPOKE INTELLIGENCE / SPECIALIST DISCOVERY</p>
          <h2 className="mt-4 text-[clamp(2.25rem,4vw,3.8rem)] font-semibold tracking-[-.05em]">For projects that don’t fit a standard box.</h2>
          <p className="mt-5 text-sm leading-7 text-[#d7e3f6]/70">Explore specialist data and premium research capabilities separately from approved standard proposal offers.</p>
        </div>
        <BrokeragePremiumDiscovery />
      </section>
      <div className="pb-20 pt-8">
        <CommercialBuyerExplanation />
        <TamBuyingIntentEvidenceGuide />
      </div>
      <footer className="flex flex-wrap items-center justify-between gap-4 border-t border-[#b7c9ec]/15 py-9 text-xs text-[#cbdaed]/60">
        <span>EMPIRE AI / COMMERCIAL INTELLIGENCE</span>
        <span>Evidence-led scope · Explicit consent · Verified outcomes</span>
        <a href="/privacy" className="hover:text-white">Privacy</a>
      </footer>
    </div>
  </main>;
}
