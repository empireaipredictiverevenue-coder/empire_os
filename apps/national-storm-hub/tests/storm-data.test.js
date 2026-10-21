import test from "node:test";
import assert from "node:assert/strict";
import {
  normalizeState, normalizeZip, normalizeAlert, normalizeAlerts, nwsAlertUrl,
  geocodeFromZippopotam, STATE_NAMES
} from "../lib/storm-data.js";

test("validates every supported state and rejects untrusted geography", () => {
  assert.equal(Object.keys(STATE_NAMES).length,51);
  assert.equal(normalizeState("tx"),"TX");
  assert.equal(normalizeState("xx"),null);
  assert.equal(normalizeState("TX/../FL"),null);
  assert.equal(normalizeZip("75201"),"75201");
  assert.equal(normalizeZip("75201<script>"),null);
  assert.equal(normalizeZip("1234"),null);
});
test("NWS URLs are restricted to weather.gov and validated point/state", () => {
  assert.equal(nwsAlertUrl({state:"TX"}),"https://api.weather.gov/alerts/active?area=TX");
  assert.equal(nwsAlertUrl({state:"FL",latitude:28.54,longitude:-81.38}),
    "https://api.weather.gov/alerts/active?point=28.5400,-81.3800");
  assert.throws(()=>nwsAlertUrl({state:"ZZ",latitude:Infinity,longitude:1}));
});
test("ZIP geocoding has finite coordinates and matching ZIP", () => {
  const data={"post code":"75201",places:[{latitude:"32.7904",longitude:"-96.8044",
    "state abbreviation":"TX","place name":"Dallas"}]};
  assert.equal(geocodeFromZippopotam(data,"75201").state,"TX");
  assert.throws(()=>geocodeFromZippopotam(data,"33101"));
  assert.throws(()=>geocodeFromZippopotam({"post code":"75201",places:[{...data.places[0],latitude:"0"}]},"75201"));
});
test("NWS records retain provenance and never infer damage", () => {
  const f={id:"https://api.weather.gov/alerts/urn:test",properties:{
    event:"Severe Thunderstorm Warning",status:"Actual",severity:"Severe",
    areaDesc:"Dallas County",senderName:"NWS",sent:"2026-10-21T10:00:00Z"
  }};
  const parsed=normalizeAlert(f);
  assert.equal(parsed.event,"Severe Thunderstorm Warning");
  assert.equal(parsed.source,f.id);
  assert.equal(Object.hasOwn(parsed,"damage"),false);
  assert.equal(normalizeAlert({...f,id:"https://evil.test/alert"}),null);
  assert.equal(normalizeAlert({...f,properties:{...f.properties,status:"Test"}}),null);
  assert.deepEqual(normalizeAlerts({features:[f,f]}),[parsed]);
  assert.throws(()=>normalizeAlerts({features:null}));
});
