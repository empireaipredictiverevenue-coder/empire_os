import { dailyTrend, dailyWindow, validateDaily, type DailySeries } from "./gsc-daily";

export async function loadDailyHistory(now = new Date(), reader: typeof fetch = fetch) {
  const window = dailyWindow(now);
  try {
    const params = new URLSearchParams({ start_date: window.start, end_date: window.end, limit: "30" });
    const response = await reader(`http://127.0.0.1:8771/v1/search/search-console/daily?${params}`, {
      cache: "no-store", redirect: "error", signal: AbortSignal.timeout(16000), headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error("Unavailable");
    const body = await response.text();
    if (body.length > 65536) throw new Error("Oversized evidence");
    return { ...window, series: validateDaily(JSON.parse(body), window.start, window.end), checkedAt: now.toISOString() };
  } catch {
    return { ...window, series: null, checkedAt: now.toISOString() };
  }
}
const number = (n: number) => n.toLocaleString("en-GB");
const label = (date: string) => new Date(`${date}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
function Plot({ series, metric }: { series: DailySeries; metric: "clicks" | "impressions" }) {
  const color = metric === "impressions" ? "#7dd3fc" : "#fcd34d";
  const max = Math.max(1, ...series.rows.map(row => row[metric]));
  const x = (i: number) => 48 + i * 636 / 29;
  const y = (value: number) => 142 - value / max * 110;
  return <div className="min-w-0 rounded-xl border border-white/10 bg-[#060e1e] p-3">
    <h3 className="text-sm font-semibold capitalize" style={{ color }}>{metric === "impressions" ? "━" : "●"} {metric}</h3>
    <svg viewBox="0 0 720 180" className="mt-2 w-full" role="img" aria-label={`Daily GSC ${metric}, ${series.start} to ${series.end}. Scale zero to ${max}. Missing days have gaps. Exact values in daily evidence table.`}>
      {[0, max / 2, max].map(value => <g key={value}>
        <line x1="48" x2="684" y1={y(value)} y2={y(value)} stroke="#334155" strokeDasharray="3 5" />
        <text x="40" y={y(value) + 4} textAnchor="end" fill="#cbd5e1" fontSize="12">{Number.isInteger(value) ? value : value.toFixed(1)}</text>
      </g>)}
      {series.days.map((day, i) => {
        if (!day.row) return <text key={day.date} x={x(i)} y="155" textAnchor="middle" fill="#94a3b8" fontSize="12">×</text>;
        const prior = series.days[i - 1]?.row;
        return <g key={day.date}>
          {prior && <line x1={x(i - 1)} y1={y(prior[metric])} x2={x(i)} y2={y(day.row[metric])} stroke={color} strokeWidth="2.5" />}
          <circle cx={x(i)} cy={y(day.row[metric])} r={metric === "clicks" ? 4 : 3} fill={color}><title>{`${day.date}: ${day.row[metric]} ${metric}`}</title></circle>
        </g>;
      })}
      {[0, 9, 19, 29].map(i => <text key={i} x={x(i)} y="176" textAnchor="middle" fill="#cbd5e1" fontSize="13">{label(series.days[i].date)}</text>)}
    </svg>
    <p className="text-xs leading-5 text-slate-300">{dailyTrend(series, metric)}</p>
  </div>;
}
export function GSCHistoryView({ series, start, end, checkedAt }: Awaited<ReturnType<typeof loadDailyHistory>>) {
  const latest = series?.rows.at(-1)?.date;
  const lag = latest ? Math.floor((Date.parse(checkedAt.slice(0, 10)) - Date.parse(latest)) / 86400000) : null;
  return <section aria-labelledby="gsc-history-heading" className="mt-7 rounded-xl border border-sky-400/25 bg-[#091426] p-4 sm:p-6">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><p className="text-xs font-semibold uppercase tracking-widest text-sky-300">Property performance · Google Search Console</p>
        <h2 id="gsc-history-heading" className="mt-2 text-xl font-semibold sm:text-2xl">30 days of search visibility</h2>
        <p className="mt-2 text-sm text-slate-300">{label(start)} – {label(end)} · {start.slice(0, 4)} · ending three days before today (UTC)</p></div>
      <span className="rounded-full border border-amber-300/25 px-3 py-1 text-xs text-amber-200">Delayed GSC reporting</span>
    </div>
    {!series || !series.rows.length ? <div role="status" className="mt-5 rounded-lg border border-amber-300/25 p-4 text-sm text-amber-100">
      <p className="font-semibold">Daily GSC history unavailable</p>
      <p className="mt-2">{series ? "The source returned no observed daily rows for this window." : "The private date-dimension source could not be read or validated."} No traffic totals or zero-filled history are inferred.</p>
    </div> : <>
      <dl className="my-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[["Reported impressions", number(series.impressions)], ["Reported clicks", number(series.clicks)], ["Observed-day CTR", series.ctr === null ? "Unavailable" : `${(series.ctr * 100).toFixed(2)}%`], ["Days observed / missing", `${series.rows.length} / ${30 - series.rows.length}`]].map(([name, value]) =>
          <div key={name} className="rounded-lg border border-white/10 p-3"><dt className="text-xs text-slate-400">{name}</dt><dd className="mt-2 text-xl font-semibold tabular-nums">{value}</dd></div>)}
      </dl>
      <p className="mb-4 text-xs leading-6 text-slate-300">Latest reported day: {latest} · {lag} days behind check date. Totals cover reported days only. CTR = reported clicks ÷ reported impressions; undefined when impressions are zero.</p>
      <div className="grid gap-4 lg:grid-cols-2"><Plot series={series} metric="impressions" /><Plot series={series} metric="clicks" /></div>
      <p className="mt-3 text-xs text-slate-400">Separate vertical scales preserve click detail. × marks a missing day; lines stop at gaps. A reported zero remains zero.</p>
      <details className="mt-5 rounded-lg border border-white/10 p-3">
        <summary className="cursor-pointer text-sm font-semibold text-sky-200">Daily evidence table · all 30 dates</summary>
        <div className="mt-3 overflow-x-auto"><table className="w-full text-left text-xs tabular-nums">
          <caption className="pb-3 text-left text-slate-400">GSC property date rows; missing values are unreported, not zero.</caption>
          <thead><tr>{["Date", "Impressions", "Clicks", "Evidence"].map(h => <th key={h} scope="col" className="p-2">{h}</th>)}</tr></thead>
          <tbody>{series.days.map(day => <tr key={day.date} className="border-t border-white/10"><th scope="row" className="whitespace-nowrap p-2 font-normal">{day.date}</th><td className="p-2">{day.row ? number(day.row.impressions) : "Missing"}</td><td className="p-2">{day.row ? number(day.row.clicks) : "Missing"}</td><td className="p-2">{day.row ? "Reported" : "Unreported"}</td></tr>)}</tbody>
        </table></div>
      </details>
    </>}
    <p className="mt-5 break-words text-xs leading-6 text-slate-400">Source: google_search_console · sc-domain:empire-ai.co.uk · dimensions=[date] · existing private Search Intelligence daily reader. Read checked at {checkedAt}; this is a read time, not Google’s publication time. GSC dates retain the source’s reporting timezone. Missing days stay missing; recent data may be revised. Query/page and page-only samples below are separate evidence and are never added to these totals. Clicks are not verified sessions, leads or revenue. GSC average position is not independent SERP rank.</p>
  </section>;
}
export default async function GSCHistory() { return <GSCHistoryView {...await loadDailyHistory()} />; }
