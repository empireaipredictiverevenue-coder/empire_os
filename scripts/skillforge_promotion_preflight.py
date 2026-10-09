#!/usr/bin/env python3
"""Inspect SkillForge promotion readiness without modifying trust approvals."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from empire_os.skillforge_benchmark import HoldoutContractError, score_holdout_file
from empire_os.skillforge_promotion import promotion_preflight


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--skill-name', required=True)
    parser.add_argument('--suite', type=Path, help='Independent labelled holdout output pairs')
    options = parser.parse_args()
    suite = None
    if options.suite:
        try:
            score_holdout_file(options.suite)
            suite = json.loads(options.suite.read_text(encoding='utf-8'))
        except (HoldoutContractError, OSError, ValueError, UnicodeError) as exc:
            print(json.dumps({'status': 'BLOCKED', 'reason':type(exc).__name__, 'approved':False}))
            return 2
    result = promotion_preflight(
        options.skill_name, suite=suite,
        trust_registry=Path('config/skill_trust_registry.json'),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result['numeric_review_ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
