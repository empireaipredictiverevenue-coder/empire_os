import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

const page=fs.readFileSync(new URL("../app/page.jsx",import.meta.url),"utf8");
const css=fs.readFileSync(new URL("../app/globals.css",import.meta.url),"utf8");
const image=new URL("../public/visuals/nasa-blue-marble-west.jpg",import.meta.url);

test("original cinematic Earth kept but manufactured telemetry and side boxes removed",()=>{
  assert.match(page,/<GlobeVisual\/\>/);
  assert.match(page,/globe-atmosphere/);
  assert.doesNotMatch(page,/floating-weather|globe-readout|globe-pin|globe-orbit|globe-pulse|SOURCE-FIRST INTELLIGENCE/);
  assert.match(css,/\.home-clean \.globe-sphere/);
  assert.ok(fs.statSync(image).size>40000);
});
test("weather atlas summarizes official feed instead of fabricated radar",()=>{
  assert.match(page,/atlas-overview/);
  assert.match(page,/weather\.data\.alert_count/);
  assert.match(page,/weather\.kind==="error"/);
  assert.match(page,/This is not an all-clear/);
  assert.doesNotMatch(page,/atlas-radar-ring|atlas-radar-core|atlas-grid-lines|STORM EVIDENCE/);
});
test("public homepage avoids template pitches and private founder navigation",()=>{
  assert.doesNotMatch(page,/trust-ribbon|pro-module|module-line|\>Founder Revenue Pulse\</);
  assert.match(page,/No account needed/);
  assert.match(page,/NASA Blue Marble/);
  assert.match(page,/weather\.gov/);
});
