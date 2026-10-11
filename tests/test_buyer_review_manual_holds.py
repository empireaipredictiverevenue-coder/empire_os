"""Independent public due-diligence hold survives automated scout refresh."""
from __future__ import annotations
import importlib.util
import json
import time
from pathlib import Path
import pytest

from empire_os.buyer_review_holds import BuyerReviewHoldError, load_review_holds
from scripts.build_buyer_qualification_actions import plan

ROOT=Path(__file__).resolve().parents[1]


def _holds(path:Path,domains=('paymyreferral.com',)):
    path.parent.mkdir(parents=True,exist_ok=True)
    rows=[{'domain':domain,'state':'HOLD','review_required':True,
           'reason_code':'FIRST_PARTY_LEGAL_CONTACT_LINKS_HTTP_404',
           'observed_on':'2026-10-09',
           'evidence_urls':['https://'+domain+'/terms'],
           'resolution_condition':'Review valid terms and contact route'} for domain in domains]
    path.write_text(json.dumps({'schema_version':'empire.buyer_network_manual_holds.v1','holds':rows}))
    return path


def _maker():
    path=ROOT/'scripts/materialize_buyer_network_founder_review_packets.py'
    spec=importlib.util.spec_from_file_location('buyer_review_manual_test',path)
    mod=importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _maker_inputs(folder:Path,domains=('paymyreferral.com','astoriacompany.com')):
    folder.mkdir(parents=True,exist_ok=True)
    json.dump({'runs':[{'query':'buyer-network-active-verification','domains':list(domains)}]},
              (folder/'discovery_latest.json').open('w'))
    evidence={'publisher_program':True,'active_demand':True,'economics':True,
              'contactable':True,'integration':True,'compliance':True,'negative_program':False}
    json.dump({'verifications':[{'domain':d,'evidence':evidence} for d in domains]},
              (folder/'verification_latest.json').open('w'))
    json.dump({'candidates':[{'domain':d,'status':'READY_TO_APPROACH','score':99,
                              'evidence':evidence,'verticals':['home_services']} for d in domains]},
              (folder/'candidate_queue_latest.json').open('w'))
    due={'schema_version':'empire.buyer_due_diligence.v1','mode':'OBSERVE',
         'outbound_sent':False,'execution_authority':'none',
         'observations':[{
            'domain':domain,'observed_epoch':time.time(),
            'observed_at':'2026-10-09T21:00:00+00:00',
            'state':'NEEDS_FOUNDER_REVIEW',
            'home':{'url':'https://'+domain+'/','status':'PASS','http_status':200},
            'checked_links':[],'critical_broken_links':[],
            'outbound_authorized':False,
         } for domain in domains]}
    (folder/'due_diligence_latest.json').write_text(json.dumps(due))


def test_durable_repo_hold_is_verified():
    existing=load_review_holds(ROOT/'config/buyer_network_manual_review_holds.json')
    assert 'paymyreferral.com' in existing
    assert existing['paymyreferral.com']['review_required'] is True


def test_first_party_manual_hold_applies_to_materializer_main(tmp_path,monkeypatch,capsys):
    mod=_maker()
    base=tmp_path/'runtime/buyer_network_intelligence'
    _maker_inputs(base)
    config=_holds(tmp_path/'config/buyer_network_manual_review_holds.json')
    monkeypatch.setattr(mod,'HOLDS',config)
    for var,file in [('DUE_DILIGENCE','due_diligence_latest.json'),('DISCOVERY','discovery_latest.json'),('VERIFICATION','verification_latest.json'),
                     ('QUEUE','candidate_queue_latest.json'),('PACKETS','founder_review_packets_latest.json'),
                     ('PACKETS_MD','founder_review_packets_latest.md'),('BACKLOG','verification_backlog_latest.json')]:
        monkeypatch.setattr(mod,var,base/file)
    mod.main()
    summary=json.loads(capsys.readouterr().out)
    assert summary['manual_hold_count']==1
    assert summary['trusted_ready_count']==1
    assert summary['trusted_ready_domains']==['astoriacompany.com']
    artifacts=json.loads((base/'founder_review_packets_latest.json').read_text())
    assert artifacts['trusted_ready_count']==1
    assert artifacts['manual_hold_domains']==['paymyreferral.com']
    assert all(row['domain']!='paymyreferral.com' for row in artifacts['packets'])
    backlog=json.loads((base/'verification_backlog_latest.json').read_text())
    held=next(item for item in backlog['candidates'] if item['domain']=='paymyreferral.com')
    assert held['status']=='MANUAL_EVIDENCE_HOLD'
    assert held['outbound_authority'] is False
    assert held['reasons']==['manual_hold:FIRST_PARTY_LEGAL_CONTACT_LINKS_HTTP_404']


