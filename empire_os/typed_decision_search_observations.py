"""Read-only Search/SEO observation adapters for typed-decision evals."""
from __future__ import annotations
from typing import Any, Mapping


def _text(v:Any)->str:
    return str(v or "").strip()


def keyword_record_to_observation(raw:Mapping[str,Any])->dict[str,Any]:
    query=_text(raw.get("query") or raw.get("keyword"))
    observed_at=_text(raw.get("observed_at"))
    source_ref=_text(raw.get("source_ref"))
    query_id=_text(raw.get("query_id") or raw.get("id"))

    blockers=[]
    if not query: blockers.append("query_required")
    if not observed_at: blockers.append("observed_at_required")
    if not source_ref: blockers.append("source_ref_required")

    return {
        "schema_version":"typed_decision_keyword_observation.v1",
        "ready":not blockers,
        "blockers":blockers,
        "task_key":"keyword_intent",
        "case_id":f"keyword:{query_id or source_ref}" if query else None,
        "inputs":{"query":query} if query else {},
        "source_ref":source_ref or None,
        "point_in_time_ref":observed_at or None,
        "observed_existing_intent":_text(raw.get("intent") or raw.get("search_intent")) or None,
        "publishing_enabled":False,
        "indexation_enabled":False,
        "execution_authority":"none",
    }


def source_quality_record_to_observation(raw:Mapping[str,Any])->dict[str,Any]:
    source_ref=_text(raw.get("source_ref") or raw.get("source_key"))
    summary=_text(raw.get("evidence_summary") or raw.get("summary"))
    observed_at=_text(raw.get("observed_at"))
    blockers=[]
    if not source_ref: blockers.append("source_ref_required")
    if not summary: blockers.append("evidence_summary_required")
    if not observed_at: blockers.append("observed_at_required")

    return {
        "schema_version":"typed_decision_source_quality_observation.v1",
        "ready":not blockers,
        "blockers":blockers,
        "task_key":"source_quality",
        "case_id":f"source-quality:{source_ref}" if source_ref else None,
        "inputs":{
            "source_ref":source_ref,
            "evidence_summary":summary,
        } if source_ref and summary else {},
        "source_ref":source_ref or None,
        "point_in_time_ref":observed_at or None,
        "source_state_mutation":False,
        "execution_authority":"none",
    }
