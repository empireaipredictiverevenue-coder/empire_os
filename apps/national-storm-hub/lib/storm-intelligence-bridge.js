/** Source-backed National Storm Hub ↔ EmpireOS intelligence bridge.
 *
 * Public projections: NWS alert classifications + forecast/SPC review only.
 * Founder projection: minimal read-only existing EmpireOS Storm Intelligence
 * runtime snapshot; no event, buyer, tenant, company or opportunity identities.
 * Never maps forecast or warnings to property damage, customer intent or sales.
 */
const ALLOWED_ALERT_EVENTS=Object.freeze([
  "Tornado Warning","Severe Thunderstorm Warning","High Wind Warning","Flash Flood Warning"
]);
const MAX_SNAPSHOT_AGE_MIN=60;
const dateString=x=>{
  if(typeof x!=="string")return null;
  const date=new Date(x);
  return Number.isFinite(date.getTime())?date.toISOString():null;
};
const isCount=x=>Number.isSafeInteger(x)&&x>=0?x:null;

export function reviewOfficialWeatherIntelligence(raw){
  const alerts=raw?.alerts||{};
  const forecast=raw?.forecast||{};
  const spc=raw?.spc||{};
  const statuses={warnings:alerts.status||"UNAVAILABLE",forecast:forecast.status||"UNAVAILABLE",convective_outlook:spc.status||"UNAVAILABLE"};
  const warningsAvailable=statuses.warnings==="AVAILABLE"&&Array.isArray(alerts.items);
  const forecastAvailable=statuses.forecast==="AVAILABLE"&&Array.isArray(forecast.periods);
  const outlookAvailable=statuses.convective_outlook==="AVAILABLE";
  const tracked=warningsAvailable?alerts.items.filter(x=>x&&ALLOWED_ALERT_EVENTS.includes(x.event)):[];
  const covered=Number(warningsAvailable)+Number(forecastAvailable)+Number(outlookAvailable);
  const sourceTime=dateString(raw?.checked_at);
  return {
    schema_version:"nsh.intelligence_public.v1",
    classification_engine:"empire-storm-predictor-event-review-v1",
    runtime:"DETERMINISTIC_SOURCE_REVIEW",
    checked_at:sourceTime,
    source_state:covered===0?"UNAVAILABLE":covered===3?"SOURCES_RESPONDED":"PARTIAL_SOURCES_RESPONDED",
    source_checks:statuses,
    location_basis:"APPROXIMATE_ZIP_CENTROID",
    official_warning_signals:warningsAvailable?tracked.length:null,
    signal_events:warningsAvailable?[...new Set(tracked.map(x=>x.event))]:[],
    signal_state:!warningsAvailable?"UNKNOWN_SOURCE_UNAVAILABLE":tracked.length?"TRACKED_WARNINGS_PRESENT":"NO_TRACKED_WARNING_TYPES_RETURNED",
    source_context:[
      {type:"WARNINGS",truth_class:"ISSUED_OFFICIAL_ALERT",available:warningsAvailable,
       message:warningsAvailable?
        "Issued NWS warnings in the checked area; coverage and expiry must be reviewed.":"Current NWS warning records could not be checked."},
      {type:"FORECAST",truth_class:"FORECAST_NOT_OBSERVATION",available:forecastAvailable,
       message:forecastAvailable?
        "Official NWS forecast periods describe expected conditions, not confirmed events.":"Local NWS forecast periods could not be verified."},
      {type:"CONVECTIVE_OUTLOOK",truth_class:"REGIONAL_FORECAST",available:outlookAvailable,
       message:outlookAvailable?
        "The SPC layer provides a regional outlook, not an individual-property probability.":
        "The SPC outlook is unavailable or outside the checked layer's geographic coverage."}
    ],
    damage_verified:false,
    commercial_demand_verified:false,
    homeowner_intent_verified:false,
    forecast_accuracy_claimed:false,
    numeric_damage_risk:null,
    execution_authority:"none",
    advice:"Review official weather.gov and SPC sources, warning expiry, and local safety instructions."
  };
}

