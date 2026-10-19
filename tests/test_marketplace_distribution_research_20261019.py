"""Cross-owner marketplace research without false buyers or duplicate outreach."""
from datetime import datetime, timezone
import json

import pytest

from empire_os.marketplace_distribution_research_20261019 import (
    CHANNELS, SCHEMA, review_marketplace_distribution,
)
from scripts.review_marketplace_distribution_20261019 import main


NOW=datetime(2026,10,19,21,0,tzinfo=timezone.utc)


def samples(*, relationships=None, owner_items=None, exclusions=None, previously=None):
    registry={
        "schema_version":"empire.commercial_relationship_registry.v1",
        "mode":"OBSERVE","outbound_authorized":False,
        "outbound_sent":False,"execution_authority":"NONE",
        "relationships":relationships or [],
    }
    sweep={
        "schema_version":"empire.commercial.public_publisher_network_sweep.v1",
        "owner":"existing_buyer_network_owner","mode":"READ_ONLY_RESEARCH",
        "outbound_sent":False,"empiredb_writes":False,
        "items":owner_items or [],
        "excluded_as_existing_empire_network_or_research":exclusions or [],
        "excluded_as_previously_contacted":previously or [],
    }
    return registry,sweep


def test_catalogue_keeps_distinct_sale_types_and_never_invents_revenue():
    d=review_marketplace_distribution(*samples(),at=NOW)
    assert d["schema_version"]==SCHEMA
    assert d["marketplace_routes_reviewed"]==len(CHANNELS)
    assert d["new_registered_publishers"]==0
    assert d["confirmed_paying_marketplaces"]==0
    assert d["actual_product_listings_published"]==0
    assert d["applications_submitted"]==0
    assert d["outbound_authorized"] is False
    assert d["canonical_empiredb_writes"] is False
    lanes={r["lane"] for r in d["marketplace_items"]}
    assert "SELL_SOFTWARE_OR_API" in lanes
    assert "EARN_AFFILIATE_COMMISSIONS" in lanes
    assert "SELL_OWN_VERIFIED_INBOUND_CALLS" in lanes
    assert "SELL_LICENSED_B2B_DATA" in lanes
    assert all(r["seller_onboarding_verified"] is False for r in d["marketplace_items"])


def test_known_aragon_and_marketcall_held_not_resubmitted():
    registry,sweep=samples(relationships=[
        {"identity_domains":["aragon-advertising.com"],"last_outbound_at":"2026-10-10"},
        {"identity_domains":["marketcall.com"],"last_inbound_at":"2026-10-10"},
    ], previously=["aragon-advertising.com"],exclusions=["marketcall.com"])
    d=review_marketplace_distribution(registry,sweep,at=NOW)
    rows={r["id"]:r for r in d["marketplace_items"]}
    assert rows["aragon-existing"]["state"]=="EXISTING_RELATIONSHIP_HOLD"
    assert rows["marketcall-existing"]["state"]=="EXISTING_RELATIONSHIP_HOLD"
    assert rows["aragon-existing"]["previously_contacted_in_canonical_relationships"] is True
    assert all(r["application_submitted"] is False for r in d["marketplace_items"])


def test_other_agent_sweep_and_founder_application_retained_as_holds():
    registry,sweep=samples(owner_items=[
        {"domain":"ringpartner.com"}
    ])
    d=review_marketplace_distribution(registry,sweep,at=NOW)
    rows={r["id"]:r for r in d["marketplace_items"]}
    assert rows["ringpartner-existing"]["state"]=="OTHER_OWNER_RESEARCH_OR_APPLICATION_HOLD"
    assert rows["homeservpro-existing"]["state"]=="OTHER_OWNER_RESEARCH_OR_APPLICATION_HOLD"
    assert rows["callscaler-existing"]["state"]=="OTHER_OWNER_RESEARCH_OR_APPLICATION_HOLD"


def test_suppressed_marketplace_never_becomes_new_application():
    registry,sweep=samples(relationships=[
        {"identity_domains":["awin.com"],"do_not_pursue":True}
    ])
    d=review_marketplace_distribution(registry,sweep,at=NOW)
    x=next(r for r in d["marketplace_items"] if r["id"]=="awin-publisher")
    assert x["state"]=="SUPPRESSED_OR_BOUNCE_HOLD"
    assert d["outbound_authorized"] is False


def test_googles_incorporation_requirements_not_assumed_eligible():
    d=review_marketplace_distribution(*samples(),at=NOW)
    x=next(r for r in d["marketplace_items"] if r["id"]=="google-cloud-marketplace")
    assert x["state"]=="LONG_TERM_COMPLIANCE_ELIGIBILITY"
    assert x["sellable_inventory_verified"] is False


@pytest.mark.parametrize("mutator",[
    lambda r,s:r.update(outbound_authorized=True),
    lambda r,s:r.update(execution_authority="SEND"),
    lambda r,s:s.update(mode="EXECUTE"),
    lambda r,s:s.update(owner="other_agent"),
    lambda r,s:s.update(outbound_sent=True),
    lambda r,s:s.update(excluded_as_previously_contacted="aragon-advertising.com"),
    lambda r,s:r.update(relationships=[{"identity_domains":"aragon-advertising.com"}]),
])
def test_untrusted_sources_hold(mutator):
    r,s=samples()
    mutator(r,s)
    with pytest.raises(ValueError):
        review_marketplace_distribution(r,s,at=NOW)


def test_public_source_urls_are_official_and_https():
    from urllib.parse import urlsplit
    assert len({row[0] for row in CHANNELS})==len(CHANNELS)
    for slug, name, domain, lane, url, gate, action, priority in CHANNELS:
        assert url.startswith("https://")
        assert len(slug)<60
        assert urlsplit(url).hostname
        assert not urlsplit(url).username and not urlsplit(url).password


def test_bad_source_cli_returns_hold_without_leaking_private_data(tmp_path,capsys):
    source=tmp_path/"registry.json"
    source.write_text('{"private":"private@example.com"}')
    sweep=tmp_path/"sweep.json"
    sweep.write_text("{}")
    code=main(["--read-only","--relationship-registry",str(source),
               "--owner-sweep",str(sweep)])
    out=json.loads(capsys.readouterr().out)
    assert code==2
    assert out["state"]=="HOLD_SOURCE_CONTRACT_OR_MISSING_RESEARCH"
    assert "private@" not in json.dumps(out)


def test_publisher_commissions_not_confused_with_recruiting_own_sellers():
    report=review_marketplace_distribution(*samples(),at=NOW)
    rows={r["id"]:r for r in report["marketplace_items"]}
    assert rows["awin-publisher"]["lane"]=="EARN_AFFILIATE_COMMISSIONS"
    assert rows["awin-advertiser"]["lane"]=="RECRUIT_PRODUCT_AFFILIATES"
    assert rows["awin-advertiser"]["state"]=="PAID_VENDOR_PROGRAM_BUDGET_HOLD"
    assert rows["impact-advertiser"]["state"]=="PAID_VENDOR_PROGRAM_BUDGET_HOLD"
    assert rows["partnerstack-vendor"]["state"]=="PAID_VENDOR_PROGRAM_BUDGET_HOLD"
    assert report["paid_vendor_budget_holds"]==3
    assert report["new_registered_publishers"]==0
    assert report["actual_product_listings_published"]==0
