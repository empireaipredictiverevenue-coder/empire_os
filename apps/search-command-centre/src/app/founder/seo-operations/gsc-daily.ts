// Property date-dimension evidence only. Never combine query/page samples here.
export type DailyRow = { date: string; clicks: number; impressions: number };
export type DailySeries = {
  start: string; end: string; days: { date: string; row: DailyRow | null }[];
  rows: DailyRow[]; clicks: number; impressions: number; ctr: number | null;
};
const DAY = 86400000;
const iso = (time: number) => new Date(time).toISOString().slice(0, 10);
export function dailyWindow(now = new Date()) {
  const end = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()) - 3 * DAY;
  return { start: iso(end - 29 * DAY), end: iso(end) };
}
function validDate(value: string) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value)) && iso(Date.parse(value)) === value;
}
export function validateDaily(raw: unknown, start: string, end: string): DailySeries {
  const fail = () => { throw new Error("Daily GSC evidence unavailable or invalid"); };
  if (!validDate(start) || !validDate(end) || Date.parse(end) - Date.parse(start) !== 29 * DAY) return fail();
  if (!raw || typeof raw !== "object") return fail();
  const d = raw as Record<string, unknown>;
  if (d.available !== true || d.source !== "google_search_console" || d.site_url !== "sc-domain:empire-ai.co.uk" ||
      !Array.isArray(d.dimensions) || d.dimensions.length !== 1 || d.dimensions[0] !== "date" ||
      !Array.isArray(d.items) || d.items.length > 30 || d.count !== d.items.length || d.limit !== 30) return fail();
  const rows: DailyRow[] = [];
  const seen = new Set<string>();
  for (const item of d.items) {
    if (!item || typeof item !== "object") return fail();
    const { keys, clicks, impressions } = item;
    if (!Array.isArray(keys) || keys.length !== 1 || typeof keys[0] !== "string" || !validDate(keys[0]) ||
        keys[0] < start || keys[0] > end || seen.has(keys[0]) ||
        !Number.isSafeInteger(clicks) || !Number.isSafeInteger(impressions) ||
        clicks < 0 || impressions < 0 || clicks > impressions) return fail();
    seen.add(keys[0]);
    rows.push({ date: keys[0], clicks, impressions });
  }
  rows.sort((a, b) => a.date.localeCompare(b.date));
  const byDate = new Map(rows.map(row => [row.date, row]));
  const days = Array.from({ length: 30 }, (_, i) => {
    const date = iso(Date.parse(start) + i * DAY);
    return { date, row: byDate.get(date) ?? null };
  });
  const clicks = rows.reduce((sum, row) => sum + row.clicks, 0);
  const impressions = rows.reduce((sum, row) => sum + row.impressions, 0);
  if (!Number.isSafeInteger(clicks) || !Number.isSafeInteger(impressions)) return fail();
  return { start, end, days, rows, clicks, impressions, ctr: impressions ? clicks / impressions : null };
}
export function dailyTrend(series: DailySeries, metric: "clicks" | "impressions") {
  const previous = series.days.slice(-14, -7), current = series.days.slice(-7);
  if ([...previous, ...current].some(day => !day.row)) return "Trend unavailable · incomplete last 14 days";
  const sum = (days: typeof current) => days.reduce((n, day) => n + day.row![metric], 0);
  const before = sum(previous), after = sum(current), delta = after - before;
  return `${delta > 0 ? "↑ Up" : delta < 0 ? "↓ Down" : "→ Unchanged"} ${Math.abs(delta).toLocaleString("en-GB")} ${metric}${before ? ` (${(Math.abs(delta) / before * 100).toFixed(1)}%)` : " · prior week zero"} · last 7 vs previous 7 days`;
}
