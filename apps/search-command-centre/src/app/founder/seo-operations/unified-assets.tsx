import { ASSETS, loadUnifiedAssets } from "./unified-assets-data";

export function UnifiedAssetsView({ start, end, checkedAt, pages, jev, browser }: Awaited<ReturnType<typeof loadUnifiedAssets>>) {
  const assets = pages?.assets ?? ASSETS.map(([name, url]) => ({ name, url, metrics: null }));
  return <section aria-labelledby="unified-assets-heading" className="mt-7 min-w-0 rounded-2xl border border-cyan-400/25 bg-[#091426] p-4 sm:p-6">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><p className="text-xs font-semibold uppercase tracking-widest text-cyan-300">First-party assets · Private execution evidence</p>
        <h2 id="unified-assets-heading" className="mt-2 text-2xl font-semibold">Unified Search Assets &amp; Execution</h2></div>
      <span className="rounded-full border border-amber-300/25 px-3 py-1 text-xs text-amber-200">OBSERVE · No execution authority</span>
    </div>
    <p className="mt-3 text-sm leading-6 text-slate-300">Four allowlisted Empire AI landing assets. Observed page-only GSC evidence for {start} – {end}, finalized reporting state. Publication and microsite release rights remain with ASTRA.</p>
    <p className="mt-2 text-xs leading-6 text-slate-400">{pages ? `${pages.returned} returned page rows; this may be a partial sample.` : "Page-only source unavailable or invalid. Asset performance is unknown."} Separate dimensions: these metrics are never summed or compared with the property date-dimension chart. Presence is not proof of Google indexing, sessions, leads or revenue.</p>
    <div className="mt-5 grid min-w-0 gap-3 md:grid-cols-2">
      {assets.map(asset => <article key={asset.url} className="min-w-0 rounded-xl border border-white/10 bg-[#060e1e] p-4">
        <h3 className="font-semibold text-slate-100">{asset.name}</h3>
        <a href={asset.url} className="mt-2 block break-all text-xs leading-5 text-cyan-300 underline decoration-cyan-300/30">{asset.url}</a>
        {asset.metrics ? <><p className="mt-4 text-xs text-amber-200">Observed page-only</p>
          <dl className="mt-3 grid grid-cols-2 gap-4 text-sm">
            {[["Clicks", asset.metrics.clicks.toLocaleString("en-GB")], ["Impressions", asset.metrics.impressions.toLocaleString("en-GB")],
              ["CTR", `${(asset.metrics.ctr * 100).toFixed(2)}%`], ["GSC average position", asset.metrics.position.toFixed(1)]].map(([label, value]) =>
              <div key={label}><dt className="text-xs text-slate-400">{label}</dt><dd className="mt-1 font-semibold tabular-nums">{value}</dd></div>)}
          </dl></> : <p className="mt-4 text-sm leading-6 text-amber-200">{pages ? "Not present in returned rows · metrics unknown" : "Metrics unknown · source unavailable"}</p>}
      </article>)}
    </div>
    <div className="mt-5 grid gap-3 md:grid-cols-2">
      <article className="min-w-0 rounded-xl border border-cyan-400/20 p-4"><h3 className="font-semibold">Jev department review</h3>
        <p className="mt-3 text-sm text-cyan-200">{jev ? `${jev.tasks} tasks in returned department review` : "Private Jev source unavailable or invalid"}</p>
        <p className="mt-2 text-sm leading-6 text-slate-400">{jev ? "0 inference calls · 0 scores generated. Review evidence only; no execution authority." : "Task count, inference calls and scores are unknown. No execution is inferred."} Existing department owners retain their assignments. No inference or spend is requested.</p>
      </article>
      <article className="min-w-0 rounded-xl border border-cyan-400/20 p-4"><h3 className="font-semibold">Original Browser Operator</h3>
        <p className="mt-3 text-sm text-cyan-200">{browser ? `${browser.tasks} all recent tasks · feed capped at 25` : "Private Browser Operator feed unavailable or invalid"}</p>
        <p className="mt-2 text-sm leading-6 text-slate-400">All recent tasks, not verified SEO actions or lifetime totals. No revenue or automatic execution is implied. Original Browser Operator retains execution ownership.</p>
        <a href="/founder/browser-tasks" className="mt-3 inline-block text-sm text-cyan-300 underline">Open private browser tasks</a>
      </article>
    </div>
    <aside aria-label="Separate portfolio ownership" className="mt-5 rounded-xl border border-amber-300/20 p-4 text-sm leading-6 text-slate-300">
      <p className="font-semibold text-amber-200">Separate portfolio boundaries</p>
      <p className="mt-2">National Storm Hub has a separate property and owner. Lead Smart roofing content is separately gated. Neither is treated as an Empire-owned microsite or included in empire-ai.co.uk analytics here. Current portfolio destinations are unverified; no links are inferred.</p>
    </aside>
    <p className="mt-4 break-words text-xs leading-6 text-slate-400">Read checked at {checkedAt} (UTC); read time is not source publication time. GSC source: google_search_console · sc-domain:empire-ai.co.uk · dimensions=[page] · data_state=final. Activity sources: private Jev department review and Founder recent browser-task feed; source event freshness is unknown. Each read is bounded to 4 seconds and 256 KiB. No route checks, crawl, submission or publication performed.</p>
  </section>;
}
export default async function UnifiedAssets() { return <UnifiedAssetsView {...await loadUnifiedAssets()} />; }
