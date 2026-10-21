import test from "node:test";
import assert from "node:assert/strict";
import {prepareFounderPulse} from "../lib/revenue-pulse-website.js";
const now=new Date("2026-10-21T12:00:00Z");
function sample(){
 return {schema_version:"empire.revenue-pulse.v3",snapshot_source:"canonical_empiredb_postgres",generated_at:"2026-10-21T11:55:00Z",
 current_window:{label:"current_24h",evidence_refs:["empiredb:current_24h"],acquisitions:5,qualified:7,commercial_replies:0},
 recognized_revenue_truth:{recognized_revenue_cents:123456},
 alerts:[{kind:"conversion_gap",stage:"commercial_replies",message:"Evidence-backed conversion gap",prediction:false}]};
}
test("Global company revenue is never attributed to National Storm Hub",()=>{
 const s=prepareFounderPulse(sample(),now);
 assert.equal(s.status,"CURRENT");
 assert.equal(s.scope,"EMPIRE_AI_ORGANISATION_WIDE_NOT_NATIONAL_STORM_HUB");
 assert.equal(s.recognized_revenue_cents,123456);
 assert.equal(s.national_storm_hub.recognized_revenue_cents,null);
 assert.equal(s.national_storm_hub.inquiries_verified,null);
 assert.equal(s.national_storm_hub.payments_verified,null);
 assert.equal(s.alerts.length,1);
 assert.equal(s.send_authority,"none");
});
test("Unknown cannot become zero or a forecast sale",()=>{
 const raw=sample();raw.current_window.qualified=null;raw.current_window.commercial_replies=-2;raw.recognized_revenue_truth.recognized_revenue_cents=null;
 const v=prepareFounderPulse(raw,now);
 assert.equal(v.stages.qualified,null);
 assert.equal(v.stages.commercial_replies,null);
 assert.equal(v.recognized_revenue_cents,null);
});
test("Rejects unverified, future and stale snapshots",()=>{
 const raw=sample();
 assert.equal(prepareFounderPulse({...raw,snapshot_source:"web_guess"},now).status,"SOURCE_UNAVAILABLE");
 assert.equal(prepareFounderPulse({...raw,generated_at:"2026-10-21T12:01:00Z"},now).status,"STALE");
 assert.equal(prepareFounderPulse({...raw,generated_at:"2026-10-21T11:00:00Z"},now).status,"STALE");
 assert.equal(prepareFounderPulse({...raw,current_window:{...raw.current_window,evidence_refs:[]}},now).status,"SOURCE_UNAVAILABLE");
});
test("Never returns unknown stages or raw private evidence",()=>{
 const raw=sample();raw.alerts=[{kind:"customer",stage:"private_field",message:"sensitive"},{stage:"qualified",message:"0 observed"}];
 const v=prepareFounderPulse(raw,now);
 assert.equal(v.alerts.length,1);
 assert.equal(Object.hasOwn(v,"evidence_refs"),false);
 assert.equal(Object.hasOwn(v,"buyer_id"),false);
});
