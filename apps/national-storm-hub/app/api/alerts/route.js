import { NextResponse } from "next/server";
import {
  normalizeZip, normalizeState, geocodeFromZippopotam,
  nwsAlertUrl, normalizeAlerts, STATE_NAMES
} from "../../../lib/storm-data.js";

export const dynamic = "force-dynamic";
const ERROR_HEADERS = {"Cache-Control":"no-store"};
const nwsAgent = process.env.STORM_HUB_NWS_USER_AGENT ||
  "NationalStormHubPreview/0.1 (https://nationalstormhub.com)";
async function readJSON(url, headers = {}) {
  const resp = await fetch(url, {
    headers: {"Accept":"application/geo+json, application/json", ...headers},
    next: {revalidate:120},
    signal: AbortSignal.timeout(8000),
  });
  if (!resp.ok) throw new Error("SOURCE_HTTP_"+resp.status);
  return resp.json();
}
export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const rawZip = searchParams.get("zip");
  const rawState = searchParams.get("state");
  if (rawZip != null && !normalizeZip(rawZip)) {
    return NextResponse.json({error:"Enter a valid five-digit US ZIP code."},{status:400,headers:ERROR_HEADERS});
  }
  if (rawZip == null && !normalizeState(rawState || "TX")) {
    return NextResponse.json({error:"Choose a valid US state."},{status:400,headers:ERROR_HEADERS});
  }
  try {
    let location;
    if (rawZip != null) {
      const zip = normalizeZip(rawZip);
      const payload = await readJSON("https://api.zippopotam.us/us/"+zip);
      location = geocodeFromZippopotam(payload, zip);
    } else {
      const state = normalizeState(rawState || "TX");
      location = {state,name:STATE_NAMES[state],zip:null};
    }
    const raw = await readJSON(nwsAlertUrl(location), {"User-Agent":nwsAgent});
    const alerts = normalizeAlerts(raw);
    return NextResponse.json({
      status:"SOURCE_CHECKED",
      mode: location.zip ? "ZIP_CENTROID" : "STATEWIDE",
      area:location.name,
      state:location.state,
      zip:location.zip,
      checked_at:new Date().toISOString(),
      source:"National Weather Service",
      source_home:"https://www.weather.gov/",
      alert_count:alerts.length,
      alerts,
      disclaimer:"Official NWS source records. Alerts do not prove property damage. ZIP locations use approximate centroids. For emergencies follow local authorities.",
    },{headers:{"Cache-Control":"no-store"}});
  } catch (err) {
    const code = String(err?.message || "");
    if (code === "ZIP_NOT_FOUND" || code === "INVALID_ZIP_LOCATION") {
      return NextResponse.json({error:"We couldn't locate that ZIP code. Choose a state instead."},
        {status:404,headers:ERROR_HEADERS});
    }
    return NextResponse.json({
      error:"Live NWS information could not be retrieved. Use weather.gov for official updates.",
      status:"SOURCE_UNAVAILABLE",
    },{status:503,headers:ERROR_HEADERS});
  }
}
