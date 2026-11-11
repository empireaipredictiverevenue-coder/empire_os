"""Regression: name-not-corroborated must never become evidence of identity."""
import uuid
from datetime import datetime, timezone
from hashlib import sha256
import pytest
from empire_os.search_fabric.automated_source_recovery_v60 import classify_site, source_recovery_cycle, SCHEMA
from empire_os.search_fabric.source_evidence_memory_v61 import validate_observation, reconcile


def packet(status,has_name,has_phone):
    return {
        'prospect_id':str(uuid.uuid4()),
        'research_status':status,
        'source_hostname_sha256':sha256(b'roofers.example').hexdigest(),
        'first_party_company_name_correlated':has_name,
        'first_party_phone_last_ten_observed':has_phone,
        'legal_company_verified':False,
        'buyer_or_contact_permission_verified':False,
    }


def test_mismatched_name_fails_closed_and_new_memory_rejects_false_positive_flag():
    result=classify_site(
        website='https://actual-roofing-company.test/', business_name='Actual Roofing Company',
        phone=None, result={
            'ok':True, 'final_url':'https://actual-roofing-company.test/',
            'business_names':['Entirely Different Business'], 'phones':[],
        })
    assert result['research_status']=='FIRST_PARTY_NAME_NOT_CORROBORATED'
    assert result['first_party_company_name_correlated'] is False
    row=packet(result['research_status'],False,False)
    assert validate_observation(row)['observed_name'] is False
    # Old archived V60 shape is replayable, but must normalise to false.
    row['first_party_company_name_correlated']=True
    assert validate_observation(row)['observed_name'] is False


def test_historical_archive_replay_repairs_false_name_flag_without_promotion():
    old=packet('FIRST_PARTY_NAME_NOT_CORROBORATED',True,False)
    report={
        'schema_version':'empire.search_fabric.original_automated_source_recovery.v60',
        'mode':'AUTONOMOUS_ORIGINAL_SEARCH_FABRIC_EVIDENCE_RECOVERY_OBSERVE',
        'database_writes':False,'new_outbound_sent':0,
        'observed_at_utc':'2026-11-10T09:00:00+00:00',
        'official_sites_attempted':1,'review_only_prospect_evidence':[old],
    }
    memory=reconcile(history=None,report=report,cycle=1)
    evidence=next(iter(memory['prospects'].values()))
    assert evidence['research_status']=='FIRST_PARTY_NAME_NOT_CORROBORATED'
    assert evidence['observed_name'] is False
    assert evidence['automatic_original_record_promotion_authorized'] is False


def test_corroborated_name_and_phone_yield_narrow_review_evidence():
    result=classify_site(
        website='https://acme-roofing.test/',business_name='Acme Roofing',phone='+1 555 123 4321',
        result={'ok':True,'final_url':'https://acme-roofing.test/',
                'business_names':['Acme Roofing'],'phones':['+1 555 123 4321']})
    assert result['research_status']=='FIRST_PARTY_NAME_AND_PHONE_OBSERVED_REVIEW_ONLY'
    assert result['first_party_company_name_correlated'] is True
    assert result['first_party_phone_last_ten_observed'] is True
    row=validate_observation(packet(result['research_status'],True,True))
    assert row['observed_name'] is True
    assert row['observed_phone_last_ten'] is True
    assert row['contact_permission_verified'] is False
    assert row['automatic_original_record_promotion_authorized'] is False


def test_corroborated_name_without_phone_is_not_phone_evidence():
    result=classify_site(
        website='https://acme-roofing.test/',business_name='Acme Roofing',phone=None,
        result={'ok':True,'final_url':'https://acme-roofing.test/',
                'business_names':['Acme Roofing'],'phones':[]})
    assert result['research_status']=='FIRST_PARTY_BUSINESS_NAME_OBSERVED_REVIEW_ONLY'
    assert result['first_party_company_name_correlated'] is True
    assert result['first_party_phone_last_ten_observed'] is False
    row=validate_observation(packet(result['research_status'],True,False))
    assert row['observed_phone_last_ten'] is False
    with pytest.raises(ValueError,match='UNSAFE'):
        validate_observation(packet(result['research_status'],False,False))


def test_original_recovery_pipeline_records_mismatch_without_name_corrob_or_contact():
    uid=str(uuid.uuid4())
    now=datetime(2026,11,11,10,0,tzinfo=timezone.utc)
    row={'id':uid,'website':'https://acme-roofing.test/',
         'business_name':'Acme Roofing', 'phone':None,'niche':'roofing',
         'has_acquisition':False,'has_entity_link':False,'v2_scored':False}
    prior={'schema_version':SCHEMA,'next_cursor':None,
           'domain_attempts':{},'cycles':0}
    report,state=source_recovery_cycle(
        rows=[row],state=prior,now=now,max_verify=1,
        probe=lambda site,**options: {
            'ok':True,'final_url':site,
            'business_names':['Different Roofing Company'],'phones':[]},
        permission_check=lambda site:True,
        clock=lambda:0,time_budget_seconds=100)
    assert report['official_sites_attempted']==1
    evidence=report['review_only_prospect_evidence'][0]
    assert evidence['research_status']=='FIRST_PARTY_NAME_NOT_CORROBORATED'
    assert evidence['first_party_company_name_correlated'] is False
    saved=reconcile(history=None,report=report,cycle=1)
    assert saved['prospects'][uid]['observed_name'] is False
    assert saved['buyer_outreach_or_revenue_triggered'] is False


def test_other_holds_are_never_name_proof():
    for status in ['SITE_PROBE_FAILED','SOURCE_RIGHTS_OR_ROBOTS_HOLD',
                   'SITE_REDIRECT_IDENTITY_HOLD']:
        row=validate_observation(packet(status,False,False))
        assert row['observed_name'] is False
        with pytest.raises(ValueError):
            validate_observation(packet(status,True,False))
