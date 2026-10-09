"""Frozen mailbox + qualification packets never imply a commercially verified buyer."""
from __future__ import annotations
import json
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
