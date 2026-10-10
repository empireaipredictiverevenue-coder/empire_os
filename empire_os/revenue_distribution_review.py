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

# Supply-side recruitment projection; intentionally separate from buyer affiliates.
# This never polls Gmail, approves sends, allocates traffic, or calculates income.
def build_publisher_recruitment_summary(prospects, delivery):
    import hashlib

    out = {
        "schema_version": "empire.publisher_supply_recruitment_review.v1",
        "mode": "OBSERVE", "state": "EVIDENCE_UNAVAILABLE",
        "source_role": "potential_supply_publisher_not_buyer",
        "source_mailbox_live_sync": False,
        "candidate_count": 0, "email_submitted_count": 0,
        "hard_bounce_count": 0, "awaiting_response_count": 0,
        "unsent_draft_count": 0, "verified_reply_count": 0,
        "reply_observed_count": 0, "paid_only_reply_count": 0,
        "homeowner_supply_candidates": 0, "contractor_software_affiliate_candidates": 0,
        "verified_onboarded_count": 0, "recognized_revenue_cents": 0,
        "outbound_authorized": False, "traffic_authorized": False,
        "publisher_payment_authorized": False, "execution_authority": "none",
        "items": [],
    }
    if prospects is None or delivery is None:
        return out
    try:
        if (not isinstance(prospects, dict) or
            prospects.get("schema_version") !=
                "empire.publisher_supply_recruitment_evidence.v1" or
            not isinstance(delivery, dict) or
            delivery.get("schema_version") !=
                "empire.publisher_recruitment.gmail_sent_evidence.v1" or
            delivery.get("source_mailbox") != "flavag83@gmail.com" or
            delivery.get("delivered_or_inbox_placement_verified") is not False or
            delivery.get("empire_os_outbound_governor_send") is not False or
            delivery.get("buyer_programme_activated") is not False or
            delivery.get("revenue_recognized_cents") != 0 or
            delivery.get("publisher_enrolled_count") != 0):
            raise ValueError("untrusted_recruitment_source")
        candidates = prospects.get("items")
        messages = delivery.get("messages")
        if (not isinstance(candidates, list) or not 0 <= len(candidates) <= 25
                or not isinstance(messages, list) or not 0 <= len(messages) <= len(candidates)):
            raise ValueError("unbounded_recruitment_source")
        by_contact, domains = {}, set()
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise ValueError("invalid_recruitment_candidate")
            address, domain = candidate.get("contact_email"), candidate.get("domain")
            if (not isinstance(address, str) or "@" not in address
                    or not isinstance(domain, str) or not domain
                    or address in by_contact or domain in domains
                    or not str(candidate.get("draft_url", "")).startswith("https://mail.google.com/")
                    or not str(candidate.get("source_url", "")).startswith("https://")):
                raise ValueError("duplicate_or_invalid_recruitment_candidate")
            by_contact[address] = candidate
            domains.add(domain)

        sent, bounce_count, paid_only_replies = {}, 0, {}
        for message in messages:
            if not isinstance(message, dict):
                raise ValueError("invalid_recruitment_send")
            contact, mid = message.get("recipient"), message.get("gmail_message_id")
            hard_bounce = message.get("recipient_delivery_status") == "BOUNCED_NO_SUCH_USER_550_5_1_1"
            if (contact not in by_contact or contact in sent
                    or not isinstance(mid, str) or len(mid) < 16
                    or message.get("gmail_label") != "SENT"
                    or message.get("unsubscribe_text_present") is not True
                    or message.get("postal_footer_present") is not True
                    or message.get("commercial_terms_agreed") is not False):
                raise ValueError("untrusted_recruitment_send")
            if hard_bounce:
                if (message.get("retry_authorized") is not False
                        or not isinstance(message.get("bounce_gmail_message_id"), str)):
                    raise ValueError("unverified_hard_bounce")
                bounce_count += 1
            elif message.get("recipient_delivery_status") is not None:
                raise ValueError("untrusted_recruitment_delivery_state")
            reply_id = message.get("reply_message_id")
            if reply_id is not None:
                if (hard_bounce or not isinstance(reply_id, str) or len(reply_id) < 16
                        or reply_id == mid or message.get("reply_from") != contact
                        or not isinstance(message.get("reply_received_at"), str)
                        or message.get("reply_classification") != "PAID_ONLY_UPFRONT_REQUIRED"
                        or message.get("reported_minimum_placement_usd") != 500
                        or message.get("reply_terms_accepted") is not False
                        or message.get("no_cost_publisher_fit") is not False):
                    raise ValueError("untrusted_recruitment_reply")
                paid_only_replies[contact] = reply_id
            elif any(key in message for key in ("reply_from", "reply_received_at",
                         "reply_classification", "reported_minimum_placement_usd")):
                raise ValueError("orphan_recruitment_reply_metadata")
            sent[contact] = hard_bounce
        if (delivery.get("submitted_to_gmail_count") != len(sent)
                or delivery.get("confirmed_hard_bounce_count") != bounce_count
                or delivery.get("no_bounce_observed_yet_count") != len(sent) - bounce_count
                or delivery.get("reply_observed_count", 0) != len(paid_only_replies)
                or delivery.get("paid_only_reply_count", 0) != len(paid_only_replies)):
            raise ValueError("conflicting_recruitment_totals")
        rows = []
        for contact, candidate in by_contact.items():
            stage = ("HARD_BOUNCE_NO_RETRY" if sent.get(contact) is True
                     else "PAID_ONLY_NO_ZERO_BUDGET_FIT" if contact in paid_only_replies
                     else "GMAIL_SUBMITTED_DELIVERY_UNVERIFIED" if contact in sent
                     else "DRAFT_UNSENT")
            vertical = candidate.get("vertical")
            affiliate_lane = (
                "CONTRACTOR_SOFTWARE_AFFILIATE"
                if vertical in ("B2B_CONTRACTOR_SOFTWARE", "B2B_LEGAL_TECH")
                else "HOMEOWNER_REFERRAL_SUPPLY"
            )
            rows.append({
                "domain": candidate["domain"],
                "company": candidate.get("company"),
                "market": candidate.get("market"),
                "vertical": vertical,
                "revenue_lane": affiliate_lane,
                "requires_verified_buyer_subaffiliate_permission": (
                    affiliate_lane == "HOMEOWNER_REFERRAL_SUPPLY"
                ),
                "monetization_precondition": (
                    "VERIFIED_SAAS_SALE_AND_PARTNER_TERMS"
                    if affiliate_lane == "CONTRACTOR_SOFTWARE_AFFILIATE"
                    else "BUYER_APPROVED_GEO_SOURCE_AND_COLLECTED_PAYOUT"
                ),
                "commercial_role": "TRAFFIC_SUPPLY_RESEARCH_ONLY",
                "stage": stage,
                "reply_observed_in_connected_gmail": contact in paid_only_replies,
                "reply_verified": False,
                "live_buyer_route_verified": False,
                "outbound_authorized": False,
                "payout_verified": False,
            })
        out.update({
            "state": "HUMAN_REVIEW_ONLY",
            "evidence_observed_date": delivery.get("observed_date"),
            "source_sha256": hashlib.sha256(
                json.dumps(
                    {"prospects": prospects, "delivery": delivery},
                    sort_keys=True, allow_nan=False).encode()).hexdigest(),
            "candidate_count": len(candidates),
            "email_submitted_count": len(sent),
            "hard_bounce_count": bounce_count,
            "reply_observed_count": len(paid_only_replies),
            "paid_only_reply_count": len(paid_only_replies),
            "awaiting_response_count": len(sent) - bounce_count - len(paid_only_replies),
            "unsent_draft_count": len(candidates) - len(sent),
            "homeowner_supply_candidates": sum(
                row["revenue_lane"] == "HOMEOWNER_REFERRAL_SUPPLY"
                for row in rows
            ),
            "contractor_software_affiliate_candidates": sum(
                row["revenue_lane"] == "CONTRACTOR_SOFTWARE_AFFILIATE"
                for row in rows
            ),
            "items": rows,
        })
    except (ValueError, TypeError, KeyError):
        out["state"] = "HOLD_INVALID_OR_CONFLICTING_EVIDENCE"
    return out

