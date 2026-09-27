"""Canonical acquisition metadata for Predictive Revenue enterprise targets.

All identities and routes in this module are public first-party observations.
Company-level routes are not person-bound contacts and grant no outreach authority.
"""
from __future__ import annotations

from typing import Any

from empire_os.lead_sources import LeadCandidate
from empire_os.predictive_revenue_enterprise_targets import TARGETS


TARGET_ACQUISITION: dict[str, dict[str, Any]] = {
    "apex_service_partners": {
        "website": "https://apexservicepartners.com/",
        "metro": "United States",
        "country_code": "US",
        "company_contact_routes": (
            {
                "channel": "email",
                "value": "info@apexservicepartners.com",
                "verified": True,
                "person_bound": False,
                "source": "first_party_privacy_policy",
                "evidence_url": "https://apexservicepartners.com/privacy-policy/",
            },
            {
                "channel": "webform",
                "value": "https://apexservicepartners.com/partner-with-us/",
                "verified": True,
                "person_bound": False,
                "source": "first_party_partner_form",
                "evidence_url": "https://apexservicepartners.com/partner-with-us/",
            },
        ),
    },
    "redwood_services": {
        "website": "https://redwoodservices.com/",
        "metro": "Memphis, TN",
        "country_code": "US",
        "company_contact_routes": (
            {
                "channel": "webform",
                "value": "https://redwoodservices.com/connect/",
                "verified": True,
                "person_bound": False,
                "source": "first_party_contact_form",
                "evidence_url": "https://redwoodservices.com/connect/",
            },
        ),
    },
    "neighborly": {
        "website": "https://www.neighborlybrands.com/",
        "metro": "Waco, TX",
        "country_code": "US",
        "company_contact_routes": (
            {
                "channel": "webform",
                "value": "https://www.neighborlybrands.com/contact-us/",
                "verified": True,
                "person_bound": False,
                "source": "first_party_contact_form",
                "evidence_url": "https://www.neighborlybrands.com/contact-us/",
            },
            {
                "channel": "voice",
                "value": "+18552178437",
                "verified": True,
                "person_bound": False,
                "source": "first_party_contact_page",
                "evidence_url": "https://www.neighborlybrands.com/contact-us/",
            },
        ),
    },
    "authority_brands": {
        "website": "https://www.authoritybrands.com/",
        "metro": "Columbia, MD",
        "country_code": "US",
        "company_contact_routes": (
            {
                "channel": "webform",
                "value": "https://www.authoritybrands.com/contact-us/",
                "verified": True,
                "person_bound": False,
                "source": "first_party_contact_form",
                "evidence_url": "https://www.authoritybrands.com/contact-us/",
            },
            {
                "channel": "voice",
                "value": "+18004969019",
                "verified": True,
                "person_bound": False,
                "source": "first_party_contact_page",
                "evidence_url": "https://www.authoritybrands.com/contact-us/",
            },
        ),
    },
    "sila_services": {
        "website": "https://silaservices.com/",
        "metro": "King of Prussia, PA",
        "country_code": "US",
        "company_contact_routes": (
            {
                "channel": "webform",
                "value": "https://silaservices.com/contact/",
                "verified": True,
                "person_bound": False,
                "source": "first_party_contact_form",
                "evidence_url": "https://silaservices.com/contact/",
            },
            {
                "channel": "voice",
                "value": "+16104919409",
                "verified": True,
                "person_bound": False,
                "source": "first_party_contact_page",
                "evidence_url": "https://silaservices.com/contact/",
            },
        ),
    },
    "turnpoint_services": {
        "website": "https://www.turnpointservices.com/",
        "metro": "Louisville, KY",
        "country_code": "US",
        "company_contact_routes": (
            {
                "channel": "webform",
                "value": "https://www.turnpointservices.com/contact/",
                "verified": True,
                "person_bound": False,
                "source": "first_party_contact_form",
                "evidence_url": "https://www.turnpointservices.com/contact/",
            },
            {
                "channel": "voice",
                "value": "+18335078077",
                "verified": True,
                "person_bound": False,
                "source": "first_party_terms_contact",
                "evidence_url": "https://www.turnpointservices.com/terms-and-condition/",
            },
        ),
    },
    "blackstone_operating_team": {
        "website": "https://www.blackstone.com/",
        "metro": "New York, NY",
        "country_code": "US",
        "company_contact_routes": (
            {
                "channel": "voice",
                "value": "+12125835000",
                "verified": True,
                "person_bound": False,
                "source": "first_party_offices_page",
                "evidence_url": "https://www.blackstone.com/the-firm/our-offices/",
            },
        ),
    },
    "vista_equity_partners": {
        "website": "https://www.vistaequitypartners.com/",
        "metro": "Austin, TX",
        "country_code": "US",
        "company_contact_routes": (
            {
                "channel": "webform",
                "value": "https://www.vistaequitypartners.com/contact/",
                "verified": True,
                "person_bound": False,
                "source": "first_party_contact_page",
                "evidence_url": "https://www.vistaequitypartners.com/contact/",
            },
            {
                "channel": "voice",
                "value": "+15127302400",
                "verified": True,
                "person_bound": False,
                "source": "first_party_contact_page",
                "evidence_url": "https://www.vistaequitypartners.com/contact/",
            },
        ),
    },
    "eqt": {
        "website": "https://eqtgroup.com/",
        "metro": "Stockholm",
        "country_code": "SE",
        "company_contact_routes": (
            {
                "channel": "voice",
                "value": "+46850655300",
                "verified": True,
                "person_bound": False,
                "source": "first_party_stockholm_office",
                "evidence_url": "https://eqtgroup.com/about/offices/stockholm",
            },
        ),
    },
}


