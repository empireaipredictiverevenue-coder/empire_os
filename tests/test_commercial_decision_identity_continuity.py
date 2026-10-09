"""Offline contract fixtures. Queue files stay in pytest temporary directories."""
from dataclasses import replace
import json
import subprocess

import pytest

from empire_os.opportunity_quant_review import build_quant_review
from empire_os.predictive_revenue_jev import compile_predictive_revenue_jev
from empire_os.department_work_queue import DepartmentWorkQueue, DepartmentWorkQueueError
from empire_os.decision_identity import bind_execution_evidence
from empire_os.economic_memory import build_economic_memory_snapshot
from test_predictive_revenue_jev import signal, normalized, NOW
from test_department_work_queue import step
from test_economic_memory import _evaluation, _verified_packet


KEY = 'market:roofing:denver'


def quant():
    inputs = dict(normalized()['quant_inputs'], revenue_low_cents=130000,
        revenue_high_cents=160000, success_cost_low_cents=25000, success_cost_high_cents=35000)
    return build_quant_review({'items':[{'opportunity_key':KEY,
        'normalization':{'quant_inputs':inputs}, 'decision_provenance':{
            'schema_version':'empire.real_world_decision.v1', 'decision_id':'a'*64,
            'execution_authority':'none', 'hidden_reasoning':'MUST NOT PROPAGATE'}}]}, trials=100)['items'][0]


def jev(q=None):
    return compile_predictive_revenue_jev(signal=signal(), normalized_opportunity=normalized(),
        quant_review=q if q is not None else quant(), as_of=NOW,
        actions=[{'action_key':'review', 'probability_action_changes_outcome':0.5,
                  'incremental_revenue_if_changed_cents':150000, 'action_cost_cents':1000, 'confidence':0.8}])


def work_step(packet=None, *, shadow=True, **overrides):
    packet = packet or jev()
    provenance = dict(opportunity_key=packet.opportunity_key, prediction_ref=packet.prediction_ref,
        source_ref='recommendation_snapshot:test-1', state_ref='state_snapshot:test-1',
        shadow_only=shadow, selection_authority_ref=None if shadow else 'authority:test:selection-1',
        execution_authority='none')
    provenance.update(overrides)
    return step(target_component='commercial_product_catalog', authority='internal_write',
        commercial_decision_provenance=provenance)


def enqueue(tmp_path, *, shadow=True, **overrides):
    queue = DepartmentWorkQueue(tmp_path)
    item, _ = queue.enqueue_step(plan_id='astra_plan_test', step=work_step(shadow=shadow, **overrides))
    return queue, item


def memory(work, *, linked=True, verified=True):
    row = work.as_dict()
    if linked:
        row['result']['causal_outcome_refs'] = ['canonical:commercial_outcomes:outcome-1']
    return build_economic_memory_snapshot(executive_evaluation=_evaluation(), department_work=[row],
        cortex_learning={'packets':[_verified_packet()]} if verified else {'packets':[]})


def test_quant_identity_survives_jev_without_reasoning_or_authority():
    q = quant()
    packet = jev(q)
    assert packet.prediction_ref == q['prediction_ref']
    assert packet.opportunity_key == q['opportunity_key']
    assert packet.decision_provenance['decision_id'] == q['decision_provenance']['decision_id']
    assert 'hidden_reasoning' not in packet.decision_provenance
    assert packet.recommendation_only is True
    assert packet.actual_revenue is False
    assert packet.execution_authority == packet.decision_provenance['execution_authority'] == 'none'
    assert not hasattr(packet, 'outcome_ref')
    assert packet.recommended_action['prediction_ref'] == q['prediction_ref']
    assert packet.next_best_action['recommended_action']['prediction_ref'] == q['prediction_ref']
    assert packet.next_best_action['actions'][0]['opportunity_key'] == KEY


def test_prediction_candidate_and_task_survive_selected_work(tmp_path):
    packet = jev()
    queue, item = enqueue(tmp_path)
    identity = item.decision_identity
    assert identity['candidate_id'] == packet.opportunity_key
    assert identity['prediction_ref'] == packet.prediction_ref
    assert identity['task_key'] == item.id
    claimed = queue.claim_next()
    assert claimed.decision_identity == identity
    assert identity['execution_performed'] is False
    assert identity['execution_ref'] is None
    assert identity['causal_eligible'] is False


