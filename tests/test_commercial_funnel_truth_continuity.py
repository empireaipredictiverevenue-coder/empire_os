"""Persisted stage evidence, explicit canonical attribution, offline fixtures only."""
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime
import pytest

from empire_os.execution_bus_data_repository import ExecutionBusDataRepository
from empire_os.adaptive_outreach_optimizer import build_performance_snapshot, MIN_DELIVERED_PER_ARM, SEGMENT_MIN_DELIVERED, EXPLORATION_FRACTION
from empire_os.conversation_qualification import validate_qualified_conversation_stage
from empire_os.commercial_terms_materializer import validate_commercial_terms_stage
from test_outreach_verified_outcome_runtime_bridge import canonical, completed, INTENT, PROSPECT, CASE, REPLY, TENANT, ORDER, OPPORTUNITY, NOW, THEN, produce

QUALIFIED = '2026-10-03T08:00:00+00:00'
APPROVED = '2026-10-03T09:00:00+00:00'


@pytest.fixture
def stages(canonical):
    t = canonical.tables
    t['closer_cases'][0]['state'] = 'qualified'
    t['outbound_replies'][0]['body_text'] = 'We have buying authority and require the stated service.'
    t['closer_events'] = [dict(id='qualified-event-1', case_id=CASE, event_type='state_advanced',
        actor='human.operator', occurred_at=QUALIFIED, created_at=QUALIFIED,
        payload={'state': 'qualified', 'note': 'Reviewed explicit buyer requirements and decision authority.'})]
    terms = dict(currency='USD', settlement_asset='USDT', settlement_chain='BSC', description='Observed terms')
    review = dict(id='review-1', fulfilment_order_id=ORDER, status='approved', price_cents=10000,
        terms=terms, commercial_terms_sha256='b'*64, proposed_by='planner', proposed_at=THEN,
        decided_by='human.operator', decided_at=APPROVED)
    t['commercial_terms_reviews'] = [review]
    t['commercial_terms_events'] = [dict(id='approval-event-1', review_id='review-1', fulfilment_order_id=ORDER,
        event_type='approved', actor='human.operator', occurred_at=APPROVED, payload={'commercial_terms_sha256':'b'*64})]
    t['fulfilment_orders'][0]['commercial_payload'].update(commercial_terms_review_id='review-1',
        commercial_terms=deepcopy(terms), terms_approved_by='human.operator', terms_approved_at=APPROVED)
    return canonical


def mid(gateway, tmp_path):
    intent = gateway.tables['outbound_intents'][0]
    return ExecutionBusDataRepository(gateway).outreach_middle_funnel_record(
        dict(intent_id=INTENT, metadata=deepcopy(intent['metadata']), delivered=True, classification='positive'),
        repo_root=tmp_path, as_of=NOW)


def funnel(rows):
    return build_performance_snapshot(rows, generated_at=NOW.isoformat())


def counts(rows):
    return funnel(rows)['segments']['__global__']['body_arms']['a']


@pytest.mark.parametrize('label', ['positive', 'question', 'objection', 'later'])
def test_reply_labels_and_advisory_state_never_qualify(canonical, tmp_path, label):
    canonical.tables['outbound_replies'][0]['classification'] = label
    canonical.tables['closer_cases'][0]['state'] = 'qualified'
    canonical.tables['closer_recommendations'] = [{'case_id':CASE,'recommendation':'qualify','confidence':1}]
    row = mid(canonical, tmp_path)
    assert counts([row])['qualified_conversation'] == 0
    assert row['qualified_conversation_state'] == 'UNKNOWN'


def test_persisted_stages_reach_snapshot_independently_of_revenue(stages, tmp_path):
    stages.tables['commercial_outcomes'] = []
    stages.tables['commercial_events'] = []
    stages.tables['bsc_payment_evidence'] = []
    rows = produce(stages, tmp_path)
    row = rows[0]
    assert row['outcome_bridge_state'] == 'UNKNOWN'
    assert row['qualified_conversation_state'] == 'QUALIFIED'
    assert row['commercial_terms_state'] == 'APPROVED'
    result = counts(rows)
    assert result['qualified_conversation'] == result['commercial_terms'] == 1
    assert result['verified_payment'] == result['recognized_revenue'] == result['fulfilled'] == result['order'] == 0
    for key in ('tenant_id','outbound_intent_id','reply_id','closer_case_id','prospect_id','buyer_id','opportunity_id'):
        assert row[key]


