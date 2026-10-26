"use client";

import { useMemo, useState } from "react";

export type BuyerTeamRow = {
  domain: string;
  tier: string;
  action: string;
  role: string;
  contact: string;
  sectors: string[];
  matchedSectors: string[];
  sectorResearchState: string;
  observedOverflow: number;
  siteCorroborated: boolean;
  sourceCurrent: boolean;
};
export type BuyerTeamView = {
  generatedAt: string;
  stale: boolean;
  teamCount: number;
  reviewCount: number;
  sectorFitCount: number;
  geoVerifiedCount: number;
  demandState: string;
  rows: BuyerTeamRow[];
};

function readable(value: string) {
  return value.toLowerCase().replaceAll("_", " ").replace(/^./, (x) => x.toUpperCase());
}
function lane(row: BuyerTeamRow) {
  if (row.action === "NO_NEW_SEND_RECONCILE_SUPPRESSION_OR_DELIVERY") return "HOLD";
  if (row.action === "REVIEW_LIVE_RELATIONSHIP_AND_QUALIFY_BUYER_PILOT") return "CONVERSATION";
  if (row.action === "REVIEW_PRIOR_THREAD_FOR_RESPONSE_NO_DUPLICATE_FIRST_TOUCH") return "PRIOR CONTACT";
  if (row.tier === "ECOSYSTEM_RESEARCH") return "ECOSYSTEM";
  if (row.tier === "FOUNDER_REVIEW_ONLY") return "FOUNDER REVIEW";
  return "RESEARCH";
}
function tone(value: string) {
  if (value === "CONVERSATION") return "border-emerald-400/30 bg-emerald-400/10 text-emerald-200";
  if (value === "FOUNDER REVIEW") return "border-sky-400/30 bg-sky-400/10 text-sky-200";
  if (value === "PRIOR CONTACT") return "border-amber-400/30 bg-amber-400/10 text-amber-200";
  if (value === "HOLD") return "border-rose-400/30 bg-rose-400/10 text-rose-200";
  return "border-white/10 bg-white/5 text-slate-200";
}
export default function BuyerAcquisitionTeamTable({ data }: { data: BuyerTeamView }) {
  const [search, setSearch] = useState("");
  const [sector, setSector] = useState("ALL");
  const [state, setState] = useState("ALL");
  const [showAll, setShowAll] = useState(false);
  const sectors = useMemo(() => Array.from(new Set(data.rows.flatMap((x) =>
    [...x.sectors, ...x.matchedSectors]))).sort(), [data.rows]);
  const filtered = useMemo(() => data.rows.filter((row) => {
    const query = search.toLowerCase().trim();
    return (!query || row.domain.includes(query) || row.action.toLowerCase().includes(query))
      && (sector === "ALL" || row.sectors.includes(sector) || row.matchedSectors.includes(sector))
      && (state === "ALL" || lane(row) === state);
  }), [data.rows, search, sector, state]);
  const visible = showAll ? filtered : filtered.slice(0, 30);
  const counts = [
    { label: "Researched companies", value: data.teamCount, note: "Research candidates, not customers" },
    { label: "Founder-reviewed evidence", value: data.reviewCount, note: "Not contracted buyers" },
    { label: "First-party sector fit", value: data.sectorFitCount, note: "Research matches to current overflow" },
    { label: "Accepted ZIP coverage", value: data.geoVerifiedCount, note: "No matched buyer coverage verified" },
  ];
  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {counts.map(({ label, value, note }) => <div key={label} className="rounded-xl border border-white/10 bg-[#081327] p-4">
          <p className="text-xs font-semibold text-slate-400">{label}</p>
          <p className="mt-2 text-3xl font-bold tabular-nums text-white">{value.toLocaleString("en-GB")}</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">{note}</p>
        </div>)}
      </div>
      <p className="mt-4 text-xs text-slate-400" role="status">
        Snapshot {data.generatedAt.replace("T", " ").slice(0, 19)} UTC · Demand source {readable(data.demandState)}.
        {data.stale && <span className="ml-2 font-semibold text-amber-200">Evidence is stale; no current-state claims.</span>}
      </p>
      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        <label className="text-xs font-semibold text-slate-300">
          Search company or next task
          <input aria-label="Search buyer companies" type="search" value={search}
            onChange={(e) => { setSearch(e.target.value); setShowAll(false); }}
            placeholder="Company, pilot, verification..." className="mt-2 w-full rounded-lg border border-white/15 bg-[#081327] px-3 py-2.5 text-sm text-white outline-none focus:border-sky-400" />
        </label>
        <label className="text-xs font-semibold text-slate-300">
          Industry
          <select aria-label="Filter companies by industry" value={sector}
            onChange={(e) => { setSector(e.target.value); setShowAll(false); }}
            className="mt-2 w-full rounded-lg border border-white/15 bg-[#081327] px-3 py-2.5 text-sm text-white">
            <option value="ALL">All industries</option>
            {sectors.map((x) => <option key={x} value={x}>{readable(x)}</option>)}
          </select>
        </label>
        <label className="text-xs font-semibold text-slate-300">
          Workstream
          <select aria-label="Filter buyer acquisition workstream" value={state}
            onChange={(e) => { setState(e.target.value); setShowAll(false); }}
            className="mt-2 w-full rounded-lg border border-white/15 bg-[#081327] px-3 py-2.5 text-sm text-white">
            {["ALL", "CONVERSATION", "PRIOR CONTACT", "FOUNDER REVIEW", "RESEARCH", "HOLD", "ECOSYSTEM"].map((x) =>
              <option key={x} value={x}>{x === "ALL" ? "All workstreams" : readable(x)}</option>)}
          </select>
        </label>
      </div>
      <div className="mt-5 flex flex-wrap items-center justify-between gap-2 text-sm text-slate-400">
        <p><strong className="text-white">{filtered.length.toLocaleString("en-GB")}</strong> companies matching current filters</p>
        <p>Sorted by live commercial research priority; no verified contract, traffic or payout implied.</p>
      </div>
      <div className="mt-3 space-y-3">
        {visible.map((row) => {
          const category = lane(row);
          return <article key={row.domain} className="rounded-xl border border-white/10 bg-[#091529] p-4 sm:p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="font-semibold tracking-tight text-white">{row.domain}</h3>
                <p className="mt-1 text-xs text-slate-400">Relationship: {readable(row.contact)}</p>
              </div>
              <span className={"rounded-md border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide " + tone(category)}>{category}</span>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-200"><span className="font-semibold text-sky-300">Next:</span> {readable(row.action)}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {row.matchedSectors.map((s) => <span key={s} className="rounded-md border border-sky-300/20 bg-sky-400/5 px-2 py-1 text-xs text-sky-200">{readable(s)} · first-party research match</span>)}
              {!row.matchedSectors.length && row.sectors.slice(0, 3).map((s) =>
                <span key={s} className="rounded-md border border-white/10 px-2 py-1 text-xs text-slate-400">{readable(s)} · discovery label</span>)}
            </div>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-3 text-xs text-slate-400">
              <span>{row.siteCorroborated ? "Official website role corroborated" : "Buyer role not independently corroborated"} · {row.sourceCurrent ? "Due diligence current" : "Due diligence pending/stale"}</span>
              <a href={"https://" + row.domain + "/"} target="_blank" rel="noopener noreferrer"
                className="font-semibold text-sky-300 underline underline-offset-4 hover:text-white">Review first-party website</a>
            </div>
          </article>;
        })}
        {visible.length === 0 && <p className="rounded-lg border border-white/10 p-5 text-sm text-slate-400">No companies match these filters. Change the workstream or industry to inspect the full sourced queue.</p>}
      </div>
      {!showAll && filtered.length > visible.length &&
        <button type="button" onClick={() => setShowAll(true)}
          className="mt-5 w-full rounded-lg border border-sky-300/30 bg-sky-400/10 px-4 py-3 text-sm font-semibold text-sky-200 hover:bg-sky-400/20">
          Show all {filtered.length.toLocaleString("en-GB")} matching companies
        </button>}
      {showAll && filtered.length > 30 &&
        <button type="button" onClick={() => setShowAll(false)}
          className="mt-5 w-full rounded-lg border border-white/10 px-4 py-3 text-sm text-slate-300 hover:bg-white/5">Show top 30</button>}
      <p className="mt-5 border-t border-white/10 pt-4 text-xs leading-5 text-slate-500">Source: Original EmpireOS Buyer Acquisition Team evidence · no new CRM, email, database, payments or outbound permissions · contact details and private message contents intentionally excluded.</p>
    </>
  );
}
