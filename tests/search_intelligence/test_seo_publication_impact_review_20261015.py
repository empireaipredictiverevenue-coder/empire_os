"""SEO post-release measurement must never fabricate buyer conversions or PPC."""
from copy import deepcopy
from datetime import date
from pathlib import Path
import json
import os
from types import SimpleNamespace

import pytest

from empire_os.search_intelligence.seo_publication_impact_review import (
    PAGE_SET, FIRST_RELEASE, SECOND_RELEASE, SCHEMA, review_publication_impact,
)
from scripts import review_seo_director_publication_impact_readonly as op


def inputs():
    earlier = {
        'schema_version':'empire.public.four-page-seo-release.v1',
        'release_state':'FOUR_PAGES_RELEASED_LOOPBACK_VERIFIED',
        'gateway_restart_performed':False, 'paid_media_authorized':False,
        'buyer_outbound_authorized':False,
        'pages':{p:{'after_sha256':'a'*64} for p in FIRST_RELEASE},
    }
    latest=deepcopy(earlier)
    latest['pages']={p:{'after_sha256':'b'*64} for p in SECOND_RELEASE}
    baseline={
        'schema_version':'empire.search.owned_gsc_organic_review.v1',
        'tenant_id':'empire-ai','site_id':'empire-ai.co.uk',
        'gsc_property':'sc-domain:empire-ai.co.uk',
        'mode':'OBSERVE','measurement_status':'GSC_DAILY_SITEWIDE_PLUS_QUERY_PAGE',
        'gsc_currently_available':True, 'production_mutation':False,
        'direct_publishing_allowed':False,
        'window':{'start':'2026-09-15','end':'2026-10-13'},
        'sitewide_current':{'impressions':83,'clicks':1,'commercial_source_attribution_verified':False},
        'sitewide_previous':{'impressions':168,'clicks':3,'commercial_source_attribution_verified':False},
        'current':{'impressions':27,'clicks':0},
    }
    packet={
        'available':True,'source':'google_search_console',
        'site_url':'sc-domain:empire-ai.co.uk','count':2,
        'items':[
            {'keys':['example commercial search','https://empire-ai.co.uk/commercial'],
             'clicks':0,'impressions':2},
            {'keys':['brand','https://empire-ai.co.uk/'],
             'clicks':0,'impressions':25},
        ],
    }
    live={}
    for path in PAGE_SET:
        name=path.lstrip('/')+'.html'
        live[path]={
            'http':200,'sha256':('b' if name in SECOND_RELEASE else 'a')*64,
            'canonical':'https://empire-ai.co.uk'+path,
            'h1_count':1,'expected_buyer_heading_visible':True,
            'approved_internal_business_link_present':True,'noindex':False,
            'required_consent_checkbox':True,'privacy_link_inside_form':True,
        }
    return dict(baseline=baseline,observed_query_pages=packet,
                earlier_release=earlier,latest_release=latest,
                live_pages=live,buyer_capacity_status='NO_VERIFIED_COMMERCIAL_CAPACITY',
                www_status=200)


def test_complete_release_without_fake_post_release_conversion_claim():
    result=review_publication_impact(**inputs())
    assert result['schema_version']==SCHEMA
    assert result['status']=='PRE_PUBLICATION_SEARCH_BASELINE_ONLY'
    assert result['post_release_gsc_days_in_window_max']==0
    assert result['gsc_sitewide']['impressions']==83
    assert result['gsc_sitewide']['clicks']==1
    assert result['gsc_sitewide']['visible_query_page_impressions']==27
    assert result['gsc_sitewide']['query_page_data_complete'] is False
    assert result['seo_pages_verified_public']==4
    assert result['page_evidence']['/commercial']['visible_query_page_impressions']==2
    assert result['page_evidence']['/industries/solar']['visible_query_page_impressions']==0
    assert all(row['complete_page_performance_known'] is False
               for row in result['page_evidence'].values())
    assert all(row['commercial_enquiries_verified'] is None
               for row in result['page_evidence'].values())
    assert result['accepted_click_count'] is None
    assert result['paid_cpc_revenue'] is None
    assert result['actual_founder_enquiries_attributed_to_seo'] is None
    assert result['www_host_redirect_review_needed'] is True
    assert result['buyer_capacity_status']=='NO_VERIFIED_COMMERCIAL_CAPACITY'
    for key in ('production_site_modified','buyer_outbound_authorized',
                'paid_media_spend_authorized','publisher_pay_per_click_live',
                'database_writes','new_scheduler_created'):
        assert result[key] is False
    assert result['execution_authority']=='none'
    assert 'example commercial search' not in json.dumps(result)


