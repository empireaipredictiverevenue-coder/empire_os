"""Human review projection owned by Revenue Distribution; never a commercial writer."""
from __future__ import annotations

import hashlib
import json
from urllib.parse import urlsplit

REVIEW_SOURCES = {
    'promotion': 'runtime/buyer_acquisition/promotion_plan_latest.json',
    'enterprise': 'runtime/predictive_revenue/enterprise_targets_latest.json',
    'activation': 'runtime/predictive_revenue/enterprise_activation_latest.json',
    'contacts': 'runtime/predictive_revenue/enterprise_contact_intelligence_latest.json',
    'conversations': 'runtime/conversation_recovery/latest.json',
    'probes': 'runtime/buyer_probe_targeted/latest.json',
}
LANES = ('lead_call_networks', 'direct_enterprise', 'smb_end_service', 'mrr_saas',
         'search_geo_aeo', 'permit_property_private_capital', 'data_intelligence',
         'api_feed', 'predictive_opportunity', 'enterprise_contracts',
         'white_label_partners', 'publisher_affiliate')


def _rows(data, key):
    values = data.get(key, []) if isinstance(data, dict) else []
    return [v for v in values if isinstance(v, dict)] if isinstance(values, list) else []


def _domain(value):
    try:
        return (urlsplit(value if '://' in str(value) else 'https://' + str(value or '')).hostname or '').lower().removeprefix('www.')
    except ValueError:
        return ''


def _name(value):
    return ' '.join(str(value or '').lower().split())


