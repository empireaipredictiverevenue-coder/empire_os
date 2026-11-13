import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { digest, filesystemReader, manifestRoutes, PATCH_COMMIT, probe, PROTECTED_ROUTES, reconcile, SEO_DIRECTORY, SEO_HASHES, seoMarkers, SEO_ROUTE, type Reader } from "./reconciliation-preflight";
const bytes = (s: string) => Buffer.from(s);
const headings = '<h2 id="gsc-history-heading">History</h2><h2 id="unified-assets-heading">Assets</h2>';
const manifest = (routes: string[]) => bytes(JSON.stringify(Object.fromEntries(routes.map(r => [r + "/page", "app" + r + "/page.js"]))));
const root = process.env.SEO_CANDIDATE_ROOT ?? process.cwd();
const read = filesystemReader(root);
// Canonical page is an offline fixture: the older owner branch legitimately differs.
const fixture: Reader = p => p.startsWith(".next/") ? manifest([...PROTECTED_ROUTES, SEO_ROUTE]) : p === SEO_DIRECTORY + "page.tsx" ? readFileSync(resolve(root, SEO_DIRECTORY + "reconciliation-canonical-page.fixture.txt")) : read(p);
const live = () => [...PROTECTED_ROUTES, SEO_ROUTE].map(route => ({ route, status: 200, http: "ok" as const, markers: "present" as const, data: "unverified" as const, error: null }));

