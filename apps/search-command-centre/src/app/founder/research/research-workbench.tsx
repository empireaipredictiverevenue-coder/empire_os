"use client";

import { useState } from "react";
import ResearchIntakeReview, { type ResearchIntake, type MarketSearchReport } from "./research-intake-review";

type Catalog = {
  products?: Record<string, { title?: string; description?: string }>;
  markets?: string[];
  niches?: string[];
  private_execution_guardrails?: Record<string, unknown>;
};
type ResearchReport = {
  status?: string;
  original_source_count?: number;
  research?: { niche_intake_plans?: ResearchIntake[]; market_reports?: Array<{
    current_search_discovery?: MarketSearchReport["current_search_discovery"];
    country?: string;
    evidence_fingerprint_sha256?: string;
    evidence_ledger?: Array<{
      original_url?: string;
      publisher_host?: string;
      inspected?: boolean;
      page_headings_as_observed?: string[];
      original_passage_anchors_for_editorial_only?: Array<{original_page_excerpt?: string}>;
    }>;
  }> };
  agent_workflow?: { step_receipts?: Array<{ step?: string; state?: string; explanation?: string }> };
};

export default function ResearchWorkbench({ catalog }: { catalog: Catalog }) {
  const [product, setProduct] = useState("empire_research");
  const [country, setCountry] = useState("both");
  const [niche, setNiche] = useState("dental");
  const [depth, setDepth] = useState("quality");
  const [freshDiscovery, setFreshDiscovery] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ResearchReport | null>(null);
  const [error, setError] = useState("");
  async function execute() {
    if (busy) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const response = await fetch("/founder/research/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        body: JSON.stringify({ product, country, niche, depth, fresh_discovery: freshDiscovery }),
      });
      const body = await response.json();
      if (!response.ok) {
        setError(typeof body.detail === "string" ? body.detail : `Research held (${response.status})`);
        return;
      }
      setResult(body as ResearchReport);
    } catch {
      setError("Private Research service unavailable");
    } finally {
      setBusy(false);
    }
  }
  const control = "mt-2 w-full rounded-xl border border-white/20 bg-[#091b2e] px-3 py-3 text-sm text-white";
  return (
    <>
      <section className="mt-7 rounded-2xl border border-white/15 bg-white/[0.04] p-5">
        <h2 className="text-xl font-semibold text-white">Private Research Workbench</h2>
        <p className="mt-2 text-sm text-slate-400">Original source inspection only. No customer send, proposal, payment or editorial release is authorised.</p>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <label className="text-sm text-slate-300">Product
            <select className={control} value={product} onChange={e => setProduct(e.target.value)}>
              {Object.entries(catalog.products ?? {}).map(([id, spec]) => <option key={id} value={id}>{spec.title ?? id}</option>)}
            </select>
          </label>
          <label className="text-sm text-slate-300">Market
            <select className={control} value={country} onChange={e => setCountry(e.target.value)}>
              {(catalog.markets ?? []).map(m => <option key={m} value={m}>{m === "both" ? "UK + USA" : m === "GB" ? "United Kingdom" : "United States"}</option>)}
            </select>
          </label>
          <label className="text-sm text-slate-300">Industry
            <select className={control} value={niche} onChange={e => setNiche(e.target.value)}>
              {(catalog.niches ?? []).map(n => <option key={n} value={n}>{n[0].toUpperCase() + n.slice(1)}</option>)}
            </select>
          </label>
          <label className="text-sm text-slate-300">Source budget
            <select className={control} value={depth} onChange={e => setDepth(e.target.value)}>
              <option value="speed">Speed · 1 source/market</option>
              <option value="balanced">Balanced · 2 sources/market</option>
              <option value="quality">Quality · 3 sources/market</option>
            </select>
          </label>
        </div>
        <label className="mt-5 flex items-center gap-3 text-sm text-slate-300"><input type="checkbox" checked={freshDiscovery} onChange={e => setFreshDiscovery(e.target.checked)} /> Probe fresh Search Fabric candidates (up to four queries, zero auto-admissions)</label>
        <button onClick={execute} disabled={busy} className="mt-6 rounded-xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-[#051421] disabled:opacity-50">
          {busy ? "Inspecting permitted sources…" : "Run private research"}
        </button>
        <p className="mt-3 text-xs text-slate-500">One job at a time; 60-second cooldown per verified Founder session. Sources not independently admitted remain discovery candidates only.</p>
        {error && <p role="alert" className="mt-4 rounded-xl border border-amber-400/30 p-4 text-sm text-amber-200">{error}</p>}
      </section>
      {result && <section className="mt-7 space-y-5">
        <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/[0.04] p-5">
          <p className="text-sm text-slate-400">Execution outcome · not editorial approval</p>
          <h2 className="mt-2 text-lg font-semibold text-white">{result.status ?? "UNKNOWN"}</h2>
          <p className="mt-2 text-sm text-slate-300">Original sources inspected: {result.original_source_count ?? "Unknown"}</p>
        </div>
        {result.research?.market_reports?.map((report, i) => <div key={report.country ?? i} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
          <h3 className="text-lg font-semibold text-white">{report.country} · original source receipts</h3>
          <p className="mt-2 break-all text-xs text-slate-500">Fingerprint: {report.evidence_fingerprint_sha256 ?? "Unavailable"}</p>
          {report.evidence_ledger?.map((source, j) => <div className="mt-4 border-t border-white/10 pt-4" key={source.original_url ?? j}>
            <p className="text-sm font-medium text-white">{source.publisher_host} · {source.inspected ? "Inspected" : "Held"}</p>
            {source.original_url?.startsWith("https://") && <a href={source.original_url} rel="noopener noreferrer" target="_blank" className="mt-1 block break-all text-sm text-cyan-300 underline">Original publisher ↗</a>}
            <p className="mt-2 text-sm text-slate-300">{(source.page_headings_as_observed ?? []).join(" · ") || "Headings unavailable"}</p>
            {(source.original_passage_anchors_for_editorial_only ?? []).slice(0, 2).map((anchor, k) => <p key={k} className="mt-2 border-l border-cyan-400/30 pl-3 text-xs text-slate-400">{anchor.original_page_excerpt}</p>)}
          </div>)}
        </div>)}
        <ResearchIntakeReview intakes={result.research?.niche_intake_plans} marketReports={result.research?.market_reports} />
        {result.agent_workflow?.step_receipts?.map((step, i) => <div key={step.step ?? i} className="rounded-xl border border-white/10 p-4">
          <p className="text-sm font-semibold text-white">{step.step} · {step.state}</p>
          <p className="mt-1 text-sm text-slate-400">{step.explanation}</p>
        </div>)}
        <p className="text-sm text-amber-200">All insights remain subject to authentic Research-owner review, source rights and commercial approval. No buyer need, accepted deal or revenue is implied.</p>
      </section>}
    </>
  );
}
