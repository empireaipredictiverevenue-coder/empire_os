/**
 * National Storm Hub consumer predictor: read-only, source-first projection.
 *
 * Preserves EmpireOS storm_predictor.py classifications, but intentionally
 * excludes commercial intent, lead generation, automated actions and the
 * legacy predictor's unsupported numerical severity/demand score.
 */
export const PREDICTOR_EVENTS=Object.freeze([
  "Tornado Warning","Severe Thunderstorm Warning","High Wind Warning","Flash Flood Warning"
]);
export const SPC_LABELS=Object.freeze({
  2:"General Thunderstorm",3:"Marginal",4:"Slight",
  5:"Enhanced",6:"Moderate",8:"High"
});
const STR=s=>typeof s==="string"?s.trim():"";
function clean(s,max=300){return STR(s).slice(0,max);}
export function normalizePeriods(data) {
  const periods=data?.properties?.periods;
  if(!Array.isArray(periods))throw new Error("NWS_FORECAST_INVALID");
  return periods.slice(0,8).map(p=>({
    name:clean(p?.name,70),
    start:clean(p?.startTime,50),
    end:clean(p?.endTime,50),
    forecast:clean(p?.shortForecast,220),
    details:clean(p?.detailedForecast,550),
    temperature:typeof p?.temperature==="number"&&Number.isFinite(p.temperature)?p.temperature:null,
    unit:["F","C"].includes(p?.temperatureUnit)?p.temperatureUnit:null,
    wind:clean(p?.windSpeed,40),
    windDirection:clean(p?.windDirection,30),
    isDaytime:p?.isDaytime===true
  })).filter(p=>p.name&&p.start);
}
export function verifiedForecastUrl(points) {
  const raw=points?.properties?.forecast;
  if(typeof raw!=="string")throw new Error("NO_FORECAST_URL");
  const u=new URL(raw);
  if(u.protocol!=="https:" || u.hostname!=="api.weather.gov" ||
     u.username || u.password || u.search || u.hash ||
     !/^\/gridpoints\/[A-Z]{2,5}\/\d{1,4},\d{1,4}\/forecast\/?$/.test(u.pathname)) {
    throw new Error("INVALID_FORECAST_SOURCE");
  }
  return u.toString();
}
export function spcQueryUrl(latitude,longitude) {
  if(!Number.isFinite(latitude)||!Number.isFinite(longitude)||
     latitude<24||latitude>50||longitude< -125||longitude> -66) return null;
  const params=new URLSearchParams({
    where:"1=1",geometry:`${longitude.toFixed(4)},${latitude.toFixed(4)}`,
    geometryType:"esriGeometryPoint",inSR:"4326",
    spatialRel:"esriSpatialRelIntersects",outFields:"dn,valid,expire,issue",returnGeometry:"false",f:"json"
  });
  return "https://mapservices.weather.noaa.gov/vector/rest/services/outlooks/SPC_wx_outlks/FeatureServer/1/query?"+params.toString();
}
export function normalizeSpc(payload) {
  if(!payload||payload.error||!Array.isArray(payload.features))throw new Error("SPC_RESPONSE_INVALID");
  const categories=payload.features.map(f=>{
    const a=f?.attributes||{},dn=Number(a.dn);
    return Object.hasOwn(SPC_LABELS,dn)?{
      label:SPC_LABELS[dn],code:dn,
      valid:typeof a.valid==="string"?clean(a.valid,60):null,
      source:"https://www.spc.noaa.gov/products/outlook/"
    }:null;
  }).filter(Boolean);
  categories.sort((a,b)=>b.code-a.code);
  return categories[0]||null;
}
export function summarizePredictor({alerts=[],periods=[],spc=null}){
  const signals=alerts.filter(a=>PREDICTOR_EVENTS.includes(a.event)).map(a=>({
    event:a.event,source:a.source,expires:a.expires,severity:a.severity,
  }));
  const selected=periods.slice(0,6);
  return {
    model:"empire-storm-predictor-event-review-v1",
    model_kind:"EVIDENCE_CLASSIFICATION_NOT_DAMAGE_PREDICTION",
    storm_signals:signals,
    signal_count:signals.length,
    outlook:spc,
    next_periods:selected.length,
    overview:selected.length?
      "Review the official forecast periods and current warnings below; neither proves storm damage at a property.":
      "No point-forecast periods could be verified.",
    property_damage_predicted:false,
    paid_lead_inferred:false,
    commercial_authority:"none",
    recommended_action:"Consult NWS and local authorities. Use household preparedness checklists."
  };
}
