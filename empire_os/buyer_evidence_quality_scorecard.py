"""Cohort-safe Buyer Scout evidence quality receipt, without external authority.

Scout discoveries and pending-holding review inventory have different
denominators. Do NOT present their counts as one conversion funnel.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.buyer_claim_provenance import verified_direct_purchase_receipt
from empire_os.first_party_evidence_contract import first_party_contact_decision


OUTPUT = Path("runtime/buyer_acquisition/evidence_quality_latest.json")
SOURCES = (
    "scout_latest.json",
    "reconciliation_latest.json",
    "persistence_latest.json",
    "review_readiness_latest.json",
)


def _moment(value: Any) -> datetime | None:
    try:
        time = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return time.astimezone(timezone.utc) if time.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def build_evidence_quality_scorecard(
    scout: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
    persistence: Mapping[str, Any],
    review: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must have a timezone")
    current = current.astimezone(timezone.utc)
    rows = [r for r in (scout.get("candidates") or []) if isinstance(r, Mapping)]
    seen_domains: set[str] = set()
    counts: Counter[str] = Counter()
    role_count: Counter[str] = Counter()
    for row in rows:
        website = str(row.get("website") or "")
        domain = str(row.get("domain") or "").casefold()
        if domain:
            seen_domains.add(domain)
        role_count[str(row.get("buyer_relationship") or "unknown")] += 1
        sitemap_fetched = max(0, int(row.get("commercial_sitemap_page_fetch_count") or 0))
        if sitemap_fetched:
            counts["candidate_with_sitemap_commercial_page"] += 1
            counts["commercial_sitemap_pages_fetched"] += sitemap_fetched
        if row.get("first_party_people"):
            counts["candidate_with_named_person_record"] += 1
        if row.get("first_party_emails"):
            counts["candidate_with_published_company_email"] += 1
        if row.get("first_party_phones"):
            counts["candidate_with_published_company_phone"] += 1
        if row.get("first_party_people"):
            for person in row["first_party_people"][:10]:
                if not isinstance(person, Mapping):
                    continue
                if not all(str(person.get(k) or "").strip() for k in ("name", "title", "email")):
                    continue
                valid, _reason = first_party_contact_decision(
                    website=website,
                    source_url=person.get("url") or person.get("evidence_url"),
                    email=person.get("email"),
                    direct_publication=person.get("direct_publication"),
                )
                if valid:
                    counts["candidate_with_strict_named_person_email_binding"] += 1
                    break
        proof = verified_direct_purchase_receipt(
            {"buyer_claim_provenance": row.get("buyer_claim_provenance")},
            company_website=website, now=current,
        )
        if proof:
            counts["candidate_with_valid_direct_purchase_receipt"] += 1
        if row.get("explicit_direct_buyer_evidence") is True and not proof:
            counts["unsupported_positive_direct_buyer_flags"] += 1
        if row.get("buyer_relationship") == "mixed_role_requires_review":
            counts["candidate_with_mixed_buyer_supplier_roles"] += 1

    time_map = {
        "scout": _moment(scout.get("generated_at")),
        "reconciliation": _moment(reconciliation.get("generated_at")),
        "persistence": _moment(persistence.get("generated_at")),
        "holding_review": _moment(review.get("generated_at")),
    }
    scout_at = time_map["scout"]
    fresh = bool(
        scout_at and current >= scout_at
        and (current - scout_at).total_seconds() <= 3600
    )
    aligned = bool(
        scout_at and all(
            t and -120 <= (t - scout_at).total_seconds() <= 1200
            for t in time_map.values()
        )
    )
    count = len(rows)
    notes = [
        "Scout denominators are same-run discovered candidate domains; no estimate of true buyers.",
        "Holding review denominator is previously accumulated pending inventory and is not a Scout-cohort conversion rate.",
        "Observed people or published company emails are NOT verified person-email bindings.",
        "A first-party buying statement is not proof of completed purchase, verified budget, consent or delivery.",
    ]
    return {
        "schema_version": "empire.buyer_evidence_quality.v1",
        "mode": "OBSERVE",
        "generated_at": current.isoformat(),
        "source_generated_at": {
            name: timestamp.isoformat() if timestamp else None
            for name, timestamp in time_map.items()
        },
        "scout_receipt_fresh": fresh,
        "stage_receipts_time_aligned": aligned,
        "scout_candidate_count": count,
        "unique_scout_domain_count": len(seen_domains),
        "buyer_relationship_counts": dict(sorted(role_count.items())),
        "candidate_with_sitemap_commercial_page": counts[
            "candidate_with_sitemap_commercial_page"
        ],
        "commercial_sitemap_pages_fetched": counts[
            "commercial_sitemap_pages_fetched"
        ],
        "candidate_with_named_person_record": counts["candidate_with_named_person_record"],
        "candidate_with_published_company_email": counts["candidate_with_published_company_email"],
        "candidate_with_published_company_phone": counts["candidate_with_published_company_phone"],
        "candidate_with_strict_named_person_email_binding": counts[
            "candidate_with_strict_named_person_email_binding"
        ],
        "candidate_with_valid_direct_purchase_receipt": counts[
            "candidate_with_valid_direct_purchase_receipt"
        ],
        "unsupported_positive_direct_buyer_flags": counts[
            "unsupported_positive_direct_buyer_flags"
        ],
        "candidate_with_mixed_buyer_supplier_roles": counts[
            "candidate_with_mixed_buyer_supplier_roles"
        ],
        "same_cycle_reconciliation_candidates": reconciliation.get("candidate_count"),
        "same_cycle_holding_persistence_count": persistence.get("persisted_candidate_count"),
        "pending_holding_review_evaluated": review.get("candidate_count"),
        "pending_holding_new_review_transitions": review.get("review_ready_count"),
        "pending_holding_blocker_counts": dict(review.get("blocked_reason_counts") or {}),
        "scout_to_pending_holding_conversion_rate": None,
        "limitations": notes,
        "database_write_performed": False,
        "outbound_sent": False,
        "commercial_authority": "none",
    }


def refresh_evidence_quality_scorecard(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    data = {}
    for name in SOURCES:
        obj = json.loads((root / "runtime/buyer_acquisition" / name).read_text())
        if not isinstance(obj, Mapping):
            raise ValueError("evidence_quality_source_not_object:" + name)
        data[name] = obj
    score = build_evidence_quality_scorecard(
        *(data[name] for name in SOURCES),
    )
    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(score, indent=2, sort_keys=True) + "\n")
    temp.replace(path)
    return score
