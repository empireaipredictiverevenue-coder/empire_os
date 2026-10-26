"""Buyer qualification gap continuation inside original five-minute Team owner.

This records what proof is missing, whose existing queue owns the next review,
and whether a previously surfaced review became materially different.
It never infers ZIP capacity, contacts a prospect, or dispatches a worker.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from empire_os.buyer_qualification_evidence_bridge import load_registry, match_partner_buyboxes
from empire_os.buyer_partner_buybox_reply_tracker import read_original_gmail_metadata, review_partner_replies
import json
import os
import re

BASE = Path("runtime/buyer_network_intelligence")
QUALIFICATION = BASE / "founder_qualification_actions_latest.json"
REPORT = BASE / "qualification_gap_loop_latest.json"
MEMORY = BASE / "qualification_gap_loop_state_latest.json"
SCHEMA = "empire.buyer_acquisition.qualification_gap_loop.v1"
DOMAIN = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")
MAX_AGE = 3 * 3600
MAX_ROWS = 500
MAX_SURFACED = 20


class GapAction(str, Enum):
    REVIEW_CONVERSATION_REQUIREMENTS = "REVIEW_CONVERSATION_REQUIREMENTS"
    REVIEW_REPLY_AND_BUYER_CRITERIA = "REVIEW_REPLY_AND_BUYER_CRITERIA"
    WAIT_FOR_EXTERNAL_BUYER_EVIDENCE = "WAIT_FOR_EXTERNAL_BUYER_EVIDENCE"
    VERIFY_ACCEPTED_GEO_AND_INVENTORY = "VERIFY_ACCEPTED_GEO_AND_INVENTORY"
    VERIFY_FIRST_PARTY_ROLE = "VERIFY_FIRST_PARTY_ROLE"
    VERIFY_DECISION_MAKER_CONTACT = "VERIFY_DECISION_MAKER_CONTACT"
    REFRESH_STALE_FIRST_PARTY_EVIDENCE = "REFRESH_STALE_FIRST_PARTY_EVIDENCE"
    POLICY_HOLD = "POLICY_HOLD"


ROUTES = {
    GapAction.REVIEW_CONVERSATION_REQUIREMENTS: "existing_founder_commercial_review",
    GapAction.REVIEW_REPLY_AND_BUYER_CRITERIA: "existing_buyer_gmail_evidence_owner",
    GapAction.WAIT_FOR_EXTERNAL_BUYER_EVIDENCE: "existing_buyer_gmail_evidence_owner",
    GapAction.VERIFY_ACCEPTED_GEO_AND_INVENTORY: "existing_buyer_network_research_owner",
    GapAction.VERIFY_FIRST_PARTY_ROLE: "existing_buyer_network_research_owner",
    GapAction.VERIFY_DECISION_MAKER_CONTACT: "existing_buyer_network_contact_intelligence_owner",
    GapAction.REFRESH_STALE_FIRST_PARTY_EVIDENCE: "existing_buyer_network_due_diligence_owner",
    GapAction.POLICY_HOLD: None,
}
LIVE = frozenset(("EXISTING_CONVERSATION", "WORKSPACE_RECIPROCAL_THREAD_OBSERVED",
                  "FOUNDER_FORM_SUBMITTED"))
PRIOR = frozenset(("ALREADY_CONTACTED", "WORKSPACE_SENT_ALREADY_CONTACTED",
                   "FOUNDER_REVIEWED_PRIOR_GMAIL_THREAD"))
HOLD_CONTACT = frozenset(("DO_NOT_PURSUE", "DELIVERY_HOLD",
                          "EXISTING_CONVERSATION_PARTIAL_BOUNCE", "SOURCE_UNAVAILABLE"))
GEO_REQUIREMENTS = (
    "buyer_accepted_sector", "buyer_accepted_states_or_zips",
    "buyer_operating_hours", "accepted_lead_or_call_format",
    "consent_routing_attribution_requirements",
)


def _hash(obj: Any) -> str:
    return sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _read(root: Path, filename: Path, *, max_bytes: int = 3_000_000) -> dict:
    target = root / filename
    if target.is_symlink() or not target.is_file() or not 30 <= target.stat().st_size <= max_bytes:
        raise ValueError("missing_or_unsafe_qualification_gap_source")
    data = json.loads(target.read_text(encoding="utf8"))
    if not isinstance(data, dict):
        raise ValueError("invalid_qualification_gap_object")
    return data


def _time(text: Any) -> datetime:
    try:
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError("timestamp_missing_timezone")
        return result.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("invalid_qualification_source_time") from exc


def _valid_snapshot(src: dict, now: datetime) -> list[dict]:
    if (src.get("schema_version") != "empire.buyer_qualification_actions.v1"
            or src.get("mode") != "OBSERVE"
            or src.get("execution_authority") != "none"
            or src.get("outbound_sent") is not False
            or src.get("outbound_enabled") is not False
            or not isinstance(src.get("targets"), list)
            or len(src["targets"]) > MAX_ROWS
            or src.get("shortlisted_count") != len(src["targets"])):
        raise ValueError("unsafe_qualification_gap_input")
    age = (now - _time(src.get("generated_at"))).total_seconds()
    if age < -300 or age > MAX_AGE:
        raise ValueError("qualification_evidence_not_current")
    seen = set()
    for row in src["targets"]:
        if not isinstance(row, dict) or not isinstance(row.get("domain"), str):
            raise ValueError("unrecognised_company_row")
        domain = row["domain"]
        if not DOMAIN.fullmatch(domain) or domain in seen:
            raise ValueError("duplicate_or_invalid_company")
        seen.add(domain)
    return src["targets"]


def classify(row: dict, *, demand_current: bool) -> tuple[GapAction, list[str], bool]:
    contact = str(row.get("contact_history_state") or "")
    fit = row.get("active_demand_sector_research_fit")
    fit = fit if isinstance(fit, dict) else {}
    matched = demand_current and fit.get("state") == "FIRST_PARTY_SECTOR_RESEARCH_FIT"
    current_site = (row.get("first_party_due_diligence") or {}).get("freshness") == "CURRENT"
    held = (row.get("manual_hold_reason") is not None
            or row.get("automated_hold_reason") is not None
            or contact in HOLD_CONTACT
            or row.get("outbound_authorized") is True)
    gaps = list(GEO_REQUIREMENTS) if matched else ["first_party_buyer_role_and_sector"]
    if not current_site:
        gaps.insert(0, "current_first_party_site_evidence")
    if held:
        return GapAction.POLICY_HOLD, gaps, matched
    if contact in LIVE:
        return GapAction.REVIEW_CONVERSATION_REQUIREMENTS, gaps, matched
    if contact in PRIOR:
        # A genuinely newer inbound event in the existing canonical contact
        # evidence reopens the existing relationship. Never manufacture reply
        # activity from an outbound timestamp or an unsourced status change.
        try:
            inbound = _time(row.get("contact_history_last_inbound_at"))
            outbound = _time(row.get("contact_history_last_outbound_at"))
            if inbound > outbound:
                return GapAction.REVIEW_REPLY_AND_BUYER_CRITERIA, gaps, matched
        except ValueError:
            pass
        # Previously contacted is not a licence to send another introduction.
        return GapAction.WAIT_FOR_EXTERNAL_BUYER_EVIDENCE, gaps, matched
    if not current_site:
        return GapAction.REFRESH_STALE_FIRST_PARTY_EVIDENCE, gaps, matched
    if matched:
        return GapAction.VERIFY_ACCEPTED_GEO_AND_INVENTORY, gaps, matched
    if row.get("site_corroborated_buyer_role") is not True:
        return GapAction.VERIFY_FIRST_PARTY_ROLE, gaps, matched
    return GapAction.VERIFY_DECISION_MAKER_CONTACT, gaps, matched


def priority(action: GapAction, matched: bool, row: dict) -> int:
    base = {
        GapAction.REVIEW_CONVERSATION_REQUIREMENTS: 110,
        GapAction.REVIEW_REPLY_AND_BUYER_CRITERIA: 100,
        GapAction.VERIFY_ACCEPTED_GEO_AND_INVENTORY: 81,
        GapAction.WAIT_FOR_EXTERNAL_BUYER_EVIDENCE: 38,
        GapAction.VERIFY_DECISION_MAKER_CONTACT: 62,
        GapAction.VERIFY_FIRST_PARTY_ROLE: 43,
        GapAction.REFRESH_STALE_FIRST_PARTY_EVIDENCE: 60,
        GapAction.POLICY_HOLD: 0,
    }[action]
    if matched:
        base += 18
    if row.get("tier") == "FOUNDER_REVIEW_ONLY":
        base += 8
    return min(150, base)


def evaluate(src: dict, previous: dict | None, *, now: datetime,
             buyer_partner_context: dict[str, dict] | None = None,
             partner_source_state: str = "SOURCE_NOT_LOADED") -> tuple[dict, dict]:
    rows = _valid_snapshot(src, now)
    if previous is not None and (
            previous.get("schema_version") != SCHEMA
            or previous.get("outbound_authorized") is not False
            or previous.get("payment_authorized") is not False
            or not isinstance(previous.get("surfaced"), dict)
            or len(previous["surfaced"]) > MAX_ROWS):
        raise ValueError("unsafe_gap_memory_checkpoint")
    old = previous.get("surfaced", {}) if previous else {}
    demand_current = src.get("active_demand_source_state") == "CURRENT_RESEARCH_PRIORITIES"
    portfolio = []
    changed = []
    fresh = {}
    counters = Counter()
    for row in rows:
        domain = row["domain"]
        action, gaps, matched = classify(row, demand_current=demand_current)
        evidence_gaps = row.get("missing_evidence")
        evidence_gaps = (sorted(set(evidence_gaps))
                         if isinstance(evidence_gaps, list)
                         and all(isinstance(v, str) and len(v) <= 80 for v in evidence_gaps)
                         else [])
        gaps.extend(g for g in evidence_gaps if g not in gaps)
        partner = (buyer_partner_context or {}).get(domain)
        partner = partner if isinstance(partner, dict) else {}
        # Existing buyer requests are context to resolve, not verified terms.
        extra = partner.get("requirements_requested_not_verified")
        extra = (extra if isinstance(extra, list) and
                 all(isinstance(v, str) and len(v) <= 100 for v in extra) else [])
        gaps.extend(g for g in extra if g not in gaps)
        # Deliberately exclude refreshed timestamps and the snapshot time.
        # An inbound buyer response or a new requirement changes the fingerprint.
        semantic = {
            "action": action.value,
            "gaps": gaps,
            "contact_state": row.get("contact_history_state"),
            "last_inbound": row.get("contact_history_last_inbound_at"),
            "contact_next_action": row.get("contact_history_next_action"),
            "sector_fit": matched,
            "sectors": ((row.get("active_demand_sector_research_fit") or {})
                        .get("first_party_matching_sector_names", []) if matched else []),
            "corridors": ((row.get("active_demand_sector_research_fit") or {})
                          .get("sample_corridors_for_research", []) if matched else []),
            "site_role": row.get("site_corroborated_buyer_role"),
            "first_party_due_diligence_state": (row.get("first_party_due_diligence") or {}).get("state"),
            "partner_buybox_evidence": {
                "entity": partner.get("entity_key"),
                "pending": extra,
                "previous_full_request_known": partner.get("full_request_already_known") is True,
                "geo": partner.get("geography_state"),
            } if partner else None,
            "manual_hold": row.get("manual_hold_reason"),
            "automated_hold": row.get("automated_hold_reason"),
        }
        signature = _hash(semantic)
        fresh[domain] = signature
        changed_evidence = old.get(domain) != signature
        state = ("POLICY_HELD" if action == GapAction.POLICY_HOLD
                 else "WAITING_EXTERNAL_EVIDENCE" if action == GapAction.WAIT_FOR_EXTERNAL_BUYER_EVIDENCE
                 else "NEW_OR_CHANGED_OWNER_REVIEW" if changed_evidence
                 else "PREVIOUSLY_SURFACED_UNCHANGED")
        candidate = {
            "domain": domain,
            "action": action.value,
            "owner": ROUTES[action],
            "priority": priority(action, matched, row),
            "state": state,
            "first_party_sector_match": matched,
            "matched_sectors": semantic["sectors"],
            "research_corridors_not_accepted_capacity": semantic["corridors"],
            "missing_requirements": gaps,
            "next_proof_to_check": (gaps[0] if gaps else "independent_buyer_acceptance"),
            "decision_reason": (
                "Suppression, delivery hold, or other explicit safety hold" if action == GapAction.POLICY_HOLD
                else "Existing conversation requires factual buying criteria before a proposal" if action == GapAction.REVIEW_CONVERSATION_REQUIREMENTS
                else "New inbound reply observed after prior send; review buyer criteria in the existing thread" if action == GapAction.REVIEW_REPLY_AND_BUYER_CRITERIA
                else "Previously contacted: wait for or verify a real reply, never automatically resend" if action == GapAction.WAIT_FOR_EXTERNAL_BUYER_EVIDENCE
                else "Fresh first-party sector fit but no accepted states, ZIPs, hours, or format" if action == GapAction.VERIFY_ACCEPTED_GEO_AND_INVENTORY
                else "First-party evidence needs refreshing at the existing owner" if action == GapAction.REFRESH_STALE_FIRST_PARTY_EVIDENCE
                else "Research buyer identity and role from legitimate first-party evidence"),
            "evidence_fingerprint": signature,
            "contact_history_state": row.get("contact_history_state"),
            "buyer_accepted_geo_verified": False,
            "buyer_commercial_acceptance_verified": False,
            "action_executed": False,
            "new_intro_authorized": False,
            "original_partner_requirements_evidence": partner or None,
            "founder_outbound_buyer_requirements_repeat_blocked":
                partner.get("full_request_already_known") is True,
        }
        portfolio.append(candidate)
        counters[state] += 1
        if (changed_evidence and action != GapAction.POLICY_HOLD
                and action != GapAction.WAIT_FOR_EXTERNAL_BUYER_EVIDENCE):
            changed.append(candidate)
    # Bounded delta presentation while keeping a durable view of the full cohort.
    changed.sort(key=lambda r: (-r["priority"], r["domain"]))
    portfolio.sort(key=lambda r: (-r["priority"], r["domain"]))
    selection = changed[:MAX_SURFACED]
    result = {
        "schema_version": SCHEMA,
        "generated_at": now.isoformat(),
        "source_generated_at": src["generated_at"],
        "source_fingerprint": _hash({"rows": fresh}),
        "mode": "OBSERVE",
        "companies_evaluated": len(rows),
        "first_party_sector_matches": sum(p["first_party_sector_match"] for p in portfolio),
        "live_relationships_with_first_party_match": sum(
            p["first_party_sector_match"] and p["contact_history_state"] in LIVE for p in portfolio),
        "prior_contacts_with_first_party_match": sum(
            p["first_party_sector_match"] and p["contact_history_state"] in PRIOR for p in portfolio),
        "partner_requirement_registry_source_state": partner_source_state,
        "linked_partner_requirement_records": sum(
            p["original_partner_requirements_evidence"] is not None for p in portfolio),
        "previous_partner_buybox_requests_known": sum(
            p["founder_outbound_buyer_requirements_repeat_blocked"] for p in portfolio),
        "independently_verified_buyer_coverage": 0,
        "pilot_qualification_verified": 0,
        "open_geo_verification": sum(p["first_party_sector_match"]
                                     and not p["buyer_accepted_geo_verified"] for p in portfolio),
        "decision_states": dict(sorted(counters.items())),
        "portfolio": portfolio,
        "newly_surfaced_reviews": selection,
        "not_yet_surfaced_changed_reviews": max(0, len(changed) - len(selection)),
        "duplicate_work_suppressed": sum(
            p["state"] == "PREVIOUSLY_SURFACED_UNCHANGED" for p in portfolio),
        "outbound_authorized": False,
        "payment_authorized": False,
        "database_writes": False,
        "revenue_verified": False,
        "automatic_worker_dispatch": False,
        "capacity_claims_accepted": 0,
    }
    checkpoint = {
        "schema_version": SCHEMA,
        "evaluated_at": now.isoformat(),
        "surfaced": {**{key: value for key, value in old.items()
                       if key in fresh and key not in {p["domain"] for p in selection}},
                     **{p["domain"]: p["evidence_fingerprint"] for p in selection}},
        "outbound_authorized": False,
        "payment_authorized": False,
    }
    return result, checkpoint


def _atomic(path: Path, obj: dict) -> None:
    if path.is_symlink():
        raise ValueError("unsafe_gap_destination_symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", dir=path.parent, encoding="utf8",
                            prefix=".buyer_gap_", suffix=".tmp", delete=False) as f:
        filename = f.name
        os.fchmod(f.fileno(), 0o600)
        json.dump(obj, f, sort_keys=True, separators=(",", ":"))
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    try:
        os.replace(filename, path)
    finally:
        if os.path.exists(filename):
            os.unlink(filename)


def refresh_gap_loop(root: Path, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    snapshot = _read(root, QUALIFICATION)
    previous = _read(root, MEMORY, max_bytes=220_000) if (root / MEMORY).is_file() else None
    registry, partner_state = load_registry(root, now=now)
    admissible_domains = {r["domain"] for r in snapshot.get("targets", [])
                          if isinstance(r, dict) and isinstance(r.get("domain"), str)}
    linked = match_partner_buyboxes(registry, allowed_domains=admissible_domains,
                                    source_state=partner_state)
    result, state = evaluate(snapshot, previous, now=now,
                             buyer_partner_context=linked,
                             partner_source_state=partner_state)
    source_partners = {x.get("entity_key") for x in registry.get("partner_pilot_readiness_queue", [])
                       if isinstance(x, dict) and isinstance(x.get("entity_key"), str)}
    matched_partners = {x["entity_key"] for x in linked.values()}
    result["original_partner_buyboxes_in_source"] = len(source_partners)
    result["partner_buyboxes_not_linked_to_candidate_cohort"] = len(source_partners - matched_partners)
    result["unlinked_buyboxes_automatically_admitted"] = 0
    gmail, gmail_source_state = read_original_gmail_metadata(root, now=now)
    prior_reply_ids = (previous or {}).get("partner_message_ids")
    partner_replies, updated_reply_ids = review_partner_replies(
        registry, gmail, cohort_matches=linked,
        prior_message_ids=prior_reply_ids,
        gmail_source_state=gmail_source_state)
    result["original_partner_buybox_reply_tracking"] = partner_replies
    result["partner_gmail_metadata_source_state"] = gmail_source_state
    if partner_replies["status"] == "PRIOR_MESSAGE_CHECKPOINT_INVALID":
        raise ValueError("unsafe_original_partner_reply_checkpoint")
    state["partner_message_ids"] = updated_reply_ids
    _atomic(root / REPORT, result)
    _atomic(root / MEMORY, state)
    return {
        "status": "ORIGINAL_BUYER_QUALIFICATION_GAP_LOOP_EVALUATED",
        "companies": result["companies_evaluated"],
        "sector_matches": result["first_party_sector_matches"],
        "new_reviews": len(result["newly_surfaced_reviews"]),
        "unchanged_suppressed": result["duplicate_work_suppressed"],
        "open_geo_verification": result["open_geo_verification"],
        "linked_original_buyboxes": result["linked_partner_requirement_records"],
        "unlinked_partner_buyboxes": result["partner_buyboxes_not_linked_to_candidate_cohort"],
        "repeat_full_buybox_requests_known": result["previous_partner_buybox_requests_known"],
        "partner_registry_state": partner_state,
        "partner_reply_source_state": gmail_source_state,
        "partner_reply_changes_to_review": partner_replies.get("changed_inbound_message_ids_review_only", 0),
        "outbound_authorized": False,
        "database_writes": False,
    }
