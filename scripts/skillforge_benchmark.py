#!/usr/bin/env python3
"""Score supplied paired holdout outputs; never send data or approve a skill."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from empire_os.skillforge_benchmark import HoldoutContractError, score_holdout_file


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--suite', required=True, type=Path)
    options = parser.parse_args()
    try:
        report = score_holdout_file(options.suite)
    except HoldoutContractError as exc:
        print(json.dumps({'status':'BLOCKED', 'reason':str(exc),
                          'execution_authority':'none', 'approved':False}))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report['numeric_gate_pass'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