def test_qualification_can_precede_order_and_does_not_imply_terms(stages, tmp_path):
    stages.tables['closer_cases'][0]['fulfilment_order_id'] = None
    stages.tables['fulfilment_orders'] = []
    row = mid(stages, tmp_path)
    assert row['fulfilment_order_id'] is None
    assert counts([row])['qualified_conversation'] == 1
    assert counts([row])['commercial_terms'] == counts([row])['recognized_revenue'] == 0


@pytest.mark.parametrize('change', ['future','synthetic','forecast','model','advisory','missing_note','missing_actor',
    'tenant','intent','reply','case','prospect','buyer','opportunity','conversation'])
def test_invalid_qualification_evidence_is_not_truth(stages, tmp_path, change):
    event = stages.tables['closer_events'][0]
    if change == 'future': event['occurred_at'] = '2099-01-01T00:00:00+00:00'
    if change == 'synthetic': event['synthetic'] = True
    if change == 'forecast': event['payload']['forecast_derived'] = True
    if change == 'model': event['payload']['model_inferred'] = True
    if change == 'advisory': event['event_type'] = 'recommendation'
    if change == 'missing_note': event['payload']['note'] = ''
    if change == 'missing_actor': event['actor'] = ''
    if change == 'case': event['case_id'] = 'wrong'
    if change in ('tenant','intent','reply','prospect','buyer','opportunity','conversation'):
        event['payload'][{'tenant':'tenant_id','intent':'outbound_intent_id','reply':'reply_id','prospect':'prospect_id',
                         'buyer':'buyer_id','opportunity':'opportunity_id','conversation':'conversation_id'}[change]] = 'wrong'
    row = mid(stages, tmp_path)
    assert counts([row])['qualified_conversation'] == 0
    assert counts([row])['commercial_terms'] == 1


@pytest.mark.parametrize('state', ['pending', 'draft', 'rejected', 'expired'])
def test_proposed_draft_rejected_expired_terms_do_not_count(stages, tmp_path, state):
    stages.tables['commercial_terms_reviews'][0]['status'] = state
    row = mid(stages, tmp_path)
    assert counts([row])['commercial_terms'] == 0
    assert counts([row])['qualified_conversation'] == 1


@pytest.mark.parametrize('change', ['future','expiry','synthetic','forecast','tenant','buyer','opportunity','order',
    'review_pointer','hash','price','currency','missing_actor','missing_approval','approval_order','approval_review'])
def test_invalid_terms_evidence_does_not_count(stages, tmp_path, change):
    review = stages.tables['commercial_terms_reviews'][0]
    approval = stages.tables['commercial_terms_events'][0]
    if change == 'future': review['decided_at'] = '2099-01-01T00:00:00+00:00'
    if change == 'expiry': review['terms']['expires_at'] = '2026-10-01T00:00:00+00:00'
    if change == 'synthetic': approval['synthetic'] = True
    if change == 'forecast': review['terms']['forecast_derived'] = True
    if change in ('tenant','buyer','opportunity'): review[change + '_id'] = 'wrong'
    if change == 'order': review['fulfilment_order_id'] = 'wrong'
    if change == 'review_pointer': stages.tables['fulfilment_orders'][0]['commercial_payload']['commercial_terms_review_id'] = 'wrong'
    if change == 'hash': review['commercial_terms_sha256'] = 'c'*64
    if change == 'price': review['price_cents'] = 99999
    if change == 'currency': review['terms']['currency'] = 'UNKNOWN'
    if change == 'missing_actor': review['decided_by'] = None
    if change == 'missing_approval': stages.tables['commercial_terms_events'] = []
    if change == 'approval_order': approval['fulfilment_order_id'] = 'wrong'
    if change == 'approval_review': approval['review_id'] = 'wrong'
    row = mid(stages, tmp_path)
    assert counts([row])['commercial_terms'] == 0
    assert counts([row])['qualified_conversation'] == 1


def test_accepted_terms_need_actual_matching_acceptance_evidence(stages, tmp_path):
    accepted_at = '2026-10-03T10:00:00+00:00'
    payload = stages.tables['fulfilment_orders'][0]['commercial_payload']
    payload.update(buyer_acceptance_kind='signed_agreement', buyer_acceptance_reference='agreement:1',
        buyer_accepted_at=accepted_at, buyer_acceptance_recorded_by='human.operator')
    stages.tables['commercial_terms_events'].append(dict(id='acceptance-event-1', review_id='review-1',
        fulfilment_order_id=ORDER, event_type='accepted', actor='human.operator', occurred_at=accepted_at,
        payload=dict(evidence_kind='signed_agreement', evidence_reference='agreement:1', accepted_at=accepted_at,
                     commercial_terms_sha256='b'*64)))
    row = mid(stages, tmp_path)
    assert row['commercial_terms_state'] == 'ACCEPTED'
    assert counts([row])['commercial_terms'] == 1
    assert counts([row])['verified_payment'] == counts([row])['recognized_revenue'] == 0
    stages.tables['commercial_terms_events'][-1]['payload']['evidence_reference'] = 'wrong'
    assert counts([mid(stages, tmp_path)])['commercial_terms'] == 0


