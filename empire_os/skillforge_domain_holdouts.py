"""Read-only domain contract replay for SkillForge review.

Runs actual EmpireOS catalogue/forecast code against non-sensitive authored
fixtures, alongside an isolated stricter *proposal*. This measures contract
coverage, NOT agent skill improvement, live predictive accuracy or independent
label provenance. No imports of gateways, no DB, external calls or runtime writes.
"""
from __future__ import annotations

from datetime import date
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from typing import Any

from empire_os.commercial_product_catalog import assess_catalog_item, public_catalog_projection
from empire_os.predictive_cloud_v3 import ObservedMetricPoint, forecast_observed_metric

DOMAINS = frozenset(('commercial_product_catalog', 'predictive_cloud_opportunity_loop'))
CASE_ID = re.compile(r'^[a-z][a-z0-9_]{2,70}$')
MAX_FIXTURE = 250_000


class DomainHoldoutError(ValueError):
    pass


def _decision(allowed: bool, reason: str) -> dict[str, str]:
    return {'decision': 'allow' if allowed else 'block', 'reason_code': reason}


def _catalog_baseline(row: dict[str, Any]) -> dict[str, str]:
    assessed = assess_catalog_item(row)
    ready = assessed['binding_terms_ready'] is True
    public = public_catalog_projection({'products': [assessed]})
    if ready and public['count'] != 1:
        return _decision(False, 'public_projection_missing')
    if not ready and public['count'] != 0:
        return _decision(True, 'unexpected_public_exposure')
    return _decision(ready, 'verified' if ready else assessed['readiness_blockers'][0])


def _catalog_proposed(row: dict[str, Any]) -> dict[str, str]:
    """Extra evidence checks for review; NEVER invoked by production readers."""
    original = _catalog_baseline(row)
    if original['decision'] != 'allow':
        return original
    if not isinstance(row.get('product_code'), str) or not row['product_code'].strip():
        return _decision(False, 'missing_product_identity')
    price = row.get('price_basis')
    acquisition = row.get('acquisition_cost_basis')
    fulfilment = row.get('fulfilment_cost_basis')
    policy = row.get('margin_policy')
    for name, basis in (('price', price), ('acquisition', acquisition), ('fulfilment', fulfilment)):
        if not isinstance(basis, dict):
            return _decision(False, f'invalid_{name}_basis')
        cents = basis.get('amount_cents')
        if type(cents) is not int or cents < 0 or (name == 'price' and cents == 0):
            return _decision(False, f'invalid_{name}_amount')
        if not isinstance(basis.get('currency'), str) or not basis['currency']:
            return _decision(False, f'missing_{name}_currency')
        if not isinstance(basis.get('unit'), str) or not basis['unit']:
            return _decision(False, f'missing_{name}_unit')
    currency = row.get('currency')
    if not isinstance(currency, str) or any(
        basis['currency'] != currency for basis in (price, acquisition, fulfilment)
    ):
        return _decision(False, 'basis_currency_mismatch')
    if len({price['unit'], acquisition['unit'], fulfilment['unit']}) != 1:
        return _decision(False, 'basis_unit_mismatch')
    floor = policy.get('minimum_margin_bps') if isinstance(policy, dict) else None
    if type(floor) is not int or not 0 <= floor <= 10000:
        return _decision(False, 'invalid_margin_policy_floor')
    realized_margin_bps = 10000 * (
        price['amount_cents'] - acquisition['amount_cents'] - fulfilment['amount_cents']
    ) / price['amount_cents']
    if realized_margin_bps < floor:
        return _decision(False, 'margin_floor_breached')
    return _decision(True, 'verified')


def _forecast_baseline(case: dict[str, Any]) -> tuple[dict[str, str], float | None]:
    try:
        rows = [ObservedMetricPoint(date.fromisoformat(x['date']), x['value'], x['source'])
                for x in case['points']]
        output = forecast_observed_metric(
            metric=case['metric'], points=rows, horizon_days=case['horizon_days'],
        )
        if not output.available:
            return _decision(False, 'insufficient_history'), None
        prediction = output.predicted_value
        if (type(prediction) not in (int, float)
            or not math.isfinite(prediction)):
            return _decision(True, 'non_finite_forecast_output'), None
        return _decision(True, 'observed_forecast_available'), prediction
    except (ValueError, TypeError, OverflowError, ZeroDivisionError, KeyError, AttributeError):
        return _decision(False, 'invalid_forecast_evidence'), None


