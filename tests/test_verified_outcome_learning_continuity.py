"""Scoped offline fixtures; no database or outbound operations."""
import copy
import json
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.outcome_feedback import build_verified_outcome_feedback, validate_verified_feedback
from empire_os.predictive_calibration import review_commercial_prediction
from empire_os.economic_memory import build_economic_memory_snapshot
from empire_os.astra_feedback import build_verified_learning_feedback
from empire_os.predictive_intelligence import build_product_estimate
from empire_os.cortex_learning_loop import build_cortex_learning_packet
from test_cortex_learning_loop import _twin, _verified_outcome
from test_commercial_decision_identity_continuity import enqueue, KEY

NOW = datetime(2026,10,5,12,tzinfo=timezone.utc)
TENANT = 'tenant-A'


def twin():
    row = _twin()
    row['tenant_id'] = TENANT
    outcome = dict(_verified_outcome(), tenant_id=TENANT, recorded_at='2026-10-04T12:00:00+00:00',
        evidence={'tenant_id':TENANT, 'opportunity_key':KEY, 'prediction_ref':'quant_prediction:original',
                  'decision_ref':None, 'execution_ref':None})
    row['outcomes']['history'] = [outcome]
    row['commercial']['payment_evidence'] = [{'id':'payment-1', 'tenant_id':TENANT,
        'fulfilment_order_id':'order-1', 'transaction_hash':'test-proof', 'verified_at':'2026-10-04T11:00:00+00:00'}]
    row['commercial']['fulfilment_orders'] = [{'id':'order-1', 'tenant_id':TENANT, 'product_id':'prod-1',
        'state':'outcome_captured', 'delivered_at':'2026-10-04T10:00:00+00:00'}]
    row['revenue_truth'].update(tenant_id=TENANT, fulfilment_order_id='order-1',
        recognized_at='2026-10-04T13:00:00+00:00', recognized_revenue_cents=1000,
        actual_cost_cents=1200, realized_gp_cents=-200, actual_cost_verified=True, actual_revenue=True,
        evidence_refs=['canonical:commercial_events:revenue-1'], actual_cost_evidence_refs=['canonical:commercial_events:cost-1'])
    return row


def feedback(row=None):
    return build_verified_outcome_feedback(row or twin(), tenant_id=TENANT, as_of=NOW)


def prediction():
    return dict(tenant_id=TENANT, opportunity_key=KEY, prediction_ref='quant_prediction:original',
        prediction_type='conversion_probability', predicted_probability=0.6,
        predicted_at='2026-10-01T12:00:00+00:00', horizon_until='2026-10-06T12:00:00+00:00',
        evidence_refs=['quant_prediction:original'])


def calibration(f=None, p=None):
    return review_commercial_prediction(prediction=p or prediction(), feedback=f or feedback(), tenant_id=TENANT, as_of=NOW)


def memory(f=None, work=()):
    f = f or feedback()
    return build_economic_memory_snapshot(executive_evaluation={}, department_work=list(work),
        cortex_learning={'packets':[f['cortex_packet']]}, tenant_id=TENANT,
        verified_feedback=[f], calibration_reviews=[calibration(f)], as_of=NOW)


def test_verified_outcome_identity_and_separate_prediction_actual_calibration():
    f = feedback()
    assert f['outcome_ref'] == 'canonical:commercial_outcomes:outcome-1'
    c = calibration(f)
    assert c['prediction_ref'] == 'quant_prediction:original'
    assert c['predicted_value'] == 0.6 and c['actual_value'] == 1
    assert c['signed_error'] == 0.4 and c['brier_score'] == 0.16
    assert c['predicted_at'] != c['actual_at']
    assert c == calibration(f)
    assert c['execution_authority'] == 'none' and c['shadow_only'] is True
    assert c['promoted_learning'] is False


@pytest.mark.parametrize('kind', ['prediction', 'expected_revenue', 'selected', 'execution'])
def test_non_outcomes_never_supply_commercial_learning(kind):
    row = _twin()
    row['tenant_id'] = TENANT
    row[kind] = {'expected_revenue':100000, 'execution_performed':True}
    with pytest.raises(ValueError):
        feedback(row)


