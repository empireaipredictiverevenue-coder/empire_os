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



OFFICIAL_STATE_SCHEMA = "empire.revenue_strike.texas_official_state_dataset_research.v1"
OFFICIAL_STATE_URL = "https://data.texas.gov/resource/9cir-efmm.json"


def _official_name_key(raw: str) -> str:
    """Normalise legal punctuation/AND/& and company suffix, not trade aliases."""
    if not isinstance(raw, str) or len(raw) > 150:
        raise ValueError("OFFICIAL_LEGAL_NAME_INVALID")
    parts = re.findall(r"[a-z0-9]+", raw.lower().replace("&", " and "))
    return " ".join(x for x in parts if x not in {
        "and", "inc", "llc", "limited", "corporation", "corp", "co",
    })


def review_official_state_dataset(
    data: Mapping | None, *, approved_bbb_names: Mapping[str, str],
    as_of: date,
) -> dict[str, dict]:
    """Parse exact legal-name matches from the official Texas public dataset.

    Raw status codes are NOT a live franchise-status certificate, and this
    evidence is NOT a demonstrated relation between a state entity and website.
    Non-A right-to-transact codes are held pending a verified official lookup.
    """
    if data is None:
        return {}
    reject_sensitive_input(data)
    if (not isinstance(data, Mapping)
            or data.get("schema") != OFFICIAL_STATE_SCHEMA
            or data.get("source_url") != OFFICIAL_STATE_URL
            or data.get("dataset_id") != "9cir-efmm"
            or data.get("status_codes_uninterpreted") is not True
            or data.get("outbound_authorized") is not False
            or data.get("official_live_account_status_verified") is not False
            or data.get("dossier_domain_matches_independently_confirmed") is not False):
        raise ValueError("OFFICIAL_DATASET_SOURCE_CONTRACT_INVALID")
    captured = data.get("observed_at")
    try:
        from datetime import datetime
        observed = datetime.fromisoformat(captured.replace("Z", "+00:00"))
        if observed.tzinfo is None:
            raise ValueError("NO_OFFICIAL_OBSERVATION_TIMEZONE")
        observed_date = observed.date()
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError("OFFICIAL_OBSERVATION_TIMESTAMP_INVALID") from exc
    published = parse_date(data.get("dataset_last_reported_update_date"))
    if (not published or published > observed_date or observed_date > as_of
            or (as_of - published).days > 30):
        raise ValueError("OFFICIAL_DATASET_NOT_CURRENT")
    records = data.get("records")
    if not isinstance(records, list) or len(records) > 25:
        raise ValueError("UNBOUNDED_OFFICIAL_RESEARCH")
    found = {}
    for row in records:
        if not isinstance(row, Mapping):
            raise ValueError("OFFICIAL_RECORD_NOT_OBJECT")
        domain = normalized_domain(row.get("company_domain"))
        name = row.get("taxpayer_name")
        if (not domain or domain in found or domain not in approved_bbb_names
                or _official_name_key(name) != _official_name_key(approved_bbb_names[domain])):
            raise ValueError("OFFICIAL_ENTITY_NAME_NOT_COHORT_CORROBORATED")
        if (row.get("taxpayer_state") != "TX"
                or row.get("verified_web_domain_is_same_entity") is not False
                or row.get("official_status_details_separately_verified") is not False
                or row.get("outbound_authorized") is not False):
            raise ValueError("OFFICIAL_EVIDENCE_AUTHORITY_INVALID")
        file_number = row.get("sos_file_number")
        if not isinstance(file_number, str) or not re.fullmatch(r"[0-9]{10}", file_number):
            raise ValueError("OFFICIAL_ENTITY_FILE_NUMBER_INVALID")
        raw_right = row.get("right_to_transact_business_code_raw")
        raw_sos = row.get("sos_status_code_raw")
        if (not isinstance(raw_right, str) or not re.fullmatch(r"[A-Z]{1,2}", raw_right)
                or not isinstance(raw_sos, str) or not re.fullmatch(r"[A-Z]{1,2}", raw_sos)):
            raise ValueError("OFFICIAL_STATE_CODE_UNVERIFIED")
        count = row.get("exact_normalized_name_matches")
        broad = row.get("broad_name_matches_in_query")
        if (type(count) is not int or count != 1 or type(broad) is not int
                or not 1 <= broad <= 15):
            raise ValueError("OFFICIAL_EXACT_NAME_MATCH_NOT_UNIQUE")
        from datetime import date as _date
        charter = parse_date(row.get("sos_charter_date"))
        if (not charter or charter > published
                or not isinstance(row.get("taxpayer_city"), str)
                or not re.fullmatch(r"[A-Z .-]{2,70}", row["taxpayer_city"])):
            raise ValueError("OFFICIAL_ENTITY_DETAILS_INVALID")
        state = (
            "STATE_CODE_REVIEW_HOLD"
            if raw_right != "A" else
            "OFFICIAL_DATASET_NAME_MATCH_PENDING_LIVE_STATUS"
        )
        found[domain] = {
            "status": state,
            "legal_name_as_listed": name,
            "sos_file_number": file_number,
            "charter_date_as_listed": charter.isoformat(),
            "city_as_listed": row["taxpayer_city"],
            "sos_status_code_raw": raw_sos,
            "right_to_transact_business_code_raw": raw_right,
            "dataset_last_reported_update_date": published.isoformat(),
            "source_url": OFFICIAL_STATE_URL,
            "broad_similar_name_row_count": broad,
            "official_name_match_count": 1,
            "website_entity_control_verified": False,
            "live_official_account_status_verified": False,
            "current_business_authority_verified": False,
            "named_recipient_suppression_verified": False,
            "outbound_authorized": False,
        }
    return found