# Signed referral token and conversion-review utilities are offline only.
# Reuse the current Revenue Distribution review; never launch a new tracker.
from empire_os.affiliate_tracking import affiliate_tracking_capability

# Six-way visibility over existing producer snapshots. This is a review
# projection only: neither a new workflow engine nor an authority source.
REVENUE_PIPELINE_SPECS = (
    ("buyer_demand", ("buyer_scout", "buyer_acquisition", "buyer_capacity"),
     "Buyer-specific buy-box, payable event, permitted supply source and terms"),
    ("publisher_supply", (),
     "Verified owner, consented source and buyer permission for sub-affiliates"),
    ("owned_organic", ("search", "aeo", "crawler"),
     "Approved first-party source, live buyer corridor and separate PPC/PPL route"),
    ("saas_affiliates", ("catalog",),
     "Deliverable paid SaaS product, approved affiliate terms and verified sales"),
    ("conversion_fulfilment", ("exchange", "buyer_capacity", "conversion"),
     "Partner-specific lead/call intake, lawful consent, acceptance and fulfilment"),
    ("economic_memory", (),
     "Collected payment, reversal checks, publisher costs and recognised margin"),
)


def build_revenue_multi_pipeline_review(report):
    """Overlay six separate source/demand/economic queues onto one OBSERVE spine.

    Every readiness is held until independent real business/operational proof.
    A visible source, draft or public buyer page never grants traffic authority.
    """
    if not isinstance(report, dict):
        raise ValueError("revenue distribution required")
    sources = report.get("sources", {})
    source_map = sources if isinstance(sources, dict) else {}
    publisher = report.get("publisher_supply_recruitment", {})
    publisher = publisher if isinstance(publisher, dict) else {}
    valid_publisher = publisher.get("state") == "HUMAN_REVIEW_ONLY"
    lanes = []
    for name, dependencies, needed in REVENUE_PIPELINE_SPECS:
        observed = {
            key: source_map.get(key, {}).get("status", "missing_or_invalid")
            if isinstance(source_map.get(key), dict) else "missing_or_invalid"
            for key in dependencies
        }
        if name in ("publisher_supply", "saas_affiliates"):
            evidence_state = "REVIEW_ONLY" if valid_publisher else "HOLD_EVIDENCE_UNAVAILABLE"
        else:
            evidence_state = "REVIEW_ONLY" if any(
                state == "available" for state in observed.values()
            ) else "HOLD_EVIDENCE_UNAVAILABLE"
        if name == "economic_memory":
            evidence_state = "HOLD_PAYMENT_EVIDENCE_UNAVAILABLE"
        counters = {}
        if name == "publisher_supply" and valid_publisher:
            counters = {
                "researched_source_count": publisher.get("homeowner_supply_candidates"),
                "awaiting_reply_count": publisher.get("awaiting_response_count"),
                "verified_onboarded_count": publisher.get("verified_onboarded_count"),
            }
        elif name == "saas_affiliates" and valid_publisher:
            counters = {
                "researched_b2b_referrer_count": publisher.get(
                    "contractor_software_affiliate_candidates"
                ),
                "verified_onboarded_count": publisher.get("verified_onboarded_count"),
            }
        elif name == "economic_memory":
            counters = {
                "publisher_cohort_recognized_revenue_cents":
                    publisher.get("recognized_revenue_cents")
                    if valid_publisher else None,
                "verified_publisher_paid_outcomes": None,
            }
        lanes.append({
            "pipeline": name,
            "evidence_state": evidence_state,
            "source_statuses": observed,
            "observed_research_counts_not_revenue": counters,
            "missing_activation_evidence": needed,
            "live_traffic_authorized": False,
            "outbound_authorized": False,
            "terms_or_payout_authorized": False,
            "collected_revenue_verified_here": False,
            "execution_authority": "none",
        })
    return {
        "schema_version": "empire.revenue_multi_pipeline_review.v1",
        "mode": "OBSERVE",
        "readiness_source": "existing_empire_revenue_distribution_snapshots",
        "independent_pipeline_count": len(lanes),
        "canonical_business_database": "EmpireDB",
        "parallel_queues_not_new_schedulers": True,
        "compliance_and_economic_truth_shared": True,
        "new_service_installed": False,
        "automatic_dispatch_authorized": False,
        "execution_authority": "none",
        "affiliate_tracking": affiliate_tracking_capability(
            researched_sources=publisher.get("candidate_count")
            if valid_publisher and type(publisher.get("candidate_count")) is int
            else None,
        ),
        "pipelines": lanes,
    }
