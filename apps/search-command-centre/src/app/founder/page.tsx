import Link from "next/link";
import { connection } from "next/server";
import {
  getFounderDashboard,
  type FounderStage,
} from "@/lib/founder-api";

function show(value: unknown, fallback = "Unknown") {
  return value == null || value === "" ? fallback : String(value);
}

function int(value: unknown) {
  return typeof value === "number" ? value.toLocaleString("en-GB") : "Unknown";
}

function truth(value: boolean | null | undefined) {
  if (value === true) return "Observed";
  if (value === false) return "Not observed";
  return "Unknown";
}

function stageClass(stage: FounderStage) {
  if (stage.observed === true) {
    return "border-emerald-400/25 bg-emerald-400/[0.07]";
  }
  if (stage.observed === false) {
    return "border-amber-400/20 bg-amber-400/[0.05]";
  }
  return "border-white/8 bg-white/[0.025]";
}

function operatingTone(value: string | undefined) {
  if (value === "WAITING_EXTERNAL") {
    return "border-cyan-400/30 bg-cyan-400/10 text-cyan-200";
  }
  if (value === "FOUNDER_GATE") {
    return "border-violet-400/30 bg-violet-400/10 text-violet-200";
  }
  if (value === "COMPLETE") {
    return "border-emerald-400/30 bg-emerald-400/10 text-emerald-200";
  }
  return "border-amber-400/30 bg-amber-400/10 text-amber-200";
}

