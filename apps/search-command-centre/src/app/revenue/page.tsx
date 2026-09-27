import Link from "next/link";
import { connection } from "next/server";
import { getRevenueAttributionData } from "@/lib/search-api";

function text(value: unknown, fallback = "Unknown") {
  return value == null || value === "" ? fallback : String(value);
}

function money(value: unknown) {
  return typeof value === "number"
    ? new Intl.NumberFormat("en-GB", {
        style: "currency",
        currency: "GBP",
      }).format(value / 100)
    : "Unknown";
}

export default async function RevenuePage() {
  await connection();
  const data = await getRevenueAttributionData();
  const rows = data.revenue.data?.items ?? [];
  const gated = !data.revenue.ok;

  const totalRevenue = rows.reduce(
    (sum, row) =>
      sum + (typeof row.revenue_cents === "number" ? row.revenue_cents : 0),
    0,
  );
  const linkedPages = new Set(
    rows
      .map((row) => row.page_id)
      .filter((value): value is string => typeof value === "string" && !!value),
  ).size;
  const linkedQueries = new Set(
    rows
      .map((row) => row.query)
      .filter((value): value is string => typeof value === "string" && !!value),
  ).size;

  return (
    <main className="min-h-screen bg-[#07100d] text-slate-100">
      <div className="grid-noise" />
      <div className="mx-auto max-w-[1300px] px-5 py-6 lg:px-10 lg:py-9">
        <header className="border-b border-white/10 pb-7">
          <Link
            href="/"
            className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-300 hover:text-emerald-200"
          >
            ← Search Command Centre
          </Link>
          <p className="eyebrow mt-6">Phase 5 · Commercial attribution</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-[-0.04em] text-white md:text-5xl">
            Organic Revenue
          </h1>
          <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-400">
            Read-only attribution evidence linking observed search touches to
            recognized commercial revenue. Unknown linkage stays unknown; this
            surface does not create attribution or revenue records.
          </p>
        </header>

        <section className="mt-7 grid gap-4 sm:grid-cols-3">
          <div className="metric-card metric-accent">
            <p className="eyebrow">Attributed revenue</p>
            <p className="mt-4 text-3xl font-semibold text-white">
              {gated ? "—" : money(totalRevenue)}
            </p>
            <p className="mt-2 text-xs text-slate-500">Observed records only</p>
          </div>
          <div className="metric-card">
            <p className="eyebrow">Linked pages</p>
            <p className="mt-4 text-3xl font-semibold text-white">
              {gated ? "—" : linkedPages}
            </p>
            <p className="mt-2 text-xs text-slate-500">Canonical page IDs</p>
          </div>
          <div className="metric-card">
            <p className="eyebrow">Linked queries</p>
            <p className="mt-4 text-3xl font-semibold text-white">
              {gated ? "—" : linkedQueries}
            </p>
            <p className="mt-2 text-xs text-slate-500">Observed query evidence</p>
          </div>
        </section>

        {gated ? (
          <section className="panel mt-7">
            <p className="eyebrow">Canonical revenue feed</p>
            <h2 className="mt-1 text-lg font-semibold text-white">
              Repository gated
            </h2>
            <p className="mt-4 text-sm text-slate-400">
              The revenue attribution view is ready, but the canonical Search
              reader is not activated here.
            </p>
            <p className="mt-3 font-mono text-[11px] text-slate-600">
              {data.revenue.reason ?? "unknown_gate"}
            </p>
          </section>
        ) : rows.length ? (
          <div className="mt-7 grid gap-3">
            {rows.map((row, index) => (
              <section className="panel" key={text(row.id, String(index))}>
                <div className="grid gap-4 lg:grid-cols-[1.5fr_.8fr_.8fr]">
                  <div>
                    <p className="eyebrow">Search touch</p>
                    <h2 className="mt-1 text-lg font-semibold text-white">
                      {text(row.url ?? row.query ?? row.page_id, "Observed attribution")}
                    </h2>
                    <p className="mt-2 text-sm text-slate-400">
                      {text(row.query, "Query unknown")} ·{" "}
                      {text(row.attribution_kind, "Attribution kind unknown")}
                    </p>
                    <p className="mt-3 font-mono text-[11px] text-slate-600">
                      session {text(row.external_session_id)} · prospect{" "}
                      {text(row.prospect_id)}
                    </p>
                  </div>

                  <div>
                    <p className="eyebrow">Commercial evidence</p>
                    <p className="mt-2 text-sm text-slate-300">
                      Order {text(row.fulfilment_order_id)}
                    </p>
                    <p className="mt-1 text-sm text-slate-400">
                      Event {text(row.commercial_event_id)}
                    </p>
                    <p className="mt-1 text-sm text-slate-400">
                      Opportunity {text(row.opportunity_id)}
                    </p>
                  </div>

                  <div className="lg:text-right">
                    <p className="eyebrow">Recognized revenue</p>
                    <p className="mt-2 text-2xl font-semibold text-emerald-200">
                      {money(row.revenue_cents)}
                    </p>
                    <p className="mt-2 font-mono text-[11px] text-slate-600">
                      {text(row.occurred_at ?? row.recorded_at, "Timestamp unknown")}
                    </p>
                  </div>
                </div>
              </section>
            ))}
          </div>
        ) : (
          <section className="panel mt-7">
            <p className="text-sm text-slate-500">
              No canonical search-attributed revenue evidence observed yet.
            </p>
          </section>
        )}

        <footer className="mt-6 border-t border-white/10 pt-5 text-xs text-slate-600">
          Read-only evidence · no attribution writes · no revenue recognition
          authority
        </footer>
      </div>
    </main>
  );
}