def test_identical_inputs_have_identical_decision_ref_without_clock_dependency(tmp_path, monkeypatch):
    q1, one = enqueue(tmp_path/'one')
    monkeypatch.setattr(DepartmentWorkQueue, '_now', staticmethod(lambda:'2099-01-01T00:00:00+00:00'))
    q2, two = enqueue(tmp_path/'two')
    assert one.created_at != two.created_at
    assert one.decision_identity == two.decision_identity


def test_changed_prediction_changes_decision_ref(tmp_path):
    _, one = enqueue(tmp_path/'one')
    _, two = enqueue(tmp_path/'two', prediction_ref='quant_prediction:changed')
    assert one.decision_identity['decision_ref'] != two.decision_identity['decision_ref']


def test_missing_prediction_remains_missing_through_jev_and_work(tmp_path):
    q = quant()
    q['prediction_ref'] = None
    packet = jev(q)
    assert packet.prediction_ref is None
    queue = DepartmentWorkQueue(tmp_path)
    work, _ = queue.enqueue_step(plan_id='astra_plan_test', step=work_step(packet))
    assert work.decision_identity['prediction_ref'] is None


@pytest.mark.parametrize('field,value', [('opportunity_key','other'), ('prediction_ref','')])
def test_jev_conflicting_or_invalid_origin_fails_closed(field, value):
    q = quant()
    q[field] = value
    with pytest.raises(ValueError):
        jev(q)


def test_shadow_cannot_claim_selection_authority(tmp_path):
    with pytest.raises(ValueError, match='shadow'):
        enqueue(tmp_path, selection_authority_ref='authority:invented')


def test_shadow_cannot_bind_execution(tmp_path):
    queue, item = enqueue(tmp_path)
    with pytest.raises(ValueError, match='shadow'):
        bind_execution_evidence(item.decision_identity, execution_ref=f'department_work:{item.id}')
    claimed = queue.claim_next()
    done = queue.complete(claimed, {'returncode':0}, evidence_refs=('test:completion',), execution_completed=True)
    assert done.result['decision_identity']['execution_performed'] is False
    assert memory(done)['decision_outcome_attribution_count'] == 0


def test_nonshadow_requires_external_selection_evidence(tmp_path):
    with pytest.raises(ValueError, match='selection_authority_ref'):
        enqueue(tmp_path, shadow=False, selection_authority_ref=None)


def test_selection_and_done_without_verified_execution_are_noncausal(tmp_path):
    queue, item = enqueue(tmp_path, shadow=False)
    claimed = queue.claim_next()
    assert claimed.decision_identity['execution_performed'] is False
    done = queue.complete(claimed, {'status':'PROPOSED'}, evidence_refs=('test:proposal',))
    assert done.result['decision_identity']['execution_performed'] is False
    assert memory(done)['decision_outcome_attribution_count'] == 0


@pytest.mark.parametrize('status', ['PROPOSED', 'QUEUED', 'SELECTED', 'ATTEMPTED', 'BLOCKED', 'SIMULATED'])
def test_noncompleted_status_cannot_be_bound(tmp_path, status):
    queue, item = enqueue(tmp_path, shadow=False)
    claimed = queue.claim_next()
    with pytest.raises(DepartmentWorkQueueError, match='non-completed'):
        queue.complete(claimed, {'status':status}, evidence_refs=('test:attempt',), execution_completed=True)
    assert queue.counts()['done'] == 0


def test_actual_completion_uses_canonical_binder_and_stable_work_ref(tmp_path, monkeypatch):
    import empire_os.department_work_queue as module
    queue, item = enqueue(tmp_path, shadow=False)
    claimed = queue.claim_next()
    called = []
    def spy(identity, *, execution_ref):
        called.append(execution_ref)
        return bind_execution_evidence(identity, execution_ref=execution_ref)
    monkeypatch.setattr(module, 'bind_execution_evidence', spy)
    done = queue.complete(claimed, {'returncode':0}, evidence_refs=('test:completion',), execution_completed=True)
    assert called == [f'department_work:{item.id}']
    bound = done.result['decision_identity']
    assert bound['execution_ref'] == called[0]
    assert bound['execution_performed'] is True
    assert bound['decision_ref'] == item.decision_identity['decision_ref']
    again = queue.complete(claimed, {'status':'ATTEMPTED'})
    assert again.result['decision_identity'] == bound
    assert called == [f'department_work:{item.id}']
    assert bound['execution_authority'] == 'none'


