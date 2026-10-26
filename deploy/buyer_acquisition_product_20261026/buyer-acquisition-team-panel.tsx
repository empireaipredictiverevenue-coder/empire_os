import { readFile, lstat } from "node:fs/promises";
import BuyerAcquisitionTeamTable, { type BuyerTeamView } from "./buyer-acquisition-team-table";

const SOURCE = "/srv/empire_os/runtime/buyer_network_intelligence/founder_qualification_actions_latest.json";
const validDomain = /^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$/;

function text(value: unknown, maximum = 140): string {
  return typeof value === "string" ? value.slice(0, maximum) : "";
}
function number(value: unknown): number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0 ? value : 0;
}
function fromObject(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
function words(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((x): x is string => typeof x === "string" && /^[a-z_]{2,40}$/.test(x)).slice(0, 12);
}
async function readTeam(): Promise<{ data: BuyerTeamView | null; reason: string }> {
  try {
    const info = await lstat(SOURCE);
    if (!info.isFile() || info.isSymbolicLink() || info.size > 2_500_000 || info.size < 100) {
      return { data: null, reason: "Buyer Team private evidence is missing or unsafe." };
    }
    const document = fromObject(JSON.parse(await readFile(SOURCE, "utf8")));
    if (
      document.schema_version !== "empire.buyer_qualification_actions.v1" ||
      document.mode !== "OBSERVE" || document.execution_authority !== "none" ||
      document.outbound_sent !== false || document.outbound_enabled !== false ||
      !Array.isArray(document.targets) || document.targets.length > 500 ||
      document.shortlisted_count !== document.targets.length
    ) {
      return { data: null, reason: "Buyer Team evidence does not meet the read-only product contract." };
    }
    const generatedAt = text(document.generated_at, 40);
    const generatedEpoch = Date.parse(generatedAt);
    if (!Number.isFinite(generatedEpoch) || generatedEpoch > Date.now() + 300_000) {
      return { data: null, reason: "Buyer Team evidence timestamp cannot be verified." };
    }
    const selected: BuyerTeamView["rows"] = [];
    for (const input of document.targets) {
      const item = fromObject(input);
      const domain = text(item.domain, 255);
      if (!validDomain.test(domain)) continue;
      const fit = fromObject(item.active_demand_sector_research_fit);
      const tier = text(item.tier, 45);
      const action = text(item.commercial_next_action, 110);
      const role = text(item.buyer_relationship_role_review, 100);
      selected.push({
        domain, tier, action, role,
        contact: text(item.contact_history_state, 85),
        sectors: words(item.verticals),
        matchedSectors: words(fit.first_party_matching_sector_names),
        sectorResearchState: text(fit.state, 60),
        observedOverflow: number(fit.observed_overflow_units_for_sectors),
        siteCorroborated: item.site_corroborated_buyer_role === true,
        sourceCurrent: fromObject(item.first_party_due_diligence).freshness === "CURRENT",
      });
    }
    return {
      data: {
        generatedAt,
        stale: Date.now() - generatedEpoch > 2 * 3600_000,
        teamCount: selected.length,
        reviewCount: number(document.trusted_founder_review_count),
        sectorFitCount: number(document.first_party_sector_research_fit_count),
        geoVerifiedCount: number(document.buyer_accepted_geo_or_zip_coverage_count),
        demandState: text(document.active_demand_source_state, 70),
        rows: selected,
      },
      reason: "",
    };
  } catch {
    return { data: null, reason: "Buyer Team private evidence is temporarily unavailable." };
  }
}

/** Additive original Founder Commercial Operations reader. No new API/agent. */
export default async function BuyerAcquisitionTeamPanel() {
  const { data, reason } = await readTeam();
  return (
    <section className="mt-6 rounded-2xl border border-sky-400/15 bg-[#0b1730] p-5 sm:p-7" aria-label="Buyer Acquisition Team operating queue">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[.19em] text-amber-300">EmpireOS · Original Buyer Acquisition Team</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white">Buyer intelligence workbench</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">All researched companies, sector evidence, relationship history and their real next qualification action. Buyer research is not accepted demand, contracted capacity or revenue.</p>
        </div>
        <span className="rounded-lg border border-cyan-300/20 px-3 py-2 text-xs font-semibold text-cyan-200">Read-only · Original team</span>
      </div>
      {!data ? <p role="status" className="rounded-lg border border-amber-300/25 bg-amber-400/5 p-4 text-sm text-amber-200">{reason}</p> :
        <BuyerAcquisitionTeamTable data={data} />}
    </section>
  );
}
