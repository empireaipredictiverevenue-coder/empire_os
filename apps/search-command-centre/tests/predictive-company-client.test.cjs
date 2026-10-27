const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");
const file = path.resolve(__dirname, "../src/lib/founder-api.ts");
const loaded = new Module(file, module);
loaded.filename = file; loaded.paths = module.paths;
loaded._compile(ts.transpileModule(fs.readFileSync(file, "utf8"), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}
}).outputText, file);
const review = loaded.exports.getPredictiveCompanyReview;
const token = "a".repeat(60) + "." + "b".repeat(60) + ".signature";
const packet = {schema_version: "empire.predictive-revenue-company-export-review.v4.21",
  company_scope: "company", source_id: "source", execution_authority: "none",
  eligible_for_training_or_live_prediction: false, model_promotion_or_payment_authorized: false};
function setup(t, handler) {
  const old = process.env.EMPIRE_API_BASE_URL;
  process.env.EMPIRE_API_BASE_URL = "http://127.0.0.1:8766";
  t.after(() => { if (old === undefined) delete process.env.EMPIRE_API_BASE_URL; else process.env.EMPIRE_API_BASE_URL = old; });
  t.mock.method(global, "fetch", handler);
}
test("original bearer is request-local; no tenant query, cookies, caching or redirects", async t => {
  const calls = [];
  setup(t, async (url, init) => { calls.push({url, init}); return {ok: true, status: 200, json: async () => packet}; });
  const results = await Promise.all([review(token, "company", "source"), review(token + "x", "company", "source")]);
  assert.ok(results.every(r => r.ok));
  assert.deepEqual(calls.map(c => c.init.headers.Authorization), ["Bearer " + token, "Bearer " + token + "x"]);
  for (const {url, init} of calls) {
    assert.deepEqual([...new URL(url).searchParams.keys()], ["company_scope", "source_id"]);
    assert.equal(init.cache, "no-store"); assert.equal(init.credentials, "omit"); assert.equal(init.redirect, "error");
    assert.ok(!url.includes(token));
  }
});
test("missing login and insecure remote transport never fetch evidence", async t => {
  let calls = 0; setup(t, async () => { calls++; throw Error("must not fetch"); });
  assert.equal((await review("", "company", "source")).reason, "crm_session_required");
  assert.equal((await review(token, "company&tenant=other", "source")).reason, "company_source_scope_required");
  process.env.EMPIRE_API_BASE_URL = "http://remote.example";
  assert.equal((await review(token, "company", "source")).reason, "secure_api_origin_required");
  assert.equal(calls, 0);
});
test("denied and unavailable evidence never falls back to demo", async t => {
  let status = 403; setup(t, async () => ({ok: false, status, json: async () => {throw Error("must not read");}}));
  for (status of [401, 403, 503]) {
    const result = await review(token, "company", "source");
    assert.equal(result.data, null); assert.equal(result.reason, "http_" + status);
  }
});
test("wrong company, authority escalation and transport details are withheld", async t => {
  let data = {...packet, company_scope: "other"};
  setup(t, async () => {if (data === null) throw Error(token); return {ok: true, status: 200, json: async () => data};});
  for (data of [{...packet, company_scope: "other"}, {...packet, execution_authority: "live"}, {...packet, model_promotion_or_payment_authorized: true}])
    assert.equal((await review(token, "company", "source")).reason, "invalid_company_review_contract");
  data = null;
  assert.deepEqual(await review(token, "company", "source"), {ok: false, status: null, data: null, reason: "company_review_unavailable"});
});
