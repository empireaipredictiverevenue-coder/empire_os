"""Cost-capped Jev choice-model review for *owned* GSC legacy-404 cases.

Exactly five independently addressed cases per manually triggered request.
The state contains public first-party paths and sample metrics only. No private
GSC queries, customer names, credentials, page copy or data rights assertions.
Model classifications are NON-EXECUTING proposals, never verified truth.
"""
from __future__ import annotations

import json
import math
from typing import Any, Callable, Mapping

import requests

from .ai_first_seo_review import LABELS, CRITERIA, RESEARCH_NEXT, validated_cases

ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
MODEL = "typesafe/jev-1.13"
MAX_COST_PER_BATCH_USD = 0.001
BATCH_COUNT = 6
CASES_PER_BATCH = 5
MAX_BODY_BYTES = 7200
MAX_INPUT_TOKENS = 7500
SCHEMA = "empire.search.jev_original_page_batch.v1"


class JevPageBatchHeld(ValueError):
    pass


def batch_plan(index: int) -> dict[str, Any]:
    if type(index) is not int or not 0 <= index < BATCH_COUNT:
        raise JevPageBatchHeld("BATCH_INDEX_OUTSIDE_FIXED_COHORT")
    cases=validated_cases()
    ordered=sorted(
        cases,
        key=lambda c: (c["deterministic_review_category"] == "OFF_CORE_RETAIN_404_PENDING_EVIDENCE",
                       -c["observed_page_dimension_impressions"], c["case_id"]),
    )
    selection=ordered[index*CASES_PER_BATCH:(index+1)*CASES_PER_BATCH]
    if len(selection) != CASES_PER_BATCH:
        raise JevPageBatchHeld("GSC_CASE_COUNT_CHANGED")
    states=[]
    questions={}
    keys=[]
    for j,c in enumerate(selection):
        k=f"case_{j+1}"
        state={
            "case_ref": k,
            "first_party_path": c["path"],  # Public owned URI path only.
            "http_status_at_observation": c["observed_origin_http_status"],
            "sample_impressions": c["observed_page_dimension_impressions"],
            "sample_clicks": c["observed_page_dimension_clicks"],
            "source": "OWNED_GSC_PAGE_ONLY_HISTORICAL_SAMPLE",
            "original_content_retrieved": False,
            "original_rights_verified": False,
            "equivalent_live_page_verified": False,
            "existing_rule_category_not_truth": c["deterministic_review_category"],
        }
        states.append(state)
        keys.append({"key":k,"case_id":c["case_id"],"source_ref":c["source_ref"]})
        questions[k]={
            "type":"choice",
            "instructions": (
                f"For state.cases record {k} ONLY choose the safest NEXT "
                "READ-ONLY SEO RESEARCH action. 404 status and a URL slug "
                "alone do not establish original content, canonical match, "
                "lost traffic, buyer intent, or approval. Prefer source audit "
                "or abstention if uncertain. No publishing or redirect."
            ),
            "criteria":CRITERIA,
        }
    req={"model":MODEL,"state":{"cases":states,"review_scope":"FIVE_PUBLIC_OWNED_URI_PATHS_ONLY"},
         "questions":questions}
    if len(json.dumps(req,separators=(",",":")).encode()) > MAX_BODY_BYTES:
        raise JevPageBatchHeld("JEV_BATCH_EXCEEDS_SIZE_LIMIT")
    return {
        "schema_version":SCHEMA,
        "batch_index":index,
        "model":MODEL,
        "request":req,
        "case_keys":keys,
        "max_requests":1,
        "max_cost_usd":MAX_COST_PER_BATCH_USD,
        "external_user_or_buyer_data_sent":False,
        "origin_page_content_verified":False,
        "human_approval_granted":False,
        "execution_authority":"NONE",
    }


def _prob(x: Any) -> float:
    if type(x) not in (int,float) or not math.isfinite(x) or x < 0 or x > 1:
        raise JevPageBatchHeld("JEV_INVALID_PROBABILITY")
    return float(x)


