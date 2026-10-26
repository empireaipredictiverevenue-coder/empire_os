"""Original SEO hands avoid redundant daily checks without hiding regressions."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import os

import pytest

from scripts import review_original_seo_action_lifecycle_20261026 as op
from empire_os.search_intelligence.seo_action_lifecycle_20261026 import SEOActionHeld

T=datetime(2026,10,27,12,0,tzinfo=timezone.utc)
URL="https://empire-ai.co.uk/commercial"
SHA="e"*64


def previous(*, initial=None, observed=None, week="2026-10-26", state="tested", digest=SHA):
    o=observed or T-timedelta(hours=20)
    return {
        "schema_version":"empire.search.seo_action_lifecycle.v1",
        "observed_at":o.isoformat(),
        "weekly_source_as_of":week,
        "actions":[{
            "id":"action-1","url":URL,"reason_code":"NO_GSC_PAGE_ROW_RETURNED",
            "state":state,
            "technical_test":{
                "status":"TESTED_READ_ONLY_NO_MUTATION",
                "http_status":200,
                "self_canonical":True,
                "indexable":True,
                "html_content_type":True,
                "site_changed":False,
                "observed_source":"live_first_party_https_GET",
                "body_sha256":digest,
                **({"initial_live_test_at_utc":initial.isoformat()} if initial else {}),
            },
        }],
    }


def action():
    return {"id":"action-1","url":URL,"reason_code":"NO_GSC_PAGE_ROW_RETURNED"}


def test_valid_original_live_check_can_be_reused_for_short_window():
    old=previous()
    matches=op._validated_previous(old,T)
    assert op._previous_success(action(),matches["action-1"],
        unchanged_week=True,previous_observed_at=old["observed_at"],now=T)


def test_reuse_expires_from_original_check_not_cache_creation():
    old=previous(initial=T-timedelta(hours=50))
    matches=op._validated_previous(old,T)
    assert not op._previous_success(action(),matches["action-1"],
        unchanged_week=True,previous_observed_at=old["observed_at"],now=T)
    old2=previous(initial=T-timedelta(hours=4),observed=T-timedelta(hours=20))
    old2["actions"][0]["technical_test"]["status"]="REUSED_RECENT_VERIFIED_TECHNICAL_TEST"
    assert op._previous_success(action(),old2["actions"][0],
        unchanged_week=True,previous_observed_at=old2["observed_at"],now=T)


@pytest.mark.parametrize("override",[
    {"http_status":404},{"self_canonical":False},{"indexable":False},
    {"site_changed":True},{"body_sha256":""},{"observed_source":"unknown"},
])
def test_failed_or_unverifiable_previous_test_never_reused(override):
    old=previous()
    old["actions"][0]["technical_test"].update(override)
    assert not op._previous_success(action(),old["actions"][0],
        unchanged_week=True,previous_observed_at=old["observed_at"],now=T)


def test_different_week_or_changed_action_must_run_fresh():
    old=previous()
    assert not op._previous_success(action(),old["actions"][0],
        unchanged_week=False,previous_observed_at=old["observed_at"],now=T)
    different=action()|{"id":"new-stable-id"}
    assert not op._previous_success(different,old["actions"][0],
        unchanged_week=True,previous_observed_at=old["observed_at"],now=T)


def test_previous_archive_cannot_be_future_or_stale():
    with pytest.raises(SEOActionHeld,match="OUTSIDE_FRESHNESS"):
        op._validated_previous(previous(observed=T+timedelta(hours=1)),T)
    with pytest.raises(SEOActionHeld,match="OUTSIDE_FRESHNESS"):
        op._validated_previous(previous(observed=T-timedelta(days=4)),T)


def test_private_prior_receipt_selected_from_existing_owner_folder(tmp_path):
    root=tmp_path/"seo-owner"
    root.mkdir(mode=0o700)
    old=previous()
    source=root/"seo-actions-2026-10-26.json"
    source.write_text(json.dumps(old))
    source.chmod(0o600)
    assert op._previous_receipt(root,T)==old
    source.chmod(0o644)
    with pytest.raises(SEOActionHeld,match="PREVIOUS_PRIVATE_SEO_RECEIPT_NOT_TRUSTED"):
        op._previous_receipt(root,T)


def test_one_report_reuses_check_without_fabricating_revenue(monkeypatch):
    # Existing source adapters are mocked; this test never calls search/web.
    from scripts import review_live_organic_buyer_journey_20261024 as journey_module
    from empire_os import gtm_ops_first_sale_source as sales_module
    from empire_os.search_intelligence.seo_action_lifecycle_20261026 import _id
    week={
        "schema_version":"empire.search.seo_growth_action_queue.v1",
        "status":"EVIDENCE_BACKED_ACTION_QUEUE_READY",
        "source_property":"sc-domain:empire-ai.co.uk",
        "as_of":"2026-10-26",
        "website_changed":False,"execution_authority":"none",
        "actions":[{
            "url":URL,"reason_code":"NO_GSC_PAGE_ROW_RETURNED",
            "priority":"P2_CONTENT_EVIDENCE",
            "next_action":"REVIEW_GSC_EVIDENCE",
            "website_change_authorized":False,
            "publication_authorized":False,
        }],
    }
    # Use five-route owner fixture from existing regression test.
    from tests.test_original_seo_action_lifecycle_20261026 import sources
    _,daily,journey,release=sources()
    monkeypatch.setattr(op,"_trusted_json",lambda path:
        daily if path.name.startswith("google-index-") else
        week if path.name.startswith("weekly_seo_growth_actions_") else release)
    monkeypatch.setattr(op,"_latest_weekly",lambda:Path("weekly_seo_growth_actions_2026-10-26.json"))
    monkeypatch.setattr(journey_module,"review",lambda:journey)
    monkeypatch.setattr(sales_module,"observe_owner_ops_first_sale",
                        lambda *args,**kwargs:{"source_count_verified":False})
    old=previous()
    old["actions"][0]["id"]=_id(URL,"NO_GSC_PAGE_ROW_RETURNED")
    gets=[]
    def fake_get(url):
        gets.append(url)
        return {"status":"TESTED_READ_ONLY_NO_MUTATION","http_status":200,
            "self_canonical":True,"indexable":True,"html_content_type":True,
            "site_changed":False,"observed_source":"live_first_party_https_GET",
            "body_sha256":SHA}
    result=op.build_run(observed=T,get=fake_get,previous=old)
    assert gets==[]
    assert result["state_counts"]["tested"]==1
    assert result["milestone_reached_counts"]["tested"]==1
    assert result["read_only_technical_tests_executed"]==0
    assert result["previous_successful_tests_reused_not_rerun"]==1
    assert result["verified_revenue"] is None
    assert result["database_writes"] is False
    old["weekly_source_as_of"]="2026-10-19"
    result=op.build_run(observed=T,get=fake_get,previous=old)
    assert gets==[URL]
    assert result["read_only_technical_tests_executed"]==1
    assert result["previous_successful_tests_reused_not_rerun"]==0


def test_original_site_redirects_cannot_escape_owned_https_origin():
    from urllib.request import Request
    handler=op._OwnedRedirectOnly()
    req=Request("https://empire-ai.co.uk/industries")
    with pytest.raises(SEOActionHeld,match="CROSS_ORIGIN"):
        handler.redirect_request(req,None,302,"Found",{},
                                 "https://irrelevant.example/offsite")
    with pytest.raises(SEOActionHeld,match="CROSS_ORIGIN"):
        handler.redirect_request(req,None,302,"Found",{},
                                 "http://empire-ai.co.uk/insecure")
    with pytest.raises(SEOActionHeld,match="CROSS_ORIGIN"):
        handler.redirect_request(req,None,302,"Found",{},
                                 "https://empire-ai.co.uk/commercial?token=secret")
    redirect=handler.redirect_request(req,None,308,"Permanent Redirect",{},
                                      "https://empire-ai.co.uk/industries/roofing")
    assert redirect.full_url=="https://empire-ai.co.uk/industries/roofing"
