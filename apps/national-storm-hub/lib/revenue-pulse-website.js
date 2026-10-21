/** Restricted read model of EmpireOS Revenue Pulse V3.
 * Global EmpireOS accounting is NEVER presented as National Storm Hub income.
 * No mutating or revenue-recognition actions live in this module.
 */
const STAGES=new Set(["acquisitions","qualified","buyer_reviews","delivered_outreach","commercial_replies","commercial_terms","verified_payments","fulfilments"]);
function observedCount(x){return Number.isSafeInteger(x)&&x>=0?x:null;}
function cleanText(x,limit=180){return typeof x==="string"?x.slice(0,limit):"";}
export function prepareFounderPulse(raw,now=new Date()){
  if(!raw||raw.schema_version!=="empire.revenue-pulse.v3"||raw.snapshot_source!=="canonical_empiredb_postgres"){
    return {status:"SOURCE_UNAVAILABLE",reason:"CANONICAL_PROVENANCE_MISSING"};
  }
  const generated=new Date(raw.generated_at);
  if(!Number.isFinite(generated.getTime())||!Number.isFinite(now.getTime())){
    return {status:"SOURCE_UNAVAILABLE",reason:"TIMESTAMP_INVALID"};
  }
  const age=(now.getTime()-generated.getTime())/60000;
  const current=raw.current_window;
  if(!current||typeof current!=="object"||!Array.isArray(current.evidence_refs)||current.evidence_refs.length===0){
    return {status:"SOURCE_UNAVAILABLE",reason:"EVIDENCE_MISSING"};
  }
  const stageKeys=[...STAGES];
  const stages=Object.fromEntries(stageKeys.map(k=>[k,observedCount(current[k])]));
  const truth=raw.recognized_revenue_truth||{};
  const revenue=observedCount(truth.recognized_revenue_cents);
  const alerts=Array.isArray(raw.alerts)?raw.alerts.slice(0,15).map(a=>({
    kind:"conversion_gap",
    stage:STAGES.has(a?.stage)?a.stage:null,
    message:cleanText(a?.message),
    prediction:false,
  })).filter(a=>a.stage&&a.message):[];
  const status=age<0||age>20?"STALE":"CURRENT";
  return {
    status,source:"EmpireOS Revenue Pulse V3",
    scope:"EMPIRE_AI_ORGANISATION_WIDE_NOT_NATIONAL_STORM_HUB",
    generated_at:generated.toISOString(),
    age_minutes:Math.round(age*10)/10,
    pulse_state:cleanText(raw.pulse_state,70),
    window_label:cleanText(current.label,50),
    stages,
    recognized_revenue_cents:revenue,
    // No National Storm Hub tenant-bound payment, enquiry or revenue source wired in.
    national_storm_hub:{
      status:"TENANT_ACCOUNTING_NOT_CONNECTED",
      inquiries_verified:null,payments_verified:null,
      recognized_revenue_cents:null,
      engagement_events:null,
    },
    alerts,
    customer_contact_authorized:false,
    payments_authorized:false,
    outbound_authorized:false,
    send_authority:"none",
  };
}
