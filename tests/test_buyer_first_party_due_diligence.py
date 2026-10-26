"""First-party contract evidence, broken links and automatic scout hold proofs."""
from __future__ import annotations
import json
import time
from pathlib import Path

import pytest

from empire_os.buyer_first_party_due_diligence import (
    DueDiligenceError, MAX_LINKS, category_for_link,
    linked_first_party_pages,load_due_diligence,observe_domain,
    safe_page_url,verified_observation_holds,
)
from scripts import observe_buyer_first_party_due_diligence as cycle

DOMAIN='paymyreferral.com'
MAIN_HTML='''<html><body><h1>Company</h1>
<a href="/terms">Terms of Service</a>
<a href="/privacy">Privacy Policy</a>
<a href="/compliance">TCPA Compliance</a>
<a href="/marketplace-rules">Marketplace Quality Guidelines</a>
<a href="/contact">Contact Us</a>
<a href="https://evil.example.org/terms">Third-party terms</a>
<a href="http://127.0.0.1/admin">localhost API</a>
<a href="mailto:buyer@example.org">Mail us</a>
<form action="/signup" method="POST"><input name="email"></form>
</body></html>'''


def make_fetch(*,broken=True,missing=False,empty=False):
    calls=[]
    def fake(domain,url):
        calls.append((domain,url))
        if url=='https://'+domain+'/':
            return {'url':url,'status':'PASS','http_status':200,
                    'body_sha256':'h'*64,'_html':('no links' if empty else MAIN_HTML)}
        if missing:
            return {'url':url,'status':'UNAVAILABLE','http_status':None}
        if broken and urlsplit_path(url) in ('/terms','/compliance','/contact','/marketplace-rules'):
            return {'url':url,'status':'HTTP_ERROR','http_status':404}
        return {'url':url,'status':'PASS','http_status':200,'body_sha256':'b'*64,
                '_html':'example body including private@example.org should never be stored'}
    return fake,calls


def urlsplit_path(url):
    from urllib.parse import urlsplit
    return urlsplit(url).path


def test_first_party_link_classification_observes_only_actual_page_links():
    links=linked_first_party_pages(DOMAIN,MAIN_HTML)
    assert [item['category'] for item in links]==[
        'terms','privacy','compliance','rules','contact'
    ]
    assert len(links)<=MAX_LINKS
    assert not any('evil' in x['url'] or '127.0.0.1' in x['url'] for x in links)
    assert category_for_link('Publisher API documentation','/docs')=='integration'
    assert safe_page_url(DOMAIN,'https://evil.example.org/terms') is None
    assert safe_page_url(DOMAIN,'https://127.0.0.1/admin') is None
    assert safe_page_url(DOMAIN,'javascript:alert(1)') is None
    assert safe_page_url(DOMAIN,'mailto:buyer@example.org') is None
    assert safe_page_url(DOMAIN,'/terms?private=customer-email@example.org')=='https://paymyreferral.com/terms'


def test_linked_broken_term_is_evidence_hold_not_approved_buyer():
    fetch,calls=make_fetch()
    row=observe_domain(DOMAIN,fetch=fetch,now_epoch=100_000.)
    assert len(calls)==6
    assert row['state']=='EVIDENCE_HOLD'
    assert row['home']['status']=='PASS'
    assert {x['category'] for x in row['critical_broken_links']}=={'terms','compliance','rules','contact'}
    assert row['payout_economics_contract_verified'] is False
    assert row['source_compliance_contract_verified'] is False
    assert row['outbound_authorized'] is False
    assert 'private@example.org' not in json.dumps(row)
    report={'schema_version':'empire.buyer_due_diligence.v1','mode':'OBSERVE',
            'execution_authority':'none','outbound_sent':False,'observations':[row]}
    holds=verified_observation_holds(report,now_epoch=100_100.)
    assert holds[DOMAIN]['reason_code']=='FIRST_PARTY_CRITICAL_LINK_HTTP_404_OR_410'
    assert holds[DOMAIN]['review_required'] is True