def test_terms_do_not_require_or_imply_qualification(stages, tmp_path):
    stages.tables['closer_events'] = []
    row = mid(stages, tmp_path)
    result = counts([row])
    assert result['commercial_terms'] == 1 and result['qualified_conversation'] == 0
    assert result['verified_payment'] == result['recognized_revenue'] == 0


def test_duplicate_canonical_stage_evidence_counts_once(stages, tmp_path):
    first = mid(stages, tmp_path)
    second = deepcopy(first)
    second['intent_id'] = 'other-explicit-intent'
    second['outbound_intent_id'] = 'other-explicit-intent'
    for name in ('qualified_conversation_evidence','commercial_terms_evidence'):
        second[name]['outbound_intent_id'] = 'other-explicit-intent'
    result = counts([first,first,second])
    assert result['qualified_conversation'] == result['commercial_terms'] == 1


@pytest.mark.parametrize('key', ['tenant_id','outbound_intent_id','reply_id','closer_case_id','conversation_id',
    'prospect_id','buyer_id','opportunity_id','fulfilment_order_id'])
def test_consumers_reject_overridden_stage_identity(stages, tmp_path, key):
    row = mid(stages, tmp_path)
    for name in ('qualified_conversation_evidence','commercial_terms_evidence'):
        row[name][key] = 'wrong'
    assert counts([row])['qualified_conversation'] == counts([row])['commercial_terms'] == 0


def test_missing_linkage_and_name_email_time_proximity_cannot_attribute(stages, tmp_path):
    stages.tables['closer_cases'][0]['outbound_intent_id'] = 'wrong'
    for table in ('closer_cases','outbound_intents','fulfilment_orders'):
        stages.tables[table][0].update(email='same@example.com', business_name='Same company', created_at=THEN)
    rows = produce(stages, tmp_path)
    assert counts(rows)['qualified_conversation'] == counts(rows)['commercial_terms'] == 0
    assert 'qualified_conversation_evidence' not in rows[0]


def test_existing_verified_outcome_path_and_authority_remain_independent(stages, tmp_path):
    result = counts(produce(stages, tmp_path))
    assert result['qualified_conversation'] == result['commercial_terms'] == result['recognized_revenue'] == 1
    payload = funnel(produce(stages, tmp_path))
    assert payload['execution_authority'] == 'none' and not payload['winner_claim_allowed']
    assert (MIN_DELIVERED_PER_ARM, SEGMENT_MIN_DELIVERED, EXPLORATION_FRACTION) == (8,16,.20)


def test_actual_refresh_preserves_read_only_snapshot_and_stage_states(stages, tmp_path, monkeypatch):
    import scripts.refresh_adaptive_outreach_optimizer as runtime
    import empire_os.data_backends.empiredb as backend
    events=[]
    class Provider:
        @contextmanager
        def read_only_snapshot(self):
            events.append('read-only')
            yield stages
    monkeypatch.setattr(backend,'EmpireDbProvider',lambda connector:Provider())
    payload = runtime.refresh(tmp_path, dsn='postgresql://offline-unused', now=NOW)
    assert events == ['read-only'] and payload['outcome_bridge']['read_only'] is True
    assert payload['middle_funnel_states'] == {'qualified_conversation':{'QUALIFIED':1},'commercial_terms':{'APPROVED':1}}
    assert payload['outbound_mutation'] is False


@pytest.mark.parametrize('key', ['reply_id','closer_case_id','conversation_id','tenant_id','prospect_id','buyer_id','opportunity_id','fulfilment_order_id'])
def test_caller_ids_cannot_override_persisted_identity(stages, tmp_path, key):
    intent = stages.tables['outbound_intents'][0]
    record = dict(intent_id=INTENT, metadata=deepcopy(intent['metadata']), **{key:'wrong'})
    with pytest.raises(ValueError):
        ExecutionBusDataRepository(stages).outreach_middle_funnel_record(record, repo_root=tmp_path, as_of=NOW)


