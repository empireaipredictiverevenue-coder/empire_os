import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {
  ownedRevenueGuideProposalHref,
  claimedEntryForReview,
  industryCommercialProposalHref,
} from "../apps/empire-public-site/src/lib/commercial-entry-review.ts";

test("the original SaaS guide uses an allowlisted, unverified buyer-entry hint",()=>{
  assert.equal(
    ownedRevenueGuideProposalHref(),
    "/commercial?entry=%2Fpredictive-revenue#commercial-enquiry",
  );
  assert.equal(claimedEntryForReview("?entry=%2Fpredictive-revenue"),"/predictive-revenue");
  assert.equal(claimedEntryForReview("?entry=https%3A%2F%2Fevil.example"),undefined);
  assert.equal(claimedEntryForReview("?entry=%2Fadmin"),undefined);
  assert.equal(claimedEntryForReview("?entry=%2Fpredictive-revenue&entry=%2Fadmin"),undefined);
});

test("a separate SaaS guide CTA remains wired to existing Commercial review",()=>{
  const jsx=readFileSync(
    new URL("../apps/empire-public-site/src/components/SaaSRevenueLeakageGuide.tsx",import.meta.url),
    "utf8",
  );
  assert.match(jsx,/href=\{ownedRevenueGuideProposalHref\(\)\}/);
  assert.match(jsx,/Buyer-initiated contact only/);
  assert.equal(industryCommercialProposalHref("bad-company"),"/commercial#commercial-enquiry");
});
