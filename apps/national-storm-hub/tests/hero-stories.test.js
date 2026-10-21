import test from "node:test";
import assert from "node:assert/strict";
import {HERO_STORIES,nextHeroIndex} from "../lib/hero-stories.js";
test("three unique useful journeys link to existing truthful features",()=>{
  assert.equal(HERO_STORIES.length,3);
  assert.equal(new Set(HERO_STORIES.map(x=>x.id)).size,3);
  assert.deepEqual(HERO_STORIES.map(x=>x.href),["/predictor","/alerts","#passport"]);
  assert.ok(HERO_STORIES.every(x=>x.description.length>60 && !/AI predicts property damage/i.test(x.description)));
});
test("slider wraps in both directions and never invents a fourth stage",()=>{
  assert.equal(nextHeroIndex(0,-1),2);
  assert.equal(nextHeroIndex(2,1),0);
  assert.equal(nextHeroIndex(0,4),1);
});
