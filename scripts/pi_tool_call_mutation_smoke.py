#!/usr/bin/env python3
from __future__ import annotations

import json

from empire_os.pi_sandbox_runner import (
    PiSandboxJob,
    run_pi_sandbox_job,
)


def main() -> int:
    marker = "tests/pi_tool_call_smoke_marker.txt"
    result = run_pi_sandbox_job(
        "/srv/empire_os",
        PiSandboxJob(
            job_id="pi-tool-call-mutation-smoke",
            prompt=(
                "You must use Pi's write tool exactly once to create the file "
                f"{marker} containing exactly: PI_TOOL_CALL_OK followed by a newline. "
                "Do not modify any other file. After writing it, stop."
            ),
            allowed_paths=(marker,),
            lease_resources=("domain:pi_tool_call_smoke",),
            pytest_targets=(),
            max_runtime_seconds=180,
            require_changes=True,
            publish_proposal=False,
        ),
    )
    print(json.dumps(result, indent=2, sort_keys=True))

    changed = result.get("changed_paths") or []
    tool_count = int(result.get("tool_execution_count") or 0)
    ok = (
        result.get("status") == "MUTATION_SMOKE_PASSED"
        and marker in changed
        and tool_count >= 1
        and result.get("production_mutation") is False
        and result.get("execution_authority") == "none"
    )
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
