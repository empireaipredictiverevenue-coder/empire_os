"""Read-only verification of SIX real Jev batches covering 30 original URLs.

No provider calls in API. Original paths, questions, source text and private
record identifiers never leave this server via the summary.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any

from .ai_first_seo_review import validated_cases
from .jev_page_case_review import LABELS

ROOT=Path("/home/ubuntu/empire_releases/search_jev_owner_receipts_20261021")
PINNED_SHA256=(
    "e579ba9408c2701ff725169658fbf54af2686eced3f4b1621f2a973b5c67e9ca",
    "9d541ee5e7247b6aefa9f7f5c22b60c7ba9014258959e814fe037c0719bddef5",
    "f8e49221a0168b381b9db6da3eceecbc68b7ee476a17b426667fb802ea05e62a",
    "844e9fa0d18161d0c67f919321f4d953a85231b8e04d02a5b60dc40f0500d332",
    "fc4d4242b72d40cd51e74294861ffdda3300875c980d6cde021e229bc5a824de",
    "f15cf107e91cac521fc31215e9cf5c97a4b702d518dedd2826743a05343345ea",
)


class JevCaseReceiptHeld(ValueError):
    pass


def reviewed_case_summary(
    root: Path = ROOT,
    hashes: tuple[str,...] = PINNED_SHA256,
    *,
    source_case_ids: set[str] | None = None,
) -> dict[str, Any]:
    if len(hashes)!=6:
        raise JevCaseReceiptHeld("JEV_RECEIPT_BATCH_SET_INCOMPLETE")
    allowed=source_case_ids if source_case_ids is not None else {
        c["case_id"] for c in validated_cases()
    }
    if len(allowed)!=30:
        raise JevCaseReceiptHeld("ORIGINAL_EVIDENCE_COHORT_INVALID")
    cases=[]
    spent=0.0
    for i,digest in enumerate(hashes):
        path=root/f"jev_page_batch_{i}_20261022.json"
        if (path.is_symlink() or not path.is_file()
                or path.stat().st_mode & 0o077
                or not 600 <= path.stat().st_size <= 32000):
            raise JevCaseReceiptHeld("JEV_BATCH_FILE_MISSING_OR_UNSAFE")
        raw=path.read_bytes()
        if sha256(raw).hexdigest()!=digest:
            raise JevCaseReceiptHeld("JEV_BATCH_PINNED_HASH_MISMATCH")
        try:
            record=json.loads(raw)
        except (ValueError,UnicodeError) as exc:
            raise JevCaseReceiptHeld("JEV_BATCH_NOT_JSON") from exc
        if (record.get("schema_version")!="empire.search.jev_original_page_batch_result.v1"
                or record.get("provider")!="openrouter_typesafe_jev"
                or not isinstance(record.get("model"),str)
                or not record["model"].startswith("typesafe/jev-1.13")
                or record.get("batch_index")!=i
                or record.get("actual_model_calls")!=1
                or record.get("cases_reviewed")!=5
                or record.get("ground_truth_labels_verified")!=0
                or record.get("inference_automatically_scheduled") is not False
                or record.get("external_customer_data_sent") is not False
                or record.get("original_page_content_verified") is not False
                or record.get("authorised_publication") is not False
                or record.get("execution_authority")!="NONE"):
            raise JevCaseReceiptHeld("JEV_BATCH_EXECUTION_CONTRACT_DRIFT")
        cost=record.get("cost_usd_reported")
        if type(cost) not in (float,int) or not math.isfinite(cost) or not 0<=cost<=0.001:
            raise JevCaseReceiptHeld("JEV_BATCH_COST_OUTSIDE_CAP")
        spent+=float(cost)
        rows=record.get("case_reviews")
        if not isinstance(rows,list) or len(rows)!=5:
            raise JevCaseReceiptHeld("JEV_BATCH_CASE_COUNT_MISMATCH")
        for case in rows:
            if (not isinstance(case,dict)
                    or case.get("case_id") not in allowed
                    or case.get("choice") not in LABELS
                    or not isinstance(case.get("source_ref"),str)
                    or not case["source_ref"].startswith("gsc-page-origin-sha256:")
                    or type(case.get("confidence")) not in (float,int)
                    or not math.isfinite(case["confidence"])
                    or not 0<=case["confidence"]<=1
                    or case.get("decision_status")!="AI_DEEP_RESEARCH_CANDIDATE_ONLY"
                    or case.get("human_ground_truth") is not False
                    or case.get("source_content_verified") is not False
                    or case.get("publisher_rights_verified") is not False
                    or case.get("automatic_redirect_authority") is not False
                    or case.get("publish_authority") is not False):
                raise JevCaseReceiptHeld("JEV_CASE_TRUTH_OR_LABEL_INVALID")
            cases.append(case)
    if (len({c["case_id"] for c in cases})!=30
            or {c["case_id"] for c in cases}!=allowed
            or spent>0.006):
        raise JevCaseReceiptHeld("JEV_COHORT_INCOMPLETE_DUPLICATED_OR_OVER_BUDGET")
    labels=dict(sorted(Counter(c["choice"] for c in cases).items()))
    return {
        "schema_version":"empire.search.jev_original_page_case_summary.v1",
        "mode":"REAL_PROVIDER_EVALUATION_SHADOW",
        "provider_key":"openrouter_typesafe_jev",
        "verified_provider_batches":6,
        "original_page_cases_assessed":30,
        "validated_model_responses":30,
        "model_choice_counts":labels,
        "model_confidence_at_least_0_80":sum(c["confidence"]>=0.8 for c in cases),
        "model_confidence_below_0_80":sum(c["confidence"]<0.8 for c in cases),
        "reported_cost_usd":round(spent,9),
        "model_prediction_accuracy_verified":False,
        "original_page_copy_verified":False,
        "model_outputs_are_human_labels":False,
        "model_research_recommendations_are_authorised_fixes":False,
        "unattended_provider_calls_enabled":False,
        "new_inference_requests_during_status":0,
        "external_buyer_or_personal_data_sent":False,
        "case_url_paths_exposed":False,
        "manual_publication_or_redirect_authority":False,
        "execution_authority":"NONE",
    }
