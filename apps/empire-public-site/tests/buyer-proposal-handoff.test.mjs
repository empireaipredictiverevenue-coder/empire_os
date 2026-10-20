import test from "node:test";
import assert from "node:assert/strict";
import {
  INTELLIGENCE_PROPOSAL_CODES,
  approvedProposalHref,
  selectApprovedProposalOffer,
} from "../src/lib/buyer-proposal-handoff.ts";

const approved = [
  {product_code:"consultancy_opportunity_assessment"},
  ...INTELLIGENCE_PROPOSAL_CODES.map(product_code => ({product_code})),
];

test("all four catalogue codes link to the nonbinding first-party form", () => {
  assert.equal(INTELLIGENCE_PROPOSAL_CODES.length, 4);
  for (const code of INTELLIGENCE_PROPOSAL_CODES) {
    assert.equal(approvedProposalHref(code), "/commercial?product=" + code + "#commercial-enquiry");
    assert.deepEqual(selectApprovedProposalOffer(code, approved), {code, rejected:false});
  }
});

test("unapproved checkout codes do not become approved proposals", () => {
  assert.equal(approvedProposalHref(null), "/commercial#commercial-enquiry");
  assert.equal(approvedProposalHref("unknown_code"), "/commercial#commercial-enquiry");
  assert.equal(approvedProposalHref("javascript:alert(1)"), "/commercial#commercial-enquiry");
});

test("untrusted query is only allowed if the live offers explicitly allow it", () => {
  for (const injected of ["javascript:alert(1)", "fake_product", "../../../evil", "<script>", "competitor_search_gap%0A", "__proto__"]) {
    assert.deepEqual(selectApprovedProposalOffer(injected, approved), {code:"", rejected:true});
  }
  assert.deepEqual(selectApprovedProposalOffer("competitor_search_gap", [
    {product_code:"consultancy_opportunity_assessment"},
  ]), {code:"", rejected:true});
});

test("normal commercial visitor keeps first approved catalogue offer", () => {
  assert.deepEqual(selectApprovedProposalOffer(null, approved), {
    code:"consultancy_opportunity_assessment", rejected:false,
  });
  assert.deepEqual(selectApprovedProposalOffer(null, []), {code:"", rejected:false});
});

test("preselection is pure and never submits a lead or order", () => {
  const result = selectApprovedProposalOffer("search_opportunity_map", approved);
  assert.deepEqual(result, {code:"search_opportunity_map", rejected:false});
});
