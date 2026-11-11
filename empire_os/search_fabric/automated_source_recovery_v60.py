"""Autonomous original Search Fabric first-party evidence recovery (OBSERVE).

Read-only original EmpireDB input, bounded public-only official-website reads,
new-only/atomic runtime receipts. Zero customer contact, score change, CRM
promotion, lead import, paid search, entity merge or revenue declaration.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any,Mapping
from urllib.parse import urlsplit,urlunsplit
import ipaddress,json,os,re,time,uuid

SCHEMA='empire.search_fabric.original_automated_source_recovery.v60'
MAX_SCAN=400
MAX_VERIFY=12
COOLDOWN_DAYS=7
AGENT='EmpireSearchFabricEvidence/1.0 (+https://empire-ai.co.uk)'


def _host(url:str)->str:
    try:
        u=urlsplit(url)
        if (u.scheme not in ('http','https') or u.username or u.password
            or u.port not in (None,80,443) or u.query or u.fragment):
            return ''
        h=(u.hostname or '').strip('.').lower()
        if (not h or '.' not in h or h.endswith('.local')
            or h.endswith('.internal') or h in ('localhost','localhost.localdomain')):
            return ''
        try:ipaddress.ip_address(h);return ''
        except ValueError:pass
        if not re.fullmatch(r'[a-z0-9.-]{4,253}',h):return ''
        return h
    except (ValueError,TypeError):return ''


def acceptable_url(value:Any)->str:
    raw=str(value or '').strip()
    if len(raw)>400 or not raw:return ''
    if '://' not in raw:raw='https://'+raw
    if not _host(raw):return ''
    u=urlsplit(raw)
    # Only use root website for a bounded first-party check, never arbitrary
    # API or user-controlled query URLs from historical data.
    return urlunsplit((u.scheme,u.netloc.lower(),'/', '', ''))


def _norm(value:Any)->str:
    return ' '.join(re.findall(r'[a-z0-9]+',str(value or '').casefold()))

_SUFFIXES={'llc','ltd','limited','inc','incorporated','corp','corporation','co','company','plc'}

def business_name_overlap(original:Any,published:list[str])->bool:
    target=tuple(t for t in _norm(original).split() if t not in _SUFFIXES)
    if len(target)<1 or sum(len(t) for t in target)<5:
        return False
    for raw in published[:20]:
        tokens=tuple(t for t in _norm(raw).split() if t not in _SUFFIXES)
        if tokens and target==tokens:return True
    return False


def number_observation_matches(original:Any,observations:list[str])->bool:
    source=re.sub(r'\D','',str(original or ''))
    if len(source)<10:return False
    for value in observations[:20]:
        phone=re.sub(r'\D','',str(value or ''))
        if len(phone)>=10 and phone[-10:]==source[-10:]:return True
    return False


def classify_site(*,website:str,business_name:Any,phone:Any,result:Mapping[str,Any])->dict[str,Any]:
    host=_host(website)
    final=_host(str(result.get('final_url') or ''))
    if result.get('ok') is not True:
        status='SITE_PROBE_FAILED'
    elif not host or not final or final.removeprefix('www.')!=host.removeprefix('www.'):
        status='SITE_REDIRECT_IDENTITY_HOLD'
    elif not business_name_overlap(business_name,list(result.get('business_names') or [])):
        status='FIRST_PARTY_NAME_NOT_CORROBORATED'
    elif number_observation_matches(phone,list(result.get('phones') or [])):
        status='FIRST_PARTY_NAME_AND_PHONE_OBSERVED_REVIEW_ONLY'
    else:status='FIRST_PARTY_BUSINESS_NAME_OBSERVED_REVIEW_ONLY'
    return {'research_status':status,'first_party_company_name_correlated':status in (
            'FIRST_PARTY_NAME_AND_PHONE_OBSERVED_REVIEW_ONLY',
            'FIRST_PARTY_BUSINESS_NAME_OBSERVED_REVIEW_ONLY'),
            'first_party_phone_last_ten_observed':status=='FIRST_PARTY_NAME_AND_PHONE_OBSERVED_REVIEW_ONLY',
            'legal_company_verified':False,'buyer_or_contact_permission_verified':False,
            'first_party_evidence_candidate_only':True}


def normalize_state(raw:Any)->dict:
    if not isinstance(raw,dict) or raw.get('schema_version')!=SCHEMA:
        return {'schema_version':SCHEMA,'next_cursor':None,'domain_attempts':{},'cycles':0}
    cursor=raw.get('next_cursor')
    if cursor is not None:
        cursor=str(uuid.UUID(str(cursor)))
    attempts=raw.get('domain_attempts') or {}
    if not isinstance(attempts,dict) or len(attempts)>40000:
        raise ValueError('SOURCE_RECOVERY_STATE_UNTRUSTED')
    cleaned={}
    for host,stamp in attempts.items():
        if (type(host) is not str or not re.fullmatch(r'[a-z0-9.-]{4,253}',host)
            or type(stamp) is not str or len(stamp)>50):
            raise ValueError('SOURCE_RECOVERY_STATE_UNTRUSTED')
        dt=datetime.fromisoformat(stamp.replace('Z','+00:00'))
        if dt.tzinfo is None:raise ValueError('SOURCE_RECOVERY_STATE_UNTRUSTED')
        cleaned[host]=dt.astimezone(timezone.utc).isoformat()
    cycles=raw.get('cycles',0)
    if type(cycles) is not int or not 0<=cycles<=10000000:
        raise ValueError('SOURCE_RECOVERY_STATE_UNTRUSTED')
    return {'schema_version':SCHEMA,'next_cursor':cursor,'domain_attempts':cleaned,'cycles':cycles}


def select_candidates(rows:list[Mapping[str,Any]],state:dict,*,now:datetime,max_verify:int)->tuple[list[dict],dict]:
    if (now.tzinfo is None or type(max_verify) is not int or not 0<=max_verify<=MAX_VERIFY
        or len(rows)>MAX_SCAN):raise ValueError('UNBOUNDED_SEARCH_FABRIC_SOURCE_SELECTION')
    next_state=normalize_state(state)
    selected=[];seen=set();latest=next_state['next_cursor']
    for row in rows:
        if max_verify and len(selected)>=max_verify:
            break  # Never skip rows beyond the actual website verification budget.
        key=str(uuid.UUID(str(row['id'])))
        latest=key
        site=acceptable_url(row.get('website'))
        if not site:continue
        host=_host(site).removeprefix('www.')
        if host in seen:continue
        seen.add(host)
        prior=next_state['domain_attempts'].get(host)
        if prior and now-datetime.fromisoformat(prior)<timedelta(days=COOLDOWN_DAYS):
            continue
        if len(selected)>=max_verify:continue
        # Prefer only source gaps. Never probe a complete identity-linked and
        # already-v2-scored record just to increase request numbers.
        gaps=[]
        if not row.get('has_acquisition'):gaps.append('MISSING_ACCEPTED_ACQUISITION_PROVENANCE')
        if not row.get('has_entity_link'):gaps.append('MISSING_VERIFIED_ENTITY_LINK')
        if not row.get('v2_scored'):gaps.append('V2_NOT_YET_SCORED_DIFFERENT_OWNER')
        if not row.get('niche'):gaps.append('MISSING_TAXONOMY')
        if not gaps:continue
        selected.append({'prospect_id':key,'website':site,'business_name':row.get('business_name'),
                         'phone':row.get('phone'),'research_gaps':gaps})
    next_state['next_cursor']=latest
    return selected,next_state


def source_recovery_cycle(*,rows:list[Mapping[str,Any]],state:dict,now:datetime,
       max_verify:int,probe,permission_check,clock=time.monotonic,
       time_budget_seconds:float=100)->tuple[dict,dict]:
    if not 15<=time_budget_seconds<=180:raise ValueError('UNBOUNDED_SOURCE_CYCLE_BUDGET')
    started=clock()
    selected,nxt=select_candidates(rows,state,now=now,max_verify=max_verify)
    results=[];counts=Counter();attempted=set()
    for item in selected:
        if clock()-started>time_budget_seconds:
            counts['SKIPPED_TIME_BUDGET']+=len(selected)-len(results);break
        site=item['website'];host=_host(site).removeprefix('www.')
        try:
            permission=permission_check(site)
            if permission is not True:
                observation={'research_status':'SOURCE_RIGHTS_OR_ROBOTS_HOLD',
                             'legal_company_verified':False,
                             'buyer_or_contact_permission_verified':False}
            else:
                # Original SSRF-safe public-only website observation module.
                raw=probe(site,max_pages=1,request_timeout=5,
                          time_budget_seconds=9,public_only=True)
                observation=classify_site(website=site,business_name=item['business_name'],
                                         phone=item['phone'],result=raw)
        except Exception:
            observation={'research_status':'PUBLIC_SITE_PROBE_EXCEPTION_REVIEW',
                         'legal_company_verified':False,
                         'buyer_or_contact_permission_verified':False}
        status=observation['research_status'];counts[status]+=1
        # Private receipt stores only canonical UUID and boolean evidence,
        # never name/email/phone/website or raw scraped HTML/contact lists.
        results.append({'prospect_id':item['prospect_id'],'research_status':status,
              'source_hostname_sha256':sha256(host.encode()).hexdigest(),
              'missing_prior_evidence':item['research_gaps'],
              'first_party_company_name_correlated':observation.get('first_party_company_name_correlated',False),
              'first_party_phone_last_ten_observed':observation.get('first_party_phone_last_ten_observed',False),
              'legal_company_verified':False,'buyer_or_contact_permission_verified':False})
        attempted.add(host)
        nxt['domain_attempts'][host]=now.astimezone(timezone.utc).isoformat()
    # Selected-but-unattempted official websites must be retried next cycle;
    # never advance the live scan cursor beyond the last attempted candidate.
    if len(results)<len(selected):
        nxt['next_cursor']=(results[-1]['prospect_id'] if results
                            else state.get('next_cursor'))
    # Trim expired attempts to prevent infinitely growing state and allow
    # future retries. Unsuccessful rights checks receive the same cooldown.
    cutoff=now-timedelta(days=COOLDOWN_DAYS)
    nxt['domain_attempts']={k:v for k,v in nxt['domain_attempts'].items()
                  if datetime.fromisoformat(v)>=cutoff}
    nxt['cycles']+=1
    report={'schema_version':SCHEMA,
       'mode':'AUTONOMOUS_ORIGINAL_SEARCH_FABRIC_EVIDENCE_RECOVERY_OBSERVE',
       'observed_at_utc':now.astimezone(timezone.utc).isoformat(),
       'scanned_existing_prospect_rows':len(rows),
       'source_websites_selected':len(selected),
       'official_sites_attempted':len(results),
       'research_status_counts':dict(sorted(counts.items())),
       'review_only_prospect_evidence':results,
       'cursor_advanced':nxt['next_cursor']!=state.get('next_cursor'),
       'state_cycle_count':nxt['cycles'],
       'next_action':'CONTINUE_PRIORITY_SOURCE_RECOVERY_IN_EXISTING_SEARCH_FABRIC',
       'raw_contacts_serialized':False,'legal_entities_promoted':0,
       'new_prospects_created':0,'new_outbound_sent':0,'paid_search_requests':0,
       'brave_requests':0,'database_writes':False,
       'payment_authorized':False,'buyer_demand_inferred':False}
    return report,nxt