@pytest.mark.parametrize('missing', ['payment', 'fulfilment', 'revenue'])
def test_partial_commercial_chain_cannot_verify_win(missing):
    row = twin()
    if missing == 'payment':
        row['commercial']['payment_evidence'] = []
    elif missing == 'fulfilment':
        row['commercial']['fulfilment_orders'] = []
    else:
        row['revenue_truth']['recognized_revenue_cents'] = 0
    with pytest.raises(ValueError):
        feedback(row)
    assert build_cortex_learning_packet(row)['label']['available'] is False


@pytest.mark.parametrize('change', ['synthetic', 'forecast_derived', 'unverified', 'no_evidence', 'no_id'])
def test_invalid_outcome_cannot_create_verified_label(change):
    row = twin()
    outcome = row['outcomes']['history'][0]
    if change == 'unverified': outcome['verified'] = False
    elif change == 'no_evidence': outcome['evidence_reference'] = ''
    elif change == 'no_id': outcome.pop('id')
    else: outcome[change] = True
    with pytest.raises(ValueError): feedback(row)
    assert build_cortex_learning_packet(row)['label']['available'] is False


@pytest.mark.parametrize('scope', ['outcome', 'payment', 'fulfilment', 'revenue', 'prediction'])
def test_tenant_mismatch_fails_closed(scope):
    row = twin()
    if scope == 'prediction':
        p = prediction(); p['tenant_id'] = 'tenant-B'
        with pytest.raises(ValueError): calibration(p=p)
        return
    if scope == 'outcome': row['outcomes']['history'][0]['tenant_id'] = 'tenant-B'
    elif scope == 'revenue': row['revenue_truth']['tenant_id'] = 'tenant-B'
    else: row['commercial']['payment_evidence' if scope=='payment' else 'fulfilment_orders'][0]['tenant_id'] = 'tenant-B'
    with pytest.raises(ValueError): feedback(row)


@pytest.mark.parametrize('field', ['recorded_at', 'verified_at', 'delivered_at', 'recognized_at'])
def test_future_verification_is_not_available_at_original_time(field):
    row = twin(); future = (NOW+timedelta(days=1)).isoformat()
    if field == 'recorded_at': row['outcomes']['history'][0][field] = future
    elif field == 'recognized_at': row['revenue_truth'][field] = future
    else: row['commercial']['payment_evidence' if field=='verified_at' else 'fulfilment_orders'][0][field] = future
    with pytest.raises(ValueError): feedback(row)


def test_learning_attaches_after_fact_without_mutating_original_decision():
    from test_real_world_decision_intelligence import artifact
    original = artifact()
    before = copy.deepcopy(original)
    p = prediction(); p['decision_snapshot'] = original
    reviewed = calibration(p=p)
    assert original == before
    assert reviewed['prediction']['decision_snapshot'] == before
    with pytest.raises(ValueError):
        review_commercial_prediction(prediction=prediction(), feedback=feedback(), tenant_id=TENANT,
                                   as_of=datetime(2026,10,4,12,30,tzinfo=timezone.utc))


def test_original_prediction_window_cannot_be_rewritten():
    p = prediction(); p['predicted_at'] = NOW.isoformat()
    with pytest.raises(ValueError): calibration(p=p)
    p = prediction(); p['horizon_until'] = '2026-10-02T12:00:00+00:00'
    with pytest.raises(ValueError): calibration(p=p)


def test_memory_separates_outcome_calibration_and_causal_credit():
    m = memory()
    assert m['outcome_conditioned_memory_count'] == 1
    assert m['calibration_evidence_count'] == 1
    assert m['department_episode_count'] == 0
    assert m['decision_outcome_attribution_count'] == 0
    assert m['outcome_conditioned_memories'][0]['memory_type'] == 'outcome_conditioned'
    assert m['learning_stage'] == 'SHADOW_LEARNING'


