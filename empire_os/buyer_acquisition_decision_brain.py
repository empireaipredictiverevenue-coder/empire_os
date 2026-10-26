"""Decision policy inside the ORIGINAL Buyer Acquisition Team cycle.

Not a new agent/scheduler. Evidence-led portfolio decisions and one bounded
existing internal refresh, with persistent semantic memory and no authority to
send email, mutate EmpireDB, change an external system or activate finances.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
from tempfile import NamedTemporaryFile
from typing import Any

SCHEMA = "empire.buyer_acquisition.decision_brain.v1"
REL = Path("runtime/buyer_network_intelligence")
QUAL = REL / "founder_qualification_actions_latest.json"
STATE = REL / "team_brain_state_latest.json"
REPORT = REL / "team_brain_latest.json"
DOMAIN = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")
REFRESH_AFTER = 20 * 60
REFRESH_COOLDOWN = 20 * 60
MAX_OUTPUT_TASKS = 25
MAX_STORED_IDENTITIES = 500


class BuyerDecision(str, Enum):
    """Internal, evidence-only decision vocabulary (not execution authority)."""
    REVIEW_EXISTING_BUYER_RELATIONSHIP = "REVIEW_EXISTING_BUYER_RELATIONSHIP"
    REVIEW_PREVIOUS_BUYER_CONTACT = "REVIEW_PREVIOUS_BUYER_CONTACT"
    VERIFY_COMPANY_BUYER_ROLE = "VERIFY_COMPANY_BUYER_ROLE"
    VERIFY_FIRST_PARTY_SITE = "VERIFY_FIRST_PARTY_SITE"
    VERIFY_BUYER_GEO_AND_PRODUCT_REQUIREMENTS = "VERIFY_BUYER_GEO_AND_PRODUCT_REQUIREMENTS"
    VERIFY_DECISION_MAKER_AND_CONTACT = "VERIFY_DECISION_MAKER_AND_CONTACT"
    RESEARCH_COMPANY_ROLE = "RESEARCH_COMPANY_ROLE"
    RESEARCH_EVENT_ECOSYSTEM = "RESEARCH_EVENT_ECOSYSTEM"


OWNER = {
    "REVIEW_EXISTING_BUYER_RELATIONSHIP": "existing_founder_commercial_review",
    "REVIEW_PREVIOUS_BUYER_CONTACT": "existing_buyer_gmail_evidence_owner",
    "VERIFY_COMPANY_BUYER_ROLE": "existing_buyer_network_research_owner",
    "VERIFY_FIRST_PARTY_SITE": "existing_buyer_network_due_diligence_owner",
    "VERIFY_BUYER_GEO_AND_PRODUCT_REQUIREMENTS": "existing_buyer_network_research_owner",
    "VERIFY_DECISION_MAKER_AND_CONTACT": "existing_buyer_network_contact_intelligence_owner",
    "RESEARCH_COMPANY_ROLE": "existing_buyer_network_research_owner",
    "RESEARCH_EVENT_ECOSYSTEM": "existing_buyer_network_research_owner",
}
SAFE_STATES = frozenset(action.value for action in BuyerDecision)
assert SAFE_STATES == frozenset(OWNER), "Every typed decision needs one original owner"
SENSITIVE_ACTIONS = frozenset({
    "NO_NEW_SEND_RECONCILE_SUPPRESSION_OR_DELIVERY",
})
LIVE = frozenset({
    "EXISTING_CONVERSATION", "WORKSPACE_RECIPROCAL_THREAD_OBSERVED",
    "FOUNDER_FORM_SUBMITTED",
})
PREVIOUS = frozenset({
    "ALREADY_CONTACTED", "WORKSPACE_SENT_ALREADY_CONTACTED",
    "FOUNDER_REVIEWED_PRIOR_GMAIL_THREAD",
})
EVENT = "INDUSTRY_CONFERENCE_NOT_VERIFIED_LEAD_BUYER"


def digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def _read(root: Path, relative: Path, max_bytes: int = 2_500_000) -> dict:
    path = root / relative
    if path.is_symlink() or not path.is_file() or not 20 < path.stat().st_size <= max_bytes:
        raise ValueError("buyer_team_source_missing_or_unsafe_" + relative.name)
    document = json.loads(path.read_text())
    if not isinstance(document, dict):
        raise ValueError("buyer_team_source_invalid_" + relative.name)
    return document


def _stamp(raw: Any, *, now: datetime, max_age: float = 3600 * 3) -> float:
    try:
        observed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if observed.utcoffset() is None:
            raise ValueError("no UTC offset")
        age = now.timestamp() - observed.timestamp()
    except (ValueError, OverflowError, TypeError) as exc:
        raise ValueError("buyer_team_invalid_source_time") from exc
    if not -300 <= age <= max_age:
        raise ValueError("buyer_team_stale_or_future_source_time")
    return age


def classify(row: dict) -> str | None:
    """Conservative portfolio direction; not buyer admission or task dispatch."""
    action = row.get("commercial_next_action")
    contact = row.get("contact_history_state")
    tier = row.get("tier")
    fit = row.get("active_demand_sector_research_fit")
    fit = fit if isinstance(fit, dict) else {}
    dd = row.get("first_party_due_diligence")
    dd = dd if isinstance(dd, dict) else {}
    if (action in SENSITIVE_ACTIONS or tier in
            ("MANUAL_EVIDENCE_HOLD", "AUTOMATED_EVIDENCE_HOLD")
            or row.get("manual_hold_reason") is not None
            or row.get("automated_hold_reason") is not None
            or row.get("outbound_authorized") is True
            or contact in ("SOURCE_UNAVAILABLE", "DO_NOT_PURSUE",
                           "DELIVERY_HOLD", "EXISTING_CONVERSATION_PARTIAL_BOUNCE")):
        return None
    if row.get("buyer_relationship_role_review") == EVENT:
        return "RESEARCH_EVENT_ECOSYSTEM"
    if contact in LIVE:
        return "REVIEW_EXISTING_BUYER_RELATIONSHIP"
    if contact in PREVIOUS:
        return "REVIEW_PREVIOUS_BUYER_CONTACT"
    if dd.get("freshness") != "CURRENT" and tier in (
            "FOUNDER_REVIEW_ONLY", "DUE_DILIGENCE_PENDING", "EVIDENCE_RECOVERY"):
        return "VERIFY_FIRST_PARTY_SITE"
    if (tier == "FOUNDER_REVIEW_ONLY" and
            fit.get("state") == "FIRST_PARTY_SECTOR_RESEARCH_FIT" and
            fit.get("market_or_zip_coverage_verified") is False):
        return "VERIFY_BUYER_GEO_AND_PRODUCT_REQUIREMENTS"
    if tier == "FOUNDER_REVIEW_ONLY":
        return "VERIFY_DECISION_MAKER_AND_CONTACT"
    if tier == "EVIDENCE_RECOVERY" or tier == "DUE_DILIGENCE_PENDING":
        if fit.get("state") == "FIRST_PARTY_SECTOR_RESEARCH_FIT":
            return "VERIFY_BUYER_GEO_AND_PRODUCT_REQUIREMENTS"
        return "VERIFY_COMPANY_BUYER_ROLE"
    return "RESEARCH_COMPANY_ROLE"


def _priority(row: dict, action: str) -> int:
    tier = row.get("tier")
    fit = row.get("active_demand_sector_research_fit")
    fit = fit if isinstance(fit, dict) else {}
    priority = {
        "REVIEW_EXISTING_BUYER_RELATIONSHIP": 100,
        "REVIEW_PREVIOUS_BUYER_CONTACT": 72,
        "VERIFY_BUYER_GEO_AND_PRODUCT_REQUIREMENTS": 82,
        "VERIFY_DECISION_MAKER_AND_CONTACT": 67,
        "VERIFY_FIRST_PARTY_SITE": 62,
        "VERIFY_COMPANY_BUYER_ROLE": 40,
        "RESEARCH_COMPANY_ROLE": 20,
        "RESEARCH_EVENT_ECOSYSTEM": 12,
    }[action]
    if tier == "FOUNDER_REVIEW_ONLY":
        priority += 8
    if fit.get("state") == "FIRST_PARTY_SECTOR_RESEARCH_FIT":
        priority += 14
    units = fit.get("observed_overflow_units_for_sectors")
    if type(units) is int:
        priority += min(units, 20) // 4
    return min(priority, 150)


def review(snapshot: dict, previous: dict | None, *, now: datetime,
           refresh_attempt: dict | None = None) -> tuple[dict, dict]:
    """Decision memory: observe changed evidence once, don't reissue unchanged tasks."""
    if (snapshot.get("schema_version") != "empire.buyer_qualification_actions.v1"
            or snapshot.get("mode") != "OBSERVE"
            or snapshot.get("execution_authority") != "none"
            or snapshot.get("outbound_sent") is not False
            or snapshot.get("outbound_enabled") is not False):
        raise ValueError("unsafe_buyer_qualification_evidence")
    rows = snapshot.get("targets")
    if not isinstance(rows, list) or len(rows) > 500:
        raise ValueError("unbounded_buyer_research_cohort")
    _stamp(snapshot.get("generated_at"), now=now)
    if previous is not None and (
        previous.get("schema_version") != SCHEMA
        or previous.get("outbound_authorized") is not False
        or previous.get("payment_authorized") is not False
        or not isinstance(previous.get("identity_decisions"), dict)
        or len(previous["identity_decisions"]) > MAX_STORED_IDENTITIES
        or not isinstance(previous.get("emitted_decisions", {}), dict)
        or len(previous.get("emitted_decisions", {})) > MAX_STORED_IDENTITIES
    ):
        raise ValueError("unsafe_previous_buyer_decision_checkpoint")

    before = previous.get("identity_decisions", {}) if previous else {}
    emitted_before = previous.get("emitted_decisions", {}) if previous else {}
    decisions: dict[str, str] = {}
    due: list[dict] = []
    # The complete, durable state is distinct from the per-cycle change delta.
    # A surfaced recommendation is not a completed task or a sent message.
    portfolio: list[dict[str, Any]] = []
    legacy_emitted: dict[str, str] = {}
    held = 0
    unchanged = 0
    materially_changed = 0
    counters: Counter[str] = Counter()
    priority_hints: dict[str, int] = {}
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid_buyer_row")
        domain = row.get("domain")
        if not isinstance(domain, str) or not DOMAIN.fullmatch(domain) or domain in seen:
            raise ValueError("duplicate_or_invalid_buyer_entity")
        seen.add(domain)
        # The qualification source normally invalidates stale demand. Also
        # fail closed here when reviewing an injected/legacy stale snapshot.
        eligible_row = row
        if snapshot.get("active_demand_source_state") not in (
                None, "CURRENT_RESEARCH_PRIORITIES"):
            eligible_row = {**row, "active_demand_sector_research_fit": {
                "state": "NO_SECTOR_GAP_MATCH_OBSERVED",
                "first_party_matching_sector_names": [],
                "sample_corridors_for_research": [],
                "market_or_zip_coverage_verified": False,
            }}
        recommended = classify(eligible_row)
        if recommended is None:
            held += 1
            portfolio.append({"domain": domain, "recommended_action": None,
                              "existing_owner": None, "research_priority": 0,
                              "decision_state": "POLICY_HOLD",
                              "task_dispatched": False})
            continue
        if recommended not in SAFE_STATES:
            raise ValueError("unknown_buyer_decision")
        fit = eligible_row.get("active_demand_sector_research_fit")
        fit = fit if isinstance(fit, dict) else {}
        due_diligence = row.get("first_party_due_diligence")
        due_diligence = due_diligence if isinstance(due_diligence, dict) else {}
        semantic = {
            "next_action": recommended,
            "tier": row.get("tier"),
            "contact": row.get("contact_history_state"),
            "fit": fit.get("state"),
            "sectors": fit.get("first_party_matching_sector_names", []),
            "corridors": fit.get("sample_corridors_for_research", []),
            "due_freshness": due_diligence.get("freshness"),
            "due_state": due_diligence.get("state"),
            "site_role_flags": row.get("site_evidence_flags"),
            "evidence_gaps": row.get("missing_evidence"),
            "role_review": row.get("buyer_relationship_role_review"),
            "contact_next_action": row.get("contact_history_next_action"),
            "last_inbound_at": row.get("contact_history_last_inbound_at"),
            "queue_status": row.get("queue_status"),
        }
        stamp = digest(semantic)
        # Upgrade the original v1 fingerprints in place. Enriching the policy
        # with reply timestamps must not re-surface every prior task once.
        legacy_stamp = digest({
            "next_action": recommended,
            "tier": row.get("tier"),
            "contact": row.get("contact_history_state"),
            "fit": fit.get("state"),
            "sectors": fit.get("first_party_matching_sector_names", []),
            "corridors": fit.get("sample_corridors_for_research", []),
            "due_freshness": due_diligence.get("freshness"),
            "due_observed": due_diligence.get("observed_at"),
        })
        # Read-only source availability and historical outbound timestamps
        # are not new buyer intent. Recognize the short-lived enriched v1
        # fingerprint to avoid another migration-only reissue.
        enriched_stamp = digest({
            **semantic,
            "last_outbound_at": row.get("contact_history_last_outbound_at"),
            "contact_source_fresh": row.get("contact_history_source_fresh"),
        })
        if emitted_before.get(domain) in (legacy_stamp, enriched_stamp):
            legacy_emitted[domain] = stamp
        decisions[domain] = stamp
        counters[recommended] += 1
        # Stable prioritisation for the original direct-site researcher.
        # Hints neither create work nor bypass eligibility/cooldowns.
        if recommended in {
            "VERIFY_FIRST_PARTY_SITE", "VERIFY_COMPANY_BUYER_ROLE",
            "VERIFY_BUYER_GEO_AND_PRODUCT_REQUIREMENTS",
            "RESEARCH_COMPANY_ROLE",
        }:
            priority_hints[domain] = _priority(eligible_row, recommended)
        if before.get(domain) not in (stamp, legacy_stamp, enriched_stamp):
            materially_changed += 1
        was_surfaced = (emitted_before.get(domain) == stamp
                         or domain in legacy_emitted)
        portfolio.append({
            "domain": domain, "recommended_action": recommended,
            "existing_owner": OWNER[recommended],
            "research_priority": _priority(eligible_row, recommended),
            "source_evidence_fingerprint": stamp,
            "decision_state": (
                "SURFACED_AWAITING_OWNER_EVIDENCE" if was_surfaced
                else "QUEUED_FOR_BOUNDED_REVIEW"),
            "task_dispatched": False,
        })
        if was_surfaced:
            unchanged += 1
            continue
        due.append({
            "domain": domain, "recommended_action": recommended,
            "existing_owner": OWNER[recommended],
            "research_priority": _priority(eligible_row, recommended),
            "source_evidence_fingerprint": stamp,
            "first_party_sector_match": fit.get("state") == "FIRST_PARTY_SECTOR_RESEARCH_FIT",
            "market_coverage_verified": False,
            "buyer_acceptance_verified": False,
            "outbound_authorized": False,
            "task_dispatched": False,
        })
    due.sort(key=lambda x: (-x["research_priority"], x["domain"]))
    selected = due[:MAX_OUTPUT_TASKS]
    recorded = {k:v for k,v in emitted_before.items() if decisions.get(k) == v}
    recorded.update(legacy_emitted)
    recorded.update({x["domain"]:x["source_evidence_fingerprint"] for x in selected})
    surfaced = {x["domain"] for x in selected}
    for item in portfolio:
        if item["domain"] in surfaced:
            item["decision_state"] = "SURFACED_TO_EXISTING_OWNER_REVIEW"
    portfolio.sort(key=lambda x: (-x["research_priority"], x["domain"]))
    last_refresh = refresh_attempt or {}
    result = {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "generated_at": now.isoformat(),
        "source_generated_at": snapshot["generated_at"],
        "source_snapshot_digest": digest(decisions),
        "current_candidates": len(rows),
        "recommendation_types": dict(sorted(counters.items())),
        "research_priority_hints": dict(sorted(priority_hints.items())),
        "research_priority_hints_are_not_research_authority": True,
        "materially_changed_recommendations": materially_changed,
        "recommendations_due_or_not_yet_surfaced": len(due),
        "unchanged_recommendations_suppressed": unchanged,
        "policy_held_count": held,
        "priority_worklist": selected,
        "portfolio_next_actions": portfolio,
        "portfolio_next_actions_are_review_not_execution": True,
        "worklist_truncated_count": max(0, len(due) - MAX_OUTPUT_TASKS),
        "source_refresh": last_refresh,
        "astra_owner": "existing_astra_dispatcher_advisory_only",
        "owner_timers_preserved": True,
        "outbound_authorized": False, "payment_authorized": False,
        "buyer_admission_authorized": False, "database_writes": False,
        "external_execution_performed": False,
        "individual_recommendations_dispatched": False,
    }
    checkpoint = {
        "schema_version": SCHEMA, "evaluated_at": now.isoformat(),
        "source_snapshot_digest": result["source_snapshot_digest"],
        "identity_decisions": decisions,
        "emitted_decisions": recorded,
        "last_refresh_attempt_at": last_refresh.get("at") or (previous or {}).get("last_refresh_attempt_at"),
        "outbound_authorized": False,
        "payment_authorized": False,
        "database_writes": False,
    }
    return result, checkpoint


