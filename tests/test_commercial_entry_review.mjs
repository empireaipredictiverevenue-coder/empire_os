import {test} from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import {
  industryCommercialProposalHref, claimedEntryForReview,
} from "../apps/empire-public-site/src/lib/commercial-entry-review.ts";
import {reuseCommercialInterestAttempt} from "../apps/empire-public-site/src/lib/commercial-interest-attempt.ts";

const industrySource = fs.readFileSync(
  new URL("../apps/empire-public-site/src/components/IndustryIntelligencePage.tsx",import.meta.url),"utf8");
const formSource = fs.readFileSync(
  new URL("../apps/empire-public-site/src/app/commercial/page.tsx",import.meta.url),"utf8");

test("only allowed industry links can carry an unverified review entry",()=>{
  for(const slug of ["roofing","solar","hvac","property"]) {
    const path="/industries/"+slug;
    assert.equal(industryCommercialProposalHref(slug),
      "/commercial?entry="+encodeURIComponent(path)+"#commercial-enquiry");
    assert.equal(claimedEntryForReview("?entry="+encodeURIComponent(path)),path);
  }
  for(const slug of ["legal","../admin","roofing?utm=bad","", "roofing#x"]) {
    assert.equal(industryCommercialProposalHref(slug),"/commercial#commercial-enquiry");
  }
  assert.equal(industrySource.match(/href=\{industryCommercialProposalHref\(page.slug\)\}/g)?.length,2);
});

test("untrusted browser entry paths and multiple values are rejected",()=>{
  for(const search of [
    "?entry=https%3A%2F%2Fevil.example",
    "?entry=%2Fadmin",
    "?entry=%2Findustries%2Froofing%3Femail%3Dprivate",
    "?entry=%2Findustries%2Froofing&entry=%2Findustries%2Fsolar",
    "?entry=%252Findustries%252Froofing",
    "?entry=%2Findustries%2Funknown",
    "?utm_source=google",
    "",
  ]) {
    assert.equal(claimedEntryForReview(search),undefined);
  }
});

test("review hint only transmitted in consented commercial form",()=>{
  assert.match(formSource,/claimed_entry_page: claimedEntryForReview\(window.location.search\)/);
  assert.match(formSource,/body: JSON.stringify\(\{\.\.\.details, idempotency_key: attempt.idempotencyKey\}\)/);
  assert.match(formSource,/if \(!code \|\| !consent \|\| submitting/);
  assert.doesNotMatch(formSource,/localStorage|sessionStorage|document.referrer/);
});

test("same consented submission reuses key but changed hint gets new key",()=>{
  let i=0;
  const base={
    product_code:"consultancy_opportunity_assessment",business_name:"Sample Ltd",
    email:"example@sample.test",domain:"sample.test",industry:"Services",
    geography:"United Kingdom",desired_outcome:"Need qualified inbound customer enquiries.",
    contact_consent:true,website:"",claimed_entry_page:"/industries/roofing",
  };
  const next=()=>"entry-retry-key-"+(++i)+"-secure";
  const a=reuseCommercialInterestAttempt(null,base,next);
  assert.equal(reuseCommercialInterestAttempt(a,{...base},next),a);
  assert.notEqual(reuseCommercialInterestAttempt(a,{...base,claimed_entry_page:"/industries/solar"},next).idempotencyKey,a.idempotencyKey);
  assert.equal(i,2);
});
