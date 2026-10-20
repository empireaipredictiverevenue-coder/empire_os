"""Read-only website receipt and OpenManus scope cannot elevate buyer claims."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import pytest

from empire_os.a2a_first_party_recovery_readback_v1 import review_first_party_research
from empire_os.a2a_openmanus_scoped_research_bridge_v1 import build_scoped_openmanus_plan
from tests.test_a2a_owner_research_protocol_v1_20261020 import pickup

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def approved():
    entries = [
        ("tampa, fl","roofing","https://roofer.example/"),
        ("little rock, ar","hvac","https://hvac.example/"),
        ("nyc","general_contractor","https://builder.example/"),
    ]
    return {
        "schema_version":"empire.a2a.approved_first_party_business_sites.v1",
        "mode":"OBSERVE","send_messages":False,"assume_buyer_intent":False,
        "sites":[{"market":m,"niche":n,"url":u} for m,n,u in entries],
    }


def recovered():
    return {
        "schema_version":"empire.a2a.first_party_site_evidence_recovery.v1",
        "mode":"OBSERVE","execution_authority":"NONE",
        "buyers_verified":0,"contacts_sent":0,"crm_write_performed":False,
        "new_prospects_created":0,"no_personal_contact_harvesting":True,
        "collected_at_utc":NOW.isoformat(),
        "websites_attempted":3,
        "records":[
            {
                "company_site": url, "sector_requested": niche, "market_requested":metro,
                "site_fetch_status":"HTTP_200","robots_policy":"ROBOTS_ALLOWED",
                "source_body_sha256":sha256(url.encode()).hexdigest(),
                "self_described_sector_matched":True,
                "self_described_city_or_region_matched":True,
                "actual_buyer_intent":False,"buyer_budget_verified":False,
                "contact_authorised":False,
                "independently_verified_company_identity":False,
                "person_contact_details_recorded":False,
                "independently_verified_service_territory":False,
            } for metro,niche,url in (
                ("tampa, fl","roofing","https://roofer.example/"),
                ("little rock, ar","hvac","https://hvac.example/"),
                ("nyc","general_contractor","https://builder.example/"),
            )
        ]
    }


def test_local_cached_first_party_readback_never_makes_leads():
    packet = review_first_party_research(approved(), recovered(),now=NOW)
    assert packet["sites_read"] == 3
    assert packet["source_state"] == "CACHED_FIRST_PARTY_PUBLIC_RESEARCH_WITHIN_7_DAYS"
    assert packet["new_verified_sales_leads"] == 0
    assert packet["source_issuer_signature_verified"] is False
    assert not packet["commercial_buying_intent_verified"]
    assert packet["market_coverage"]["tampa, fl"]["self_described_sector_and_region_matches"] == 1


def test_expired_recovery_is_not_new_city_demand():
    old=deepcopy(recovered())
    old["collected_at_utc"]=(NOW-timedelta(days=10)).isoformat()
    v=review_first_party_research(approved(),old,now=NOW)
    assert v["source_state"] == "STALE_FIRST_PARTY_PUBLIC_RESEARCH_OVER_7_DAYS"
    assert v["new_verified_sales_leads"] == 0


def test_untrusted_company_post_cannot_elevate_buyer_claims():
    bad=deepcopy(recovered())
    bad["records"][0]["actual_buyer_intent"]=True
    with pytest.raises(ValueError, match="UNAUTHORIZED"):
        review_first_party_research(approved(),bad,now=NOW)
    bad=deepcopy(recovered())
    bad["records"][0]["company_site"]="https://third-party.example/"
    with pytest.raises(ValueError,match="UNAPPROVED"):
        review_first_party_research(approved(),bad,now=NOW)
    bad=deepcopy(recovered())
    bad["records"][0]["source_body_sha256"]=None
    with pytest.raises(ValueError,match="SOURCE_EVIDENCE"):
        review_first_party_research(approved(),bad,now=NOW)


def test_scoped_openmanus_plan_is_not_external_browser_automation():
    p=pickup()
    r=review_first_party_research(approved(),recovered(),now=NOW)
    plan=build_scoped_openmanus_plan(p,r)
    assert plan["jobs_prepared"] == 2
    assert plan["jobs_executed"] == 0
    assert plan["production_openmanus_executor_verified"] is False
    assert not plan["commercial_outbound_authorized"]
    assert all(x["openmanus_unrestricted_shell_allowed"] is False for x in plan["jobs"])
    assert all(x["production_job_dispatch_performed"] is False for x in plan["jobs"])
    assert all(x["owner_ticket_ids"]["buyer_scout"] for x in plan["jobs"])


def test_even_owner_claim_cannot_self_enable_execution():
    p=pickup()
    r=review_first_party_research(approved(),recovered(),now=NOW)
    plan=build_scoped_openmanus_plan(p,r,executor_verified_by_owner=True)
    assert plan["executor_claim_supplied_but_not_authenticated"]
    assert not plan["production_openmanus_executor_verified"]
    assert plan["production_jobs_dispatched"] == 0
    bad=deepcopy(r); bad["new_verified_sales_leads"]=1
    with pytest.raises(ValueError,match="UNTRUSTED_PUBLIC"):
        build_scoped_openmanus_plan(p,bad)


def test_without_snapshot_no_markets_gets_promoted():
    missing=review_first_party_research(approved(),None,now=NOW)
    assert missing["source_state"] == "SOURCE_CACHE_MISSING_NEEDS_OPERATOR_COLLECTION"
    assert not missing["source_records"]
    assert not missing["commercial_buying_intent_verified"]