def test_verified_execution_and_explicit_outcome_keep_full_identity(tmp_path):
    queue, item = enqueue(tmp_path, shadow=False)
    done = queue.complete(queue.claim_next(), {'returncode':0}, evidence_refs=('test:completion',), execution_completed=True)
    result = memory(done)
    assert result['decision_outcome_attribution_count'] == 1
    row = result['decision_outcome_attributions'][0]
    for field in ('decision_ref','prediction_ref'):
        assert row[field] == done.result['decision_identity'][field]
    assert row['execution_ref'] == f'department_work:{item.id}'
    assert row['outcome_ref'] == 'canonical:commercial_outcomes:outcome-1'
    assert row['execution_authority'] == 'none'
    assert 'causal_outcome_refs' not in done.result


@pytest.mark.parametrize('linked,verified', [(False,True), (True,False)])
def test_no_causal_credit_without_explicit_link_and_verified_outcome(tmp_path, linked, verified):
    queue, item = enqueue(tmp_path, shadow=False)
    done = queue.complete(queue.claim_next(), {'returncode':0}, evidence_refs=('test:completion',), execution_completed=True)
    assert memory(done, linked=linked, verified=verified)['decision_outcome_attribution_count'] == 0


def test_cortex_still_rejects_unverified_won_despite_prediction():
    from test_cortex_learning_loop import _twin, _verified_outcome
    from empire_os.cortex_learning_loop import build_cortex_learning_packet
    twin = _twin()
    twin['outcomes']['history'] = [_verified_outcome('won')]
    twin['prediction_ref'] = jev().prediction_ref
    packet = build_cortex_learning_packet(twin)
    assert packet['label']['available'] is False
    assert {'verified_payment_missing','verified_fulfilment_missing','recognized_revenue_missing'} <= set(packet['label']['blockers'])


def test_worker_binds_only_actual_allowlisted_completion(tmp_path, monkeypatch):
    import empire_os.department_worker as worker
    queue, item = enqueue(tmp_path, shadow=False)
    monkeypatch.setattr(worker.subprocess, 'run', lambda command, **kwargs:
        subprocess.CompletedProcess(command, 0, stdout='{"ok":true}', stderr=''))
    result = worker.run_one_department_work(tmp_path)
    assert result['state'] == 'DONE'
    done = queue._load(queue.done/f'{item.id}.json')
    assert done.result['decision_identity']['execution_ref'] == f'department_work:{item.id}'
    assert done.result['decision_identity']['prediction_ref'] == jev().prediction_ref


def test_astra_preserves_quant_prediction_into_real_dispatch(tmp_path):
    from empire_os.astra_executive import build_executive_snapshot
    from empire_os.astra_department_dispatch import dispatch_executive_plan
    from test_astra_executive import routes, status, pulse
    q = quant()
    plan = build_executive_snapshot(predictive_status=status(), evidence_routes=routes(),
        next_best_action={'actions':[]}, revenue_pulse=pulse(),
        quant_review={'items':[q]})
    selected = [s for s in plan['plan'] if s['commercial_decision_provenance']]
    assert selected
    p = selected[0]['commercial_decision_provenance']
    assert p['prediction_ref'] == q['prediction_ref']
    assert p['opportunity_key'] == KEY
    path = tmp_path/'runtime/astra/executive_latest.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(plan))
    dispatch_executive_plan(tmp_path)
    queue = DepartmentWorkQueue(tmp_path)
    items = [queue._load(path) for path in queue.ready.glob('*.json')]
    work = next(item for item in items if item.decision_identity)
    assert work.decision_identity['prediction_ref'] == q['prediction_ref']
    assert work.decision_identity['candidate_id'] == KEY
    assert work.decision_identity['shadow_only'] is True