def build_enterprise_lead_candidates() -> tuple[LeadCandidate, ...]:
    candidates: list[LeadCandidate] = []
    for target in TARGETS:
        acquisition = TARGET_ACQUISITION[target.account_key]
        website = str(acquisition["website"])
        candidates.append(
            LeadCandidate(
                name=target.account_name,
                niche="predictive_revenue_enterprise",
                metro=str(acquisition["metro"]),
                country_code=str(acquisition["country_code"]),
                source="public_enterprise_target",
                lead_score=50,
                url=target.evidence_urls[0],
                details=target.campaign_angle,
                raw={
                    "account_key": target.account_key,
                    "account_type": target.account_type,
                    "wave": target.wave,
                    "business_website": website,
                    "observed_people": [
                        dict(person)
                        for person in target.observed_people
                    ],
                    "target_roles": list(target.target_roles),
                    "target_product_codes": list(
                        target.target_product_codes
                    ),
                    "evidence_urls": list(target.evidence_urls),
                    "company_contact_routes": [
                        dict(route)
                        for route in acquisition[
                            "company_contact_routes"
                        ]
                    ],
                    "evidence_classification": (
                        "PUBLIC_OBSERVED_EVIDENCE"
                    ),
                    "fit_classification": "INTERNAL_HYPOTHESIS",
                    "contact_verified": False,
                    "binding_intent_verified": False,
                    "outreach_authorized": False,
                    "actual_revenue": False,
                },
            )
        )
    return tuple(candidates)


def build_enterprise_acquisition_review() -> dict[str, Any]:
    candidates = build_enterprise_lead_candidates()
    return {
        "schema_version": (
            "empire.predictive-revenue-enterprise-acquisition.v1"
        ),
        "candidate_count": len(candidates),
        "source": "public_enterprise_target",
        "candidates": [
            {
                "name": item.name,
                "metro": item.metro,
                "country_code": item.country_code,
                "source": item.source,
                "lead_score": item.lead_score,
                "url": item.url,
                "raw": item.raw,
            }
            for item in candidates
        ],
        "public_fit_is_buyer_intent": False,
        "person_name_is_contact_verification": False,
        "company_route_is_person_bound": False,
        "outreach_authorized": False,
        "payment_action": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }
