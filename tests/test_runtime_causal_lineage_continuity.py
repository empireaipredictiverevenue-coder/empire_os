"""V2C offline proof using canonical queue fixtures and full independent records."""
import copy
import json
import subprocess
from datetime import datetime, timezone

import pytest

from empire_os.decision_identity import causal_lineage_from_work, validate_causal_lineage
from empire_os.department_work_queue import DepartmentWorkQueue
from empire_os.execution_bus_data_repository import ExecutionBusDataRepository
from empire_os.outcome_feedback import build_verified_feedback_from_records
from empire_os.predictive_calibration import review_commercial_prediction
from empire_os.economic_memory import build_economic_memory_snapshot
from empire_os.astra_feedback import build_verified_learning_feedback
from test_commercial_decision_identity_continuity import work_step, KEY

TENANT = '10000000-0000-4000-8000-000000000001'
OPPORTUNITY = '20000000-0000-4000-8000-000000000001'
ORDER = '30000000-0000-4000-8000-000000000001'
NOW = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
THEN = '2026-10-02T12:00:00+00:00'


@pytest.fixture
def completed(tmp_path, monkeypatch):
    monkeypatch.setattr(DepartmentWorkQueue, '_now', staticmethod(lambda: THEN))
    q = DepartmentWorkQueue(tmp_path)
    item, _ = q.enqueue_step(plan_id='astra_plan_test', step=work_step(shadow=False,
        tenant_id=TENANT, opportunity_id=OPPORTUNITY))
    import empire_os.department_worker as worker
    with monkeypatch.context() as patch:
        patch.setattr(worker.subprocess, 'run', lambda command, **kwargs:
            subprocess.CompletedProcess(command, 0, stdout='{"ok":true}', stderr=''))
        assert worker.run_one_department_work(tmp_path)['state'] == 'DONE'
    return DepartmentWorkQueue.read_completed_work(tmp_path, item.id)


def lineage(work, **kwargs):
    return causal_lineage_from_work(work, tenant_id=TENANT, opportunity_key=KEY,
                                   opportunity_id=OPPORTUNITY, **kwargs)


def records(work):
    causal = lineage(work)
    order = dict(id=ORDER, buyer_id='buyer-1', entity_id='entity-1', opportunity_id=OPPORTUNITY,
        product_id='product-1', state='settled', price_cents=10000,
        delivered_at='2026-10-03T12:00:00+00:00',
        commercial_payload={'existing':'preserved', 'commercial_terms_sha256':'b'*64, 'causal_lineage':causal})
    outcome = dict(id='40000000-0000-4000-8000-000000000001', fulfilment_order_id=ORDER,
        conversion_outcome='won', delivery_outcome='confirmed', evidence_kind='buyer_feedback',
        evidence_reference='independent:buyer-reply', recorded_at='2026-10-04T12:00:00+00:00',
        evidence={'independent':'preserved', 'causal_lineage':copy.deepcopy(causal)})
    payment = dict(id='payment-1', tenant_id=TENANT, fulfilment_order_id=ORDER, request_id='request-1',
        transaction_hash='0xfixture', verified_at='2026-10-04T11:00:00+00:00')
    costs = dict(fulfilment_order_id=ORDER, actual_cost_ready=True,
        acquisition_cost=dict(evidence_id='cost-1', source_type='provider_invoice', amount_cents=1000,
                              observed_at='2026-10-04T10:00:00+00:00'),
        fulfilment_cost=dict(evidence_id='cost-2', source_type='internal_actual', amount_cents=2000,
                             observed_at='2026-10-04T10:00:00+00:00'))
    event = dict(id='event-1', fulfilment_order_id=ORDER, opportunity_id=OPPORTUNITY,
        event_type='revenue_recognized', amount_cents=10000, cost_cents=3000, margin_cents=7000,
        occurred_at='2026-10-04T11:00:00+00:00', created_at='2026-10-04T13:00:00+00:00',
        payload=dict(actual_revenue=True, settlement_source='direct_payment', evidence_id='payment-1',
            payment_request_id='request-1', transaction_hash='0xfixture', actual_cost_evidence=costs,
            actual_cost_evidence_verified=True, causal_lineage=copy.deepcopy(causal)))
    return order, outcome, payment, event


