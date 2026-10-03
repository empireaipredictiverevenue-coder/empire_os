#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.business_optimization_automation import (
    run_business_optimization_cycle,
)
from empire_os.business_optimization_sources import (
    materialize_business_optimization_sources,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one bounded Empire business optimization cycle."
    )
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--max-requests", type=int, default=24)
    parser.add_argument("--benchmark-variable-limit", type=int, default=18)
    args = parser.parse_args()

    root = Path(args.repo_root)
    source_readiness = materialize_business_optimization_sources(root)
    result = run_business_optimization_cycle(
        root,
        max_requests=args.max_requests,
        benchmark_variable_limit=args.benchmark_variable_limit,
    )
    result["source_readiness"] = {
        "ready_workload_count": source_readiness.get(
            "ready_workload_count"
        ),
        "blocked_workload_count": source_readiness.get(
            "blocked_workload_count"
        ),
        "generated_request_count": source_readiness.get(
            "generated_request_count"
        ),
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
