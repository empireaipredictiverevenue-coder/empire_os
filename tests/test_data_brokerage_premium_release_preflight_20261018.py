"""Premium brokerage launch is held even with valid public/private catalogs."""
from __future__ import annotations
from copy import deepcopy
import json

from scripts import review_data_brokerage_premium_enquiry_20261018 as r

def sources():
    private={
        "status":"THREE_BROKERAGE_DRAFT_PACKAGES_READY_REVENUE_HELD",
        "mode":"OBSERVE",
        "payment_activated":False,"outbound_sent":False,"database_writes":False,
    }
    public={
        "status":"ONE_PUBLIC_ENTRY_TWO_PRIVATE_RECURRING_DRAFTS",
        "public_entry_match_count":1,"private_recurring_package_count":2,
        "public_enquiry_offers_total":10,
        "website_mutation":False,"database_writes":False,
    }
    return private,public

def test_clean_live_shape_is_feature_tested_but_release_still_held():
    p,c=sources()
    report=r.inspect(private=lambda **_:p,public=lambda:c)
    assert report["status"]=="PREMIUM_DISCOVERY_FEATURE_TESTED_RELEASE_HELD"
    assert report["premium_unpriced_proposals"]==2
    assert report["existing_public_entry_enquiry_options"]==1
    assert report["production_premium_discovery_authorized"] is False
    assert report["production_premium_route_mounted"] is False
    assert report["public_site_changed"] is False
    assert report["crm_records_created"]==0
    assert report["end_to_end_public_enquiry_to_founder_crm_verified"] is False
    assert report["existing_frontend_unpriced_option_rendering_verified"] is False
    assert report["actual_buyer_discovery_enquiries_verified"]==0

def test_crm_or_public_authority_drift_fails_closed():
    for surface,key,value in (
        ("p","payment_activated",True),("p","outbound_sent",True),
        ("p","database_writes",True),
        ("c","public_entry_match_count",0),
        ("c","private_recurring_package_count",0),
        ("c","website_mutation",True),
    ):
        p,c=sources()
        if surface=="p":p[key]=value
        else:c[key]=value
        report=r.inspect(private=lambda **_:p,public=lambda:c)
        assert report["status"].startswith("HOLD"),(surface,key)
        assert report["production_premium_discovery_authorized"] is False

def test_failure_does_not_show_private_email_or_database_exception():
    def fail_public():
        raise ValueError("NEVER_PRINT_PRIVATE_RECIPIENT")
    p,c=sources()
    report=r.inspect(private=lambda **_:p,public=fail_public)
    assert report["status"].startswith("HOLD")
    assert "PRIVATE_RECIPIENT" not in json.dumps(report)

def test_cli_requires_readonly_before_any_source_access(monkeypatch,capsys):
    monkeypatch.setattr(r,"inspect",lambda:(_ for _ in ()).throw(
        AssertionError("should not contact public services")))
    assert r.main([])==2
    assert "HOLD_EXPLICIT_READ_ONLY_FLAG_REQUIRED" in capsys.readouterr().out
