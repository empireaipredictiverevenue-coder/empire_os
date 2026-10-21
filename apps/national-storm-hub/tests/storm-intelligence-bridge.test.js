import test from "node:test";
import assert from "node:assert/strict";
import {reviewOfficialWeatherIntelligence,projectEmpireStormRuntime} from "../lib/storm-intelligence-bridge.js";
import {verifyFounderRequest} from "../lib/founder-auth.js";
const now=new Date("2026-10-21T14:00:00Z");
const snapshot=()=>({
 schema_version:"empire.storm_opportunity_snapshot.v1",
 runtime_schema_version:"empire.storm_intelligence_runtime.v1",
 mode:"OBSERVE", unknown_stays_unknown:true, generated_at:"2026-10-21T13:50:00Z",
 execution_authority:"none",commercial_authority:"none",outreach_authority:"none",
 payment_authority:"none",revenue_recognition_authority:"none",
 damage_inferred:false,demand_inferred:false,buyer_intent_inferred:false,
 economics_inferred:false,pricing_inferred:false,automatic_external_execution_allowed:false,
 candidate_count:0,candidates:[], diagnostics:{events_seen:3,blocked_count:3,source_health:"HEALTHY",
 next_best_evidence:[{tenant_id:"private",event_id:"private-alert",buyer_id:"buyer-secret"}]}
});
test("fresh runtime is internal diagnostics only, never National Storm Hub demand",()=>{
 const output=projectEmpireStormRuntime(snapshot(),now);
 assert.equal(output.status,"CURRENT");
 assert.equal(output.events_reviewed,3);
 assert.equal(output.active_commercial_candidates,null);
 assert.equal(output.commercial_ready,false);
 assert.equal(output.payment_authorized,false);
 assert.equal(output.damage_verified,false);
 assert.doesNotMatch(JSON.stringify(output),/private-alert|buyer-secret|private"/);
});
test("stale internal intelligence cannot become live metrics",()=>{
 const old={...snapshot(),generated_at:"2026-10-05T11:20:00Z"};
 const output=projectEmpireStormRuntime(old,now);
 assert.equal(output.status,"STALE");
 assert.equal(output.events_reviewed,null);
 assert.equal(output.source_health,"UNKNOWN");
 assert.equal(output.archived_candidate_count,0);
});
test("authority, unexpected candidates or timestamps fail closed",()=>{
 assert.equal(projectEmpireStormRuntime({...snapshot(),outreach_authority:"approved"},now).status,"UNAVAILABLE");
 assert.equal(projectEmpireStormRuntime({...snapshot(),candidate_count:1},now).status,"UNAVAILABLE");
 assert.equal(projectEmpireStormRuntime({...snapshot(),generated_at:"2026-10-21T15:00:00Z"},now).status,"UNAVAILABLE");
 assert.equal(projectEmpireStormRuntime({...snapshot(),damage_inferred:true},now).status,"UNAVAILABLE");
});
test("warnings remain separate from observations, damage and buyer demand",()=>{
 const r=reviewOfficialWeatherIntelligence({
  checked_at:now.toISOString(),
  alerts:{status:"AVAILABLE",items:[{event:"Tornado Warning"},{event:"Flood Watch"}]},
  forecast:{status:"AVAILABLE",periods:[{name:"Tonight"}]},
  spc:{status:"AVAILABLE",category:{label:"Slight"}}
 });
 assert.equal(r.official_warning_signals,1);
 assert.deepEqual(r.signal_events,["Tornado Warning"]);
 assert.equal(r.source_state,"SOURCES_RESPONDED");
 assert.equal(r.damage_verified,false);
 assert.equal(r.homeowner_intent_verified,false);
 assert.equal(r.numeric_damage_risk,null);
});
test("unavailable sources produce null, not false zero or all clear",()=>{
 const r=reviewOfficialWeatherIntelligence({
  checked_at:now.toISOString(),
  alerts:{status:"UNAVAILABLE",items:[]},
  forecast:{status:"AVAILABLE",periods:[]},spc:{status:"UNAVAILABLE"}
 });
 assert.equal(r.source_state,"PARTIAL_SOURCES_RESPONDED");
 assert.equal(r.official_warning_signals,null);
 assert.equal(r.signal_state,"UNKNOWN_SOURCE_UNAVAILABLE");
});
test("founder authorization requires configured private key and correct bearer",()=>{
 const secret="a".repeat(64);
 assert.equal(verifyFounderRequest(new Headers(),secret),"UNAUTHORIZED");
 assert.equal(verifyFounderRequest(new Headers({Authorization:"Bearer "+"x".repeat(64)}),secret),"UNAUTHORIZED");
 assert.equal(verifyFounderRequest(new Headers({Authorization:"Bearer "+secret}),secret),"AUTHORIZED");
 assert.equal(verifyFounderRequest(new Headers({Authorization:"Bearer "+secret}),""),"NOT_CONFIGURED");
});
