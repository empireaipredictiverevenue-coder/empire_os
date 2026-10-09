"""Actionable, non-executing evidence recovery for EmpireOS Buyer Flow Meter.

Use existing company-level Scout evidence and *independent* accumulated
holding blockers. Never turn count-based recommendations into database tasks,
re-probing loops or outbound permission.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping
from urllib.parse import urlsplit

from empire_os.buyer_claim_provenance import verified_direct_purchase_receipt
from empire_os.first_party_evidence_contract import first_party_contact_decision

# This is discovery infrastructure, not evidence of a prospective buyer.
NON_PROSPECT_DISCOVERY_HOSTS = frozenset({"search.google", "cybo.com"})

BLOCKER_RECOVERY = {
    "direct_buyer_evidence_missing": (
        "first_party_purchase_claim_recovery",
        "Search Fabric commercial page discovery + buyer_claim_provenance",
        4,
        "Locate an exact first-party statement from the company that it buys leads or calls; reject marketplace marketing as direct-buying proof.",
    ),
    "official_registry_identity_mismatch": (
        "official_registry_identity_corroboration",
        "existing official registry evidence + first-party company identity",
        4,
        "Resolve legal name and company website conflicts without attaching an unrelated search-hit domain.",
    ),
    "business_name_not_verified": (
        "first_party_legal_name_verification",
        "Search Fabric first-party business identity observation",
        3,
        "Confirm the company's observed first-party name; search-query titles do not establish company identity.",
    ),
    "business_identity_incomplete": (
        "canonical_company_identity_recovery",
        "existing Buyer Scout canonical prospect seed and first-party site corroboration",
        3,
        "Reconcile the exact canonical prospect website with separately observed company identity; do not infer from name similarity.",
    ),
    "site_evidence_below_floor": (
        "site_evidence_quality_recovery",
        "existing bounded Search Fabric site probe",
        1,
        "Inspect the existing site evidence and choose a higher-quality first-party page only when new evidence can be found.",
    ),
    "first_party_contact_path_missing": (
        "first_party_company_contact_path",
        "existing first-party contact probe",
        2,
        "Verify a public company contact route without falsely binding it to a named decision-maker.",
    ),
    "permit_territory_not_verified": (
        "official_permit_territory_verification",
        "existing permit evidence and official NYC territory sources",
        2,
        "Confirm source-backed permit territory; no location inference from general company marketing.",
    ),
    "query_evidence_missing": (
        "source_query_provenance_recovery",
        "existing Search Fabric query provenance",
        2,
        "Recover a source-backed discovery query, not a synthetic evidence link.",
    ),
}
MAX_TARGETS = 5
MAX_BLOCKERS = 8


def _domain(raw: Any) -> str:
    if not isinstance(raw, str) or len(raw) > 300:
        return ""
    try:
        parsed = urlsplit(raw)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.username or parsed.password
            or parsed.query or parsed.fragment
            or parsed.port not in {None, 80, 443}
        ):
            return ""
        hostname = (parsed.hostname or "").casefold().rstrip(".").removeprefix("www.")
        if not hostname or "." not in hostname or ".." in hostname:
            return ""
        if any(not label.isalnum() and "-" not in label for label in hostname.split(".")):
            return ""
        return hostname
    except ValueError:
        return ""


def _fpr(domain: str) -> str:
    return sha256(("empire:buyerflow:v1:" + domain).encode("utf-8")).hexdigest()[:24]


def _strict_contact_bound(row: Mapping[str, Any]) -> bool:
    website = str(row.get("website") or "")
    for person in (row.get("first_party_people") or [])[:10]:
        if not isinstance(person, Mapping) or not all(
            str(person.get(k) or "").strip() for k in ("name", "title", "email")
        ):
            continue
        valid, _ = first_party_contact_decision(
            website=website,
            source_url=person.get("url") or person.get("evidence_url"),
            email=person.get("email"),
            direct_publication=person.get("direct_publication"),
        )
        if valid:
            return True
    return False


def _identity_bound(row: Mapping[str, Any], domain: str) -> bool:
    return bool(
        row.get("canonical_identity_verified") is True
        and row.get("canonical_seed_identity_corroborated") is True
        and row.get("canonical_seed_prospect_id")
        and _domain(row.get("canonical_seed_website")) == domain
        and row.get("discovery_source") == "canonical_prospect_seed"
    )


def candidate_evidence_states(
    scout: Mapping[str, Any], *,
    now: datetime,
) -> dict[str, dict[str, Any]]:
    """Only exact-company source evidence, never person details or guessed IDs."""
    output: dict[str, dict[str, Any]] = {}
    duplicate: set[str] = set()
    rows = scout.get("candidates")
    if not isinstance(rows, list):
        return {}
    for row in rows[:100]:
        if not isinstance(row, Mapping):
            continue
        domain = _domain(row.get("website"))
        declared = str(row.get("domain") or "").casefold().rstrip(".").removeprefix("www.")
        if not domain or domain != declared or domain in NON_PROSPECT_DISCOVERY_HOSTS:
            continue
        fingerprint = _fpr(domain)
        if fingerprint in duplicate:
            continue
        if fingerprint in output:
            del output[fingerprint]
            duplicate.add(fingerprint)
            continue
        proof = verified_direct_purchase_receipt(
            {"buyer_claim_provenance": row.get("buyer_claim_provenance")},
            company_website=str(row.get("website")), now=now,
        )
        relationship = str(row.get("buyer_relationship") or "unknown")
        if relationship not in {
            "unknown", "direct_inventory_buyer",
            "intermediary_or_marketplace", "lead_supplier_or_publisher",
            "mixed_role_requires_review",
        }:
            relationship = "unknown"
        output[fingerprint] = {
            "company_domain": domain,
            "relationship": relationship,
            "purchase_statement_verified": bool(proof),
            "named_person_email_bound": _strict_contact_bound(row),
            "canonical_company_correlated": _identity_bound(row, domain),
            "site_evidence_below_floor": (
                isinstance(row.get("site_evidence_score"), (int, float))
                and not isinstance(row.get("site_evidence_score"), bool)
                and float(row["site_evidence_score"]) < 0.5
            ),
            "has_canonical_seed": bool(row.get("canonical_seed_prospect_id")),
        }
    return output


def plan_recovery(
    flow: Mapping[str, Any],
    scout: Mapping[str, Any],
    *,
    now: datetime,
) -> dict[str, Any]:
    """Produce bounded next-evidence actions; execution remains forbidden."""
    health = flow.get("source_health") or {}
    valid_scout = (health.get("scout") or {}).get("status") == "fresh"
    valid_review = (health.get("review") or {}).get("status") == "fresh"
    blockers = flow.get("blockers") or []
    priorities = []
    if valid_review:
        for item in blockers:
            if not isinstance(item, Mapping):
                continue
            reason = str(item.get("reason") or "")
            options = BLOCKER_RECOVERY.get(reason)
            count = item.get("count")
            if not options or not isinstance(count, int) or isinstance(count, bool) or count <= 0:
                continue
            action, capability, weight, measurement = options
            priorities.append({
                "blocking_reason": reason,
                "blocked_records": count,
                "existing_capability": capability,
                "next_evidence_action": action,
                "expected_evidence": measurement,
                "priority_weight": weight,
                "priority_score": count * weight,
                "outbound_authorized": False,
            })
    priorities.sort(key=lambda p: (-p["priority_score"], -p["blocked_records"], p["blocking_reason"]))
    statuses = candidate_evidence_states(scout, now=now) if valid_scout else {}
    candidates = []
    for value in statuses.values():
        domain = value["company_domain"]
        relationship = value["relationship"]
        # Platforms are partners, not assumed direct inventory purchasers.
        if relationship in {"intermediary_or_marketplace", "lead_supplier_or_publisher"}:
            action = "partner_relationship_review"
            reason = "not_proven_direct_inventory_buyer"
            rank = 30
        elif value["has_canonical_seed"] and not value["canonical_company_correlated"]:
            action = "first_party_canonical_identity_corroboration"
            reason = "canonical_identity_unverified"
            rank = 100
        elif not value["purchase_statement_verified"]:
            action = "first_party_purchase_claim_recovery"
            reason = "direct_purchasing_evidence_unverified"
            rank = 85
        elif not value["named_person_email_bound"]:
            action = "exact_named_person_contact_verification"
            reason = "first_party_person_email_binding_unverified"
            rank = 60
        else:
            action = "review_provenance_and_authority"
            reason = "evidence_observed_not_commercial_authority"
            rank = 25
        if value["site_evidence_below_floor"]:
            rank += 10
        candidates.append({
            "company_domain": domain,
            "next_evidence_action": action,
            "evidence_gap": reason,
            "site_evidence_below_floor": value["site_evidence_below_floor"],
            "relationship": relationship,
            "priority_score": rank,
            "execution_authority": "none",
        })
    candidates.sort(key=lambda item: (-item["priority_score"], item["company_domain"]))
    return {
        "schema_version": "empire.buyer_flow_evidence_recovery.v1",
        "mode": "OBSERVE",
        "status": (
            "ready_for_research_review" if valid_scout and valid_review
            else "source_receipts_stale_or_unavailable"
        ),
        "holding_blocker_priority": priorities[:MAX_BLOCKERS],
        "scout_targets": candidates[:MAX_TARGETS],
        "scout_target_population": len(candidates),
        "all_targets_manual_evidence_research_only": True,
        "source_counts_are_first_blocker_not_all_gaps": True,
        "no_new_network_probe": True,
        "db_writes": 0,
        "outbound_sent": False,
        "execution_authority": "none",
    }


def compare_repeated_domains(
    previous: Mapping[str, Mapping[str, Any]],
    current: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Same-company evidence state improvements, not commercial conversions."""
    repeated = set(previous) & set(current)
    names = (
        "purchase_statement_verified",
        "named_person_email_bound",
        "canonical_company_correlated",
    )
    return {
        "status": "matched_repeat_companies" if repeated else "no_repeat_companies",
        "repeated_company_count": len(repeated),
        "newly_observed": {
            name: sum(
                previous[fpr].get(name) is False
                and current[fpr].get(name) is True
                for fpr in repeated
            )
            for name in names
        },
        "evidence_no_longer_current": {
            name: sum(
                previous[fpr].get(name) is True
                and current[fpr].get(name) is False
                for fpr in repeated
            )
            for name in names
        },
        "causal_revenue_conversion_rate": None,
    }