export default async function FounderPage() {
  await connection();
  const result = await getFounderDashboard();
  const data = result.data;
  const loop = data?.commercial_loop;
  const astra = data?.astra;
  const source = data?.source_health;
  const observed = astra?.observed ?? {};
  const board = astra?.board ?? [];
  const phases = data?.phases ?? [];
  const stages = loop?.stages ?? [];
  const operating = loop?.operating_state?.class ?? "UNKNOWN";

  return (
    <main className="min-h-screen bg-[#07100d] text-slate-100">
      <div className="grid-noise" />
      <div className="mx-auto max-w-[1600px] px-5 py-6 lg:px-10 lg:py-9">
        <header className="border-b border-white/10 pb-7">
          <div className="flex flex-col justify-between gap-5 xl:flex-row xl:items-end">
            <div>
              <Link
                href="/"
                className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-300 hover:text-emerald-200"
              >
                ← Search Command Centre
              </Link>
              <p className="eyebrow mt-6">Empire AI · Founder operating view</p>
              <h1 className="mt-2 text-4xl font-semibold tracking-[-0.04em] text-white md:text-5xl">
                Empire Founder Console
              </h1>
              <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-400">
                One truth surface for acquisition, buyer progression, real
                revenue evidence, Astra priorities and Blueprint state.
                Forecasts and requests are never presented as realized revenue.
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 text-xs font-semibold text-emerald-200">
                {show(data?.mode, "MODE UNKNOWN")}
              </span>
              <span
                className={[
                  "rounded-full border px-3 py-1 text-xs font-semibold",
                  operatingTone(operating),
                ].join(" ")}
              >
                {operating.replaceAll("_", " ")}
              </span>
            </div>
          </div>
        </header>

        {!result.ok || !data ? (
          <section className="panel mt-7">
            <p className="eyebrow">Founder read model</p>
            <h2 className="mt-1 text-lg font-semibold text-white">
              Dashboard API unavailable
            </h2>
            <p className="mt-4 text-sm text-slate-400">
              {result.reason === "api_base_not_configured"
                ? "Set the server-only Empire API base URL to activate this read-only view."
                : result.reason ?? "Founder evidence is unavailable."}
            </p>
          </section>
        ) : (
          <>
            <section className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
              <MetricCard
                label="Owned inventory"
                value={int(observed.owned_inventory_count)}
                note="Canonical inventory"
              />
              <MetricCard
                label="Qualified unallocated"
                value={int(observed.qualified_unallocated_count)}
                note="Ready inventory"
              />
              <MetricCard
                label="Buyer capacity"
                value={int(observed.active_buyer_capacity)}
                note="Verified capacity"
              />
              <MetricCard
                label="Replies waiting"
                value={int(observed.replies_waiting)}
                note="Closer input"
              />
              <MetricCard
                label="Recognized revenue"
                value={
                  typeof astra?.calibration?.actual_revenue_cents === "number"
                    ? new Intl.NumberFormat("en-GB", {
                        style: "currency",
                        currency: "GBP",
                      }).format(
                        Number(astra.calibration.actual_revenue_cents) / 100,
                      )
                    : "Unknown"
                }
                note="Actual only"
              />
              <MetricCard
                label="Realized GP"
                value={
                  typeof astra?.calibration?.gross_profit_cents === "number"
                    ? new Intl.NumberFormat("en-GB", {
                        style: "currency",
                        currency: "GBP",
                      }).format(
                        Number(astra.calibration.gross_profit_cents) / 100,
                      )
                    : "Unknown"
                }
                note="Cost-backed only"
              />
            </section>

            <div className="mt-7 grid gap-5 2xl:grid-cols-[1.55fr_.85fr]">
              <section className="panel">
                <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
                  <div>
                    <p className="eyebrow">Commercial loop</p>
                    <h2 className="mt-1 text-2xl font-semibold text-white">
                      Revenue path
                    </h2>
                    <p className="mt-2 max-w-2xl text-sm text-slate-500">
                      Current next event:{" "}
                      <span className="text-slate-300">
                        {show(loop?.operating_state?.next_event)}
                      </span>
                    </p>
                  </div>
                  <div className="text-left lg:text-right">
                    <p className="text-xs uppercase tracking-[0.14em] text-slate-600">
                      Founder action
                    </p>
                    <p className="mt-1 text-sm font-semibold text-white">
                      {loop?.operating_state?.founder_action_required
                        ? "Required"
                        : "Not required"}
                    </p>
                  </div>
                </div>

                <div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {stages.map((stage, index) => (
                    <div
                      key={show(stage.stage, String(index))}
                      className={[
                        "rounded-2xl border p-4",
                        stageClass(stage),
                      ].join(" ")}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-sm font-semibold text-white">
                          {show(stage.stage).replaceAll("_", " ")}
                        </p>
                        <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                          {truth(stage.observed)}
                        </span>
                      </div>
                      <p className="mt-2 text-xs leading-5 text-slate-500">
                        {show(stage.detail)}
                      </p>
                    </div>
                  ))}
                </div>
              </section>

              <section className="panel">
                <p className="eyebrow">Acquisition health</p>
                <h2 className="mt-1 text-xl font-semibold text-white">
                  {show(source?.source)} · {show(source?.metro)}
                </h2>
                <div className="mt-5 grid grid-cols-2 gap-3">
                  <Evidence
                    label="Endpoint"
                    value={truth(source?.endpoint_healthy)}
                  />
                  <Evidence
                    label="End to end"
                    value={truth(source?.end_to_end_healthy)}
                  />
                  <Evidence
                    label="Candidates seen"
                    value={int(source?.candidates_seen)}
                  />
                  <Evidence
                    label="Quality accepted"
                    value={int(source?.quality_accepted)}
                  />
                  <Evidence
                    label="Canonical authority"
                    value={truth(source?.canonical_ingest_authorized)}
                  />
                  <Evidence
                    label="Scheduled"
                    value={truth(source?.canonical_ingest_scheduled)}
                  />
                </div>
                <div className="mt-5 border-t border-white/8 pt-4">
                  <p className="text-xs text-slate-500">
                    {source?.blockers?.length
                      ? source.blockers.join(" · ")
                      : "No current source-health blocker"}
                  </p>
                </div>
              </section>
            </div>

            <div className="mt-5 grid gap-5 xl:grid-cols-2">
              <section className="panel">
                <p className="eyebrow">Astra command board</p>
                <h2 className="mt-1 text-xl font-semibold text-white">
                  Current priorities
                </h2>
                <div className="mt-5 grid gap-3">
                  {board.length ? (
                    board.slice(0, 6).map((item, index) => (
                      <div
                        className="rounded-2xl border border-white/8 bg-white/[0.025] p-4"
                        key={String(item.id ?? index)}
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <p className="text-sm font-semibold text-white">
                              {show(item.workstream ?? item.title)}
                            </p>
                            <p className="mt-1 text-xs text-slate-500">
                              {show(
                                item.recommended_job_type ??
                                  item.recommendation,
                              )}
                            </p>
                          </div>
                          <span className="text-sm font-semibold text-emerald-200">
                            {show(item.priority)}
                          </span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-slate-500">
                      No Astra board items observed.
                    </p>
                  )}
                </div>
              </section>

              <section className="panel">
                <p className="eyebrow">Growth & opportunity</p>
                <h2 className="mt-1 text-xl font-semibold text-white">
                  Opportunity Foundry
                </h2>
                <p className="mt-3 text-sm leading-6 text-slate-400">
                  Search demand, market gaps, buyer demand, available supply,
                  predictive evidence and experiments converge here. Unknown
                  evidence remains unknown; no synthetic opportunity value is
                  created.
                </p>
                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                  <Drill href="/opportunities" title="Search opportunities" />
                  <Drill href="/revenue" title="Organic revenue evidence" />
                  <Drill href="/competitors" title="Competitor gaps" />
                  <Drill href="/evidence" title="Evidence timeline" />
                </div>
              </section>
            </div>

            <section className="panel mt-5">
              <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
                <div>
                  <p className="eyebrow">Blueprint control room</p>
                  <h2 className="mt-1 text-xl font-semibold text-white">
                    Phases 3–18
                  </h2>
                </div>
                <p className="text-xs text-slate-600">
                  Verified markers are implementation evidence, not revenue.
                </p>
              </div>
              <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {phases.map((phase) => (
                  <div
                    className="rounded-2xl border border-white/8 bg-white/[0.025] p-4"
                    key={phase.phase}
                  >
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-emerald-300">
                      Phase {show(phase.phase)}
                    </p>
                    <p className="mt-2 text-sm font-semibold text-white">
                      {show(phase.title)}
                    </p>
                    <p className="mt-3 text-xs text-slate-500">
                      {show(phase.state).replaceAll("_", " ")}
                    </p>
                    <p className="mt-2 text-xs text-slate-600">
                      {int(phase.verified_markers)} verified markers
                    </p>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
      </div>
    </main>
  );
}

function MetricCard({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note: string;
}) {
  return (
    <div className="metric-card">
      <p className="eyebrow">{label}</p>
      <p className="mt-4 text-3xl font-semibold text-white">{value}</p>
      <p className="mt-2 text-xs text-slate-500">{note}</p>
    </div>
  );
}

function Evidence({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.025] p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">
        {label}
      </p>
      <p className="mt-2 text-sm font-semibold text-slate-200">{value}</p>
    </div>
  );
}

function Drill({ href, title }: { href: string; title: string }) {
  return (
    <Link
      href={href}
      className="rounded-2xl border border-white/8 bg-white/[0.025] p-4 text-sm font-semibold text-slate-200 transition hover:border-emerald-400/30 hover:text-emerald-200"
    >
      {title} →
    </Link>
  );
}
