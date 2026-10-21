/**
 * Public NWS weather alert reader. No personal-data storage or mutation.
 * A current alert is not evidence that any individual property was damaged.
 */
export const STATE_NAMES = Object.freeze({
  AL:"Alabama",AK:"Alaska",AZ:"Arizona",AR:"Arkansas",CA:"California",
  CO:"Colorado",CT:"Connecticut",DE:"Delaware",FL:"Florida",GA:"Georgia",
  HI:"Hawaii",ID:"Idaho",IL:"Illinois",IN:"Indiana",IA:"Iowa",KS:"Kansas",
  KY:"Kentucky",LA:"Louisiana",ME:"Maine",MD:"Maryland",MA:"Massachusetts",
  MI:"Michigan",MN:"Minnesota",MS:"Mississippi",MO:"Missouri",MT:"Montana",
  NE:"Nebraska",NV:"Nevada",NH:"New Hampshire",NJ:"New Jersey",NM:"New Mexico",
  NY:"New York",NC:"North Carolina",ND:"North Dakota",OH:"Ohio",OK:"Oklahoma",
  OR:"Oregon",PA:"Pennsylvania",RI:"Rhode Island",SC:"South Carolina",
  SD:"South Dakota",TN:"Tennessee",TX:"Texas",UT:"Utah",VT:"Vermont",
  VA:"Virginia",WA:"Washington",WV:"West Virginia",WI:"Wisconsin",WY:"Wyoming",
  DC:"District of Columbia"
});
const ALLOWED_LEVELS = new Set(["Extreme","Severe","Moderate","Minor","Unknown"]);
export const ZIP_PATTERN = /^[0-9]{5}$/;
const safeText = (input, max=500) => typeof input === "string" ? input.trim().slice(0,max) : "";
export function normalizeState(input) {
  const code = typeof input === "string" ? input.trim().toUpperCase() : "";
  return /^[A-Z]{2}$/.test(code) && Object.hasOwn(STATE_NAMES,code) ? code : null;
}
export function normalizeZip(input) {
  const z = typeof input === "string" ? input.trim() : "";
  return ZIP_PATTERN.test(z) ? z : null;
}
export function normalizeAlert(feature) {
  if (!feature || typeof feature !== "object" || !feature.properties) return null;
  const p = feature.properties;
  const id = safeText(feature.id ?? p.id,400);
  if (!id.startsWith("https://api.weather.gov/alerts/")) return null;
  if (p.status && p.status !== "Actual") return null;
  if (p.messageType === "Cancel") return null;
  const event = safeText(p.event,120);
  if (!event) return null;
  const severity = ALLOWED_LEVELS.has(p.severity) ? p.severity : "Unknown";
  return {
    id, event, severity,
    headline: safeText(p.headline || event,280),
    area: safeText(p.areaDesc,400),
    description: safeText(p.description,1000),
    instruction: safeText(p.instruction,1000),
    issuer: safeText(p.senderName,140) || "National Weather Service",
    sent: safeText(p.sent,40),
    effective: safeText(p.effective,40),
    expires: safeText(p.expires,40),
    source: id,
  };
}
export function normalizeAlerts(geojson) {
  if (!geojson || !Array.isArray(geojson.features)) throw new Error("INVALID_NWS_RESPONSE");
  const seen = new Set();
  return geojson.features.map(normalizeAlert).filter(item => {
    if (!item || seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  }).slice(0,25);
}
export function nwsAlertUrl({ state, latitude, longitude }) {
  if (typeof latitude === "number" && Number.isFinite(latitude) &&
      typeof longitude === "number" && Number.isFinite(longitude) &&
      latitude >= 18 && latitude <= 72 && longitude >= -180 && longitude <= -60) {
    return "https://api.weather.gov/alerts/active?point="+latitude.toFixed(4)+","+longitude.toFixed(4);
  }
  const code = normalizeState(state);
  if (!code) throw new Error("INVALID_REGION");
  return "https://api.weather.gov/alerts/active?area="+code;
}
export function geocodeFromZippopotam(payload, expectedZip) {
  const place = payload?.places?.[0];
  if (!place || payload["post code"] !== expectedZip) throw new Error("ZIP_NOT_FOUND");
  const latitude = Number(place.latitude), longitude = Number(place.longitude);
  const state = normalizeState(place["state abbreviation"]);
  if (!state || !Number.isFinite(latitude) || !Number.isFinite(longitude) ||
      latitude < 18 || latitude > 72 || longitude < -180 || longitude > -60) {
    throw new Error("INVALID_ZIP_LOCATION");
  }
  return {latitude,longitude,state,name:safeText(place["place name"],100),zip:expectedZip};
}
