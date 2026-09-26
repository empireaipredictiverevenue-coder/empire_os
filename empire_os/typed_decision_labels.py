"""Governed real-label intake for typed-decision evaluation datasets.

No raw production mutation. Records labels/provenance/review state and produces
promotion-eligible evaluation cases only when review requirements are met.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping, Iterable

from empire_os.typed_decision_dataset import TASK_SCHEMAS


LABEL_SOURCES={"human_review","verified_outcome","independent_verifier","deterministic_rule"}
REVIEW_STATES={"pending","accepted","rejected","disputed"}


def _text(v:Any)->str:
    return str(v or "").strip()


@dataclass(frozen=True)
class LabelRecord:
    label_id:str
    case_id:str
    task_key:str
    proposed_label:str
    label_source:str
    source_ref:str
    reviewer_ref:str|None
    review_state:str
    point_in_time_ref:str
    tenant_key:str|None
    notes_ref:str|None=None

    def validate(self)->None:
        if not self.label_id: raise ValueError("label_id required")
        if not self.case_id: raise ValueError("case_id required")
        if self.task_key not in TASK_SCHEMAS: raise ValueError("unsupported task_key")
        if self.proposed_label not in TASK_SCHEMAS[self.task_key]["labels"]:
            raise ValueError("proposed_label not allowed for task")
        if self.label_source not in LABEL_SOURCES: raise ValueError("unsupported label_source")
        if not self.source_ref: raise ValueError("source_ref required")
        if self.review_state not in REVIEW_STATES: raise ValueError("unsupported review_state")
        if not self.point_in_time_ref: raise ValueError("point_in_time_ref required")
        if self.review_state=="accepted" and not self.reviewer_ref:
            raise ValueError("accepted label requires reviewer_ref")

    def as_dict(self)->dict[str,Any]:
        self.validate()
        return asdict(self)


def label_from_mapping(raw:Mapping[str,Any])->LabelRecord:
    return LabelRecord(
        label_id=_text(raw.get("label_id")),
        case_id=_text(raw.get("case_id")),
        task_key=_text(raw.get("task_key")),
        proposed_label=_text(raw.get("proposed_label")),
        label_source=_text(raw.get("label_source")),
        source_ref=_text(raw.get("source_ref")),
        reviewer_ref=_text(raw.get("reviewer_ref")) or None,
        review_state=_text(raw.get("review_state")).lower(),
        point_in_time_ref=_text(raw.get("point_in_time_ref")),
        tenant_key=_text(raw.get("tenant_key")) or None,
        notes_ref=_text(raw.get("notes_ref")) or None,
    )


def review_label_record(raw:Mapping[str,Any])->dict[str,Any]:
    try:
        r=label_from_mapping(raw)
        r.validate()
        blockers=[]
    except ValueError as exc:
        return {
            "schema_version":"typed_decision_label_review.v1",
            "accepted_for_dataset":False,
            "blockers":[str(exc)],
            "execution_authority":"none",
        }

    if r.review_state!="accepted":
        blockers.append("label_not_accepted")
    if r.label_source=="deterministic_rule":
        blockers.append("deterministic_rule_not_real_human_or_outcome_label")

    return {
        "schema_version":"typed_decision_label_review.v1",
        "record":r.as_dict(),
        "accepted_for_dataset":not blockers,
        "blockers":blockers,
        "commercial_evidence":False,
        "execution_authority":"none",
    }


def resolve_label_consensus(rows:Iterable[Mapping[str,Any]])->dict[str,Any]:
    records=[label_from_mapping(r) for r in rows]
    for r in records: r.validate()
    if not records:
        return {"available":False,"reason":"no_labels","execution_authority":"none"}

    case_ids={r.case_id for r in records}
    tasks={r.task_key for r in records}
    if len(case_ids)!=1: raise ValueError("consensus batch must contain one case_id")
    if len(tasks)!=1: raise ValueError("consensus batch must contain one task_key")

    accepted=[r for r in records if r.review_state=="accepted"]
    if not accepted:
        return {
            "schema_version":"typed_decision_label_consensus.v1",
            "available":False,
            "reason":"no_accepted_labels",
            "case_id":records[0].case_id,
            "execution_authority":"none",
        }

    counts={}
    for r in accepted:
        counts[r.proposed_label]=counts.get(r.proposed_label,0)+1
    ordered=sorted(counts.items(),key=lambda kv:(kv[1],kv[0]),reverse=True)
    top_label,top_count=ordered[0]
    tied=len(ordered)>1 and ordered[1][1]==top_count

    return {
        "schema_version":"typed_decision_label_consensus.v1",
        "available":not tied,
        "reason":"label_disagreement" if tied else None,
        "case_id":records[0].case_id,
        "task_key":records[0].task_key,
        "consensus_label":None if tied else top_label,
        "accepted_label_count":len(accepted),
        "label_counts":counts,
        "promotion_eligible":(
            not tied
            and any(r.label_source in {"human_review","verified_outcome","independent_verifier"} for r in accepted)
        ),
        "commercial_evidence":False,
        "execution_authority":"none",
    }


def build_real_eval_case(
    *,
    observation:Mapping[str,Any],
    labels:Iterable[Mapping[str,Any]],
)->dict[str,Any]:
    consensus=resolve_label_consensus(labels)
    if consensus.get("available") is not True or consensus.get("promotion_eligible") is not True:
        return {
            "schema_version":"typed_decision_real_eval_case.v1",
            "ready":False,
            "blockers":[consensus.get("reason") or "label_not_promotion_eligible"],
            "execution_authority":"none",
        }

    task=consensus["task_key"]
    required=TASK_SCHEMAS[task]["input_fields"]
    inputs=dict(observation.get("inputs") or {})
    missing=[f for f in required if inputs.get(f) in (None,"")]
    blockers=[]
    if missing: blockers.append("missing_input_fields:"+",".join(missing))
    if not _text(observation.get("source_ref")): blockers.append("observation_source_ref_required")
    if not _text(observation.get("point_in_time_ref")): blockers.append("point_in_time_ref_required")

    if blockers:
        return {
            "schema_version":"typed_decision_real_eval_case.v1",
            "ready":False,
            "blockers":blockers,
            "execution_authority":"none",
        }

    return {
        "schema_version":"typed_decision_real_eval_case.v1",
        "ready":True,
        "case":{
            "case_id":consensus["case_id"],
            "task_key":task,
            "inputs":inputs,
            "ground_truth":consensus["consensus_label"],
            "label_source":"reviewed_real_observation",
            "source_ref":_text(observation.get("source_ref")),
            "synthetic_test_fixture":False,
        },
        "point_in_time_ref":_text(observation.get("point_in_time_ref")),
        "commercial_evidence":False,
        "execution_authority":"none",
    }
