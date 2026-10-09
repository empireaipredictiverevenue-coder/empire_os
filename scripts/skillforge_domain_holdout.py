#!/usr/bin/env python3
"""Replay authored, non-sensitive domain holdouts against actual EmpireOS code.

Never approves a skill, deploys a proposed policy, accesses the DB or contacts
an inference provider. Optional private evidence write is append-only.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path

from empire_os.skillforge_domain_holdouts import DomainHoldoutError, evaluate_domain_file
from empire_os.skillforge_proposals import proposal_history
from empire_os import commercial_product_catalog, predictive_cloud_v3

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = {
    'catalogue': ROOT/'tests/fixtures/skillforge_domain/commercial_catalogue_v1.json',
    'predictive': ROOT/'tests/fixtures/skillforge_domain/predictive_cloud_v1.json',
}
SOURCES = {
    'catalogue': ROOT/'empire_os/commercial_product_catalog.py',
    'predictive': ROOT/'empire_os/predictive_cloud_v3.py',
}


def run(domain: str, *, save_private: bool = False, root: Path = ROOT) -> dict:
    if domain not in FIXTURES:
        raise DomainHoldoutError('unknown_domain')
    # Read only fixed, reviewable repo fixtures; do not read customer data.
    path = root / FIXTURES[domain].relative_to(ROOT)
    # Code is imported from this checkout, not from an arbitrary report root.
    source = SOURCES[domain]
    module = commercial_product_catalog if domain == 'catalogue' else predictive_cloud_v3
    if (path.is_symlink() or source.is_symlink() or not source.is_file()
        or Path(module.__file__).resolve() != source.resolve()):
        raise DomainHoldoutError('unsafe_or_mismatched_review_source')
    before_code = sha256(source.read_bytes()).hexdigest()
    before_fixture = sha256(path.read_bytes()).hexdigest()
    report = evaluate_domain_file(path)
    if (sha256(source.read_bytes()).hexdigest() != before_code
        or sha256(path.read_bytes()).hexdigest() != before_fixture):
        raise DomainHoldoutError('evaluation_source_changed_during_replay')
    report['baseline_module'] = str(source.relative_to(ROOT))
    report['baseline_module_sha256'] = before_code
    report['fixture_file_sha256'] = before_fixture
    report['pipeline_scope'] = ('catalogue_readiness_projection_only' if domain == 'catalogue'
                                else 'predictive_cloud_v3_directional_forecast_only')
    report['not_a_full_business_pipeline_test'] = True
    report['evaluated_as'] = 'author_proposed_safety_contract_not_validated_agent_skill'
    proposals = proposal_history(root)
    report['linked_skillforge_review_draft_ids'] = sorted(
        item['id'] for item in proposals.get('drafts', [])
        if item.get('component') == report['domain']
    )
    report['next_required_reviews'] = [
        'validate_authored_labels_independently_against_documented_policy',
        'review_canonical_data_contract_and_authoritative_empiredb_validation',
        'verify_model_baseline_and_candidate_on_representative_holdout_tasks',
        'establish_actual_forecast_accuracy_from_subsequently_observed_outcomes',
        'approve_any_runtime_policy_change_under_separate_founder_gate',
    ]
    report['stored'] = False
    if save_private:
        directory = root/'runtime/skillforge/domain_holdouts'
        parent = directory.parent
        if parent.is_symlink() or directory.is_symlink():
            raise DomainHoldoutError('unsafe_review_storage')
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if directory.is_symlink() or not directory.is_dir():
            raise DomainHoldoutError('unsafe_review_storage')
        os.chmod(directory, 0o700)
        # Stable report digest excludes the storage flag and avoids changing
        # the source report on later identical runs.
        payload = json.dumps(report, indent=2, sort_keys=True)+'\n'
        suffix = sha256(payload.encode('utf-8')).hexdigest()[:24]
        target = directory / f'{domain}_{suffix}.json'
        if target.is_symlink():
            raise DomainHoldoutError('unsafe_existing_review')
        try:
            fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        except FileExistsError:
            if target.read_bytes() != payload.encode('utf-8'):
                raise DomainHoldoutError('review_digest_collision_or_tamper')
            report['stored'] = True
        else:
            with os.fdopen(fd, 'wb') as f:
                f.write(payload.encode('utf-8'))
                f.flush()
                os.fsync(f.fileno())
            report['stored'] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='Tool-free local domain contract replay')
    parser.add_argument('--domain', choices=('catalogue', 'predictive', 'both'), default='both')
    parser.add_argument('--save-private', action='store_true')
    args = parser.parse_args()
    reports = []
    for domain in ('catalogue', 'predictive') if args.domain == 'both' else (args.domain,):
        try:
            reports.append(run(domain, save_private=args.save_private))
        except (DomainHoldoutError, OSError, ValueError) as exc:
            print(json.dumps({'status':'BLOCKED','reason':type(exc).__name__,
                              'approval':False,'execution_authority':'none'}))
            return 2
    # Print bounded summaries by default; the JSON files store full synthetic
    # case-by-case evidence when explicitly requested.
    summary = [{key: row[key] for key in (
        'domain', 'pipeline_scope', 'case_count', 'negative_count',
        'baseline_correct', 'proposed_correct', 'newly_caught_issues',
        'regressions', 'fixture_sha256', 'fixture_file_sha256', 'baseline_module_sha256',
        'labels_independently_reviewed', 'skill_quality_verified',
        'proposed_policy_deployed', 'execution_authority', 'stored',
        'linked_skillforge_review_draft_ids',
    )} for row in reports]
    print(json.dumps({'mode':'OBSERVE','result_type':'domain_contract_replay',
                      'results':summary,'skill_promoted':False,
                      'independent_agent_quality_verified':False}, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