def test_good_http_pages_still_require_independent_terms_and_founder_review():
    fetch,_=make_fetch(broken=False)
    row=observe_domain(DOMAIN,fetch=fetch,now_epoch=100_000.)
    assert row['state']=='NEEDS_FOUNDER_REVIEW'
    assert row['critical_broken_links']==[]
    for key in ('programme_currently_accepting_verified', 'integration_verified',
                'payout_economics_contract_verified','source_compliance_contract_verified',
                'terms_and_data_use_approved','outbound_authorized'):
        assert row[key] is False


def test_report_requires_actual_404_or_410_page_proofs(tmp_path):
    fetch,_=make_fetch()
    row=observe_domain(DOMAIN,fetch=fetch,now_epoch=100_000.)
    report={'schema_version':'empire.buyer_due_diligence.v1','mode':'OBSERVE',
            'execution_authority':'none','outbound_sent':False,'observations':[row]}
    source=tmp_path/'due_diligence_latest.json';source.write_text(json.dumps(report))
    rows,holds=load_due_diligence(source,now_epoch=100_200.)
    assert rows[DOMAIN]['freshness']=='CURRENT'
    assert rows[DOMAIN]['broken_critical_links']==4
    assert len(holds)==1
    # Stale information remains a HOLD, rather than silently disappearing.
    rows,holds=load_due_diligence(source,now_epoch=100_000.+8*86400)
    assert rows[DOMAIN]['freshness']=='STALE'
    assert DOMAIN in holds
    report['observations'][0]['checked_links']=[]
    source.write_text(json.dumps(report))
    with pytest.raises(DueDiligenceError,match='proof_missing'):
        load_due_diligence(source,now_epoch=100_100.)


def test_unavailable_home_page_is_not_false_positive_or_clearance():
    def unavailable(domain,url):
        return {'url':url,'status':'UNAVAILABLE','http_status':None}
    row=observe_domain(DOMAIN,fetch=unavailable,now_epoch=1000.)
    assert row['state']=='UNAVAILABLE'
    assert row['checked_links']==[]
    assert row['outbound_authorized'] is False


def _runner_fixture(root:Path,domains=(DOMAIN,'px.com')):
    base=root/'runtime/buyer_network_intelligence'
    base.mkdir(parents=True,exist_ok=True)
    shortlist=[{'domain':name,'founder_priority':100-i}
               for i,name in enumerate(domains)]
    (base/cycle.SOURCE).write_text(json.dumps({'shortlist_count':len(shortlist),'shortlist':shortlist}))
    return base


def test_one_existing_scout_cycle_writes_private_proof_and_caches(tmp_path):
    base=_runner_fixture(tmp_path)
    fetch,calls=make_fetch()
    def observer(domain,*,now_epoch):
        return observe_domain(domain,fetch=fetch,now_epoch=now_epoch)
    preview=cycle.run(root=tmp_path,plan_only=True,fetch_observer=observer,now_epoch=100_000.)
    assert preview['network_fetch_performed'] is False
    assert len(preview['selected_domains'])==2
    assert calls==[]
    assert not (base/cycle.OUTPUT).exists()
    first=cycle.run(root=tmp_path,fetch_observer=observer,now_epoch=100_000.)
    assert first['new_checks_performed']==2
    assert first['automated_evidence_hold_count']==2
    path=base/cycle.OUTPUT
    assert path.stat().st_mode & 0o777==0o600
    saved=json.loads(path.read_text())
    assert saved['outbound_sent'] is False
    assert saved['execution_authority']=='none'
    first_calls=len(calls)
    second=cycle.run(root=tmp_path,fetch_observer=observer,now_epoch=100_000.+60)
    assert second['new_checks_performed']==0
    assert len(calls)==first_calls


