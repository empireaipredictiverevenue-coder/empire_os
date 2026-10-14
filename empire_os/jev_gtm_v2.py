"""JEV GTM V2: governed, read-only commercial decision composition.

Reuses the canonical ICP, reply, suppression and Predictive Revenue contracts.
The packet is a recommendation, never contact permission or a revenue fact.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from empire_os.buyer_reply_operations_agent import analyze_buyer_reply
from empire_os.icp_buyer_trigger_intelligence import assess_icp_candidate
from empire_os.jev_gtm_buying_window import assess_buying_window
from empire_os.typed_decision_batch import DecisionBatchRequestV2, DecisionBatchResultV2

SCHEMA_VERSION = "empire.jev.gtm_decision.v2"
POLICY_VERSION = "jev_gtm_policy_20261014"
SIGNAL_TYPES = frozenset({
    "hiring", "funding", "expansion", "job_change", "procurement",
    "direct_buyer_intent", "customer_inquiry", "partner_referral",
    "lead_demand", "territory_change",
})
ACTION_TYPES = frozenset({
    "HOLD", "REPLY_REVIEW", "FOLLOWUP_REVIEW", "IDENTITY_REVIEW",
    "EVIDENCE_REVIEW", "INTRODUCTION_REVIEW", "OUTREACH_REVIEW",
    "RESEARCH_REQUIRED",
})


def _text(value: Any) -> str:
    return str(value).strip() if isinstance(value, (str, int)) else ""


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _refs(raw: Any) -> tuple[str, ...]:
    if not isinstance(raw, (tuple, list)):
        return ()
    return tuple(dict.fromkeys(v.strip() for v in raw if isinstance(v, str) and v.strip()))


def review_gtm_signals(
    signals: Sequence[Mapping[str, Any]],
    *,
    as_of: datetime,
    max_age_days: int = 90,
    entity_id: str | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Use only scoped, observed, evidenced, dated signals; flag contradictions."""
    if as_of.tzinfo is None or max_age_days < 1:
        raise ValueError("timezone-aware as_of and positive freshness window required")
    seen: set[str] = set()
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    contradiction = False
    for index, item in enumerate(signals):
        if not isinstance(item, Mapping):
            rejected.append({"row": index, "reason": "invalid_record"})
            continue
        sid = _text(item.get("signal_id"))
        kind = _text(item.get("signal_type"))
        stamp = _time(item.get("observed_at"))
        evidence = _refs(item.get("evidence_refs"))
        source = _text(item.get("source_id"))
        if (not sid or not source or kind not in SIGNAL_TYPES or not evidence
                or stamp is None or item.get("truth_class") != "OBSERVED"):
            rejected.append({"row": index, "reason": "missing_or_invalid_evidence"})
            continue
        if ((entity_id is not None and item.get("entity_id") != entity_id)
                or (tenant_id is not None and item.get("tenant_id") != tenant_id)):
            rejected.append({"row": index, "reason": "signal_scope_mismatch"})
            continue
        if sid in seen:
            rejected.append({"row": index, "reason": "duplicate_signal"})
            continue
        seen.add(sid)
        age = (as_of.astimezone(timezone.utc) - stamp).total_seconds() / 86400
        if age < 0:
            rejected.append({"row": index, "reason": "future_signal"})
            continue
        if age > max_age_days:
            rejected.append({"row": index, "reason": "stale_signal"})
            continue
        if item.get("contradicted") is True:
            contradiction = True
        accepted.append({
            "signal_id": sid,
            "signal_type": kind,
            "source_id": source,
            "observed_at": stamp.isoformat(),
            "age_days": round(age, 2),
            "evidence_refs": list(evidence),
            "contradicted": item.get("contradicted") is True,
            "source_revision": _text(item.get("source_revision")) or None,
        })
    accepted.sort(key=lambda s: (s["observed_at"], s["signal_id"]), reverse=True)
    return {
        "fresh": accepted,
        "excluded": rejected,
        "has_contradiction": contradiction,
        "distinct_sources": len({s["source_id"] for s in accepted}),
        "execution_authority": "none",
    }


