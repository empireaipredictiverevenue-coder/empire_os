"use client";

import { useState } from "react";
import { ArrowRight, CheckCircle2, CircleAlert, ScanSearch } from "lucide-react";

/**
 * Public, illustrative diagnostic: never uses customer data or calls an API.
 * This is NOT an assessment of anyone's CRM, evidence of achieved outcomes,
 * a separate contact funnel, or a promise of paid delivery.
 */
const CASES = [
  {
    id: "pipeline",
    label: "Lead to demo",
    question: "Are leads becoming real sales conversations?",
    checks: [
      { stage: "Accepted lead", proof: "Named company, original source and sales owner", hold: "A page visit or email open is not a qualified lead" },
      { stage: "Demo completed", proof: "Buyer attended and meeting outcome was recorded", hold: "A booked meeting does not prove the demo happened" },
      { stage: "Next buyer decision", proof: "Explicitly agreed next action with a date", hold: "An internal reminder is not evidence of buyer intent" },
    ],
    action: "First identify abandoned lead handoffs and demos without a buyer-approved next step.",
  },
  {
    id: "trial",
    label: "Trial to contract",
    question: "Which trials are getting stuck before a decision?",
    checks: [
      { stage: "Trial accepted", proof: "Sponsor, start date and buyer-agreed success criteria", hold: "A self-serve signup is not always an enterprise evaluation" },
      { stage: "Trial outcome", proof: "Passed, rejected or completed with reason and date", hold: "Activity in the product is not an approved contract" },
      { stage: "Signed scope", proof: "Agreement with its actual effective date and entity", hold: "A pipeline estimate is not booked revenue" },
    ],
    action: "Separate technical use from a commercial decision; review stale trials by last buyer-confirmed progress.",
  },
  {
    id: "revenue",
    label: "Deal to cash",
    question: "How much forecast revenue actually became real?",
    checks: [
      { stage: "Commercial estimate", proof: "Owner, stage, assumption and as-of date", hold: "Seller-estimated deal value is not a customer commitment" },
      { stage: "Signed booking", proof: "Buyer-approved agreement and authorised amount", hold: "Closed-won alone is not independently verified revenue" },
      { stage: "Realised revenue", proof: "Finance-issued settlement or recognition evidence", hold: "A payment link or unsigned invoice is not collected cash" },
    ],
    action: "Maintain distinct forecast, booking, fulfilment and cash histories so predictions can be checked against outcomes.",
  },
] as const;

export default function SaaSRevenueEvidencePreview() {
  const [selection, setSelection] = useState<(typeof CASES)[number]["id"]>("pipeline");
  const selected = CASES.find((item) => item.id === selection) ?? CASES[0];

  return (
    <section
      id="free-evidence-sample"
      aria-labelledby="evidence-sample-title"
      className="mb-12 scroll-mt-24 overflow-hidden rounded-3xl border border-cyan-300/20 bg-[linear-gradient(130deg,rgba(12,32,72,.95),rgba(3,12,28,.98))] p-5 shadow-[0_24px_80px_rgba(3,15,40,.36)] md:p-8"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-cyan-200">
          <ScanSearch className="size-4" aria-hidden="true" />
          Free evidence-methodology preview
        </span>
        <span className="rounded-full border border-white/10 px-3 py-1.5 text-[10px] font-medium text-white/50">
          Example only — no customer data
        </span>
      </div>

      <div className="mt-5 grid gap-6 lg:grid-cols-[1.3fr_.7fr] lg:items-start">
        <div>
          <h2 id="evidence-sample-title" className="max-w-3xl text-2xl font-semibold tracking-[-.035em] text-white md:text-3xl">
            See what a revenue diagnostic actually checks.
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300/80">
            Instead of claiming a conversion uplift, Empire separates observable
            buyer progress from estimates, bookings and money received. Explore
            three common B2B SaaS decisions before sharing any company details.
          </p>

          <div aria-label="Choose an illustrative commercial question" className="mt-6 flex flex-wrap gap-2">
            {CASES.map((item) => (
              <button
                key={item.id}
                type="button"
                aria-pressed={selection === item.id}
                onClick={() => setSelection(item.id)}
                className={
                  "rounded-full border px-4 py-2.5 text-xs font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-200 " +
                  (selection === item.id
                    ? "border-cyan-200/55 bg-cyan-300/15 text-cyan-100"
                    : "border-white/10 text-white/55 hover:border-cyan-200/30 hover:text-white")
                }
              >
                {item.label}
              </button>
            ))}
          </div>

          <h3 className="mt-7 text-base font-semibold text-white">{selected.question}</h3>
          <div className="mt-4 grid gap-3">
            {selected.checks.map((check, index) => (
              <div key={check.stage} className="rounded-2xl border border-white/10 bg-white/[.035] p-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
                  <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-cyan-300/15 text-xs text-cyan-200">{index + 1}</span>
                  {check.stage}
                </div>
                <div className="mt-3 flex gap-2 text-xs leading-5 text-slate-300/80">
                  <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-cyan-300" aria-hidden="true" />
                  <span><strong className="text-slate-200">Evidence:</strong> {check.proof}</span>
                </div>
                <div className="mt-2 flex gap-2 text-xs leading-5 text-slate-400">
                  <CircleAlert className="mt-0.5 size-4 shrink-0 text-amber-200/70" aria-hidden="true" />
                  <span>{check.hold}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <aside className="rounded-2xl border border-blue-200/15 bg-[#06122c]/80 p-5">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-sky-200">
            The actionable question
          </div>
          <p className="mt-3 text-sm leading-7 text-white/80">{selected.action}</p>
          <div className="mt-6 border-t border-white/10 pt-5">
            <div className="text-xs font-semibold text-white">What you receive from this free preview</div>
            <p className="mt-2 text-xs leading-6 text-white/55">
              A public evidence checklist, not fabricated company scores.
              A customer-specific diagnostic needs permitted real records,
              agreed scope and independent validation.
            </p>
          </div>
          <a
            href="#deployment-request"
            className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-[#eaf2ff] px-4 py-3 text-center text-xs font-bold text-[#07132c] transition hover:bg-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-200"
          >
            Discuss your own revenue question <ArrowRight className="size-4" aria-hidden="true" />
          </a>
          <p className="mt-3 text-center text-[10px] leading-5 text-white/40">
            Uses the existing consent-based deployment enquiry. No new
            mailing list, payment or data collection for this preview.
          </p>
        </aside>
      </div>
    </section>
  );
}
