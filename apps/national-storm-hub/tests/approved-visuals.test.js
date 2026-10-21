import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
const p=fs.readFileSync(new URL("../app/page.jsx",import.meta.url),"utf8");
const slide=fs.readFileSync(new URL("../components/StormJourneySlider.jsx",import.meta.url),"utf8");
const css=fs.readFileSync(new URL("../app/globals.css",import.meta.url),"utf8");
test("original cinematic Earth stays and existing intelligence / ZIP search remain",()=>{
 assert.match(p,/<GlobeVisual\/>/);
 assert.match(p,/api\/alerts/);
 assert.match(p,/zip-search/);
 assert.match(p,/StormJourneySlider/);
 assert.match(p,/storm-hub-mark.webp/);
 assert.match(p,/national-storm-hub-logo.webp/);
});
test("approved visuals are isolated from warnings and marked illustrative",()=>{
 for(const s of ["storm-prepare.webp","storm-understand.webp","storm-recover.webp","storm-intelligence-background.webp"])
  assert.ok(css.includes(s),s);
 assert.match(slide,/NOT LIVE WEATHER/);
 assert.match(p,/Storm scene is illustrative/);
 assert.match(css,/journey-cinematic-photo/);
});
test("no new fake severe weather status or duplicate backend added",()=>{
 assert.doesNotMatch(slide,/live radar|real[- ]time storm track|predicted property damage/i);
 assert.match(p,/weather\.kind===/);
});