def test_unavailable_or_removed_link_cannot_clear_hold(tmp_path):
    base=_runner_fixture(tmp_path,domains=(DOMAIN,))
    original,_=make_fetch()
    cycle.run(root=tmp_path,fetch_observer=lambda d,*,now_epoch:
              observe_domain(d,fetch=original,now_epoch=now_epoch),now_epoch=100_000.)
    def unavailable(d,*,now_epoch):
        return {'domain':d,'observed_epoch':now_epoch,'state':'UNAVAILABLE',
                'home':{'status':'UNAVAILABLE'},'critical_broken_links':[],
                'checked_links':[],'outbound_authorized':False}
    next_run=cycle.run(root=tmp_path,fetch_observer=unavailable,
                       now_epoch=100_000.+7*3600)
    assert next_run['automated_evidence_hold_count']==1
    empty,_=make_fetch(empty=True)
    removed=cycle.run(root=tmp_path,fetch_observer=lambda d,*,now_epoch:
                      observe_domain(d,fetch=empty,now_epoch=now_epoch),
                      now_epoch=100_000.+14*3600)
    assert removed['automated_evidence_hold_count']==1
    saved=json.loads((base/cycle.OUTPUT).read_text())
    assert saved['observations'][0]['state']=='EVIDENCE_HOLD'
    good,_=make_fetch(broken=False)
    recovered=cycle.run(root=tmp_path,fetch_observer=lambda d,*,now_epoch:
                        observe_domain(d,fetch=good,now_epoch=now_epoch),
                        now_epoch=100_000.+21*3600)
    assert recovered['automated_evidence_hold_count']==0
    saved=json.loads((base/cycle.OUTPUT).read_text())
    assert saved['observations'][0]['state']=='NEEDS_FOUNDER_REVIEW'
    assert saved['observations'][0]['outbound_authorized'] is False


def test_automatic_selection_never_exceeds_eight_domains(tmp_path):
    domains=['buyer'+str(i)+'.com' for i in range(15)]
    _runner_fixture(tmp_path,domains=domains)
    result=cycle.run(root=tmp_path,plan_only=True,max_domains=8,now_epoch=100_000.)
    assert len(result['selected_domains'])==8
    assert result['network_fetch_performed'] is False
    with pytest.raises(DueDiligenceError,match='batch_bound'):
        cycle.run(root=tmp_path,plan_only=True,max_domains=9)
    from empire_os.buyer_first_party_due_diligence import MAX_HISTORY_DOMAINS
    assert MAX_HISTORY_DOMAINS >= 131


def test_source_race_fails_before_writing_snapshot(tmp_path):
    base=_runner_fixture(tmp_path,domains=(DOMAIN,))
    fetch,_=make_fetch()
    def malicious_simulated_race(domain,*,now_epoch):
        p=base/cycle.SOURCE
        d=json.loads(p.read_text());d['marker']='someone_else_updated'
        p.write_text(json.dumps(d))
        return observe_domain(domain,fetch=fetch,now_epoch=now_epoch)
    with pytest.raises(DueDiligenceError,match='changed_during_probe'):
        cycle.run(root=tmp_path,fetch_observer=malicious_simulated_race,now_epoch=100_000.)
    assert not (base/cycle.OUTPUT).exists()


def test_observed_policy_keywords_do_not_turn_into_contract_approvals():
    from empire_os.buyer_first_party_due_diligence import observed_topics
    html='<p>Publisher payouts require TCPA consent and API integration.</p><script>Artificial intelligence</script><p>Artificial intelligence data restrictions.</p>'
    topics=observed_topics(html)
    assert 'PAYOUT_LANGUAGE' in topics
    assert 'CONSENT_LANGUAGE' in topics
    assert 'INTEGRATION_LANGUAGE' in topics
    assert 'AI_OR_ML_DATA_TERMS_LANGUAGE' in topics
    fetch,_=make_fetch(broken=False)
    row=observe_domain(DOMAIN,fetch=fetch,now_epoch=1000.)
    assert row['keyword_topics_are_verified_terms'] is False
    assert row['payout_economics_contract_verified'] is False
    assert row['terms_and_data_use_approved'] is False


