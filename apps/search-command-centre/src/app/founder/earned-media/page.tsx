import Link from "next/link";
import { notFound } from "next/navigation";
import { connection } from "next/server";
import { getFounderEarnedMedia, type EarnedMediaReviewItem } from "@/lib/founder-api";

const LANES: Array<{ key: EarnedMediaReviewItem["lane"]; label: string }> = [
  { key: "pr", label: "Press & PR" },
  { key: "editorial", label: "Editorial & organic" },
  { key: "consultancy", label: "Consultancy" },
  { key: "proposal", label: "Proposals" },
];

function humanState(value: string) {
  return value.replaceAll("_", " ").toLowerCase();
}

function startingPrice(item: EarnedMediaReviewItem) {
  if (typeof item.amount_minor !== "number") return null;
  return new Intl.NumberFormat("en-GB", {
    style: "currency", currency: "GBP", maximumFractionDigits: 0,
  }).format(item.amount_minor / 100)
    + (item.billing_model === "monthly" ? "/month" : " starting price");
}

export default async function FounderEarnedMediaPage() {
  // Feature flags are not authentication. Never release without verified ingress.
  if (process.env.EMPIRE_EARNED_MEDIA_FOUNDER_UI_ENABLED !== "1" ||
      process.env.EMPIRE_FOUNDER_CONSOLE_PRIVATE_AUTH_VERIFIED !== "1") {
    notFound();
  }
  await connection();
  const result = await getFounderEarnedMedia();
  const packet = result.data;
  const items = packet?.items ?? [];

  return (
    <main className="min-h-screen bg-[#060b18] px-4 py-7 text-slate-100 sm:px-6 lg:px-10">
      <div className="mx-auto max-w-[1450px]">
        <header className="rounded-3xl border border-white/10 bg-[#0b1225] p-6">
          <Link href="/founder" className="text-xs uppercase tracking-[0.16em] text-cyan-300">
            ← Founder Console
          </Link>
          <p className="mt-6 text-xs uppercase tracking-wider text-amber-300">
            Founder review only · no outbound authority
          </p>
          <h1 className="mt-2 text-3xl font-semibold">
            PR, Editorial, Consultancy & Proposals
          </h1>
          <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-300">
            One evidence view across existing Marketing, Search and commercial work.
            Previous sent pitches are not new leads. Contract, publishing, CRM binding,
            accepted payment and attribution all require separate proof.
          </p>
          {!result.ok || !packet ? (
            <p className="mt-4 rounded-xl border border-amber-400/20 p-3 text-sm text-amber-200">
              Founder review unavailable ({result.reason ?? "read not configured"}).
              No authorisations inferred.
            </p>
          ) : (
            <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
              {LANES.map((lane) => (
                <div key={lane.key} className="rounded-xl border border-white/10 bg-white/[0.035] p-4">
                  <p className="text-xs text-slate-400">{lane.label}</p>
                  <p className="mt-1 text-2xl font-semibold">{packet.lane_counts?.[lane.key] ?? 0}</p>
                </div>
              ))}
            </div>
          )}
        </header>
        {packet && (
          <>
            <div className="mt-5 rounded-2xl border border-amber-400/20 bg-amber-400/5 p-4 text-sm text-amber-100">
              <strong>Release:</strong> {humanState(packet.status ?? "unverified")}.
              CRM: {humanState(packet.crm_reconciliation_state ?? "unverified")}.
              No client deal or realised revenue is proved by these files.
            </div>
            <section className="mt-7 rounded-3xl border border-white/10 bg-[#0b1225] p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-300">
                Lead intelligence · multi-sector · read-only
              </p>
              <h2 className="mt-2 text-2xl font-semibold">Commercial prospect research</h2>
              <p className="mt-2 text-sm text-slate-400">
                Existing company research and documented external service requests.
                Scores rank evidence review effort, not likelihood of buying.
              </p>
              {packet.lead_generation?.status ===
              "RESEARCH_PRIORITY_QUEUE_NOT_BUYER_PIPELINE" ? (
                <>
                  <div className="mt-4 grid gap-3 sm:grid-cols-3">
                    <div className="rounded-xl border border-white/10 p-4">
                      <p className="text-xs text-slate-400">Public service-demand signals</p>
                      <p className="mt-1 text-2xl font-semibold">
                        {packet.lead_generation.counts?.source_signal ?? 0}
                      </p>
                    </div>
                    <div className="rounded-xl border border-white/10 p-4">
                      <p className="text-xs text-slate-400">Researched accounts</p>
                      <p className="mt-1 text-2xl font-semibold">
                        {packet.lead_generation.counts?.researched_account ?? 0}
                      </p>
                      <p className="mt-1 text-xs text-amber-200">
                        {packet.lead_generation.counts?.unbound_researched_account ?? 0}
                        {" "}without canonical prospect ID
                      </p>
                    </div>
                    <div className="rounded-xl border border-amber-400/20 p-4">
                      <p className="text-xs text-slate-400">Verified purchasing buyers</p>
                      <p className="mt-1 text-2xl font-semibold">
                        {packet.lead_generation.counts?.qualified_buyer ?? 0}
                      </p>
                      <p className="mt-1 text-xs text-amber-200">No send or quote authority</p>
                    </div>
                  </div>
                  {packet.sales_actionability?.status ===
                  "REVIEW_PRIORITIES_NOT_EXECUTABLE_SALES_PIPELINE" && (
                    <div className="mt-5 rounded-xl border border-amber-400/25 p-4">
                      <h3 className="text-sm font-semibold text-amber-200">Commercial actionability gates</h3>
                      <p className="mt-2 text-xs text-slate-300">
                        Source discovery is not a qualified buyer. Contact ready:
                        {" "}{packet.sales_actionability.ready_for_contact}. Proposal ready:
                        {" "}{packet.sales_actionability.ready_for_proposal}.
                      </p>
                      <div className="mt-3 grid gap-2 sm:grid-cols-2">
                        {Object.entries(packet.sales_actionability.actionability_counts).map(([reason, count]) => (
                          <div key={reason} className="rounded-lg border border-white/10 bg-white/[0.025] p-3">
                            <span className="text-lg font-semibold">{count}</span>
                            <span className="ml-2 text-xs text-slate-400">{humanState(reason)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="mt-5 grid gap-3 md:grid-cols-2">
                    {(packet.lead_generation.opportunities ?? []).slice(0, 8).map((lead) => (
                      <article key={lead.opportunity_id}
                        className="rounded-xl border border-white/10 bg-white/[0.025] p-4">
                        <div className="flex justify-between gap-3">
                          <h3 className="text-sm font-semibold">{lead.label}</h3>
                          <span className="shrink-0 text-xs text-cyan-200">
                            Review {lead.priority_score}/100
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-amber-200">
                          {humanState(lead.lead_stage)}
                        </p>
                        <p className="mt-3 text-sm text-slate-300">{lead.next_action}</p>
                        {packet.sales_actionability?.records
                          ?.filter((record) => record.opportunity_id === lead.opportunity_id)
                          .map((gate) => (
                            <div key={gate.opportunity_id} className="mt-3 border-t border-amber-300/15 pt-3">
                              <p className="text-xs font-semibold text-amber-200">
                                {humanState(gate.actionability)}
                              </p>
                              <p className="mt-1 text-xs text-slate-300">{gate.next_evidence_step}</p>
                              <p className="mt-1 text-xs text-slate-500">
                                Public source: {humanState(gate.source_index_check)}
                              </p>
                            </div>
                          ))}
                        <p className="mt-2 text-xs text-slate-400">
                          Free sample concept: {lead.value_first_free_sample_outline}
                        </p>
                        <Link
                          href={`/founder/earned-media/sample/${encodeURIComponent(lead.opportunity_id)}`}
                          className="mt-3 inline-block text-xs font-semibold text-cyan-200 hover:text-cyan-100"
                        >
                          Preview original value-first sample →
                        </Link>
                        <p className="mt-2 text-xs text-slate-500">
                          Blockers: {lead.blockers.length}
                          {lead.existing_canonical_prospect_id
                            ? " · historical prospect ID exists"
                            : " · no canonical prospect match"}
                        </p>
                      </article>
                    ))}
                  </div>
                  <p className="mt-4 text-xs text-slate-500">
                    Original source snapshots may be stale. No current job availability,
                    editor placement, qualified buyer, accepted proposal or revenue verified.
                  </p>
                </>
              ) : (
                <p className="mt-4 text-sm text-amber-200">
                  Lead generation source checks held. No prospect claims inferred.
                </p>
              )}
            </section>
            <section className="mt-7 rounded-2xl border border-cyan-300/15 bg-[#0b1225] p-5">
              <p className="text-xs uppercase tracking-[0.17em] text-cyan-200">
                Original content → First-party commercial enquiry
              </p>
              <h2 className="mt-2 text-xl font-semibold">Revenue leakage guide source review</h2>
              <p className="mt-3 text-sm text-slate-300">
                {packet.first_party_conversion?.state
                  ? humanState(packet.first_party_conversion.state)
                  : "Source bridge has not been reviewed"}
              </p>
              {packet.first_party_conversion?.source_code_readiness && (
                <p className="mt-2 text-sm text-slate-300">
                  First-party entry: {packet.first_party_conversion.reviewed_entry_page}.
                  Existing consented form link is staged for website-owner review.
                </p>
              )}
              <p className="mt-3 text-xs leading-6 text-amber-200">
                Separate AI readiness article: {humanState(
                  packet.first_party_conversion?.article_publication_state ?? "not verified"
                )}. No published PR placement, attributable click, opted-in buyer,
                signed scope or settled revenue is proved here.
              </p>
              <p className="mt-2 text-xs text-slate-400">
                {packet.first_party_conversion?.review_step ??
                  "Founder and ASTRA review required before website release."}
              </p>
            </section>
            {LANES.map((lane) => {
              const rows = items.filter((item) => item.lane === lane.key);
              return (
                <section key={lane.key} className="mt-7">
                  <h2 className="mb-3 text-xl font-semibold">{lane.label}</h2>
                  <div className="grid gap-3 md:grid-cols-2">
                    {rows.map((item) => (
                      <article key={item.item_id}
                        className="rounded-2xl border border-white/10 bg-[#0b1225] p-5">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <h3 className="text-lg font-medium">{item.label}</h3>
                          <span className="rounded-full border border-amber-400/25 px-3 py-1 text-xs text-amber-200">
                            {humanState(item.state)}
                          </span>
                        </div>
                        {startingPrice(item) &&
                          <p className="mt-2 text-sm text-cyan-200">{startingPrice(item)}</p>}
                        <p className="mt-3 text-sm leading-6 text-slate-300">{item.next_review}</p>
                        <p className="mt-3 break-all text-xs text-slate-500">
                          Evidence: {item.evidence_reference}
                        </p>
                        <p className="mt-2 text-xs text-slate-400">
                          Smart CRM: {humanState(item.crm_linkage?.state ?? "unverified")}
                        </p>
                      </article>
                    ))}
                  </div>
                </section>
              );
            })}
            {Object.values(packet.sources ?? {}).some((source) =>
              source.state.startsWith("HELD")
            ) && (
              <p className="mt-6 rounded-2xl border border-rose-400/30 p-4 text-sm text-rose-200">
                A source is missing or failed validation. Corresponding items remain held.
              </p>
            )}
            <p className="mt-10 text-xs text-slate-500">
              Historical, read-only Founder view. No send, publish, quote, contract,
              CRM write or payment controls.
            </p>
          </>
        )}
      </div>
    </main>
  );
}
