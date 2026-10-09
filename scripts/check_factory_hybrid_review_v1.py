#!/usr/bin/env python3
"""Read-only factory review queue diagnostic; never instantiates queue runtime."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from empire_os.factory_hybrid_review_v1 import assess_held_review


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo-root', type=Path, default=Path('/srv/empire_os'))
    parser.add_argument('--work-id', required=True)
    args = parser.parse_args()
    work_id = args.work_id
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', work_id):
        parser.error('invalid work id')
    root = args.repo_root.resolve() / 'runtime' / 'departments' / 'work'
    entries = [root / kind / (work_id + '.json') for kind in ('blocked', 'review')]
    found = [p for p in entries if p.is_file() and not p.is_symlink()]
    if len(found) != 1:
        print(json.dumps({'status': 'BLOCKED', 'reason': 'work_identity_missing_or_ambiguous',
                          'queue_mutated': False, 'department_work_done': False}))
        return 2
    try:
        payload = json.loads(found[0].read_text(encoding='utf-8'))
    except (OSError, ValueError):
        print(json.dumps({'status': 'BLOCKED', 'reason': 'work_record_invalid',
                          'queue_mutated': False, 'department_work_done': False}))
        return 2
    if not isinstance(payload, dict) or payload.get('id') != work_id or payload.get('status') != found[0].parent.name.upper():
        print(json.dumps({'status': 'BLOCKED', 'reason': 'work_record_path_binding_failed',
                          'queue_mutated': False, 'department_work_done': False}))
        return 2
    assessment = assess_held_review(work_item=payload)
    print(json.dumps(assessment.as_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
