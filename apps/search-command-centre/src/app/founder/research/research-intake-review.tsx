"use client";

type Candidate = {
  url?: string;
  title?: string;
  provider?: string;
  discovery_query?: string;
  admission_state?: string;
};
type Discovery = {
  status?: string;
  queries_attempted?: number;
  provider_errors?: string[];
  source_admissions?: number;
  fresh_provider_responses?: number;
  provider_results_seen?: number;
  niche_rejected?: number;
  market_rejected?: number;
  candidate_urls?: Candidate[];
};
export type ResearchIntake = {
  country?: string;
  niche?: string;
  buyer_problem_to_qualify?: string;
  research_question?: string;
  evidence_categories_to_verify?: string[];
  unverified_inferences_to_avoid?: string[];
  source_catalogue_state?: string;
  next_action?: string;
  public_search_diagnostic?: Discovery;
};
export type MarketSearchReport = {
  country?: string;
  current_search_discovery?: Discovery;
};

function safeCandidateUrl(input?: string): string | null {
  if (!input || input.length > 1000) return null;
  try {
    const uri = new URL(input);
    return uri.protocol === "https:" &&
      !uri.username && !uri.password && uri.port === "" &&
      uri.hostname.includes(".") ? uri.href : null;
  } catch {
    return null;
  }
}

function DiscoveryReview({ discovery }: { discovery?: Discovery }) {
  if (!discovery) return null;
  return <div className="mt-5 rounded-xl border border-white/10 bg-[#0b1728] p-4">
    <p className="text-sm font-semibold text-slate-100">Fresh discovery · not accepted source evidence</p>
    <p className="mt-2 text-xs text-slate-400">
      State: {discovery.status ?? "UNKNOWN"} · Queries: {discovery.queries_attempted ?? 0} ·
      Admitted sources: {discovery.source_admissions ?? 0}
    </p>
    {typeof discovery.fresh_provider_responses === "number" &&
      <p className="mt-2 text-xs text-slate-400">Provider responses: {discovery.fresh_provider_responses} ·
      Candidate URLs checked: {discovery.provider_results_seen ?? 0} ·
      Rejected by niche: {discovery.niche_rejected ?? 0} · Rejected by market: {discovery.market_rejected ?? 0}</p>}
    {!!discovery.provider_errors?.length &&
      <p className="mt-2 text-xs text-amber-300">Provider issues: {discovery.provider_errors.join(", ")}</p>}
    {!discovery.candidate_urls?.length
      ? <p className="mt-3 text-xs text-slate-400">No usable new publisher candidates observed. This is not proof that the market has no supply.</p>
      : <div className="mt-3 space-y-3">{discovery.candidate_urls.slice(0, 10).map((c, i) => {
        const target = safeCandidateUrl(c.url);
        return <div key={(c.url ?? "") + i} className="border-t border-white/10 pt-3">
          <p className="text-sm text-slate-100">{c.title || c.url || "Unlabelled discovery"}</p>
          {target && <a className="mt-1 block break-all text-xs text-cyan-300 underline"
            href={target} target="_blank" rel="noopener noreferrer nofollow">Open publisher candidate ↗</a>}
          <p className="mt-2 text-xs text-slate-500">{c.provider ?? "Unverified provider"} ·
            {c.admission_state ?? "NOT_ADMITTED"} · No automatic licence or source approval
          </p>
        </div>;
      })}</div>}
  </div>;
}

export default function ResearchIntakeReview({ intakes, marketReports }: {
  intakes?: ResearchIntake[];
  marketReports?: MarketSearchReport[];
}) {
  return <section className="mt-5 space-y-5">
    {(intakes ?? []).map((intake, i) =>
      <article key={(intake.country ?? "") + i} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
        <h3 className="text-lg font-semibold text-white">{intake.country} · {intake.niche} · source intake</h3>
        <p className="mt-2 text-xs text-amber-200">Original source catalogue: {intake.source_catalogue_state ?? "UNKNOWN"} · Source-rights review required</p>
        <p className="mt-4 text-sm text-slate-300"><strong className="text-white">Buyer question:</strong> {intake.buyer_problem_to_qualify}</p>
        <p className="mt-2 text-sm text-slate-300"><strong className="text-white">Research question:</strong> {intake.research_question}</p>
        <p className="mt-4 text-xs font-semibold uppercase tracking-widest text-slate-400">Required original source classes</p>
        <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-slate-300">
          {(intake.evidence_categories_to_verify ?? []).map((x, j) => <li key={j}>{x}</li>)}
        </ul>
        <p className="mt-4 text-xs font-semibold uppercase tracking-widest text-slate-400">Unsupported inferences to avoid</p>
        <p className="mt-2 text-sm text-slate-300">{(intake.unverified_inferences_to_avoid ?? []).join(" · ")}</p>
        <DiscoveryReview discovery={intake.public_search_diagnostic} />
        <p className="mt-4 text-sm text-amber-200">Next Research-owner review: {intake.next_action ?? "SOURCE_RIGHTS_AND_EDITORIAL_QA"}</p>
      </article>
    )}
    {(marketReports ?? []).map((report, i) => report.current_search_discovery && (
      <article key={(report.country ?? "") + i} className="rounded-2xl border border-white/10 p-5">
        <h3 className="text-lg font-semibold text-white">{report.country} · current Search Fabric discovery</h3>
        <DiscoveryReview discovery={report.current_search_discovery} />
      </article>
    ))}
  </section>;
}
