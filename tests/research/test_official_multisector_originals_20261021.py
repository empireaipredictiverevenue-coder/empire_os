"""Bounded multi-niche first-party sources are NOT rights or sales authority."""
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import pytest

from scripts.review_official_multisector_originals_20261021 import (
    SOURCES,SCHEMA,DATASET_ID,JSON_URL,
    fetch_official_metadata,review_candidates,
)
from empire_os.research.research_products import use_product

ROOT=Path(__file__).resolve().parents[2]
LEDGER=ROOT/'docs/commercial/RESEARCH_SOLAR_HVAC_LEGAL_PROPERTY_UK_US_OFFICIAL_SOURCES_20261021.json'
OBSERVED={
    'ORIGINAL_OFFICIAL_HTML_OBSERVED_NOT_ADMITTED',
    'ORIGINAL_OFFICIAL_METADATA_OBSERVED_NOT_ADMITTED',
    'ORIGINAL_OFFICIAL_HEADING_ONLY_NOT_ADMITTED',
}


def sample_html(url):
    title=(
        'Lawyer Search' if url.endswith('/Lawyer/Search') else
        'Attorney Licensure' if url.endswith('/attorney-licensure/') else
        'Official agency information')
    paragraph=(
        'This is an official page describing renewable solar export and electricity, '
        'registered engineer gas safe heating systems, energy conservation rules, '
        'solicitor practising certificates, brownfield register planning development.'
    )
    # For the two exact HTML title-only legal pages no qualifying original
    # paragraph is present, so headings never establish named-lawyer status.
    if title in ('Lawyer Search','Attorney Licensure'):
        paragraph='None'
    return (
        '<html><head><title>'+title+'</title></head><body><main><p>'
        +paragraph+'</p></main></body></html>'
    ).encode()


def sample_json(url):
    assert url==JSON_URL
    return json.dumps({'id':DATASET_ID,'name':'Zoning Districts',
                       'columns':[{'fieldName':'the_geom'}]}).encode()


def test_fixed_source_scope_is_eight_market_pairs():
    keys={(sector,country) for sector,country,*_ in SOURCES}
    assert keys=={(sector,country) for sector in ('solar','hvac','legal','property')
                 for country in ('US','GB')}
    assert len(SOURCES)==15
    assert len({s[3] for s in SOURCES})==len(SOURCES)
    assert all(s[3].startswith('https://') for s in SOURCES)


def test_synthetic_offline_candidate_preflight_cannot_approve_sources():
    original=review_candidates(html_fetch=sample_html,json_fetch=sample_json,
                               when=datetime(2026,10,21,tzinfo=timezone.utc))
    assert original['schema_version']==SCHEMA
    assert original['total_exact_sources_checked']==15
    assert original['source_admissions']==0
    assert original['independent_editorial_signoffs']==0
    assert original['real_buyer_requests_proven']==0
    assert original['money_moved'] is False
    assert original['database_writes'] is False
    assert len(original['sector_market_matrix'])==8
    for row in original['rows']:
        assert row['source_admitted'] is False
        assert row['source_license_or_reuse_rights_verified'] is False
        assert row['editorial_owner_signed_off'] is False
        assert row['outbound_authorized'] is False
        assert row['customer_delivery_authorized'] is False
        assert row['named_business_registration_checked'] is False
        assert row['individual_property_or_person_records_fetched']==0


def test_heading_only_pages_are_lower_confidence_and_never_factual_approval():
    results=review_candidates(html_fetch=sample_html,json_fetch=sample_json)
    low=[r for r in results['rows'] if
         r['status']=='ORIGINAL_OFFICIAL_HEADING_ONLY_NOT_ADMITTED']
    assert len(low)==2
    assert {r['label'] for r in low}=={
        'illinois_ardc_search','illinois_courts_licensure'}
    assert all(r['sector']=='legal' and r['market']=='US'
               and r['substantive_original_passage_verified'] is False
               and r['topic_anchor_count']==0
               and r['source_identity_page_title_only'] is True
               for r in low)


def test_live_observation_ledger_has_fixed_checksum_sources_and_no_admissions():
    data=json.loads(LEDGER.read_text(encoding='utf-8'))
    assert data['schema_version']==SCHEMA
    assert data['total_exact_sources_checked']==15
    assert data['original_candidates_observed']==11
    assert data['held_candidates']==4
    assert len(data['rows'])==15
    assert len(data['sector_market_matrix'])==8
    assert all(x['original_candidates_observed']>=1
               and x['source_admissions']==0 for x in data['sector_market_matrix'])
    expected={x[3] for x in SOURCES}
    assert {r['exact_source_url'] for r in data['rows']}==expected
    for row in data['rows']:
        assert row['source_admitted'] is False
        assert row['source_license_or_reuse_rights_verified'] is False
        assert row['official_claim_independently_validated'] is False
        assert row['customer_demand_verified'] is False
        assert row['editorial_owner_signed_off'] is False
        assert row['outbound_authorized'] is False
        assert row['db_or_finance_authorized'] is False
        assert row['individual_property_or_person_records_fetched']==0
        datetime.fromisoformat(row['observed_at_utc'])
        if row['status'] in OBSERVED:
            assert re.fullmatch('[a-f0-9]{64}',row['source_body_sha256'])
            assert 0<row['source_body_bytes']<=600000
        else:
            assert row['status']=='ORIGINAL_SOURCE_FETCH_OR_TOPIC_HELD'
            assert not row.get('source_body_sha256')
    zoning=next(r for r in data['rows'] if r['label']=='chicago_zoning_metadata')
    assert zoning['status']=='ORIGINAL_OFFICIAL_METADATA_OBSERVED_NOT_ADMITTED'
    assert zoning['original_dataset_id']==DATASET_ID
    assert zoning['permit_or_zoning_rows_fetched']==0


def test_bad_official_dataset_identity_does_not_create_accepted_source():
    def hostile_json(url):
        return json.dumps({'id':'different-dataset','columns':[]}).encode()
    r=review_candidates(html_fetch=sample_html,json_fetch=hostile_json)
    zoning=next(x for x in r['rows'] if x['label']=='chicago_zoning_metadata')
    assert zoning['status']=='ORIGINAL_SOURCE_FETCH_OR_TOPIC_HELD'
    assert r['source_admissions']==0


def test_fetch_cannot_be_used_for_arbitrary_url():
    with pytest.raises(ValueError,match='UNKNOWN_FIXED_OFFICIAL_DATASET'):
        fetch_official_metadata('https://not-an-approved-source.invalid/data.json')


def test_rejects_naive_observation_clock():
    with pytest.raises(ValueError):
        review_candidates(when=datetime(2026,10,21),html_fetch=sample_html,
                          json_fetch=sample_json)


@pytest.mark.parametrize('sector',('solar','hvac','legal','property'))
def test_existing_research_products_keep_non_dental_sources_held(sector):
    for product in ('empire_research','empire_agent'):
        result=use_product(product,country='both',niche=sector,depth='quality',
                           fresh_discovery=False)
        assert result['original_source_count']==0
        assert result['fresh_discovery_candidates_admitted']==0
        assert result['editorial_approval_verified'] is False
        assert result['outbound_authorized'] is False
        assert result['database_writes'] is False
        assert result['finance_authorized'] is False
