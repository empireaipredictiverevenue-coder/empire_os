#!/usr/bin/env python3
"""Inspect task mappings and metadata without authorizing any skill."""
from __future__ import annotations
import json
from empire_os.skill_exchange import TASK_SKILLS, discover_task_skills
from empire_os.skill_review import review_local_skill

def main() -> int:
    result=[]
    for task in sorted(TASK_SKILLS):
        discovery=discover_task_skills(task)
        result.append({'task':task, 'status':discovery['status'],
                       'skills':[review_local_skill(x['name']) for x in discovery['skills']]})
    print(json.dumps({'mode':'OBSERVE','execution_authority':'none',
                      'approval_performed':False,'tasks':result}, sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