def _forecast_proposed(case: dict[str, Any]) -> tuple[dict[str, str], float | None]:
    """Calendar integrity and leakage checks proposed for review only."""
    baseline, estimate = _forecast_baseline(case)
    if baseline['decision'] != 'allow':
        return baseline, estimate
    dates = []
    for point in case['points']:
        try:
            stamp = date.fromisoformat(point['date'])
            value = point['value']
        except (TypeError, KeyError, ValueError):
            return _decision(False, 'invalid_forecast_evidence'), None
        if (type(value) not in (float, int) or not math.isfinite(value)
            or value < 0):
            return _decision(False, 'invalid_metric_value'), None
        dates.append(stamp)
    if len(set(dates)) != len(dates):
        return _decision(False, 'duplicate_observation_date'), None
    ordered = sorted(dates)
    if any((later - earlier).days != 1 for earlier, later in zip(ordered, ordered[1:])):
        return _decision(False, 'non_daily_observation_cadence'), None
    try:
        as_of = date.fromisoformat(case['as_of_date'])
    except (TypeError, ValueError, KeyError):
        return _decision(False, 'missing_as_of_date'), None
    if ordered[-1] > as_of:
        return _decision(False, 'future_observation_leakage'), None
    if type(estimate) not in (int, float) or not math.isfinite(estimate):
        return _decision(False, 'non_finite_forecast'), None
    return baseline, estimate


def evaluate_domain_holdout(payload: dict[str, Any]) -> dict[str, Any]:
    """Actual baseline-vs-proposed policy replay; no learned skill is executed."""
    if not isinstance(payload, dict) or payload.get('schema_version') != 'empire.skillforge.domain_holdout.v1':
        raise DomainHoldoutError('invalid_fixture_contract')
    domain = payload.get('domain')
    items = payload.get('cases')
    if domain not in DOMAINS or not isinstance(items, list) or not 10 <= len(items) <= 80:
        raise DomainHoldoutError('invalid_domain_or_case_count')
    if payload.get('data_provenance') != 'authored_synthetic_contract_cases':
        raise DomainHoldoutError('unreviewed_provenance')
    results = []
    ids: set[str] = set()
    negative = 0
    for case in items:
        if not isinstance(case, dict) or not CASE_ID.fullmatch(str(case.get('id') or '')):
            raise DomainHoldoutError('invalid_case_identity')
        if case['id'] in ids:
            raise DomainHoldoutError('duplicate_holdout_case')
        ids.add(case['id'])
        expected = case.get('expected_decision')
        if expected not in ('allow', 'block') or case.get('split') != 'holdout':
            raise DomainHoldoutError('invalid_expected_decision_or_split')
        negative += expected == 'block'
        if domain == 'commercial_product_catalog':
            if not isinstance(case.get('row'), dict):
                raise DomainHoldoutError('invalid_catalog_case')
            baseline = _catalog_baseline(case['row'])
            proposed = _catalog_proposed(case['row'])
            baseline_value = proposed_value = None
        else:
            if (not isinstance(case.get('points'), list) or len(case['points']) > 60
                or not isinstance(case.get('metric'), str)
                or type(case.get('horizon_days')) is not int
                or not isinstance(case.get('as_of_date'), str)):
                raise DomainHoldoutError('invalid_forecast_case')
            if any(not isinstance(point, dict) for point in case['points']):
                raise DomainHoldoutError('invalid_forecast_case')
            baseline, baseline_value = _forecast_baseline(case)
            proposed, proposed_value = _forecast_proposed(case)
        baseline_correct = baseline['decision'] == expected
        proposed_correct = proposed['decision'] == expected
        results.append({
            'case_id': case['id'], 'scenario': case.get('scenario_class', 'unspecified'),
            'expected': expected,
            'actual_baseline': baseline, 'proposed_validation': proposed,
            'baseline_correct': baseline_correct,
            'proposed_correct': proposed_correct,
            'newly_caught_issue': not baseline_correct and proposed_correct,
            'regression': baseline_correct and not proposed_correct,
            'baseline_prediction': baseline_value,
            'proposed_prediction': proposed_value,
        })
    if negative < 2 or negative == len(items):
        raise DomainHoldoutError('unbalanced_holdout_cases')
    regressions = sum(x['regression'] for x in results)
    wins = sum(x['newly_caught_issue'] for x in results)
    return {
        'schema_version': 'empire.skillforge.domain_holdout_report.v1',
        'domain': domain, 'case_count': len(results), 'negative_count': negative,
        'baseline_correct': sum(x['baseline_correct'] for x in results),
        'proposed_correct': sum(x['proposed_correct'] for x in results),
        'newly_caught_issues': wins, 'regressions': regressions,
        'policy_replay_pass': regressions == 0 and wins > 0,
        'results': results,
        'fixture_sha256': sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        'data_provenance': 'authored_synthetic_contract_cases',
        'labels_independently_reviewed': False,
        'skill_quality_verified': False, 'agent_execution_performed': False,
        'forecast_accuracy_verified_against_actuals': False,
        'proposed_policy_deployed': False,
        'approved': False, 'execution_authority': 'none',
    }


def evaluate_domain_file(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_FIXTURE:
        raise DomainHoldoutError('invalid_fixture_path')
    try:
        doc = json.loads(p.read_text(encoding='utf-8'))
    except (OSError, ValueError, UnicodeError) as exc:
        raise DomainHoldoutError('unreadable_fixture') from exc
    return evaluate_domain_holdout(doc)
