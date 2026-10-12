"""Bounded discovery of additional Gmail buyer threads; no send or activation."""
from __future__ import annotations
import base64
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
import json
import pytest

from empire_os.buyer_thread_discovery import discover
from scripts.import_connected_gmail_buyer_metadata import refreshed_summary
from empire_os.commercial_relationship_registry import (
    RelationshipEvidenceError, reconcile,
)
from tests.test_connected_gmail_buyer_metadata import inputs

NOW=datetime(2026,10,10,12,0,tzinfo=timezone.utc)
TS=int(datetime(2026,10,10,11,51,tzinfo=timezone.utc).timestamp()*1000)
TID='dddddddddddddddd'
UNKNOWN='aaaaaaaaaaaaaaaa'

def msg(mid,sender,recipient,*, sent,body="",aligned=True):
    domain=sender.rsplit('@',1)[-1]
    headers=[
        {'name':'From','value':sender},
        {'name':'To','value':recipient},
    ]
    if not sent:
        auth=(f'mx.google.com; spf=pass; dmarc=pass (p=NONE) '
              f'header.from={domain};' if aligned else
              f'mx.google.com; dmarc=fail header.from={domain};')
        headers.append({'name':'Authentication-Results','value':auth})
    encoded=base64.urlsafe_b64encode(body.encode()).decode().rstrip('=')
    return {
        'id':mid,'internalDate':str(TS+1000 if not sent else TS),
        'labelIds':['SENT'] if sent else ['INBOX'],
        'payload':{'mimeType':'text/plain','headers':headers,
                   'body':{'data':encoded}},
    }

def thread(tid=TID,domain='leadsmartinc.com',*,aligned=True,
           sender=None,one_way=False):
    sender=sender or 'sam@'+domain
    records=[msg('1111111111111111','flavag83@gmail.com',sender,
                 sent=True,body='Could you send the buyer onboarding pack?')]
    if not one_way:
        records.append(msg('2222222222222222',sender,'flavag83@gmail.com',
                 sent=False,aligned=aligned,
                 body='Recordings are enabled.'))
    return {'id':tid,'messages':records}

class Reply:
    def __init__(self,obj):self.obj=obj
    def execute(self):return self.obj
class GmailMessages:
    def __init__(self,tids):self.tids=tids
    def list(self,**kwargs):
        assert kwargs['q']=='in:sent newer_than:21d'
        return Reply({'messages':[{'threadId':tid,'id':'1111111111111111'}
                                   for tid in self.tids]})
class GmailThreads:
    def __init__(self,rows):self.rows=rows
    def get(self,**kwargs):
        assert kwargs['format']=='full'
        return Reply(self.rows[kwargs['id']])
class GmailUsers:
    def __init__(self,tids,rows):self.tids=tids;self.rows=rows
    def messages(self):return GmailMessages(self.tids)
    def threads(self):return GmailThreads(self.rows)
class FakeService:
    def __init__(self,rows):self.rows=rows
    def users(self):return GmailUsers(list(self.rows),self.rows)

def known_source():
    old,_=inputs()
    row=old['threads'][0]
    row['last_inbound_at']='2026-10-09T18:00:00Z'
    row['last_inbound_message_id']='bbbbbbbbbbbbbbbb'
    row['last_outbound_at']='2026-10-09T17:00:00Z'
    row['last_outbound_message_id']='cccccccccccccccc'
    return old

def test_automatically_discovers_two_way_known_and_unlinked_unknown():
    source=known_source()
    rows={TID:thread(), UNKNOWN:thread(UNKNOWN,'prospectivebuyer.example')}
    r=discover(FakeService(rows),source,now=NOW)
    assert r['checked_thread_count']==2
    assert r['known_buyer_threads']==1
    assert r['unlinked_review_count']==1
    by={x['thread_id']:x for x in r['candidates']}
    linked=by[TID]
    assert linked['entity_key']=='lead-smart'
    assert linked['provider_auth_dmarc_aligned']
    assert linked['recognized_events'][0]['event_code']=='RECORDING_ENABLED_REPORTED'
    assert linked['recognized_events'][0]['evidence_grade']=='EMAIL_REPORTED_UNVERIFIED'
    assert by[UNKNOWN]['entity_key'] is None
    assert by[UNKNOWN]['status']=='NEW_DOMAIN_REQUIRES_IDENTITY_REVIEW'
    assert not r['outbound_authorized']
    assert 'sam@' not in json.dumps(r)
    assert 'Recordings are enabled' not in json.dumps(r)

