/** Read-only, data-grounded SEO chart panel. The API validates each point first.
 *  No client requests, cookies, chart libraries, forecasts or synthetic zeros.
 */
import type { GscDailyChart } from "@/lib/search-api";

type DayRow = GscDailyChart["rows"][number];

function prettyDate(value: string): string {
  const [year, month, day] = value.split("-");
  return `${day}/${month}`; // Year remains visible in the source-window caption.
}

function ObservedBars({ rows }: { rows: DayRow[] }) {
  const maximum = Math.max(1, ...rows.map((row) => row.impressions));
  return (
    <div className="mt-5 rounded-2xl border border-cyan-400/15 bg-[#071922] p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h3 className="text-sm font-semibold text-cyan-100">Observed daily impressions</h3>
        <span className="text-xs text-slate-400">Source: GSC date dimension</span>
      </div>
      <div role="img" aria-label="Daily Google Search Console reported impression bars; exact values follow in the table." className="mt-6 flex h-44 items-end justify-between gap-1.5 border-b border-white/10 pb-2 sm:gap-3">
        {rows.map((point) => (
          <div key={point.date} className="group relative flex h-full min-w-0 flex-1 flex-col justify-end">
            <div
              className="min-h-0 w-full rounded-t-md bg-gradient-to-t from-[#0079cb] to-[#6bdcff] ring-1 ring-cyan-300/20 transition-colors group-hover:from-[#0089e6] group-hover:to-[#a0eeff]"
              style={{ height: `${point.impressions === 0 ? 0 : Math.max(5, (point.impressions / maximum) * 100)}%` }}
              title={`${point.date}: ${point.impressions} reported impressions`}
            />
          </div>
        ))}
      </div>
      <div className="mt-2 flex justify-between gap-2 text-[10px] text-slate-400">
        <span>{prettyDate(rows[0].date)}</span>
        <span>{prettyDate(rows[rows.length - 1].date)}</span>
      </div>
    </div>
  );
}

function ClicksLine({ rows }: { rows: DayRow[] }) {
  // The series only connects dates actually returned by GSC. If source dates
  // are missing we avoid implying a continuous or zero-valued timeline.
  const maximum = Math.max(1, ...rows.map((row) => row.clicks));
  const padding = 12;
  const width = 660;
  const height = 128;
  const positionX = (index: number) =>
    padding + index * (width - padding * 2) / Math.max(1, rows.length - 1);
  const positionY = (count: number) =>
    height - padding - (count / maximum) * (height - padding * 2);
  const segments = rows.map((row, i) => ({
    ...row,
    x: positionX(i),
    y: positionY(row.clicks),
  }));
  return (
    <div className="mt-5 rounded-2xl border border-amber-300/15 bg-[#151512] p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h3 className="text-sm font-semibold text-amber-100">Observed daily clicks</h3>
        <span className="text-xs text-slate-400">GSC-reported clicks—not buyer enquiries</span>
      </div>
      <svg
        viewBox="0 0 660 128" role="img"
        aria-label="Google Search Console reported clicks for observed dates; exact values are in the data table below."
        className="mt-4 block w-full" preserveAspectRatio="none"
      >
        <line x1="12" y1="116" x2="648" y2="116" stroke="#475569" strokeOpacity="0.5" />
        {segments.length > 1 && segments.slice(1).map((point, i) => (
          <line key={point.date} x1={segments[i].x} y1={segments[i].y}
            x2={point.x} y2={point.y} stroke="#e8bd72" strokeWidth="2.25" />
        ))}
        {segments.map((point) => (
          <circle key={point.date} cx={point.x} cy={point.y} r="4"
            fill="#f5c979" stroke="#2b261c" strokeWidth="1.5">
            <title>{`${point.date}: ${point.clicks} reported clicks`}</title>
          </circle>
        ))}
      </svg>
      <div className="flex justify-between text-[10px] text-slate-400">
        <span>{prettyDate(rows[0].date)}</span><span>{prettyDate(rows[rows.length - 1].date)}</span>
      </div>
    </div>
  );
}

