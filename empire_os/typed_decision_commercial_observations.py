"""Read-only commercial + routing observation adapters for typed-decision evals."""
from __future__ import annotations
from typing import Any, Mapping


def _text(v:Any)->str:
    return str(v or "").strip()


def buyer_corridor_record_to_observation(raw:Mapping[str,Any])->dict[str,Any]:
    buyer_ref=_text(raw.get("buyer_ref") or raw.get("buyer_id"))
    corridor_ref=_text(raw.get("corridor_ref") or raw.get("corridor_id"))
    observed_at=_text(raw.get("observed_at"))
    source_ref=_text(raw.get("source_ref"))
    blockers=[]
    if not buyer_ref: blockers.append("buyer_ref_required")
    if not corridor_ref: blockers.append("corridor_ref_required")
    if not observed_at: blockers.append("observed_at_required")
    if not source_ref: blockers.append("source_ref_required")
    return {
        "schema_version":"typed_decision_buyer_corridor_observation.v1",
        "ready":not blockers,
        "blockers":blockers,
        "task_key":"buyer_corridor_fit",
        "case_id":f"buyer-corridor:{buyer_ref}:{corridor_ref}" if buyer_ref and corridor_ref else None,
        "inputs":{
            "buyer_ref":buyer_ref,
            "corridor_ref":corridor_ref,
        } if buyer_ref and corridor_ref else {},
        "source_ref":source_ref or None,
        "point_in_time_ref":observed_at or None,
        "buyer_activation":False,
        "territory_allocation":False,
        "commercial_mutation":False,
        "execution_authority":"none",
    }


def routing_task_to_observation(raw:Mapping[str,Any])->dict[str,Any]:
    task_ref=_text(raw.get("task_ref"))
    task_text=_text(raw.get("task_text"))
    observed_at=_text(raw.get("observed_at"))
    source_ref=_text(raw.get("source_ref"))
    blockers=[]
    if not task_ref: blockers.append("task_ref_required")
    if not task_text: blockers.append("task_text_required")
    if not observed_at: blockers.append("observed_at_required")
    if not source_ref: blockers.append("source_ref_required")
    return {
        "schema_version":"typed_decision_agent_routing_observation.v1",
        "ready":not blockers,
        "blockers":blockers,
        "task_key":"agent_routing",
        "case_id":f"routing:{task_ref}" if task_ref else None,
        "inputs":{"task_text":task_text} if task_text else {},
        "source_ref":source_ref or None,
        "point_in_time_ref":observed_at or None,
        "observed_current_route":_text(raw.get("observed_current_route")) or None,
        "provider_activation":False,
        "model_route_mutation":False,
        "execution_authority":"none",
    }
