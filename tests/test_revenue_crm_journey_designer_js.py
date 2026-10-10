"""Execute first-party designer validation in Node, without browser, network or CRM data."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "empire_os/static/revenue_crm_journey_designer.js"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node syntax/runtime unavailable")
def test_browser_graph_safety_validation_and_custom_editor_draft():
    runner = r'''
const fs = require("fs");
const vm = require("vm");
const assert = require("node:assert/strict");
const src = fs.readFileSync(process.argv[1], "utf8");
assert(src.includes("  initialize();"));
const fake = {
  document: {
    getElementById: id => ({id, addEventListener() {}, disabled: false})
  },
  structuredClone: global.structuredClone
};
const injected = src.replace(
  "  initialize();",
  "  globalThis.__test = { validate, defaultModel, dag, setBase(g) { base = g; } };"
);
vm.runInNewContext(injected, fake, {timeout: 500});
const t = fake.__test;
const graph = {
  nodes: [
    {id:"source_observed",type:"source",label:"Canonical record"},
    {id:"consent_suppression_gate",type:"decision",label:"Consent + suppression"},
    {id:"conversation_review",type:"review",label:"Conversation review"},
    {id:"recognized_revenue_proof",type:"evidence",label:"Recognized revenue proof"}
  ],
  edges: [
    {from:"source_observed",to:"consent_suppression_gate"},
    {from:"consent_suppression_gate",to:"conversation_review"},
    {from:"conversation_review",to:"recognized_revenue_proof"}
  ]
};
t.setBase(graph);
let design=t.defaultModel(graph);
assert.equal(t.validate(design).state,"DESIGN_ONLY");
design.nodes.push({id:"custom_1",type:"review",label:"Human review",x:950,y:450,locked:false});
design.edges.push({from:"consent_suppression_gate",to:"custom_1",condition:"evidence_review_only",locked:false});
assert.equal(t.validate(design).nodes.length,5);
function rejected(fn) {
  const draft=structuredClone(design);
  fn(draft);
  assert.throws(()=>t.validate(draft));
}
rejected(d => d.nodes.splice(1,1)); // cannot delete consent gate
rejected(d => d.nodes[1].locked=false); // cannot unlock consent gate
rejected(d => d.nodes[1].label="Bypass consent"); // cannot rename security gate
rejected(d => d.edges.splice(0,1)); // cannot bypass mandatory edge
rejected(d => d.edges.push({from:"source_observed",to:"recognized_revenue_proof",condition:"evidence_review_only",locked:false})); // forbidden shortcut
rejected(d => d.edges.push({from:"custom_1",to:"recognized_revenue_proof",condition:"evidence_review_only",locked:false})); // skips stages
rejected(d => d.edges.push({from:"custom_1",to:"source_observed",condition:"evidence_review_only",locked:false})); // cycle
rejected(d => d.nodes.push({...d.nodes[4]})); // duplicate custom step
rejected(d => d.nodes[4].type="send_email"); // no send step
rejected(d => d.nodes[4].label="person@example.com"); // reject address labels
rejected(d => d.nodes[4].x=999999); // bounded canvas
rejected(d => d.execution_authority="live"); // cannot claim authority
rejected(d => d.tenant_data_included=true); // cannot include tenant data
rejected(d => d.server_persistence=true); // cannot imply stored in CRM
rejected(d => d.edges[2].condition="send_email"); // review-only edge
console.log("NODE_DESIGNER_VALIDATION=PASS (15 negative security cases)");
''';
    result = subprocess.run(
        ["node", "-e", runner, str(JS)], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "NODE_DESIGNER_VALIDATION=PASS" in result.stdout
