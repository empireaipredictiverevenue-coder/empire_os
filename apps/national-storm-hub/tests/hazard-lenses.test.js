import test from "node:test";
import assert from "node:assert/strict";
import {HAZARD_LENSES} from "../lib/hazard-lenses.js";
test("hazard slider has four unique editorial lanes with trustworthy external sources",()=>{
  assert.equal(HAZARD_LENSES.length,4);
  assert.equal(new Set(HAZARD_LENSES.map(h=>h.id)).size,4);
  assert.ok(HAZARD_LENSES.every(h=>h.href.startsWith("https://") && h.summary.length>80));
  assert.ok(HAZARD_LENSES.every(h=>!h.summary.includes("your property has been damaged")));
});
