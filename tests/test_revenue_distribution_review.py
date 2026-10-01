from copy import deepcopy

from empire_os.revenue_distribution_review import build_human_review_queue
from empire_os.revenue_distribution import build_revenue_distribution


def evidence(domain='example.org', **kw):
    return dict(domain=domain, person_name='Verified Person', job_title='Owner',
                source_url='https://' + domain + '/team', observed_at='2026-09-29T00:00:00Z',
                source_kind='human_checked_first_party', person_explicitly_named=True,
                email='person@' + domain, email_explicitly_published=True, **kw)


def inputs():
    return {'conversations': {'items': [{'business_name': 'Example Co', 'recipient': 'person@example.org',
                                         'root_intent_id': 'intent-1', 'recoverable': True,
                                         'recovery_reason': 'due_now', 'delivered_at': '2026-09-20T00:00:00Z'}]},
            'promotion': {'public_contact_evidence': [evidence()]}}


def queue(review, snapshots=None):
    return build_human_review_queue(snapshots or {}, review, [])


def test_person_evidence_does_not_authorize_outreach_or_prove_demand():
    data = inputs()
    data['promotion']['public_contact_evidence'][0].update(execution_authority='full', outreach_authorized=True)
    row = queue(data)['human_review_queue'][0]
    assert row['person_verified'] and row['email_verified']
    assert row['execution_authority'] == 'none' and row['outreach_authorized'] is False
    assert row['demand_state'] == 'UNKNOWN' and row['expected_revenue_cents'] is None
    assert row['conversation_state'] == 'DELIVERED_FIRST_TOUCH_REPLY_UNKNOWN'
    assert row['conversation_refs'] == ['intent-1']
    assert 'current_canonical_suppression_and_inbox_check' in row['readiness_blockers']


def test_suppression_excludes_company_across_sources_and_aliases():
    data = inputs()
    data['conversations']['items'][0]['recovery_reason'] = 'suppressed_after_delivery'
    data['promotion']['proposals'] = [{'domain': 'www.example.org', 'proposed_prospect_payload': {'business_name': 'Alias'}}]
    assert queue(data)['human_review_queue'] == []
    assert queue(data)['excluded_suppression_count'] == 1


def test_opt_out_flag_also_excludes():
    data = inputs()
    data['conversations']['items'][0]['opted_out'] = True
    assert not queue(data)['human_review_queue']


def test_domain_mismatch_and_ambiguous_people_do_not_verify():
    for kind in ('mismatch', 'duplicate', 'missing_source', 'extracted_label'):
        data = inputs()
        p = data['promotion']['public_contact_evidence'][0]
        if kind == 'mismatch': p['source_url'] = 'https://other.org/team'
        if kind == 'duplicate': data['promotion']['public_contact_evidence'].append(deepcopy(p))
        if kind == 'missing_source': p['source_url'] = None
        if kind == 'extracted_label': p['source_kind'] = 'visible_text'
        assert queue(data)['human_review_queue'][0]['person_verified'] is False


def test_delivery_and_named_person_do_not_verify_email_binding():
    data = inputs()
    data['promotion']['public_contact_evidence'][0].update(email=None, email_explicitly_published=False)
    row = queue(data)['human_review_queue'][0]
    assert row['person_verified'] and not row['email_verified']
    assert row['email'] == 'person@example.org'


def test_duplicates_merge_context_without_restarting_outreach():
    data = inputs()
    data['promotion']['proposals'] = [{'domain': 'example.org', 'target_product_codes': ['permit_intelligence'],
                                       'proposed_prospect_payload': {'business_name': 'Example Co alias'}}]
    result = queue(data)
    assert len(result['human_review_queue']) == 1
    row = result['human_review_queue'][0]
    assert 'permit_intelligence' in row['product_codes']
    assert 'existing thread' in row['next_proposed_action']


def test_unknown_sources_never_claim_complete_reconciliation():
    result = queue({})
    assert result['human_review_queue'] == []
    assert 'live_canonical_reconciliation_required' in result['review_blockers']
    assert all(not r['available'] for r in result['review_sources'].values())
    assert len(result['revenue_lane_coverage']) == 12


def test_relationship_holds_are_separate_and_non_authorizing():
    holds = queue({})['relationship_holds']
    assert holds[0]['commercial_role'] == 'publisher_affiliate_partner'
    assert holds[1]['company'] == 'Connex'
    assert all(h['execution_authority'] == 'none' for h in holds)


def test_verified_person_context_prioritized_without_new_score():
    data = inputs()
    data['conversations']['items'].insert(0, {'business_name': 'Unknown', 'recipient': 'unknown@other.org', 'root_intent_id': 'i2'})
    result = queue(data)
    assert result['human_review_queue'][0]['company'] == 'Example Co'
    assert result['human_review_queue'][0]['existing_qualification_score'] is None


def test_zero_cash_has_no_budget_blocker_but_paid_stays_blocked():
    for budget in (None, 0, 100):
        result = build_revenue_distribution({}, generated_at='2026-09-29T00:00:00Z', acquisition_budget_cents=budget)
        assert not any('budget' in b for b in result['blockers'])
        assert result['zero_cash_research_ready'] is False  # No source evidence, not a budget gate.
        assert 'founder_authorization_required' in result['paid_acquisition_blockers']
        assert result['authority']['paid_traffic'] is False
        if budget is None: assert 'acquisition_budget_unknown' in result['paid_acquisition_blockers']
        if budget == 0: assert 'acquisition_budget_zero' in result['paid_acquisition_blockers']


def test_full_review_pool_preserves_default_top20():
    review = {
        "promotion": {
            "proposals": [
                {
                    "domain":
                        f"company-{i}.example",
                    "target_product_codes": [
                        "managed_service"
                    ],
                    "proposed_prospect_payload": {
                        "business_name":
                            f"Company {i}"
                    },
                }
                for i in range(25)
            ]
        }
    }

    default = build_human_review_queue(
        {},
        review,
        [],
    )

    full = build_human_review_queue(
        {},
        review,
        [],
        limit=None,
    )

    assert (
        len(default["human_review_queue"])
        == 20
    )

    assert (
        len(full["human_review_queue"])
        == 25
    )

    assert (
        full["review_candidate_count"]
        == 25
    )


def test_full_review_pool_preserves_default_top20():
    review = {
        "promotion": {
            "proposals": [
                {
                    "domain":
                        f"company-{i}.example",
                    "target_product_codes": [
                        "managed_service"
                    ],
                    "proposed_prospect_payload": {
                        "business_name":
                            f"Company {i}"
                    },
                }
                for i in range(25)
            ]
        }
    }

    default = build_human_review_queue(
        {},
        review,
        [],
    )

    full = build_human_review_queue(
        {},
        review,
        [],
        limit=None,
    )

    assert (
        len(default["human_review_queue"])
        == 20
    )

    assert (
        len(full["human_review_queue"])
        == 25
    )

    assert (
        full["review_candidate_count"]
        == 25
    )
