import test from "node:test";
import assert from "node:assert/strict";
import {
  PREDICTOR_EVENTS,normalizePeriods,verifiedForecastUrl,
  spcQueryUrl,normalizeSpc,summarizePredictor
} from "../lib/predictor.js";
test("reuses existing EmpireOS storm event classes without numerical damage claims",()=>{
  assert.deepEqual(PREDICTOR_EVENTS,["Tornado Warning","Severe Thunderstorm Warning","High Wind Warning","Flash Flood Warning"]);
  const s=summarizePredictor({alerts:[{event:"Tornado Warning",source:"https://api.weather.gov/alerts/X"},{event:"Air Quality Alert",source:"https://api.weather.gov/alerts/Y"}],periods:[]});
  assert.equal(s.signal_count,1);
  assert.equal(s.property_damage_predicted,false);
  assert.equal(s.paid_lead_inferred,false);
  assert.equal(s.commercial_authority,"none");
});
test("forecast source rejects server-side SSRF destinations",()=>{
  assert.equal(verifiedForecastUrl({properties:{forecast:"https://api.weather.gov/gridpoints/FWD/89,104/forecast"}}),
    "https://api.weather.gov/gridpoints/FWD/89,104/forecast");
  for(const uri of ["http://api.weather.gov/gridpoints/FWD/89,104/forecast","https://evil.com/gridpoints/FWD/89,104/forecast","https://api.weather.gov.evil.com/gridpoints/FWD/89,104/forecast","https://api.weather.gov/alerts/active"]) {
    assert.throws(()=>verifiedForecastUrl({properties:{forecast:uri}}));
  }
});
test("forecasts never inject raw status or unknown timestamps",()=>{
  const p=normalizePeriods({properties:{periods:[{name:"Tonight",startTime:"2026-10-21T20:00:00-05:00",shortForecast:"Windy",temperature:60,temperatureUnit:"F",windSpeed:"10 mph"}]}});
  assert.equal(p.length,1);
  assert.equal(p[0].temperature,60);
  assert.throws(()=>normalizePeriods({}));
});
test("SPC categorical layers stay categorical with no guessed numeric probability",()=>{
  const category=normalizeSpc({features:[{attributes:{dn:3}},{attributes:{dn:5}}]});
  assert.equal(category.label,"Enhanced");
  assert.equal(category.code,5);
  assert.equal(normalizeSpc({features:[]}),null);
  assert.throws(()=>normalizeSpc({error:{message:"upstream"}}));
  assert.equal(spcQueryUrl(32.7904,-96.8044).startsWith("https://mapservices.weather.noaa.gov/"),true);
  assert.equal(spcQueryUrl(20,-155),null);
  assert.equal(spcQueryUrl(Infinity,4),null);
});
