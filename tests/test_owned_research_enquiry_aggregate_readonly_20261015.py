"""Fail-closed, zero-PII, no-write SEO research enquiry count proof."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from scripts.probe_owned_research_enquiry_aggregate_readonly import (
    FIELDS, SCHEMA, SQL, classify, run,
)


def packet(**updates):
    original={
        'research_enquiry_rows':0,
        'research_campaigns_with_enquiries':0,
        'enquiry_marketing_or_outbound_hold_violations':0,
        'server_received_submission_events':0,
        'browser_page_view_events':5,
        'browser_cta_click_events':2,
        'browser_enquiry_started_events':1,
        'invalid_submission_events':0,
    }
    original.update(updates)
    return original


def classification(**changes):
    return classify(privileged=True,returncode=0,stdout=json.dumps(packet(**changes)))


def test_zero_enquiries_does_not_confuse_browser_interaction_with_a_buyer():
    result=classification()
    assert result['schema_version']==SCHEMA
    assert result['status']=='NO_RESEARCH_ENQUIRIES_IN_CANONICAL_SOURCE'
    assert result['research_enquiry_rows']==0
    assert result['browser_page_view_events']==5
    assert result['aggregate_event_consistency_verified'] is True
    assert result['commercial_sales_status_inferred'] is False
    assert result['lead_transfer_enabled'] is False
    assert result['contact_data_disclosed'] is False
    for key in ('database_writes','outbound_sent','new_privileges_granted','payment_executed'):
        assert result[key] is False
    assert result['execution_authority']=='NONE'


def test_three_genuine_research_enquiries_are_interest_not_sales():
    result=classification(research_enquiry_rows=3,
                          research_campaigns_with_enquiries=2,
                          server_received_submission_events=3)
    assert result['status']=='RESEARCH_ENQUIRIES_OBSERVED_SEPARATE_FROM_SALES'
    assert result['next_action']=='REVIEW_CONSENT_AND_COMMERCIAL_FIT_BEFORE_PROMOTION'
    assert result['commercial_sales_status_inferred'] is False
    assert result['raw_customer_rows_read_by_operator'] is False
    assert all('email' not in k for k in result.keys())


@pytest.mark.parametrize('changes',[
    {'research_enquiry_rows':3,'server_received_submission_events':2},
    {'research_enquiry_rows':0,'server_received_submission_events':1},
    {'research_enquiry_rows':2,'server_received_submission_events':2,
     'enquiry_marketing_or_outbound_hold_violations':1},
    {'research_enquiry_rows':2,'server_received_submission_events':2,
     'invalid_submission_events':1},
])
def test_mismatch_or_consent_policy_violation_is_never_marked_healthy(changes):
    outcome=classification(**changes)
    assert outcome['status']=='RESEARCH_ENQUIRY_EVIDENCE_INCONSISTENT_REVIEW_REQUIRED'
    assert outcome['aggregate_event_consistency_verified'] is False
    assert outcome['lead_transfer_enabled'] is False


@pytest.mark.parametrize('changes',[
    {'research_campaigns_with_enquiries':2,'research_enquiry_rows':1},
    {'enquiry_marketing_or_outbound_hold_violations':2,'research_enquiry_rows':1},
    {'research_enquiry_rows':-1},
    {'research_enquiry_rows':True},
    {'research_enquiry_rows':2.5},
    {'research_enquiry_rows':1_000_000_001},
])
def test_contradictions_and_non_integer_counts_fail_closed(changes):
    result=classification(**changes)
    assert result['status']=='HELD_UNVERIFIED_EVIDENCE'
    assert result['reason_code']=='UNTRUSTED_RESEARCH_AGGREGATE_RESPONSE'
    assert result['execution_authority']=='NONE'


def test_unexpected_fields_cannot_disclose_identifiers():
    p=packet(reply_email='example@private.invalid')
    result=classify(privileged=True,returncode=0,stdout=json.dumps(p))
    assert result['status']=='HELD_UNVERIFIED_EVIDENCE'
    assert result['contact_data_disclosed'] is False
    assert 'example@private.invalid' not in json.dumps(result)
    p=packet();p.pop('research_enquiry_rows')
    assert classify(privileged=True,returncode=0,stdout=json.dumps(p))['status']=='HELD_UNVERIFIED_EVIDENCE'


def test_multiple_json_rows_or_untrusted_stdout_are_rejected():
    text=json.dumps(packet())
    for bad in (text+'\n'+text, 'email someone@example.com\n'+text, text+'\nWARNING', 'x'*10000, ''):
        result=classify(privileged=True,returncode=0,stdout=bad)
        assert result['status']=='HELD_UNVERIFIED_EVIDENCE'
        assert result['contact_data_disclosed'] is False


def test_missing_authority_or_sql_failure_does_not_claim_no_demand():
    denied=classify(privileged=False,returncode=0,stdout=json.dumps(packet()))
    assert denied['status']=='HELD_UNVERIFIED_EVIDENCE'
    assert denied['reason_code']=='AUTHORIZED_LOCAL_READONLY_OPERATOR_REQUIRED'
    db_bad=classify(privileged=True,returncode=1,stdout=json.dumps(packet()))
    assert db_bad['status']=='HELD_UNVERIFIED_EVIDENCE'
    assert db_bad['reason_code']=='OWNED_RESEARCH_AGGREGATE_UNAVAILABLE'


def test_query_only_uses_existing_research_tables_and_readonly_controls():
    assert 'BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY' in SQL
    assert 'statement_timeout' in SQL and 'lock_timeout' in SQL
    assert 'public.owned_campaign_enquiries' in SQL
    assert 'public.owned_campaign_events' in SQL
    assert 'ROLLBACK;' in SQL
    for word in ('reply_email', 'research_question', 'company', 'prospect_id',
                 'normalized_contact', 'source_ip', 'contact_phone'):
        assert word not in SQL
    assert 'CREATE TABLE' not in SQL.upper()
    assert 'INSERT INTO' not in SQL.upper()
    assert 'UPDATE PUBLIC.' not in SQL.upper()
    assert 'GRANT ' not in SQL.upper()
    assert 'RETURNING' not in SQL.upper()


def test_privileged_run_uses_fixed_local_command_and_only_count_output():
    calls=[]
    def fake_runner(command,**kwargs):
        calls.append((command,kwargs))
        return SimpleNamespace(returncode=0,stdout=json.dumps(packet()),stderr='')
    result=run(euid=0,command_runner=fake_runner)
    assert result['status']=='NO_RESEARCH_ENQUIRIES_IN_CANONICAL_SOURCE'
    command,kwargs=calls[0]
    assert command[:4]==['/usr/sbin/runuser','-u','postgres','--']
    assert command[-2:]==['-f','-']
    assert kwargs['input']==SQL
    assert kwargs['capture_output'] is True and kwargs['check'] is False
    assert kwargs['timeout']<=16
    assert 'PGPASSWORD' not in kwargs['env']


def test_nonprivileged_never_invokes_database():
    def unsafe(*args,**kwargs):
        raise AssertionError('privilege fail-closed should not call database')
    assert run(euid=1000,command_runner=unsafe)['status']=='HELD_UNVERIFIED_EVIDENCE'


def test_missing_schema_does_not_get_reported_as_zero():
    result=run(euid=0,command_runner=lambda *args,**kwargs:
               SimpleNamespace(returncode=3,stdout='',stderr='table missing'))
    assert result['status']=='HELD_UNVERIFIED_EVIDENCE'
    assert 'table missing' not in json.dumps(result)
