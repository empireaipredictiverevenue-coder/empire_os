const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");
const filename = path.resolve(__dirname, "../src/app/predictive-revenue/money.ts");
const loaded = new Module(filename, module);
loaded.filename = filename;
loaded.paths = module.paths;
loaded._compile(ts.transpileModule(fs.readFileSync(filename, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
}).outputText, filename);
const { moneyCents, currencyOf } = loaded.exports;

test("uses supplied currency and preserves cents without conversion", () => {
  assert.equal(moneyCents(12345, "GBP"), "GBP\u00a0123.45");
  assert.equal(moneyCents(12345, "USD"), "USD\u00a0123.45");
  assert.equal(moneyCents(12345, "EUR"), "EUR\u00a0123.45");
  assert.equal(moneyCents(0, "GBP"), "GBP\u00a00.00");
});
test("missing currency or amount never becomes dollars or zero", () => {
  for (const currency of [undefined, null, "", "usd", "ZZZ", "XXX", "JPY", "KWD"])
    assert.equal(moneyCents(12345, currency), "UNKNOWN");
  for (const amount of [undefined, null, NaN, Infinity, 1.5, "12345", true, Number.MAX_SAFE_INTEGER + 1])
    assert.equal(moneyCents(amount, "USD"), "UNKNOWN");
  assert.equal(currencyOf(null), undefined);
  assert.equal(currencyOf({}), undefined);
  assert.equal(currencyOf({currency: "GBP"}), "GBP");
});
test("existing page renders actual row currency and missing financial evidence", async () => {
  const React = require("react");
  const {renderToStaticMarkup} = require("react-dom/server");
  const pageFile = path.resolve(__dirname, "../src/app/predictive-revenue/page.tsx");
  const page = new Module(pageFile, module);
  page.filename = pageFile; page.paths = module.paths;
  const originalRequire = page.require.bind(page);
  page.require = name => {
    if (name === "next/link") return {default: ({children}) => React.createElement("span", null, children)};
    if (name === "next/server") return {connection: async () => {}};
    if (name === "./company-review") return {CompanyReview: () => null};
    if (name === "./money") return loaded.exports;
    if (name === "./snapshot-evidence") return {SnapshotEvidence: () => null};
    if (name === "@/lib/founder-api") return {getPredictiveRevenueDemo: async () => ({ok: true, data: {
      revenue_truth: {recognized_revenue_cents: 987654},
      commercial_catalog: {active_binding_products: [
        {product_code: "gbp-fixture", amount_cents: 12345, currency: "GBP"},
        {product_code: "missing-fixture", amount_cents: null}
      ]},
      proof_chain: [{stage: "REVENUE", value_cents: 987654}]
    }})};
    return originalRequire(name);
  };
  page._compile(ts.transpileModule(fs.readFileSync(pageFile, "utf8"), {
    compilerOptions: {module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022}
  }).outputText, pageFile);
  const html = renderToStaticMarkup(await page.exports.default());
  assert.ok(html.includes("GBP\u00a0123.45"));
  assert.ok(html.includes("UNKNOWN"));
  assert.ok(!html.includes("9,876.54"));
  assert.ok(!html.includes("$250,000"));
  assert.ok(!html.slice(html.indexOf("missing-fixture")).includes("Verified terms</p>"));
  assert.ok(html.slice(html.indexOf("missing-fixture")).includes("UNKNOWN"));
});
