"""Source-reliability acceptance for original Scout's pinned UK Overture partner."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import pytest
from scripts.overture_uk_partner_research_20261111 import (
    read_partner, SOURCE, SOURCE_SHA256,
)
from scripts.overture_scout_research_input_20261110 import read_live


@pytest.mark.skipif(not SOURCE.is_file(), reason="private production receipt only")
def test_existing_scout_receives_uk_partner_without_reclassifying_buyer():
    rows,summary=read_live(Path('/srv/empire_os'))
    assert summary['status']=='ORIGINAL_SCOUT_OVERTURE_RESEARCH_OBSERVED'
    assert summary['source_count']==3
    assert summary['original_public_prospect_domain_matches_suppressed']==2
    assert summary['uk_partner_research_source']['source_count']==1
    assert {r['domain'] for r in rows}=={
        'fowlerroofingpros.com','alowcostroofingdallas.com','commversion.com'}
    partner=next(r for r in rows if r['domain']=='commversion.com')
    assert partner['truth_class']=='RESEARCH_ONLY_POTENTIAL_PARTNER_NOT_BUYER'
    assert partner['canonical_crm_duplicate_status']=='UNKNOWN_NOT_QUERIED'
    assert partner['contact_permission_verified'] is False
    assert partner['outreach_authorized'] is False
    assert partner['verified_product_purchasing_agreement'] is False
    assert summary['all_tenant_crm_dedup_verified'] is False


@pytest.mark.skipif(not SOURCE.is_file(), reason="private production receipt only")
def test_original_source_hash_is_pinned():
    assert sha256(SOURCE.read_bytes()).hexdigest()==SOURCE_SHA256
    rows,report=read_partner()
    assert [x['domain'] for x in rows]==['commversion.com']
    assert report['qualified_buyers']==0


@pytest.mark.skipif(not SOURCE.is_file(), reason="private production receipt only")
def test_tampered_partner_permission_cannot_be_promoted(tmp_path):
    payload=json.loads(SOURCE.read_text())
    for case in payload['candidate_cases']:
        if case['domain']=='commversion.com':
            case['outreach_authorized']=True
    p=tmp_path/'review.json';p.write_text(json.dumps(payload))
    rows,report=read_partner(source=p,expected_sha256=sha256(p.read_bytes()).hexdigest())
    assert rows==[]
    assert report['status']=='UK_OVERTURE_PARTNER_SOURCE_HELD'


def test_stale_external_source_is_held_without_new_buyer():
    rows,report=read_partner(now=datetime(2026,11,20,tzinfo=timezone.utc))
    assert rows==[]
    assert report['source_count']==0
    assert report['outreach_authorized'] is False
