import Link from "next/link";
import { connection } from "next/server";
import { getFounderSolarIntelligence } from "@/lib/founder-api";

function show(value: unknown, fallback = "Unknown") {
  return value == null || value === "" ? fallback : String(value);
}

export default async function SolarIntelligencePage() {
  await connection();
  const result = await getFounderSolarIntelligence("GB");
  const data = result.data;
  const proof = data?.latest_proof;
  const plan = data?.source_plan;
  const waterfall = plan?.waterfall ?? [];
  const candidates = proof?.candidates ?? [];

  return (
    <main className="min-h-screen bg-[#07100d] text-slate-100">
      <div className="grid-noise" />
      <div className="mx-auto max-w-[1600px] px-5 py-6 lg:px-10 lg:py-9">
        <header className="border-b border-white/10 pb-7">
          <div className="flex flex-col justify-between gap-5 xl:flex-row xl:items-end">
            <div>
              <Link
                href="/founder"
                className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-300 hover:text-emerald-200"
              >
                ← Founder Console
              </Link>
              <p className="eyebrow mt-6">Empire AI · Source Intelligence OS</p>
              <h1 className="mt-2 text-4xl font-semibold tracking-[-0.04em] text-white md:text-5xl">
                UK Solar Intelligence
              </h1>
              <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-400">
                Verified-source market intelligence for UK Solar PV. This view
                separates observed evidence from enrichment still required and
                never treats a prospect, score or forecast as revenue.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 text-xs font-semibold text-emerald-200">
                VERIFIED SOURCE PROOF
              </span>
              <span className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-xs font-semibold text-cyan-200">
                OBSERVE
              </span>
            </div>
          </div>
        </header>

        {!result.ok || !data ? (
          <section className="panel mt-7">
            <p className="eyebrow">Solar Intelligence</p>
            <h2 className="mt-1 text-lg font-semibold text-white">
              Read API unavailable
            </h2>
            <p className="mt-4 text-sm text-slate-400">
              {result.reason ?? "Source intelligence evidence unavailable."}
            </p>
          </section>
        ) : (
          <>
            <section className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
              <Metric label="UK market anchors" value={show(data.market_anchor_count)} note="National acquisition grid" />
              <Metric label="Observed candidates" value={show(proof?.candidate_count, "0")} note="Latest RECC proof" />
              <Metric label="Primary source" value={show(plan?.selected_source)} note="Current source waterfall" />
              <Metric label="Canonical write" value={data.truth?.canonical_write_observed ? "Observed" : "Not yet"} note="Dry-run remains separate" />
              <Metric label="Recognized revenue" value="£0" note="Truth only" />
            </section>

            <div className="mt-7 grid gap-5 2xl:grid-cols-[1.5fr_.9fr]">
              <section className="panel">
                <p className="eyebrow">Live proof</p>
                <div className="mt-1 flex flex-col justify-between gap-3 md:flex-row md:items-end">
                  <div>
                    <h2 className="text-2xl font-semibold text-white">
                      RECC Solar PV candidates
                    </h2>
                    <p className="mt-2 text-sm text-slate-500">
                      Latest bounded run · {show(proof?.started_at)}
                    </p>
                  </div>
                  <span className="text-xs font-semibold text-emerald-300">
                    {show(proof?.candidate_count, "0")} observed
                  </span>
                </div>

                <div className="mt-6 overflow-hidden rounded-2xl border border-white/8">
                  <div className="grid grid-cols-[1.5fr_.7fr_.55fr] gap-3 border-b border-white/8 bg-white/[0.035] px-4 py-3 text-[10px] font-semibold uppercase tracking-[0.13em] text-slate-500">
                    <span>Business</span>
                    <span>Evidence</span>
                    <span>Confidence</span>
                  </div>
                  {candidates.slice(0, 20).map((row, index) => (
                    <div
                      key={show(row.name, String(index))}
                      className="grid grid-cols-[1.5fr_.7fr_.55fr] gap-3 border-b border-white/6 px-4 py-3 last:border-b-0"
                    >
                      <div>
                        <p className="text-sm font-semibold text-white">
                          {show(row.name)}
                        </p>
                        <p className="mt-1 text-xs text-slate-600">
                          Solar PV · United Kingdom
                        </p>
                      </div>
                      <span className="self-center text-xs text-slate-400">
                        RECC member
                      </span>
                      <span className="self-center text-xs font-semibold text-emerald-300">
                        {show(row.quality_confidence)}%
                      </span>
                    </div>
                  ))}
                </div>
              </section>

              <section className="panel">
                <p className="eyebrow">Evidence waterfall</p>
                <h2 className="mt-1 text-xl font-semibold text-white">
                  Source stack
                </h2>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  Specialist and official sources are used before generic web
                  discovery. Quarantined sources are skipped automatically.
                </p>
                <div className="mt-5 grid gap-3">
                  {waterfall.map((source, index) => (
                    <div
                      key={show(source.source_id, String(index))}
                      className="rounded-2xl border border-white/8 bg-white/[0.025] p-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-white">
                            {show(source.authority)}
                          </p>
                          <p className="mt-1 text-xs text-slate-500">
                            {show(source.source_type).replaceAll("_", " ")}
                          </p>
                        </div>
                        <span className="text-xs font-semibold text-emerald-300">
                          {show(source.provenance_strength)}
                        </span>
                      </div>
                      <p className="mt-3 text-[11px] uppercase tracking-[0.12em] text-slate-600">
                        {show(source.freshness)} · {show(source.production_status)}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            </div>

            <section className="panel mt-5">
              <p className="eyebrow">Demo narrative</p>
              <h2 className="mt-1 text-xl font-semibold text-white">
                From installer list to commercial opportunity
              </h2>
              <div className="mt-5 grid gap-3 md:grid-cols-5">
                <Stage title="Discover" value="Observed" note="Certified Solar PV businesses" active />
                <Stage title="Resolve" value="Next" note="Companies House legal entity" />
                <Stage title="Verify" value="Next" note="MCS / TrustMark / first-party" />
                <Stage title="Opportunity" value="Next" note="EPC · planning · grid · territory" />
                <Stage title="Revenue" value="Unknown" note="Conversation · terms · payment" />
              </div>
            </section>

            <section className="mt-5 grid gap-5 xl:grid-cols-2">
              <div className="panel">
                <p className="eyebrow">What Empire knows</p>
                <h2 className="mt-1 text-xl font-semibold text-white">
                  Evidence already proved
                </h2>
                <div className="mt-5 grid gap-3">
                  <Evidence label="National market grid" value={show(data.market_anchor_count) + " anchors"} />
                  <Evidence label="Certified-source discovery" value="Observed" />
                  <Evidence label="Real business entities" value={show(proof?.candidate_count) + " in latest proof"} />
                  <Evidence label="Generic scraper dependency" value="Removed from production" />
                </div>
              </div>

              <div className="panel">
                <p className="eyebrow">What stays unknown</p>
                <h2 className="mt-1 text-xl font-semibold text-white">
                  No fabricated economics
                </h2>
                <div className="mt-5 grid gap-3">
                  <Evidence label="Customer demand" value="Needs EPC / planning evidence" />
                  <Evidence label="Installer capacity" value="Needs direct evidence" />
                  <Evidence label="Pricing" value="Needs verified commercial evidence" />
                  <Evidence label="Revenue" value="£0 until payment is verified" />
                </div>
              </div>
            </section>
          </>
        )}
      </div>
    </main>
  );
}

function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="panel">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-white">{value}</p>
      <p className="mt-1 text-xs text-slate-600">{note}</p>
    </div>
  );
}

function Stage({ title, value, note, active = false }: { title: string; value: string; note: string; active?: boolean }) {
  return (
    <div className={"rounded-2xl border p-4 " + (active ? "border-emerald-400/30 bg-emerald-400/[0.07]" : "border-white/8 bg-white/[0.025]")}>
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">{title}</p>
      <p className="mt-2 text-sm font-semibold text-white">{value}</p>
      <p className="mt-1 text-xs leading-5 text-slate-600">{note}</p>
    </div>
  );
}

function Evidence({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-xl border border-white/8 bg-white/[0.025] px-4 py-3">
      <span className="text-xs text-slate-500">{label}</span>
      <span className="text-xs font-semibold text-slate-200">{value}</span>
    </div>
  );
}
