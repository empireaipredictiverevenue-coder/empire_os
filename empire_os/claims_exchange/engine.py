"""Evidence-first, OBSERVE-only candidate, economics and compliance preflight.

This module forks concepts (not transport or write paths) from Buyer Demand Graph,
buyer-review governance, Storm Revenue Strike and carrier_rosters. It never
negotiates claims, submits referrals, sends messages, alters data or prices
settlement services. Compliance determinations require qualified jurisdictional review.
"""
from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlparse

SCHEMA = "empire.claims_exchange.research_v1"
KINDS = frozenset(("contractor", "carrier", "managed_repair_network", "licensed_claims_partner", "buyer_research_candidate"))
EVIDENCE = frozenset(("identity", "service", "territory", "public_contact_route",
                      "licensed_status", "buyer_demand", "buyer_capacity"))
BASE_SAFE = frozenset(("subscription", "fixed_service"))
REGULATED_OR_HIGH_RISK = frozenset(("settlement_percentage", "claim_referral",
                                     "claim_qualified_opportunity", "repair_contract_percentage"))


def _https(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username


def _verified_evidence(candidate: Mapping) -> dict[str, dict]:
    result = {}
    records = candidate.get("evidence", [])
    if not isinstance(records, list):
        return result
    for item in records:
        if (isinstance(item, dict)
            and item.get("kind") in EVIDENCE
            and item.get("verified") is True
            and _https(item.get("source_url"))
            and isinstance(item.get("observed_at"), str)
            and item.get("observed_at").strip()):
            result[item["kind"]] = {
                "source_url": item["source_url"],
                "observed_at": item["observed_at"],
            }
    return result


def assess_candidate(record: Mapping) -> dict:
    """Read only: distinguish discovered names from evidence-qualified opportunities.

    verified=True is merely a provenance assertion from an upstream verifier.
    No external verification is done here; verify independently before outreach.
    """
    if not isinstance(record, Mapping):
        raise TypeError("candidate must be a mapping")
    kind = record.get("kind")
    if kind not in KINDS:
        raise ValueError("unsupported entity kind")
    entity_id = record.get("entity_id")
    if not isinstance(entity_id, str) or not entity_id.strip():
        raise ValueError("canonical entity_id required")
    evidence = _verified_evidence(record)
    required = {"identity", "service", "territory", "public_contact_route"}
    missing = sorted(required - evidence.keys())
    if kind == "licensed_claims_partner" and "licensed_status" not in evidence:
        missing.append("licensed_status")
    if kind in {"carrier", "managed_repair_network"}:
        # They may be researched without assuming they buy our services.
        missing.extend(sorted({"buyer_demand", "buyer_capacity"} - evidence.keys()))
    jurisdiction = record.get("jurisdiction")
    if not isinstance(jurisdiction, str) or not jurisdiction.strip():
        missing.append("jurisdiction")
    return {
        "schema": SCHEMA, "mode": "OBSERVE",
        "entity_id": entity_id.strip(), "kind": kind,
        "jurisdiction": jurisdiction if isinstance(jurisdiction, str) else None,
        "evidence_count": len(evidence), "verified_evidence": evidence,
        "missing_evidence": sorted(set(missing)),
        "review_state": "RESEARCH_READY" if missing else "FOUNDER_REVIEW_READY",
        "outbound_authorized": False, "contract_authorized": False,
        "claim_handling_authorized": False, "execution_authority": "none",
    }


def assess_offer(offer: Mapping) -> dict:
    """No fee quote authorisation, especially for settlement-linked revenue."""
    basis = offer.get("basis")
    if basis not in BASE_SAFE | REGULATED_OR_HIGH_RISK | {"qualified_opportunity"}:
        raise ValueError("unsupported pricing basis")
    jurisdiction = offer.get("jurisdiction")
    if basis in REGULATED_OR_HIGH_RISK:
        state, reason = "BLOCKED_PENDING_SPECIALIST_LEGAL_REVIEW", "claims_or_repair_related_compensation"
    elif basis == "qualified_opportunity":
        state, reason = "BLOCKED_PENDING_REFERRAL_RULE_REVIEW", "lead_or_referral_rules_vary_by_jurisdiction"
    else:
        state, reason = "FOUNDER_TERMS_REVIEW", "draft_non_claim_contingent_commercial_service"
    if not isinstance(jurisdiction, str) or not jurisdiction.strip():
        state, reason = "BLOCKED_MISSING_JURISDICTION", "jurisdiction_required"
    return {
        "schema": SCHEMA, "mode": "OBSERVE", "basis": basis,
        "jurisdiction": jurisdiction, "quote_state": state, "reason": reason,
        "quote_authorized": False, "outbound_authorized": False,
        "settlement_fee_authorized": False, "execution_authority": "none",
    }


def match_capacity(contractor: Mapping, buyer: Mapping, demand: Mapping) -> dict:
    """Suggest review only when buyer demand, capacity, service and territory agree."""
    c, b = assess_candidate(contractor), assess_candidate(buyer)
    reasons = []
    if c["kind"] != "contractor" or b["kind"] not in {"carrier", "managed_repair_network"}:
        reasons.append("wrong_entity_pair")
    if c["review_state"] != "FOUNDER_REVIEW_READY" or b["review_state"] != "FOUNDER_REVIEW_READY":
        reasons.append("unqualified_candidate")
    if c["jurisdiction"] != b["jurisdiction"]:
        reasons.append("territory_mismatch")
    service = demand.get("service")
    if not isinstance(service, str) or not service.strip():
        reasons.append("service_unknown")
    c_services = contractor.get("services", [])
    b_services = buyer.get("services", [])
    if not isinstance(c_services, list) or service not in c_services:
        reasons.append("contractor_service_unverified")
    if not isinstance(b_services, list) or service not in b_services:
        reasons.append("buyer_service_unverified")
    capacity = demand.get("capacity_remaining")
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
        reasons.append("positive_capacity_not_verified")
    if not _https(demand.get("demand_evidence_url")):
        reasons.append("demand_evidence_missing")
    if not _https(demand.get("capacity_evidence_url")):
        reasons.append("capacity_evidence_missing")
    if demand.get("demand_verified") is not True or demand.get("capacity_verified") is not True:
        reasons.append("demand_or_capacity_unverified")
    return {
        "schema": SCHEMA, "mode": "OBSERVE",
        "contractor_id": c["entity_id"], "buyer_id": b["entity_id"],
        "service": service, "reasons": sorted(set(reasons)),
        "state": "MATCH_FOR_FOUNDER_REVIEW" if not reasons else "RESEARCH_ONLY",
        "allocation_authorized": False, "outbound_authorized": False,
        "execution_authority": "none",
    }


def build_review_packets(candidates: list[Mapping]) -> list[dict]:
    """Canonical dedupe. Never turn contact/claim records into exposure exports."""
    seen = set()
    output = []
    for record in candidates:
        packet = assess_candidate(record)
        key = (packet["entity_id"].casefold(), (packet["jurisdiction"] or "").casefold())
        if key in seen:
            continue
        seen.add(key)
        output.append(packet)
    return sorted(output, key=lambda x: (x["kind"], x["entity_id"].casefold()))
