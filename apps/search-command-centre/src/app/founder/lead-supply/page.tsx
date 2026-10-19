import Link from "next/link";
import { connection } from "next/server";
import {
  getFounderLeadSupply,
  getFounderLeadSupplyPackages,
  type FounderLeadSupply,
  type FounderTerritoryMrr,
} from "@/lib/founder-api";

const fmt = (v: number | undefined) =>
  typeof v === "number" ? v.toLocaleString("en-GB") : "Unknown";
const entries = (record: Record<string, number> | undefined) =>
  Object.entries(record ?? {}).sort((a, b) => b[1] - a[1]);

function Tile({ label, value, note }: {
  label: string; value: string; note: string;
}) {
  return (
    <div className="panel p-5">
      <p className="eyebrow">{label}</p>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-white">{value}</p>
      <p className="mt-2 text-xs text-slate-400">{note}</p>
    </div>
  );
}

export default async function FounderLeadSupplyPage({
  searchParams,
}: {
  searchParams: Promise<{ niche?: string }>;
}) {
  await connection();
  const query = await searchParams;
  const [result, packageResult] = await Promise.all([
    getFounderLeadSupply(),
    getFounderLeadSupplyPackages(),
  ]);
  const data: FounderLeadSupply | null = result.data?.available ? result.data : null;
  const packages: FounderTerritoryMrr | null =
    packageResult.data?.available ? packageResult.data : null;
  const selected = typeof query.niche === "string" ? query.niche.trim().slice(0, 120) : "";
  const niches = data?.niches ?? [];
  const visible = selected ? niches.filter((v) => v.niche === selected) : niches;
  const seats = data?.exchange?.buyer_seat_states ?? {};
  const scoring = data?.scoring_coverage;
  const corridors = (data?.corridors ?? []).filter((row) => !selected || row.niche === selected);

  return (
    <main className="min-h-screen bg-[#07100d] text-slate-100">
      <div className="mx-auto max-w-[1600px] px-5 py-8 lg:px-10">
        <header className="border-b border-white/10 pb-7">
          <Link href="/founder" className="text-xs uppercase tracking-widest text-cyan-300">
            ← Founder Console
          </Link>
          <p className="eyebrow mt-5">Empire AI · Supply & Demand Intelligence</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight">Niche lead inventory</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
            Canonical EmpireDB prospect counts, acquisition provenance, crawler receipts,
            buyer-seat evidence and exchange corridors. Private founder view only;
            no lead delivery, public inventory commitment or financial activation.
          </p>
          <p className="mt-3 text-xs text-slate-500">
            As of {data?.observed_at ?? "not yet materialized"} · OBSERVE ·{" "}
            {data?.lead_counts_complete
              ? "Complete bounded table read; not a transactionally consistent snapshot"
              : "Counts unavailable or incomplete — do not present as total supply"}
          </p>
        </header>

        <section className="panel mt-7">
          <p className="eyebrow">Commercial Exchange · Recurring Revenue</p>
          <h2 className="mt-2 text-2xl font-semibold">MRR seats and territory packages</h2>
          <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-400">
            Existing founder-approved monthly product tiers, linked to the current
            qualified lead corridors and buyer seat evidence. A listed package is
            not an active customer subscription; nominated territory is not exclusive
            and buyer-stated demand is not a binding reservation.
          </p>
          {!packages ? (
            <p className="mt-5 text-sm text-amber-200">
              Package/corridor preview not yet released.
              The existing checkout catalogue remains a separate interest-only surface.
            </p>
          ) : (
            <>
              <p className="mt-3 text-xs text-slate-500">
                Exchange evidence: {packages.exchange_observed_at ?? "Unknown"} ·
                Subscriptions reader: {packages.buyer_subscriptions_reader_available
                  ? "observed" : "not connected"} ·
                Verified monthly revenue: not established by this source
              </p>
              <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {(packages.product_catalog ?? []).map((item) => (
                  <div key={item.code} className="rounded-xl border border-white/10 p-5">
                    <p className="text-sm font-semibold text-white">{item.name}</p>
                    <p className="mt-3 text-3xl font-semibold text-cyan-200">
                      ${(item.monthly_price_cents / 100).toLocaleString("en-GB")}/mo
                    </p>
                    <p className="mt-2 text-sm text-slate-400">
                      {item.corridor_limit == null
                        ? "Custom contract territory"
                        : `Up to ${item.corridor_limit} ${item.corridor_limit === 1 ? "corridor" : "corridors"}`}
                    </p>
                    <p className="mt-2 text-xs text-slate-500">
                      {item.territory_model.replaceAll("_", " ")} ·
                      Exclusivity {item.exclusivity_eligible ? "eligible, not granted" : "not included"}
                    </p>
                    <p className="mt-3 text-xs text-amber-200">
                      {item.binding_terms_ready
                        ? "Binding terms flagged ready in catalog"
                        : "Not activated · binding terms outstanding"}
                    </p>
                  </div>
                ))}
              </div>
              <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <Tile label="Observed package definitions"
                  value={fmt(packages.product_catalog_count)}
                  note={`${fmt(packages.territory_market_count)} niche/territory markets in the exchange snapshot`} />
                <Tile label="Legacy strike-pack rows"
                  value={fmt(packages.strike_pack_record_count ?? undefined)}
                  note="Read-only EmpireDB count, if accessible" />
                <Tile label="Buyer subscription records"
                  value={fmt(packages.buyer_subscription_record_count ?? undefined)}
                  note="Includes paused, expired and unverified subscriptions" />
                <Tile label="Marked active subscription rows"
                  value={fmt(packages.marked_active_subscription_record_count ?? undefined)}
                  note="Database state; not verified receipts or realised MRR" />
              </div>
              <p className="mt-3 text-xs text-slate-500">
                Configured recurring price fields and old Stripe references are
                not financial verification. Direct USDT/BSC receipts, fulfilment,
                contracts and entitlements require their own evidence.
              </p>
              <div className="mt-7">
                <h3 className="text-lg font-semibold">Niche and territory seat coverage</h3>
                <p className="mt-2 text-xs text-slate-400">
                  Qualified exchange sample, grouped by niche and metro. Raw buyer
                  delivery corridors (webhook/phone) and lead-supply corridors
                  use different route identities; market overlap is not proof of
                  a deliverable route, signed territory or exclusivity.
                </p>
                <div className="mt-4 max-h-[500px] overflow-auto">
                  <table className="w-full min-w-[850px] text-left text-sm">
                    <thead className="sticky top-0 bg-[#0b1716] text-xs uppercase tracking-wider text-slate-500">
                      <tr>
                        <th className="py-3 pr-4">Niche</th>
                        <th className="py-3 pr-4">Territory</th>
                        <th className="py-3 pr-4">Seat records</th>
                        <th className="py-3 pr-4">Capacity-ready</th>
                        <th className="py-3 pr-4">Sampled leads</th>
                        <th className="py-3 pr-4">Overflow</th>
                        <th className="py-3 pr-4">Operational readiness</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(packages.territory_markets ?? [])
                        .filter((item) => !selected || item.niche === selected)
                        .map((item) => (
                          <tr key={item.niche + ":" + item.metro} className="border-t border-white/[0.06]">
                            <td className="py-2 pr-4 font-semibold text-cyan-200">
                              {item.niche}
                            </td>
                            <td className="py-2 pr-4">{item.metro}</td>
                            <td className="py-2 pr-4">{fmt(item.buyer_seat_records)}</td>
                            <td className="py-2 pr-4">{fmt(item.verified_active_capacity_records)}</td>
                            <td className="py-2 pr-4">{fmt(item.sampled_qualified_inventory_records)}</td>
                            <td className="py-2 pr-4">{fmt(item.sampled_overflow_records)}</td>
                            <td className="py-2 pr-4 text-xs text-amber-200">
                              {item.readiness.replaceAll("_", " ")}
                            </td>
                          </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </section>

        {!data ? (
          <section className="panel mt-8">
            <h2 className="text-xl font-semibold">Canonical lead-count report not available</h2>
            <p className="mt-3 text-sm text-amber-200">
              {result.reason ?? result.data?.reason ?? "Private EmpireDB collector has not been released."}
            </p>
            <p className="mt-3 text-sm text-slate-400">
              Historical crawler events and the qualified exchange sample cannot substitute
              for full unique-lead totals.
            </p>
          </section>
        ) : (
          <>
            <section className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <Tile label="Unique canonical prospects" value={fmt(data.unique_prospects_observed)}
                note={data.lead_counts_complete ? "All rows in bounded scan" : "Partial sample only"} />
              <Tile label="Qualified with evidence" value={fmt(data.qualified_with_evidence_observed)}
                note="Qualification evidence, not a sold lead" />
              <Tile label="Buyer-seat records" value={fmt(data.exchange?.buyer_seat_record_count)}
                note="Includes unactivated and blocked records" />
              <Tile label="Verified active seats" value={fmt(seats.active_capacity)}
                note="Only independently eligible delivery capacity" />
            </section>

            <section className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <Tile label="Exchange inventory sample" value={fmt(data.exchange?.inventory_sample_count)}
                note="Selected qualifications, not all discovered leads" />
              <Tile label="Corridors observed" value={fmt(data.exchange?.corridor_count)}
                note="Niche × location × demand × delivery routes" />
              <Tile label="Missing source provenance" value={fmt(data.prospects_missing_acquisition_provenance)}
                note="Canonical prospects without linked acquisition record" />
              <Tile label="Verified market prices" value={fmt(data.exchange?.verified_market_price_count)}
                note="No estimated or invented prices" />
            </section>

            <section className="panel mt-7">
              <p className="eyebrow">OMEGA · CORTEX · Qualification v2 · Enrichment</p>
              <h2 className="mt-2 text-xl font-semibold">Lead intelligence engine coverage</h2>
              <p className="mt-2 text-sm text-slate-400">
                This measures canonical evidence linkages. OMEGA scores are deterministic,
                not independently calibrated sales probabilities; CORTEX learns from
                verified outcomes and is not a replacement qualification score.
              </p>
              {!scoring?.available ? (
                <p className="mt-5 text-sm text-amber-200">
                  Intelligence score reader unavailable. No zero-score assumption.
                </p>
              ) : (
                <>
                  <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    <Tile label="Scoring v2 records" value={fmt(scoring.counts?.v2_scored_rows)}
                      note="Latest canonical v2 records per prospect" />
                    <Tile label="Enrichment evidence" value={fmt(scoring.counts?.enrichment_evidence_present)}
                      note="Evidence attached to qualification result" />
                    <Tile label="OMEGA evidence matched" value={fmt(scoring.omega_evidence_matched_unique_prospects)}
                      note="Matched qualification ID and active entity identity" />
                    <Tile label="Missing qualification" value={fmt(scoring.counts?.unscored)}
                      note="No canonical v1/v2 score in census" />
                  </div>
                  <div className="mt-6 max-h-[430px] overflow-auto">
                    <table className="w-full min-w-[780px] text-left text-sm">
                      <thead className="sticky top-0 bg-[#0b1716] text-xs uppercase tracking-wider text-slate-500">
                        <tr>
                          <th className="py-3 pr-4">Niche</th>
                          <th className="py-3 pr-4">v2 scored</th>
                          <th className="py-3 pr-4">Hot</th>
                          <th className="py-3 pr-4">Warm</th>
                          <th className="py-3 pr-4">Evidence missing</th>
                          <th className="py-3 pr-4">Enriched</th>
                          <th className="py-3 pr-4">OMEGA matched</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(scoring.by_niche ?? [])
                          .filter((n) => !selected || n.niche === selected)
                          .map((n) => (
                          <tr key={n.niche} className="border-t border-white/[0.06]">
                            <td className="py-2 pr-4 font-semibold text-cyan-200">{n.niche}</td>
                            <td className="py-2 pr-4">{fmt(n.v2_scored_rows)}</td>
                            <td className="py-2 pr-4">{fmt(n.tier_hot)}</td>
                            <td className="py-2 pr-4">{fmt(n.tier_warm)}</td>
                            <td className="py-2 pr-4">{fmt(n.insufficient_evidence)}</td>
                            <td className="py-2 pr-4">{fmt(n.enrichment_evidence_present)}</td>
                            <td className="py-2 pr-4">{fmt(n.omega_evidence_matched)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
              <div className="mt-6 rounded-xl border border-white/10 p-4">
                <p className="font-semibold">CORTEX outcome learning</p>
                <p className="mt-2 text-xs text-slate-400">
                  Snapshot: {scoring?.cortex?.generated_at ?? "Unavailable"} ·{" "}
                  {scoring?.cortex?.stale_older_than_24h
                    ? "STALE" : scoring?.cortex?.available ? "Available" : "Unverified"} ·{" "}
                  {fmt(scoring?.cortex?.verified_customer_learning_count)} verified customer learning records
                </p>
                <p className="mt-2 text-xs text-amber-200">
                  A CORTEX snapshot does not prove live niche-level model learning.
                  Verified fulfilled and paid outcomes are required before any learning promotion.
                </p>
              </div>
              <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {(scoring?.engine_registry ?? []).map((item) => (
                  <div key={item.engine} className="rounded-xl border border-white/10 p-4">
                    <p className="font-semibold">{item.engine}</p>
                    <p className="mt-2 text-xs text-slate-400">{item.observed_connection.replaceAll("_", " ")}</p>
                    <p className="mt-2 break-all text-xs text-slate-500">{item.files.join(", ")}</p>
                  </div>
                ))}
              </div>
            </section>

            <section className="panel mt-7">
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <p className="eyebrow">Lead inventory by niche</p>
                  <h2 className="mt-2 text-xl font-semibold">Source → niche → buyer capacity</h2>
                  <p className="mt-2 text-xs text-slate-400">
                    One prospect counted once per niche; a lead can have several provenance sources.
                  </p>
                </div>
                {selected && <Link href="/founder/lead-supply" className="text-sm text-cyan-300">
                  Clear niche filter
                </Link>}
              </div>
              <div className="mt-6 overflow-x-auto">
                <table className="w-full min-w-[940px] text-left text-sm">
                  <thead className="border-b border-white/10 text-xs uppercase tracking-wider text-slate-500">
                    <tr>
                      <th className="py-3 pr-4">Niche</th>
                      <th className="py-3 pr-4">Unique</th>
                      <th className="py-3 pr-4">Qualified</th>
                      <th className="py-3 pr-4">Source gaps</th>
                      <th className="py-3 pr-4">Seated records</th>
                      <th className="py-3 pr-4">Active seats</th>
                      <th className="py-3 pr-4">Markets</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visible.map((niche) => (
                      <tr key={niche.niche} className="border-b border-white/[0.06]">
                        <td className="py-3 pr-4 font-semibold text-cyan-200">
                          <Link href={`/founder/lead-supply?niche=${encodeURIComponent(niche.niche)}`}>
                            {niche.niche}
                          </Link>
                        </td>
                        <td className="py-3 pr-4">{fmt(niche.unique_leads_observed)}</td>
                        <td className="py-3 pr-4">{fmt(niche.qualified_with_evidence_observed)}</td>
                        <td className="py-3 pr-4">{fmt(niche.no_acquisition_provenance)}</td>
                        <td className="py-3 pr-4">
                          {fmt(Object.values(niche.buyer_seat_states ?? {}).reduce((a, b) => a + b, 0))}
                        </td>
                        <td className="py-3 pr-4">{fmt(niche.buyer_seat_states?.active_capacity ?? 0)}</td>
                        <td className="py-3 pr-4">{Object.keys(niche.by_metro ?? {}).length}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {selected && visible[0] && (
                <div className="mt-7 grid gap-5 md:grid-cols-2">
                  <div>
                    <h3 className="font-semibold">Locations</h3>
                    {entries(visible[0].by_metro).map(([name, count]) => (
                      <p key={name} className="mt-2 flex justify-between text-sm text-slate-300">
                        <span>{name}</span><span>{fmt(count)}</span>
                      </p>
                    ))}
                  </div>
                  <div>
                    <h3 className="font-semibold">Acquisition sources</h3>
                    {entries(visible[0].by_source).map(([name, count]) => (
                      <p key={name} className="mt-2 flex justify-between text-sm text-slate-300">
                        <span>{name}</span><span>{fmt(count)}</span>
                      </p>
                    ))}
                  </div>
                </div>
              )}
            </section>

            <section className="panel mt-7">
              <p className="eyebrow">Commercial corridors</p>
              <h2 className="mt-2 text-xl font-semibold">Seat capacity versus sampled lead supply</h2>
              <p className="mt-2 text-xs text-amber-200">
                Sampled supply is from the qualified exchange selection. A corridor key
                does not guarantee pricing, delivery or contractual territory.
              </p>
              <div className="mt-5 max-h-[580px] overflow-auto">
                <table className="w-full min-w-[820px] text-left text-sm">
                  <thead className="sticky top-0 bg-[#0b1716] text-xs uppercase tracking-wider text-slate-500">
                    <tr>
                      <th className="py-3 pr-4">Niche / market</th>
                      <th className="py-3 pr-4">Delivery corridor</th>
                      <th className="py-3 pr-4">Seat records</th>
                      <th className="py-3 pr-4">Active</th>
                      <th className="py-3 pr-4">Overflow</th>
                    </tr>
                  </thead>
                  <tbody>
                    {corridors.map((row) => (
                      <tr key={row.corridor_key} className="border-t border-white/[0.06]">
                        <td className="py-2 pr-4 text-cyan-200">{row.niche} · {row.metro}</td>
                        <td className="py-2 pr-4 break-all text-xs text-slate-400">{row.corridor_key}</td>
                        <td className="py-2 pr-4">{fmt(row.buyer_seat_records)}</td>
                        <td className="py-2 pr-4">{fmt(row.active_seat_records)}</td>
                        <td className="py-2 pr-4">{fmt(row.sampled_overflow)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="mt-7 grid gap-5 xl:grid-cols-2">
              <div className="panel">
                <p className="eyebrow">Crawler operations</p>
                <h2 className="mt-2 text-xl font-semibold">Historical event receipts</h2>
                <p className="mt-2 text-xs text-amber-200">
                  Attempts and logs are not unique, available or sellable leads.
                </p>
                {entries(data.crawler_receipts?.event_totals).map(([kind, count]) => (
                  <p key={kind} className="mt-3 flex justify-between text-sm text-slate-300">
                    <span>{kind.replaceAll("_", " ")}</span><span>{fmt(count)}</span>
                  </p>
                ))}
                {data.crawler_receipts?.truncated && <p className="mt-3 text-xs text-amber-200">
                  Log scan truncated; event metrics are partial.
                </p>}
              </div>
              <div className="panel">
                <p className="eyebrow">Intelligence connectivity</p>
                <h2 className="mt-2 text-xl font-semibold">Evidence pipeline</h2>
                {(data.intelligence_connections ?? []).map((edge, i) => (
                  <div key={i} className="mt-3 border-b border-white/8 pb-3 text-xs text-slate-300">
                    <p>{edge.from} → {edge.to}</p>
                    <p className="mt-1 text-slate-500">{edge.state.replaceAll("_", " ")}</p>
                  </div>
                ))}
              </div>
            </section>

            <section className="panel mt-7">
              <p className="eyebrow">Source Intelligence contracts</p>
              <h2 className="mt-2 text-xl font-semibold">Registered evidence sources</h2>
              <p className="mt-2 text-xs text-amber-200">
                Catalogue status is not proof of live API connectivity, consent,
                redistributable raw data or successful canonical ingests.
              </p>
              <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {(data.source_contract_catalog ?? []).map((source) => (
                  <div key={source.source_id} className="rounded-xl border border-white/10 p-4">
                    <p className="text-sm font-semibold text-white">{source.source_id}</p>
                    <p className="mt-2 text-xs text-slate-400">
                      {source.country} · {source.production_status_in_catalog} ·{" "}
                      {source.niches.join(", ")}
                    </p>
                    <p className="mt-2 text-xs text-slate-500">Licence: {source.licence}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      Raw resale: {source.raw_resale_allowed ? "Rights still require review" : "Not permitted"}
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