def feedback(work, rows=None):
    order, outcome, payment, event = rows or records(work)
    return build_verified_feedback_from_records(order=order, outcome=outcome, payment_evidence=[payment],
        revenue_event=event, canonical_work=work, tenant_id=TENANT, as_of=NOW)


def test_bound_work_lineage_is_deterministic_and_preserves_all_refs(completed):
    original = copy.deepcopy(completed)
    causal = lineage(completed)
    assert causal == lineage(completed)
    for field in ('prediction_ref', 'decision_ref', 'execution_ref', 'selection_authority_ref', 'source_ref', 'state_ref'):
        assert causal[field] == completed['result']['decision_identity'][field]
    assert causal['tenant_id'] == TENANT and causal['opportunity_key'] == KEY
    assert causal['opportunity_id'] == OPPORTUNITY
    assert causal['execution_authority'] == 'none' and causal['execution_performed'] is True
    assert completed == original


def test_known_scope_survives_factory_quant_jev_astra_selection(tmp_path):
    from empire_os.opportunity_factory_intake import build_factory_intake
    from empire_os.opportunity_quant_review import build_quant_review
    from empire_os.predictive_revenue_jev import compile_predictive_revenue_jev
    from empire_os.astra_executive import _commercial_selection_provenance
    from test_predictive_revenue_jev import normalized,signal,NOW as JEV_NOW
    intake=build_factory_intake({'opportunity_key':KEY,'tenant_id':TENANT,'opportunity_id':OPPORTUNITY})
    intake['normalization']=normalized()
    q=build_quant_review({'items':[intake]},trials=100)['items'][0]
    row={**normalized(),'tenant_id':TENANT,'opportunity_id':OPPORTUNITY}
    packet=compile_predictive_revenue_jev(signal=signal(),normalized_opportunity=row,quant_review=q,as_of=JEV_NOW)
    assert packet.tenant_id==TENANT and packet.opportunity_id==OPPORTUNITY
    provenance=_commercial_selection_provenance({'quant_review_items':[q]},KEY,packet.as_dict())
    step=work_step();step['commercial_decision_provenance']=provenance
    item,_=DepartmentWorkQueue(tmp_path).enqueue_step(plan_id='astra_plan_test',step=step)
    assert item.tenant_id==TENANT and item.commercial_decision_provenance['opportunity_id']==OPPORTUNITY
    assert item.decision_identity['prediction_ref']==q['prediction_ref']
    assert item.decision_identity['shadow_only'] and item.decision_identity['execution_ref'] is None


@pytest.mark.parametrize('field',['tenant_id','opportunity_id'])
def test_jev_selection_rejects_scope_mismatch(field):
    from empire_os.predictive_revenue_jev import compile_predictive_revenue_jev
    from test_commercial_decision_identity_continuity import quant
    from test_predictive_revenue_jev import normalized,signal,NOW as JEV_NOW
    q=quant();q.update(tenant_id=TENANT,opportunity_id=OPPORTUNITY)
    with pytest.raises(ValueError):
        compile_predictive_revenue_jev(signal=signal(),normalized_opportunity={**normalized(),field:'wrong'},
            quant_review=q,as_of=JEV_NOW)


@pytest.mark.parametrize('key', ['tenant_id','opportunity_key','opportunity_id','prediction_ref','decision_ref','execution_ref'])
def test_caller_cannot_override_canonical_identity(completed, key):
    with pytest.raises(ValueError): lineage(completed, claimed_lineage={key:'wrong'})


@pytest.mark.parametrize('key,value', [('status','BLOCKED'), ('status','READY'), ('status','RUNNING'),
    ('result_evidence_refs',[]), ('execution_ref','department_work:wrong'), ('decision_ref','decision:wrong'),
    ('prediction_ref','quant_prediction:wrong'), ('simulated',True), ('queued',True), ('proposed',True)])
