import Link from "next/link";
import { connection } from "next/server";
import { getSeoDepartmentReview, type SeoDepartmentReview } from "@/lib/search-api";
import { ObservedGscTrend } from "./observed-trend";

export const metadata = {
  title: "SEO Evidence | Empire AI Search Command Centre",
  robots: { index: false, follow: false },
};

function Metric({ label, value, note }: {
  label: string; value: number; note: string;
}) {
  return <div className="metric-card">
    <p className="text-xs uppercase tracking-[.12em] text-slate-400">{label}</p>
    <p className="mt-3 text-3xl font-semibold text-white">{value.toLocaleString("en-GB")}</p>
    <p className="mt-2 text-xs leading-5 text-slate-500">{note}</p>
  </div>;
}
function State({ verified }: { verified: boolean }) {
  return <span className={"rounded-full border px-3 py-1 text-xs font-medium " + (verified
    ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"
    : "border-amber-400/30 bg-amber-400/10 text-amber-200")}>
    {verified ? "Evidence observed" : "Not verified"}
  </span>;
}
const tasks: Record<string, string> = {
  ORGANIC_RELEASE_SOURCE_COMMIT_NOT_VERIFIED: "Confirm canonical organic-release commit provenance.",
  INDUSTRY_CAMPAIGN_RELEASE_NOT_VERIFIED: "Verify the real industry-campaign measurement release.",
  HISTORIC_GSC_404_EDITORIAL_TRIAGE_PENDING: "Review historical URLs against genuinely equivalent content.",
  SEMANTIC_ORIGINAL_CONTENT_EDITORIAL_REVIEW_PENDING: "Improve original HVAC heat-pump and solar PV explanations.",
  INDEPENDENT_AI_ANSWER_CITATION_EVIDENCE_MISSING: "Gather independent AI citation and GEO observations.",
  INDEPENDENT_SERP_RANKING_OBSERVATIONS_NOT_VERIFIED_BY_THIS_REVIEW: "Obtain live, engine- and locale-attributed keyword ranks.",
  ORGANIC_BUYER_ENQUIRY_AND_REALIZED_REVENUE_NOT_PROVEN: "Match a genuine organic enquiry to a canonical CRM and payment receipt.",
  EDITORIAL_RESEARCH_REQUIRES_OWNER_PUBLICATION_DECISION: "Review original research campaigns before any publication.",
};

function Content({ report: d }: { report: SeoDepartmentReview }) {
  return <>
    <section aria-label="Google Search Console sample" className="mt-8">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="text-xl font-semibold text-white">Google Search Console · page sample</h2>
        <p className="text-xs text-slate-400">Final-data window {d.gsc_final_page_window.join(" to ")}</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Returned page rows" value={d.gsc_returned_page_rows} note="Partial page sample, not unique visitors." />
        <Metric label="Reported impressions" value={d.gsc_returned_page_sample_impressions} note="Only in these returned rows." />
        <Metric label="Reported clicks" value={d.gsc_returned_page_sample_clicks} note="Not proof of a customer or conversion." />
        <Metric label="Historical 404 rows" value={d.legacy_missing_404_count_in_returned_page_sample} note={d.legacy_missing_404_impressions_in_returned_page_sample + " impressions; " + d.legacy_missing_404_clicks_in_returned_page_sample + " clicks."} />
      </div>
    </section>
    <ObservedGscTrend chart={d.gsc_daily_chart} />
    <div className="mt-7 grid gap-6 xl:grid-cols-2">
      <section className="panel">
        <p className="eyebrow">Original content recovery</p>
        <h2 className="mt-1 text-xl font-semibold text-white">404 editorial priorities</h2>
        <p className="mt-2 text-sm leading-6 text-slate-400">Review topical equivalence before any redirect. Keep off-core URLs retired.</p>
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <Metric label="Core topic reviews" value={d.legacy_404_core_topic_editorial_review_count} note="Existing product and industry content." />
          <Metric label="Off-core, keep retired" value={d.legacy_404_off_core_retain_404_count} note="No mass redirects or synthetic pages." />
        </div>
        <dl className="mt-5 space-y-2 text-xs text-slate-300">
          {Object.entries(d.legacy_404_editorial_category_counts).map(([key, value]) =>
            <div className="flex justify-between gap-3 border-b border-white/10 pb-2" key={key}>
              <dt className="break-all">{key.replaceAll("_", " ").toLowerCase()}</dt>
              <dd className="font-semibold text-white">{value}</dd>
            </div>)}
        </dl>
      </section>
      <section className="panel">
        <p className="eyebrow">Existing Search Fabric</p>
        <h2 className="mt-1 text-xl font-semibold text-white">Cached evidence health</h2>
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <Metric label="Fresh cache envelopes" value={d.search_fabric_cache_fresh_candidates_24h} note="24h TTL; not current Google rank positions." />
          <Metric label="Stale records" value={d.search_fabric_cache_stale_candidates} note="Excluded from fresh-candidate counts." />
          <Metric label="Total cache files" value={d.search_fabric_cache_files_observed} note="Existing bounded local inventory." />
          <Metric label="Invalid envelopes" value={d.search_fabric_cache_invalid_envelopes} note="Not promoted into verified evidence." />
        </div>
        <div className="mt-5 flex flex-wrap items-center justify-between gap-2 border-t border-white/10 pt-5 text-sm">
          <span>Independent Google ranking positions</span>
          <State verified={d.independent_google_rank_positions_verified} />
        </div>
      </section>
      <section className="panel">
        <p className="eyebrow">Owned site and content</p>
        <h2 className="mt-1 text-xl font-semibold text-white">Editorial work</h2>
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <Metric label="Priority pages reviewed" value={d.semantic_live_priority_pages_checked} note="Owned first-party HTML observations." />
          <Metric label="Copy reviews pending" value={d.semantic_editorial_review_candidates} note="HVAC heat pumps and solar PV context." />
          <Metric label="Specialist desks" value={d.growth_specialist_desks} note="Existing marketing_growth department." />
          <Metric label="Research campaigns" value={d.research_campaigns} note="Draft-only; no automatic publication." />
        </div>
      </section>
      <section className="panel">
        <p className="eyebrow">Proof boundaries</p>
        <h2 className="mt-1 text-xl font-semibold text-white">Organic revenue chain</h2>
        <div className="mt-5 space-y-4 text-sm">
          {([
            ["Owned industry-to-commercial links", d.semantic_owned_pages_commercial_route_verified],
            ["Independent search-engine rankings", d.search_rankings_verified],
            ["AI answer citation observations", d.external_ai_answer_citation_verified],
            ["GEO mentions", d.external_geo_mentions_verified],
            ["Real organic buyer enquiries", d.buyer_enquiries_verified],
            ["Realised organic revenue", d.realised_revenue_verified],
          ] as [string, boolean][]).map(([label, verified]) =>
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-3" key={label}>
              <span className="text-slate-300">{label}</span><State verified={verified} />
            </div>)}
        </div>
      </section>
    </div>
    <section className="panel mt-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><p className="eyebrow">Department checklist</p>
          <h2 className="mt-1 text-xl font-semibold text-white">Remaining evidence and release gaps</h2></div>
        <span className="rounded-full border border-amber-400/30 bg-amber-400/10 px-3 py-1 text-xs text-amber-200">{d.open_gates.length} open</span>
      </div>
      <ul className="mt-5 divide-y divide-white/10">
        {d.open_gates.map(gate => <li className="flex gap-3 py-3" key={gate}>
          <span aria-hidden="true" className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-amber-300" />
          <div><p className="text-sm text-slate-200">{tasks[gate] ?? "Unreviewed gate: " + gate}</p>
            <p className="mt-1 break-all font-mono text-[10px] text-slate-600">{gate}</p></div>
        </li>)}
      </ul>
    </section>
  </>;
}

