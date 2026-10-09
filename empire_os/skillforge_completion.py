"""One-pass, read-only Empire SkillForge completion/acceptance report.

Separates verified engineering/runtime contracts from intentionally withheld
human/founder trust approvals and independent business-outcome evidence.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from empire_os.skill_exchange import TASK_SKILLS, SKILLS_ROOT, discover_task_skills
from empire_os.skill_trust import SkillTrustError, load_pinned_skill, read_trust_registry
from empire_os.skillforge import catalogue
from empire_os.skillforge_evaluation import evaluate_skill
from empire_os.skillforge_domain_holdouts import evaluate_domain_file, DomainHoldoutError

_DOMAINS = {
    'commercial_product_catalog': 'commercial_catalogue_v1.json',
    'predictive_cloud_opportunity_loop': 'predictive_cloud_v1.json',
}


def _check(name: str, passed: bool, *, detail: str) -> dict[str, Any]:
    return {'name': name, 'passed': bool(passed), 'detail': detail}


def completion_report(repo_root: str | Path, *,
                      require_runtime_observations: bool = False) -> dict[str, Any]:
    """Review all necessary SkillForge engineering gates exactly once.

    Never executes work, reads credentials, writes approvals, promotes skills,
    or makes an external request. An engineering PASS != approval or revenue.
    """
    root = Path(repo_root).resolve()
    library = root / 'empire_os/skills_library/skills'
    registry_path = root / 'config/skill_trust_registry.json'
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []

    try:
        registry = read_trust_registry(registry_path)
        registry_valid = (registry.get('schema_version') == 'empire.skill_trust.v1'
                          and isinstance(registry.get('approved_skills'), dict))
    except SkillTrustError:
        registry = {}
        registry_valid = False
    checks.append(_check('explicit_trust_registry', registry_valid,
                         detail='requires_valid_registry_and_explicit_pins'))

    approved = registry.get('approved_skills', {}) if registry_valid else {}
    unsafe_approvals: list[str] = []
    for name in approved:
        try:
            if not name.startswith('empire-'):
                raise SkillTrustError('not_empire_owned')
            load_pinned_skill(name, root=library, registry=registry)
        except (SkillTrustError, OSError, ValueError):
            unsafe_approvals.append(name)
    checks.append(_check('all_registry_approvals_load_verified',
                         registry_valid and not unsafe_approvals,
                         detail='invalid_or_unloadable_pins='+str(len(unsafe_approvals))))

    missing_tasks: list[str] = []
    for task, (_, names) in TASK_SKILLS.items():
        selection = discover_task_skills(task, root=library)
        found = {s['name'] for s in selection['skills']}
        if not names or not set(names).issubset(found):
            missing_tasks.append(task)
    checks.append(_check('all_department_skill_routes_resolve', not missing_tasks,
                         detail='unmapped_tasks='+str(len(missing_tasks))))

    try:
        cat = catalogue(root=library, registry_path=registry_path, repo_root=root)
        catalog_ok = True
    except (OSError, ValueError, TypeError):
        cat = {}
        catalog_ok = False
    count = int(cat.get('skill_count', 0)) if catalog_ok else 0
    static_failures: list[str] = []
    if catalog_ok:
        for skill in cat.get('skills', []):
            check = evaluate_skill(skill['name'], root=library)
            if not check['passed'] or check.get('sha256') != skill['sha256']:
                static_failures.append(skill['name'])
    checks.append(_check('owned_skill_static_contracts',
                         catalog_ok and count >= len(TASK_SKILLS) and not static_failures,
                         detail=f'catalogued={count};static_failed={len(static_failures)}'))

    learning = cat.get('learning') if catalog_ok else None
    learning = learning if isinstance(learning, dict) else {}
    validated_obs = learning.get('observation_count', 0)
    invalid_obs = learning.get('invalid_observations', 0)
    truncated_obs = learning.get('inventory_truncated', True)
    learning_ok = (isinstance(validated_obs, int) and validated_obs >= 0
                   and invalid_obs == 0 and truncated_obs is False)
    if require_runtime_observations:
        learning_ok = learning_ok and validated_obs > 0
    checks.append(_check('canonical_learning_provenance', learning_ok,
                         detail=f'validated_observations={validated_obs};invalid={invalid_obs};truncated={truncated_obs}'))

    queue = cat.get('review_queue') if catalog_ok else None
    queue = queue if isinstance(queue, dict) else {}
    drafts = queue.get('draft_count', 0)
    queue_ok = (isinstance(drafts, int) and drafts >= 0
                and queue.get('invalid_drafts') == 0
                and queue.get('inventory_truncated', False) is False)
    if require_runtime_observations:
        queue_ok = queue_ok and drafts > 0
    checks.append(_check('immutable_private_review_drafts', queue_ok,
                         detail=f'valid_drafts={drafts};invalid={queue.get("invalid_drafts")}'))

    replay_summary: list[dict[str, Any]] = []
    replay_ok = True
    for domain, filename in _DOMAINS.items():
        fixture = root / 'tests/fixtures/skillforge_domain' / filename
        try:
            replay = evaluate_domain_file(fixture)
            valid = (replay['domain'] == domain and replay['case_count'] >= 10
                     and replay['negative_count'] >= 2
                     and replay['regressions'] == 0
                     and replay['proposed_correct'] >= replay['baseline_correct']
                     and replay['labels_independently_reviewed'] is False
                     and replay['skill_quality_verified'] is False
                     and replay['proposed_policy_deployed'] is False
                     and replay['execution_authority'] == 'none')
            replay_summary.append({'domain': domain,
                                   'cases': replay['case_count'],
                                   'baseline_correct': replay['baseline_correct'],
                                   'proposed_correct': replay['proposed_correct'],
                                   'newly_caught_issues': replay['newly_caught_issues'],
                                   'independently_verified': False})
        except (OSError, ValueError, KeyError, TypeError, DomainHoldoutError):
            valid = False
            replay_summary.append({'domain': domain, 'status': 'unavailable'})
        replay_ok = replay_ok and valid
    checks.append(_check('domain_evaluation_contracts', replay_ok,
                         detail='domains='+str(len(replay_summary))+';independent_quality_not_claimed'))

    checks.append(_check('no_implicit_skill_approval',
                         catalog_ok and cat.get('approved_count') == len(approved)
                         and all(s.get('trust') == 'approved_pinned' for s in cat.get('skills', [])
                                 if s['name'] in approved),
                         detail='approved_by_registry='+str(len(approved))))

    engineering_verified = all(check['passed'] for check in checks)
    if len(approved) == 0:
        warnings.append('FOUNDER_GATE: no skill approved for production agent loading')
    warnings.append('INDEPENDENT_EVIDENCE_GATE: authored domain labels and agent quality not independently verified')
    warnings.append('RUNTIME_CHANGE_GATE: proposed catalogue and forecast input guards not deployed')
    warnings.append('REVENUE_GATE: learning events and benchmarks are not realized revenue')
    return {
        'schema_version': 'empire.skillforge.completion.v1',
        'product': 'Empire SkillForge', 'mode': 'OBSERVE',
        'engineering_verified': engineering_verified,
        'engineering_checks_passed': sum(x['passed'] for x in checks),
        'engineering_checks_total': len(checks),
        'engineering_checks': checks,
        'skill_count': count,
        'approved_skill_count': len(approved),
        'verified_observation_count': validated_obs,
        'pending_review_draft_count': drafts,
        'domain_replays': replay_summary,
        'founder_or_external_gates': warnings,
        'skill_promoted': False,
        'production_changes_performed': False,
        'independent_quality_verified': False,
        'execution_authority': 'none',
    }
