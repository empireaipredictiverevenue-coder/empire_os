#!/usr/bin/env python3
"""One SkillForge acceptance command: fail-closed readiness + optional gauntlet.

This CLI does not approve, train, promote, send, fund, access production data,
or start services. The gauntlet executes only local isolated test fixtures.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from empire_os.skillforge_completion import completion_report

GAUNTLET_TESTS = (
    'tests/coder',
    'tests/test_no_sim_runtime.py',
    'tests/test_agent_intelligence_coder_bridge.py',
    'tests/test_email_expert_skillforge.py',
    'tests/test_legacy_skillforge_loader.py',
    'tests/test_synthetic_agent_skillforge.py',
    'tests/test_skillforge_benchmark.py',
    'tests/test_skillforge_promotion.py',
    'tests/test_skillforge_sandbox.py',
    'tests/test_skillforge_proposals.py',
    'tests/test_skillforge_learning.py',
    'tests/test_skillforge.py',
    'tests/test_skillforge_evaluation.py',
    'tests/test_skillforge_domain_holdouts.py',
    'tests/test_skillforge_completion.py',
    'tests/test_skill_review.py',
    'tests/test_skill_exchange.py',
    'tests/test_skill_trust.py',
    'tests/test_astra_skill_advice.py',
    'tests/test_astra_dispatcher.py',
    'tests/test_department_skill_preflight.py',
    'tests/test_department_worker.py',
    'tests/test_commercial_product_catalog.py',
    'tests/test_predictive_cloud_v3.py',
)


def run_gauntlet(repo_root: Path) -> dict:
    """Bound the pytest workload and redact environment to minimum local keys."""
    from empire_os.coder.policy import filtered_environment
    if not all((repo_root/path).exists() for path in GAUNTLET_TESTS):
        return {'passed': False, 'reason': 'missing_test_contract', 'execution_authority': 'none'}
    env = filtered_environment()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    command = [sys.executable, '-m', 'pytest', '-q', '--tb=short',
               '--disable-warnings', '-p', 'no:cacheprovider',
               '--maxfail=1', *GAUNTLET_TESTS]
    try:
        run = subprocess.run(command, cwd=str(repo_root), env=env,
                             capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return {'passed': False, 'reason': 'test_execution_unavailable',
                'execution_authority': 'none'}
    lines = (run.stdout or '').splitlines()
    # Report the summary only. Do not expose raw failing output, stack traces,
    # fixtures, credentials or customer records in the acceptance JSON.
    return {'passed': run.returncode == 0, 'exit_code': run.returncode,
            'summary': ' | '.join(lines[-3:])[:500],
            'selection_count': len(GAUNTLET_TESTS),
            'execution_authority': 'none', 'tests_only': True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--require-live-learning', action='store_true',
                        help='Require canonical observed work and pending review drafts')
    parser.add_argument('--gauntlet', action='store_true',
                        help='Run the bounded offline safety and integration regression suite')
    options = parser.parse_args()
    root = Path.cwd()
    result = completion_report(root,
        require_runtime_observations=options.require_live_learning)
    if options.gauntlet:
        gauntlet = run_gauntlet(root)
        result['gauntlet'] = gauntlet
        result['engineering_checks_total'] += 1
        result['engineering_checks_passed'] += bool(gauntlet['passed'])
        result['engineering_checks'].append({
            'name': 'bounded_offline_regression_gauntlet',
            'passed': gauntlet['passed'],
            'detail': gauntlet.get('summary') or gauntlet.get('reason', 'unknown'),
        })
        result['engineering_verified'] = result['engineering_verified'] and gauntlet['passed']
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result['engineering_verified'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