def test_invalid_config_does_not_overwrite_existing_packets(tmp_path,monkeypatch):
    mod=_maker()
    base=tmp_path/'runtime/buyer_network_intelligence'
    _maker_inputs(base,('paymyreferral.com',))
    config=tmp_path/'config/buyer_network_manual_review_holds.json'
    config.parent.mkdir()
    config.write_text('not json')
    monkeypatch.setattr(mod,'HOLDS',config)
    for var,file in [('DUE_DILIGENCE','due_diligence_latest.json'),('DISCOVERY','discovery_latest.json'),('VERIFICATION','verification_latest.json'),
                     ('QUEUE','candidate_queue_latest.json'),('PACKETS','founder_review_packets_latest.json'),
                     ('PACKETS_MD','founder_review_packets_latest.md'),('BACKLOG','verification_backlog_latest.json')]:
        monkeypatch.setattr(mod,var,base/file)
    target=base/'founder_review_packets_latest.json'
    target.write_text('ORIGINAL_UNTOUCHED')
    with pytest.raises(BuyerReviewHoldError,match='unreadable'):
        mod.main()
    assert target.read_text()=='ORIGINAL_UNTOUCHED'


def test_qualification_tier_stays_manual_hold_even_when_prior_packet_stale(tmp_path):
    from tests.test_buyer_qualification_actions import _case
    base=_case(tmp_path)
    _holds(tmp_path/'config/buyer_network_manual_review_holds.json',('publisheralpha.example.com',))
    report=plan(tmp_path)
    assert report['trusted_founder_review_count']==0
    assert report['manual_evidence_hold_count']==1
    held=next(row for row in report['targets'] if row['domain']=='publisheralpha.example.com')
    assert held['tier']=='MANUAL_EVIDENCE_HOLD'
    assert held['manual_hold_reason']=='FIRST_PARTY_LEGAL_CONTACT_LINKS_HTTP_404'
    assert held['outbound_authorized'] is False
    assert report['targets'][-1]['domain']==held['domain']


def test_bad_hold_cannot_change_external_domain_or_bypass_policy(tmp_path):
    path=_holds(tmp_path/'holds.json')
    raw=json.loads(path.read_text())
    raw['holds'][0]['evidence_urls']=['https://unrelated.com/terms']
    path.write_text(json.dumps(raw))
    with pytest.raises(BuyerReviewHoldError,match='source_invalid'):
        load_review_holds(path)


def test_symlink_and_missing_hold_policy_fail_closed(tmp_path):
    path=_holds(tmp_path/'valid.json')
    link=tmp_path/'linked.json';link.symlink_to(path)
    with pytest.raises(BuyerReviewHoldError,match='missing_or_unsafe'):
        load_review_holds(link)
    with pytest.raises(BuyerReviewHoldError,match='missing_or_unsafe'):
        load_review_holds(tmp_path/'not-here.json')


def test_automated_broken_legal_link_blocks_first_party_packet(tmp_path,monkeypatch,capsys):
    """Even fully corroborated buyer sites cannot bypass independent 404 proof."""
    mod=_maker()
    base=tmp_path/'runtime/buyer_network_intelligence'
    _maker_inputs(base,('paymyreferral.com','astoriacompany.com'))
    config=_holds(tmp_path/'config/buyer_network_manual_review_holds.json',())
    due_file=base/'due_diligence_latest.json'
    due=json.loads(due_file.read_text())
    row=next(x for x in due['observations'] if x['domain']=='paymyreferral.com')
    row['state']='EVIDENCE_HOLD'
    row['checked_links']=[{'category':'terms','url':'https://paymyreferral.com/terms',
                           'status':'HTTP_ERROR','http_status':404}]
    row['critical_broken_links']=[{'category':'terms','url':'https://paymyreferral.com/terms',
                                   'http_status':404}]
    due_file.write_text(json.dumps(due))
    monkeypatch.setattr(mod,'HOLDS',config)
    for var,file in [('DUE_DILIGENCE','due_diligence_latest.json'),('DISCOVERY','discovery_latest.json'),
                     ('VERIFICATION','verification_latest.json'),('QUEUE','candidate_queue_latest.json'),
                     ('PACKETS','founder_review_packets_latest.json'),('PACKETS_MD','founder_review_packets_latest.md'),
                     ('BACKLOG','verification_backlog_latest.json')]:
        monkeypatch.setattr(mod,var,base/file)
    mod.main()
    summary=json.loads(capsys.readouterr().out)
    assert summary['manual_hold_count']==0
    assert summary['automated_evidence_hold_count']==1
    assert summary['trusted_ready_domains']==['astoriacompany.com']
    backlog=json.loads((base/'verification_backlog_latest.json').read_text())
    held=next(x for x in backlog['candidates'] if x['domain']=='paymyreferral.com')
    assert held['status']=='AUTOMATED_EVIDENCE_HOLD'
    assert held['outbound_authority'] is False
    assert held['reasons']==['automated_hold:FIRST_PARTY_CRITICAL_LINK_HTTP_404_OR_410']


