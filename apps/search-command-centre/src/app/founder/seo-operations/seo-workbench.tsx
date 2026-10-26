"use client";

import { useMemo, useState } from "react";

export type QueryEvidence = {
  query: string;
  historical_sample_status: string;
  commercial_topic_relevance_observed: boolean;
  multiple_distinct_pages_for_query_in_sample: boolean;
  multiple_hosts_same_path_in_sample: boolean;
  historical_hosts_same_path_in_previous_sample: boolean;
  previous: { visible_impressions: number | null; visible_clicks: number | null };
  current: {
    visible_impressions: number | null;
    visible_clicks: number | null;
    gsc_impression_weighted_avg_position: number | null;
    exact_page_count: number;
  };
  current_observed_exact_pages: {url:string; impressions:number; clicks:number; gsc_avg_position:number}[];
  next_original_owner_action: string;
};
export type SearchVisibility = {
  schema_version: string; status: string; source: string; site_url: string;
  as_of: string; previous_window: string[]; current_window: string[];
  observed_queries: number; commercial_relevant_queries_observed: number;
  multi_page_query_overlap_candidates: number;
  historical_www_apex_overlap_candidates: number;
  current_www_apex_overlap_candidates?: number;
  previous_sample: { returned_query_page_rows: number; visible_query_page_impressions:number; visible_query_page_clicks:number };
  current_sample: { returned_query_page_rows: number; visible_query_page_impressions:number; visible_query_page_clicks:number };
  competitor_rankings_verified: false;
  entire_site_traffic_coverage_verified: false;
  verified_revenue: null;
  queries: QueryEvidence[];
};
type SiteJob = {
  id: string; url: string; reason_code: string; priority: string;
  owner: string; state: string; next_action: string; outcome: string;
};
type Props = { visibility: SearchVisibility | null; visibilityReason: string | null;
  jobs: SiteJob[]; resolved: number; liveChecks: number; recordedAt: string | null };
const toolCapabilities: {title:string; module:string; evidence:"gsc"|"technical"|"overlap"|"release"|"pending"; description:string}[] = [
  {title:"Keyword Explorer",module:"GSC + keyword reviewer",evidence:"gsc",description:"Real query/page exposure and original buyer questions; no invented monthly volume."},
  {title:"Position Tracking",module:"rank_history.py",evidence:"gsc",description:"Google Search Console average position; independent daily SERP rank unverified."},
  {title:"Competitor Gap",module:"competitor_gap.py",evidence:"pending",description:"The existing engine is available; external SERP evidence remains degraded."},
  {title:"Site Audit",module:"seo_indexing_health.py",evidence:"technical",description:"Bounded HTTP, canonical, indexability and sitemap tests in original daily owner."},
  {title:"Content & Cannibalisation",module:"cannibalisation.py",evidence:"overlap",description:"Flags observed multiple pages per query for editorial review; no automatic merges."},
  {title:"Backlinks & Authority",module:"backlinks.py / backlink_live_verifier.py",evidence:"pending",description:"Source-verification tooling exists; current verified referring-domain totals unavailable."},
  {title:"AEO / GEO Visibility",module:"ai_visibility.py",evidence:"pending",description:"AI answer/citation evidence engines present; no universal AI visibility score."},
  {title:"Local SEO",module:"local_visibility.py",evidence:"pending",description:"Local grid evaluator present; no independently verified local ranks yet."},
  {title:"SEO Publishing Hands",module:"original guarded releases",evidence:"release",description:"Reviewed, hash-gated, reversible releases with public readback; autonomous unrestricted publishing off."},
  {title:"Buyer Attribution",module:"existing CRM + Ops counters",evidence:"pending",description:"Counts and sales processes exist; source-to-paid-SEO lineage not yet proven."},
  {title:"Media & YouTube SEO",module:"MediaOS / YouTube observations",evidence:"pending",description:"Research adapters exist; content reach and commercial influence require verified sources."},
  {title:"Browser Operator",module:"Jev / browser agent",evidence:"pending",description:"Existing guarded browser work; no unattended live publishing authority."},
];
const pill = {
  gsc: "border-cyan-400/30 bg-cyan-400/10 text-cyan-200",
  technical:"border-cyan-400/30 bg-cyan-400/10 text-cyan-200",
  overlap:"border-amber-400/30 bg-amber-400/10 text-amber-200",
  release:"border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  pending:"border-white/10 bg-white/[0.04] text-slate-400",
};
const evidenceLabel={gsc:"GSC evidence",technical:"Live QA",overlap:"Review candidate",
  release:"Guarded execution",pending:"Evidence held"};