def test_unexecuted_or_altered_work_is_rejected(completed, key, value):
    work = copy.deepcopy(completed)
    if key in ('status','result_evidence_refs'): work[key] = value
    elif key in ('execution_ref','decision_ref','prediction_ref'): work['result']['decision_identity'][key] = value
    else: work['result'][key] = value
    with pytest.raises(ValueError): lineage(work)


def test_shadow_and_missing_prediction_stay_unexecuted_unknown(tmp_path):
    q = DepartmentWorkQueue(tmp_path)
    item, _ = q.enqueue_step(plan_id='astra_plan_test', step=work_step(shadow=True,
        tenant_id=TENANT, opportunity_id=OPPORTUNITY, prediction_ref=None))
    causal = lineage(item.as_dict())
    assert causal['prediction_ref'] is None and causal['execution_ref'] is None
    assert causal['shadow_only'] and not causal['causal_eligible']
    with pytest.raises(ValueError): validate_causal_lineage({**causal, 'execution_performed':True})


def test_missing_decision_is_not_fabricated():
    work = {'tenant_id':TENANT, 'id':'unidentified', 'commercial_decision_provenance':
            dict(tenant_id=TENANT, opportunity_key=KEY, opportunity_id=OPPORTUNITY)}
    causal = lineage(work)
    assert causal['decision_ref'] is None and causal['prediction_ref'] is None
    assert causal['execution_ref'] is None and not causal['causal_eligible']


@pytest.mark.parametrize('key', ['tenant_id','opportunity_id'])
def test_queue_same_work_cannot_silently_change_scope(completed,tmp_path,key):
    from empire_os.department_work_queue import DepartmentWorkQueueError
    values=dict(tenant_id=TENANT,opportunity_id=OPPORTUNITY)
    values[key]='wrong'
    with pytest.raises(DepartmentWorkQueueError):
        DepartmentWorkQueue(tmp_path).enqueue_step(plan_id='astra_plan_test',step=work_step(shadow=False,**values))


@pytest.mark.parametrize('change', [lambda c:c.update(execution_authority='execute'),
    lambda c:c.update(shadow_only='false'), lambda c:c.update(hidden_reasoning='secret'),
    lambda c:c.update(prediction_ref=[]), lambda c:c.pop('decision_ref')])
def test_malformed_lineage_fails_closed(completed, change):
    causal = lineage(completed);change(causal)
    with pytest.raises(ValueError): validate_causal_lineage(causal)


@pytest.mark.parametrize('key', ['tenant_id','opportunity_id','opportunity_key','prediction_ref','decision_ref','execution_ref'])
def test_v2b_rejects_contradictory_outcome_or_work_lineage(completed, key):
    rows = records(completed)
    rows[1]['evidence']['causal_lineage'][key] = 'wrong'
    with pytest.raises(ValueError): feedback(completed, rows)


@pytest.mark.parametrize('part', ['payment','fulfilment','revenue','synthetic','forecast','future_payment','future_outcome',
                                'future_recognition','future_cost','future_execution','wrong_revenue_lineage',
                                'payment_tenant','order_tenant','outcome_tenant','revenue_tenant','payment_synthetic','score_as_revenue'])
def test_partial_false_or_future_truth_never_verifies_win(completed, part):
    work = copy.deepcopy(completed)
    order,outcome,payment,event = records(work)
    if part=='payment': payment.pop('verified_at')
    if part=='fulfilment': order.pop('delivered_at');order['state']='accepted'
    if part=='revenue': event=None
    if part=='synthetic': outcome['synthetic']=True
    if part=='forecast': outcome['forecast_derived']=True
    if part=='future_payment': payment['verified_at']='2099-01-01T00:00:00+00:00'
    if part=='future_outcome': outcome['recorded_at']='2099-01-01T00:00:00+00:00'
    if part=='future_recognition': event['created_at']='2099-01-01T00:00:00+00:00'
    if part=='future_cost': event['payload']['actual_cost_evidence']['acquisition_cost']['observed_at']='2099-01-01T00:00:00+00:00'
    if part=='future_execution': work['updated_at']='2099-01-01T00:00:00+00:00'
    if part=='wrong_revenue_lineage': event['payload']['causal_lineage']['execution_ref']='wrong'
    if part=='payment_tenant': payment['tenant_id']='wrong'
    if part=='order_tenant': order['tenant_id']='wrong'
    if part=='outcome_tenant': outcome['tenant_id']='wrong'
    if part=='revenue_tenant': event['tenant_id']='wrong'
    if part=='payment_synthetic': payment['synthetic']=True
    if part=='score_as_revenue': event['amount_cents']=0.99
    with pytest.raises(ValueError): feedback(work, (order,outcome,payment,event))


