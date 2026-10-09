"""Third-party business identity research overlay for existing Revenue Strike.

Curated public directory entries can corroborate a name/site link, NEVER
prove legal registration, domain ownership, buyer interest or send authority.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from urllib.parse import urlparse
import re

from empire_os.claims_exchange.adapters import normalized_domain
from empire_os.claims_exchange.controls import parse_date, reject_sensitive_input, safe_https_source

SCHEMA = "empire.revenue_strike.dfw_company_corrob.v1"
DISCREPANCIES = frozenset({
    "LISTING_LINK_POINTS_TO_OTHER_DOMAIN",
    "UNCONFIRMED_SAME_ENTITY",
    "BUSINESS_AGE_CLAIM_DISAGREEMENT",
})


def _name_key(raw: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", raw.lower())
    ignored = {"inc", "llc", "ltd", "co", "corporation", "the"}
    return " ".join(t for t in tokens if t not in ignored)


def review_independent_evidence(data: Mapping | None, *, cohort_names: Mapping[str, str],
                                as_of: date) -> dict[str, dict]:
    """Return strictly typed independent-source observations bound to cohort."""
    if data is None:
        return {}
    reject_sensitive_input(data)
    if (not isinstance(data, Mapping) or data.get("schema") != SCHEMA
            or not isinstance(data.get("records"), list) or len(data["records"]) > 40):
        raise ValueError("UNKNOWN_THIRD_PARTY_EVIDENCE_SCHEMA")
    by_domain = {}
    for record in data["records"]:
        if not isinstance(record, Mapping):
            raise ValueError("THIRD_PARTY_RECORD_NOT_OBJECT")
        domain = normalized_domain(record.get("company_domain"))
        if not domain or domain not in cohort_names or domain in by_domain:
            raise ValueError("THIRD_PARTY_DOMAIN_NOT_UNIQUE_IN_COHORT")
        src = record.get("source_url")
        if not safe_https_source(src):
            raise ValueError("THIRD_PARTY_SOURCE_NOT_HTTPS")
        p = urlparse(src)
        if p.hostname not in {"www.bbb.org", "bbb.org"} or not p.path.startswith("/us/tx/"):
            raise ValueError("THIRD_PARTY_SOURCE_NOT_APPROVED_DIRECTORY")
        day = parse_date(record.get("observed_at"))
        if not day or day > as_of or (as_of - day).days > 45:
            raise ValueError("THIRD_PARTY_EVIDENCE_STALE")
        listed_name = record.get("listed_business_name")
        if not isinstance(listed_name, str) or not 5 <= len(listed_name) <= 180:
            raise ValueError("UNTRUSTED_THIRD_PARTY_BUSINESS_NAME")
        if _name_key(listed_name) != _name_key(cohort_names[domain]):
            raise ValueError("THIRD_PARTY_BUSINESS_NAME_UNRELATED")
        if record.get("source_type") != "BBB_BUSINESS_PROFILE":
            raise ValueError("UNSUPPORTED_THIRD_PARTY_SOURCE_TYPE")
        reasons = record.get("discrepancy_codes")
        if (not isinstance(reasons, list) or len(set(reasons)) != len(reasons)
                or not set(reasons).issubset(DISCREPANCIES)):
            raise ValueError("UNTRUSTED_THIRD_PARTY_DISCREPANCY")
        listed_url = record.get("listing_website_url")
        if listed_url is not None and not safe_https_source(listed_url):
            raise ValueError("THIRD_PARTY_WEBSITE_NOT_HTTPS")
        observed_domain = normalized_domain(urlparse(listed_url).hostname) if listed_url else None
        if listed_url and not observed_domain:
            raise ValueError("THIRD_PARTY_LISTED_DOMAIN_INVALID")
        fact = record.get("fact")
        if not isinstance(fact, str) or not 20 <= len(fact) <= 400:
            raise ValueError("THIRD_PARTY_EVIDENCE_FACT_INVALID")
        principal = record.get("business_principal")
        if principal is not None:
            if not isinstance(principal, Mapping) or len(principal) != 8:
                raise ValueError("THIRD_PARTY_PRINCIPAL_SCHEMA_INVALID")
            name, role = principal.get("name"), principal.get("role")
            if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{2,100}", name)
                    or role not in {"Owner/Director", "Owner/Manager", "President"}):
                raise ValueError("THIRD_PARTY_PRINCIPAL_IDENTITY_INVALID")
            if (principal.get("source_url") != src
                    or principal.get("evidence_class") != "DIRECTORY_LISTED_BUSINESS_MANAGEMENT_ONLY"
                    or any(principal.get(k) is not False for k in (
                        "person_identity_independently_verified",
                        "decision_making_or_budget_authority_verified",
                        "contact_route_verified", "recipient_suppression_clear",
                    ))):
                raise ValueError("THIRD_PARTY_PRINCIPAL_AUTHORITY_UNVERIFIED")
        mismatch = bool(reasons) or bool(observed_domain and observed_domain != domain)
        if mismatch:
            state = "INDEPENDENT_SOURCE_IDENTITY_CONFLICT_HOLD"
        elif observed_domain == domain:
            state = "THIRD_PARTY_PROFILE_DOMAIN_MATCH"
        else:
            state = "UNRESOLVED_INDEPENDENT_IDENTITY"
        by_domain[domain] = {
            "state": state,
            "directory_business_name": listed_name,
            "source_url": src,
            "observed_at": day.isoformat(),
            "source_type": record["source_type"],
            "listed_website_domain": observed_domain,
            "discrepancy_codes": sorted(reasons),
            "observation": fact,
            "business_management_research": {
                "name": principal["name"],
                "role_as_listed": principal["role"],
                "directory_source_url": src,
                "status": "PUBLIC_DIRECTORY_LISTED_UNCONFIRMED",
                "real_person_identity_verified": False,
                "decision_or_budget_authority_verified": False,
                "business_contact_route_verified": False,
                "recipient_suppression_verified": False,
                "outbound_authorized": False,
            } if principal is not None and not mismatch else None,
            "state_registry_identity_verified": False,
            "domain_ownership_verified": False,
            "marketing_buyer_intent_verified": False,
            "outbound_authorized": False,
        }
    return by_domain