def build_human_review_queue(snapshots, review, opportunities, *, limit=20):
    """Reconcile historical evidence, holding every row for current canonical checks.

    No artifact implies complete inbox/suppression coverage. Existing contact
    verifications describe source evidence, not mailbox deliverability or authority.
    """
    provenance = {}
    for key, path in REVIEW_SOURCES.items():
        data = review.get(key)
        provenance[key] = {
            'path': path, 'available': isinstance(data, (dict, list)),
            'observed_at': (data.get('generated_at') or data.get('observed_at')) if isinstance(data, dict) else None,
            'sha256': hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest() if data is not None else None,
            'freshness': 'REQUIRES_CURRENT_CANONICAL_RECHECK',
        }
    catalog = {r.get('product_code'): r for r in _rows(snapshots.get('catalog'), 'products')}
    conversations = _rows(review.get('conversations'), 'items')
    suppressed = [r for r in conversations if 'suppress' in str(r.get('recovery_reason', '')).lower()
                  or r.get('suppressed') is True or r.get('opted_out') is True]
    suppressed_names = {_name(r.get('business_name')) for r in suppressed}
    suppressed_domains = {_domain(str(r.get('recipient', '')).split('@')[-1]) for r in suppressed}
    suppressed_domains.discard('')
    candidates = []

    def add(company, domain, codes, lanes, source, original):
        if not company:
            return None
        domain = _domain(domain)
        if _name(company) in suppressed_names or (domain and domain in suppressed_domains):
            return None
        row = {
            'company': company, 'legal_identity_state': 'TRADING_NAME_OBSERVED_LEGAL_IDENTITY_UNKNOWN',
            'domain': domain or None, 'commercial_role': 'RESEARCH_PROSPECT_NOT_VERIFIED_BUYER',
            'person_name': None, 'job_title': None, 'person_verified': False,
            'person_evidence_state': 'UNKNOWN',
            'email': None, 'email_verified': False, 'contact_evidence': [],
            'geography': original.get('metro') or original.get('geography'),
            'product_codes': list(dict.fromkeys(codes)), 'revenue_lanes': lanes,
            'product_match_state': 'INFERRED_RESEARCH_FIT', 'demand_state': 'UNKNOWN',
            'evidence_refs': [REVIEW_SOURCES[source]], 'why_now_evidence': [],
            'conversation_state': 'UNKNOWN_REQUIRES_CANONICAL_RECONCILIATION',
            'conversation_refs': [], 'suppression_state': 'UNKNOWN_CURRENT_CHECK_REQUIRED',
            'duplicate_state': 'ARTIFACT_IDENTITIES_RECONCILED_CANONICAL_CHECK_REQUIRED',
            'readiness_blockers': ['current_canonical_suppression_and_inbox_check', 'verified_demand_unknown', 'current_catalog_readiness_check', 'historical_source_freshness_recheck'],
            'next_proposed_action': 'Review source evidence and reconcile canonical contact/conversation before proposing contact.',
            'execution_authority': 'none', 'outreach_authorized': False,
            'commercial_authority_verified': False, 'existing_qualification_score': None,
            'canonical_prospect_id': original.get('prospect_id'),
            'source_order': len(candidates),
        }
        candidates.append(row)
        return row

    contacts = {r.get('prospect_id'): r for r in _rows(review.get('contacts'), 'outcomes')}
    activations = {r.get('account_key'): r for r in _rows(review.get('activation'), 'targets')}
    for target in _rows(review.get('enterprise'), 'targets'):
        activation = activations.get(target.get('account_key'), {})
        urls = target.get('evidence_urls') or []
        row = add(target.get('account_name'), activation.get('canonical_website') or (urls[0] if urls else ''),
                  target.get('target_product_codes') or [], ['direct_enterprise', 'predictive_opportunity', 'enterprise_contracts'], 'enterprise', activation)
        if row is None:
            continue
        row['evidence_refs'] += urls + [REVIEW_SOURCES['activation'], REVIEW_SOURCES['contacts']]
        row['why_now_evidence'] = target.get('observed_triggers') or []
        row['existing_qualification_score'] = activation.get('qualification', {}).get('score')
        probe = activation.get('probe') or {}
        person = probe.get('decision_maker') or {}
        evidence = [c for c in probe.get('verified_contacts', [])
                    if c.get('bound_to_decision_maker') is True and c.get('is_valid') is True
                    and not c.get('is_role_address') and not c.get('is_disposable')
                    and c.get('email') == person.get('email') and person.get('url')]
        if evidence and activation.get('person_contact_verified') is True:
            row['person_evidence_state'] = 'HISTORICAL_FIRST_PARTY_PERSON_CONTACT'
            row.update(person_name=person.get('name'), job_title=person.get('title'), person_verified=True,
                       email=person.get('email'), email_verified=True, contact_evidence=[person, *evidence])
        else:
            # Curated person records only; raw visible-text extraction contains role labels.
            intel = contacts.get(activation.get('prospect_id'), {})
            curated = [p for p in intel.get('target_people', []) if p.get('source_kind') == 'curated_first_party'
                       and p.get('name') and p.get('evidence_url')]
            if curated:
                person = curated[0]
                row['person_evidence_state'] = 'HISTORICAL_CURATED_FIRST_PARTY'
                row.update(person_name=person['name'], job_title=person.get('title'),
                           person_verified=True, contact_evidence=[person])
        if target.get('wave') != 'direct_enterprise':
            row['revenue_lanes'].append('permit_property_private_capital')

    probes = review.get('probes') if isinstance(review.get('probes'), list) else []
    for item in conversations:
        row = add(item.get('business_name'), str(item.get('recipient', '')).split('@')[-1], [],
                  ['smb_end_service'], 'conversations', item)
        if row is None:
            continue
        row.update(email=item.get('recipient'), conversation_state='DELIVERED_FIRST_TOUCH_REPLY_UNKNOWN',
                   conversation_refs=[item.get('root_intent_id')], why_now_evidence=[{'delivered_at': item.get('delivered_at'), 'recovery_reason': item.get('recovery_reason')}],
                   next_proposed_action='Recover original thread and check replies/opt-outs; review follow-up context, never restart cold outreach.')
        row['contact_evidence'] = [{'email': item.get('recipient'), 'state': 'HISTORICAL_DELIVERY_NOT_PERSON_VERIFICATION'}]
        if not item.get('recoverable'):
            row['readiness_blockers'].append(str(item.get('recovery_reason') or 'conversation_context_missing'))
        matches = [p for p in probes if isinstance(p, dict) and _name(p.get('business_name')) == _name(item.get('business_name'))]
        if len(matches) == 1:
            p = matches[0]
            person = p.get('decision_maker') or {}
            if person.get('name'):
                row.update(person_name=person['name'], job_title=person.get('title'), canonical_prospect_id=p.get('prospect_id'))
                row['contact_evidence'].append(person)
                row['evidence_refs'].append(REVIEW_SOURCES['probes'])
                row['readiness_blockers'].append('historical_person_source_url_and_recipient_binding_required')
        # Existing acquisition product/pool matching, explicitly inferred, not demand.
        routes = [p for p in _rows(snapshots.get('buyer_acquisition'), 'product_demand_queue')
                  if 'local_and_smb_buyers' in (p.get('target_buyer_pools') or []) and p.get('binding_terms_ready') is True]
        if routes:
            route = next((p for p in routes if p.get('product_code') == 'competitor_search_gap'), routes[0])
            row['product_codes'] = [route['product_code']]
            row['revenue_lanes'].append('search_geo_aeo')
            row['evidence_refs'].append('runtime/buyer_acquisition/latest.json#product_demand_queue')

    for proposal in _rows(review.get('promotion'), 'proposals'):
        payload = proposal.get('proposed_prospect_payload') or {}
        row = add(payload.get('business_name'), proposal.get('domain'), proposal.get('target_product_codes') or [],
                  [], 'promotion', payload)
        if row:
            row['candidate_id'] = proposal.get('candidate_id')
            row['source_commercial_classification'] = proposal.get('buyer_type')
            row['target_buyer_pools'] = proposal.get('target_buyer_pools') or []
            row['evidence_refs'].append('buyer_scout_candidate:' + str(proposal.get('candidate_id')))
            row['readiness_blockers'].append('promotion_proposal_not_verified_identity_or_demand')
    for scout in _rows(snapshots.get('buyer_scout'), 'candidates'):
        row = add(scout.get('business_name'), scout.get('domain'), scout.get('target_product_codes') or [],
                  [], 'promotion', scout)
        if row:
            row['evidence_refs'] = ['runtime/buyer_acquisition/scout_latest.json']
            row['target_buyer_pools'] = scout.get('target_buyer_pools') or []
            row['why_now_evidence'] = scout.get('observed_buying_triggers') or []

    # Match every candidate against all historical outreach, including held records.
    merged = {}
    for row in candidates:
        matches = [c for c in conversations if _name(c.get('business_name')) == _name(row['company'])
                   or (row['domain'] and _domain(str(c.get('recipient', '')).split('@')[-1]) == row['domain'])]
        if matches:
            row['conversation_state'] = 'DELIVERED_FIRST_TOUCH_REPLY_UNKNOWN'
            row['conversation_refs'] = sorted({c['root_intent_id'] for c in matches if c.get('root_intent_id')})
            row['evidence_refs'].append(REVIEW_SOURCES['conversations'])
            row['next_proposed_action'] = 'Recover existing thread; reconcile replies, opt-outs and person binding before human follow-up review.'
        key = row['domain'] or _name(row['company'])
        if key in merged:
            old = merged[key]
            for field in ('evidence_refs', 'product_codes', 'revenue_lanes', 'conversation_refs', 'readiness_blockers'):
                old[field] = list(dict.fromkeys(old[field] + row[field]))
            if row['conversation_refs']:
                old['conversation_state'] = row['conversation_state']
                old['next_proposed_action'] = row['next_proposed_action']
            continue
        merged[key] = row
    rows = list(merged.values())
    public = _rows(review.get('promotion'), 'public_contact_evidence')
    for row in rows:
        observed = [p for p in public if p.get('domain') == row['domain']
                    and p.get('source_kind') == 'human_checked_first_party'
                    and p.get('person_explicitly_named') is True and p.get('person_name')
                    and p.get('observed_at') and _domain(p.get('source_url')) == row['domain']]
        if len(observed) == 1:
            person = observed[0]
            row.update(person_name=person['person_name'], job_title=person.get('job_title'),
                       person_verified=True, public_research_updated=True)
            row['contact_evidence'].append({k: v for k, v in person.items() if k not in {'execution_authority', 'outreach_authorized', 'authority'}})
            row['evidence_refs'].append(person['source_url'])
            row['person_evidence_state'] = 'FIRST_PARTY_PUBLIC_OBSERVATION'
            if person.get('email_explicitly_published') is True and person.get('email'):
                row.update(email=person['email'], email_verified=True)
            else:
                row['email_verified'] = False
                row['readiness_blockers'].append('historical_recipient_person_binding_requires_review')
            if person.get('context_review_required') is True:
                row['readiness_blockers'].append('contact_or_geography_context_review')
        row['email_verification_scope'] = 'PUBLIC_OR_STORED_PERSON_CONTACT_EVIDENCE_NOT_CURRENT_DELIVERABILITY' if row['email_verified'] else 'UNVERIFIED_PERSON_BINDING'
        pools = row.get('target_buyer_pools', [])
        for pool, lane in (('agency_and_reseller_buyers', 'white_label_partners'),
                           ('direct_demand_buyers', 'lead_call_networks'),
                           ('local_and_smb_buyers', 'smb_end_service')):
            if pool in pools and lane not in row['revenue_lanes']:
                row['revenue_lanes'].append(lane)
        for code in row['product_codes']:
            for fragment, lane in (('permit', 'permit_property_private_capital'),
                                   ('property', 'permit_property_private_capital'),
                                   ('private_capital', 'permit_property_private_capital'),
                                   ('data', 'data_intelligence'), ('api', 'api_feed'),
                                   ('search', 'search_geo_aeo'), ('white_label', 'white_label_partners'),
                                   ('predictive', 'predictive_opportunity')):
                if fragment in code and lane not in row['revenue_lanes']:
                    row['revenue_lanes'].append(lane)
            product = catalog.get(code, {})
            if product.get('billing_model') == 'monthly_subscription' and 'mrr_saas' not in row['revenue_lanes']:
                row['revenue_lanes'].append('mrr_saas')

        row['product_refs'] = [{'product_code': code, 'product_id': catalog.get(code, {}).get('product_id'),
                                'binding_terms_ready': catalog.get(code, {}).get('binding_terms_ready'),
                                'price_accepted': None} for code in row['product_codes']]
        row['opportunity_refs'] = [o['opportunity_key'] for o in opportunities
                                   if set(row['product_codes']).intersection(p['product_code'] for p in o['product_matches'])]
        row['expected_revenue_cents'] = None  # Product fit cannot supply formula factors.
        if not row['person_verified']:
            row['readiness_blockers'].append('verified_person_required')
        if not row['email_verified']:
            row['readiness_blockers'].append('verified_person_email_required')
        if not row['product_codes']:
            row['readiness_blockers'].append('product_match_required')
        if any(p['binding_terms_ready'] is not True for p in row['product_refs']):
            row['readiness_blockers'].append('product_terms_readiness_requires_review')
        row['readiness_blockers'] = sorted(set(row['readiness_blockers']))
    # Readiness first; existing qualification score only within equal readiness.
    rows.sort(key=lambda r: (not r['email_verified'], not r['person_verified'],
                             'contact_or_geography_context_review' in r['readiness_blockers'],
                             not bool(r['conversation_refs']), not bool(r['person_name']),
                             -(r['existing_qualification_score'] or 0), r['source_order']))
    top = rows if limit is None else rows[:limit]
    for index, row in enumerate(top, 1):
        row['rank'] = index
    return {
        'human_review_queue': top,
        'review_candidate_count': len(rows), 'review_sources': provenance,
        'review_ranking_policy': 'Existing verified contact readiness, person evidence, unresolved contact/geography holds, existing outreach context, existing qualification score, stable source order. No new revenue score.',
        'excluded_suppression_count': len(suppressed),
        'review_blockers': ['live_canonical_reconciliation_required', 'source_freshness_requires_recheck'],
        'relationship_holds': [
            {'company': 'Lead Smart', 'commercial_role': 'publisher_affiliate_partner', 'conversation_state': 'FOUNDER_REPORTED_ALREADY_EMAILED_SETH', 'evidence_refs': ['docs/LEAD_SMART_EVIDENCE_DELTA.md'], 'next_proposed_action': 'Recover existing affiliate thread; verify payable-call rules without classifying as direct buyer.', 'execution_authority': 'none'},
            {'company': 'Connex', 'commercial_role': 'UNKNOWN', 'conversation_state': 'FOUNDER_REPORTED_EXISTING_CONVERSATION_THREAD_UNAVAILABLE', 'evidence_refs': ['founder_instruction:2026-09-29'], 'next_proposed_action': 'Recover canonical existing conversation; do not restart contact.', 'execution_authority': 'none'},
        ],
        'revenue_lane_coverage': {lane: {'review_candidate_count': sum(lane in r['revenue_lanes'] for r in rows),
                                      'top20_count': sum(lane in r['revenue_lanes'] for r in top),
                                      'next_proposed_action': 'Review existing Buyer Acquisition product/pool research routes and obtain person and demand evidence; no outreach.',
                                      'state': 'RESEARCH_ONLY_NO_VERIFIED_DEMAND' if any(lane in r['revenue_lanes'] for r in rows) else 'EVIDENCE_GAP_RESEARCH_REQUIRED'} for lane in LANES},
    }
