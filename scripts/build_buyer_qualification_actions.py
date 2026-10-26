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
import time
from hashlib import sha256
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from empire_os.buyer_review_holds import load_review_holds
from empire_os.buyer_first_party_due_diligence import load_due_diligence
from empire_os.buyer_founder_research_decisions import load_research_decisions

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
# First-party role review prevents an industry event from being mistaken for
# a direct buyer. These specific URLs were verified on 26 October 2026.
# Role review changes only research routing; it grants no send or commercial
# authority and never overrides suppression/consent evidence.
FIRST_PARTY_ROLE_REVIEWS = {
    'contact.io': {
        'role': 'INDUSTRY_CONFERENCE_NOT_VERIFIED_LEAD_BUYER',
        'source_url': 'https://contact.io/contact-us/',
        'next_action': 'RESEARCH_EXHIBITING_BUYERS_OR_PARTNERS_SEPARATELY',
    },
    'astoriacompany.com': {
        'role': 'PUBLISHER_NETWORK_RESEARCH',
        'source_url': 'https://astoriacompany.com/publishers/sell-calls',
        'next_action': 'REVIEW_EXISTING_RELATIONSHIP_FOR_OFFER_AND_GEO_FIT',
    },
    'cre8tivemarketingllc.com': {
        'role': 'HOME_SERVICES_PUBLISHER_PROGRAMME_RESEARCH',
        'source_url': 'https://cre8tivemarketingllc.com/become-pay-per-call-publisher-home-services/',
        'next_action': 'REVIEW_EXISTING_RELATIONSHIP_FOR_PUBLISHER_PILOT',
    },
    'leadsbycall.com': {
        'role': 'PAY_PER_CALL_NETWORK_RESEARCH',
        'source_url': 'https://leadsbycall.com/faq.html',
        'next_action': 'REVIEW_EXISTING_RELATIONSHIP_FOR_PUBLISHER_PILOT',
    },
}

# Demand priority is advisory until official geo/ZIP, pricing and volume
# requirements are accepted. Never infer regional capacity from sector words.
ACTIVE_GAP_SOURCE = Path('runtime/buyer_acquisition/latest.json')
DEMAND_SOURCE_MAX_AGE_SECONDS = 2 * 3600
DIRECT_SOURCE_MAX_AGE_SECONDS = 7 * 86400
KNOWN_SECTORS = frozenset({
    'roofing', 'hvac', 'plumbing', 'restoration', 'solar',
    'painting', 'carpentry', 'electrical', 'landscaping',
    'legal', 'dental', 'general_contractor',
})


def demand_sector_priorities(payload: dict[str, Any], *, now_epoch: float) -> dict[str, dict[str, Any]]:
    """Read positive overflow only, without treating it as proof of a payer."""
    if not isinstance(payload, dict) or not isinstance(payload.get('demand_gap_queue'), list):
        return {}
    try:
        stamp = datetime.fromisoformat(str(payload['generated_at']).replace('Z', '+00:00'))
        age = now_epoch - stamp.timestamp()
    except (KeyError, ValueError, TypeError, OverflowError):
        return {}
    if not 0 <= age <= DEMAND_SOURCE_MAX_AGE_SECONDS:
        return {}
    sector_gaps: dict[str, dict[str, Any]] = {}
    for gap in payload['demand_gap_queue'][:1000]:
        if not isinstance(gap, dict) or gap.get('buyer_hunt_required') is not True:
            continue
        key = gap.get('corridor_key')
        parts = key.split(':') if isinstance(key, str) else []
        if len(parts) != 6 or parts[0:2] != ['corridor', 'v1']:
            continue
        sector = parts[2]
        if sector not in KNOWN_SECTORS or not parts[3]:
            continue
        overflow = gap.get('overflow_count')
        if type(overflow) is not int or not 0 < overflow < 100000:
            continue
        data = sector_gaps.setdefault(sector, {
            'gap_count': 0, 'overflow_count': 0, 'corridors': [],
        })
        data['gap_count'] += 1
        data['overflow_count'] += overflow
        data['corridors'].append(key)
    for data in sector_gaps.values():
        data['corridors'] = data['corridors'][:3]
    return sector_gaps


