#!/usr/bin/env python3
"""Read-only static candidate evaluation; no approval or execution."""
import json
from empire_os.skillforge import catalogue
from empire_os.skillforge_evaluation import evaluate_skill

if __name__ == '__main__':
    names = [s['name'] for s in catalogue()['skills']]
    result = [evaluate_skill(name) for name in names]
    print(json.dumps({'product': 'Empire SkillForge', 'mode': 'OBSERVE',
                      'evaluated': len(result), 'static_passed': sum(r['passed'] for r in result),
                      'agent_quality_verified': False, 'approved': False,
                      'results': result}, sort_keys=True))
