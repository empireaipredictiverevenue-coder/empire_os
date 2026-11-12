import { test } from "node:test";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import { ASSETS, boundedJSON, loadUnifiedAssets, validateBrowser, validateJev, validatePages } from "./unified-assets-data";
import { UnifiedAssetsView } from "./unified-assets";
import { validateDaily } from "./gsc-daily";
const now = new Date("2026-11-12T10:00:00Z"), start = "2026-10-11", end = "2026-11-09";
const row = (url: string) => ({ keys: [url], clicks: 0, impressions: 12, ctr: 0, position: 4 });
const source = () => ({ schema_version: "empire.search.gsc_page_observations.v1", mode: "OBSERVE", available: true, source: "google_search_console", site_url: "sc-domain:empire-ai.co.uk", dimensions: ["page"], data_state: "final", window: [start, end], count: 1, limit: 250, execution_authority: "none", items: [row(ASSETS[0][1])] });
const jev = { schema_version: "empire.search.jev_department_portfolio.v1", mode: "OBSERVE", execution_authority: "NONE", task_count: 14, jev_inference_calls: 0, jev_scores_generated: 0 };
const browser = { schema: "empire.task.founder_status_feed.v1", status: "READONLY_EVIDENCE_FEED", read_only: true, mode: "OBSERVE", execution_authority: "none", task_count: 25 };
test("page envelope rejects wrong schema, dimensions, property, authority and window", () => {
  for (const patch of [{ schema_version: "wrong" }, { dimensions: ["date"] }, { dimensions: ["query", "page"] }, { site_url: "other" }, { mode: "LIVE" }, { available: false }, { execution_authority: "write" }, { window: [end, start] }, { data_state: "all" }, { count: 2 }, { limit: 1000 }, { indexation_verified: true }]) assert.throws(() => validatePages({ ...source(), ...patch }, start, end));
});
test("all URLs validated before matching; invalid metrics fail closed", () => {
  for (const url of ["https://evil.example/", "https://empire-ai.co.uk.evil.example/", "https://user:pass@empire-ai.co.uk/", "https://empire-ai.co.uk/#x", "https://empire-ai.co.uk:443/"]) assert.throws(() => validatePages({ ...source(), count: 2, items: [...source().items, row(url)] }, start, end));
  for (const patch of [{ clicks: -1 }, { impressions: NaN }, { ctr: Infinity }, { position: -2 }]) assert.throws(() => validatePages({ ...source(), items: [{ ...source().items[0], ...patch }] }, start, end));
});
test("real domain-property GSC www, http, query and encoded rows do not invalidate exact pinned assets", () => {
  for (const url of ["https://www.empire-ai.co.uk/", "http://empire-ai.co.uk/", "https://empire-ai.co.uk/?email=private", "https://empire-ai.co.uk/%70rivate"]) {
    const d = validatePages({ ...source(), count: 2, items: [...source().items, row(url)] }, start, end);
    assert.equal(d.returned, 2);
    assert.equal(d.assets[0].metrics?.impressions, 12);
    assert.equal(d.assets[1].metrics, null);
  }
});
test("exact four assets; absent unknown, reported zero preserved, dimension boundary intact", () => {
  const pages = validatePages(source(), start, end);
  assert.equal(pages.assets.length, 4); assert.equal(pages.assets[0].metrics?.clicks, 0); assert.equal(pages.assets[1].metrics, null);
  assert.throws(() => validateDaily(source(), start, end));
});
test("browser cap is recent only and Jev rejects execution or inference", () => {
  assert.deepEqual(validateBrowser(browser), { tasks: 25 });
  for (const patch of [{ task_count: 26 }, { task_count: -1 }, { read_only: false }, { schema: "wrong" }, { execution_authority: "live" }]) assert.throws(() => validateBrowser({ ...browser, ...patch }));
  assert.equal(validateJev(jev).tasks, 14);
  for (const patch of [{ jev_inference_calls: 1 }, { jev_scores_generated: 1 }, { execution_authority: "live" }, { schema_version: "wrong" }]) assert.throws(() => validateJev({ ...jev, ...patch }));
});
test("three fixed GET no-store reads sanitize raw tasks; failures stay unavailable", async () => {
  const urls: string[] = [];
  const reader: typeof fetch = async (url, options) => {
    urls.push(String(url)); assert.equal(options?.method, "GET"); assert.equal(options?.cache, "no-store"); assert.equal(options?.redirect, "error"); assert.ok(options?.signal);
    return new Response(JSON.stringify(String(url).includes("/pages?") ? source() : String(url).includes("/jev/") ? jev : { ...browser, tasks: [{ secret: "DO_NOT_RENDER" }] }));
  };
  const data = await loadUnifiedAssets(now, reader);
  assert.equal(urls.length, 3); assert.ok(urls.includes(`http://127.0.0.1:8771/v1/search/search-console/pages?start_date=${start}&end_date=${end}&limit=250`));
  assert.deepEqual(data.browser, { tasks: 25 }); assert.ok(data.pages);
  const failed = await loadUnifiedAssets(now, async () => { throw new Error("secret"); });
  assert.equal(failed.pages, null); assert.equal(failed.jev, null); assert.equal(failed.browser, null);
});
test("byte cap and HTTP failures reject", async () => {
  await assert.rejects(boundedJSON("unused", async () => new Response("x".repeat(262145))));
  await assert.rejects(boundedJSON("unused", async () => new Response("{}", { status: 503 })));
});
test("render truth boundaries, private link and unknown states", () => {
  const props = { start, end, checkedAt: now.toISOString(), pages: validatePages(source(), start, end), jev: validateJev(jev), browser: validateBrowser(browser) };
  const html = renderToStaticMarkup(<UnifiedAssetsView {...props} />);
  for (const text of [/Unified Search Assets &amp; Execution/, /Not present in returned rows · metrics unknown/, /Observed page-only/, /never summed or compared/, /25 all recent tasks · feed capped at 25/, /not verified SEO actions or lifetime totals/, /0 inference calls · 0 scores generated/, /no execution authority/, /href="\/founder\/browser-tasks"/, /National Storm Hub/, /ASTRA/]) assert.match(html, text);
  assert.equal((html.match(/<a /g) ?? []).length, 5); assert.doesNotMatch(html, /DO_NOT_RENDER|<button|<form/);
  const offline = renderToStaticMarkup(<UnifiedAssetsView {...props} pages={null} jev={null} browser={null} />);
  assert.match(offline, /Metrics unknown · source unavailable/); assert.match(offline, /inference calls and scores are unknown/); assert.doesNotMatch(offline, /0 inference calls/);
});
