"""Public first-party contractor website research dossiers (no network I/O).

Observations are analyst-recorded snapshots. A website *self-description* does
not verify business registration, licensing, insurance, claim authority,
buyer demand, contact permission or current capacity.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from urllib.parse import urlparse

from .adapters import dfw_storm_candidates, normalized_domain
from .controls import parse_date, reject_sensitive_input, safe_https_source

SCHEMA = "empire.claims_exchange.dfw_site_review_v1"
MAX_AGE_DAYS = 90


def _host(url: object) -> str:
    if not safe_https_source(url):
        return ""
    return normalized_domain(urlparse(url).hostname)


def build_dossiers(cohort: Mapping, observations: Mapping, *, as_of: date) -> dict:
    """Reconcile exact canonical historic sites against observed final URLs."""
    reject_sensitive_input(cohort)
    reject_sensitive_input(observations)
    candidates, source = dfw_storm_candidates(cohort)
    if not isinstance(observations, Mapping) or observations.get("schema") != SCHEMA:
        raise ValueError("observations_schema_not_supported")
    entries = observations.get("sites")
    if not isinstance(entries, list) or len(entries) > 100:
        raise ValueError("invalid_site_observations")

    by_domain = {}
    duplicates = set()
    for item in entries:
        if not isinstance(item, Mapping):
            raise ValueError("invalid_site_observation_record")
        domain = normalized_domain(item.get("original_domain"))
        if not domain:
            raise ValueError("untrusted_original_domain")
        if domain in by_domain:
            duplicates.add(domain)
        else:
            by_domain[domain] = item

    dossiers = []
    for contractor in candidates:
        domain = contractor["public_domain"]
        problems = []
        evidence = {}
        details = by_domain.get(domain)
        if domain in duplicates:
            details = None
            problems.append("CONFLICTING_SITE_OBSERVATIONS")
        elif details is None:
            problems.append("SOURCE_OBSERVATION_MISSING")
        else:
            reviewed = parse_date(details.get("observed_at"))
            if (not reviewed or reviewed > as_of or
                    (as_of - reviewed).days > MAX_AGE_DAYS):
                problems.append("STALE_OR_FUTURE_OBSERVATION")
            if not isinstance(details.get("reviewer"), str) or not details["reviewer"].strip():
                problems.append("SOURCE_REVIEWER_MISSING")
            original = details.get("source_url")
            final = details.get("final_url")
            if _host(original) != domain:
                problems.append("SOURCE_URL_IDENTITY_MISMATCH")
            final_host = _host(final)
            if not final_host:
                problems.append("FINAL_URL_NOT_VERIFIED")
            elif final_host != domain:
                problems.append("REDIRECTED_TO_DIFFERENT_COMPANY_DOMAIN")

            evidence = {
                "source_url": original if _host(original) == domain else None,
                "final_url": final if _host(final) else None,
                "observed_at": details.get("observed_at"),
                "reviewer": details.get("reviewer"),
            }
            described_name = details.get("self_described_name")
            if (not isinstance(described_name, str)
                    or described_name.strip().casefold() not in (
                        contractor["company_name"].casefold(),
                        contractor["company_name"].casefold().replace(" & ", " and "))):
                problems.append("BUSINESS_NAME_NOT_MATCHED_ON_SITE")

            if not details.get("roofing_services_observed") is True:
                problems.append("ROOFING_SERVICE_NOT_VERIFIED_ON_SITE")
            if not details.get("dfw_service_area_observed") is True:
                problems.append("DFW_SERVICE_AREA_NOT_VERIFIED_ON_SITE")

            route = details.get("public_business_contact")
            if not isinstance(route, Mapping):
                problems.append("FIRST_PARTY_BUSINESS_CONTACT_MISSING")
            else:
                route_type = route.get("type")
                if route_type == "email":
                    contact = route.get("value", "")
                    if (not isinstance(contact, str) or "@" not in contact or
                            not contact.casefold().endswith("@" + domain)):
                        problems.append("FIRST_PARTY_EMAIL_DOMAIN_MISMATCH")
                elif route_type == "phone":
                    val = route.get("value", "")
                    if not isinstance(val, str) or len("".join(ch for ch in val if ch.isdigit())) < 10:
                        problems.append("PHONE_FORMAT_UNVERIFIED")
                else:
                    problems.append("CONTACT_TYPE_UNSUPPORTED")
            if details.get("insurance_claims_wording_observed") is True:
                problems.append("INSURANCE_ADVERTISING_LEGAL_COPY_REVIEW")

        # Web self-claims are not proof of a registered legal company.
        problems.append("INDEPENDENT_COMPANY_IDENTITY_CORROBORATION_REQUIRED")
        problems.append("MARKETING_BUYER_INTEREST_UNVERIFIED")
        problems = sorted(set(problems))
        blockers = set(problems) - {"INSURANCE_ADVERTISING_LEGAL_COPY_REVIEW"}
        review_stage = (
            "IDENTITY_CHANGE_HOLD"
            if "REDIRECTED_TO_DIFFERENT_COMPANY_DOMAIN" in problems
            else "SOURCE_REVIEW_HOLD" if blockers - {
                "INDEPENDENT_COMPANY_IDENTITY_CORROBORATION_REQUIRED",
                "MARKETING_BUYER_INTEREST_UNVERIFIED",
            }
            else "CORROBORATION_PENDING"
        )
        dossiers.append({
            "entity_id": contractor["entity_id"],
            "company_name": contractor["company_name"],
            "original_domain": domain,
            "site_evidence": evidence,
            "public_contact_source_observed": (
                isinstance(details, Mapping)
                and not any(x in problems for x in (
                    "SOURCE_URL_IDENTITY_MISMATCH", "FINAL_URL_NOT_VERIFIED",
                    "STALE_OR_FUTURE_OBSERVATION", "SOURCE_REVIEWER_MISSING",
                    "BUSINESS_NAME_NOT_MATCHED_ON_SITE"))
                and "FIRST_PARTY_BUSINESS_CONTACT_MISSING" not in problems
                and "FIRST_PARTY_EMAIL_DOMAIN_MISMATCH" not in problems
                and "PHONE_FORMAT_UNVERIFIED" not in problems
                and "CONTACT_TYPE_UNSUPPORTED" not in problems
                and "REDIRECTED_TO_DIFFERENT_COMPANY_DOMAIN" not in problems
            ),
            "qualification_stage": review_stage,
            "research_tasks": problems,
            "research_priority": (
                0 if review_stage == "IDENTITY_CHANGE_HOLD"
                else 80 if review_stage == "CORROBORATION_PENDING" else 30
            ),
            "founder_review_ready": False,
            "outbound_authorized": False,
            "claim_services_authorized": False,
        })
    dossiers.sort(key=lambda x: (-x["research_priority"], x["company_name"].casefold()))
    return {
        "schema": SCHEMA,
        "mode": "OBSERVE",
        "source": source,
        "summary": {
            "historic_cohort_size": len(candidates),
            "sites_with_review_observations": sum(bool(r["site_evidence"]) for r in dossiers),
            "identity_change_holds": sum(r["qualification_stage"] == "IDENTITY_CHANGE_HOLD" for r in dossiers),
            "corroboration_pending": sum(r["qualification_stage"] == "CORROBORATION_PENDING" for r in dossiers),
            "unverified_commercial_interest": len(dossiers),
            "outbound_sent": 0,
            "verified_payments": 0,
        },
        "dossiers": dossiers,
        "outbound_authorized": False,
        "execution_authority": "none",
    }
