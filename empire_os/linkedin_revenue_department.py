"""Governed LinkedIn Revenue Department orchestration.

This module maps the familiar LinkedIn acquisition loop (ICP -> account research
-> decision-maker resolution -> buying signals -> prioritisation -> drafting ->
content -> follow-up -> reply classification) onto existing EmpireOS
intelligence primitives.

It is analysis-only. It does not browse LinkedIn, mutate canonical data, send
messages, connect with people, post content, or grant outreach authority.
Unknown evidence remains unknown.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from empire_os.icp_buyer_trigger_intelligence import assess_icp_candidate
from empire_os.outreach_account_strategy import (
    build_buying_committee,
    evaluate_contact_fatigue,
)
from empire_os.outreach_message_optimizer import optimise_first_touch
from empire_os.predictive_revenue_formula import expected_revenue_value
from empire_os.reply_classifier import classify_reply_text


SCHEMA_VERSION = "empire.linkedin_revenue_department.v1"
SCOUT_SNAPSHOT = Path("runtime/buyer_acquisition/scout_latest.json")
OUTPUT = Path("runtime/buyer_acquisition/linkedin_revenue_department_latest.json")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _parse_time(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _observed_signals(
    signals: Iterable[Mapping[str, Any]],
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    """Keep only timestamped, evidenced, non-future public/observed signals."""
    rows: list[dict[str, Any]] = []
    for raw in signals or ():
        evidence_ref = _text(raw.get("evidence_ref"))
        observed_at = _parse_time(raw.get("observed_at"))
        signal_type = _text(raw.get("signal_type")) or "other"
        summary = _text(raw.get("summary"))
        if not evidence_ref or observed_at is None or observed_at > now:
            continue
        age_days = max(0.0, (now - observed_at).total_seconds() / 86400.0)
        rows.append({
            "signal_type": signal_type,
            "summary": summary or None,
            "observed_at": observed_at.isoformat(),
            "age_days": round(age_days, 2),
            "confidence": _number(raw.get("confidence")),
            "evidence_ref": evidence_ref,
            "source": _text(raw.get("source")) or None,
            "observed": True,
        })
    rows.sort(key=lambda row: (row["observed_at"], row["evidence_ref"]), reverse=True)
    return rows


def _economic_projection(inputs: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(inputs or {})
    try:
        return expected_revenue_value(data)
    except (TypeError, ValueError) as exc:
        return {
            "schema_version": "empire.predictive_revenue.erv.v1",
            "status": "UNAVAILABLE",
            "missing_fields": [],
            "reason": "invalid_economic_inputs",
            "error": str(exc),
            "unknown_is_zero": False,
            "prediction_only": True,
            "actual_revenue": False,
            "execution_authority": "none",
        }


def _content_brief(
    *,
    business_name: str,
    signals: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Create an evidence-only content brief without inventing a narrative."""
    evidence = [
        {
            "signal_type": row.get("signal_type"),
            "summary": row.get("summary"),
            "evidence_ref": row.get("evidence_ref"),
        }
        for row in signals[:5]
    ]
    themes = list(dict.fromkeys(
        _text(row.get("signal_type"))
        for row in signals
        if _text(row.get("signal_type"))
    ))
    return {
        "business_name": business_name,
        "observed_signal_themes": themes[:5],
        "evidence": evidence,
        "content_recommendation": (
            "review_observed_signal_for_founder_or_market_commentary"
            if evidence else "insufficient_observed_evidence"
        ),
        "invented_claims": False,
        "post_enabled": False,
        "execution_authority": "none",
    }


def _reply_state(record: Mapping[str, Any]) -> dict[str, Any] | None:
    body = record.get("reply_text")
    subject = record.get("reply_subject")
    if body is None and subject is None:
        return None
    result = classify_reply_text(body, subject)
    return {
        **result,
        "mutation_applied": False,
        "execution_authority": "none",
    }


def _sequence_recommendation(
    *,
    suppressed: bool,
    fatigue: Mapping[str, Any],
    reply: Mapping[str, Any] | None,
    touch_count: int,
) -> dict[str, Any]:
    if suppressed:
        action = "STOP_SUPPRESSED"
        reason = "suppression_is_authoritative"
    elif reply and reply.get("classification") == "unsubscribe":
        action = "STOP_UNSUBSCRIBE"
        reason = "unsubscribe_detected"
    elif reply and reply.get("classification") == "negative":
        action = "STOP_NEGATIVE"
        reason = "negative_reply_detected"
    elif reply and reply.get("classification") == "later":
        action = "REVIEW_LATER_FOLLOWUP"
        reason = "later_reply_detected"
    elif reply and reply.get("classification") in {"positive", "question", "objection"}:
        action = "REVIEW_REPLY"
        reason = f"{reply.get('classification')}_reply_detected"
    elif fatigue.get("blocked"):
        action = "HOLD"
        reason = "contact_fatigue_or_invalid_touch_evidence"
    elif touch_count:
        action = "REVIEW_FOLLOWUP"
        reason = "prior_touch_observed"
    else:
        action = "REVIEW_FIRST_TOUCH"
        reason = "no_prior_touch_observed"

    return {
        "recommended_action": action,
        "reason": reason,
        "recommendation_only": True,
        "message_send_enabled": False,
        "connection_action_enabled": False,
        "execution_authority": "none",
    }


def build_linkedin_revenue_opportunity(
    record: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build one evidence-backed LinkedIn acquisition review packet."""
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    business_name = _text(record.get("business_name"))
    if not business_name:
        raise ValueError("business_name is required")

    icp = assess_icp_candidate(
        record,
        target_profile_keys=record.get("target_profile_keys") or (),
    )
    committee = build_buying_committee(
        record.get("first_party_people") or ()
    )
    primary = committee.get("primary")
    observed_signals = _observed_signals(
        record.get("signals") or (),
        now=current,
    )
    touches = [
        dict(row)
        for row in (record.get("touches") or ())
        if isinstance(row, Mapping)
    ]
    fatigue = evaluate_contact_fatigue(touches, now=current)
    suppressed = record.get("suppressed") is True
    reply = _reply_state(record)
    economics = _economic_projection(record.get("economic_inputs"))

    reason_now = next(
        (
            _text(row.get("summary"))
            for row in observed_signals
            if _text(row.get("summary"))
        ),
        "",
    )
    proof = reason_now
    message = None
    if primary and reason_now:
        message = optimise_first_touch(
            business_name=business_name,
            reason_now=reason_now,
            proof=proof,
            contact_title=primary.get("title"),
            territory=_text(record.get("territory")) or None,
            sender_email=_text(record.get("sender_email")) or None,
            brand_domain=_text(record.get("brand_domain")) or None,
            enterprise_target=record.get("enterprise_target") is True,
        )

    blockers: list[str] = []
    if primary is None:
        blockers.append("decision_maker_unresolved")
    elif primary.get("contact_verified") is not True:
        blockers.append("contact_unverified")
    if not observed_signals:
        blockers.append("buying_signal_unknown")
    if not reason_now:
        blockers.append("message_proof_unavailable")
    if suppressed:
        blockers.append("suppressed")
    for blocker in fatigue.get("blockers") or []:
        if blocker not in blockers:
            blockers.append(str(blocker))

    sequence = _sequence_recommendation(
        suppressed=suppressed,
        fatigue=fatigue,
        reply=reply,
        touch_count=len(touches),
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "OBSERVE",
        "channel": "linkedin",
        "account": {
            "account_id": _text(record.get("account_id")) or None,
            "business_name": business_name,
            "territory": _text(record.get("territory")) or None,
            "source_evidence_ref": _text(
                record.get("source_evidence_ref")
            ) or None,
        },
        "stage_01_icp": icp,
        "stage_02_account_research": {
            "research_status": (
                "EVIDENCED"
                if _text(record.get("source_evidence_ref"))
                else "PARTIAL"
            ),
            "description_present": bool(_text(record.get("description"))),
            "notes_present": bool(_text(record.get("notes"))),
            "invented_account_facts": False,
        },
        "stage_03_decision_makers": committee,
        "stage_04_buying_signals": {
            "state": "OBSERVED_SIGNALS" if observed_signals else "UNKNOWN",
            "observed_signal_count": len(observed_signals),
            "signals": observed_signals,
            "binding_intent_verified": False,
        },
        "stage_05_priority": {
            "model_fit_score": icp.get("model_fit_score"),
            "score_classification": icp.get("score_classification"),
            "expected_revenue_value": economics,
            "ranking_basis": (
                "expected_revenue_value_then_fit"
                if economics.get("status") == "AVAILABLE"
                else "fit_and_observed_evidence_review_only"
            ),
            "new_revenue_scoring_model_introduced": False,
        },
        "stage_06_personalised_outreach": {
            "draft": message,
            "reason_now": reason_now or None,
            "evidence_ref": (
                observed_signals[0].get("evidence_ref")
                if observed_signals else None
            ),
            "outreach_authorized": False,
            "send_enabled": False,
            "execution_authority": "none",
        },
        "stage_07_linkedin_content": _content_brief(
            business_name=business_name,
            signals=observed_signals,
        ),
        "stage_08_follow_up": {
            "fatigue": fatigue,
            "sequence": sequence,
        },
        "stage_09_replies": reply,
        "review_readiness": {
            "ready_for_human_review": not blockers,
            "blockers": blockers,
            "suppressed": suppressed,
            "linkedin_automation_enabled": False,
            "outreach_authorized": False,
            "execution_authority": "none",
        },
        "truth_contract": {
            "observed_signal_is_binding_intent": False,
            "reply_is_revenue": False,
            "meeting_is_revenue": False,
            "forecast_is_revenue": False,
            "actual_revenue": False,
            "unknown_preserved": True,
            "synthetic_data_allowed": False,
            "execution_authority": "none",
        },
    }


def scout_candidate_to_linkedin_record(
    candidate: Mapping[str, Any],
    *,
    observed_at: str | None,
) -> dict[str, Any]:
    """Adapt Buyer Scout evidence without promoting it to verified intent.

    Buyer Scout trigger terms were observed in first-party/public site evidence.
    The scout snapshot timestamp is the observation timestamp for this derived
    channel packet. People are only promoted into the buying committee when the
    upstream record already carries an explicit person id and evidence ref.
    """
    website = _text(candidate.get("website"))
    people: list[dict[str, Any]] = []
    for raw in candidate.get("first_party_people") or ():
        if not isinstance(raw, Mapping):
            continue
        if (
            not _text(raw.get("person_id"))
            or not _text(raw.get("name"))
            or not _text(raw.get("evidence_ref"))
        ):
            continue
        people.append(dict(raw))

    signals: list[dict[str, Any]] = []
    if website and observed_at:
        for trigger in candidate.get("observed_buying_triggers") or ():
            term = _text(trigger)
            if not term:
                continue
            signals.append({
                "signal_type": "public_buying_trigger_term",
                "summary": f"Observed public trigger term: {term}",
                "observed_at": observed_at,
                "evidence_ref": website,
                "source": "buyer_acquisition_scout_first_party_site",
                "confidence": None,
            })

    return {
        "business_name": _text(candidate.get("business_name")),
        "description": _text(candidate.get("description")),
        "buyer_type": _text(candidate.get("buyer_type")),
        "direct_signal_hits": list(
            candidate.get("direct_signal_hits") or ()
        ),
        "reseller_signal_hits": list(
            candidate.get("reseller_signal_hits") or ()
        ),
        "target_buyer_pools": list(
            candidate.get("target_buyer_pools") or ()
        ),
        "target_product_codes": list(
            candidate.get("target_product_codes") or ()
        ),
        "target_profile_keys": list(
            candidate.get("target_icp_profile_keys") or ()
        ),
        "first_party_people": people,
        "signals": signals,
        "source_evidence_ref": website or None,
        "enterprise_target": (
            candidate.get("predictive_revenue_enterprise_candidate") is True
        ),
        "scout_provenance": {
            "domain": _text(candidate.get("domain")) or None,
            "discovery_source": _text(
                candidate.get("discovery_source")
            ) or None,
            "query_evidence_count": int(
                candidate.get("query_evidence_count") or 0
            ),
            "candidate_state": _text(
                candidate.get("candidate_state")
            ) or None,
            "canonical_identity_verified": (
                candidate.get("canonical_identity_verified") is True
            ),
            "commercial_terms_verified": (
                candidate.get("commercial_terms_verified") is True
            ),
        },
    }


def build_linkedin_revenue_department_from_scout_snapshot(
    scout_snapshot: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Project a Buyer Scout snapshot into the governed LinkedIn review lane."""
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    generated = _parse_time(scout_snapshot.get("generated_at"))
    observed_at = (
        generated.isoformat()
        if generated is not None and generated <= current
        else None
    )
    records = [
        scout_candidate_to_linkedin_record(
            candidate,
            observed_at=observed_at,
        )
        for candidate in (scout_snapshot.get("candidates") or ())
        if isinstance(candidate, Mapping)
        and _text(candidate.get("business_name"))
    ]
    payload = build_linkedin_revenue_department_snapshot(
        records,
        now=current,
    )
    payload.update({
        "source": "buyer_acquisition_scout",
        "source_schema_version": scout_snapshot.get("schema_version"),
        "source_generated_at": (
            generated.isoformat() if generated is not None else None
        ),
        "source_candidate_count": len(records),
        "source_snapshot_fresh_enough_for_signal_time": (
            observed_at is not None
        ),
        "database_write_performed": False,
        "outbound_sent": False,
        "content_posted": False,
    })
    return payload


def _priority_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    stage = row.get("stage_05_priority") or {}
    economics = stage.get("expected_revenue_value") or {}
    available = economics.get("status") == "AVAILABLE"
    erv = _number(economics.get("expected_revenue_value_cents"))
    fit = _number(stage.get("model_fit_score")) or 0.0
    signals = (
        row.get("stage_04_buying_signals") or {}
    ).get("observed_signal_count") or 0
    primary = (row.get("stage_03_decision_makers") or {}).get("primary") or {}
    contact_verified = primary.get("contact_verified") is True
    business = _text((row.get("account") or {}).get("business_name")).lower()
    return (
        0 if available else 1,
        -(erv or 0.0),
        -fit,
        -int(signals),
        0 if contact_verified else 1,
        business,
    )


def build_linkedin_revenue_department_snapshot(
    records: Iterable[Mapping[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build and rank a read-only LinkedIn acquisition department snapshot."""
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    items = [
        build_linkedin_revenue_opportunity(row, now=current)
        for row in (records or ())
        if isinstance(row, Mapping)
    ]
    items.sort(key=_priority_key)
    for rank, row in enumerate(items, 1):
        row["review_rank"] = rank

    return {
        "schema_version": "empire.linkedin_revenue_department.snapshot.v1",
        "mode": "OBSERVE",
        "generated_at": current.isoformat(),
        "channel": "linkedin",
        "candidate_count": len(items),
        "observed_signal_candidate_count": sum(
            1
            for row in items
            if (row["stage_04_buying_signals"]["observed_signal_count"] > 0)
        ),
        "human_review_ready_count": sum(
            1
            for row in items
            if row["review_readiness"]["ready_for_human_review"]
        ),
        "resolved_decision_maker_count": sum(
            1
            for row in items
            if row["stage_03_decision_makers"]["primary"] is not None
        ),
        "verified_contact_count": sum(
            1
            for row in items
            if (
                (row["stage_03_decision_makers"]["primary"] or {}).get(
                    "contact_verified"
                ) is True
            )
        ),
        "outreach_draft_count": sum(
            1
            for row in items
            if row["stage_06_personalised_outreach"]["draft"] is not None
        ),
        "reply_classified_count": sum(
            1 for row in items if row["stage_09_replies"] is not None
        ),
        "positive_reply_count": sum(
            1
            for row in items
            if (
                (row["stage_09_replies"] or {}).get("classification")
                == "positive"
            )
        ),
        "economic_value_available_count": sum(
            1
            for row in items
            if row["stage_05_priority"]["expected_revenue_value"].get(
                "status"
            ) == "AVAILABLE"
        ),
        "predicted_expected_revenue_value_cents_total": round(
            sum(
                float(
                    row["stage_05_priority"]["expected_revenue_value"].get(
                        "expected_revenue_value_cents"
                    )
                    or 0.0
                )
                for row in items
                if row["stage_05_priority"]["expected_revenue_value"].get(
                    "status"
                ) == "AVAILABLE"
            ),
            4,
        ),
        "items": items,
        "linkedin_automation_enabled": False,
        "live_outbound_enabled": False,
        "commercial_authority": "none",
        "execution_authority": "none",
    }



def refresh_linkedin_revenue_department(
    repo_root: str | Path,
) -> dict[str, Any]:
    """Refresh the channel snapshot from the latest Buyer Scout evidence."""
    root = Path(repo_root).resolve()
    try:
        raw = json.loads(
            (root / SCOUT_SNAPSHOT).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        raw = {}
    scout = raw if isinstance(raw, dict) else {}
    payload = build_linkedin_revenue_department_from_scout_snapshot(
        scout
    )
    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
