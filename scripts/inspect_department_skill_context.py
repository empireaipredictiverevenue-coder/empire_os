#!/usr/bin/env python3
"""Read-only skill-context preflight; never claims or executes queue work."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from empire_os.skill_exchange import SKILLS_ROOT
from empire_os.skill_trust import SkillTrustError, load_work_item_skill_context, read_trust_registry


def inspect(*, departments: list[str], trust_registry: Path, skills_root: Path = SKILLS_ROOT,
            target_component: str | None = None) -> dict:
    try:
        registry = read_trust_registry(trust_registry)
        trust_status = 'registry_loaded'
    except SkillTrustError as exc:
        registry = None
        trust_status = str(exc)
    result = load_work_item_skill_context(
        {'id': 'preflight', 'department_keys': departments, 'target_component': target_component},
        root=skills_root, registry=registry,
    )
    # No skill bodies or untrusted instructions in diagnostic output.
    return {'mode': 'OBSERVE', 'execution_authority': 'none',
            'trust_status': trust_status, 'loaded_skill_count': len(result['skills']),
            'context_bytes': result['context_bytes'],
            'loaded_skills': [{'name': s['name'], 'sha256': s['sha256']} for s in result['skills']],
            'rejected': result['rejected'], 'scripts_executed': False,
            'queue_mutated': False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--department', action='append', required=True)
    parser.add_argument('--component', default=None, help='Exact target component, no fuzzy matching')
    parser.add_argument('--trust-registry', type=Path, default=Path('config/skill_trust_registry.json'))
    args = parser.parse_args()
    result = inspect(departments=args.department, trust_registry=args.trust_registry,
                     target_component=args.component)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['loaded_skill_count'] and not result['rejected'] else 2

if __name__ == '__main__':
    raise SystemExit(main())
