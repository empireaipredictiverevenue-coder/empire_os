"""Deterministic, read-only buyer recovery triage for the existing scout cycle.

No new agent, timer, email transport, contact binding, approval, or DB write.
The private packet is a research/evidence workload, never a send list.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

from empire_os.buyer_deferred_enrichment import (
    _parked_without_new_evidence,
    _parse,
    _priority,
    _recovery_lane,
    _recovery_prerequisite,
)
from empire_os.buyer_discovery import looks_like_person_name


SCHEMA = "empire.buyer_recovery_action_desk.v1"
SOURCE = Path("runtime/hunter/buyer_deferred_enrichment.json")
DESTINATION = Path(
    "runtime/buyer_network_intelligence/buyer_recovery_action_desk_latest.json"
)
MAX_SOURCE_BYTES = 8_000_000
MAX_SOURCE_RECORDS = 20_000
MAX_REVIEW_ITEMS = 25
MIN_PRIORITY = 80

# Verified first-party identity conflict, scoped to the EXACT bad source
# company-label / website pair. Do not reassign directory executives or
# replace a canonical prospect website from a search result.
KNOWN_COMPANY_WEBSITE_CONFLICTS = {
    (
        "sean regan law | personal injury & car accident lawyer",
        "lawful.com",
    ): {
        "case": "SEAN_REGAN_VS_LAWFUL_20261014",
        "claimed_firm_source": "https://seanreganlaw.com/",
        "distinct_directory_source": "https://lawful.com/about",
    },
}


def _known_identity_conflict(business_name: Any, website: Any) -> dict[str, str] | None:
    try:
        parsed = urlsplit(str(website or "").strip())
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or parsed.username or parsed.password:
        return None
    domain = (parsed.hostname or "").casefold().removeprefix("www.")
    label = " ".join(str(business_name or "").casefold().strip().split())
    return KNOWN_COMPANY_WEBSITE_CONFLICTS.get((label, domain))

NEXT_EVIDENCE = {
    "site_unavailable": "Obtain a current first-party company website",
    "site_timeout": "Verify the same company website is reachable",
    "network_probe_budget_exhausted": "Await bounded source-collection capacity",
    "no_decision_maker": "Verify a named decision-maker on the company website",
    "decision_maker_missing": "Verify a named decision-maker on the company website",
    "no_bound_contact": "Verify a person-bound company contact from first-party evidence",
    "no_contact_evidence": "Verify a person-bound company contact from first-party evidence",
    "contact_not_verified": "Independently verify the exact person-bound contact",
    "target_contact_not_verified": "Verify the exact named person-to-company email binding",
    "target_identity_mismatch": "Resolve person/company identity mismatch before contact",
    "outreach_not_ready": "Recheck first-party identity and commercial outreach eligibility",
    "contact_not_ready": "Verify first-party contact evidence before founder review",
    "role_address_only": "Verify a named person rather than a role inbox",
    "decision_score_below_floor": "Verify real decision authority before escalation",
}


class RecoveryDeskError(ValueError):
    pass


def _read_source(path: Path) -> tuple[dict[str, Any], str]:
    if path.is_symlink() or not path.is_file():
        raise RecoveryDeskError("missing_or_symlinked_queue")
    meta = path.stat()
    if not stat.S_ISREG(meta.st_mode) or not 0 < meta.st_size <= MAX_SOURCE_BYTES:
        raise RecoveryDeskError("unsafe_queue_size_or_type")
    raw = path.read_bytes()
    if len(raw) > MAX_SOURCE_BYTES:
        raise RecoveryDeskError("oversize_queue")
    try:
        data = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise RecoveryDeskError("invalid_queue_json") from exc
    if not isinstance(data, dict) or len(data) > MAX_SOURCE_RECORDS:
        raise RecoveryDeskError("invalid_queue_shape_or_count")
    if any(not isinstance(v, dict) for v in data.values()):
        raise RecoveryDeskError("invalid_queue_record")
    return data, sha256(raw).hexdigest()


def _same_host_evidence(value: Any, website: Any) -> str | None:
    """A same-host reference to review, NOT validated person-email evidence."""
    try:
        url = urlsplit(str(value or "").strip())
        source = urlsplit(str(website or "").strip())
    except ValueError:
        return None
    if url.scheme not in {"https", "http"} or source.scheme not in {"https", "http"}:
        return None
    if url.username or url.password or source.username or source.password:
        return None
    left = (url.hostname or "").casefold().removeprefix("www.")
    right = (source.hostname or "").casefold().removeprefix("www.")
    if not left or "." not in left or left != right:
        return None
    if len(str(value)) > 600:
        return None
    return urlunsplit((url.scheme, url.netloc, url.path or "/", "", ""))


def _rank_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    # Person-bound commercial discovery ahead of blind, repeated crawl.
    return (
        # A documented wrong-company linkage is not a prospecting work item.
        row["stage"] == "IDENTITY_CONFLICT_HOLD",
        # Existing, product-scoped enterprise evidence ahead of broad
        # unfunded/regulated-sector research; never proof of buyer demand.
        row["product_hypothesis_count"] == 0,
        row["stage"] != "NAMED_PERSON_EVIDENCE_RECOVERY",
        row["stage"] != "PERSON_CONTACT_RESEARCH",
        -row["person_evidence_count"],
        -row["priority_score"],
        row["attempts"],
        row["company_domain"],
        row["prospect_id"],
    )


def make_packet(
    queue: Mapping[str, Any],
    *,
    source_sha256: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    summary: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    prerequisites: Counter[str] = Counter()
    high: list[dict[str, Any]] = []
    domain_members: Counter[str] = Counter()

    for key, item in queue.items():
        if not isinstance(key, str) or not isinstance(item, dict):
            raise RecoveryDeskError("invalid_queue_record_identity")
        status = str(item.get("status") or "")
        summary["total"] += 1
        summary["status_" + (status if status in {"pending", "deferred", "running", "resolved"} else "unknown")] += 1
        if status not in {"pending", "deferred"}:
            continue
        summary["unresolved"] += 1
        lane = _recovery_lane(item)
        summary["lane_" + lane] += 1
        identity_conflict = _known_identity_conflict(
            item.get("business_name"), item.get("website")
        )
        parked = _parked_without_new_evidence(item) or identity_conflict is not None
        if identity_conflict is not None:
            summary["verified_identity_conflicts_held"] += 1
        summary["parked" if parked else "eligible_after_backoff"] += 1
        priority = _priority(item.get("priority_score"))
        reason = str(item.get("reason") or "")
        reasons[reason if reason in NEXT_EVIDENCE else "other"] += 1
        prerequisite = str(
            item.get("next_prerequisite") or _recovery_prerequisite(reason)
        )[:90]
        prerequisites[prerequisite] += 1
        retry_at = _parse(item.get("next_retry_at"))
        if not parked and (retry_at is None or retry_at <= current):
            summary["due_now"] += 1
        if priority < MIN_PRIORITY:
            continue
        summary["high_priority"] += 1
        summary["high_priority_parked" if parked else "high_priority_eligible"] += 1

        website = str(item.get("website") or "").strip()
        try:
            parsed = urlsplit(website)
        except ValueError:
            parsed = urlsplit("")
        domain = (parsed.hostname or "").casefold().removeprefix("www.")
        if not domain or "." not in domain or parsed.scheme not in {"http", "https"}:
            domain = ""
        if domain:
            domain_members[domain] += 1
        people = []
        for person in item.get("target_people") or []:
            if not isinstance(person, dict):
                continue
            name = str(person.get("name") or "").strip()
            title = str(person.get("title") or "").strip()
            if not looks_like_person_name(name) or not title:
                continue
            source_url = _same_host_evidence(
                person.get("evidence_url"), website
            )
            if source_url:
                people.append({
                    "name": name[:100], "title": title[:100],
                    "first_party_url_to_reverify": source_url,
                    "contact_verified": False,
                })
        routes = {
            str(r.get("channel") or "").lower()
            for r in (item.get("company_contact_routes") or [])
            if isinstance(r, dict) and r.get("verified") is True
            and str(r.get("channel") or "") in {"email", "webform", "voice"}
        }
        if identity_conflict is not None:
            # Contacts, titles and routes are from a distinct organization,
            # never something to "verify" as the named target firm.
            people = []
            routes = set()
        stage = (
            "IDENTITY_CONFLICT_HOLD" if identity_conflict is not None
            else "NAMED_PERSON_EVIDENCE_RECOVERY"
            if lane == "hot_contact_recovery" and people
            else "PERSON_CONTACT_RESEARCH" if lane == "hot_contact_recovery"
            else "SOURCE_CHANGE_REQUIRED"
        )
        prospect_id = str(item.get("prospect_id") or key).strip()
        high.append({
            "prospect_id": prospect_id[:120],
            "company_name": str(item.get("business_name") or "")[:140],
            "company_domain": domain,
            "priority_score": priority,
            "recovery_lane": lane,
            "stage": stage,
            "attempts": max(0, int(item.get("attempts") or 0)),
            "parked_until_new_evidence": parked,
            "next_retry_at": retry_at.isoformat() if retry_at and not parked else None,
            "reason": reason[:90],
            "missing_evidence": (
                "Resolve exact company/website mismatch before any person evidence"
                if identity_conflict is not None else prerequisite
            ),
            "next_evidence_action": (
                "Reconcile original canonical company identity; never reuse directory contacts"
                if identity_conflict is not None else NEXT_EVIDENCE.get(
                    reason, "Verify company and person-bound first-party evidence"
                )
            ),
            "identity_conflict_verified": identity_conflict is not None,
            "identity_conflict_evidence": identity_conflict,
            "person_evidence_count": len(people),
            "person_evidence_to_reverify": people[:4],
            "verified_company_route_types": sorted(routes),
            "offer_key": str(item.get("offer_key") or "")[:100] or None,
            "product_hypothesis_count": len([
                code for code in (item.get("target_product_codes") or [])
                if isinstance(code, str) and code.strip()
            ][:6]),
            "first_party_contact_verified": False,
            "contact_history_verified": False,
            "suppression_verified_for_sending": False,
            "buyer_demand_verified": False,
            "founder_review_required": True,
            "outbound_authorized": False,
            "activation_authority": "NONE",
        })
    high.sort(key=_rank_key)
    for row in high:
        row["other_same_domain_records"] = max(
            0, domain_members[row["company_domain"]] - 1
        ) if row["company_domain"] else 0

    # Zero is a real observation, not missing telemetry. Keep the main
    # counters explicit when all candidates are on backoff or evidence hold.
    for key in (
        "total", "unresolved", "due_now", "parked",
        "eligible_after_backoff", "verified_identity_conflicts_held", "high_priority",
        "high_priority_parked", "high_priority_eligible",
        "status_pending", "status_deferred", "status_running",
        "status_resolved",
    ):
        summary.setdefault(key, 0)

    return {
        "schema_version": SCHEMA,
        "generated_at": current.isoformat(),
        "mode": "OBSERVE",
        "execution_authority": "NONE",
        "source": str(SOURCE),
        "source_sha256": source_sha256,
        "counts": dict(sorted(summary.items())),
        "recovery_reason_counts": dict(sorted(reasons.items())),
        "missing_prerequisite_counts": dict(sorted(prerequisites.items())),
        "high_priority_total": len(high),
        "review_packet_count": min(MAX_REVIEW_ITEMS, len(high)),
        "review_packet_truncated": len(high) > MAX_REVIEW_ITEMS,
        "packets": high[:MAX_REVIEW_ITEMS],
        "required_next_gates": [
            "independent_first_party_person_company_binding",
            "live_outreach_history_and_exact_suppression",
            "real_buyer_demand_and_product_scope",
            "founder_approved_first_touch",
            "binding_commercial_terms_and_payment_separately_approved",
        ],
        "owned_mailbox_live_verified": False,
        "automatic_email_drafts_created": False,
        "outbound_sent": False,
        "db_write": False,
        "traffic_activation": False,
        "payment_action": False,
        "human_review_required": True,
    }


def plan(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    path = root / SOURCE
    queued, digest = _read_source(path)
    result = make_packet(queued, source_sha256=digest)
    _, after_digest = _read_source(path)
    if after_digest != digest:
        raise RecoveryDeskError("queue_changed_during_analysis")
    return result


def save_private(root: Path, report: Mapping[str, Any]) -> Path:
    dest = Path(root).resolve() / DESTINATION
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink() or (dest.exists() and not dest.is_file()):
        raise RecoveryDeskError("unsafe_report_destination")
    data = json.dumps(report, sort_keys=True, indent=2) + "\n"
    # Never create a transient world-readable review packet.
    fd, name = tempfile.mkstemp(dir=dest.parent, prefix=".buyer-recovery-", suffix=".tmp")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, dest)
        os.chmod(dest, 0o600)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return dest