def test_later_gsc_date_is_context_not_proven_causal_uplift():
    inp=inputs()
    inp['baseline']['window']={'start':'2026-09-20','end':'2026-10-18'}
    inp['baseline']['sitewide_current']['impressions']=1000
    inp['baseline']['sitewide_current']['clicks']=75
    result=review_publication_impact(**inp)
    assert result['post_release_gsc_days_in_window_max']==3
    assert result['status']=='POST_PUBLICATION_MEASUREMENT_OBSERVED_CAUSALITY_UNKNOWN'
    assert result['post_release_gsc_outcome_attributable_to_site_change'] is False
    assert result['paid_cpc_revenue'] is None


@pytest.mark.parametrize('field,value',[
    ('gsc_property','sc-domain:other.com'),('tenant_id','other'),
    ('mode','EXECUTE'),('gsc_currently_available',False),
    ('production_mutation',True),('direct_publishing_allowed',True),
    ('measurement_status','QUERY_PAGE_ONLY_SITEWIDE_UNKNOWN'),
])
def test_untrusted_cross_property_or_executing_baseline_rejected(field,value):
    inp=inputs();inp['baseline'][field]=value
    with pytest.raises(ValueError,match='untrusted_existing_owned_gsc_review'):
        review_publication_impact(**inp)


@pytest.mark.parametrize('value',[-1,True,2.5,100000001])
def test_untrusted_sitewide_impressions_rejected(value):
    inp=inputs();inp['baseline']['sitewide_current']['impressions']=value
    with pytest.raises(ValueError,match='impossible_owned_sitewide_gsc_count'):
        review_publication_impact(**inp)


def test_forecast_cannot_be_commercial_source_proof():
    inp=inputs();inp['baseline']['sitewide_current']['commercial_source_attribution_verified']=True
    with pytest.raises(ValueError,match='gsc_clicks_are_not_commercial_conversions'):
        review_publication_impact(**inp)


@pytest.mark.parametrize('field,value',[
    ('release_state','REVIEW_ONLY'),('gateway_restart_performed',True),
    ('paid_media_authorized',True),('buyer_outbound_authorized',True),
])
def test_release_manifest_cannot_launder_unapproved_execution(field,value):
    inp=inputs();inp['latest_release'][field]=value
    with pytest.raises(ValueError,match='untrusted_scope_or_execution'):
        review_publication_impact(**inp)


def test_release_receipt_exact_two_and_four_page_scopes_required():
    inp=inputs();inp['earlier_release']['pages'].pop('industries/solar.html')
    with pytest.raises(ValueError,match='incorrect_reviewed_release_page_scope'):
        review_publication_impact(**inp)
    inp=inputs();inp['latest_release']['pages']['buy.html']={'after_sha256':'b'*64}
    with pytest.raises(ValueError,match='incorrect_reviewed_release_page_scope'):
        review_publication_impact(**inp)


@pytest.mark.parametrize('item,value',[
    ('http',404),('sha256','a'*64),('canonical','https://bad.example/commercial'),
    ('h1_count',2),('expected_buyer_heading_visible',False),
    ('approved_internal_business_link_present',False),('noindex',True),
    ('required_consent_checkbox',False),('privacy_link_inside_form',False),
])
def test_commercial_page_requires_real_current_source_and_unmodified_consent(item,value):
    inp=inputs();inp['live_pages']['/commercial'][item]=value
    with pytest.raises(ValueError,match='published_page_not_current_verified_release|consented_founder_form_regression'):
        review_publication_impact(**inp)


def test_gsc_query_rows_from_other_domain_rejected():
    inp=inputs();inp['observed_query_pages']['items'][0]['keys'][1]='https://attacker.example/commercial'
    with pytest.raises(ValueError,match='external_gsc_page_url'):
        review_publication_impact(**inp)


def test_query_page_subset_must_reconcile_and_remain_noncomplete():
    inp=inputs();inp['observed_query_pages']['items'][0]['impressions']=3
    with pytest.raises(ValueError,match='gsc_query_page_receipt_not_matching_review'):
        review_publication_impact(**inp)


