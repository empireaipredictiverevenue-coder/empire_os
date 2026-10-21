"""Original public-page observations must never grant research source admission."""
from pathlib import Path
from datetime import datetime
import json
import re

ROOT=Path(__file__).resolve().parents[2]
REPORT=ROOT/'docs/commercial/RESEARCH_ROOFING_UK_US_PRIMARY_SOURCE_PREFLIGHT_20261021.json'

def test_source_scope_and_all_holds():
    d=json.loads(REPORT.read_text())
    assert d['schema']=='empire.research.public_primary_candidate_preflight.v1'
    assert d['source_count']==6
    assert d['original_html_observed']==3
    assert d['original_json_metadata_observed']==1
    assert sum('NOT_ACCESSIBLE' in r['fetch_status'] for r in d['rows'])==2
    assert len({r['source_url'] for r in d['rows']})==6
    assert d['source_rights_approved']==0 and d['editorial_signoffs']==0
    assert d['outbound_authorized'] is False and d['database_writes'] is False

def test_sha256_and_original_source_roles_fail_closed():
    d=json.loads(REPORT.read_text())
    for r in d['rows']:
        datetime.fromisoformat(r['observed_at_utc'])
        assert r['source_url'].startswith('https://')
        assert r['market'] in ('US','GB')
        assert r['original_source_admitted'] is False
        assert r['reuse_rights_verified'] is False
        assert r['buyer_intent_verified'] is False
        assert r['customer_delivery_authorized'] is False
        if 'OBSERVED_NOT_ADMITTED' in r['fetch_status']:
            assert re.fullmatch('[a-f0-9]{64}',r['body_sha256'])
            assert 0<r['body_bytes']<500001
        else:
            assert 'NOT_ACCESSIBLE' in r['fetch_status']
            assert not r.get('body_sha256')

def test_chicago_metadata_is_not_property_targeting():
    d=json.loads(REPORT.read_text())
    r=next(x for x in d['rows'] if x['label']=='US_Chicago_official_metadata')
    assert r['record_rows_fetched']==0
    assert r['column_count']==122
    assert r['dataset_id']=='ydr8-5enu'
    assert 'permit_records' not in r and 'contacts' not in r