test("seven immutable canonical patch hashes match pinned Git objects", () => {
  assert.equal(PATCH_COMMIT, "19eb011ebf05d792bb7970414bd5f6f698c11634");
  assert.equal(Object.keys(SEO_HASHES).length, 7);
  for (const [file, hash] of Object.entries(SEO_HASHES)) assert.equal(digest(fixture(SEO_DIRECTORY + file)), hash);
});
test("complete structural candidate PASS never grants production authority", () => {
  const result = reconcile(fixture, live());
  assert.equal(result.candidateVerification, "PASS");
  assert.equal(result.productionRelease, "HOLD");
  assert.equal(result.handoff.activationPerformed, false);
  assert.ok(result.requirements.every(r => r.live[0].data === "unverified"));
});
test("browser route drop fails closed even if live HTTP200 and no change proposed", () => {
  const result = reconcile(p => p.startsWith(".next/") ? manifest([SEO_ROUTE, "/founder"]) : fixture(p), live());
  assert.equal(result.candidateVerification, "HOLD");
  const browser = result.requirements.find(r => r.route === "/founder/browser-tasks")!;
  assert.equal(browser.candidatePresent, false); assert.equal(browser.live[0].http200, true);
  assert.ok(result.reasons.includes("required_route_missing_needs_original_release_owner"));
});
test("source mismatch, missing files, malformed manifest and offline probes hold", () => {
  for (const reader of [((p: string) => p.endsWith("page.tsx") ? bytes("changed") : fixture(p)), (() => { throw new Error("PRIVATE_INPUT"); })]) {
    const result = reconcile(reader);
    assert.equal(result.candidateVerification, "HOLD"); assert.ok(!JSON.stringify(result).includes("PRIVATE_INPUT"));
  }
  assert.ok(reconcile(fixture).reasons.includes("live_http_parity_unverified"));
  assert.ok(reconcile(p => p.startsWith(".next/") ? bytes("[]") : fixture(p), live()).reasons.includes("candidate_manifest_unverified"));
});
test("owner can extend protected inventory; changes outside SEO always hold", () => {
  assert.ok(reconcile(fixture, live(), ["/founder/other"]).requirements.some(r => r.route === "/founder/other" && !r.candidatePresent));
  assert.ok(reconcile(fixture, live(), [], ["/founder/browser-tasks"]).reasons.includes("proposed_change_outside_seo_scope_needs_original_release_owner"));
  for (const route of ["//evil", "/founder?secret=x", "/../secret", "https://evil"]) assert.throws(() => reconcile(fixture, [], [route]));
});
test("compiled route groups normalize; dynamic routes cannot cover browser invariant", () => {
  assert.deepEqual(manifestRoutes(bytes('{"/(private)/founder/browser-tasks/page":"app/a.js","/founder/[slug]/page":"app/b.js"}')), ["/founder/browser-tasks"]);
  for (const raw of ['null', '[]', '{"/x/page":42}', '{"/x/page":"../x.js"}', '{"/x":"app/x.js"}']) assert.throws(() => manifestRoutes(bytes(raw)));
  assert.throws(() => manifestRoutes(new Uint8Array(2097153)));
});
test("HTML markers distinguish headings from scripts, comments, attributes, escaped payloads", () => {
  assert.equal(seoMarkers(headings), true);
  assert.equal(seoMarkers(headings.replaceAll('id="', "id='" ).replaceAll('">', "'>")), true);
  for (const html of [headings.replaceAll("h2", "div"), headings.replaceAll("id=", "data-id="), `<!--${headings}-->`, `<script>${headings}</script>`, `<template>${headings}</template>`, `<textarea>${headings}</textarea>`, `<div title='${headings}'>ignore</div>`, headings.replaceAll('id="', 'title=" id='), headings.replaceAll("<", "&lt;"), '<h2 id="gsc-history-heading">Only one</h2>']) assert.equal(seoMarkers(html), false);
});
test("GET loopback only, no redirects/cookies, bounded sanitized readback", async () => {
  const reader: typeof fetch = async (url, options) => {
    assert.equal(url, "http://127.0.0.1:3001" + SEO_ROUTE);
    assert.equal(options?.method, "GET"); assert.equal(options?.credentials, "omit"); assert.equal(options?.redirect, "error"); assert.ok(options?.signal);
    assert.deepEqual(options?.headers, { Accept: "text/html" });
    return new Response(headings + "PRIVATE_BODY", { headers: { "content-type": "text/html; charset=utf-8" } });
  };
  const result = await probe(SEO_ROUTE, reader);
  assert.equal(result.markers, "present"); assert.equal(result.status, 200);
  assert.ok(!JSON.stringify(result).includes("PRIVATE_BODY"));
  await assert.rejects(probe("http://evil", reader));
});
test("redirect/auth/404/error, oversized and wrong MIME never count as marker proof", async () => {
  for (const status of [302, 401, 403, 404, 500]) {
    const result = await probe(SEO_ROUTE, async () => new Response("PRIVATE", { status }));
    assert.equal(result.status, status); assert.equal(result.http, "not_ok"); assert.equal(result.markers, "unknown");
  }
  for (const reader of [async () => { throw new Error("PRIVATE"); }, async () => new Response(headings), async () => new Response(headings, { headers: { "content-type": "text/html", "content-length": "2097153" } }), async () => new Response("x".repeat(2097153), { headers: { "content-type": "text/html" } })]) {
    const result = await probe(SEO_ROUTE, reader);
    assert.equal(result.http, "unavailable"); assert.equal(result.markers, "unknown"); assert.ok(!JSON.stringify(result).includes("PRIVATE"));
  }
});
test("safe reader rejects arbitrary files; summary never forwards extra observation data", () => {
  assert.throws(() => read("../../.env"));
  const result = reconcile(fixture, live().map(o => ({ ...o, raw: "PRIVATE_HTML" })));
  assert.ok(!JSON.stringify(result).includes("PRIVATE_HTML"));
  assert.ok(readFileSync(resolve(root, SEO_DIRECTORY + "page.tsx")).length > 0);
});

test("observed additional live routes become protected without separate inventory", () => {
  const result = reconcile(fixture, [...live(), { ...live()[0], route: "/founder/extra" }]);
  assert.equal(result.candidateVerification, "HOLD");
  assert.ok(result.requirements.some(r => r.route === "/founder/extra" && r.protected && !r.candidatePresent));
});
