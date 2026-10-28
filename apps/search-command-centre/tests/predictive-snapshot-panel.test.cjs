const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const filename = path.resolve(__dirname, "../src/app/predictive-revenue/snapshot-evidence.tsx");
const output = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 }
}).outputText;
const loaded = new Module(filename, module);
loaded.filename = filename;
loaded.paths = module.paths;
loaded._compile(output, filename);
const render = payload => renderToStaticMarkup(React.createElement(loaded.exports.SnapshotEvidence, { payload }));
const packet = () => ({ intelligence_snapshot_evidence: {
  schema_version: "empire.predictive_revenue.snapshot_evidence.v1",
  scope: "SYSTEM_AGGREGATE_METADATA_ONLY", execution_authority: "none",
  sources: ["cloud", "predictive", "jev"].map(source => ({ source, evidence_ref: "runtime/" + source,
    snapshot_digest: "a".repeat(64), snapshot_generated_at: "2026-10-26T10:00:00+00:00", state: "OBSERVED" }))
}});
test("renders source lineage and keeps forecast hold separate", () => {
  const html = render(packet());
  assert.match(html, /runtime\/jev/);
  assert.match(html, /2026-10-26T10:00:00/);
  assert.match(html, /a{64}/);
  assert.match(html, /30 \/ 60 \/ 90-day forecasts: HOLD/);
});
test("missing or unauthorized contracts are unknown", () => {
  for (const p of [null, {}, {intelligence_snapshot_evidence: {}}]) assert.match(render(p), /contract unavailable or invalid/);
  const p = packet(); p.intelligence_snapshot_evidence.execution_authority = "live";
  assert.match(render(p), /contract unavailable or invalid/);
});
test("source failures render explicitly and source text is escaped", () => {
  const p = packet();
  p.intelligence_snapshot_evidence.sources[0].state = "STALE";
  p.intelligence_snapshot_evidence.sources[1].state = "UNAVAILABLE";
  p.intelligence_snapshot_evidence.sources[2].evidence_ref = "<script>bad()</script>";
  const html = render(p);
  assert.match(html, /STALE/); assert.match(html, /UNAVAILABLE/);
  assert.ok(!html.includes("<script>")); assert.match(html, /&lt;script&gt;/);
});
