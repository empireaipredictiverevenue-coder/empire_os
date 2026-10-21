import test from "node:test";
import assert from "node:assert/strict";
import {summarizeHomeSource} from "../lib/home-source-view.js";
const record=(count,alerts=[])=>({kind:"ready",data:{
  source:"National Weather Service",
  checked_at:"2026-10-21T10:00:00Z",
  alert_count:count,alerts,area:"Texas"
}});
test("waiting cannot look like no alerts",()=>{
  const x=summarizeHomeSource({kind:"loading"});
  assert.equal(x.phase,"loading");assert.equal(x.count,null);
});
test("error cannot look like an all clear",()=>{
  const x=summarizeHomeSource({kind:"error",message:"timeout"});
  assert.equal(x.phase,"unavailable");assert.equal(x.count,null);
});
test("zero records are explicitly not an all clear",()=>{
  const x=summarizeHomeSource(record(0));
  assert.equal(x.count,0);assert.equal(x.phase,"available");
  assert.match(x.detail,/not an all-clear/);
});
test("source, date and count must validate",()=>{
  assert.equal(summarizeHomeSource(record(3,[])).phase,"unavailable");
  assert.equal(summarizeHomeSource({kind:"ready",data:{...record(0).data,source:"unknown"}}).phase,"unavailable");
  assert.equal(summarizeHomeSource({kind:"ready",data:{...record(0).data,checked_at:"bad"}}).phase,"unavailable");
});
test("one alert displays exact scoped evidence",()=>{
  const x=summarizeHomeSource(record(1,[{id:"NWS-A"}]));
  assert.equal(x.title,"1 active alert returned");
  assert.equal(x.area,"Texas");
  assert.match(x.detail,/do not prove property damage/);
  assert.equal(x.checked_at,"2026-10-21T10:00:00.000Z");
});
