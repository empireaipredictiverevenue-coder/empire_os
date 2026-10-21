import test from "node:test";
import assert from "node:assert/strict";
import {STATE_HUBS,getStateHub} from "../lib/state-hubs.js";
test("state pilot pages contain distinct original topics and canonical official sources",()=>{
  assert.deepEqual(Object.keys(STATE_HUBS).sort(),["florida","texas"]);
  assert.equal(getStateHub("florida").code,"FL");
  assert.equal(getStateHub("texas").code,"TX");
  assert.notEqual(getStateHub("florida").headline,getStateHub("texas").headline);
  assert.notDeepEqual(getStateHub("florida").themes,getStateHub("texas").themes);
  for(const region of Object.values(STATE_HUBS)){
    assert.equal(region.steps.length,4);
    assert.ok(region.sources.length>=2);
    assert.ok(region.sources.every(x=>x.href.startsWith("https://")));
  }
  assert.equal(getStateHub("__proto__"),null);
  assert.equal(getStateHub("new-york"),null);
});