def _economic_review(quant_packet: Mapping[str, Any] | None, tenant_id: str, opportunity_key: str) -> dict[str, Any]:
    """Only carry the result of the canonical economic owner; never re-score it."""
    if not quant_packet:
        return {"status": "UNAVAILABLE", "expected_gross_profit_cents": None, "reason": "verified_economics_missing"}
    if quant_packet.get("tenant_id") != tenant_id or quant_packet.get("opportunity_key") != opportunity_key:
        return {"status": "BLOCKED", "expected_gross_profit_cents": None, "reason": "quant_scope_mismatch"}
    if quant_packet.get("execution_authority") != "none" or quant_packet.get("actual_revenue") is not False:
        return {"status": "BLOCKED", "expected_gross_profit_cents": None, "reason": "quant_authority_mismatch"}
    if quant_packet.get("value_available") is not True:
        return {"status": "UNAVAILABLE", "expected_gross_profit_cents": None, "reason": "unverified_economics"}
    value = quant_packet.get("expected_gross_profit_cents")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not -1e15 < value < 1e15:
        return {"status": "BLOCKED", "expected_gross_profit_cents": None, "reason": "invalid_economics"}
    return {"status": "MODELED", "expected_gross_profit_cents": float(value), "reason": "upstream_canonical_quant"}


