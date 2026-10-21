import test from "node:test";
import assert from "node:assert/strict";
import {formatWeatherTime} from "../lib/weather-time.js";
test("official source timestamps format without invalid ICU option combinations",()=>{
  const value=formatWeatherTime("2026-10-21T10:00:00Z");
  assert.match(value,/2026/);
  assert.match(value,/Oct/);
  assert.match(value,/\d/);
});
test("missing or invalid source times never crash a homepage or alert card",()=>{
  assert.equal(formatWeatherTime(null),"Time unavailable");
  assert.equal(formatWeatherTime("invalid","No source time"),"No source time");
  assert.equal(formatWeatherTime("","Not provided"),"Not provided");
});
