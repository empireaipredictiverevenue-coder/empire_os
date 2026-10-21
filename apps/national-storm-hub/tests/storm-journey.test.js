import test from "node:test";
import assert from "node:assert/strict";
import {STORM_JOURNEYS,journeyIndex} from "../lib/storm-journey.js";
test("three original homeowner stages with safe genuine destinations",()=>{
 assert.deepEqual(STORM_JOURNEYS.map(s=>s.id),["prepare","understand","recover"]);
 assert.ok(STORM_JOURNEYS.every(s=>s.actions.length===3 && s.description.length>90));
 assert.deepEqual(STORM_JOURNEYS.map(s=>s.primary.href),["#passport","/alerts","/recovery"]);
 assert.ok(STORM_JOURNEYS.every(s=>s.secondary.href.startsWith("https://")));
 assert.ok(STORM_JOURNEYS.every(s=>!(/guaranteed|damaged home|pay now|AI-driven|urgent repair lead/i.test(JSON.stringify(s)))));
});
test("arrows and swipe wrap around and skip invalid indices",()=>{
 assert.equal(journeyIndex(0,-1),2);
 assert.equal(journeyIndex(2,1),0);
 assert.equal(journeyIndex(1,1),2);
 assert.throws(()=>journeyIndex(0,1,0));
});
