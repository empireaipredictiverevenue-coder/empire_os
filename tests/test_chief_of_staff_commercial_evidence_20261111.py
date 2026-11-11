"""Original Chief of Staff source-to-revenue telemetry, not buyer promotion."""
from datetime import datetime, timedelta, timezone
import json
from empire_os.chief_of_staff_continuity import summarize_first_party_commercial_evidence

NOW = datetime(2026, 11, 11, 9, 40, tzinfo=timezone.utc)


def fixtures(root, *, age_minutes=1, tamper_source=False, tamper_readiness=False):
    root_catalog=root/'runtime/search_fabric_evidence'
    root_readiness=root/'runtime/buyer_acquisition'
    root_catalog.mkdir(parents=True,exist_ok=True)
    root_readiness.mkdir(parents=True,exist_ok=True)
    row=lambda named,phone: {
        'observed_name':named, 'observed_phone_last_ten':phone,
        'research_status': ('FIRST_PARTY_NAME_AND_PHONE_OBSERVED_REVIEW_ONLY' if phone
            else 'FIRST_PARTY_BUSINESS_NAME_OBSERVED_REVIEW_ONLY' if named
            else 'SOURCE_RIGHTS_OR_ROBOTS_HOLD'),
        'automatic_original_record_promotion_authorized':False,
        'contact_permission_verified':False, 'source_resale_rights_verified':False,
    }
    catalog={
        'schema_version':'empire.search_fabric.original_evidence_memory.v61',
        'mode':'READ_ONLY_FIRST_PARTY_SEARCH_EVIDENCE_MEMORY',
        'last_cycle_at_utc':(NOW-timedelta(minutes=age_minutes)).isoformat(),
        'distinct_prospects_observed':3,
        'prospects':{'a':row(True,True),'b':row(True,False),'c':row(False,False)},
        'buyer_outreach_or_revenue_triggered':False,
        'source_rights_or_contact_authorization_assumed':False,
        'prospect_data_updates':0, 'legal_entity_merges':0,
    }
    if tamper_source:
        catalog['prospects']['a']['contact_permission_verified']=True
    readiness={
        'schema_version':'empire.buyer_scout_review_readiness.v1','mode':'OBSERVE',
        'generated_at':(NOW-timedelta(minutes=age_minutes)).isoformat(),
        'execution_authority':'none','database_write_performed':False,
        'outbound_sent':False,'candidate_count':4,'review_ready_count':0,
        'blocked_count':4,'blocked_reason_counts':{
            'site_evidence_below_floor':3,'direct_buyer_evidence_missing':1},
    }
    if tamper_readiness:
        readiness['database_write_performed']=True
    (root_catalog/'source_evidence_catalog_v61.json').write_text(json.dumps(catalog))
    (root_readiness/'review_readiness_latest.json').write_text(json.dumps(readiness))


def test_live_sources_distinguish_first_party_evidence_from_ready_buyers(tmp_path):
    fixtures(tmp_path)
    report=summarize_first_party_commercial_evidence(tmp_path,NOW)
    assert report['source_fabric_state']=='FIRST_PARTY_RESEARCH_OBSERVED_NOT_QUALIFIED'
    assert report['first_party_prospects_observed']==3
    assert report['first_party_name_corroborated']==2
    assert report['first_party_name_and_phone_corroborated']==1
    assert report['historical_false_positive_name_flags']==0
    assert report['readiness_state']=='ZERO_REVIEW_READY'
    assert report['reviewed_candidates']==4
    assert report['review_ready_candidates']==0
    assert report['top_holding_reasons'][0]['count']==3
    assert report['outreach_authorized'] is False
    assert report['automatic_promotion'] is False
    assert report['full_customer_qualification_proven'] is False


def test_tampered_source_is_held_and_does_not_invalidate_independent_scout(tmp_path):
    fixtures(tmp_path,tamper_source=True)
    report=summarize_first_party_commercial_evidence(tmp_path,NOW)
    assert report['source_fabric_state']=='SOURCE_EVIDENCE_UNAVAILABLE'
    assert report['first_party_prospects_observed'] is None
    assert report['readiness_state']=='ZERO_REVIEW_READY'


def test_tampered_scout_is_held_even_when_fabric_has_evidence(tmp_path):
    fixtures(tmp_path,tamper_readiness=True)
    report=summarize_first_party_commercial_evidence(tmp_path,NOW)
    assert report['source_fabric_state']=='FIRST_PARTY_RESEARCH_OBSERVED_NOT_QUALIFIED'
    assert report['readiness_state']=='SCOUT_READINESS_UNAVAILABLE'
    assert report['review_ready_candidates'] is None


def test_stale_evidence_is_not_mislabelled_as_current(tmp_path):
    fixtures(tmp_path,age_minutes=181)
    report=summarize_first_party_commercial_evidence(tmp_path,NOW)
    assert report['source_fabric_state']=='SOURCE_EVIDENCE_UNAVAILABLE'
    assert report['readiness_state']=='SCOUT_READINESS_UNAVAILABLE'


def test_historical_name_mismatch_is_explicit_not_counted_as_corroboration(tmp_path):
    fixtures(tmp_path)
    path=tmp_path/'runtime/search_fabric_evidence/source_evidence_catalog_v61.json'
    data=json.loads(path.read_text())
    item=data['prospects']['c']
    item['research_status']='FIRST_PARTY_NAME_NOT_CORROBORATED'
    item['observed_name']=True
    path.write_text(json.dumps(data))
    report=summarize_first_party_commercial_evidence(tmp_path,NOW)
    assert report['first_party_name_corroborated']==2
    assert report['first_party_name_and_phone_corroborated']==1
    assert report['historical_false_positive_name_flags']==1
    assert report['full_customer_qualification_proven'] is False


def test_unavailable_evidence_fails_closed(tmp_path):
    report=summarize_first_party_commercial_evidence(tmp_path,NOW)
    assert report['first_party_prospects_observed'] is None
    assert report['review_ready_candidates'] is None
    assert report['outreach_authorized'] is False
