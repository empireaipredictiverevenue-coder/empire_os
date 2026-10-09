"""Actual domain implementation replay, never self-asserted skill quality."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import pytest

from empire_os.skillforge_domain_holdouts import (
    DomainHoldoutError, evaluate_domain_file, evaluate_domain_holdout,
)
from scripts.skillforge_domain_holdout import run

ROOT=Path(__file__).resolve().parents[1]
FIXTURES={
    'catalogue': ROOT/'tests/fixtures/skillforge_domain/commercial_catalogue_v1.json',
    'predictive': ROOT/'tests/fixtures/skillforge_domain/predictive_cloud_v1.json',
}


@pytest.mark.parametrize('domain,total,baseline,wins', [
    ('catalogue',22,12,10),('predictive',19,16,3),
])
def test_actual_production_baseline_replay_against_policy_proposal(domain,total,baseline,wins):
    report=evaluate_domain_file(FIXTURES[domain])
    assert report['case_count']==total
    assert report['baseline_correct']==baseline
    assert report['proposed_correct']==total
    assert report['newly_caught_issues']==wins
    assert report['regressions']==0
    assert report['labels_independently_reviewed'] is False
    assert report['skill_quality_verified'] is False
    assert report['agent_execution_performed'] is False
    assert report['proposed_policy_deployed'] is False
    assert report['execution_authority']=='none'


def test_replay_identifies_catalogue_public_false_allows():
    report=evaluate_domain_file(FIXTURES['catalogue'])
    flagged={x['case_id'] for x in report['results'] if x['newly_caught_issue']}
    assert {'missing_price_cents','currency_mismatch','margin_floor_breached',
            'unit_mismatch','missing_product_id'} <= flagged
    for row in report['results']:
        assert row['baseline_prediction'] is None
        assert row['proposed_prediction'] is None


def test_replay_flags_forecast_duplicate_cadence_and_future_leakage():
    report=evaluate_domain_file(FIXTURES['predictive'])
    flagged={x['case_id']:x for x in report['results'] if x['newly_caught_issue']}
    assert set(flagged)=={'duplicate_observation_dates','irregular_daily_cadence',
                          'future_observation_leakage'}
    assert flagged['future_observation_leakage']['proposed_validation']['reason_code'] == 'future_observation_leakage'
    for row in report['results']:
        if row['actual_baseline']['decision']=='allow' and row['proposed_validation']['decision']=='allow':
            assert row['baseline_prediction']==row['proposed_prediction']


def test_case_mutation_cannot_claim_new_independent_label_review():
    payload=json.loads(FIXTURES['catalogue'].read_text())
    payload['cases'][0]['expected_decision']='block'
    report=evaluate_domain_holdout(payload)
    assert report['proposed_correct'] < report['case_count']
    assert report['labels_independently_reviewed'] is False
    assert report['skill_quality_verified'] is False


def test_duplicate_and_unbalanced_case_fixtures_fail_closed():
    payload=json.loads(FIXTURES['catalogue'].read_text())
    payload['cases'][1]['id']=payload['cases'][0]['id']
    with pytest.raises(DomainHoldoutError,match='duplicate_holdout_case'):
        evaluate_domain_holdout(payload)
    payload=json.loads(FIXTURES['catalogue'].read_text())
    for case in payload['cases']:
        case['expected_decision']='block'
    with pytest.raises(DomainHoldoutError,match='unbalanced_holdout_cases'):
        evaluate_domain_holdout(payload)


def test_fake_provenance_and_external_symlink_rejected(tmp_path):
    payload=json.loads(FIXTURES['catalogue'].read_text())
    payload['data_provenance']='independently_verified_real_customer'
    with pytest.raises(DomainHoldoutError,match='unreviewed_provenance'):
        evaluate_domain_holdout(payload)
    link=tmp_path/'fixture.json';link.symlink_to(FIXTURES['catalogue'])
    with pytest.raises(DomainHoldoutError,match='invalid_fixture_path'):
        evaluate_domain_file(link)


@pytest.mark.parametrize('domain',[ 'catalogue','predictive'])
def test_operator_default_is_read_only_and_scope_identified(domain):
    result=run(domain)
    assert result['stored'] is False
    assert result['not_a_full_business_pipeline_test'] is True
    assert result['baseline_module_sha256']
    assert result['evaluated_as']=='author_proposed_safety_contract_not_validated_agent_skill'
    assert result['proposed_policy_deployed'] is False


def test_append_only_private_reporting_is_idempotent_and_non_approving(tmp_path):
    # Use an isolated repo root with only sources/fixtures, never the live runtime.
    src=ROOT/'empire_os/commercial_product_catalog.py'
    fixture=FIXTURES['catalogue']
    (tmp_path/'empire_os').mkdir()
    (tmp_path/'empire_os/commercial_product_catalog.py').write_bytes(src.read_bytes())
    target=tmp_path/'tests/fixtures/skillforge_domain/commercial_catalogue_v1.json'
    target.parent.mkdir(parents=True)
    target.write_bytes(fixture.read_bytes())
    first=run('catalogue',save_private=True,root=tmp_path)
    second=run('catalogue',save_private=True,root=tmp_path)
    assert first['stored'] is True
    assert second['stored'] is True
    directory=tmp_path/'runtime/skillforge/domain_holdouts'
    files=list(directory.iterdir())
    assert len(files)==1
    assert files[0].stat().st_mode & 0o777 == 0o600
    report=json.loads(files[0].read_text())
    assert report['skill_quality_verified'] is False
    assert report['approved'] is False


def test_review_report_links_only_matching_existing_skillforge_drafts(tmp_path):
    (tmp_path/'empire_os').mkdir()
    (tmp_path/'empire_os/commercial_product_catalog.py').write_bytes(
        (ROOT/'empire_os/commercial_product_catalog.py').read_bytes())
    target=tmp_path/'tests/fixtures/skillforge_domain/commercial_catalogue_v1.json'
    target.parent.mkdir(parents=True)
    target.write_bytes(FIXTURES['catalogue'].read_bytes())
    # One preserved, structurally valid review draft (not approved).
    from empire_os.skillforge_proposals import _draft_markdown
    root = tmp_path/'runtime/skillforge/proposals/skill_proposal_abc'
    root.mkdir(parents=True)
    spec = {
        'schema_version':'empire.skillforge.proposal.v1',
        'proposal_id':'skill_proposal_abc',
        'component':'commercial_product_catalog',
        'adapter':'safe_internal_command','checkpoint':3,'evidenced_work_count':3,
        'proposed_skill_name':'empire-learned-commercial-product-catalog',
        'observed_work_set_sha256':'f'*64,
        'status':'DRAFT_REVIEW_REQUIRED','approved':False,
        'skill_available_to_agents':False,'execution_authority':'none',
    }
    (root/'manifest.json').write_text(json.dumps(spec))
    (root/'SKILL.md').write_text(_draft_markdown(spec))
    report=run('catalogue', root=tmp_path)
    assert report['linked_skillforge_review_draft_ids']==['skill_proposal_abc']
    assert report['next_required_reviews']
    assert report['approved'] is False


def test_malformed_forecast_fixture_fails_closed_without_traceback():
    payload=json.loads(FIXTURES['predictive'].read_text())
    payload['cases'][0].pop('horizon_days')
    with pytest.raises(DomainHoldoutError,match='invalid_forecast_case'):
        evaluate_domain_holdout(payload)


def test_nonfinite_input_is_rejected_by_proposal_and_report_remains_valid_json():
    payload=json.loads(FIXTURES['predictive'].read_text())
    sample=next(x for x in payload['cases'] if x['id']=='seven_day_uptrend')
    sample['points'][0]['value']=float('nan')
    sample['expected_decision']='block'
    result=evaluate_domain_holdout(payload)
    inspected=next(x for x in result['results'] if x['case_id']=='seven_day_uptrend')
    assert inspected['proposed_validation']['decision']=='block'
    assert inspected['proposed_validation']['reason_code']=='invalid_metric_value'
    assert inspected['actual_baseline']['decision']=='allow'
    assert inspected['baseline_prediction'] == 0.0  # current baseline clamps a NaN-derived estimate
    # Prevent emitting JSON NaN/Infinity tokens into downstream review files.
    json.dumps(result,allow_nan=False)