def test_unknown_buyer_status_not_interpreted_as_verified():
    inp=inputs();inp['buyer_capacity_status']='UNKNOWN_NOT_VERIFIED'
    result=review_publication_impact(**inp)
    assert result['buyer_capacity_status']=='UNKNOWN_NOT_VERIFIED'
    assert result['publisher_pay_per_click_live'] is False
    inp['buyer_capacity_status']='READY_PAYING_US_BUYER'
    with pytest.raises(ValueError,match='invalid_buyer_capacity_evidence'):
        review_publication_impact(**inp)


def test_private_receipt_exact_name_and_no_overwrite(tmp_path):
    p=tmp_path/'empire_seo_director_postrelease_20261015.json'
    op.write_private_once({'status':'OBSERVE','user_data':False},p,allowed_root=tmp_path)
    assert p.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        op.write_private_once({},p,allowed_root=tmp_path)
    with pytest.raises(ValueError,match='bounded_private_observation_filename_required'):
        op.write_private_once({},tmp_path/'manual_report.json',allowed_root=tmp_path)


def test_symlink_unsafe_receipt_rejected(tmp_path):
    original=tmp_path/'original';original.write_text('{}')
    fake=tmp_path/'fake';fake.symlink_to(original)
    with pytest.raises(ValueError,match='trusted_publication_receipt_required'):
        op._receipt(fake)


def test_third_b2b_search_metadata_release_overlays_only_exact_industry_pages():
    inp=inputs()
    new_receipt=deepcopy(inp["earlier_release"])
    new_receipt["pages"]={name:{"after_sha256":"c"*64} for name in
        ("industries/roofing.html","industries/solar.html")}
    inp["metadata_release"]=new_receipt
    inp["live_pages"]["/industries/roofing"]["sha256"]="c"*64
    inp["live_pages"]["/industries/solar"]["sha256"]="c"*64
    result=review_publication_impact(**inp)
    assert result["buyer_intent_search_metadata_release_verified"] is True
    assert result["seo_pages_verified_public"]==4
    assert result["paid_cpc_revenue"] is None
    assert result["production_site_modified"] is False
    assert result["buyer_outbound_authorized"] is False


def test_missing_or_malformed_third_receipt_cannot_hide_changed_live_page_hash():
    inp=inputs()
    inp["live_pages"]["/industries/solar"]["sha256"]="c"*64
    with pytest.raises(ValueError,match="published_page_not_current_verified_release"):
        review_publication_impact(**inp)
    inp["metadata_release"]=deepcopy(inp["earlier_release"])
    inp["metadata_release"]["pages"]={"industries/roofing.html":{"after_sha256":"c"*64}}
    with pytest.raises(ValueError,match="incorrect_reviewed_release_page_scope"):
        review_publication_impact(**inp)


def test_six_industry_release_hash_chain_and_readonly_outcome():
    from empire_os.search_intelligence.seo_publication_impact_review import INDUSTRY_LINK_RELEASE
    inp=inputs()
    metadata=deepcopy(inp["earlier_release"])
    metadata["pages"]={k:{"after_sha256":"c"*64} for k in
        ("industries/roofing.html","industries/solar.html")}
    inp["metadata_release"]=metadata
    release=deepcopy(inp["earlier_release"])
    release["pages"]={k:{"before_sha256":"c"*64,"after_sha256":"d"*64}
                      for k in INDUSTRY_LINK_RELEASE}
    release.update({"approved_page_count":6, "gateway_restart_required":False,
                    "consumer_roofing_indexation_enabled":False})
    inp["industry_link_release"]=release
    for page in ("/industries/roofing","/industries/solar"):
        inp["live_pages"][page]["sha256"]="d"*64
    result=review_publication_impact(**inp)
    assert result["six_industry_editorial_link_release_verified"] is True
    assert result["seo_pages_verified_public"] == 4
    assert result["paid_cpc_revenue"] is None
    assert result["production_site_modified"] is False
    release["pages"]["industries/roofing.html"]["before_sha256"]="0"*64
    with pytest.raises(ValueError, match="industry_link_release_previous_hash_chain_broken"):
        review_publication_impact(**inp)
    release["pages"]["industries/roofing.html"]["before_sha256"]="c"*64
    release["gateway_restart_required"]=True
    with pytest.raises(ValueError, match="untrusted_six_industry_link_release_scope"):
        review_publication_impact(**inp)