def _atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("buyer_brain_destination_symlink_held")
    with NamedTemporaryFile("w", dir=path.parent, prefix=".buyer_brain_",
                            suffix=".tmp", delete=False, encoding="utf-8") as f:
        name = f.name
        os.fchmod(f.fileno(), 0o600)
        json.dump(payload, f, sort_keys=True, separators=(",", ":"))
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    try:
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def run_team_brain(root: Path, *, now: datetime | None = None,
                   allow_internal_refresh: bool = True) -> dict:
    """Run from the original five-minute team owner; no separate daemon."""
    now = now or datetime.now(timezone.utc)
    previous = None
    if (root / STATE).is_file():
        previous = _read(root, STATE, max_bytes=200_000)
    refresh = {"status": "NOT_DUE", "existing_job": "build_buyer_qualification_actions",
               "executed": False}
    snapshot = _read(root, QUAL)
    age = _stamp(snapshot.get("generated_at"), now=now)
    last_time = None
    if previous and previous.get("last_refresh_attempt_at"):
        try:
            last_time = datetime.fromisoformat(previous["last_refresh_attempt_at"]).timestamp()
        except (ValueError, TypeError):
            pass
    if (allow_internal_refresh and age >= REFRESH_AFTER
            and (last_time is None or now.timestamp() - last_time >= REFRESH_COOLDOWN)):
        refresh.update(status="EXISTING_INTERNAL_REFRESH_FAILED",
                       at=now.isoformat(), executed=True)
        cmd = [str(root / ".venv/bin/python"), "-B",
               str(root / "scripts/build_buyer_qualification_actions.py"), "--write"]
        try:
            proc = subprocess.run(cmd, cwd=root, capture_output=True,
                                  text=True, timeout=35, check=False)
            if proc.returncode == 0:
                candidate = _read(root, QUAL)
                _stamp(candidate.get("generated_at"), now=now, max_age=90)
                snapshot = candidate
                refresh["status"] = "EXISTING_QUALIFICATION_REFRESH_SUCCEEDED"
            else:
                refresh["failure_class"] = "EXISTING_OWNER_RETURNED_NONZERO"
        except (OSError, subprocess.TimeoutExpired, ValueError):
            refresh["failure_class"] = "EXISTING_OWNER_UNAVAILABLE"
    result, checkpoint = review(snapshot, previous, now=now, refresh_attempt=refresh)
    _atomic(root / REPORT, result)
    _atomic(root / STATE, checkpoint)
    return {
        "status": "EXISTING_BUYER_TEAM_BRAIN_EVALUATED",
        "current_candidates": result["current_candidates"],
        "new_evidence_decisions": result["materially_changed_recommendations"],
        "newly_surfaced_recommendations": len(result["priority_worklist"]),
        "awaiting_next_research_queue_cycle": result["worklist_truncated_count"],
        "repeat_decisions_suppressed": result["unchanged_recommendations_suppressed"],
        "owner_review_recommendations_surfaced": len(result["priority_worklist"]),
        "existing_qualification_refresh": refresh["status"],
        "external_execution_performed": False,
        "outbound_authorized": False, "database_writes": False,
    }
