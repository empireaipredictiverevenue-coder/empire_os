#!/usr/bin/env python3
"""Turn existing buyer-network evidence into a founder-owned qualification queue.

NO discovery crawl, network request, vendor action, email, phone call, DB write,
contact admission, skill approval, offer acceptance, payment, or extra timer.
Only existing snapshots from EmpireOS are read; the optional private artifact
is created under runtime/buyer_network_intelligence on explicit --write.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from empire_os.buyer_review_holds import load_review_holds

ROOT = Path('/srv/empire_os')
BASE = Path('runtime/buyer_network_intelligence')
SOURCES = {
    'shortlist': 'founder_shortlist_latest.json',
    'packets': 'founder_review_packets_latest.json',
    'direct_site': 'direct_site_verification_latest.json',
    'queue': 'candidate_queue_latest.json',
}
MAX_BYTES = 2_500_000
DOMAIN = re.compile(r'^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$')
EVIDENCE_TASKS = {
    'verify_payout_economics': 'Check official payout amount, currency, unit, timing and source; public use of the word payout is not an accepted rate.',
    'verify_compliance_requirements': 'Verify current first-party publisher consent, jurisdiction, privacy and call/lead data obligations.',
    'verify_tracking_or_integration': 'Verify first-party integration method, required fields, test procedure, routing and attribution.',
    'verify_contact_or_application_path': 'Verify a current first-party business contact or publisher application path without contacting anyone.',
    'verify_active_buyer_demand': 'Verify a live accepting-buyer or publisher programme and matching sector, not just broad marketing copy.',
    'verify_publisher_acceptance': 'Confirm the programme currently accepts new qualified traffic partners or publishers.',
}


class BuyerPriorityError(ValueError):
    pass


def _domain(value: Any) -> str:
    raw = str(value or '').lower().strip().rstrip('.')
    if not DOMAIN.fullmatch(raw) or len(raw)>253:
        return ''
    try:
        ipaddress.ip_address(raw)
    except ValueError:
        pass
    else:
        return ''
    if raw.endswith(('.local','.internal','.test','.example','.invalid','.localhost')):
        return ''
    return raw


def _snapshots(root: Path):
    loaded = {}
    hashes = {}
    for key,filename in SOURCES.items():
        path = root/BASE/filename
        if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_BYTES:
            raise BuyerPriorityError('missing_or_unsafe_'+key+'_snapshot')
        raw = path.read_bytes()
        try:
            obj=json.loads(raw.decode('utf-8'))
        except (UnicodeError, ValueError) as exc:
            raise BuyerPriorityError('invalid_'+key+'_snapshot') from exc
        if not isinstance(obj,dict):
            raise BuyerPriorityError('invalid_'+key+'_payload')
        loaded[key]=obj
        hashes[key]=sha256(raw).hexdigest()
    return loaded,hashes


def plan(root: Path = ROOT) -> dict[str,Any]:
    root=Path(root).resolve()
    snapshots, hashes = _snapshots(root)
    holds = load_review_holds(root/'config/buyer_network_manual_review_holds.json')
    shortlist=snapshots['shortlist'].get('shortlist')
    packets=snapshots['packets'].get('packets')
    queued=snapshots['queue'].get('candidates')
    site=snapshots['direct_site'].get('results')
    if not all(isinstance(x,list) for x in (shortlist,packets,queued,site)):
        raise BuyerPriorityError('invalid_candidate_collections')
    if len(shortlist)>500 or len(packets)>500 or len(queued)>50000 or len(site)>10000:
        raise BuyerPriorityError('candidate_count_exceeds_contract')
    if (snapshots['shortlist'].get('shortlist_count')!=len(shortlist)
        or snapshots['packets'].get('trusted_ready_count')!=len(packets)
        or snapshots['queue'].get('candidate_count')!=len(queued)):
        raise BuyerPriorityError('inconsistent_source_counts')
    current_domains={_domain(x.get('domain')) for x in queued if isinstance(x,dict)}
    current_domains.discard('')
    verified_packets={}
    for item in packets:
        if not isinstance(item,dict):continue
        domain=_domain(item.get('domain'))
        if (domain and domain in current_domains and item.get('authority')=='FOUNDER_REVIEW_ONLY'
            and item.get('outbound_authority') is False
            and item.get('active_verification') is True
            and item.get('buyer_role_corroborated') is True):
            verified_packets[domain]=item
    sites={_domain(x.get('domain')): x for x in site
           if isinstance(x,dict) and _domain(x.get('domain'))}
    actions=[]
    seen=set()
    gap_totals=Counter()
    for item in shortlist:
        if not isinstance(item,dict):continue
        domain=_domain(item.get('domain'))
        if not domain or domain in seen or domain not in current_domains:continue
        seen.add(domain)
        manual_hold = holds.get(domain)
        is_founder_review = domain in verified_packets and manual_hold is None
        gaps=[g for g in item.get('evidence_gaps',[])
              if isinstance(g,str) and g in EVIDENCE_TASKS] if isinstance(item.get('evidence_gaps'),list) else []
        gaps=list(dict.fromkeys(gaps))
        if not is_founder_review and not gaps:
            gaps=['independent_buyer_review_evidence']
        gap_totals.update(gaps)
        direct=sites.get(domain) or {}
        score=item.get('founder_priority')
        score=score if type(score) is int and 0<=score<=100 else 0
        actions.append({
            'domain':domain,
            'tier':('MANUAL_EVIDENCE_HOLD' if manual_hold is not None
                    else 'FOUNDER_REVIEW_ONLY' if is_founder_review
                    else 'EVIDENCE_RECOVERY'),
            'manual_hold_reason':manual_hold['reason_code'] if manual_hold is not None else None,
            'manual_hold_resolution_condition':(
                manual_hold['resolution_condition'] if manual_hold is not None else None
            ),
            'queue_status':str(item.get('queue_status') or 'WATCH')[:50],
            'founder_priority':score,
            'verticals':[v for v in item.get('verticals',[]) if isinstance(v,str) and len(v)<50][:8],
            'site_corroborated_buyer_role':direct.get('buyer_role') is True and direct.get('corroborated') is True,
            'site_evidence_flags':{k: bool(v) for k,v in (direct.get('evidence') or {}).items()
                                   if k in ('active_demand','publisher_program','integration','economics','compliance','contactable','negative_program') and type(v) is bool},
            'review_source':'founder_review_packets_latest.json' if is_founder_review else 'founder_shortlist_latest.json',
            'missing_evidence':gaps,
            'next_evidence_actions':[EVIDENCE_TASKS.get(g,
                'Independent commercial evidence and founder-review confirmation required.') for g in gaps],
            'commercial_terms_verified':False,
            'canonical_contact_or_reply_verified':False,
            'outbound_authorized':False,
            'mailbox_send_provisioned':False,
            'actual_revenue':False,
        })
    order={'FOUNDER_REVIEW_ONLY':0,'EVIDENCE_RECOVERY':1,'MANUAL_EVIDENCE_HOLD':2}
    actions.sort(key=lambda x:(order[x['tier']],-x['founder_priority'],x['domain']))
    # Reject stale mixed-source races. A scheduler might replace its snapshots
    # concurrently; do not promote an optimistic partial report.
    _,after_hashes=_snapshots(root)
    if hashes!=after_hashes:
        raise BuyerPriorityError('source_snapshots_changed_during_read')
    return {
        'schema_version':'empire.buyer_qualification_actions.v1',
        'generated_at':datetime.now(timezone.utc).isoformat(),
        'mode':'OBSERVE','execution_authority':'none',
        'source_sha256':hashes,
        'network_candidate_count':len(current_domains),
        'shortlisted_count':len(actions),
        'trusted_founder_review_count':sum(x['tier']=='FOUNDER_REVIEW_ONLY' for x in actions),
        'manual_evidence_hold_count':sum(x['tier']=='MANUAL_EVIDENCE_HOLD' for x in actions),
        'contact_verified_for_outbound_count':0,
        'outbound_sent':False,'outbound_enabled':False,
        'human_review_required':True,'buyer_conversation_verified':False,
        'gap_counts':dict(gap_totals),
        'targets':actions,
    }


def save_private(root:Path,report:dict[str,Any])->Path:
    directory=Path(root).resolve()/BASE
    if directory.is_symlink() or not directory.is_dir():
        raise BuyerPriorityError('unsafe_output_directory')
    target=directory/'founder_qualification_actions_latest.json'
    if target.is_symlink():raise BuyerPriorityError('unsafe_output_symlink')
    content=(json.dumps(report,indent=2,sort_keys=True)+'\n').encode('utf-8')
    fd,tmp=tempfile.mkstemp(prefix='.qualification_actions_',dir=directory)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'wb') as output:
            output.write(content)
            output.flush();os.fsync(output.fileno())
        os.replace(tmp,target)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return target


def main() -> int:
    import argparse
    parser=argparse.ArgumentParser(description='Summarize existing qualified buyer evidence without outreach')
    parser.add_argument('--write',action='store_true',help='Update one read-only private founder qualification artifact')
    args=parser.parse_args()
    try:
        report=plan()
        if args.write:
            save_private(ROOT,report)
    except (BuyerPriorityError,OSError,ValueError) as exc:
        print(json.dumps({'status':'BLOCKED','reason':str(exc),
                          'outbound_enabled':False,'execution_authority':'none'}))
        return 2
    print(json.dumps({'status':'PASS','mode':report['mode'],
        'network_candidate_count':report['network_candidate_count'],
        'shortlisted_count':report['shortlisted_count'],
        'trusted_founder_review_count':report['trusted_founder_review_count'],
        'manual_evidence_hold_count':report['manual_evidence_hold_count'],
        'gap_counts':report['gap_counts'],
        'target_domains_by_tier':[{'domain':x['domain'],'tier':x['tier'],
                                   'manual_hold_reason':x['manual_hold_reason'],
                                   'missing_evidence':x['missing_evidence']}
                                  for x in report['targets'][:10]],
        'written':bool(args.write),'outbound_sent':False,
        'execution_authority':'none'},sort_keys=True,indent=2))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
