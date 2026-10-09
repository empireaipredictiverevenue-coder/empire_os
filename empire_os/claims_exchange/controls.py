"""Deterministic bounded evidence and compliance controls for V2 research.

No claims handling, source fetching, personal claim records, sales authority or
unverified claims of operating status. Designed to enrich existing V1 output.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from ipaddress import ip_address
from urllib.parse import urlparse
from collections.abc import Mapping
import re

from .engine import assess_candidate, assess_offer

SCHEMA = "empire.claims_exchange.v2.controls"
PUBLIC_TYPES = frozenset(("first_party", "official_registry", "network_program",
                          "public_alert", "published_business_page"))
SENSITIVE_KEYS = frozenset((
    "claimant", "claimant_name", "homeowner", "homeowner_email",
    "homeowner_phone", "policyholder", "policyholder_name", "policy_number",
    "claim_number", "social_security_number", "medical_record", "dob",
    "personal_email", "ssn", "credit_card", "account_number",
))
SAFETY_KEYS = frozenset((
    "jurisdiction", "services", "entity_id", "kind", "evidence",
    "company_name", "public_domain",
))
CLAIM_CONTEXT_FLAGS = frozenset((
    "compensation_tied_to_claim", "percentage_of_claim",
    "referral_to_public_adjuster", "based_on_insurance_proceeds",
    "based_on_repair_award", "fee_split_with_adjuster", "settlement_linked",
))


def parse_date(value: object) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.date()


def safe_https_source(value: object) -> bool:
    if not isinstance(value, str) or not 0 < len(value) <= 2048:
        return False
    try:
        u = urlparse(value)
        host = u.hostname
        if u.scheme != "https" or not host or u.username or u.password or u.port:
            return False
        if not re.fullmatch(r"[A-Za-z0-9.-]+", host) or "." not in host:
            return False
        if host.endswith((".local", ".internal", ".test")) or host in ("localhost",):
            return False
        try:
            ip_address(host)
            return False
        except ValueError:
            return True
    except ValueError:
        return False


def reject_sensitive_input(value: object, *, max_nodes: int = 12000) -> None:
    """Fail closed for known policyholder/claims personal-data fields.

    Not a full DLP system. Upstream must still avoid sending any claim data.
    """
    remaining = max_nodes
    pending = [value]
    while pending:
        remaining -= 1
        if remaining < 0:
            raise ValueError("payload_too_large")
        current = pending.pop()
        if isinstance(current, Mapping):
            for key, child in current.items():
                k = str(key).strip().lower().replace("-", "_")
                if k in SENSITIVE_KEYS or k.startswith(("policyholder_", "claimant_", "homeowner_")):
                    raise ValueError("sensitive_claim_person_data_blocked")
                pending.append(child)
        elif isinstance(current, (list, tuple)):
            pending.extend(current)


def evidence_audit(record: Mapping, *, as_of: date, max_age_days: int = 120) -> dict:
    """Only upstream-verified, timestamped and attributed public-source evidence counts.

    This is *not* independent live validation of the upstream verifier.
    """
    if max_age_days < 1:
        raise ValueError("max_age_days must be positive")
    records = record.get("evidence")
    domain = str(record.get("public_domain", "")).lower().strip().removeprefix("www.")
    accepted = {}
    rejected = {}
    if not isinstance(records, list):
        records = []
    for item in records[:100]:
        if not isinstance(item, Mapping):
            rejected["invalid_record"] = rejected.get("invalid_record", 0) + 1
            continue
        kind = item.get("kind")
        observation_date = parse_date(item.get("observed_at"))
        source = item.get("source_url")
        source_type = item.get("source_type")
        if item.get("verified") is not True or not item.get("verified_by"):
            reason = "not_independently_verified"
        elif not safe_https_source(source) or source_type not in PUBLIC_TYPES:
            reason = "invalid_source"
        elif (source_type == "first_party"
              and (not domain or not urlparse(source).hostname
                   or not (urlparse(source).hostname.removeprefix("www.") == domain
                           or urlparse(source).hostname.endswith("." + domain)))):
            reason = "first_party_domain_mismatch"
        elif observation_date is None or not (as_of - timedelta(days=max_age_days) <= observation_date <= as_of):
            reason = "stale_or_future_evidence"
        elif kind not in (
                "identity", "service", "territory", "public_contact_route",
                "licensed_status", "buyer_demand", "buyer_capacity"):
            reason = "unknown_kind"
        elif kind == "licensed_status" and source_type != "official_registry":
            reason = "license_requires_registry_evidence"
        elif kind == "public_contact_route" and source_type != "first_party":
            reason = "contact_requires_first_party_evidence"
        else:
            reason = None
        if reason:
            rejected[reason] = rejected.get(reason, 0) + 1
            continue
        # newest verified source by kind wins, no raw contents exported.
        previous = accepted.get(kind)
        if previous is None or observation_date > previous["date"]:
            accepted[kind] = {
                "date": observation_date, "source_url": source,
                "source_type": source_type,
            }
    return {
        "accepted_kinds": sorted(accepted),
        "accepted_count": len(accepted),
        "rejected_reasons": dict(sorted(rejected.items())),
        "provenance": {k: {"source_url": v["source_url"],
                            "observed_at": v["date"].isoformat()}
                       for k, v in sorted(accepted.items())},
    }


def candidate_readiness(record: Mapping, *, as_of: date) -> dict:
    reject_sensitive_input(record)
    baseline = assess_candidate(record)
    audit = evidence_audit(record, as_of=as_of)
    kinds = set(audit["accepted_kinds"])
    required = {"identity", "service", "territory", "public_contact_route"}
    if baseline["kind"] == "licensed_claims_partner":
        required.add("licensed_status")
    if baseline["kind"] in {"carrier", "managed_repair_network"}:
        required.update(("buyer_demand", "buyer_capacity"))
    missing = required - kinds
    if not baseline["jurisdiction"] or baseline["jurisdiction"] in ("UNVERIFIED", "UNKNOWN"):
        missing.add("jurisdiction")
    if baseline["kind"] == "buyer_research_candidate":
        missing.add("verified_buyer_type")
    services = record.get("services")
    if not isinstance(services, list) or not services or not all(isinstance(x, str) and x.strip() for x in services):
        missing.add("services")
    # evidence confidence is not a sales/execution authority.
    confidence = min(100, 12 * len(kinds) + (8 if len(set(
        urlparse(v["source_url"]).hostname for v in audit["provenance"].values())) >= 2 else 0))
    return {
        "schema": SCHEMA,
        "mode": "OBSERVE",
        "entity_id": baseline["entity_id"],
        "kind": baseline["kind"],
        "jurisdiction": baseline["jurisdiction"],
        "company_name": str(record.get("company_name", ""))[:120],
        "confidence": confidence,
        "evidence": audit,
        "missing_evidence": sorted(missing),
        "review_state": "FOUNDER_REVIEW_READY" if not missing else "RESEARCH_ONLY",
        "outbound_authorized": False,
        "claim_handling_authorized": False,
        "quote_authorized": False,
        "execution_authority": "none",
    }


def offer_compliance(offer: Mapping) -> dict:
    reject_sensitive_input(offer)
    baseline = assess_offer(offer)
    flags = sorted(x for x in CLAIM_CONTEXT_FLAGS if offer.get(x) is True)
    # Disallow fields that could hide contingency in arbitrary agreements.
    allowed = {"basis", "jurisdiction", "counterparty_type", "package_code"} | CLAIM_CONTEXT_FLAGS
    unknown = set(offer) - allowed
    is_claims_partner = offer.get("counterparty_type") == "licensed_claims_partner"
    if unknown:
        state = "BLOCKED_UNREVIEWED_TERMS"
        reason = "unrecognized_offer_terms_require_manual_review"
    elif flags or is_claims_partner:
        state = "BLOCKED_CLAIMS_COMPENSATION_OR_REFERRAL"
        reason = "no_fee_split_claim_referral_or_hidden_settlement_contingency"
    else:
        state = baseline["quote_state"]
        reason = baseline["reason"]
    return {
        **baseline,
        "schema": SCHEMA,
        "quote_state": state,
        "reason": reason,
        "claim_context_flags": flags,
        "settlement_fee_authorized": False,
        "outbound_authorized": False,
        "execution_authority": "none",
    }


def classify_signal(signal: Mapping, *, as_of: date) -> dict:
    """A weather alert is market context, never proof of a claimant or buyer."""
    reject_sensitive_input(signal)
    kind = signal.get("kind")
    if kind not in {"storm_alert", "hiring_growth", "business_pain", "buyer_rfp",
                    "permit_activity", "network_registration"}:
        return {"status": "REJECTED", "reason": "unknown_signal_kind", "points": 0}
    observed = parse_date(signal.get("observed_at"))
    if (signal.get("verified") is not True
            or not safe_https_source(signal.get("source_url"))
            or observed is None or not as_of - timedelta(days=45) <= observed <= as_of):
        return {"status": "REJECTED", "reason": "insufficient_or_stale_provenance", "points": 0}
    weights = {"storm_alert": 5, "hiring_growth": 8, "business_pain": 12,
               "buyer_rfp": 18, "permit_activity": 5, "network_registration": 3}
    return {
        "status": "CONTEXT_ONLY", "reason": "signal_is_not_entity_identity_or_claim",
        "points": weights[kind], "kind": kind,
        "entity_id": signal.get("entity_id") if isinstance(signal.get("entity_id"), str) else None,
        "source_url": signal["source_url"],
    }
