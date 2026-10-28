const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");
function load(relative, dependencies = {}) {
  const file = path.resolve(__dirname, relative);
  const m = new Module(file, module); m.filename = file; m.paths = module.paths;
  const original = m.require.bind(m);
  m.require = name => dependencies[name] ?? original(name);
  m._compile(ts.transpileModule(fs.readFileSync(file, "utf8"), {
    compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}
  }).outputText, file);
  return m.exports;
}
const client = load("../src/lib/founder-api.ts");
const {GET} = load("../src/app/api/predictive-revenue/company-review/route.ts", {"@/lib/founder-api": client});
const priorOrigin = process.env.EMPIRE_CONSOLE_ORIGIN;
test.beforeEach(() => { process.env.EMPIRE_CONSOLE_ORIGIN = "https://console.example"; });
test.afterEach(() => { if (priorOrigin === undefined) delete process.env.EMPIRE_CONSOLE_ORIGIN; else process.env.EMPIRE_CONSOLE_ORIGIN = priorOrigin; });
const token = "a".repeat(60) + "." + "b".repeat(60) + ".sig";
const base = "https://console.example/api/predictive-revenue/company-review";
const query = "?company_scope=company&source_id=source";
const packet = {schema_version: "empire.predictive-revenue-company-export-review.v4.21",
  company_scope: "company", source_id: "source", execution_authority: "none",
  eligible_for_training_or_live_prediction: false, model_promotion_or_payment_authorized: false};
function setup(t, fetcher) {
 const old = process.env.EMPIRE_API_BASE_URL; process.env.EMPIRE_API_BASE_URL = "http://127.0.0.1:8766";
 t.after(() => { if (old === undefined) delete process.env.EMPIRE_API_BASE_URL; else process.env.EMPIRE_API_BASE_URL = old; });
 t.mock.method(global, "fetch", fetcher);
}
function request(extra = {}, suffix = query) {
 return new Request(base + suffix, {headers: {Authorization: "Bearer " + token, ...extra}});
}
test("browser route reaches original client without forwarding cookies or caller tenant", async t => {
 let calls = 0;
 setup(t, async (url, init) => {
  calls++; assert.equal(new URL(url).pathname, "/v1/predictive-revenue/company-review");
  assert.equal(init.headers.Authorization, "Bearer " + token);
  assert.equal(init.headers.Cookie, undefined);
  assert.equal(init.redirect, "error");
  return Response.json(packet);
 });
 const response = await GET(request({Cookie: "other-session=not-authority", Origin: "https://console.example"}));
 assert.equal(response.status, 200); assert.deepEqual(await response.json(), packet);
 assert.equal(response.headers.get("cache-control"), "no-store");
 assert.equal(response.headers.get("access-control-allow-origin"), null);
 assert.equal(calls, 1);
});
test("anonymous, duplicate bearer, cross-origin and injected scope never reach backend", async t => {
 let calls = 0; setup(t, async () => {calls++; throw Error("unexpected");});
 const cases = [
 [request({Authorization: "", Cookie: "crm=present"}), 401],
 [request({Authorization: "Bearer " + token + ", Bearer " + token}), 401],
 [request({Origin: "https://other.example"}), 403],
 [request({"Sec-Fetch-Site": "same-site"}), 403],
 [request({}, query + "&tenant_id=other"), 400],
 [request({}, query + "&source_id=other"), 400],
 ];
 for (const [req, status] of cases) assert.equal((await GET(req)).status, status);
 assert.equal(calls, 0);
});
test("upstream access denial and malformed evidence stay explicit and uncached", async t => {
 let status = 403;
 setup(t, async () => Response.json(status === 200 ? {...packet, company_scope: "wrong"} : {detail: "private backend diagnostic"}, {status}));
 for (status of [401, 403, 503, 200]) {
  const response = await GET(request());
  assert.equal(response.status, status === 200 ? 503 : status);
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.ok(!(await response.text()).includes("private backend"));
 }
});

test("missing or malformed release origin cannot fall back to request headers", async t => {
 let calls = 0; t.mock.method(global, "fetch", async () => { calls++; throw Error("must not forward"); });
 for (const origin of [undefined, "", "https://console.example/", "http://public.example", "https://console.example/path", "https://user:password@console.example"]) {
  if (origin === undefined) delete process.env.EMPIRE_CONSOLE_ORIGIN; else process.env.EMPIRE_CONSOLE_ORIGIN = origin;
  assert.equal((await GET(request())).status, 503);
 }
 assert.equal(calls, 0);
});
