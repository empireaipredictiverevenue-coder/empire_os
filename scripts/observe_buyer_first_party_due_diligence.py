#!/usr/bin/env python3
"""Automatic first-party legal/contact link audit on existing buyer scout.

OBSERVE-only. Four domains and seven same-host pages per domain maximum per
cycle, daily cache, independently revisited holds, no emails or new timer.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import fcntl
import json
import os
from pathlib import Path
import tempfile
import time
from hashlib import sha256
from typing import Any, Callable

from empire_os.buyer_first_party_due_diligence import (
    DueDiligenceError,MAX_DOMAINS_PER_CYCLE,MAX_HISTORY_DOMAINS,
    RESULT_TTL_SECONDS,RECHECK_SECONDS,HOLD_RECHECK_SECONDS,
    observe_domain,verified_observation_holds,
)
from empire_os.buyer_network_research_rotation import accepted_domain

ROOT=Path('/srv/empire_os')
SOURCE='founder_shortlist_latest.json'
OUTPUT='due_diligence_latest.json'
LOCK='due_diligence.lock'


def _read(path:Path,max_bytes:int)->tuple[dict[str,Any],str]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size>max_bytes:
        raise DueDiligenceError('due_diligence_source_missing_or_unsafe')
    raw=path.read_bytes()
    try:
        data=json.loads(raw.decode('utf-8'))
    except (ValueError,UnicodeError) as exc:
        raise DueDiligenceError('due_diligence_source_unreadable') from exc
    if not isinstance(data,dict):
        raise DueDiligenceError('due_diligence_source_invalid')
    return data,sha256(raw).hexdigest()


def _save(path:Path,payload:dict[str,Any]):
    if path.is_symlink():
        raise DueDiligenceError('due_diligence_output_symlink')
    raw=(json.dumps(payload,sort_keys=True,indent=2)+'\n').encode('utf-8')
    descriptor,temp=tempfile.mkstemp(dir=path.parent,prefix='.due_diligence_')
    try:
        os.fchmod(descriptor,0o600)
        with os.fdopen(descriptor,'wb') as handle:
            handle.write(raw)
            handle.flush();os.fsync(handle.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)


def _due(shortlist:list[dict[str,Any]],existing:dict[str,dict[str,Any]],now:float,
         max_domains:int)->list[str]:
    selectable=[]
    seen=set()
    for row in shortlist:
        if not isinstance(row,dict):continue
        domain=str(row.get('domain') or '').lower().strip()
        if not accepted_domain(domain) or domain in seen:
            continue
        seen.add(domain)
        prev=existing.get(domain)
        if prev:
            observed=float(prev.get('observed_epoch') or 0)
            last_check=max(observed,float(prev.get('last_recheck_unavailable_epoch') or 0))
            age=now-last_check
            cooldown=HOLD_RECHECK_SECONDS if prev.get('state') in ('EVIDENCE_HOLD','UNAVAILABLE') else RECHECK_SECONDS
            if age<cooldown and age>=0:
                continue
            last=float(prev.get('observed_epoch') or 0)
        else:
            last=0.0
        priority=row.get('founder_priority')
        priority=priority if type(priority) is int else 0
        selectable.append((0 if last==0 else 1,last,-priority,domain))
    selectable.sort()
    return [x[3] for x in selectable[:max_domains]]


def run(*,root:Path=ROOT,plan_only:bool=False,max_domains:int=MAX_DOMAINS_PER_CYCLE,
        fetch_observer:Callable[...,dict[str,Any]]=observe_domain,
        now_epoch:float|None=None)->dict[str,Any]:
    if type(max_domains) is not int or not 1<=max_domains<=MAX_DOMAINS_PER_CYCLE:
        raise DueDiligenceError('invalid_due_diligence_batch_bound')
    root=Path(root).resolve()
    base=root/'runtime/buyer_network_intelligence'
    if base.is_symlink() or not base.is_dir():
        raise DueDiligenceError('due_diligence_runtime_directory_missing')
    now=now_epoch if now_epoch is not None else time.time()
    source,initial_hash=_read(base/SOURCE,2_500_000)
    shortlist=source.get('shortlist')
    if not isinstance(shortlist,list) or len(shortlist)>500 or source.get('shortlist_count')!=len(shortlist):
        raise DueDiligenceError('due_diligence_invalid_shortlist')
    old={}
    if (base/OUTPUT).exists():
        previous,_=_read(base/OUTPUT,2_000_000)
        # Enforce the trust/schema contract instead of discarding old holds.
        verified_observation_holds(previous,now_epoch=now)
        for item in previous['observations']:
            if isinstance(item,dict) and accepted_domain(str(item.get('domain') or '')):
                old[item['domain']]=item
    selected=_due(shortlist,old,now,max_domains)
    if plan_only:
        return {'status':'PLAN_ONLY','mode':'OBSERVE','selected_domains':selected,
                'planned_domain_count':len(selected),'network_fetch_performed':False,
                'files_written':0,'outbound_sent':False,'execution_authority':'none'}
    observations=[]
    if selected:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures={pool.submit(fetch_observer,domain,now_epoch=now):domain
                     for domain in selected}
            for future in concurrent.futures.as_completed(futures):
                domain=futures[future]
                try:
                    value=future.result()
                    if not isinstance(value,dict) or value.get('domain')!=domain:
                        raise DueDiligenceError('due_diligence_observer_contract_invalid')
                except Exception:
                    # Fail closed, preserving old known holds rather than writing a
                    # fabricated absence of critical-link violations.
                    value={
                        'domain':domain,'observed_epoch':now,
                        'observed_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(now)),
                        'state':'UNAVAILABLE','home':{'status':'UNAVAILABLE'},
                        'checked_links':[],'critical_broken_links':[],
                        'outbound_authorized':False,'execution_authority':'none',
                    }
                observations.append(value)
    # An unavailable recheck must never erase previously verified broken links.
    for row in observations:
        domain=row['domain']
        previous=old.get(domain)
        if previous and previous.get('critical_broken_links'):
            unresolved=[]
            checks={(x.get('category'),x.get('url')):x.get('http_status')
                    for x in row.get('checked_links',[]) if isinstance(x,dict)}
            for gap in previous['critical_broken_links']:
                # An automatically held site only recovers when the previously
                # broken first-party URL itself now responds successfully.
                # Removing the terms/contact link or timing out is not proof.
                status=checks.get((gap['category'],gap['url']))
                if status is None or not 200<=status<300:
                    unresolved.append(gap)
            if unresolved:
                previous['last_recheck_unavailable_epoch']=now
                if row.get('home',{}).get('status')=='PASS':
                    # Keep the historical HTTP 404 proof, while the current
                    # page's missing link is a pending explicit review task.
                    previous['latest_recheck_home_sha256']=row['home'].get('body_sha256')
                continue
        old[domain]=row
    current={str(row.get('domain') or '') for row in shortlist if isinstance(row,dict)}
    retained=[row for domain,row in old.items() if domain in current
              and (row.get('critical_broken_links') or
                   0<=now-float(row.get('observed_epoch') or 0)<=RESULT_TTL_SECONDS)]
    retained.sort(key=lambda row:(-float(row.get('observed_epoch') or 0),row['domain']))
    retained=retained[:MAX_HISTORY_DOMAINS]
    payload={
        'schema_version':'empire.buyer_due_diligence.v1',
        'generated_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(now)),
        'mode':'OBSERVE','source_shortlist_sha256':initial_hash,
        'selected_domain_count':len(selected),'selected_domains':selected,
        'observed_domain_count':len(retained),
        'new_checks_performed':len(observations),
        'observations':retained,
        'outbound_sent':False,'outbound_authorized':False,'db_write':False,
        'signups_performed':False,'traffic_activated':False,'execution_authority':'none',
    }
    holds=verified_observation_holds(payload,now_epoch=now)
    payload['automated_evidence_hold_count']=len(holds)
    payload['automated_evidence_hold_domains']=sorted(holds)
    _,ending_hash=_read(base/SOURCE,2_500_000)
    if ending_hash!=initial_hash:
        raise DueDiligenceError('due_diligence_shortlist_changed_during_probe')
    _save(base/OUTPUT,payload)
    return {'status':'PASS','mode':'OBSERVE',
            'selected_domains':selected,
            'new_checks_performed':len(observations),
            'retained_evidence_count':len(retained),
            'automated_evidence_hold_count':len(holds),
            'automated_evidence_hold_domains':sorted(holds),
            'files_written':1,'outbound_sent':False,'execution_authority':'none'}


def main()->int:
    cli=argparse.ArgumentParser()
    cli.add_argument('--plan-only',action='store_true')
    cli.add_argument('--max-domains',type=int,default=MAX_DOMAINS_PER_CYCLE)
    args=cli.parse_args()
    base=ROOT/'runtime/buyer_network_intelligence'
    if base.is_symlink() or not base.is_dir():
        print(json.dumps({'status':'BLOCKED','reason':'unsafe_runtime_location'}))
        return 2
    if args.plan_only:
        try:
            result=run(plan_only=True,max_domains=args.max_domains)
        except (DueDiligenceError,OSError,ValueError) as exc:
            print(json.dumps({'status':'BLOCKED','reason':str(exc)[:100],
                              'outbound_sent':False,'execution_authority':'none'}))
            return 2
        print(json.dumps(result,sort_keys=True))
        return 0
    lock=base/LOCK
    if lock.is_symlink():
        print(json.dumps({'status':'BLOCKED','reason':'unsafe_lock_location'}))
        return 2
    descriptor=os.open(lock,os.O_RDWR|os.O_CREAT,0o600)
    with os.fdopen(descriptor,'a+') as handle:
        try:
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({'status':'ALREADY_RUNNING','mode':'OBSERVE'}))
            return 2
        try:
            result=run(plan_only=args.plan_only,max_domains=args.max_domains)
        except (DueDiligenceError,OSError,ValueError) as exc:
            print(json.dumps({'status':'BLOCKED','reason':str(exc)[:100],
                              'outbound_sent':False,'execution_authority':'none'}))
            return 2
        finally:
            fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