@pytest.mark.parametrize('key', ['tenant_id','buyer_id','opportunity_id','closer_case_id','outbound_intent_id'])
def test_approval_event_payload_identity_cannot_contradict_canonical_binding(stages, tmp_path, key):
    stages.tables['commercial_terms_events'][0]['payload'][key] = 'wrong'
    assert counts([mid(stages,tmp_path)])['commercial_terms'] == 0


def test_model_evidence_does_not_become_a_qualification_decision(stages, tmp_path):
    stages.tables['closer_events'][0]['payload']['source_type'] = 'model_inference'
    assert counts([mid(stages,tmp_path)])['qualified_conversation'] == 0


def test_literal_buyer_price_and_materializer_proposals_are_not_terms_success(stages, tmp_path):
    from empire_os.buyer_commercial_terms_intake import parse_buyer_stated_price
    assert parse_buyer_stated_price('We pay $100 per lead')['has_explicit_price_evidence']
    review = stages.tables['commercial_terms_reviews'][0]
    review.update(status='pending',proposed_by='AI-recommendation')
    row = mid(stages,tmp_path)
    assert row['commercial_terms_state'] == 'PROPOSED'
    assert counts([row])['commercial_terms'] == counts([row])['recognized_revenue'] == 0


def test_middle_stages_without_v2c_lineage_do_not_fabricate_prediction_refs(stages, tmp_path):
    stages.tables['outbound_intents'][0]['metadata'].pop('causal_lineage')
    stages.tables['fulfilment_orders'][0]['commercial_payload'].pop('causal_lineage')
    row = mid(stages,tmp_path)
    assert row['prediction_ref'] is row['decision_ref'] is row['execution_ref'] is row['outcome_ref'] is None
    assert counts([row])['qualified_conversation'] == counts([row])['commercial_terms'] == 1


def test_unsubscribe_and_sample_safeguards_are_not_changed_by_middle_stages(stages,tmp_path):
    row = mid(stages,tmp_path)
    row['classification'] = 'unsubscribe'
    payload = funnel([row])
    assert counts([row])['unsubscribes'] == 1 and counts([row])['commercial_replies'] == 0
    assert payload['winner_claim_allowed'] is False and payload['execution_authority'] == 'none'


def test_payment_alone_cannot_be_recognized_revenue(stages,tmp_path):
    stages.tables['commercial_events'] = []
    rows = produce(stages,tmp_path)
    assert counts(rows)['commercial_terms'] == 1
    assert counts(rows)['recognized_revenue'] == 0


def test_case_explicit_buyer_opportunity_binding_survives_missing_original_optional_ids(stages,tmp_path):
    stages.tables['outbound_intents'][0]['buyer_id'] = None
    stages.tables['outbound_intents'][0]['opportunity_id'] = None
    stages.tables['commercial_events'] = []
    rows = produce(stages,tmp_path)
    assert rows[0]['buyer_id'] == 'buyer-1' and rows[0]['opportunity_id'] == OPPORTUNITY
    assert counts(rows)['qualified_conversation'] == counts(rows)['commercial_terms'] == 1


@pytest.mark.parametrize('key,value', [('price_cents',99999),('settlement_asset','unknown'),('settlement_chain','unknown')])
def test_terms_content_cannot_contradict_approved_economics(stages,tmp_path,key,value):
    stages.tables['commercial_terms_reviews'][0]['terms'][key] = value
    stages.tables['fulfilment_orders'][0]['commercial_payload']['commercial_terms'][key] = value
    assert counts([mid(stages,tmp_path)])['commercial_terms'] == 0


def test_explicit_expiry_is_preserved_without_counting_terms_success(stages,tmp_path):
    stages.tables['commercial_terms_reviews'][0]['terms']['expires_at'] = '2026-10-01T00:00:00+00:00'
    row = mid(stages,tmp_path)
    assert row['commercial_terms_state'] == 'EXPIRED'
    assert counts([row])['commercial_terms'] == 0


def test_qualified_event_must_agree_with_persisted_closer_progression(stages,tmp_path):
    stages.tables['closer_cases'][0]['state'] = 'engaged'
    row = mid(stages,tmp_path)
    assert counts([row])['qualified_conversation'] == 0
    assert counts([row])['commercial_terms'] == 1


@pytest.mark.parametrize('state',['raw','qualified','matched'])
def test_approved_terms_must_agree_with_persisted_order_progression(stages,tmp_path,state):
    stages.tables['fulfilment_orders'][0]['state'] = state
    row = mid(stages,tmp_path)
    assert counts([row])['qualified_conversation'] == 1
    assert counts([row])['commercial_terms'] == 0
