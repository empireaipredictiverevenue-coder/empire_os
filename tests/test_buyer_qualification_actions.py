"""Frozen mailbox + qualification packets never imply a commercially verified buyer."""
from __future__ import annotations
import json
import time
from pathlib import Path
import pytest

from scripts.build_buyer_qualification_actions import (
    BuyerPriorityError,plan,save_private,BASE,SOURCES,
)


def _case(root:Path,*,verified:bool=True, bad:int=0):
    directory=root/BASE
    directory.mkdir(parents=True,exist_ok=True)
    config=root/'config/buyer_network_manual_review_holds.json'
    config.parent.mkdir(parents=True,exist_ok=True)
    config.write_text(json.dumps({'schema_version':'empire.buyer_network_manual_holds.v1',
                                  'holds':[]}))
    d1='publisheralpha.example.com'
    d2='buyerbeta.example.com'
    queue=[{'domain':d1,'status':'VERIFY_REQUIREMENTS'},
           {'domain':d2,'status':'WATCH'}]
    shortlist=[
      {'domain':d1,'founder_priority':86,'founder_class':'B_VERIFY_REQUIREMENTS',
       'queue_status':'VERIFY_REQUIREMENTS','evidence_gaps':[
         'verify_payout_economics','verify_compliance_requirements'],
       'verticals':['roofing'],
       'contact_email':'buyer1@example.org','raw_body':'private customer content'},
      {'domain':d2,'founder_priority':65,'founder_class':'B_VERIFY_REQUIREMENTS',
       'queue_status':'WATCH','evidence_gaps':['verify_contact_or_application_path'],
       'verticals':['solar']},
    ]
    packets=[{'domain':d1,'authority':'FOUNDER_REVIEW_ONLY',
              'outbound_authority':False if verified else True,
              'active_verification':True,'buyer_role_corroborated':True,
              'private_email':'private@example.org'}]
    data={
     'shortlist':{'shortlist_count':len(shortlist),'shortlist':shortlist},
     'packets':{'trusted_ready_count':len(packets),'packets':packets},
     'direct_site':{'results':[
         {'domain':d1,'buyer_role':True,'corroborated':True,
          'evidence':{'publisher_program':True,'economics':True,'contactable':True},
          'raw_contact':'private@example.org'}]},
     'queue':{'candidate_count':len(queue),'candidates':queue},
    }
    due={'schema_version':'empire.buyer_due_diligence.v1','mode':'OBSERVE',
         'execution_authority':'none','outbound_sent':False,
         'observations':[{
             'domain':d,'observed_epoch':time.time(),
             'observed_at':'2026-10-09T21:00:00+00:00',
             'state':'NEEDS_FOUNDER_REVIEW',
             'home':{'url':'https://'+d+'/','status':'PASS','http_status':200},
             'checked_links':[],'critical_broken_links':[],
             'outbound_authorized':False,
         } for d in (d1,d2)]}
    (directory/'founder_research_decisions_20261009.json').write_text(json.dumps({
        'schema_version':'empire.founder_research_decisions.v1',
        'mode':'OBSERVE','source':'explicit_founder_chat_decision',
        'execution_authority':'none',
        'outbound_authorized':False,'outbound_sent':False,
        'traffic_authorized':False,'commercial_terms_approved':False,
        'qualification_override':False,'manual_hold_override':False,
        'db_write_authorized':False,
        'decisions':[{'domain':domain,'decision':'CONTINUE_RESEARCH'} for domain in
                     ('astoriacompany.com','rvnu.com','buythecalls.com')],
    }))
    (directory/'due_diligence_latest.json').write_text(json.dumps(due))
    if bad==1:
        data['shortlist']['shortlist_count']=1000
    for key,name in SOURCES.items():
        (directory/name).write_text(json.dumps(data[key]))
    return directory


def test_founder_review_ranks_first_but_cannot_send(tmp_path):
    directory=_case(tmp_path)
    report=plan(tmp_path)
    assert report['network_candidate_count']==2
    assert report['shortlisted_count']==2
    assert report['first_party_due_diligence_current_count']==2
    assert report['first_party_due_diligence_unverified_count']==0
    assert report['trusted_founder_review_count']==1
    assert report['buyer_conversation_verified'] is False
    assert report['contact_verified_for_outbound_count']==0
    assert report['outbound_sent'] is False
    assert report['outbound_enabled'] is False
    assert report['targets'][0]['tier']=='FOUNDER_REVIEW_ONLY'
    assert report['targets'][0]['site_corroborated_buyer_role'] is True
    assert report['targets'][0]['outbound_authorized'] is False
    assert report['targets'][0]['commercial_terms_verified'] is False
    assert report['targets'][1]['tier']=='EVIDENCE_RECOVERY'
    serialized=json.dumps(report)
    assert 'private@example.org' not in serialized
    assert 'buyer1@example.org' not in serialized
    assert 'private customer content' not in serialized
    assert not (directory/'founder_qualification_actions_latest.json').exists()


def test_malformed_packet_never_bypasses_founder_review_gate(tmp_path):
    _case(tmp_path,verified=False)
    report=plan(tmp_path)
    assert report['trusted_founder_review_count']==0
    assert all(x['tier']=='EVIDENCE_RECOVERY' for x in report['targets'])
    assert report['contact_verified_for_outbound_count']==0


def test_mixed_snapshot_count_fails_closed(tmp_path):
    _case(tmp_path,bad=1)
    with pytest.raises(BuyerPriorityError,match='inconsistent_source_counts'):
        plan(tmp_path)