def completed_work(tmp_path, *, execute=True, linked=True):
    queue, item = enqueue(tmp_path, shadow=False, tenant_id=TENANT)
    done = queue.complete(queue.claim_next(), {'returncode':0}, evidence_refs=('test:done',), execution_completed=execute)
    if linked: done.result['causal_outcome_refs'] = ['canonical:commercial_outcomes:outcome-1']
    row = twin()
    row['outcomes']['history'][0]['evidence'].update(
        prediction_ref=item.decision_identity['prediction_ref'],
        decision_ref=item.decision_identity['decision_ref'], execution_ref=f'department_work:{item.id}')
    f = feedback(row)
    p = prediction(); p['prediction_ref'] = f['prediction_ref']
    return done.as_dict(), f, review_commercial_prediction(prediction=p, feedback=f, tenant_id=TENANT, as_of=NOW)


@pytest.mark.parametrize('failure', [None, 'decision', 'execution', 'tenant', 'no_execution', 'no_link'])
def test_causal_lineage_only_with_correct_verified_execution_and_link(tmp_path, failure):
    work, f, c = completed_work(tmp_path, execute=failure!='no_execution', linked=failure!='no_link')
    if failure in ('decision','execution'):
        key=failure+'_ref'; f[key]='wrong'; f['cortex_packet']['learning_lineage'][key]='wrong'
        p=c['prediction']; c=review_commercial_prediction(prediction=p, feedback=f, tenant_id=TENANT, as_of=NOW)
    if failure=='tenant': work['tenant_id']='tenant-B'
    m=build_economic_memory_snapshot(executive_evaluation={}, department_work=[work],
        cortex_learning={'packets':[f['cortex_packet']]}, tenant_id=TENANT,
        verified_feedback=[f], calibration_reviews=[c], as_of=NOW)
    assert m['decision_outcome_attribution_count'] == (1 if failure is None else 0)
    if failure is None:
        attributed=m['decision_outcome_attributions'][0]
        for key in ('decision_ref','prediction_ref','execution_ref','outcome_ref','tenant_id'):
            assert attributed[key] == f[key]


def test_astra_consumes_shadow_feedback_and_unverified_cannot_change_it():
    m=memory(); observed=build_verified_learning_feedback(m, tenant_id=TENANT, as_of=NOW)
    assert observed['outcome_calibration']['negative_margin_orders'] == 1
    assert observed['shadow_only'] and not observed['promoted_learning']
    assert observed['execution_authority'] == 'none'
    bad=copy.deepcopy(m); bad['verified_learning_feedback'][0]['verified_outcome']=False
    with pytest.raises(ValueError): build_verified_learning_feedback(bad,tenant_id=TENANT,as_of=NOW)
    assert observed == build_verified_learning_feedback(m,tenant_id=TENANT,as_of=NOW)


def test_verified_history_changes_existing_astra_review_with_same_current_evidence(tmp_path):
    from empire_os.astra_observer import run_observer_cycle
    from test_astra_observer import _complete_snapshot, _factory
    args=dict(dsn='postgresql://offline-fixture', operational_snapshot_json=json.dumps(_complete_snapshot()),
              rpc_factory=_factory([],[]), now_utc=NOW, tenant_id=TENANT)
    empty=build_economic_memory_snapshot(executive_evaluation={},department_work=[],cortex_learning={},tenant_id=TENANT)
    prior=run_observer_cycle(**args,economic_memory=empty,output_path=tmp_path/'prior.json')
    learned=run_observer_cycle(**args,economic_memory=memory(),output_path=tmp_path/'learned.json')
    restored=run_observer_cycle(**args,economic_memory=empty,output_path=tmp_path/'restored.json')
    assert prior['decision']['result'] == restored['decision']['result']
    assert prior['decision']['result'] != learned['decision']['result']
    assert learned['decision']['result']['recommended_job_type']=='review_negative_margin'
    assert learned['verified_learning_feedback']['execution_authority']=='none'
    assert learned['side_effects']=='none'