def buyer_demand_fit(
    *, verticals: list[str], site: dict[str, Any], priorities: dict[str, dict[str, Any]],
    now_epoch: float,
) -> dict[str, Any]:
    """Sector research fit only; NEVER a claim of local buyer capacity."""
    inferred = sorted(set(verticals) & priorities.keys())
    verified: list[str] = []
    try:
        observed = float(site.get('observed_epoch') or 0)
    except (TypeError, ValueError):
        observed = 0
    if (site.get('corroborated') is True
            and site.get('buyer_role') is True
            and type(site.get('pages_successful')) is int
            and site['pages_successful'] > 0
            and 0 <= now_epoch - observed <= DIRECT_SOURCE_MAX_AGE_SECONDS
            and isinstance(site.get('verticals_detected'), list)):
        verified = sorted(set(v for v in site['verticals_detected']
                              if isinstance(v, str)) & priorities.keys())
    matched = verified or inferred
    return {
        'state': ('FIRST_PARTY_SECTOR_RESEARCH_FIT' if verified else
                  'UNVERIFIED_SECTOR_RESEARCH_FIT' if inferred else
                  'NO_SECTOR_GAP_MATCH_OBSERVED'),
        'matching_sector_names': matched[:12],
        'first_party_matching_sector_names': verified[:12],
        'active_demand_gap_count': sum(priorities[x]['gap_count'] for x in matched),
        'observed_overflow_units_for_sectors': sum(priorities[x]['overflow_count'] for x in matched),
        'sample_corridors_for_research': list(dict.fromkeys(
            corridor for x in matched for corridor in priorities[x]['corridors']
        ))[:5],
        'market_or_zip_coverage_verified': False,
        'buyer_acceptance_verified': False,
        'inventory_saleable_or_revenue_verified': False,
        'next_research_action': (
            'VERIFY_BUYER_ACCEPTED_STATES_ZIPS_HOURS_AND_FORMAT_FOR_MATCHED_SECTORS'
            if matched else 'RESEARCH_FIRST_PARTY_BUYER_ROLE_AND_SERVICE_SECTOR'
        ),
    }


DISCOVERY_REQUIREMENTS = (
    'Confirm currently accepted service verticals and consumer intent',
    'Confirm states, ZIP coverage, hours and accepted inventory formats',
    'Confirm permissible first-party organic search traffic and consent requirements',
    'Agree a bounded proof-of-quality pilot with the buyer, not a volume claim',
    'Confirm connection/routing, minimum duration and attribution requirements',
    'Discuss payout, rejection rules and settlement only on the agreed product',
)


