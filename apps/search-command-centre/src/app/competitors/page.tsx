import Link from "next/link";
import { connection } from "next/server";
import { getCompetitorData } from "@/lib/search-api";

function pct(value: unknown) {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "Unknown";
}

function num(value: unknown) {
  return typeof value === "number" ? String(value) : "Unknown";
}

export default async function CompetitorsPage() {
  await connection();
  const data = await getCompetitorData();
  const items = data.opportunities.data?.items ?? [];
  const observe =
    data.health.data?.execution_mode === "OBSERVE" ||
    data.health.data?.execution_mode === "observe";

  return (
    <main className="min-h-screen bg-[#07100d] text-slate-100">
      <div className="grid-noise" />
      <div className="mx-auto max-w-[1500px] px-5 py-6 lg:px-10 lg:py-9">
        <header className="border-b border-white/10 pb-7">
          <div className="flex flex-col justify-between gap-5 md:flex-row md:items-end">
            <div>
              <Link
                href="/"
                className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-300 hover:text-emerald-200"
              >
                ← Search Command Centre
              </Link>
              <p className="eyebrow mt-6">Phase 5 · Competitor intelligence</p>
              <h1 className="mt-2 text-4xl font-semibold tracking-[-0.04em] text-white md:text-5xl">
                Observed search gaps
              </h1>
              <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-400">
                Competitor coverage is derived only from observed SERP and canonical opportunity evidence. Traffic, keyword volume, authority and market share remain unknown unless independently evidenced.
              </p>
            </div>
            <span
              className={[
                "w-fit rounded-full border px-3 py-1 text-xs font-semibold",
                observe
                  ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"
                  : "border-amber-400/30 bg-amber-400/10 text-amber-200",
              ].join(" ")}
            >
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
                ? "The competitor view is ready, but the canonical Search reader is not activated in production yet."
                : data.opportunities.reason ?? "Competitor evidence is unavailable."}
            </p>
          </section>
        ) : items.length ? (
          <div className="mt-7 grid gap-4">
            {items.map((item, index) => (
              <section className="panel" key={String(item.id ?? index)}>
                <div className="grid gap-6 xl:grid-cols-[1fr_auto]">
                  <div>
                    <p className="eyebrow">Observed opportunity</p>
                    <h2 className="mt-1 text-xl font-semibold text-white">
                      {String(item.query ?? item.topic ?? `Opportunity ${index + 1}`)}
                    </h2>
                    <p className="mt-3 text-sm text-slate-500">
                      {String(item.score_reason ?? "Canonical Search Intelligence record")}
                    </p>
                  </div>
                  <div className="grid min-w-[320px] grid-cols-2 gap-3 sm:grid-cols-4">
                    <Metric label="Empire coverage" value={pct(item.current_empire_coverage)} />
                    <Metric label="Competitor presence" value={pct(item.competitor_presence)} />
                    <Metric label="Content gap" value={pct(item.content_gap)} />
                    <Metric label="Opportunity" value={num(item.opportunity_score)} />
                  </div>
                </div>
                <div className="mt-5 grid gap-3 border-t border-white/8 pt-5 md:grid-cols-3">
                  <EvidenceField label="Intent" value={item.intent} />
                  <EvidenceField label="Target page" value={item.target_page_type} />
                  <EvidenceField label="Observed at" value={item.observed_at} />
                </div>
              </section>
            ))}
          </div>
        ) : (
          <section className="panel mt-7">
            <p className="text-sm text-slate-500">No canonical competitor-gap opportunities observed yet.</p>
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

function EvidenceField({ label, value }: { label: string; value: unknown }) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">{label}</p>
      <p className="mt-1 text-sm text-slate-300">{value == null || value === "" ? "Unknown" : String(value)}</p>
    </div>
  );
}