def unaddressed_reply():
    candidate=thread()
    candidate['messages'][1]['payload']['headers'][0]['value']='other@leadsmartinc.com'
    return candidate

@pytest.mark.parametrize('row',[
    thread(aligned=False),
    thread(domain='gmail.com'),
    thread(one_way=True),
    unaddressed_reply(),
])
def test_dmarc_fail_free_domain_one_way_and_unaddressed_inbound_are_not_linked(row):
    r=discover(FakeService({TID:row}),known_source(),now=NOW)
    assert r['known_buyer_threads']==0
    assert r['unlinked_review_count']==0
    assert r['candidates']==[]

def test_existing_thread_not_reread_or_duplicated():
    source=known_source()
    source['threads'][0]['gmail_thread_id']=TID
    r=discover(FakeService({TID:thread()}),source,now=NOW)
    assert r['candidate_thread_count']==0

def attach(old,index,discovery):
    index['discovery']=discovery
    return refreshed_summary(old,index,now=NOW)[0]

def test_admitted_known_thread_is_monitorable_and_unknown_only_goes_to_review():
    old,index=inputs()
    original=old['threads'][0]
    original.update(last_inbound_at='2026-10-09T18:00:00Z',
                    last_inbound_message_id='bbbbbbbbbbbbbbbb',
                    last_outbound_at='2026-10-09T17:00:00Z',
                    last_outbound_message_id='cccccccccccccccc')
    discovery=discover(
        FakeService({TID:thread(), UNKNOWN:thread(UNKNOWN,'prospectivebuyer.example')}),
        old,now=NOW,
    )
    result=attach(old,index,discovery)
    new=next(x for x in result['threads'] if x.get('gmail_thread_id')==TID)
    assert new['automatic_discovery_link'] is True
    assert new['entity_key']=='lead-smart'
    assert new['buyer_signal_events'][0]['event_code']=='RECORDING_ENABLED_REPORTED'
    assert TID in result['partial_updated_thread_ids']
    review=result['buyer_new_thread_review']
    assert len(review)==1
    assert review[0]['thread_id']==UNKNOWN
    assert review[0]['status']=='REVIEW_IDENTITY_NO_SEND'
    assert all(not x['outbound_authorized'] for x in review)
    queue=reconcile(result,{'candidate_count':0,'candidates':[]},
                    {'shortlisted_count':0,'targets':[]},now=NOW,
                    do_not_pursue_domains=frozenset())
    assert queue['new_engaged_buyer_identity_review_count']==1
    assert queue['new_engaged_buyer_identity_review_queue'][0]['domain']=='prospectivebuyer.example'
    assert all(x['execution_authority']=='NONE' for x in queue['new_engaged_buyer_identity_review_queue'])
    buyer=next(x for x in queue['relationships'] if x['entity_key']=='lead-smart')
    assert any(x['event_code']=='RECORDING_ENABLED_REPORTED'
               for x in buyer['automatically_recognized_buyer_events'])
    assert buyer['recognized_buyer_events_are_verified'] is False
    assert buyer['outbound_authorized'] is False
    assert queue['outbound_authorized'] is False

def test_conflicted_discovery_identity_fails_closed():
    old,index=inputs()
    original=old['threads'][0]
    original.update(last_inbound_at='2026-10-09T18:00:00Z',
                    last_inbound_message_id='bbbbbbbbbbbbbbbb',
                    last_outbound_at='2026-10-09T17:00:00Z',
                    last_outbound_message_id='cccccccccccccccc')
    d=discover(FakeService({TID:thread()}),old,now=NOW)
    d['candidates'][0]['entity_key']='another-company'
    with pytest.raises(RelationshipEvidenceError,match='IDENTITY_CONFLICT'):
        attach(old,index,d)