@pytest.mark.parametrize('part', ['prediction','execution','recommendation','expected_revenue'])
def test_provenance_does_not_manufacture_outcome(completed, part):
    order,outcome,payment,event=records(completed)
    outcome={'fulfilment_order_id':ORDER, part:lineage(completed)}
    with pytest.raises(ValueError): feedback(completed,(order,outcome,payment,event))


def test_full_runtime_handoff_reaches_calibration_memory_astra(completed):
    original=copy.deepcopy(completed)
    f=feedback(completed)
    prediction=dict(tenant_id=TENANT, opportunity_key=KEY, prediction_ref=f['prediction_ref'],
        prediction_type='conversion_probability', predicted_probability=0.6,
        predicted_at='2026-10-01T12:00:00+00:00', horizon_until='2026-10-06T12:00:00+00:00',
        evidence_refs=[f['prediction_ref']])
    c=review_commercial_prediction(prediction=prediction,feedback=f,tenant_id=TENANT,as_of=NOW)
    m=build_economic_memory_snapshot(executive_evaluation={},department_work=[completed],
        cortex_learning={'packets':[f['cortex_packet']]},verified_feedback=[f],calibration_reviews=[c],tenant_id=TENANT,as_of=NOW)
    assert m['decision_outcome_attribution_count']==1
    attribution=m['decision_outcome_attributions'][0]
    for key in ('prediction_ref','decision_ref','execution_ref','outcome_ref'):
        assert attribution[key]==f[key]
    assert f['outcome_ref']=='canonical:commercial_outcomes:'+records(completed)[1]['id']
    a=build_verified_learning_feedback(m,tenant_id=TENANT,as_of=NOW)
    assert a['shadow_only'] and a['execution_authority']=='none'
    assert completed==original
    assert f==feedback(completed)


def test_no_execution_or_explicit_outcome_link_receives_no_causal_credit(completed):
    f=feedback(completed)
    for key in ('execution_ref','decision_ref'):
        work=copy.deepcopy(completed);work['result']['decision_identity'][key]=None
        m=build_economic_memory_snapshot(executive_evaluation={},department_work=[work],
            cortex_learning={'packets':[f['cortex_packet']]},verified_feedback=[f],tenant_id=TENANT,as_of=NOW)
        assert m['decision_outcome_attribution_count']==0
    f['causal_lineage']=None;f['cortex_packet']['learning_lineage'].pop('causal_lineage')
    m=build_economic_memory_snapshot(executive_evaluation={},department_work=[completed],
        cortex_learning={'packets':[f['cortex_packet']]},verified_feedback=[f],tenant_id=TENANT,as_of=NOW)
    assert m['decision_outcome_attribution_count']==0


class Gateway:
    def __init__(self, rows): self.rows=rows;self.queries=[]
    def query(self, table, columns='*', **kwargs):
        self.queries.append((table,columns,kwargs))
        return copy.deepcopy(self.rows.get(table, []))
    def snapshot(self):
        class Snapshot:
            def as_dict(self): return {'primary_backend':'empiredb'}
        return Snapshot()