export default async function SeoDepartmentPage() {
  await connection();
  const response = await getSeoDepartmentReview();
  const d = response.ok ? response.data : null;
  const trusted = d?.schema_version === "empire.search_growth.department_integration.v1"
    && d.mode === "OBSERVE" && d.execution_authority === "NONE"
    && d.customer_identifiers_disclosed === false
    && d.publisher_mutation_authorized === false;
  return <main className="min-h-screen bg-[#07100d] px-5 py-8 text-slate-100 lg:px-10 lg:py-12">
    <div className="mx-auto max-w-7xl">
      <nav aria-label="Search Command Centre navigation" className="mb-8 flex flex-wrap gap-5 text-xs font-semibold uppercase tracking-[.13em]">
        <Link href="/" className="text-cyan-300 hover:text-cyan-100 focus-visible:outline focus-visible:outline-cyan-300">← Search Command Centre</Link>
        <Link href="/technical" className="text-slate-400 hover:text-white focus-visible:outline focus-visible:outline-cyan-300">Technical evidence</Link>
        <Link href="/revenue" className="text-slate-400 hover:text-white focus-visible:outline focus-visible:outline-cyan-300">Revenue attribution</Link>
      </nav>
      <header className="border-b border-white/10 pb-8">
        <p className="eyebrow">Empire AI · Predictive Revenue · SEO/AEO/GEO/A2A</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white md:text-5xl">Unified SEO evidence</h1>
        <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-400">
          First-party GSC, historical AEO recovery, semantic quality, Search Fabric cache and growth research.
          Cached sources are not Google rankings; impressions are not customers.
        </p>
        <div className="mt-5"><State verified={trusted} /></div>
      </header>
      {!trusted || !d ? <section className="panel mt-8" role="status">
        <h2 className="text-xl font-semibold text-white">Department evidence unavailable</h2>
        <p className="mt-3 text-sm text-slate-400">The source is unavailable or unverified. No zero counts or invented ranks are substituted.</p>
        <p className="mt-3 font-mono text-xs text-slate-500">
          {response.status === 503 ? "Source review held" : response.reason ?? "Server-only connection pending"}
        </p>
      </section> : <Content report={d} />}
      <footer className="mt-8 border-t border-white/10 pt-6 text-xs text-slate-500">
        OBSERVE only · Existing loopback Search Intelligence API · No cookies, tracking, redirects, publication or database writes.
      </footer>
    </div>
  </main>;
}