CONTACT_SOURCE_SCHEMA = "empire.revenue_strike.dfw_contractor_public_business_contact_research.v1"
CITY_BEDFORD_PDF = (
    "https://bedfordtx.gov/DocumentCenter/View/9744/"
    "2024-Registered-General-Contractors-Sorted-Alphabetically"
)
BUSINESS_EMAIL_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9._+%-]{0,63}@[a-z0-9-]+(?:\.[a-z0-9-]+)+$"
)


def review_public_business_contact(
    data: Mapping | None, *, cohort_domains: set[str], as_of: date,
) -> dict[str, dict]:
    """Bounded business-only first-party + historical municipal research.

    No email validation/consent, person verification, offer or send permissions.
    Municipality's expired 2024 listing is NEVER treated as a current route.
    """
    if data is None:
        return {}
    reject_sensitive_input(data)
    if (not isinstance(data, Mapping) or data.get("schema") != CONTACT_SOURCE_SCHEMA
            or not isinstance(data.get("records"), list) or len(data["records"]) > 20):
        raise ValueError("BUSINESS_CONTACT_SOURCE_CONTRACT_INVALID")
    observed = parse_date(data.get("researched_at"))
    if not observed or observed > as_of or (as_of-observed).days > 30:
        raise ValueError("BUSINESS_CONTACT_RESEARCH_TIME_INVALID")
    found = {}
    for row in data["records"]:
        if not isinstance(row, Mapping):
            raise ValueError("BUSINESS_CONTACT_RECORD_INVALID")
        domain = normalized_domain(row.get("company_domain"))
        if not domain or domain not in cohort_domains or domain in found:
            raise ValueError("BUSINESS_CONTACT_OUTSIDE_COHORT_OR_DUPLICATE")
        first = row.get("first_party_site_contact")
        historic = row.get("official_historical_registry_contact")
        if not isinstance(first, Mapping) or not isinstance(historic, Mapping):
            raise ValueError("MISSING_CONTACT_SOURCE_PROVENANCE")
        src = first.get("source_url")
        if not safe_https_source(src) or normalized_domain(urlparse(src).hostname) != domain:
            raise ValueError("BUSINESS_CONTACT_NOT_FROM_FIRST_PARTY")
        if (parse_date(first.get("listed_at_review_date")) != observed
                or first.get("purpose") != "general_company_enquiries"
                or first.get("inbox_acceptance_tested") is not False
                or first.get("authorises_vendor_solicitation") is not False):
            raise ValueError("FIRST_PARTY_CONTACT_AUTHORITY_UNVERIFIED")
        generic = first.get("email")
        historic_email = historic.get("printed_contact_email")
        if (not isinstance(generic, str) or not BUSINESS_EMAIL_PATTERN.fullmatch(generic)
                or not isinstance(historic_email, str)
                or not BUSINESS_EMAIL_PATTERN.fullmatch(historic_email)):
            raise ValueError("CONTACT_EMAIL_NOT_WELL_FORMED")
        contact_domain = generic.rsplit("@", 1)[-1]
        if (contact_domain != historic_email.rsplit("@", 1)[-1]
                or row.get("alias_domain_supported_by_first_party") is not True):
            raise ValueError("HISTORICAL_CONTACT_DOMAIN_NOT_FIRST_PARTY_ATTESTED")
        if (historic.get("source_url") != CITY_BEDFORD_PDF
                or historic.get("government_source_as_of") != "2024-05-29"
                or historic.get("printed_registration") != "GCR-23-120"
                or historic.get("printed_registration_expires") != "2025-04-04"
                or historic.get("printed_company_name") != "SPC Construction and Roofing"
                or historic.get("printed_company_address")
                    != "1107 S Airport Circle Suite B, Euless TX 76040"):
            raise ValueError("HISTORICAL_MUNICIPAL_RECORD_NOT_RECONCILED")
        if (observed <= date(2025, 4, 4)
                or any(historic.get(k) is not False for k in (
                    "current_registration_verified",
                    "recipient_still_uses_email_verified",
                    "person_to_mailbox_match_independently_verified",
                    "current_business_contact_authority_verified",
                ))
                or row.get("marketing_buyer_intent_verified") is not False
                or row.get("do_not_contact_unless_governed_cleared") is not True
                or row.get("outbound_authorized") is not False):
            raise ValueError("HISTORICAL_CONTACT_NOT_VALID_FOR_OUTBOUND")
        found[domain] = {
            "state": "PUBLIC_GENERAL_COMPANY_ROUTE_HISTORICAL_PERSON_HOLD",
            "first_party_business_contact_email": generic,
            "first_party_business_contact_source": src,
            "associated_public_business_email_domain": contact_domain,
            "historical_person_candidate_email": historic_email,
            "historical_registry_source": CITY_BEDFORD_PDF,
            "historical_registry_as_of": "2024-05-29",
            "historical_registration_expired": True,
            "person_candidate_current_route_verified": False,
            "named_person_to_email_attribution_verified": False,
            "exact_recipient_suppression_clear": False,
            "recipient_level_contact_history_complete": False,
            "marketing_buyer_intent_verified": False,
            "outbound_authorized": False,
        }
    return found