def build_jev_gtm_decision(
    *,
    account: Mapping[str, Any],
    signals: Sequence[Mapping[str, Any]],
    as_of: datetime,
    relationship: Mapping[str, Any] | None = None,
    outreach: Mapping[str, Any] | None = None,
    reply: Mapping[str, Any] | None = None,
    quant_packet: Mapping[str, Any] | None = None,
    shadow_batch: tuple[DecisionBatchRequestV2, DecisionBatchResultV2] | None = None,
    max_signal_age_days: int = 90,
) -> dict[str, Any]:
    """Make one evidence-backed, non-executing GTM recommendation.

    Inputs are read-only snapshots from existing canonical sources; this function
    intentionally does not connect to a DB, send mail, use a model or create leads.
    """
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    as_of = as_of.astimezone(timezone.utc)
    entity_id = _text(account.get("entity_id"))
    tenant_id = _text(account.get("tenant_id"))
    opportunity_key = _text(account.get("opportunity_key"))
    if not entity_id or not tenant_id or not opportunity_key:
        raise ValueError("canonical entity, tenant and opportunity identity required")

    snap = review_gtm_signals(
        signals, as_of=as_of, max_age_days=max_signal_age_days,
        entity_id=entity_id, tenant_id=tenant_id,
    )
    fit = assess_icp_candidate(account)
    access = dict(outreach or {})
    contact_suppressed = (
        any(access.get(flag) is True for flag in ("suppressed", "do_not_contact", "opted_out"))
        or access.get("suppression_state") == "SUPPRESSED"
    )
    # A suppression-hit-only reader can report UNKNOWN, never CLEAR.
    # Merely seeing a boolean 'checked' does not provide clearance.
    suppression_checked = (
        access.get("suppression_checked") is True
        and access.get("suppression_state") in {"SUPPRESSED", "CLEAR"}
        and bool(_text(access.get("suppression_readback_ref")))
        and access.get("canonical_readback_verified") is True
    )
    identity_verified = account.get("entity_verified") is True and account.get("tenant_binding_verified") is True

    rel = dict(relationship or {})
    rel_refs = _refs(rel.get("evidence_refs"))
    last_contact = _time(rel.get("last_interaction_at"))
    is_warm = (
        rel.get("verified") is True and bool(rel_refs)
        and rel.get("entity_id") == entity_id and rel.get("tenant_id") == tenant_id
        and last_contact is not None
        and 0 <= (as_of - last_contact).total_seconds() <= 365 * 86400
        and rel.get("person_identity_verified") is True
    )

    reply_packet: dict[str, Any] | None = None
    if reply:
        if (not _text(reply.get("source_ref")) or not _time(reply.get("received_at"))
                or reply.get("entity_id") != entity_id
                or reply.get("tenant_id") != tenant_id
                or reply.get("thread_linkage_verified") is not True):
            reply_packet = {"classification": "unverified", "next_action": "manual_review"}
        elif _time(reply["received_at"]) > as_of:
            reply_packet = {"classification": "unverified", "next_action": "manual_review"}
        elif (as_of - _time(reply["received_at"])).total_seconds() > 180 * 86400:
            reply_packet = {"classification": "stale", "next_action": "manual_review"}
        else:
            ops = analyze_buyer_reply(reply.get("body_text"), reply.get("subject", ""))
            reply_packet = {
                "classification": ops.classification,
                "next_action": ops.next_action,
                "review_required": ops.review_required,
                "source_ref": reply["source_ref"],
            }
            if ops.classification == "unsubscribe":
                contact_suppressed = True

    economic = _economic_review(quant_packet, tenant_id, opportunity_key)
    blockers: list[str] = []
    if not identity_verified:
        blockers.append("canonical_identity_or_tenant_binding_unverified")
    if not suppression_checked:
        blockers.append("suppression_readback_missing")
    if contact_suppressed:
        blockers.append("contact_suppressed")
    if not snap["fresh"]:
        blockers.append("fresh_evidenced_signal_missing")
    if snap["has_contradiction"]:
        blockers.append("contradictory_signal_requires_review")
    if economic["status"] == "BLOCKED":
        blockers.append(economic["reason"])

    reply_class = (reply_packet or {}).get("classification")
    if contact_suppressed or reply_class == "negative" or (economic["status"] == "MODELED" and economic["expected_gross_profit_cents"] <= 0):
        action, reason = "HOLD", "suppressed_negative_or_uneconomic"
    elif economic["status"] == "BLOCKED":
        action, reason = "HOLD", "economic_scope_or_provenance_invalid"
    elif reply_class in {"positive", "question", "objection"} and identity_verified:
        action, reason = "REPLY_REVIEW", "existing_buyer_conversation"
    elif reply_class == "later" and identity_verified:
        action, reason = "FOLLOWUP_REVIEW", "buyer_requested_later"
    elif not identity_verified:
        action, reason = "IDENTITY_REVIEW", "canonical_identity_unverified"
    elif snap["has_contradiction"] or reply_class in {"unverified", "stale"}:
        action, reason = "EVIDENCE_REVIEW", "source_evidence_ambiguous"
    elif not suppression_checked:
        action, reason = "EVIDENCE_REVIEW", "canonical_contact_evidence_unverified"
    elif snap["fresh"] and fit["model_fit_score"] >= 55 and is_warm:
        action, reason = "INTRODUCTION_REVIEW", "verified_warm_relationship_and_signal"
    elif snap["fresh"] and fit["model_fit_score"] >= 55:
        action, reason = "OUTREACH_REVIEW", "observed_signal_and_heuristic_icp_fit"
    else:
        action, reason = "RESEARCH_REQUIRED", "insufficient_commercial_fit_or_signal"

    if action not in ACTION_TYPES:
        raise AssertionError("unknown GTM action")
    evidence = list(dict.fromkeys(
        [ref for sig in snap["fresh"] for ref in sig["evidence_refs"]]
        + list(rel_refs)
        + ([_text(reply_packet.get("source_ref"))] if reply_packet and reply_packet.get("source_ref") else [])
    ))
    provider_review: dict[str, Any] | None = None
    if shadow_batch is not None:
        req, result = shadow_batch
        result.validate(req)
        provider_review = {
            "schema_ref": req.schema_ref,
            "provider": result.provider_key,
            "model": result.model_key,
            "labels": {
                k: (v.get("choice") if "choice" in v else None)
                for k, v in result.answers.items()
            },
            "shadow_only": True,
            "changes_route": False,
        }

    missing_next = (
        "confirm_suppression_state" if not suppression_checked
        else "verify_canonical_identity" if not identity_verified
        else "resolve_contradictory_signal" if snap["has_contradiction"]
        else "collect_dated_buyer_signal" if not snap["fresh"]
        else "verify_economic_inputs" if economic["status"] != "MODELED"
        else "review_commercial_opportunity"
    )
    fingerprint_input = {
        "schema": SCHEMA_VERSION, "policy": POLICY_VERSION,
        "entity": entity_id, "tenant": tenant_id, "opportunity": opportunity_key,
        "signals": snap["fresh"], "excluded": snap["excluded"],
        "fit": fit["model_fit_score"], "relationship_verified": is_warm,
        "reply": reply_packet,
        "reply_body_sha256": (
            sha256(str(reply.get("body_text") or "").encode()).hexdigest()
            if reply else None
        ),
        "reply_received_at": reply.get("received_at") if reply else None,
        "relationship_ref": list(rel_refs),
        "relationship_last_contact": rel.get("last_interaction_at"),
        "account_source_revision": account.get("source_revision"),
        "account_snapshot_digest": sha256(
            json.dumps(dict(account), sort_keys=True, default=str).encode()
        ).hexdigest(),
        "account_evidence_refs": _refs(account.get("evidence_refs")),
        "shadow_observations": provider_review,
        "suppression_checked": suppression_checked,
        "suppression_readback_ref": access.get("suppression_readback_ref"),
        "suppression_state": access.get("suppression_state"),
        "suppression_canonical_verified": access.get("canonical_readback_verified") is True,
        "suppressed": contact_suppressed, "identity_verified": identity_verified,
        "economic": economic, "action": action,
    }
    digest = sha256(json.dumps(fingerprint_input, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "decision_fingerprint": digest,
        "as_of": as_of.isoformat(),
        "entity_id": entity_id,
        "tenant_id": tenant_id,
        "opportunity_key": opportunity_key,
        "action": action,
        "reason": reason,
        "blockers": sorted(set(blockers)),
        "evidence_refs": evidence,
        "signal_review": snap,
        "buying_window": assess_buying_window(snap),
        "icp": {
            "profile_key": fit["best_profile_key"],
            "fit_score": fit["model_fit_score"],
            "score_type": "DETERMINISTIC_HEURISTIC_NOT_PROBABILITY",
            "observed_buying_triggers": fit["observed_buying_triggers"],
        },
        "relationship": {"warm_verified": is_warm, "evidence_refs": list(rel_refs)},
        "reply": reply_packet,
        "economics": economic,
        "next_research_action": missing_next,
        "value_of_information": {"status": "UNAVAILABLE", "reason": "not_calibrated"},
        "shadow_decision": provider_review,
        "prediction_of_purchase_probability": None,
        "contact_suppressed": contact_suppressed,
        "suppression_checked": suppression_checked,
        "outbound_approved": False,
        "contact_permission_granted": False,
        "database_write": False,
        "payment_action": False,
        "fulfilment_action": False,
        "actual_revenue": False,
        "recommendation_only": True,
        "execution_authority": "none",
        "mode": "OBSERVE",
    }


# Bounded, tenant-scoped read-only review queue. No scheduler or persistence.
REVIEW_PRIORITY = {
    "REPLY_REVIEW": 0,
    "INTRODUCTION_REVIEW": 1,
    "FOLLOWUP_REVIEW": 2,
    "OUTREACH_REVIEW": 3,
    "EVIDENCE_REVIEW": 4,
    "IDENTITY_REVIEW": 5,
    "RESEARCH_REQUIRED": 6,
    "HOLD": 7,
}


def build_jev_gtm_review_queue(
    *,
    tenant_id: str,
    cases: Sequence[Mapping[str, Any]],
    as_of: datetime,
    max_candidates: int = 250,
) -> dict[str, Any]:
    """Rank governed internal reviews without asserting outreach permission.

    The caller must obtain cases from an authorised, tenant-scoped canonical
    reader. This function verifies exact tenant identity on every case, and
    refuses mixed-tenant batches.
    """
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("timezone-aware as_of required")
    if not tenant_id.strip():
        raise ValueError("trusted tenant identity required")
    if not 1 <= max_candidates <= 1000 or len(cases) > max_candidates:
        raise ValueError("bounded candidate limit exceeded")
    prepared: list[dict[str, Any]] = []
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, Mapping) or not isinstance(case.get("account"), Mapping):
            raise ValueError("case account mapping required")
        account = case["account"]
        if account.get("tenant_id") != tenant_id:
            raise ValueError("mixed tenant case refused")
        key = _text(account.get("opportunity_key"))
        if not key or key in seen:
            raise ValueError("missing or duplicate opportunity key")
        seen.add(key)
        prepared.append(build_jev_gtm_decision(
            account=account,
            signals=case.get("signals") or (),
            as_of=as_of,
            relationship=case.get("relationship"),
            outreach=case.get("outreach"),
            reply=case.get("reply"),
            quant_packet=case.get("quant_packet"),
        ))
    def _order(row: Mapping[str, Any]) -> tuple[int, float, str]:
        econ = row["economics"]
        upside = (max(0.0, econ["expected_gross_profit_cents"])
                  if econ["status"] == "MODELED" else 0.0)
        return REVIEW_PRIORITY[row["action"]], -upside, row["opportunity_key"]
    prepared.sort(key=_order)
    totals = {name: 0 for name in REVIEW_PRIORITY}
    for row in prepared:
        totals[row["action"]] += 1
    return {
        "schema_version": "empire.jev.gtm_review_queue.v2",
        "tenant_id": tenant_id,
        "as_of": as_of.astimezone(timezone.utc).isoformat(),
        "item_count": len(prepared),
        "items": prepared,
        "action_counts": totals,
        "priority_basis": "review_class_then_verified_economic_projection_not_probability",
        "read_only": True,
        "outbound_sent": False,
        "paid_api_called": False,
        "database_write": False,
        "execution_authority": "none",
    }