function int(value:number|null|undefined) { return typeof value==="number" ? value.toLocaleString("en-GB"):"Not observed"; }
function pathName(url:string) {
  try { const x=new URL(url); return x.host==="empire-ai.co.uk" || x.host==="www.empire-ai.co.uk" ? x.pathname : "Outside original host"; }
  catch { return "Invalid source URL"; }
}
function safeUrl(url:string) {
  try {const x=new URL(url);return x.protocol==="https:" &&
    (x.hostname==="empire-ai.co.uk"||x.hostname==="www.empire-ai.co.uk") &&
    !x.username&&!x.password&&!x.search&&!x.hash ? x.toString():null;
  } catch{return null;}
}

export default function SEOWorkbench({visibility,visibilityReason,jobs,resolved,liveChecks,recordedAt}:Props) {
  const [tab,setTab]=useState<"keywords"|"jobs"|"tools">("keywords");
  const [search,setSearch]=useState("");
  const [onlyCommercial,setOnlyCommercial]=useState(false);
  const [jobView,setJobView]=useState<"open"|"all"|"verified">("open");
  const queryRows=useMemo(()=> (visibility?.queries??[]).filter(x=>
    (!onlyCommercial||x.commercial_topic_relevance_observed) &&
    (x.query.toLowerCase().includes(search.toLowerCase())||
      x.current_observed_exact_pages.some(p=>p.url.toLowerCase().includes(search.toLowerCase())))),[visibility,search,onlyCommercial]);
  const jobRows=useMemo(()=>jobs.filter(x=>
    (jobView==="all"||(jobView==="verified" ? x.state==="verified":x.state!=="verified")) &&
    (x.url.toLowerCase().includes(search.toLowerCase()) ||
     x.reason_code.toLowerCase().includes(search.toLowerCase()))),[jobs,jobView,search]);
  const current=visibility?.current_sample;
  const previous=visibility?.previous_sample;
  return <section className="mt-7 space-y-6" aria-label="SEO intelligence tool workbench">
    <div className="overflow-hidden rounded-2xl border border-sky-400/15 bg-gradient-to-br from-[#0b203b] via-[#0a172b] to-[#080f1d] p-5 sm:p-7">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div><p className="text-xs font-bold uppercase tracking-[0.18em] text-amber-200">Empire Search Intelligence · Unified tool suite</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white sm:text-3xl">Organic Growth Command Centre</h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">
            Keyword visibility, site health, competitor research, authority, AI visibility and conversion work—connected to the original SEO owners.
            Every finding keeps its source and execution gate.</p></div>
        <span className="rounded-full border border-cyan-400/25 bg-cyan-400/10 px-3 py-2 text-xs font-semibold text-cyan-200">
          {visibility ? "Google evidence connected":"Google visibility unavailable"}
        </span>
      </div>
      <div className="mt-7 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
        {[
          ["Observed keywords",visibility?.observed_queries??null],
          ["Sample impressions",current?.visible_query_page_impressions??null],
          ["Sample clicks",current?.visible_query_page_clicks??null],
          ["Commercial queries",visibility?.commercial_relevant_queries_observed??null],
          ["Technical checks",liveChecks],
          ["SEO actions resolved",resolved],
        ].map(([label,value])=><div key={label} className="rounded-xl border border-white/10 bg-black/20 p-4">
          <p className="min-h-8 text-xs leading-4 text-slate-400">{label}</p>
          <p className="mt-2 text-2xl font-semibold tabular-nums text-white">{int(value as number|null)}</p>
        </div>)}
      </div>
      <p className="mt-4 text-xs text-slate-400">
        {visibility ? <>Google Search Console sampled query/page windows: {visibility.previous_window.join(" to ")} vs {visibility.current_window.join(" to ")}.
          Previous impressions {int(previous?.visible_query_page_impressions)}; current {int(current?.visible_query_page_impressions)}.
          These are <strong className="text-slate-200">not</strong> unique visitors, full site totals, keyword search volume or independent SERP rankings.</>
          : <>Google query/page evidence held: {visibilityReason ?? "unknown"}. Do not substitute hypothetical rankings.</>}
      </p>
    </div>
    <div className="flex flex-wrap gap-2" aria-label="SEO tools">
      {([
        ["keywords","Keyword intelligence"],
        ["jobs","Execution queue"],
        ["tools","All SEO tools"],
      ] as const).map(([value,label])=><button type="button" key={value}
        aria-pressed={tab===value} onClick={()=>{setTab(value);setSearch("");}}
        className={"rounded-xl border px-4 py-2.5 text-sm font-semibold transition "+
          (tab===value?"border-amber-400/40 bg-amber-400/15 text-amber-100":"border-white/10 bg-white/[0.03] text-slate-300 hover:bg-white/10")}>
        {label}</button>)}
    </div>
    {tab!=="tools"&&<div className="flex flex-wrap items-center gap-4">
      <input value={search} onChange={e=>setSearch(e.target.value)} placeholder={tab==="keywords"?"Filter query or page URL":"Filter page or problem"}
        aria-label="Filter SEO evidence" className="min-w-[220px] flex-1 rounded-xl border border-white/15 bg-[#0a1425] px-4 py-3 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/40" />
      {tab==="keywords" ? <label className="flex items-center gap-2 text-sm text-slate-300">
        <input type="checkbox" checked={onlyCommercial} onChange={e=>setOnlyCommercial(e.target.checked)}/>Commercial themes only
      </label> : <select value={jobView} onChange={e=>setJobView(e.target.value as "open"|"all"|"verified")}
        aria-label="SEO job status" className="rounded-lg border border-white/15 bg-[#0a1425] p-3 text-sm text-white">
        <option value="open">Open jobs</option><option value="all">All jobs</option><option value="verified">Resolved</option>
      </select>}
    </div>}
    {tab==="keywords"&&<div className="overflow-hidden rounded-xl border border-white/10 bg-[#0a1425]">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 px-5 py-4">
        <h3 className="font-semibold text-slate-100">Keyword explorer · observed Google data</h3>
        <span className="text-xs text-slate-400">{queryRows.length} sampled queries</span>
      </header>
      {!visibility?<p className="px-5 py-7 text-sm text-amber-200">No trusted private Google query/page receipt available.</p>:
        queryRows.length===0?<p className="px-5 py-7 text-sm text-slate-400">No matching observed queries. This does not mean search demand is zero.</p>:
        <div className="divide-y divide-white/10">{queryRows.map(q=><article key={q.query} className="p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="max-w-[840px]">
              <p className="font-medium leading-6 text-white">{q.query}</p>
              <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
                {q.commercial_topic_relevance_observed&&<span className="rounded-md border border-amber-400/25 bg-amber-400/10 px-2 py-1 text-amber-200">Commercial topic</span>}
                {q.multiple_distinct_pages_for_query_in_sample&&<span className="rounded-md border border-sky-400/25 bg-sky-400/10 px-2 py-1 text-sky-200">Multiple pages · review intent</span>}
                <span className="rounded-md border border-white/10 px-2 py-1 text-slate-400">{q.historical_sample_status.replaceAll("_"," ").toLowerCase()}</span>
              </div>
            </div>
            <div className="flex gap-5 text-right">
              <div><p className="text-xs text-slate-500">Impressions</p><p className="mt-1 font-semibold tabular-nums">{int(q.current.visible_impressions)}</p></div>
              <div><p className="text-xs text-slate-500">Clicks</p><p className="mt-1 font-semibold tabular-nums">{int(q.current.visible_clicks)}</p></div>
              <div><p className="text-xs text-slate-500">GSC avg pos.</p><p className="mt-1 font-semibold tabular-nums">{q.current.gsc_impression_weighted_avg_position?.toFixed(1)??"—"}</p></div>
            </div>
          </div>
          {q.current_observed_exact_pages.length>0&&<div className="mt-3 flex flex-wrap gap-2">{q.current_observed_exact_pages.slice(0,5).map(p=>{
            const href=safeUrl(p.url);
            return href?<a key={p.url} href={href} target="_blank" rel="noopener noreferrer" className="rounded-md border border-white/10 px-2 py-1 text-xs text-sky-200 hover:bg-white/10">{pathName(p.url)} · {p.impressions} impressions</a>
              :<span key={p.url} className="text-xs text-slate-500">Untrusted URL omitted</span>;
          })}</div>}
          <p className="mt-3 text-xs text-slate-400">Next owner action: {q.next_original_owner_action.replaceAll("_"," ").toLowerCase()}. No page publication authorised from this observation.</p>
        </article>)}</div>}
    </div>}
    {tab==="jobs"&&<div className="overflow-hidden rounded-xl border border-white/10 bg-[#0a1425]">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 px-5 py-4">
        <h3 className="font-semibold text-white">SEO agent action queue</h3>
        <span className="text-xs text-slate-400">{jobRows.length} jobs · observed {recordedAt ?? "unknown"}</span>
      </header>
      <div className="divide-y divide-white/10">{jobRows.map(j=><article key={j.id} className="flex flex-wrap justify-between gap-3 px-5 py-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className={"rounded-md border px-2 py-1 text-xs font-semibold "+(j.state==="verified"?pill.release:j.state==="tested"?pill.gsc:pill.overlap)}>{j.state}</span>
            <span className="text-xs text-slate-400">{j.priority} · {j.reason_code.replaceAll("_"," ")}</span></div>
          <p className="mt-2 break-all text-sm font-semibold text-white">{pathName(j.url)}</p>
          <p className="mt-2 text-xs text-slate-400">Owner: {j.owner.replaceAll("_"," ")} · {j.state==="verified"?j.outcome.replaceAll("_"," "):j.next_action.replaceAll("_"," ")}</p>
        </div>
        {safeUrl(j.url)&&<a href={safeUrl(j.url)!} target="_blank" rel="noopener noreferrer" className="h-fit rounded-lg border border-white/15 px-3 py-2 text-xs font-semibold text-sky-200">Inspect</a>}
      </article>)}
      {jobRows.length===0&&<p className="p-5 text-sm text-slate-400">No matching jobs in the original action receipt.</p>}</div>
    </div>}
    {tab==="tools"&&<div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {toolCapabilities.map(t=><article key={t.title} className="rounded-xl border border-white/10 bg-[#0a1425] p-5">
        <div className="flex flex-wrap items-start justify-between gap-3"><h3 className="font-semibold text-white">{t.title}</h3>
          <span className={"rounded-md border px-2 py-1 text-[11px] font-semibold "+pill[t.evidence]}>{evidenceLabel[t.evidence]}</span></div>
        <p className="mt-3 text-xs font-medium text-sky-200">{t.module}</p>
        <p className="mt-2 text-sm leading-6 text-slate-400">{t.description}</p>
      </article>)}
    </div>}
    <p className="text-xs leading-6 text-slate-500">SEO intelligence is read-only here. No advertising spend, bought backlinks, fabricated rankings, unauthorised publishing or assumed payment. Original publisher releases and approved commercial owners keep execution authority.</p>
  </section>;
}