def test_explicit_private_output_is_atomic_and_safe(tmp_path):
    _case(tmp_path)
    report=plan(tmp_path)
    target=save_private(tmp_path,report)
    assert target.stat().st_mode&0o777 == 0o600
    content=json.loads(target.read_text())
    assert content['trusted_founder_review_count']==1
    assert content['outbound_enabled'] is False
    assert content['execution_authority']=='none'
    save_private(tmp_path,report)
    assert len(list(target.parent.glob('founder_qualification_actions_latest.json')))==1


def test_output_symlink_never_followed(tmp_path):
    _case(tmp_path)
    report=plan(tmp_path)
    target=tmp_path/BASE/'founder_qualification_actions_latest.json'
    outside=tmp_path/'outside.json';outside.write_text('DO_NOT_REPLACE')
    target.symlink_to(outside)
    with pytest.raises(BuyerPriorityError,match='unsafe_output_symlink'):
        save_private(tmp_path,report)
    assert outside.read_text()=='DO_NOT_REPLACE'


def test_sources_do_not_allow_private_or_ip_targets(tmp_path):
    directory=_case(tmp_path)
    file=directory/SOURCES['shortlist']
    d=json.loads(file.read_text())
    d['shortlist'].append({'domain':'127.0.0.1','founder_priority':100,'evidence_gaps':[]})
    d['shortlist_count']+=1
    file.write_text(json.dumps(d))
    report=plan(tmp_path)
    assert len(report['targets'])==2
    assert all(x['domain']!='127.0.0.1' for x in report['targets'])


def test_auto_critical_link_hold_overrides_existing_founder_packet(tmp_path):
    import time
    directory=_case(tmp_path)
    path=directory/'due_diligence_latest.json'
    due=json.loads(path.read_text())
    row=due['observations'][0]
    row['state']='EVIDENCE_HOLD'
    row['critical_broken_links']=[{
        'category':'terms','url':'https://publisheralpha.example.com/terms','http_status':404}]
    row['checked_links']=[{'category':'terms',
        'url':'https://publisheralpha.example.com/terms','http_status':404,'status':'HTTP_ERROR'}]
    path.write_text(json.dumps(due))
    report=plan(tmp_path)
    assert report['trusted_founder_review_count']==0
    assert report['automated_evidence_hold_count']==1
    held=next(x for x in report['targets'] if x['domain']=='publisheralpha.example.com')
    assert held['tier']=='AUTOMATED_EVIDENCE_HOLD'
    assert held['automated_hold_reason']=='FIRST_PARTY_CRITICAL_LINK_HTTP_404_OR_410'
    assert held['outbound_authorized'] is False


def test_no_legal_due_artifact_cannot_claim_review_readiness(tmp_path):
    directory=_case(tmp_path)
    (directory/'due_diligence_latest.json').unlink()
    report=plan(tmp_path)
    assert report['trusted_founder_review_count']==0
    assert report['first_party_due_diligence_unverified_count']==2
    assert report['due_diligence_pending_count']==1
    assert report['outbound_enabled'] is False


def test_commercial_actions_do_not_use_budget_as_discovery_gate(tmp_path):
    _case(tmp_path)
    report=plan(tmp_path)
    assert report['buyer_budget_requirement_not_used_as_discovery_gate'] is True
    assert report['contact_verified_for_outbound_count']==0
    assert report['outbound_enabled'] is False
    for row in report['targets']:
        assert row['budget_required_to_research_or_discuss_pilot'] is False
        assert row['commercial_terms_to_be_agreed_before_delivery'] is True
        assert row['buyer_relationship_accepted_or_pilot_authorized'] is False
        assert len(row['buyer_discovery_requirements']) == 6
        assert row['commercial_next_action']
        assert row['outbound_authorized'] is False


def test_contact_history_and_first_party_role_drive_correct_next_action():
    from scripts.build_buyer_qualification_actions import next_commercial_action
    def decide(state='DISCOVERED_NO_CONFIRMED_CONTACT',status='READY_TO_APPROACH',
               tier='FOUNDER_REVIEW_ONLY',role=None):
        return next_commercial_action(
            contact_state=state,queue_status=status,tier=tier,verified_role=role)
    assert decide(state='EXISTING_CONVERSATION') == (
        'REVIEW_LIVE_RELATIONSHIP_AND_QUALIFY_BUYER_PILOT')
    assert decide(state='WORKSPACE_SENT_ALREADY_CONTACTED') == (
        'REVIEW_PRIOR_THREAD_FOR_RESPONSE_NO_DUPLICATE_FIRST_TOUCH')
    assert decide(state='DELIVERY_HOLD') == (
        'NO_NEW_SEND_RECONCILE_SUPPRESSION_OR_DELIVERY')
    assert decide(state='DO_NOT_PURSUE',
                  role='INDUSTRY_CONFERENCE_NOT_VERIFIED_LEAD_BUYER') == (
        'NO_NEW_SEND_RECONCILE_SUPPRESSION_OR_DELIVERY')
    assert decide(role='INDUSTRY_CONFERENCE_NOT_VERIFIED_LEAD_BUYER') == (
        'RESEARCH_RELEVANT_BUYERS_IN_EVENT_ECOSYSTEM_NO_SALES_INTRO')
    assert decide(status='WATCH',tier='EVIDENCE_RECOVERY') == (
        'RESEARCH_COMPANY_ROLE_DEMAND_AND_FIRST_PARTY_CONTACT_PATH')


def test_first_party_role_review_does_not_claim_contract_or_buyer_authority():
    from scripts.build_buyer_qualification_actions import FIRST_PARTY_ROLE_REVIEWS
    assert FIRST_PARTY_ROLE_REVIEWS['contact.io']['role'] == (
        'INDUSTRY_CONFERENCE_NOT_VERIFIED_LEAD_BUYER')
    for domain,item in FIRST_PARTY_ROLE_REVIEWS.items():
        assert item['source_url'].startswith('https://' + domain + '/')
