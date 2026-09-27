"""Governed call-plan materialization for phone-fallback buyers.

Plans are internal preparation only. They do not dial, reserve provider
resources, accept terms, move funds, or recognize revenue.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from empire_os.buyer_deferred_enrichment import (
    CALL_READY_PATH,
    canonical_phone,
)

CALL_PLAN_PATH = Path(
    "/srv/empire_os/runtime/closer/call_plans_latest.json"
)


@dataclass(frozen=True)
class BuyerCallPlan:
    prospect_id: str
    business_name: str
    phone: str
    website: str
    reason: str
    enrichment_attempts: int
    channel: str = "phone"
    provider_preference: str = "vonage"
    objective: str = (
        "Identify or reach the economic buyer, confirm business relevance, "
        "and invite a genuine conversation. Do not invent facts or outcomes."
    )
    execution_allowed: bool = False
    live_call_authority_required: bool = True
    terms_authority: bool = False
    funds_authority: bool = False
    revenue_authority: bool = False

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["guardrails"] = {
            "no_autodial_without_live_phone_authority": True,
            "no_binding_terms": True,
            "no_payment_request_without_canonical_terms_path": True,
            "unknown_stays_unknown": True,
            "no_fake_contact_or_conversation_data": True,
        }
        payload["telemetry"] = {
            "conversation_os_ingest": True,
            "record_provider_event_ids": True,
            "record_answer_state": True,
            "record_human_reply_only": True,
            "provider_execution": "disabled",
        }
        return payload


def build_call_plan(row: Mapping[str, Any]) -> BuyerCallPlan | None:
    if str(row.get("status") or "") != "ready_for_review":
        return None
    phone = canonical_phone(row.get("phone"))
    prospect_id = str(row.get("prospect_id") or "").strip()
    if not prospect_id or not phone:
        return None
    return BuyerCallPlan(
        prospect_id=prospect_id,
        business_name=str(row.get("business_name") or "").strip(),
        phone=phone,
        website=str(row.get("website") or "").strip(),
        reason=str(row.get("reason") or "email_enrichment_exhausted"),
        enrichment_attempts=max(
            1,
            int(row.get("enrichment_attempts") or 1),
        ),
    )


def materialize_call_plans(
    *,
    call_ready_path: str | Path = CALL_READY_PATH,
    output_path: str | Path = CALL_PLAN_PATH,
    limit: int = 25,
) -> dict[str, Any]:
    source = Path(call_ready_path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}

    plans: list[dict[str, Any]] = []
    for row in raw.values():
        if not isinstance(row, dict):
            continue
        plan = build_call_plan(row)
        if plan is not None:
            plans.append(plan.as_dict())

    plans.sort(
        key=lambda item: (
            -int(item.get("enrichment_attempts") or 0),
            str(item.get("business_name") or "").lower(),
        )
    )
    plans = plans[: max(1, min(int(limit), 100))]
    payload = {
        "schema_version": "empire.buyer_call_plans.v1",
        "count": len(plans),
        "plans": plans,
        "execution_allowed": False,
        "live_calls_placed": 0,
        "authority_expansion_required": True,
    }

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(target)
    return payload