def test_auto_linked_thread_is_polled_and_updated_again_next_cycle():
    old,index=inputs()
    old['threads'][0].update(last_inbound_at='2026-10-09T18:00:00Z',
                            last_inbound_message_id='bbbbbbbbbbbbbbbb',
                            last_outbound_at='2026-10-09T17:00:00Z',
                            last_outbound_message_id='cccccccccccccccc')
    discovery=discover(FakeService({TID:thread()}),old,now=NOW)
    linked=attach(old,index,discovery)
    assert len(linked['threads'])==len(old['threads'])+1
    follow=deepcopy(index)
    follow.pop('discovery',None)
    follow['threads'].append({
        "thread_id":TID,
        "partner":"Lead Smart",
        "truncated":False,"message_count":2,
        "messages":[
            {"id":"1111111111111111","date":"2026-10-10T11:51:00",
             "from":"Phil <flavag83@gmail.com>","labels":["SENT"]},
            {"id":"2222222222222222","date":"2026-10-10T11:51:01",
             "from":"sam@leadsmartinc.com","labels":["INBOX"],
             "recognized_codes":["RECORDING_ENABLED_REPORTED"]},
        ],
    })
    updated,summary=refreshed_summary(linked,follow,now=NOW)
    rows=[r for r in updated['threads'] if r['gmail_thread_id']==TID]
    assert len(rows)==1
    assert rows[0]['automatic_discovery_link'] is True
    assert rows[0]['buyer_signal_events'][0]['event_code']=="RECORDING_ENABLED_REPORTED"
    assert TID in updated['partial_updated_thread_ids']
    assert summary['known_threads_checked']==len(index['threads'])+1
    assert not summary['outbound_authorized']


def test_source_is_unchanged_if_spoofed_new_discovery_identity_conflicts():
    old,index=inputs()
    old['threads'][0].update(last_inbound_at='2026-10-09T18:00:00Z',
                            last_inbound_message_id='bbbbbbbbbbbbbbbb',
                            last_outbound_at='2026-10-09T17:00:00Z',
                            last_outbound_message_id='cccccccccccccccc')
    original=deepcopy(old)
    discovery=discover(FakeService({TID:thread()}),old,now=NOW)
    discovery['candidates'][0]['provider_auth_dmarc_aligned']=False
    with pytest.raises(RelationshipEvidenceError,match='IDENTITY'):
        attach(old,index,discovery)
    assert old==original


def test_sponsored_placements_only_reply_is_not_a_performance_publisher(tmp_path):
    from scripts.reconcile_buyer_email_relationships import annotate_new_engaged_commercial_roles
    from empire_os.buyer_mail_semantics import classify_visible_claims
    text="Hi Phil, We only do sponsored posts, guest posts, and link placements in existing content as part of collaborations."
    assert "PUBLISHER_SPONSORED_PLACEMENTS_ONLY_REPORTED" in classify_visible_claims(text)
    current=thread(UNKNOWN,"roofpitch.net")
    raw=base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")
    current['messages'][1]['payload']['body']['data']=raw
    old,index=inputs()
    report=discover(FakeService({UNKNOWN:current}),old,now=NOW)
    assert report["known_buyer_threads"]==0
    refreshed=attach(old,index,report)
    item=refreshed["buyer_new_thread_review"][0]
    assert item["status"]=="HOLD_PAID_PLACEMENTS_ONLY_NO_PERFORMANCE_CONTACT"
    assert item["reported_constraint"]=="SPONSORED_PLACEMENTS_ONLY_REPORTED"
    queue=reconcile(refreshed,{"candidate_count":0,"candidates":[]},
                    {"shortlisted_count":0,"targets":[]},now=NOW,
                    do_not_pursue_domains=frozenset())
    assert queue["new_engaged_buyer_identity_review_count"]==1
    path=tmp_path/"docs/commercial/PUBLISHER_SUPPLY_RECRUITMENT_EVIDENCE_20261010.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "schema_version":"empire.publisher_supply_recruitment_evidence.v1",
        "items":[{"domain":"roofpitch.net","company":"RoofPitch.net",
                  "role":"TRAFFIC_SUPPLY_HYPOTHESIS"}]
    }))
    annotate_new_engaged_commercial_roles(queue,root=tmp_path)
    assert queue["new_engaged_buyer_identity_review_count"]==0
    assert queue["new_engaged_publisher_supply_review_count"]==1
    reviewed=queue["new_engaged_publisher_supply_review_queue"][0]
    assert reviewed["next_action"]=="HOLD_PERFORMANCE_PARTNERSHIP_NO_REPEAT_EMAIL"
    assert not reviewed["publisher_supply_accepted"]
    assert not reviewed["buyer_demand_verified"]
    assert not reviewed["outbound_authorized"]