def test_verified_historical_cohort_uses_existing_beta_mechanism_only():
    rows=[]
    for index in range(20):
        t=twin(); t['outcomes']['history'][0]['id']='outcome-'+str(index)
        order='order-'+str(index)
        t['outcomes']['history'][0]['fulfilment_order_id']=order
        t['commercial']['fulfilment_orders'][0]['id']=order
        t['commercial']['payment_evidence'][0]['fulfilment_order_id']=order
        t['revenue_truth']['fulfilment_order_id']=order
        rows.append(feedback(t))
    prior=build_product_estimate('product',[],tenant_id=TENANT,as_of=NOW)
    learned=build_product_estimate('product',rows,tenant_id=TENANT,as_of=NOW)
    restored=build_product_estimate('product',[],tenant_id=TENANT,as_of=NOW)
    assert prior==restored and prior['probability_success'] is None
    assert learned['probability_success']==round(21/22,6)
    assert learned['execution_authority']=='none' and learned['shadow_only'] is True
    with pytest.raises(ValueError): build_product_estimate('product',rows,tenant_id='tenant-B',as_of=NOW)
    duplicate=build_product_estimate('product',rows+rows,tenant_id=TENANT,as_of=NOW)
    assert duplicate==learned


def test_scoped_cohort_cannot_contaminate_other_tenant_normalization():
    from empire_os.opportunity_evidence_normalizer import normalize_candidate
    estimate=build_product_estimate('managed_service',[feedback()],tenant_id=TENANT,as_of=NOW,min_terminal_samples=1)
    with pytest.raises(ValueError):
        normalize_candidate({'opportunity_key':KEY,'offer_key':'managed_service','tenant_id':'tenant-B'},
                            predictive_intelligence={'product_estimates':{'managed_service':estimate}})


def test_unknown_actual_cost_and_profit_stay_unknown():
    row=twin(); row['revenue_truth'].pop('actual_cost_verified')
    f=feedback(row)
    assert f['actual_cost_cents'] is None and f['gross_profit_cents'] is None
    observed=build_verified_learning_feedback(memory(f),tenant_id=TENANT,as_of=NOW)
    assert observed['outcome_calibration']['actual_cost_cents'] is None
    assert observed['outcome_calibration']['gross_profit_cents'] is None


def test_unscoped_cohort_cannot_train_scoped_candidate():
    from empire_os.opportunity_evidence_normalizer import normalize_candidate
    estimate = build_product_estimate('managed_service', [])
    with pytest.raises(ValueError):
        normalize_candidate({'opportunity_key': KEY, 'offer_key': 'managed_service', 'tenant_id': TENANT},
                            predictive_intelligence={'product_estimates': {'managed_service': estimate}})


def test_unscoped_projection_cannot_change_scoped_astra_decision(tmp_path):
    from empire_os.astra_observer import run_observer_cycle
    from test_astra_observer import _complete_snapshot, _factory
    empty=build_economic_memory_snapshot(executive_evaluation={},department_work=[],cortex_learning={},tenant_id=TENANT)
    result=run_observer_cycle(dsn='postgresql://offline-fixture',tenant_id=TENANT,economic_memory=empty,
        operational_snapshot_json=json.dumps(_complete_snapshot()),now_utc=NOW,output_path=tmp_path/'local.json',
        rpc_factory=_factory([{'conversion_outcome':'won','actual_revenue_cents':1000000,'gross_profit_cents':-999}],[]))
    assert result['calibration']['sample_size']==0
    assert result['decision']['result']['recommended_job_type']!='review_negative_margin'


@pytest.mark.parametrize('field', ['actual_revenue_cents','gross_profit_cents','available_at'])
def test_calibration_and_astra_reject_changed_verified_actuals(field):
    f=feedback()
    f[field]='2099-01-01T00:00:00+00:00' if field=='available_at' else 999999
    with pytest.raises(ValueError): calibration(f=f)


def test_missing_recognized_event_provenance_is_not_a_win():
    row=twin();row['revenue_truth'].pop('evidence_refs')
    with pytest.raises(ValueError): feedback(row)


def test_unvalidated_packet_cannot_enter_scoped_outcome_memory():
    f=feedback()
    m=build_economic_memory_snapshot(executive_evaluation={},department_work=[],
        cortex_learning={'packets':[f['cortex_packet']]},tenant_id=TENANT)
    assert m['outcome_conditioned_memory_count']==0