def test_existing_work_cannot_be_silently_rebound(tmp_path):
    queue, item = enqueue(tmp_path)
    with pytest.raises(DepartmentWorkQueueError, match='conflicting'):
        queue.enqueue_step(plan_id='astra_plan_test', step=work_step(prediction_ref='quant_prediction:other'))
    assert queue._load(queue.ready/f'{item.id}.json').decision_identity == item.decision_identity


def test_completion_uses_persisted_identity_not_caller_mutation(tmp_path):
    queue, item = enqueue(tmp_path, shadow=False)
    claimed = queue.claim_next()
    claimed.decision_identity['prediction_ref'] = 'injected'
    done = queue.complete(claimed, {'returncode':0}, evidence_refs=('test:completion',), execution_completed=True)
    assert done.result['decision_identity']['prediction_ref'] == item.decision_identity['prediction_ref']


def test_execution_binding_requires_active_lease(tmp_path):
    queue, item = enqueue(tmp_path, shadow=False)
    claimed = queue.claim_next()
    claimed.lease_id = None
    with pytest.raises(DepartmentWorkQueueError, match='active work lease'):
        queue.complete(claimed, {'returncode':0}, evidence_refs=('test:completion',), execution_completed=True)


@pytest.mark.parametrize('value', [{'confidence':0.99}, True, 123])
def test_structured_reference_never_coerces_prose_scores_or_objects(tmp_path, value):
    with pytest.raises(DepartmentWorkQueueError, match='structured decision reference'):
        enqueue(tmp_path, prediction_ref=value)


def test_queued_coder_proposal_does_not_bind_execution(tmp_path, monkeypatch):
    import empire_os.department_worker as worker
    queue = DepartmentWorkQueue(tmp_path)
    item, _ = queue.enqueue_step(plan_id='astra_plan_test',
        step=dict(work_step(shadow=False), target_component='empire_coder'))
    monkeypatch.setattr(worker, '_coder_bridge', lambda root, item: {
        'coder_task_id':'test-task', 'coder_job_id':'test-job', 'status':'QUEUED'})
    output = worker.run_one_department_work(tmp_path)
    assert output['state'] == 'DONE'
    done = queue._load(queue.done/f'{item.id}.json')
    assert done.result['decision_identity']['execution_performed'] is False
    assert memory(done)['decision_outcome_attribution_count'] == 0


def test_astra_buyer_work_keeps_originating_quant_identity():
    from empire_os.astra_executive import build_executive_snapshot
    from test_astra_executive import status, pulse, nba
    source = quant()
    actions = nba()
    actions['actions'][0].update(opportunity_key=KEY, prediction_ref=source['prediction_ref'])
    plan = build_executive_snapshot(predictive_status=status(), evidence_routes={},
        next_best_action=actions, revenue_pulse=pulse(), quant_review={'items':[source]})
    work = next(row for row in plan['plan'] if row['action'] == 'verify_decision_maker')
    assert work['commercial_decision_provenance']['prediction_ref'] == source['prediction_ref']
    assert work['commercial_decision_provenance']['opportunity_key'] == KEY


def test_astra_replay_ignores_refresh_clock_and_missing_prediction_stays_missing():
    from empire_os.astra_executive import _commercial_selection_provenance
    source = quant()
    source['prediction_ref'] = None
    one = _commercial_selection_provenance({'quant_review_items':[source]}, KEY)
    source['generated_at'] = '2099-01-01T00:00:00+00:00'
    two = _commercial_selection_provenance({'quant_review_items':[source]}, KEY)
    assert one == two
    assert one['prediction_ref'] is None


def test_jev_does_not_relabel_an_action_from_another_prediction():
    with pytest.raises(ValueError, match='action origin'):
        compile_predictive_revenue_jev(signal=signal(), normalized_opportunity=normalized(),
            quant_review=quant(), as_of=NOW, actions=[{'action_key':'review', 'prediction_ref':'other'}])


def test_completion_with_no_result_evidence_does_not_bind(tmp_path):
    queue, item = enqueue(tmp_path, shadow=False)
    with pytest.raises(DepartmentWorkQueueError, match='completed execution evidence'):
        queue.complete(queue.claim_next(), {'returncode':0}, execution_completed=True)