export function projectEmpireStormRuntime(raw,now=new Date()){
  const unavailable=(reason)=>({
    schema_version:"nsh.empire_storm_runtime_view.v1",status:"UNAVAILABLE",reason,
    mode:"OBSERVE",generated_at:null,age_minutes:null,source_health:null,
    events_reviewed:null,active_commercial_candidates:null,
    commercial_ready:false,execution_authority:"none",
    customer_outreach_authorized:false,payment_authorized:false,
    damage_verified:false,buyer_demand_verified:false,
  });
  if(!raw||raw.schema_version!=="empire.storm_opportunity_snapshot.v1"||
     raw.runtime_schema_version!=="empire.storm_intelligence_runtime.v1"||
     raw.mode!=="OBSERVE"||raw.unknown_stays_unknown!==true||
     raw.execution_authority!=="none"||raw.commercial_authority!=="none"||
     raw.outreach_authority!=="none"||raw.payment_authority!=="none"||
     raw.revenue_recognition_authority!=="none"||
     raw.damage_inferred!==false||raw.demand_inferred!==false||
     raw.buyer_intent_inferred!==false||raw.economics_inferred!==false||
     raw.pricing_inferred!==false||raw.automatic_external_execution_allowed!==false){
    return unavailable("INVALID_CANONICAL_AUTHORITY_OR_PROVENANCE");
  }
  const timestamp=dateString(raw.generated_at);
  if(!timestamp||!Number.isFinite(now.getTime()))return unavailable("INVALID_TIMESTAMP");
  const elapsedMinutes=(now.getTime()-new Date(timestamp).getTime())/60000;
  if(elapsedMinutes<0)return unavailable("FUTURE_SNAPSHOT");
  const isCurrent=elapsedMinutes<=MAX_SNAPSHOT_AGE_MIN;
  const diagnostics=raw.diagnostics;
  if(!diagnostics||typeof diagnostics!=="object"||
     isCount(diagnostics.events_seen)===null||
     isCount(raw.candidate_count)===null||
     !Array.isArray(raw.candidates)||raw.candidates.length!==raw.candidate_count){
    return unavailable("INVALID_RUNTIME_COUNTS");
  }
  return {
    schema_version:"nsh.empire_storm_runtime_view.v1",
    status:isCurrent?"CURRENT":"STALE",
    reason:isCurrent?"VERIFIED_RUNTIME_SNAPSHOT":"SNAPSHOT_OLDER_THAN_60_MINUTES",
    mode:"OBSERVE",source:"EmpireOS Storm Intelligence Runtime",
    scope:"EMPIREOS_INTERNAL_NOT_NATIONAL_STORM_HUB_COMMERCIAL_TENANT",
    generated_at:timestamp,
    age_minutes:Math.round(elapsedMinutes),
    source_health:isCurrent&&["HEALTHY","DEGRADED","UNAVAILABLE"].includes(diagnostics.source_health)?
      diagnostics.source_health:"UNKNOWN",
    events_reviewed:isCurrent?diagnostics.events_seen:null,
    active_commercial_candidates:null,
    archived_candidate_count:raw.candidate_count,
    missing_evidence:isCurrent&&isCount(diagnostics.blocked_count)!==null?
      diagnostics.blocked_count:null,
    commercial_ready:false,
    execution_authority:"none",
    customer_outreach_authorized:false,payment_authorized:false,
    damage_verified:false,buyer_demand_verified:false,
    explanatory_note:isCurrent?
     "Historical internal observation counts are not geolocated leads, verified buyer intent or National Storm Hub revenue.":
     "The canonical storm snapshot is stale. Fresh source and scoped readiness evidence must be obtained before any commercial inference.",
  };
}
