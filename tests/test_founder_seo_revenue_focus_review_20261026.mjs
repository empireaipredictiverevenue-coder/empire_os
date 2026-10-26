import test from "node:test";
import assert from "node:assert/strict";
import {safeSeoFocus,safeAeoCanary} from "../apps/search-command-centre/src/lib/seo-revenue-focus-review.ts";
const NOW=new Date("2026-10-26T20:25:00Z");
const stamp="2026-10-26T20:20:00+00:00";
const focus={
 status:"GROW_DISCOVERY_FOR_PUBLISHED_BUYER_ENTRY",
 next_existing_owner_action:"REVIEW_EXACT_GOOGLE_INDEX_COVERAGE_AND_PAGE_USEFULNESS",
 google_unknown_exact_buyer_entry_urls:[
  "https://empire-ai.co.uk/commercial","https://empire-ai.co.uk/industries/solar",
 ],
 sitewide_canonical_sales_count:0,count_source_verified:true,
 seo_attributed_buyer_count:null,earned_revenue_verified:false,
 new_publication_authorized:false,google_indexing_requests_submitted:0,
};
test("trust actual original read-only focus and source counts only",()=>{
 const r=safeSeoFocus(focus,{observed_at:stamp,now:NOW});
 assert.equal(r.focus?.sitewide_canonical_sales_count,0);
 assert.equal(r.aged,false);
 assert.deepEqual(r.focus?.google_unknown_exact_buyer_entry_urls,focus.google_unknown_exact_buyer_entry_urls);
});
test("old saved receipt explicitly reported stale",()=>{
 const r=safeSeoFocus(focus,{observed_at:"2026-10-26T16:55:00Z",now:NOW});
 assert.equal(r.aged,true);
});
test("missing current focus never becomes zero sales",()=>{
 const r=safeSeoFocus(undefined,{observed_at:stamp,now:NOW});
 assert.equal(r.focus,null);
 assert.equal(r.reason,"FOCUS_NOT_IN_SAVED_ORIGINAL_OWNER_RECEIPT");
});
test("malicious/external or permissive focus rejected",()=>{
 for(const bad of [
  {...focus,google_unknown_exact_buyer_entry_urls:["https://evil.example/"]},
  {...focus,google_unknown_exact_buyer_entry_urls:["https://empire-ai.co.uk/commercial?email=x"]},
  {...focus,sitewide_canonical_sales_count:2,count_source_verified:false},
  {...focus,sitewide_canonical_sales_count:null,count_source_verified:true},
  {...focus,seo_attributed_buyer_count:1},
  {...focus,earned_revenue_verified:true},
  {...focus,google_indexing_requests_submitted:1},
  {...focus,new_publication_authorized:true},
 ]) assert.equal(safeSeoFocus(bad,{observed_at:stamp,now:NOW}).focus,null);
});
test("observed live handoff means navigation only, not a sale",()=>{
 const r=safeAeoCanary({
  status:"THREE_AEO_TO_COMMERCIAL_SOURCE_LINKS_GET_VERIFIED",
  live_aeo_links_verified:3,commercial_compiled_claim_support_verified:true,
  submitted_enquiries_verified:false,outbound_sent:false,database_writes:false,
 });
 assert.equal(r?.live_aeo_links_verified,3);
 assert.equal(r?.submitted_enquiries_verified,false);
});
test("bad AEO link count and unverified claims held",()=>{
 assert.equal(safeAeoCanary({
  status:"THREE_AEO_TO_COMMERCIAL_SOURCE_LINKS_GET_VERIFIED",
  live_aeo_links_verified:2,commercial_compiled_claim_support_verified:true,
  submitted_enquiries_verified:false,outbound_sent:false,database_writes:false,
 }),null);
 assert.equal(safeAeoCanary({
  status:"HELD",live_aeo_links_verified:0,
  commercial_compiled_claim_support_verified:false,
  submitted_enquiries_verified:true,outbound_sent:false,database_writes:false,
 }),null);
});
