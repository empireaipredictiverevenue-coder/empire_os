#!/usr/bin/env python3
"""Read-only readiness check: no queue instantiation, no file writes."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
from empire_os.factory_hybrid_review_finalizer_v1 import (
    FinalisationDenied, assess_finalisation, load_root_attested_receipt,
)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--repo-root', type=Path, default=Path('/srv/empire_os'))
    p.add_argument('--work-id', required=True)
    args = p.parse_args()
    wid = args.work_id
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', wid):
        p.error('invalid work id')
    review_dir = args.repo_root.resolve() / 'runtime/departments/work/review'
    source = review_dir / (wid + '.json')
    if not source.is_file() or source.is_symlink():
        print(json.dumps({'allowed': False, 'reason': 'review_record_missing', 'work_id':wid}))
        return 2
    try:
        data = source.read_bytes()
        work = json.loads(data)
        receipt = load_root_attested_receipt(wid)
        outcome = assess_finalisation(work_record=work, record_bytes=data, receipt=receipt)
    except (OSError, ValueError, FinalisationDenied) as exc:
        print(json.dumps({'allowed':False, 'reason':str(exc), 'work_id':wid}))
        return 2
    print(json.dumps(outcome.as_dict(), indent=2, sort_keys=True))
    return 0 if outcome.allowed else 2


if __name__ == '__main__':
    raise SystemExit(main())
