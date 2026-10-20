import assert from "node:assert/strict";
import * as THREE from "three";
import { createScrollWorldFrame, sampleScrollWorld } from "../src/components/scroll-world-director.ts";

const pos = new THREE.Vector3(), look = new THREE.Vector3();
const frames = [0, 0.25, 0.5, 0.75, 1].map(t => {
  const frame = sampleScrollWorld(t, 1, pos, look);
  assert.equal(frame.progress, t);
  assert.ok([pos.x,pos.y,pos.z,look.x,look.y,look.z].every(Number.isFinite));
  return { t, chapter: frame.chapter, position: pos.clone(), look: look.clone(), warmth: frame.warmth };
});
assert.deepEqual(frames.map(x => x.chapter), [0,1,2,3,4]);
assert.ok(frames.every((x,i) => i===0 || x.position.z < frames[i-1].position.z));
assert.ok(frames[4].warmth > frames[0].warmth);

const reused = createScrollWorldFrame();
assert.strictEqual(sampleScrollWorld(0.8, 1, pos, look, reused), reused);
assert.equal(reused.progress, 0.8);
assert.strictEqual(sampleScrollWorld(0.2, 1, pos, look, reused), reused);
assert.equal(reused.progress, 0.2);
sampleScrollWorld(0.8, 1, pos, look, reused);
const forward = [pos.toArray(),look.toArray()];
sampleScrollWorld(0.2, 1, pos, look);
sampleScrollWorld(0.8, 1, pos, look);
assert.deepEqual([pos.toArray(), look.toArray()],forward);

for (const boundary of [0.125,0.375,0.625,0.875]) {
  sampleScrollWorld(boundary-0.0001,1,pos,look); const before=pos.clone();
  sampleScrollWorld(boundary+0.0001,1,pos,look); const after=pos.clone();
  assert.ok(before.distanceTo(after) < 0.02, "Discontinuous camera at " + boundary);
}

sampleScrollWorld(0,0,pos,look); const hero=pos.clone();
sampleScrollWorld(1,0,pos,look); assert.ok(pos.distanceTo(hero)<1e-10);
const clamped = sampleScrollWorld(Number.NaN,100,pos,look);
assert.equal(clamped.progress,0);assert.equal(clamped.entry,1);
console.log("SCROLL_WORLD_DIRECTOR_PASS",frames.map(({t,chapter,warmth})=>({t,chapter,warmth})));