def next_commercial_action(
    *,
    contact_state: str,
    queue_status: str,
    tier: str,
    verified_role: str | None,
) -> str:
    """Pick an executable RESEARCH/review task; no implicit outbound."""
    if contact_state in {'DO_NOT_PURSUE', 'DELIVERY_HOLD',
                         'EXISTING_CONVERSATION_PARTIAL_BOUNCE'}:
        return 'NO_NEW_SEND_RECONCILE_SUPPRESSION_OR_DELIVERY'
    if verified_role == 'INDUSTRY_CONFERENCE_NOT_VERIFIED_LEAD_BUYER':
        return 'RESEARCH_RELEVANT_BUYERS_IN_EVENT_ECOSYSTEM_NO_SALES_INTRO'
    if contact_state == 'SOURCE_UNAVAILABLE':
        return 'RECONCILE_CONTACT_HISTORY_BEFORE_ANY_OUTREACH'
    if contact_state in {'EXISTING_CONVERSATION', 'FOUNDER_FORM_SUBMITTED',
                         'WORKSPACE_RECIPROCAL_THREAD_OBSERVED'}:
        return 'REVIEW_LIVE_RELATIONSHIP_AND_QUALIFY_BUYER_PILOT'
    if contact_state in {'ALREADY_CONTACTED',
                         'WORKSPACE_SENT_ALREADY_CONTACTED',
                         'FOUNDER_REVIEWED_PRIOR_GMAIL_THREAD'}:
        return 'REVIEW_PRIOR_THREAD_FOR_RESPONSE_NO_DUPLICATE_FIRST_TOUCH'
    if tier == 'FOUNDER_REVIEW_ONLY':
        return 'VERIFY_BUSINESS_CONTACT_PATH_AND_PREPARE_DISCOVERY_PROPOSAL'
    if queue_status == 'VERIFY_REQUIREMENTS':
        return 'VERIFY_FIRST_PARTY_BUYER_DEMAND_AND_DISCOVERY_CONTACT'
    return 'RESEARCH_COMPANY_ROLE_DEMAND_AND_FIRST_PARTY_CONTACT_PATH'


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
    research_decisions = load_research_decisions(root/BASE)
    now_epoch = time.time()
    demand_path = root / ACTIVE_GAP_SOURCE
    demand_hash = None
    demand_state = 'NOT_AVAILABLE_OR_UNSAFE'
    demand_priorities: dict[str, dict[str, Any]] = {}
    if (not demand_path.is_symlink() and demand_path.is_file()
            and demand_path.stat().st_size <= 2_500_000):
        raw_demand = demand_path.read_bytes()
        demand_hash = sha256(raw_demand).hexdigest()
        try:
            candidate_plan = json.loads(raw_demand)
        except (UnicodeError, ValueError):
            demand_state = 'INVALID'
        else:
            demand_priorities = demand_sector_priorities(candidate_plan, now_epoch=now_epoch)
            demand_state = 'CURRENT_RESEARCH_PRIORITIES' if demand_priorities else 'UNAVAILABLE_STALE_OR_EMPTY'
    holds = load_review_holds(root/'config/buyer_network_manual_review_holds.json')
    due_path = root/BASE/'due_diligence_latest.json'
    due_reviews, due_holds = load_due_diligence(due_path, now_epoch=time.time())
    due_hash = sha256(due_path.read_bytes()).hexdigest() if due_path.is_file() else None
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
        auto_hold = due_holds.get(domain)
        due_review = due_reviews.get(domain) or {}
        due_ready = (due_review.get('freshness') == 'CURRENT'
                     and due_review.get('homepage_reachable') is True
                     and due_review.get('state') == 'NEEDS_FOUNDER_REVIEW')
        is_founder_review = (domain in verified_packets and manual_hold is None
                             and auto_hold is None and due_ready)
        gaps=[g for g in item.get('evidence_gaps',[])
              if isinstance(g,str) and g in EVIDENCE_TASKS] if isinstance(item.get('evidence_gaps'),list) else []
        gaps=list(dict.fromkeys(gaps))
        if not is_founder_review and not gaps:
            gaps=['independent_buyer_review_evidence']
        gap_totals.update(gaps)
        direct=sites.get(domain) or {}
        sector_fit = buyer_demand_fit(
            verticals=[v for v in item.get('verticals', []) if isinstance(v, str)],
            site=direct, priorities=demand_priorities, now_epoch=now_epoch,
        )
        score=item.get('founder_priority')
        score=score if type(score) is int and 0<=score<=100 else 0
        contact = item.get('contact_history')
        contact = contact if isinstance(contact,dict) else {}
        contact_state = str(contact.get('state') or 'UNKNOWN_HISTORY')[:80]
        role_review = FIRST_PARTY_ROLE_REVIEWS.get(domain)
        tier = ('MANUAL_EVIDENCE_HOLD' if manual_hold is not None
                else 'AUTOMATED_EVIDENCE_HOLD' if auto_hold is not None
                else 'ECOSYSTEM_RESEARCH' if role_review is not None
                    and role_review['role']=='INDUSTRY_CONFERENCE_NOT_VERIFIED_LEAD_BUYER'
                else 'DUE_DILIGENCE_PENDING' if domain in verified_packets and not due_ready
                else 'FOUNDER_REVIEW_ONLY' if is_founder_review
                else 'EVIDENCE_RECOVERY')
        action = ('NO_NEW_SEND_RECONCILE_SUPPRESSION_OR_DELIVERY'
                  if manual_hold is not None or auto_hold is not None
                  else next_commercial_action(
                      contact_state=contact_state,
                      queue_status=str(item.get('queue_status') or 'WATCH'),
                      tier=tier,
                      verified_role=role_review['role'] if role_review else None))
        actions.append({
            'domain':domain,
            'tier':tier,
            'buyer_relationship_role_review':role_review['role'] if role_review else 'UNCLASSIFIED_BUYER_RESEARCH',
            'buyer_role_first_party_source':role_review['source_url'] if role_review else None,
            'contact_history_state':contact_state,
            'contact_history_next_action':str(contact.get('next_action') or 'RECONCILE_HISTORY')[:120],
            # Per-company change evidence, not email content or send authority.
            'contact_history_last_inbound_at':(
                str(contact['last_inbound_at'])[:40]
                if isinstance(contact.get('last_inbound_at'), str) else None
            ),
            'contact_history_last_outbound_at':(
                str(contact['last_outbound_at'])[:40]
                if isinstance(contact.get('last_outbound_at'), str) else None
            ),
            'contact_history_source_fresh':contact.get('gmail_snapshot_fresh') is True,
            'commercial_next_action':action,
            'active_demand_sector_research_fit':sector_fit,
            'buyer_discovery_requirements':list(DISCOVERY_REQUIREMENTS)
                if tier in {'FOUNDER_REVIEW_ONLY','EVIDENCE_RECOVERY'} else [],
            'budget_required_to_research_or_discuss_pilot':False,
            'commercial_terms_to_be_agreed_before_delivery':True,
            'buyer_relationship_accepted_or_pilot_authorized':False,
            'automated_hold_reason':auto_hold['reason_code'] if auto_hold else None,
            'first_party_due_diligence':due_review,
            'manual_hold_reason':manual_hold['reason_code'] if manual_hold is not None else None,
            'manual_hold_resolution_condition':(
                manual_hold['resolution_condition'] if manual_hold is not None else None
            ),
            'queue_status':str(item.get('queue_status') or 'WATCH')[:50],
            'founder_research_decision': ('CONTINUE_RESEARCH' if domain in research_decisions else None),
            'founder_priority':score,
            'verticals':[v for v in item.get('verticals',[]) if isinstance(v,str) and len(v)<50][:8],
            'site_corroborated_buyer_role':direct.get('buyer_role') is True and direct.get('corroborated') is True,
            'site_evidence_flags':{k: bool(v) for k,v in (direct.get('evidence') or {}).items()
                                   if k in ('active_demand','publisher_program','integration','economics','compliance','contactable','negative_program') and type(v) is bool},
            'review_source':'founder_review_packets_latest.json' if tier=='FOUNDER_REVIEW_ONLY' else 'founder_shortlist_latest.json',
            'missing_evidence':gaps,
            'next_evidence_actions':[EVIDENCE_TASKS.get(g,
                'Independent commercial evidence and founder-review confirmation required.') for g in gaps],
            'existing_first_party_source_urls': ([
                page['final_url'] for page in direct.get('pages',[])
                if isinstance(page,dict) and page.get('status')=='PASS'
                and isinstance(page.get('final_url'),str)
                and page['final_url'].startswith(('https://'+domain+'/', 'https://'+domain))
            ][:8] if domain in research_decisions else []),
            'targeted_recovery_requirements': ([
                {'evidence_key':g, 'required_proof':EVIDENCE_TASKS[g],
                 'acceptable_source':'first_party_document_or_authenticated_commercial_evidence',
                 'status':'UNVERIFIED', 'auto_approve':False}
                for g in gaps if g in EVIDENCE_TASKS
            ] if domain in research_decisions else []),
            'commercial_terms_verified':False,
            'canonical_contact_or_reply_verified':False,
            'outbound_authorized':False,
            'mailbox_send_provisioned':False,
            'actual_revenue':False,
        })
    order={'FOUNDER_REVIEW_ONLY':0,'DUE_DILIGENCE_PENDING':1,
           'EVIDENCE_RECOVERY':2,'ECOSYSTEM_RESEARCH':3,
           'AUTOMATED_EVIDENCE_HOLD':4,'MANUAL_EVIDENCE_HOLD':5}
    # Existing conversations outrank cold research within the SAME tier.
    # First-party sector fit outranks inferred broad industry relevance.
    # No approved contact, geography or capacity is inferred by this order.
    relationship_order = {
        'REVIEW_LIVE_RELATIONSHIP_AND_QUALIFY_BUYER_PILOT': 0,
        'REVIEW_PRIOR_THREAD_FOR_RESPONSE_NO_DUPLICATE_FIRST_TOUCH': 1,
        'VERIFY_BUSINESS_CONTACT_PATH_AND_PREPARE_DISCOVERY_PROPOSAL': 2,
    }
    evidence_order = {
        'FIRST_PARTY_SECTOR_RESEARCH_FIT': 0,
        'UNVERIFIED_SECTOR_RESEARCH_FIT': 1,
        'NO_SECTOR_GAP_MATCH_OBSERVED': 2,
    }
    actions.sort(key=lambda x:(
        order[x['tier']],
        relationship_order.get(x['commercial_next_action'], 3),
        evidence_order[x['active_demand_sector_research_fit']['state']],
        -x['active_demand_sector_research_fit']['observed_overflow_units_for_sectors'],
        -x['founder_priority'], x['domain'],
    ))
    # Reject stale mixed-source races. A scheduler might replace its snapshots
    # concurrently; do not promote an optimistic partial report.
    _,after_hashes=_snapshots(root)
    after_due_hash = sha256(due_path.read_bytes()).hexdigest() if due_path.is_file() else None
    if hashes!=after_hashes or due_hash!=after_due_hash:
        raise BuyerPriorityError('source_snapshots_changed_during_read')
    if demand_hash is not None:
        if (not demand_path.is_file() or demand_path.is_symlink()
                or sha256(demand_path.read_bytes()).hexdigest() != demand_hash):
            raise BuyerPriorityError('demand_priorities_changed_during_read')
    return {
        'schema_version':'empire.buyer_qualification_actions.v1',
        'generated_at':datetime.now(timezone.utc).isoformat(),
        'mode':'OBSERVE','execution_authority':'none',
        'source_sha256':hashes,
        'active_demand_source_sha256':demand_hash,
        'active_demand_source_state':demand_state,
        'active_demand_sector_priorities':{
            k:{'market_gap_count':v['gap_count'],'observed_overflow_units':v['overflow_count']}
            for k,v in sorted(demand_priorities.items())
        },
        'first_party_sector_research_fit_count':sum(
            x['active_demand_sector_research_fit']['state']=='FIRST_PARTY_SECTOR_RESEARCH_FIT'
            for x in actions
        ),
        'inferred_sector_research_fit_count':sum(
            x['active_demand_sector_research_fit']['state']=='UNVERIFIED_SECTOR_RESEARCH_FIT'
            for x in actions
        ),
        'buyer_accepted_geo_or_zip_coverage_count':0,
        'commercial_priority_research_domains':[
            {'domain':x['domain'],
             'sector_fit':x['active_demand_sector_research_fit']['state'],
             'matched_sectors':x['active_demand_sector_research_fit']['matching_sector_names'],
             'next_action':x['commercial_next_action']}
            for x in actions if
            x['active_demand_sector_research_fit']['state']=='FIRST_PARTY_SECTOR_RESEARCH_FIT'
            and x['tier']!='ECOSYSTEM_RESEARCH'
            and x['commercial_next_action']!='NO_NEW_SEND_RECONCILE_SUPPRESSION_OR_DELIVERY'
        ][:30],
        'network_candidate_count':len(current_domains),
        'shortlisted_count':len(actions),
        'founder_continue_research_count':sum(x['founder_research_decision']=='CONTINUE_RESEARCH' for x in actions),
        'first_party_due_diligence_current_count':sum(
            x['first_party_due_diligence'].get('freshness') == 'CURRENT'
            for x in actions
        ),
        'first_party_due_diligence_unverified_count':sum(
            x['first_party_due_diligence'].get('freshness') != 'CURRENT'
            or not x['first_party_due_diligence'].get('homepage_reachable')
            for x in actions
        ),
        'trusted_founder_review_count':sum(x['tier']=='FOUNDER_REVIEW_ONLY' for x in actions),
        'manual_evidence_hold_count':sum(x['tier']=='MANUAL_EVIDENCE_HOLD' for x in actions),
        'automated_evidence_hold_count':sum(x['tier']=='AUTOMATED_EVIDENCE_HOLD' for x in actions),
        'due_diligence_pending_count':sum(x['tier']=='DUE_DILIGENCE_PENDING' for x in actions),
        'due_diligence_source_sha256':due_hash,
        'contact_verified_for_outbound_count':0,
        'commercial_action_counts':dict(sorted(Counter(
            x['commercial_next_action'] for x in actions).items())),
        'contact_history_state_counts':dict(sorted(Counter(
            x['contact_history_state'] for x in actions).items())),
        'event_ecosystem_not_direct_buyer_count':sum(
            x['buyer_relationship_role_review']=='INDUSTRY_CONFERENCE_NOT_VERIFIED_LEAD_BUYER'
            for x in actions),
        'buyer_budget_requirement_not_used_as_discovery_gate':True,
        'first_party_publisher_role_evidence_only':True,
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
        'first_party_due_diligence_current_count':report['first_party_due_diligence_current_count'],
        'first_party_due_diligence_unverified_count':report['first_party_due_diligence_unverified_count'],
        'trusted_founder_review_count':report['trusted_founder_review_count'],
        'manual_evidence_hold_count':report['manual_evidence_hold_count'],
        'automated_evidence_hold_count':report['automated_evidence_hold_count'],
        'due_diligence_pending_count':report['due_diligence_pending_count'],
        'gap_counts':report['gap_counts'],
        'target_domains_by_tier':[{'domain':x['domain'],'tier':x['tier'],
                                   'manual_hold_reason':x['manual_hold_reason'],
                                   'automated_hold_reason':x['automated_hold_reason'],
                                   'missing_evidence':x['missing_evidence']}
                                  for x in report['targets'][:10]],
        'written':bool(args.write),'outbound_sent':False,
        'execution_authority':'none'},sort_keys=True,indent=2))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
