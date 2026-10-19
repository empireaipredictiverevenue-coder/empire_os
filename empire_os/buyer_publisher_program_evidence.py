"""Owner-reviewed public publisher-program claims for existing Scout rows.

Strictly non-binding website research, never accepted commercial terms.
"""
from __future__ import annotations
from datetime import date, timedelta
import json
from pathlib import Path
from urllib.parse import urlsplit
from typing import Mapping

CATALOG = Path("docs/commercial/BUYER_PUBLISHER_PROGRAM_EVIDENCE_20261019.json")
SCHEMA = "empire.buyer_publisher_program_evidence.v1"
CLASSIFICATIONS_BY_DOMAIN = {
    "bh-network.com":"PUBLIC_US_CALL_AND_LEAD_BUYER_CLAIM",
    "joinglobalwiz.com":"PUBLIC_HOME_SERVICES_PAY_PER_CALL_NETWORK",
    "centfix.ca":"PUBLIC_CANADIAN_REFERRAL_REVENUE_SHARE",
}
REGIONS_BY_DOMAIN = {
    "bh-network.com":frozenset({"US"}),
    "joinglobalwiz.com":frozenset({"US_TRAFFIC","UK_AFFILIATE_APPLICANTS"}),
    "centfix.ca":frozenset({"CA_ON","CA_BC","CA_AB","CA_QC"}),
}
REGIONS = frozenset({"US", "US_TRAFFIC", "UK_AFFILIATE_APPLICANTS",
                    "CA_ON","CA_BC","CA_AB","CA_QC"})
FROZEN_FALSE = (
    "accepted_payout_verified", "accepted_campaign_verified",
    "actual_capacity_verified", "identity_verified_as_buyer",
    "application_submitted", "contact_authorised",
)
class PublicProgrammeHold(ValueError):
    pass

def _host(value: str):
    if not isinstance(value,str) or len(value) > 2048:
        return None
    try:
        p = urlsplit(value)
        if p.scheme != "https" or not p.hostname or p.username or p.password:
            return None
        return p.hostname.lower().removeprefix("www.")
    except ValueError:
        return None

def read_public_program_claims(root: Path, *, today:date|None=None) -> dict:
    today=today or date.today()
    path=Path(root)/CATALOG
    if not path.exists():
        return {"status":"NOT_AVAILABLE","programmes":{}}
    if path.is_symlink() or not path.is_file() or not 100<path.stat().st_size<40_000:
        raise PublicProgrammeHold("untrusted_catalog_path")
    try:
        catalog=json.loads(path.read_text(encoding="utf-8"))
    except (ValueError,UnicodeError) as err:
        raise PublicProgrammeHold("unreadable_programme_catalog") from err
    if (not isinstance(catalog,dict) or catalog.get("schema_version")!=SCHEMA
        or catalog.get("execution_authority")!="NONE"
        or catalog.get("source_policy")!="PUBLIC_FIRST_PARTY_CLAIMS_NOT_ACCEPTED_COMMERCIAL_TERMS"
        or not isinstance(catalog.get("programs"),list)
        or len(catalog["programs"])>15):
        raise PublicProgrammeHold("catalog_authority_or_schema_drift")
    try:
        observed=date.fromisoformat(catalog["observed_at"])
    except (TypeError,ValueError) as err:
        raise PublicProgrammeHold("missing_claim_observation_date") from err
    if observed>today:
        raise PublicProgrammeHold("future_observation_date")
    if today-observed>timedelta(days=30):
        return {"status":"PUBLIC_CLAIMS_STALE_REVERIFY","programmes":{}}
    programmes={}
    for source in catalog["programs"]:
        if not isinstance(source,Mapping):
            raise PublicProgrammeHold("programme_record_invalid")
        domain=source.get("domain")
        if (not isinstance(domain,str) or not domain or domain in programmes
            or _host(source.get("source_url"))!=domain
            or source.get("source_kind")!="company_first_party_site"
            or source.get("classification") != CLASSIFICATIONS_BY_DOMAIN.get(domain)
            or any(source.get(flag) is not False for flag in FROZEN_FALSE)):
            raise PublicProgrammeHold("public_claim_commercial_gate_changed")
        delegated=_host(source.get("application_url"))
        if delegated!=domain and not (
            domain=="bh-network.com" and delegated=="webuycalls.com"
            and source.get("route_status")=="HISTORICAL_WEBUYCALLS_DELIVERABILITY_HOLD"
        ):
            raise PublicProgrammeHold("unsupported_application_delegation")
        regions=source.get("programme_regions")
        if (not isinstance(regions,list) or frozenset(regions) != REGIONS_BY_DOMAIN[domain]
            or len(regions) != len(REGIONS_BY_DOMAIN[domain])):
            raise PublicProgrammeHold("unverified_territory_claim")
        for key in ("claim_evidence","next_questions"):
            claims=source.get(key)
            if (not isinstance(claims,list) or not 1<=len(claims)<=8
                or any(not isinstance(x,str) or not 10<=len(x)<=260 for x in claims)):
                raise PublicProgrammeHold("claim_evidence_missing_or_unbounded")
        if not isinstance(source.get("payout_type"),str) or len(source["payout_type"])>110:
            raise PublicProgrammeHold("payout_claim_untrusted")
        lane=(
            "PRIOR_DELIVERY_HOLD_RECONCILE_BEFORE_CONTACT" if domain=="bh-network.com"
            else "US_CAMPAIGN_AND_PUBLISHER_APPROVAL_REVIEW" if "US_TRAFFIC" in regions
            else "OUTSIDE_UK_US_CORRIDOR_HOLD"
        )
        programmes[domain]={
            "status":"PUBLIC_FIRST_PARTY_PROGRAMME_CLAIM_ONLY",
            "source_url":source["source_url"],
            "publisher_application_url":source["application_url"],
            "public_claim_classification":source["classification"],
            "published_territory_claims":list(regions),
            "public_claims":list(source["claim_evidence"]),
            "public_payout_claim_not_accepted":source["payout_type"],
            "review_lane":lane,
            "next_verification_questions":list(source["next_questions"]),
            "affiliate_application_submitted":False,
            "approved_buyer_capacity":False,
            "accepted_commercial_terms":False,
            "permitted_contact_verified":False,
            "founder_outreach_authorized":False,
        }
    return {"status":"PUBLIC_CLAIMS_SOURCE_REVIEWED_NOT_CONTRACTED",
            "observed_at":observed.isoformat(),"programmes":programmes}
