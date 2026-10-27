"""Original call-acquisition intelligence: no-PII, reason-coded call-loss study.

Two separate views:
* Actual, accessible original Lead Smart pulse and pilot state (no call-to-cash).
* A STRICT contract for *future* owner-approved same-cohort aggregates.

This module never calls Ringba, reads privileged financial receipts, asks for
caller IDs/recordings, or enables a route. Provider connection != human answer,
and provider payout != independently settled revenue.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "empire.competitor_call_loss_readiness.v1"
PULSE_SCHEMA = "empire.lead_smart.commercial_pulse.v1"
PILOT_SCHEMA = "empire.lead_smart.effective_pilot_state.v1"
PULSE = Path("runtime/revenue/lead_smart/commercial_pulse/latest.json")
PILOT = Path("runtime/revenue/lead_smart/effective_pilot_state/latest.json")
DEST = Path("runtime/competitive_intelligence/call_loss_readiness_latest.json")
OFFICIAL_REPORT = "https://support.ringba.com/hc/en-us/articles/26894023126551"
OFFICIAL_DASHBOARD = "https://support.ringba.com/hc/en-us/articles/24286807682839-Ringba-Dashboard"

NO_CONNECT_REASONS = (
    "NO_ELIGIBLE_TARGET",
    "TARGET_NO_ANSWER",
    "TARGET_BUSY",
    "TARGET_ERROR",
    "CALLER_LEFT_BEFORE_CONNECTION",
    "BLOCKED_BY_SOURCE_POLICY",
    "UNCLASSIFIED_NO_CONNECT",
)
NO_PAYABLE_REASONS = (
    "WRONG_SERVICE",
    "WRONG_GEOGRAPHY",
    "BELOW_CONTRACT_DURATION",
    "DUPLICATE_OR_REPEAT",
    "BUYER_DECLINED_UNDER_WRITTEN_TERMS",
    "DISPUTED_OR_REVERSAL_PENDING",
    "UNCLASSIFIED_NOT_PAYABLE",
)
COUNTS = (
    "provider_incoming_calls",
    "provider_target_connected_calls",
    "buyer_human_answered_calls",
    "buyer_accepted_payable_calls",
    "independently_settled_calls",
)


def _clock(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        t = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        return None
    return t.astimezone(timezone.utc) if t.tzinfo else None


def _bool(value: Any) -> bool:
    return type(value) is bool and value


def summarize_readable_pulse(
    pulse: Mapping[str, Any] | None,
    pilot: Mapping[str, Any] | None,
    *, now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("aware review clock required")
    now = now.astimezone(timezone.utc)
    p = pulse if isinstance(pulse, Mapping) else {}
    state = pilot if isinstance(pilot, Mapping) else {}
    pulse_valid = (
        p.get("schema_version") == PULSE_SCHEMA
        and p.get("buyer") == "Lead Smart"
        and p.get("raw_call_identifiers_persisted") is False
        and p.get("no_real_revenue_inferred_from_tracking") is True
        and p.get("caller_personal_data_persisted") is False
        and p.get("qualified_billable_calls_verified") is False
        and p.get("settled_revenue_verified") is False
    )
    ts = _clock(p.get("observed_at_utc")) if pulse_valid else None
    age = (now - ts).total_seconds() if ts else None
    pulse_fresh = bool(
        pulse_valid and age is not None and 0 <= age <= 36 * 3600
    )
    ringba = p.get("ringba") if pulse_fresh else None
    if not isinstance(ringba, Mapping):
        ringba = {}
    exact = ringba.get("matching_rows_in_returned_window")
    exact = exact if type(exact) is int and 0 <= exact <= 50000 else None
    if ringba.get("status") != "RESTRICTED_PROVIDER_ROWS_OBSERVED":
        exact = None
    pilot_valid = (
        state.get("schema_version") == PILOT_SCHEMA
        and state.get("buyer") == "Lead Smart"
        and state.get("execution_authority") == "NONE"
        and state.get("revenue_recognized") is False
    )
    expires = _clock(p.get("campaign_expires_at")) if pulse_fresh else None
    expired_in_snapshot = expires is not None and expires < now
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "generated_at": now.isoformat(),
        "original_commercial_pulse_available": pulse_valid,
        "original_commercial_pulse_fresh": pulse_fresh,
        "original_commercial_pulse_observed_at": ts.isoformat() if ts else None,
        "pilot_source_valid": pilot_valid,
        "pilot_mode": state.get("mode") if pilot_valid else None,
        "traffic_enabled_in_original_pilot": (
            state.get("traffic_enabled") if pilot_valid
            and type(state.get("traffic_enabled")) is bool else None
        ),
        "routing_enabled_in_original_pilot": (
            state.get("routing_enabled") if pilot_valid
            and type(state.get("routing_enabled")) is bool else None
        ),
        "campaign_expiry_in_pulse": (
            expires.isoformat() if expires else None
        ),
        "campaign_expiry_in_pulse_is_past": expired_in_snapshot,
        "campaign_expiry_is_provider_currently_confirmed": False,
        "ringba_matching_rows_bounded_observation": exact,
        "bounded_rows_absence_is_proof_of_no_calls": False,
        "ringba_provider_payout_as_settled_revenue": False,
        "buyer_target_connection_verified": (
            False if pulse_fresh and ringba.get("buyer_leg_connected_verified") is False
            else None
        ),
        "buyer_human_answer_count_verified": None,
        "ringba_target_connected_count_verified": None,
        "accepted_payable_call_count_verified": None,
        "independently_settled_call_count_verified": None,
        "actual_cash_margin_cents": None,
        "all_disposition_reasons_unknown": True,
        "source_to_cash_attribution_verified": False,
        "call_qa_operators": [
            {
                "reason_group": "NO_TARGET_OR_BUYER_UNAVAILABLE",
                "provider_report_columns": [
                    "No Targets", "No Answer", "No Connect", "Incomplete Call Reason"
                ],
                "original_owner": "ORIGINAL_RINGBA_COMMERCIAL_OWNER",
                "next_evidence": "Owner-approved aggregate source-joined no-target/no-answer/target-busy dispositions",
            },
            {
                "reason_group": "SOURCE_OR_CALLER_UNQUALIFIED",
                "provider_report_columns": [
                    "Block Reason", "No Conversion Reason", "No Payout Reason"
                ],
                "original_owner": "ORIGINAL_BUYER_AND_PUBLISHER_QA_OWNER",
                "next_evidence": "Written buyer rule + privacy-safe aggregate call rejection reason",
            },
            {
                "reason_group": "PAYABLE_OR_SETTLEMENT_UNVERIFIED",
                "provider_report_columns": ["Converted", "Approved Adjustment", "Revenue", "Payout"],
                "original_owner": "ORIGINAL_COMMERCIAL_FINANCE_OWNER",
                "next_evidence": "Original owner verifies payable acceptance, reversal and independent bank settlement",
            },
        ],
        "official_ringba_sources": [OFFICIAL_REPORT, OFFICIAL_DASHBOARD],
        "top_owner_action": (
            "VERIFY_ORIGINAL_CAMPAIGN_EXPIRY_WITH_OWNER"
            if expired_in_snapshot
            else "VERIFY_ORIGINAL_BUYER_AVAILABILITY_AND_CALL_DISPOSITION"
        ),
        "routing_changes_authorized": False,
        "source_ad_spend_authorized": False,
        "live_call_activation_authorized": False,
        "protected_commercial_receipts_opened": False,
        "execution_authority": "none",
    }


def evaluate_approved_call_cohort(
    *,
    source_id: str,
    cohort_ref: str,
    counts: Mapping[str, int | None],
    no_connect_reasons: Mapping[str, int] | None,
    no_payable_reasons: Mapping[str, int] | None,
    refs: Mapping[str, str | None],
    original_owner_authorized: bool,
    source_lineage_verified: bool,
    buyer_acceptance_verified: bool,
    unique_inbound_terminal_dispositions_verified: bool,
) -> dict[str, Any]:
    """Never transform an unverified aggregate into a real call cohort.

    Reason buckets count only UNIQUE incoming calls' final terminal outcome.
    Ringba dashboard "No Answer" can count *target attempts*, not unique calls:
    raw target-attempt counters must never be added to call-level buckets.
    Actual reason totals require original-owner approval, verified terminal
    deduplication, source-joined counts and stage receipts. No call identifiers.
    """
    if (not isinstance(source_id, str) or not 2 <= len(source_id) <= 80
            or not source_id.replace("_", "").isalnum()
            or not isinstance(cohort_ref, str) or not 8 <= len(cohort_ref) <= 160
            or not isinstance(counts, Mapping) or set(counts) != set(COUNTS)
            or not isinstance(refs, Mapping) or set(refs) != set(COUNTS)
            or any(type(flag) is not bool for flag in (
                original_owner_authorized, source_lineage_verified,
                buyer_acceptance_verified,
                unique_inbound_terminal_dispositions_verified,
            ))):
        raise ValueError("untrusted call cohort contract")
    for stage in COUNTS:
        n = counts[stage]
        ref = refs[stage]
        if n is not None and (type(n) is not int or not 0 <= n <= 100_000):
            raise ValueError("invalid count")
        if ref is not None and (not isinstance(ref, str) or not 8 <= len(ref) <= 180):
            raise ValueError("invalid aggregate receipt")
    prior = None
    for name in COUNTS:
        n = counts[name]
        if n is not None and prior is not None and n > prior:
            raise ValueError("non-monotonic cohort counts")
        prior = n
    def reason_check(raw: Mapping[str, int] | None, names: tuple[str, ...],
                     expected: int | None) -> dict | None:
        if raw is None:
            return None
        if not isinstance(raw, Mapping) or set(raw) != set(names):
            raise ValueError("complete approved reason taxonomy required")
        if any(type(v) is not int or v < 0 or v > 100_000 for v in raw.values()):
            raise ValueError("invalid reason count")
        if expected is None or sum(raw.values()) != expected:
            raise ValueError("reason counts conflict with owner total")
        return dict(raw)
    nc = reason_check(no_connect_reasons, NO_CONNECT_REASONS,
                      counts["provider_incoming_calls"] -
                      counts["provider_target_connected_calls"]
                      if counts["provider_incoming_calls"] is not None
                      and counts["provider_target_connected_calls"] is not None
                      else None)
    np = reason_check(no_payable_reasons, NO_PAYABLE_REASONS,
                      counts["buyer_human_answered_calls"] -
                      counts["buyer_accepted_payable_calls"]
                      if counts["buyer_human_answered_calls"] is not None
                      and counts["buyer_accepted_payable_calls"] is not None
                      else None)
    authoritative = (
        original_owner_authorized and source_lineage_verified
        and buyer_acceptance_verified
        and unique_inbound_terminal_dispositions_verified
        and all(counts[k] is not None and refs[k] for k in COUNTS)
    )
    if not authoritative:
        nc, np = None, None
    incoming = counts["provider_incoming_calls"] if authoritative else None
    connected = counts["provider_target_connected_calls"] if authoritative else None
    human = counts["buyer_human_answered_calls"] if authoritative else None
    payable = counts["buyer_accepted_payable_calls"] if authoritative else None
    return {
        "schema_version": "empire.competitor_call_loss_approved_cohort.v1",
        "mode": "OBSERVE", "source_id": source_id,
        "cohort_ref": cohort_ref,
        "authoritative_original_owner_cohort": authoritative,
        "unique_inbound_terminal_dispositions_verified":
            unique_inbound_terminal_dispositions_verified,
        "raw_ringba_target_attempt_counters_not_used": True,
        "provider_incoming_calls": incoming,
        "provider_target_connected_calls": connected,
        "buyer_human_answered_calls": human,
        "buyer_accepted_payable_calls": payable,
        "independently_settled_calls": (
            counts["independently_settled_calls"] if authoritative else None
        ),
        "no_connect_reasons": nc,
        "not_payable_reasons_among_human_answered": np,
        "target_connected_is_human_answered": False,
        "publisher_defect_inferred": False,
        "buyer_misconduct_inferred": False,
        "settled_revenue_inferred": False,
        "status": ("REVIEWABLE_APPROVED_AGGREGATE" if authoritative
                   else "ORIGINAL_OWNER_LINEAGE_NOT_VERIFIED"),
        "live_routing_authorized": False,
        "execution_authority": "none",
    }


def _load_readonly(path: Path) -> dict | None:
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 150_000:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, UnicodeError, ValueError):
        return None


def refresh(root: Path) -> dict:
    report = summarize_readable_pulse(
        _load_readonly(root / PULSE),
        _load_readonly(root / PILOT),
    )
    destination = root / DEST
    if not destination.parent.is_dir() or destination.parent.is_symlink() or destination.is_symlink():
        raise ValueError("unsafe original read-only research destination")
    fd, tmp = tempfile.mkstemp(prefix=".call-loss-", dir=destination.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as writer:
            json.dump(report, writer, indent=2, sort_keys=True)
            writer.write("\n")
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(tmp, destination)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return report
