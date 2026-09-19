import Link from "next/link";
import { connection } from "next/server";
import { getOpportunityData } from "@/lib/search-api";

function show(value: unknown) {
  return value == null || value === "" ? "Unknown" : String(value);
}

function metric(value: unknown, percent = false) {
  if (typeof value !== "number") return "Unknown";
  return percent ? `${Math.round(value * 100)}%` : String(value);
}

export default async function OpportunitiesPage() {
  await connection();
  const data = await getOpportunityData();
  const items = data.opportunities.data?.items ?? [];
  const observe =
    data.health.data?.execution_mode === "OBSERVE" ||
    data.health.data?.execution_mode === "observe";

  return (
    <main className="min-h-screen bg-[#07100d] text-slate-100">
      <div className="grid-noise" />
      <div className="mx-auto max-w-[1500px] px-5 py-6 lg:px-10 lg:py-9">
        <header className="border-b border-white/10 pb-7">
          <Link href="/" className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-300 hover:text-emerald-200">
            ← Search Command Centre
          </Link>
          <div className="mt-6 flex flex-col justify-between gap-5 md:flex-row md:items-end">
            <div>
              <p className="eyebrow">Phase 5 · Opportunity intelligence</p>
              <h1 className="mt-2 text-4xl font-semibold tracking-[-0.04em] text-white md:text-5xl">
                Opportunity drill-down
              </h1>
              <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-400">
                Canonical opportunity evidence only. Missing commercial, traffic or ranking evidence remains Unknown.
              </p>
            </div>
            <span className="w-fit rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 text-xs font-semibold text-emerald-200">
              {observe ? "OBSERVE" : "MODE UNKNOWN"}
            </span>
          </div>
        </header>
        {!data.opportunities.ok ? (
          <section className="panel mt-7">
            <p className="eyebrow">Canonical opportunity feed</p>
            <h2 className="mt-1 text-lg font-semibold text-white">Repository gated</h2>
            <p className="mt-4 text-sm text-slate-400">
              {data.opportunities.reason === "canonical_search_repository_not_activated"
                ? "The opportunity drill-down is ready, but the canonical Search reader is not activated in production yet."
                : data.opportunities.reason ?? "Opportunity evidence is unavailable."}
            </p>
          </section>
        ) : items.length ? (
          <div className="mt-7 grid gap-4">
            {items.map((item, index) => (
              <section className="panel" key={String(item.id ?? index)}>
                <div className="flex flex-col justify-between gap-5 xl:flex-row xl:items-start">
                  <div>
                    <p className="eyebrow">Observed opportunity</p>
                    <h2 className="mt-1 text-xl font-semibold text-white">
                      {show(item.query ?? item.topic ?? `Opportunity ${index + 1}`)}
                    </h2>
                    <p className="mt-3 max-w-3xl text-sm text-slate-500">
                      {show(item.score_reason)}
                    </p>
                  </div>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <Metric label="Opportunity" value={metric(item.opportunity_score)} />
                    <Metric label="Commercial intent" value={metric(item.commercial_intent, true)} />
                    <Metric label="Competition" value={metric(item.competition, true)} />
                    <Metric label="Conversion probability" value={metric(item.conversion_probability, true)} />
                  </div>
                </div>

                <div className="mt-5 grid gap-3 border-t border-white/8 pt-5 md:grid-cols-2 xl:grid-cols-4">
                  <Evidence label="Intent" value={item.intent} />
                  <Evidence label="Target page type" value={item.target_page_type} />
                  <Evidence label="Competitor presence" value={metric(item.competitor_presence, true)} />
                  <Evidence label="Empire coverage" value={metric(item.current_empire_coverage, true)} />
                  <Evidence label="Content gap" value={metric(item.content_gap, true)} />
                  <Evidence label="Relevance" value={metric(item.relevance, true)} />
                  <Evidence label="Authority fit" value={metric(item.authority_fit, true)} />
                  <Evidence label="Trend signal" value={metric(item.trend_signal, true)} />
                  <Evidence label="Conversion history" value={metric(item.conversion_history, true)} />
                  <Evidence label="Revenue history (cents)" value={item.revenue_history_cents} />
                  <Evidence label="Estimated business value (cents)" value={item.estimated_business_value_cents} />
                  <Evidence label="Observed at" value={item.observed_at} />
                </div>
              </section>
            ))}
          </div>
        ) : (
          <section className="panel mt-7">
            <p className="text-sm text-slate-500">No canonical opportunities observed yet.</p>
          </section>
        )}
      </div>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.025] p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">{label}</p>
      <p className="mt-2 text-lg font-semibold text-white">{value}</p>
    </div>
  );
}

function Evidence({ label, value }: { label: string; value: unknown }) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">{label}</p>
      <p className="mt-1 break-words text-sm text-slate-300">{show(value)}</p>
    </div>
  );
}
