import Link from "next/link";
import { connection } from "next/server";
import {
  getFounderDashboard,
  getFounderDataProducts,
  getFounderDailyResults,
  getFounderIntelligenceNodes,
  getFounderOps,
  getFounderOperationalTruth,
  getSpatialPhysicalStatus,
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

function operationalLaneTone(value: string) {
  if (value === "LIVE") return "border-emerald-400/30 bg-emerald-400/10 text-emerald-200";
  if (value === "READY") return "border-cyan-400/30 bg-cyan-400/10 text-cyan-200";
  if (value === "GATED") return "border-violet-400/30 bg-violet-400/10 text-violet-200";
  if (value === "BLOCKED") return "border-rose-400/30 bg-rose-400/10 text-rose-200";
  if (value === "OBSERVE") return "border-amber-400/30 bg-amber-400/10 text-amber-200";
  return "border-white/10 bg-white/[0.035] text-slate-400";
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
  const [
    result,
    nodesResult,
    productsResult,
    opsResult,
    dailyResult,
    operationalTruthResult,
    spatialResult,
  ] = await Promise.all([
    getFounderDashboard(),
    getFounderIntelligenceNodes(),
    getFounderDataProducts(),
    getFounderOps(),
    getFounderDailyResults(),
    getFounderOperationalTruth(),
    getSpatialPhysicalStatus(),
  ]);
  const data = result.data;
  const decision = data?.predictive_decision_control;
  const nextPriorities = decision?.top_three ?? [];
  const departmentHandoff = decision?.department_handoff;
  const buyerCapacity = decision?.buyer_capacity_action_brief;
  const formulaEvidence = decision?.formula_evidence;
  const streamMining = decision?.data_stream_mining;
  const evidencePathways = decision?.evidence_pathways;
  const commercialEvidence = decision?.commercial_evidence_request;
  const loop = data?.commercial_loop;
  const astra = data?.astra;
  const source = data?.source_health;
  const observed = astra?.observed ?? {};
  const board = astra?.board ?? [];
  const phases = data?.phases ?? [];
  const recovery = data?.recovery_portfolio;
  const recoveryProducts = recovery?.products ?? [];
  const recoveryByState = recovery?.summary?.by_state ?? {};
  const stages = loop?.stages ?? [];
  const operating = loop?.operating_state?.class ?? "UNKNOWN";
  const intelligenceNodes = nodesResult.data?.nodes ?? [];
  const dataProducts = productsResult.data?.products ?? [];
  const ops = opsResult.data;
  const incidents = ops?.incident_manager?.diagnoses ?? [];
  const repairPlan = ops?.sentinel?.repair_plan ?? [];
  const daily = dailyResult.data;
  const operationalTruth = operationalTruthResult.data;
  const operationalLanes = operationalTruth?.lanes ?? [];
  const dailyFunnel = daily?.commercial_funnel;
  const competitorIntelligence = data?.competitor_audience_intelligence;
  const competitorCompanies = competitorIntelligence?.companies ?? [];
  const graphCompany = [...competitorCompanies].sort(
    (a, b) => (b.competitor_count ?? 0) - (a.competitor_count ?? 0),
  )[0];
  const spatialStatus = spatialResult.data;
  const stormObservation = spatialStatus?.physical_rows?.[0];
  const stormMultiplier =
    typeof spatialStatus?.storm_multiplier_max === "number"
      ? spatialStatus.storm_multiplier_max.toFixed(3) + "×"
      : "Unknown";
  const opportunityRadar = data?.opportunity_radar;
  const opportunityBlockers = Object.entries(
    opportunityRadar?.blocker_counts ?? {},
  ).sort((a, b) => b[1] - a[1]);

  return (
    <main className="min-h-screen bg-[#07100d] text-slate-100">
      <div className="grid-noise" />
      <div className="mx-auto max-w-[1600px] px-5 py-6 lg:px-10 lg:py-9">
        <header className="border-b border-white/10 pb-7">
          <div className="flex flex-col justify-between gap-5 xl:flex-row xl:items-end">
            <div>
              <div className="flex flex-wrap gap-5">
                <Link
                  href="/"
                  className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-300 hover:text-emerald-200"
                >
                  ← Search Command Centre
                </Link>
                <Link
                  href="/predictive-revenue"
                  className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-300 hover:text-cyan-200"
                >
                  Predictive Revenue live demo →
                </Link>
              </div>
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
            <section className="panel mt-7" aria-labelledby="decision-control-title">
              <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
                <div>
                  <p className="eyebrow">Predictive decision control · Evidence-led</p>
                  <h2 id="decision-control-title" className="mt-1 text-2xl font-semibold tracking-tight text-white">
                    What Empire AI should work on next
                  </h2>
                  <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
                    Live canonical priorities, departmental ownership and clear approval boundaries.
                    Ranking is a triage heuristic, not a revenue forecast or execution permission.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2 text-xs">
                  <span className="rounded-full border border-cyan-300/25 bg-cyan-300/10 px-3 py-1 font-medium text-cyan-100">
                    {show(decision?.status, "NOT CONNECTED").replaceAll("_", " ")}
                  </span>
                  <span className="rounded-full border border-white/15 px-3 py-1 text-slate-300">
                    Observe only · No dispatch
                  </span>
                </div>
              </div>
              {decision ? (
                <>
                  <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
                    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                      <p className="text-xs text-slate-400">Priorities identified</p>
                      <p className="mt-2 text-2xl font-semibold text-white">{int(decision.priority_count)}</p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                      <p className="text-xs text-slate-400">Internal preparation</p>
                      <p className="mt-2 text-2xl font-semibold text-cyan-200">{int(decision.internal_preparation?.length)}</p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                      <p className="text-xs text-slate-400">Founder decisions</p>
                      <p className="mt-2 text-2xl font-semibold text-amber-200">{int(decision.founder_decisions?.length)}</p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                      <p className="text-xs text-slate-400">Work actually dispatched</p>
                      <p className="mt-2 text-lg font-semibold text-slate-300">{decision.task_dispatch_performed ? "Review" : "None"}</p>
                    </div>
                  </div>
                  <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl border border-white/10 bg-white/[0.025] px-4 py-3 text-xs text-slate-300">
                    <span className="font-semibold text-cyan-200">
                      Economic north star: realised gross profit
                    </span>
                    <span>Revenue evidence: {show(decision.revenue_truth_status).replaceAll("_", " ")}</span>
                    <span>Recognised revenue: {decision.recognized_revenue_cents == null ? "Unknown" : `${decision.recognized_revenue_cents.toLocaleString()} minor units`}</span>
                    <span>Realised GP: {decision.realized_gp_cents == null ? "Unknown" : `${decision.realized_gp_cents.toLocaleString()} minor units`}</span>
                    <span className="text-slate-500">
                      Currency and independent settlement reconciliation are not asserted by this view.
                    </span>
                  </div>
                  <div className="mt-5 rounded-2xl border border-cyan-300/15 bg-[#08131d] p-5">
                    <div className="flex flex-wrap justify-between gap-3">
                      <div>
                        <p className="eyebrow">Predictive Cloud · Intelligence mining</p>
                        <h3 className="mt-1 text-lg font-semibold text-white">
                          Existing data streams and research teams
                        </h3>
                        <p className="mt-2 text-xs leading-5 text-slate-400">
                          Mine existing source evidence without creating contacts,
                          guessed probabilities or fictional commercial outcomes.
                        </p>
                      </div>
                      <span className="text-xs text-cyan-200">
                        {show(streamMining?.status, "NOT CONNECTED").replaceAll("_", " ")}
                      </span>
                    </div>
                    {streamMining ? (
                      <>
                        <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-300">
                          <span>Source adapters: {streamMining.source_count}</span>
                          <span>Department workstreams: {streamMining.lane_count}</span>
                          <span>External spend: £0</span>
                        </div>
                        <div className="mt-4 rounded-xl border border-white/10 bg-white/[0.025] p-3">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="text-sm font-semibold text-white">Deeper UK / US source discovery</p>
                            <span className="text-xs text-cyan-200">
                              {streamMining.source_discovery?.source_count ?? "Unknown"} official / existing candidates assessed
                            </span>
                          </div>
                          <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-300">
                            <span>Existing connectors: {streamMining.source_discovery?.by_readiness?.REUSE_EXISTING ?? 0}</span>
                            <span>Read-only pilots: {streamMining.source_discovery?.by_readiness?.PILOT_READ_ONLY ?? 0}</span>
                            <span>New adapters to review: {streamMining.source_discovery?.by_readiness?.NEW_ADAPTER_REVIEW ?? 0}</span>
                            <span>Access/rights/empty holds: {Object.entries(streamMining.source_discovery?.by_readiness ?? {})
                              .filter(([status]) => !["REUSE_EXISTING", "PILOT_READ_ONLY", "NEW_ADAPTER_REVIEW"].includes(status))
                              .reduce((sum, [, count]) => sum + count, 0)}</span>
                          </div>
                          <p className="mt-2 text-xs text-slate-400">
                            Next candidate feeds: {(streamMining.source_discovery?.top_new_public_source_choices ?? [])
                              .slice(0, 5).map((key) => key.replaceAll("_", " ")).join(" · ") || "Source research required"}
                          </p>
                          <div className="mt-3 rounded-lg border border-cyan-300/10 p-3">
                            <p className="text-xs font-semibold text-white">UK procurement incremental cursor</p>
                            <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-300">
                              <span>Status: {show(streamMining.source_discovery?.uk_tender_incremental?.status, "Not activated").replaceAll("_", " ")}</span>
                              <span>Private pages: {streamMining.source_discovery?.uk_tender_incremental?.inflight_page_count ?? "Unknown"}</span>
                              <span>Private release receipts: {streamMining.source_discovery?.uk_tender_incremental?.inflight_source_records ?? "Unknown"}</span>
                              <span>Pending sector research: {streamMining.source_discovery?.uk_tender_incremental?.pending_sector_research_count ?? "Unknown"}</span>
                              <span>Backfill lag: {streamMining.source_discovery?.uk_tender_incremental?.backfill_remaining_hours ?? "Unknown"} hours</span>
                              <span>Receipt slots remaining: {streamMining.source_discovery?.uk_tender_incremental?.completed_receipt_slots_remaining ?? "Unknown"}</span>
                              <span>Previous checkpoint: {show(streamMining.source_discovery?.uk_tender_incremental?.previous_checkpoint_recovery, "Unknown").replaceAll("_", " ")}</span>
                            </div>
                            <p className="mt-2 text-[11px] text-slate-500">
                              Latest completed window: {streamMining.source_discovery?.uk_tender_incremental?.last_complete_window_end ?? "None verified"}.
                              Only a fully exhausted source cursor can complete a watermark.
                              Next internal action: {show(streamMining.source_discovery?.uk_tender_incremental?.next_safe_operator_action, "Review source readiness").replaceAll("_", " ")}.
                              Continuous polling and commercial execution remain off.
                            </p>
                          </div>
                          <div className="mt-3 rounded-lg border border-cyan-300/10 p-3">
                            <p className="text-xs font-semibold text-white">Scientific Agent · Ling 3.1 specialist</p>
                            <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-300">
                              <span>Ling free route: {show(streamMining.ling31_specialist?.status, "Not configured").replaceAll("_", " ")}</span>
                              <span>Scientific controls: {streamMining.scientific_validation?.controls_to_execute.length ?? "Unknown"}</span>
                              <span>Calibrated probability: no</span>
                            </div>
                            <p className="mt-2 text-[11px] text-slate-500">
                              Scientific method checklists are available for review.
                              Ling and OpenManus have not been invoked by this dashboard.
                              Model-generated findings cannot create buyer, conversion or revenue evidence.
                            </p>
                          </div>
                          <p className="mt-2 text-[11px] text-slate-500">
                            Research catalogue only; new external polling is not scheduled or activated.
                          </p>
                        </div>
                        <div className="mt-3 grid gap-2 md:grid-cols-2">
                          {streamMining.department_lanes.map((lane) => (
                            <div key={lane.stream} className="rounded-xl border border-white/10 bg-white/[0.025] p-3">
                              <div className="flex flex-wrap justify-between gap-2 text-xs font-medium text-white">
                                <span>{lane.stream.replaceAll("_", " ")}</span>
                                <span className={lane.status === "FRESH" || lane.status === "OBSERVED" ? "text-cyan-200" : "text-amber-200"}>
                                  {lane.status.replaceAll("_", " ")}
                                </span>
                              </div>
                              <p className="mt-2 text-xs text-slate-300">
                                Owner: {lane.department.replaceAll("_", " ")}
                              </p>
                              <p className="mt-1 text-xs text-slate-400">
                                {lane.next_internal_action.replaceAll("_", " ")}
                              </p>
                              <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-400">
                                {Object.entries(lane.counts).slice(0, 4).map(([key, value]) => (
                                  <span key={key}>{key.replaceAll("_", " ")}: {value}</span>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                        <p className="mt-3 text-[11px] text-slate-500">
                          Same source records may appear in several desks; counts are not additive.
                          This panel is read-only and does not dispatch work.
                        </p>
                      </>
                    ) : (
                      <p className="mt-3 text-xs text-slate-400">Existing source-stream mining waits for the paired backend release.</p>
                    )}
                  </div>
                  <div className="mt-5 rounded-2xl border border-cyan-300/15 bg-[#08131d] p-5">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="eyebrow">Predictive Cloud · Evidence reasoning pathways</p>
                        <h3 className="mt-1 text-lg font-semibold text-white">Source → hypothesis → economics → learning</h3>
                        <p className="mt-2 text-xs leading-5 text-slate-400">
                          Typed evidence links, not a trained neural network. Every blocked connection
                          identifies a fact our teams must independently verify.
                        </p>
                      </div>
                      <span className="text-xs text-cyan-200">
                        {show(evidencePathways?.status, "NOT CONNECTED").replaceAll("_", " ")}
                      </span>
                    </div>
                    {evidencePathways?.status === "EVIDENCE_PATHWAY_REVIEW_READY" ? (
                      <>
                        <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-300">
                          <span>Observed candidate records: {evidencePathways.candidate_count ?? "Unknown"}</span>
                          <span>Complete Quant packets: {evidencePathways.quant_complete_count ?? "Unknown"}</span>
                          <span>Contradictory records: {evidencePathways.candidates_with_contradictions ?? "Unknown"}</span>
                        </div>
                        <div className="mt-3 grid gap-2 lg:grid-cols-2">
                          {evidencePathways.research_shortlist.slice(0, 4).map((item) => (
                            <div key={item.opportunity_ref} className="rounded-xl border border-white/10 bg-white/[0.025] p-3">
                              <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-semibold text-white">
                                <span>{item.niche || "Unclassified market research"}</span>
                                <span className="text-amber-200">Evidence hold</span>
                              </div>
                              <p className="mt-2 text-xs text-slate-300">
                                Next missing fact: {show(item.first_unverified_requirement, "Review").replaceAll("_", " ")}
                              </p>
                              <p className="mt-1 text-xs text-slate-400">
                                Owner: {item.next_owner.replaceAll("_", " ")} ·
                                Missing Quant factors: {item.missing_quant_factor_count}
                              </p>
                              <div className="mt-2 flex flex-wrap gap-1">
                                {item.pathway_nodes.map((node) => (
                                  <span key={node.id} className={node.state === "EVIDENCE_HOLD"
                                    ? "rounded-md border border-amber-300/15 px-2 py-1 text-[10px] text-amber-200"
                                    : "rounded-md border border-cyan-300/15 px-2 py-1 text-[10px] text-cyan-200"}>
                                    {node.stage.replaceAll("_", " ")}
                                  </span>
                                ))}
                              </div>
                              {item.contradictions_to_investigate.length > 0 && (
                                <p className="mt-2 text-[11px] text-amber-200">
                                  Disputed evidence: {item.contradictions_to_investigate.join(", ").replaceAll("_", " ")}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                        <div className="mt-3 rounded-xl border border-amber-200/15 bg-white/[0.025] p-3">
                          <p className="text-sm font-semibold text-white">First-party commercial evidence handoff</p>
                          <p className="mt-1 text-xs text-slate-300">
                            {show(commercialEvidence?.status, "NOT CONNECTED").replaceAll("_", " ")}
                          </p>
                          {commercialEvidence?.request ? (
                            <>
                              <p className="mt-2 text-xs text-slate-300">
                                Priority: {commercialEvidence.request.niche || "Unclassified"} ·
                                {commercialEvidence.request.first_missing_evidence.replaceAll("_", " ")}
                              </p>
                              <p className="mt-1 text-xs text-slate-400">
                                Required proof: {commercialEvidence.request.required_authoritative_source.replaceAll("_", " ")}.
                                Outstanding Quant factors: {commercialEvidence.request.quant_gaps.length}.
                              </p>
                              <p className="mt-1 text-[11px] text-slate-500">
                                This prepares a review for Business Development only. No buyer checked,
                                no contact sent, no economics estimated and no prediction registered.
                              </p>
                            </>
                          ) : (
                            <p className="mt-2 text-xs text-amber-200">
                              {show(commercialEvidence?.reason_code, "No verified current handoff").replaceAll("_", " ")}
                            </p>
                          )}
                        </div>
                        <p className="mt-3 text-[11px] text-slate-500">
                          This is an internal evidence-join review. It does not infer a buyer, estimate
                          commercial probability, execute outreach, train model weights or book revenue.
                        </p>
                      </>
                    ) : (
                      <p className="mt-3 text-xs text-amber-200">
                        {show(evidencePathways?.reason_code, "Waiting for trusted matching source snapshots").replaceAll("_", " ")}
                      </p>
                    )}
                  </div>
                  <div className="mt-5 rounded-2xl border border-cyan-300/15 bg-[#08131d] p-5">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="eyebrow">Predictive Cloud + Predictive Revenue</p>
                        <h3 className="mt-1 text-lg font-semibold text-white">
                          Formula and calibration evidence health
                        </h3>
                        <p className="mt-2 text-xs leading-5 text-slate-400">
                          Formula installed does not mean commercial predictions are ready.
                          Old opportunity inputs and unknown outcomes cannot become a live revenue forecast.
                        </p>
                      </div>
                      <span className="rounded-lg border border-cyan-300/20 px-3 py-1 text-xs text-cyan-100">
                        {show(formulaEvidence?.status, "NOT CONNECTED").replaceAll("_", " ")}
                      </span>
                    </div>
                    {formulaEvidence ? (
                      <>
                        <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-slate-300 lg:grid-cols-4">
                          <span>Cloud snapshot: {show(formulaEvidence.source_status?.cloud_formula).replaceAll("_", " ")}</span>
                          <span>Revenue distribution: {show(formulaEvidence.source_status?.revenue_distribution).replaceAll("_", " ")}</span>
                          <span>Prediction ready: {formulaEvidence.cloud_prediction_ready === null ? "Unknown" : formulaEvidence.cloud_prediction_ready ? "Yes" : "No"}</span>
                          <span>Fresh opportunities: {formulaEvidence.fresh_opportunity_count ?? "Unknown"}</span>
                        </div>
                        {formulaEvidence.blockers.length > 0 ? (
                          <div className="mt-4">
                            <p className="text-xs font-semibold text-amber-200">Evidence to restore</p>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {formulaEvidence.blockers.slice(0, 10).map((blocker) => (
                                <span key={blocker} className="rounded-md border border-white/10 px-2 py-1 text-[11px] text-slate-300">
                                  {blocker.replaceAll("_", " ")}
                                </span>
                              ))}
                            </div>
                          </div>
                        ) : null}
                        {formulaEvidence.missing_factor_counts ? (
                          <div className="mt-3 text-xs text-slate-400">
                            Missing funnel evidence: {Object.entries(formulaEvidence.missing_factor_counts)
                              .slice(0, 10).map(([factor, count]) => `${factor.replaceAll("_", " ")} (${count})`).join(" · ") || "None reported"}
                          </div>
                        ) : null}
                        <div className="mt-5 rounded-xl border border-white/10 bg-white/[0.025] p-4">
                          <div className="flex flex-wrap justify-between gap-2">
                            <h4 className="text-sm font-semibold text-white">
                              Quant → original conversion prediction
                            </h4>
                            <span className="text-xs text-slate-400">
                              Quant source: {show(formulaEvidence.source_status?.opportunity_quant, "Unknown").replaceAll("_", " ")}
                            </span>
                          </div>
                          <div className="mt-3 grid grid-cols-2 gap-3 text-xs text-slate-300 lg:grid-cols-3">
                            <span>Observed Quant candidates: {formulaEvidence.quant_original_prediction_readiness?.candidate_count ?? "Unknown"}</span>
                            <span>Complete Quant inputs: {formulaEvidence.quant_original_prediction_readiness?.available_quant_decision_count ?? "Unknown"}</span>
                            <span>Missing economics: {formulaEvidence.quant_original_prediction_readiness?.missing_quant_economics_count ?? "Unknown"}</span>
                          </div>
                          {formulaEvidence.quant_original_prediction_readiness ? (
                            <>
                              <p className="mt-3 text-xs font-medium text-amber-100">
                                Next: {formulaEvidence.quant_original_prediction_readiness.next_evidence_action.replaceAll("_", " ")}
                              </p>
                              <p className="mt-2 text-xs leading-5 text-slate-400">
                                Missing input evidence: {Object.entries(formulaEvidence.quant_original_prediction_readiness.missing_input_counts)
                                  .slice(0, 8).map(([factor, count]) => `${factor.replaceAll("_", " ")} (${count})`).join(" · ") || "None reported"}
                              </p>
                            </>
                          ) : (
                            <p className="mt-3 text-xs text-amber-100">A current validated Quant review is required.</p>
                          )}
                          <p className="mt-2 text-[11px] leading-5 text-slate-500">
                            Quant scores do not establish an original conversion forecast.
                            A timestamped canonical prediction receipt is required before learning from an outcome.
                          </p>
                        </div>
                        <div className="mt-5 rounded-xl border border-white/10 bg-white/[0.025] p-4">
                          <div className="flex flex-wrap justify-between gap-2">
                            <h4 className="text-sm font-semibold text-white">
                              Learning from verified commercial outcomes
                            </h4>
                            <span className="text-xs text-amber-200">
                              {show(formulaEvidence.verified_outcome_learning?.status, "NOT AVAILABLE").replaceAll("_", " ")}
                            </span>
                          </div>
                          <div className="mt-3 grid grid-cols-2 gap-3 text-xs text-slate-300 lg:grid-cols-4">
                            <span>Verified reviews: {formulaEvidence.verified_outcome_learning?.verified_review_count ?? "Unknown"}</span>
                            <span>Matched outcomes: {formulaEvidence.verified_outcome_learning?.verified_outcome_feedback_count ?? "Unknown"}</span>
                            <span>Time-safe holdout: {formulaEvidence.verified_outcome_learning?.temporal_holdout_count ?? "Unknown"}</span>
                            <span>Model vs baseline: {formulaEvidence.verified_outcome_learning?.candidate_beats_baseline === null ||
                              formulaEvidence.verified_outcome_learning?.candidate_beats_baseline === undefined
                              ? "Not established"
                              : formulaEvidence.verified_outcome_learning.candidate_beats_baseline ? "Improved" : "Not improved"}</span>
                          </div>
                          <p className="mt-3 text-xs font-medium text-amber-100">
                            Next: {show(formulaEvidence.verified_outcome_learning?.next_evidence_action, "Refresh validated outcomes").replaceAll("_", " ")}
                          </p>
                          <p className="mt-2 text-[11px] leading-5 text-slate-500">
                            Reuses Economic Memory and time-safe Quant Brier comparison.
                            Empty or unverified cohorts are not treated as calibrated performance.
                          </p>
                        </div>
                        <p className="mt-3 text-[11px] text-slate-500">
                          Diagnostics only · no forecast generated here · no model promotion, outbound or payments.
                        </p>
                      </>
                    ) : (
                      <p className="mt-3 text-xs text-slate-400">Formula evidence view awaits the paired backend release.</p>
                    )}
                  </div>
                  <div className="mt-5 rounded-2xl border border-amber-300/20 bg-[#171713] p-5">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div>
                        <p className="eyebrow">Predictive Revenue · First commercial bottleneck</p>
                        <h3 className="mt-2 text-lg font-semibold text-white">
                          Verify an actual paying buyer and their buy-box
                        </h3>
                        <p className="mt-2 text-sm text-slate-300">
                          Existing buyer counts are aggregate evidence, not proof that one customer has
                          a verified market, volume, price and acceptance path.
                        </p>
                      </div>
                      <span className="rounded-lg border border-amber-300/25 px-3 py-1 text-xs text-amber-100">
                        {show(buyerCapacity?.status, "NOT CONNECTED").replaceAll("_", " ")}
                      </span>
                    </div>
                    {buyerCapacity ? (
                      <>
                        <div className="mt-4 flex flex-wrap gap-5 text-xs text-slate-300">
                          <span>Buyer records observed: {buyerCapacity.buyers_seen ?? "Unknown"}</span>
                          <span>Same-record preparation candidates: {buyerCapacity.same_record_preparation_count ?? "Unknown"}</span>
                          <span>Buyer-specific buy-box proof: {buyerCapacity.verified_specific_buybox_count ?? "Unknown"}</span>
                          <span>Owner: {show(buyerCapacity.owner).replaceAll("_", " ")}</span>
                        </div>
                        <p className="mt-4 text-sm font-semibold text-amber-100">
                          Next evidence: {show(buyerCapacity.first_missing_evidence, "Refresh trusted evidence").replaceAll("_", " ")}
                        </p>
                        <div className="mt-4 grid gap-2 md:grid-cols-2">
                          {buyerCapacity.evidence_checklist.map((stage) => (
                            <div key={stage.evidence_key} className="rounded-xl border border-white/10 bg-white/[0.025] p-3">
                              <div className="flex justify-between gap-3 text-xs">
                                <span className="font-semibold text-slate-100">
                                  {stage.action_code.replaceAll("_", " ")}
                                </span>
                                <span className="shrink-0 text-slate-400">Aggregate: {stage.aggregate_observed_count}</span>
                              </div>
                              <p className="mt-2 text-xs leading-5 text-slate-300">{stage.requirement}</p>
                              <p className="mt-2 text-[11px] text-amber-200">
                                {stage.status.replaceAll("_", " ")}
                              </p>
                            </div>
                          ))}
                        </div>
                        <p className="mt-3 text-xs text-slate-500">
                          No buy-box verified, payout quotation, lead delivery or email send is approved
                          by this evidence review. No work has been dispatched.
                        </p>
                      </>
                    ) : (
                      <p className="mt-4 text-sm text-amber-100">
                        The buyer-capacity evidence checklist will appear when the paired backend is released.
                      </p>
                    )}
                  </div>
                  <div className="mt-5 grid gap-3 lg:grid-cols-3">
                    {nextPriorities.length ? nextPriorities.map((task, index) => (
                      <article key={task.task_id} className="rounded-2xl border border-cyan-300/15 bg-[#0a1820] p-5">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-semibold uppercase tracking-widest text-cyan-200">
                            Priority {index + 1}
                          </span>
                          <span className="text-[11px] text-slate-400">{task.department.replaceAll("_", " ")}</span>
                        </div>
                        <h3 className="mt-3 break-words text-base font-semibold text-white">
                          {task.recommended_action.replaceAll("_", " ")}
                        </h3>
                        {task.company_name ? (
                          <p className="mt-1 text-xs text-slate-400">{task.company_name}</p>
                        ) : null}
                        <p className="mt-3 text-sm leading-6 text-slate-300">{task.reason ?? task.hold_or_gate_reason}</p>
                        <div className="mt-4 flex flex-wrap gap-2 text-[11px]">
                          <span className="rounded-md border border-white/15 px-2 py-1 text-slate-200">
                            {task.lane.replaceAll("_", " ")}
                          </span>
                          <span className="rounded-md border border-white/10 px-2 py-1 text-slate-400">
                            {task.source_freshness.replaceAll("_", " ")}
                          </span>
                        </div>
                        <p className="mt-4 text-xs text-slate-500">
                          {task.can_prepare_internal_work
                            ? "Eligible for internal preparation; not authorised to execute."
                            : task.founder_gate_required
                              ? "Explicit founder decision required."
                              : "Review, external evidence or an existing governor is required."}
                        </p>
                      </article>
                    )) : (
                      <p className="col-span-full rounded-xl border border-white/10 p-5 text-sm text-slate-400">
                        No trusted current decisions available. Missing evidence is not treated as a task completed.
                      </p>
                    )}
                  </div>
                  <div className="mt-6 rounded-2xl border border-white/10 bg-[#071620] p-5">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="eyebrow">Existing department queue · Handoff</p>
                        <h3 className="mt-1 text-lg font-semibold text-white">Internal work prepared for review</h3>
                        <p className="mt-2 max-w-2xl text-xs leading-5 text-slate-400">
                          Read-only review packets, not queue submissions. Existing work is checked before suggesting
                          any new task, and completed work is not counted as commercial revenue.
                        </p>
                      </div>
                      <span className="rounded-lg border border-white/10 px-3 py-1 text-xs text-slate-300">
                        {show(departmentHandoff?.status, "NOT AVAILABLE").replaceAll("_", " ")}
                      </span>
                    </div>
                    {departmentHandoff ? (
                      <>
                        <div className="mt-4 flex flex-wrap gap-4 text-xs text-slate-300">
                          <span>Review packets: {int(departmentHandoff.candidate_count)}</span>
                          <span>Not yet queued: {int(departmentHandoff.ready_for_review_count)}</span>
                          <span>Existing work: {int(departmentHandoff.existing_work_count)}</span>
                          <span>Held: {int(departmentHandoff.held_count)}</span>
                        </div>
                        <div className="mt-4 grid gap-2 md:grid-cols-2">
                          {departmentHandoff.candidates.map((candidate) => (
                            <div key={candidate.task_id ?? candidate.source_action}
                              className="rounded-lg border border-white/10 bg-white/[0.025] p-3">
                              <p className="text-sm font-medium text-white">
                                {show(candidate.source_action).replaceAll("_", " ")}
                              </p>
                              <p className="mt-1 text-xs text-slate-400">
                                {show(candidate.owner).replaceAll("_", " ")} ·
                                {show(candidate.current_work_status, "EVIDENCE HOLD").replaceAll("_", " ")}
                              </p>
                              <p className="mt-1 text-[11px] text-slate-500">
                                {show(candidate.queue_observation_reason, "Review required").replaceAll("_", " ")}
                              </p>
                            </div>
                          ))}
                        </div>
                        <p className="mt-3 text-[11px] text-slate-500">
                          No execution bus lease, email send, paid API call, financial movement or task submission
                          is authorised by these review packets.
                        </p>
                      </>
                    ) : (
                      <p className="mt-4 text-xs text-amber-200">
                        Department handoff is unavailable until the matching backend release is deployed.
                      </p>
                    )}
                  </div>
                  <p className="mt-4 text-xs leading-5 text-slate-500">
                    Buyer evidence: {show(decision.sources?.buyer_next_best_action)} ·
                    Executive observer: {show(decision.sources?.astra_executive_observer)} ·
                    Revenue snapshot: {show(decision.sources?.revenue_pulse).replaceAll("_", " ")}.
                    No outbound, financial activation or database write is authorised here.
                  </p>
                </>
              ) : (
                <p className="mt-4 text-sm text-amber-200">
                  Decision control is not yet exposed by the running Founder Dashboard API.
                  Existing operations remain unchanged.
                </p>
              )}
            </section>
            <section className="panel mt-7">
              <div className="flex flex-col justify-between gap-3 md:flex-row md:items-end">
                <div>
                  <p className="eyebrow">Revenue lane truth</p>
                  <h2 className="mt-1 text-2xl font-semibold text-white">
                    What is actually live, ready, gated or blocked
                  </h2>
                </div>
                <p className="text-xs text-slate-500">
                  Founder gates: {operationalTruth?.summary?.founder_gate_count ?? 0}
                </p>
              </div>
              <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {operationalLanes.map((lane) => (
                  <div
                    key={lane.key}
                    className={["rounded-2xl border p-4", operationalLaneTone(lane.state)].join(" ")}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-sm font-semibold capitalize text-white">
                        {lane.key.replaceAll("_", " ")}
                      </p>
                      <span className="text-[10px] font-semibold uppercase tracking-[0.12em]">
                        {lane.state}
                      </span>
                    </div>
                    <p className="mt-3 text-xs leading-5 text-slate-300">
                      {lane.detail}
                    </p>
                    {lane.blocker ? (
                      <p className="mt-3 text-[11px] text-slate-400">
                        Blocker: {lane.blocker.replaceAll("_", " ")}
                      </p>
                    ) : null}
                    {lane.next_action ? (
                      <p className="mt-2 text-[11px] leading-5 text-white/80">
                        Next: {lane.next_action}
                      </p>
                    ) : null}
                  </div>
                ))}
                {!operationalLanes.length ? (
                  <div className="rounded-2xl border border-white/10 bg-white/[0.025] p-4 text-xs text-slate-400">
                    Operational truth API unavailable. No state is inferred.
                  </div>
                ) : null}
              </div>
            </section>

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

                <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-3">
                  <Evidence
                    label="Radar candidates"
                    value={int(opportunityRadar?.radar_candidate_count)}
                  />
                  <Evidence
                    label="Researched"
                    value={int(opportunityRadar?.research_candidate_count)}
                  />
                  <Evidence
                    label="Normalized"
                    value={int(
                      opportunityRadar
                        ?.candidates_with_any_normalized_score,
                    )}
                  />
                  <Evidence
                    label="Factory ready"
                    value={int(opportunityRadar?.factory_ready_count)}
                  />
                  <Evidence
                    label="Quant ready"
                    value={int(opportunityRadar?.quant_ready_count)}
                  />
                  <Evidence
                    label="AI plans"
                    value={int(opportunityRadar?.ai_plan_queued_count)}
                  />
                </div>

                <div className="mt-4 rounded-2xl border border-white/8 bg-white/[0.025] p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-xs uppercase tracking-[0.12em] text-slate-600">
                        Primary evidence gap
                      </p>
                      <p className="mt-1 text-sm font-semibold text-white">
                        {show(
                          opportunityRadar
                            ?.highest_priority_evidence_gap,
                        ).replaceAll("_", " ")}
                      </p>
                    </div>
                    <span className="text-xs font-semibold text-amber-200">
                      {int(opportunityRadar?.factory_blocked_count)} blocked
                    </span>
                  </div>

                  <div className="mt-3 space-y-1">
                    {opportunityBlockers.length ? (
                      opportunityBlockers.slice(0, 4).map(
                        ([blocker, count]) => (
                          <div
                            key={blocker}
                            className="flex justify-between gap-3 text-[11px]"
                          >
                            <span className="text-slate-500">
                              {blocker.replaceAll("_", " ")}
                            </span>
                            <span className="font-semibold text-slate-300">
                              {count}
                            </span>
                          </div>
                        ),
                      )
                    ) : (
                      <p className="text-xs text-slate-500">
                        No current Factory blocker observed.
                      </p>
                    )}
                  </div>

                  <p className="mt-3 border-t border-white/8 pt-3 text-[11px] text-slate-600">
                    Stage mix:{" "}
                    {Object.entries(
                      opportunityRadar?.stage_counts ?? {},
                    )
                      .map(([stage, count]) => `${stage} ${count}`)
                      .join(" · ") || "Unknown"}
                  </p>
                </div>

                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                  <Drill href="/opportunities" title="Search opportunities" />
                  <Drill href="/revenue" title="Organic revenue evidence" />
                  <Drill href="/competitors" title="Competitor gaps" />
                  <Drill href="/evidence" title="Evidence timeline" />
                  <Drill href="/founder/solar" title="UK Solar Intelligence" />
                  <Drill href="/founder/mail" title="Empire Mail" />
                </div>
              </section>
            </div>

            <section className="mt-5 grid gap-5 xl:grid-cols-[1.35fr_.65fr]">
              <div className="panel overflow-hidden">
                <div className="flex flex-col justify-between gap-3 md:flex-row md:items-end">
                  <div>
                    <p className="eyebrow">Competitive intelligence graph</p>
                    <h2 className="mt-1 text-xl font-semibold text-white">
                      Observed market overlap
                    </h2>
                    <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
                      Company-to-competitor edges come only from canonical
                      observed comparison/listing evidence. Buyer or commercial
                      intent is not inferred from graph proximity.
                    </p>
                  </div>
                  <div className="text-left md:text-right">
                    <p className="text-xs text-slate-600">
                      {int(competitorIntelligence?.canonical_signal_row_count)} canonical signals
                    </p>
                    <p className="mt-1 text-xs text-emerald-200">
                      {int(competitorIntelligence?.company_count)} observed companies
                    </p>
                  </div>
                </div>

                <div className="mt-5 grid gap-4 lg:grid-cols-[1.15fr_.85fr]">
                  <CompetitorGraph company={graphCompany} />
                  <div className="space-y-3">
                    {competitorCompanies.slice(0, 4).map((company) => (
                      <div
                        key={company.entity_id ?? company.company_name}
                        className="rounded-2xl border border-white/8 bg-white/[0.025] p-4 transition duration-300 hover:-translate-y-0.5 hover:border-cyan-300/25 hover:bg-cyan-300/[0.035]"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-white">
                              {show(company.company_name)}
                            </p>
                            <p className="mt-1 text-[11px] text-slate-500">
                              {int(company.competitor_count)} observed competitors
                            </p>
                          </div>
                          <span className="rounded-full border border-cyan-300/20 bg-cyan-300/[0.06] px-2.5 py-1 text-[10px] font-semibold text-cyan-100">
                            {typeof company.confidence === "number"
                              ? Math.round(company.confidence * 100) + "%"
                              : "Unknown"}
                          </span>
                        </div>
                        <p className="mt-3 text-[11px] leading-5 text-slate-500">
                          {(company.competitors ?? [])
                            .slice(0, 4)
                            .map(formatGraphLabel)
                            .join(" · ") || "No observed competitor edges"}
                        </p>
                      </div>
                    ))}
                    {!competitorCompanies.length ? (
                      <div className="rounded-2xl border border-white/8 bg-white/[0.025] p-4 text-xs text-slate-500">
                        No canonical competitor graph observations available.
                      </div>
                    ) : null}
                  </div>
                </div>

                <p className="mt-4 border-t border-white/8 pt-4 text-[11px] leading-5 text-slate-600">
                  Latest canonical observation: {show(competitorIntelligence?.latest_observed_at)} ·
                  execution authority {show(competitorIntelligence?.execution_authority, "none")}.
                </p>
              </div>

              <div className="panel relative overflow-hidden [perspective:1100px]">
                <div className="pointer-events-none absolute -right-20 -top-20 size-64 rounded-full bg-cyan-400/[0.08] blur-3xl" />
                <div className="pointer-events-none absolute -bottom-24 -left-16 size-64 rounded-full bg-emerald-400/[0.06] blur-3xl" />
                <div className="relative transition duration-500 [transform-style:preserve-3d] hover:[transform:rotateX(1.5deg)_rotateY(-2deg)_translateZ(6px)]">
                  <p className="eyebrow">Storm Leads Multiplier</p>
                  <h2 className="mt-1 text-xl font-semibold text-white">
                    Physical demand acceleration
                  </h2>
                  <div className="mt-6 rounded-3xl border border-cyan-300/20 bg-gradient-to-br from-cyan-300/[0.08] via-white/[0.025] to-emerald-300/[0.05] p-5 shadow-[0_25px_70px_rgba(0,0,0,.22)]">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-200/70">
                      Modeled max multiplier
                    </p>
                    <p className="mt-2 text-5xl font-semibold tracking-[-0.05em] text-white">
                      {stormMultiplier}
                    </p>
                    <p className="mt-3 text-xs leading-5 text-slate-400">
                      Modeled priority effect only. It does not equal revenue,
                      delivered leads or buyer demand.
                    </p>
                  </div>

                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
                    <Evidence
                      label="Physical observations"
                      value={int(spatialStatus?.physical_observations)}
                    />
                    <Evidence
                      label="Storm observed"
                      value={truth(spatialStatus?.source_state?.storm_exposure_observed)}
                    />
                  </div>

                  <div className="mt-4 rounded-2xl border border-white/8 bg-white/[0.025] p-4">
                    <p className="text-sm font-semibold text-white">
                      {show(stormObservation?.market)}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      {show(stormObservation?.phenomenon).replaceAll("_", " ")}
                    </p>
                    <p className="mt-3 text-[11px] leading-5 text-slate-400">
                      {show(stormObservation?.source)}
                    </p>
                    <p className="mt-2 break-all text-[10px] leading-5 text-cyan-200/70">
                      {show(stormObservation?.evidence_ref)}
                    </p>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2">
                    <TruthPill
                      label="Preview only"
                      value={spatialStatus?.preview_only === true}
                    />
                    <TruthPill
                      label="Execution allowed"
                      value={spatialStatus?.execution_allowed === true}
                    />
                    <TruthPill
                      label="Revenue mutation"
                      value={spatialStatus?.revenue_mutation === true}
                    />
                  </div>
                </div>
              </div>
            </section>

            <section className="panel mt-5">
              <div className="flex flex-col justify-between gap-3 md:flex-row md:items-end">
                <div>
                  <p className="eyebrow">Daily Results Hub</p>
                  <h2 className="mt-1 text-xl font-semibold text-white">
                    One operating result for everything
                  </h2>
                </div>
                <p className="text-xs text-slate-600">
                  {show(daily?.date)} · generated {show(daily?.generated_at)}
                </p>
              </div>
              <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
                <Evidence
                  label="Omega"
                  value={int(dailyFunnel?.omega_observations)}
                />
                <Evidence
                  label="Approved buyers"
                  value={int(dailyFunnel?.approved_buyers)}
                />
                <Evidence
                  label="Outbound sent"
                  value={int(dailyFunnel?.outbound_sent)}
                />
                <Evidence
                  label="Buyer conversations"
                  value={int(dailyFunnel?.commercial_buyer_replies)}
                />
                <Evidence
                  label="Verified payments"
                  value={int(dailyFunnel?.verified_payments)}
                />
                <Evidence
                  label="Revenue events"
                  value={int(dailyFunnel?.recognized_revenue_events)}
                />
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                <Evidence
                  label="Buyer rows"
                  value={int(daily?.buyer_capacity?.buyers_seen)}
                />
                <Evidence
                  label="Status active"
                  value={int(daily?.buyer_capacity?.status_active)}
                />
                <Evidence
                  label="Terms verified"
                  value={int(daily?.buyer_capacity?.terms_verified)}
                />
                <Evidence
                  label="Capacity verified"
                  value={int(daily?.buyer_capacity?.capacity_verified)}
                />
                <Evidence
                  label="Delivery verified"
                  value={int(daily?.buyer_capacity?.delivery_verified)}
                />
                <Evidence
                  label="Fully activated"
                  value={int(daily?.buyer_capacity?.fully_activated)}
                />
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                <Evidence
                  label="Recovery ready"
                  value={int(daily?.conversation_recovery?.recoverable)}
                />
                <Evidence
                  label="Follow-up eligible"
                  value={int(daily?.conversation_recovery?.followup_eligible_delivered)}
                />
                <Evidence
                  label="Suppressed after delivery"
                  value={int(daily?.conversation_recovery?.suppressed_after_delivery)}
                />
                <Evidence
                  label="Follow-ups due"
                  value={int(daily?.conversation_recovery?.due_now)}
                />
                <Evidence
                  label="Due within 24h"
                  value={int(daily?.conversation_recovery?.due_within_24h)}
                />
                <Evidence
                  label="Next due (hours)"
                  value={show(daily?.conversation_recovery?.next_due_in_hours)}
                />
                <Evidence
                  label="Legacy subjects"
                  value={int(daily?.conversation_recovery?.legacy_generic_subjects)}
                />
                <Evidence
                  label="Delivery coverage gap"
                  value={int(daily?.conversation_recovery?.pulse_delivery_gap)}
                />
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                <Evidence
                  label="Pulse state"
                  value={show(daily?.revenue_pulse?.pulse_state)}
                />
                <Evidence
                  label="24h acquisitions"
                  value={int(daily?.revenue_pulse?.current_window?.acquisitions)}
                />
                <Evidence
                  label="24h qualified"
                  value={int(daily?.revenue_pulse?.current_window?.qualified)}
                />
                <Evidence
                  label="24h delivered"
                  value={int(daily?.revenue_pulse?.current_window?.delivered_outreach)}
                />
                <Evidence
                  label="24h replies"
                  value={int(daily?.revenue_pulse?.current_window?.commercial_replies)}
                />
                <Evidence
                  label="Control components"
                  value={int(daily?.control_fabric?.component_count)}
                />
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Evidence
                  label="Volumetric observations"
                  value={int(
                    daily?.revenue_pulse?.spatial_physical_pulse
                      ?.volumetric_observations,
                  )}
                />
                <Evidence
                  label="Physical observations"
                  value={int(
                    daily?.revenue_pulse?.spatial_physical_pulse
                      ?.physical_observations,
                  )}
                />
                <Evidence
                  label="Modeled physical opportunities"
                  value={int(
                    daily?.revenue_pulse?.spatial_physical_pulse
                      ?.modeled_opportunities,
                  )}
                />
                <Evidence
                  label="Max modeled priority boost"
                  value={show(
                    daily?.revenue_pulse?.spatial_physical_pulse
                      ?.max_combined_priority_boost,
                  )}
                />
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <Evidence
                  label="Intent observations"
                  value={int(daily?.intent_and_pain?.observations)}
                />
                <Evidence
                  label="High intent"
                  value={int(daily?.intent_and_pain?.high_intent)}
                />
                <Evidence
                  label="Reddit source"
                  value={truth(daily?.intent_and_pain?.source_status?.reddit?.ok)}
                />
                <Evidence
                  label="LinkedIn source"
                  value={truth(daily?.intent_and_pain?.source_status?.linkedin?.ok)}
                />
                <Evidence
                  label="Coder running"
                  value={int(daily?.coder?.running)}
                />
                <Evidence
                  label="Commercial blocker"
                  value={show(daily?.headline?.commercial_blocker)}
                />
              </div>
              <div className="mt-4 flex flex-col justify-between gap-3 border-t border-white/8 pt-4 md:flex-row md:items-center">
                <p className="text-xs leading-5 text-slate-500">
                  Unknown stays unknown. Sends, scores, forecasts and payment
                  requests are never counted as revenue.
                </p>
                <Link
                  href="/founder/results"
                  className="text-xs font-semibold text-emerald-300 hover:text-emerald-200"
                >
                  Open daily history →
                </Link>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                <Evidence
                  label="AEO assets"
                  value={int(daily?.search_and_seo?.aeo_asset_count)}
                />
                <Evidence
                  label="Legal sources"
                  value={int(daily?.legal_intelligence?.source_count_ready) + " / " + int(daily?.legal_intelligence?.source_count_total)}
                />
                <Evidence
                  label="Deal Room bridge"
                  value={truth(daily?.deal_room?.bridge_ready)}
                />
                <Evidence
                  label="Trust ready"
                  value={truth(daily?.security?.trust_ready)}
                />
                <Evidence
                  label="RLS disabled"
                  value={int(daily?.security?.findings?.rls_disabled_in_public)}
                />
                <Evidence
                  label="Privileged tables"
                  value={int(daily?.security?.rls_classes?.privileged_operator)}
                />
                <Evidence
                  label="Incidents"
                  value={int(daily?.reliability?.incident_count)}
                />
              </div>
            </section>

            <div className="mt-5 grid gap-5 xl:grid-cols-[.8fr_1.2fr]">
              <section className="panel">
                <p className="eyebrow">System control</p>
                <h2 className="mt-1 text-xl font-semibold text-white">
                  Sentinel · Incident Manager
                </h2>
                <div className="mt-5 grid grid-cols-2 gap-3">
                  <Evidence
                    label="Technical health"
                    value={truth(ops?.healthy)}
                  />
                  <Evidence
                    label="Incidents"
                    value={int(ops?.incident_manager?.incident_count)}
                  />
                  <Evidence
                    label="Safe repairs queued"
                    value={int(repairPlan.length)}
                  />
                  <Evidence
                    label="Commercial blocker"
                    value={show(ops?.business_blocker)}
                  />
                </div>
                <div className="mt-5 rounded-xl border border-white/8 bg-white/[0.025] p-4">
                  <p className="text-sm font-semibold text-slate-200">
                    Lead-to-revenue evidence
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    OBSERVE only · verified signals, not projected revenue
                  </p>
                  <div className="mt-3 grid grid-cols-2 gap-3">
                    <Evidence
                      label="Readiness"
                      value={show(ops?.leadgen_truth?.status)}
                    />
                    <Evidence
                      label="Open prerequisites"
                      value={int(ops?.leadgen_truth?.readiness_blocker_count)}
                    />
                    <Evidence
                      label="Evidence conflicts"
                      value={int(ops?.leadgen_truth?.integrity_finding_count)}
                    />
                    <Evidence
                      label="Measured outcome"
                      value={truth(ops?.leadgen_truth?.campaign_outcome_proved)}
                    />
                    <Evidence
                      label="Founder reviews waiting"
                      value={int(ops?.leadgen_truth?.gtm_founder_reviews_pending)}
                    />
                    <Evidence
                      label="Failed user workers"
                      value={int(ops?.user_worker_health?.failed_worker_count)}
                    />
                    <Evidence
                      label="Worker inspection"
                      value={show(ops?.user_worker_health?.status)}
                    />
                  </div>
                  {(ops?.user_worker_health?.failed_workers?.length ?? 0) > 0 ? (
                    <div className="mt-3 space-y-1 border-t border-white/8 pt-3">
                      {(ops?.user_worker_health?.failed_workers ?? []).slice(0, 6).map((unit) => (
                        <p key={unit} className="text-xs text-rose-200">
                          {unit}
                        </p>
                      ))}
                    </div>
                  ) : null}
                  {(ops?.leadgen_truth?.integrity_findings?.length ||
                    ops?.leadgen_truth?.readiness_blockers?.length) ? (
                    <div className="mt-3 space-y-1 border-t border-white/8 pt-3">
                      {[
                        ...(ops?.leadgen_truth?.integrity_findings ?? []),
                        ...(ops?.leadgen_truth?.readiness_blockers ?? []),
                      ].slice(0, 6).map((code) => (
                        <p key={code} className="text-xs text-amber-200">
                          {code.toLowerCase().replaceAll("_", " ")}
                        </p>
                      ))}
                    </div>
                  ) : null}
                </div>
                <div className="mt-5 space-y-2 border-t border-white/8 pt-4">
                  {incidents.length ? (
                    incidents.slice(0, 4).map((incident, index) => (
                      <div
                        key={String(incident.incident_key ?? index)}
                        className="rounded-xl border border-white/8 bg-white/[0.025] p-3"
                      >
                        <p className="text-xs font-semibold text-slate-200">
                          {show(incident.label).replaceAll("_", " ")}
                        </p>
                        <p className="mt-1 text-[11px] text-slate-500">
                          {show(incident.playbook).replaceAll("_", " ")}
                        </p>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-slate-500">
                      No active incident diagnosis observed.
                    </p>
                  )}
                </div>
              </section>

              <section className="panel">
                <div className="flex flex-col justify-between gap-3 md:flex-row md:items-end">
                  <div>
                    <p className="eyebrow">Intelligence Fabric</p>
                    <h2 className="mt-1 text-xl font-semibold text-white">
                      Intelligence Nodes
                    </h2>
                  </div>
                  <p className="text-xs text-slate-600">
                    {int(nodesResult.data?.node_count)} catalogued nodes
                  </p>
                </div>
                <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {intelligenceNodes.map((node) => (
                    <div
                      key={node.key}
                      className="rounded-2xl border border-white/8 bg-white/[0.025] p-4"
                    >
                      <p className="text-sm font-semibold text-white">
                        {node.name}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {node.market.replaceAll("_", " ")}
                      </p>
                      <p className="mt-3 text-[11px] text-emerald-200">
                        {typeof node.runtime_evidence?.observation_count ===
                        "number"
                          ? String(node.runtime_evidence.observation_count) +
                            " current observation(s)"
                          : node.runtime_evidence?.current_source_match
                            ? "Current source evidence observed"
                            : node.runtime_evidence?.evidence_state ===
                                "no_real_3d_evidence_observed"
                              ? "No real 3D evidence observed"
                              : "No current-source evidence in snapshot"}
                      </p>
                      <p className="mt-2 text-[11px] leading-5 text-slate-600">
                        {node.products.slice(0, 3).join(" · ")}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            </div>

            <section className="panel mt-5">
              <div className="flex flex-col justify-between gap-3 md:flex-row md:items-end">
                <div>
                  <p className="eyebrow">Commercial product layer</p>
                  <h2 className="mt-1 text-xl font-semibold text-white">
                    Sellable Intelligence Data Products
                  </h2>
                </div>
                <p className="text-xs text-slate-600">
                  Pricing remains unknown until verified terms exist.
                </p>
              </div>
              <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {dataProducts.map((product) => (
                  <div
                    key={product.key}
                    className="rounded-2xl border border-white/8 bg-white/[0.025] p-4"
                  >
                    <p className="text-sm font-semibold text-white">
                      {product.name}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      {product.category.replaceAll("_", " ")}
                    </p>
                    <p className="mt-3 text-[11px] text-slate-400">
                      {product.delivery_modes.join(" · ")}
                    </p>
                    <p className="mt-2 text-[11px] text-emerald-200">
                      {product.commercial_model.replaceAll("_", " ")}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            <section className="panel mt-5">
              <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
                <div>
                  <p className="eyebrow">Recovery & salvage control</p>
                  <h2 className="mt-1 text-xl font-semibold text-white">
                    Half-built · gated · reusable assets
                  </h2>
                </div>
                <p className="max-w-xl text-xs leading-5 text-slate-600">
                  Historical assets are recovery memory, not production truth.
                  Promote only after canonical integration, evidence and tests.
                </p>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
                <Evidence
                  label="Recovery products"
                  value={int(recovery?.summary?.product_count)}
                />
                <Evidence
                  label="Active build"
                  value={int(recoveryByState.ACTIVE_BUILD)}
                />
                <Evidence
                  label="Salvage candidates"
                  value={int(recoveryByState.SALVAGE_CANDIDATE)}
                />
                <Evidence
                  label="Rebuild later"
                  value={int(recoveryByState.REBUILD_LATER)}
                />
                <Evidence
                  label="Founder gated"
                  value={int(recoveryByState.FOUNDER_GATE)}
                />
                <Evidence
                  label="Pricing observed"
                  value={int(recovery?.summary?.pricing_observed_count)}
                />
              </div>

              <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {recoveryProducts.map((product) => (
                  <div
                    key={product.key ?? product.name}
                    className="rounded-2xl border border-white/8 bg-white/[0.025] p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-white">
                          {show(product.name)}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          {show(product.family).replaceAll("_", " ")}
                        </p>
                      </div>
                      <span
                        className={[
                          "rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.08em]",
                          recoveryTone(product.state),
                        ].join(" ")}
                      >
                        {show(product.state).replaceAll("_", " ")}
                      </span>
                    </div>
                    <p className="mt-4 text-[11px] leading-5 text-slate-400">
                      {(product.surfaces ?? []).slice(0, 4).join(" · ") ||
                        "No canonical surfaces listed"}
                    </p>
                    <p className="mt-3 text-[11px] leading-5 text-emerald-200">
                      {(product.revenue_models ?? []).join(" · ") ||
                        "Revenue model unknown"}
                    </p>
                    {product.notes ? (
                      <p className="mt-3 border-t border-white/8 pt-3 text-[11px] leading-5 text-slate-600">
                        {product.notes}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>

              <div className="mt-4 border-t border-white/8 pt-4">
                <p className="text-xs leading-5 text-slate-500">
                  Protected recovery paths stay untouched. Legacy SQLite,
                  synthetic commercial truth and retired Solana/USDC payment
                  paths are not restored into production.
                </p>
              </div>
            </section>

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


function formatGraphLabel(value: string | undefined) {
  const text = (value ?? "").replaceAll("-", " ").trim();
  if (!text) return "Unknown";
  return text.length > 24 ? text.slice(0, 23) + "…" : text;
}

function CompetitorGraph({
  company,
}: {
  company:
    | {
        company_name?: string;
        competitors?: string[];
        confidence?: number;
        evidence?: Array<{ source_ref?: string }>;
      }
    | undefined;
}) {
  const competitors = (company?.competitors ?? []).slice(0, 9);
  const width = 680;
  const height = 390;
  const cx = width / 2;
  const cy = height / 2;
  const radius = 145;
  const nodes = competitors.map((competitor, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(competitors.length, 1) - Math.PI / 2;
    return {
      competitor,
      x: cx + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius,
    };
  });

  if (!company) {
    return (
      <div className="grid min-h-[360px] place-items-center rounded-3xl border border-white/8 bg-white/[0.02] text-sm text-slate-500">
        No canonical competitor graph available.
      </div>
    );
  }

  return (
    <div className="rounded-3xl border border-white/8 bg-[radial-gradient(circle_at_50%_45%,rgba(34,211,238,.09),transparent_38%),linear-gradient(145deg,rgba(255,255,255,.025),rgba(255,255,255,.01))] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,.04),0_30px_80px_rgba(0,0,0,.18)] [perspective:1200px]">
      <div className="transition duration-500 [transform-style:preserve-3d] hover:[transform:rotateX(1.5deg)_rotateY(1.5deg)_translateZ(8px)]">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`Observed competitor graph for ${show(company.company_name)}`}
          className="h-auto w-full"
        >
          <defs>
            <radialGradient id="graph-core" cx="35%" cy="30%" r="70%">
              <stop offset="0%" stopColor="#d9fbff" stopOpacity="0.95" />
              <stop offset="45%" stopColor="#22d3ee" stopOpacity="0.75" />
              <stop offset="100%" stopColor="#0f766e" stopOpacity="0.45" />
            </radialGradient>
            <radialGradient id="graph-node" cx="35%" cy="30%" r="70%">
              <stop offset="0%" stopColor="#ecfdf5" stopOpacity="0.9" />
              <stop offset="55%" stopColor="#34d399" stopOpacity="0.55" />
              <stop offset="100%" stopColor="#064e3b" stopOpacity="0.35" />
            </radialGradient>
            <filter id="graph-glow">
              <feGaussianBlur stdDeviation="5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {nodes.map((node) => (
            <line
              key={"edge-" + node.competitor}
              x1={cx}
              y1={cy}
              x2={node.x}
              y2={node.y}
              stroke="#67e8f9"
              strokeOpacity="0.26"
              strokeWidth="1.4"
            />
          ))}

          {nodes.map((node) => (
            <g key={node.competitor}>
              <circle
                cx={node.x}
                cy={node.y}
                r="26"
                fill="url(#graph-node)"
                stroke="#6ee7b7"
                strokeOpacity="0.35"
                filter="url(#graph-glow)"
              />
              <text
                x={node.x}
                y={node.y + 42}
                textAnchor="middle"
                fill="#94a3b8"
                fontSize="10"
              >
                {formatGraphLabel(node.competitor)}
              </text>
            </g>
          ))}

          <circle
            cx={cx}
            cy={cy}
            r="58"
            fill="url(#graph-core)"
            stroke="#a5f3fc"
            strokeOpacity="0.55"
            filter="url(#graph-glow)"
          />
          <text
            x={cx}
            y={cy - 4}
            textAnchor="middle"
            fill="#ffffff"
            fontSize="13"
            fontWeight="700"
          >
            {formatGraphLabel(company.company_name)}
          </text>
          <text
            x={cx}
            y={cy + 16}
            textAnchor="middle"
            fill="#cffafe"
            fontSize="10"
          >
            {competitors.length} observed edges
          </text>
        </svg>
      </div>
      <div className="flex items-center justify-between gap-3 border-t border-white/8 px-2 pt-3 text-[10px] text-slate-600">
        <span>{(company.evidence ?? []).length} evidence records</span>
        <span>
          confidence{" "}
          {typeof company.confidence === "number"
            ? Math.round(company.confidence * 100) + "%"
            : "unknown"}
        </span>
      </div>
    </div>
  );
}

function TruthPill({ label, value }: { label: string; value: boolean }) {
  return (
    <span
      className={[
        "rounded-full border px-2.5 py-1 text-[10px] font-semibold",
        value
          ? "border-emerald-300/25 bg-emerald-300/[0.08] text-emerald-100"
          : "border-slate-400/15 bg-white/[0.025] text-slate-500",
      ].join(" ")}
    >
      {label}: {value ? "yes" : "no"}
    </span>
  );
}

function recoveryTone(value: string | undefined) {
  if (value === "ACTIVE_BUILD" || value === "PRODUCTION") {
    return "border-emerald-400/25 bg-emerald-400/10 text-emerald-200";
  }
  if (value === "FOUNDER_GATE") {
    return "border-violet-400/25 bg-violet-400/10 text-violet-200";
  }
  if (value === "SALVAGE_CANDIDATE" || value === "INCUBATE") {
    return "border-cyan-400/25 bg-cyan-400/10 text-cyan-200";
  }
  if (value === "REBUILD_LATER") {
    return "border-amber-400/25 bg-amber-400/10 text-amber-200";
  }
  return "border-white/10 bg-white/[0.035] text-slate-400";
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
