#!/usr/bin/env python3
"""Read-only multi-desk campaign research queue for EXISTING marketing_growth.

No agent, crawler, timer, credentials, DB, customer record, public HTTP,
marketing spend, campaign send, publishing, indexing or file output.
Candidate scores reflect research priority, NEVER ranking likelihood/revenue.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'docs/marketing/ORGANIC_GROWTH_DEPARTMENT_RESEARCH_PORTFOLIO_20261016.json'
ALLOWED_FIELDS=('fit','source','commercial_readiness','distribution_access','time_to_test')
WEIGHTS=(30,25,20,15,10)
MAX_COUNT=16
ALLOWED_STATES={'RESEARCH_ONLY'}

class EvidenceHold(ValueError):
    pass


def validate_and_prioritize(packet: dict)->dict:
    if not isinstance(packet,dict):raise EvidenceHold('invalid_portfolio')
    if packet.get('parent_department')!='marketing_growth' or packet.get('mode')!='OBSERVE' or packet.get('execution_authority')!='NONE':
        raise EvidenceHold('unapproved_department_or_execution_authority')
    if packet.get('canonical_database')!='EmpireDB PostgreSQL' or packet.get('no_new_agent_server_timer_database_or_external_spend') is not True:
        raise EvidenceHold('wrong_database_or_unapproved_infrastructure')
    desks=packet.get('specialist_desks')
    if not isinstance(desks,list) or len(desks)<7 or len(desks)>12:raise EvidenceHold('department_desk_count_invalid')
    desk_keys={x.get('key') for x in desks if isinstance(x,dict)}
    if len(desk_keys)!=len(desks) or any(not x.get('owner') for x in desks):raise EvidenceHold('missing_or_duplicate_desk_owners')
    candidates=packet.get('research_candidates')
    if not isinstance(candidates,list) or not 1<=len(candidates)<=MAX_COUNT:
        raise EvidenceHold('unsafe_portfolio_count')
    results=[];seen=set()
    for c in candidates:
        if not isinstance(c,dict):raise EvidenceHold('malformed_campaign')
        identifier=c.get('id')
        if not isinstance(identifier,str) or not identifier.startswith('GROWTH-') or identifier in seen:
            raise EvidenceHold('duplicate_or_invalid_campaign_id')
        seen.add(identifier)
        if c.get('status') not in ALLOWED_STATES or not isinstance(c.get('holds'),list) or not c['holds']:
            raise EvidenceHold('unreviewed_publication_or_missing_holds')
        if c.get('risk') not in range(1,6):raise EvidenceHold('risk_not_scored')
        raw=[]
        for key in ALLOWED_FIELDS:
            n=c.get(key)
            if type(n) is not int or n not in range(1,6):raise EvidenceHold('invalid_score:'+key)
            raw.append(n)
        if not isinstance(c.get('search_hypotheses'),list) or not c['search_hypotheses'] or any(not isinstance(q,str) or not q.strip() for q in c['search_hypotheses']):
            raise EvidenceHold('missing_search_intent_hypothesis')
        sources=c.get('data_sources')
        if not isinstance(sources,list) or not sources:raise EvidenceHold('unreferenced_campaign')
        for s in sources:
            v=urlsplit(s if isinstance(s,str) else '')
            if v.scheme!='https' or not v.hostname or v.username or v.password or v.fragment:
                raise EvidenceHold('untrusted_source_reference')
        url=c.get('existing_url')
        if url is not None:
            p=urlsplit(url)
            if p.scheme!='https' or p.hostname!='empire-ai.co.uk' or p.query or p.fragment or p.username or p.password:
                raise EvidenceHold('unapproved_public_url')
        # Weighted strategic research triage ONLY; never a volume, ranking,
        # buyer-acceptance, conversion, or predicted revenue signal.
        score=sum(w*n for w,n in zip(WEIGHTS,raw))//5
        # Risk is a review-order modifier, not a permit or legal advice.
        score=max(0,score - 3*(c['risk']-1))
        tier='P1_VALIDATE_FIRST' if score>=77 else 'P2_RESEARCH' if score>=61 else 'P3_HOLD_AND_MONITOR'
        results.append({'campaign_id':identifier,'title':c['title'],'segment':c['segment'],
                        'current_live_url':url,'research_priority_score_not_ranking_probability':score,
                        'research_priority':tier,'status':'RESEARCH_ONLY',
                        'demand_volume_verified':False,'search_position_verified':False,
                        'external_ai_citation_verified':False,'accepted_buyer_or_revenue_verified':False,
                        'missing_evidence_gates':c['holds'],'source_count':len(sources),
                        'next_handoff':'existing_market_intelligence_strategist_SERP_AND_GSC_RESEARCH'})
    results.sort(key=lambda x:(-x['research_priority_score_not_ranking_probability'],x['campaign_id']))
    return {
        'schema_version':'empire.marketing_growth.search_department.portfolio_review.v1',
        'status':'RESEARCH_DEPARTMENT_PORTFOLIO_REVIEWED_NOT_ACTIVATED',
        'canonical_department':'marketing_growth','operating_mode':'OBSERVE',
        'desk_count':len(desks),'campaign_count':len(results),
        'campaigns':results,'budget_gbp':0,'production_write':False,
        'credentials_read':False,'external_requests':False,
        'outbound_or_publication_performed':False,
        'campaigns_approved_to_launch':0,'founder_gate_bypassed':False,
        'rankings_or_organic_click_growth_claimed':False,
        'primary_existing_owner':'marketing_director',
        'handoff':'existing_marketing_agency_department_cycle_REVIEW_ONLY',
        'score_disclaimer':'Research order only. No validated search volume, ranking, lead, revenue or executable campaign approval.'
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-only',action='store_true',required=True)
    args=parser.parse_args()
    if not args.review_only:parser.error('observe only')
    try:
        packet=json.loads(MANIFEST.read_text(encoding='utf-8'))
        result=validate_and_prioritize(packet)
    except (OSError,ValueError,TypeError) as exc:
        result={'status':'EVIDENCE_HOLD','error':type(exc).__name__,
                'production_write':False,'execution_authority':'NONE'}
        print(json.dumps(result,sort_keys=True))
        raise SystemExit(2)
    print(json.dumps(result,sort_keys=True,indent=2))

if __name__=='__main__':main()
