import { test } from "node:test";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import { dailyWindow, dailyTrend, validateDaily } from "./gsc-daily";
import { GSCHistoryView, loadDailyHistory } from "./gsc-history";
const now = new Date("2026-11-12T10:00:00Z");
const { start, end } = dailyWindow(now);
const row = (date: string, clicks = 0, impressions = 10) => ({ keys: [date], clicks, impressions });
const source = (items = [row(start), row(end, 2)]) => ({ available: true, source: "google_search_console", site_url: "sc-domain:empire-ai.co.uk", dimensions: ["date"], items, count: items.length, limit: 30 });
test("30-day delayed UTC window crosses months and years", () => {
  assert.deepEqual({ start, end }, { start: "2026-10-11", end: "2026-11-09" });
  assert.deepEqual(dailyWindow(new Date("2027-01-02T23:00:00Z")), { start: "2026-12-01", end: "2026-12-30" });
});
test("missing dates stay null; reported zero survives; aggregates use observed rows", () => {
  const series = validateDaily(source(), start, end);
  assert.equal(series.rows.length, 2); assert.equal(series.days.length, 30);
  assert.equal(series.days[0].row?.clicks, 0); assert.equal(series.days[1].row, null);
  assert.equal(series.clicks, 2); assert.equal(series.impressions, 20); assert.equal(series.ctr, 0.1);
  assert.match(dailyTrend(series, "clicks"), /unavailable/);
  assert.equal(validateDaily(source([row(start, 0, 0)]), start, end).ctr, null);
});
test("reject wrong source, dimensions, counts, duplicates, dates and invalid metrics", () => {
  const invalid: unknown[] = [null, { ...source(), source: "sample" }, { ...source(), available: false },
    { ...source(), site_url: "other" }, { ...source(), dimensions: ["page"] }, { ...source(), count: 1 },
    { ...source(), limit: 20 }, source([row(start), row(start)]), source([row("2026-11-10")]),
    source([row("2026-02-30")]), source([row(start, -1)]), source([row(start, 11)]),
    source([row(start, 0.5)]), source([row(start, 0, Infinity)]), source([row(start, 0, NaN)])];
  for (const value of invalid) assert.throws(() => validateDaily(value, start, end));
});
test("trend compares only two complete seven-day periods", () => {
  const dates = validateDaily(source([]), start, end).days.slice(-14);
  const series = validateDaily(source(dates.map((day, i) => row(day.date, i < 7 ? 1 : 2))), start, end);
  assert.match(dailyTrend(series, "clicks"), /↑ Up 7 clicks \(100.0%\)/);
});
test("one bounded loopback GET; unavailable on transport or schema failure", async () => {
  let calls = 0;
  const reader: typeof fetch = async (url, options) => {
    calls++; assert.equal(String(url), `http://127.0.0.1:8771/v1/search/search-console/daily?start_date=${start}&end_date=${end}&limit=30`);
    assert.equal(options?.cache, "no-store"); assert.equal(options?.redirect, "error");
    return new Response(JSON.stringify(source()));
  };
  assert.equal((await loadDailyHistory(now, reader)).series?.rows.length, 2); assert.equal(calls, 1);
  assert.equal((await loadDailyHistory(now, async () => { throw new Error("offline"); })).series, null);
  assert.equal((await loadDailyHistory(now, async () => new Response('{}'))).series, null);
  assert.equal((await loadDailyHistory(now, async () => new Response('', { status: 503 }))).series, null);
});
test("accessible chart/table and explicit unavailable rendering", () => {
  const props = { start, end, checkedAt: now.toISOString() };
  const html = renderToStaticMarkup(<GSCHistoryView {...props} series={validateDaily(source(), start, end)} />);
  assert.equal((html.match(/role="img"/g) || []).length, 2);
  assert.match(html, /<caption/); assert.match(html, /Missing/); assert.match(html, /Reported clicks/);
  const unavailable = renderToStaticMarkup(<GSCHistoryView {...props} series={null} />);
  assert.match(unavailable, /Daily GSC history unavailable/); assert.doesNotMatch(unavailable, /<svg/);
});