def test_missing_due_diligence_never_promotes_ready_buyer(tmp_path,monkeypatch,capsys):
    mod=_maker()
    base=tmp_path/'runtime/buyer_network_intelligence'
    _maker_inputs(base,('astoriacompany.com',))
    (base/'due_diligence_latest.json').unlink()
    config=_holds(tmp_path/'config/buyer_network_manual_review_holds.json',())
    monkeypatch.setattr(mod,'HOLDS',config)
    for var,file in [('DUE_DILIGENCE','due_diligence_latest.json'),('DISCOVERY','discovery_latest.json'),
                     ('VERIFICATION','verification_latest.json'),('QUEUE','candidate_queue_latest.json'),
                     ('PACKETS','founder_review_packets_latest.json'),('PACKETS_MD','founder_review_packets_latest.md'),
                     ('BACKLOG','verification_backlog_latest.json')]:
        monkeypatch.setattr(mod,var,base/file)
    mod.main()
    result=json.loads(capsys.readouterr().out)
    assert result['trusted_ready_count']==0
    assert result['due_diligence_pending_count']==1
    backlog=json.loads((base/'verification_backlog_latest.json').read_text())
    assert backlog['candidates'][0]['status']=='DUE_DILIGENCE_PENDING'


def test_corrupted_due_snapshot_does_not_overwrite_founder_packets(tmp_path,monkeypatch):
    from empire_os.buyer_first_party_due_diligence import DueDiligenceError
    mod=_maker()
    base=tmp_path/'runtime/buyer_network_intelligence'
    _maker_inputs(base,('astoriacompany.com',))
    due=base/'due_diligence_latest.json'
    due.write_text('{corrupted snapshot')
    config=_holds(tmp_path/'config/buyer_network_manual_review_holds.json',())
    monkeypatch.setattr(mod,'HOLDS',config)
    for var,file in [('DUE_DILIGENCE','due_diligence_latest.json'),('DISCOVERY','discovery_latest.json'),
                     ('VERIFICATION','verification_latest.json'),('QUEUE','candidate_queue_latest.json'),
                     ('PACKETS','founder_review_packets_latest.json'),('PACKETS_MD','founder_review_packets_latest.md'),
                     ('BACKLOG','verification_backlog_latest.json')]:
        monkeypatch.setattr(mod,var,base/file)
    original=base/'founder_review_packets_latest.json'
    original.write_text('DONT_OVERWRITE_REVIEW_PACKET')
    with pytest.raises(DueDiligenceError,match='invalid'):
        mod.main()
    assert original.read_text()=='DONT_OVERWRITE_REVIEW_PACKET'

def test_founder_do_not_pursue_source_contains_verified_restrictions():
    from empire_os.buyer_review_holds import do_not_pursue_domains, is_do_not_pursue_domain
    holds = load_review_holds(ROOT / 'config/buyer_network_manual_review_holds.json')
    row = holds['callvox.pro']
    assert row['do_not_pursue'] is True
    assert row['blocked_recipients'] == ('partners@callvox.pro',)
    assert row['review_required'] is True
    assert is_do_not_pursue_domain('www.callvox.pro')
    assert not is_do_not_pursue_domain('polyares.com')
    assert do_not_pursue_domains() == frozenset({'callvox.pro'})


def test_invalid_policy_flag_fails_closed(tmp_path):
    path = _holds(tmp_path / 'holds.json')
    payload = json.loads(path.read_text())
    payload['holds'][0]['do_not_pursue'] = 'false'
    path.write_text(json.dumps(payload))
    with pytest.raises(BuyerReviewHoldError, match='exclusion_invalid'):
        load_review_holds(path)
