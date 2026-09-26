#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from empire_os.astra_department_evaluator import evaluate_executive_plan

def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args=parser.parse_args()
    payload=evaluate_executive_plan(args.repo_root)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
