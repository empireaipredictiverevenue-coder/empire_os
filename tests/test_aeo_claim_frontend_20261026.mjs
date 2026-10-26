import { test } from "node:test";
import assert from "node:assert/strict";
import { aeoCommercialProposalHref,claimedEntryForReview } from
  "../apps/empire-public-site/src/lib/commercial-entry-review.ts";
const reviewed = [
 "/aeo/general_contractor/NYC/","/aeo/hvac/DFW/","/aeo/roofing/DFW/",
];
test("only exact AEO links submit bounded source hint via existing form",()=>{
 for(const path of reviewed){
  assert.equal(aeoCommercialProposalHref(path),
    "/commercial?entry="+encodeURIComponent(path)+"#commercial-enquiry");
  assert.equal(claimedEntryForReview("?entry="+encodeURIComponent(path)),path);
 }
 for (const invalid of ["/aeo/roofing/DFW","/aeo/roofing/SF/",
    "//example.invalid","/aeo/hvac/DFW/?utm_source=google"]) {
   assert.equal(aeoCommercialProposalHref(invalid),"/commercial#commercial-enquiry");
 }
});
test("query, PII, redirect and duplicate pollution never become claimed source",()=>{
 for (const input of [
  "?entry=%2Faeo%2Fhvac%2FDFW%2F%3Femail%3Dname%40example.test",
  "?entry=%2Faeo%2Fhvac%2FDFW%2F&entry=%2Faeo%2Froofing%2FDFW%2F",
  "?entry=https%3A%2F%2Fevil.example%2Faeo%2Fhvac%2FDFW%2F",
  "?entry=%2Faeo%2Froofing%2FDFW%2F%23marketing",
  "?entry=%2Faeo%2Fhvac%2FNYC%2F",
 ]) assert.equal(claimedEntryForReview(input),undefined);
});
