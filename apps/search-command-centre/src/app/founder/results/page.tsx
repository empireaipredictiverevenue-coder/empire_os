import Link from "next/link";
import { connection } from "next/server";
import { getFounderDailyResultsHistory } from "@/lib/founder-api";

function show(value: unknown, fallback = "Unknown") {
  return value == null || value === "" ? fallback : String(value);
}

function int(value: unknown) {
  return typeof value === "number" ? value.toLocaleString("en-GB") : "Unknown";
}

export default async function FounderResultsPage() {
  await connection();
  const result = await getFounderDailyResultsHistory(14);
  const items = result.data?.items ?? [];

  return (
    <main className="min-h-screen bg-[#07100d] text-slate-100">
      <div className="grid-noise" />
      <div className="mx-auto max-w-[1500px] px-5 py-7 lg:px-10">
        <header className="border-b border-white/10 pb-7">
          <Link
            href="/founder"
            className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-300 hover:text-emerald-200"
          >
            ← Founder Console
          </Link>
          <p className="eyebrow mt-6">Empire AI · Daily Results</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-[-0.04em] text-white">
            Operating History
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
            Acquisition, intent, commercial progression, Search, Coder,
            reliability and security in one evidence-first daily timeline.
          </p>
        </header>

        {!result.ok ? (
          <section className="panel mt-7">
            <p className="text-sm text-slate-400">
              Daily history unavailable: {show(result.reason)}
            </p>
          </section>
        ) : items.length === 0 ? (
          <section className="panel mt-7">
            <p className="text-sm text-slate-400">
              No daily results snapshots have been recorded yet.
            </p>
          </section>
        ) : (
          <div className="mt-7 space-y-5">
            {items.map((day) => (
              <section className="panel" key={show(day.date)}>
                <div className="flex flex-col justify-between gap-3 md:flex-row md:items-end">
                  <div>
                    <p className="eyebrow">{show(day.date)}</p>
                    <h2 className="mt-1 text-xl font-semibold text-white">
                      {show(day.headline?.commercial_blocker, "No blocker observed")}
                    </h2>
                  </div>
                  <p className="text-xs text-slate-600">
                    Owner {show(day.headline?.blocker_owner)} · authority{" "}
                    {show(day.headline?.blocker_authority)}
                  </p>
                </div>

                <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
                  <Result label="Omega" value={int(day.commercial_funnel?.omega_observations)} />
                  <Result label="Approved" value={int(day.commercial_funnel?.approved_buyers)} />
                  <Result label="Sent" value={int(day.commercial_funnel?.outbound_sent)} />
                  <Result label="Conversations" value={int(day.commercial_funnel?.commercial_buyer_replies)} />
                  <Result label="Payments" value={int(day.commercial_funnel?.verified_payments)} />
                  <Result label="Revenue" value={int(day.commercial_funnel?.recognized_revenue_events)} />
                </div>

                <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
                  <Result label="Pulse state" value={show(day.revenue_pulse?.pulse_state)} />
                  <Result label="24h acquisitions" value={int(day.revenue_pulse?.current_window?.acquisitions)} />
                  <Result label="24h qualified" value={int(day.revenue_pulse?.current_window?.qualified)} />
                  <Result label="24h delivered" value={int(day.revenue_pulse?.current_window?.delivered_outreach)} />
                  <Result label="24h replies" value={int(day.revenue_pulse?.current_window?.commercial_replies)} />
                  <Result label="Control components" value={int(day.control_fabric?.component_count)} />
                </div>

                <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
                  <Result label="Intent" value={int(day.intent_and_pain?.observations)} />
                  <Result label="High intent" value={int(day.intent_and_pain?.high_intent)} />
                  <Result label="AEO assets" value={int(day.search_and_seo?.aeo_asset_count)} />
                  <Result label="Legal sources" value={int(day.legal_intelligence?.source_count_ready) + " / " + int(day.legal_intelligence?.source_count_total)} />
                  <Result label="RLS disabled" value={int(day.security?.findings?.rls_disabled_in_public)} />
                  <Result label="Incidents" value={int(day.reliability?.incident_count)} />
                </div>
              </section>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}

function Result({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.025] p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">
        {label}
      </p>
      <p className="mt-2 text-sm font-semibold text-slate-200">{value}</p>
    </div>
  );
}
