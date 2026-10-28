// Isolated localhost browser test. All credentials and evidence are fixtures.
const test = require("node:test"), assert = require("node:assert/strict");
const http = require("node:http"), net = require("node:net"), path = require("node:path"), {spawn} = require("node:child_process");
const puppeteer = require(process.env.EMPIRE_TEST_PUPPETEER_PATH || "puppeteer");
const token = "a".repeat(60) + "." + "b".repeat(60) + ".sig";
const packet = {schema_version: "empire.predictive-revenue-company-export-review.v4.21", company_scope: "company", source_id: "source", execution_authority: "none", eligible_for_training_or_live_prediction: false, model_promotion_or_payment_authorized: false, decision: "HOLD_UNVERIFIED_BUSINESS_HISTORY", as_of_utc: "2026-10-27T12:00:00+00:00", payload_sha256: "a".repeat(64), v5_predictive_cloud_staging_read_only: {issued_forecast_risk_screens_unverified: [{forecast_id: "fixture-forecast-30", horizon_days: 30, research_risk_band: {decision: "HOLD"}}]}};
const listen = server => new Promise(resolve => server.listen(0, "127.0.0.1", () => resolve(server.address().port)));
test("existing React page signs in, reviews and clears private evidence", {timeout: 90000}, async t => {
 let expires = 300, reviewStatus = 200, reviews = 0, loginCalls = 0;
 const server = http.createServer((req, res) => {
  const reply = (status, data) => {res.writeHead(status, {"Content-Type": "application/json", "Cache-Control": "no-store"}); res.end(JSON.stringify(data));};
  if (req.url === "/v1/revenue-crm/auth/login") {
   loginCalls++; let raw = ""; req.on("data", x => raw += x); req.on("end", () => {
    assert.equal(JSON.parse(raw).email, "fixture@example.invalid");
    reply(200, {access_token: token, token_type: "Bearer", scope: "crm:read", expires_in: expires});
   }); return;
  }
  if (req.url.startsWith("/v1/predictive-revenue/company-review?")) {
   reviews++; assert.equal(req.headers.authorization, "Bearer " + token);
   assert.equal(new URL(req.url, "http://local").searchParams.get("tenant_id"), null);
   return reply(reviewStatus, reviewStatus === 200 ? packet : {detail: "denied"});
  }
  return reply(503, {detail: "fixture_aggregate_unavailable"});
 });
 const backendPort = await listen(server); t.after(() => server.close());
 const allocator = net.createServer(); const appPort = await listen(allocator); await new Promise(r => allocator.close(r));
 const cwd = path.resolve(__dirname, "..");
 const child = spawn(process.execPath, [path.join(cwd, "node_modules/next/dist/bin/next"), "start", "--hostname", "127.0.0.1", "--port", String(appPort)], {cwd, env: {...process.env, EMPIRE_API_BASE_URL: "http://127.0.0.1:" + backendPort, EMPIRE_CRM_API_BASE_URL: "http://127.0.0.1:" + backendPort, EMPIRE_CONSOLE_ORIGIN: "http://127.0.0.1:" + appPort, NEXT_TELEMETRY_DISABLED: "1"}, stdio: "ignore"});
 t.after(() => child.kill("SIGTERM"));
 const origin = "http://127.0.0.1:" + appPort;
 for (let i = 0; i < 100; i++) {try {await fetch(origin + "/predictive-revenue"); break;} catch {await new Promise(r => setTimeout(r, 100));}}
 const browser = await puppeteer.launch({headless: true, args: ["--no-sandbox", "--disable-setuid-sandbox"]}); t.after(() => browser.close());
 let loginHttp = null;
 const page = await browser.newPage(); page.on("response", r => {if (r.url().endsWith("/auth/login")) loginHttp = r.status();}); await page.setViewport({width: 390, height: 844});
 await page.goto(origin + "/predictive-revenue", {waitUntil: "networkidle0"});
 const login = async () => {
  await page.type('[name="email"]', "fixture@example.invalid"); await page.type('[name="password"]', "fixture-password-only");
  await page.type('[name="tenant_id"]', "11111111-1111-1111-1111-111111111111");
  await page.click('button[type="submit"], form button');
  try { await page.waitForSelector('[name="company_scope"]', {timeout: 5000}); }
  catch { throw Error("Login UI failure: " + await page.$eval('[role="status"]', e => e.textContent) + "; http=" + loginHttp + "; upstream_calls=" + loginCalls + "; validation=" + await page.$$eval("input", items => items.map(e => e.name + ":" + e.validity.valid).join(","))); }
 };
 const review = async () => {
  await page.type('[name="company_scope"]', "company"); await page.type('[name="source_id"]', "source");
  await page.evaluate(() => [...document.querySelectorAll("button")].find(x => x.textContent === "Review permitted evidence").click());
 };
 const signout = async () => {await page.evaluate(() => [...document.querySelectorAll("button")].find(x => x.textContent === "Sign out").click()); await page.waitForSelector('[name="email"]');};
 await login(); await review(); await page.waitForSelector('[data-testid="private-company-result"]');
 let html = await page.content(); assert.ok(html.includes("fixture-forecast-30")); assert.ok(html.includes("60-day research horizon")); assert.ok(html.includes("no issued forecast supplied"));
 assert.ok(!html.includes(token));
 assert.deepEqual(await page.evaluate(() => [localStorage.length, sessionStorage.length, document.cookie]), [0, 0, ""]);
 await signout(); assert.equal(await page.$('[data-testid="private-company-result"]'), null);
 reviewStatus = 403; await login(); await review();
 await page.waitForFunction(() => document.body.textContent.includes("not authorised")); assert.equal(await page.$('[data-testid="private-company-result"]'), null);
 await signout();
 reviewStatus = 200; expires = 2; await page.setViewport({width: 1440, height: 900}); await login(); await review(); await page.waitForSelector('[data-testid="private-company-result"]');
 await page.waitForFunction(() => document.body.textContent.includes("CRM session expired")); assert.equal(await page.$('[data-testid="private-company-result"]'), null);
 assert.equal(reviews, 3); assert.equal(loginCalls, 3);
});