export function ObservedGscTrend({ chart }: { chart?: GscDailyChart }) {
  if (!chart || chart.status !== "DATE_DIMENSION_ROWS_OBSERVED" || chart.rows.length === 0
      || chart.days_missing_unreported === null
      || chart.reported_date_dimension_impressions === null
      || chart.reported_date_dimension_clicks === null) {
    return (
      <section className="panel mt-7" aria-label="First-party daily search trend">
        <p className="eyebrow">Measurement intelligence</p>
        <h2 className="mt-1 text-xl font-semibold text-white">Daily search trend</h2>
        <p className="mt-4 text-sm text-slate-400">
          Daily date-dimension evidence is not yet available through the running SEO API.
          No missing dates, clicks or impressions have been fabricated.
        </p>
      </section>
    );
  }
  const noFill = chart.days_missing_unreported.length === 0;
  return (
    <section className="panel mt-7" aria-label="First-party daily search trend">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow">Empire AI · Search Intelligence</p>
          <h2 className="mt-1 text-xl font-semibold text-white">Observed organic search trend</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
            First-party Google Search Console reporting by date, {chart.date_window[0]}–{chart.date_window[1]}.
            Separate from page-level totals and independent SERP ranking measurements.
          </p>
        </div>
        <span className="rounded-full border border-cyan-300/25 bg-cyan-300/10 px-3 py-1 text-xs font-medium text-cyan-100">
          {chart.days_observed} observed dates
        </span>
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-white/10 bg-white/[0.035] p-4">
          <p className="text-xs text-slate-400">Date-dimension impressions</p>
          <p className="mt-2 text-2xl font-semibold text-white">{chart.reported_date_dimension_impressions.toLocaleString("en-GB")}</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.035] p-4">
          <p className="text-xs text-slate-400">Date-dimension clicks</p>
          <p className="mt-2 text-2xl font-semibold text-white">{chart.reported_date_dimension_clicks.toLocaleString("en-GB")}</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.035] p-4">
          <p className="text-xs text-slate-400">Dates not reported</p>
          <p className="mt-2 text-2xl font-semibold text-white">{chart.days_missing_unreported.length}</p>
          <p className="mt-1 text-xs text-slate-400">Unreported ≠ zero traffic</p>
        </div>
      </div>
      {noFill ? (
        <div className="mt-3 grid gap-4 lg:grid-cols-2">
          <ObservedBars rows={chart.rows} />
          <ClicksLine rows={chart.rows} />
        </div>
      ) : (
        <div className="mt-5 rounded-xl border border-amber-400/30 bg-amber-400/5 px-4 py-3 text-sm text-amber-100" role="status">
          {chart.days_missing_unreported.length} dates have no source rows. Trend graphics are withheld
          to avoid connecting observations across unreported dates.
        </div>
      )}
      <details className="mt-5 rounded-xl border border-white/10 p-4">
        <summary className="cursor-pointer text-sm font-semibold text-slate-200">
          View exact daily measurements
        </summary>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[460px] text-left text-sm">
            <caption className="sr-only">
              First-party GSC date-dimension daily impressions, clicks and GSC average position.
            </caption>
            <thead className="text-xs uppercase tracking-wider text-slate-400">
              <tr>
                <th scope="col" className="px-2 py-2">Date</th>
                <th scope="col" className="px-2 py-2 text-right">Impressions</th>
                <th scope="col" className="px-2 py-2 text-right">Clicks</th>
                <th scope="col" className="px-2 py-2 text-right">GSC average position</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {chart.rows.map((row) => (
                <tr key={row.date} className="text-slate-200">
                  <th scope="row" className="px-2 py-2 font-medium">{row.date}</th>
                  <td className="px-2 py-2 text-right">{row.impressions}</td>
                  <td className="px-2 py-2 text-right">{row.clicks}</td>
                  <td className="px-2 py-2 text-right">{row.gsc_reported_average_position.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <p className="mt-4 text-xs leading-5 text-slate-400">
        The plotted counts are GSC reported date-dimension metrics. They are not sitewide unique visitors,
        leads, realised revenue or independently observed keyword ranks. No synthetic dates or clicks.
      </p>
    </section>
  );
}
