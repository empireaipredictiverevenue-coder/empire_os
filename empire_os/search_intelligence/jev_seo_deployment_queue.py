"""Deployment-grade *proposal* queue from 30 actual Jev choices and GSC URLs.

No new model calls, historical-content invention, redirects, public publishing
or revenue recognition. Outputs carry the original source provenance and
distinguish an editorial opportunity from an approved landing-page change.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from .ai_first_seo_review import validated_cases
from .jev_case_receipts import ROOT, PINNED_SHA256, reviewed_case_summary

SCHEMA="empire.search.jev_evidence_to_deployment_queue.v1"
CASE_LIMIT=30
CORE_CATEGORIES={
    "BUYER_INTENT_EDITORIAL_REVIEW",
    "EMPIRE_PRODUCT_TOPIC_REVIEW",
    "ROOFING_RESEARCH_REVIEW",
}
LANE_SPEC={
    "BUYER_INTENT_EDITORIAL_REVIEW":{
        "workstream":"ORIGINAL_BUYER_INTENT_TAM_RESEARCH",
        "candidate_existing_asset":"docs/seo/BUYER_INTENT_TAM_EDITORIAL_DRAFT_20261015.md",
        "potential_related_live_page":"/predictive-revenue",
        "next_work":"EVALUATE_EXISTING_TAM_BRIEF_AND_ORIGINAL_SCOPE_FOR_HELPFUL_ARTICLE",
    },
    "EMPIRE_PRODUCT_TOPIC_REVIEW":{
        "workstream":"PREDICTIVE_REVENUE_PRODUCT_CONTENT_RESEARCH",
        "candidate_existing_asset":"docs/seo/ASTRA_REVENUE_FIRST_ORIGINAL_SEO_BRIEFS_20261017.md",
        "potential_related_live_page":"/predictive-revenue",
        "next_work":"REVIEW_PRODUCT_TOPIC_AGAINST_EXISTING_PREDICTIVE_REVENUE_PAGE",
    },
    "ROOFING_RESEARCH_REVIEW":{
        "workstream":"ROOFING_HELPFUL_CONTENT_RESEARCH",
        "candidate_existing_asset":"apps/empire-public-site/src/app/roofing/page.tsx",
        "potential_related_live_page":"/roofing",
        "next_work":"REVIEW_EXISTING_HOMEOWNER_GUIDES_AND_BUYER_SERVICE_EVIDENCE",
    },
}
EXPECTED_JEV_CHOICE="SOURCE_AUDIT"


class JevDeploymentQueueHeld(ValueError):
    pass


def _digest(p: Path) -> str:
    return sha256(p.read_bytes()).hexdigest()


def prepare_jev_seo_deployment_queue(
    *,
    cases: list[dict[str,Any]] | None=None,
    provider_records: list[dict[str,Any]] | None=None,
    source_root: Path=Path("/srv/empire_os"),
    receipt_root: Path=ROOT,
    pinned_hashes: tuple[str,...]=PINNED_SHA256,
) -> dict[str,Any]:
    original=validated_cases() if cases is None else cases
    if not isinstance(original,list) or len(original)!=CASE_LIMIT:
        raise JevDeploymentQueueHeld("GSC_COHORT_MISSING_OR_CHANGED")
    keys={r["case_id"] for r in original}
    if len(keys)!=CASE_LIMIT:
        raise JevDeploymentQueueHeld("SOURCE_CASE_IDS_DUPLICATED")
    recorded=reviewed_case_summary(
        root=receipt_root,hashes=pinned_hashes,source_case_ids=keys)
    if (recorded.get("validated_model_responses")!=30
            or recorded.get("model_prediction_accuracy_verified") is not False
            or recorded.get("model_outputs_are_human_labels") is not False
            or recorded.get("new_inference_requests_during_status")!=0):
        raise JevDeploymentQueueHeld("UNVERIFIED_MODEL_RECEIPTS")
    if provider_records is None:
        provider_records=[]
        for i,digest in enumerate(pinned_hashes):
            path=receipt_root/f"jev_page_batch_{i}_20261022.json"
            if path.is_symlink() or not path.is_file() or _digest(path)!=digest:
                raise JevDeploymentQueueHeld("SOURCE_MODEL_HASH_CHANGED")
            doc=json.loads(path.read_text(encoding="utf-8"))
            provider_records.extend(doc["case_reviews"])
    if not isinstance(provider_records,list) or len(provider_records)!=CASE_LIMIT:
        raise JevDeploymentQueueHeld("MODEL_REVIEW_COHORT_MISMATCH")
    by_id={p["case_id"]:p for p in provider_records if isinstance(p,Mapping)}
    if len(by_id)!=CASE_LIMIT or set(by_id)!=keys:
        raise JevDeploymentQueueHeld("MODEL_SOURCE_JOIN_FAILED")
    source_assets={}
    for lane in LANE_SPEC.values():
        rel=lane["candidate_existing_asset"]
        file=source_root/rel
        if (file.is_symlink() or not file.is_file()
                or not file.resolve().is_relative_to(source_root.resolve())
                or file.stat().st_size<100):
            raise JevDeploymentQueueHeld("RELEVANT_ORIGINAL_SOURCE_ASSET_MISSING")
        source_assets[rel]="repo-sha256:"+_digest(file)

    queue=[]
    for row in original:
        case_id=row["case_id"]
        model=by_id[case_id]
        if (model.get("source_ref")!=row["source_ref"]
                or model.get("choice")!=EXPECTED_JEV_CHOICE
                or model.get("human_ground_truth") is not False
                or model.get("source_content_verified") is not False
                or model.get("publisher_rights_verified") is not False
                or model.get("automatic_redirect_authority") is not False
                or model.get("publish_authority") is not False):
            raise JevDeploymentQueueHeld("MODEL_CASE_PROVENANCE_OR_AUTHORITY_MISMATCH")
        category=row["deterministic_review_category"]
        if category in CORE_CATEGORIES:
            lane=LANE_SPEC[category]
            task_type="EDITORIAL_EVIDENCE_RESEARCH_ONLY"
            next_action=lane["next_work"]
            suggested_asset=lane["candidate_existing_asset"]
            related_page=lane["potential_related_live_page"]
            related_truth="RELATED_PAGE_ONLY_NOT_HISTORICAL_EQUIVALENCE"
            source_asset_digest=source_assets[suggested_asset]
            requires_source_recovery=True
            group=lane["workstream"]
        elif category=="OFF_CORE_RETAIN_404_PENDING_EVIDENCE":
            task_type="RETAIN_404_AND_MONITOR"
            next_action="COLLECT_STRONGER_FIRST_PARTY_DEMAND_BEFORE_ANY_RESTORATION"
            suggested_asset=None
            related_page=None
            related_truth="NO_EQUIVALENT_PAGE_CLAIM"
            source_asset_digest=None
            requires_source_recovery=False
            group="OFF_CORE_LEGACY_MONITOR"
        else:
            raise JevDeploymentQueueHeld("UNKNOWN_CASE_CATEGORY")
        impressions=row["observed_page_dimension_impressions"]
        if type(impressions) is not int or not 0<=impressions<=100_000:
            raise JevDeploymentQueueHeld("UNVERIFIED_IMPRESSIONS")
        if type(model.get("confidence")) not in (float,int) or not 0<=model["confidence"]<=1:
            raise JevDeploymentQueueHeld("MODEL_CONFIDENCE_INVALID")
        priority=("RESEARCH_CORE_FIRST" if task_type=="EDITORIAL_EVIDENCE_RESEARCH_ONLY"
                  else "HOLD_OFF_CORE")
        queue.append({
            "case_id":case_id,
            "first_party_path":row["path"], # stays private; not in public API.
            "gsc_page_evidence_ref":row["source_ref"],
            "jev_review_evidence_ref":"jev-page-choice:"+sha256(
                (case_id+"|"+model["choice"]+"|"+str(model["confidence"])).encode()).hexdigest(),
            "source_window":row["window"],
            "observed_origin_http_status":row["observed_origin_http_status"],
            "sample_impressions":impressions,
            "sample_clicks":row["observed_page_dimension_clicks"],
            "rule_category":category,
            "model_recommended_work":model["choice"],
            "model_confidence":model["confidence"],
            "workstream":group,
            "work_type":task_type,
            "investigate_first":priority,
            "next_research_step":next_action,
            "related_owned_page_for_context":related_page,
            "related_page_evidence_status":related_truth,
            "existing_original_asset_for_review":suggested_asset,
            "existing_asset_sha256":source_asset_digest,
            "historical_page_text_recovered":False,
            "original_publisher_rights_verified":False,
            "source_to_related_page_equivalence_verified":False,
            "original_new_content_drafted":False,
            "published_or_redirected":False,
            "automatic_website_change_authorized":False,
            "source_recovery_required":requires_source_recovery,
            "qualified_buyer_enquiry_verified":False,
            "revenue_recognised":False,
        })
    queue.sort(key=lambda r: (
        0 if r["work_type"]=="EDITORIAL_EVIDENCE_RESEARCH_ONLY" else 1,
        -r["sample_impressions"],r["first_party_path"],
    ))
    types=Counter(r["work_type"] for r in queue)
    groups=Counter(r["workstream"] for r in queue)
    count_core=types["EDITORIAL_EVIDENCE_RESEARCH_ONLY"]
    count_hold=types["RETAIN_404_AND_MONITOR"]
    if (count_core!=15 or count_hold!=15 or sum(groups.values())!=30
            or sum(r["sample_impressions"] for r in queue)!=44
            or sum(r["sample_clicks"] for r in queue)!=0
            or recorded.get("model_choice_counts")!={"SOURCE_AUDIT":30}):
        raise JevDeploymentQueueHeld("COMMERCIAL_PORTFOLIO_AGGREGATES_CHANGED")
    briefs=[
        {
            "workstream":group,
            "case_count":groups[group],
            "total_gsc_sample_impressions":sum(r["sample_impressions"] for r in queue if r["workstream"]==group),
            "recommended_sequence":i+1,
            "task_state":"RESEARCH_ONLY" if group!="OFF_CORE_LEGACY_MONITOR"
                         else "RETAIN_404_MONITOR",
            "source_asset_verified_in_repo":group!="OFF_CORE_LEGACY_MONITOR",
            "publication_gate":"HISTORIC_SOURCE_AND_RIGHTS_AND_HUMAN_RELEASE_REQUIRED",
        }
        for i,group in enumerate([
            "PREDICTIVE_REVENUE_PRODUCT_CONTENT_RESEARCH",
            "ROOFING_HELPFUL_CONTENT_RESEARCH",
            "ORIGINAL_BUYER_INTENT_TAM_RESEARCH",
            "OFF_CORE_LEGACY_MONITOR",
        ])
    ]
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "mission":"OWNED_ORGANIC_SOURCE_TO_ORIGINAL_EDITORIAL_EVIDENCE",
        "source":"PINNED_GSC_PAGE_ONLY_AND_SIX_REAL_JEV_BATCH_RECEIPTS",
        "original_case_count":30,
        "jev_actual_case_predictions":30,
        "sample_total_impressions":44,
        "sample_total_clicks":0,
        "core_topic_research_case_count":count_core,
        "off_core_hold_case_count":count_hold,
        "research_portfolios":briefs,
        "private_work_queue":queue,
        "publisher_source_assets_verified":source_assets,
        "baseline_ranking_or_organic_click_lift_verified":False,
        "source_page_contents_recovered":False,
        "case_truth_or_jev_accuracy_verified":False,
        "buyer_enquiries_verified":False,
        "realised_revenue_verified":False,
        "new_model_requests":0,
        "database_writes":False,
        "automatic_redirects":False,
        "automatic_publication":False,
        "commercial_outbound_authorized":False,
        "money_moved":False,
        "execution_authority":"NONE",
    }


def safe_deployment_portfolio_summary(packet: Mapping[str,Any]) -> dict[str,Any]:
    if (packet.get("schema_version")!=SCHEMA
            or packet.get("mode")!="OBSERVE"
            or packet.get("source")!="PINNED_GSC_PAGE_ONLY_AND_SIX_REAL_JEV_BATCH_RECEIPTS"
            or packet.get("original_case_count")!=30
            or packet.get("jev_actual_case_predictions")!=30
            or packet.get("core_topic_research_case_count")!=15
            or packet.get("off_core_hold_case_count")!=15
            or packet.get("sample_total_impressions")!=44
            or packet.get("sample_total_clicks")!=0
            or packet.get("source_page_contents_recovered") is not False
            or packet.get("realised_revenue_verified") is not False
            or packet.get("new_model_requests")!=0
            or packet.get("automatic_publication") is not False
            or packet.get("automatic_redirects") is not False
            or packet.get("execution_authority")!="NONE"):
        raise JevDeploymentQueueHeld("UNVERIFIED_PORTFOLIO_PUBLIC_STATUS")
    groups=packet.get("research_portfolios")
    if (not isinstance(groups,list) or len(groups)!=4
            or sum(r.get("case_count",0) for r in groups)!=30):
        raise JevDeploymentQueueHeld("INVALID_PORTFOLIO_GROUPS")
    return {
        "schema_version":"empire.search.jev_organic_deployment_summary.v1",
        "mode":"RESEARCH_TO_RELEASE_READY",
        "original_url_observations":30,
        "jev_predictions_observed":30,
        "core_topic_research_observations":15,
        "off_core_urls_retained_404":15,
        "sample_page_impressions":44,
        "sample_page_clicks":0,
        "research_workstreams":[{
            "workstream":r["workstream"],
            "case_count":r["case_count"],
            "sample_impressions":r["total_gsc_sample_impressions"],
            "status":r["task_state"],
        } for r in groups],
        "website_changes_live":False,
        "first_party_source_content_verified":False,
        "seo_traffic_lift_verified":False,
        "qualified_leads_verified":False,
        "realised_revenue_verified":False,
        "model_calls_during_summary":0,
        "personal_data_or_paths_disclosed":False,
        "automatic_publishing_or_redirects_authorised":False,
        "execution_authority":"NONE",
    }
