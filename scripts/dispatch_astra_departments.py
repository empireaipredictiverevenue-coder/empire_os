#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from empire_os.astra_department_dispatch import dispatch_executive_plan

def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--okf-bundle", default=None,
                        help="Optional private OKF v0.2 research bundle; no execution authority")
    args=parser.parse_args()
    payload=dispatch_executive_plan(args.repo_root, okf_bundle_path=args.okf_bundle)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