def run_batch(
    plan: Mapping[str,Any],
    *,
    api_key: str,
    post: Callable[...,Any] = requests.post,
) -> dict[str,Any]:
    if (plan.get("schema_version")!=SCHEMA
            or plan.get("execution_authority")!="NONE"
            or plan.get("external_user_or_buyer_data_sent") is not False
            or plan.get("request",{}).get("model")!=MODEL
            or plan.get("batch_index") not in range(BATCH_COUNT)):
        raise JevPageBatchHeld("BATCH_AUTHORITY_INVALID")
    # Recompute exact expected payload from pinned private GSC receipt.
    expected=batch_plan(plan["batch_index"])
    if (plan["request"] != expected["request"]
            or plan["case_keys"] != expected["case_keys"]):
        raise JevPageBatchHeld("BATCH_PAYLOAD_OUTSIDE_PINNED_SOURCE")
    if not isinstance(api_key,str) or len(api_key)<20 or any(c.isspace() for c in api_key):
        raise JevPageBatchHeld("JEV_GATEWAY_CREDENTIAL_INVALID")
    try:
        resp=post(
            ENDPOINT,
            headers={"Authorization":"Bearer "+api_key,"Content-Type":"application/json"},
            json=plan["request"],timeout=16,allow_redirects=False,
        )
        if resp.status_code != 200:
            raise JevPageBatchHeld(f"JEV_GATEWAY_STATUS_{resp.status_code}")
        data=resp.json()
    except JevPageBatchHeld:
        raise
    except (requests.RequestException,ValueError,TypeError) as exc:
        raise JevPageBatchHeld("JEV_GATEWAY_UNAVAILABLE") from exc
    if (not isinstance(data,Mapping)
            or not isinstance(data.get("model"),str)
            or not data["model"].startswith("typesafe/jev-1.13")
            or not isinstance(data.get("usage"),Mapping)
            or not isinstance(data.get("answers"),Mapping)
            or set(data["answers"]) != set(plan["request"]["questions"])):
        raise JevPageBatchHeld("JEV_BATCH_PROVIDER_SCHEMA")
    usage=data["usage"]
    tokens=usage.get("input_tokens")
    cost=usage.get("cost")
    if (type(tokens) is not int or tokens<0 or tokens>MAX_INPUT_TOKENS
            or type(cost) not in (int,float) or not math.isfinite(cost)
            or cost<0 or cost>MAX_COST_PER_BATCH_USD):
        raise JevPageBatchHeld("JEV_BATCH_USAGE_EXCEEDS_LIMIT")
    reviewed=[]
    for entry in plan["case_keys"]:
        result=data["answers"][entry["key"]]
        if (not isinstance(result,Mapping) or result.get("type")!="choice"
                or result.get("choice") not in LABELS
                or not isinstance(result.get("probabilities"),Mapping)
                or set(result["probabilities"]) != set(LABELS)):
            raise JevPageBatchHeld("JEV_BATCH_INVALID_ANSWER")
        ps={k:_prob(result["probabilities"][k]) for k in LABELS}
        if abs(sum(ps.values())-1)>0.04:
            raise JevPageBatchHeld("JEV_BATCH_INVALID_PROBABILITY_SUM")
        confidence=_prob(result.get("confidence"))
        reviewed.append({
            "case_id":entry["case_id"],
            "source_ref":entry["source_ref"],
            "choice":result["choice"],
            "confidence":round(confidence,4),
            "next_ai_research_action":RESEARCH_NEXT[result["choice"]],
            "decision_status":"AI_DEEP_RESEARCH_CANDIDATE_ONLY",
            "human_ground_truth":False,
            "source_content_verified":False,
            "publisher_rights_verified":False,
            "automatic_redirect_authority":False,
            "publish_authority":False,
        })
    return {
        "schema_version":"empire.search.jev_original_page_batch_result.v1",
        "provider":"openrouter_typesafe_jev",
        "model":data["model"],
        "batch_index":plan["batch_index"],
        "actual_model_calls":1,
        "cases_reviewed":len(reviewed),
        "case_reviews":reviewed,
        "input_tokens":tokens,
        "cost_usd_reported":float(cost),
        "ground_truth_labels_verified":0,
        "inference_automatically_scheduled":False,
        "external_customer_data_sent":False,
        "original_page_content_verified":False,
        "authorised_publication":False,
        "execution_authority":"NONE",
    }
