const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs"), path = require("node:path"), Module = require("node:module"), ts = require("typescript");
const file = path.resolve(__dirname, "../src/app/v1/revenue-crm/auth/login/route.ts");
const m = new Module(file, module); m.filename = file; m.paths = module.paths;
m._compile(ts.transpileModule(fs.readFileSync(file, "utf8"), {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText, file);
const {POST} = m.exports;
const body = {email: "fixture@example.invalid", password: "fixture-only", tenant_id: "11111111-1111-1111-1111-111111111111"};
const token = "a".repeat(60) + "." + "b".repeat(60) + ".sig";
function req(overrides = {}, data = body) {return new Request("https://console.example/v1/revenue-crm/auth/login", {method: "POST", headers: {Origin: "https://console.example", "Content-Type": "application/json", ...overrides}, body: JSON.stringify(data)});}
test("original login forwarded once, no cookies and no extra upstream fields exposed", async t => {
 const old = process.env.EMPIRE_CRM_API_BASE_URL; process.env.EMPIRE_CRM_API_BASE_URL = "http://127.0.0.1:8783";
 t.after(() => {if (old === undefined) delete process.env.EMPIRE_CRM_API_BASE_URL; else process.env.EMPIRE_CRM_API_BASE_URL = old;});
 t.mock.method(global, "fetch", async (url, init) => {
  assert.equal(String(url), "http://127.0.0.1:8783/v1/revenue-crm/auth/login");
  assert.deepEqual(JSON.parse(init.body), body); assert.equal(init.redirect, "error"); assert.equal(init.credentials, "omit");
  return Response.json({access_token: token, token_type: "Bearer", expires_in: 300, scope: "crm:read", private: "not returned"});
 });
 const response = await POST(req()); assert.equal(response.status, 200);
 assert.equal(response.headers.get("cache-control"), "no-store"); assert.equal(response.headers.get("set-cookie"), null);
 assert.equal((await response.json()).private, undefined);
});
test("cross origin, oversized input and extra fields fail before original login", async t => {
 let calls = 0; t.mock.method(global, "fetch", async () => {calls++; throw Error("unexpected");});
 assert.equal((await POST(req({Origin: "https://elsewhere.example"}))).status, 403);
 assert.equal((await POST(req({}, {...body, scope: "admin"}))).status, 400);
 assert.equal((await POST(req({}, {...body, password: "x".repeat(9000)}))).status, 413);
 assert.equal(calls, 0);
});

test("configured console origin survives internal proxy URL without trusting forwarded host", async t => {
 const old = process.env.EMPIRE_CONSOLE_ORIGIN; process.env.EMPIRE_CONSOLE_ORIGIN = "https://console.example";
 t.after(() => {if (old === undefined) delete process.env.EMPIRE_CONSOLE_ORIGIN; else process.env.EMPIRE_CONSOLE_ORIGIN = old;});
 const upstream = process.env.EMPIRE_CRM_API_BASE_URL; delete process.env.EMPIRE_CRM_API_BASE_URL;
 t.after(() => {if (upstream !== undefined) process.env.EMPIRE_CRM_API_BASE_URL = upstream;});
 const valid = new Request("http://localhost:3000/v1/revenue-crm/auth/login", {method: "POST", headers: {Origin: "https://console.example", "Content-Type": "application/json"}, body: JSON.stringify(body)});
 assert.equal((await POST(valid)).status, 503); // Origin accepted, upstream deliberately absent.
 assert.equal((await POST(req({Origin: "https://attacker.example", "X-Forwarded-Host": "attacker.example"}))).status, 403);
});
