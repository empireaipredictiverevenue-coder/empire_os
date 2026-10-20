/**
 * Internal, pure source-readiness review for the Empire AI ROI assessment.
 *
 * Source of truth: existing EmpireOS canonical OBSERVE snapshots. This is NOT
 * a public adapter. No private row, tenant, opportunity, source ref, market,
 * probability or forecast is copied into a public Next.js page.
 *
 * Approval to display public evidence is separate and intentionally absent.
 */
export type RoiSourceName =
  "PREDICTIVE_INTELLIGENCE" | "MARKET_INTELLIGENCE" | "OPPORTUNITY_INTELLIGENCE";
export type RoiReadinessStatus =
  "SOURCE_INVALID" | "SOURCE_STALE" | "INSUFFICIENT_VERIFIED_EVIDENCE" | "INTERNAL_REVIEW_ONLY";
export type RoiSourceReadiness = Readonly<{
  source: RoiSourceName;
  status: RoiReadinessStatus;
  publicUseAuthorized: false;
  forecastAvailableToVisitor: false;
  shortReason: string;
}>;

type Snapshot = Record<string, unknown>;
const isRecord=(value:unknown):value is Snapshot =>
  value!==null && typeof value==="object" && !Array.isArray(value);
const count=(value:unknown):number|null=>
  typeof value==="number" && Number.isSafeInteger(value) && value>=0 ? value : null;
const freshness=(input:Snapshot,now:Date):boolean=>{
  const raw=input.generated_at;
  if(typeof raw!=="string"||!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d/.test(raw))return false;
  const timestamp=Date.parse(raw);
  return Number.isFinite(timestamp)&&timestamp<=now.getTime()+60_000 &&
    now.getTime()-timestamp<=86_400_000;
};
const status=(source:RoiSourceName,status:RoiReadinessStatus,shortReason:string):RoiSourceReadiness=>({
  source,status,shortReason,publicUseAuthorized:false,forecastAvailableToVisitor:false,
});

/** Fail closed even on internally available evidence without public release. */
export function reviewRoiSource(
  source:RoiSourceName,
  raw:unknown,
  now:Date=new Date(),
):RoiSourceReadiness {
  if(!isRecord(raw)||raw.mode!=="OBSERVE"||!Number.isFinite(now.getTime())) {
    return status(source,"SOURCE_INVALID","No valid canonical observation snapshot");
  }
  const expected={
    PREDICTIVE_INTELLIGENCE:"empire.predictive_intelligence.v1",
    MARKET_INTELLIGENCE:"empire.market_sweep_revenue_gps.v1",
    OPPORTUNITY_INTELLIGENCE:"empire.opportunity_evidence_normalizer_batch.v1",
  } as const;
  if(raw.schema_version!==expected[source]||raw.execution_authority!=="none" ||
      (source==="PREDICTIVE_INTELLIGENCE"&&raw.tenant_id!=null)) {
    return status(source,"SOURCE_INVALID","Source schema, scope or authority is not eligible");
  }
  if(!freshness(raw,now)) {
    return status(source,"SOURCE_STALE","Existing intelligence snapshot requires a fresh observation");
  }
  if(source==="PREDICTIVE_INTELLIGENCE"){
    const matches=count(raw.matched_outcome_count);
    const probabilities=count(raw.probability_ready_product_count);
    if(matches===null||probabilities===null||probabilities>matches||
      raw.probability_source!=="verified_terminal_commercial_outcomes_only" ||
      raw.unverified_pipeline_state_used_as_outcome!==false ||
      raw.llm_probability_used!==false ||
      raw.search_scores_used!==false) {
      return status(source,"SOURCE_INVALID","Predictive evidence safeguards are not satisfied");
    }
    if(probabilities===0) {
      return status(source,"INSUFFICIENT_VERIFIED_EVIDENCE",
        "No calibrated product-level commercial probability is ready");
    }
    return status(source,"INTERNAL_REVIEW_ONLY",
      "Verified cohort estimates exist internally, but no public-use approval has been supplied");
  }
  if(source==="MARKET_INTELLIGENCE"){
    const demand=count(raw.commercial_demand_market_count);
    if(demand===null||raw.buyer_intent_inferred!==false ||
      raw.market_share_inferred!==false||raw.revenue_inferred!==false ||
      raw.restricted_source_scope!=="RESTRICTED_AGGREGATES_ONLY") {
      return status(source,"SOURCE_INVALID","Market source cannot support a customer demand claim");
    }
    return demand===0
      ?status(source,"INSUFFICIENT_VERIFIED_EVIDENCE","No market has verified commercial demand in the checked snapshot")
      :status(source,"INTERNAL_REVIEW_ONLY","Market evidence is internal and not approved for visitors");
  }
  const scores=count(raw.total_normalized_scores);
  if(scores===null||raw.revenue_inferred!==false ||
      raw.market_share_inferred!==false||raw.search_result_counts_used_as_scores!==false) {
    return status(source,"SOURCE_INVALID","Opportunity evidence does not pass source checks");
  }
  return scores===0
    ?status(source,"INSUFFICIENT_VERIFIED_EVIDENCE",
      "No normalized source-backed opportunity score is ready")
    :status(source,"INTERNAL_REVIEW_ONLY","Opportunity scores are not real sales or authorised public predictions");
}

/** Intentionally returns only fixed text, not even aggregate counts. */
export function reviewRoiSources(
  snapshots:Partial<Record<RoiSourceName,unknown>>,
  now:Date=new Date(),
):readonly RoiSourceReadiness[] {
  return (["PREDICTIVE_INTELLIGENCE","MARKET_INTELLIGENCE","OPPORTUNITY_INTELLIGENCE"] as const)
    .map(name=>reviewRoiSource(name,snapshots[name],now));
}