def test_first_party_partial_capture_remains_review_only():
    def partial(domain,url):
        if url=='https://'+domain+'/':
            return {'url':url,'status':'PARTIAL_PASS','http_status':200,
                    'body_sha256':'p'*64,'capture_truncated':True,
                    '_html':'<a href="/terms">Terms of Service</a>'}
        return {'url':url,'status':'PASS','http_status':200,'body_sha256':'q'*64,
                'capture_truncated':False,'_html':'<p>Official terms</p>'}
    row=observe_domain(DOMAIN,fetch=partial,now_epoch=1000.)
    assert row['state']=='NEEDS_FOUNDER_REVIEW'
    assert row['home']['capture_truncated'] is True
    assert row['outbound_authorized'] is False
    report={'schema_version':'empire.buyer_due_diligence.v1','mode':'OBSERVE',
            'execution_authority':'none','outbound_sent':False,'observations':[row]}
    assert row['critical_broken_links']==[]
    assert verified_observation_holds(report,now_epoch=1100.)=={}


def test_legacy_placeholder_telemetry_excluded_without_erasing_valid_hold(tmp_path):
    base=_runner_fixture(tmp_path,domains=(DOMAIN,))
    fetch,_=make_fetch(broken=True)
    legit=observe_domain(DOMAIN,fetch=fetch,now_epoch=100_000.)
    unwanted={**legit,'domain':'company.com','state':'UNAVAILABLE',
              'home':{'status':'UNAVAILABLE'},'checked_links':[],
              'critical_broken_links':[]}
    original={'schema_version':'empire.buyer_due_diligence.v1',
              'mode':'OBSERVE','execution_authority':'none','outbound_sent':False,
              'observations':[legit,unwanted]}
    path=base/cycle.OUTPUT
    path.write_text(json.dumps(original))
    planned=cycle.run(root=tmp_path,plan_only=True,now_epoch=100_100.)
    assert planned['status']=='PLAN_ONLY'
    assert 'company.com' in path.read_text()  # plan never rewrites source
    outcome=cycle.run(root=tmp_path,now_epoch=100_100.)
    assert outcome['automated_evidence_hold_count']==1
    next_report=json.loads(path.read_text())
    assert [x['domain'] for x in next_report['observations']]==[DOMAIN]
    assert next_report['excluded_invalid_legacy_domains']==['company.com']
    assert next_report['prior_report_sha256']
    assert next_report['outbound_sent'] is False


def test_legacy_invalid_domain_with_critical_hold_fails_closed(tmp_path):
    base=_runner_fixture(tmp_path,domains=(DOMAIN,))
    fetch,_=make_fetch(broken=True)
    row=observe_domain(DOMAIN,fetch=fetch,now_epoch=100_000.)
    row={**row,'domain':'company.com'}
    p=base/cycle.OUTPUT
    content=json.dumps({'schema_version':'empire.buyer_due_diligence.v1',
              'mode':'OBSERVE','execution_authority':'none','outbound_sent':False,
              'observations':[row]})
    p.write_text(content)
    with pytest.raises(DueDiligenceError,match='observation_invalid'):
        cycle.run(root=tmp_path,plan_only=True,now_epoch=100_100.)
    assert p.read_text()==content


def test_timestamp_only_shortlist_rotation_keeps_first_party_evidence(tmp_path):
    base=_runner_fixture(tmp_path,domains=(DOMAIN,))
    fetch,_=make_fetch()
    def concurrent_timestamp_refresh(domain,*,now_epoch):
        p=base/cycle.SOURCE
        snapshot=json.loads(p.read_text())
        snapshot['generated_at']='2026-10-26T15:04:00+00:00'
        p.write_text(json.dumps(snapshot))
        return observe_domain(domain,fetch=fetch,now_epoch=now_epoch)
    result=cycle.run(
        root=tmp_path,
        fetch_observer=concurrent_timestamp_refresh,
        now_epoch=100_000.,
    )
    assert result['status']=='PASS'
    saved=json.loads((base/cycle.OUTPUT).read_text())
    assert saved['timestamp_only_source_refresh_accepted'] is True
    assert len(saved['end_source_shortlist_sha256'])==64
    assert saved['observations'][0]['domain']==DOMAIN
    assert saved['outbound_sent'] is False
    assert saved['traffic_activated'] is False
