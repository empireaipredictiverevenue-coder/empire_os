"""A deterministic evidence guard for ASTRA's model-generated snapshot reviews.

This is a harness *script* and tool contract, not another report. The local model
may suggest a review, but only original redacted source fields can be asserted.
"""
from __future__ import annotations
from collections.abc import Mapping
import json
import re

REVIEW_FLAGS = ("verified_replies", "verified_revenue", "activation_ready")

def _count(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("original non-negative integer count required")
    return value

def verified_snapshot_facts(kind: str, source: Mapping) -> dict:
    if source.get("mode") != "OBSERVE" or source.get("execution_authority") != "none":
        raise ValueError("unauthorised original source")
    if kind == "conversion":
        stages=source.get("counts")
        if not isinstance(stages, Mapping):
            raise ValueError("missing canonical funnel counters")
        stage=stages.get("delivered_outreach_to_reply")
        if not isinstance(stage, Mapping):
            raise ValueError("missing exact delivered-to-reply stage")
        entered=_count(stage.get("entered"))
        converted=_count(stage.get("converted"))
        if converted > entered:
            raise ValueError("invalid original conversion counts")
        return {"kind":kind,"source_facts":{"outreach_entered":entered,"observed_replies":converted},
                "reason":f"Conversion snapshot reports {converted} of {entered} delivered-outreach-to-reply conversions; provider reply verification is unproven."}
    if kind == "acquisition":
        targets=_count(source.get("icp_priority_target_count"))
        gaps=_count(source.get("demand_gap_count"))
        return {"kind":kind,"source_facts":{"priority_target_candidates":targets,"demand_gap_candidates":gaps},
                "reason":f"Buyer acquisition snapshot reports {targets} priority target candidates and {gaps} demand gaps; these are not verified customer conversions."}
    if kind == "revenue":
        truth=source.get("recognized_revenue_truth")
        if not isinstance(truth, Mapping):
            raise ValueError("recognized revenue truth missing")
        cents=_count(truth.get("recognized_revenue_cents"))
        return {"kind":kind,"source_facts":{"snapshot_recognized_revenue_cents":cents},
                "reason":f"Revenue Pulse snapshot reports recognized_revenue_cents={cents}; this runtime artifact is not authenticated exact-order proof."}
    raise ValueError("unrecognised original evidence task")

def evaluate_guarded_answer(kind: str, source: Mapping, model_reply: str) -> dict:
    """Keep a correct flag result; replace unverified prose with exact source facts.

    Never infer customer identity, authorization, settlement or fraud. This
    source-specific task has no authenticated positive-outcome evidence.
    """
    facts=verified_snapshot_facts(kind,source)
    match=re.search(r"\{[\s\S]*?\}",model_reply)
    try:
        raw=json.loads(match.group(0)) if match else {}
        if not isinstance(raw,dict):raw={}
    except (ValueError,AttributeError):
        raw={}
    flags_safe=all(raw.get(flag) is False for flag in REVIEW_FLAGS)
    result={flag:False for flag in REVIEW_FLAGS}
    result["one_brief_reason"]=facts["reason"]
    return {
        "schema_version":"empire.astra.harness2_grounded_tool.v1",
        "task":kind,"review":result,"observed_facts":facts["source_facts"],
        "raw_model_flags_safe":flags_safe,
        "reason_replaced_with_source_facts":True,
        "authenticated_buyer_outcome_claimed":False,
        "outbound_authorized":False,"training_authorized":False,
        "source_owned_snapshot_only":True,
    }
