import json

from empire_os.astra_department_evaluator import evaluate_executive_plan
from empire_os.department_budget_ledger import DepartmentBudgetLedger
from empire_os.department_work_queue import DepartmentWorkQueue


def _step(*, budget=None, step_id='budget_step'):
    req = {'task':'reasoning'}
    if budget is not None:
        req['budget'] = budget
    return {
        'step_id': step_id,
        'goal_key': 'budget_test',
        'department_keys': ['engineering'],
        'target_component': 'commercial_product_catalog',
        'action': 'review',
        'authority': 'internal_write',
        'intelligence_request': req,
        'evidence_refs': ['test:evidence'],
        'success_condition': 'bounded work',
    }


def _claimed(tmp_path, *, budget=None, step_id='budget_step'):
    queue = DepartmentWorkQueue(tmp_path)
    queue.enqueue_step(plan_id='astra_plan_budget', step=_step(budget=budget, step_id=step_id))
    item = queue.claim_next(worker_id='test')
    assert item is not None
    return queue, item


def _policy(tmp_path, *, dept_tokens=None, dept_cost=None, company_tokens=None, company_cost=None):
    path = tmp_path / 'config/department_budgets.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        'schema_version':'empire.department-budget-policy.v1',
        'period':'monthly',
        'company':{'model_tokens':company_tokens,'external_cost_cents':company_cost},
        'departments':{'engineering':{'model_tokens':dept_tokens,'external_cost_cents':dept_cost}},
    }))


def test_no_explicit_resource_request_needs_no_reservation(tmp_path):
    _, item = _claimed(tmp_path)
    result = DepartmentBudgetLedger(tmp_path).reserve(item)
    assert result.allowed is True
    assert result.reason == 'no_explicit_resource_budget_required'
    assert result.reservation_id is None
    assert not (tmp_path/'runtime/departments/budget/reservations.jsonl').exists()


def test_explicit_token_request_blocks_when_department_cap_unconfigured(tmp_path):
    _, item = _claimed(tmp_path, budget={'requested_model_tokens':50})
    result = DepartmentBudgetLedger(tmp_path).reserve(item)
    assert result.allowed is False
    assert result.reason == 'department_token_budget_unconfigured'
    assert result.cash_spend_authority is False


def test_configured_cap_reserves_idempotently_and_denies_over_budget(tmp_path):
    _policy(tmp_path, dept_tokens=100, dept_cost=0)
    queue, first = _claimed(tmp_path, budget={'requested_model_tokens':60}, step_id='first')
    ledger = DepartmentBudgetLedger(tmp_path)
    one = ledger.reserve(first)
    two = ledger.reserve(first)
    assert one.allowed is True and one.reason == 'budget_reserved'
    assert two.allowed is True and two.reason == 'reservation_already_exists'
    assert len(ledger._events()) == 1
    queue.block(first, 'test_terminal')

    _, second = _claimed(tmp_path, budget={'requested_model_tokens':50}, step_id='second')
    denied = ledger.reserve(second)
    assert denied.allowed is False
    assert denied.reason == 'department_token_budget_exhausted'


def test_company_cap_is_enforced_when_configured(tmp_path):
    _policy(tmp_path, dept_tokens=1000, dept_cost=0, company_tokens=80)
    _, item = _claimed(tmp_path, budget={'requested_model_tokens':90})
    denied = DepartmentBudgetLedger(tmp_path).reserve(item)
    assert denied.allowed is False
    assert denied.reason == 'company_token_budget_exhausted'


def test_terminal_reservation_is_consumed_and_evaluator_exposes_budget(tmp_path):
    _policy(tmp_path, dept_tokens=100, dept_cost=0)
    queue, item = _claimed(tmp_path, budget={'requested_model_tokens':40})
    ledger = DepartmentBudgetLedger(tmp_path)
    assert ledger.reserve(item).allowed is True
    queue.complete(item, {'resource_usage':{'model_tokens':55,'external_cost_cents':0}})

    plan = tmp_path/'runtime/astra/executive_latest.json'
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(json.dumps({'plan_id':'astra_plan_budget','plan':[{
        **_step(budget={'requested_model_tokens':40}),
        'auto_dispatch_eligible':True,
        'founder_gate_required':False,
    }]}))
    result = evaluate_executive_plan(tmp_path)
    dept = result['budget']['departments']['engineering']
    assert dept['consumed']['model_tokens'] == 55
    assert dept['headroom']['model_tokens'] == 45
    assert dept['work_attempts'] == 1
    assert result['budget']['cash_spend_authority'] is False
    assert result['budget']['execution_authority'] == 'none'