def test_canonical_repository_reads_real_id_and_full_evidence(completed, tmp_path):
    order,outcome,payment,event=records(completed)
    g=Gateway({'fulfilment_orders':[order], 'buyers':[{'id':order['buyer_id'],'org_id':TENANT}],
        'commercial_outcomes':[outcome], 'commercial_events':[event], 'bsc_payment_evidence':[payment],
        'bsc_payment_requests':[dict(id='request-1', fulfilment_order_id=ORDER,status='approved',
            approved_at=THEN,approved_by='external',commercial_terms_sha256='b'*64,amount_usdt='100',settlement_mode='direct')]})
    repo=ExecutionBusDataRepository(g)
    f=repo.verified_outcome_feedback(ORDER,tenant_id=TENANT,repo_root=tmp_path,as_of=NOW)
    assert f['outcome_ref']=='canonical:commercial_outcomes:'+outcome['id']
    assert f['prediction_ref']==lineage(completed)['prediction_ref']
    g.rows['buyers'][0]['org_id']='wrong'
    with pytest.raises(ValueError):repo.verified_outcome_feedback(ORDER,tenant_id=TENANT,repo_root=tmp_path,as_of=NOW)


def test_history_projection_preserves_outcome_id_and_evidence():
    class HistoryGateway(Gateway):
        def query(self, table, columns='*', **kwargs):
            super().query(table,columns,**kwargs)
            return [{'id':ORDER}] if table=='fulfilment_orders' else [{'id':'real-outcome','evidence':{'source':'real'}}]
    gateway=HistoryGateway({});repo=ExecutionBusDataRepository(gateway)
    rows=repo.prospect_commercial_outcomes('prospect-1')
    assert rows[0]['id']=='real-outcome'
    assert 'id' in gateway.queries[-1][1].split(',') and 'evidence' in gateway.queries[-1][1].split(',')


def test_real_closer_capacity_boundary_reads_persisted_work(completed, tmp_path):
    from empire_os.closer_reply_worker import run_closer_reply_worker
    from test_closer_reply_worker import FakeRpc
    class LinkedRpc(FakeRpc):
        def __call__(self,name,params):
            result=super().__call__(name,params)
            if name=='get_closer_reply_context':
                result.update(department_work_id=completed['id'], tenant_id=TENANT,
                    opportunity_key=KEY,opportunity_id=OPPORTUNITY,
                    reply_body_text='We cover Austin, can take 10 leads per day, deliver by email.')
            return result
    rpc=LinkedRpc([{'reply_id':'reply-1','classification':'positive','case_id':'case-1'}])
    result=run_closer_reply_worker(rpc,repo_root=tmp_path)
    assert result.errors==()
    evidence=next(params['p_evidence'] for name,params in rpc.calls if name=='record_buyer_capacity_intake')
    assert evidence['causal_lineage']==lineage(completed)
    assert result.as_dict()['actual_revenue'] is False


def test_scoped_handoff_rejects_legacy_backend_before_reads():
    from test_execution_bus_data_repository import FakeGateway
    gateway=FakeGateway()
    with pytest.raises(ValueError,match='EmpireDB'):
        ExecutionBusDataRepository(gateway).verified_outcome_feedback(ORDER,tenant_id=TENANT,repo_root='unused',as_of=NOW)
    assert gateway.queries==[]


def test_verified_shadow_outcome_is_learning_without_causal_execution(tmp_path,monkeypatch):
    monkeypatch.setattr(DepartmentWorkQueue,'_now',staticmethod(lambda:THEN))
    q=DepartmentWorkQueue(tmp_path)
    item,_=q.enqueue_step(plan_id='astra_plan_test',step=work_step(shadow=True,tenant_id=TENANT,opportunity_id=OPPORTUNITY))
    done=q.complete(q.claim_next(),{'adapter':'safe_internal_command','returncode':0},
        evidence_refs=('fixture:completed',),execution_completed=True)
    work=done.as_dict()
    f=feedback(work)
    m=build_economic_memory_snapshot(executive_evaluation={},department_work=[work],
        cortex_learning={'packets':[f['cortex_packet']]},verified_feedback=[f],tenant_id=TENANT,as_of=NOW)
    assert f['verified_outcome'] and f['execution_ref'] is None
    assert f['causal_lineage']['shadow_only'] and not f['causal_lineage']['causal_eligible']
    assert m['outcome_conditioned_memory_count']==1 and m['decision_outcome_attribution_count']==0
