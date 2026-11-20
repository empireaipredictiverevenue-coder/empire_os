"""Security and read-only routing checks for enterprise skill candidate preview."""
from pathlib import Path
import importlib.util

from empire_os.skill_exchange import PORTFOLIO_TASK_SKILLS, COMPONENT_TASKS

MODULE = Path(__file__).resolve().parents[1] / 'scripts/review_enterprise_skill_candidates_20261120.py'
spec = importlib.util.spec_from_file_location('enterprise_skill_preview', MODULE)
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


def test_portfolio_routes_have_exact_component_selector():
    assert len(PORTFOLIO_TASK_SKILLS) == 8
    for task, (_, names) in PORTFOLIO_TASK_SKILLS.items():
        assert len(names) >= 2
        assert task in COMPONENT_TASKS.values()


def test_license_classifier_distinguishes_in_house_apache_and_restricted(tmp_path):
    internal = '---\nlicense: Internal EmpireOS authored instructions; ownership review required before redistribution.\n---\n'
    assert preview.licence_status(tmp_path, internal) == 'empire_internal_restricted_redistribution'
    assert preview.licence_status(tmp_path, '# No license') == 'licence_undocumented_hold'
    (tmp_path / 'LICENSE.txt').write_text('Apache License\nVersion 2.0, January 2004')
    assert preview.licence_status(tmp_path, '# External') == 'apache_2_0_documented'
    (tmp_path / 'LICENSE.txt').write_text('Use of these materials is governed by your agreement with Anthropic regarding use of Anthropic services')
    assert preview.licence_status(tmp_path, '# External') == 'anthropic_service_terms_requires_legal_review'


def test_isolated_review_preserves_real_registry_and_external_authority():
    before = preview.TRUST.read_bytes()
    report = preview.inspect()
    assert preview.TRUST.read_bytes() == before
    assert report['production_registry_unchanged'] is True
    assert report['production_approved_skill_count'] == 12
    assert report['exact_digest_content_trust_count'] == 12
    assert report['status'] == 'ADVISORY_CONTENT_TRUST_ACTIVE_INDEPENDENT_QUALITY_HOLD'
    assert report['production_agent_execution_verified'] is False
    assert report['candidate_count'] == 16
    assert report['in_memory_eligible_count'] > 0
    assert report['execution_authority'] == 'none'
    assert report['scripts_executed'] is False
    assert report['founder_exact_digest_approval_recorded'] is False
    assert report['independent_holdout_verification_complete'] is False
    assert report['production_skill_activation_verified'] is False
    assert report['snapshot_work_item_count'] >= 1
    assert any(item['in_memory_loaded_count'] > 0 for item in report['existing_work_item_checks'])
    assert all(r['manual_review_status'] == 'manual_review_required' for r in report['candidates'])
    for r in report['candidates']:
        if r['in_memory_test_eligible']:
            assert r['source_state'] == 'tracked_clean'
            assert r['licence'] == 'empire_internal_restricted_redistribution'
            assert r['static_contract_pass']


def test_third_party_never_marked_eligible_without_separate_legal_review():
    report = preview.inspect()
    by_name = {r['name']:r for r in report['candidates']}
    for name in ('pdf','xlsx','doc-coauthoring','skill-creator'):
        assert by_name[name]['in_memory_test_eligible'] is False
        assert by_name[name]['decision'] == 'HOLD'
    for name in ('frontend-design', 'webapp-testing'):
        assert by_name[name]['in_memory_test_eligible'] is False
        assert by_name[name]['production_approval'] is True
        assert by_name[name]['decision'] == 'CONTENT_TRUST_PINNED_QUALITY_UNVERIFIED'


def test_real_work_inventory_exposes_no_unearned_holdout_or_agent_quality():
    rows = preview.real_evidence_review_inventory()
    assert len(rows) == 8
    assert sum(len(row['sample']) for row in rows) > 0
    assert all(row['quality_holdout_ready'] is False for row in rows)
    assert all(row['independently_labelled_case_count'] == 0 for row in rows)
    assert all(row['agent_baseline_outputs_available'] is False for row in rows)
    assert all(row['agent_candidate_outputs_available'] is False for row in rows)
    for row in rows:
        for case in row['sample']:
            assert len(case['source_work_sha256']) == 64
            assert len(case['source_record_sha256']) == 64
            assert case['quality_gold_label_present'] is False
            assert 'source_ref' not in case and 'expected' not in case


def test_real_case_digest_replay_is_read_only_and_requires_independent_labels():
    result = preview.verify_selected_work_sources(preview.real_evidence_review_inventory())
    counts = result['counts']
    assert counts['cases'] > 0
    assert counts['source_digest_verified'] == counts['cases']
    assert counts['missing_source_or_digest_mismatch'] == 0
    assert result['all_source_digests_verified'] is True
    assert result['independent_label_count'] == 0
    assert result['holdout_quality_verified'] is False
    assert result['external_actions'] is False
    assert all(case['independent_gold_label'] is None for case in result['cases'])
    assert all(case['paired_agent_outputs_available'] is False for case in result['cases'])
    assert all(case['independent_source_receipt_readback'] is False for case in result['cases'])
    assert counts['negative_cases_needing_independent_label'] > 0
    assert counts['negative_missing_result_refs'] > 0



def test_source_integrity_mismatch_fails_closed(tmp_path):
    import json
    from hashlib import sha256
    p = tmp_path / 'runtime/departments/work/done' / ('dept_work_' + 'a' * 24 + '.json')
    p.parent.mkdir(parents=True)
    content = {'id': p.stem, 'status': 'DONE', 'result_evidence_refs': ['evidence:source'], 'error': None}
    p.write_text(json.dumps(content))
    sample = {'name': 'empire-evidence-verification', 'sample': [
        {'source_work_sha256': sha256(p.stem.encode()).hexdigest(),
         'source_record_sha256': '0' * 64,
         'queue_status': 'DONE'}]}
    result = preview.verify_selected_work_sources([sample], repo_root=tmp_path)
    assert result['all_source_digests_verified'] is False
    assert result['counts']['missing_source_or_digest_mismatch'] == 1
    assert result['counts']['positive_with_result_refs_no_error'] == 0


def test_canonical_promotion_preflight_remains_blocked_without_independent_holdout():
    result = preview.inspect()
    checks = result['canonical_promotion_preflight']
    assert len(checks) == result['in_memory_eligible_count']
    assert all(check['status'] == 'BLOCKED' for check in checks)
    assert all('independently_labelled_holdout_not_supplied' in check['blocks'] for check in checks)
    assert all(check['promoted'] is False for check in checks)
    assert all(check['founder_approval_recorded'] is False for check in checks)
    assert all(check['independent_performance_verified'] is False for check in checks)
    assert all(check['required_reviews'] for check in checks)
